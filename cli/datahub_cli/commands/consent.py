"""Consent management commands (GDPR compliance)."""


import click

from ..api_client import api_client
from ..output import print_json_output


@click.group()
def consent():
    """Consent management — purposes, records, dashboard."""


# ── Purposes ────────────────────────────────────────────────────────────


@consent.group("purposes")
def consent_purposes():
    """Consent purpose management."""


@consent_purposes.command("list")
def consent_purposes_list():
    """List consent purposes."""
    data = api_client.get("consent/consent-purposes/")
    print_json_output(data)


@consent_purposes.command("create")
@click.option("--name", required=True)
@click.option("--description", required=True)
@click.option("--required/--optional", default=False)
def consent_purposes_create(name, description, required):
    """Create a consent purpose."""
    resp = api_client.post(
        "consent/consent-purposes/",
        json_data={
            "name": name,
            "description": description,
            "required": required,
        },
    )
    print_json_output(resp)


@consent_purposes.command("delete")
@click.argument("purpose_id")
@click.option("--confirm", is_flag=True)
def consent_purposes_delete(purpose_id, confirm):
    """Delete a consent purpose."""
    if not confirm:
        raise click.UsageError("Use --confirm to delete.")
    api_client.delete(f"consent/consent-purposes/{purpose_id}/")
    click.echo(f"Purpose {purpose_id} deleted.")


# ── Records ─────────────────────────────────────────────────────────────


@consent.group("records")
def consent_records():
    """Consent record management."""


@consent_records.command("list")
def consent_records_list():
    """List consent records."""
    data = api_client.get("consent/consent-records/")
    print_json_output(data)


@consent_records.command("create")
@click.option("--purpose-id", required=True)
@click.option("--granted/--denied", default=True)
def consent_records_create(purpose_id, granted):
    """Record a consent decision."""
    resp = api_client.post(
        "consent/consent-records/",
        json_data={
            "purpose_id": purpose_id,
            "granted": granted,
        },
    )
    print_json_output(resp)


# ── Dashboard ───────────────────────────────────────────────────────────


@consent.command("dashboard")
def consent_dashboard():
    """Show consent compliance dashboard."""
    data = api_client.get("consent/consent-dashboard/")
    print_json_output(data)
