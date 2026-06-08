"""
285.10.3.4.3 — Tests for warehouse compliance view endpoint.
"""
import pytest

import uuid

from rest_framework.test import APIClient

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.tenants.models import Tenant

from django.contrib.auth import get_user_model as _get_user_model
User = _get_user_model()


@pytest.mark.django_db
@pytest.mark.integration
class TestScanWarehouseEndpoint:
    @pytest.fixture(autouse=True)
    def setup(self, django_user_model):
        self.tenant = Tenant.objects.create(
            name=f"cv-{uuid.uuid4().hex[:8]}", slug=f"cv-{uuid.uuid4().hex[:8]}",
            compliance_fail_closed_enabled=True,
            warehouse_compliance_enabled=True,
        )
        self.user = django_user_model.objects.create_user(
            email=f"cv-{uuid.uuid4().hex[:8]}@test.com", password="test",
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
            scan_mode=kw.pop("scan_mode", "warehouse_sql"),
            status=ComplianceRunStatus.PENDING,
            warehouse_config=kw.pop("warehouse_config", {"table_fqn": "DB.S.T"}),
            **kw,
        )

    @pytest.mark.integration
    def test_400_for_non_warehouse_mode(self):
        run = self._create_run(scan_mode="file_scan")
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
