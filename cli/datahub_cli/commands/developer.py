"""
283.5.12 — Developer portal CLI commands.
"""

from __future__ import annotations

import json

import click

from ..api_client import api_client


@click.group()
def developer():
    """Developer portal: plugins, API keys, SDK, docs"""


# ── Plugins ─────────────────────────────────────────────────────────────────


@developer.group("plugins")
def plugins():
    """Manage developer plugins"""


@plugins.command("list")
def list_plugins():
    """List plugins"""
    data = api_client.get("developer/plugins/")
    results = data if isinstance(data, list) else data.get("results", [])
    if not results:
        click.echo("No plugins found.")
        return
    for r in results:
        click.echo(f"{r.get('id', '')}  {r.get('name', '')}")


@plugins.command("create")
@click.option("--name", required=True)
@click.option("--config", "config_json", default="{}", help="Plugin config JSON")
def create_plugin(name, config_json):
    """Create a plugin"""
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid JSON: {exc}")
    data = api_client.post("developer/plugins/", json_data={"name": name, "config": config})
    click.echo(json.dumps(data, indent=2, default=str))


@plugins.command("get")
@click.argument("plugin_id")
def get_plugin(plugin_id):
    """Get plugin details"""
    data = api_client.get(f"developer/plugins/{plugin_id}/")
    click.echo(json.dumps(data, indent=2, default=str))


@plugins.command("delete")
@click.argument("plugin_id")
@click.confirmation_option(prompt="Delete this plugin?")
def delete_plugin(plugin_id):
    """Delete a plugin"""
    api_client.delete(f"developer/plugins/{plugin_id}/")
    click.echo(f"Deleted plugin: {plugin_id}")


# ── API Keys ────────────────────────────────────────────────────────────────


@developer.group("api-keys")
def api_keys():
    """Manage API keys"""


@api_keys.command("list")
def list_api_keys():
    """List API keys"""
    data = api_client.get("developer/api-keys/")
    results = data if isinstance(data, list) else data.get("results", [])
    if not results:
        click.echo("No API keys found.")
        return
    for r in results:
        click.echo(f"{r.get('id', '')}  {r.get('name', '')}  {r.get('created_at', '')}")


@api_keys.command("create")
@click.option("--name", required=True)
def create_api_key(name):
    """Create an API key"""
    data = api_client.post("developer/api-keys/", json_data={"name": name})
    click.echo(json.dumps(data, indent=2, default=str))
    click.echo(f"\nAPI Key (store securely): {data.get('key', 'N/A')}")


@api_keys.command("revoke")
@click.argument("key_id")
@click.confirmation_option(prompt="Revoke this API key?")
def revoke_api_key(key_id):
    """Revoke an API key"""
    api_client.delete(f"developer/api-keys/{key_id}/")
    click.echo(f"Revoked API key: {key_id}")


# ── SDK / Docs / Portal ─────────────────────────────────────────────────────


@developer.command("sdk")
def get_sdk():
    """Get SDK metadata"""
    data = api_client.get("developer/sdk/")
    click.echo(json.dumps(data, indent=2, default=str))


@developer.command("docs")
def get_docs():
    """Get documentation metadata"""
    data = api_client.get("developer/docs/")
    click.echo(json.dumps(data, indent=2, default=str))


@developer.command("portal")
def get_portal():
    """Get developer portal info"""
    data = api_client.get("developer/portal/")
    click.echo(json.dumps(data, indent=2, default=str))


@developer.command("api-usage")
def get_api_usage():
    """Get API usage statistics"""
    data = api_client.get("developer/api-usage/")
    click.echo(json.dumps(data, indent=2, default=str))
