"""The record that makes a non-retainable lookup accountable.

This is the result the design exists for: an append-only, publishable record of
evidence the project is forbidden to keep.

It is publishable *because* it is empty of the content it attests to. It holds
the request — which is entirely ours, since we chose the cell, the radius, and
the field list — and a digest of the response, which is not content. A reader
with their own key re-issues the request and compares. Nothing in the row is
Maps Content, so no term is strained by publishing it, and the accountability
claim survives the licence intact.

Two structural constraints, both enforced here rather than described:

  * **The payload is built from a named key list.** Not `asdict(result)`, not
    `**kwargs`. A future edit that adds a field to `LiveResult` cannot leak it
    into the record by inheritance, and an edit that adds a key here fails the
    assertion below until somebody has decided that key belongs in a published
    file. The publication-boundary incident was a constraint nothing read;
    this one is read on every call.
  * **The request must name a tile, not a point.** `live_lookup_record` is
    classified `resolution_cap: tile`, and a record carrying an exact lat/lon
    would contradict its own classification. Requiring `h3_cell` is the
    positive form of that constraint — an allowlist, not a hunt for coordinate
    -shaped keys.

There is deliberately no recorder for the `cited-only` regime. No rule
authorizes a cited-only claim — it falls through to `default-deny` — so there
is no authorized lookup to record. If a rule ever permits one, the shape of its
record is an open question rather than an omission: grounding citations are
simultaneously the smallest accountable unit (§3) and third-party identifiers
of the kind §11.2 keeps out of published records. That tension should be
resolved on purpose, not by whichever code got written first.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geosteward.harness.audit import AuditLog
from geosteward.live.base import LiveRequest, LiveResult, LiveSource, describe

#: Exactly the keys a published live-lookup payload may carry. The list is the
#: enforcement surface: `payload.keys()` is asserted equal to it on every write.
RECORDED_KEYS = frozenset(
    {
        "provider",
        "api",
        "request",
        "response_sha256",
        "n_results",
        "license",
        "verifiability",
        "retention",
        "attribution",
    }
)

#: Request parameters must locate the lookup by tile. See the module docstring.
REQUIRED_REQUEST_PARAMETER = "h3_cell"

ACTION = "live_lookup"


class RecordShapeError(Exception):
    """The record does not have the shape a published file is allowed to have.

    Raised instead of writing. A lookup that cannot be recorded accountably is
    a lookup whose result must not be used, which is the fail-closed direction
    the rest of the harness moves in.
    """


def _actor(source: LiveSource) -> str:
    """`live.places` for a `places.searchNearby` source."""
    return f"live.{source.api.split('.', 1)[0]}"


def build_payload(
    source: LiveSource, request: LiveRequest, result: LiveResult
) -> dict[str, Any]:
    """The publishable payload for one lookup, and nothing else.

    Every value is read by name. `display_payload` and `reference_ids` are
    never mentioned, so they cannot appear.
    """
    if REQUIRED_REQUEST_PARAMETER not in request.parameters:
        raise RecordShapeError(
            f"Live lookup request must locate itself by '{REQUIRED_REQUEST_PARAMETER}'; "
            f"got parameters {sorted(request.parameters)}. A published record classified "
            "at tile resolution cannot carry a point."
        )

    declarations = describe(source)
    payload = {
        "provider": declarations["provider"],
        "api": request.api,
        "request": dict(request.parameters),
        "response_sha256": result.response_sha256,
        "n_results": result.n_results,
        "license": declarations["license"],
        "verifiability": declarations["verifiability"],
        "retention": declarations["retention"],
        "attribution": declarations["attribution"],
    }

    unexpected = set(payload) - RECORDED_KEYS
    if unexpected:
        raise RecordShapeError(
            f"Live-lookup payload carries unapproved key(s) {sorted(unexpected)}. "
            "Add them to RECORDED_KEYS only after deciding they belong in a public file."
        )
    missing = RECORDED_KEYS - set(payload)
    if missing:
        raise RecordShapeError(
            f"Live-lookup payload is missing required key(s) {sorted(missing)}; "
            "an incomplete attestation is not re-derivable."
        )
    return payload


class LiveEvidenceRecorder:
    """Appends content-free attestations to `events/live_evidence.jsonl`."""

    def __init__(self, path: Path, run_id: str | None = None):
        self.log = AuditLog(path) if run_id is None else AuditLog(path, run_id=run_id)

    @property
    def path(self) -> Path:
        return self.log.path

    def record(
        self, source: LiveSource, request: LiveRequest, result: LiveResult
    ) -> dict[str, Any]:
        """Write one attestation; returns the row as written."""
        return self.log.record(
            ACTION, _actor(source), payload=build_payload(source, request, result)
        )


def compare_digests(recorded_sha256: str, replayed_sha256: str) -> dict[str, Any]:
    """Re-derivation verdict for a reader who replayed a recorded request.

    Drift is reported as drift, not as an error. A differing digest means the
    response changed — a facility opened, closed, or was re-classified — which
    is exactly the kind of thing a reader checking a disaster product wants to
    learn. Calling it a failure would train people to ignore it.
    """
    matched = recorded_sha256 == replayed_sha256
    return {
        "matched": matched,
        "recorded_sha256": recorded_sha256,
        "replayed_sha256": replayed_sha256,
        "verdict": "re-derived" if matched else "drift",
        "note": (
            "Response digest reproduced from the recorded request."
            if matched
            else "Response changed since the record was written; the provider's "
            "data moved. This is signal about the world, not a verification failure."
        ),
    }
