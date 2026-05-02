"""
Phase 240.1.A.1 — base client surface for DQ alert delivery.

Every channel client (EMAIL / SLACK / WEBHOOK / PAGERDUTY) MUST:

1. Subclass ``BaseAlertClient``.
2. Implement ``_deliver(rule, payload)`` returning a ``DeliveryResult``.
3. Set the class-level ``channel`` attribute to the matching
   ``DQAlertChannel`` value so ``get_client_for_channel`` can dispatch.

The public entry point is ``deliver(rule, payload)`` on the base class
— it wraps ``_deliver`` with a per-channel circuit breaker (Phase
240.1.A.6) so a flapping partner can't pin a worker on slow timeouts
forever. The breaker emits ``DQ_ALERT_CHANNEL_DEGRADED`` audit events
on state transitions; clients only need to focus on the wire-protocol
shape.
"""
from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type

from ..log_helpers import _redact


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class DeliveryResult:
    """Wire shape returned by every ``BaseAlertClient.deliver`` call.

    Attributes
    ----------
    success
        True if the partner accepted the alert (HTTP 2xx, SMTP 250,
        PagerDuty ``status="success"``). False on any non-2xx, network
        error, signature-rejection, etc.
    delivery_id
        Channel-supplied identifier (Slack ``ts``, PagerDuty
        ``dedup_key``, SendGrid message id, webhook ``X-Request-Id``)
        for cross-system trace correlation. Empty string when the
        partner doesn't return one.
    error
        Human-readable failure reason. None on success.
    metadata
        Channel-specific extras (e.g. PagerDuty ``incident_key``,
        webhook response status code) for callers that need them.
    """

    success: bool
    delivery_id: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertDeliveryError(Exception):
    """Raised by ``_deliver`` when the channel fails *unrecoverably*.

    Recoverable failures (HTTP 5xx, network timeouts) are returned as
    ``DeliveryResult(success=False)`` so the dispatcher can schedule an
    RQ retry. Raise this exception only when retry would be pointless
    (mis-configured webhook URL, malformed PagerDuty integration key).
    """


class _TransientDeliveryError(Exception):
    """Internal-only sentinel — wraps a transient ``DeliveryResult`` so
    the circuit breaker actually counts it as a failure.

    The CircuitBreaker only increments its failure counter when the
    wrapped callable RAISES; a returned-but-failed value is treated
    as success. Without this wrapper a flapping partner could 5xx
    forever and the breaker would never open.

    Caught by ``BaseAlertClient.deliver`` and unwrapped back to the
    original ``DeliveryResult`` before returning to the caller.
    """

    def __init__(self, result: DeliveryResult) -> None:
        self.result = result
        super().__init__(result.error or "transient delivery failure")


# ---------------------------------------------------------------------------
# Base client
# ---------------------------------------------------------------------------


class BaseAlertClient(abc.ABC):
    """ABC for all DQ alert-delivery clients.

    Subclasses MUST set ``channel`` to a ``DQAlertChannel`` value and
    implement ``_deliver``. ``deliver`` (the public entry-point) is
    intentionally non-abstract so subclasses can't accidentally bypass
    the circuit-breaker wrapping.
    """

    #: Channel this client handles. Subclasses override.
    channel: str = ""

    #: Per-channel circuit breaker name. Defaults to
    #: ``"dq_alert_<channel>"``; subclasses can override if needed.
    circuit_breaker_name: str = ""

    #: Failure threshold + timeout from D240.8.
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_timeout_seconds: int = 60

    def __init__(self) -> None:
        if not self.channel:
            raise NotImplementedError(
                f"{type(self).__name__} must set channel"
            )
        # Default the breaker name from the channel if not overridden.
        if not self.circuit_breaker_name:
            self.circuit_breaker_name = f"dq_alert_{self.channel.lower()}"

    # ---- public surface ---------------------------------------------------

    def deliver(self, rule, payload: Dict[str, Any]) -> DeliveryResult:
        """Deliver ``payload`` for ``rule`` through this client's channel.

        Wraps ``_deliver`` with a per-channel circuit breaker so a
        flapping partner doesn't pin worker threads on slow timeouts.

        Implementation note — the breaker only counts RAISED
        exceptions as failures (a returned ``DeliveryResult(success=
        False)`` is treated as success). To make the breaker count
        transient failures we wrap ``_deliver`` in
        ``_attempt_with_transient_raise``: it re-raises a transient
        ``DeliveryResult`` as ``_TransientDeliveryError`` for the
        breaker, and we unwrap it back into the original result for
        the caller.

        State-transition audit (spec 240.1.A.6) — when the breaker
        transitions to OPEN (CLOSED→OPEN OR HALF_OPEN→OPEN) we emit
        ``DQ_ALERT_CHANNEL_DEGRADED`` exactly once. Subsequent
        short-circuited calls log a warning but do NOT emit
        additional audit rows (one degradation event per transition
        is what the auditor needs; flooding the audit table with
        rows-per-rejected-call would defeat the purpose).

        Translates ``CircuitBreakerError`` (raised when the breaker is
        OPEN) into a ``success=False`` result with
        ``metadata['circuit_open']=True`` so the dispatcher can
        decide whether to dead-letter.
        """
        from hub.apps.core.resilience.circuit_breaker import (
            CircuitBreakerError,
            CircuitBreakerState,
        )

        breaker = self._get_circuit_breaker()
        state_before = breaker.get_state()
        try:
            try:
                result = breaker.call(
                    self._attempt_with_transient_raise, rule, payload,
                )
                return result
            except _TransientDeliveryError as exc:
                # Transient — return the wrapped result; the breaker
                # has already counted this as a failure (and may have
                # transitioned to OPEN — see the post-call check
                # below).
                return exc.result
            except CircuitBreakerError as exc:
                logger.warning(
                    "dq_alert_channel_degraded_short_circuit",
                    extra=_redact({
                        "channel": self.channel,
                        "rule_id": str(rule.id),
                        "alert_id": payload.get("alert_id"),
                        "circuit_breaker": self.circuit_breaker_name,
                    }),
                )
                return DeliveryResult(
                    success=False,
                    error=f"channel_circuit_open: {exc}",
                    metadata={"circuit_open": True},
                )
            except AlertDeliveryError as exc:
                # Unrecoverable — surfaced as a structured result. We
                # deliberately do NOT make the breaker count this as
                # a failure (config errors don't indicate partner
                # health degradation).
                return DeliveryResult(
                    success=False,
                    error=f"unrecoverable: {exc}",
                    metadata={"unrecoverable": True},
                )
        finally:
            # State-transition detection AFTER the breaker has had
            # its chance to update state. ``HALF_OPEN`` is also a
            # degradation signal (recovery probe failed), so any
            # transition INTO ``OPEN`` triggers the audit row.
            state_after = breaker.get_state()
            if (
                state_after == CircuitBreakerState.OPEN
                and state_before != CircuitBreakerState.OPEN
            ):
                self._emit_channel_degraded_audit(
                    rule=rule, payload=payload, breaker=breaker,
                )

    def _attempt_with_transient_raise(
        self, rule, payload: Dict[str, Any],
    ) -> DeliveryResult:
        """Wrapper that raises ``_TransientDeliveryError`` when
        ``_deliver`` returns a transient failure result.

        Without this re-raise the circuit breaker would never see a
        failure and never open.
        """
        result = self._deliver(rule, payload)
        if (
            not result.success
            and isinstance(result.metadata, dict)
            and result.metadata.get("transient")
        ):
            raise _TransientDeliveryError(result)
        return result

    def _emit_channel_degraded_audit(
        self, *, rule, payload: Dict[str, Any], breaker,
    ) -> None:
        """Emit the ``DQ_ALERT_CHANNEL_DEGRADED`` audit row.

        Called exactly once per state transition into OPEN. Best-
        effort — wrapped in try/except so a misbehaving audit
        backend can never crash the alert-delivery path.
        """
        try:
            from hub.apps.audit.event_types import (
                DQ_ALERT_CHANNEL_DEGRADED,
                DQ_ALERT_RESOURCE_TYPE,
            )
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type=DQ_ALERT_RESOURCE_TYPE,
                action=DQ_ALERT_CHANNEL_DEGRADED,
                actor_user=None,
                tenant=rule.tenant,
                resource_id=str(rule.id),
                result="WARNING",
                details={
                    "channel": self.channel,
                    "tenant_id": str(rule.tenant_id),
                    "circuit_breaker_name": self.circuit_breaker_name,
                    "failure_count": breaker.failure_threshold,
                    "timeout_seconds": breaker.timeout_seconds,
                    "alert_id": payload.get("alert_id"),
                    "rule_id": str(rule.id),
                },
            )
        except Exception as exc:  # noqa: BLE001 — boundary
            logger.error(
                "dq_alert_channel_degraded_audit_failed",
                extra=_redact({
                    "channel": self.channel,
                    "rule_id": str(rule.id),
                    "error": str(exc),
                }),
                exc_info=True,
            )

    # ---- circuit-breaker plumbing ----------------------------------------

    def _get_circuit_breaker(self):
        """Get / create the shared per-channel circuit breaker.

        Reuses the project-wide registry in
        ``hub.apps.core.resilience.service_breakers`` so all worker
        processes share the same Redis-backed state.
        """
        from hub.apps.core.resilience.service_breakers import (
            get_shared_circuit_breaker,
        )

        return get_shared_circuit_breaker(
            self.circuit_breaker_name,
            failure_threshold=self.circuit_breaker_failure_threshold,
            timeout_seconds=self.circuit_breaker_timeout_seconds,
        )

    # ---- subclass surface -------------------------------------------------

    @abc.abstractmethod
    def _deliver(self, rule, payload: Dict[str, Any]) -> DeliveryResult:
        """Channel-specific delivery. Subclasses implement.

        MUST return a ``DeliveryResult`` for both success and recoverable
        failure (5xx, timeout). MAY raise ``AlertDeliveryError`` for
        truly unrecoverable failures so the breaker doesn't waste
        retry budget on mis-configurations.
        """


# ---------------------------------------------------------------------------
# Dispatch registry
# ---------------------------------------------------------------------------


def _channel_registry() -> Dict[str, Type[BaseAlertClient]]:
    """Build the channel→client map.

    Done lazily inside the function so importing ``base.py`` doesn't
    pull in network libraries (``requests`` etc.) at Django app-config
    time. The dispatcher calls this once per delivery, which is
    acceptable — the registry is tiny.
    """
    from .email_client import EmailAlertClient
    from .pagerduty_client import PagerDutyAlertClient
    from .slack_client import SlackAlertClient
    from .webhook_client import WebhookAlertClient

    return {
        EmailAlertClient.channel: EmailAlertClient,
        SlackAlertClient.channel: SlackAlertClient,
        WebhookAlertClient.channel: WebhookAlertClient,
        PagerDutyAlertClient.channel: PagerDutyAlertClient,
    }


def get_client_for_channel(channel: str) -> BaseAlertClient:
    """Resolve a channel string to the appropriate client instance.

    ``channel`` matches one of the ``DQAlertChannel`` enum values
    (``EMAIL`` / ``SLACK`` / ``WEBHOOK`` / ``PAGERDUTY``).

    Raises
    ------
    ValueError
        Unknown channel — caller should treat as a configuration bug
        and surface to the operator.
    """
    registry = _channel_registry()
    cls = registry.get(channel)
    if cls is None:
        raise ValueError(
            f"unknown DQ alert channel: {channel!r}. "
            f"valid: {sorted(registry)}"
        )
    return cls()
