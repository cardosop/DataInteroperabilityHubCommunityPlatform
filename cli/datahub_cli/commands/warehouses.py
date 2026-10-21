"""
Warehouse connectivity commands.

Covers all /api/v1/warehouses/ endpoints — connection CRUD, testing,
schema reflection, ACL management, live queries, and Delta Sharing.
"""

import json

import click

from ..api_client import api_client
from ..output import print_json_output


@click.group()
def warehouses():
    """Warehouse connections, queries, ACLs, and Delta Sharing."""


# ── Connection CRUD ─────────────────────────────────────────────────────


@warehouses.group("connections")
def warehouses_connections():
    """Warehouse connection management."""


@warehouses_connections.command("list")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def warehouses_connections_list(output_format):
    """List warehouse connections."""
    data = api_client.get("warehouses/connections/")
    if output_format == "json":
        print_json_output(data)
    else:
        results = data.get("results", data) if isinstance(data, dict) else data
        items = results if isinstance(results, list) else results.get("results", [])
        if not items:
            click.echo("No connections found.")
            return
        for c in items:
            click.echo(
                f"{c.get('id', '?')[:8]}  {c.get('name', '?'):20s}  {c.get('db_type', '?'):10s}  {c.get('status', '?')}"
            )


@warehouses_connections.command("get")
@click.argument("connection_id")
def warehouses_connections_get(connection_id):
    """Get a warehouse connection by ID."""
    data = api_client.get(f"warehouses/connections/{connection_id}/")
    print_json_output(data)


@warehouses_connections.command("create")
@click.option("--name", required=True)
@click.option(
    "--warehouse-type",
    required=True,
    type=click.Choice(["SNOWFLAKE", "BIGQUERY", "DATABRICKS", "ATHENA"]),
)
@click.option(
    "--config",
    "config_json",
    help="Connection config as JSON string (host, credentials, ...)",
)
@click.option("--region", default="", help="Warehouse region")
@click.option("--private-endpoint-url", default="", help="PrivateLink / PSC endpoint URL")
@click.option("--is-active/--no-is-active", default=True)
def warehouses_connections_create(
    name, warehouse_type, config_json, region, private_endpoint_url, is_active
):
    """Create a new warehouse connection.

    Mirrors ``WarehouseConnectionCreateSerializer``:
    ``name``, ``warehouse_type``, ``config``, ``region``,
    ``private_endpoint_url``, ``is_active``.
    """
    resp = api_client.post(
        "warehouses/connections/",
        json_data={
            "name": name,
            "warehouse_type": warehouse_type,
            "config": json.loads(config_json) if config_json else {},
            "region": region,
            "private_endpoint_url": private_endpoint_url,
            "is_active": is_active,
        },
    )
    print_json_output(resp)


@warehouses_connections.command("update")
@click.argument("connection_id")
@click.option("--name", default=None)
@click.option("--host", default=None)
@click.option("--port", type=int, default=None)
@click.option("--database", default=None)
@click.option("--username", default=None)
@click.option("--password", default=None, hide_input=True)
def warehouses_connections_update(connection_id, **kwargs):
    """Update a warehouse connection."""
    body = {k: v for k, v in kwargs.items() if v is not None}
    if not body:
        raise click.UsageError("At least one option to update is required")
    resp = api_client.patch(f"warehouses/connections/{connection_id}/", json_data=body)
    print_json_output(resp)


@warehouses_connections.command("delete")
@click.argument("connection_id")
@click.option("--confirm", is_flag=True, help="Confirm deletion")
def warehouses_connections_delete(connection_id, confirm):
    """Delete a warehouse connection."""
    if not confirm:
        raise click.UsageError("Use --confirm to delete. This cannot be undone.")
    api_client.delete(f"warehouses/connections/{connection_id}/")
    click.echo(f"Connection {connection_id} deleted.")


@warehouses_connections.command("test")
@click.argument("connection_id")
def warehouses_connections_test(connection_id):
    """Test a warehouse connection."""
    resp = api_client.post(f"warehouses/connections/{connection_id}/test/", json_data={})
    print_json_output(resp)


@warehouses_connections.command("schema")
@click.argument("connection_id")
@click.option("--table", default=None, help="Filter to a specific table")
def warehouses_connections_schema(connection_id, table):
    """Reflect database schema from a connection."""
    url = f"warehouses/connections/{connection_id}/schema/"
    if table:
        url += f"?table={table}"
    data = api_client.get(url)
    print_json_output(data)


# ── ACLs ────────────────────────────────────────────────────────────────


@warehouses.group("acls")
def warehouses_acls():
    """Connection ACL management."""


@warehouses_acls.command("list")
def warehouses_acls_list():
    """List ACLs."""
    data = api_client.get("warehouses/acls/")
    print_json_output(data)


@warehouses_acls.command("get")
@click.argument("acl_id")
def warehouses_acls_get(acl_id):
    """Get ACL by ID."""
    data = api_client.get(f"warehouses/acls/{acl_id}/")
    print_json_output(data)


@warehouses_acls.command("create")
@click.option("--connection", required=True, help="Warehouse connection ID")
@click.option("--user", default=None, help="User ID the ACL applies to")
@click.option("--role", required=True, type=click.Choice(["ADMIN", "OPERATOR", "VIEWER"]))
def warehouses_acls_create(connection, user, role):
    """Create an ACL entry.

    Mirrors ``WarehouseConnectionACLSerializer`` fields:
    ``connection``, ``user``, ``role``.
    """
    payload = {"connection": connection, "role": role}
    if user:
        payload["user"] = user
    resp = api_client.post(
        "warehouses/acls/",
        json_data=payload,
    )
    print_json_output(resp)


@warehouses_acls.command("delete")
@click.argument("acl_id")
@click.option("--confirm", is_flag=True)
def warehouses_acls_delete(acl_id, confirm):
    """Delete an ACL entry."""
    if not confirm:
        raise click.UsageError("Use --confirm to delete.")
    api_client.delete(f"warehouses/acls/{acl_id}/")
    click.echo(f"ACL {acl_id} deleted.")


# ── Live Query ──────────────────────────────────────────────────────────


@warehouses.command("query")
@click.option("--asset-id", required=True, help="LIVE_QUERY asset ID to query")
@click.option("--limit", type=int, default=100, help="Max rows per page")
@click.option("--cursor", default=None, help="Opaque cursor for pagination")
def warehouses_query(asset_id, limit, cursor):
    """Query a LIVE_QUERY warehouse asset.

    GET /api/v1/warehouses/query/?asset_id=<id>&limit=<n>&cursor=<...>
    """
    params = {"asset_id": asset_id, "limit": limit}
    if cursor:
        params["cursor"] = cursor
    resp = api_client.get(
        "warehouses/query/",
        params=params,
    )
    print_json_output(resp)


# ── Compliance ──────────────────────────────────────────────────────────


@warehouses.command("residency-mismatches")
def warehouses_residency_mismatches():
    """List data residency mismatches across connections."""
    data = api_client.get("warehouses/connections/residency-mismatches/")
    print_json_output(data)
