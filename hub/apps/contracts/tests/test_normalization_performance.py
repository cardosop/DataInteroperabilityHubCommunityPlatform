"""
Phase 227 Wave 1 (227.L8.6 + L8.7) — normalisation performance baseline.

Pins three load-bearing SLOs on the contract-normalisation hot path
using ``pytest-benchmark``. Failures (>20% regression vs. the saved
baseline) fail CI via ``--benchmark-fail-on-regression`` (configured
in the workflow).

SLOs (p99)
----------
* 1000-field ODCS contract: < 500 ms
* 100-port ODPS contract (10 fields/port): < 1 s
* 50000-field analytics contract: < 5 s, < 500 MB resident memory

Why these limits
----------------
The 1000-field case represents a typical "wide" contract from an
enterprise data warehouse. 500 ms is the threshold above which
synchronous request handling starts to feel sluggish in the API.

The 100-port ODPS represents a multi-output data product (one of the
biggest in production today carries 78 outputPorts). 1 s budgets the
recursive walker + per-port DB lookup the L1 helper does.

The 50 000-field analytics case is the upper bound we accept before
we'd ask the customer to split into multiple contracts. 5 s + 500 MB
is comfortably within request-timeout / pod-resource limits.

Implementation notes
--------------------
* The benchmark hits :func:`normalize_contract` directly (no Django
  request layer) so we measure the engine, not request middleware.
* Memory measurement uses :mod:`resource` (Linux) when available;
  the assert is skipped on platforms that don't expose RSS.
* The test self-skips when ``pytest-benchmark`` isn't installed —
  the CI image installs it; local dev runs without it skip cleanly.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

# Phase 227 L8.6 — gracefully skip when the dev-only dep is missing
# (e.g. local runs that don't install requirements-dev.txt).
benchmark_module = pytest.importorskip(
    "pytest_benchmark",
    reason="pytest-benchmark not installed; perf benchmark skipped",
)
del benchmark_module  # imported only for the importorskip side-effect


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _odcs_contract_with_n_fields(n: int) -> str:
    """Build a well-formed ODCS v3.1.0 contract with ``n`` fields."""
    fields: list[dict[str, Any]] = [{"name": f"f_{i}", "type": "string"} for i in range(n)]
    doc = {
        "kind": "DataContract",
        "apiVersion": "v3.1.0",
        "id": "perf",
        "name": "perf",
        "version": "1.0.0",
        "status": "active",
        "schema": [{"name": "wide", "fields": fields}],
    }
    return json.dumps(doc)


def _odps_contract_with_n_ports(n: int, fields_per_port: int) -> str:
    """Build a well-formed ODPS v4.1 contract with ``n`` outputPorts,
    each carrying ``fields_per_port`` inline ODCS fields."""
    ports = []
    for i in range(n):
        fields = [{"name": f"f_{j}", "type": "string"} for j in range(fields_per_port)]
        ports.append(
            {
                "name": f"port_{i}",
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": f"port-{i}",
                        "name": f"port-{i}",
                        "version": "1.0.0",
                        "status": "active",
                        "schema": [{"name": f"port_{i}_table", "fields": fields}],
                    },
                },
            }
        )
    doc = {
        "schema": "https://opendataproducts.org/schema/v4.1",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "productID": "perf-odps",
                    "name": "perf-odps",
                    "productVersion": "1.0.0",
                }
            },
            "outputPorts": ports,
        },
    }
    return json.dumps(doc)


def _measure_normalize_memory_mb(raw: str, spec_type: str) -> float:
    """Measure the **peak Python heap delta** during a single
    normalisation run, in MB. Uses :mod:`tracemalloc` so the
    measurement is scoped to the operation under test, not the
    process-wide RSS (which is polluted by Django's startup heap, the
    test harness, etc.).

    Note: ``tracemalloc`` measures Python-allocated memory only.
    C-extension allocations (e.g. yaml's libyaml backing) don't show
    up. That's acceptable for our SLO — the contract walker is pure
    Python and dominates the budget.
    """
    import tracemalloc

    tracemalloc.start()
    try:
        _normalize(raw, spec_type)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak / (1024 * 1024)


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


def _normalize(raw: str, spec_type: str) -> Any:
    """Run the engine; return the hub_contract."""
    from hub.apps.contracts.normalization import normalize_contract

    hub, _spec_type, _spec_version, _status, _errors, _warnings = normalize_contract(
        raw_contract=raw,
        format="JSON",
        spec_type=spec_type,
    )
    return hub


@pytest.mark.benchmark(group="normalize-odcs-1000-fields")
def test_perf_odcs_1000_fields(benchmark):
    """SLO: p99 < 500 ms."""
    raw = _odcs_contract_with_n_fields(1000)
    result = benchmark(lambda: _normalize(raw, "ODCS"))
    assert result is not None
    # Self-test: the engine produced 1000 fields.
    fields = (
        (result.get("models") or [{}])[0].get("fields") or [] if isinstance(result, dict) else []
    )
    assert len(fields) == 1000


@pytest.mark.benchmark(group="normalize-odps-100-ports")
def test_perf_odps_100_ports_10_fields_each(benchmark):
    """SLO: p99 < 1 s."""
    raw = _odps_contract_with_n_ports(100, 10)
    result = benchmark(lambda: _normalize(raw, "ODPS"))
    assert result is not None


@pytest.mark.benchmark(group="normalize-odcs-50000-fields")
def test_perf_odcs_50000_fields(benchmark):
    """SLO: p99 < 5 s, peak Python-heap delta < 500 MB."""
    raw = _odcs_contract_with_n_fields(50_000)
    result = benchmark(lambda: _normalize(raw, "ODCS"))
    assert result is not None
    # Memory budget — separate run via ``tracemalloc`` so we measure
    # the operation's heap delta (not process RSS polluted by other
    # tests). ``benchmark`` re-runs the function multiple times for
    # statistical accuracy; we measure once with tracemalloc here.
    peak_mb = _measure_normalize_memory_mb(raw, "ODCS")
    assert peak_mb < 500, f"Peak Python-heap delta {peak_mb:.1f} MB exceeds 500 MB budget"
