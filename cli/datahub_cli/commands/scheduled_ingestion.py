"""
Scheduled ingestion management commands.

Provides CLI commands for managing scheduled data ingestion workflows.
Uses real hub API - no mocks/stubs.
"""

import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def scheduled_ingestion():
    """Scheduled ingestion management commands"""
    pass


@scheduled_ingestion.command("list")
@click.option("--status", help="Filter by status (ACTIVE, PAUSED, ERROR)")
@click.option("--asset-id", help="Filter by asset ID")
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_ingestions(
    status: Optional[str], asset_id: Optional[str], limit: int, offset: int, output_format: str
):
    """List scheduled ingestions"""
    params = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    if asset_id:
        params["asset_id"] = asset_id

    try:
        data = api_client.get("scheduled-ingestions/", params=params)
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
                click.echo("No scheduled ingestions found.")
                return

            # Table format
            click.echo(
                f"{'ID':<40} {'Name':<30} {'Source Type':<15} {'Status':<15} {'Next Run':<25}"
            )
            click.echo("-" * 125)
            for ingestion in results:
                if not isinstance(ingestion, dict):
                    continue
                ingestion_id = str(ingestion.get("id", ""))[:36] if ingestion.get("id") else ""
                name = str(ingestion.get("name", ""))[:28] if ingestion.get("name") else ""
                source_type = (
                    str(ingestion.get("source_type", ""))[:13]
                    if ingestion.get("source_type")
                    else ""
                )
                status_val = (
                    str(ingestion.get("status", ""))[:13] if ingestion.get("status") else ""
                )
                next_run = (
                    str(ingestion.get("next_run_at", ""))[:23]
                    if ingestion.get("next_run_at")
                    else "N/A"
                )
                click.echo(
                    f"{ingestion_id:<40} "
                    f"{name:<30} "
                    f"{source_type:<15} "
                    f"{status_val:<15} "
                    f"{next_run:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list scheduled ingestions: {e}")


@scheduled_ingestion.command("get")
@click.argument("ingestion_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_ingestion(ingestion_id: str, output_format: str):
    """Get scheduled ingestion details"""
    try:
        data = api_client.get(f"scheduled-ingestions/{ingestion_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Name: {data.get('name')}")
            click.echo(f"Source Type: {data.get('source_type')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Schedule Type: {data.get('schedule_type')}")
            if data.get("schedule_config"):
                click.echo(f"Schedule Config: {json.dumps(data.get('schedule_config'))}")
            if data.get("file_pattern"):
                click.echo(f"File Pattern: {data.get('file_pattern')}")
            if data.get("next_run_at"):
                click.echo(f"Next Run: {data.get('next_run_at')}")
            if data.get("description"):
                click.echo(f"Description: {data.get('description')}")
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get scheduled ingestion: {e}")


@scheduled_ingestion.command("create")
@click.option("--name", required=True, help="Ingestion name")
@click.option(
    "--source-type",
    required=True,
    help="Source type (S3, GCS, AZURE_BLOB, HTTP, FTP, SFTP, DATABASE)",
)
@click.option("--source-config", required=True, help="Source configuration as JSON string")
@click.option(
    "--schedule-type", default="DAILY", help="Schedule type (DAILY, WEEKLY, MONTHLY, CUSTOM_CRON)"
)
@click.option(
    "--schedule-config", help="Schedule configuration as JSON string (required for CUSTOM_CRON)"
)
@click.option("--file-pattern", default=".*", help="File pattern regex")
@click.option("--asset-id", help="Target asset ID")
@click.option("--description", help="Description")
@click.option("--auto-create-asset", is_flag=True, help="Auto-create asset if not exists")
@click.option("--auto-activate", is_flag=True, help="Auto-activate asset after ingestion")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def create_ingestion(
    name: str,
    source_type: str,
    source_config: str,
    schedule_type: str,
    schedule_config: Optional[str],
    file_pattern: str,
    asset_id: Optional[str],
    description: Optional[str],
    auto_create_asset: bool,
    auto_activate: bool,
    output_format: str,
):
    """Create scheduled ingestion"""
    try:
        # Parse JSON strings
        try:
            source_config_dict = json.loads(source_config)
        except json.JSONDecodeError:
            raise click.ClickException(f"Invalid JSON in --source-config: {source_config}")

        schedule_config_dict = {}
        if schedule_config:
            try:
                schedule_config_dict = json.loads(schedule_config)
            except json.JSONDecodeError:
                raise click.ClickException(f"Invalid JSON in --schedule-config: {schedule_config}")
        elif schedule_type == "CUSTOM_CRON":
            raise click.ClickException(
                "--schedule-config is required for CUSTOM_CRON schedule type"
            )

        # Build request data
        data = {
            "name": name,
            "source_type": source_type,
            "source_config": source_config_dict,
            "schedule_type": schedule_type,
            "schedule_config": schedule_config_dict,
            "file_pattern": file_pattern,
            "auto_create_asset": auto_create_asset,
            "auto_activate": auto_activate,
        }

        if asset_id:
            data["asset_id"] = asset_id
        if description:
            data["description"] = description

        result = api_client.post("scheduled-ingestions/", json_data=data)

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Created scheduled ingestion: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Status: {result.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to create scheduled ingestion: {e}")


@scheduled_ingestion.command("update")
@click.argument("ingestion_id")
@click.option("--name", help="Update name")
@click.option("--source-config", help="Update source configuration as JSON string")
@click.option("--schedule-type", help="Update schedule type")
@click.option("--schedule-config", help="Update schedule configuration as JSON string")
@click.option("--file-pattern", help="Update file pattern")
@click.option("--status", help="Update status (ACTIVE, PAUSED)")
@click.option("--description", help="Update description")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def update_ingestion(
    ingestion_id: str,
    name: Optional[str],
    source_config: Optional[str],
    schedule_type: Optional[str],
    schedule_config: Optional[str],
    file_pattern: Optional[str],
    status: Optional[str],
    description: Optional[str],
    output_format: str,
):
    """Update scheduled ingestion"""
    try:
        data = {}

        if name:
            data["name"] = name
        if source_config:
            try:
                data["source_config"] = json.loads(source_config)
            except json.JSONDecodeError:
                raise click.ClickException(f"Invalid JSON in --source-config: {source_config}")
        if schedule_type:
            data["schedule_type"] = schedule_type
        if schedule_config:
            try:
                data["schedule_config"] = json.loads(schedule_config)
            except json.JSONDecodeError:
                raise click.ClickException(f"Invalid JSON in --schedule-config: {schedule_config}")
        if file_pattern:
            data["file_pattern"] = file_pattern
        if status:
            data["status"] = status
        if description:
            data["description"] = description

        if not data:
            raise click.ClickException("At least one field must be provided for update")

        result = api_client.patch(f"scheduled-ingestions/{ingestion_id}/", json_data=data)

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Updated scheduled ingestion: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Status: {result.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to update scheduled ingestion: {e}")


@scheduled_ingestion.command("trigger")
@click.argument("ingestion_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def trigger_ingestion(ingestion_id: str, output_format: str):
    """Manually trigger scheduled ingestion"""
    try:
        result = api_client.post(f"scheduled-ingestions/{ingestion_id}/trigger/")

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Triggered scheduled ingestion: {ingestion_id}")
            if result.get("run_id"):
                click.echo(f"Run ID: {result.get('run_id')}")
            if result.get("status"):
                click.echo(f"Status: {result.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to trigger scheduled ingestion: {e}")


@scheduled_ingestion.command("runs")
@click.argument("ingestion_id")
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
def list_runs(
    ingestion_id: str, status: Optional[str], limit: int, offset: int, output_format: str
):
    """List runs for scheduled ingestion"""
    params = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status

    try:
        data = api_client.get(f"scheduled-ingestions/{ingestion_id}/runs/", params=params)
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
            click.echo(
                f"{'Run ID':<40} {'Status':<15} {'Started':<25} {'Completed':<25} {'Files':<10}"
            )
            click.echo("-" * 115)
            for run in results:
                if not isinstance(run, dict):
                    continue
                run_id = str(run.get("id", ""))[:36] if run.get("id") else ""
                status_val = str(run.get("status", ""))[:13] if run.get("status") else ""
                started = str(run.get("started_at", ""))[:23] if run.get("started_at") else "N/A"
                completed = (
                    str(run.get("completed_at", ""))[:23] if run.get("completed_at") else "N/A"
                )
                files_processed = str(run.get("files_processed", 0))
                click.echo(
                    f"{run_id:<40} "
                    f"{status_val:<15} "
                    f"{started:<25} "
                    f"{completed:<25} "
                    f"{files_processed:<10}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list runs: {e}")


@scheduled_ingestion.command("run-detail")
@click.argument("ingestion_id")
@click.argument("run_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_run_detail(ingestion_id: str, run_id: str, output_format: str):
    """Get scheduled ingestion run details"""
    try:
        data = api_client.get(f"scheduled-ingestions/{ingestion_id}/runs/{run_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"Run ID: {data.get('id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Started: {data.get('started_at')}")
            click.echo(f"Completed: {data.get('completed_at')}")
            click.echo(f"Files Found: {data.get('files_found', 0)}")
            click.echo(f"Files Processed: {data.get('files_processed', 0)}")
            click.echo(f"Files Failed: {data.get('files_failed', 0)}")
            click.echo(f"Datasets Created: {data.get('datasets_created', 0)}")
            if data.get("error_message"):
                click.echo(f"Error: {data.get('error_message')}")
            if data.get("result_json"):
                click.echo(f"Result: {json.dumps(data.get('result_json'), indent=2)}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get run details: {e}")
