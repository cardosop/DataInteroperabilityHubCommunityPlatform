"""285.14.8.4 — Processor Agreement metrics."""

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

    processor_agreement_created_total: Counter | _MetricLike = Counter(
        "processor_agreement_created_total",
        "Total processor agreements created.",
        ["tenant_id"],
    )
    processor_agreement_signed_total: Counter | _MetricLike = Counter(
        "processor_agreement_signed_total",
        "Total processor agreements signed.",
        ["tenant_id"],
    )
    processor_agreement_expired_total: Counter | _MetricLike = Counter(
        "processor_agreement_expired_total",
        "Processor agreements past expiry date.",
        ["tenant_id"],
    )

except Exception:  # pragma: no cover
    processor_agreement_created_total = _MetricStub()
    processor_agreement_signed_total = _MetricStub()
    processor_agreement_expired_total = _MetricStub()
