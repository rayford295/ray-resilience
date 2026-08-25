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
from pydantic import BaseModel, Field

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


class AskRequest(BaseModel):
    role: str = Field(pattern="^(resident|planner)$")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    question: str = Field(min_length=1, max_length=2000)


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    # Task 3 finishes this: AskRequest gains an `area` field and this call
    # passes it through as `area=request.area`.
    return steward.answer(request.role, request.question, lat=request.lat, lon=request.lon)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "events": sorted(steward.store.events)}
