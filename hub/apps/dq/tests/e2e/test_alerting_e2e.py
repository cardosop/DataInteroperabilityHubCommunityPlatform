"""
Phase 240.1.A.9 — end-to-end happy-path for the alerting pipeline.

Scenario
--------
1. Create a real ``DQAlertingRule`` (WEBHOOK channel) for a real
   ``DQRun`` whose quality_score is below the configured threshold.
2. Invoke ``DQAlertingService.evaluate_rules(dq_run)`` — the dispatcher
   delivers the alert end-to-end through the WebhookAlertClient
   against a mocked HTTP endpoint.
3. Assert: client invoked exactly once.
4. Trigger the SAME condition again — the dedup window short-
   circuits delivery before the client is invoked.
5. Assert: client invocation count is still 1.

Real model rows, real evaluation, real client code, real audit
emission. The only stub is the network boundary (``responses``).
"""

from __future__ import annotations

import uuid

import pytest
import responses
from django.test import TestCase

pytestmark = [pytest.mark.django_db(transaction=True)]


def _setup_real_dq_run():
    """Build the minimal real-DB graph (Tenant → User → File → Asset →
    Dataset → DQ rows) needed for ``evaluate_rules`` to walk an actual
    ``DQRun`` instance — no mocks for the model layer."""
    from hub.apps.assets.models import Asset, AssetStatus
    from hub.apps.datasets.models import Dataset
    from hub.apps.dq.models import (
        DQAlertingRule,
        DQAnomalySeverity,
        DQEngine,
        DQRun,
        DQRunStatus,
    )
    from hub.apps.files.models import File, FileStatus
    from hub.apps.jobs.models import Job, JobStatus, JobType
    from hub.apps.tenants.models import Tenant
    from hub.apps.users.models import User, UserStatus

    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"E2E Tenant {uid}",
        slug=f"e2e-tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    user = User.objects.create_user(
        email=f"e2e-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"e2e-{uid}",
        name=f"E2E Asset {uid}",
        status=AssetStatus.ACTIVE,
        created_by=user,
    )
    file_obj = File.objects.create(
        tenant=tenant,
        name=f"e2e-{uid}.csv",
        content_type="text/csv",
        size=1024,
        status=FileStatus.ACTIVE,
        storage_path=f"e2e/{uid}.csv",
        content_sha256="0" * 64,
        created_by=user,
    )
    dataset = Dataset.objects.create(
        tenant=tenant,
        asset=asset,
        file=file_obj,
        format="CSV",
        created_by=user,
    )
    job = Job.objects.create(
        tenant=tenant,
        type=JobType.DQ_RUN,
        status=JobStatus.COMPLETED,
        # ``Job.resource_type`` + ``resource_id`` are NOT NULL; tie the
        # job to the asset under DQ check so the row reflects reality.
        resource_type="ASSET",
        resource_id=asset.id,
        created_by=user,
    )
    dq_run = DQRun.objects.create(
        tenant=tenant,
        asset=asset,
        dataset=dataset,
        job=job,
        profile_key="intake_basic_soda",
        engine=DQEngine.SODA,
        status=DQRunStatus.SUCCEEDED,
        quality_score=0.55,
        # Triggers the rule below: 0.55 < 0.9.
        details_json={"completeness": 0.55},
    )
    rule = DQAlertingRule.objects.create(
        tenant=tenant,
        asset=asset,
        name=f"E2E quality score rule {uid}",
        metric_type="quality_score",
        threshold=0.9,
        comparison_operator="<",
        severity=DQAnomalySeverity.HIGH,
        alert_channels=["WEBHOOK"],
        channel_config={"url": "https://partner.example.com/dq-e2e"},
        enabled=True,
        created_by=user,
    )
    return tenant, dq_run, rule


class AlertingHappyPathE2E(TestCase):
    def setUp(self):
        from hub.apps.core.resilience.circuit_breaker import (
            reset_circuit_breaker_by_name,
        )

        reset_circuit_breaker_by_name("dq_alert_webhook")
        self.tenant, self.dq_run, self.rule = _setup_real_dq_run()

    @responses.activate
    def test_first_trigger_delivers_then_dedup_blocks_second(self):
        from hub.apps.audit.event_types import DQ_ALERT_DELIVERED
        from hub.apps.audit.models import AuditEvent
        from hub.apps.dq.alerting import DQAlertingService
        from hub.apps.dq.models import DQAlertingRule

        responses.add(
            responses.POST,
            "https://partner.example.com/dq-e2e",
            status=200,
            headers={"X-Request-Id": "e2e-1"},
        )

        # 1. First evaluation — rule fires, client invoked once.
        triggered = DQAlertingService.evaluate_rules(self.dq_run)
        assert len(triggered) == 1
        assert len(responses.calls) == 1, f"expected 1 HTTP call, got {len(responses.calls)}"

        # Validate the webhook request body contains expected DQ alert fields
        import json

        body = json.loads(responses.calls[0].request.body)
        assert "rule_id" in body
        assert "rule_name" in body
        assert "metric_type" in body
        assert "metric_value" in body
        assert "threshold" in body
        assert "dq_run_id" in body
        assert "severity" in body
        assert body["metric_type"] == "quality_score"
        assert body["metric_value"] == 0.55

        # last_alert_id stamped + audit emitted.
        reloaded = DQAlertingRule.objects.get(pk=self.rule.pk)
        assert reloaded.last_alert_id is not None
        assert reloaded.last_fired_at is not None
        delivered_audits = AuditEvent.objects.filter(
            action=DQ_ALERT_DELIVERED,
            resource_id=str(self.rule.id),
        )
        assert delivered_audits.count() == 1

        # 2. Second evaluation, identical condition.
        triggered_again = DQAlertingService.evaluate_rules(self.dq_run)
        # The rule still evaluates True (0.55 < 0.9), but delivery is
        # dedup'd.  Pin: the dedup state is still in effect.
        assert len(triggered_again) == 1  # condition still met
        reloaded_again = DQAlertingRule.objects.get(pk=self.rule.pk)
        assert reloaded_again.last_alert_id is not None
        # last_fired_at should be within the 24h dedup window
        assert reloaded_again.last_fired_at is not None
        from datetime import timedelta

        from django.utils import timezone

        assert reloaded_again.last_fired_at > timezone.now() - timedelta(hours=24)
        assert len(responses.calls) == 1, "dedup should have prevented a second HTTP call"
        assert (
            AuditEvent.objects.filter(
                action=DQ_ALERT_DELIVERED,
                resource_id=str(self.rule.id),
            ).count()
            == 1
        )

    @responses.activate
    def test_rule_does_not_trigger_when_condition_not_met(self):
        """Rule whose threshold the current metric does NOT cross should
        not fire — no HTTP call, no audit event."""
        from hub.apps.audit.event_types import DQ_ALERT_DELIVERED
        from hub.apps.audit.models import AuditEvent
        from hub.apps.dq.alerting import DQAlertingService
        from hub.apps.dq.models import DQAlertingRule, DQAnomalySeverity

        # Rule expects quality_score < 0.1, but actual is 0.55 → no fire.
        # Register BOTH URLs so @responses.activate doesn't raise
        # ConnectionError for the primary rule's delivery.
        responses.add(
            responses.POST,
            "https://partner.example.com/dq-e2e",
            status=200,
            headers={"X-Request-Id": "e2e-neg-control"},
        )
        responses.add(
            responses.POST,
            "https://partner.example.com/dq-no-trigger",
            status=200,
        )
        no_trigger_rule = DQAlertingRule.objects.create(
            tenant=self.tenant,
            asset=self.dq_run.asset,
            name="E2E no-trigger rule",
            metric_type="quality_score",
            threshold=0.1,
            comparison_operator="<",
            severity=DQAnomalySeverity.HIGH,
            alert_channels=["WEBHOOK"],
            channel_config={"url": "https://partner.example.com/dq-no-trigger"},
            enabled=True,
            created_by=self.dq_run.asset.created_by,
        )
        triggered = DQAlertingService.evaluate_rules(self.dq_run)
        triggered_ids = {t["rule_id"] for t in triggered}
        self.assertIn(str(self.rule.id), triggered_ids)
        self.assertNotIn(str(no_trigger_rule.id), triggered_ids)
        # Primary rule's webhook WAS called; no-trigger rule's was NOT
        called_urls = [c.request.url for c in responses.calls]
        self.assertIn(
            "https://partner.example.com/dq-e2e",
            called_urls,
            "Primary rule should have been delivered",
        )
        self.assertNotIn(
            "https://partner.example.com/dq-no-trigger",
            called_urls,
            "No-trigger rule should NOT have been delivered",
        )

    @responses.activate
    def test_dedup_window_expiry_allows_redelivery(self):
        """After the 24h dedup window expires, re-delivery occurs."""
        from datetime import timedelta

        from django.utils import timezone
        from hub.apps.dq.alerting import DQAlertingService
        from hub.apps.dq.models import DQAlertingRule

        responses.add(
            responses.POST,
            "https://partner.example.com/dq-e2e",
            status=200,
            headers={"X-Request-Id": "e2e-expiry-1"},
        )
        # First delivery
        DQAlertingService.evaluate_rules(self.dq_run)
        self.assertEqual(len(responses.calls), 1)

        # Expire the dedup window manually
        rule = DQAlertingRule.objects.get(pk=self.rule.pk)
        rule.last_fired_at = timezone.now() - timedelta(hours=25)
        rule.save(update_fields=["last_fired_at"])

        # Second response
        responses.add(
            responses.POST,
            "https://partner.example.com/dq-e2e",
            status=200,
            headers={"X-Request-Id": "e2e-expiry-2"},
        )
        DQAlertingService.evaluate_rules(self.dq_run)
        self.assertEqual(
            len(responses.calls), 2,
            f"Expected 2 HTTP calls after dedup expiry, got {len(responses.calls)}",
        )

    @responses.activate
    def test_webhook_500_triggers_retry_handling(self):
        """When webhook returns 500, dispatcher handles it gracefully
        (no unhandled exception)."""
        from hub.apps.dq.alerting import DQAlertingService
        from hub.apps.core.resilience.circuit_breaker import (
            reset_circuit_breaker_by_name,
        )

        # Ensure circuit breaker is not open from other tests
        reset_circuit_breaker_by_name("dq_alert_webhook")
        responses.add(
            responses.POST,
            "https://partner.example.com/dq-e2e",
            status=500,
            body="Internal Server Error",
        )
        # Must not raise — dispatcher handles 500 gracefully
        try:
            triggered = DQAlertingService.evaluate_rules(self.dq_run)
        except Exception as exc:
            self.fail(f"evaluate_rules should not raise on 5xx: {exc}")
        # Rule still evaluates as triggered (condition met)
        self.assertEqual(len(triggered), 1)
