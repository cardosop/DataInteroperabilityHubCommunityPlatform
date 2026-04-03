"""
Phase 205: DQ shared circuit breaker + activation degradation (no unittest mocks).

Opens the real ``dq-service`` circuit using a connection-refused URL, then verifies
activation proceeds with WARN and audit ``DQ_SERVICE_UNAVAILABLE``.
"""
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, ComplianceStatus, DQStatus
from hub.apps.audit.models import AuditEvent
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
from hub.apps.dq.services import DQService
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


@override_settings(DQ_SERVICE_URL="http://127.0.0.1:1")
class DQCircuitBreakerActivationTests(TestCase):
    def setUp(self):
        reset_circuit_breaker_by_name("dq-service")
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"DQ CB Tenant {uid}",
            slug=f"dq-cb-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"dq-cb-user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def tearDown(self):
        reset_circuit_breaker_by_name("dq-service")

    def _open_dq_circuit(self) -> None:
        breaker = get_shared_circuit_breaker("dq-service")
        threshold = breaker.failure_threshold
        # Sub-threshold calls: each should fail and increment the failure count
        for _ in range(threshold - 1):
            with self.assertRaises(Exception):
                DQService.run_external_dq_check(b"col\n1\n", "csv", use_cache=False)
        # Threshold-reaching call: triggers OPEN and returns fallback
        out = DQService.run_external_dq_check(b"col\n1\n", "csv", use_cache=False)
        self.assertEqual(out.get("overall_status"), "UNKNOWN")
        self.assertEqual(breaker.get_state(), CircuitBreakerState.OPEN)

    def test_activation_proceeds_with_warn_when_dq_circuit_open(self):
        self._open_dq_circuit()
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uuid.uuid4().hex[:8]}",
            name="DQ CB Asset",
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
            storage_path="t/x.csv",
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
        self.assertEqual(asset.dq_status, DQStatus.WARN)
        ev = AuditEvent.objects.filter(
            action="DQ_SERVICE_UNAVAILABLE", resource_id=asset.id
        ).first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.details_json.get("circuit_state"), "OPEN")
        self.assertEqual(str(ev.details_json.get("asset_id")), str(asset.id))
