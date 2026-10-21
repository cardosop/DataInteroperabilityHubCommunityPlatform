"""Phase 6 (openspec wire-databricks-dlt-movement task 6.11) — the
guard-bypass ONLY-in-pipeline pins at the round-trip level (design D4,
the spec's "The guard bypass is pipeline-scoped only" scenario).

The 6.5 suite pins the scope mechanics in units; these pins hold the
contract through the REAL pipeline execution: the guard is bypassed
ONLY on the executor's thread INSIDE the real dlt run, and everywhere
else — including a concurrent thread and every exit path — the default
stays blocking. NO MOCKS: the real executor + scope + ReadOnlyGuard.
"""

from __future__ import annotations

import threading
import uuid

import pytest

from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.data_movement.pipeline_scope import (
    GuardScopeError,
    MovementPipelineExecutor,
    is_guard_bypassed,
    pipeline_guard_scope,
)
from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

pytestmark = pytest.mark.django_db(transaction=True)

_WRITE_SQL = "INSERT INTO staging.t VALUES (1)"


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"guard-rt-{uid}",
        slug=f"guard-rt-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        data_movement_enabled=True,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


class TestGuardBypassRoundTrip:
    def test_the_default_stays_blocking_at_every_boundary(self):
        assert is_guard_bypassed() is False
        with pytest.raises(ValueError, match="INSERT"):
            ReadOnlyGuard.check(_WRITE_SQL)

    def test_a_forged_token_is_refused(self):
        with pytest.raises(GuardScopeError), pipeline_guard_scope(object()):
            pass
        assert is_guard_bypassed() is False

    def test_nesting_is_refused(self):
        tenant = _mk_tenant()
        executor = MovementPipelineExecutor(tenant=tenant)

        def _attempt_nesting():
            with pipeline_guard_scope(executor._token), pipeline_guard_scope(executor._token):
                pass

        with pytest.raises(GuardScopeError, match="nesting"):
            _attempt_nesting()
        assert is_guard_bypassed() is False

    def test_the_scope_is_thread_local(self):
        tenant = _mk_tenant()
        executor = MovementPipelineExecutor(tenant=tenant)
        inside: dict = {}
        outside: dict = {}
        with pipeline_guard_scope(executor._token):
            inside["bypassed"] = is_guard_bypassed()

            def probe():
                outside["bypassed"] = is_guard_bypassed()
                try:
                    ReadOnlyGuard.check(_WRITE_SQL)
                    outside["write_allowed"] = True
                except ValueError:
                    outside["write_allowed"] = False

            thread = threading.Thread(target=probe)
            thread.start()
            thread.join()

        assert inside["bypassed"] is True
        assert outside["bypassed"] is False, (
            "a scope entered on one thread never leaks into another"
        )
        assert outside["write_allowed"] is False, (
            "the write guard stays blocking on the other thread"
        )
        assert is_guard_bypassed() is False

    def test_every_exit_restores_the_guard(self):
        tenant = _mk_tenant()
        executor = MovementPipelineExecutor(tenant=tenant)
        with pytest.raises(RuntimeError, match="boom"), pipeline_guard_scope(executor._token):
            raise RuntimeError("boom")
        assert is_guard_bypassed() is False
        with pytest.raises(ValueError, match="INSERT"):
            ReadOnlyGuard.check(_WRITE_SQL)

    def test_the_real_pipeline_run_is_bypassed_inside_only(self):
        """The round-trip level: the REAL entrypoint run executes inside
        the scope — the recording run observes the bypass ON while
        running, and the guard is restored when the run ends."""
        tenant = _mk_tenant()
        executor = MovementPipelineExecutor(tenant=tenant)
        observations: dict = {}

        def work():
            observations["inside"] = is_guard_bypassed()
            ReadOnlyGuard.check(_WRITE_SQL)  # must pass inside the scope
            return "done"

        result = executor.execute(work)
        assert result == "done"
        assert observations["inside"] is True
        assert is_guard_bypassed() is False
        with pytest.raises(ValueError, match="INSERT"):
            ReadOnlyGuard.check(_WRITE_SQL)

    def test_a_uc_target_without_a_credential_still_refuses_to_construct(self):
        """The fail-closed construction stays the entry gate — a UC
        staging target without a scoped credential never reaches the
        scope."""
        from hub.data_movement.pipeline_scope import CredentialNotResolvedError
        from hub.data_movement.staging import StagingTarget

        tenant = _mk_tenant()
        target = StagingTarget(
            catalog="meshant", schema="staging", volume_name="_dlt_staging_load_volume"
        )
        with pytest.raises(CredentialNotResolvedError):
            MovementPipelineExecutor(tenant=tenant, staging_target=target)
