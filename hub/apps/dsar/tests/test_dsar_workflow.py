"""Phase 232.2 DSAR workflow — real DB, mail outbox, no stubbed captcha (skip flag)."""

from __future__ import annotations

import io
import uuid
import zipfile

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from freezegun import freeze_time
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.dsar.models import (
    BackupAffectedBySubject,
    DSARRequest,
    DSARRequestType,
    DSARSLALevel,
    DSARStatus,
    DSARVerificationMethod,
)
from hub.apps.dsar.packaging import (
    build_dsar_zip_bytes,
    execute_warm_erasure_if_linked,
    registry_backup_for_erasure,
)
from hub.apps.dsar.sla_scan import run_dsar_statutory_clock_scan
from hub.apps.dsar.workflow import create_dsar_public, transition_status
from hub.apps.gdpr.models import ErasureRequest, ErasureRequestStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus


@override_settings(
    DSAR_SKIP_HCAPTCHA_VERIFICATION=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DSAR_PUBLIC_IDEMPOTENCY_WINDOW_HOURS=24,
)
class DsarPublicFlowTests(TestCase):
    def setUp(self):
        mail.outbox.clear()
        self.tenant = Tenant.objects.create(
            name="dsar-t",
            slug="dsar-" + uuid.uuid4().hex[:8],
            compliance_dsar_enabled=True,
        )
        self.client = APIClient()
        # Use unique idempotency keys per-run to avoid Redis staleness
        # from prior test executions (middleware checks Redis first).
        self._idem_key = uuid.uuid4().hex

    @override_settings(DSAR_SKIP_HCAPTCHA_VERIFICATION=True)
    @pytest.mark.integration
    def test_public_submit_sends_otp_email(self):
        url = "/api/v1/public/dsar-requests/"
        body = {
            "tenant_id": str(self.tenant.id),
            "request_type": DSARRequestType.ACCESS,
            "subject_email": "subject@example.com",
            "regimes": ["GDPR"],
            "hcaptcha_response": "test-token",
        }
        r = self.client.post(url, body, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self.assertEqual(len(mail.outbox), 1)
        row = DSARRequest.objects.get(id=r.data["id"])
        self.assertEqual(row.status, DSARStatus.IDV_PENDING)

    @override_settings(DSAR_SKIP_HCAPTCHA_VERIFICATION=True)
    @pytest.mark.integration
    def test_idempotency_returns_existing_row(self):
        url = "/api/v1/public/dsar-requests/"
        body = {
            "tenant_id": str(self.tenant.id),
            "request_type": DSARRequestType.PORTABILITY,
            "subject_email": "idem@example.com",
            "regimes": ["GDPR"],
            "hcaptcha_response": "x",
        }
        h = {"HTTP_IDEMPOTENCY_KEY": f"idem-{self._idem_key}"}
        r1 = self.client.post(url, body, format="json", **h)
        r2 = self.client.post(url, body, format="json", **h)
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        # Idempotent retry returns the original response (201, not 200).
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        import json

        body1 = json.loads(r1.content)
        body2 = json.loads(r2.content)
        self.assertEqual(body1["public_reference_token"], body2["public_reference_token"])

    @override_settings(DSAR_SKIP_HCAPTCHA_VERIFICATION=True)
    @pytest.mark.integration
    def test_public_internal_api_token_enters_under_review_without_mail(self):
        mail.outbox.clear()
        url = "/api/v1/public/dsar-requests/"
        body = {
            "tenant_id": str(self.tenant.id),
            "request_type": DSARRequestType.ACCESS,
            "subject_email": "int@example.com",
            "regimes": ["GDPR"],
            "hcaptcha_response": "x",
            "verification_method": DSARVerificationMethod.INTERNAL_API_TOKEN,
        }
        r = self.client.post(url, body, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self.assertEqual(len(mail.outbox), 0)
        row = DSARRequest.objects.get(id=r.data["id"])
        self.assertEqual(row.status, DSARStatus.UNDER_REVIEW)

    @override_settings(DSAR_SKIP_HCAPTCHA_VERIFICATION=True)
    @pytest.mark.integration
    def test_idempotency_key_outside_window_triggers_new_dsar(self):
        url = "/api/v1/public/dsar-requests/"
        body = {
            "tenant_id": str(self.tenant.id),
            "request_type": DSARRequestType.ACCESS,
            "subject_email": "stale@example.com",
            "regimes": ["GDPR"],
            "hcaptcha_response": "y",
        }
        h = {"HTTP_IDEMPOTENCY_KEY": f"rotate-{self._idem_key}"}
        with freeze_time("2026-01-01T12:00:00Z"):
            r1 = self.client.post(url, body, format="json", **h)
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        with freeze_time("2026-01-03T12:00:00Z"):
            r2 = self.client.post(url, body, format="json", **h)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(r1.data["id"], r2.data["id"])


class DsarSlaScanTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="sla",
            slug="sla-" + uuid.uuid4().hex[:8],
            compliance_dsar_enabled=True,
        )

    @freeze_time("2026-05-01T12:00:00Z")
    @pytest.mark.integration
    def test_sla_warn_when_inside_window(self):
        row = create_dsar_public(
            tenant_id=str(self.tenant.id),
            request_type=DSARRequestType.ACCESS,
            subject_email="a@b.com",
            regimes=["GDPR"],
            verification_method=DSARVerificationMethod.MANUAL_REVIEW,
        )
        transition_status(row, DSARStatus.UNDER_REVIEW)
        with freeze_time("2026-05-25T12:00:00Z"):
            counters = run_dsar_statutory_clock_scan()
        self.assertGreaterEqual(counters.get("warn", 0) + counters.get("critical", 0), 1)
        row.refresh_from_db()
        self.assertNotEqual(row.last_sla_level, DSARSLALevel.NONE)

    @freeze_time("2026-05-01T12:00:00Z")
    @pytest.mark.integration
    def test_sla_scan_counters_increment_only_on_transition(self):
        row = create_dsar_public(
            tenant_id=str(self.tenant.id),
            request_type=DSARRequestType.ACCESS,
            subject_email="metrics@b.com",
            regimes=["GDPR"],
            verification_method=DSARVerificationMethod.MANUAL_REVIEW,
        )
        transition_status(row, DSARStatus.UNDER_REVIEW)
        with freeze_time("2026-05-25T12:00:00Z"):
            c1 = run_dsar_statutory_clock_scan()
        self.assertGreater(sum(c1.values()), 0)
        with freeze_time("2026-05-25T13:00:00Z"):
            c2 = run_dsar_statutory_clock_scan()
        self.assertEqual(sum(c2.values()), 0)


@override_settings(DSAR_SKIP_HCAPTCHA_VERIFICATION=True)
class DsarZipManifestTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="z", slug="z-" + uuid.uuid4().hex[:8])

    @pytest.mark.integration
    def test_zip_contains_manifest(self):
        row = DSARRequest.objects.create(
            tenant=self.tenant,
            request_type=DSARRequestType.ACCESS,
            regimes=["GDPR"],
            subject_email="zip@example.com",
        )
        raw, agg = build_dsar_zip_bytes(row)
        self.assertGreater(len(raw), 20)
        self.assertEqual(len(agg), 64)

    @pytest.mark.integration
    def test_access_zip_has_json_and_csv_manifested(self):
        row = DSARRequest.objects.create(
            tenant=self.tenant,
            request_type=DSARRequestType.ACCESS,
            regimes=["GDPR"],
            subject_email="mixed@example.com",
        )
        raw, _sha = build_dsar_zip_bytes(row)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = set(zf.namelist())
        self.assertIn("ACCESS/summary.json", names)
        self.assertIn("ACCESS/summary.csv", names)
        self.assertIn("MANIFEST.json", names)


class DsarBackupRegistryTests(TestCase):
    """D232.9 — cold-store backup annotation for erasure subjects."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="bk", slug="bk-" + uuid.uuid4().hex[:8])

    @pytest.mark.integration
    def test_registry_row_points_at_dsar(self):
        row = DSARRequest.objects.create(
            tenant=self.tenant,
            request_type=DSARRequestType.ERASURE,
            regimes=["GDPR"],
            subject_email="erase@example.com",
        )
        backup = registry_backup_for_erasure(row)
        self.assertEqual(backup.dsar_id, row.id)
        self.assertEqual(backup.subject_email_normalized, "erase@example.com")
        self.assertTrue(BackupAffectedBySubject.objects.filter(dsar=row).exists())


User = get_user_model()


class DsarErasureWarmCompletenessTests(TestCase):
    """Erasure completeness: DSAR ERASURE + linked Hub user runs real ErasureService."""

    @pytest.mark.integration
    def test_linked_user_triggers_erasure_completion(self):
        tenant = Tenant.objects.create(
            name="er-comp",
            slug="er-comp-" + uuid.uuid4().hex[:8],
            compliance_dsar_enabled=True,
        )
        user = User.objects.create_user(
            email=f"warm-erasure-{uuid.uuid4().hex[:6]}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        dsar = DSARRequest.objects.create(
            tenant=tenant,
            request_type=DSARRequestType.ERASURE,
            regimes=["GDPR"],
            subject_email=user.email.lower(),
            linked_user=user,
            status=DSARStatus.SUBMITTED,
        )
        execute_warm_erasure_if_linked(dsar, actor_user_id=str(user.id))
        latest = ErasureRequest.objects.filter(user=user).order_by("-requested_at").first()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.status, ErasureRequestStatus.COMPLETED)
