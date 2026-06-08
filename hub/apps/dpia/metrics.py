"""285.14.8.4 — DPIA module metrics."""
from __future__ import annotations
from typing import Protocol


class _MetricLike(Protocol):
    def labels(self, **kwargs: str) -> "_MetricLike": ...
    def inc(self, amount: float = 1) -> None: ...


class _MetricStub:
    def labels(self, **_: object) -> "_MetricStub":
        return self
    def inc(self, _amount: float = 1) -> None:
        return None


try:
    from prometheus_client import Counter

    dpia_created_total: Counter | _MetricLike = Counter(
        "dpia_created_total",
        "Total DPIAs created.",
        ["tenant_id"],
    )
    dpia_completed_total: Counter | _MetricLike = Counter(
        "dpia_completed_total",
        "Total DPIAs completed (approved).",
        ["tenant_id", "risk_level"],
    )
    dpia_review_overdue_total: Counter | _MetricLike = Counter(
        "dpia_review_overdue_total",
        "DPIAs past scheduled review date.",
        ["tenant_id"],
    )

except Exception:  # pragma: no cover
    dpia_created_total = _MetricStub()
    dpia_completed_total = _MetricStub()
    dpia_review_overdue_total = _MetricStub()
