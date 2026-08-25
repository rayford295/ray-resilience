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
        # docs/design/ cites paths it is about to create, so it may not fail
        # the gate.
        anchors = ma.collect([Path("docs")], REPO)
        sources = {str(a.source) for a in anchors}
        self.assertFalse([s for s in sources if s.startswith("docs/design/")])

    def test_no_stale_skips_in_this_repo(self):
        self.assertEqual(ma.stale_skips(REPO), [])

    def test_stale_skip_is_reported_when_its_subject_is_gone(self):
        # Mirrors test_declared_absent_path_that_now_exists_is_reported: a
        # SKIP_PATHS entry that outlives its subject is a silent hole, so an
        # empty root (naming none of SKIP_PATHS's subjects) must surface
        # every entry as stale.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale = ma.stale_skips(root)
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


class GeneratedPathTests(unittest.TestCase):
    def test_generated_path_resolves_when_absent(self):
        # app/dist doesn't exist in a fresh checkout -- npm run build hasn't
        # run -- but the citation is still correct and must resolve.
        (anchor,) = ma.extract_anchors("`app/dist`", Path("x.md"))
        self.assertIn(anchor.path, ma.GENERATED_PATHS)
        self.assertTrue(ma.resolve(anchor, REPO))

    def test_generated_path_resolves_when_present(self):
        # On a machine that HAS built the app, the path exists on disk too.
        # A generated path must resolve either way -- that's what makes it
        # different from an ordinary anchor.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app" / "dist").mkdir(parents=True)
            (anchor,) = ma.extract_anchors("`app/dist`", Path("x.md"))
            self.assertTrue(ma.resolve(anchor, root))

    def test_generated_path_trailing_slash_variants_both_resolve(self):
        # The manual cites app/public/events/ with and without the
        # trailing slash across different lines; both must resolve.
        anchors = ma.extract_anchors("`app/public/events` and `app/public/events/`", Path("x.md"))
        self.assertEqual(len(anchors), 2)
        for anchor in anchors:
            self.assertTrue(ma.resolve(anchor, REPO))

    def test_entry_not_in_gitignore_is_reported(self):
        # This is the self-policing check: a GENERATED_PATHS entry that
        # isn't actually git-ignored is indistinguishable from a typo that
        # happens not to exist yet, and must be caught the same way a
        # stale absence or a stale skip is.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".gitignore").write_text("some/other/path/\n")
            stale = ma.stale_generated_paths(root)
            self.assertEqual(set(stale), set(ma.GENERATED_PATHS))

    def test_no_stale_generated_paths_in_this_repo(self):
        # Mirrors test_no_stale_skips_in_this_repo /
        # test_no_stale_absences_in_this_repo: the repo's own .gitignore
        # must actually cover every entry in GENERATED_PATHS right now.
        self.assertEqual(ma.stale_generated_paths(REPO), [])

    def test_generated_paths_seeded_with_exactly_the_two_build_outputs(self):
        self.assertEqual(
            {p.rstrip("/") for p in ma.GENERATED_PATHS},
            {"app/dist", "app/public/events"},
        )


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
