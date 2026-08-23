# GeoSteward Plan 2: Tier-1 Watch (US Hazard Connectors + Live Publishing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nationwide near-real-time multi-hazard watch: four keyless US public-source connectors (USGS earthquakes, NWS flood/weather alerts, NHC tropical cyclones, NIFC wildfires), a fail-closed watch product builder that runs harness checks, an orchestration script with audit logging, and an hourly GitHub Actions workflow publishing append-only snapshots + products to a dedicated `live-data` branch.

**Architecture:** Each connector is a module with a pure `parse(payload) -> list[WatchEvent]` function (unit-tested on committed fixtures) and a thin `fetch()` using stdlib urllib (same pattern as the existing `zj_typhoon.py`). The orchestrator treats every connector independently: a failing source is recorded as a failure and never blocks the others (fail-closed, no fabrication). The product builder runs Steward Harness outcome checks (CRS declaration, lat/lon bounds) and emits declared unknowns.

**Tech Stack:** Python stdlib (urllib, json) + existing deps only (pyyaml). No new dependencies. unittest runner.

**Spec:** `docs/design/specs/2026-08-19-geosteward-design.md` (Plan 2 of 5).

**Recorded deviation from spec:** live artifacts publish to a dedicated **`live-data` branch** (readable via `raw.githubusercontent.com`, which sends `Access-Control-Allow-Origin: *`) instead of `gh-pages`, because GitHub Pages currently serves `docs/` on `main` and switching the Pages source now would break the existing site URL. Plan 4 (PWA) decides final hosting and may consolidate.

## Global Constraints

- All repository content in English.
- Test runner is **unittest**: `python -m unittest discover -s tests -v`.
- No new Python dependencies; network I/O via `urllib.request` with a 30s default timeout and the header `{"User-Agent": "Mozilla/5.0 (GeoSteward research snapshot)"}`.
- Fail closed: a source outage yields a recorded failure entry, never a fabricated or silently-missing layer.
- Append-only: snapshots are never overwritten; `capture_index.jsonl` only grows.
- Connector `parse` functions are pure and defensive: a malformed feature is skipped and counted, never raises out of `parse`.
- Working directory `~/Documents/GeoSteward`, branch `main`. After each task's commit: `git push origin main && git push orgfork main`.

---

### Task 1: WatchEvent model + snapshot store

**Files:**
- Create: `src/geosteward/sources/watchbase.py`
- Test: `tests/test_watchbase.py`

**Interfaces (produced, used by Tasks 2-5):**
- `WatchEvent(source: str, source_id: str, hazard: str, name: str, lat: float, lon: float, severity: str, observed_utc: str, properties: dict)` frozen dataclass with `.as_feature() -> dict` (GeoJSON Feature, Point [lon, lat], all scalar fields + properties merged into feature properties)
- `fetch_json(url: str, timeout: int = 30) -> Any` — GET + JSON decode with the standard UA header
- `save_snapshot(root: Path, source: str, payload: Any) -> Path` — writes `root/snapshots/<source>_<UTCSTAMP>.json` and appends `{"source", "path", "utc"}` to `root/snapshots/capture_index.jsonl`; returns the snapshot path

- [ ] **Step 1: Write the failing tests**

Create `tests/test_watchbase.py`:

```python
"""Tier-1 watch foundations: event model and append-only snapshot store."""

import json
import tempfile
import unittest
from pathlib import Path

from geosteward.sources.watchbase import WatchEvent, save_snapshot


def event(**overrides):
    base = dict(
        source="usgs",
        source_id="us7000abcd",
        hazard="earthquake",
        name="M 4.5 - 10km NE of Somewhere, CA",
        lat=36.5,
        lon=-118.2,
        severity="4.5",
        observed_utc="20260819T120000Z",
        properties={"depth_km": 8.1},
    )
    base.update(overrides)
    return WatchEvent(**base)


class TestWatchEvent(unittest.TestCase):
    def test_as_feature_is_valid_geojson_point(self) -> None:
        feature = event().as_feature()
        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["geometry"], {"type": "Point", "coordinates": [-118.2, 36.5]})
        props = feature["properties"]
        self.assertEqual(props["source"], "usgs")
        self.assertEqual(props["hazard"], "earthquake")
        self.assertEqual(props["severity"], "4.5")
        self.assertEqual(props["depth_km"], 8.1)

    def test_extra_properties_do_not_shadow_core_fields(self) -> None:
        feature = event(properties={"source": "spoof"}).as_feature()
        self.assertEqual(feature["properties"]["source"], "usgs")


class TestSnapshotStore(unittest.TestCase):
    def test_save_snapshot_appends_index_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = save_snapshot(root, "usgs", {"a": 1})
            second = save_snapshot(root, "usgs", {"a": 2})
            self.assertTrue(first.exists() and second.exists())
            self.assertNotEqual(first, second)
            index = root / "snapshots" / "capture_index.jsonl"
            rows = [json.loads(line) for line in index.read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["source"], "usgs")
            self.assertTrue(rows[0]["utc"].endswith("Z"))
            self.assertEqual(json.loads(first.read_text())["a"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.test_watchbase -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geosteward.sources.watchbase'`

- [ ] **Step 3: Implement**

Create `src/geosteward/sources/watchbase.py`:

```python
"""Shared foundations for Tier-1 watch connectors.

Every connector normalizes its payload into WatchEvent rows and archives the
raw payload as an append-only snapshot, so any product can be traced back to
the exact bytes a source served at a specific time.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HEADERS = {"User-Agent": "Mozilla/5.0 (GeoSteward research snapshot)"}


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fetch_json(url: str, timeout: int = 30) -> Any:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


@dataclass(frozen=True)
class WatchEvent:
    """One normalized hazard observation from a public source."""

    source: str
    source_id: str
    hazard: str
    name: str
    lat: float
    lon: float
    severity: str
    observed_utc: str
    properties: dict[str, Any] = field(default_factory=dict)

    def as_feature(self) -> dict[str, Any]:
        props: dict[str, Any] = dict(self.properties)
        props.update(
            {
                "source": self.source,
                "source_id": self.source_id,
                "hazard": self.hazard,
                "name": self.name,
                "severity": self.severity,
                "observed_utc": self.observed_utc,
            }
        )
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [self.lon, self.lat]},
            "properties": props,
        }


def save_snapshot(root: Path, source: str, payload: Any) -> Path:
    snapshots = root / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    path = snapshots / f"{source}_{stamp}.json"
    while path.exists():  # same-second rerun: never overwrite
        stamp += "x"
        path = snapshots / f"{source}_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    with (snapshots / "capture_index.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"source": source, "path": path.name, "utc": stamp}) + "\n")
    return path
```

- [ ] **Step 4: Run tests (module + full suite)**

Run: `python -m unittest discover -s tests -v`
Expected: PASS (42 existing + 3 new).

- [ ] **Step 5: Commit and push**

```bash
git add src/geosteward/sources/watchbase.py tests/test_watchbase.py
git commit -m "feat: WatchEvent model and append-only snapshot store for Tier-1 watch"
git push origin main && git push orgfork main
```

---

### Task 2: USGS earthquake + NWS alert connectors

**Files:**
- Create: `src/geosteward/sources/usgs.py`, `src/geosteward/sources/nws.py`, `tests/fixtures/usgs_all_day.json`, `tests/fixtures/nws_alerts.json`
- Test: `tests/test_connectors_usgs_nws.py`

**Interfaces (produced; same shape for Task 3):** each connector module exposes
- `SOURCE: str`, `HAZARD: str`, `URL: str`
- `fetch(timeout: int = 30) -> Any` — returns the raw payload (`watchbase.fetch_json(URL, timeout)`)
- `parse(payload: Any) -> tuple[list[WatchEvent], int]` — (events, skipped_count); pure, defensive: any per-feature error → skip and count

- [ ] **Step 1: Write fixtures**

Create `tests/fixtures/usgs_all_day.json`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": "us7000quake1",
      "properties": {"mag": 4.6, "place": "10 km NE of Ridgecrest, CA", "time": 1755600000000, "type": "earthquake"},
      "geometry": {"type": "Point", "coordinates": [-117.55, 35.68, 8.1]}
    },
    {
      "type": "Feature",
      "id": "us7000quake2",
      "properties": {"mag": 2.1, "place": "Kenai Peninsula, Alaska", "time": 1755603600000, "type": "earthquake"},
      "geometry": {"type": "Point", "coordinates": [-151.2, 60.1, 40.0]}
    },
    {
      "type": "Feature",
      "id": "usbadfeature",
      "properties": {"mag": null, "place": "No geometry", "time": 1755603600000, "type": "earthquake"},
      "geometry": null
    }
  ]
}
```

Create `tests/fixtures/nws_alerts.json`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": "urn:oid:2.49.0.1.840.0.alert1",
      "geometry": {"type": "Polygon", "coordinates": [[[-97.5, 30.2], [-97.3, 30.2], [-97.3, 30.4], [-97.5, 30.4], [-97.5, 30.2]]]},
      "properties": {"event": "Flood Warning", "severity": "Severe", "areaDesc": "Travis, TX", "effective": "2026-08-19T06:00:00-05:00", "headline": "Flood Warning for Travis County"}
    },
    {
      "type": "Feature",
      "id": "urn:oid:2.49.0.1.840.0.alert2",
      "geometry": null,
      "properties": {"event": "Heat Advisory", "severity": "Moderate", "areaDesc": "Maricopa, AZ", "effective": "2026-08-19T08:00:00-07:00", "headline": "Heat Advisory"}
    }
  ]
}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_connectors_usgs_nws.py`:

```python
"""USGS and NWS connectors: pure parse functions tested on committed fixtures."""

import json
import unittest
from pathlib import Path

from geosteward.sources import nws, usgs

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


class TestUsgsParse(unittest.TestCase):
    def test_parses_valid_features_and_skips_broken(self) -> None:
        events, skipped = usgs.parse(load("usgs_all_day.json"))
        self.assertEqual(len(events), 2)
        self.assertEqual(skipped, 1)
        quake = events[0]
        self.assertEqual(quake.source, "usgs")
        self.assertEqual(quake.hazard, "earthquake")
        self.assertEqual(quake.source_id, "us7000quake1")
        self.assertAlmostEqual(quake.lat, 35.68)
        self.assertAlmostEqual(quake.lon, -117.55)
        self.assertEqual(quake.severity, "4.6")
        self.assertEqual(quake.observed_utc, "20260819T104000Z")
        self.assertAlmostEqual(quake.properties["depth_km"], 8.1)

    def test_module_contract(self) -> None:
        self.assertEqual(usgs.SOURCE, "usgs")
        self.assertTrue(usgs.URL.startswith("https://earthquake.usgs.gov/"))


class TestNwsParse(unittest.TestCase):
    def test_polygon_alert_uses_centroid_and_null_geometry_skipped(self) -> None:
        events, skipped = nws.parse(load("nws_alerts.json"))
        self.assertEqual(len(events), 1)
        self.assertEqual(skipped, 1)
        alert = events[0]
        self.assertEqual(alert.source, "nws")
        self.assertEqual(alert.hazard, "weather_alert")
        self.assertEqual(alert.name, "Flood Warning for Travis County")
        self.assertEqual(alert.severity, "Severe")
        self.assertAlmostEqual(alert.lat, 30.3, places=1)
        self.assertAlmostEqual(alert.lon, -97.4, places=1)
        self.assertEqual(alert.properties["event"], "Flood Warning")

    def test_module_contract(self) -> None:
        self.assertEqual(nws.SOURCE, "nws")
        self.assertTrue(nws.URL.startswith("https://api.weather.gov/alerts/active"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run to verify failure** — `python -m unittest tests.test_connectors_usgs_nws -v` → `ModuleNotFoundError`

- [ ] **Step 4: Implement**

Create `src/geosteward/sources/usgs.py`:

```python
"""USGS earthquake feed connector (keyless, updated every minute)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from geosteward.sources.watchbase import WatchEvent, fetch_json

SOURCE = "usgs"
HAZARD = "earthquake"
URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"


def fetch(timeout: int = 30) -> Any:
    return fetch_json(URL, timeout=timeout)


def parse(payload: Any) -> tuple[list[WatchEvent], int]:
    events: list[WatchEvent] = []
    skipped = 0
    for feature in payload.get("features", []):
        try:
            lon, lat, depth_km = feature["geometry"]["coordinates"][:3]
            props = feature["properties"]
            observed = dt.datetime.fromtimestamp(
                props["time"] / 1000, tz=dt.timezone.utc
            ).strftime("%Y%m%dT%H%M%SZ")
            events.append(
                WatchEvent(
                    source=SOURCE,
                    source_id=str(feature["id"]),
                    hazard=HAZARD,
                    name=f"M {props['mag']} - {props['place']}",
                    lat=float(lat),
                    lon=float(lon),
                    severity=str(props["mag"]),
                    observed_utc=observed,
                    properties={"depth_km": float(depth_km)},
                )
            )
        except (KeyError, TypeError, ValueError, IndexError):
            skipped += 1
    return events, skipped
```

Create `src/geosteward/sources/nws.py`:

```python
"""NWS active alerts connector (keyless): floods, storms, heat, more."""

from __future__ import annotations

from typing import Any

from geosteward.sources.watchbase import WatchEvent, fetch_json

SOURCE = "nws"
HAZARD = "weather_alert"
URL = "https://api.weather.gov/alerts/active?status=actual"


def fetch(timeout: int = 30) -> Any:
    return fetch_json(URL, timeout=timeout)


def _centroid(geometry: dict[str, Any]) -> tuple[float, float]:
    """Mean of the outer ring's vertices — a display anchor, not a survey point."""

    if geometry["type"] == "Point":
        lon, lat = geometry["coordinates"][:2]
        return float(lat), float(lon)
    ring = geometry["coordinates"][0]
    if geometry["type"] == "MultiPolygon":
        ring = geometry["coordinates"][0][0]
    lats = [point[1] for point in ring]
    lons = [point[0] for point in ring]
    return sum(lats) / len(lats), sum(lons) / len(lons)


def parse(payload: Any) -> tuple[list[WatchEvent], int]:
    events: list[WatchEvent] = []
    skipped = 0
    for feature in payload.get("features", []):
        try:
            geometry = feature["geometry"]
            if not geometry:
                skipped += 1
                continue
            lat, lon = _centroid(geometry)
            props = feature["properties"]
            events.append(
                WatchEvent(
                    source=SOURCE,
                    source_id=str(feature["id"]),
                    hazard=HAZARD,
                    name=props.get("headline") or props["event"],
                    lat=lat,
                    lon=lon,
                    severity=str(props.get("severity", "Unknown")),
                    observed_utc=str(props.get("effective", "")),
                    properties={"event": props["event"], "area": props.get("areaDesc", "")},
                )
            )
        except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
            skipped += 1
    return events, skipped
```

- [ ] **Step 5: Run tests (module + full suite), commit, push**

Run: `python -m unittest discover -s tests -v` → all green.

```bash
git add src/geosteward/sources/usgs.py src/geosteward/sources/nws.py tests/fixtures tests/test_connectors_usgs_nws.py
git commit -m "feat: USGS earthquake and NWS alert connectors with fixture-tested parsers"
git push origin main && git push orgfork main
```

---

### Task 3: NHC tropical cyclone + NIFC wildfire connectors

**Files:**
- Create: `src/geosteward/sources/nhc.py`, `src/geosteward/sources/nifc.py`, `tests/fixtures/nhc_current_storms.json`, `tests/fixtures/nifc_incidents.json`
- Test: `tests/test_connectors_nhc_nifc.py`

**Interfaces:** same module contract as Task 2 (`SOURCE`, `HAZARD`, `URL`, `fetch`, `parse`).

- [ ] **Step 1: Write fixtures**

Create `tests/fixtures/nhc_current_storms.json`:

```json
{
  "activeStorms": [
    {
      "id": "al062026",
      "binNumber": "AT1",
      "name": "Franklin",
      "classification": "HU",
      "intensity": "85",
      "pressure": "962",
      "latitudeNumeric": 24.9,
      "longitudeNumeric": -83.4,
      "movementDir": 315,
      "movementSpeed": 12,
      "lastUpdate": "2026-08-19T09:00:00.000Z"
    },
    {
      "id": "ep092026",
      "binNumber": "EP2",
      "name": "Gil",
      "classification": "TS",
      "intensity": "50",
      "pressure": "997",
      "latitudeNumeric": 16.2,
      "longitudeNumeric": -128.7,
      "movementDir": 280,
      "movementSpeed": 9,
      "lastUpdate": "2026-08-19T09:00:00.000Z"
    },
    {
      "id": "brokenstorm",
      "name": "NoCoords",
      "classification": "TD",
      "intensity": "30",
      "lastUpdate": "2026-08-19T09:00:00.000Z"
    }
  ]
}
```

Create `tests/fixtures/nifc_incidents.json`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 1,
      "geometry": {"type": "Point", "coordinates": [-118.13, 34.19]},
      "properties": {"IncidentName": "EATON", "FireDiscoveryDateTime": 1736035200000, "DailyAcres": 14021.0, "PercentContained": 100.0, "POOState": "US-CA"}
    },
    {
      "type": "Feature",
      "id": 2,
      "geometry": {"type": "Point", "coordinates": [-105.6, 40.2]},
      "properties": {"IncidentName": "Ridge Creek", "FireDiscoveryDateTime": 1755400000000, "DailyAcres": 312.5, "PercentContained": 20.0, "POOState": "US-CO"}
    },
    {
      "type": "Feature",
      "id": 3,
      "geometry": null,
      "properties": {"IncidentName": "NoGeom", "FireDiscoveryDateTime": 1755400000000, "DailyAcres": 1.0, "PercentContained": 0.0, "POOState": "US-MT"}
    }
  ]
}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_connectors_nhc_nifc.py`:

```python
"""NHC and NIFC connectors: pure parse functions tested on committed fixtures."""

import json
import unittest
from pathlib import Path

from geosteward.sources import nhc, nifc

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


class TestNhcParse(unittest.TestCase):
    def test_parses_active_storms_and_skips_broken(self) -> None:
        events, skipped = nhc.parse(load("nhc_current_storms.json"))
        self.assertEqual(len(events), 2)
        self.assertEqual(skipped, 1)
        storm = events[0]
        self.assertEqual(storm.source, "nhc")
        self.assertEqual(storm.hazard, "tropical_cyclone")
        self.assertEqual(storm.source_id, "al062026")
        self.assertEqual(storm.name, "Hurricane Franklin")
        self.assertAlmostEqual(storm.lat, 24.9)
        self.assertAlmostEqual(storm.lon, -83.4)
        self.assertEqual(storm.severity, "85")
        self.assertEqual(storm.properties["classification"], "HU")

    def test_classification_labels(self) -> None:
        events, _ = nhc.parse(load("nhc_current_storms.json"))
        self.assertEqual(events[1].name, "Tropical Storm Gil")

    def test_module_contract(self) -> None:
        self.assertEqual(nhc.SOURCE, "nhc")
        self.assertTrue(nhc.URL.startswith("https://www.nhc.noaa.gov/"))


class TestNifcParse(unittest.TestCase):
    def test_parses_incidents_and_skips_null_geometry(self) -> None:
        events, skipped = nifc.parse(load("nifc_incidents.json"))
        self.assertEqual(len(events), 2)
        self.assertEqual(skipped, 1)
        fire = events[0]
        self.assertEqual(fire.source, "nifc")
        self.assertEqual(fire.hazard, "wildfire")
        self.assertEqual(fire.name, "EATON")
        self.assertAlmostEqual(fire.lat, 34.19)
        self.assertAlmostEqual(fire.lon, -118.13)
        self.assertEqual(fire.severity, "14021.0")
        self.assertEqual(fire.properties["percent_contained"], 100.0)
        self.assertEqual(fire.properties["state"], "US-CA")

    def test_module_contract(self) -> None:
        self.assertEqual(nifc.SOURCE, "nifc")
        self.assertIn("f=geojson", nifc.URL)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run to verify failure** — `ModuleNotFoundError` expected.

- [ ] **Step 4: Implement**

Create `src/geosteward/sources/nhc.py`:

```python
"""NHC current tropical cyclones connector (keyless)."""

from __future__ import annotations

from typing import Any

from geosteward.sources.watchbase import WatchEvent, fetch_json

SOURCE = "nhc"
HAZARD = "tropical_cyclone"
URL = "https://www.nhc.noaa.gov/CurrentStorms.json"

_CLASS_LABELS = {
    "HU": "Hurricane",
    "TS": "Tropical Storm",
    "TD": "Tropical Depression",
    "STD": "Subtropical Depression",
    "STS": "Subtropical Storm",
    "PTC": "Post-tropical Cyclone",
    "PC": "Potential Tropical Cyclone",
}


def fetch(timeout: int = 30) -> Any:
    return fetch_json(URL, timeout=timeout)


def parse(payload: Any) -> tuple[list[WatchEvent], int]:
    events: list[WatchEvent] = []
    skipped = 0
    for storm in payload.get("activeStorms", []):
        try:
            classification = str(storm.get("classification", ""))
            label = _CLASS_LABELS.get(classification, classification or "Cyclone")
            events.append(
                WatchEvent(
                    source=SOURCE,
                    source_id=str(storm["id"]),
                    hazard=HAZARD,
                    name=f"{label} {storm['name']}",
                    lat=float(storm["latitudeNumeric"]),
                    lon=float(storm["longitudeNumeric"]),
                    severity=str(storm.get("intensity", "")),
                    observed_utc=str(storm.get("lastUpdate", "")),
                    properties={
                        "classification": classification,
                        "pressure_mb": storm.get("pressure"),
                        "movement_dir": storm.get("movementDir"),
                        "movement_kt": storm.get("movementSpeed"),
                    },
                )
            )
        except (KeyError, TypeError, ValueError):
            skipped += 1
    return events, skipped
```

Create `src/geosteward/sources/nifc.py`:

```python
"""NIFC/WFIGS current wildfire incidents connector (keyless ArcGIS feed)."""

from __future__ import annotations

from typing import Any

from geosteward.sources.watchbase import WatchEvent, fetch_json

SOURCE = "nifc"
HAZARD = "wildfire"
URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "WFIGS_Incident_Locations_Current/FeatureServer/0/query"
    "?where=1%3D1&outFields=IncidentName,FireDiscoveryDateTime,DailyAcres,"
    "PercentContained,POOState&returnGeometry=true&f=geojson"
)


def fetch(timeout: int = 30) -> Any:
    return fetch_json(URL, timeout=timeout)


def parse(payload: Any) -> tuple[list[WatchEvent], int]:
    events: list[WatchEvent] = []
    skipped = 0
    for feature in payload.get("features", []):
        try:
            geometry = feature["geometry"]
            if not geometry:
                skipped += 1
                continue
            lon, lat = geometry["coordinates"][:2]
            props = feature["properties"]
            events.append(
                WatchEvent(
                    source=SOURCE,
                    source_id=str(feature.get("id", props["IncidentName"])),
                    hazard=HAZARD,
                    name=str(props["IncidentName"]),
                    lat=float(lat),
                    lon=float(lon),
                    severity=str(props.get("DailyAcres", "")),
                    observed_utc=str(props.get("FireDiscoveryDateTime", "")),
                    properties={
                        "percent_contained": props.get("PercentContained"),
                        "state": props.get("POOState"),
                    },
                )
            )
        except (KeyError, TypeError, ValueError, IndexError):
            skipped += 1
    return events, skipped
```

- [ ] **Step 5: Run full suite, commit, push**

```bash
git add src/geosteward/sources/nhc.py src/geosteward/sources/nifc.py tests/fixtures tests/test_connectors_nhc_nifc.py
git commit -m "feat: NHC tropical cyclone and NIFC wildfire connectors"
git push origin main && git push orgfork main
```

---

### Task 4: Watch product builder (harness-checked, fail-closed)

**Files:**
- Create: `src/geosteward/watch.py`
- Test: `tests/test_watch_product.py`

**Interfaces (produced, used by Task 5 and the Plan-4 PWA):**
- `build_watch_product(parsed: dict[str, tuple[list[WatchEvent], int]], failures: dict[str, str], generated_utc: str) -> tuple[dict, dict]` returning `(collection, status)`:
  - `collection` — GeoJSON FeatureCollection; top-level `"geosteward:crs": "EPSG:4326"`, `"geosteward:generated_utc"`, features from all events that pass `check_bounds` on lat [-90, 90] and lon [-180, 180] (out-of-bounds events are dropped and counted per source)
  - `status` — `{"generated_utc", "sources": {name: {"status": "ok"|"failed", "events": int, "skipped": int, "dropped_bounds": int, "error": str|None}}, "declared_unknowns": [ ... ], "checks": [CheckResult rows]}`
  - `declared_unknowns` always contains: `"Watch data supports monitoring only; no damage or exposure conclusions."` and, when any source failed or any features were skipped/dropped, a line naming them.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_watch_product.py`:

```python
"""The watch product: harness-checked, fail-closed, unknowns declared."""

import unittest

from geosteward.sources.watchbase import WatchEvent
from geosteward.watch import build_watch_product


def event(source="usgs", lat=35.0, lon=-100.0, **overrides):
    base = dict(
        source=source,
        source_id=f"{source}-1",
        hazard="earthquake",
        name="test event",
        lat=lat,
        lon=lon,
        severity="1",
        observed_utc="20260819T000000Z",
        properties={},
    )
    base.update(overrides)
    return WatchEvent(**base)


class TestBuildWatchProduct(unittest.TestCase):
    def test_collection_carries_crs_and_all_valid_events(self) -> None:
        collection, status = build_watch_product(
            parsed={"usgs": ([event(), event(source="usgs")], 0)},
            failures={},
            generated_utc="20260819T120000Z",
        )
        self.assertEqual(collection["type"], "FeatureCollection")
        self.assertEqual(collection["geosteward:crs"], "EPSG:4326")
        self.assertEqual(collection["geosteward:generated_utc"], "20260819T120000Z")
        self.assertEqual(len(collection["features"]), 2)
        self.assertEqual(status["sources"]["usgs"]["status"], "ok")
        self.assertEqual(status["sources"]["usgs"]["events"], 2)

    def test_out_of_bounds_events_dropped_and_counted(self) -> None:
        collection, status = build_watch_product(
            parsed={"usgs": ([event(), event(lat=95.0)], 0)},
            failures={},
            generated_utc="20260819T120000Z",
        )
        self.assertEqual(len(collection["features"]), 1)
        self.assertEqual(status["sources"]["usgs"]["dropped_bounds"], 1)

    def test_failed_source_recorded_never_fabricated(self) -> None:
        collection, status = build_watch_product(
            parsed={"usgs": ([event()], 0)},
            failures={"nhc": "HTTP 503"},
            generated_utc="20260819T120000Z",
        )
        self.assertEqual(status["sources"]["nhc"]["status"], "failed")
        self.assertEqual(status["sources"]["nhc"]["error"], "HTTP 503")
        self.assertEqual(status["sources"]["nhc"]["events"], 0)
        sources_in_features = {f["properties"]["source"] for f in collection["features"]}
        self.assertNotIn("nhc", sources_in_features)

    def test_declared_unknowns_always_present_and_name_failures(self) -> None:
        _, clean_status = build_watch_product(
            parsed={"usgs": ([event()], 0)}, failures={}, generated_utc="x"
        )
        self.assertTrue(
            any("monitoring only" in u for u in clean_status["declared_unknowns"])
        )
        _, degraded_status = build_watch_product(
            parsed={"usgs": ([event()], 2)},
            failures={"nifc": "timeout"},
            generated_utc="x",
        )
        joined = " ".join(degraded_status["declared_unknowns"])
        self.assertIn("nifc", joined)
        self.assertIn("skipped", joined)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError: No module named 'geosteward.watch'`

- [ ] **Step 3: Implement**

Create `src/geosteward/watch.py`:

```python
"""Tier-1 watch product builder.

Merges normalized events from every source into one national FeatureCollection,
running Steward Harness outcome checks and declaring what is NOT known with the
same prominence as what is. A failed source appears as a recorded failure —
never as silently-missing data.
"""

from __future__ import annotations

from typing import Any

from geosteward.harness.checks import check_bounds, check_crs
from geosteward.sources.watchbase import WatchEvent

CRS = "EPSG:4326"


def build_watch_product(
    parsed: dict[str, tuple[list[WatchEvent], int]],
    failures: dict[str, str],
    generated_utc: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    features: list[dict[str, Any]] = []
    sources: dict[str, Any] = {}
    checks = [check_crs(CRS).as_row()]

    for source, (events, skipped) in parsed.items():
        dropped = 0
        for event in events:
            lat_ok = check_bounds("lat", event.lat, -90.0, 90.0)
            lon_ok = check_bounds("lon", event.lon, -180.0, 180.0)
            if lat_ok.passed and lon_ok.passed:
                features.append(event.as_feature())
            else:
                dropped += 1
                checks.append((lat_ok if not lat_ok.passed else lon_ok).as_row())
        sources[source] = {
            "status": "ok",
            "events": len(events) - dropped,
            "skipped": skipped,
            "dropped_bounds": dropped,
            "error": None,
        }
    for source, error in failures.items():
        sources[source] = {
            "status": "failed",
            "events": 0,
            "skipped": 0,
            "dropped_bounds": 0,
            "error": error,
        }

    unknowns = ["Watch data supports monitoring only; no damage or exposure conclusions."]
    failed = sorted(failures)
    if failed:
        unknowns.append(f"Sources currently failed (no data, not zero hazards): {', '.join(failed)}.")
    total_skipped = sum(row["skipped"] for row in sources.values())
    total_dropped = sum(row["dropped_bounds"] for row in sources.values())
    if total_skipped or total_dropped:
        unknowns.append(
            f"{total_skipped} feature(s) skipped as malformed; {total_dropped} dropped by bounds checks."
        )

    collection = {
        "type": "FeatureCollection",
        "geosteward:crs": CRS,
        "geosteward:generated_utc": generated_utc,
        "features": features,
    }
    status = {
        "generated_utc": generated_utc,
        "sources": sources,
        "declared_unknowns": unknowns,
        "checks": checks,
    }
    return collection, status
```

- [ ] **Step 4: Run full suite** — all green.

- [ ] **Step 5: Commit and push**

```bash
git add src/geosteward/watch.py tests/test_watch_product.py
git commit -m "feat: harness-checked fail-closed national watch product builder"
git push origin main && git push orgfork main
```

---

### Task 5: Orchestration script `run_watch.py` with audit logging

**Files:**
- Create: `scripts/run_watch.py`
- Test: `tests/test_run_watch.py`

**Interfaces:**
- `run_watch(connectors: list, live_root: Path, timeout: int = 30) -> dict` (importable from the script as a module function): for each connector module, `fetch → save_snapshot → parse`; exceptions land in `failures[SOURCE]` (fail-closed); builds the product; writes `live_root/products/national_watch.geojson` and `live_root/products/watch_status.json`; audits every step to `live_root/audit_log.jsonl`; returns the status dict.
- CLI: `python scripts/run_watch.py [--live-root live] [--timeout 30]` using the four real connectors.

- [ ] **Step 1: Write the failing test**

Create `tests/test_run_watch.py`:

```python
"""Orchestration: fail-closed per source, audited, products written."""

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_watch", REPO / "scripts" / "run_watch.py")
run_watch_module = importlib.util.module_from_spec(spec)
sys.modules["run_watch"] = run_watch_module
spec.loader.exec_module(run_watch_module)

from geosteward.sources.watchbase import WatchEvent  # noqa: E402


def fake_connector(source: str, ok: bool) -> types.SimpleNamespace:
    def fetch(timeout: int = 30):
        if not ok:
            raise RuntimeError("HTTP 503")
        return {"payload": source}

    def parse(payload):
        return (
            [
                WatchEvent(
                    source=source,
                    source_id=f"{source}-1",
                    hazard="test",
                    name="event",
                    lat=30.0,
                    lon=-90.0,
                    severity="1",
                    observed_utc="20260819T000000Z",
                    properties={},
                )
            ],
            0,
        )

    return types.SimpleNamespace(SOURCE=source, fetch=fetch, parse=parse)


class TestRunWatch(unittest.TestCase):
    def test_failed_source_does_not_block_others_and_all_is_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            live_root = Path(tmp)
            status = run_watch_module.run_watch(
                connectors=[fake_connector("good", True), fake_connector("bad", False)],
                live_root=live_root,
            )
            self.assertEqual(status["sources"]["good"]["status"], "ok")
            self.assertEqual(status["sources"]["bad"]["status"], "failed")
            collection = json.loads(
                (live_root / "products" / "national_watch.geojson").read_text()
            )
            self.assertEqual(len(collection["features"]), 1)
            written_status = json.loads(
                (live_root / "products" / "watch_status.json").read_text()
            )
            self.assertEqual(written_status["sources"]["bad"]["error"], "HTTP 503")
            snapshots = list((live_root / "snapshots").glob("good_*.json"))
            self.assertEqual(len(snapshots), 1)
            audit_rows = [
                json.loads(line)
                for line in (live_root / "audit_log.jsonl").read_text().splitlines()
            ]
            actions = [row["action"] for row in audit_rows]
            self.assertIn("source_ok", actions)
            self.assertIn("source_failed", actions)
            self.assertIn("product_built", actions)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure** — file not found / attribute errors expected.

- [ ] **Step 3: Implement**

Create `scripts/run_watch.py`:

```python
"""Run the Tier-1 watch loop once: fetch all sources, build the national product.

Each source is independent: a failure is recorded and audited, never fabricated
and never allowed to block the other sources.

Usage:
    python scripts/run_watch.py [--live-root live] [--timeout 30]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from geosteward.harness.audit import AuditLog
from geosteward.sources import nhc, nifc, nws, usgs
from geosteward.sources.watchbase import save_snapshot, utc_stamp
from geosteward.watch import build_watch_product

CONNECTORS = [usgs, nws, nhc, nifc]


def run_watch(connectors: list, live_root: Path, timeout: int = 30) -> dict:
    live_root.mkdir(parents=True, exist_ok=True)
    audit = AuditLog(live_root / "audit_log.jsonl")
    parsed: dict = {}
    failures: dict[str, str] = {}
    for connector in connectors:
        source = connector.SOURCE
        try:
            payload = connector.fetch(timeout=timeout)
            snapshot = save_snapshot(live_root, source, payload)
            events, skipped = connector.parse(payload)
            parsed[source] = (events, skipped)
            audit.record(
                "source_ok",
                f"watch.{source}",
                payload={"snapshot": snapshot.name, "events": len(events), "skipped": skipped},
            )
        except Exception as error:  # noqa: BLE001 - recorded, never swallowed
            failures[source] = str(error)
            audit.record("source_failed", f"watch.{source}", payload={"error": str(error)})

    generated = utc_stamp()
    collection, status = build_watch_product(parsed, failures, generated)
    products = live_root / "products"
    products.mkdir(parents=True, exist_ok=True)
    (products / "national_watch.geojson").write_text(
        json.dumps(collection, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (products / "watch_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    audit.record(
        "product_built",
        "watch.builder",
        payload={
            "features": len(collection["features"]),
            "failed_sources": sorted(failures),
            "generated_utc": generated,
        },
    )
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-root", type=Path, default=Path("live"))
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    status = run_watch(CONNECTORS, args.live_root, timeout=args.timeout)
    ok = sum(1 for row in status["sources"].values() if row["status"] == "ok")
    print(f"watch run complete: {ok}/{len(status['sources'])} sources ok")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run full suite** — all green.

- [ ] **Step 5: Live smoke test (network allowed here, one run)**

```bash
python scripts/run_watch.py --live-root /tmp/geosteward_watch_smoke
cat /tmp/geosteward_watch_smoke/products/watch_status.json
```

Expected: exits 0; each source either `ok` with real event counts or `failed` with a recorded error (a transient source failure is acceptable — that IS the fail-closed behavior; do not retry-loop). If a source consistently fails on a parse error (schema drift), fix that connector's `parse` and add the real payload shape to its fixture.

- [ ] **Step 6: Commit and push**

```bash
git add scripts/run_watch.py tests/test_run_watch.py
git commit -m "feat: watch orchestration script with per-source fail-closed audit"
git push origin main && git push orgfork main
```

---

### Task 6: `live-data` branch + hourly GitHub Actions workflow

**Files:**
- Create: `.github/workflows/live.yml`
- Modify: `README.md` (add a "Live watch data" subsection under Hazard coverage)
- Branch: create orphan `live-data`

- [ ] **Step 1: Create the orphan `live-data` branch (via a temp worktree; do NOT move HEAD on the main checkout)**

```bash
cd ~/Documents/GeoSteward
git worktree add --detach /tmp/gs-live-init
cd /tmp/gs-live-init
git checkout --orphan live-data
git rm -rf . -q
printf '# GeoSteward live watch data\n\nAppend-only Tier-1 snapshots and products, refreshed hourly by CI.\nConsume via raw.githubusercontent.com/rayford295/GeoSteward/live-data/...\n' > README.md
git add README.md && git commit -m "chore: initialize live-data branch"
git push origin live-data
cd ~/Documents/GeoSteward && git worktree remove --force /tmp/gs-live-init
```

- [ ] **Step 2: Write the workflow**

Create `.github/workflows/live.yml`:

```yaml
name: live-watch

on:
  schedule:
    - cron: "23 * * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  watch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          ref: live-data
          path: live-data
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install package
        run: python -m pip install -e .
      - name: Run watch loop against the live-data tree
        run: python scripts/run_watch.py --live-root live-data/live
      - name: Commit and push live data
        run: |
          cd live-data
          git config user.name "geosteward-watch-bot"
          git config user.email "actions@github.com"
          git add live
          git diff --cached --quiet || git commit -m "watch: hourly capture $(date -u +%Y-%m-%dT%H:%MZ)"
          git push
```

- [ ] **Step 3: Add the README subsection**

In `README.md`, after the Tier 1/2/3 bullet list in "Hazard coverage (tiered)", insert:

```markdown
**Live watch data** is refreshed hourly by CI onto the
[`live-data`](https://github.com/rayford295/GeoSteward/tree/live-data) branch:
`live/products/national_watch.geojson` (all active US hazards) and
`live/products/watch_status.json` (per-source health, declared unknowns), with
append-only raw snapshots under `live/snapshots/`.
```

- [ ] **Step 4: Commit, push, and verify the workflow end-to-end**

```bash
git add .github/workflows/live.yml README.md
git commit -m "feat: hourly live-watch workflow publishing to live-data branch"
git push origin main && git push orgfork main
gh workflow run live-watch --repo rayford295/GeoSteward
sleep 90
gh run list --repo rayford295/GeoSteward --workflow live-watch --limit 1
```

Expected: the dispatched run concludes `success`; then verify data landed:

```bash
gh api repos/rayford295/GeoSteward/contents/live/products/watch_status.json?ref=live-data --jq '.name'
```

If the run fails, read its log (`gh run view <id> --log-failed`), fix, and re-dispatch before completing this task.

---

## Completion Criteria

- Full suite green (42 + ~13 new tests).
- One manual smoke run against real endpoints recorded in the Task 5 report.
- `live-data` branch exists with at least one CI-produced commit containing `live/products/national_watch.geojson`.
- Both remotes' `main` synced.
- Next: Plan 3 (deep cases — blocked on dataset locations), Plan 4 (PWA).
