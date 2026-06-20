"""
285.14.11.V.7 — Core shared metrics.

throttle_hit_total counter emitted on 429 (rate-limit exceeded) responses
with app, view, scope, and tenant_id tags.
"""

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

    throttle_hit_total: Counter | _MetricLike = Counter(
        "throttle_hit_total",
        "285.14.11.V.7 — total rate-limit (429) responses emitted, "
        "labelled by app, view, scope, and tenant_id.",
        ["app", "view", "scope", "tenant_id"],
    )

except Exception:  # pragma: no cover
    throttle_hit_total = _MetricStub()
