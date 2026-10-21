"""
283.5.13 — OpenLineage CLI commands.
"""

from __future__ import annotations

import click

from ..api_client import api_client
from ..output import print_json_output


@click.group()
def openlineage():
    """OpenLineage API key and status management"""


@openlineage.command("keys")
def list_keys():
    """List OpenLineage API keys"""
    data = api_client.get("openlineage/keys/")
    results = data if isinstance(data, list) else data.get("results", [])
    if not results:
        click.echo("No OpenLineage keys found.")
        return
    for r in results:
        click.echo(f"{r.get('id', '')}  {r.get('name', '')}  {r.get('created_at', '')}")


@openlineage.command("create-key")
@click.option("--name", required=True, help="Key name for identification")
def create_key(name):
    """Create an OpenLineage API key"""
    data = api_client.post("openlineage/keys/", json_data={"name": name})
    print_json_output(data)


@openlineage.command("revoke-key")
@click.argument("key_id")
@click.confirmation_option(prompt="Revoke this OpenLineage key?")
def revoke_key(key_id):
    """Revoke an OpenLineage API key"""
    api_client.delete(f"openlineage/keys/{key_id}/")
    click.echo(f"Revoked key: {key_id}")


@openlineage.command("status")
def status():
    """Get OpenLineage service status"""
    data = api_client.get("openlineage/status/")
    print_json_output(data)
