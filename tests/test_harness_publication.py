"""The publication boundary: planning what ships, and verifying what shipped.

`plan_publication` turns the distribution policy plus the committed manifests
into an allowlist. `verify_site` checks an assembled site tree against that
allowlist by set difference — anything present that is not allowed is a
violation, so an unrecognised file fails closed instead of sliding through a
pattern match it happens not to trigger.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from geosteward.harness.distribution import DistributionPolicy
from geosteward.harness.publication import (
    WORKSTATION_PATH,
    plan_publication,
    verify_site,
    write_allowlist,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_V1 = REPO_ROOT / "src" / "geosteward" / "harness" / "policy_v1.yaml"
EVENTS = REPO_ROOT / "events"

RESTRICTED = "events/eaton-2025/exposure/dins_points_restricted.csv.gz"

#: Scope for the synthetic fixture below; the real scope lives in the policy.
DEMO = ["demo-2026"]


def manifest_row(path: str, kind: str) -> str:
    return json.dumps({"path": path, "kind": kind, "sha256": "0" * 64})


def fake_events(tmp: Path) -> Path:
    """A minimal events/ tree: one public grid, one restricted source."""
    root = tmp / "events"
    event = root / "demo-2026"
    (event / "exposure").mkdir(parents=True)
    (event / "exposure" / "grid.geojson").write_text("{}", encoding="utf-8")
    (event / "exposure" / "points_restricted.csv.gz").write_text("secret", encoding="utf-8")
    (event / "artifact_manifest.jsonl").write_text(
        manifest_row("events/demo-2026/exposure/grid.geojson", "damage_grid")
        + "\n"
        + manifest_row(
            "events/demo-2026/exposure/points_restricted.csv.gz", "damage_points_restricted"
        )
        + "\n",
        encoding="utf-8",
    )
    (event / "audit_log.jsonl").write_text("", encoding="utf-8")
    return root


class TestPlanPublication(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = DistributionPolicy.from_yaml(POLICY_V1)

    def test_public_grid_is_planned_and_restricted_source_is_not(self) -> None:
        with TemporaryDirectory() as tmp:
            plan = plan_publication(fake_events(Path(tmp)), self.policy, DEMO)
            allowed = {f.path for f in plan.allowed}
            self.assertIn("events/demo-2026/exposure/grid.geojson", allowed)
            self.assertNotIn("events/demo-2026/exposure/points_restricted.csv.gz", allowed)

    def test_denied_artifacts_carry_the_rule_that_denied_them(self) -> None:
        with TemporaryDirectory() as tmp:
            plan = plan_publication(fake_events(Path(tmp)), self.policy, DEMO)
            denied = {d.path: d.rule_id for d in plan.denied}
            self.assertEqual(
                denied["events/demo-2026/exposure/points_restricted.csv.gz"],
                "deny-publish-parcel-resolution",
            )

    def test_manifest_and_audit_log_are_planned_as_accountability_records(self) -> None:
        with TemporaryDirectory() as tmp:
            plan = plan_publication(fake_events(Path(tmp)), self.policy, DEMO)
            allowed = {f.path for f in plan.allowed}
            self.assertIn("events/demo-2026/artifact_manifest.jsonl", allowed)
            self.assertIn("events/demo-2026/audit_log.jsonl", allowed)

    def test_manifest_is_flagged_for_workstation_path_redaction(self) -> None:
        with TemporaryDirectory() as tmp:
            plan = plan_publication(fake_events(Path(tmp)), self.policy, DEMO)
            flagged = {f.path: f.redact_workstation_paths for f in plan.allowed}
            self.assertTrue(flagged["events/demo-2026/artifact_manifest.jsonl"])
            self.assertFalse(flagged["events/demo-2026/exposure/grid.geojson"])

    def test_event_absent_from_published_events_is_not_planned(self) -> None:
        # Which events form the public surface is a governance decision, so it
        # is declared in the policy rather than in a build script. A retired
        # event keeps its manifest on disk and stays off the site.
        with TemporaryDirectory() as tmp:
            root = fake_events(Path(tmp))
            retired = root / "archive" / "old-2020"
            retired.mkdir(parents=True)
            (retired / "artifact_manifest.jsonl").write_text(
                manifest_row("events/archive/old-2020/x.geojson", "damage_grid") + "\n",
                encoding="utf-8",
            )
            (retired / "x.geojson").write_text("{}", encoding="utf-8")
            plan = plan_publication(root, self.policy, published_events=["demo-2026"])
            allowed = {f.path for f in plan.allowed}
            self.assertNotIn("events/archive/old-2020/artifact_manifest.jsonl", allowed)
            self.assertNotIn("events/archive/old-2020/x.geojson", allowed)
            self.assertIn("events/demo-2026/exposure/grid.geojson", allowed)

    def test_file_on_disk_absent_from_the_manifest_is_reported_as_unclassified(self) -> None:
        # An artifact nobody recorded is the same hazard as an unclassified
        # kind: it must not ship just because no rule mentions it.
        with TemporaryDirectory() as tmp:
            root = fake_events(Path(tmp))
            (root / "demo-2026" / "exposure" / "stray.geojson").write_text("{}", encoding="utf-8")
            plan = plan_publication(root, self.policy, DEMO)
            self.assertIn(
                "events/demo-2026/exposure/stray.geojson",
                {d.path for d in plan.denied},
            )


class TestVerifySite(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = DistributionPolicy.from_yaml(POLICY_V1)

    def _site(self, tmp: Path, files: dict[str, str]) -> Path:
        site = tmp / "_site"
        for rel, body in files.items():
            target = site / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        return site

    def test_clean_site_passes(self) -> None:
        with TemporaryDirectory() as tmp:
            allowlist = ["events/demo-2026/exposure/grid.geojson"]
            site = self._site(Path(tmp), {"app/events/demo-2026/exposure/grid.geojson": "{}"})
            self.assertEqual(verify_site(site, allowlist), [])

    def test_planted_restricted_artifact_is_reported(self) -> None:
        # The regression that matters: this exact file was live on 2026-08-20.
        with TemporaryDirectory() as tmp:
            allowlist = ["events/eaton-2025/exposure/dins_h3_r9_damage_grid.geojson"]
            site = self._site(
                Path(tmp),
                {
                    "app/events/eaton-2025/exposure/dins_h3_r9_damage_grid.geojson": "{}",
                    f"app/{RESTRICTED}": "lat,lon\n1,2\n",
                },
            )
            violations = verify_site(site, allowlist)
            self.assertEqual(len(violations), 1)
            self.assertIn("dins_points_restricted", violations[0].detail)
            self.assertEqual(violations[0].kind, "unauthorized_artifact")

    def test_leaked_workstation_path_is_reported(self) -> None:
        with TemporaryDirectory() as tmp:
            allowlist = ["events/demo-2026/artifact_manifest.jsonl"]
            site = self._site(
                Path(tmp),
                {
                    "app/events/demo-2026/artifact_manifest.jsonl": json.dumps(
                        {"inputs": ["C:/Users/yyang295/Desktop/data/x.csv"]}
                    )
                },
            )
            violations = verify_site(site, allowlist)
            self.assertEqual([v.kind for v in violations], ["leaked_workstation_path"])

    def test_redacted_manifest_passes(self) -> None:
        with TemporaryDirectory() as tmp:
            allowlist = ["events/demo-2026/artifact_manifest.jsonl"]
            site = self._site(
                Path(tmp),
                {
                    "app/events/demo-2026/artifact_manifest.jsonl": json.dumps(
                        {"inputs": ["<workstation>/Desktop/data/x.csv"]}
                    )
                },
            )
            self.assertEqual(verify_site(site, allowlist), [])

    def test_files_outside_events_trees_are_ignored(self) -> None:
        with TemporaryDirectory() as tmp:
            site = self._site(Path(tmp), {"app/assets/index-abc123.js": "console.log(1)"})
            self.assertEqual(verify_site(site, []), [])


class TestWorkstationPathPattern(unittest.TestCase):
    def test_matches_windows_and_posix_home_paths(self) -> None:
        for sample in (
            "C:/Users/yyang295/Desktop/x.csv",
            r"C:\Users\yyang295\Desktop\x.csv",
            "/Users/yifn/Documents/x.csv",
            "/home/runner/work/x.csv",
        ):
            with self.subTest(sample=sample):
                self.assertRegex(sample, WORKSTATION_PATH)

    def test_does_not_match_repo_relative_paths(self) -> None:
        for sample in ("events/eaton-2025/exposure/grid.geojson", "<workstation>/Desktop/x.csv"):
            with self.subTest(sample=sample):
                self.assertNotRegex(sample, WORKSTATION_PATH)


class TestShippedRepositoryPlan(unittest.TestCase):
    """The plan over the real `events/` tree — the public surface, asserted."""

    def setUp(self) -> None:
        self.policy = DistributionPolicy.from_yaml(POLICY_V1)
        self.plan = plan_publication(EVENTS, self.policy, self.policy.published_events)

    def test_restricted_dins_source_is_denied(self) -> None:
        self.assertIn(RESTRICTED, {d.path for d in self.plan.denied})

    def test_no_snapshot_is_published(self) -> None:
        published_snapshots = [p for p in (f.path for f in self.plan.allowed) if "/snapshots/" in p]
        self.assertEqual(published_snapshots, [])

    def test_no_archived_event_is_published(self) -> None:
        archived = [p for p in (f.path for f in self.plan.allowed) if "/archive/" in p]
        self.assertEqual(archived, [])

    def test_published_events_match_the_layer_catalog(self) -> None:
        # The policy's event list and the app's event list must not drift; a
        # layer pointing at an unpublished event would 404 in production.
        views = (REPO_ROOT / "app" / "src" / "lib" / "views.js").read_text(encoding="utf-8")
        catalog = set(__import__("re").findall(r'"(\w+-\d{4})":\s*\{\s*\n\s*title:', views))
        self.assertEqual(catalog, set(self.policy.published_events))

    def test_every_layer_the_app_fetches_is_published(self) -> None:
        views = (REPO_ROOT / "app" / "src" / "lib" / "views.js").read_text(encoding="utf-8")
        allowed = {"/" + f.path for f in self.plan.allowed}
        for url in sorted(set(__import__("re").findall(r'"(/events/[^"]+)"', views))):
            with self.subTest(url=url):
                self.assertIn(url, allowed)


if __name__ == "__main__":
    unittest.main()
