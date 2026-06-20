"""
283.3.6.2 — Processor Agreements CLI commands.

Processor register, Article 28 agreements, and asset–processor links.
"""

from __future__ import annotations

import json

import click

from ..api_client import api_client

BASE = "governance"


@click.group()
def processor_agreements():
    """Processor agreements commands"""


# ── Processor commands ──────────────────────────────────────────────────────


@processor_agreements.group("processors")
def processors():
    """Manage registered processors"""


@processors.command("list")
@click.option("--page", default=1, help="Page number")
@click.option("--page-size", default=25, help="Results per page")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_processors(page: int, page_size: int, output_format: str):
    """List registered processors"""
    data = api_client.get(f"{BASE}/processors/", params={"page": page, "page_size": page_size})
    results = data.get("results", []) if isinstance(data, dict) else []
    if output_format == "json":
        click.echo(json.dumps(results, indent=2, default=str))
        return
    if not results:
        click.echo("No processors registered.")
        return
    click.echo(f"{'ID':<38} {'Name':<30} {'Country':<8} {'Created'}")
    click.echo("-" * 90)
    for r in results:
        click.echo(
            f"{str(r.get('id', ''))[:36]:<38} {r.get('name', ''):<30} {r.get('country_code', ''):<8} {(r.get('created_at', '') or '')[:10]}"
        )


@processors.command("create")
@click.option("--name", required=True, help="Processor name")
@click.option("--legal-name", default="", help="Legal entity name")
@click.option("--country-code", default="", help="ISO 3166-1 alpha-2")
@click.option("--website", default="", help="Public website URL")
@click.option("--notes", default="", help="Internal notes")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def create_processor(
    name: str, legal_name: str, country_code: str, website: str, notes: str, output_format: str
):
    """Register a new processor"""
    data = api_client.post(
        f"{BASE}/processors/",
        json_data={
            "name": name,
            "legal_name": legal_name,
            "country_code": country_code,
            "website": website,
            "notes": notes,
        },
    )
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Created processor: {data.get('id')} — {data.get('name')}")


@processors.command("delete")
@click.argument("processor_id")
@click.confirmation_option(prompt="Are you sure you want to delete this processor?")
def delete_processor(processor_id: str):
    """Delete a processor"""
    api_client.delete(f"{BASE}/processors/{processor_id}/")
    click.echo(f"Deleted processor: {processor_id}")


# ── Agreement commands ──────────────────────────────────────────────────────


@processor_agreements.group("agreements")
def agreements():
    """Manage processor agreements"""


@agreements.command("list")
@click.option("--page", default=1, help="Page number")
@click.option("--page-size", default=25, help="Results per page")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_agreements(page: int, page_size: int, output_format: str):
    """List processor agreements"""
    data = api_client.get(
        f"{BASE}/processor-agreements/", params={"page": page, "page_size": page_size}
    )
    results = data.get("results", []) if isinstance(data, dict) else []
    if output_format == "json":
        click.echo(json.dumps(results, indent=2, default=str))
        return
    if not results:
        click.echo("No agreements found.")
        return
    click.echo(f"{'ID':<38} {'Type':<8} {'Processor':<25} {'Status':<12} {'Effective'}")
    click.echo("-" * 100)
    for r in results:
        click.echo(
            f"{str(r.get('id', ''))[:36]:<38} {r.get('agreement_type', ''):<8} {r.get('processor_name', ''):<25} {r.get('status', ''):<12} {str(r.get('effective_from', ''))[:10]}"
        )


@agreements.command("create")
@click.option("--processor-id", required=True, help="Processor UUID")
@click.option(
    "--type",
    "agreement_type",
    required=True,
    type=click.Choice(["DPA", "BAA", "SCC", "BCR"]),
    help="Agreement type",
)
@click.option("--document-uri", required=True, help="Document URI")
@click.option("--document-hash", required=True, help="SHA-256 hex digest")
@click.option("--effective-from", required=True, help="Effective date (YYYY-MM-DD)")
@click.option("--expires-on", default=None, help="Expiry date (YYYY-MM-DD)")
@click.option("--jurisdiction-region", default="", help="Region hint")
@click.option("--transfer-mechanism", default="", help="Transfer mechanism summary")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def create_agreement(
    processor_id: str,
    agreement_type: str,
    document_uri: str,
    document_hash: str,
    effective_from: str,
    expires_on: str | None,
    jurisdiction_region: str,
    transfer_mechanism: str,
    output_format: str,
):
    """Create a new processor agreement"""
    payload: dict = {
        "processor": processor_id,
        "agreement_type": agreement_type,
        "document_uri": document_uri,
        "document_hash": document_hash,
        "effective_from": effective_from,
    }
    if expires_on:
        payload["expires_on"] = expires_on
    if jurisdiction_region:
        payload["jurisdiction_region"] = jurisdiction_region
    if transfer_mechanism:
        payload["transfer_mechanism_summary"] = transfer_mechanism
    data = api_client.post(f"{BASE}/processor-agreements/", json_data=payload)
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Created agreement: {data.get('id')} ({data.get('agreement_type')})")


@agreements.command("delete")
@click.argument("agreement_id")
@click.confirmation_option(prompt="Are you sure you want to delete this agreement?")
def delete_agreement(agreement_id: str):
    """Delete a processor agreement"""
    api_client.delete(f"{BASE}/processor-agreements/{agreement_id}/")
    click.echo(f"Deleted agreement: {agreement_id}")


# ── Asset–Processor Link commands ───────────────────────────────────────────


@processor_agreements.group("links")
def links():
    """Manage asset–processor links"""


@links.command("list")
@click.option("--page", default=1, help="Page number")
@click.option("--page-size", default=25, help="Results per page")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_links(page: int, page_size: int, output_format: str):
    """List asset–processor links"""
    data = api_client.get(
        f"{BASE}/asset-processor-links/", params={"page": page, "page_size": page_size}
    )
    results = data.get("results", []) if isinstance(data, dict) else []
    if output_format == "json":
        click.echo(json.dumps(results, indent=2, default=str))
        return
    if not results:
        click.echo("No links found.")
        return
    click.echo(f"{'ID':<38} {'Asset':<38} {'Processor':<38}")
    click.echo("-" * 116)
    for r in results:
        click.echo(
            f"{str(r.get('id', ''))[:36]:<38} {str(r.get('asset', ''))[:36]:<38} {str(r.get('processor', ''))[:36]:<38}"
        )


@links.command("create")
@click.option("--asset-id", required=True, help="Asset UUID")
@click.option("--processor-id", required=True, help="Processor UUID")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def create_link(asset_id: str, processor_id: str, output_format: str):
    """Link an asset to a processor"""
    data = api_client.post(
        f"{BASE}/asset-processor-links/",
        json_data={
            "asset": asset_id,
            "processor": processor_id,
        },
    )
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Created link: {data.get('id')}")


@links.command("delete")
@click.argument("link_id")
@click.confirmation_option(prompt="Are you sure you want to delete this link?")
def delete_link(link_id: str):
    """Delete an asset–processor link"""
    api_client.delete(f"{BASE}/asset-processor-links/{link_id}/")
    click.echo(f"Deleted link: {link_id}")
