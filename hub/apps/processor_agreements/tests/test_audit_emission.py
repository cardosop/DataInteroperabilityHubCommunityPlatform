"""283.3.6.3 — verify PROCESSOR_AGREEMENT_CREATED / UPDATED / DELETED emit
from all mutation paths. Real DB, real audit rows — no mocks."""

from __future__ import annotations
import pytest
import pytest

import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.processor_agreements.models import (
    Processor,
    ProcessorAgreement,
    ProcessorAgreementType,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, User, UserRole, UserStatus


class ProcessorAgreementAuditEmissionTests(TestCase):
    """Verify PROCESSOR_AGREEMENT_CREATED/UPDATED/DELETED emit from all mutation paths."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="pa-audit",
            slug="pa-audit-" + uuid.uuid4().hex[:8],
            compliance_processor_agreements_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.user = User.objects.create_user(
            email=f"pa-{uuid.uuid4().hex[:8]}@example.com",
            password="M3sh@nt!Hub#2026",
            tenant=self.tenant,
            display_name="PA Admin",
            status=UserStatus.ACTIVE,
        )
        admin_role = Role.objects.create(tenant=self.tenant, name="TENANT_ADMIN", description="")
        UserRole.objects.create(user=self.user, tenant=self.tenant, role=admin_role)

        self.processor = Processor.objects.create(
            tenant=self.tenant,
            name="TestProcessor",
            legal_name="Test Processor Ltd",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @pytest.mark.integration
    def test_create_agreement_emits_created_event(self):
        """POST /processor-agreements/ → PROCESSOR_AGREEMENT_CREATED."""
        before = AuditEvent.objects.filter(
            tenant=self.tenant, action="PROCESSOR_AGREEMENT_CREATED"
        ).count()
        resp = self.client.post(
            "/api/v1/processor-agreements/processor-agreements/",
            {
                "processor": str(self.processor.id),
                "agreement_type": "DPA",
                "document_uri": "https://example.com/dpa.pdf",
                "document_hash": "a" * 64,
                "effective_from": "2026-01-01",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        after = AuditEvent.objects.filter(
            tenant=self.tenant, action="PROCESSOR_AGREEMENT_CREATED"
        ).count()
        self.assertEqual(after, before + 1)

    @pytest.mark.integration
    def test_update_agreement_emits_updated_event(self):
        """PATCH /processor-agreements/{id}/ → PROCESSOR_AGREEMENT_UPDATED."""
        agreement = ProcessorAgreement.objects.create(
            tenant=self.tenant,
            processor=self.processor,
            agreement_type=ProcessorAgreementType.DPA,
            document_uri="https://example.com/dpa.pdf",
            document_hash="a" * 64,
            effective_from="2026-01-01",
        )
        before = AuditEvent.objects.filter(
            tenant=self.tenant, action="PROCESSOR_AGREEMENT_UPDATED"
        ).count()
        resp = self.client.patch(
            f"/api/v1/processor-agreements/processor-agreements/{agreement.id}/",
            {"transfer_mechanism_summary": "Updated transfer mechanism"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        after = AuditEvent.objects.filter(
            tenant=self.tenant, action="PROCESSOR_AGREEMENT_UPDATED"
        ).count()
        self.assertEqual(after, before + 1)

    @pytest.mark.integration
    def test_delete_agreement_emits_deleted_event(self):
        """DELETE /processor-agreements/{id}/ → PROCESSOR_AGREEMENT_DELETED."""
        agreement = ProcessorAgreement.objects.create(
            tenant=self.tenant,
            processor=self.processor,
            agreement_type=ProcessorAgreementType.SCC,
            document_uri="https://example.com/scc.pdf",
            document_hash="b" * 64,
            effective_from="2026-01-01",
        )
        before = AuditEvent.objects.filter(
            tenant=self.tenant, action="PROCESSOR_AGREEMENT_DELETED"
        ).count()
        resp = self.client.delete(
            f"/api/v1/processor-agreements/processor-agreements/{agreement.id}/",
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        after = AuditEvent.objects.filter(
            tenant=self.tenant, action="PROCESSOR_AGREEMENT_DELETED"
        ).count()
        self.assertEqual(after, before + 1)
