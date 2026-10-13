"""TDD pins for the stuck-EXECUTING reaper (openspec add-databricks-uc-write
task 2.5) — D4's rollback policy.

The reaper resolves ``UCChangeRequest`` rows stuck in EXECUTING beyond
the lease: a stuck CREATE-type request is rolled back BEST-EFFORT (the
compensating DROP deletes exactly what the request created — through the
PRODUCTION client against a REAL local HTTP server, with the 2.4
denylist BYPASSED as the sanctioned policy carve-out) and lands in
ROLLED_BACK even when the compensating delete fails; a stuck destructive
request (DROP) lands in FAILED with ZERO compensating DDL — destructive
DDL is NEVER auto-rolled-back (recreating dropped data is forbidden).
Identity failures fail the request too (a stuck request never lingers).

The RQ surface mirrors the 1.5 sync pattern: one
``JobType.DATABRICKS_UC_CHANGE_REAPER`` job per tenant (admin-DB
discovery in the management command), the handler reaps under
``tenant_context``, and the helm CronJob runs it hourly.

No mocks: real Postgres request rows, real local HTTP for every
network-observable assertion, real audit-free D12 identity resolution.
"""

import json
import uuid
from datetime import timedelta

import pytest
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from hub.apps.databricks_admin.models import (
    UCChangeAction,
    UCChangeRequest,
    UCChangeRequestStatus,
    UCObjectType,
)
from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import (
    _local_client_factory,
    _make_approval,
    _make_credential,
    _make_workspace,
)
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _make_request(
    tenant,
    workspace,
    user,
    *,
    change_type,
    securable_type,
    identifiers,
    status=UCChangeRequestStatus.EXECUTING,
    executing_at="stale",
    name="main",
):
    """A real UCChangeRequest row (the 2.2 model) in EXECUTING state.
    ``executing_at``: "stale" (beyond the lease), "fresh" (now), or None
    (unmarked — abandoned)."""
    if executing_at == "stale":
        executing_at_value = timezone.now() - timedelta(hours=2)
    elif executing_at == "fresh":
        executing_at_value = timezone.now()
    else:
        executing_at_value = None
    return UCChangeRequest.objects.create(
        tenant=tenant,
        workspace=workspace,
        requested_by=user,
        change_type=change_type,
        securable_type=securable_type,
        full_name=".".join(identifiers) if identifiers else name,
        definition={"identifiers": list(identifiers), "options": {}},
        status=status,
        executing_at=executing_at_value,
    )


class _ReaperSetupMixin:
    def _setup(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.admin = _make_user(
            self.tenant, f"ucs-reap-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.workspace = _make_workspace(self.tenant)
        self.approval = _make_approval(self.tenant, self.admin)
        _make_credential(self.workspace, self.approval)

        import hub.apps.databricks_admin.uc_change_reaper as reaper_module

        self._original_factory = reaper_module._build_uc_client
        self.addCleanup(setattr, reaper_module, "_build_uc_client", self._original_factory)

    def _patch_factory(self, port):
        import hub.apps.databricks_admin.uc_change_reaper as reaper_module

        reaper_module._build_uc_client = _local_client_factory(port)

    def _start_local_server(self):
        """A real threaded local HTTP server (plain helper — pytest
        fixtures cannot serve TestCase methods, the 0.8 lesson).

        The scripted queue models the REAL M2M flow: the client's FIRST
        request is the OAuth client-credentials exchange (the workspace
        M2M credential — the D12 background identity), so entry 0 is the
        token response and entry 1 serves the compensating DELETE."""
        import http.server
        import threading

        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = [
            json.dumps({"access_token": "tok-reaper", "expires_in": 3600}),
            "{}",
        ]
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        return port


class TestReaperLeaseResolution(TestCase, _ReaperSetupMixin):
    """The lease decides who is stuck — status AND the executing_at
    anchor, with the unmarked-EXECUTING row treated as abandoned."""

    def setUp(self):
        self._setup()

    def test_stale_executing_request_is_stuck(self):
        from hub.apps.databricks_admin.uc_change_reaper import find_stuck_requests

        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
        )
        assert list(find_stuck_requests(self.tenant)) == [request]

    def test_fresh_executing_request_is_not_stuck(self):
        from hub.apps.databricks_admin.uc_change_reaper import find_stuck_requests

        _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
            executing_at="fresh",
        )
        assert list(find_stuck_requests(self.tenant)) == []

    def test_unmarked_executing_request_is_treated_as_stuck(self):
        # An EXECUTING row with NO executing_at is abandoned — fail-closed
        # on the lease (it can never prove freshness).
        from hub.apps.databricks_admin.uc_change_reaper import find_stuck_requests

        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
            executing_at=None,
        )
        assert list(find_stuck_requests(self.tenant)) == [request]

    def test_non_executing_requests_are_ignored(self):
        from hub.apps.databricks_admin.uc_change_reaper import find_stuck_requests

        _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
            status=UCChangeRequestStatus.APPROVED,
        )
        assert list(find_stuck_requests(self.tenant)) == []

    def test_fresh_request_is_refused_by_the_resolver(self):
        # Re-entrancy: the resolver re-checks the lease — a request that
        # turned fresh (another worker already claimed it) is left alone.
        from hub.apps.databricks_admin.uc_change_reaper import resolve_stuck_request

        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
            executing_at="fresh",
        )
        outcome = resolve_stuck_request(request)
        assert outcome["skipped"] is True
        request.refresh_from_db()
        assert request.status == UCChangeRequestStatus.EXECUTING


class TestReaperRollbackPolicy(TestCase, _ReaperSetupMixin):
    """CREATE rolls back best-effort; destructive DDL is never rolled back."""

    def setUp(self):
        self._setup()

    def test_stuck_create_compensates_with_the_delete_and_lands_rolled_back(self):
        port = self._start_local_server()

        from hub.apps.databricks_admin.uc_change_reaper import resolve_stuck_request

        # The rollback policy is the sanctioned denylist carve-out: the
        # tenant's destructive-DDL flag is OFF (the default) and the
        # compensating delete STILL executes — the reaper deletes exactly
        # what the request itself created, it is not a user request.
        assert self.tenant.databricks_uc_destructive_ddl_enabled is False

        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
        )
        self._patch_factory(port)

        outcome = resolve_stuck_request(request)
        assert outcome["terminal"] == "ROLLED_BACK", outcome

        request.refresh_from_db()
        assert request.status == UCChangeRequestStatus.ROLLED_BACK
        assert request.rolled_back_at is not None

        # The FIRST request is the OAuth exchange riding the workspace's
        # M2M credential (the D12 background identity).
        exchange = RecordingHandler.requests[0]
        assert exchange["method"] == "POST"
        assert exchange["path"] == "/oidc/v1/token"
        assert "client_id=sync-client" in exchange["body"], (
            "the compensating DDL must run on the workspace M2M credential"
        )

        delete_calls = [r for r in RecordingHandler.requests if r["method"] == "DELETE"]
        assert len(delete_calls) == 1
        assert delete_calls[0]["path"] == "/api/2.1/unity-catalog/tables/main.sales.orders", (
            "the compensating DROP must target exactly what the request created"
        )

    def test_failed_compensating_delete_is_best_effort_still_rolled_back(self):
        port = self._start_local_server()

        # The object never actually existed (the worker died BEFORE the
        # DDL) — the compensating DELETE 404s; the request still resolves.
        # The script queue: exchange OK first, then the DELETE 404s.
        RecordingHandler.script = [200, 404]
        RecordingHandler.json_script = [
            json.dumps({"access_token": "tok-reaper", "expires_in": 3600}),
            json.dumps({"error_code": "NOT_FOUND"}),
        ]

        from hub.apps.databricks_admin.uc_change_reaper import resolve_stuck_request

        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
        )
        self._patch_factory(port)

        outcome = resolve_stuck_request(request)
        assert outcome["terminal"] == "ROLLED_BACK", outcome
        request.refresh_from_db()
        assert request.status == UCChangeRequestStatus.ROLLED_BACK

    def test_stuck_destructive_request_is_failed_never_rolled_back(self):
        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = ["{}"]

        from hub.apps.databricks_admin.uc_change_reaper import resolve_stuck_request

        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.DROP,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
        )
        outcome = resolve_stuck_request(request)
        assert outcome["terminal"] == "FAILED", outcome
        assert "never auto-rolled-back" in outcome["reason"]

        request.refresh_from_db()
        assert request.status == UCChangeRequestStatus.FAILED
        assert "never auto-rolled-back" in request.execution_error
        assert RecordingHandler.requests == [], (
            "a destructive request must fail with ZERO compensating DDL"
        )

    def test_identity_failure_lands_the_request_in_failed(self):
        # The workspace loses its M2M credential (or its approver
        # linkage) — the D12 decision fails closed and the stuck request
        # resolves to FAILED (it must never linger in EXECUTING).
        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = ["{}"]

        from hub.apps.databricks_admin.models import DatabricksCredential
        from hub.apps.databricks_admin.uc_change_reaper import resolve_stuck_request

        DatabricksCredential.objects.filter(workspace=self.workspace).delete()
        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
        )
        outcome = resolve_stuck_request(request)
        assert outcome["terminal"] == "FAILED", outcome
        request.refresh_from_db()
        assert request.status == UCChangeRequestStatus.FAILED
        assert RecordingHandler.requests == []


class TestReaperJobHandler(TestCase, _ReaperSetupMixin):
    """The RQ handler reaps only its own tenant (tenant_context)."""

    def setUp(self):
        self._setup()

    def _job(self, tenant):
        from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType

        return Job.objects.create(
            tenant=tenant,
            type=JobType.DATABRICKS_UC_CHANGE_REAPER,
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            resource_type="TENANT",
            resource_id=tenant.id,
        )

    def test_handler_reaps_the_jobs_tenant_only(self):
        from hub.apps.databricks_admin.uc_change_reaper_jobs import (
            _execute_databricks_uc_change_reaper_job,
        )

        other_tenant = TenantFactory.create_tenant()
        _activate_billing(other_tenant)
        other_admin = _make_user(
            other_tenant, f"ucs-reap-o-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        other_workspace = _make_workspace(other_tenant, name="ws-other")

        mine = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.DROP,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
        )
        sibling = _make_request(
            other_tenant,
            other_workspace,
            other_admin,
            change_type=UCChangeAction.DROP,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "sibling_orders"),
        )

        result = _execute_databricks_uc_change_reaper_job(self._job(self.tenant))
        assert result["reaped"] == 1, result

        mine.refresh_from_db()
        sibling.refresh_from_db()
        assert mine.status == UCChangeRequestStatus.FAILED
        assert sibling.status == UCChangeRequestStatus.EXECUTING, (
            "a sibling tenant's stuck request must never be touched"
        )


class TestReaperJobRegistration:
    """JobType + timeout/retry + dispatch wiring (the 1.5 pattern)."""

    def test_job_type_registered_with_timeout_and_retries(self):
        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import get_job_max_retries, get_job_timeout

        assert JobType.DATABRICKS_UC_CHANGE_REAPER.value == "DATABRICKS_UC_CHANGE_REAPER"
        assert get_job_timeout(JobType.DATABRICKS_UC_CHANGE_REAPER) == 1800
        assert get_job_max_retries(JobType.DATABRICKS_UC_CHANGE_REAPER) == 1

    def test_dispatch_routes_the_reaper_type(self):
        import inspect

        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.tasks_base import _execute_job_logic

        # The dispatch branch resolves the handler (a smoke pin — the
        # full execution is the handler suite's contract).
        source = inspect.getsource(_execute_job_logic)
        assert "DATABRICKS_UC_CHANGE_REAPER" in source
        assert "_execute_databricks_uc_change_reaper_job" in source
        assert JobType.DATABRICKS_UC_CHANGE_REAPER


class TestReaperManagementCommand(TransactionTestCase):
    """The CronJob-facing command: admin-DB discovery + one PENDING RQ
    job per tenant with a stuck request."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.admin = _make_user(
            self.tenant, f"ucs-reap-cmd-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.workspace = _make_workspace(self.tenant)
        _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
        )
        self.tenant_without_stuck = TenantFactory.create_tenant()

    def test_dry_run_reports_tenants_without_creating_jobs(self):
        from django.core.management import call_command

        from hub.apps.jobs.models import Job, JobType

        out = call_command("databricks_uc_change_reaper", "--dry-run")
        assert str(self.tenant.id) in out
        assert str(self.tenant_without_stuck.id) not in out
        assert not Job.objects.filter(
            type=JobType.DATABRICKS_UC_CHANGE_REAPER, tenant_id=self.tenant.id
        ).exists()

    def test_run_creates_one_pending_job_per_tenant(self):
        from django.core.management import call_command
        from django_rq import get_queue

        from hub.apps.jobs.models import Job, JobStatus, JobType

        queue = get_queue("job_default")
        queue.empty()
        call_command("databricks_uc_change_reaper")

        jobs = Job.objects.filter(
            type=JobType.DATABRICKS_UC_CHANGE_REAPER, tenant_id=self.tenant.id
        )
        assert jobs.count() == 1
        job = jobs.get()
        # Race-tolerant row shape (the 1.5 convention — a live RQ worker
        # may process the job between create and assert).
        assert job.status in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED)
        assert job.resource_type == "TENANT"
        assert str(job.resource_id) == str(self.tenant.id)
        queue.empty()


class TestReaperModelContract(TestCase):
    """The lease anchor + the reaper's state-machine hop."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.admin = _make_user(
            self.tenant, f"ucs-reap-m-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.workspace = _make_workspace(self.tenant)

    def test_executing_at_is_nullable_and_unset_by_default(self):
        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
            executing_at=None,
        )
        assert request.executing_at is None

    def test_executing_to_rolled_back_is_allowed_for_the_reaper(self):
        # 2.5 contract evolution: the reaper resolves a stuck CREATE
        # EXECUTING → ROLLED_BACK through the state machine (the single
        # source of truth), never by writing the status directly.
        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
        )
        assert request.transition_to(UCChangeRequestStatus.ROLLED_BACK) is True

    def test_reaper_purpose_is_a_background_purpose(self):
        from hub.apps.databricks_admin.identity import BACKGROUND_PURPOSES

        assert "uc_change_reaper" in BACKGROUND_PURPOSES, (
            "the reaper resolves under the D12 BACKGROUND identity "
            "(workspace M2M credential + approver linkage)"
        )


class TestReaperFailClosedRobustness(TestCase, _ReaperSetupMixin):
    """The reaper must resolve EVERY stuck request — malformed rows land
    FAILED, never crash the sweep, never trigger a compensation we
    cannot justify.

    The 2.2 model persists the enums as CHARFIELDS: rows written by an
    OLDER service version (or a future one — 2.6 adds securables, a
    later phase may add ALTER) carry values today's vocabulary does not
    know. The reaper's job is terminal resolution: unknown values must
    fail the REQUEST, not the reaper.
    """

    def setUp(self):
        self._setup()

    def test_unknown_securable_type_lands_failed_not_a_crash(self):
        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = ["{}"]

        from hub.apps.databricks_admin.uc_change_reaper import resolve_stuck_request

        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
        )
        # The deploy-rollback shape: the row was written while a WIDER
        # vocabulary was live; reads do NOT validate choices, so the
        # reaper sees the unknown value raw (model clean() only runs on
        # save — QuerySet.update bypasses it, exactly like the real row).
        UCChangeRequest.objects.filter(pk=request.pk).update(securable_type="BOGUS_SECURABLE")
        request.refresh_from_db()
        outcome = resolve_stuck_request(request)
        assert outcome["terminal"] == "FAILED", outcome

        request.refresh_from_db()
        assert request.status == UCChangeRequestStatus.FAILED
        assert RecordingHandler.requests == [], (
            "an unknown securable must fail with ZERO network — the reaper "
            "cannot determine what the request created"
        )

    def test_unknown_change_type_lands_failed_never_compensated(self):
        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = ["{}"]

        from hub.apps.databricks_admin.uc_change_reaper import resolve_stuck_request

        # A future vocabulary action (e.g. ALTER) must NEVER fall through
        # into the CREATE rollback path — compensating for an operation we
        # do not understand is forbidden.
        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
        )
        UCChangeRequest.objects.filter(pk=request.pk).update(change_type="ALTER")
        request.refresh_from_db()
        outcome = resolve_stuck_request(request)
        assert outcome["terminal"] == "FAILED", outcome

        request.refresh_from_db()
        assert request.status == UCChangeRequestStatus.FAILED
        assert RecordingHandler.requests == [], (
            "an unknown action must fail with ZERO compensating DDL"
        )
