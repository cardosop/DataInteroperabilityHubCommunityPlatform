"""
Job management commands.
"""

import json
import time

import click

from ..api_client import api_client


@click.group()
def jobs():
    """Job management commands"""


@jobs.command("list")
@click.option("--type", "job_type", help="Filter by job type")
@click.option("--status", help="Filter by status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)")
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_jobs(
    job_type: str | None, status: str | None, limit: int, offset: int, output_format: str
):
    """List jobs"""
    params = {"limit": limit, "offset": offset}
    if job_type:
        params["type"] = job_type
    if status:
        params["status"] = status

    try:
        # API endpoint structure: /api/v1/jobs/jobs/ (jobs/ from api/urls.py + jobs from router)
        data = api_client.get("jobs/jobs/", params=params)
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
                click.echo("No jobs found.")
                return

            # Table format
            click.echo(f"{'ID':<40} {'Type':<20} {'Status':<15} {'Created':<25}")
            click.echo("-" * 100)
            for job in results:
                created = job.get("created_at", "")[:19] if job.get("created_at") else "N/A"
                click.echo(
                    f"{job.get('id', '')[:36]:<40} "
                    f"{job.get('type', '')[:18]:<20} "
                    f"{job.get('status', '')[:13]:<15} "
                    f"{created:<25}"
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list jobs: {e}")


@jobs.command("get")
@click.argument("job_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_job(job_id: str, output_format: str):
    """Get job details"""
    try:
        # API endpoint structure: /api/v1/jobs/jobs/{id}/ (jobs/ from api/urls.py + jobs from router)
        data = api_client.get(f"jobs/jobs/{job_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"ID: {data.get('id')}")
            click.echo(f"Type: {data.get('type')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Resource Type: {data.get('resource_type')}")
            click.echo(f"Resource ID: {data.get('resource_id')}")
            click.echo(f"Created: {data.get('created_at')}")
            if data.get("started_at"):
                click.echo(f"Started: {data.get('started_at')}")
            if data.get("completed_at"):
                click.echo(f"Completed: {data.get('completed_at')}")
            if data.get("error_message"):
                click.echo(f"Error: {data.get('error_message')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get job: {e}")


@jobs.command("cancel")
@click.argument("job_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def cancel_job(job_id: str, output_format: str):
    """Cancel a job"""
    try:
        # API endpoint structure: /api/v1/jobs/jobs/{id}/cancel/ (jobs/ from api/urls.py + jobs from router)
        result = api_client.post(f"jobs/jobs/{job_id}/cancel/")

        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Job {job_id} cancelled successfully!")
            click.echo(f"Status: {result.get('status')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to cancel job: {e}")


@jobs.command("watch")
@click.argument("job_id")
@click.option("--interval", type=int, default=2, help="Polling interval in seconds")
@click.option("--timeout", type=int, default=300, help="Timeout in seconds")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def watch_job(job_id: str, interval: int, timeout: int, output_format: str):
    """Watch a job until completion"""
    start_time = time.time()

    try:
        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                raise click.ClickException(f"Timeout waiting for job {job_id} to complete")

            # Get job status
            # API endpoint structure: /api/v1/jobs/jobs/{id}/ (jobs/ from api/urls.py + jobs from router)
            data = api_client.get(f"jobs/jobs/{job_id}/")
            status = data.get("status")

            if output_format == "table":
                click.echo(f"Job {job_id}: {status}")

            # Check if job is complete
            if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                if output_format == "json":
                    click.echo(json.dumps(data, indent=2))
                else:
                    click.echo(f"\nJob {status.lower()}!")
                    if status == "COMPLETED":
                        click.echo("Job completed successfully.")
                    elif status == "FAILED":
                        if data.get("error_message"):
                            click.echo(f"Error: {data.get('error_message')}")
                    elif status == "CANCELLED":
                        click.echo("Job was cancelled.")
                return

            # Wait before next poll
            time.sleep(interval)
    except click.ClickException:
        raise
    except KeyboardInterrupt:
        click.echo("\nWatching cancelled by user.")
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to watch job: {e}")
