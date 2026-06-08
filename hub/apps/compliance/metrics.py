"""285.14.8.4 — Compliance scan metrics."""
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


try:
    from prometheus_client import Counter, Histogram

    compliance_scan_total: Counter | _MetricLike = Counter(
        "compliance_scan_total",
        "Total compliance scans started.",
        ["tenant_id", "framework", "regulation_key"],
    )
    compliance_scan_completed_total: Counter | _MetricLike = Counter(
        "compliance_scan_completed_total",
        "Total compliance scans completed.",
        ["tenant_id", "outcome"],
    )
    compliance_scan_failed_total: Counter | _MetricLike = Counter(
        "compliance_scan_failed_total",
        "Total compliance scans that failed.",
        ["tenant_id", "reason"],
    )
    compliance_scan_duration_seconds: Histogram | _MetricLike = Histogram(
        "compliance_scan_duration_seconds",
        "Compliance scan duration histogram.",
        ["framework"],
        buckets=(1, 5, 10, 30, 60, 120, 300, 600),
    )

except Exception:  # pragma: no cover
    compliance_scan_total = _MetricStub()
    compliance_scan_completed_total = _MetricStub()
    compliance_scan_failed_total = _MetricStub()
    compliance_scan_duration_seconds = _MetricStub()
