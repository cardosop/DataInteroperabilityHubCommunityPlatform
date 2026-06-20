"""
Phase 205: Compliance shared circuit breaker + activation degradation (no unittest mocks).

Uses a connection-refused compliance URL to open the circuit, then verifies activation
with WARN and audit ``COMPLIANCE_SERVICE_UNAVAILABLE``.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, ComplianceStatus, DQStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.compliance.service_client import ComplianceServiceClient
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreakerState,
    reset_circuit_breaker_by_name,
)
from hub.apps.core.resilience.service_breakers import get_shared_circuit_breaker
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


@override_settings(COMPLIANCE_SERVICE_URL="http://127.0.0.1:1")
class ComplianceCircuitBreakerActivationTests(TestCase):
    def setUp(self):
        reset_circuit_breaker_by_name("compliance-service")
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Comp CB Tenant {uid}",
            slug=f"comp-cb-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"comp-cb-user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def tearDown(self):
        reset_circuit_breaker_by_name("compliance-service")

    def _open_compliance_circuit(self) -> None:
        client = ComplianceServiceClient()
        breaker = get_shared_circuit_breaker("compliance-service")
        threshold = breaker.failure_threshold
        for i in range(threshold):
            result = client.scan_file(
                b"c\n1\n",
                "csv",
                tenant_id=str(self.tenant.id),
            )
            # Verify each call actually failed (returned fallback/error)
            self.assertEqual(
                result.get("overall_status"),
                "UNKNOWN",
                f"Call {i + 1}/{threshold} should have failed against unreachable host",
            )
        self.assertEqual(breaker.get_state(), CircuitBreakerState.OPEN)

    def test_activation_proceeds_with_warn_when_compliance_circuit_open(self):
        self._open_compliance_circuit()
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uuid.uuid4().hex[:8]}",
            name="Comp CB Asset",
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "schema": {"fields": []}}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="t.csv",
            content_type="text/csv",
            size=8,
            storage_path="t/y.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            created_by=self.user,
        )

        resp = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/",
            {"version": asset.version},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        asset.refresh_from_db()
        self.assertEqual(asset.compliance_status, ComplianceStatus.WARN)
        ev = AuditEvent.objects.filter(
            action="COMPLIANCE_SERVICE_UNAVAILABLE", resource_id=asset.id
        ).first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.details_json.get("circuit_state"), "OPEN")
        self.assertEqual(str(ev.details_json.get("asset_id")), str(asset.id))
