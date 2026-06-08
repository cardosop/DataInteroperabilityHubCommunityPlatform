"""
Phase 231.4 — compliance.completed tenant webhook emission on terminal ComplianceRun.

Real HTTP receivers (TestWebhookServer), real ORM, no mocks of webhook or signal logic.
"""

from __future__ import annotations
import pytest
import pytest

import json
import uuid
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.compliance.webhook_emission import (
    build_compliance_completed_webhook_data,
    build_report_presigned_token,
    publish_compliance_check_completed,
)
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import UserStatus
from hub.apps.webhooks.models import Webhook, WebhookEventType, WebhookStatus
from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

_ALLOWED_DATA_KEYS = frozenset(
    {
        "risk_level",
        "asset_id",
        "run_id",
        "completed_at",
        "report_presigned_url",
        "terminal_status",
        "event_id",
    }
)


@pytest.mark.django_db(transaction=True)
class BuildComplianceWebhookDataTest(TransactionTestCase):
    """Scrubs PII-rich fields — only contracted keys appear."""

    reset_sequences = False

    def _fixture_teardown(self):
        pass

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Wh-{uid}",
            slug=f"wh-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"w-{uid}@example.com",
            password="x",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"w-{uuid.uuid4().hex[:6]}",
            name="Webhook asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            resource_type="ASSET",
            resource_id=str(self.asset.id),
            created_by=self.user,
            status=JobStatus.COMPLETED,
        )

    @pytest.mark.integration
    def test_payload_keys_are_scrubbed_and_contract_complete(self):
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.HIGH.value,
            completed_at=timezone.now(),
            regulations=["GDPR"],
            detected_categories_json={"EMAIL": {"count": 99}},
            column_findings_json=[{"column": "email", "samples": ["a@b.com"]}],
        )
        payload = build_compliance_completed_webhook_data(
            run, report_presigned_url="https://signed.example/o"
        )
        self.assertEqual(set(payload.keys()), _ALLOWED_DATA_KEYS)
        self.assertEqual(payload["run_id"], str(run.id))
        self.assertEqual(payload["risk_level"], RiskLevel.HIGH.value)
        self.assertEqual(payload["asset_id"], str(self.asset.id))
        self.assertIsNotNone(payload["completed_at"])
        self.assertEqual(payload["terminal_status"], ComplianceRunStatus.SUCCEEDED.value)
        self.assertEqual(payload["report_presigned_url"], "https://signed.example/o")
        self.assertEqual(payload["event_id"], str(run.id))
        serialized = json.dumps(payload)
        self.assertNotIn("GDPR", serialized)
        self.assertNotIn('"EMAIL"', serialized)
        self.assertNotIn("samples", serialized.lower())


@override_settings(
    WEBHOOK_ASYNC_DELIVERY=False,
    # ``WebhookDeliveryService._attempt_delivery`` runs an SSRF guard
    # (``WEBHOOK_SSRF_ENABLED`` default True) that rejects
    # ``http://localhost:<port>/...`` as a reserved/private address —
    # which is exactly what ``TestWebhookServer`` binds to. Without
    # disabling the guard the delivery is short-circuited at
    # ``service.py:343`` before the HTTP POST and the test webhook
    # server never receives anything (asserting ``len(received) == 1``
    # then 0-vs-1 fails).
    WEBHOOK_SSRF_ENABLED=False,
    COMPLIANCE_WEBHOOK_REPORT_BASE_URL="http://testserver/api/v1/compliance",
)
class ComplianceCompletedWebhookSignalTest(TestCase):
    """Terminal transition invokes tenant webhook subscription + audit + stamp.

    Inherits ``TestCase`` (not ``TransactionTestCase``) because the
    compliance ``post_save`` signal schedules the webhook publish via
    ``transaction.on_commit`` — only ``TestCase`` exposes
    ``captureOnCommitCallbacks(execute=True)`` to deterministically
    flush those callbacks before the assertions read from the test
    webhook server. Under ``TransactionTestCase`` the callbacks fire
    asynchronously across thread/connection boundaries and the
    HTTP-server polling races with delivery.
    """

    def _make_run_pending(self):
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Sig-{uid}",
            slug=f"sig-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        user = User.objects.create_user(
            email=f"s-{uid}@example.com",
            password="x",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"s-{uuid.uuid4().hex[:6]}",
            name="Sig asset",
            status=AssetStatus.ACTIVE,
            created_by=user,
        )
        job = Job.objects.create(
            tenant=tenant,
            type=JobType.COMPLIANCE_RUN,
            resource_type="ASSET",
            resource_id=str(asset.id),
            created_by=user,
            status=JobStatus.RUNNING,
        )
        run = ComplianceRun.objects.create(
            tenant=tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.PENDING,
            risk_level=None,
        )
        return tenant, user, run

    @pytest.mark.integration
    def test_succeeded_transition_delivers_scrubbed_compliance_completed(self):
        tenant, user, run = self._make_run_pending()
        before_audit = AuditEvent.objects.filter(action=audit_event_types.COMPLIANCE_WEBHOOK_FIRED).count()
        with TestWebhookServer(response_status=200) as server:
            Webhook.objects.create(
                tenant=tenant,
                name="Compliance webhook",
                url=server.get_url(),
                secret="sig-secret",
                event_types=[str(WebhookEventType.COMPLIANCE_COMPLETED)],
                status=WebhookStatus.ACTIVE,
                created_by=user,
            )
            # ``captureOnCommitCallbacks(execute=True)`` flushes the
            # ``transaction.on_commit`` queue inline — required under
            # ``TestCase`` because the outer atomic NEVER commits, so
            # the webhook publisher's ``on_commit`` registration would
            # otherwise drop on rollback.
            with self.captureOnCommitCallbacks(execute=True):
                run.status = ComplianceRunStatus.SUCCEEDED
                run.risk_level = RiskLevel.MEDIUM.value
                run.completed_at = timezone.now()
                run.save(update_fields=["status", "risk_level", "completed_at"])

            received = server.get_received_requests(timeout=4.0)
            self.assertEqual(len(received), 1)
            outer = json.loads(received[0]["body"])
            self.assertEqual(outer["event_type"], WebhookEventType.COMPLIANCE_COMPLETED)
            data = outer["data"]
            self.assertEqual(set(data.keys()), _ALLOWED_DATA_KEYS)
            self.assertEqual(data["terminal_status"], "SUCCEEDED")

        run.refresh_from_db()
        self.assertIsNotNone(run.webhook_fired_at)
        after_audit = AuditEvent.objects.filter(action=audit_event_types.COMPLIANCE_WEBHOOK_FIRED).count()
        self.assertEqual(after_audit, before_audit + 1)

    @pytest.mark.integration
    def test_failed_terminal_transition_also_emits_webhook_once(self):
        tenant, user, run = self._make_run_pending()
        with TestWebhookServer(response_status=200) as server:
            Webhook.objects.create(
                tenant=tenant,
                name="Compliance webhook failed",
                url=server.get_url(),
                secret="sig-secret-f",
                event_types=[str(WebhookEventType.COMPLIANCE_COMPLETED)],
                status=WebhookStatus.ACTIVE,
                created_by=user,
            )
            # ``captureOnCommitCallbacks(execute=True)`` flushes the
            # ``transaction.on_commit`` queue inline — under
            # ``TestCase`` the outer atomic never commits so the
            # webhook publisher's ``on_commit`` registration would
            # otherwise drop on rollback.
            with self.captureOnCommitCallbacks(execute=True):
                run.status = ComplianceRunStatus.FAILED
                run.completed_at = timezone.now()
                run.save(update_fields=["status", "completed_at"])

            received = server.get_received_requests(timeout=4.0)
            self.assertEqual(len(received), 1)
            outer = json.loads(received[0]["body"])
            self.assertEqual(outer["data"]["terminal_status"], "FAILED")

    @pytest.mark.integration
    def test_skip_when_webhook_fired_at_already_populated_before_transition(self):
        tenant, user, run = self._make_run_pending()
        ts = timezone.now()
        ComplianceRun.objects.filter(pk=run.pk).update(webhook_fired_at=ts)
        run.refresh_from_db()
        with TestWebhookServer(response_status=200) as server:
            Webhook.objects.create(
                tenant=tenant,
                name="No duplicate",
                url=server.get_url(),
                secret="x",
                event_types=[str(WebhookEventType.COMPLIANCE_COMPLETED)],
                status=WebhookStatus.ACTIVE,
                created_by=user,
            )
            # ``captureOnCommitCallbacks(execute=True)`` flushes the
            # ``transaction.on_commit`` queue inline. The publisher
            # SHOULD short-circuit because ``webhook_fired_at`` is
            # already populated; the fact that no webhook fires is
            # the contract under test.
            with self.captureOnCommitCallbacks(execute=True):
                run.status = ComplianceRunStatus.SUCCEEDED
                run.completed_at = timezone.now()
                run.save(update_fields=["status", "completed_at"])
            received = server.get_received_requests(timeout=1.0)
            self.assertEqual(len(received), 0)


@override_settings(
    WEBHOOK_ASYNC_DELIVERY=False,
    # See ``ComplianceCompletedWebhookSignalTest`` for the
    # ``WEBHOOK_SSRF_ENABLED=False`` rationale: the production guard
    # rejects localhost as a reserved address, blocking the
    # ``TestWebhookServer`` URL.
    WEBHOOK_SSRF_ENABLED=False,
    COMPLIANCE_WEBHOOK_REPORT_BASE_URL="http://testserver/api/v1/compliance",
)
class PublishComplianceCheckCompletedDirectTest(TestCase):
    """Calling the publisher twice is idempotent.

    See ``ComplianceCompletedWebhookSignalTest`` for the rationale on
    using ``TestCase`` (rather than ``TransactionTestCase``) so the
    ``captureOnCommitCallbacks(execute=True)`` context manager — the
    only deterministic way to flush the publisher's
    ``transaction.on_commit`` queue — is available.
    """

    @pytest.mark.integration
    def test_double_publish_second_is_no_op(self):
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Dir-{uid}",
            slug=f"dir-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        user = User.objects.create_user(
            email=f"d-{uid}@example.com",
            password="x",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"d-{uuid.uuid4().hex[:6]}",
            name="d",
            status=AssetStatus.ACTIVE,
            created_by=user,
        )
        job = Job.objects.create(
            tenant=tenant,
            type=JobType.COMPLIANCE_RUN,
            resource_type="ASSET",
            resource_id=str(asset.id),
            created_by=user,
            status=JobStatus.COMPLETED,
        )
        run = ComplianceRun.objects.create(
            tenant=tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.LOW.value,
            completed_at=timezone.now(),
        )
        with TestWebhookServer(response_status=200) as server:
            Webhook.objects.create(
                tenant=tenant,
                name="w",
                url=server.get_url(),
                secret="s",
                event_types=[str(WebhookEventType.COMPLIANCE_COMPLETED)],
                status=WebhookStatus.ACTIVE,
                created_by=user,
            )
            # ``captureOnCommitCallbacks(execute=True)`` flushes the
            # publisher's ``transaction.on_commit`` queue inline.
            # Calling the publisher TWICE inside the SAME capture
            # block proves the de-duplication contract: only one
            # delivery fires regardless of how many times publish is
            # called for the same terminal-stamped run.
            with self.captureOnCommitCallbacks(execute=True):
                publish_compliance_check_completed(run)
                publish_compliance_check_completed(run)
            received = server.get_received_requests(timeout=4.0)
            self.assertEqual(len(received), 1)

    @pytest.mark.integration
    def test_publish_accepts_detached_stub_like_on_commit_signal(self):
        """Same entry point as the on_commit signal — only pk and tenant_id populated."""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"St-{uid}",
            slug=f"st-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        user = User.objects.create_user(
            email=f"st-{uid}@example.com",
            password="x",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"st-{uuid.uuid4().hex[:6]}",
            name="st",
            status=AssetStatus.ACTIVE,
            created_by=user,
        )
        job = Job.objects.create(
            tenant=tenant,
            type=JobType.COMPLIANCE_RUN,
            resource_type="ASSET",
            resource_id=str(asset.id),
            created_by=user,
            status=JobStatus.COMPLETED,
        )
        run = ComplianceRun.objects.create(
            tenant=tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.LOW.value,
            completed_at=timezone.now(),
        )
        stub = ComplianceRun(pk=run.pk, tenant_id=tenant.pk)
        with TestWebhookServer(response_status=200) as server:
            Webhook.objects.create(
                tenant=tenant,
                name="stub",
                url=server.get_url(),
                secret="s2",
                event_types=[str(WebhookEventType.COMPLIANCE_COMPLETED)],
                status=WebhookStatus.ACTIVE,
                created_by=user,
            )
            # ``captureOnCommitCallbacks(execute=True)`` flushes the
            # publisher's ``transaction.on_commit`` queue inline so
            # the test webhook server actually receives the request
            # before the assertion polls.
            with self.captureOnCommitCallbacks(execute=True):
                publish_compliance_check_completed(stub)
            received = server.get_received_requests(timeout=4.0)
            self.assertEqual(len(received), 1)
            outer = json.loads(received[0]["body"])
            self.assertEqual(outer["data"]["run_id"], str(run.id))


@override_settings(COMPLIANCE_WEBHOOK_REPORT_BASE_URL="http://testserver/api/v1/compliance")
@pytest.mark.django_db(transaction=True)
class ComplianceReportSummaryAnonymousTest(TransactionTestCase):
    """Signed URL returns the same scrubbed summary bundle (GET, no JWT)."""

    reset_sequences = False

    def _fixture_teardown(self):
        pass

    @pytest.mark.integration
    def test_report_summary_endpoint_returns_scrub_json(self):
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Rep-{uid}",
            slug=f"rep-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        user = User.objects.create_user(
            email=f"r-{uid}@example.com",
            password="x",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"r-{uuid.uuid4().hex[:6]}",
            name="r",
            status=AssetStatus.ACTIVE,
            created_by=user,
        )
        job = Job.objects.create(
            tenant=tenant,
            type=JobType.COMPLIANCE_RUN,
            resource_type="ASSET",
            resource_id=str(asset.id),
            created_by=user,
            status=JobStatus.COMPLETED,
        )
        run = ComplianceRun.objects.create(
            tenant=tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.NONE.value,
            completed_at=timezone.now(),
            regulations=["GDPR"],
        )
        token = build_report_presigned_token(run)
        path = reverse("compliance-webhook-report-summary") + "?token=" + quote(token, safe="")
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content.decode())
        self.assertEqual(body["run_id"], str(run.id))
        self.assertEqual(body["risk_level"], RiskLevel.NONE.value)
        self.assertNotIn("GDPR", json.dumps(body))
