"""TDD pins for the Databricks jobs client (openspec add-databricks-jobs
task 4.3) — the CRUD + run-now + runs/get|list surface of the pinned
jobs API (``/api/2.1/jobs/*``, 2.1).

The client rides the PRODUCTION ``DatabricksApiClient`` (retries,
breaker, version-pinned paths) — no mocks: every test drives a REAL
threaded local HTTP server with scripted jobs envelopes (the 0.5/3.2
convention). The contract pinned here:

- create/get/update/delete/run-now/runs.get/runs.list each hit their
  exact version-pinned path (``api_paths.py``).
- The task allowlist + the cluster-policy guard run BEFORE any network
  call (the D3 gate-first discipline): Spark SQL / notebook /
  SQL-warehouse tasks are allowed; Python tasks (spark_python /
  python_wheel) are gated by ``python_tasks_enabled`` (default OFF);
  every other task kind is refused; a job cluster without a cluster
  policy id is refused — each refusal raises ``DatabricksJobTaskError``
  (``DATABRICKS_JOB_TASK_FORBIDDEN``) with ZERO jobs API calls (the
  spec scenarios).
- An allowed create ships the caller's fields EXACTLY and returns the
  response's job id (the spec scenario).
- Workspace rejections propagate the classified ``Databricks*Error``
  family; malformed/non-object 2xx bodies are classified client errors
  (the 0.7 discipline) while mutation answers tolerate the API's
  legitimate empty-body 200.
- Shape discipline: wrong TYPES raise TypeError, wrong VALUES raise
  ValueError (the repo's boundary convention) — always BEFORE any
  network call (pinned with ``RecordingHandler.requests == []``).

Pure-transport suite: the client performs ZERO ORM work (the caller owns
the client — the 3.2 mirror contract; the tenant flag is the caller's
input), so there is deliberately NO ``django_db`` mark. The tenant flag
itself (field + registry entry) is pinned in ``test_flag_gating.py``.
"""

import json
from pathlib import Path

import pytest

from hub.apps.databricks_admin.tests._http import RecordingHandler

REPO_ROOT = Path(__file__).resolve().parents[4]


def _jobs_client(port, *, python_tasks_enabled=False):
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
        ),
        python_tasks_enabled=python_tasks_enabled,
    )


def _server():
    import http.server
    import threading

    RecordingHandler.script = []
    RecordingHandler.requests = []
    RecordingHandler.json_script = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return port


def _scripted(*payloads):
    RecordingHandler.json_script = [json.dumps(p) for p in payloads]


def _sql_task_payload(task_key="ingest", warehouse_id="wh-abc"):
    return {
        "task_key": task_key,
        "spark_sql_task": {"warehouse_id": warehouse_id, "query": "SELECT 1"},
    }


def _policy_cluster(job_cluster_key="default", policy_id="policy-abc"):
    return {
        "job_cluster_key": job_cluster_key,
        "new_cluster": {
            "cluster_policy_id": policy_id,
            "spark_version": "14.3.x-scala2.12",
            "node_type_id": "m5d.large",
            "num_workers": 1,
        },
    }


class TestJobsApiPaths:
    """Every 4.3 operation resolves to its exact version-pinned path."""

    def test_every_operation_is_version_pinned_2_1(self):
        from hub.apps.databricks_admin.api_paths import API_PATH_VERSIONS, API_PATHS, path

        expected = {
            "jobs.list": "/api/2.1/jobs/list",
            "jobs.runs.list": "/api/2.1/jobs/runs/list",
            "jobs.create": "/api/2.1/jobs/create",
            "jobs.update": "/api/2.1/jobs/update",
            "jobs.delete": "/api/2.1/jobs/delete",
            "jobs.get": "/api/2.1/jobs/get",
            "jobs.run_now": "/api/2.1/jobs/run-now",
            "jobs.runs.get": "/api/2.1/jobs/runs/get",
        }
        for operation, pinned in expected.items():
            assert operation in API_PATHS, f"{operation} must be pinned in API_PATHS"
            assert path(operation) == pinned, operation
            assert API_PATH_VERSIONS.get(operation) == "2.1", operation


class TestJobTaskGate:
    """The allowlist gates BEFORE any network call (the D3 discipline)."""

    def _create(self, client, **kwargs):
        return client.create_job(name=kwargs.pop("name", "nightly-etl"), **kwargs)

    def test_an_allowed_task_configuration_creates_end_to_end(self):
        # The spec scenario: a Spark SQL task + a policy-carrying job
        # cluster — the jobs API receives those EXACT fields and the
        # response's job id is returned.
        port = _server()
        _scripted({"job_id": 12345})
        client = _jobs_client(port)
        tasks = [_sql_task_payload()]
        clusters = [_policy_cluster()]
        job_id = self._create(client, tasks=tasks, job_clusters=clusters)

        assert job_id == "12345"
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "POST"
        assert recorded["path"] == "/api/2.1/jobs/create"
        sent = json.loads(recorded["body"])
        assert sent == {
            "name": "nightly-etl",
            "tasks": tasks,
            "job_clusters": clusters,
        }, "the create envelope must ship the caller's fields exactly"

    def test_notebook_and_sql_warehouse_tasks_are_allowed(self):
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError

        allowed = [
            {"task_key": "nb", "notebook_task": {"notebook_path": "/Shared/etl"}},
            {"task_key": "sql-wh", "sql_task": {"warehouse_id": "wh-abc", "query": "SELECT 1"}},
        ]
        for task in allowed:
            port = _server()
            _scripted({"job_id": 9})
            client = _jobs_client(port)
            job_id = self._create(client, tasks=[task])
            assert job_id == "9"
            sent = json.loads(RecordingHandler.requests[-1]["body"])
            assert sent["tasks"] == [task]

        # The gate is an ALLOWLIST: an empty/unknown task must be refused.
        port = _server()
        client = _jobs_client(port)
        with pytest.raises(DatabricksJobTaskError) as excinfo:
            client.create_job(name="x", tasks=[{"task_key": "plain"}])
        assert excinfo.value.code == "DATABRICKS_JOB_TASK_FORBIDDEN"
        assert RecordingHandler.requests == [], "a refused job must issue ZERO jobs API calls"

    def test_a_python_task_without_the_flag_is_refused_with_zero_network(self):
        # The spec scenario: the flag off → DATABRICKS_JOB_TASK_FORBIDDEN
        # and no jobs API call is issued.
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError

        port = _server()
        client = _jobs_client(port)  # python_tasks_enabled defaults OFF
        with pytest.raises(DatabricksJobTaskError) as excinfo:
            client.create_job(
                name="py-job",
                tasks=[{"task_key": "py", "spark_python_task": {"python_file": "dbfs:/etl.py"}}],
            )
        assert excinfo.value.code == "DATABRICKS_JOB_TASK_FORBIDDEN"
        assert RecordingHandler.requests == [], "the flag-gated refusal must issue ZERO calls"

    def test_a_python_task_with_the_flag_passes_the_gate(self):
        port = _server()
        _scripted({"job_id": 77})
        client = _jobs_client(port, python_tasks_enabled=True)
        tasks = [
            {"task_key": "py", "spark_python_task": {"python_file": "dbfs:/etl.py"}},
            {"task_key": "wheel", "python_wheel_task": {"package_name": "etl_pkg"}},
        ]
        job_id = client.create_job(name="py-job", tasks=tasks)
        assert job_id == "77"
        sent = json.loads(RecordingHandler.requests[-1]["body"])
        assert sent["tasks"] == tasks

    def test_known_but_never_allowed_task_kinds_are_refused(self):
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError

        forbidden = [
            {"task_key": "jar", "spark_jar_task": {"main_class_name": "Main"}},
            {"task_key": "dbt", "dbt_task": {"commands": ["run"]}},
            {"task_key": "pipe", "pipeline_task": {"pipeline_id": "p-1"}},
            {"task_key": "sub", "run_job_task": {"job_id": 1}},
        ]
        for task in forbidden:
            port = _server()
            client = _jobs_client(port)
            with pytest.raises(DatabricksJobTaskError):
                client.create_job(name="x", tasks=[task])
            assert RecordingHandler.requests == [], (
                f"{task['task_key']} must be refused with ZERO calls"
            )

    def test_ambiguous_and_malformed_task_shapes_are_refused(self):
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError

        port = _server()
        client = _jobs_client(port)
        # Two kinds on one task — the gate refuses, never guesses.
        with pytest.raises(DatabricksJobTaskError):
            client.create_job(
                name="x",
                tasks=[
                    {
                        "task_key": "both",
                        "spark_sql_task": {"warehouse_id": "w"},
                        "notebook_task": {"notebook_path": "/n"},
                    }
                ],
            )
        # A kind payload that is not a dict is malformed — refused.
        with pytest.raises(DatabricksJobTaskError):
            client.create_job(name="x", tasks=[{"task_key": "s", "spark_sql_task": "SELECT 1"}])
        assert RecordingHandler.requests == [], "gate refusals must issue ZERO calls"

    def test_task_list_shape_violations_fail_before_any_call(self):
        port = _server()
        client = _jobs_client(port)
        with pytest.raises(TypeError):
            client.create_job(name="x", tasks="SELECT 1")  # not a list
        with pytest.raises(TypeError):
            client.create_job(name="x", tasks=[["nested"]])  # not a dict task
        with pytest.raises(ValueError, match="at least one task"):
            client.create_job(name="x", tasks=[])  # empty
        assert RecordingHandler.requests == [], "shape violations must issue ZERO calls"

    def test_update_gates_the_same_allowlist(self):
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError

        port = _server()
        _scripted({})
        client = _jobs_client(port)
        # Allowed update ships the exact envelope (new_settings).
        client.update_job("12345", name="v2", tasks=[_sql_task_payload()])
        sent = json.loads(RecordingHandler.requests[-1]["body"])
        assert sent == {
            "job_id": "12345",
            "new_settings": {"name": "v2", "tasks": [_sql_task_payload()]},
        }

        port = _server()
        client = _jobs_client(port)
        with pytest.raises(DatabricksJobTaskError):
            client.update_job(
                "12345",
                name="v2",
                tasks=[{"task_key": "py", "spark_python_task": {"python_file": "f.py"}}],
            )
        assert RecordingHandler.requests == [], "the update gate must refuse with ZERO calls"


class TestClusterPolicyGuard:
    """Job clusters REQUIRE a cluster policy id (D3 — cost governance)."""

    def test_a_policy_less_job_cluster_is_refused_with_zero_network(self):
        # The spec scenario: a job whose cluster carries no policy id is
        # refused with DATABRICKS_JOB_TASK_FORBIDDEN and no API call.
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError

        for cluster in (
            {"job_cluster_key": "k", "new_cluster": {"spark_version": "14.3.x"}},
            {
                "job_cluster_key": "k",
                "new_cluster": {"cluster_policy_id": "", "spark_version": "14.3.x"},
            },
            {"job_cluster_key": "k", "new_cluster": {"cluster_policy_id": 42}},
            {"job_cluster_key": "k"},
        ):
            port = _server()
            client = _jobs_client(port)
            with pytest.raises(DatabricksJobTaskError) as excinfo:
                client.create_job(name="x", tasks=[_sql_task_payload()], job_clusters=[cluster])
            assert excinfo.value.code == "DATABRICKS_JOB_TASK_FORBIDDEN"
            assert RecordingHandler.requests == [], (
                f"the policy-less cluster {cluster} must be refused with ZERO calls"
            )

    def test_a_policy_carrying_cluster_creates_end_to_end(self):
        port = _server()
        _scripted({"job_id": 55})
        client = _jobs_client(port)
        clusters = [_policy_cluster()]
        job_id = client.create_job(name="x", tasks=[_sql_task_payload()], job_clusters=clusters)
        assert job_id == "55"
        sent = json.loads(RecordingHandler.requests[-1]["body"])
        assert sent["job_clusters"] == clusters

    def test_cluster_list_shape_violations_fail_before_any_call(self):
        port = _server()
        client = _jobs_client(port)
        with pytest.raises(TypeError):
            client.create_job(name="x", tasks=[_sql_task_payload()], job_clusters={"k": "v"})
        with pytest.raises(TypeError):
            client.create_job(name="x", tasks=[_sql_task_payload()], job_clusters=[["nested"]])
        assert RecordingHandler.requests == [], "shape violations must issue ZERO calls"


class TestJobsClientCRUD:
    """The CRUD surface hits the pinned paths with the exact envelopes."""

    def test_get_job_returns_the_reported_payload(self):
        port = _server()
        _scripted({"job_id": 1, "settings": {"name": "nightly"}})
        client = _jobs_client(port)
        payload = client.get_job("1")
        assert payload == {"job_id": 1, "settings": {"name": "nightly"}}
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "GET"
        assert recorded["path"] == "/api/2.1/jobs/get?job_id=1", recorded["path"]

    def test_delete_job_posts_the_job_id_and_tolerates_an_empty_body(self):
        port = _server()
        _scripted({})
        client = _jobs_client(port)
        assert client.delete_job("7") is None
        recorded = RecordingHandler.requests[-1]
        assert recorded["path"] == "/api/2.1/jobs/delete"
        assert json.loads(recorded["body"]) == {"job_id": "7"}

        # The API's legitimate empty-body answer is a success.
        port = _server()
        RecordingHandler.json_script = [""]
        client = _jobs_client(port)
        assert client.delete_job("7") is None

    def test_job_id_shape_violations_fail_before_any_call(self):
        port = _server()
        client = _jobs_client(port)
        for method in (
            lambda: client.get_job(""),
            lambda: client.delete_job("   "),
            lambda: client.run_now(""),
            lambda: client.update_job("", name="x", tasks=[_sql_task_payload()]),
        ):
            with pytest.raises(ValueError, match="must not be empty"):
                method()
        for method in (lambda: client.get_job(42), lambda: client.delete_job(None)):
            with pytest.raises(TypeError):
                method()
        assert RecordingHandler.requests == [], "id shape violations must issue ZERO calls"

    def test_create_response_without_a_job_id_is_classified(self):
        from hub.apps.databricks_admin.client import DatabricksApiError

        port = _server()
        _scripted({})
        client = _jobs_client(port)
        with pytest.raises(DatabricksApiError):
            client.create_job(name="x", tasks=[_sql_task_payload()])


class TestJobsClientRuns:
    """run-now + runs/get + runs/list on the pinned paths."""

    def test_run_now_posts_the_job_id_and_returns_the_run_id(self):
        port = _server()
        _scripted({"run_id": 999})
        client = _jobs_client(port)
        assert client.run_now("42") == "999"
        recorded = RecordingHandler.requests[-1]
        assert recorded["path"] == "/api/2.1/jobs/run-now"
        assert json.loads(recorded["body"]) == {"job_id": "42"}

    def test_run_now_without_a_run_id_in_the_answer_is_classified(self):
        from hub.apps.databricks_admin.client import DatabricksApiError

        port = _server()
        _scripted({})
        client = _jobs_client(port)
        with pytest.raises(DatabricksApiError):
            client.run_now("42")

    def test_get_run_returns_the_reported_payload(self):
        port = _server()
        _scripted({"run_id": 999, "state": {"life_cycle_state": "TERMINATED"}})
        client = _jobs_client(port)
        payload = client.get_run("999")
        assert payload["state"]["life_cycle_state"] == "TERMINATED"
        recorded = RecordingHandler.requests[-1]
        assert recorded["path"] == "/api/2.1/jobs/runs/get?run_id=999", recorded["path"]

    def test_list_runs_ships_the_filters_and_requires_a_runs_list(self):
        from hub.apps.databricks_admin.client import DatabricksApiError

        port = _server()
        _scripted({"runs": [{"run_id": 1}], "has_more": False})
        client = _jobs_client(port)
        runs = client.list_runs(job_id="42", page_token="tok-1")
        assert runs == [{"run_id": 1}]
        recorded = RecordingHandler.requests[-1]
        assert recorded["path"] == "/api/2.1/jobs/runs/list?job_id=42&page_token=tok-1", recorded[
            "path"
        ]

        port = _server()
        _scripted({"runs": "not-a-list"})
        client = _jobs_client(port)
        with pytest.raises(DatabricksApiError):
            client.list_runs()

    def test_list_jobs_returns_the_jobs_list(self):
        from hub.apps.databricks_admin.client import DatabricksApiError

        port = _server()
        _scripted({"jobs": [{"job_id": 1}], "has_more": False})
        client = _jobs_client(port)
        assert client.list_jobs() == [{"job_id": 1}]

        port = _server()
        _scripted({"jobs": "not-a-list"})
        client = _jobs_client(port)
        with pytest.raises(DatabricksApiError):
            client.list_jobs()

    def test_run_id_shape_violations_fail_before_any_call(self):
        port = _server()
        client = _jobs_client(port)
        with pytest.raises(ValueError, match="must not be empty"):
            client.get_run("")
        with pytest.raises(TypeError):
            client.get_run(999)
        assert RecordingHandler.requests == [], "run id shape violations must issue ZERO calls"


class TestJobsClientErrors:
    """Workspace rejections propagate the classified family; malformed
    bodies are classified client errors (the 0.7 discipline)."""

    def test_a_workspace_rejection_propagates_the_classified_family(self):
        from hub.apps.databricks_admin.client import DatabricksAuthError

        port = _server()
        RecordingHandler.script = [401]
        client = _jobs_client(port)
        with pytest.raises(DatabricksAuthError) as excinfo:
            client.get_job("1")
        assert excinfo.value.code == "DATABRICKS_AUTH_FAILED"

    def test_a_non_json_body_on_a_read_is_classified(self):
        from hub.apps.databricks_admin.client import DatabricksApiError

        port = _server()
        _scripted("not json")
        client = _jobs_client(port)
        with pytest.raises(DatabricksApiError):
            client.get_job("1")

    def test_a_non_object_body_on_a_read_is_classified(self):
        from hub.apps.databricks_admin.client import DatabricksApiError

        port = _server()
        _scripted(["an", "array"])
        client = _jobs_client(port)
        with pytest.raises(DatabricksApiError):
            client.get_job("1")

    def test_the_constructor_rejects_a_non_bool_flag(self):
        from hub.apps.databricks_admin.client import DatabricksApiClient

        port = _server()
        from hub.apps.databricks_admin.jobs_client import DatabricksJobsClient

        with pytest.raises(TypeError):
            DatabricksJobsClient(
                DatabricksApiClient(base_url=f"http://127.0.0.1:{port}"), python_tasks_enabled="yes"
            )
