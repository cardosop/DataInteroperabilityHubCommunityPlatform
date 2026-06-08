"""
283.5.8 — Form draft CLI commands.
"""
from __future__ import annotations

import json

import click

from ..api_client import api_client


@click.group()
def drafts():
    """Form draft operations (auto-save / restore)"""
    pass


@drafts.command("get")
@click.option("--resource-type", required=True, help="e.g. asset, contract, dataset")
@click.option("--draft-key", default="default", help="Draft identifier")
def get_draft(resource_type, draft_key):
    """Retrieve a saved form draft"""
    data = api_client.get("drafts/", params={"resource_type": resource_type, "draft_key": draft_key})
    click.echo(json.dumps(data, indent=2, default=str))


@drafts.command("save")
@click.option("--resource-type", required=True)
@click.option("--draft-key", default="default")
@click.option("--data", "payload", required=True, help="JSON payload for the draft")
def save_draft(resource_type, draft_key, payload):
    """Save a form draft"""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid JSON payload: {exc}")
    # api_client has no put() — use the generic request() with PUT method.
    resp = api_client.request("PUT", "drafts/save/", json_data={
        "resource_type": resource_type, "draft_key": draft_key, "data": parsed,
    })
    if not resp.ok:
        raise click.ClickException(f"Save draft failed: {resp.status_code} {resp.text}")
    data = resp.json()
    click.echo(json.dumps(data, indent=2, default=str))


@drafts.command("delete")
@click.option("--resource-type", required=True)
@click.option("--draft-key", default="default")
@click.confirmation_option(prompt="Delete this draft?")
def delete_draft(resource_type, draft_key):
    """Delete a saved draft"""
    resp = api_client.request("DELETE", "drafts/delete/", params={
        "resource_type": resource_type, "draft_key": draft_key,
    })
    if not resp.ok:
        raise click.ClickException(f"Delete draft failed: {resp.status_code} {resp.text}")
    click.echo(f"Deleted draft: {resource_type}/{draft_key}")
