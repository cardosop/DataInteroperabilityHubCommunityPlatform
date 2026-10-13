"""TDD pins for the jobs task allowlist (openspec add-databricks-jobs
task 4.8) — the FULL matrix of the 4.3 gate, checked against a
hardcoded contract (the 3.10 tier-gating convention).

The allowance contract is restated INDEPENDENTLY here, three ways:

- the production sets EQUAL the contract (a silent vocabulary drift
  fails the table pin);
- every (task kind x flag) cell behaves per the contract — allowed
  kinds create end-to-end, Python kinds flip with the flag, forbidden
  kinds are refused BY NAME on BOTH flag settings, each refusal raises
  ``DatabricksJobTaskError`` (``DATABRICKS_JOB_TASK_FORBIDDEN``) with
  ZERO jobs API calls (``RecordingHandler.requests == []`` per cell);
- the cluster-policy guard matrix + the envelope/shape cells refuse
  BEFORE any network call.

Pure-transport suite: no ``django_db`` mark (the client is ORM-free —
the 4.3 precedent). Every test drives the PRODUCTION
``DatabricksJobsClient`` over a REAL threaded local HTTP server.
"""

import json

import pytest

from hub.apps.databricks_admin.tests._http import RecordingHandler

# The independent contract (design D3).
ALLOWED_KINDS = ["spark_sql_task", "notebook_task", "sql_task"]
PYTHON_KINDS = ["spark_python_task", "python_wheel_task"]
FORBIDDEN_KINDS = [
    "dbt_task",
    "spark_jar_task",
    "spark_submit_task",
    "pipeline_task",
    "run_job_task",
    "for_each_task",
    "clean_rooms_notebook_task",
]

# One realistic payload per task kind (the jobs API's shapes).
TASK_PAYLOADS = {
    "spark_sql_task": {"warehouse_id": "wh-abc", "query": "SELECT 1"},
    "notebook_task": {"notebook_path": "/Shared/etl"},
    "sql_task": {"warehouse_id": "wh-abc", "query": "SELECT 1"},
    "spark_python_task": {"python_file": "dbfs:/etl.py"},
    "python_wheel_task": {"package_name": "etl_pkg", "entry_point": "main"},
    "dbt_task": {"commands": ["run"]},
    "spark_jar_task": {"main_class_name": "Main"},
    "spark_submit_task": {"parameters": ["--conf", "x=1"]},
    "pipeline_task": {"pipeline_id": "p-1"},
    "run_job_task": {"job_id": 42},
    "for_each_task": {"inputs": "x", "task": {"task_key": "inner"}},
    "clean_rooms_notebook_task": {"notebook_name": "nb"},
}


def _client(port, *, python_tasks_enabled=False):
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
        ),
        python_tasks_enabled=python_tasks_enabled,
    )


def _task(kind, task_key=None):
    return {"task_key": task_key or f"task-{kind}", kind: TASK_PAYLOADS[kind]}


def _scripted(*payloads):
    RecordingHandler.json_script = [json.dumps(payload) for payload in payloads]


def _create(client, **kwargs):
    return client.create_job(name=kwargs.pop("name", "nightly-etl"), **kwargs)


class TestAllowanceContract:
    """The production sets EQUAL the independent contract — a silent
    vocabulary drift in either direction fails."""

    def test_the_production_kind_sets_equal_the_contract(self):
        from hub.apps.databricks_admin import jobs_client

        assert set(jobs_client._ALLOWED_TASK_KINDS) == set(ALLOWED_KINDS)
        assert set(jobs_client._PYTHON_TASK_KINDS) == set(PYTHON_KINDS)
        assert set(jobs_client._KNOWN_FORBIDDEN_KINDS) == set(FORBIDDEN_KINDS)

    def test_the_kind_sets_partition_without_overlap(self):
        assert set(ALLOWED_KINDS).isdisjoint(PYTHON_KINDS)
        assert set(ALLOWED_KINDS).isdisjoint(FORBIDDEN_KINDS)
        assert set(PYTHON_KINDS).isdisjoint(FORBIDDEN_KINDS)


class TestTaskAllowlistMatrix:
    """Every (kind x flag) cell: pass ⟺ the contract allows it — with
    ZERO network calls on every refusal cell."""

    @pytest.mark.parametrize("kind", ALLOWED_KINDS)
    def test_allowed_kinds_create_end_to_end_with_the_flag_off(self, kind, local_http_server):
        _scripted({"job_id": 5})
        client = _client(local_http_server)
        job_id = _create(client, tasks=[_task(kind)])
        assert job_id == "5"
        sent = json.loads(RecordingHandler.requests[-1]["body"])
        assert sent["tasks"] == [_task(kind)], "the allowed task ships exactly"

    @pytest.mark.parametrize("kind", PYTHON_KINDS + FORBIDDEN_KINDS)
    def test_python_and_forbidden_kinds_are_refused_with_the_flag_off(
        self, kind, local_http_server
    ):
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError

        client = _client(local_http_server)  # python_tasks_enabled defaults OFF
        with pytest.raises(DatabricksJobTaskError) as excinfo:
            _create(client, tasks=[_task(kind)])
        assert excinfo.value.code == "DATABRICKS_JOB_TASK_FORBIDDEN"
        assert RecordingHandler.requests == [], f"{kind} must be refused with ZERO jobs API calls"

    @pytest.mark.parametrize("kind", PYTHON_KINDS)
    def test_python_kinds_pass_the_gate_with_the_flag_on(self, kind, local_http_server):
        _scripted({"job_id": 9})
        client = _client(local_http_server, python_tasks_enabled=True)
        job_id = _create(client, tasks=[_task(kind)])
        assert job_id == "9"
        sent = json.loads(RecordingHandler.requests[-1]["body"])
        assert sent["tasks"] == [_task(kind)]

    @pytest.mark.parametrize("kind", FORBIDDEN_KINDS)
    def test_forbidden_kinds_stay_refused_even_with_the_flag_on(self, kind, local_http_server):
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError

        client = _client(local_http_server, python_tasks_enabled=True)
        with pytest.raises(DatabricksJobTaskError) as excinfo:
            _create(client, tasks=[_task(kind)])
        assert excinfo.value.code == "DATABRICKS_JOB_TASK_FORBIDDEN", (
            "the flag NEVER admits a forbidden kind"
        )
        assert RecordingHandler.requests == []

    @pytest.mark.parametrize(
        "task",
        [
            {"task_key": "no-kind"},
            {
                "task_key": "both",
                "spark_sql_task": {"warehouse_id": "w"},
                "notebook_task": {"notebook_path": "/n"},
            },
            {"task_key": "malformed", "spark_sql_task": "SELECT 1"},
        ],
    )
    def test_unknown_ambiguous_and_malformed_task_shapes_are_refused(self, task, local_http_server):
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError

        client = _client(local_http_server)
        with pytest.raises(DatabricksJobTaskError) as excinfo:
            _create(client, tasks=[task])
        assert excinfo.value.code == "DATABRICKS_JOB_TASK_FORBIDDEN"
        assert RecordingHandler.requests == [], "refused shapes issue ZERO calls"

    def test_task_list_shape_violations_fail_before_any_call(self, local_http_server):
        client = _client(local_http_server)
        with pytest.raises(TypeError):
            _create(client, tasks="SELECT 1")
        with pytest.raises(TypeError):
            _create(client, tasks=[["nested"]])
        with pytest.raises(ValueError, match="at least one task"):
            _create(client, tasks=[])
        assert RecordingHandler.requests == []

    def test_update_gates_the_same_allowlist_matrix(self, local_http_server):
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError

        _scripted({})
        client = _client(local_http_server)
        client.update_job("1", name="v2", tasks=[_task("spark_sql_task")])
        sent = json.loads(RecordingHandler.requests[-1]["body"])
        assert sent == {
            "job_id": "1",
            "new_settings": {"name": "v2", "tasks": [_task("spark_sql_task")]},
        }

        RecordingHandler.requests = []
        with pytest.raises(DatabricksJobTaskError):
            client.update_job("1", name="v2", tasks=[_task("spark_jar_task")])
        assert RecordingHandler.requests == [], "the update gate refuses with ZERO calls"


class TestClusterPolicyGuardMatrix:
    """Job clusters REQUIRE a cluster policy id — the refusal matrix
    issues ZERO network calls per cell."""

    @pytest.mark.parametrize(
        "cluster",
        [
            {"job_cluster_key": "k", "new_cluster": {"spark_version": "14.3.x"}},
            {
                "job_cluster_key": "k",
                "new_cluster": {"cluster_policy_id": "", "spark_version": "14.3.x"},
            },
            {"job_cluster_key": "k", "new_cluster": {"cluster_policy_id": 42}},
            {"job_cluster_key": "k", "new_cluster": {"cluster_policy_id": None}},
            {"job_cluster_key": "k"},
        ],
    )
    def test_policy_less_cluster_variants_are_refused(self, cluster, local_http_server):
        from hub.apps.databricks_admin.jobs_client import DatabricksJobTaskError

        client = _client(local_http_server)
        with pytest.raises(DatabricksJobTaskError) as excinfo:
            _create(client, tasks=[_task("spark_sql_task")], job_clusters=[cluster])
        assert excinfo.value.code == "DATABRICKS_JOB_TASK_FORBIDDEN"
        assert RecordingHandler.requests == [], "the policy-less cluster issues ZERO calls"

    def test_cluster_list_shape_violations_fail_before_any_call(self, local_http_server):
        client = _client(local_http_server)
        with pytest.raises(TypeError):
            _create(client, tasks=[_task("spark_sql_task")], job_clusters={"k": "v"})
        with pytest.raises(TypeError):
            _create(client, tasks=[_task("spark_sql_task")], job_clusters=[["nested"]])
        assert RecordingHandler.requests == []

    def test_a_policy_carrying_cluster_passes_and_ships_exactly(self, local_http_server):
        _scripted({"job_id": 55})
        client = _client(local_http_server)
        cluster = {
            "job_cluster_key": "default",
            "new_cluster": {
                "cluster_policy_id": "policy-abc",
                "spark_version": "14.3.x-scala2.12",
                "num_workers": 1,
            },
        }
        job_id = _create(client, tasks=[_task("spark_sql_task")], job_clusters=[cluster])
        assert job_id == "55"
        sent = json.loads(RecordingHandler.requests[-1]["body"])
        assert sent["job_clusters"] == [cluster]

    def test_an_existing_cluster_id_task_is_not_a_job_cluster(self, local_http_server):
        # existing_cluster_id references a cluster that already exists —
        # nothing new is created, so the policy guard leaves it alone.
        _scripted({"job_id": 66})
        client = _client(local_http_server)
        task = {
            "task_key": "existing",
            "spark_sql_task": {"warehouse_id": "wh-abc", "query": "SELECT 1"},
            "existing_cluster_id": "0609-123456-abcdef",
        }
        job_id = _create(client, tasks=[task])
        assert job_id == "66"
        sent = json.loads(RecordingHandler.requests[-1]["body"])
        assert sent["tasks"] == [task]


class TestEnvelopeShapeCells:
    """Wrong TYPES raise TypeError, wrong VALUES raise ValueError — the
    repo's boundary convention — always BEFORE any network call."""

    def test_name_shape_violations_fail_before_any_call(self, local_http_server):
        client = _client(local_http_server)
        with pytest.raises(TypeError):
            _create(client, name=42, tasks=[_task("spark_sql_task")])
        with pytest.raises(ValueError, match="non-empty"):
            _create(client, name="   ", tasks=[_task("spark_sql_task")])
        assert RecordingHandler.requests == []

    def test_schedule_and_concurrency_shape_violations_fail_before_any_call(
        self, local_http_server
    ):
        client = _client(local_http_server)
        with pytest.raises(TypeError):
            _create(client, tasks=[_task("spark_sql_task")], schedule="daily")
        with pytest.raises(TypeError):
            _create(client, tasks=[_task("spark_sql_task")], max_concurrent_runs=True)
        with pytest.raises(ValueError, match="positive"):
            _create(client, tasks=[_task("spark_sql_task")], max_concurrent_runs=0)
        with pytest.raises(ValueError, match="positive"):
            _create(client, tasks=[_task("spark_sql_task")], max_concurrent_runs=-1)
        assert RecordingHandler.requests == []

    def test_the_create_envelope_ships_every_provided_field_exactly(self, local_http_server):
        _scripted({"job_id": 88})
        client = _client(local_http_server)
        schedule = {"quartz_cron_expression": "0 0 3 * * ?", "timezone_id": "UTC"}
        cluster = {
            "job_cluster_key": "default",
            "new_cluster": {"cluster_policy_id": "policy-abc", "num_workers": 1},
        }
        job_id = _create(
            client,
            name="scheduled-etl",
            tasks=[_task("spark_sql_task")],
            job_clusters=[cluster],
            schedule=schedule,
            max_concurrent_runs=3,
        )
        assert job_id == "88"
        sent = json.loads(RecordingHandler.requests[-1]["body"])
        assert sent == {
            "name": "scheduled-etl",
            "tasks": [_task("spark_sql_task")],
            "job_clusters": [cluster],
            "schedule": schedule,
            "max_concurrent_runs": 3,
        }, "the allowed envelope ships the caller's fields EXACTLY"

    def test_run_now_has_no_gate_executing_a_python_job_is_legal(self, local_http_server):
        # The allowlist governs job DEFINITIONS — a Python-task job that
        # exists (created through a flag-enabled caller) can be run.
        _scripted({"run_id": 999})
        client = _client(local_http_server)  # flag OFF — but run-now is execute-only
        assert client.run_now("42") == "999"
        recorded = RecordingHandler.requests[-1]
        assert recorded["path"] == "/api/2.1/jobs/run-now"
        assert json.loads(recorded["body"]) == {"job_id": "42"}

    def test_the_constructor_rejects_a_non_bool_flag(self, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.jobs_client import DatabricksJobsClient

        with pytest.raises(TypeError):
            DatabricksJobsClient(
                DatabricksApiClient(base_url=f"http://127.0.0.1:{local_http_server}"),
                python_tasks_enabled="yes",
            )
        assert RecordingHandler.requests == []
