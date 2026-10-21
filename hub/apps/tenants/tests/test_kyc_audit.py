"""
Tests for KYC status transitions and audit (feat1 2.3.3).

Asserts that transitions to PENDING_REVIEW and VERIFIED produce audit entries
(KYC_STATUS_CHANGED). No mocks; uses real Tenant save and AuditEvent.
"""

import pytest
from django.test import TestCase

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class KYCStatusAuditTest(TestCase):
    """Test that kyc_status changes produce KYC_STATUS_CHANGED audit events."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="KYC Audit Tenant",
            slug="kyc-audit-tenant",
            kyc_status=KYCStatus.UNVERIFIED,
        )

    def test_transition_to_pending_review_produces_audit_entry(self):
        """Transition UNVERIFIED -> PENDING_REVIEW produces KYC_STATUS_CHANGED audit."""
        initial_count = AuditEvent.objects.filter(
            action="KYC_STATUS_CHANGED",
            tenant=self.tenant,
        ).count()

        self.tenant.kyc_status = KYCStatus.PENDING_REVIEW
        self.tenant.save(update_fields=["kyc_status", "updated_at"])

        events = AuditEvent.objects.filter(
            action="KYC_STATUS_CHANGED",
            tenant=self.tenant,
        ).order_by("-timestamp")
        self.assertEqual(events.count(), initial_count + 1)
        latest = events.first()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.resource_type, "TENANT")
        self.assertEqual(latest.tenant_id, self.tenant.id)
        self.assertEqual(latest.details_json.get("previous_kyc_status"), KYCStatus.UNVERIFIED)
        self.assertEqual(latest.details_json.get("new_kyc_status"), KYCStatus.PENDING_REVIEW)
        self.assertEqual(latest.details_json.get("tenant_id"), str(self.tenant.id))

    def test_transition_to_verified_produces_audit_entry(self):
        """Transition PENDING_REVIEW -> VERIFIED produces KYC_STATUS_CHANGED audit."""
        self.tenant.kyc_status = KYCStatus.PENDING_REVIEW
        self.tenant.save(update_fields=["kyc_status", "updated_at"])

        initial_count = AuditEvent.objects.filter(
            action="KYC_STATUS_CHANGED",
            tenant=self.tenant,
        ).count()

        self.tenant.kyc_status = KYCStatus.VERIFIED
        self.tenant.save(update_fields=["kyc_status", "updated_at"])

        events = AuditEvent.objects.filter(
            action="KYC_STATUS_CHANGED",
            tenant=self.tenant,
        ).order_by("-timestamp")
        self.assertEqual(events.count(), initial_count + 1)
        latest = events.first()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.details_json.get("previous_kyc_status"), KYCStatus.PENDING_REVIEW)
        self.assertEqual(latest.details_json.get("new_kyc_status"), KYCStatus.VERIFIED)

    def test_transition_unverified_to_verified_produces_audit_entry(self):
        """Transition UNVERIFIED -> VERIFIED produces KYC_STATUS_CHANGED audit."""
        initial_count = AuditEvent.objects.filter(
            action="KYC_STATUS_CHANGED",
            tenant=self.tenant,
        ).count()

        self.tenant.kyc_status = KYCStatus.VERIFIED
        self.tenant.save(update_fields=["kyc_status", "updated_at"])

        events = AuditEvent.objects.filter(
            action="KYC_STATUS_CHANGED",
            tenant=self.tenant,
        ).order_by("-timestamp")
        self.assertEqual(events.count(), initial_count + 1)
        latest = events.first()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.details_json.get("previous_kyc_status"), KYCStatus.UNVERIFIED)
        self.assertEqual(latest.details_json.get("new_kyc_status"), KYCStatus.VERIFIED)

    def test_kyc_status_unchanged_produces_no_audit_entry(self):
        """Saving tenant without changing kyc_status does not create KYC_STATUS_CHANGED."""
        self.tenant.name = "KYC Audit Tenant Renamed"
        self.tenant.save(update_fields=["name", "updated_at"])

        count = AuditEvent.objects.filter(
            action="KYC_STATUS_CHANGED",
            tenant=self.tenant,
        ).count()
        self.assertEqual(count, 0)

    def test_update_tenant_service_kyc_status_produces_audit_entry(self):
        """TenantService.update_tenant(kyc_status=...) produces KYC_STATUS_CHANGED."""
        from hub.apps.tenants.services import TenantService

        service = TenantService(tenant_id=str(self.tenant.id), user_id=None)
        initial_count = AuditEvent.objects.filter(
            action="KYC_STATUS_CHANGED",
            tenant=self.tenant,
        ).count()

        service.update_tenant(
            tenant_id=str(self.tenant.id),
            kyc_status=KYCStatus.PENDING_REVIEW,
        )

        events = AuditEvent.objects.filter(
            action="KYC_STATUS_CHANGED",
            tenant=self.tenant,
        ).order_by("-timestamp")
        self.assertEqual(events.count(), initial_count + 1)
        latest = events.first()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.details_json.get("previous_kyc_status"), KYCStatus.UNVERIFIED)
        self.assertEqual(latest.details_json.get("new_kyc_status"), KYCStatus.PENDING_REVIEW)
