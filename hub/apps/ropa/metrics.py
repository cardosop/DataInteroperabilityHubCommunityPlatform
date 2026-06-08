"""285.14.8.4 — RoPA module metrics."""
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

    ropa_generated_total: Counter | _MetricLike = Counter(
        "ropa_generated_total",
        "Total RoPA reports generated.",
        ["tenant_id", "regulation"],
    )
    ropa_export_total: Counter | _MetricLike = Counter(
        "ropa_export_total",
        "Total RoPA report exports.",
        ["tenant_id", "format"],
    )

except Exception:  # pragma: no cover
    ropa_generated_total = _MetricStub()
    ropa_export_total = _MetricStub()
