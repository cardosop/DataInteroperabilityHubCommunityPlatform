"""
284.A.4 — Federated Import CLI commands.

Provides ``datahub federated-import`` commands for listing providers,
creating import jobs, checking status, and cancelling.
"""

from __future__ import annotations

import json

import click

from ..api_client import api_client


@click.group()
def federated_import():
    """Federated marketplace import management"""


@federated_import.group("providers")
def providers():
    """Manage federated import providers"""


@providers.command("list")
@click.option("--json", "as_json", is_flag=True, help="Emit raw JSON")
def list_providers(as_json: bool):
    """List supported federated import providers.

    \b
    Examples:
        datahub federated-import providers list
        datahub federated-import providers list --json
    """
    data = api_client.get("integrations/federated-import/providers/")
    items = data.get("providers", data) if isinstance(data, dict) else data
    if as_json:
        click.echo(json.dumps(items, indent=2, default=str))
    else:
        if not items:
            click.echo("No providers available.")
            return
        click.echo(f"{'ID':<30} {'NAME':<30} {'CREDENTIAL TYPE':<25}")
        click.echo("-" * 85)
        for p in items:
            if isinstance(p, dict):
                click.echo(
                    f"{p.get('id', '?'):<30} {p.get('name', '?'):<30} {p.get('credential_type', '?'):<25}"
                )


@federated_import.group("import")
def import_group():
    """Manage federated import jobs"""


@import_group.command("create")
@click.option("--provider-id", required=True, help="Provider id from 'providers list'")
@click.option("--credential-ref", required=True, help="AWS Secrets Manager ARN (never raw creds)")
@click.option("--external-listing-id", default="", help="External listing id to import")
@click.option(
    "--data-strategy",
    type=click.Choice(["METADATA_ONLY", "DOWNLOAD_SELECTIVE", "DOWNLOAD_ALL"]),
    default="METADATA_ONLY",
    show_default=True,
    help="Data download strategy",
)
@click.option("--json", "as_json", is_flag=True, help="Emit raw JSON")
def create_import(
    provider_id: str,
    credential_ref: str,
    external_listing_id: str,
    data_strategy: str,
    as_json: bool,
):
    """Create a federated import job. Returns job id for status polling.

    \b
    Examples:
        datahub federated-import import create \\
            --provider-id snowflake_marketplace \\
            --credential-ref arn:aws:secretsmanager:us-east-1:123456789:secret:my-creds
    """
    payload = {
        "provider_id": provider_id,
        "credential_ref": credential_ref,
        "data_strategy": data_strategy,
    }
    if external_listing_id:
        payload["external_listing_id"] = external_listing_id

    resp = api_client.request(
        "POST",
        "integrations/federated-import/imports/",
        json_data=payload,
    )
    if not resp.ok:
        detail = resp.json() if resp.text else {"error": resp.text[:500]}
        raise click.ClickException(f"Import creation failed (HTTP {resp.status_code}): {detail}")
    data = resp.json()
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo("Import job created.")
        click.echo(f"  Job ID:      {data.get('id', '?')}")
        click.echo(f"  Status:      {data.get('status', '?')}")
        click.echo(f"  Provider:    {data.get('provider_id', '?')}")
        click.echo(f"  Strategy:    {data.get('data_strategy', '?')}")


@import_group.command("status")
@click.argument("job_id")
@click.option("--json", "as_json", is_flag=True, help="Emit raw JSON")
def import_status(job_id: str, as_json: bool):
    """Get federated import job status.

    \b
    Examples:
        datahub federated-import import status abc-123-def
    """
    data = api_client.get(f"integrations/federated-import/imports/{job_id}/")
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Job:         {data.get('id', job_id)}")
        click.echo(f"Type:        {data.get('type', '?')}")
        click.echo(f"Status:      {data.get('status', '?')}")
        click.echo(f"Created:     {data.get('created_at', '?')}")
        if data.get("updated_at"):
            click.echo(f"Updated:     {data['updated_at']}")
        if data.get("completed_at"):
            click.echo(f"Completed:   {data['completed_at']}")


@import_group.command("cancel")
@click.argument("job_id")
@click.option("--confirm", is_flag=True, help="Skip interactive confirmation")
@click.option("--json", "as_json", is_flag=True, help="Emit raw JSON")
def cancel_import(job_id: str, confirm: bool, as_json: bool):
    """Cancel a pending or running federated import job.

    \b
    Examples:
        datahub federated-import import cancel abc-123-def --confirm
    """
    if not confirm:
        click.echo(f"WARNING: This will cancel federated import job {job_id}.")
        if not click.confirm("Continue?"):
            click.echo("Aborted.")
            return

    resp = api_client.request(
        "POST",
        f"integrations/federated-import/imports/{job_id}/cancel/",
    )
    if not resp.ok:
        detail = resp.json() if resp.text else {"error": resp.text[:500]}
        raise click.ClickException(f"Cancel failed (HTTP {resp.status_code}): {detail}")
    data = resp.json()
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Cancelled job {data.get('id', job_id)}. Status: {data.get('status', '?')}")
