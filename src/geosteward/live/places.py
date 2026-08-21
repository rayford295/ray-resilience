"""Google Places (New) `searchNearby` — the re-derivable regime, for real.

Stdlib only, in the style of `gateway/llm.py`: no SDK, so the dependency is the
HTTP shape rather than a vendor package, and the whole adapter is auditable in
one screen.

**Unverified against the live API.** This has never been executed against
Google's servers: the project has no billing project or key yet (design §10,
blocker 1). The request shape below follows the published Places API (New)
documentation, but "follows the documentation" is not "observed to work", and
the difference is exactly the sort of thing this project refuses to blur. Two
consequences, both deliberate:

  * Every parse failure raises `LiveUnavailable` rather than returning a
    half-built result. If the wire shape differs from what this expects, the
    caller reports an outage — which is true — instead of quietly attesting to
    a response it misread.
  * `tests/test_live_adapters.py` drives this against a local stub, so what is
    tested is this module's own behaviour, not Google's. Nothing here is
    evidence that the integration works end to end, and the design document
    records the measured numbers only once it has run for real.

The request is scoped by H3 cell rather than by the user's coordinates. That is
not a formality: `live_lookup_record` is classified `resolution_cap: tile`, the
recorder refuses a request that cannot name a cell, and deriving the circle
centre from the cell means an exact position never enters the request in the
first place — so it cannot leak into a published record later.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

import h3

from geosteward.live.base import (
    NOT_RETAINED,
    RE_DERIVABLE,
    THIRD_PARTY_RESTRICTED,
    LiveRequest,
    LiveResult,
    LiveUnavailable,
    response_digest,
)

DEFAULT_BASE_URL = "https://places.googleapis.com/v1"

#: Field mask sent to the API, and recorded in the request so a reader replays
#: the same one. Kept to what a facility-context answer needs: no ratings, no
#: reviews, no photos, no phone numbers. Asking for less is both cheaper and a
#: smaller retention question.
DEFAULT_FIELDS: tuple[str, ...] = ("id", "displayName", "location", "primaryType")

DEFAULT_INCLUDED_TYPES: tuple[str, ...] = (
    "hospital",
    "fire_station",
    "police",
    "school",
)

DEFAULT_RADIUS_M = 1200
DEFAULT_MAX_RESULTS = 20


def build_request(
    h3_cell: str,
    radius_m: int = DEFAULT_RADIUS_M,
    included_types: tuple[str, ...] = DEFAULT_INCLUDED_TYPES,
    fields: tuple[str, ...] = DEFAULT_FIELDS,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> LiveRequest:
    """A tile-scoped lookup request — the half of the evidence we own."""
    return LiveRequest(
        api="places.searchNearby",
        parameters={
            "h3_cell": h3_cell,
            "radius_m": radius_m,
            "included_types": list(included_types),
            "fields": list(fields),
            "max_results": max_results,
        },
    )


@dataclass
class PlacesSource:
    """A `LiveSource` over Places API (New) `places:searchNearby`."""

    provider: str = "google-maps-platform"
    api: str = "places.searchNearby"
    license: str = THIRD_PARTY_RESTRICTED
    verifiability: str = RE_DERIVABLE
    #: Google's terms require attribution wherever the content is displayed.
    #: Carried as a field so every surface that renders a result can read it
    #: off the source instead of hardcoding a string it might forget to update.
    attribution: str = "Google"
    retention: str = NOT_RETAINED

    timeout: float = 30.0
    #: Read at call time, not construction, so a process can acquire a key (or
    #: a test can remove one) without rebuilding the source.
    api_key_env: str = "STEWARD_GMP_API_KEY"
    base_url_env: str = "STEWARD_PLACES_BASE_URL"
    _last_status: dict[str, Any] = field(default_factory=dict, repr=False)

    def _api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "").strip()
        if not key:
            raise LiveUnavailable(
                f"No Places API key in ${self.api_key_env}; the live facility layer is "
                "declared unavailable rather than approximated from another source."
            )
        return key

    def request_for_cell(self, h3_cell: str) -> LiveRequest:
        return build_request(h3_cell)

    def lookup(self, request: LiveRequest) -> LiveResult:
        parameters = request.parameters
        try:
            cell = parameters["h3_cell"]
        except KeyError:
            raise LiveUnavailable(
                "Places lookup requires an 'h3_cell' parameter; the adapter derives the "
                "search circle from the tile so an exact position is never requested."
            ) from None

        api_key = self._api_key()
        latitude, longitude = h3.cell_to_latlng(cell)
        fields = tuple(parameters.get("fields", DEFAULT_FIELDS))
        body = {
            "includedTypes": list(parameters.get("included_types", DEFAULT_INCLUDED_TYPES)),
            "maxResultCount": int(parameters.get("max_results", DEFAULT_MAX_RESULTS)),
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": float(parameters.get("radius_m", DEFAULT_RADIUS_M)),
                }
            },
        }
        base_url = os.environ.get(self.base_url_env, DEFAULT_BASE_URL)
        http_request = urllib.request.Request(
            f"{base_url.rstrip('/')}/places:searchNearby",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": ",".join(f"places.{name}" for name in fields),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (
            urllib.error.URLError,
            json.JSONDecodeError,
            TimeoutError,
            UnicodeDecodeError,
        ) as error:
            raise LiveUnavailable(f"{type(error).__name__}: {error}") from error

        if not isinstance(payload, dict):
            raise LiveUnavailable(
                f"Places response was {type(payload).__name__}, not an object; "
                "refusing to attest to a response this adapter did not understand."
            )
        # An empty result is a real answer ("no facilities of these types within
        # the radius") and must not be confused with a failure. A `places` key
        # of the wrong type is a failure.
        places = payload.get("places", [])
        if not isinstance(places, list):
            raise LiveUnavailable(
                f"Places response 'places' was {type(places).__name__}, not a list."
            )

        return LiveResult(
            reference_ids=tuple(
                str(place["id"]) for place in places if isinstance(place, dict) and "id" in place
            ),
            response_sha256=response_digest(payload),
            display_payload=payload,
            n_results=len(places),
        )

    def summarize(self, result: LiveResult) -> dict[str, int]:
        """Facility counts by `primaryType`. No names, no ratings."""
        counts: dict[str, int] = {}
        places = result.display_payload.get("places", []) or []
        for place in places:
            if not isinstance(place, dict):
                continue
            category = place.get("primaryType") or "unspecified"
            counts[str(category)] = counts.get(str(category), 0) + 1
        return dict(sorted(counts.items()))
