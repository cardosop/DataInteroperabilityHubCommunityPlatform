"""
Webhook management commands.

Provides CLI commands for managing webhooks.
Uses real hub API - no mocks/stubs.
"""

import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def webhooks():
    """Webhook management commands"""
    pass


@webhooks.command("list")
@click.option("--status", help="Filter by status (ACTIVE, INACTIVE)")
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_webhooks(status: Optional[str], limit: int, offset: int, output_format: str):
    """List webhooks"""
    params = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status

    try:
        data = api_client.get("webhooks/webhooks/", params=params)
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
                click.echo("No webhooks found.")
                return

            # Table format
            click.echo(f"{'ID':<40} {'Name':<30} {'URL':<50} {'Status':<15} {'Events':<20}")
            click.echo("-" * 155)
            for webhook in results:
                if not isinstance(webhook, dict):
                    continue
                webhook_id = str(webhook.get("id", ""))[:36] if webhook.get("id") else ""
                name = str(webhook.get("name", ""))[:28] if webhook.get("name") else ""
                url = str(webhook.get("url", ""))[:48] if webhook.get("url") else ""
                status_val = str(webhook.get("status", ""))[:13] if webhook.get("status") else ""
                event_types = (
                    ", ".join(webhook.get("event_types", []))[:18]
                    if webhook.get("event_types")
                    else ""
                )
                click.echo(
                    f"{webhook_id:<40} "
                    f"{name:<30} "
                    f"{url:<50} "
                    f"{status_val:<15} "
                    f"{event_types:<20}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list webhooks: {e}")


@webhooks.command("get")
@click.argument("webhook_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_webhook(webhook_id: str, output_format: str):
    """Get webhook details"""
    try:
        data = api_client.get(f"webhooks/webhooks/{webhook_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Name: {data.get('name')}")
            click.echo(f"URL: {data.get('url')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Event Types: {', '.join(data.get('event_types', []))}")
            click.echo(f"Max Retries: {data.get('max_retries', 5)}")
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get webhook: {e}")


@webhooks.command("create")
@click.option("--name", required=True, help="Webhook name")
@click.option("--url", required=True, help="Webhook URL")
@click.option("--secret", required=True, help="Webhook secret")
@click.option("--event-types", required=True, help="Comma-separated list of event types")
@click.option(
    "--status", type=click.Choice(["ACTIVE", "INACTIVE"]), default="ACTIVE", help="Webhook status"
)
@click.option("--max-retries", type=int, default=5, help="Maximum retry attempts")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def create_webhook(
    name: str,
    url: str,
    secret: str,
    event_types: str,
    status: str,
    max_retries: int,
    output_format: str,
):
    """Create webhook"""
    try:
        event_types_list = [et.strip() for et in event_types.split(",")]

        data = {
            "name": name,
            "url": url,
            "secret": secret,
            "event_types": event_types_list,
            "status": status,
            "max_retries": max_retries,
        }

        result = api_client.post("webhooks/webhooks/", json_data=data)

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Created webhook: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Status: {result.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to create webhook: {e}")


@webhooks.command("update")
@click.argument("webhook_id")
@click.option("--name", help="Update name")
@click.option("--url", help="Update URL")
@click.option("--secret", help="Update secret")
@click.option("--event-types", help="Update event types (comma-separated)")
@click.option("--status", type=click.Choice(["ACTIVE", "INACTIVE"]), help="Update status")
@click.option("--max-retries", type=int, help="Update max retries")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def update_webhook(
    webhook_id: str,
    name: Optional[str],
    url: Optional[str],
    secret: Optional[str],
    event_types: Optional[str],
    status: Optional[str],
    max_retries: Optional[int],
    output_format: str,
):
    """Update webhook"""
    try:
        data = {}

        if name:
            data["name"] = name
        if url:
            data["url"] = url
        if secret:
            data["secret"] = secret
        if event_types:
            data["event_types"] = [et.strip() for et in event_types.split(",")]
        if status:
            data["status"] = status
        if max_retries is not None:
            data["max_retries"] = max_retries

        if not data:
            raise click.ClickException("At least one field must be provided for update")

        result = api_client.patch(f"webhooks/webhooks/{webhook_id}/", json_data=data)

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Updated webhook: {result.get('id')}")
            click.echo(f"Name: {result.get('name')}")
            click.echo(f"Status: {result.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to update webhook: {e}")


@webhooks.command("delete")
@click.argument("webhook_id")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def delete_webhook(webhook_id: str, confirm: bool):
    """Delete webhook"""
    if not confirm:
        if not click.confirm(f"Are you sure you want to delete webhook {webhook_id}?"):
            click.echo("Cancelled.")
            return

    try:
        api_client.delete(f"webhooks/webhooks/{webhook_id}/")
        click.echo(f"Webhook {webhook_id} deleted successfully!")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to delete webhook: {e}")


@webhooks.command("event-types")
@click.option("--odps-only", is_flag=True, help="Show only ODPS event types")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_event_types(odps_only: bool, output_format: str):
    """List available webhook event types"""
    params = {}
    if odps_only:
        params["odps_only"] = "true"

    try:
        data = api_client.get("webhooks/webhooks/event-types/", params=params)

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            event_types = data.get("event_types", [])
            if not event_types:
                click.echo("No event types found.")
                return

            click.echo(f"{'Value':<40} {'Label':<50}")
            click.echo("-" * 90)
            for et in event_types:
                value = str(et.get("value", ""))[:38] if et.get("value") else ""
                label = str(et.get("label", ""))[:48] if et.get("label") else ""
                click.echo(f"{value:<40} {label:<50}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list event types: {e}")
