"""The contract for a source whose content this project may not retain.

Every other source in GeoSteward is proved by a stored copy: fetch it, hash it,
freeze it under `snapshots/`, and a reader checks the number against the file.
A source under third-party terms cannot be proved that way, so the contract
here splits a response into two halves that are treated completely differently:

  * the **content** (`display_payload`) — Maps Content, or whatever the
    provider calls it. Returned to the caller for immediate rendering and never
    written to disk by anything in this package.
  * the **attestation** (`response_sha256`, `n_results`, and the request that
    produced them) — a digest and a count, which are not content and can be
    published.

The request matters as much as the digest, and it is the half this project owns
outright: we chose the cell, the radius, and the field list. A reader with
their own key re-issues exactly that request and compares digests. Drift is
signal — the world changed, or the provider did — not error.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from geosteward.harness.policy import CITED_ONLY, RE_DERIVABLE

#: Retention stances a source may declare. Both are honest; neither is a
#: promise the source keeps on its own — `NOT_RETAINED` is enforced by the
#: recorder never being handed a place to put the content.
NOT_RETAINED = "not-retained"
RETAINED_LOCALLY = "retained-locally"

THIRD_PARTY_RESTRICTED = "third-party-restricted"


class LiveUnavailable(Exception):
    """The live source could not be reached, or has no key configured.

    Mirrors `LLMUnavailable`: the caller reports the outage rather than
    substituting a fake, a cache, or a keyless approximation. A declared
    absence is a usable answer; a quietly different answer is not.
    """


def response_digest(payload: Any) -> str:
    """The anchor a third party re-derives: sha256 over canonical JSON.

    Canonical rather than raw bytes on purpose. Raw bytes would make the digest
    depend on key order and whitespace the provider is free to change between
    responses, and re-derivation would then report drift on every call, which
    is the same as reporting nothing. Sorting keys leaves exactly the changes
    that mean something: different content.
    """
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()


@dataclass(frozen=True)
class LiveRequest:
    """The half of a lookup this project owns, and can therefore publish."""

    api: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveResult:
    """One live lookup, with its content quarantined from its attestation."""

    #: Provider-side stable identifiers (Places `id`, for one). The terms permit
    #: storing these indefinitely, so the project keeps them for its own joins.
    #: They stay out of the published record — permission to store is not
    #: obviously permission to redistribute, and re-derivation replays the
    #: REQUEST, so the verification story does not need them (§6, §11.2).
    reference_ids: tuple[str, ...]
    response_sha256: str
    #: Third-party content. Rendered immediately, never written to disk.
    display_payload: Any
    n_results: int


@runtime_checkable
class LiveSource(Protocol):
    """A structured, re-derivable third-party source.

    The four declarations are what the harness reasons about, so they are part
    of the contract rather than documentation: a source that cannot say what
    its licence and verifiability are cannot be authorized.
    """

    provider: str
    api: str
    license: str
    verifiability: str
    attribution: str
    retention: str

    def lookup(self, request: LiveRequest) -> LiveResult:
        ...


@dataclass(frozen=True)
class GroundedResult:
    """Model prose grounded in third-party references.

    No `response_sha256`, and that absence is the point. This content is not
    reproducible — grounded answers vary across model versions even at
    temperature 0 — so hashing the prose would produce a number that looks like
    an anchor and holds nothing. What survives is the citations.

    > When evidence can be neither retained nor reproduced, the smallest
    > accountable unit is the citation, not the content.
    """

    text: str
    citations: tuple[str, ...]


@runtime_checkable
class GroundedSource(Protocol):
    """A non-deterministic grounded source, always `cited-only`."""

    provider: str
    api: str
    license: str
    verifiability: str
    attribution: str
    retention: str

    def ask(self, question: str, parameters: dict[str, Any]) -> GroundedResult:
        ...


def describe(source: LiveSource | GroundedSource) -> dict[str, str]:
    """The source's own declarations, for the record and for the policy."""
    return {
        "provider": source.provider,
        "api": source.api,
        "license": source.license,
        "verifiability": source.verifiability,
        "retention": source.retention,
        "attribution": source.attribution,
    }


#: Re-exported so adapters and tests name the same constants the policy does,
#: rather than repeating the strings and drifting from the ordered axis.
__all__ = [
    "CITED_ONLY",
    "RE_DERIVABLE",
    "NOT_RETAINED",
    "RETAINED_LOCALLY",
    "THIRD_PARTY_RESTRICTED",
    "GroundedResult",
    "GroundedSource",
    "LiveRequest",
    "LiveResult",
    "LiveSource",
    "LiveUnavailable",
    "describe",
    "response_digest",
]
