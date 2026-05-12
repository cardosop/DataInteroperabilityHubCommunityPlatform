"""
Phase 273.4 — search / SPARQL OTel metrics.

Bounded-cardinality label fallback (UNKNOWN) per the L7 helpers
convention. All record_* functions are best-effort — metric-backend
outage MUST NOT fail the search/SPARQL response.
"""
from __future__ import annotations

from typing import Protocol


class _MetricLike(Protocol):
    def labels(self, **kwargs: str) -> "_MetricLike": ...

    def inc(self, amount: float = 1) -> None: ...

    def observe(self, amount: float) -> None: ...


class _MetricStub:
    def labels(self, **_: object) -> "_MetricStub":
        return self

    def inc(self, _amount: float = 1) -> None:
        return None

    def observe(self, _amount: float) -> None:
        return None


# ── Metric definitions ─────────────────────────────────────────────────

try:
    from prometheus_client import Counter, Histogram

    search_request_duration_seconds: Histogram | _MetricLike = Histogram(
        "search_request_duration_seconds",
        "Phase 273.4 — search request duration histogram.",
        ["kind", "outcome"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    )

    search_results_count_total: Counter | _MetricLike = Counter(
        "search_results_count_total",
        "Phase 273.4 — total results returned by search, labelled by kind.",
        ["kind"],
    )

    search_no_result_total: Counter | _MetricLike = Counter(
        "search_no_result_total",
        "Phase 273.4 — empty-result searches, labelled by kind.",
        ["kind"],
    )

    search_query_length_bytes: Histogram | _MetricLike = Histogram(
        "search_query_length_bytes",
        "Phase 273.4 — search query length in bytes.",
        ["kind"],
        buckets=(1, 4, 16, 64, 256, 512, 1024, 2048),
    )

    sparql_execution_seconds: Histogram | _MetricLike = Histogram(
        "sparql_execution_seconds",
        "Phase 273.4 — SPARQL execution duration histogram.",
        ["outcome"],
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0),
    )

    sparql_timeout_total: Counter | _MetricLike = Counter(
        "sparql_timeout_total",
        "Phase 273.4 — SPARQL timeout counter.",
        [],
    )

except Exception:  # pragma: no cover
    search_request_duration_seconds = _MetricStub()
    search_results_count_total = _MetricStub()
    search_no_result_total = _MetricStub()
    search_query_length_bytes = _MetricStub()
    sparql_execution_seconds = _MetricStub()
    sparql_timeout_total = _MetricStub()

_VALID_KINDS = frozenset({"fts", "sparql", "listing", "ai"})
_VALID_OUTCOMES = frozenset({"success", "empty", "error", "throttled"})


def record_search(
    *,
    kind: str,
    outcome: str,
    duration_s: float,
    result_count: int,
    query_length: int = 0,
) -> None:
    """Record search metrics with bounded-cardinality label fallback."""
    _kind = kind if kind in _VALID_KINDS else "fts"
    _outcome = outcome if outcome in _VALID_OUTCOMES else "success"

    try:
        search_request_duration_seconds.labels(kind=_kind, outcome=_outcome).observe(duration_s)
    except Exception:
        pass
    try:
        search_results_count_total.labels(kind=_kind).inc(float(result_count))
    except Exception:
        pass
    if result_count == 0:
        try:
            search_no_result_total.labels(kind=_kind).inc()
        except Exception:
            pass
    if query_length > 0:
        try:
            search_query_length_bytes.labels(kind=_kind).observe(float(query_length))
        except Exception:
            pass


def record_sparql(
    *,
    duration_s: float,
    outcome: str,
    timed_out: bool = False,
) -> None:
    """Record SPARQL execution metrics."""
    _outcome = outcome if outcome in _VALID_OUTCOMES else "success"

    try:
        sparql_execution_seconds.labels(outcome=_outcome).observe(duration_s)
    except Exception:
        pass
    if timed_out:
        try:
            sparql_timeout_total.inc()
        except Exception:
            pass
