"""Journey pins for the P4 jobs surface (openspec add-databricks-jobs
task 4.7) — JOURNEY-DB-011 (Run a Databricks Job) + UC-DB-011 (Run
Databricks Job).

Class/method names are PINNED by the UC docs' "Phase P4 Test" field
(docs/mvpdocs/use-cases/UC-DB-011.md) — renaming them breaks the
docs↔test drift gates (GATE-28).

The journey spans the shipped P4 surfaces with NO mocks — real Postgres
rows (tenant/workspace/job-mirror/run-mirror/audit/webhook), the REAL
4.5 viewset (mirror-first browse, zero network), the REAL 4.3 jobs
client (gate-first allowlist + cluster-policy guard), the REAL 4.4
run-now service (Hub ``Job`` → dispatch → backoff poll with the REAL
sleeper → terminal audit + stored cost estimate), and the REAL 4.5
webhook delivery (a real Webhook row + a real HTTP receiver, the
synchronous mesh delivery). The compute surface is a REAL threaded HTTP
server answering the pinned 2.1 jobs paths.
"""

import json
import time
import uuid

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_job_runs import (
    _run_payload,
    _seed_mirror_job,
    _seed_workspace,
)
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.journey("JOURNEY-DB-011"),
    pytest.mark.uc("UC-DB-011"),
]

JOBS_URL = "/api/v1/databricks/workspaces/{workspace_id}/jobs/"


def _compute_client(port, *, tenant_id="t1", python_tasks_enabled=False):
    from hub.apps.databricks_admin.client import DatabricksApiClient
    from hub.apps.databricks_admin.jobs_client import DatabricksJobsClient

    return DatabricksJobsClient(
        DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id=tenant_id,
            credential_config={"token": "dapi-jobs"},
            timeout_ms=5000,
            max_retries=1,
            retry_base_delay=0.05,
            retry_max_delay=0.1,
            use_breaker=False,  # the 1.7 delegation convention — the test owns the transport
        ),
        python_tasks_enabled=python_tasks_enabled,
    )


def _seed_run_mirror(job, *, run_id="42", lifecycle="RUNNING", result="SUCCESS"):
    from hub.apps.databricks_admin.models import DatabricksJobRun

    return DatabricksJobRun.objects.create(
        job=job,
        run_id=run_id,
        lifecycle_state=lifecycle,
        result_state=result,
        duration_ms=60000,
    )


class TestJOURNEYDB011RunDatabricksJob:
    """A data engineer runs a Databricks job from the Hub: the mirror
    serves the fleet (zero network on the READ leg), the client's gate
    refuses ungoverned definitions BEFORE any jobs call, run-now
    dispatches and the poller follows the run through its state machine
    to a terminal outcome with the audit trail and the stored cost
    estimate, and a terminal failure fires the real
    ``databricks.job.run.failed`` webhook.

    Plain class (not TestCase) — pytest fixtures cannot serve TestCase
    methods (the 0.8 trap); the Test* prefix satisfies python_classes
    (the 1.3 trap).
    """

    def _seed(self):
        self.tenant, self.admin = _setup_tenant()
        self.workspace = _seed_workspace(self.tenant)
        self.mirror = _seed_mirror_job(self.workspace)

    def test_mirror_first_browse_lists_jobs_and_runs_with_zero_network(self):
        """The READ leg: the 4.5 viewset serves the mirrored fleet and
        the nested run rows from the DATABASE — the wire never sees a
        request — and an unknown job surfaces the 404 boundary."""
        self._seed()
        _seed_run_mirror(self.mirror, run_id="42")
        _seed_run_mirror(self.mirror, run_id="43", lifecycle="TERMINATED", result="FAILED")
        client = APIClient()
        client.force_authenticate(user=self.admin)
        RecordingHandler.requests = []

        response = client.get(JOBS_URL.format(workspace_id=self.workspace.id))
        assert response.status_code == 200, response.content
        envelope = response.json()
        assert envelope["count"] == 1
        row = envelope["results"][0]
        assert row["job_id"] == self.mirror.job_id
        assert row["name"] == "nightly-etl"
        assert isinstance(row["task_config"], list)

        runs_response = client.get(
            JOBS_URL.format(workspace_id=self.workspace.id) + f"{self.mirror.job_id}/runs/"
        )
        assert runs_response.status_code == 200, runs_response.content
        runs = runs_response.json()["results"]
        assert {run["run_id"] for run in runs} == {"42", "43"}
        for run in runs:
            assert run["lifecycle_state"] in ("RUNNING", "TERMINATED")
            assert run["result_state"] in ("SUCCESS", "FAILED")
            assert run["duration_ms"] == 60000

        assert RecordingHandler.requests == [], "the mirror-first browse never touches the wire"

        missing = client.get(
            JOBS_URL.format(workspace_id=self.workspace.id) + "job-does-not-exist/runs/"
        )
        assert missing.status_code == 404

    def test_poller_state_machine(self, local_http_server):
        """The run-now leg (the doc-pinned pin): dispatch → backoff poll
        with the REAL sleeper → terminal. The Hub Job walks
        PENDING → RUNNING → COMPLETED, the audit trail records one row
        per transition with attribution, and the stored cost estimate
        derives from the run payload's real duration and worker count."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.job_runs import run_databricks_job_now
        from hub.apps.jobs.models import JobStatus, JobType

        self._seed()
        client = _compute_client(local_http_server, tenant_id=str(self.tenant.id))
        RecordingHandler.json_script = [
            json.dumps({"run_id": "7"}),  # the run-now answer
            json.dumps(_run_payload(lifecycle="PENDING")),
            json.dumps(_run_payload(lifecycle="RUNNING")),
            json.dumps(_run_payload(lifecycle="TERMINATED", result="SUCCESS")),
        ]

        # The REAL sleeper — the poller's backoff intervals (2s then 3s)
        # are the production discipline, never stubbed.
        job = run_databricks_job_now(
            workspace=self.workspace,
            mirror_job=self.mirror,
            actor_user=self.admin,
            client=client,
            sleeper=time.sleep,
            poll_timeout_s=60,
        )

        assert job.type == JobType.DATABRICKS_JOB_RUN
        assert job.status == JobStatus.COMPLETED
        assert job.databricks_run_id == 7
        assert job.started_at is not None
        assert job.completed_at is not None
        assert job.details_json["databricks_job_id"] == self.mirror.job_id
        assert job.result_json["databricks_run_state"] == "SUCCESS"
        estimate = job.result_json["cost_estimate"]
        assert estimate["duration_seconds"] == 60.0
        assert estimate["size_factor"] == 2.0  # 1 + 0.5 x num_workers=2

        # The wire conversation: run-now POST then three runs/get polls.
        requests = RecordingHandler.requests
        assert requests[0]["method"] == "POST"
        assert requests[0]["path"] == "/api/2.1/jobs/run-now"
        assert json.loads(requests[0]["body"]) == {"job_id": self.mirror.job_id}
        polls = [r for r in requests[1:] if r["method"] == "GET"]
        assert len(polls) == 3
        assert all(r["path"] == "/api/2.1/jobs/runs/get?run_id=7" for r in polls)

        # The audit trail: one row per Hub-side transition, attributed.
        events = AuditEvent.objects.filter(
            tenant=self.tenant, resource_type="DATABRICKS_JOB"
        ).order_by("timestamp")
        assert [event.action for event in events] == ["RUN_STARTED", "RUN_SUCCEEDED"]
        assert all(str(event.resource_id) == str(job.id) for event in events)
        assert all(event.details_json["databricks_run_id"] == "7" for event in events)
        assert all(event.actor_user_id == self.admin.id for event in events)

    def test_forbidden_task_type_is_refused_before_any_call(self, local_http_server):
        """The D3 gate leg: a Python task (flag off) and a policy-less
        job cluster are refused with ``DATABRICKS_JOB_TASK_FORBIDDEN``
        and ZERO jobs API calls; an allowlisted definition passes the
        gate and creates through the real wire."""
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError

        self._seed()
        client = _compute_client(local_http_server)
        RecordingHandler.requests = []

        with pytest.raises(DatabricksJobTaskError) as refused:
            client.create_job(
                name="python-etl",
                tasks=[{"task_key": "py", "spark_python_task": {"python_file": "dbfs:/x.py"}}],
            )
        assert refused.value.code == "DATABRICKS_JOB_TASK_FORBIDDEN"

        with pytest.raises(DatabricksJobTaskError) as ungoverned:
            client.create_job(
                name="bare-cluster",
                tasks=[{"task_key": "sql", "sql_task": {"warehouse_id": "wh-1"}}],
                job_clusters=[{"job_cluster_key": "c", "new_cluster": {"num_workers": 2}}],
            )
        assert ungoverned.value.code == "DATABRICKS_JOB_TASK_FORBIDDEN"
        assert RecordingHandler.requests == [], "a gated definition never reaches the jobs API"

        # The allowed leg: Spark SQL task + a policy-governed cluster.
        RecordingHandler.json_script = [json.dumps({"job_id": "job-created"})]
        created = client.create_job(
            name="governed-etl",
            tasks=[{"task_key": "sql", "sql_task": {"warehouse_id": "wh-1"}}],
            job_clusters=[
                {
                    "job_cluster_key": "c",
                    "new_cluster": {"num_workers": 2, "cluster_policy_id": "policy-1"},
                }
            ],
        )
        assert created == "job-created"
        request = RecordingHandler.requests[-1]
        assert request["path"] == "/api/2.1/jobs/create"
        assert json.loads(request["body"])["name"] == "governed-etl"

    @override_settings(WEBHOOK_ASYNC_DELIVERY=False)
    def test_a_failed_run_records_the_failure_and_fires_the_webhook(self, local_http_server):
        """The terminal-failure leg: a FAILED run marks the Hub Job
        FAILED with the real state message, records RUN_STARTED +
        RUN_FAILED, and the REAL webhook delivery lands at a real
        receiver with the run id and the reported failure state."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.job_runs import run_databricks_job_now

        # A REAL webhook subscriber on the journey tenant (the 4.5
        # delivery pins' setup — KYC-verified + active subscription).
        from hub.apps.databricks_admin.tests._fixtures import require_dns
        from hub.apps.jobs.models import JobStatus
        from hub.apps.tenants.models import KYCStatus, Tenant
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        from hub.apps.users.models import User
        from hub.apps.webhooks.models import (
            DeliveryStatus,
            Webhook,
            WebhookDelivery,
            WebhookStatus,
        )
        from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer
        from tests.utils.polling import wait_until

        require_dns()
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Jobs Journey Tenant {uid}",
            slug=f"jobs-journey-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(tenant)
        actor = User.objects.create_user(
            email=f"jobs-journey-{uid}@example.com", password="testpass123", tenant=tenant
        )
        workspace = _seed_workspace(tenant)
        mirror = _seed_mirror_job(workspace)
        client = _compute_client(local_http_server, tenant_id=str(tenant.id))
        RecordingHandler.json_script = [
            json.dumps({"run_id": "7"}),  # the run-now answer
            json.dumps(
                _run_payload(
                    lifecycle="TERMINATED",
                    result="FAILED",
                    state_message="Task etl failed: OOM",
                )
            ),
        ]

        with TestWebhookServer(response_status=200) as receiver:
            Webhook.objects.create(
                tenant=tenant,
                name="Jobs Journey Webhook",
                url=receiver.get_url(),
                secret="test-secret-key",
                event_types=["databricks.job.run.failed"],
                status=WebhookStatus.ACTIVE,
                created_by=actor,
            )
            job = run_databricks_job_now(
                workspace=workspace,
                mirror_job=mirror,
                actor_user=actor,
                client=client,
                sleeper=time.sleep,
            )

            assert job.status == JobStatus.FAILED
            assert "OOM" in (job.error_message or "")

            events = AuditEvent.objects.filter(
                tenant=tenant, resource_type="DATABRICKS_JOB"
            ).order_by("timestamp")
            assert [event.action for event in events] == ["RUN_STARTED", "RUN_FAILED"]

            wait_until(
                lambda: WebhookDelivery.objects.filter(
                    webhook__tenant=tenant, event_type="databricks.job.run.failed"
                ).exists(),
                timeout=5.0,
                message="databricks.job.run.failed delivery not recorded",
            )
            delivery = WebhookDelivery.objects.get(
                webhook__tenant=tenant, event_type="databricks.job.run.failed"
            )
            assert delivery.status == DeliveryStatus.SUCCESS
            payload = delivery.payload or {}
            assert payload.get("event_type") == "databricks.job.run.failed"
            assert payload.get("resource_id") == "7"
            data = payload.get("data") or {}
            assert data.get("run_id") == "7"
            assert data.get("result_state") == "FAILED"
            assert data.get("error_message") == "Task etl failed: OOM"
