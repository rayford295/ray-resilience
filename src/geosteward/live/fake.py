"""Deterministic fakes for both non-retainable regimes.

The default payload is deliberately loud. Every string in it is something the
terms forbid warehousing — a facility name, a phone number, a rating — and none
of it plausibly occurs anywhere else in this repository. So a leak is not
something a reviewer has to squint for: `POISON_STRINGS` is greppable, and any
test that drives the recorder through this fake checks the containment property
whether or not it set out to.

The fakes are also what makes the design testable without a key. `places.py`
and `grounded.py` need billing and credentials; the contract, the recorder, the
policy rules, and the post-check do not, and they are where the argument lives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from geosteward.live.base import (
    CITED_ONLY,
    NOT_RETAINED,
    RE_DERIVABLE,
    THIRD_PARTY_RESTRICTED,
    GroundedResult,
    LiveRequest,
    LiveResult,
    LiveUnavailable,
    response_digest,
)

#: Content of exactly the kinds the licence forbids retaining.
POISON_PAYLOAD: dict[str, Any] = {
    "places": [
        {
            "id": "PLACEID_POISON_AAA",
            "displayName": {"text": "Mulholland Poisonstring Medical Center"},
            "primaryType": "hospital",
            "nationalPhoneNumber": "(555) 013-0117",
            "rating": 4.7,
            "userRatingCount": 812,
            "location": {"latitude": 34.1897, "longitude": -118.1312},
        },
        {
            "id": "PLACEID_POISON_BBB",
            "displayName": {"text": "Zzyzx Canyon Poisonstring Elementary"},
            "primaryType": "school",
            "nationalPhoneNumber": "(555) 013-0288",
            "rating": 4.1,
            "userRatingCount": 96,
            "location": {"latitude": 34.1921, "longitude": -118.1275},
        },
        {
            "id": "PLACEID_POISON_CCC",
            "displayName": {"text": "Poisonstring Volunteer Fire Station 77"},
            "primaryType": "fire_station",
            "nationalPhoneNumber": "(555) 013-0399",
            "rating": 4.9,
            "userRatingCount": 41,
            "location": {"latitude": 34.1866, "longitude": -118.1350},
        },
    ]
}

#: Substrings that must never appear in a written record. Asserted by
#: `tests/test_live_record.py`, which is the load-bearing test of this design.
#:
#: Content VALUES only — names, numbers, identifiers the provider returned.
#: Field NAMES like `displayName` and `userRatingCount` are deliberately absent
#: from this list, and the distinction is the design rather than a concession:
#: the request is ours, it must be recorded verbatim for a reader to replay it,
#: and it necessarily names the fields we asked for. Recording that we requested
#: display names discloses nothing about any place. Recording a display name
#: does.
POISON_STRINGS: tuple[str, ...] = (
    "Mulholland Poisonstring Medical Center",
    "Zzyzx Canyon Poisonstring Elementary",
    "Poisonstring Volunteer Fire Station 77",
    "(555) 013-0117",
    "(555) 013-0288",
    "(555) 013-0399",
    "PLACEID_POISON_AAA",
    "PLACEID_POISON_BBB",
    "PLACEID_POISON_CCC",
    "Poisonstring",
)
#: Bare numerics (a `rating` of 4.7, a `userRatingCount` of 812) are not listed,
#: because a short digit string can occur inside a 64-character hex digest by
#: chance and the test would fail on the day the hash happened to contain it.
#: Numeric content is covered two other ways: the phone numbers above are
#: distinctive enough to grep for, and `RECORDED_KEYS` structurally forbids any
#: field nobody approved — which is the guarantee that generalises.


@dataclass
class FakeLiveSource:
    """A `LiveSource` that returns the same digest for the same payload."""

    provider: str = "fake-maps-provider"
    api: str = "places.searchNearby"
    license: str = THIRD_PARTY_RESTRICTED
    verifiability: str = RE_DERIVABLE
    attribution: str = "Fake Maps Provider"
    retention: str = NOT_RETAINED

    payload: dict[str, Any] = field(default_factory=lambda: dict(POISON_PAYLOAD))
    #: Set to simulate an outage or a missing key. The caller must report it,
    #: never paper over it — same contract as `LLMUnavailable`.
    unavailable: bool = False
    #: Every request seen, so a test can assert what was asked as well as what
    #: was recorded.
    calls: list[LiveRequest] = field(default_factory=list)

    def request_for_cell(self, h3_cell: str) -> LiveRequest:
        return LiveRequest(
            api=self.api,
            parameters={
                "h3_cell": h3_cell,
                "radius_m": 1200,
                "included_types": ["hospital", "school", "fire_station"],
                "fields": ["id", "displayName", "location", "primaryType"],
            },
        )

    def lookup(self, request: LiveRequest) -> LiveResult:
        if self.unavailable:
            raise LiveUnavailable(f"{self.provider}: no key configured for {self.api}")
        self.calls.append(request)
        places = self.payload.get("places", [])
        return LiveResult(
            reference_ids=tuple(p["id"] for p in places if "id" in p),
            response_sha256=response_digest(self.payload),
            display_payload=self.payload,
            n_results=len(places),
        )

    def summarize(self, result: LiveResult) -> dict[str, int]:
        counts: dict[str, int] = {}
        for place in result.display_payload.get("places", []) or []:
            category = place.get("primaryType") or "unspecified"
            counts[category] = counts.get(category, 0) + 1
        return dict(sorted(counts.items()))


@dataclass
class FakeGroundedSource:
    """A `GroundedSource`: prose plus citations, and no reproducible digest."""

    provider: str = "fake-grounding-provider"
    api: str = "grounding.maps"
    license: str = THIRD_PARTY_RESTRICTED
    verifiability: str = CITED_ONLY
    attribution: str = "Fake Grounding Provider"
    retention: str = NOT_RETAINED

    text: str = (
        "Three critical facilities sit within roughly a kilometre of this tile, "
        "including a hospital and a fire station."
    )
    citations: tuple[str, ...] = (
        "PLACEID_POISON_AAA",
        "PLACEID_POISON_CCC",
    )
    #: Grounded prose is not reproducible even at temperature 0, so the fake
    #: varies its text per call by default — a fake that returned identical
    #: prose forever would let a test accidentally depend on determinism this
    #: regime does not have.
    vary: bool = True
    _calls: int = 0

    def ask(self, question: str, parameters: dict[str, Any]) -> GroundedResult:
        self._calls += 1
        text = self.text
        if self.vary:
            text = f"{self.text} (draft {self._calls})"
        return GroundedResult(text=text, citations=self.citations)
