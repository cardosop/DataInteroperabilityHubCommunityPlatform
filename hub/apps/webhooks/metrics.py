"""
Phase 233.6 — Cross-cutting Prometheus metrics for the webhook surface.

Exposes the two metrics 233.6.2 names (alongside
``meshant_webhook_rate_limit_blocks_total`` which lives in
``rate_limit.py`` co-located with its emission path):

* ``meshant_webhook_outbound_total`` — Counter of outbound webhook
  delivery attempts at every lifecycle point, labelled by
  ``{tenant_id, webhook_id, event_type, outcome}``. The ``outcome``
  label has SIX values spanning the full delivery lifecycle:

  Trigger-time outcomes (one per call to ``trigger_webhook``):

    * ``triggered``         — platform initiated dispatch
    * ``rate_limited``      — per-tenant rate limit blocked the call
    * ``duplicate_skipped`` — idempotency check matched a prior SUCCESS

  Terminal-state outcomes (one per call to ``_attempt_delivery`` that
  reaches a terminal state):

    * ``delivered_success``     — HTTP 2xx, ``DeliveryStatus.SUCCESS``
    * ``delivered_failed``      — non-recoverable error, ``DeliveryStatus.FAILED``
    * ``delivered_dead_letter`` — max retries exhausted, ``DeliveryStatus.DEAD_LETTER``

  Trigger-time + terminal-state are at DIFFERENT lifecycle points
  for the same delivery: a healthy delivery emits ``triggered`` once
  AND ``delivered_success`` once (rate ≈ rate). A platform-wide
  divergence between the two rates means the dispatch worker is
  failing or the retry storm is consuming the rate-limit budget.

* ``meshant_webhook_signature_verification_duration_seconds`` —
  Histogram of HMAC-SHA256 signature COMPUTATION duration on the
  outbound-signing path. The label name "verification" matches the
  spec's literal wording (Phase 233.6.2); the metric measures the
  time spent computing the signature that a SUBSCRIBER will later
  verify (the two times are functionally equal — same HMAC operation,
  same payload size). Bucketed against the typical sub-millisecond
  signature work; outliers indicate either a very large payload or
  an encryption-backend slowdown (KMS round-trip latency on the
  ``decrypt_secret`` call before HMAC).

Defensive fallback: if ``prometheus_client`` is not installed (test
environments, isolated CI runners), both metrics are stubs with
``labels()`` + ``inc()`` + ``observe()`` no-ops. Mirrors the pattern
in ``hub.apps.observability.cross_tenant_metrics`` and the rate-limit
counter in ``rate_limit.py``.

Bounded-cardinality labels: subscriber URL is deliberately excluded
from every metric (a tenant could have hundreds of webhooks each
pointing at unique URLs across rotations). The ``webhook_id`` label
is sufficient — operators can join with the webhook table to recover
URLs when needed.
"""
from __future__ import annotations
from typing import Protocol

import structlog


logger = structlog.get_logger(__name__)


class _OutboundCounter(Protocol):
    """Structural type covering both prometheus_client.Counter and the stub."""

    def labels(self, **kwargs: str) -> "_OutboundCounter": ...

    def inc(self) -> None: ...


class _SignatureHistogram(Protocol):
    """Structural type covering both prometheus_client.Histogram and the stub."""

    def labels(self, **kwargs: str) -> "_SignatureHistogram": ...

    def observe(self, amount: float) -> None: ...


# Histogram buckets in seconds. HMAC-SHA256 of a typical webhook payload
# (1-10 KB) takes microseconds on modern CPUs; the bucket boundaries
# below capture the typical sub-ms work AND the long tail when
# ``decrypt_secret`` round-trips KMS or Fernet.
_SIGNATURE_DURATION_BUCKETS = (
    0.0001,   # 100 µs — typical sub-ms HMAC
    0.0005,   # 500 µs
    0.001,    # 1 ms — boundary where work becomes user-perceptible
    0.005,    # 5 ms — reasonable upper bound for HMAC + decrypt
    0.01,     # 10 ms — slow path, KMS round-trip
    0.05,     # 50 ms — very slow, investigation threshold
    0.1,      # 100 ms — alert threshold
    0.5,      # 500 ms — pathological
    1.0,      # 1 s — should never happen
)


try:
    from prometheus_client import Counter, Histogram

    webhook_outbound_total: _OutboundCounter = Counter(
        "meshant_webhook_outbound_total",
        (
            "Outbound webhook delivery attempts at trigger time. "
            "outcome=triggered means the platform initiated dispatch; "
            "outcome=rate_limited means the per-tenant rate limit "
            "blocked the delivery; outcome=duplicate_skipped means "
            "the idempotency check matched a prior SUCCESS."
        ),
        ["tenant_id", "webhook_id", "event_type", "outcome"],
    )

    webhook_signature_verification_duration_seconds: _SignatureHistogram = Histogram(
        "meshant_webhook_signature_verification_duration_seconds",
        (
            "HMAC-SHA256 signature computation duration on outbound "
            "deliveries. Includes the ``decrypt_secret`` round-trip "
            "(KMS or Fernet) plus the HMAC operation. "
            "Spec-named 'verification' (Phase 233.6.2 literal) — the "
            "compute time on our side equals the verification time on "
            "the subscriber side for the same HMAC + payload."
        ),
        ["tenant_id", "webhook_id"],
        buckets=_SIGNATURE_DURATION_BUCKETS,
    )

except Exception:  # pragma: no cover — defensive fallback
    class _CounterStub:
        def labels(self, **_: object) -> "_CounterStub":  # noqa: ARG002
            return self

        def inc(self) -> None:
            return None

    class _HistogramStub:
        def labels(self, **_: object) -> "_HistogramStub":  # noqa: ARG002
            return self

        def observe(self, _amount: float) -> None:  # noqa: ARG002
            return None

    webhook_outbound_total = _CounterStub()
    webhook_signature_verification_duration_seconds = _HistogramStub()


# ---------------------------------------------------------------------------
# Helper functions — best-effort emission so a metric-backend outage MUST
# NOT roll back the actual delivery work.
# ---------------------------------------------------------------------------


def emit_outbound_attempt(
    *,
    tenant_id: str,
    webhook_id: str,
    event_type: str,
    outcome: str,
) -> None:
    """Increment the outbound-attempt counter.

    ``outcome`` MUST be one of: ``triggered``, ``rate_limited``,
    ``duplicate_skipped``, ``delivered_success``, ``delivered_failed``,
    ``delivered_dead_letter``. Other values are accepted (cardinality
    is bounded by the call sites — operators add new outcomes by
    editing the call site, not the metric definition) but the
    documented set is the supported one for dashboarding.
    """
    try:
        webhook_outbound_total.labels(
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
            outcome=outcome,
        ).inc()
    except Exception as exc:  # pragma: no cover — metric backend issues
        logger.warning(
            "webhook_outbound_metric_emit_failed",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            outcome=outcome,
            error=str(exc),
        )


def observe_signature_duration(
    *,
    tenant_id: str,
    webhook_id: str,
    duration_seconds: float,
) -> None:
    """Record a signature-computation duration measurement."""
    try:
        webhook_signature_verification_duration_seconds.labels(
            tenant_id=tenant_id,
            webhook_id=webhook_id,
        ).observe(duration_seconds)
    except Exception as exc:  # pragma: no cover — metric backend issues
        logger.warning(
            "webhook_signature_metric_emit_failed",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            error=str(exc),
        )
