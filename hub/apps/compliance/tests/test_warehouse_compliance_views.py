"""
285.10.3.4.3 — Tests for warehouse compliance view endpoint.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model as _get_user_model
from rest_framework.test import APIClient

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

User = _get_user_model()


@pytest.mark.django_db
@pytest.mark.integration
class TestScanWarehouseEndpoint:
    @pytest.fixture(autouse=True)
    def setup(self, django_user_model):
        self.tenant = Tenant.objects.create(
            name=f"cv-{uuid.uuid4().hex[:8]}",
            slug=f"cv-{uuid.uuid4().hex[:8]}",
            compliance_fail_closed_enabled=True,
            warehouse_compliance_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = django_user_model.objects.create_user(
            email=f"cv-{uuid.uuid4().hex[:8]}@test.com",
            password="test",
            tenant=self.tenant,
        )
        # Minimal asset to satisfy ComplianceRun.clean() FK validation
        from hub.apps.assets.models import Asset

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"cv-{uuid.uuid4().hex[:8]}",
            name="CV Asset",
            status="DRAFT",
            created_by=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _create_run(self, **kw):
        return ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            scan_mode=kw.pop("scan_mode", "WAREHOUSE_SQL"),
            status=ComplianceRunStatus.PENDING,
            warehouse_config=kw.pop("warehouse_config", {"table_fqn": "DB.S.T"}),
            **kw,
        )

    @pytest.mark.integration
    def test_400_for_non_warehouse_mode(self):
        run = self._create_run(scan_mode="FILE_SCAN")
        resp = self.client.post(f"/api/v1/compliance/runs/{run.id}/scan-warehouse/")
        assert resp.status_code == 400

    @pytest.mark.integration
    def test_400_for_missing_warehouse_config(self):
        run = self._create_run(warehouse_config=None)
        resp = self.client.post(f"/api/v1/compliance/runs/{run.id}/scan-warehouse/")
        assert resp.status_code == 400

    @pytest.mark.integration
    def test_403_when_flag_disabled(self):
        self.tenant.warehouse_compliance_enabled = False
        self.tenant.save()
        run = self._create_run()
        resp = self.client.post(f"/api/v1/compliance/runs/{run.id}/scan-warehouse/")
        assert resp.status_code == 403

    @pytest.mark.integration
    def test_401_unauthenticated(self):
        client = APIClient()
        run = self._create_run()
        resp = client.post(f"/api/v1/compliance/runs/{run.id}/scan-warehouse/")
        assert resp.status_code == 401

    @pytest.mark.integration
    def test_200_successful_warehouse_scan(self):
        """Valid WAREHOUSE_SQL run with warehouse_config returns 200."""
        from unittest.mock import patch

        run = self._create_run(scan_mode="WAREHOUSE_SQL")
        # Avoid real microservice call — the view's scan_warehouse
        # action delegates to ComplianceService.scan_inmemory_warehouse.
        with patch(
            "hub.apps.compliance.views.ComplianceService.scan_inmemory_warehouse",
            return_value=run,
        ) as mock_scan:
            resp = self.client.post(
                f"/api/v1/compliance/runs/{run.id}/scan-warehouse/",
            )
            assert resp.status_code == 200
            body = resp.json()
            assert "id" in body
            assert body["status"] == run.status
            assert body["overall_status"] == run.overall_status
            assert "risk_level" in body
            mock_scan.assert_called_once()

    @pytest.mark.integration
    def test_404_cross_tenant_scan_warehouse(self):
        """get_object() returns 404 when run belongs to another tenant."""
        other_tenant = Tenant.objects.create(
            name=f"cv-other-{uuid.uuid4().hex[:8]}",
            slug=f"cv-other-{uuid.uuid4().hex[:8]}",
            warehouse_compliance_enabled=True,
        )
        ensure_tenant_has_active_subscription(other_tenant)
        other_user = self.user.__class__.objects.create_user(
            email=f"cv-other-{uuid.uuid4().hex[:8]}@test.com",
            password="test",
            tenant=other_tenant,
        )
        from hub.apps.assets.models import Asset

        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key=f"cv-other-{uuid.uuid4().hex[:8]}",
            name="Other Asset",
            status="DRAFT",
            created_by=other_user,
        )
        other_run = ComplianceRun.objects.create(
            tenant=other_tenant,
            asset=other_asset,
            scan_mode="WAREHOUSE_SQL",
            status=ComplianceRunStatus.PENDING,
            warehouse_config={"table_fqn": "DB.S.T"},
        )
        resp = self.client.post(
            f"/api/v1/compliance/runs/{other_run.id}/scan-warehouse/",
        )
        assert resp.status_code == 404
