"""
Databricks control-plane commands (openspec add-databricks-control-plane).

Covers /api/v1/databricks/ — the workspace registry + credentials, the
UC mirror browse, the UC change-request approval pipeline, the SQL
warehouse + job fleets, cost budgets, DLT pipelines, the ML-asset
surface, the account plane, and SSO. Every command issues the SAME
endpoint shapes the frontend surfaces use; mirror-first reads are
tenant-scoped by the backend's RLS.

The route↔command parity map is pinned by
cli/tests/unit/test_commands_databricks_parity.py (a new API route
without a CLI command fails there).
"""

import json

import click

from ..api_client import api_client
from ..output import print_json_output

# Cloud choices mirror the backend's DatabricksWorkspace cloud field.
CLOUD_CHOICES = click.Choice(["AWS", "AZURE", "GCP"], case_sensitive=True)


@click.group()
def databricks():
    """Databricks workspace registry and credentials."""


@databricks.group("workspaces")
def databricks_workspaces():
    """Workspace registration, testing, and credential rotation."""


@databricks_workspaces.command("register")
@click.option("--name", required=True, help="Workspace display name (tenant-unique)")
@click.option(
    "--host",
    required=True,
    help="Workspace host, e.g. dbc-xxxx.cloud.databricks.com (regional/gov variants allowed)",
)
@click.option("--cloud", required=True, type=CLOUD_CHOICES, help="AWS | AZURE | GCP")
@click.option("--region", required=True, help="Cloud region, e.g. us-east-1")
@click.option("--metastore-id", default=None, help="Unity Catalog metastore id")
def databricks_workspaces_register(name, host, cloud, region, metastore_id):
    """Register a BYO Databricks workspace with the control plane.

    The backend validates the host against the Databricks host-family
    allowlist and SSRF/residency rules; the workspace starts REGISTERED.
    ``--region`` is required — the serializer requires it and residency
    validation consumes it.
    """
    payload = {
        "name": name,
        "host": host,
        "cloud": cloud,
        "region": region,
    }
    if metastore_id:
        payload["metastore_id"] = metastore_id

    resp = api_client.post("databricks/workspaces/", json_data=payload)
    print_json_output(resp)


@databricks_workspaces.command("list")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_workspaces_list(output_format):
    """List registered Databricks workspaces for the current tenant."""
    data = api_client.get("databricks/workspaces/")
    if output_format == "json":
        print_json_output(data)
        return

    results = data.get("results", data) if isinstance(data, dict) else data
    items = results if isinstance(results, list) else results.get("results", [])
    if not items:
        click.echo("No Databricks workspaces registered.")
        return
    for ws in items:
        click.echo(
            f"{str(ws.get('id', '?'))[:8]:8s}  {ws.get('name', '?'):28s}  "
            f"{ws.get('host', '?'):38s}  {ws.get('status', '?')}"
        )


@databricks_workspaces.command("test")
@click.argument("workspace_id")
def databricks_workspaces_test(workspace_id):
    """Probe a workspace connection with its stored credential.

    Success moves the workspace to ACTIVE and prints the latency; failure
    surfaces the backend's MASKED reason (``DATABRICKS_AUTH_FAILED``) — the
    CLI never echoes credential material.
    """
    resp = api_client.post(f"databricks/workspaces/{workspace_id}/test/", json_data={})
    print_json_output(resp)


@databricks_workspaces.command("rotate")
@click.argument("workspace_id")
@click.argument("credential_id")
@click.option(
    "--client-secret",
    default=None,
    hide_input=False,
    help="New client secret — REQUIRED when rotating an OAuth M2M credential",
)
def databricks_workspaces_rotate(workspace_id, credential_id, client_secret):
    """Rotate a stored workspace credential.

    PAT mode: the Hub creates a replacement token via the Databricks
    token-management API and deletes the old one. M2M mode requires the
    new ``--client-secret``.
    """
    payload = {}
    if client_secret is not None:
        payload["client_secret"] = client_secret
    resp = api_client.post(
        f"databricks/workspaces/{workspace_id}/credentials/{credential_id}/rotate/",
        json_data=payload,
    )
    print_json_output(resp)


@databricks.group("uc")
def databricks_uc():
    """Unity Catalog mirror browsing (task 1.9 — `uc list`).

    Reads the RLS-scoped UC mirror through the 1.3 browse endpoints —
    catalogs, schemas, tables (and views/volumes/models via --kind).
    """


@databricks_uc.command("list")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--catalog", default=None, help="Catalog id — list its schemas")
@click.option("--schema", default=None, help="Schema id — list its objects")
@click.option(
    "--kind",
    type=click.Choice(["tables", "views", "volumes", "models"], case_sensitive=False),
    default="tables",
    help="Object kind under --schema (default: tables)",
)
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_uc_list(workspace, catalog, schema, kind, output_format):
    """List the workspace's mirrored Unity Catalog objects.

    Default: catalogs. ``--catalog`` lists schemas; ``--schema`` lists
    tables/views/volumes/models (``--kind``). All reads are mirror-first
    (the 1.3 contract) — tenant-scoped by the backend's RLS.
    """
    if schema:
        endpoint = f"databricks/workspaces/{workspace}/uc/schemas/{schema}/{kind}/"
        header = f"{kind.capitalize()} in schema {schema}:"
    elif catalog:
        endpoint = f"databricks/workspaces/{workspace}/uc/catalogs/{catalog}/schemas/"
        header = f"Schemas in catalog {catalog}:"
    else:
        endpoint = f"databricks/workspaces/{workspace}/uc/catalogs/"
        header = "Catalogs:"

    data = api_client.get(endpoint)
    if output_format == "json":
        print_json_output(data)
        return

    results = data.get("results", []) if isinstance(data, dict) else []
    if not results:
        click.echo("No objects found.")
        return
    click.echo(header)
    for row in results:
        name = row.get("name", "?")
        full = row.get("full_name") or name
        click.echo(f"  {full}")


@databricks.group("warehouses")
def databricks_warehouses():
    """SQL warehouse lifecycle (task 3.7 — `warehouses list/start/stop`).

    Mirror-first reads + the live start/stop actions through the 3.7
    endpoints; tenant-scoped by the backend's RLS.
    """


@databricks_warehouses.command("list")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_warehouses_list(workspace, output_format):
    """List the workspace's mirrored SQL warehouses."""
    data = api_client.get(f"databricks/workspaces/{workspace}/sql-warehouses/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No SQL warehouses.")
        return
    click.echo(f"{'WAREHOUSE ID':<20} {'STATE':<12} {'TYPE':<12} {'SIZE':<6} NAME")
    for row in rows:
        wtype = "serverless" if row.get("serverless") else "classic"
        size = row.get("size") or "-"
        click.echo(
            f"{row['warehouse_id']:<20} {row['state']:<12} {wtype:<12} {size:<6} {row['name']}"
        )


@databricks_warehouses.command("start")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--warehouse", required=True, help="Warehouse id (the compute API's identity)")
def databricks_warehouses_start(workspace, warehouse):
    """Start a SQL warehouse (a no-op when it is already running)."""
    resp = api_client.post(f"databricks/workspaces/{workspace}/sql-warehouses/{warehouse}/start/")
    print_json_output(resp)


@databricks_warehouses.command("stop")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--warehouse", required=True, help="Warehouse id (the compute API's identity)")
def databricks_warehouses_stop(workspace, warehouse):
    """Stop a SQL warehouse (a no-op when it is already stopped)."""
    resp = api_client.post(f"databricks/workspaces/{workspace}/sql-warehouses/{warehouse}/stop/")
    print_json_output(resp)


# ── DLT pipelines (openspec add-databricks-dlt-pipelines task 10.7) ──────
# The `dlt` commands ride the SAME API surface as the DLT page (design
# D7) — the CLI never builds a second client stack.


@databricks.group("dlt")
def databricks_dlt():
    """DLT pipeline management (the U5 surface)."""


@databricks_dlt.command("list")
@click.argument("workspace", required=True)
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_dlt_list(workspace, output_format):
    """List the workspace's mirrored DLT pipelines (mirror-first)."""
    data = api_client.get(f"databricks/workspaces/{workspace}/dlt-pipelines/")
    if output_format == "json":
        print_json_output(data)
        return

    results = data.get("results", data) if isinstance(data, dict) else data
    items = results if isinstance(results, list) else results.get("results", [])
    if not items:
        click.echo("No DLT pipelines mirrored for this workspace.")
        return
    for row in items:
        latest = row.get("latest_update_state") or "-"
        click.echo(
            f"{row.get('pipeline_id', '?')!s:20s} {row.get('state', '?')!s:10s} "
            f"{latest!s:12s} {row.get('name', '?')}"
        )


@databricks_dlt.command("create")
@click.argument("workspace", required=True)
@click.option(
    "--file",
    "settings_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the pipeline settings JSON (the 10.4 chain validates it server-side)",
)
def databricks_dlt_create(workspace, settings_file):
    """Create a DLT pipeline (the server runs the databricks.dlt.create chain)."""
    with open(settings_file, encoding="utf-8") as handle:
        settings = json.load(handle)
    if not isinstance(settings, dict):
        raise click.ClickException("the settings file must contain a JSON object")
    resp = api_client.post(f"databricks/workspaces/{workspace}/dlt-pipelines/", json_data=settings)
    print_json_output(resp)


@databricks_dlt.command("start")
@click.argument("workspace", required=True)
@click.argument("pipeline_id", required=True)
@click.option("--full-refresh", is_flag=True, help="Start a full-refresh update")
@click.option(
    "--refresh-selection",
    default=None,
    help="The selective refresh as a JSON object (the API's {tables, files} shape)",
)
def databricks_dlt_start(workspace, pipeline_id, full_refresh, refresh_selection):
    """Start an update (the server's conflict gate refuses an active update)."""
    payload = {"full_refresh": bool(full_refresh)}
    if refresh_selection is not None:
        try:
            payload["refresh_selection"] = json.loads(refresh_selection)
        except ValueError as exc:
            raise click.ClickException(f"--refresh-selection must be valid JSON ({exc})") from exc
    resp = api_client.post(
        f"databricks/workspaces/{workspace}/dlt-pipelines/{pipeline_id}/start/",
        json_data=payload,
    )
    print_json_output(resp)


@databricks_dlt.command("stop")
@click.argument("workspace", required=True)
@click.argument("pipeline_id", required=True)
def databricks_dlt_stop(workspace, pipeline_id):
    """Stop the pipeline's active update (a no-op when the pipeline is idle)."""
    resp = api_client.post(f"databricks/workspaces/{workspace}/dlt-pipelines/{pipeline_id}/stop/")
    print_json_output(resp)


@databricks_dlt.command("update")
@click.argument("workspace", required=True)
@click.argument("pipeline_id", required=True)
@click.option(
    "--file",
    "settings_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the new pipeline settings JSON (the server re-runs the 10.4 chain)",
)
def databricks_dlt_update(workspace, pipeline_id, settings_file):
    """Update a DLT pipeline's settings (PUT; the server validates)."""
    with open(settings_file, encoding="utf-8") as handle:
        settings = json.load(handle)
    if not isinstance(settings, dict):
        raise click.ClickException("the settings file must contain a JSON object")
    resp = api_client.request(
        "PUT",
        f"databricks/workspaces/{workspace}/dlt-pipelines/{pipeline_id}/",
        json_data=settings,
    )
    if not resp.ok:
        raise click.ClickException(f"Update failed: {resp.status_code} {resp.text}")
    print_json_output(resp.json())


@databricks_dlt.command("delete")
@click.argument("workspace", required=True)
@click.argument("pipeline_id", required=True)
@click.confirmation_option(prompt="Delete this DLT pipeline?")
def databricks_dlt_delete(workspace, pipeline_id):
    """Delete a DLT pipeline (the server's guard refuses an active update)."""
    resp = api_client.delete(f"databricks/workspaces/{workspace}/dlt-pipelines/{pipeline_id}/")
    print_json_output(resp)


# ── UC browse extras (task 1.3) — external locations, storage
# credentials, and table detail ride the same mirror-first contract as
# `uc list`.


@databricks_uc.command("external-locations")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_uc_external_locations(workspace, output_format):
    """List the workspace's mirrored UC external locations."""
    data = api_client.get(f"databricks/workspaces/{workspace}/uc/external-locations/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No external locations mirrored.")
        return
    click.echo("External locations:")
    for row in rows:
        click.echo(f"  {row.get('name', '?')} — {row.get('url', '?')}")


@databricks_uc.command("storage-credentials")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_uc_storage_credentials(workspace, output_format):
    """List the workspace's mirrored UC storage credentials (metadata only —
    the backend never returns credential material)."""
    data = api_client.get(f"databricks/workspaces/{workspace}/uc/storage-credentials/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No storage credentials mirrored.")
        return
    click.echo("Storage credentials:")
    for row in rows:
        click.echo(f"  {row.get('name', '?')}")


@databricks_uc.command("table")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--table", "table_id", required=True, help="Table id (uuid)")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_uc_table(workspace, table_id, output_format):
    """Show a mirrored UC table's detail (columns + metadata)."""
    data = api_client.get(f"databricks/workspaces/{workspace}/uc/tables/{table_id}/")
    if output_format == "json":
        print_json_output(data)
        return
    columns = (data or {}).get("columns") if isinstance(data, dict) else None
    if not columns:
        print_json_output(data)
        return
    click.echo(f"{data.get('name', table_id)} ({data.get('data_source_format', '?')}):")
    for column in columns:
        click.echo(f"  {column.get('name', '?'):24s} {column.get('type_text', '?')}")


# ── UC change-request approval pipeline (task 2.8 — the U4 surface) ─────


@databricks_uc.group("changes")
def databricks_uc_changes():
    """UC change-request approval pipeline (submit → approve/reject)."""


@databricks_uc_changes.command("list")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_uc_changes_list(workspace, output_format):
    """List the workspace's UC change requests."""
    data = api_client.get(f"databricks/workspaces/{workspace}/uc/changes/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No UC change requests.")
        return
    click.echo(f"{'CHANGE ID':<36} {'TYPE':<12} {'STATUS':<22} SECURABLE")
    for row in rows:
        change_id = str(row.get("id", "?"))[:36]
        click.echo(
            f"{change_id:<36} {row.get('change_type', '?'):<12} "
            f"{row.get('status', '?'):<22} {row.get('securable_type', '?')}"
        )


@databricks_uc_changes.command("inbox")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_uc_changes_inbox(output_format):
    """List the cross-workspace approver inbox (pending approvals)."""
    data = api_client.get("databricks/uc/changes/pending-approvals/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No pending approvals.")
        return
    click.echo(f"{'CHANGE ID':<36} {'WORKSPACE':<38} {'REQUESTED BY':<24}")
    for row in rows:
        change_id = str(row.get("id", "?"))[:36]
        workspace = str(row.get("workspace", "?"))[:38]
        click.echo(f"{change_id:<36} {workspace:<38} {row.get('requested_by', '?')}")


@databricks_uc_changes.command("show")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--change", "change_id", required=True, help="Change-request id (uuid)")
def databricks_uc_changes_show(workspace, change_id):
    """Show one UC change request (status, definition, approval workflow)."""
    data = api_client.get(f"databricks/workspaces/{workspace}/uc/changes/{change_id}/")
    print_json_output(data)


@databricks_uc_changes.command("create")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option(
    "--file",
    "payload_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the change-request JSON {change_type, securable_type, definition} "
    "(the 2.4 guards validate it server-side)",
)
def databricks_uc_changes_create(workspace, payload_file):
    """Create a UC change request (DRAFT; submit moves it to approval)."""
    with open(payload_file, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise click.ClickException("the payload file must contain a JSON object")
    resp = api_client.post(f"databricks/workspaces/{workspace}/uc/changes/", json_data=payload)
    print_json_output(resp)


@databricks_uc_changes.command("submit")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--change", "change_id", required=True, help="Change-request id (uuid)")
def databricks_uc_changes_submit(workspace, change_id):
    """Submit a DRAFT change request for approval."""
    resp = api_client.post(f"databricks/workspaces/{workspace}/uc/changes/{change_id}/submit/")
    print_json_output(resp)


@databricks_uc_changes.command("approve")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--change", "change_id", required=True, help="Change-request id (uuid)")
def databricks_uc_changes_approve(workspace, change_id):
    """Approve a pending change request (advances the approval chain)."""
    resp = api_client.post(f"databricks/workspaces/{workspace}/uc/changes/{change_id}/approve/")
    print_json_output(resp)


@databricks_uc_changes.command("reject")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--change", "change_id", required=True, help="Change-request id (uuid)")
@click.option("--reason", default=None, help="Rejection reason (recorded on the request)")
def databricks_uc_changes_reject(workspace, change_id, reason):
    """Reject a pending change request."""
    payload = {"reason": reason} if reason else {}
    resp = api_client.post(
        f"databricks/workspaces/{workspace}/uc/changes/{change_id}/reject/", json_data=payload
    )
    print_json_output(resp)


@databricks_uc_changes.command("timeline")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--change", "change_id", required=True, help="Change-request id (uuid)")
def databricks_uc_changes_timeline(workspace, change_id):
    """Show the change request's audit timeline."""
    data = api_client.get(f"databricks/workspaces/{workspace}/uc/changes/{change_id}/timeline/")
    print_json_output(data)


@databricks_uc_changes.command("comment")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--change", "change_id", required=True, help="Change-request id (uuid)")
@click.option("--text", required=True, help="Comment body")
def databricks_uc_changes_comment(workspace, change_id, text):
    """Add a comment to a change request."""
    resp = api_client.post(
        f"databricks/workspaces/{workspace}/uc/changes/{change_id}/comments/",
        json_data={"body": text},
    )
    print_json_output(resp)


# ── Job-fleet reads (task 4.5) ───────────────────────────────────────────


@databricks.group("jobs")
def databricks_jobs():
    """Job-fleet reads (the 4.5 mirror)."""


@databricks_jobs.command("list")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_jobs_list(workspace, output_format):
    """List the workspace's mirrored jobs."""
    data = api_client.get(f"databricks/workspaces/{workspace}/jobs/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No jobs mirrored for this workspace.")
        return
    click.echo(f"{'JOB ID':<22} {'NAME':<36} {'SCHEDULE':<16} {'STATE':<14}")
    for row in rows:
        schedule = row.get("schedule") or {}
        cron = schedule.get("quartz_cron_expression", "-") if isinstance(schedule, dict) else "-"
        click.echo(
            f"{row.get('job_id', '?')!s:<22} {str(row.get('name', '?'))[:36]:<36} "
            f"{str(cron)[:16]:<16} {row.get('state', '?'):<14}"
        )


@databricks_jobs.command("runs")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--job", "job_id", required=True, help="Job id (the compute API's identity)")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_jobs_runs(workspace, job_id, output_format):
    """List a job's mirrored runs."""
    data = api_client.get(f"databricks/workspaces/{workspace}/jobs/{job_id}/runs/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No runs mirrored for this job.")
        return
    click.echo(f"{'RUN ID':<22} {'LIFECYCLE':<16} {'RESULT':<12} STARTED")
    for row in rows:
        click.echo(
            f"{row.get('run_id', '?')!s:<22} {row.get('lifecycle_state', '?'):<16} "
            f"{row.get('result_state', '-')!s:<12} {row.get('start_time', '?')}"
        )


# ── Cost budgets (task 7.6 — the U9 budget page) ─────────────────────────


@databricks.group("budgets")
def databricks_budgets():
    """Databricks cost budgets (tenant-scoped)."""


@databricks_budgets.command("list")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_budgets_list(output_format):
    """List the tenant's budget rows with rolling progress."""
    data = api_client.get("databricks/budgets/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No cost budgets configured.")
        return
    click.echo(f"{'SCOPE':<30} {'CONSUMED':<10} {'BUDGET':<10} MODE")
    for row in rows:
        click.echo(
            f"{str(row.get('scope', '?'))[:30]:<30} {row.get('consumed', '?')!s:<10} "
            f"{row.get('budget_amount', '?')!s:<10} {row.get('mode', '?')}"
        )


# ── ML assets (openspec add-databricks-ml-assets 12.x — the U12 page) ────


@databricks.group("ml")
def databricks_ml():
    """Unity Catalog ML assets (models, feature tables, serving endpoints)."""


@databricks_ml.command("models")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_ml_models(workspace, output_format):
    """List the workspace's mirrored ML models."""
    data = api_client.get(f"databricks/workspaces/{workspace}/ml-assets/models/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No ML models mirrored.")
        return
    click.echo(f"{'MODEL ID':<38} {'FULL NAME':<48} OWNER")
    for row in rows:
        model_id = str(row.get("id", "?"))[:38]
        click.echo(
            f"{model_id:<38} {str(row.get('full_name', '?'))[:48]:<48} {row.get('owner', '?')}"
        )


@databricks_ml.command("register-model")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option(
    "--file",
    "payload_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the register-model JSON (name, catalog, schema — the server validates)",
)
def databricks_ml_register_model(workspace, payload_file):
    """Register an ML model in the workspace's Unity Catalog."""
    with open(payload_file, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise click.ClickException("the payload file must contain a JSON object")
    resp = api_client.post(
        f"databricks/workspaces/{workspace}/ml-assets/models/", json_data=payload
    )
    print_json_output(resp)


@databricks_ml.command("log-version")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--model", "model_id", required=True, help="Model id (uuid)")
@click.option(
    "--file",
    "payload_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the log-version JSON (version, source, run — the server validates)",
)
def databricks_ml_log_version(workspace, model_id, payload_file):
    """Log a new version for a registered model."""
    with open(payload_file, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise click.ClickException("the payload file must contain a JSON object")
    resp = api_client.post(
        f"databricks/workspaces/{workspace}/ml-assets/models/{model_id}/versions/",
        json_data=payload,
    )
    print_json_output(resp)


@databricks_ml.group("alias")
def databricks_ml_alias():
    """Model alias management (champion/challenger)."""


@databricks_ml_alias.command("set")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--model", "model_id", required=True, help="Model id (uuid)")
@click.option("--alias", required=True, help="Alias name (e.g. champion)")
@click.option("--version-num", required=True, type=int, help="Model version the alias points at")
def databricks_ml_alias_set(workspace, model_id, alias, version_num):
    """Point an alias at a model version."""
    resp = api_client.request(
        "PUT",
        f"databricks/workspaces/{workspace}/ml-assets/models/{model_id}/aliases/{alias}/",
        json_data={"version_num": version_num},
    )
    if not resp.ok:
        raise click.ClickException(f"Alias set failed: {resp.status_code} {resp.text}")
    print_json_output(resp.json())


@databricks_ml_alias.command("remove")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--model", "model_id", required=True, help="Model id (uuid)")
@click.option("--alias", required=True, help="Alias name")
def databricks_ml_alias_remove(workspace, model_id, alias):
    """Remove an alias from a model."""
    resp = api_client.delete(
        f"databricks/workspaces/{workspace}/ml-assets/models/{model_id}/aliases/{alias}/"
    )
    print_json_output(resp)


@databricks_ml.command("feature-tables")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_ml_feature_tables(workspace, output_format):
    """List the workspace's feature-store-tagged tables."""
    data = api_client.get(f"databricks/workspaces/{workspace}/ml-assets/feature-tables/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No feature tables tagged.")
        return
    click.echo("Feature tables:")
    for row in rows:
        click.echo(f"  {row.get('full_name', row.get('name', '?'))}")


@databricks_ml.group("feature-tag")
def databricks_ml_feature_tag():
    """Feature-store tag management (mark/unmark tables)."""


@databricks_ml_feature_tag.command("mark")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--table", "table_id", required=True, help="Table id (uuid)")
def databricks_ml_feature_tag_mark(workspace, table_id):
    """Tag a table as a feature table."""
    resp = api_client.post(
        f"databricks/workspaces/{workspace}/ml-assets/tables/{table_id}/feature-tag/"
    )
    print_json_output(resp)


@databricks_ml_feature_tag.command("unmark")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--table", "table_id", required=True, help="Table id (uuid)")
def databricks_ml_feature_tag_unmark(workspace, table_id):
    """Remove the feature-table tag from a table."""
    resp = api_client.delete(
        f"databricks/workspaces/{workspace}/ml-assets/tables/{table_id}/feature-tag/"
    )
    print_json_output(resp)


@databricks_ml.group("serving-endpoints")
def databricks_ml_serving_endpoints():
    """Model serving endpoints."""


@databricks_ml_serving_endpoints.command("list")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_ml_serving_endpoints_list(workspace, output_format):
    """List the workspace's serving endpoints."""
    data = api_client.get(f"databricks/workspaces/{workspace}/ml-assets/serving-endpoints/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No serving endpoints.")
        return
    click.echo("Serving endpoints:")
    for row in rows:
        click.echo(f"  {row.get('name', '?')} — {row.get('state', '?')}")


@databricks_ml_serving_endpoints.command("create")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option(
    "--file",
    "payload_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the serving-endpoint JSON (name, config — the server validates)",
)
def databricks_ml_serving_endpoints_create(workspace, payload_file):
    """Create a model serving endpoint."""
    with open(payload_file, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise click.ClickException("the payload file must contain a JSON object")
    resp = api_client.post(
        f"databricks/workspaces/{workspace}/ml-assets/serving-endpoints/", json_data=payload
    )
    print_json_output(resp)


@databricks_ml_serving_endpoints.command("delete")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--name", required=True, help="Serving endpoint name")
@click.confirmation_option(prompt="Delete this serving endpoint?")
def databricks_ml_serving_endpoints_delete(workspace, name):
    """Delete a serving endpoint."""
    resp = api_client.delete(
        f"databricks/workspaces/{workspace}/ml-assets/serving-endpoints/{name}/"
    )
    print_json_output(resp)


@databricks_ml.group("vector-endpoints")
def databricks_ml_vector_endpoints():
    """Vector search endpoints."""


@databricks_ml_vector_endpoints.command("list")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_ml_vector_endpoints_list(workspace, output_format):
    """List the workspace's vector search endpoints."""
    data = api_client.get(f"databricks/workspaces/{workspace}/ml-assets/vector-search-endpoints/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No vector search endpoints.")
        return
    click.echo("Vector search endpoints:")
    for row in rows:
        click.echo(f"  {row.get('name', '?')} — {row.get('state', '?')}")


@databricks_ml_vector_endpoints.command("create")
@click.option("--workspace", required=True, help="Workspace id (uuid)")
@click.option(
    "--file",
    "payload_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the vector-endpoint JSON (name, config — the server validates)",
)
def databricks_ml_vector_endpoints_create(workspace, payload_file):
    """Create a vector search endpoint."""
    with open(payload_file, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise click.ClickException("the payload file must contain a JSON object")
    resp = api_client.post(
        f"databricks/workspaces/{workspace}/ml-assets/vector-search-endpoints/",
        json_data=payload,
    )
    print_json_output(resp)


# ── Account plane (openspec add-databricks-account-plane 8.x) ────────────


@databricks.group("accounts")
def databricks_accounts():
    """Databricks account plane (accounts + the estate summary)."""


@databricks_accounts.command("list")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_accounts_list(output_format):
    """List the tenant's Databricks accounts."""
    data = api_client.get("databricks/accounts/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No Databricks accounts.")
        return
    click.echo(f"{'ACCOUNT ID':<26} {'STATUS':<16} NAME")
    for row in rows:
        click.echo(
            f"{row.get('account_id', '?')!s:<26} {row.get('status', '?'):<16} {row.get('name', '?')}"
        )


@databricks_accounts.command("create")
@click.option(
    "--file",
    "payload_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the account JSON (account_id, credentials — the server validates)",
)
def databricks_accounts_create(payload_file):
    """Register a Databricks account (the server runs the provisioning
    pre-flight)."""
    with open(payload_file, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise click.ClickException("the payload file must contain a JSON object")
    resp = api_client.post("databricks/accounts/", json_data=payload)
    print_json_output(resp)


@databricks_accounts.command("metastores")
@click.option("--account", "account_id", required=True, help="Account id")
@click.option(
    "--file",
    "payload_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Optional metastore JSON (name, region — the server validates)",
)
def databricks_accounts_metastores(account_id, payload_file):
    """Create a metastore under the account."""
    payload = {}
    if payload_file:
        with open(payload_file, encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise click.ClickException("the payload file must contain a JSON object")
    resp = api_client.post(f"databricks/accounts/{account_id}/metastores/", json_data=payload)
    print_json_output(resp)


@databricks_accounts.command("provision-workspace")
@click.option("--account", "account_id", required=True, help="Account id")
@click.option(
    "--file",
    "payload_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Optional workspace JSON (name, region — the server validates)",
)
def databricks_accounts_provision_workspace(account_id, payload_file):
    """Provision a workspace under the account."""
    payload = {}
    if payload_file:
        with open(payload_file, encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise click.ClickException("the payload file must contain a JSON object")
    resp = api_client.post(f"databricks/accounts/{account_id}/workspaces/", json_data=payload)
    print_json_output(resp)


@databricks_accounts.command("estate")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_accounts_estate(output_format):
    """Show the account-plane estate summary."""
    data = api_client.get("databricks/estate-summary/")
    if output_format == "json":
        print_json_output(data)
        return
    print_json_output(data)


# ── SSO (openspec add-databricks-sso-obo 8.x) — the browser flow's
# CLI-visible surfaces: the login URL and the session state. The OAuth
# callback itself is a browser redirect flow — not a CLI command.


@databricks.group("sso")
def databricks_sso():
    """Databricks SSO (login URL + session state)."""


@databricks_sso.command("workspaces")
@click.option("--tenant", "tenant_id", required=True, help="Tenant id")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_sso_workspaces(tenant_id, output_format):
    """List the tenant's SSO-enabled workspaces.

    The SSO surface is AllowAny — the backend resolves the tenant
    EXPLICITLY from the query string (no request.tenant exists there),
    so the tenant id is a required option.
    """
    data = api_client.get("databricks/sso/workspaces/", params={"tenant_id": tenant_id})
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No SSO-enabled workspaces.")
        return
    click.echo("SSO-enabled workspaces:")
    for row in rows:
        click.echo(f"  {row.get('workspace_id', '?')}")


@databricks_sso.command("login-url")
@click.option("--workspace", "workspace_id", required=True, help="Workspace id (uuid)")
@click.option("--tenant", "tenant_id", required=True, help="Tenant id")
def databricks_sso_login_url(workspace_id, tenant_id):
    """Print the SSO login URL (open it in a browser; the callback
    completes the flow server-side)."""
    data = api_client.get(
        "databricks/sso/login-url/",
        params={"tenant_id": tenant_id, "workspace_id": workspace_id},
    )
    print_json_output(data)


@databricks_sso.command("session")
def databricks_sso_session():
    """Show the current user's Databricks SSO session state."""
    data = api_client.get("databricks/sso/session/")
    print_json_output(data)


# ── Workspace registry extras — credentials + soft-delete ────────────────


@databricks_workspaces.group("credentials")
def databricks_workspaces_credentials():
    """Stored workspace credentials (metadata only — secrets never leave
    the backend)."""


@databricks_workspaces_credentials.command("list")
@click.argument("workspace_id")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def databricks_workspaces_credentials_list(workspace_id, output_format):
    """List a workspace's stored credentials (auth mode + status only)."""
    data = api_client.get(f"databricks/workspaces/{workspace_id}/credentials/")
    if output_format == "json":
        print_json_output(data)
        return
    rows = (data or {}).get("results", []) if isinstance(data, dict) else []
    if not rows:
        click.echo("No credentials stored for this workspace.")
        return
    click.echo(f"{'CREDENTIAL ID':<38} {'AUTH MODE':<14} STATUS")
    for row in rows:
        cred_id = str(row.get("id", "?"))[:38]
        click.echo(f"{cred_id:<38} {row.get('auth_mode', '?'):<14} {row.get('status', '?')}")


@databricks_workspaces_credentials.command("add")
@click.argument("workspace_id")
@click.option(
    "--file",
    "payload_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the credential JSON (auth_mode + config — the server "
    "encrypts the config; it is never echoed back)",
)
def databricks_workspaces_credentials_add(workspace_id, payload_file):
    """Store a new credential for a workspace."""
    with open(payload_file, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise click.ClickException("the payload file must contain a JSON object")
    resp = api_client.post(f"databricks/workspaces/{workspace_id}/credentials/", json_data=payload)
    print_json_output(resp)


@databricks_workspaces.command("delete")
@click.argument("workspace_id")
@click.confirmation_option(prompt="Delete this workspace registration?")
def databricks_workspaces_delete(workspace_id):
    """Soft-delete a workspace registration (the backend decommissions the
    stored credentials and stops the mirrors)."""
    resp = api_client.delete(f"databricks/workspaces/{workspace_id}/")
    print_json_output(resp)
