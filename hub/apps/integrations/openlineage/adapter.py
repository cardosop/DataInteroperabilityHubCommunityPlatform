"""
Phase 228 F4 (228.F4.5) — outbound OpenLineage event emitter.

The adapter is the only HTTP boundary in the F4 surface. Every
other module operates on dicts; the adapter takes a translated
event + the receiver URL + the owning tenant, performs the POST
with exponential backoff, and either returns
``DeliveryOutcome.DELIVERED`` or persists an
:class:`OpenLineageDeadLetter` row and returns
``DeliveryOutcome.DEAD_LETTERED``.

Backoff schedule (REQ-LIN-F4-002): ``1s → 2s → 4s → 8s → 16s``,
max 5 attempts. After the 5th failed attempt the event is
dead-lettered with the encrypted payload + the failure context;
the operator-driven ``replay_openlineage_dlq`` command picks up
from there.

Status-code classification:

* ``2xx`` → delivered.
* ``408`` (Request Timeout) / ``429`` (Too Many Requests) → retryable.
* Other ``4xx`` → permanent — DLQ immediately, no retries.
* ``5xx`` → retryable.
* ``ConnectionError`` / ``Timeout`` (network exception) → retryable.

Idempotency: the adapter does NOT dedupe — that's the receiver's
job (Marquez deduplicates by ``run.runId`` natively). Re-emission
of the same event_id is therefore safe under the OpenLineage spec.

The adapter exposes a synchronous ``deliver`` API; the
``send_openlineage_event_async`` RQ task in
:mod:`.tasks` is the canonical fire-and-forget entry-point that
wraps ``deliver`` with the worker context.
"""
from __future__ import annotations

import enum
import json
import logging
import time
import uuid
from typing import Any

import requests


logger = logging.getLogger(__name__)


# REQ-LIN-F4-002: 1s → 2s → 4s → 8s → 16s. The 5th attempt has no
# trailing sleep (we sleep BEFORE each retry, not after the final).
DEFAULT_BACKOFF_SCHEDULE = (1, 2, 4, 8, 16)
"""Each entry is the sleep duration BEFORE the next attempt."""

DEFAULT_MAX_ATTEMPTS = 5

# Retryable status codes per RFC 7231 + REST best-practice.
RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


class DeliveryOutcome(str, enum.Enum):
    DELIVERED = "delivered"
    DEAD_LETTERED = "dead_lettered"


def _record_outbound_metric(*, result: str, tenant_id: str) -> None:
    """Emit ``openlineage_outbound_total{result, tenant_id}`` per
    REQ-LIN-F4-001. Best-effort: a metrics-emit failure must not
    fail the dispatch path."""
    try:
        from hub.apps.observability.metrics import openlineage_outbound_total
    except Exception:  # noqa: BLE001 — metrics module optional
        return
    try:
        openlineage_outbound_total.labels(
            result=result, tenant_id=tenant_id,
        ).inc()
    except Exception:  # noqa: BLE001 — best-effort
        logger.debug(
            "openlineage_outbound_metric_emit_failed",
            extra={"result": result, "tenant_id": tenant_id},
        )


class OpenLineageAdapter:
    """Synchronous outbound emitter. Exposes :meth:`deliver`."""

    def __init__(
        self,
        *,
        backoff_schedule: tuple[int, ...] = DEFAULT_BACKOFF_SCHEDULE,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        request_timeout_seconds: float = 10.0,
    ):
        if max_attempts > len(backoff_schedule) + 1:
            # Each ATTEMPT (after the first) consumes one entry of the
            # schedule. ``max_attempts=5`` requires 4 sleep entries; the
            # default schedule has 5 entries which is room enough plus
            # a safety margin.
            raise ValueError(
                f"max_attempts={max_attempts} exceeds the backoff "
                f"schedule length {len(backoff_schedule)}"
            )
        self.backoff_schedule = backoff_schedule
        self.max_attempts = max_attempts
        self.request_timeout_seconds = request_timeout_seconds
        self._session = requests.Session()

    # ------------------------------------------------------------------

    def deliver(
        self,
        *,
        event: dict[str, Any],
        target_url: str,
        tenant,
        hmac_signature: str | None = None,
    ) -> DeliveryOutcome:
        """POST one OpenLineage event to ``target_url``.

        Returns :class:`DeliveryOutcome` describing the terminal
        state. On ``DEAD_LETTERED`` an :class:`OpenLineageDeadLetter`
        row is persisted with the encrypted payload + failure
        context; the caller does not need to handle the DLQ
        directly.

        Emits :data:`openlineage_outbound_total` per
        REQ-LIN-F4-001:

        * ``result=success`` increments once on the first 2xx response.
        * ``result=retry`` increments **per transient retry** (so a
          1-retry-then-success delivery emits ``retry=1, success=1``).
        * ``result=dlq`` increments once when the row is persisted.
        """
        body = json.dumps(event, sort_keys=True).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Marquez accepts events without auth; staging is locked
            # behind VPC + mTLS per ADR-LIN-009 / 228.F4.16.
        }
        if hmac_signature:
            headers["X-Meshant-Signature"] = hmac_signature

        last_failure: tuple[str, str] = ("UNKNOWN", "")
        tenant_id = str(getattr(tenant, "id", "")) or "unknown"

        for attempt in range(1, self.max_attempts + 1):
            outcome = self._attempt_once(
                target_url=target_url,
                body=body,
                headers=headers,
                attempt=attempt,
            )
            if outcome == "delivered":
                _record_outbound_metric(result="success", tenant_id=tenant_id)
                return DeliveryOutcome.DELIVERED
            if outcome == "permanent":
                # Permanent — no retry; DLQ now.
                last_failure = self._last_failure_for_attempt
                break
            # Transient: retry if we have attempts left.
            last_failure = self._last_failure_for_attempt
            _record_outbound_metric(result="retry", tenant_id=tenant_id)
            if attempt < self.max_attempts:
                sleep_seconds = self.backoff_schedule[attempt - 1]
                logger.info(
                    "openlineage_adapter_retry",
                    extra={
                        "attempt": attempt,
                        "next_sleep_seconds": sleep_seconds,
                        "target_url": target_url,
                        "reason": last_failure[0],
                    },
                )
                time.sleep(sleep_seconds)

        # All attempts exhausted (or permanent failure) — DLQ.
        self._dead_letter(
            event=event,
            tenant=tenant,
            target_url=target_url,
            attempts=attempt,
            failure_reason=last_failure[0],
            failure_detail=last_failure[1],
        )
        _record_outbound_metric(result="dlq", tenant_id=tenant_id)
        return DeliveryOutcome.DEAD_LETTERED

    # ------------------------------------------------------------------

    def _attempt_once(
        self,
        *,
        target_url: str,
        body: bytes,
        headers: dict[str, str],
        attempt: int,
    ) -> str:
        """Return ``'delivered'``, ``'transient'``, or ``'permanent'``."""
        try:
            resp = self._session.post(
                target_url,
                data=body,
                headers=headers,
                timeout=self.request_timeout_seconds,
            )
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exc:
            self._last_failure_for_attempt = ("network_error", str(exc))
            return "transient"
        except requests.exceptions.RequestException as exc:
            # Anything else from requests (e.g., MissingSchema, InvalidURL)
            # is permanent — retrying won't fix a malformed request.
            self._last_failure_for_attempt = ("request_error", str(exc))
            return "permanent"

        if 200 <= resp.status_code < 300:
            return "delivered"
        if resp.status_code in RETRYABLE_STATUS_CODES:
            self._last_failure_for_attempt = (
                f"http_{resp.status_code}",
                (resp.text or "")[:2048],
            )
            return "transient"
        # Other 4xx → permanent.
        self._last_failure_for_attempt = (
            f"http_{resp.status_code}",
            (resp.text or "")[:2048],
        )
        return "permanent"

    # ------------------------------------------------------------------

    def _dead_letter(
        self,
        *,
        event: dict[str, Any],
        tenant,
        target_url: str,
        attempts: int,
        failure_reason: str,
        failure_detail: str,
    ) -> None:
        """Persist an :class:`OpenLineageDeadLetter` row with the
        encrypted payload + failure context.

        Setting ``OpenLineageDeadLetter.event_payload`` (the property
        setter) routes through the in-house encryption helper, so the
        column at rest never holds plaintext.
        """
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )

        run_id = (event.get("run") or {}).get("runId") or str(uuid.uuid4())
        row = OpenLineageDeadLetter(
            tenant=tenant,
            event_id=str(run_id),
            target_url=target_url,
            failure_reason=failure_reason[:255],
            failure_detail=failure_detail or "",
            attempts=attempts,
        )
        # Property setter encrypts.
        row.event_payload = event
        row.save()

        logger.warning(
            "openlineage_adapter_dlq",
            extra={
                "tenant_id": str(getattr(tenant, "id", "")),
                "event_id": str(run_id),
                "attempts": attempts,
                "failure_reason": failure_reason,
                "target_url": target_url,
            },
        )


__all__ = [
    "DEFAULT_BACKOFF_SCHEDULE",
    "DEFAULT_MAX_ATTEMPTS",
    "DeliveryOutcome",
    "OpenLineageAdapter",
    "RETRYABLE_STATUS_CODES",
]
