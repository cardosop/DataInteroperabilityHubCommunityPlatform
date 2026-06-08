"""
Phase 240.1.A.8 — comprehensive tests for the alerting client surface.

Coverage targets (one test class per channel + cross-cutting concerns):

* Each client's success / 5xx-retry / 4xx-unrecoverable / timeout
  / network-error paths.
* The dedup short-circuit at the dispatcher (deterministic alert_id).
* RQ retry semantics — first failure schedules attempt 2 with the
  back-off ladder; retry budget exhaustion dead-letters.
* Circuit-breaker open / half-open / close transitions per channel.

External services (Slack / PagerDuty / arbitrary webhook) are stubbed
ONLY at the HTTP boundary via ``responses`` (real ``requests`` calls,
real serialization, real header / body assertions). The model layer
uses real DB rows. Per the project's TDD doctrine: no mocks beyond
the boundary.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
import responses
from django.test import TestCase, override_settings
from django.utils import timezone


pytestmark = [pytest.mark.django_db(transaction=True)]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_rule(*, channels, channel_config, **kwargs):
    """Create a real DQAlertingRule + tenant for use in client tests."""
    from hub.apps.dq.models import DQAlertingRule, DQAnomalySeverity
    from hub.apps.tenants.models import Tenant

    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"AC Tenant {uid}",
        slug=f"ac-tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    return DQAlertingRule.objects.create(
        tenant=tenant,
        name=kwargs.pop("name", f"Rule {uid}"),
        metric_type=kwargs.pop("metric_type", "quality_score"),
        threshold=kwargs.pop("threshold", 0.9),
        comparison_operator=kwargs.pop("comparison_operator", "<"),
        severity=kwargs.pop("severity", DQAnomalySeverity.HIGH),
        alert_channels=list(channels),
        channel_config=dict(channel_config),
        enabled=True,
        **kwargs,
    )


def _payload(**overrides):
    base = {
        "rule_id": "11111111-1111-1111-1111-111111111111",
        "rule_name": "Quality below threshold",
        "severity": "HIGH",
        "metric_type": "quality_score",
        "metric_value": 0.7,
        "threshold": 0.9,
        "comparison_operator": "<",
        "dq_run_id": "22222222-2222-2222-2222-222222222222",
        "asset_id": None,
        "dataset_id": None,
        "triggered_at": "2026-05-02T12:00:00+00:00",
        "message": "quality dropped",
        "alert_id": "deadbeef" * 4,  # 32-char placeholder
    }
    base.update(overrides)
    return base


def _reset_circuit_breaker(channel: str) -> None:
    """Wipe shared circuit-breaker state between tests so a prior
    failure run doesn't keep the breaker OPEN for the next test."""
    from hub.apps.core.resilience.circuit_breaker import (
        reset_circuit_breaker_by_name,
    )
    reset_circuit_breaker_by_name(f"dq_alert_{channel.lower()}")


# ---------------------------------------------------------------------------
# Slack client
# ---------------------------------------------------------------------------


class SlackAlertClientTests(TestCase):

    def setUp(self):
        _reset_circuit_breaker("SLACK")
        self.rule = _make_rule(
            channels=["SLACK"],
            channel_config={"webhook_url": "https://hooks.slack.com/abc"},
        )

    @responses.activate
    def test_success_returns_success_result(self):
        from hub.apps.dq.clients import SlackAlertClient

        responses.add(
            responses.POST,
            "https://hooks.slack.com/abc",
            body="ok",
            status=200,
            headers={"X-Slack-Req-Id": "req-1234"},
        )
        result = SlackAlertClient().deliver(self.rule, _payload())

        assert result.success is True
        assert result.delivery_id == "req-1234"
        # Verify Block Kit body.
        body = json.loads(responses.calls[0].request.body)
        assert body["blocks"][0]["type"] == "header"
        assert "DQ Alert" in body["blocks"][0]["text"]["text"]

    @responses.activate
    def test_5xx_returns_transient_failure(self):
        from hub.apps.dq.clients import SlackAlertClient

        responses.add(
            responses.POST,
            "https://hooks.slack.com/abc",
            status=503,
            body="overloaded",
        )
        result = SlackAlertClient().deliver(self.rule, _payload())
        assert result.success is False
        assert result.metadata.get("transient") is True
        assert "503" in (result.error or "")

    @responses.activate
    def test_4xx_marks_unrecoverable(self):
        from hub.apps.dq.clients import SlackAlertClient

        responses.add(
            responses.POST,
            "https://hooks.slack.com/abc",
            status=400,
            body="invalid_payload",
        )
        result = SlackAlertClient().deliver(self.rule, _payload())
        assert result.success is False
        assert result.metadata.get("unrecoverable") is True

    @responses.activate
    def test_timeout_marks_transient(self):
        from hub.apps.dq.clients import SlackAlertClient
        import requests

        # ``responses`` provides a ConnectionError if no match — to
        # simulate a Timeout we use a callback that raises.
        def _raise_timeout(_request):
            raise requests.exceptions.Timeout("read timed out")

        responses.add_callback(
            responses.POST,
            "https://hooks.slack.com/abc",
            callback=_raise_timeout,
        )
        result = SlackAlertClient().deliver(self.rule, _payload())
        assert result.success is False
        assert result.metadata.get("transient") is True
        assert "timeout" in (result.error or "").lower()

    def test_missing_webhook_url_raises_unrecoverable(self):
        from hub.apps.dq.clients import SlackAlertClient

        rule = _make_rule(
            channels=["SLACK"], channel_config={"webhook_url": ""},
        )
        # ``deliver`` translates AlertDeliveryError to a result so the
        # dispatcher can move on; the metadata flags it.
        result = SlackAlertClient().deliver(rule, _payload())
        assert result.success is False
        assert result.metadata.get("unrecoverable") is True


# ---------------------------------------------------------------------------
# Webhook client
# ---------------------------------------------------------------------------


class WebhookAlertClientTests(TestCase):

    def setUp(self):
        _reset_circuit_breaker("WEBHOOK")
        self.rule = _make_rule(
            channels=["WEBHOOK"],
            channel_config={
                "url": "https://partner.example.com/dq-alerts",
                "headers": {"X-Custom": "value"},
                "hmac_secret": "s3cr3t",
            },
        )

    @responses.activate
    def test_success_returns_delivery_id_from_response(self):
        from hub.apps.dq.clients import WebhookAlertClient

        responses.add(
            responses.POST,
            "https://partner.example.com/dq-alerts",
            status=200,
            json={"received": True},
            headers={"X-Request-Id": "remote-7"},
        )
        result = WebhookAlertClient().deliver(self.rule, _payload())
        assert result.success is True
        assert result.delivery_id == "remote-7"

    @responses.activate
    def test_hmac_signature_header_present(self):
        from hub.apps.dq.clients import WebhookAlertClient

        responses.add(
            responses.POST,
            "https://partner.example.com/dq-alerts",
            status=202,
        )
        WebhookAlertClient().deliver(self.rule, _payload())
        headers = responses.calls[0].request.headers
        assert headers["X-DQ-Signature"].startswith("sha256=")
        assert "X-DQ-Signature-Timestamp" in headers
        assert headers["X-Custom"] == "value"

    @responses.activate
    def test_5xx_is_transient(self):
        from hub.apps.dq.clients import WebhookAlertClient

        responses.add(
            responses.POST,
            "https://partner.example.com/dq-alerts",
            status=502,
        )
        result = WebhookAlertClient().deliver(self.rule, _payload())
        assert result.success is False
        assert result.metadata.get("transient") is True

    @responses.activate
    def test_4xx_is_unrecoverable(self):
        from hub.apps.dq.clients import WebhookAlertClient

        responses.add(
            responses.POST,
            "https://partner.example.com/dq-alerts",
            status=422,
            body="schema mismatch",
        )
        result = WebhookAlertClient().deliver(self.rule, _payload())
        assert result.success is False
        assert result.metadata.get("unrecoverable") is True

    def test_header_injection_blocked(self):
        from hub.apps.dq.clients.webhook_client import _build_headers

        config = {
            "url": "https://x",
            "headers": {
                "Good": "ok",
                # CR/LF in value → header-injection vector → reject.
                "Evil": "value\r\nX-Injected: pwned",
                # Space is NOT in the RFC 7230 token set, so this name
                # must be rejected. (``!`` IS valid per RFC 7230 — only
                # truly non-token characters belong here.)
                "Bad Name": "x",
                # Colon would terminate the header line — also rejected.
                "Has:Colon": "x",
            },
        }
        headers = _build_headers(config, b"{}")
        assert headers.get("Good") == "ok"
        assert "Evil" not in headers  # CR/LF rejected
        assert "Bad Name" not in headers  # space → invalid token
        assert "Has:Colon" not in headers  # colon → invalid token


# ---------------------------------------------------------------------------
# PagerDuty client
# ---------------------------------------------------------------------------


class PagerDutyAlertClientTests(TestCase):

    def setUp(self):
        _reset_circuit_breaker("PAGERDUTY")
        self.rule = _make_rule(
            channels=["PAGERDUTY"],
            channel_config={"integration_key": "pd-int-key-1234"},
        )

    @responses.activate
    def test_202_success_returns_dedup_key(self):
        from hub.apps.dq.clients import PagerDutyAlertClient

        responses.add(
            responses.POST,
            "https://events.pagerduty.com/v2/enqueue",
            status=202,
            json={
                "status": "success",
                "message": "Event processed",
                "dedup_key": "pd-dedup-1",
            },
        )
        result = PagerDutyAlertClient().deliver(
            self.rule, _payload(severity="CRITICAL"),
        )
        assert result.success is True
        assert result.delivery_id == "pd-dedup-1"
        body = json.loads(responses.calls[0].request.body)
        assert body["routing_key"] == "pd-int-key-1234"
        assert body["payload"]["severity"] == "critical"

    @responses.activate
    def test_400_unrecoverable(self):
        from hub.apps.dq.clients import PagerDutyAlertClient

        responses.add(
            responses.POST,
            "https://events.pagerduty.com/v2/enqueue",
            status=400,
            json={"errors": ["invalid event"]},
        )
        result = PagerDutyAlertClient().deliver(self.rule, _payload())
        assert result.success is False
        assert result.metadata.get("unrecoverable") is True

    @responses.activate
    def test_429_transient(self):
        from hub.apps.dq.clients import PagerDutyAlertClient

        responses.add(
            responses.POST,
            "https://events.pagerduty.com/v2/enqueue",
            status=429,
            body="rate limited",
        )
        result = PagerDutyAlertClient().deliver(self.rule, _payload())
        assert result.success is False
        assert result.metadata.get("transient") is True


# ---------------------------------------------------------------------------
# Email client
# ---------------------------------------------------------------------------


class EmailAlertClientTests(TestCase):

    def setUp(self):
        _reset_circuit_breaker("EMAIL")
        self.rule = _make_rule(
            channels=["EMAIL"],
            channel_config={"emails": ["ops@example.com", "team@example.com"]},
        )

    def test_success_returns_message_id(self):
        from hub.apps.dq.clients import EmailAlertClient

        class _StubService:
            def send_email(self, **kwargs):
                return {"success": True, "message_id": "smtp-7"}

        with patch(
            "hub.apps.notifications.services.get_email_service",
            return_value=_StubService(),
        ):
            result = EmailAlertClient().deliver(self.rule, _payload())
        assert result.success is True
        assert result.delivery_id == "smtp-7"
        assert result.metadata["delivered_to_count"] == 2

    def test_partial_delivery_marks_partial(self):
        from hub.apps.dq.clients import EmailAlertClient

        class _PartialService:
            def __init__(self):
                self.calls = 0

            def send_email(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return {"success": True, "message_id": "ok-1"}
                return {"success": False, "error": "smtp 421 deferred"}

        with patch(
            "hub.apps.notifications.services.get_email_service",
            return_value=_PartialService(),
        ):
            result = EmailAlertClient().deliver(self.rule, _payload())
        assert result.success is True
        assert result.metadata["partial"] is True

    def test_no_recipients_unrecoverable(self):
        from hub.apps.dq.clients import EmailAlertClient

        rule = _make_rule(
            channels=["EMAIL"], channel_config={"emails": []},
        )
        result = EmailAlertClient().deliver(rule, _payload())
        assert result.success is False
        assert result.metadata.get("unrecoverable") is True


# ---------------------------------------------------------------------------
# Dispatcher: dedup window + RQ retry semantics
# ---------------------------------------------------------------------------


class DispatcherDedupTests(TestCase):

    def setUp(self):
        _reset_circuit_breaker("WEBHOOK")
        self.rule = _make_rule(
            channels=["WEBHOOK"],
            channel_config={"url": "https://partner.example.com/dq"},
        )

    @responses.activate
    def test_first_fire_delivers_and_stamps_last_alert_id(self):
        from hub.apps.dq.alerting import DQAlertingService, compute_alert_id
        from hub.apps.dq.models import DQAlertingRule

        responses.add(
            responses.POST,
            "https://partner.example.com/dq",
            status=202,
        )
        alert = {
            "rule_id": str(self.rule.id),
            "rule_name": self.rule.name,
            "severity": "HIGH",
            "metric_type": "quality_score",
            "metric_value": 0.5,
            "threshold": 0.9,
            "comparison_operator": "<",
            "dq_run_id": "33333333-3333-3333-3333-333333333333",
            "asset_id": None,
            "dataset_id": None,
            "triggered_at": "2026-05-02T12:00:00+00:00",
            "message": "below",
        }
        outcomes = DQAlertingService._deliver_alert(alert, self.rule)
        assert len(outcomes) == 1
        assert outcomes[0]["success"] is True
        # last_alert_id stamped from compute_alert_id; same formula
        # locally to verify byte-for-byte.
        expected = compute_alert_id(
            rule_id=str(self.rule.id),
            run_id="33333333-3333-3333-3333-333333333333",
            alert_type="quality_score",
        )
        reloaded = DQAlertingRule.objects.get(pk=self.rule.pk)
        assert reloaded.last_alert_id == expected
        assert reloaded.last_fired_at is not None

    @responses.activate
    def test_dedup_short_circuits_within_window(self):
        from hub.apps.dq.alerting import (
            DEDUP_WINDOW_HOURS,
            DQAlertingService,
            compute_alert_id,
        )

        # Pre-stamp last_alert_id + last_fired_at so the dedup hits.
        self.rule.last_alert_id = compute_alert_id(
            rule_id=str(self.rule.id),
            run_id="run-1",
            alert_type="quality_score",
        )
        self.rule.last_fired_at = timezone.now() - timedelta(
            hours=DEDUP_WINDOW_HOURS - 1,
        )
        self.rule.save(update_fields=["last_alert_id", "last_fired_at"])

        responses.add(
            responses.POST,
            "https://partner.example.com/dq",
            status=202,
        )
        outcomes = DQAlertingService._deliver_alert(
            {"dq_run_id": "run-1", "metric_type": "quality_score"},
            self.rule,
        )
        # Empty outcomes => dedup hit.
        assert outcomes == []
        # No HTTP call was made.
        assert len(responses.calls) == 0

    @responses.activate
    def test_dedup_does_not_short_circuit_after_window_expires(self):
        from hub.apps.dq.alerting import (
            DEDUP_WINDOW_HOURS,
            DQAlertingService,
            compute_alert_id,
        )

        # Pre-stamp older than the window.
        self.rule.last_alert_id = compute_alert_id(
            rule_id=str(self.rule.id),
            run_id="run-old",
            alert_type="quality_score",
        )
        self.rule.last_fired_at = timezone.now() - timedelta(
            hours=DEDUP_WINDOW_HOURS + 1,
        )
        self.rule.save(update_fields=["last_alert_id", "last_fired_at"])

        responses.add(
            responses.POST,
            "https://partner.example.com/dq",
            status=202,
        )
        outcomes = DQAlertingService._deliver_alert(
            {"dq_run_id": "run-old", "metric_type": "quality_score"},
            self.rule,
        )
        # Outside the window — should fire.
        assert len(outcomes) == 1
        assert outcomes[0]["success"] is True


# ---------------------------------------------------------------------------
# RQ retry / dead-letter semantics
# ---------------------------------------------------------------------------


class RetrySchedulingTests(TestCase):

    def setUp(self):
        _reset_circuit_breaker("WEBHOOK")
        self.rule = _make_rule(
            channels=["WEBHOOK"],
            channel_config={"url": "https://partner.example.com/dq"},
        )

    @responses.activate
    def test_first_failure_schedules_retry_with_backoff(self):
        from hub.apps.dq.tasks import (
            RETRY_SCHEDULE_SECONDS, deliver_or_schedule_retry,
        )

        responses.add(
            responses.POST, "https://partner.example.com/dq", status=503,
        )
        with patch("hub.apps.dq.tasks.get_queue") as fake_get_queue:
            queue = fake_get_queue.return_value
            outcome = deliver_or_schedule_retry(
                rule_id=str(self.rule.id),
                channel="WEBHOOK",
                payload=_payload(),
                attempt_number=1,
            )
        assert outcome["next_action"] == "retry_scheduled"
        # enqueue_in called with the FIRST back-off delay.
        delay_arg = queue.enqueue_in.call_args.args[0]
        assert delay_arg == timedelta(seconds=RETRY_SCHEDULE_SECONDS[0])
        # next attempt = 2 (we just failed attempt 1).
        assert queue.enqueue_in.call_args.kwargs["attempt_number"] == 2

    @responses.activate
    def test_unrecoverable_failure_dead_letters_immediately(self):
        from hub.apps.audit.event_types import DQ_ALERT_DEAD_LETTER
        from hub.apps.audit.models import AuditEvent
        from hub.apps.dq.tasks import deliver_or_schedule_retry

        responses.add(
            responses.POST, "https://partner.example.com/dq", status=400,
        )
        with patch("hub.apps.dq.tasks.get_queue"):
            outcome = deliver_or_schedule_retry(
                rule_id=str(self.rule.id),
                channel="WEBHOOK",
                payload=_payload(),
                attempt_number=1,
            )
        assert outcome["next_action"] == "dead_lettered"
        assert AuditEvent.objects.filter(
            action=DQ_ALERT_DEAD_LETTER,
            resource_id=str(self.rule.id),
        ).exists()

    @responses.activate
    def test_retry_budget_exhaustion_dead_letters(self):
        from hub.apps.audit.event_types import DQ_ALERT_DEAD_LETTER
        from hub.apps.audit.models import AuditEvent
        from hub.apps.dq.tasks import (
            MAX_DELIVERY_ATTEMPTS, deliver_or_schedule_retry,
        )

        responses.add(
            responses.POST, "https://partner.example.com/dq", status=503,
        )
        # Pretend we're at the final attempt — next failure dead-letters.
        with patch("hub.apps.dq.tasks.get_queue"):
            outcome = deliver_or_schedule_retry(
                rule_id=str(self.rule.id),
                channel="WEBHOOK",
                payload=_payload(),
                attempt_number=MAX_DELIVERY_ATTEMPTS,
            )
        assert outcome["next_action"] == "dead_lettered"
        assert AuditEvent.objects.filter(
            action=DQ_ALERT_DEAD_LETTER,
        ).exists()


# ---------------------------------------------------------------------------
# Circuit breaker open / half-open / close per channel
# ---------------------------------------------------------------------------


class CircuitBreakerTransitionTests(TestCase):

    def setUp(self):
        _reset_circuit_breaker("SLACK")
        self.rule = _make_rule(
            channels=["SLACK"],
            channel_config={"webhook_url": "https://hooks.slack.com/x"},
        )

    @responses.activate
    def test_breaker_opens_after_failure_threshold(self):
        from hub.apps.core.resilience.circuit_breaker import (
            CircuitBreakerState,
        )
        from hub.apps.core.resilience.service_breakers import (
            get_shared_circuit_breaker,
        )
        from hub.apps.dq.clients import SlackAlertClient

        responses.add(
            responses.POST,
            "https://hooks.slack.com/x",
            status=503,
        )
        client = SlackAlertClient()
        for _ in range(5):
            client.deliver(self.rule, _payload())

        breaker = get_shared_circuit_breaker(
            "dq_alert_slack", failure_threshold=5, timeout_seconds=60,
        )
        assert breaker.get_state() == CircuitBreakerState.OPEN

    @responses.activate
    def test_open_breaker_short_circuits_subsequent_calls(self):
        from hub.apps.core.resilience.service_breakers import (
            get_shared_circuit_breaker,
        )
        from hub.apps.dq.clients import SlackAlertClient

        responses.add(
            responses.POST,
            "https://hooks.slack.com/x",
            status=503,
        )
        client = SlackAlertClient()
        for _ in range(5):
            client.deliver(self.rule, _payload())

        # Reset the responses registry — if breaker actually short-
        # circuits, NO new HTTP call should be made.
        prior_call_count = len(responses.calls)
        result = client.deliver(self.rule, _payload())
        assert result.success is False
        assert result.metadata.get("circuit_open") is True
        assert len(responses.calls) == prior_call_count

        # Sanity: clean up state for downstream tests.
        get_shared_circuit_breaker("dq_alert_slack").reset()

    @responses.activate
    def test_half_open_recovers_to_closed_on_success(self):
        from hub.apps.core.resilience.circuit_breaker import (
            CircuitBreakerState,
            reset_circuit_breaker_by_name,
        )
        from hub.apps.core.resilience.service_breakers import (
            get_shared_circuit_breaker,
        )
        from hub.apps.dq.clients import SlackAlertClient

        # Use a short timeout so we can test the OPEN→HALF_OPEN
        # transition without sleeping a real minute.
        from unittest.mock import patch as _patch

        # C8: Reset any cached breaker before creating the client.
        # Without this, a prior test may have created the shared
        # "dq_alert_slack" breaker with timeout_seconds=60, and
        # get_shared_circuit_breaker returns the cached instance
        # (ignoring the patched timeout). The test then sleeps 1.5s
        # but the breaker never transitions to HALF_OPEN — the
        # final CLOSED assertion passes vacuously because the
        # breaker was never really tested.
        reset_circuit_breaker_by_name("dq_alert_slack")

        with _patch.object(
            SlackAlertClient, "circuit_breaker_timeout_seconds", 1,
        ):
            client = SlackAlertClient()
            responses.add(
                responses.POST,
                "https://hooks.slack.com/x",
                status=503,
            )
            # Open the breaker.
            for _ in range(5):
                client.deliver(self.rule, _payload())

            breaker = get_shared_circuit_breaker(
                "dq_alert_slack", failure_threshold=5, timeout_seconds=1,
            )
            assert breaker.get_state() == CircuitBreakerState.OPEN

            # Wait past the timeout so the next call probes HALF_OPEN.
            time.sleep(1.5)

            # Re-prime responses with a healthy 200 and then run the
            # success_threshold count of calls so the breaker closes.
            responses.reset()
            responses.add(
                responses.POST,
                "https://hooks.slack.com/x",
                status=200,
                body="ok",
            )
            # success_threshold defaults to 2 in CircuitBreaker.
            client.deliver(self.rule, _payload())
            client.deliver(self.rule, _payload())

            assert breaker.get_state() == CircuitBreakerState.CLOSED


# ---------------------------------------------------------------------------
# Audit-event constant wiring
# ---------------------------------------------------------------------------


class AuditEventEmissionTests(TestCase):
    """Verify the dispatcher emits the right audit codes for each path."""

    def setUp(self):
        _reset_circuit_breaker("WEBHOOK")
        self.rule = _make_rule(
            channels=["WEBHOOK"],
            channel_config={"url": "https://partner.example.com/dq"},
        )

    @responses.activate
    def test_delivered_audit_emitted_on_success(self):
        from hub.apps.audit.event_types import DQ_ALERT_DELIVERED
        from hub.apps.audit.models import AuditEvent
        from hub.apps.dq.tasks import deliver_or_schedule_retry

        responses.add(
            responses.POST, "https://partner.example.com/dq", status=200,
        )
        deliver_or_schedule_retry(
            rule_id=str(self.rule.id),
            channel="WEBHOOK",
            payload=_payload(),
            attempt_number=1,
        )
        assert AuditEvent.objects.filter(
            action=DQ_ALERT_DELIVERED,
            resource_id=str(self.rule.id),
        ).exists()

    @responses.activate
    def test_failed_audit_emitted_on_5xx(self):
        from hub.apps.audit.event_types import DQ_ALERT_FAILED
        from hub.apps.audit.models import AuditEvent
        from hub.apps.dq.tasks import deliver_or_schedule_retry

        responses.add(
            responses.POST, "https://partner.example.com/dq", status=503,
        )
        with patch("hub.apps.dq.tasks.get_queue"):
            deliver_or_schedule_retry(
                rule_id=str(self.rule.id),
                channel="WEBHOOK",
                payload=_payload(),
                attempt_number=1,
            )
        assert AuditEvent.objects.filter(
            action=DQ_ALERT_FAILED,
            resource_id=str(self.rule.id),
        ).exists()

    @responses.activate
    def test_channel_degraded_audit_emitted_on_breaker_open(self):
        """Spec 240.1.A.6 — circuit-open MUST emit
        ``DQ_ALERT_CHANNEL_DEGRADED`` exactly once per state
        transition into OPEN."""
        from hub.apps.audit.event_types import DQ_ALERT_CHANNEL_DEGRADED
        from hub.apps.audit.models import AuditEvent
        from hub.apps.core.resilience.circuit_breaker import (
            reset_circuit_breaker_by_name,
        )
        from hub.apps.dq.clients import WebhookAlertClient

        # Make sure we start with a fresh breaker so this test is
        # independent of execution order with the other suites.
        reset_circuit_breaker_by_name("dq_alert_webhook")

        responses.add(
            responses.POST, "https://partner.example.com/dq", status=503,
        )
        client = WebhookAlertClient()

        # Five 5xx failures take the breaker from CLOSED to OPEN.
        # The transition fires on the FIFTH failure, so we should
        # see exactly one DQ_ALERT_CHANNEL_DEGRADED row after the
        # loop completes — not five, not zero.
        for _ in range(5):
            client.deliver(self.rule, _payload())

        rows = AuditEvent.objects.filter(
            action=DQ_ALERT_CHANNEL_DEGRADED,
            resource_id=str(self.rule.id),
        )
        assert rows.count() == 1, (
            f"expected exactly 1 channel-degraded audit, got {rows.count()}"
        )
        details = rows.first().details_json or {}
        assert details.get("channel") == "WEBHOOK"
        assert details.get("circuit_breaker_name") == "dq_alert_webhook"
        assert details.get("tenant_id") == str(self.rule.tenant_id)

        # Subsequent short-circuited calls MUST NOT spam the audit
        # table — the contract is one row per transition into OPEN.
        client.deliver(self.rule, _payload())
        client.deliver(self.rule, _payload())
        assert AuditEvent.objects.filter(
            action=DQ_ALERT_CHANNEL_DEGRADED,
            resource_id=str(self.rule.id),
        ).count() == 1

        reset_circuit_breaker_by_name("dq_alert_webhook")

    @responses.activate
    def test_dead_letter_audit_carries_required_details(self):
        """Spec 240.1.A.5 — dead-letter audit row must surface
        ``last_error``, ``total_attempts``, ``dead_lettered_at`` so
        the auditor can reconstruct the failure context without
        cross-referencing log streams."""
        from hub.apps.audit.event_types import DQ_ALERT_DEAD_LETTER
        from hub.apps.audit.models import AuditEvent
        from hub.apps.dq.tasks import (
            MAX_DELIVERY_ATTEMPTS, deliver_or_schedule_retry,
        )

        responses.add(
            responses.POST, "https://partner.example.com/dq", status=503,
        )
        with patch("hub.apps.dq.tasks.get_queue"):
            deliver_or_schedule_retry(
                rule_id=str(self.rule.id),
                channel="WEBHOOK",
                payload=_payload(),
                attempt_number=MAX_DELIVERY_ATTEMPTS,
            )
        row = AuditEvent.objects.filter(
            action=DQ_ALERT_DEAD_LETTER,
            resource_id=str(self.rule.id),
        ).first()
        assert row is not None
        details = row.details_json or {}
        assert details.get("channel") == "WEBHOOK"
        assert details.get("rule_id") == str(self.rule.id)
        assert details.get("total_attempts") == MAX_DELIVERY_ATTEMPTS
        assert "last_error" in details
        assert "dead_lettered_at" in details


# ---------------------------------------------------------------------------
# Email-channel breaker integration
# ---------------------------------------------------------------------------


class EmailBreakerTransientTests(TestCase):
    """Spec 240.1.A.6 — SMTP outages MUST trip the email breaker.

    Originally the email client returned ``DeliveryResult(success=False)``
    without ``metadata.transient=True``, which meant the breaker never
    saw a failure and an extended SMTP outage would burn the entire
    RQ retry budget on every alert. This pins the regression."""

    def setUp(self):
        _reset_circuit_breaker("EMAIL")
        self.rule = _make_rule(
            channels=["EMAIL"],
            channel_config={"emails": ["ops@example.com"]},
        )

    def test_smtp_outage_trips_breaker(self):
        from hub.apps.core.resilience.circuit_breaker import (
            CircuitBreakerState, reset_circuit_breaker_by_name,
        )
        from hub.apps.core.resilience.service_breakers import (
            get_shared_circuit_breaker,
        )
        from hub.apps.dq.clients import EmailAlertClient

        reset_circuit_breaker_by_name("dq_alert_email")

        class _OutageService:
            def send_email(self, **kwargs):
                # Simulates SendGrid 5xx / network blip — service
                # returns success=False but does not raise.
                return {"success": False, "error": "smtp 503"}

        client = EmailAlertClient()
        with patch(
            "hub.apps.notifications.services.get_email_service",
            return_value=_OutageService(),
        ):
            for _ in range(5):
                client.deliver(self.rule, _payload())

        breaker = get_shared_circuit_breaker(
            "dq_alert_email", failure_threshold=5, timeout_seconds=60,
        )
        assert breaker.get_state() == CircuitBreakerState.OPEN
        reset_circuit_breaker_by_name("dq_alert_email")
