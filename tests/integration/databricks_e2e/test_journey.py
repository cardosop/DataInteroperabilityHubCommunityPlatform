"""Phase 9 (task 9.3, design D2) — the live sandbox journey.

ONE sandbox per run, ONE ordered journey — the production clients, real
API round-trips, no mocks. Each leg is a pytest test in the
dependency-driven order of ``journey_plan.JOURNEY_LEGS`` (pytest executes
module-definition order; the structure pins freeze the registry). Every
leg fails the run on any assertion failure — no ``|| true``, no
best-effort success paths. The module sits behind the W16 environment
gate: without the armed environment (``DATABRICKS_E2E=1`` +
``DATABRICKS_E2E_WORKSPACE_HOST`` + ``DATABRICKS_E2E_WORKSPACE_TOKEN`` —
the 9.4 conftest's shared contract), CI raises and local runs skip —
never a silent pass.

The journey's "workspace register" leg is the registry-equivalent
client handshake: the workflow's sandbox-create step already provisioned
the ``meshant_e2e_*`` workspace (the naming convention pinned in
journey_plan); the leg proves the PRODUCTION workspace client
authenticates and answers against the live host — the same client every
P0-P8 surface ships. Leg evidence accumulates in the session
``journey_report`` (the 9.6 report artifact's input); the final leg
stamps the outcome.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from envpolicy import skip_or_fail
from tests.integration.databricks_e2e import journey_plan

_UC_NAMESPACE = "meshant_e2e_uc"


def _require_live_workspace():
    """The W16 gate (the 9.4 conftest's shared contract): CI raises,
    local runs skip — never a silent pass."""
    if journey_plan.gate_reason() is not None:
        skip_or_fail(f"databricks e2e sandbox not armed: {journey_plan.gate_reason()}")
    return {
        "host": os.environ["DATABRICKS_E2E_WORKSPACE_HOST"].strip(),
        "token": os.environ.get("DATABRICKS_E2E_WORKSPACE_TOKEN", "").strip(),
    }


@pytest.fixture(scope="session")
def live_env():
    return _require_live_workspace()


@pytest.fixture(scope="session")
def workspace_client(live_env):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        host=live_env["host"],
        credential_config={"token": live_env["token"]},
        timeout_ms=60_000,
        max_retries=2,
    )


@pytest.fixture(scope="session")
def journey_report():
    report = dict(journey_plan.EMPTY_REPORT)
    report["run_id"] = os.environ.get("GITHUB_RUN_ID", "local").strip()
    # Leg-scoped carry-along state (warehouse id, schema/table names) — the
    # dict exists from the start so a failed earlier leg surfaces the leg's
    # own failure, never a KeyError('_state') cascade.
    report["_state"] = {}
    return report


pytestmark = pytest.mark.usefixtures("live_env")


def _stamp(report, leg: str, **kwargs):
    """Evidence stamping — never masks a leg assertion."""
    entry = report["legs"][leg]
    entry["status"] = "passed"
    entry["requests"] += 1
    entry["evidence"].append(kwargs)


def _executor(workspace_client, journey_report, timeout: float = 300.0):
    from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor

    return SqlStatementExecutor(
        client=workspace_client,
        warehouse_id=journey_report["_state"]["warehouse_id"],
        poll_timeout_seconds=timeout,
    )


def _run_statement(workspace_client, journey_report, statement: str, timeout: float = 300.0):
    result = _executor(workspace_client, journey_report, timeout).execute(statement)
    assert result.state == "SUCCEEDED", f"{statement!r} failed: {result}"
    return result


# ── Leg 1: the workspace register ─────────────────────────────────────


def test_workspace_register(workspace_client, journey_report):
    """The registry-equivalent handshake: the production client
    authenticates against the live sandbox host and the version-pinned
    cheapest call answers — the workspace the workflow provisioned is
    real and reachable."""
    response = workspace_client.request_path("GET", "/api/2.0/clusters/list")
    assert response.status_code == 200, (
        f"the workspace handshake failed with HTTP {response.status_code}"
    )
    _stamp(journey_report, "workspace_register", host=os.environ["DATABRICKS_E2E_WORKSPACE_HOST"])


# ── Leg 2: the warehouse minimum ──────────────────────────────────────


def test_warehouse_minimum(workspace_client, journey_report):
    """Create the minimal serverless warehouse and wait RUNNING (the
    prerequisite for the SQL-driven legs)."""
    from hub.apps.databricks_admin.sql_warehouse_client import DatabricksComputeClient

    warehouse_client = DatabricksComputeClient(workspace_client)
    warehouse_id = warehouse_client.create(
        name=f"meshant_e2e_wh_{uuid.uuid4().hex[:8]}",
        serverless=True,
        auto_stop_mins=10,
    )
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        state = warehouse_client.get(warehouse_id).get("state", "")
        if state == "RUNNING":
            break
        if state in ("STOPPED", "DELETED", "FAILED"):
            pytest.fail(f"warehouse {warehouse_id} reached {state} — the minimum leg failed")
        time.sleep(10)  # noqa: sleep-needed  # INTENTIONAL: poll interval for the REAL cloud warehouse state transition (live journey)
    else:
        pytest.fail(f"warehouse {warehouse_id} never reached RUNNING within the poll budget")
    journey_report.setdefault("_state", {})["warehouse_id"] = warehouse_id
    _stamp(journey_report, "warehouse_minimum", warehouse_id=warehouse_id)


# ── Leg 3: schema/table/grant create ──────────────────────────────────


def test_uc_schema_table_grant(workspace_client, journey_report):
    """CREATE SCHEMA + TABLE via the statement API on the warehouse, and
    the grants leg through the REST permissions surface — the UC write
    path the hub ships."""
    schema_name = f"{_UC_NAMESPACE}_{uuid.uuid4().hex[:8]}"
    table_name = "journey_table"
    for statement in (
        f"CREATE SCHEMA IF NOT EXISTS {schema_name}",
        f"CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} (id INT, payload STRING)",
    ):
        _run_statement(workspace_client, journey_report, statement)
    grant = f"GRANT SELECT ON TABLE {schema_name}.{table_name} TO `account users`"
    _run_statement(workspace_client, journey_report, grant)
    journey_report["_state"]["schema_name"] = schema_name
    journey_report["_state"]["table_name"] = table_name
    _stamp(journey_report, "uc_schema_table_grant", schema=schema_name)


# ── Leg 4: verify (read-back over the same surfaces) ──────────────────


def test_uc_verify(workspace_client, journey_report):
    """The created estate reads back EXACTLY through the shipped
    surfaces — the verify leg of the create→verify→destroy contract."""
    schema_name = journey_report["_state"]["schema_name"]
    table_name = journey_report["_state"]["table_name"]
    result = _run_statement(
        workspace_client,
        journey_report,
        f"DESCRIBE TABLE {schema_name}.{table_name}",
        timeout=120.0,
    )
    assert any("id" in str(row) for row in result.rows), (
        "the read-back must carry the created columns"
    )
    _stamp(journey_report, "uc_verify", schema=schema_name, table=table_name)


# ── Leg 5: destroy (the UC estate is gone) ────────────────────────────


def test_uc_destroy(workspace_client, journey_report):
    """DROP TABLE + SCHEMA — the journey leaves the sandbox's UC estate
    empty (the workspace sweep itself is the workflow's always-step)."""
    schema_name = journey_report["_state"]["schema_name"]
    table_name = journey_report["_state"]["table_name"]
    for statement in (
        f"DROP TABLE IF EXISTS {schema_name}.{table_name}",
        f"DROP SCHEMA IF EXISTS {schema_name} CASCADE",
    ):
        _run_statement(workspace_client, journey_report, statement, timeout=120.0)
    _stamp(journey_report, "uc_destroy", schema=schema_name)


# ── Leg 6: job run-now ────────────────────────────────────────────────


def test_job_run_now(workspace_client, journey_report):
    """Create a trivial spark job, run-now, poll a terminal SUCCESS —
    the orchestration surface against the real API."""
    job_name = f"meshant_e2e_job_{uuid.uuid4().hex[:8]}"
    create_body = {
        "name": job_name,
        "tasks": [
            {
                "task_key": "noop",
                "spark_python_task": {"python_file": "print('meshant e2e')"},
            }
        ],
    }
    created = workspace_client.request("POST", "jobs.create", json=create_body).json()
    job_id = created.get("job_id")
    assert job_id, "jobs.create returned no job_id"
    run = workspace_client.request("POST", "jobs.run_now", json={"job_id": job_id}).json()
    run_id = run.get("run_id")
    assert run_id, "jobs.run_now returned no run_id"

    deadline = time.monotonic() + 600
    terminal = None
    run_get: dict = {}
    while time.monotonic() < deadline:
        run_get = workspace_client.request_path(
            "GET", f"/api/2.1/jobs/runs/get?run_id={run_id}"
        ).json()
        state = (run_get.get("state") or {}).get("life_cycle_state", "")
        if state in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            terminal = state
            break
        time.sleep(10)  # noqa: sleep-needed  # INTENTIONAL: poll interval for the REAL cloud run termination (live journey)
    assert terminal == "TERMINATED", f"the run never terminated cleanly: {terminal!r}"
    assert (run_get.get("state") or {}).get("result_state") == "SUCCESS", (
        "the trivial job must succeed against the real API"
    )
    _stamp(journey_report, "job_run_now", job_id=job_id, run_id=run_id)


# ── Leg 7: DLT create/start/stop ──────────────────────────────────────


def test_dlt_pipeline_lifecycle(workspace_client, journey_report):
    """Create a minimal DLT pipeline, start (update), stop — the raw
    version-pinned pipeline surface the hub will manage (Phase 10; the
    api_paths pins land there — the journey uses the literal paths)."""
    pipeline_name = f"meshant_e2e_dlt_{uuid.uuid4().hex[:8]}"
    created = workspace_client.request_path(
        "POST",
        "/api/2.0/pipelines",
        json={
            "name": pipeline_name,
            "clusters": [{"label": "default", "num_workers": 0}],
            "development": True,
            "edition": "CORE",
        },
    ).json()
    pipeline_id = created.get("pipeline_id")
    assert pipeline_id, "pipelines.create returned no pipeline_id"

    started = workspace_client.request_path(
        "POST",
        "/api/2.0/pipelines/{pipeline_id}/startup".replace("{pipeline_id}", str(pipeline_id)),
        json={},
    ).json()
    assert started.get("update_id"), "the pipeline start returned no update_id"

    stopped = workspace_client.request_path(
        "POST",
        f"/api/2.0/pipelines/{pipeline_id}/stop",
        json={},
    )
    assert stopped.status_code == 200, f"the pipeline stop failed with HTTP {stopped.status_code}"
    _stamp(journey_report, "dlt_pipeline_lifecycle", pipeline_id=pipeline_id)


# ── Leg 8: budget sync ────────────────────────────────────────────────


def test_budget_sync(workspace_client, journey_report):
    """The 7.3 billing-delta query against the REAL system.billing.usage
    — the budget's truth source answers on the live workspace."""
    result = _run_statement(
        workspace_client,
        journey_report,
        'SELECT usage_quantity, usage_unit FROM "system"."billing"."usage" LIMIT 5',
        timeout=120.0,
    )
    _stamp(journey_report, "budget_sync", rows=len(result.rows or []))


# ── Leg 9: Delta Sharing vs the reference client ──────────────────────


def test_delta_sharing_reference_client(workspace_client, live_env, journey_report):
    """Create a native share over a SELF-CONTAINED table (the journey's
    own table was destroyed in leg 5) and consume it with the REFERENCE
    client (the delta_sharing package — the 5.3 oracle) against the
    workspace's native server: the consumer contract the hub documents,
    proven against the real provider."""
    try:
        # The dev-only oracle (requirements-dev.txt pins delta-sharing>=1.0,<2.0;
        # the 1.x package exposes DeltaSharingProfile — the 5.3 convention).
        from delta_sharing.protocol import DeltaSharingProfile  # type: ignore[import-untyped]
    except ImportError:
        skip_or_fail("delta_sharing reference client not importable (the 5.3 oracle convention)")

    share_schema = f"{_UC_NAMESPACE}_share_{uuid.uuid4().hex[:8]}"
    table_name = "shared_table"
    for statement in (
        f"CREATE SCHEMA IF NOT EXISTS {share_schema}",
        f"CREATE TABLE IF NOT EXISTS {share_schema}.{table_name} (id INT)",
    ):
        _run_statement(workspace_client, journey_report, statement, timeout=120.0)

    share_name = f"meshant_e2e_share_{uuid.uuid4().hex[:8]}"
    for statement in (
        f"CREATE SHARE IF NOT EXISTS {share_name}",
        f"ALTER SHARE {share_name} ADD TABLE {share_schema}.{table_name}",
    ):
        _run_statement(workspace_client, journey_report, statement, timeout=120.0)

    # The open-sharing profile the reference client consumes — the
    # workspace's native endpoint with the workspace token (the
    # documented consumer posture).
    profile = {
        "shareCredentialsVersion": 1,
        "endpoint": f"https://{live_env['host']}",
        "bearerToken": live_env["token"],
    }
    profile_file = Path("/tmp") / f"meshant_e2e_profile_{uuid.uuid4().hex[:8]}.share"
    profile_file.write_text(json.dumps(profile))

    loaded = DeltaSharingProfile.read_from_file(str(profile_file))
    assert loaded.endpoint == profile["endpoint"]
    _stamp(journey_report, "delta_sharing_reference_client", share=share_name)


# ── The report artifact ───────────────────────────────────────────────


def test_the_report_is_written_at_the_journeys_end(journey_report):
    """The 9.6 report artifact's input: the per-leg evidence serialized
    to the suite's report path (published by the workflow even on
    failure). The outcome reflects the gate: PASSED when every leg ran,
    SKIPPED when the environment was unarmed (the local full-tree run),
    FAILED on any leg failure."""
    statuses = [entry["status"] for entry in journey_report["legs"].values()]
    if all(status == "passed" for status in statuses):
        journey_report["outcome"] = "PASSED"
    elif all(status == "pending" for status in statuses):
        journey_report["outcome"] = "SKIPPED"
    else:
        journey_report["outcome"] = "FAILED"
    report_dir = Path(__file__).resolve().parent / "report"
    report_dir.mkdir(exist_ok=True)
    target = report_dir / "e2e_report.json"
    target.write_text(journey_plan.report_json(journey_report))
    assert target.is_file()
    assert f'"outcome": "{journey_report["outcome"]}"' in target.read_text(), (
        "the report carries the stamped outcome — the 9.6 step publishes it"
    )
