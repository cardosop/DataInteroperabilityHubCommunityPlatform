"""
Tenant management commands (Phase 25).

Provides CLI commands for tenant usage and configuration.
Uses real hub API - no mocks/stubs.
"""

import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def tenants():
    """Tenant management commands"""
    pass


@tenants.command("usage")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_usage(output_format: str):
    """Get current usage for tenant"""
    try:
        data = api_client.get("tenants/me/usage/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Plan: {data.get('plan_slug')} ({data.get('plan_tier')})")
            click.echo("\nCurrent Usage:")
            click.echo(f"  Assets: {data.get('asset_count', 0)}")
            click.echo(f"  Datasets: {data.get('dataset_count', 0)}")
            click.echo(f"  Scheduled Ingestions: {data.get('scheduled_ingestion_count', 0)}")
            click.echo(f"  Scheduled Exports: {data.get('scheduled_export_count', 0)}")
            click.echo(f"  Storage: {data.get('storage_gb', 0):.2f} GB")
            click.echo(f"  API Calls (this month): {data.get('api_calls_this_month', 0)}")

            plan_limits = data.get("plan_limits", {})
            usage_percentages = data.get("usage_percentages", {})

            if plan_limits:
                click.echo("\nPlan Limits:")
                for limit_key, max_limit in plan_limits.items():
                    if max_limit is None:
                        click.echo(f"  {limit_key}: Unlimited")
                    else:
                        percentage = usage_percentages.get(limit_key, 0)
                        click.echo(f"  {limit_key}: {max_limit} ({percentage:.1f}% used)")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get usage: {e}")
