"""
Phase 216.X.5 — locked JSON schema for performance test results.

Schema (frozen by ``test_perf_record.py``):

    {
        "test_name":     str,
        "git_sha":       str,
        "timestamp_utc": str (ISO-8601 'YYYY-MM-DDTHH:MM:SSZ'),
        "measurement_ms": float,
        "budget_ms":     float,
        "passed":        bool,
        "environment":   str,
        "iterations":    int,
        "p50_ms":        float,
        "p95_ms":        float,
        "p99_ms":        float
    }

Storage layout:

* **Local**: ``.perf-results/<xdist_worker_id>/<test_name>.json``
  (gitignored). Per-worker subdirectory prevents two parallel workers
  from clobbering each other's writes.
* **CI**: uploaded to S3 bucket ``meshant-perf-results/`` after the
  nightly run; 90-day lifecycle policy. Bucket provisioning lives in
  ``infrastructure/terraform/`` and is **deferred** to the perf-infra
  deployment phase (not implemented in this code-only PR).

Regression detection: a separate nightly job (``scripts/perf_regression_check.py``,
also deferred) reads the last 7 days from S3, computes p95 of each
test's ``measurement_ms``, and opens a GitHub issue if today's run is
> 20% above that p95. The 20% threshold is documented in the spec.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

# The schema field set is locked by ``test_perf_record.py``. Any change
# to this list must update the test in lockstep so the schema lock is
# explicit and the change is reviewable.
SCHEMA_FIELDS: tuple[str, ...] = (
    "test_name",
    "git_sha",
    "timestamp_utc",
    "measurement_ms",
    "budget_ms",
    "passed",
    "environment",
    "iterations",
    "p50_ms",
    "p95_ms",
    "p99_ms",
)


@dataclass(frozen=True)
class PerfRecord:
    """Single performance measurement record."""

    test_name: str
    git_sha: str
    timestamp_utc: str
    measurement_ms: float
    budget_ms: float
    passed: bool
    environment: str
    iterations: int
    p50_ms: float
    p95_ms: float
    p99_ms: float

    def to_dict(self) -> dict:
        """Return the record as a JSON-safe dict (in canonical field order)."""
        d = asdict(self)
        return {k: d[k] for k in SCHEMA_FIELDS}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=False, indent=2)


def _git_sha() -> str:
    """Resolve the current git HEAD sha, or ``"unknown"`` if not in a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _now_iso_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _percentile(values: Sequence[float], pct: float) -> float:
    """Return the percentile of ``values`` using linear interpolation.

    Empty input returns 0.0 (avoids ``StatisticsError`` for tests that
    record zero iterations — caller is responsible for declaring the
    measurement valid).
    """
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    return float(statistics.quantiles(values, n=100, method="inclusive")[int(pct) - 1])


def build_perf_record(
    *,
    test_name: str,
    measurements_ms: Sequence[float],
    budget_ms: float,
    environment: str = "local",
    git_sha: str | None = None,
    timestamp_utc: str | None = None,
) -> PerfRecord:
    """Aggregate raw per-iteration measurements into a single record.

    Args:
        test_name: Stable test identifier (typically ``request.node.nodeid``).
        measurements_ms: Per-iteration latency measurements in milliseconds.
            MUST be non-empty and contain non-negative finite values.
        budget_ms: SLO budget for this test in milliseconds.
        environment: ``local`` / ``staging`` / ``ci`` — used by the
            S3 partition layout.
        git_sha: Override the resolved git sha (used by tests so they
            do not depend on the git CLI being installed).
        timestamp_utc: Override the timestamp (also for deterministic tests).
    """
    if not measurements_ms:
        raise ValueError("measurements_ms must be non-empty")
    if any(m < 0 or m != m for m in measurements_ms):  # NaN check via self-compare
        raise ValueError(f"measurements_ms contains invalid value(s): {measurements_ms!r}")
    if budget_ms <= 0:
        raise ValueError(f"budget_ms must be > 0, got {budget_ms!r}")
    measurement = statistics.mean(measurements_ms)
    return PerfRecord(
        test_name=test_name,
        git_sha=git_sha or _git_sha(),
        timestamp_utc=timestamp_utc or _now_iso_utc(),
        measurement_ms=measurement,
        budget_ms=budget_ms,
        passed=measurement <= budget_ms,
        environment=environment,
        iterations=len(measurements_ms),
        p50_ms=_percentile(sorted(measurements_ms), 50),
        p95_ms=_percentile(sorted(measurements_ms), 95),
        p99_ms=_percentile(sorted(measurements_ms), 99),
    )


def perf_results_dir(root: Path | str | None = None) -> Path:
    """Return the per-worker output directory for perf results.

    The directory is created if missing. Per-xdist-worker subdirectories
    prevent parallel workers from clobbering each other's writes.
    """
    base = Path(root or os.environ.get("PERF_RESULTS_DIR", ".perf-results"))
    worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    out = base / worker
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_perf_record(record: PerfRecord, *, root: Path | str | None = None) -> Path:
    """Persist a record under ``perf_results_dir()`` and return the path.

    The filename is derived from the test_name with ``/`` and ``::``
    replaced by ``_`` so it is filesystem-safe across platforms.
    """
    safe_name = record.test_name.replace("/", "_").replace("::", "_")
    out_path = perf_results_dir(root) / f"{safe_name}.json"
    out_path.write_text(record.to_json(), encoding="utf-8")
    return out_path
