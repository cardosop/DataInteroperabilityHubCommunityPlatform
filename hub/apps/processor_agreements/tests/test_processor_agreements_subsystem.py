"""Integration tests for processor agreement tracker (real ORM; no mocks)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.audit.models import AuditEvent
from hub.apps.notifications.models import UserNotification
from hub.apps.processor_agreements.expiry_scan import run_processor_agreement_expiry_scan
from hub.apps.processor_agreements.models import (
    Processor,
    ProcessorAgreement,
    ProcessorAgreementType,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

User = get_user_model()

_DOC_HASH = hashlib.sha256(b"dummy-pdf-bytes").hexdigest()


class ProcessorAgreementWorkflowTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="pa1",
            slug="pa1-" + uuid.uuid4().hex[:8],
            compliance_processor_agreements_enabled=True,
        )
        # Phase 25.2.4 ``TenantSuspensionMiddleware`` blocks writes
        # (POST/PUT/PATCH/DELETE) on tenants without an ACTIVE
        # subscription — every API test below issues writes.
        ensure_tenant_has_active_subscription(self.tenant)
        self.admin = User.objects.create_user(
            email=f"pa1-{uuid.uuid4().hex[:8]}@example.com",
            password="M3sh@nt!Hub#2026!",
            tenant=self.tenant,
            display_name="Admin",
            status=UserStatus.ACTIVE,
        )
        role = Role.objects.create(tenant=self.tenant, name="TENANT_ADMIN", description="")
        UserRole.objects.create(user=self.admin, tenant=self.tenant, role=role)

    def _client(self) -> APIClient:
        c = APIClient()
        c.force_authenticate(self.admin)
        return c

    @pytest.mark.integration
    def test_ssrf_rejects_loopback_document_uri(self):
        proc = Processor.objects.create(tenant=self.tenant, name="P1")
        agreement = ProcessorAgreement(
            tenant=self.tenant,
            processor=proc,
            agreement_type=ProcessorAgreementType.DPA,
            document_uri="http://127.0.0.1/evil",
            document_hash=_DOC_HASH,
            effective_from=date.today(),
            sub_processors_declared=[],
        )
        with self.assertRaises(ValidationError):
            agreement.full_clean()

    @pytest.mark.integration
    def test_scc_requires_transfer_summary(self):
        proc = Processor.objects.create(tenant=self.tenant, name="SCC vendor")
        agreement = ProcessorAgreement(
            tenant=self.tenant,
            processor=proc,
            agreement_type=ProcessorAgreementType.SCC,
            document_uri="https://example.com/scc.pdf",
            document_hash=_DOC_HASH,
            effective_from=date.today(),
            transfer_mechanism_summary="short",
            sub_processors_declared=[],
        )
        with self.assertRaises(ValidationError):
            agreement.full_clean()

    @pytest.mark.integration
    def test_expiry_scan_warn_60_and_idempotent(self):
        proc = Processor.objects.create(tenant=self.tenant, name="ExpiringCo")
        today = date(2027, 1, 1)
        ProcessorAgreement.objects.create(
            tenant=self.tenant,
            processor=proc,
            agreement_type=ProcessorAgreementType.DPA,
            document_uri="https://example.com/dpa.pdf",
            document_hash=_DOC_HASH,
            effective_from=today - timedelta(days=30),
            expires_on=today + timedelta(days=60),
            sub_processors_declared=[],
        )
        c1 = run_processor_agreement_expiry_scan(today=today)
        self.assertEqual(c1.get("warn_60", 0), 1)
        c2 = run_processor_agreement_expiry_scan(today=today)
        self.assertEqual(c2.get("warn_60", 0), 0)

    @pytest.mark.integration
    def test_subprocessor_change_notifies_tenant_admin(self):
        proc = Processor.objects.create(tenant=self.tenant, name="SubCo")
        agr = ProcessorAgreement.objects.create(
            tenant=self.tenant,
            processor=proc,
            agreement_type=ProcessorAgreementType.DPA,
            document_uri="https://example.com/dpa.pdf",
            document_hash=_DOC_HASH,
            effective_from=date.today(),
            sub_processors_declared=[{"name": "Alpha"}],
        )
        before = UserNotification.objects.filter(user=self.admin, tenant=self.tenant).count()
        client = self._client()
        url = f"/api/v1/processor-agreements/processor-agreements/{agr.id}/"
        resp = client.patch(
            url,
            {"sub_processors_declared": [{"name": "Beta"}]},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                resource_id=str(agr.id),
                action="PROCESSOR_AGREEMENT_SUBPROCESSOR_CHANGED",
            ).exists()
        )
        after = UserNotification.objects.filter(user=self.admin, tenant=self.tenant).count()
        self.assertGreater(after, before)

    @pytest.mark.integration
    def test_asset_processor_link(self):
        proc = Processor.objects.create(tenant=self.tenant, name="LinkedCo")
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="k-" + uuid.uuid4().hex[:8],
            name="Asset 1",
            created_by=self.admin,
        )
        client = self._client()
        r = client.post(
            "/api/v1/processor-agreements/asset-processor-links/",
            {"asset": str(asset.id), "processor": str(proc.id)},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        asset.refresh_from_db()
        self.assertEqual(asset.processors.count(), 1)

    @pytest.mark.integration
    def test_agreement_delete_writes_deleted_audit(self):
        proc = Processor.objects.create(tenant=self.tenant, name="DelCo")
        agr = ProcessorAgreement.objects.create(
            tenant=self.tenant,
            processor=proc,
            agreement_type=ProcessorAgreementType.DPA,
            document_uri="https://example.com/dpa.pdf",
            document_hash=_DOC_HASH,
            effective_from=date.today(),
            sub_processors_declared=[],
        )
        client = self._client()
        url = f"/api/v1/processor-agreements/processor-agreements/{agr.id}/"
        resp = client.delete(url, HTTP_X_TENANT_ID=str(self.tenant.id))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProcessorAgreement.objects.filter(id=agr.id).exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                resource_id=str(agr.id),
                action="PROCESSOR_AGREEMENT_DELETED",
            ).exists()
        )

    @pytest.mark.integration
    def test_api_rejects_ssrf_document_uri_on_create(self):
        proc = Processor.objects.create(tenant=self.tenant, name="SSRFFail")
        client = self._client()
        resp = client.post(
            "/api/v1/processor-agreements/processor-agreements/",
            {
                "processor": str(proc.id),
                "agreement_type": "DPA",
                "document_uri": "http://127.0.0.1/evil",
                "document_hash": _DOC_HASH,
                "effective_from": str(date.today()),
                "sub_processors_declared": [],
            },
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
