"""Outcome-validity checks: the executable spatial checks of the Steward Harness."""

import unittest

from geosteward.harness.checks.outcome import (
    CheckResult,
    check_bounds,
    check_crs,
    check_join_integrity,
    check_uncertainty_present,
)


class TestCrsCheck(unittest.TestCase):
    def test_matching_crs_passes(self) -> None:
        result = check_crs("EPSG:4326")
        self.assertTrue(result.passed)
        self.assertEqual(result.check, "crs")

    def test_mismatched_crs_fails_with_both_values_in_detail(self) -> None:
        result = check_crs("EPSG:3857", expected="EPSG:4326")
        self.assertFalse(result.passed)
        self.assertIn("EPSG:3857", result.detail)
        self.assertIn("EPSG:4326", result.detail)

    def test_undeclared_crs_fails(self) -> None:
        self.assertFalse(check_crs(None).passed)


class TestJoinIntegrity(unittest.TestCase):
    def test_full_coverage_no_orphans_passes(self) -> None:
        result = check_join_integrity(["a", "b"], ["a", "b"])
        self.assertTrue(result.passed)

    def test_orphan_join_ids_fail(self) -> None:
        result = check_join_integrity(["a"], ["a", "ghost"])
        self.assertFalse(result.passed)
        self.assertIn("ghost", result.detail)

    def test_partial_coverage_below_threshold_fails(self) -> None:
        result = check_join_integrity(["a", "b", "c", "d"], ["a", "b"], min_coverage=0.9)
        self.assertFalse(result.passed)

    def test_partial_coverage_above_threshold_passes(self) -> None:
        result = check_join_integrity(["a", "b", "c", "d"], ["a", "b", "c"], min_coverage=0.7)
        self.assertTrue(result.passed)


class TestBoundsAndUncertainty(unittest.TestCase):
    def test_value_inside_bounds_passes(self) -> None:
        self.assertTrue(check_bounds("wind_kt", 120.0, 0.0, 200.0).passed)

    def test_value_outside_bounds_fails(self) -> None:
        result = check_bounds("wind_kt", 500.0, 0.0, 200.0)
        self.assertFalse(result.passed)
        self.assertIn("wind_kt", result.detail)

    def test_missing_uncertainty_field_fails(self) -> None:
        self.assertFalse(check_uncertainty_present({"value": 1}).passed)

    def test_present_uncertainty_field_passes(self) -> None:
        self.assertTrue(check_uncertainty_present({"value": 1, "uncertainty": 0.2}).passed)

    def test_as_row_is_json_ready(self) -> None:
        row = check_crs("EPSG:4326").as_row()
        self.assertEqual(row, {"check": "crs", "passed": True, "detail": row["detail"]})


if __name__ == "__main__":
    unittest.main()
