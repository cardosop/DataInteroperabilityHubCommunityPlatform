"""
Scheduled export management commands.

Provides CLI commands for managing scheduled data export workflows.
Uses real hub API - no mocks/stubs.
"""

import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def scheduled_export():
    """Scheduled export management commands [Post-MVP]"""
    pass


@scheduled_export.command("list")
@click.option("--status", help="Filter by status (ACTIVE, PAUSED, ERROR)")
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_exports(status: Optional[str], limit: int, offset: int, output_format: str):
    """List scheduled exports"""
    params = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status

    try:
        data = api_client.get("scheduled-exports/", params=params)
        # Handle both paginated response (dict with 'results') and direct list response
        if isinstance(data, dict):
            results = data.get("results", [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No scheduled exports found.")
                return

            # Table format
            click.echo(
                f"{'ID':<40} {'Name':<30} {'Destination':<15} {'Status':<15} {'Next Run':<25}"
            )
            click.echo("-" * 125)
            for export in results:
                if not isinstance(export, dict):
                    continue
                export_id = str(export.get("id", ""))[:36] if export.get("id") else ""
                name = str(export.get("name", ""))[:28] if export.get("name") else ""
                dest_type = (
                    str(export.get("destination_type", ""))[:13]
                    if export.get("destination_type")
                    else ""
                )
                status_val = str(export.get("status", ""))[:13] if export.get("status") else ""
                next_run = (
                    str(export.get("next_run_at", ""))[:23] if export.get("next_run_at") else "N/A"
                )
                click.echo(
                    f"{export_id:<40} "
                    f"{name:<30} "
                    f"{dest_type:<15} "
                    f"{status_val:<15} "
                    f"{next_run:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list scheduled exports: {e}")


@scheduled_export.command("get")
@click.argument("export_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_export(export_id: str, output_format: str):
    """Get scheduled export details"""
    try:
        data = api_client.get(f"scheduled-exports/{export_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Name: {data.get('name')}")
            click.echo(f"Destination Type: {data.get('destination_type')}")
            click.echo(f"Status: {data.get('status')}")
            if data.get("schedule_config"):
                click.echo(f"Schedule Config: {json.dumps(data.get('schedule_config'))}")
            if data.get("source_scope"):
                click.echo(f"Source Scope: {json.dumps(data.get('source_scope'))}")
            if data.get("next_run_at"):
                click.echo(f"Next Run: {data.get('next_run_at')}")
            if data.get("last_run_at"):
                click.echo(f"Last Run: {data.get('last_run_at')}")
            if data.get("last_run_status"):
                click.echo(f"Last Run Status: {data.get('last_run_status')}")
            # 118E.12: failure tracking fields
            if data.get("consecutive_failure_count") is not None:
                click.echo(f"Consecutive Failures: {data.get('consecutive_failure_count')}")
            if data.get("auto_pause_status"):
                click.echo(f"Auto-Pause Status: {data.get('auto_pause_status')}")
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get scheduled export: {e}")


@scheduled_export.command("create")
@click.option("--name", required=True, help="Export name")
@click.option(
    "--destination-type", required=True, help="Destination type (S3, GCS, AZURE_BLOB, HTTP)"
)
@click.option(
    "--destination-config", required=True, help="Destination configuration as JSON string"
)
@click.option(
    "--schedule-config",
    required=True,
    help='Schedule configuration as JSON string (must include "cron")',
)
@click.option(
    "--source-scope",
    required=True,
    help="Source scope as JSON string (asset_ids, dataset_ids, file_ids, or contract_id)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def create_export(
    name: str,
    destination_type: str,
    destination_config: str,
    schedule_config: str,
    source_scope: str,
    output_format: str,
):
    """Create scheduled export"""
    try:
        # Parse JSON strings
        try:
            destination_config_dict = json.loads(destination_config)
        except json.JSONDecodeError:
            raise click.ClickException(
                f"Invalid JSON in --destination-config: {destination_config}"
            )

        try:
            schedule_config_dict = json.loads(schedule_config)
        except json.JSONDecodeError:
            raise click.ClickException(f"Invalid JSON in --schedule-config: {schedule_config}")

        if "cron" not in schedule_config_dict:
            raise click.ClickException("schedule_config must include 'cron' field")

        try:
            source_scope_dict = json.loads(source_scope)
        except json.JSONDecodeError:
            raise click.ClickException(f"Invalid JSON in --source-scope: {source_scope}")

        # Build request data
        data = {
            "name": name,
            "destination_type": destination_type,
            "destination_config": destination_config_dict,
            "schedule_config": schedule_config_dict,
            "source_scope": source_scope_dict,
        }

        result = api_client.post("scheduled-exports/", json_data=data)

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Created scheduled export: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Status: {result.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to create scheduled export: {e}")


@scheduled_export.command("update")
@click.argument("export_id")
@click.option("--name", help="Update name")
@click.option("--destination-config", help="Update destination configuration as JSON string")
@click.option("--schedule-config", help="Update schedule configuration as JSON string")
@click.option("--source-scope", help="Update source scope as JSON string")
@click.option("--status", help="Update status (ACTIVE, PAUSED)")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def update_export(
    export_id: str,
    name: Optional[str],
    destination_config: Optional[str],
    schedule_config: Optional[str],
    source_scope: Optional[str],
    status: Optional[str],
    output_format: str,
):
    """Update scheduled export"""
    try:
        data = {}

        if name:
            data["name"] = name
        if destination_config:
            try:
                data["destination_config"] = json.loads(destination_config)
            except json.JSONDecodeError:
                raise click.ClickException(
                    f"Invalid JSON in --destination-config: {destination_config}"
                )
        if schedule_config:
            try:
                data["schedule_config"] = json.loads(schedule_config)
            except json.JSONDecodeError:
                raise click.ClickException(f"Invalid JSON in --schedule-config: {schedule_config}")
        if source_scope:
            try:
                data["source_scope"] = json.loads(source_scope)
            except json.JSONDecodeError:
                raise click.ClickException(f"Invalid JSON in --source-scope: {source_scope}")
        if status:
            data["status"] = status

        if not data:
            raise click.ClickException("At least one field must be provided for update")

        result = api_client.patch(f"scheduled-exports/{export_id}/", json_data=data)

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Updated scheduled export: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Status: {result.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to update scheduled export: {e}")


@scheduled_export.command("trigger")
@click.argument("export_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def trigger_export(export_id: str, output_format: str):
    """Manually trigger scheduled export"""
    try:
        result = api_client.post(f"scheduled-exports/{export_id}/trigger/")

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Triggered scheduled export: {export_id}")
            if result.get("run_id"):
                click.echo(f"Run ID: {result.get('run_id')}")
            if result.get("status"):
                click.echo(f"Status: {result.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to trigger scheduled export: {e}")


@scheduled_export.command("runs")
@click.argument("export_id")
@click.option("--status", help="Filter by run status")
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_runs(export_id: str, status: Optional[str], limit: int, offset: int, output_format: str):
    """List runs for scheduled export"""
    params = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status

    try:
        data = api_client.get(f"scheduled-exports/{export_id}/runs/", params=params)
        # Handle both paginated response (dict with 'results') and direct list response
        if isinstance(data, dict):
            results = data.get("results", [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No runs found.")
                return

            # Table format
            click.echo(f"{'Run ID':<40} {'Status':<15} {'Started':<25} {'Completed':<25}")
            click.echo("-" * 105)
            for run in results:
                if not isinstance(run, dict):
                    continue
                run_id = str(run.get("id", ""))[:36] if run.get("id") else ""
                status_val = str(run.get("status", ""))[:13] if run.get("status") else ""
                started = str(run.get("started_at", ""))[:23] if run.get("started_at") else "N/A"
                completed = (
                    str(run.get("completed_at", ""))[:23] if run.get("completed_at") else "N/A"
                )
                click.echo(
                    f"{run_id:<40} " f"{status_val:<15} " f"{started:<25} " f"{completed:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list runs: {e}")


@scheduled_export.command("run-detail")
@click.argument("export_id")
@click.argument("run_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_run_detail(export_id: str, run_id: str, output_format: str):
    """Get scheduled export run details"""
    try:
        data = api_client.get(f"scheduled-exports/{export_id}/runs/{run_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"Run ID: {data.get('id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Started: {data.get('started_at')}")
            click.echo(f"Completed: {data.get('completed_at')}")
            if data.get("items_processed"):
                click.echo(f"Items Processed: {data.get('items_processed')}")
            if data.get("items_failed"):
                click.echo(f"Items Failed: {data.get('items_failed')}")
            if data.get("error_message"):
                click.echo(f"Error: {data.get('error_message')}")
            if data.get("result_json"):
                click.echo(f"Result: {json.dumps(data.get('result_json'), indent=2)}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get run details: {e}")
