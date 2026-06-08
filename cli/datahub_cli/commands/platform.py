"""
283.5.6 — Platform admin CLI commands (PLATFORM_ADMIN gated).
"""
from __future__ import annotations

import json

import click

from ..api_client import api_client


@click.group()
def platform():
    """Platform admin commands (PLATFORM_ADMIN only)"""
    pass


# ── Tenant management ───────────────────────────────────────────────────────

@platform.group("tenants")
def tenants():
    """Manage tenants"""
    pass


@tenants.command("list")
@click.option("--page", default=1)
@click.option("--page-size", default=25)
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def list_tenants(page, page_size, output_format):
    """List all tenants"""
    data = api_client.get("admin/tenants/", params={"page": page, "page_size": page_size})
    results = data.get("results", []) if isinstance(data, dict) else []
    if output_format == "json":
        click.echo(json.dumps(results, indent=2, default=str))
        return
    if not results:
        click.echo("No tenants found.")
        return
    for r in results:
        click.echo(f"{r.get('id','')}  {r.get('slug','')}  {r.get('display_name','')}  {r.get('status','')}")


@tenants.command("create")
@click.option("--slug", required=True)
@click.option("--display-name", required=True)
@click.option("--admin-email", required=True)
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def create_tenant(slug, display_name, admin_email, output_format):
    """Create a new tenant"""
    data = api_client.post("admin/tenants/", json_data={
        "slug": slug, "display_name": display_name, "admin_email": admin_email,
    })
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Created tenant: {data.get('id')} ({data.get('slug')})")


@tenants.command("get")
@click.argument("tenant_id")
def get_tenant(tenant_id):
    """Get tenant details"""
    data = api_client.get(f"admin/tenants/{tenant_id}/")
    click.echo(json.dumps(data, indent=2, default=str))


@tenants.command("delete")
@click.argument("tenant_id")
@click.confirmation_option(prompt="Permanently delete this tenant?")
def delete_tenant(tenant_id):
    """Delete a tenant"""
    api_client.delete(f"admin/tenants/{tenant_id}/")
    click.echo(f"Deleted tenant: {tenant_id}")


# ── User management ─────────────────────────────────────────────────────────

@platform.group("users")
def users():
    """Manage users (PLATFORM_ADMIN)"""
    pass


@users.command("list")
@click.option("--page", default=1)
@click.option("--page-size", default=25)
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def list_users(page, page_size, output_format):
    """List all users"""
    data = api_client.get("admin/users/", params={"page": page, "page_size": page_size})
    results = data.get("results", []) if isinstance(data, dict) else []
    if output_format == "json":
        click.echo(json.dumps(results, indent=2, default=str))
        return
    if not results:
        click.echo("No users found.")
        return
    for r in results:
        click.echo(f"{r.get('id','')}  {r.get('email','')}  {r.get('status','')}")


@users.command("create")
@click.option("--email", required=True)
@click.option("--tenant-id", required=True)
@click.option("--display-name", default="")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def create_user(email, tenant_id, display_name, output_format):
    """Create a new user"""
    data = api_client.post("admin/users/", json_data={
        "email": email, "tenant_id": tenant_id, "display_name": display_name,
    })
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Created user: {data.get('id')} ({data.get('email')})")


@users.command("get")
@click.argument("user_id")
def get_user(user_id):
    """Get user details"""
    data = api_client.get(f"admin/users/{user_id}/")
    click.echo(json.dumps(data, indent=2, default=str))


# ── Impersonation ───────────────────────────────────────────────────────────

@platform.command("impersonate")
@click.option("--user-id", required=True)
@click.option("--tenant-id", required=True)
@click.option("--reason", required=True, help="Justification for audit trail")
def impersonate(user_id, tenant_id, reason):
    """Start impersonation session"""
    data = api_client.post("admin/impersonate/", json_data={
        "user_id": user_id, "tenant_id": tenant_id, "reason": reason,
    })
    click.echo(json.dumps(data, indent=2, default=str))


@platform.command("impersonate-exit")
def impersonate_exit():
    """End current impersonation session"""
    data = api_client.post("admin/impersonate/exit/")
    click.echo(json.dumps(data, indent=2, default=str))
