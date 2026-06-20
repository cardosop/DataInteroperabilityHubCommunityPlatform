"""
User management commands (278.AA.4).

Provides CLI commands for user listing, inspection, invitation, and role management.
Uses real hub API — no mocks/stubs.
"""

import json

import click

from ..api_client import api_client


@click.group()
def users():
    """User management commands"""


@users.command("list")
@click.option("--limit", type=int, default=50, help="Limit number of results")
@click.option("--offset", type=int, default=0, help="Offset for pagination")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_users(limit: int, offset: int, output_format: str):
    """List users in the current tenant"""
    try:
        params = {"limit": limit, "offset": offset}
        data = api_client.get("users/", params=params)
        results = (
            data.get("results", [])
            if isinstance(data, dict)
            else data
            if isinstance(data, list)
            else []
        )

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            if not results:
                click.echo("No users found.")
                return
            click.echo(f"{'ID':<38} {'Name':<25} {'Email':<35} {'Roles':<30}")
            click.echo("-" * 128)
            for user in results:
                if not isinstance(user, dict):
                    continue
                uid = str(user.get("id", ""))[:36]
                name = str(user.get("name") or user.get("display_name") or "")[:23]
                email = str(user.get("email", ""))[:33]
                roles = ", ".join(user.get("roles", []) or [])[:28]
                click.echo(f"{uid:<38} {name:<25} {email:<35} {roles:<30}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list users: {e}")


@users.command("get")
@click.argument("user_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_user(user_id: str, output_format: str):
    """Get user details"""
    try:
        data = api_client.get(f"users/{user_id}/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"ID:        {data.get('id')}")
            click.echo(f"Name:      {data.get('name') or data.get('display_name')}")
            click.echo(f"Email:     {data.get('email')}")
            roles = data.get("roles", []) or []
            click.echo(f"Roles:     {', '.join(roles) if roles else '(none)'}")
            click.echo(f"Tenant:    {data.get('tenant_name') or data.get('tenant_id')}")
            if data.get("is_active") is not None:
                click.echo(f"Active:    {data.get('is_active')}")
            if data.get("created_at"):
                click.echo(f"Created:   {data.get('created_at')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get user: {e}")


@users.command("invite")
@click.option("--email", required=True, help="Email address to invite")
@click.option("--name", help="Display name for the invited user")
@click.option(
    "--role",
    "roles",
    multiple=True,
    help="Role(s) to assign (repeatable). Example: --role DATA_CONSUMER",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def invite_user(
    email: str,
    name: str | None,
    roles: tuple[str, ...],
    output_format: str,
):
    """Invite a new user to the tenant"""
    try:
        payload: dict = {"email": email}
        if name:
            payload["name"] = name
        if roles:
            payload["roles"] = list(roles)

        data = api_client.post("users/invite/", json_data=payload)

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Invitation sent to {email}")
            if data.get("id"):
                click.echo(f"User ID: {data.get('id')}")
            if data.get("invitation_token"):
                click.echo(f"Token:   {data.get('invitation_token')}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to invite user: {e}")


@users.command("roles")
@click.argument("user_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_roles(user_id: str, output_format: str):
    """List roles for a user"""
    try:
        # GET user to read current roles
        data = api_client.get(f"users/{user_id}/")

        if output_format == "json":
            click.echo(json.dumps({"id": data.get("id"), "roles": data.get("roles", [])}, indent=2))
        else:
            roles = data.get("roles", []) or []
            click.echo(f"User:  {data.get('email') or user_id}")
            if roles:
                click.echo("Roles:")
                for role in roles:
                    click.echo(f"  - {role}")
            else:
                click.echo("Roles: (none)")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get user roles: {e}")
