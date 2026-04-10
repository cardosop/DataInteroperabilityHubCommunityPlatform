import pytest

pytestmark = pytest.mark.performance

"""
Phase 216.4.1 — CLI startup latency: `datahub --help` < 500ms.

Measures wall-clock time from subprocess launch to exit. The budget is
intentionally generous (500ms) to absorb CI variability; a healthy local
machine typically does this in <200ms. The test records the measurement
to .perf-results/ via the locked perf_record schema (216.X.5).
"""

import subprocess
import sys
import time

from tests.fixtures.perf_record import build_perf_record, write_perf_record

BUDGET_MS = 500.0
ITERATIONS = 5


def _measure_startup_ms() -> float:
    """Time `datahub --help` end-to-end."""
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "datahub_cli", "--help"],
        capture_output=True,
        timeout=10,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert result.returncode == 0, (
        f"datahub --help exited {result.returncode}: {result.stderr[:300]}"
    )
    return elapsed_ms


def test_cli_startup_under_budget():
    """datahub --help must complete in <500ms (mean of 5 iterations)."""
    measurements = [_measure_startup_ms() for _ in range(ITERATIONS)]

    record = build_perf_record(
        test_name="test_cli_startup_under_budget",
        measurements_ms=measurements,
        budget_ms=BUDGET_MS,
    )
    write_perf_record(record)

    assert record.passed, (
        f"CLI startup exceeded {BUDGET_MS}ms budget: "
        f"mean={record.measurement_ms:.0f}ms "
        f"p95={record.p95_ms:.0f}ms p99={record.p99_ms:.0f}ms"
    )
