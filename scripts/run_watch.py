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
from geosteward.sources import nhc, nifc, nws, usgs, wpc_ero
from geosteward.sources.watchbase import save_snapshot, utc_stamp
from geosteward.watch import build_watch_product

CONNECTORS = [usgs, nws, nhc, nifc]


def run_watch(
    connectors: list, live_root: Path, timeout: int = 30, outlook_connector=None
) -> dict:
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
            parsed.pop(source, None)  # never let partial progress before the failure count as data
            audit.record("source_failed", f"watch.{source}", payload={"error": str(error)})

    generated = utc_stamp()
    collection, status = build_watch_product(parsed, failures, generated)
    products = live_root / "products"
    products.mkdir(parents=True, exist_ok=True)

    # The Day-1 flash-flood outlook is a separate product with its own status
    # key: polygons and a forecast, so it never mixes into the point watch —
    # and its failure is recorded exactly like a watch source's, never fatal.
    if outlook_connector is not None:
        try:
            payload = outlook_connector.fetch(timeout=timeout)
            snapshot = save_snapshot(live_root, outlook_connector.SOURCE, payload)
            outlook_features, outlook_skipped = outlook_connector.parse(payload)
            outlook = outlook_connector.build_flood_outlook(
                outlook_features, outlook_skipped, generated
            )
            (products / "flood_outlook.geojson").write_text(
                json.dumps(outlook, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            status["flood_outlook"] = {
                "status": "ok", "areas": len(outlook_features),
                "skipped": outlook_skipped, "error": None,
            }
            audit.record(
                "source_ok", f"watch.{outlook_connector.SOURCE}",
                payload={"snapshot": snapshot.name, "areas": len(outlook_features),
                         "skipped": outlook_skipped},
            )
        except Exception as error:  # noqa: BLE001 - recorded, never swallowed
            status["flood_outlook"] = {
                "status": "failed", "areas": 0, "skipped": 0, "error": str(error),
            }
            audit.record(
                "source_failed", f"watch.{outlook_connector.SOURCE}",
                payload={"error": str(error)},
            )
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
    status = run_watch(CONNECTORS, args.live_root, timeout=args.timeout, outlook_connector=wpc_ero)
    ok = sum(1 for row in status["sources"].values() if row["status"] == "ok")
    print(f"watch run complete: {ok}/{len(status['sources'])} sources ok")


if __name__ == "__main__":
    main()
