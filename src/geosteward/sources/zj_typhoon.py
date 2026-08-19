"""Public source connector: Zhejiang Water Resources typhoon API.

Free, unauthenticated, near-real-time western-Pacific typhoon tracks with
quadrant wind radii and multi-agency forecasts. One of the source connectors
DisasterPilot's watcher polls; additional connectors (GDACS, USGS, CMA best
track) register the same interface.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

BASE = "https://typhoon.slt.zj.gov.cn/Api"
HEADERS = {
    "Referer": "https://typhoon.slt.zj.gov.cn/",
    "User-Agent": "Mozilla/5.0 (DisasterPilot research snapshot)",
}


def _get(url: str, timeout: int = 30) -> Any:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def list_typhoons(year: int, timeout: int = 30) -> list[dict[str, Any]]:
    """All typhoons registered for a year, including `isactive` flags."""

    return _get(f"{BASE}/TyphoonList/{year}", timeout=timeout)


def active_typhoons(year: int, timeout: int = 30) -> list[dict[str, Any]]:
    return [row for row in list_typhoons(year, timeout) if row.get("isactive") == "1"]


def typhoon_detail(tfid: str, timeout: int = 30) -> dict[str, Any]:
    """Full payload for one typhoon: points, wind radii, forecasts."""

    return _get(f"{BASE}/TyphoonInfo/{tfid}", timeout=timeout)
