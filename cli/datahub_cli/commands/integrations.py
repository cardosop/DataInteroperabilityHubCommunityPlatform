"""
283.5.11 — Integration CLI commands.
"""
from __future__ import annotations

import json

import click

from ..api_client import api_client


@click.group()
def integrations():
    """Integration connections, sync jobs, and marketplace connectors"""
    pass


# ── Connections ─────────────────────────────────────────────────────────────

@integrations.group("connections")
def connections():
    """Manage integration connections"""
    pass


@connections.command("list")
def list_connections():
    """List connections"""
    data = api_client.get("integrations/connections/")
    results = data if isinstance(data, list) else data.get("results", [])
    if not results:
        click.echo("No connections found.")
        return
    for r in results:
        click.echo(f"{r.get('id','')}  {r.get('source_type','')}  {r.get('status','')}")


@connections.command("create")
@click.option("--source-type", required=True)
@click.option("--config", "config_json", required=True, help="Connection config as JSON")
def create_connection(source_type, config_json):
    """Create a connection"""
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid JSON config: {exc}")
    data = api_client.post("integrations/connections/", json_data={
        "source_type": source_type, "config": config,
    })
    click.echo(json.dumps(data, indent=2, default=str))


@connections.command("get")
@click.argument("conn_id")
def get_connection(conn_id):
    """Get connection details"""
    data = api_client.get(f"integrations/connections/{conn_id}/")
    click.echo(json.dumps(data, indent=2, default=str))


@connections.command("delete")
@click.argument("conn_id")
@click.confirmation_option(prompt="Delete this connection?")
def delete_connection(conn_id):
    """Delete a connection"""
    api_client.delete(f"integrations/connections/{conn_id}/")
    click.echo(f"Deleted connection: {conn_id}")


# ── Sync jobs ───────────────────────────────────────────────────────────────

@integrations.command("sync-jobs")
def list_sync_jobs():
    """List sync jobs"""
    data = api_client.get("integrations/sync-jobs/")
    results = data if isinstance(data, list) else data.get("results", [])
    if not results:
        click.echo("No sync jobs found.")
        return
    for r in results:
        click.echo(f"{r.get('id','')}  {r.get('status','')}  {r.get('created_at','')}")


# ── Marketplace connectors ──────────────────────────────────────────────────

@integrations.group("marketplace")
def marketplace():
    """Browse marketplace connectors"""
    pass


@marketplace.command("list")
def list_marketplace_connectors():
    """List marketplace connectors"""
    data = api_client.get("integrations/marketplace-connectors/")
    results = data if isinstance(data, list) else data.get("results", [])
    if not results:
        click.echo("No marketplace connectors found.")
        return
    for r in results:
        click.echo(f"{r.get('id','')}  {r.get('name','')}")


@marketplace.command("get")
@click.argument("connector_id")
def get_marketplace_connector(connector_id):
    """Get connector details"""
    data = api_client.get(f"integrations/marketplace-connectors/{connector_id}/")
    click.echo(json.dumps(data, indent=2, default=str))
