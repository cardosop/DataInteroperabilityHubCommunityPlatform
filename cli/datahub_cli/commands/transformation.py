"""
Transformation pipeline management commands (Phase 118E).

Provides CLI commands for managing transformation pipelines
and their execution runs.
"""

import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def transformation():
    """Transformation pipeline management commands"""
    pass


# ── Pipelines ────────────────────────────────────────────


@transformation.group("pipelines")
def pipelines():
    """Manage transformation pipelines"""
    pass


@pipelines.command("list")
@click.option("--status", help="Filter by status")
@click.option("--limit", type=int, default=20)
@click.option("--offset", type=int, default=0)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def list_pipelines(
    status: Optional[str], limit: int, offset: int,
    output_format: str,
):
    """List transformation pipelines"""
    params = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status

    try:
        data = api_client.get(
            "transformation/pipelines/", params=params,
        )
        results = (
            data.get("results", [])
            if isinstance(data, dict) else
            data if isinstance(data, list) else []
        )

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No pipelines found.")
                return
            click.echo(
                f"{'ID':<40} {'Name':<30} "
                f"{'Status':<12} {'Updated':<25}"
            )
            click.echo("-" * 107)
            for p in results:
                if not isinstance(p, dict):
                    continue
                click.echo(
                    f"{str(p.get('id', ''))[:36]:<40} "
                    f"{str(p.get('name', ''))[:28]:<30} "
                    f"{str(p.get('status', '')):<12} "
                    f"{str(p.get('updated_at', ''))[:23]:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to list pipelines: {e}"
        )


@pipelines.command("get")
@click.argument("pipeline_id")
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def get_pipeline(pipeline_id: str, output_format: str):
    """Get pipeline details"""
    try:
        data = api_client.get(
            f"transformation/pipelines/{pipeline_id}/",
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Name: {data.get('name')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(
                f"Description: "
                f"{data.get('description', 'N/A')}"
            )
            if data.get("config"):
                click.echo(
                    f"Config: "
                    f"{json.dumps(data.get('config'))}"
                )
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to get pipeline: {e}"
        )


@pipelines.command("create")
@click.option("--name", required=True, help="Pipeline name")
@click.option("--description", help="Description")
@click.option(
    "--config", "config_json",
    help="Pipeline config as JSON string",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def create_pipeline(
    name: str,
    description: Optional[str],
    config_json: Optional[str],
    output_format: str,
):
    """Create a transformation pipeline"""
    payload = {"name": name}
    if description:
        payload["description"] = description
    if config_json:
        payload["config"] = json.loads(config_json)

    try:
        data = api_client.post(
            "transformation/pipelines/",
            json_data=payload,
            timeout=120,
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("Pipeline created successfully!")
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Name: {data.get('name')}")
            click.echo(f"Status: {data.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to create pipeline: {e}"
        )


@pipelines.command("update")
@click.argument("pipeline_id")
@click.option("--name", help="Pipeline name")
@click.option("--description", help="Description")
@click.option(
    "--config", "config_json",
    help="Pipeline config as JSON string",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def update_pipeline(
    pipeline_id: str,
    name: Optional[str],
    description: Optional[str],
    config_json: Optional[str],
    output_format: str,
):
    """Update a transformation pipeline"""
    payload = {}
    if name:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if config_json:
        payload["config"] = json.loads(config_json)
    if not payload:
        raise click.ClickException("No fields to update")

    try:
        data = api_client.patch(
            f"transformation/pipelines/{pipeline_id}/",
            json_data=payload,
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("Pipeline updated successfully!")
            click.echo(f"ID: {data.get('id')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to update pipeline: {e}"
        )


@pipelines.command("delete")
@click.argument("pipeline_id")
@click.option("--confirm", is_flag=True)
def delete_pipeline(pipeline_id: str, confirm: bool):
    """Delete a transformation pipeline"""
    if not confirm:
        if not click.confirm(
            f"Delete pipeline {pipeline_id}?"
        ):
            click.echo("Cancelled.")
            return
    try:
        api_client.delete(
            f"transformation/pipelines/{pipeline_id}/",
        )
        click.echo(
            f"Pipeline {pipeline_id} deleted."
        )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to delete pipeline: {e}"
        )


@pipelines.command("validate")
@click.argument("pipeline_id")
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def validate_pipeline(
    pipeline_id: str, output_format: str,
):
    """Validate a transformation pipeline configuration"""
    try:
        data = api_client.post(
            f"transformation/pipelines/{pipeline_id}"
            f"/validate/",
            timeout=120,
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            valid = data.get("is_valid", False)
            click.echo(
                f"Valid: {'Yes' if valid else 'No'}"
            )
            errors = data.get("errors", [])
            if errors:
                click.echo("Errors:")
                for err in errors:
                    click.echo(f"  - {err}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to validate pipeline: {e}"
        )


# ── Runs ─────────────────────────────────────────────────


@transformation.group("runs")
def runs():
    """Manage transformation pipeline runs"""
    pass


@runs.command("list")
@click.option("--pipeline-id", help="Filter by pipeline")
@click.option("--status", help="Filter by status")
@click.option("--limit", type=int, default=20)
@click.option("--offset", type=int, default=0)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def list_runs(
    pipeline_id: Optional[str],
    status: Optional[str],
    limit: int, offset: int,
    output_format: str,
):
    """List transformation runs"""
    params = {"limit": limit, "offset": offset}
    if pipeline_id:
        params["pipeline_id"] = pipeline_id
    if status:
        params["status"] = status

    try:
        data = api_client.get(
            "transformation/executions/", params=params,
        )
        results = (
            data.get("results", [])
            if isinstance(data, dict) else
            data if isinstance(data, list) else []
        )
        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No runs found.")
                return
            click.echo(
                f"{'ID':<40} {'Pipeline':<30} "
                f"{'Status':<12} {'Started':<25}"
            )
            click.echo("-" * 107)
            for r in results:
                if not isinstance(r, dict):
                    continue
                click.echo(
                    f"{str(r.get('id', ''))[:36]:<40} "
                    f"{str(r.get('pipeline_id', ''))[:28]:<30} "
                    f"{str(r.get('status', '')):<12} "
                    f"{str(r.get('started_at', ''))[:23]:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to list runs: {e}"
        )


@runs.command("get")
@click.argument("run_id")
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def get_run(run_id: str, output_format: str):
    """Get transformation run details"""
    try:
        data = api_client.get(
            f"transformation/executions/{run_id}/",
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Run ID: {data.get('id')}")
            click.echo(
                f"Pipeline: {data.get('pipeline_id')}"
            )
            click.echo(f"Status: {data.get('status')}")
            click.echo(
                f"Started: {data.get('started_at')}"
            )
            click.echo(
                f"Completed: "
                f"{data.get('completed_at', 'N/A')}"
            )
            if data.get("error_message"):
                click.echo(
                    f"Error: {data.get('error_message')}"
                )
            if data.get("result_json"):
                click.echo(
                    f"Result: "
                    f"{json.dumps(data['result_json'], indent=2)}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to get run: {e}"
        )


@runs.command("submit")
@click.argument("pipeline_id")
@click.option(
    "--params", "params_json",
    help="Runtime parameters as JSON",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def submit_run(
    pipeline_id: str,
    params_json: Optional[str],
    output_format: str,
):
    """Submit a new transformation run"""
    payload = {"pipeline_id": pipeline_id}
    if params_json:
        payload["params"] = json.loads(params_json)

    try:
        data = api_client.post(
            "transformation/executions/",
            json_data=payload,
            timeout=120,
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("Run submitted successfully!")
            click.echo(f"Run ID: {data.get('id')}")
            click.echo(f"Status: {data.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to submit run: {e}"
        )


@runs.command("cancel")
@click.argument("run_id")
def cancel_run(run_id: str):
    """Cancel a running transformation"""
    try:
        api_client.post(
            f"transformation/executions/{run_id}"
            f"/cancel/",
        )
        click.echo(f"Run {run_id} cancelled.")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to cancel run: {e}"
        )


# ── Plan Limits ──────────────────────────────────────────


@transformation.command("plan-limits")
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def plan_limits(output_format: str):
    """Show transformation plan limits and current usage"""
    try:
        data = api_client.get(
            "billing/subscription/current/",
        )
        limits = data.get("limits", {})

        tf_limits = {
            k: v for k, v in limits.items()
            if "transformation" in k
        }

        if output_format == "json":
            click.echo(json.dumps(tf_limits, indent=2))
        else:
            if not tf_limits:
                click.echo(
                    "No transformation limits on "
                    "current plan."
                )
                return
            click.echo(
                f"{'Limit':<40} {'Value':<15}"
            )
            click.echo("-" * 55)
            for k, v in sorted(tf_limits.items()):
                val = "Unlimited" if v is None else str(v)
                click.echo(f"{k:<40} {val:<15}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to get plan limits: {e}"
        )
