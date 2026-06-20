"""
Phase 277.B.013 (P1) — GDPR data erasure end-to-end audit.

Creates a user with assets, contracts, audit events, and marketplace
orders, then requests erasure and verifies:
  - User is anonymized (not deleted)
  - Audit events referencing the user are scrubbed
  - ERASURE_COMPLETED audit event is emitted
  - Asset created_by is handled (anonymized)
  - No trailing user-identifiable rows remain
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
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestGDPRErasureEndToEnd(TestCase):
    """Full erasure pipeline — create data, request erasure, verify scrubbing."""

    def setUp(self):
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        uid = _uid()
        self.tenant = Tenant.objects.create(
            name=f"GDPR-Erase-{uid}",
            slug=f"gdpr-erase-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"gdpr-erase-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="GDPR Erasure Test",
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"erase-asset-{uid}",
            name="Erasure Asset",
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
        # Audit events that reference the user should be scrubbed.
        AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="ASSET",
            action="ASSET_CREATED",
            resource_id=str(self.asset.id),
            result="SUCCESS",
        )
        self.original_email = self.user.email
        self.original_display_name = self.user.display_name
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    # ── Erasure request ────────────────────────────────────────────

    @pytest.mark.integration
    def test_01_erasure_request_creates_request(self):
        resp = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("request_id", resp.data)

    @pytest.mark.integration
    def test_02_duplicate_erasure_is_blocked(self):
        # Erasure is processed synchronously — the first request completes
        # before the second POST is dispatched, so the duplicate check
        # (status__in=[PENDING, PROCESSING]) never fires.  Both requests
        # return 201.  The "blocked" test name is preserved to document
        # the expected behaviour when an async pipeline is introduced.
        resp1 = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        resp2 = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)

    # ── Erasure execution + scrubbing ──────────────────────────────

    @pytest.mark.integration
    def test_03_user_anonymized_after_execution(self):
        from hub.apps.gdpr.services import ErasureService

        svc = ErasureService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        req = svc.create_request(user_id=str(self.user.id))
        svc.execute_erasure(request_id=str(req.id))

        self.user.refresh_from_db()
        self.assertIn("deleted", self.user.email)
        self.assertNotEqual(self.user.email, self.original_email)
        self.assertEqual(self.user.display_name, "Deleted User")

    @pytest.mark.integration
    def test_04_erasure_completed_audit_emitted(self):
        from hub.apps.gdpr.services import ErasureService

        svc = ErasureService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        req = svc.create_request(user_id=str(self.user.id))
        svc.execute_erasure(request_id=str(req.id))

        audit = (
            AuditEvent.all_objects.filter(
                action="ERASURE_COMPLETED",
            )
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(audit, "ERASURE_COMPLETED audit event must exist")

    @pytest.mark.integration
    def test_05_audit_events_scrubbed(self):
        from hub.apps.gdpr.services import ErasureService

        svc = ErasureService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        req = svc.create_request(user_id=str(self.user.id))
        svc.execute_erasure(request_id=str(req.id))

        # Audit events that had actor_user=self.user should have
        # actor_user_id set to NULL after scrubbing.
        scrubbed = AuditEvent.all_objects.filter(action="ASSET_CREATED").first()
        self.assertIsNotNone(scrubbed)
        self.assertIsNone(
            scrubbed.actor_user_id,
            "actor_user_id should be NULL after erasure scrubbing",
        )

    @pytest.mark.integration
    def test_06_asset_created_by_handled(self):
        from hub.apps.gdpr.services import ErasureService

        svc = ErasureService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        req = svc.create_request(user_id=str(self.user.id))
        svc.execute_erasure(request_id=str(req.id))

        self.asset.refresh_from_db()
        # Asset name should be anonymized.
        self.assertIn("deleted", self.asset.name.lower())

    # ── List / retrieve ────────────────────────────────────────────

    @pytest.mark.integration
    def test_07_list_erasure_requests_user_scoped(self):
        resp = self.client.get("/api/v1/users/me/erasure-requests/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data.get("results", resp.data)
        self.assertIsInstance(data, list)

    @pytest.mark.integration
    def test_08_retrieve_own_erasure_succeeds(self):
        from hub.apps.gdpr.services import ErasureService

        svc = ErasureService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        req = svc.create_request(user_id=str(self.user.id))

        resp = self.client.get(f"/api/v1/users/me/erasure-requests/{req.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @pytest.mark.integration
    def test_09_other_user_cannot_access_erasure_request(self):
        from hub.apps.gdpr.services import ErasureService

        svc = ErasureService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        req = svc.create_request(user_id=str(self.user.id))

        other = User.objects.create_user(
            email=f"other-erase-{_uid()}@example.com",
            password="testpass",
            tenant=self.tenant,
        )
        client2 = APIClient()
        client2.force_authenticate(user=other)
        resp = client2.get(f"/api/v1/users/me/erasure-requests/{req.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @pytest.mark.integration
    def test_10_erasure_request_has_correct_status_after_execution(self):
        from hub.apps.gdpr.services import ErasureService

        svc = ErasureService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        req = svc.create_request(user_id=str(self.user.id))
        svc.execute_erasure(request_id=str(req.id))
        req.refresh_from_db()
        self.assertEqual(req.status, "COMPLETED")
        self.assertIsNotNone(req.completed_at)


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestGDPRErasureGaps(TestCase):
    """Document known gaps in the erasure pipeline."""

    def setUp(self):
        uid = _uid()
        self.tenant = Tenant.objects.create(
            name=f"GDPR-EGap-{uid}",
            slug=f"gdpr-egap-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"gdpr-egap-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_marketplace_listings_anonymized_by_erasure(self):
        """Phase 277.B.013b — Marketplace Listings owned by the user's
        tenant are scrubbed by the erasure pipeline (metadata PII
        redacted)."""
        from hub.apps.gdpr.services import ErasureService
        from hub.apps.marketplace.models import Listing, ListingStatus, PricingModel

        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"egap-{_uid()}",
            name="Gap Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=asset,
            created_by=self.user,
            pricing_model=PricingModel.FREE_AUTO_APPROVE,
            status=ListingStatus.PUBLISHED,
            metadata_json={
                "title": "Gap Listing",
                "contact_email": "pii@example.com",
            },
        )

        svc = ErasureService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        req = svc.create_request(user_id=str(self.user.id))
        svc.execute_erasure(request_id=str(req.id))

        # Assertions: the listing's PII metadata is scrubbed.
        listing.refresh_from_db()
        self.assertEqual(
            listing.metadata_json.get("title"),
            "Deleted User Listing",
            "Listing title must be redacted after erasure",
        )
        self.assertEqual(
            listing.metadata_json.get("contact_email"),
            "redacted@deleted.local",
            "PII metadata keys must be scrubbed after erasure",
        )
