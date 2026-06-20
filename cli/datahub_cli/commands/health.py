"""
Health check commands.

Provides CLI commands for checking backend health at multiple levels:
API info, component status, circuit breakers, liveness/readiness probes.
Uses real hub API - no mocks/stubs.
"""

import json

import click

from ..api_client import api_client


@click.group()
def health():
    """Health check commands"""


@health.command("check")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def check_health(output_format: str):
    """Check backend health status.

    Calls the server-root ``/health/`` endpoint (NOT the API info root at
    ``/api/v1/``) so the output matches :meth:`DataHubClient.check_health`.
    """
    try:
        # The health endpoint lives at the server root, outside the API
        # prefix.  Use raw ``requests`` to avoid the base_url prefix that
        # ``api_client._request`` applies.
        from urllib.parse import urlparse

        import requests as _requests

        base = api_client._get_base_url()
        parsed = urlparse(base)
        health_url = f"{parsed.scheme}://{parsed.netloc}/health/"

        resp = _requests.get(health_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Status: {data.get('status', 'Unknown')}")
            click.echo(f"Database: {data.get('database', 'Unknown')}")
            redis_info = data.get("redis", {})
            if isinstance(redis_info, dict):
                for k, v in redis_info.items():
                    click.echo(f"  Redis {k}: {v}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to check health: {e}")


@health.command("components")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def check_components(output_format: str):
    """Check component-level health (database, redis, clamav, baas)"""
    try:
        data = api_client.get("/health/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Overall Status: {data.get('status', 'unknown')}")
            click.echo(f"Database:      {data.get('database', 'unknown')}")
            redis_status = data.get("redis", {})
            click.echo("Redis:")
            for instance, status in redis_status.items():
                click.echo(f"  {instance}: {status}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to check components: {e}")


@health.command("circuit-breakers")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def check_circuit_breakers(output_format: str):
    """Check circuit breaker status (requires authentication)"""
    try:
        data = api_client.get("/health/circuit-breakers/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Status:          {data.get('status', 'unknown')}")
            click.echo(f"Total Breakers:  {data.get('total_breakers', 0)}")
            click.echo(f"Open Breakers:   {data.get('open_breakers', 0)}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to check circuit breakers: {e}")


@health.command("live")
def check_liveness():
    """Check liveness probe (process is up, no DB/Redis)"""
    try:
        data = api_client.get("/health/live/")
        status = data.get("status", "unknown")
        click.echo(f"Liveness: {status}")
        if status != "ok":
            raise click.ClickException(f"Liveness check failed: {status}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to check liveness: {e}")
