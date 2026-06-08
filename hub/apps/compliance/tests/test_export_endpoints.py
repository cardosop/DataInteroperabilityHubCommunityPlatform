"""
Phase 231.8 — Compliance run export CSV/JSON (real DB + API client, no mocks).

Covers MIME types, CSV parse-back, JSON round-trip, cross-tenant 404,
throttle 429, and COMPLIANCE_EXPORT audit rows.
"""

import pytest

import csv
import io
import json
import uuid

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit import event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus


class ComplianceExportEndpointsTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Export Tenant {uid}",
            slug=f"export-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"export-user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        uid2 = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Export {uid2}",
            slug=f"other-export-{uid2}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.other_tenant)
        self.other_user = User.objects.create_user(
            email=f"export-other-{uid2}@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )

        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"export-asset-{uid}",
            name="Export Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        self.column_findings = [
            {
                "column": "email_col",
                "categories": ["PII_DIRECT_EMAIL"],
                "match_ratio": 0.85,
                "confidence": "HIGH",
            },
        ]
        completed = timezone.now()
        self.compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=self.job,
            asset=self.asset,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status="FAIL",
            risk_level="HIGH",
            allowed_to_store=False,
            column_findings_json=self.column_findings,
            regulation_mapping_json={
                "GDPR": {"applies": True, "applicable_categories": ["PII_DIRECT_EMAIL"]},
                "metadata": {},
            },
            completed_at=completed,
            started_at=completed,
        )

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.other_user,
        )
        other_asset = Asset.objects.create(
            tenant=self.other_tenant,
            key=f"other-asset-{uid2}",
            name="Other",
            status=AssetStatus.DRAFT,
            created_by=self.other_user,
        )
        self.other_run = ComplianceRun.objects.create(
            tenant=self.other_tenant,
            job=other_job,
            asset=other_asset,
            status=ComplianceRunStatus.PENDING,
        )

        self.auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="AUDITOR",
            defaults={"description": "Auditor — read-only"},
        )
        self.auditor_user = User.objects.create_user(
            email=f"export-auditor-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.auditor_user, role=self.auditor_role)

    @pytest.mark.integration
    def test_export_csv_200_correct_mime_and_parse_back(self):
        self.client.force_authenticate(user=self.user)
        rid = self.compliance_run.id
        before = AuditEvent.objects.filter(
            resource_id=str(rid),
            action=event_types.COMPLIANCE_EXPORT,
        ).count()
        resp = self.client.get(f"/api/v1/compliance/runs/{rid}/export.csv/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", resp["Content-Type"])
        # Export endpoints emit ``StreamingHttpResponse`` (chunked
        # CSV/JSON) — ``.content`` raises; concatenate
        # ``.streaming_content`` instead.
        raw = b"".join(resp.streaming_content).decode("utf-8")
        rows = list(csv.reader(io.StringIO(raw)))
        self.assertEqual(rows[0], ["column", "pii_type", "risk_score", "severity"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], "email_col")
        self.assertEqual(rows[1][1], "PII_DIRECT_EMAIL")
        self.assertEqual(rows[1][3], "HIGH")
        after = AuditEvent.objects.filter(
            resource_id=str(rid),
            action=event_types.COMPLIANCE_EXPORT,
        ).count()
        self.assertEqual(after, before + 1)

    @pytest.mark.integration
    def test_export_csv_audit_details_include_format_and_counts(self):
        self.client.force_authenticate(user=self.user)
        rid = self.compliance_run.id
        self.client.get(f"/api/v1/compliance/runs/{rid}/export.csv/")
        evt = (
            AuditEvent.objects.filter(
                resource_id=str(rid),
                action=event_types.COMPLIANCE_EXPORT,
            )
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(evt)
        self.assertEqual(evt.details_json.get("format"), "csv")
        self.assertEqual(evt.details_json.get("violation_count"), 1)

    @pytest.mark.integration
    def test_auditor_can_export_csv_and_json(self):
        """Export is read-only; AUDITOR role must not be blocked (Phase 231.8)."""
        self.client.force_authenticate(user=self.auditor_user)
        rid = self.compliance_run.id
        csv_resp = self.client.get(f"/api/v1/compliance/runs/{rid}/export.csv/")
        json_resp = self.client.get(f"/api/v1/compliance/runs/{rid}/export.json/")
        self.assertEqual(csv_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(json_resp.status_code, status.HTTP_200_OK)

    @pytest.mark.integration
    def test_export_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        rid = self.compliance_run.id
        self.assertEqual(
            self.client.get(f"/api/v1/compliance/runs/{rid}/export.csv/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/compliance/runs/{rid}/export.json/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    @pytest.mark.integration
    def test_export_json_200_correct_mime_roundtrip(self):
        self.client.force_authenticate(user=self.user)
        rid = self.compliance_run.id
        resp = self.client.get(f"/api/v1/compliance/runs/{rid}/export.json/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("application/json", resp["Content-Type"])
        # ``StreamingHttpResponse`` chunks the body — concatenate via
        # ``streaming_content`` (``.content`` raises on streaming
        # responses).
        raw = b"".join(resp.streaming_content).decode("utf-8")
        envelope = json.loads(raw)
        self.assertIn("run", envelope)
        self.assertEqual(envelope["run"]["compliance_run_id"], str(rid))
        findings = envelope["run"].get("findings") or []
        self.assertTrue(any(f["column"] == "email_col" for f in findings))

    @pytest.mark.integration
    def test_export_json_emits_compliance_export_audit(self):
        self.client.force_authenticate(user=self.user)
        rid = self.compliance_run.id
        before = AuditEvent.objects.filter(
            resource_id=str(rid),
            action=event_types.COMPLIANCE_EXPORT,
        ).count()
        resp = self.client.get(f"/api/v1/compliance/runs/{rid}/export.json/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        after = AuditEvent.objects.filter(
            resource_id=str(rid),
            action=event_types.COMPLIANCE_EXPORT,
        ).count()
        self.assertEqual(after, before + 1)
        evt = (
            AuditEvent.objects.filter(
                resource_id=str(rid),
                action=event_types.COMPLIANCE_EXPORT,
            )
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(evt)
        self.assertEqual(evt.details_json.get("format"), "json")

    @pytest.mark.integration
    def test_export_cross_tenant_returns_404_not_leak(self):
        self.client.force_authenticate(user=self.user)
        other_id = self.other_run.id
        csv_resp = self.client.get(f"/api/v1/compliance/runs/{other_id}/export.csv/")
        json_resp = self.client.get(f"/api/v1/compliance/runs/{other_id}/export.json/")
        self.assertEqual(csv_resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(json_resp.status_code, status.HTTP_404_NOT_FOUND)

    @pytest.mark.integration
    def test_export_throttle_second_burst_returns_429(self):
        """Second export in the burst window exceeds scope rate → 429.

        ``ScopedRateThrottle.THROTTLE_RATES`` is a class attribute
        captured at module import from
        ``api_settings.DEFAULT_THROTTLE_RATES``. ``override_settings``
        does NOT propagate to that class attribute (DRF's
        ``api_settings.reload()`` builds a NEW dict; the class attr
        still references the OLD one). Patch the class attribute's
        underlying dict in-place via ``mock.patch.dict`` so the test
        actually tightens the rate the throttle enforces.
        """
        from unittest import mock
        from rest_framework.throttling import ScopedRateThrottle

        cache.clear()
        self.client.force_authenticate(user=self.user)
        rid = self.compliance_run.id
        with mock.patch.dict(
            ScopedRateThrottle.THROTTLE_RATES,
            {"compliance_export": "1/minute"},
        ):
            first = self.client.get(f"/api/v1/compliance/runs/{rid}/export.csv/")
            self.assertEqual(first.status_code, status.HTTP_200_OK)
            second = self.client.get(f"/api/v1/compliance/runs/{rid}/export.csv/")
            self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @pytest.mark.integration
    def test_export_throttle_shared_across_formats(self):
        """Both export actions share ``compliance_export`` throttle scope.

        See ``test_export_throttle_second_burst_returns_429`` for why
        ``mock.patch.dict`` (not ``override_settings``) is needed here
        — ``ScopedRateThrottle.THROTTLE_RATES`` is captured once at
        DRF import.
        """
        from unittest import mock
        from rest_framework.throttling import ScopedRateThrottle

        cache.clear()
        self.client.force_authenticate(user=self.user)
        rid = self.compliance_run.id
        with mock.patch.dict(
            ScopedRateThrottle.THROTTLE_RATES,
            {"compliance_export": "1/minute"},
        ):
            first = self.client.get(f"/api/v1/compliance/runs/{rid}/export.json/")
            self.assertEqual(first.status_code, status.HTTP_200_OK)
            second = self.client.get(f"/api/v1/compliance/runs/{rid}/export.csv/")
            self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
