"""
283.3.7.2 — Data Retention CLI commands.

Retention policy management, sweep status, and enforcement.
"""

from __future__ import annotations

import json

import click

from ..api_client import api_client

AUDIT_PREFIX = "audit"


@click.group()
def retention():
    """Data retention policy and sweep commands"""


@retention.command("list-policies")
@click.option("--page", type=int, default=1)
@click.option("--page-size", type=int, default=25)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_policies(page: int, page_size: int, output_format: str):
    """List per-event-type retention policy overrides"""
    try:
        data = api_client.get(
            f"{AUDIT_PREFIX}/event-retention-policies/",
            params={"page": page, "page_size": page_size},
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            results = data.get("results", [])
            click.echo(
                f"Retention policies: {len(results)} (page {page}, total {data.get('count', '?')})"
            )
            for r in results:
                click.echo(
                    f"  {r.get('event_type', '?'):40s} {r.get('retention_days', '?'):5s}d  "
                    f"{r.get('description', '')[:60]}"
                )
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@retention.command("create-policy")
@click.option("--event-type", required=True, help="Audit event type")
@click.option("--retention-days", type=int, required=True, help="Retention period in days")
@click.option("--description", default="", help="Justification")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def create_policy(event_type: str, retention_days: int, description: str, output_format: str):
    """Create a per-event-type retention policy override"""
    try:
        data = api_client.post(
            f"{AUDIT_PREFIX}/event-retention-policies/",
            data={
                "event_type": event_type,
                "retention_days": retention_days,
                "description": description,
            },
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Policy created: {data.get('id')}")
            click.echo(f"Event type: {data.get('event_type')}")
            click.echo(f"Retention: {data.get('retention_days')} days")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@retention.command("update-policy")
@click.option("--policy-id", required=True, help="Policy UUID")
@click.option("--retention-days", type=int, required=True, help="New retention period")
@click.option("--description", default="", help="Updated justification")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def update_policy(policy_id: str, retention_days: int, description: str, output_format: str):
    """Update a retention policy override"""
    payload = {"retention_days": retention_days}
    if description:
        payload["description"] = description
    try:
        data = api_client.patch(
            f"{AUDIT_PREFIX}/event-retention-policies/{policy_id}/", data=payload
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Policy updated: {data.get('retention_days')} days")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@retention.command("delete-policy")
@click.option("--policy-id", required=True, help="Policy UUID")
def delete_policy(policy_id: str):
    """Delete a retention policy override"""
    try:
        api_client.delete(f"{AUDIT_PREFIX}/event-retention-policies/{policy_id}/")
        click.echo(f"Policy deleted: {policy_id}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@retention.command("sweep-status")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def sweep_status(output_format: str):
    """Get last retention sweep status"""
    try:
        data = api_client.get(f"{AUDIT_PREFIX}/audit-events/", params={"page_size": 10})
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            results = data.get("results", [])
            click.echo(f"Recent audit events: {len(results)}")
            click.echo("Retention sweep metrics: retention_enforcement_total (Prometheus)")
            click.echo("Sweep schedule: daily at 03:00 UTC via cron")
            click.echo("Run: python manage.py enforce_retention --execute")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
