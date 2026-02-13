"""
GDPR commands (Phase 25).

Provides CLI commands for data export and erasure requests.
Uses real hub API - no mocks/stubs.
"""

import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def gdpr():
    """GDPR data portability and erasure commands"""
    pass


@gdpr.command("export-data")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def request_export(output_format: str):
    """Request data export (GDPR Article 20 - Data Portability)"""
    try:
        data = api_client.post("users/me/export-jobs/export-data/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Export job created: {data.get('job_id')}")
            click.echo(f"Status: {data.get('status')}")
            if data.get("download_url"):
                click.echo(f"Download URL: {data.get('download_url')}")
            if data.get("download_url_expires_at"):
                click.echo(f"Download URL expires at: {data.get('download_url_expires_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to request data export: {e}")


@gdpr.command("export-jobs")
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_export_jobs(limit: int, offset: int, output_format: str):
    """List data export jobs"""
    params = {"limit": limit, "offset": offset}

    try:
        data = api_client.get("users/me/export-jobs/", params=params)
        # Handle both paginated response (dict with 'results') and direct list response
        if isinstance(data, dict):
            results = data.get("results", [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No export jobs found.")
                return

            # Table format
            click.echo(f"{'Job ID':<40} {'Status':<15} {'Created':<25} {'Download URL':<50}")
            click.echo("-" * 130)
            for job in results:
                if not isinstance(job, dict):
                    continue
                job_id = str(job.get("id", ""))[:36] if job.get("id") else ""
                status_val = str(job.get("status", ""))[:13] if job.get("status") else ""
                created = str(job.get("created_at", ""))[:23] if job.get("created_at") else ""
                download_url = (
                    str(job.get("download_url", ""))[:48] if job.get("download_url") else "N/A"
                )
                click.echo(
                    f"{job_id:<40} " f"{status_val:<15} " f"{created:<25} " f"{download_url:<50}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list export jobs: {e}")


@gdpr.command("request-erasure")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def request_erasure(output_format: str):
    """Request data erasure (GDPR Article 17 - Right to be Forgotten)"""
    if not click.confirm(
        "Are you sure you want to request data erasure? This action cannot be undone."
    ):
        click.echo("Cancelled.")
        return

    try:
        data = api_client.post("users/me/erasure-requests/request-erasure/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Erasure request created: {data.get('request_id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Requested at: {data.get('requested_at')}")
            if data.get("completed_at"):
                click.echo(f"Completed at: {data.get('completed_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to request erasure: {e}")


@gdpr.command("erasure-requests")
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_erasure_requests(limit: int, offset: int, output_format: str):
    """List erasure requests"""
    params = {"limit": limit, "offset": offset}

    try:
        data = api_client.get("users/me/erasure-requests/", params=params)
        # Handle both paginated response (dict with 'results') and direct list response
        if isinstance(data, dict):
            results = data.get("results", [])
        elif isinstance(data, list):
            results = data
        else:
            results = []

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No erasure requests found.")
                return

            # Table format
            click.echo(f"{'Request ID':<40} {'Status':<15} {'Requested':<25} {'Completed':<25}")
            click.echo("-" * 105)
            for request in results:
                if not isinstance(request, dict):
                    continue
                request_id = str(request.get("id", ""))[:36] if request.get("id") else ""
                status_val = str(request.get("status", ""))[:13] if request.get("status") else ""
                requested = (
                    str(request.get("requested_at", ""))[:23] if request.get("requested_at") else ""
                )
                completed = (
                    str(request.get("completed_at", ""))[:23]
                    if request.get("completed_at")
                    else "N/A"
                )
                click.echo(
                    f"{request_id:<40} " f"{status_val:<15} " f"{requested:<25} " f"{completed:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list erasure requests: {e}")
