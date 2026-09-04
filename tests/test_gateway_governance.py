"""The evidence store serves published, human-labelled artifacts and nothing else.

Found 2026-09-03 while landing the VLM-severity branch: `EvidenceStore` used
to load every `events/*/dossier/event_record.json` and every grid outside
`snapshots/`, ignoring both `published_events` and `model_derived`. The first
evaluation case written under `events/` (Palisades, zero-shot predictions
against DINS folder labels) would have been located by point and cited as
tile facts. These tests pin the two exclusions and the fact that the gateway
refuses to start without a scope.
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import h3

from geosteward.gateway.context import EvidenceStore
from geosteward.gateway.steward import Steward
from geosteward.harness.audit import AuditLog
from geosteward.harness.distribution import DistributionPolicy
from geosteward.harness.policy import PolicyEngine

from tests.test_gateway_area import _write_minimal_event

REPO = Path(__file__).resolve().parents[1]
POLICY = REPO / "src" / "geosteward" / "harness" / "policy_v1.yaml"
EVENTS = REPO / "events"

PUBLISHED_AOI = {"min_lat": 34.0, "max_lat": 34.1, "min_lon": -118.1, "max_lon": -118.0}
EVAL_AOI = {"min_lat": 33.9, "max_lat": 33.99, "min_lon": -118.6, "max_lon": -118.5}
IN_PUBLISHED = (34.05, -118.05)
IN_EVAL = (33.95, -118.55)


def _add_grid(root: Path, event_id: str, filename: str, cells: dict, *, model_derived: bool) -> None:
    """Register one more grid on an event `_write_minimal_event` created,
    optionally flagged `model_derived` the way the VLM builders flag the
    output of `vlm_severity.aggregate_h3` (a collection-level property)."""
    event_dir = root / event_id
    evidence = event_dir / "evidence"
    evidence.mkdir(exist_ok=True)
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]},
            "properties": {"h3_cell": cell, **props},
        }
        for cell, props in cells.items()
    ]
    collection = {"type": "FeatureCollection", "features": features}
    if model_derived:
        collection["properties"] = {"model_derived": True, "model": "some-vlm"}
    (evidence / filename).write_text(json.dumps(collection), encoding="utf-8")
    sha = hashlib.sha256(f"{event_id}-{filename}".encode()).hexdigest()
    with (event_dir / "artifact_manifest.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"path": f"{evidence}/{filename}", "sha256": sha}) + "\n")


class PublishedEventsScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cell_published = h3.latlng_to_cell(*IN_PUBLISHED, 9)
        self.cell_eval = h3.latlng_to_cell(*IN_EVAL, 9)
        _write_minimal_event(
            self.root, "published-2025", tier=3, aoi=PUBLISHED_AOI,
            cells={self.cell_published: {"n_structures": 12}},
        )
        _write_minimal_event(
            self.root, "evalcase-2025", tier=3, aoi=EVAL_AOI,
            cells={self.cell_eval: {"n_structures": 7}},
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_unscoped_store_loads_every_event_on_disk(self):
        # The permissive mode exists for synthetic-tree unit tests and is
        # explicit: None, never a default the Steward can fall into.
        store = EvidenceStore(self.root)
        self.assertEqual(sorted(store.events), ["evalcase-2025", "published-2025"])

    def test_event_outside_the_scope_is_not_located_by_point(self):
        store = EvidenceStore(self.root, published_events=["published-2025"])
        self.assertEqual(store.locate(*IN_PUBLISHED), ("published-2025", True))
        self.assertEqual(store.locate(*IN_EVAL), (None, False))
        ev = store.evidence_for(*IN_EVAL)
        self.assertFalse(ev.in_aoi)
        self.assertEqual(ev.facts, [])

    def test_event_outside_the_scope_is_not_located_by_area(self):
        store = EvidenceStore(self.root, published_events=["published-2025"])
        both = {"min_lat": 33.9, "max_lat": 34.1, "min_lon": -118.6, "max_lon": -118.0}
        ev = store.evidence_for_area(both)
        self.assertEqual(ev.event_ids, ["published-2025"])
        self.assertNotIn(self.cell_eval, ev.cells)

    def test_exclusion_is_recorded_not_silent(self):
        store = EvidenceStore(self.root, published_events=["published-2025"])
        self.assertEqual(store.excluded_events, {"evalcase-2025": "not in published_events"})

    def test_model_derived_dossier_is_excluded_even_when_listed(self):
        record = self.root / "evalcase-2025" / "dossier" / "event_record.json"
        payload = json.loads(record.read_text(encoding="utf-8"))
        payload["model_derived"] = True
        record.write_text(json.dumps(payload), encoding="utf-8")
        store = EvidenceStore(self.root, published_events=["published-2025", "evalcase-2025"])
        self.assertNotIn("evalcase-2025", store.events)
        self.assertEqual(store.excluded_events["evalcase-2025"], "dossier is model_derived")


class ModelDerivedGridTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cell = h3.latlng_to_cell(*IN_PUBLISHED, 9)
        _write_minimal_event(
            self.root, "published-2025", tier=3, aoi=PUBLISHED_AOI,
            cells={self.cell: {"n_structures": 12}},
        )
        # Same event, same tile: one human-labelled grid (above) and one grid
        # of zero-shot predictions, as Milton has once the bi-temporal VLM
        # builder runs beside the committed bitemporal grid.
        _add_grid(
            self.root, "published-2025", "vlm_pairs_h3_r9_grid.geojson",
            {self.cell: {"agreement_rate": 0.4, "labels_pred": {"Severe": 3}}},
            model_derived=True,
        )
        _add_grid(
            self.root, "published-2025", "another_human_grid.geojson",
            {self.cell: {"n_pairs": 3}},
            model_derived=False,
        )
        self.store = EvidenceStore(self.root, published_events=["published-2025"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_model_derived_grid_never_reaches_point_facts(self):
        ev = self.store.evidence_for(*IN_PUBLISHED)
        sources = {f.source_path for f in ev.facts}
        self.assertIn("grid.geojson", sources)
        self.assertIn("another_human_grid.geojson", sources)
        self.assertNotIn("vlm_pairs_h3_r9_grid.geojson", sources)
        self.assertFalse(any("agreement_rate" in f.text for f in ev.facts))

    def test_model_derived_grid_never_reaches_area_facts(self):
        ev = self.store.evidence_for_area(PUBLISHED_AOI)
        sources = {f.source_path for f in ev.facts}
        self.assertNotIn("vlm_pairs_h3_r9_grid.geojson", sources)
        coverage = next(f for f in ev.facts if "selection coverage" in f.text)
        self.assertNotIn("vlm_pairs", coverage.text)

    def test_skipped_grid_is_recorded(self):
        self.store.evidence_for(*IN_PUBLISHED)  # forces the grid scan
        self.assertEqual(
            self.store.excluded_grids, {"published-2025": ["vlm_pairs_h3_r9_grid.geojson"]}
        )


class PolicyScopeTests(unittest.TestCase):
    def test_claim_plane_and_distribution_plane_read_the_same_list(self):
        engine = PolicyEngine.from_yaml(POLICY)
        dist = DistributionPolicy.from_yaml(POLICY)
        self.assertIsNotNone(engine.published_events)
        self.assertEqual(engine.published_events, dist.published_events)

    def test_rules_only_policy_has_no_scope(self):
        engine = PolicyEngine([
            {"id": "allow-watch", "effect": "allow", "reason": "x", "match": {"purpose": "watch"}}
        ])
        self.assertIsNone(engine.published_events)

    def test_malformed_published_events_fails_at_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.yaml"
            path.write_text("rules: []\npublished_events: eaton-2025\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                PolicyEngine.from_yaml(path)


class StewardScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _write_minimal_event(self.root / "events", "evalcase-2025", tier=3, aoi=EVAL_AOI)

    def tearDown(self):
        self.tmp.cleanup()

    def _steward(self, policy, **kw):
        return Steward(
            events_root=self.root / "events", policy=policy,
            audit=AuditLog(self.root / "audit.jsonl"), llm=lambda m: "", **kw,
        )

    def test_no_scope_anywhere_refuses_to_start(self):
        rules_only = PolicyEngine([
            {"id": "allow-watch", "effect": "allow", "reason": "x", "match": {"purpose": "watch"}}
        ])
        with self.assertRaises(ValueError) as ctx:
            self._steward(rules_only)
        self.assertIn("published_events", str(ctx.exception))

    def test_policy_scope_is_the_default(self):
        steward = self._steward(PolicyEngine.from_yaml(POLICY))
        expected = frozenset(DistributionPolicy.from_yaml(POLICY).published_events)
        self.assertEqual(steward.store.published_events, expected)
        self.assertNotIn("evalcase-2025", steward.store.events)

    def test_explicit_scope_overrides_the_policy(self):
        steward = self._steward(PolicyEngine.from_yaml(POLICY), published_events=["evalcase-2025"])
        self.assertIn("evalcase-2025", steward.store.events)


class RepositoryStateTests(unittest.TestCase):
    """What the committed tree looks like through the scoped store."""

    def test_scoped_store_serves_only_published_events_with_no_model_derived_grids(self):
        policy = DistributionPolicy.from_yaml(POLICY)
        store = EvidenceStore(EVENTS, published_events=policy.published_events)
        self.assertEqual(sorted(store.events), sorted(policy.published_events))
        for event_id in store.events:
            for filename in store._grids(event_id):
                path = next(EVENTS.joinpath(event_id).glob(f"*/{filename}"))
                collection = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsNot(
                    collection.get("properties", {}).get("model_derived"), True,
                    f"{event_id}/{filename} is model_derived and was served",
                )
        for event_dir in EVENTS.iterdir():
            record = event_dir / "dossier" / "event_record.json"
            if record.exists():
                event_id = json.loads(record.read_text(encoding="utf-8"))["event_id"]
                self.assertTrue(
                    event_id in store.events or event_id in store.excluded_events,
                    f"{event_id} is neither served nor recorded as excluded",
                )


if __name__ == "__main__":
    unittest.main()
