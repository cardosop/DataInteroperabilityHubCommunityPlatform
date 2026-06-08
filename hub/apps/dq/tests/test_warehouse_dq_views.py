"""
285.10.2.4.3 — Tests for warehouse DQ view endpoint.
"""
import pytest

import uuid

from rest_framework.test import APIClient

from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

from django.contrib.auth import get_user_model as _get_user_model
User = _get_user_model()


@pytest.mark.django_db
@pytest.mark.integration
class TestExecuteWarehouseEndpoint:
    """Tests for POST /api/v1/dq/runs/{id}/execute-warehouse/."""

    @pytest.fixture(autouse=True)
    def setup(self, django_user_model):
        self.tenant = Tenant.objects.create(
            name=f"vw-{uuid.uuid4().hex[:8]}",
            slug=f"vw-{uuid.uuid4().hex[:8]}",
            data_quality_enabled=True,
            warehouse_dq_enabled=True,
        )
        self.user = django_user_model.objects.create_user(
            email=f"vw-{uuid.uuid4().hex[:8]}@test.com",
            password="test",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Minimal asset for DQRun.clean() FK validation
        from hub.apps.assets.models import Asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"vw-{uuid.uuid4().hex[:8]}",
            name="VW Asset",
            status="DRAFT",
            created_by=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _create_run(self, engine=DQEngine.WAREHOUSE_SQL, **kw):
        return DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            engine=engine,
            status=DQRunStatus.PENDING,
            warehouse_config=kw.pop("warehouse_config", {"table_fqn": "DB.S.T"}),
            **kw,
        )

    @pytest.mark.integration
    def test_returns_400_for_non_warehouse_engine(self):
        """Returns 400 when engine is not WAREHOUSE_SQL."""
        run = self._create_run(engine=DQEngine.GREAT_EXPECTATIONS)
        resp = self.client.post(f"/api/v1/dq/runs/{run.id}/execute-warehouse/")
        assert resp.status_code == 400

    @pytest.mark.integration
    def test_returns_400_for_missing_warehouse_config(self):
        """Returns 400 when warehouse_config is not set."""
        run = self._create_run(warehouse_config=None)
        resp = self.client.post(f"/api/v1/dq/runs/{run.id}/execute-warehouse/")
        assert resp.status_code == 400

    @pytest.mark.integration
    def test_returns_403_when_flag_disabled(self):
        """Returns 403 when warehouse_dq_enabled is False."""
        self.tenant.warehouse_dq_enabled = False
        self.tenant.save()
        run = self._create_run()
        resp = self.client.post(f"/api/v1/dq/runs/{run.id}/execute-warehouse/")
        assert resp.status_code == 403

    @pytest.mark.integration
    def test_returns_401_for_unauthenticated(self):
        """Returns 401 when not authenticated."""
        client = APIClient()
        run = self._create_run()
        resp = client.post(f"/api/v1/dq/runs/{run.id}/execute-warehouse/")
        assert resp.status_code == 401
