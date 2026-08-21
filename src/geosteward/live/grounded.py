"""Grounding with Google Maps — the `cited-only` regime, for real.

The harder of the two regimes, and the one the design is actually about. A
grounded answer can be neither retained (the licence) nor reproduced (the model
varies across versions even at temperature 0), so there is no digest worth
computing. What survives a replay is the citations.

Note what this module does NOT do: it does not hash `text`. A digest over
non-reproducible prose would look exactly like the anchor `places.py` produces
and would attest to nothing, which is worse than having no anchor at all —
somebody would eventually cite it. `GroundedResult` therefore has no
`response_sha256` field for this adapter to fill in.

**Unverified against the live API**, on the same terms as `places.py` and for
the same reason (no key; design §10). Two further limits specific to grounding,
both worth stating before anyone builds on it:

  * The response shape parsed below is the Gemini `generateContent` envelope
    with a `google_maps` tool. If it differs, this raises `LiveUnavailable`
    rather than returning prose with no citations attached — an ungrounded
    paragraph that *looks* grounded is the failure mode to avoid.
  * Nothing in the harness currently authorizes a cited-only claim. No allow
    rule matches `verifiability: cited-only`, so such a request falls through
    to `default-deny`. This adapter exists so the regime has a real
    implementation to reason about, not because it has a route to production.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from geosteward.live.base import (
    CITED_ONLY,
    NOT_RETAINED,
    THIRD_PARTY_RESTRICTED,
    GroundedResult,
    LiveUnavailable,
)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

#: Override when the account has a different grounding-capable model. The tool
#: name below is what makes the call grounded; the model only has to support it.
DEFAULT_MODEL = "gemini-2.5-flash"

MAPS_TOOL = "google_maps"


def _extract_text(candidate: dict[str, Any]) -> str:
    parts = candidate.get("content", {}).get("parts", [])
    if not isinstance(parts, list):
        raise LiveUnavailable("Grounded response 'parts' was not a list.")
    texts = [part["text"] for part in parts if isinstance(part, dict) and "text" in part]
    if not texts:
        raise LiveUnavailable("Grounded response carried no text parts.")
    return "".join(texts).strip()


def _extract_citations(candidate: dict[str, Any]) -> tuple[str, ...]:
    """Every grounding reference the response attached, in order.

    Raises when there are none. That is the whole contract of this regime: if
    the citations are the only accountable unit and there are no citations,
    there is nothing to be accountable with, and returning the prose anyway
    would launder an ungrounded answer into a grounded-looking one.
    """
    metadata = candidate.get("groundingMetadata") or {}
    chunks = metadata.get("groundingChunks") or []
    if not isinstance(chunks, list):
        raise LiveUnavailable("Grounded response 'groundingChunks' was not a list.")
    citations: list[str] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        maps = chunk.get("maps") or chunk.get("web") or {}
        if not isinstance(maps, dict):
            continue
        reference = maps.get("placeId") or maps.get("uri") or maps.get("title")
        if reference:
            citations.append(str(reference))
    if not citations:
        raise LiveUnavailable(
            "Grounded response carried no citations. In the cited-only regime the "
            "citation IS the evidence, so prose without one is refused rather than "
            "returned."
        )
    return tuple(citations)


@dataclass
class GroundedMapsSource:
    """A `GroundedSource` over Gemini with the Google Maps grounding tool."""

    provider: str = "google-maps-platform"
    api: str = "grounding.maps"
    license: str = THIRD_PARTY_RESTRICTED
    verifiability: str = CITED_ONLY
    attribution: str = "Google"
    retention: str = NOT_RETAINED

    timeout: float = 60.0
    api_key_env: str = "STEWARD_GEMINI_API_KEY"
    base_url_env: str = "STEWARD_GEMINI_BASE_URL"
    model_env: str = "STEWARD_GEMINI_MODEL"

    def _api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "").strip()
        if not key:
            raise LiveUnavailable(
                f"No Gemini API key in ${self.api_key_env}; grounded facility context is "
                "declared unavailable rather than answered from model memory."
            )
        return key

    def ask(self, question: str, parameters: dict[str, Any]) -> GroundedResult:
        api_key = self._api_key()
        model = os.environ.get(self.model_env, DEFAULT_MODEL)
        base_url = os.environ.get(self.base_url_env, DEFAULT_BASE_URL)

        # The prompt carries the tile, not a point, for the same reason
        # `places.py` derives its circle from the cell.
        cell = parameters.get("h3_cell")
        prompt = question if cell is None else f"{question}\n(H3 r9 tile: {cell})"

        http_request = urllib.request.Request(
            f"{base_url.rstrip('/')}/models/{model}:generateContent",
            data=json.dumps(
                {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "tools": [{MAPS_TOOL: {}}],
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
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

        candidates = payload.get("candidates") if isinstance(payload, dict) else None
        if not isinstance(candidates, list) or not candidates:
            raise LiveUnavailable(
                "Grounded response carried no candidates; refusing to invent one."
            )
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise LiveUnavailable("Grounded response candidate was not an object.")

        return GroundedResult(
            text=_extract_text(candidate), citations=_extract_citations(candidate)
        )
