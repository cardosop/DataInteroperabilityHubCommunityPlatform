"""
Tenant management commands.

Covers tenant usage, configuration, feature flags, tax ID, plan management,
seed data, and admin operations (PLATFORM_ADMIN gated).
"""

import json

import click

from ..api_client import api_client


@click.group()
def tenants():
    """Tenant management — usage, config, plans, feature flags."""


# ── List ──────────────────────────────────────────────────────────────────


@tenants.command("list")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
@click.option("--page", type=int, default=1)
@click.option("--page-size", type=int, default=25)
def list_tenants(output_format, page, page_size):
    """List tenants accessible to the current user."""
    try:
        data = api_client.get("tenants/", params={"page": page, "page_size": page_size})
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            results = data.get("results", [])
            if not results:
                click.echo("(no tenants)")
                return
            for t in results:
                click.echo(f"{t.get('id', '?')}  {t.get('slug', t.get('display_name', '?'))}")
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)


# ── Usage ────────────────────────────────────────────────────────────────


@tenants.command("usage")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def get_usage(output_format):
    """Get current tenant usage."""
    try:
        data = api_client.get("tenants/me/usage/")
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Plan: {data.get('plan_slug')} ({data.get('plan_tier')})")
            click.echo(f"  Assets: {data.get('asset_count', 0)}")
            click.echo(f"  Datasets: {data.get('dataset_count', 0)}")
            click.echo(f"  Storage: {data.get('storage_gb', 0):.2f} GB")
            click.echo(f"  API Calls: {data.get('api_calls_this_month', 0)}")
    except Exception as e:
        raise click.ClickException(str(e))


# ── Profile / Config ─────────────────────────────────────────────────────


@tenants.command("me")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def tenants_me(output_format):
    """Show current tenant details."""
    data = api_client.get("tenants/me/")
    if output_format == "json":
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"Name:   {data.get('name', 'N/A')}")
        click.echo(f"Slug:   {data.get('slug', 'N/A')}")
        click.echo(f"Status: {data.get('status', 'N/A')}")
        click.echo(f"KYC:    {data.get('kyc_status', 'N/A')}")


@tenants.group("config")
def tenants_config():
    """Tenant configuration."""


@tenants_config.command("get")
def tenants_config_get():
    """Get current tenant configuration."""
    data = api_client.get("tenants/me/config/")
    click.echo(json.dumps(data, indent=2))


@tenants_config.command("update")
@click.option("--key", required=True, help="Config key to update")
@click.option("--value", required=True, help="New value (JSON-compatible)")
def tenants_config_update(key, value):
    """Update a tenant configuration value."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = value
    resp = api_client.patch("tenants/me/config/", json={key: parsed})
    click.echo(json.dumps(resp, indent=2))


# ── Feature Flags ────────────────────────────────────────────────────────


@tenants.group("feature-flags")
def tenants_feature_flags():
    """Feature flag management."""


@tenants_feature_flags.command("list")
def tenants_feature_flags_list():
    """List feature flags for the current tenant."""
    data = api_client.get("tenants/me/feature-flags/")
    click.echo(json.dumps(data, indent=2))


@tenants_feature_flags.command("update")
@click.option("--flag", required=True, help="Flag name to toggle")
@click.option("--enable/--disable", default=True, help="Enable or disable the flag")
def tenants_feature_flags_update(flag, enable):
    """Enable or disable a feature flag."""
    resp = api_client.patch("tenants/me/feature-flags/", json={flag: enable})
    click.echo(json.dumps(resp, indent=2))


@tenants_feature_flags.command("history")
def tenants_feature_flags_history():
    """Show feature flag change history."""
    data = api_client.get("tenants/me/feature-flag-history/")
    click.echo(json.dumps(data, indent=2))


# ── Tax ID ───────────────────────────────────────────────────────────────


@tenants.group("tax-id")
def tenants_tax_id():
    """Tax ID management."""


@tenants_tax_id.command("get")
def tenants_tax_id_get():
    """Get current tax ID."""
    data = api_client.get("tenants/me/tax-id/")
    click.echo(json.dumps(data, indent=2))


@tenants_tax_id.command("submit")
@click.option("--tax-id", required=True, help="Tax identification number")
@click.option("--country", required=True, help="ISO 3166-1 alpha-2 country code")
def tenants_tax_id_submit(tax_id, country):
    """Submit or update tax ID."""
    resp = api_client.post("tenants/me/tax-id/", json={"tax_id": tax_id, "country": country})
    click.echo(json.dumps(resp, indent=2))


# ── Seed Sample Data ─────────────────────────────────────────────────────


@tenants.command("seed-sample")
def tenants_seed_sample():
    """Seed sample demo data into the current tenant."""
    resp = api_client.post("tenants/me/seed-sample/", json={})
    click.echo(json.dumps(resp, indent=2))


# ── Plan Management ──────────────────────────────────────────────────────


@tenants.group("plan")
def tenants_plan():
    """Plan and subscription management."""


@tenants_plan.command("info")
def tenants_plan_info():
    """Show current plan details."""
    data = api_client.get("tenants/me/plan/")
    click.echo(json.dumps(data, indent=2))


@tenants_plan.command("available-upgrades")
def tenants_plan_available_upgrades():
    """List available plan upgrades."""
    data = api_client.get("tenants/me/plan/available-upgrades/")
    click.echo(json.dumps(data, indent=2))


@tenants_plan.command("upgrade")
@click.option("--plan-slug", required=True, help="Target plan slug")
@click.option("--confirm", is_flag=True, help="Confirm the upgrade")
def tenants_plan_upgrade(plan_slug, confirm):
    """Upgrade to a higher plan tier."""
    if not confirm:
        raise click.UsageError("Use --confirm to proceed with plan upgrade.")
    resp = api_client.post("tenants/me/plan/upgrade/", json={"plan_slug": plan_slug})
    click.echo(json.dumps(resp, indent=2))


@tenants_plan.command("downgrade")
@click.option("--plan-slug", required=True, help="Target plan slug")
@click.option("--confirm", is_flag=True, help="Confirm the downgrade")
def tenants_plan_downgrade(plan_slug, confirm):
    """Downgrade to a lower plan tier."""
    if not confirm:
        raise click.UsageError("Use --confirm to proceed with plan downgrade.")
    resp = api_client.post("tenants/me/plan/downgrade/", json={"plan_slug": plan_slug})
    click.echo(json.dumps(resp, indent=2))


@tenants_plan.command("ml-addons")
def tenants_plan_ml_addons():
    """List available ML add-ons."""
    data = api_client.get("tenants/me/plan/available-ml-addons/")
    click.echo(json.dumps(data, indent=2))


# ── Onboarding ───────────────────────────────────────────────────────────


@tenants.command("onboarding")
@click.option("--tenant-name", required=True)
@click.option("--email", required=True)
@click.option("--password", required=True, hide_input=True)
@click.option("--display-name", default=None)
def tenants_onboarding(tenant_name, email, password, display_name):
    """Create a tenant with initial admin user (onboarding flow)."""
    body = {"tenant_name": tenant_name, "email": email, "password": password}
    if display_name:
        body["display_name"] = display_name
    resp = api_client.post("tenants/onboarding/", json=body)
    click.echo(json.dumps(resp, indent=2))


# ── Admin Operations (PLATFORM_ADMIN gated) ──────────────────────────────


@tenants.group("admin")
def tenants_admin():
    """Admin operations (requires PLATFORM_ADMIN role)."""


@tenants_admin.command("list")
def tenants_admin_list():
    """List all tenants (platform admin)."""
    data = api_client.get("admin/tenants/")
    click.echo(json.dumps(data, indent=2))


@tenants_admin.command("create")
@click.option("--name", required=True)
@click.option("--slug", required=True)
@click.option("--email", required=True, help="Admin user email")
@click.option("--password", required=True, hide_input=True)
def tenants_admin_create(name, slug, email, password):
    """Create a new tenant (platform admin)."""
    resp = api_client.post(
        "admin/tenants/",
        json={
            "name": name,
            "slug": slug,
            "email": email,
            "password": password,
        },
    )
    click.echo(json.dumps(resp, indent=2))


@tenants_admin.command("delete")
@click.argument("tenant_id")
@click.option("--confirm", is_flag=True)
def tenants_admin_delete(tenant_id, confirm):
    """Delete a tenant (platform admin)."""
    if not confirm:
        raise click.UsageError("Use --confirm to delete. This cannot be undone.")
    api_client.delete(f"admin/tenants/{tenant_id}/")
    click.echo(f"Tenant {tenant_id} deleted.")


@tenants_admin.command("feature-flags")
@click.argument("tenant_id")
def tenants_admin_feature_flags(tenant_id):
    """View feature flags for any tenant (platform admin)."""
    data = api_client.get(f"admin/tenants/{tenant_id}/feature-flags/")
    click.echo(json.dumps(data, indent=2))


@tenants_admin.command("impersonate")
@click.option("--user-id", required=True, help="User ID to impersonate")
@click.option("--tenant-id", required=True, help="Tenant ID the user belongs to")
def tenants_admin_impersonate(user_id, tenant_id):
    """Impersonate a user (platform admin)."""
    resp = api_client.post("admin/impersonate/", json={"user_id": user_id, "tenant_id": tenant_id})
    click.echo(json.dumps(resp, indent=2))


@tenants_admin.command("impersonate-exit")
def tenants_admin_impersonate_exit():
    """Exit impersonation mode."""
    resp = api_client.post("admin/impersonate/exit/", json={})
    click.echo(json.dumps(resp, indent=2))
