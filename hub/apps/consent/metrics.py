"""285.14.8.4 — Consent module metrics."""
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

    consent_granted_total: Counter | _MetricLike = Counter(
        "consent_granted_total",
        "Total consent grants.",
        ["tenant_id", "purpose"],
    )
    consent_withdrawn_total: Counter | _MetricLike = Counter(
        "consent_withdrawn_total",
        "Total consent withdrawals.",
        ["tenant_id", "purpose"],
    )
    consent_verification_total: Counter | _MetricLike = Counter(
        "consent_verification_total",
        "Total consent verifications performed.",
        ["tenant_id", "result"],
    )

except Exception:  # pragma: no cover
    consent_granted_total = _MetricStub()
    consent_withdrawn_total = _MetricStub()
    consent_verification_total = _MetricStub()
