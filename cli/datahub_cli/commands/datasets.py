"""
Dataset management commands (278.AA.5).

Provides CLI commands for dataset listing, inspection, version history,
and file refresh. Uses real hub API — no mocks/stubs.
"""

import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def datasets():
    """Dataset management commands"""
    pass


@datasets.command("list")
@click.option("--status", help="Filter by status")
@click.option("--limit", type=int, default=50, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_datasets(
    status: Optional[str],
    limit: int,
    offset: int,
    output_format: str,
):
    """List datasets"""
    try:
        params: dict = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        data = api_client.get("datasets/", params=params)
        results = (
            data.get("results", [])
            if isinstance(data, dict)
            else data if isinstance(data, list)
            else []
        )

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No datasets found.")
                return
            click.echo(
                f"{'ID':<38} {'Name':<30} {'Format':<10} {'Status':<12} {'Rows':>8}"
            )
            click.echo("-" * 100)
            for ds in results:
                if not isinstance(ds, dict):
                    continue
                uid = str(ds.get("id", ""))[:36]
                name = str(ds.get("name", ""))[:28]
                fmt = str(ds.get("format") or ds.get("file_type") or "")[:8]
                status = str(ds.get("status", ""))[:10]
                rows = str(ds.get("row_count") or ds.get("rows") or "")
                click.echo(f"{uid:<38} {name:<30} {fmt:<10} {status:<12} {rows:>8}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list datasets: {e}")


@datasets.command("get")
@click.argument("dataset_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_dataset(dataset_id: str, output_format: str):
    """Get dataset details"""
    try:
        data = api_client.get(f"datasets/{dataset_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"ID:          {data.get('id')}")
            click.echo(f"Name:        {data.get('name')}")
            if data.get("key"):
                click.echo(f"Key:         {data.get('key')}")
            click.echo(f"Format:      {data.get('format') or data.get('file_type')}")
            click.echo(f"Status:      {data.get('status')}")
            if data.get("row_count") is not None:
                click.echo(f"Rows:        {data.get('row_count')}")
            if data.get("size_bytes") is not None:
                size_mb = data["size_bytes"] / (1024 * 1024)
                click.echo(f"Size:        {size_mb:.2f} MB")
            if data.get("description"):
                click.echo(f"Description: {data.get('description')}")
            if data.get("version"):
                click.echo(f"Version:     {data.get('version')}")
            click.echo(f"Created:     {data.get('created_at')}")
            click.echo(f"Updated:     {data.get('updated_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get dataset: {e}")


@datasets.command("versions")
@click.argument("dataset_id")
@click.option("--limit", type=int, default=20, help="Limit number of results")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_versions(dataset_id: str, limit: int, output_format: str):
    """List version history for a dataset"""
    try:
        # Versions are returned as part of the dataset detail or via a dedicated
        # endpoint.  Try the detail endpoint first; it carries a 'versions' key
        # when the serializer includes historical snapshots.
        data = api_client.get(f"datasets/{dataset_id}/", params={"limit": str(limit)})
        versions = data.get("versions") or data.get("version_history") or []

        if output_format == "json":
            click.echo(json.dumps(versions, indent=2))
        else:
            if not versions:
                click.echo("No version history found for this dataset.")
                return
            click.echo(
                f"{'Version':>8} {'Created':<22} {'Rows':>8} {'Size':>10}"
            )
            click.echo("-" * 52)
            for v in versions:
                if not isinstance(v, dict):
                    continue
                ver = str(v.get("version") or v.get("id", ""))[:6]
                created = str(v.get("created_at", ""))[:20]
                rows = str(v.get("row_count") or v.get("rows") or "")
                size = str(v.get("size_bytes") or "")
                if size and size.isdigit():
                    size = f"{int(size) / (1024*1024):.1f} MB"
                click.echo(f"{ver:>8} {created:<22} {rows:>8} {size:>10}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list versions: {e}")


@datasets.command("refresh")
@click.argument("dataset_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def refresh_dataset(dataset_id: str, output_format: str):
    """Refresh a dataset from its source file"""
    try:
        data = api_client.post(f"datasets/{dataset_id}/refresh-from-file/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Refresh triggered for dataset {dataset_id}")
            if data.get("status"):
                click.echo(f"Status:  {data.get('status')}")
            if data.get("job_id"):
                click.echo(f"Job ID:  {data.get('job_id')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to refresh dataset: {e}")
