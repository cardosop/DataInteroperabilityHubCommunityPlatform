"""285.14.8.4 — DSAR module metrics."""

from __future__ import annotations

from typing import Protocol


class _MetricLike(Protocol):
    def labels(self, **kwargs: str) -> _MetricLike: ...
    def inc(self, amount: float = 1) -> None: ...


class _MetricStub:
    def labels(self, **_: object) -> _MetricStub:
        return self

    def inc(self, _amount: float = 1) -> None:
        return None


try:
    from prometheus_client import Counter

    dsar_submitted_total: Counter | _MetricLike = Counter(
        "dsar_submitted_total",
        "Total DSAR requests submitted.",
        ["tenant_id", "request_type"],
    )
    dsar_completed_total: Counter | _MetricLike = Counter(
        "dsar_completed_total",
        "Total DSAR requests completed.",
        ["tenant_id", "request_type", "outcome"],
    )
    dsar_overdue_total: Counter | _MetricLike = Counter(
        "dsar_overdue_total",
        "DSAR requests past statutory deadline.",
        ["tenant_id"],
    )
    dsar_rejected_total: Counter | _MetricLike = Counter(
        "dsar_rejected_total",
        "DSAR requests rejected (with justification).",
        ["tenant_id", "reason"],
    )

except ImportError:  # pragma: no cover
    dsar_submitted_total = _MetricStub()
    dsar_completed_total = _MetricStub()
    dsar_overdue_total = _MetricStub()
    dsar_rejected_total = _MetricStub()
