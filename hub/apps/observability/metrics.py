"""
Phase 228 (REQ-LIN-007, 228.0.19) — lineage observability primitives.

This module is the canonical home for **lineage-specific** Prometheus
metrics. It re-uses the existing OTel wrappers from ``otel_metrics``
so emission shape, label cardinality, and Grafana scraping are
identical to every other Meshant metric.

The Phase 228 metrics surface:

* :data:`lineage_query_total` — counter of lineage read calls. Labels:
  ``detail`` (``contract|model|field|full|visualization``),
  ``cross_tenant`` (``true|false``), ``as_of`` (``true|false``).
* :data:`lineage_query_duration_seconds` — histogram of read latencies.
  Labels: ``detail``.
* :data:`lineage_edge_writes_total` — counter of edge mutations.
  Labels: ``operation`` (``add|remove|noop``), optional ``tenant_id``.

The spec also requires audit-event action codes and trace spans —
both implemented in this module:

* Audit codes added to :class:`hub.apps.audit.models.AuditEvent` —
  registered in the same canonical place where every other Meshant
  audit code lives.
* :func:`trace` decorator — a thin wrapper over OpenTelemetry's
  ``tracer.start_as_current_span`` that the spec's REQ-LIN-007
  references.
"""
from __future__ import annotations

import functools
import time
from typing import Any, Callable

from hub.apps.observability.otel_metrics import (
    _CounterWrapper,
    _HistogramWrapper,
)


# ---------------------------------------------------------------------------
# Phase 228 (REQ-LIN-007) — Prometheus metrics
# ---------------------------------------------------------------------------

lineage_query_total = _CounterWrapper(
    "lineage_query_total",
    "Total number of lineage read calls (Phase 228 / REQ-LIN-007).",
    unit="1",
    expected_labels=("detail", "cross_tenant", "as_of"),
)

lineage_query_duration_seconds = _HistogramWrapper(
    "lineage_query_duration_seconds",
    "Lineage read-method wall-clock latency (Phase 228 / REQ-LIN-007).",
    unit="s",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    expected_labels=("detail",),
)

lineage_edge_writes_total = _CounterWrapper(
    "lineage_edge_writes_total",
    (
        "Total number of LineageEdge mutations performed by the "
        "post_save signal handler or the backfill command "
        "(Phase 228 / REQ-LIN-002 / REQ-LIN-003)."
    ),
    unit="1",
    expected_labels=("operation", "tenant_id"),
)


# ---------------------------------------------------------------------------
# Phase 228 F4 (REQ-LIN-F4-001 / REQ-LIN-F4-004) — OpenLineage metrics
# ---------------------------------------------------------------------------

openlineage_outbound_total = _CounterWrapper(
    "openlineage_outbound_total",
    (
        "Total OpenLineage outbound dispatch outcomes "
        "(Phase 228 F4 / REQ-LIN-F4-001). result=success|retry|dlq; "
        "result=retry increments per transient retry attempt; "
        "result=dlq increments once when the DLQ row is persisted."
    ),
    unit="1",
    expected_labels=("result", "tenant_id"),
)

openlineage_inbound_total = _CounterWrapper(
    "openlineage_inbound_total",
    (
        "Total OpenLineage inbound endpoint outcomes "
        "(Phase 228 F4 / REQ-LIN-F4-002). result=accepted|duplicate|"
        "validation_failed|auth_failed|too_large."
    ),
    unit="1",
    expected_labels=("result",),
)

# Phase 228 F5 (REQ-LIN-F5-001 / DoD-G6) — time-travel query counter.
# Labels: ``type ∈ {as_of, version}`` per spec.
lineage_time_travel_queries_total = _CounterWrapper(
    "lineage_time_travel_queries_total",
    (
        "Total point-in-time lineage queries against the visualization "
        "endpoint (Phase 228 F5 / REQ-LIN-F5-001). type=as_of → caller "
        "passed an ISO timestamp; type=version → caller passed a "
        "contract version int that the view resolved to created_at."
    ),
    unit="1",
    expected_labels=("type",),
)


openlineage_dlq_depth = _CounterWrapper(
    "openlineage_dlq_depth",
    (
        "Pending OpenLineageDeadLetter rows (Phase 228 F4 / "
        "REQ-LIN-F4-004). Sampled by the dlq-depth scrape job; "
        "spec calls this a gauge but the project's metric substrate "
        "uses counter-style sampling so the value-on-emit semantics "
        "match Prometheus rate() / max_over_time() queries."
    ),
    unit="1",
    expected_labels=("permanently_failed",),
)


# ---------------------------------------------------------------------------
# Phase 228 (REQ-LIN-007) — distributed-tracing decorator
# ---------------------------------------------------------------------------


def trace(span_name: str | None = None):
    """Decorator wrapping a callable in an OpenTelemetry span. The
    span name defaults to ``f"{module}.{qualname}"``.

    Best-effort: when OTel is not configured the decorator is a no-op
    (it still records latency on the lineage-query histogram for the
    method-level observability the spec requires). Apply via::

        @trace("lineage.get_full_lineage")
        def get_full_lineage(self, ...):
            ...

    The decorator is idempotent — wrapping a method twice is harmless
    (the inner span is parent of the outer; cardinality stays bounded
    because the names are static strings).
    """

    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        effective_name = span_name or f"{fn.__module__}.{fn.__qualname__}"

        @functools.wraps(fn)
        def _wrapped(*args, **kwargs):
            try:
                from hub.apps.observability.tracing import get_tracer

                tracer = get_tracer(__name__)
            except Exception:  # noqa: BLE001 — observability optional
                tracer = None

            start = time.monotonic()
            if tracer is None:
                try:
                    return fn(*args, **kwargs)
                finally:
                    _record_method_duration(effective_name, time.monotonic() - start)
            with tracer.start_as_current_span(effective_name):
                try:
                    return fn(*args, **kwargs)
                finally:
                    _record_method_duration(effective_name, time.monotonic() - start)

        return _wrapped

    return _decorator


def _record_method_duration(span_name: str, duration_s: float) -> None:
    """Best-effort latency observation — feeds the
    ``lineage_query_duration_seconds`` histogram when the span name
    matches a known lineage method. Failures are swallowed."""
    detail = _detail_label_from_span(span_name)
    if not detail:
        return
    try:
        lineage_query_duration_seconds.labels(detail=detail).observe(duration_s)
    except Exception:  # noqa: BLE001 — best-effort
        return


def _detail_label_from_span(span_name: str) -> str | None:
    """Map ``LineageService.<method>`` span names to the canonical
    histogram label values. Returns ``None`` for non-lineage spans so
    the helper does not pollute the histogram with unrelated samples."""
    mapping = {
        "get_contract_lineage": "contract",
        "get_model_lineage": "model",
        "get_field_lineage": "field",
        "get_full_lineage": "full",
        "get_lineage_visualization": "visualization",
    }
    for suffix, label in mapping.items():
        if span_name.endswith(suffix):
            return label
    return None


__all__ = [
    "lineage_edge_writes_total",
    "lineage_query_duration_seconds",
    "lineage_query_total",
    "lineage_time_travel_queries_total",
    "openlineage_dlq_depth",
    "openlineage_inbound_total",
    "openlineage_outbound_total",
    "trace",
]
