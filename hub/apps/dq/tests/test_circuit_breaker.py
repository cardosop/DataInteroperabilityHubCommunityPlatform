"""
Phase 205: DQ shared circuit breaker + activation degradation.

Verifies that asset activation degrades gracefully to ``DQStatus.WARN``
when the dq-service circuit breaker is OPEN and emits the
``DQ_SERVICE_UNAVAILABLE`` audit event.

Uses direct state injection (``breaker._set_state(OPEN)``) to open the
circuit rather than accumulating real connection-refused failures over
HTTP with retry-backoff.  The circuit breaker's failure-counting +
OPEN-transition logic is tested exhaustively in
``hub/apps/core/tests/test_circuit_breaker.py``; this test only needs
the post-OPEN behaviour — the activation degradation path and the audit
event shape.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
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
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DQCircuitBreakerActivationTests(TestCase):
    """Phase 205: DQ shared circuit breaker + activation degradation.

    Directly injects the circuit-breaker OPEN state via
    ``_set_state(CircuitBreakerState.OPEN)`` so the test is fast,
    deterministic, and isolated from the retry/backoff behaviour of the
    real ``DQServiceClient`` transport layer (which is exercised
    elsewhere).
    """

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

    @staticmethod
    def _open_dq_circuit() -> None:
        """Force the shared dq-service circuit breaker to OPEN.

        Uses ``_set_state`` (a public-method-by-convention internal
        API) because this test verifies the *downstream* behaviour
        when the circuit is already open — not the failure-counting
        transition logic (which lives in the core circuit-breaker
        test suite).
        """
        breaker = get_shared_circuit_breaker("dq-service")
        breaker._set_state(CircuitBreakerState.OPEN)
        breaker._set_opened_at()
        breaker._reset_success_count()

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

        # Activation with circuit OPEN: the activation endpoint checks
        # the circuit state and degrades to WARN without making any
        # DQ-service HTTP call.
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
