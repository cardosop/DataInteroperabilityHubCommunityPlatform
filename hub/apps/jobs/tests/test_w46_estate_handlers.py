"""W4.6 (openspec oss-release-remediation, G1) — TDD pins for the
estate-job handler seam (the jobs dispatch never imports estate code).

No mocks: the REAL registry, the REAL dispatcher
(``tasks_base._execute_job_logic``), real Postgres rows. The dispatch
pin runs the REAL estate handler through the registry for a tenant with
NO active workspaces — the handler's own short-circuit returns the
clean result dict with ZERO network calls (the honest end-to-end
proof). The refusal pin proves an unregistered estate type fails
classified (``JobExecutionError``), never a silent no-op.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model

from hub.apps.jobs.estate_handlers import (
    get_estate_job_handler,
    register_estate_job_handler,
    registered_estate_job_types,
)
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.tasks_base import JobExecutionError, _execute_job_logic
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


def _make_tenant():
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(name=f"est-{uid}", slug=f"est-{uid}")


def _make_job(tenant, job_type):
    return Job.objects.create(
        tenant=tenant,
        type=job_type,
        resource_type="DATABRICKS",
        resource_id=uuid.uuid4(),
        status=JobStatus.PENDING,
    )


class TestEstateHandlerRegistry:
    def test_ready_wiring_registers_all_three_handlers(self):
        expected = {
            "DATABRICKS_UC_METADATA_SYNC",
            "DATABRICKS_COST_SYNC",
            "DATABRICKS_UC_CHANGE_REAPER",
        }
        assert expected <= set(registered_estate_job_types())
        for job_type in expected:
            handler = get_estate_job_handler(job_type)
            assert handler is not None, job_type
            assert handler.__module__.startswith(
                "hub.apps.databricks_admin."
            ), "the registered handler must be the estate implementation"

    def test_unknown_type_is_none(self):
        assert get_estate_job_handler("DATABRICKS_UNKNOWN") is None

    def test_registration_overwrites_idempotently(self):
        from hub.apps.jobs.estate_handlers import _registered_handlers

        def stand_in(job_obj):
            return {"ok": True}

        try:
            register_estate_job_handler("DATABRICKS_STAND_IN", stand_in)
            register_estate_job_handler("DATABRICKS_STAND_IN", stand_in)
            assert get_estate_job_handler("DATABRICKS_STAND_IN") is stand_in
        finally:
            # Module-global registries persist across a batch — the
            # stand-in must never leak into later tests.
            _registered_handlers.pop("DATABRICKS_STAND_IN", None)


class TestEstateJobDispatch:
    def test_real_handler_dispatches_through_the_seam(self):
        """A tenant with no ACTIVE workspaces: the REAL handler runs and
        returns its clean zero-workspace result (no network calls)."""
        tenant = _make_tenant()
        job = _make_job(tenant, JobType.DATABRICKS_UC_METADATA_SYNC)
        result = _execute_job_logic(job, str(JobType.DATABRICKS_UC_METADATA_SYNC.value))
        assert result["workspaces_synced"] == 0
        assert result["workspaces_skipped"] == []
        assert result["counters"] == {
            "created": 0,
            "updated": 0,
            "unchanged": 0,
            "deleted": 0,
        }

    def test_unregistered_estate_type_refuses_classified(self):
        """The REAL dispatcher branch refuses classified when an estate
        type has no registered handler (evicted + restored in finally —
        the module-global registry must be honest for later tests)."""
        from hub.apps.jobs.estate_handlers import _registered_handlers

        tenant = _make_tenant()
        job = _make_job(tenant, JobType.DATABRICKS_UC_METADATA_SYNC)
        job_type = JobType.DATABRICKS_UC_METADATA_SYNC.value
        real_handler = _registered_handlers.get(job_type)
        assert real_handler is not None  # the ready()-wiring pin's guard
        try:
            _registered_handlers.pop(job_type)
            with pytest.raises(
                JobExecutionError, match="no estate job handler registered"
            ):
                _execute_job_logic(job, job_type)
        finally:
            _registered_handlers[job_type] = real_handler
