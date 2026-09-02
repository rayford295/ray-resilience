"""Gateway hardening: authorization, rate limiting, client identity.

Pure logic, importable without FastAPI, so the policies are unit-testable
exactly like the harness planes. `gateway/main.py` wires these into HTTP.

The authorization default is fail-closed in the same sense as the policy
planes: with no token configured, the gateway serves loopback callers only.
Local development works out of the box; exposing the gateway to a network
is a decision someone must make explicitly, by setting a token — it can
never happen by forgetting to.
"""

from __future__ import annotations

import hmac
import time
from collections import deque
from dataclasses import dataclass, field

_LOOPBACK = ("127.", "::1", "localhost")


def is_loopback(host: str | None) -> bool:
    if not host:
        return False
    return host == "::1" or host == "localhost" or host.startswith("127.")


def client_key(peer_host: str | None, forwarded_for: str | None, trust_proxy: bool) -> str:
    """The identity a request is limited by.

    Behind a real proxy (Cloud Run), the peer is the proxy and the caller is
    the first X-Forwarded-For entry — but that header is attacker-writable
    when there is no proxy, so it is honored only when the deployment says
    to trust it. The wrong default here would let any caller mint fresh
    identities per request and walk through the rate limit.
    """
    if trust_proxy and forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return peer_host or "unknown"


def authorize(
    configured_token: str | None, presented_token: str | None, peer_host: str | None
) -> tuple[bool, str]:
    """(allowed, reason). Constant-time comparison when a token is set."""
    if configured_token:
        if presented_token and hmac.compare_digest(configured_token, presented_token):
            return True, "token"
        return False, "missing or invalid bearer token"
    if is_loopback(peer_host):
        return True, "loopback"
    return False, (
        "no API token is configured, so the gateway serves loopback callers only; "
        "set STEWARD_API_TOKEN to authorize network clients"
    )


def parse_rate_limit(spec: str) -> tuple[int, float]:
    """'20/60' -> (20 requests, per 60 seconds). Malformed specs fail loudly:
    a typo that silently disabled rate limiting would be the quiet-widening
    failure mode the policy planes exist to prevent."""
    try:
        count_s, window_s = spec.split("/")
        count, window = int(count_s), float(window_s)
    except ValueError as exc:
        raise ValueError(f"rate limit spec must look like '20/60', got {spec!r}") from exc
    if count < 1 or window <= 0:
        raise ValueError(f"rate limit spec must be positive, got {spec!r}")
    return count, window


@dataclass
class SlidingWindowLimiter:
    """Per-key sliding window. In-memory by design: one gateway instance is
    the deployment story today, and a shared store can replace this class
    behind the same two methods when that stops being true."""

    max_requests: int
    window_seconds: float
    clock: callable = time.monotonic
    _hits: dict[str, deque] = field(default_factory=dict)

    def allow(self, key: str) -> tuple[bool, float]:
        """(allowed, retry_after_seconds). Records the hit when allowed."""
        now = self.clock()
        hits = self._hits.setdefault(key, deque())
        cutoff = now - self.window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False, max(0.0, hits[0] + self.window_seconds - now)
        hits.append(now)
        return True, 0.0
