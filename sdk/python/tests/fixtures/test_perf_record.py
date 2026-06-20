"""
Phase 216.X.9 — unit tests for ``cli/tests/fixtures/perf_record.py``.

Locks the JSON schema, percentile arithmetic, file layout, and the
xdist-worker partitioning. No mocks; uses tmp_path for filesystem
isolation and explicit overrides for git_sha / timestamp.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixtures.perf_record import (
    SCHEMA_FIELDS,
    PerfRecord,
    build_perf_record,
    perf_results_dir,
    write_perf_record,
)

# ---------------------------------------------------------------------------
# Schema lock
# ---------------------------------------------------------------------------


def test_schema_fields_are_frozen() -> None:
    """The JSON schema is a contract; the field set is locked here."""
    assert SCHEMA_FIELDS == (
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


def test_record_to_dict_emits_exact_schema_keys() -> None:
    record = build_perf_record(
        test_name="t",
        measurements_ms=[10.0],
        budget_ms=20.0,
        git_sha="deadbeef",
        timestamp_utc="2026-04-08T00:00:00Z",
    )
    payload = record.to_dict()
    assert tuple(payload.keys()) == SCHEMA_FIELDS


def test_record_round_trips_through_json() -> None:
    record = build_perf_record(
        test_name="t",
        measurements_ms=[10.0, 20.0, 30.0],
        budget_ms=100.0,
        git_sha="deadbeef",
        timestamp_utc="2026-04-08T00:00:00Z",
    )
    payload = json.loads(record.to_json())
    assert payload == record.to_dict()


# ---------------------------------------------------------------------------
# build_perf_record arithmetic
# ---------------------------------------------------------------------------


def test_passed_true_when_mean_under_budget() -> None:
    record = build_perf_record(
        test_name="t",
        measurements_ms=[10.0, 12.0, 8.0],
        budget_ms=20.0,
        git_sha="x",
        timestamp_utc="2026-04-08T00:00:00Z",
    )
    assert record.passed is True
    assert record.measurement_ms == pytest.approx(10.0)


def test_passed_false_when_mean_over_budget() -> None:
    record = build_perf_record(
        test_name="t",
        measurements_ms=[100.0, 100.0, 100.0],
        budget_ms=50.0,
        git_sha="x",
        timestamp_utc="2026-04-08T00:00:00Z",
    )
    assert record.passed is False


def test_iterations_matches_input_length() -> None:
    record = build_perf_record(
        test_name="t",
        measurements_ms=[1.0] * 17,
        budget_ms=10.0,
        git_sha="x",
        timestamp_utc="2026-04-08T00:00:00Z",
    )
    assert record.iterations == 17


def test_percentiles_are_sorted_ascending() -> None:
    record = build_perf_record(
        test_name="t",
        measurements_ms=list(range(1, 101)),
        budget_ms=200.0,
        git_sha="x",
        timestamp_utc="2026-04-08T00:00:00Z",
    )
    assert record.p50_ms <= record.p95_ms <= record.p99_ms


def test_rejects_empty_measurements() -> None:
    with pytest.raises(ValueError):
        build_perf_record(
            test_name="t",
            measurements_ms=[],
            budget_ms=10.0,
            git_sha="x",
            timestamp_utc="2026-04-08T00:00:00Z",
        )


def test_rejects_negative_measurement() -> None:
    with pytest.raises(ValueError):
        build_perf_record(
            test_name="t",
            measurements_ms=[1.0, -2.0, 3.0],
            budget_ms=10.0,
            git_sha="x",
            timestamp_utc="2026-04-08T00:00:00Z",
        )


def test_rejects_zero_or_negative_budget() -> None:
    with pytest.raises(ValueError):
        build_perf_record(
            test_name="t",
            measurements_ms=[1.0],
            budget_ms=0,
            git_sha="x",
            timestamp_utc="2026-04-08T00:00:00Z",
        )


# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------


def test_perf_results_dir_is_per_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")
    monkeypatch.setenv("PERF_RESULTS_DIR", str(tmp_path / "perf"))
    out = perf_results_dir()
    assert out == tmp_path / "perf" / "gw3"
    assert out.is_dir()


def test_perf_results_dir_falls_back_to_master(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    monkeypatch.setenv("PERF_RESULTS_DIR", str(tmp_path / "perf"))
    out = perf_results_dir()
    assert out.name == "master"
    assert out.is_dir()


def test_write_perf_record_creates_file_with_safe_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PERF_RESULTS_DIR", str(tmp_path / "perf"))
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "master")
    record = build_perf_record(
        test_name="tests/test_foo.py::TestBar::test_baz",
        measurements_ms=[1.0, 2.0],
        budget_ms=10.0,
        git_sha="x",
        timestamp_utc="2026-04-08T00:00:00Z",
    )
    out = write_perf_record(record)
    # ``/`` and ``::`` are normalized to ``_``.
    assert out.name == "tests_test_foo.py_TestBar_test_baz.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["test_name"] == record.test_name
    assert payload["budget_ms"] == 10.0


def test_perfrecord_is_frozen() -> None:
    record = PerfRecord(
        test_name="t",
        git_sha="x",
        timestamp_utc="2026-04-08T00:00:00Z",
        measurement_ms=1.0,
        budget_ms=2.0,
        passed=True,
        environment="local",
        iterations=1,
        p50_ms=1.0,
        p95_ms=1.0,
        p99_ms=1.0,
    )
    with pytest.raises(Exception):
        record.test_name = "mutated"  # type: ignore[misc]
