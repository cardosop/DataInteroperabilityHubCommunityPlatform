"""
283.5.14 — Lineage subscription CLI commands.
"""
from __future__ import annotations

import json

import click

from ..api_client import api_client


@click.group()
def lineage_subscriptions():
    """Manage lineage subscriptions"""
    pass


@lineage_subscriptions.command("list")
def list_subscriptions():
    """List lineage subscriptions"""
    data = api_client.get("lineage-subscriptions/")
    results = data if isinstance(data, list) else data.get("results", [])
    if not results:
        click.echo("No lineage subscriptions found.")
        return
    for r in results:
        click.echo(f"{r.get('id','')}  {r.get('resource_type','')}  {r.get('status','')}")


@lineage_subscriptions.command("create")
@click.option("--resource-type", required=True, help="e.g. asset, dataset")
@click.option("--resource-id", required=True)
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def create_subscription(resource_type, resource_id, output_format):
    """Subscribe to lineage events"""
    data = api_client.post("lineage-subscriptions/", json_data={
        "resource_type": resource_type, "resource_id": resource_id,
    })
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Created subscription: {data.get('id')}")


@lineage_subscriptions.command("get")
@click.argument("sub_id")
def get_subscription(sub_id):
    """Get subscription details"""
    data = api_client.get(f"lineage-subscriptions/{sub_id}/")
    click.echo(json.dumps(data, indent=2, default=str))


@lineage_subscriptions.command("delete")
@click.argument("sub_id")
@click.confirmation_option(prompt="Delete this subscription?")
def delete_subscription(sub_id):
    """Delete a lineage subscription"""
    api_client.delete(f"lineage-subscriptions/{sub_id}/")
    click.echo(f"Deleted subscription: {sub_id}")
