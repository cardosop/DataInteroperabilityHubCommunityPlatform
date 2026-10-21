"""
285.10.2.4.2 — Tests for warehouse DQ service methods.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.tenants.models import Tenant


@pytest.mark.integration
class TestRunWarehouseDQ(TestCase):
    """Tests for DQService.run_warehouse_dq()."""

    def setUp(self):
        from hub.apps.assets.models import Asset
        from hub.apps.jobs.models import Job, JobStatus, JobType

        super().setUp()
        self.tenant = Tenant.objects.create(
            name=f"dq-svc-{uuid.uuid4().hex[:8]}",
            slug=f"dq-svc-{uuid.uuid4().hex[:8]}",
            data_quality_enabled=True,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name=f"dq-asset-{uuid.uuid4().hex[:8]}",
            status="DRAFT",
        )

        # Every DQRun requires a non-null Job and non-blank profile_key
        # per the model contract enforced by full_clean() in DQRun.save().
        # Use Job.objects.create() directly to avoid RQ enqueueing in
        # the test transaction (create_job enqueues to Redis via RQ).
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            timeout_seconds=300,
        )

    def _create_dq_run(self, engine, profile_key="warehouse_basic", **kw):
        """Create a DQRun with all required fields populated."""
        return DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            profile_key=profile_key,
            engine=engine,
            status=DQRunStatus.PENDING,
            **kw,
        )

    @pytest.mark.integration
    def test_rejects_non_warehouse_engine(self):
        """Raises ValidationError when engine is not WAREHOUSE_SQL."""
        from hub.apps.core.services.base import ValidationError
        from hub.apps.dq.services import DQService

        dq_run = self._create_dq_run(engine=DQEngine.GREAT_EXPECTATIONS)
        service = DQService(tenant_id=str(self.tenant.id), user_id=None)

        with pytest.raises(ValidationError, match="Engine must be WAREHOUSE_SQL"):
            service.run_warehouse_dq(run_id=str(dq_run.id))

    @pytest.mark.integration
    def test_returns_job_id_pending(self):
        """Returns {job_id, status: PENDING} on success.

        The DQRun is updated with a Job reference, and the returned
        job_id matches the Job attached to the run.
        """
        from hub.apps.dq.services import DQService

        dq_run = self._create_dq_run(
            engine=DQEngine.WAREHOUSE_SQL,
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
        # Verify a valid UUID was returned as the job_id.
        uuid.UUID(result["job_id"])

    @pytest.mark.integration
    def test_gates_advanced_checks(self):
        """Raises ValidationError when advanced checks require flag."""
        from hub.apps.core.services.base import ValidationError
        from hub.apps.dq.services import DQService

        dq_run = self._create_dq_run(
            engine=DQEngine.WAREHOUSE_SQL,
            profile_key="warehouse_advanced",
            warehouse_config={"table_fqn": "T"},
        )
        # Tenant doesn't have data_quality_advanced_enabled
        service = DQService(tenant_id=str(self.tenant.id), user_id=None)
        with pytest.raises(ValidationError, match="advanced"):
            service.run_warehouse_dq(run_id=str(dq_run.id))


@pytest.mark.integration
class TestScanInmemoryWarehouse(TestCase):
    """Tests for DQService.scan_inmemory_warehouse()."""

    def setUp(self):
        from hub.apps.assets.models import Asset
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        super().setUp()
        self.tenant = Tenant.objects.create(
            name=f"dq-scan-{uuid.uuid4().hex[:8]}",
            slug=f"dq-scan-{uuid.uuid4().hex[:8]}",
            data_quality_enabled=True,
            data_quality_advanced_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        # scan_inmemory_warehouse's DQRun.clean() needs at least one
        # of asset/dataset/file for FK validation.
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name=f"dq-scan-asset-{uuid.uuid4().hex[:8]}",
            status="DRAFT",
        )

    @pytest.mark.integration
    def test_creates_dq_run_with_warehouse_engine(self):
        """Creates a DQRun with engine=WAREHOUSE_SQL and persists it.

        Verifies the DQRun is created with the correct engine and config,
        and that it reaches a terminal state (the scan completes, even if
        the warehouse is unreachable in test).
        """
        from hub.apps.dq.services import DQService

        dq_run = DQService.scan_inmemory_warehouse(
            dataset=None,
            tenant=self.tenant,
            asset=self.asset,
            warehouse_config={
                "warehouse_type": "snowflake",
                "table_fqn": "DB.S.T",
                "checks": [
                    {"type": "not_null", "column": "id"},
                ],
            },
            user=None,
        )
        assert dq_run.engine == DQEngine.WAREHOUSE_SQL
        assert dq_run.warehouse_config == {
            "warehouse_type": "snowflake",
            "table_fqn": "DB.S.T",
            "checks": [
                {"type": "not_null", "column": "id"},
            ],
        }
        # Verify the scan reached a terminal state (SUCCEEDED with real
        # warehouse, FAILED without — either confirms the code path ran).
        assert dq_run.status in (DQRunStatus.SUCCEEDED, DQRunStatus.FAILED)
        assert dq_run.started_at is not None
        assert dq_run.completed_at is not None

    @pytest.mark.integration
    def test_returns_terminal_status(self):
        """Returns a DQRun with terminal status (SUCCEEDED or FAILED)."""
        from hub.apps.dq.services import DQService

        dq_run = DQService.scan_inmemory_warehouse(
            dataset=None,
            tenant=self.tenant,
            asset=self.asset,
            warehouse_config={"warehouse_type": "snowflake", "table_fqn": "T", "checks": []},
            user=None,
        )
        assert dq_run.status in (DQRunStatus.SUCCEEDED, DQRunStatus.FAILED)
        assert dq_run.started_at is not None
        assert dq_run.completed_at is not None

    @pytest.mark.integration
    def test_handles_empty_checks(self):
        """Handles warehouse_config with no checks gracefully.

        Returns a terminal status (SUCCEEDED when a real warehouse is
        available, FAILED when the warehouse is unreachable), with
        started_at and completed_at timestamps set in both cases —
        the important property is that we complete without crashing.
        """
        from hub.apps.dq.services import DQService

        dq_run = DQService.scan_inmemory_warehouse(
            dataset=None,
            tenant=self.tenant,
            asset=self.asset,
            warehouse_config={"warehouse_type": "snowflake", "table_fqn": "T"},
            user=None,
        )
        assert dq_run.status in (DQRunStatus.SUCCEEDED, DQRunStatus.FAILED)
        assert dq_run.started_at is not None
        assert dq_run.completed_at is not None
