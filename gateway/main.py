"""Thin HTTP skin over the Steward — deployable to Cloud Run or runnable
locally against Ollama. All accountability logic lives in
geosteward.gateway.steward; this file only parses requests and serves JSON.

Run locally:
  pip install -e .[deepcase,gateway]
  uvicorn gateway.main:app --port 8080
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from geosteward.gateway.hardening import (
    SlidingWindowLimiter,
    authorize,
    client_key,
    parse_rate_limit,
)
from geosteward.gateway.steward import Steward
from geosteward.harness.audit import AuditLog
from geosteward.harness.policy import PolicyEngine

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY = REPO_ROOT / "src" / "geosteward" / "harness" / "policy_v1.yaml"
EVENTS_ROOT = Path(os.environ.get("STEWARD_EVENTS_ROOT", REPO_ROOT / "events"))
AUDIT_PATH = Path(os.environ.get("STEWARD_AUDIT_PATH", EVENTS_ROOT / "gateway_audit.jsonl"))

#: Fail-closed deployment posture, mirroring the policy planes:
#:  - No STEWARD_API_TOKEN  -> loopback callers only. Local dev works out of
#:    the box; network exposure requires an explicit decision.
#:  - CORS defaults to the local dev origins, never `*`; a public deploy sets
#:    STEWARD_CORS_ORIGINS to the Pages origin.
#:  - Rate limit is per client (peer address; first X-Forwarded-For entry
#:    only when STEWARD_TRUST_PROXY=1, e.g. behind Cloud Run).
API_TOKEN = os.environ.get("STEWARD_API_TOKEN") or None
TRUST_PROXY = os.environ.get("STEWARD_TRUST_PROXY") == "1"
_RATE_MAX, _RATE_WINDOW = parse_rate_limit(os.environ.get("STEWARD_RATE_LIMIT", "20/60"))
_limiter = SlidingWindowLimiter(_RATE_MAX, _RATE_WINDOW)
_DEFAULT_CORS = "http://localhost:5173,http://127.0.0.1:5173"

app = FastAPI(title="GeoSteward agent gateway", version="1.0.0-dev")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("STEWARD_CORS_ORIGINS", _DEFAULT_CORS).split(","),
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def guard(request: Request, call_next):
    """Authorization and rate limiting for /ask. /health stays open — it
    reveals only the event list the public site already serves."""
    if request.url.path == "/ask":
        peer = request.client.host if request.client else None
        auth_header = request.headers.get("authorization", "")
        presented = auth_header.removeprefix("Bearer ").strip() or None
        allowed, reason = authorize(API_TOKEN, presented, peer)
        if not allowed:
            return JSONResponse(status_code=401, content={"type": "unauthorized", "reason": reason})
        key = client_key(peer, request.headers.get("x-forwarded-for"), TRUST_PROXY)
        ok, retry_after = _limiter.allow(key)
        if not ok:
            return JSONResponse(
                status_code=429,
                content={"type": "rate_limited",
                         "reason": f"rate limit {_RATE_MAX}/{_RATE_WINDOW:g}s exceeded"},
                headers={"Retry-After": str(max(1, int(retry_after + 0.999)))},
            )
    return await call_next(request)

steward = Steward(
    events_root=EVENTS_ROOT,
    policy=PolicyEngine.from_yaml(POLICY),
    audit=AuditLog(AUDIT_PATH),
)


class AreaBox(BaseModel):
    min_lat: float = Field(ge=-90, le=90)
    min_lon: float = Field(ge=-180, le=180)
    max_lat: float = Field(ge=-90, le=90)
    max_lon: float = Field(ge=-180, le=180)


class AskRequest(BaseModel):
    role: str = Field(pattern="^(resident|planner)$")
    question: str = Field(min_length=1, max_length=2000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    area: AreaBox | None = None

    @model_validator(mode="after")
    def exactly_one_location(self):
        #: Rejected here, before the harness sees it, so an ambiguous request
        #: never reaches the plane that decides authorization.
        #:
        #: A lone coordinate does not make a point, so `has_point` needs
        #: both -- but it is still a coordinate, and a coordinate given
        #: alongside an area is "both", not "neither". Checking `has_any_coord`
        #: against `area` first catches that shape before it can hide behind
        #: `has_point` being `False`; the second check then handles the
        #: ordinary neither-given and lone-coordinate cases.
        has_area = self.area is not None
        has_any_coord = self.lat is not None or self.lon is not None
        has_point = self.lat is not None and self.lon is not None
        if has_area and has_any_coord:
            raise ValueError("give either lat/lon or area, not both and not neither")
        if not has_area and not has_point:
            raise ValueError("give either lat/lon or area, not both and not neither")
        return self


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    return steward.answer(
        request.role,
        request.question,
        lat=request.lat,
        lon=request.lon,
        area=request.area.model_dump() if request.area else None,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "events": sorted(steward.store.events)}
