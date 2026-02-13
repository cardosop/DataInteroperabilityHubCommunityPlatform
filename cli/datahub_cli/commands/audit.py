"""
Audit event querying commands.

Provides CLI commands for querying audit events.
Uses real hub API - no mocks/stubs.
"""

import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def audit():
    """Audit event querying commands"""
    pass


@audit.command("query")
@click.option("--resource-type", help="Filter by resource type")
@click.option("--action", help="Filter by action")
@click.option("--actor-user-id", help="Filter by actor user ID")
@click.option("--start-date", help="Filter by start date (ISO format)")
@click.option("--end-date", help="Filter by end date (ISO format)")
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table", "csv"]),
    default="table",
    help="Output format",
)
def query_events(
    resource_type: Optional[str],
    action: Optional[str],
    actor_user_id: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    limit: int,
    offset: int,
    output_format: str,
):
    """Query audit events"""
    params = {"limit": limit, "offset": offset}
    if resource_type:
        params["resource_type"] = resource_type
    if action:
        params["action"] = action
    if actor_user_id:
        params["actor_user_id"] = actor_user_id
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date

    # For CSV export, use the export endpoint
    if output_format == "csv":
        params["format"] = "csv"
        try:
            # Use request method to get raw response for CSV
            response = api_client.request("GET", "audit/audit-events/export/", params=params)
            click.echo(response.text)
            return
        except Exception as e:
            raise click.ClickException(f"Failed to export audit events: {e}")

    try:
        data = api_client.get("audit/audit-events/", params=params)
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
                click.echo("No audit events found.")
                return

            # Table format
            click.echo(
                f"{'Timestamp':<25} {'Resource Type':<20} {'Action':<20} {'Resource ID':<40} {'Actor':<40}"
            )
            click.echo("-" * 145)
            for event in results:
                if not isinstance(event, dict):
                    continue
                timestamp = str(event.get("timestamp", ""))[:23] if event.get("timestamp") else ""
                resource_type_val = (
                    str(event.get("resource_type", ""))[:18] if event.get("resource_type") else ""
                )
                action_val = str(event.get("action", ""))[:18] if event.get("action") else ""
                resource_id = (
                    str(event.get("resource_id", ""))[:38] if event.get("resource_id") else ""
                )
                actor = (
                    str(event.get("actor_user_id", ""))[:38] if event.get("actor_user_id") else ""
                )
                click.echo(
                    f"{timestamp:<25} "
                    f"{resource_type_val:<20} "
                    f"{action_val:<20} "
                    f"{resource_id:<40} "
                    f"{actor:<40}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to query audit events: {e}")


@audit.command("get")
@click.argument("event_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_event(event_id: str, output_format: str):
    """Get audit event details"""
    try:
        data = api_client.get(f"audit/audit-events/{event_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Timestamp: {data.get('timestamp')}")
            click.echo(f"Resource Type: {data.get('resource_type')}")
            click.echo(f"Action: {data.get('action')}")
            click.echo(f"Resource ID: {data.get('resource_id')}")
            click.echo(f"Actor User ID: {data.get('actor_user_id')}")
            if data.get("details"):
                click.echo(f"Details: {json.dumps(data.get('details'), indent=2)}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get audit event: {e}")


@audit.command("export")
@click.option("--resource-type", help="Filter by resource type")
@click.option("--action", help="Filter by action")
@click.option("--actor-user-id", help="Filter by actor user ID")
@click.option("--start-date", help="Filter by start date (ISO format)")
@click.option("--end-date", help="Filter by end date (ISO format)")
@click.option("--output", help="Output file path (default: stdout)")
def export_events(
    resource_type: Optional[str],
    action: Optional[str],
    actor_user_id: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    output: Optional[str],
):
    """Export audit events as CSV"""
    params = {"format": "csv"}
    if resource_type:
        params["resource_type"] = resource_type
    if action:
        params["action"] = action
    if actor_user_id:
        params["actor_user_id"] = actor_user_id
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date

    try:
        # Use request method to get raw response for CSV
        response = api_client.request("GET", "audit/audit-events/export/", params=params)
        csv_content = response.text

        if output:
            with open(output, "w") as f:
                f.write(csv_content)
            click.echo(f"Exported audit events to {output}")
        else:
            click.echo(csv_content)
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to export audit events: {e}")
