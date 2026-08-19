"""Outcome-validity checks: executable assertions on spatial operations.

Every check is a pure function returning a CheckResult; callers decide
whether a failed check aborts the stage (fail closed) or is recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class CheckResult:
    check: str
    passed: bool
    detail: str

    def as_row(self) -> dict[str, Any]:
        return {"check": self.check, "passed": self.passed, "detail": self.detail}


def check_crs(declared: str | None, expected: str = "EPSG:4326") -> CheckResult:
    if declared is None:
        return CheckResult("crs", False, f"CRS undeclared; expected {expected}")
    if declared != expected:
        return CheckResult("crs", False, f"CRS mismatch: declared {declared}, expected {expected}")
    return CheckResult("crs", True, f"CRS {declared} matches expected")


def check_join_integrity(
    left_ids: Iterable[str],
    joined_ids: Iterable[str],
    min_coverage: float = 1.0,
) -> CheckResult:
    left, joined = set(left_ids), set(joined_ids)
    orphans = sorted(joined - left)
    if orphans:
        return CheckResult("join_integrity", False, f"orphan join ids not in left side: {orphans}")
    coverage = len(joined & left) / len(left) if left else 0.0
    if coverage < min_coverage:
        return CheckResult(
            "join_integrity",
            False,
            f"coverage {coverage:.2%} below required {min_coverage:.2%}",
        )
    return CheckResult("join_integrity", True, f"coverage {coverage:.2%}, no orphans")


def check_bounds(name: str, value: float, minimum: float, maximum: float) -> CheckResult:
    if minimum <= value <= maximum:
        return CheckResult("bounds", True, f"{name}={value} within [{minimum}, {maximum}]")
    return CheckResult("bounds", False, f"{name}={value} outside [{minimum}, {maximum}]")


def check_uncertainty_present(payload: dict, field: str = "uncertainty") -> CheckResult:
    if field in payload:
        return CheckResult("uncertainty", True, f"field '{field}' present")
    return CheckResult("uncertainty", False, f"required field '{field}' missing")
