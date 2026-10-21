"""
Authentication and session management commands.

Covers all /api/v1/auth/ endpoints — login, registration, password reset,
email verification, invitations, sessions, API keys, and SSO.
"""


import click

from ..api_client import api_client
from ..auth import login_command
from ..output import print_json_output


@click.group()
def auth():
    """Authentication, sessions, API keys, and SSO."""


# ── Login / Logout / Register ──────────────────────────────────────────


@auth.command("login")
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True)
def auth_login(email, password):
    """Login with email and password."""
    # W6.3 — the SAME implementation as `datahub login` (dedupe):
    # identical success output and identical non-zero exit on failure.
    login_command(email, password)


@auth.command("logout")
def auth_logout():
    """Logout and clear stored credentials."""
    from ..auth import auth_manager

    auth_manager.logout()
    click.echo("Logged out.")


@auth.command("register")
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True)
@click.option("--tenant-name", prompt="Tenant name")
@click.option("--display-name", default=None)
def auth_register(email, password, tenant_name, display_name):
    """Register a new account."""
    body = {"email": email, "password": password, "tenant_name": tenant_name}
    if display_name:
        body["display_name"] = display_name
    resp = api_client.post("auth/register/", json_data=body)
    print_json_output(resp)


# ── Profile ────────────────────────────────────────────────────────────


@auth.command("me")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def auth_me(output_format):
    """Show current user profile."""
    data = api_client.get("auth/me/")
    if output_format == "json":
        print_json_output(data)
    else:
        click.echo(f"Email:    {data.get('email', 'N/A')}")
        click.echo(f"Name:     {data.get('display_name', 'N/A')}")
        click.echo(f"Tenant:   {data.get('tenant', {}).get('name', 'N/A')}")
        click.echo(f"Status:   {data.get('status', 'N/A')}")


@auth.command("me-update")
@click.option("--display-name", default=None, help="New display name")
@click.option("--email", default=None, help="New email address")
def auth_me_update(display_name, email):
    """Update current user profile."""
    body = {}
    if display_name:
        body["display_name"] = display_name
    if email:
        body["email"] = email
    if not body:
        raise click.UsageError("At least one of --display-name or --email is required")
    resp = api_client.patch("auth/me/", json_data=body)
    print_json_output(resp)


@auth.command("tenants")
def auth_tenants():
    """List accessible tenants for the current user."""
    data = api_client.get("auth/me/tenants/")
    print_json_output(data)


@auth.command("switch-tenant")
@click.option("--tenant-id", required=True, help="Target tenant ID")
def auth_switch_tenant(tenant_id):
    """Switch the active tenant context."""
    resp = api_client.post("auth/switch-tenant/", json_data={"tenant_id": tenant_id})
    print_json_output(resp)


@auth.command("refresh")
def auth_refresh():
    """Refresh the JWT token."""
    try:
        api_client.post("auth/refresh/", json_data={})
        click.echo("Token refreshed.")
    except Exception as e:
        raise click.ClickException(f"Token refresh failed: {e}") from e


# ── Password Reset ─────────────────────────────────────────────────────


@auth.group("password-reset")
def auth_password_reset():
    """Password reset operations."""


@auth_password_reset.command("request")
@click.option("--email", prompt=True)
def auth_password_reset_request(email):
    """Request a password reset email."""
    resp = api_client.post("auth/password-reset/", json_data={"email": email})
    print_json_output(resp)


@auth_password_reset.command("confirm")
@click.option("--token", required=True, help="Reset token from email")
@click.option("--new-password", prompt=True, hide_input=True)
def auth_password_reset_confirm(token, new_password):
    """Confirm a password reset with token and new password."""
    resp = api_client.post(
        "auth/password-reset/confirm/",
        json_data={"token": token, "new_password": new_password},
    )
    print_json_output(resp)


# ── Email Verification ──────────────────────────────────────────────────


@auth.command("verify-email")
@click.option("--token", required=True)
def auth_verify_email(token):
    """Verify email address with token."""
    resp = api_client.post("auth/verify-email/", json_data={"token": token})
    print_json_output(resp)


@auth.command("resend-verification")
@click.option("--email", prompt=True)
def auth_resend_verification(email):
    """Resend the email verification message."""
    resp = api_client.post("auth/resend-verification/", json_data={"email": email})
    print_json_output(resp)


@auth.command("accept-invitation")
@click.option("--token", required=True)
def auth_accept_invitation(token):
    """Accept a tenant invitation with token."""
    resp = api_client.post("auth/accept-invitation/", json_data={"token": token})
    print_json_output(resp)


# ── Sessions ────────────────────────────────────────────────────────────


@auth.group("sessions")
def auth_sessions():
    """Active session management."""


@auth_sessions.command("list")
def auth_sessions_list():
    """List all active sessions."""
    data = api_client.get("auth/sessions/")
    print_json_output(data)


@auth_sessions.command("end-all-others")
def auth_sessions_end_all_others():
    """End all sessions except the current one."""
    resp = api_client.post("auth/sessions/end-all-others/", json_data={})
    print_json_output(resp)


# ── API Keys ────────────────────────────────────────────────────────────


@auth.group("api-keys")
def auth_api_keys():
    """API key management."""


@auth_api_keys.command("list")
def auth_api_keys_list():
    """List API keys."""
    data = api_client.get("auth/api-keys/")
    print_json_output(data)


@auth_api_keys.command("create")
@click.option("--name", required=True, help="Key name/label")
@click.option("--scopes", default="", help="Comma-separated scope list")
def auth_api_keys_create(name, scopes):
    """Create a new API key.

    W6.5 (S1): ``--scopes`` is validated against the carried scope
    vocabulary BEFORE the request — a typo'd or unmintable scope fails
    fast with a clear error instead of a round-trip 400 (the backend
    still enforces the role allowlist — R2-B2).
    """
    body = {"name": name}
    if scopes:
        scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
        from datahub_cli.scopes import ALL_SCOPES, validate_scopes

        invalid = validate_scopes(scope_list)
        if invalid:
            raise click.ClickException(
                f"Invalid scope(s): {', '.join(invalid)}. "
                f"Valid scopes: {', '.join(sorted(ALL_SCOPES))}. "
                "'*' is PLATFORM_ADMIN-only; "
                "'scheduled_ingestion:internal' is never mintable."
            )
        body["scopes"] = scope_list
    resp = api_client.post("auth/api-keys/", json_data=body)
    # Show the key value once — it won't be retrievable again.
    key_value = resp.get("key") or resp.get("plain_text_key")
    if key_value:
        click.echo(f"API Key (save this — it won't be shown again): {key_value}")
    print_json_output({k: v for k, v in resp.items() if k not in ("key", "plain_text_key")})


@auth_api_keys.command("revoke")
@click.option("--key-id", required=True, help="API key ID to revoke")
def auth_api_keys_revoke(key_id):
    """Revoke an API key."""
    resp = api_client.post(f"auth/api-keys/{key_id}/revoke/", json_data={})
    print_json_output(resp)


# ── SSO ─────────────────────────────────────────────────────────────────


@auth.group("sso")
def auth_sso():
    """SSO provider configuration."""


@auth_sso.command("list")
def auth_sso_list():
    """List SSO configurations."""
    data = api_client.get("auth/sso/")
    print_json_output(data)


@auth_sso.command("create")
@click.option("--provider", required=True, type=click.Choice(["google", "microsoft", "saml"]))
@click.option("--client-id", required=True)
@click.option("--client-secret", required=True)
@click.option("--domain", required=True)
def auth_sso_create(provider, client_id, client_secret, domain):
    """Create an SSO provider configuration."""
    resp = api_client.post(
        "auth/sso/",
        json_data={
            "provider": provider,
            "client_id": client_id,
            "client_secret": client_secret,
            "domain": domain,
        },
    )
    print_json_output(resp)


@auth_sso.command("delete")
@click.option("--sso-id", required=True)
def auth_sso_delete(sso_id):
    """Delete an SSO configuration."""
    resp = api_client.delete(f"auth/sso/{sso_id}/")
    print_json_output(resp)
