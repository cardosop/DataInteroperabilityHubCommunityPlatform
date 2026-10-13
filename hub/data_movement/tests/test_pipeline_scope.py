"""TDD pins for the pipeline execution context (openspec
wire-databricks-dlt-movement task 6.5): the scoped write credential and the
read-only-guard bypass that exists ONLY inside the pipeline executor.

No mocks: the REAL ``ScopedWriteCredential`` + ``MovementPipelineExecutor`` +
``pipeline_guard_scope`` + the REAL ``ReadOnlyGuard``. The adversarial
contract: the bypass cannot be entered without an executor-minted token,
nesting is refused, the scope is thread-local, exit restores the guard,
and a scoped credential refuses any target outside its bound scope.
"""

import threading

import pytest

pytestmark = pytest.mark.django_db(transaction=True)

TARGET = "meshant.staging._dlt_staging_load_volume"


@pytest.fixture
def tenant():
    from tests.factories import TenantFactory

    return TenantFactory.create_tenant()


class TestScopedWriteCredential:
    def _credential(self, **kwargs):
        from hub.data_movement.pipeline_scope import ScopedWriteCredential

        kind = kwargs.pop("kind", "PAT")
        material = kwargs.pop("material", "dapi-staging-token")
        target = kwargs.pop("target", TARGET)
        return ScopedWriteCredential(kind=kind, material=material, target=target, **kwargs)

    def test_a_pat_credential_scoped_to_a_target_constructs(self):
        cred = self._credential()
        assert cred.kind == "PAT"
        assert cred.target == TARGET

    def test_an_m2m_credential_constructs(self):
        from hub.data_movement.pipeline_scope import ScopedWriteCredential

        cred = ScopedWriteCredential(kind="M2M", material="client-id-material", target=TARGET)
        assert cred.kind == "M2M"

    def test_an_unknown_kind_is_refused(self):
        from hub.data_movement.pipeline_scope import ScopedCredentialError

        with pytest.raises(ScopedCredentialError):
            self._credential(kind="JWT")

    def test_an_empty_material_is_refused(self):
        from hub.data_movement.pipeline_scope import ScopedCredentialError

        with pytest.raises(ScopedCredentialError):
            self._credential(material="   ")

    def test_a_malformed_target_is_refused(self):
        from hub.data_movement.pipeline_scope import ScopedCredentialError

        with pytest.raises(ScopedCredentialError):
            self._credential(target="meshant.staging")

    def test_the_credential_accepts_use_for_its_bound_target(self):
        self._credential().assert_scoped_to(TARGET)

    def test_the_credential_refuses_any_other_target(self):
        from hub.data_movement.pipeline_scope import ScopedCredentialError

        with pytest.raises(ScopedCredentialError):
            self._credential().assert_scoped_to("meshant.other_schema._dlt_staging_load_volume")


class TestPipelineGuardScope:
    def _token(self, tenant):
        """A token minted by a REAL executor instance (the only legitimate
        way to obtain one through the public API)."""
        from hub.data_movement.pipeline_scope import MovementPipelineExecutor

        executor = MovementPipelineExecutor(tenant=tenant)
        return executor._token

    def test_write_sql_is_refused_outside_the_scope(self):
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        with pytest.raises(ValueError, match="not allowed"):
            ReadOnlyGuard.check("INSERT INTO staging.t VALUES (1)")

    def test_a_scope_without_a_token_is_refused(self):
        from hub.data_movement.pipeline_scope import GuardScopeError, pipeline_guard_scope

        with pytest.raises(GuardScopeError), pipeline_guard_scope(None):
            pass

    def test_a_forged_token_is_refused(self):
        from hub.data_movement.pipeline_scope import GuardScopeError, pipeline_guard_scope

        with pytest.raises(GuardScopeError), pipeline_guard_scope(object()):
            pass

    def test_the_guard_bypasses_write_sql_only_inside_the_scope(self, tenant):
        from hub.data_movement.pipeline_scope import pipeline_guard_scope
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        with pipeline_guard_scope(self._token(tenant)):
            ReadOnlyGuard.check("INSERT INTO staging.t VALUES (1)")

        with pytest.raises(ValueError, match="not allowed"):
            ReadOnlyGuard.check("INSERT INTO staging.t VALUES (1)")

    def test_nesting_two_scopes_is_refused(self, tenant):
        from hub.data_movement.pipeline_scope import GuardScopeError, pipeline_guard_scope

        token = self._token(tenant)
        with (
            pipeline_guard_scope(token),
            pytest.raises(GuardScopeError),
            pipeline_guard_scope(token),
        ):
            pass

    def test_an_exception_inside_the_scope_still_restores_the_guard(self, tenant):
        from hub.data_movement.pipeline_scope import pipeline_guard_scope
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        with (
            pytest.raises(RuntimeError, match="boom"),
            pipeline_guard_scope(self._token(tenant)),
        ):
            raise RuntimeError("boom")

        with pytest.raises(ValueError, match="not allowed"):
            ReadOnlyGuard.check("DELETE FROM staging.t")

    def test_the_scope_is_thread_local(self, tenant):
        from hub.data_movement.pipeline_scope import pipeline_guard_scope
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        other_thread_result: list[str] = []

        def other_thread():
            try:
                ReadOnlyGuard.check("UPDATE staging.t SET x = 1")
            except ValueError:
                other_thread_result.append("blocked")
            else:
                other_thread_result.append("bypassed")

        with pipeline_guard_scope(self._token(tenant)):
            thread = threading.Thread(target=other_thread)
            thread.start()
            thread.join()

        assert other_thread_result == ["blocked"], (
            "a scope entered on this thread must never leak into another thread"
        )


class TestMovementPipelineExecutor:
    def _executor(self, tenant=None, **kwargs):
        from hub.data_movement.pipeline_scope import MovementPipelineExecutor

        return MovementPipelineExecutor(tenant=tenant, **kwargs)

    def _target(self, **kwargs):
        from hub.data_movement.staging import StagingTarget

        return StagingTarget(
            catalog="meshant",
            schema="staging",
            volume_name="_dlt_staging_load_volume",
            **kwargs,
        )

    def test_a_uc_target_requires_a_scoped_credential_fail_closed(self, tenant):
        from hub.data_movement.pipeline_scope import CredentialNotResolvedError

        with pytest.raises(CredentialNotResolvedError):
            self._executor(tenant, staging_target=self._target())

    def test_execute_runs_the_work_inside_the_guard_scope(self, tenant):
        from hub.data_movement.pipeline_scope import ScopedWriteCredential
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        seen: list[str] = []
        credential = ScopedWriteCredential(kind="PAT", material="dapi-t", target=TARGET)
        executor = self._executor(tenant, staging_target=self._target(), credential=credential)

        def work():
            ReadOnlyGuard.check("CREATE TABLE staging.t (x INT)")
            seen.append("ran")
            return "result"

        result = executor.execute(work)

        assert result == "result"
        assert seen == ["ran"]

    def test_execute_refuses_a_credential_scoped_elsewhere_before_any_work(self, tenant):
        from hub.data_movement.pipeline_scope import ScopedCredentialError, ScopedWriteCredential

        called: list[str] = []
        credential = ScopedWriteCredential(
            kind="PAT", material="dapi-t", target="other.catalog.volume"
        )
        executor = self._executor(tenant, staging_target=self._target(), credential=credential)

        with pytest.raises(ScopedCredentialError):
            executor.execute(lambda: called.append("ran"))

        assert called == [], "the scope check must fail BEFORE the work runs"

    def test_the_guard_is_restored_after_execute(self, tenant):
        from hub.data_movement.pipeline_scope import ScopedWriteCredential
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        credential = ScopedWriteCredential(kind="PAT", material="dapi-t", target=TARGET)
        executor = self._executor(tenant, staging_target=self._target(), credential=credential)
        executor.execute(lambda: None)

        with pytest.raises(ValueError, match="not allowed"):
            ReadOnlyGuard.check("TRUNCATE TABLE staging.t")

    def test_a_non_callable_work_is_refused(self, tenant):
        from hub.data_movement.pipeline_scope import ScopedWriteCredential

        credential = ScopedWriteCredential(kind="PAT", material="dapi-t", target=TARGET)
        executor = self._executor(tenant, staging_target=self._target(), credential=credential)

        with pytest.raises(TypeError):
            executor.execute("not-callable")
