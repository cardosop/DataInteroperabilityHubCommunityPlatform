"""
283.5.7 — Security incident and audit log CLI commands.
"""
from __future__ import annotations

import json

import click

from ..api_client import api_client


@click.group()
def security():
    """Security incidents and audit logs"""
    pass


# ── Incidents ────────────────────────────────────────────────────────────────

@security.group("incidents")
def incidents():
    """Manage security incidents"""
    pass


@incidents.command("list")
@click.option("--page", default=1)
@click.option("--page-size", default=25)
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def list_incidents(page, page_size, output_format):
    """List security incidents"""
    data = api_client.get("security/incidents/", params={"page": page, "page_size": page_size})
    results = data.get("results", []) if isinstance(data, dict) else []
    if output_format == "json":
        click.echo(json.dumps(results, indent=2, default=str))
        return
    if not results:
        click.echo("No incidents found.")
        return
    for r in results:
        click.echo(f"{r.get('id','')}  {r.get('severity','')}  {r.get('status','')}  {r.get('title','')}")


@incidents.command("create")
@click.option("--title", required=True)
@click.option("--severity", type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]), required=True)
@click.option("--description", default="")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def create_incident(title, severity, description, output_format):
    """Create a security incident"""
    data = api_client.post("security/incidents/", json_data={
        "title": title, "severity": severity, "description": description,
    })
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Created incident: {data.get('id')}")


@incidents.command("get")
@click.argument("incident_id")
def get_incident(incident_id):
    """Get incident details"""
    data = api_client.get(f"security/incidents/{incident_id}/")
    click.echo(json.dumps(data, indent=2, default=str))


@incidents.command("update")
@click.argument("incident_id")
@click.option("--status", type=click.Choice(["OPEN", "INVESTIGATING", "RESOLVED", "CLOSED"]))
@click.option("--severity", type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]))
def update_incident(incident_id, status, severity):
    """Update incident status/severity"""
    payload = {}
    if status:
        payload["status"] = status
    if severity:
        payload["severity"] = severity
    data = api_client.patch(f"security/incidents/{incident_id}/", json_data=payload)
    click.echo(json.dumps(data, indent=2, default=str))


# ── Audit logs ──────────────────────────────────────────────────────────────

@security.group("audit-logs")
def audit_logs():
    """View audit logs"""
    pass


@audit_logs.command("list")
@click.option("--page", default=1)
@click.option("--page-size", default=25)
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def list_audit_logs(page, page_size, output_format):
    """List audit logs"""
    data = api_client.get("security/audit-logs/", params={"page": page, "page_size": page_size})
    results = data.get("results", []) if isinstance(data, dict) else []
    if output_format == "json":
        click.echo(json.dumps(results, indent=2, default=str))
        return
    if not results:
        click.echo("No audit logs found.")
        return
    for r in results:
        click.echo(f"{r.get('id','')}  {r.get('event_type','')}  {r.get('created_at','')}")


@audit_logs.command("get")
@click.argument("log_id")
def get_audit_log(log_id):
    """Get audit log details"""
    data = api_client.get(f"security/audit-logs/{log_id}/")
    click.echo(json.dumps(data, indent=2, default=str))
