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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from geosteward.gateway.steward import Steward
from geosteward.harness.audit import AuditLog
from geosteward.harness.policy import PolicyEngine

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY = REPO_ROOT / "src" / "geosteward" / "harness" / "policy_v1.yaml"
EVENTS_ROOT = Path(os.environ.get("STEWARD_EVENTS_ROOT", REPO_ROOT / "events"))
AUDIT_PATH = Path(os.environ.get("STEWARD_AUDIT_PATH", EVENTS_ROOT / "gateway_audit.jsonl"))

app = FastAPI(title="GeoSteward agent gateway", version="1.0.0-dev")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("STEWARD_CORS_ORIGINS", "*").split(","),
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

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
