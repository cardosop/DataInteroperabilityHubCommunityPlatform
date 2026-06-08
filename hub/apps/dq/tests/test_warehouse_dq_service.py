"""
285.10.2.4.2 — Tests for warehouse DQ service methods.
"""
import pytest

import uuid

from django.test import TestCase

from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.tenants.models import Tenant


@pytest.mark.integration
class TestRunWarehouseDQ(TestCase):
    """Tests for DQService.run_warehouse_dq()."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            name=f"dq-svc-{uuid.uuid4().hex[:8]}",
            slug=f"dq-svc-{uuid.uuid4().hex[:8]}",
            data_quality_enabled=True,
        )
        from hub.apps.assets.models import Asset
        cls.asset = Asset.objects.create(
            tenant=cls.tenant,
            name=f"dq-asset-{uuid.uuid4().hex[:8]}",
            status="DRAFT",
        )

    @pytest.mark.integration
    def test_rejects_non_warehouse_engine(self):
        """Raises ValidationError when engine is not WAREHOUSE_SQL."""
        from hub.apps.dq.services import DQService

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
            asset=self.asset,
        )
        service = DQService(tenant_id=str(self.tenant.id), user_id=None)

        with pytest.raises(Exception):
            service.run_warehouse_dq(run_id=str(dq_run.id))

    @pytest.mark.integration
    def test_returns_job_id_pending(self):
        """Returns {job_id, status: PENDING} on success."""
        from hub.apps.dq.services import DQService
        from hub.apps.jobs.models import JobType

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            engine=DQEngine.WAREHOUSE_SQL,
            status=DQRunStatus.PENDING,
            profile_key="warehouse_basic",
            warehouse_config={
                "warehouse_type": "snowflake",
                "table_fqn": "DB.S.T",
            },
        )
        service = DQService(tenant_id=str(self.tenant.id), user_id=None)
        result = service.run_warehouse_dq(run_id=str(dq_run.id))

        assert "job_id" in result
        assert result["status"] == "PENDING"

    @pytest.mark.integration
    def test_gates_advanced_checks(self):
        """Raises ValidationError when advanced checks require flag."""
        from hub.apps.dq.services import DQService

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            engine=DQEngine.WAREHOUSE_SQL,
            status=DQRunStatus.PENDING,
            profile_key="warehouse_advanced",
            warehouse_config={"table_fqn": "T"},
        )
        # Tenant doesn't have data_quality_advanced_enabled
        service = DQService(tenant_id=str(self.tenant.id), user_id=None)
        with pytest.raises(Exception, match="advanced"):
            service.run_warehouse_dq(run_id=str(dq_run.id))


@pytest.mark.integration
class TestScanInmemoryWarehouse(TestCase):
    """Tests for DQService.scan_inmemory_warehouse()."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            name=f"dq-scan-{uuid.uuid4().hex[:8]}",
            slug=f"dq-scan-{uuid.uuid4().hex[:8]}",
        )

    @pytest.mark.integration
    def test_creates_dq_run_with_warehouse_engine(self):
        """Creates a DQRun with engine=WAREHOUSE_SQL."""
        from hub.apps.dq.services import DQService

        service = DQService(tenant_id=str(self.tenant.id), user_id=None)
        dq_run = service.scan_inmemory_warehouse(
            warehouse_config={"table_fqn": "DB.S.T", "checks": [
                {"type": "not_null", "column": "id"},
            ]},
            tenant_id=str(self.tenant.id),
        )
        assert dq_run.engine == DQEngine.WAREHOUSE_SQL
        assert dq_run.warehouse_config == {"table_fqn": "DB.S.T", "checks": [
            {"type": "not_null", "column": "id"},
        ]}

    @pytest.mark.integration
    def test_returns_terminal_status(self):
        """Returns a DQRun with terminal status (SUCCEEDED or FAILED)."""
        from hub.apps.dq.services import DQService

        service = DQService(tenant_id=str(self.tenant.id), user_id=None)
        dq_run = service.scan_inmemory_warehouse(
            warehouse_config={"table_fqn": "T", "checks": []},
            tenant_id=str(self.tenant.id),
        )
        assert dq_run.status in (DQRunStatus.SUCCEEDED, DQRunStatus.FAILED)
        assert dq_run.started_at is not None
        assert dq_run.completed_at is not None

    @pytest.mark.integration
    def test_handles_empty_checks(self):
        """Handles warehouse_config with no checks gracefully."""
        from hub.apps.dq.services import DQService

        service = DQService(tenant_id=str(self.tenant.id), user_id=None)
        dq_run = service.scan_inmemory_warehouse(
            warehouse_config={"table_fqn": "T"},
            tenant_id=str(self.tenant.id),
        )
        assert dq_run.status == DQRunStatus.SUCCEEDED
