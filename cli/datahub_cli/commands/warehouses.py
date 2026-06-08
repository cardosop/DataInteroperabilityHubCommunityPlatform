"""
Warehouse connectivity commands.

Covers all /api/v1/warehouses/ endpoints — connection CRUD, testing,
schema reflection, ACL management, live queries, and Delta Sharing.
"""

import json

import click

from ..api_client import api_client


@click.group()
def warehouses():
    """Warehouse connections, queries, ACLs, and Delta Sharing."""
    pass


# ── Connection CRUD ─────────────────────────────────────────────────────

@warehouses.group("connections")
def warehouses_connections():
    """Warehouse connection management."""
    pass


@warehouses_connections.command("list")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def warehouses_connections_list(output_format):
    """List warehouse connections."""
    data = api_client.get("warehouses/connections/")
    if output_format == "json":
        click.echo(json.dumps(data, indent=2))
    else:
        results = data.get("results", data) if isinstance(data, dict) else data
        items = results if isinstance(results, list) else results.get("results", [])
        if not items:
            click.echo("No connections found.")
            return
        for c in items:
            click.echo(f"{c.get('id','?')[:8]}  {c.get('name','?'):20s}  {c.get('db_type','?'):10s}  {c.get('status','?')}")


@warehouses_connections.command("get")
@click.argument("connection_id")
def warehouses_connections_get(connection_id):
    """Get a warehouse connection by ID."""
    data = api_client.get(f"warehouses/connections/{connection_id}/")
    click.echo(json.dumps(data, indent=2))


@warehouses_connections.command("create")
@click.option("--name", required=True)
@click.option("--db-type", required=True, type=click.Choice(["postgresql", "mysql", "snowflake", "bigquery", "redshift", "databricks"]))
@click.option("--host", required=True)
@click.option("--port", type=int, default=5432)
@click.option("--database", required=True)
@click.option("--username", required=True)
@click.option("--password", prompt=True, hide_input=True)
@click.option("--ssl/--no-ssl", default=True)
def warehouses_connections_create(name, db_type, host, port, database, username, password, ssl):
    """Create a new warehouse connection."""
    resp = api_client.post("warehouses/connections/", json={
        "name": name, "db_type": db_type, "host": host,
        "port": port, "database": database, "username": username,
        "password": password, "ssl": ssl,
    })
    click.echo(json.dumps(resp, indent=2))


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
    resp = api_client.patch(f"warehouses/connections/{connection_id}/", json=body)
    click.echo(json.dumps(resp, indent=2))


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
    resp = api_client.post(f"warehouses/connections/{connection_id}/test/", json={})
    click.echo(json.dumps(resp, indent=2))


@warehouses_connections.command("schema")
@click.argument("connection_id")
@click.option("--table", default=None, help="Filter to a specific table")
def warehouses_connections_schema(connection_id, table):
    """Reflect database schema from a connection."""
    url = f"warehouses/connections/{connection_id}/schema/"
    if table:
        url += f"?table={table}"
    data = api_client.get(url)
    click.echo(json.dumps(data, indent=2))


# ── ACLs ────────────────────────────────────────────────────────────────

@warehouses.group("acls")
def warehouses_acls():
    """Connection ACL management."""
    pass


@warehouses_acls.command("list")
def warehouses_acls_list():
    """List ACLs."""
    data = api_client.get("warehouses/acls/")
    click.echo(json.dumps(data, indent=2))


@warehouses_acls.command("get")
@click.argument("acl_id")
def warehouses_acls_get(acl_id):
    """Get ACL by ID."""
    data = api_client.get(f"warehouses/acls/{acl_id}/")
    click.echo(json.dumps(data, indent=2))


@warehouses_acls.command("create")
@click.option("--connection-id", required=True)
@click.option("--principal", required=True, help="User or role name")
@click.option("--permission", required=True, type=click.Choice(["read", "write", "admin"]))
def warehouses_acls_create(connection_id, principal, permission):
    """Create an ACL entry."""
    resp = api_client.post("warehouses/acls/", json={
        "connection_id": connection_id, "principal": principal,
        "permission": permission,
    })
    click.echo(json.dumps(resp, indent=2))


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
@click.option("--connection-id", required=True)
@click.option("--sql", required=True, help="SQL query to execute")
def warehouses_query(connection_id, sql):
    """Execute a live SQL query against a warehouse."""
    resp = api_client.get(
        "warehouses/query/",
        params={"connection_id": connection_id, "sql": sql},
    )
    click.echo(json.dumps(resp, indent=2))


# ── Delta Sharing ───────────────────────────────────────────────────────

@warehouses.group("share")
def warehouses_share():
    """Delta Sharing operations."""
    pass


@warehouses_share.command("list")
@click.argument("asset_id")
def warehouses_share_list(asset_id):
    """List Delta Sharing tables for an asset."""
    data = api_client.get(f"warehouses/share/{asset_id}/")
    click.echo(json.dumps(data, indent=2))


@warehouses_share.command("query")
@click.argument("asset_id")
@click.option("--sql", required=True, help="SQL query against shared table")
def warehouses_share_query(asset_id, sql):
    """Query a Delta Sharing table."""
    resp = api_client.get(
        f"warehouses/share/{asset_id}/query/",
        params={"sql": sql},
    )
    click.echo(json.dumps(resp, indent=2))


# ── Compliance ──────────────────────────────────────────────────────────

@warehouses.command("residency-mismatches")
def warehouses_residency_mismatches():
    """List data residency mismatches across connections."""
    data = api_client.get("warehouses/connections/residency-mismatches/")
    click.echo(json.dumps(data, indent=2))
