"""
Health check commands.

Provides CLI commands for checking backend health.
Uses real hub API - no mocks/stubs.
"""

import json

import click

from ..api_client import api_client


@click.group()
def health():
    """Health check commands"""
    pass


@health.command("check")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def check_health(output_format: str):
    """Check backend health status"""
    try:
        # Use the API info endpoint as health check
        data = api_client.get("")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"API Name: {data.get('name', 'Unknown')}")
            click.echo(f"API Version: {data.get('version', 'Unknown')}")
            click.echo(f"Base URL: {data.get('base_url', 'Unknown')}")
            click.echo("\nAvailable Endpoints:")
            endpoints = data.get("endpoints", {})
            for endpoint_name, endpoint_path in endpoints.items():
                click.echo(f"  {endpoint_name}: {endpoint_path}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to check health: {e}")
