import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import manual_anchors as ma

REPO = Path(__file__).resolve().parents[1]


class ExtractTests(unittest.TestCase):
    def test_backticked_path_is_an_anchor(self):
        anchors = ma.extract_anchors("see `src/geosteward/pipeline.py` for it", Path("x.md"))
        self.assertEqual([a.path for a in anchors], ["src/geosteward/pipeline.py"])

    def test_markdown_link_target_is_an_anchor(self):
        anchors = ma.extract_anchors("[the engine](src/geosteward/harness/policy.py)", Path("x.md"))
        self.assertEqual([a.path for a in anchors], ["src/geosteward/harness/policy.py"])

    def test_line_reference_is_stripped_and_preserved(self):
        (anchor,) = ma.extract_anchors("`src/geosteward/harness/policy.py:195`", Path("x.md"))
        self.assertEqual(anchor.path, "src/geosteward/harness/policy.py")
        self.assertEqual(anchor.line_ref, "195")

    def test_non_path_code_spans_are_not_anchors(self):
        text = "`H3 r9`, `sha256`, `EPSG:4326`, `and/or`, `resolution_cap`"
        self.assertEqual(ma.extract_anchors(text, Path("x.md")), [])

    def test_directory_anchor_keeps_trailing_slash(self):
        (anchor,) = ma.extract_anchors("`docs/incidents/`", Path("x.md"))
        self.assertEqual(anchor.path, "docs/incidents/")

    def test_source_line_is_recorded(self):
        (anchor,) = ma.extract_anchors("intro\nsee `scripts/run_watch.py`\n", Path("x.md"))
        self.assertEqual(anchor.source_line, 2)


class ResolveTests(unittest.TestCase):
    def test_existing_file_resolves(self):
        (anchor,) = ma.extract_anchors("`src/geosteward/pipeline.py`", Path("x.md"))
        self.assertTrue(ma.resolve(anchor, REPO))

    def test_existing_directory_resolves(self):
        (anchor,) = ma.extract_anchors("`docs/incidents/`", Path("x.md"))
        self.assertTrue(ma.resolve(anchor, REPO))

    def test_missing_file_does_not_resolve(self):
        (anchor,) = ma.extract_anchors("`src/disasterpilot/sources/usgs.py`", Path("x.md"))
        self.assertFalse(ma.resolve(anchor, REPO))


class TemplateAndAbsenceTests(unittest.TestCase):
    def test_template_tokens_are_not_anchors(self):
        text = "`events/<event-id>/artifact_manifest.jsonl` and `events/*/dossier/`"
        self.assertEqual(ma.extract_anchors(text, Path("x.md")), [])

    def test_brace_notation_is_not_an_anchor(self):
        text = "moved `docs/superpowers/{specs,plans}/` to `docs/design/`"
        self.assertEqual([a.path for a in ma.extract_anchors(text, Path("x.md"))], ["docs/design/"])

    def test_test_node_id_resolves_to_its_file(self):
        (anchor,) = ma.extract_anchors(
            "`tests/test_harness_publication.py::test_planted_restricted_artifact_is_reported`",
            Path("x.md"),
        )
        self.assertEqual(anchor.path, "tests/test_harness_publication.py")
        self.assertTrue(ma.resolve(anchor, REPO))

    def test_skipped_sources_contribute_no_anchors(self):
        # docs/design/ cites paths it is about to create; docs/architecture.md is
        # stale and scheduled for deletion. Neither may fail the gate.
        anchors = ma.collect([Path("docs")], REPO)
        sources = {str(a.source) for a in anchors}
        self.assertFalse([s for s in sources if s.startswith("docs/design/")])
        self.assertNotIn("docs/architecture.md", sources)

    def test_no_stale_skips_in_this_repo(self):
        self.assertEqual(ma.stale_skips(REPO), [])

    def test_stale_skip_is_reported_when_its_subject_is_gone(self):
        # Mirrors test_declared_absent_path_that_now_exists_is_reported: a
        # SKIP_PATHS entry that outlives its subject is a silent hole, so an
        # empty root (naming neither docs/design/ nor docs/architecture.md)
        # must surface both as stale.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale = ma.stale_skips(root)
            self.assertIn("docs/architecture.md", stale)
            self.assertIn("docs/design/", stale)

    def test_declared_absent_path_resolves(self):
        # Cited in order to say it is not there; must not fail the gate.
        (anchor,) = ma.extract_anchors("`events/live_evidence.jsonl`", Path("x.md"))
        self.assertIn(anchor.path, ma.DECLARED_ABSENT)
        self.assertTrue(ma.resolve(anchor, REPO))

    def test_declared_absent_path_that_now_exists_is_reported(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "events").mkdir()
            (root / "events" / "live_evidence.jsonl").write_text("{}\n")
            stale = ma.stale_absences(root)
            self.assertIn("events/live_evidence.jsonl", stale)

    def test_no_stale_absences_in_this_repo(self):
        self.assertEqual(ma.stale_absences(REPO), [])


class CliTests(unittest.TestCase):
    def test_check_passes_on_the_repo_docs(self):
        self.assertEqual(ma.main(["check", "docs"]), 0)

    def test_check_fails_on_a_broken_anchor(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "broken.md"
            bad.write_text("this cites `src/disasterpilot/sources/usgs.py`\n")
            self.assertEqual(ma.main(["check", str(bad)]), 1)


if __name__ == "__main__":
    unittest.main()
