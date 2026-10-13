"""TDD pins for the Databricks job lifecycle audit (openspec
add-databricks-jobs task 4.6) — the six ``DATABRICKS_JOB_*`` event
constants + the CREATED/UPDATED/DELETED emission chokepoint
(``databricks_admin.jobs_lifecycle``).

The RUN_* trio registered with 4.4 (the poller's emission chokepoint,
``databricks_admin.job_runs``); this task registers
CREATED/UPDATED/DELETED and emits them at the client lifecycle points.
Emission is BEST-EFFORT (D5 / the Phase 273 contract): an audit-DB
outage never blocks the operation.

No mocks except the documented module-boundary seam patch (the 3.8
audit-outage convention — ``unittest.mock`` on ``audit.utils``, never
on the unit under test): real Postgres audit rows, real mirror rows,
and the PRODUCTION client against a REAL local HTTP server.
"""

import http.server
import json
import threading
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _client(port):
    from hub.apps.databricks_admin.client import DatabricksApiClient
    from hub.apps.databricks_admin.jobs_client import DatabricksJobsClient

    return DatabricksJobsClient(
        DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id="t1",
            credential_config={"token": "dapi-jobs"},
            timeout_ms=5000,
            max_retries=1,
            retry_base_delay=0.05,
            retry_max_delay=0.1,
            use_breaker=False,
        )
    )


def _sql_task_payload(task_key="ingest", warehouse_id="wh-abc"):
    return {
        "task_key": task_key,
        "spark_sql_task": {"warehouse_id": warehouse_id, "query": "SELECT 1"},
    }


class TestJobAuditEventRegistration:
    """All six constants exist with the exact values and are exported."""

    def test_all_six_constants_are_registered(self):
        from hub.apps.audit import event_types

        expected = {
            "DATABRICKS_JOB_CREATED": "DATABRICKS_JOB_CREATED",
            "DATABRICKS_JOB_UPDATED": "DATABRICKS_JOB_UPDATED",
            "DATABRICKS_JOB_DELETED": "DATABRICKS_JOB_DELETED",
            "DATABRICKS_JOB_RUN_STARTED": "DATABRICKS_JOB_RUN_STARTED",
            "DATABRICKS_JOB_RUN_SUCCEEDED": "DATABRICKS_JOB_RUN_SUCCEEDED",
            "DATABRICKS_JOB_RUN_FAILED": "DATABRICKS_JOB_RUN_FAILED",
        }
        for name, value in expected.items():
            assert getattr(event_types, name) == value, name
        for value in expected.values():
            assert value in event_types.__all__, f"{value} must be exported in __all__"


class TestJobLifecycleAuditEmission(TestCase):
    """The lifecycle chokepoint emits one row per performed operation."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.actor = _make_user(self.tenant, f"jobs-audit-{uuid.uuid4().hex[:8]}@test.com")
        self.workspace = _make_workspace(self.tenant, name="ws-jobs-audit")

    def _server(self):
        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return port

    def _audit_rows(self, action):
        from hub.apps.audit.models import AuditEvent

        return list(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action=action,
                resource_type="DATABRICKS_JOB",
            ).order_by("timestamp")
        )

    def _mirror_row(self, job_id="12345"):
        from hub.apps.databricks_admin.models import DatabricksJob

        return DatabricksJob.objects.create(workspace=self.workspace, job_id=job_id, name="job")

    def test_create_emits_created_with_identifiers_only(self):
        from hub.apps.databricks_admin.jobs_lifecycle import create_databricks_job

        port = self._server()
        RecordingHandler.json_script = [json.dumps({"job_id": 77})]
        job_id = create_databricks_job(
            self.workspace,
            client=_client(port),
            name="nightly-etl",
            tasks=[_sql_task_payload()],
            actor_user=self.actor,
        )
        assert job_id == "77"

        rows = self._audit_rows("DATABRICKS_JOB_CREATED")
        assert len(rows) == 1
        row = rows[0]
        assert row.actor_user_id == self.actor.id
        assert row.resource_id is None, "no mirror row exists yet — the id lives in details"
        assert row.details_json == {
            "job_id": "77",
            "workspace_id": str(self.workspace.id),
        }, "identifiers only — never task configuration material"

    def test_update_emits_updated_with_the_mirror_row_id(self):
        from hub.apps.databricks_admin.jobs_lifecycle import update_databricks_job

        mirror = self._mirror_row()
        port = self._server()
        RecordingHandler.json_script = [json.dumps({})]
        result = update_databricks_job(
            self.workspace,
            "12345",
            client=_client(port),
            name="nightly-etl-v2",
            tasks=[_sql_task_payload()],
            actor_user=self.actor,
        )
        assert result == {}

        rows = self._audit_rows("DATABRICKS_JOB_UPDATED")
        assert len(rows) == 1
        assert rows[0].resource_id == mirror.id, "the mirror row's pk anchors the event"
        assert rows[0].details_json == {
            "job_id": "12345",
            "workspace_id": str(self.workspace.id),
        }

    def test_delete_emits_deleted(self):
        from hub.apps.databricks_admin.jobs_lifecycle import delete_databricks_job

        mirror = self._mirror_row()
        port = self._server()
        RecordingHandler.json_script = [json.dumps({})]
        assert delete_databricks_job(self.workspace, "12345", client=_client(port)) is None

        rows = self._audit_rows("DATABRICKS_JOB_DELETED")
        assert len(rows) == 1
        assert rows[0].resource_id == mirror.id

    def test_a_refused_job_emits_nothing(self):
        # The gate-first refusal raises BEFORE any network call — no
        # operation happened, so no audit row exists.
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError
        from hub.apps.databricks_admin.jobs_lifecycle import create_databricks_job

        port = self._server()
        with pytest.raises(DatabricksJobTaskError):
            create_databricks_job(
                self.workspace,
                client=_client(port),
                name="py-job",
                tasks=[{"task_key": "py", "spark_python_task": {"python_file": "f.py"}}],
                actor_user=self.actor,
            )
        assert self._audit_rows("DATABRICKS_JOB_CREATED") == []
        assert RecordingHandler.requests == []

    def test_audit_outage_never_blocks_the_operation(self):
        # The Phase 273 best-effort contract: an audit-DB failure must
        # never fail the lifecycle operation itself (unittest.mock as a
        # context manager on the audit-utils seam — the 3.8 convention).
        from unittest import mock

        from hub.apps.databricks_admin.jobs_lifecycle import create_databricks_job

        def _explode(*_args, **_kwargs):
            raise RuntimeError("audit DB down")

        import hub.apps.audit.utils as audit_utils

        patch = mock.patch.object(audit_utils, "create_audit_event", _explode)
        patch.start()
        self.addCleanup(patch.stop)
        port = self._server()
        RecordingHandler.json_script = [json.dumps({"job_id": 88})]
        # The operation completes and returns its id; the audit failure
        # is swallowed with ZERO raise.
        assert (
            create_databricks_job(
                self.workspace,
                client=_client(port),
                name="nightly-etl",
                tasks=[_sql_task_payload()],
                actor_user=self.actor,
            )
            == "88"
        )
