"""
283.3.4.2 — Breach notification CLI commands.

GDPR Art. 33/34 breach notification workflow commands.
"""
from __future__ import annotations

import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def breach():
    """Breach incident notification commands"""
    pass


@breach.command("create")
@click.option("--title", required=True, help="Incident title")
@click.option("--description", required=True, help="Detailed description of the breach")
@click.option(
    "--sla-level", type=click.Choice(["STANDARD", "HIGH", "CRITICAL"]),
    default="STANDARD", help="SLA severity level",
)
@click.option("--affected-categories", default=None,
              help="Comma-separated data categories (e.g. PII,financial)")
@click.option("--affected-count", type=int, default=None,
              help="Estimated number of affected subjects")
@click.option("--discovered-at", default=None, help="ISO-8601 discovery timestamp")
@click.option("--notification-deadline", default=None, help="ISO-8601 statutory deadline override")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]),
              default="table", help="Output format")
def create(
    title: str, description: str, sla_level: str,
    affected_categories: Optional[str], affected_count: Optional[int],
    discovered_at: Optional[str], notification_deadline: Optional[str],
    output_format: str,
):
    """Create a new breach incident"""
    payload: dict = {"title": title, "description": description, "sla_level": sla_level}
    if affected_categories:
        payload["affected_data_categories"] = [c.strip() for c in affected_categories.split(",")]
    if affected_count is not None:
        payload["affected_subjects_count"] = affected_count
    if discovered_at:
        payload["discovered_at"] = discovered_at
    if notification_deadline:
        payload["notification_deadline"] = notification_deadline

    try:
        data = api_client.post("governance/breach-incidents/", data=payload)
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Incident created: {data.get('id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"SLA Level: {data.get('sla_level')}")
            click.echo(f"Statutory deadline: {data.get('notification_deadline', 'N/A')}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@breach.command("list")
@click.option("--status", "filter_status", default=None,
              help="Filter by status (OPEN, INVESTIGATING, NOTIFIED_DPA, NOTIFIED_SUBJECTS, RESOLVED, CLOSED)")
@click.option("--sla-level", "filter_sla", default=None,
              help="Filter by SLA level (STANDARD, HIGH, CRITICAL)")
@click.option("--page", type=int, default=1)
@click.option("--page-size", type=int, default=20)
@click.option("--format", "output_format", type=click.Choice(["json", "table"]),
              default="table", help="Output format")
def list_incidents(
    filter_status: Optional[str], filter_sla: Optional[str],
    page: int, page_size: int, output_format: str,
):
    """List breach incidents"""
    params: dict = {"page": page, "page_size": page_size}
    if filter_status:
        params["status"] = filter_status
    if filter_sla:
        params["sla_level"] = filter_sla

    try:
        data = api_client.get("governance/breach-incidents/", params=params)
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            results = data.get("results", [])
            click.echo(f"Breach incidents: {len(results)} (page {page}, total {data.get('count', '?')})")
            for r in results:
                click.echo(f"  {r.get('id','?')[:8]}… {r.get('status','?'):20s} "
                           f"{r.get('sla_level','?'):10s} {r.get('title','?')[:50]}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@breach.command("get")
@click.option("--incident-id", required=True, help="Incident UUID")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]),
              default="table", help="Output format")
def get(incident_id: str, output_format: str):
    """Get breach incident details"""
    try:
        data = api_client.get(f"governance/breach-incidents/{incident_id}/")
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"ID:          {data.get('id')}")
            click.echo(f"Title:       {data.get('title')}")
            click.echo(f"Status:      {data.get('status')}")
            click.echo(f"SLA Level:   {data.get('sla_level')}")
            click.echo(f"Discovered:  {data.get('discovered_at', 'N/A')}")
            click.echo(f"Deadline:    {data.get('notification_deadline', 'N/A')}")
            click.echo(f"Description: {data.get('description', '')[:200]}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@breach.command("update-status")
@click.option("--incident-id", required=True, help="Incident UUID")
@click.option(
    "--status", required=True,
    type=click.Choice(["OPEN", "INVESTIGATING", "NOTIFIED_DPA",
                       "NOTIFIED_SUBJECTS", "RESOLVED", "CLOSED"]),
    help="New status",
)
@click.option("--resolution-note", default="", help="Required for RESOLVED/CLOSED")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]),
              default="table", help="Output format")
def update_status(incident_id: str, status: str, resolution_note: str, output_format: str):
    """Update breach incident status"""
    try:
        data = api_client.patch(
            f"governance/breach-incidents/{incident_id}/status/",
            data={"status": status, "notes": resolution_note},
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Status updated: {data.get('status')}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@breach.command("sla")
@click.option("--incident-id", required=True, help="Incident UUID")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]),
              default="table", help="Output format")
def sla(incident_id: str, output_format: str):
    """Get SLA status for a breach incident (from dashboard + detail)"""
    try:
        # Fetch the incident to get SLA data (deadline, status, sla_level)
        data = api_client.get(f"governance/breach-incidents/{incident_id}/")
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"SLA Level:      {data.get('sla_level')}")
            click.echo(f"Status:         {data.get('status')}")
            click.echo(f"Deadline:       {data.get('notification_deadline', 'N/A')}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
