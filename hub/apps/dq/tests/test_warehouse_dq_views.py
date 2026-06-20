"""
285.10.2.4.3 — Tests for warehouse DQ view endpoint.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model as _get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.datasets.models import Dataset
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = _get_user_model()

WAREHOUSE_RUN_URL = "/api/v1/dq/runs/warehouse-run/"


@pytest.mark.django_db
@pytest.mark.integration
class TestExecuteWarehouseEndpoint:
    """Tests for POST /api/v1/dq/warehouse-run/ (Phase 285.10)."""

    @pytest.fixture(autouse=True)
    def setup(self, django_user_model):
        from hub.apps.assets.models import Asset
        from hub.apps.files.models import File, FileStatus
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        self.tenant = Tenant.objects.create(
            name=f"vw-{uuid.uuid4().hex[:8]}",
            slug=f"vw-{uuid.uuid4().hex[:8]}",
            data_quality_enabled=True,
            warehouse_dq_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = django_user_model.objects.create_user(
            email=f"vw-{uuid.uuid4().hex[:8]}@test.com",
            password="test",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"vw-{uuid.uuid4().hex[:8]}",
            name="VW Asset",
            status="DRAFT",
            created_by=self.user,
        )
        # Minimal file for Dataset FK
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/{file_id}/test.csv",
            created_by=self.user,
        )
        # warehouse-run endpoint requires a dataset_id.
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            row_count=100,
            status="ACTIVE",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _valid_payload(self, **overrides):
        """Minimal valid payload for warehouse-run."""
        payload = {
            "dataset_id": str(self.dataset.id),
            "warehouse_config": {
                "warehouse_type": "snowflake",
                "table_fqn": "DB.S.T",
            },
        }
        payload.update(overrides)
        return payload

    @pytest.mark.integration
    def test_returns_400_when_missing_dataset_id(self):
        """Returns 400 when dataset_id is not provided."""
        payload = self._valid_payload()
        del payload["dataset_id"]
        resp = self.client.post(WAREHOUSE_RUN_URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.integration
    def test_returns_400_when_missing_warehouse_config(self):
        """Returns 400 when warehouse_config is not provided."""
        payload = self._valid_payload()
        del payload["warehouse_config"]
        resp = self.client.post(WAREHOUSE_RUN_URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.integration
    def test_returns_403_when_flag_disabled(self):
        """Returns 403 with ``WAREHOUSE_DQ_DISABLED`` when warehouse_dq_enabled is False."""
        self.tenant.warehouse_dq_enabled = False
        self.tenant.save()
        resp = self.client.post(
            WAREHOUSE_RUN_URL, self._valid_payload(), format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        payload = resp.json()
        assert payload.get("error") == "WAREHOUSE_DQ_DISABLED"

    @pytest.mark.integration
    def test_returns_401_for_unauthenticated(self):
        """Returns 401 when not authenticated."""
        client = APIClient()
        resp = client.post(
            WAREHOUSE_RUN_URL, self._valid_payload(), format="json"
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
