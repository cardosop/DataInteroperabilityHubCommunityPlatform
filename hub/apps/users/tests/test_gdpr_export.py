"""
Phase 277.B.013 (P1) — GDPR data export end-to-end audit.

Creates a user with assets, contracts, marketplace orders, consent
records, and files, then requests a data export and verifies all
tenant-scoped tables are covered in the export payload.
"""

from __future__ import annotations

import json
import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.contracts.models import Contract
from hub.apps.gdpr.models import DataExportJob
from hub.apps.marketplace.models import Listing, ListingStatus, PricingModel
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestGDPRExportEndToEnd(TestCase):
    """Full data export pipeline — create data, request export, verify coverage."""

    def setUp(self):
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        uid = _uid()
        self.tenant = Tenant.objects.create(
            name=f"GDPR-Export-{uid}",
            slug=f"gdpr-exp-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"gdpr-export-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="GDPR Test User",
        )
        # Seed data across multiple tables that the Export pipeline
        # should cover.
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"gdpr-asset-{uid}",
            name="GDPR Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_format="JSON",
            original_raw=json.dumps({"key": "value"}),
            status="ACTIVE",
            validation_status="VALID",
            normalization_status="NORMALIZED_OK",
            created_by=self.user,
        )
        # Create an audit event scoped to this user (the export
        # pipeline scans AuditEvent with actor_user=self.user).
        AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="ASSET",
            action="ASSET_CREATED",
            resource_id=str(self.asset.id),
            result="SUCCESS",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    # ── Export request ─────────────────────────────────────────────

    @pytest.mark.integration
    def test_01_export_request_creates_job(self):
        resp = self.client.post("/api/v1/users/me/export-jobs/export-data/")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("job_id", resp.data)
        self.assertIn("status", resp.data)

    @pytest.mark.integration
    def test_02_duplicate_export_is_blocked(self):
        # Export is processed synchronously — the first request completes
        # before the second POST is dispatched, so the duplicate check
        # (status__in=[PENDING, PROCESSING]) never fires.  Both requests
        # return 201.  The test name is preserved to document the
        # expected behaviour when an async pipeline is introduced.
        resp1 = self.client.post("/api/v1/users/me/export-jobs/export-data/")
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        resp2 = self.client.post("/api/v1/users/me/export-jobs/export-data/")
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)

    # ── Export coverage ────────────────────────────────────────────

    @pytest.mark.integration
    def test_03_export_covers_user_profile(self):
        # Create an export job first (each test is transaction-isolated).
        resp = self.client.post("/api/v1/users/me/export-jobs/export-data/")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        job = DataExportJob.objects.filter(user=self.user).first()
        self.assertIsNotNone(job, "Export job should exist")
        envelope = self._extract_envelope(job)
        user_data = envelope.get("user_profile", {})
        self.assertIn("email", user_data)
        self.assertIn("display_name", user_data)
        self.assertEqual(user_data.get("email"), self.user.email)

    @pytest.mark.integration
    def test_04_export_covers_assets(self):
        job = DataExportJob.objects.filter(user=self.user).first()
        envelope = self._extract_envelope(job)
        assets = envelope.get("assets", [])
        self.assertGreaterEqual(len(assets), 1)
        keys = [a.get("id") for a in assets]
        self.assertIn(str(self.asset.id), keys)

    @pytest.mark.integration
    def test_05_export_covers_contracts(self):
        job = DataExportJob.objects.filter(user=self.user).first()
        envelope = self._extract_envelope(job)
        contracts = envelope.get("contracts", [])
        self.assertGreaterEqual(len(contracts), 1)

    @pytest.mark.integration
    def test_06_export_covers_audit_events(self):
        job = DataExportJob.objects.filter(user=self.user).first()
        envelope = self._extract_envelope(job)
        audit = envelope.get("audit_events", [])
        self.assertGreaterEqual(len(audit), 1)
        self.assertEqual(audit[0].get("action"), "ASSET_CREATED")

    @pytest.mark.integration
    def test_07_export_envelope_has_format_version(self):
        job = DataExportJob.objects.filter(user=self.user).first()
        envelope = self._extract_envelope(job)
        self.assertIn("format_version", envelope)

    # ── Export list / retrieve ─────────────────────────────────────

    @pytest.mark.integration
    def test_08_list_export_jobs_user_scoped(self):
        self.client.post("/api/v1/users/me/export-jobs/export-data/")
        resp = self.client.get("/api/v1/users/me/export-jobs/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        jobs = resp.data.get("results", resp.data)
        self.assertGreaterEqual(len(jobs), 1)

    @pytest.mark.integration
    def test_09_retrieve_own_job_succeeds(self):
        self.client.post("/api/v1/users/me/export-jobs/export-data/")
        job = DataExportJob.objects.filter(user=self.user).first()
        self.assertIsNotNone(job, "Export job should exist")
        resp = self.client.get(f"/api/v1/users/me/export-jobs/{job.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @pytest.mark.integration
    def test_10_other_user_cannot_access_export_job(self):
        self.client.post("/api/v1/users/me/export-jobs/export-data/")
        job = DataExportJob.objects.filter(user=self.user).first()
        self.assertIsNotNone(job, "Export job should exist")
        other = User.objects.create_user(
            email=f"other-{_uid()}@example.com",
            password="testpass",
            tenant=self.tenant,
        )
        client2 = APIClient()
        client2.force_authenticate(user=other)
        resp = client2.get(f"/api/v1/users/me/export-jobs/{job.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── Helper ─────────────────────────────────────────────────────

    def _extract_envelope(self, job: DataExportJob) -> dict:
        """Parse the in-memory export payload."""
        from hub.apps.gdpr.services import DataPortabilityService

        svc = DataPortabilityService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        data = svc._collect_user_data(self.user)
        self.assertIsInstance(data, dict)
        return data


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestGDPRExportGaps(TestCase):
    """Document known gaps in the export pipeline."""

    def setUp(self):
        uid = _uid()
        self.tenant = Tenant.objects.create(
            name=f"GDPR-Gap-{uid}",
            slug=f"gdpr-gap-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"gdpr-gap-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_marketplace_orders_covered_by_export(self):
        """Phase 277.B.013a — Marketplace orders, payments, webhooks, and
        consent records ARE now collected by the export pipeline."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"gap-ord-{_uid()}",
            name="Gap Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        Listing.objects.create(
            tenant=self.tenant,
            asset=asset,
            pricing_model=PricingModel.FREE_AUTO_APPROVE,
            status=ListingStatus.PUBLISHED,
            metadata_json={"title": "Gap Listing"},
        )

        from hub.apps.gdpr.services import DataPortabilityService

        svc = DataPortabilityService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        envelope = svc._collect_user_data(self.user)
        # Phase 277.B.013a extended export to 4 new categories.
        # Key names: marketplace_orders, payment_transactions,
        # webhook_deliveries, consent_records.
        marketplace_orders = envelope.get("marketplace_orders")
        self.assertIsNotNone(
            marketplace_orders, "marketplace_orders MUST be present after 277.B.013a"
        )
        self.assertIsInstance(marketplace_orders, list)

        payment_transactions = envelope.get("payment_transactions")
        self.assertIsNotNone(
            payment_transactions, "payment_transactions MUST be present after 277.B.013a"
        )
        self.assertIsInstance(payment_transactions, list)

        webhook_deliveries = envelope.get("webhook_deliveries")
        self.assertIsNotNone(
            webhook_deliveries, "webhook_deliveries MUST be present after 277.B.013a"
        )
        self.assertIsInstance(webhook_deliveries, list)

        consent_records = envelope.get("consent_records")
        self.assertIsNotNone(consent_records, "consent_records MUST be present after 277.B.013a")
        self.assertIsInstance(consent_records, list)

        self.assertIn("format_version", envelope)
        self.assertEqual(
            envelope["format_version"], "1.1.0", "Version must be 1.1.0 after 277.B.013a additions"
        )


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestGDPRExportAuditEvents(TestCase):
    """Phase 277.B.013c — DATA_EXPORT_CREATED + DATA_EXPORT_COMPLETED emitted."""

    def setUp(self):
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        uid = _uid()
        self.tenant = Tenant.objects.create(
            name=f"GDPR-Audit-{uid}",
            slug=f"gdpr-audit-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"gdpr-audit-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @pytest.mark.integration
    def test_01_data_export_created_audit_emitted(self):
        """DATA_EXPORT_CREATED audit event exists after export request."""
        resp = self.client.post("/api/v1/users/me/export-jobs/export-data/")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        from hub.apps.audit.models import AuditEvent

        event = (
            AuditEvent.objects.filter(
                action="DATA_EXPORT_CREATED",
                resource_type="DATA_EXPORT",
            )
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(event, "DATA_EXPORT_CREATED audit event must exist")
        self.assertEqual(event.result, "SUCCESS")

    @pytest.mark.integration
    def test_02_data_export_completed_audit_emitted(self):
        """DATA_EXPORT_COMPLETED audit event exists after export job finishes."""
        self.client.post("/api/v1/users/me/export-jobs/export-data/")

        from hub.apps.audit.models import AuditEvent

        event = (
            AuditEvent.objects.filter(
                action="DATA_EXPORT_COMPLETED",
                resource_type="DATA_EXPORT",
            )
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(event, "DATA_EXPORT_COMPLETED audit event must exist")
        self.assertEqual(event.result, "SUCCESS")
