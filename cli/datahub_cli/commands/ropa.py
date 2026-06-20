"""
283.3.3.2 — RoPA CLI commands.

Record of Processing Activities (GDPR Article 30) generation and management.
"""

from __future__ import annotations

import json
import time

import click

from ..api_client import api_client

REGULATION_MAP = {
    "GDPR": "General Data Protection Regulation (EU) 2016/679",
    "UK_GDPR": "UK General Data Protection Regulation",
    "LGPD": "Lei Geral de Protecao de Dados (Brazil)",
    "CCPA": "California Consumer Privacy Act",
    "PIPEDA": "Personal Information Protection and Electronic Documents Act (Canada)",
    "PDPA": "Personal Data Protection Act (Singapore)",
}

ROPA_BASE = "ropa/generations"


@click.group()
def ropa():
    """RoPA (Record of Processing Activities) commands"""


# ── list ────────────────────────────────────────────────────────────────────


@ropa.command("list")
@click.option("--page", default=1, help="Page number")
@click.option("--page-size", default=25, help="Results per page")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_records(page: int, page_size: int, output_format: str):
    """List RoPA generations for the active tenant."""
    try:
        data = api_client.get(f"{ROPA_BASE}/", params={"page": page, "page_size": page_size})
    except Exception as exc:
        raise click.ClickException(str(exc))

    results = data.get("results", []) if isinstance(data, dict) else []
    if output_format == "json":
        click.echo(json.dumps(results, indent=2))
        return

    if not results:
        click.echo("No RoPA generations found.")
        return

    click.echo(f"{'ID':<38} {'Regulation':<12} {'Format':<8} {'Status':<14} {'Created'}")
    click.echo("-" * 90)
    for r in results:
        rid = str(r.get("id", ""))[:36]
        reg = r.get("regulation", "")
        fmt = r.get("output_format", "")
        status = r.get("status", "")
        created = (r.get("created_at") or "")[:10]
        click.echo(f"{rid:<38} {reg:<12} {fmt:<8} {status:<14} {created}")


# ── get ─────────────────────────────────────────────────────────────────────


@ropa.command("get")
@click.argument("record_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_record(record_id: str, output_format: str):
    """Retrieve a single RoPA generation by ID."""
    try:
        data = api_client.get(f"{ROPA_BASE}/{record_id}/")
    except Exception as exc:
        raise click.ClickException(str(exc))

    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
        return

    click.echo(f"ID:              {data.get('id')}")
    click.echo(f"Regulation:      {data.get('regulation')}")
    click.echo(f"Output Format:   {data.get('output_format')}")
    click.echo(f"Status:          {data.get('status')}")
    click.echo(f"Byte Size:       {data.get('byte_size', 0)}")
    click.echo(f"Created At:      {data.get('created_at')}")
    click.echo(f"Completed At:    {data.get('completed_at', 'N/A')}")
    if data.get("error_message"):
        click.echo(f"Error:           {data['error_message']}")
    summary = data.get("summary_json", {})
    if summary:
        click.echo(f"Asset Count:     {summary.get('asset_count', 'N/A')}")
    gaps = data.get("gaps_json", [])
    if gaps:
        click.echo(f"Gaps:            {len(gaps)}")


# ── preview ─────────────────────────────────────────────────────────────────


@ropa.command("preview")
@click.option(
    "--regulation",
    default="GDPR",
    type=click.Choice(list(REGULATION_MAP.keys())),
    help="Regulation to preview",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def preview(regulation: str, output_format: str):
    """Preview a RoPA payload without generating an artefact."""
    try:
        data = api_client.get(f"{ROPA_BASE}/preview/", params={"regulation": regulation})
    except Exception as exc:
        raise click.ClickException(str(exc))

    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
        return

    click.echo(f"Regulation:     {data.get('regulation')}")
    click.echo(f"Cache Hit:      {data.get('cache_hit', False)}")
    summary = data.get("summary", {})
    click.echo(f"Asset Count:    {summary.get('asset_count', 'N/A')}")
    click.echo(f"Gap Count:      {summary.get('gap_count', 'N/A')}")
    gaps = data.get("gaps", [])
    if gaps:
        click.echo(f"\nGaps ({len(gaps)}):")
        for g in gaps[:20]:
            click.echo(f"  [{g.get('code')}] {g.get('asset_key', '?')}: {g.get('message', '')}")
        if len(gaps) > 20:
            click.echo(f"  ... and {len(gaps) - 20} more")


# ── generate ────────────────────────────────────────────────────────────────


@ropa.command("generate")
@click.option(
    "--regulation",
    default="GDPR",
    type=click.Choice(list(REGULATION_MAP.keys())),
    help="Regulation to generate for",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "csv", "pdf", "docx"]),
    default="json",
    help="Output format",
)
@click.option("--wait/--no-wait", default=False, help="Poll until generation completes")
@click.option("--timeout", default=120, help="Max wait time in seconds (with --wait)")
def generate(regulation: str, output_format: str, wait: bool, timeout: int):
    """Generate a new RoPA artefact."""
    try:
        data = api_client.post(
            "ropa/generate/",
            params={"regulation": regulation, "format": output_format},
        )
    except Exception as exc:
        raise click.ClickException(str(exc))

    click.echo(json.dumps(data, indent=2, default=str))

    if not wait or not data.get("async"):
        return

    ropa_id = data.get("ropa_generation_id")
    if not ropa_id:
        click.echo("No ropa_generation_id in response; cannot poll.")
        return

    start = time.monotonic()
    while time.monotonic() - start < timeout:
        time.sleep(2)
        try:
            status_data = api_client.get(f"{ROPA_BASE}/{ropa_id}/")
        except Exception:
            continue
        st = status_data.get("status", "")
        click.echo(f"  ... {st}")
        if st == "COMPLETED":
            click.echo(f"\nGeneration complete! ID: {ropa_id}")
            return
        if st == "FAILED":
            raise click.ClickException(
                f"Generation failed: {status_data.get('error_message', 'unknown')}"
            )

    raise click.ClickException(f"Generation did not complete within {timeout}s")


# ── download ────────────────────────────────────────────────────────────────


@ropa.command("download")
@click.argument("record_id")
def download_ropa(record_id: str):
    """Get a presigned download URL for a completed RoPA artefact."""
    try:
        data = api_client.get(f"{ROPA_BASE}/{record_id}/download/")
    except Exception as exc:
        raise click.ClickException(str(exc))

    url = data.get("download_url", "")
    if url:
        click.echo(f"Download URL (expires in {data.get('expires_in', 3600)}s):")
        click.echo(url)
    else:
        click.echo(json.dumps(data, indent=2))


# ── delete ──────────────────────────────────────────────────────────────────


@ropa.command("delete")
@click.argument("record_id")
@click.confirmation_option(prompt="Are you sure you want to delete this RoPA generation?")
def delete_record(record_id: str):
    """Delete a RoPA generation."""
    try:
        api_client.delete(f"{ROPA_BASE}/{record_id}/delete/")
    except Exception as exc:
        raise click.ClickException(str(exc))
    click.echo(f"Deleted RoPA generation: {record_id}")


# ── regulation-map ──────────────────────────────────────────────────────────


@ropa.command("regulation-map")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def regulation_map(output_format: str):
    """Print the map of supported regulation keys to human-readable names."""
    if output_format == "json":
        click.echo(json.dumps(REGULATION_MAP, indent=2))
        return

    click.echo(f"{'Key':<16} Description")
    click.echo("-" * 70)
    for key, desc in REGULATION_MAP.items():
        click.echo(f"{key:<16} {desc}")
