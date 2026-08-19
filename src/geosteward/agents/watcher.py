"""Watcher agent: poll public sources and register active hazard events."""

from __future__ import annotations

import datetime as dt

from geosteward.agents.base import Agent, Artifact, EventContext, utc_stamp
from geosteward.sources import zj_typhoon


class TyphoonWatcher:
    """Detects active WP typhoons and snapshots their live tracks.

    Snapshot files are append-only and timestamped; earlier captures are the
    frozen forecast-conditioned record used for post-event validation.
    """

    name = "watcher.typhoon"

    def __init__(self, year: int | None = None) -> None:
        self.year = year or dt.datetime.now(dt.timezone.utc).year

    def run(self, context: EventContext) -> list[Artifact]:
        tfid = context.metadata.get("tfid")
        if not tfid:
            raise ValueError("EventContext.metadata['tfid'] is required for TyphoonWatcher.")
        payload = zj_typhoon.typhoon_detail(tfid)
        stamp = utc_stamp()
        artifact = context.write_json(
            f"snapshots/{context.event_id}_{stamp}.json",
            payload,
            kind="track_snapshot",
            agent=self.name,
            inputs=[f"zj_typhoon:TyphoonInfo/{tfid}"],
            notes=f"live capture, isactive={payload.get('isactive')}",
        )
        return [artifact]

    @staticmethod
    def discover(year: int) -> list[dict[str, str]]:
        """List active typhoons as candidate events."""

        return [
            {
                "event_id": f"{row.get('enname', 'unknown').lower()}-{year}",
                "tfid": row["tfid"],
                "name": row.get("name", ""),
                "enname": row.get("enname", ""),
            }
            for row in zj_typhoon.active_typhoons(year)
        ]
