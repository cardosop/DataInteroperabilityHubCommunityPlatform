"""285.14.8.4 — Breach notification metrics."""

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

    breach_reported_total: Counter | _MetricLike = Counter(
        "breach_reported_total",
        "Total breach notifications filed.",
        ["tenant_id", "severity"],
    )
    breach_notified_total: Counter | _MetricLike = Counter(
        "breach_notified_total",
        "Total regulatory/DPA notifications sent.",
        ["tenant_id", "regulation"],
    )
    breach_sla_breach_total: Counter | _MetricLike = Counter(
        "breach_sla_breach_total",
        "Breach notifications past 72h statutory deadline.",
        ["tenant_id"],
    )

except Exception:  # pragma: no cover
    breach_reported_total = _MetricStub()
    breach_notified_total = _MetricStub()
    breach_sla_breach_total = _MetricStub()
