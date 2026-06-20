"""
283.6.2 / 285.2.3 — Versioning CLI commands.

Provides list, get, diff, and rollback operations for dataset/contract/asset
versions. Mirrors the SDK ``VersioningAPI`` surface (141L at sdk/.../versioning.py).

Backend endpoints (hub/apps/versioning/views.py):
  - List:  GET  /api/v1/versioning/versions/?resource_type=<type>&resource_id=<id>
  - Get:   GET  /api/v1/versioning/versions/<version_id>/
  - Compare: GET /api/v1/versioning/compare/?resource_type=<type>&id_a=<v1>&id_b=<v2>
  - Rollback: No REST endpoint exists yet (backend gap tracked in Phase 286).

Resource type mapping (CLI → backend):
  - datasets   → dataset
  - contracts  → contract
  - assets     → asset (not yet supported by backend — versioning is
                  dataset/contract-scoped; asset versioning TBD)
"""

from __future__ import annotations

import json

import click

from ..api_client import api_client

# Map CLI-facing plural names to backend singular resource_type values.
_RESOURCE_TYPE_MAP = {
    "datasets": "dataset",
    "contracts": "contract",
    # "assets": "asset",  # not yet supported by backend versioning
}

_BACKEND_LIST = "versioning/versions/"
_BACKEND_COMPARE = "versioning/compare/"


def _backend_resource_type(cli_type: str) -> str:
    mapped = _RESOURCE_TYPE_MAP.get(cli_type)
    if mapped is None:
        raise click.ClickException(
            f"Unsupported resource type '{cli_type}'. "
            f"Valid choices: {', '.join(_RESOURCE_TYPE_MAP.keys())}"
        )
    return mapped


def _version_detail_url(version_id: str) -> str:
    return f"versioning/versions/{version_id}/"


@click.group()
def versioning():
    """Dataset, contract, and asset version management"""


@versioning.command("list")
@click.argument("resource_type", type=click.Choice(["datasets", "contracts"]))
@click.argument("resource_id")
@click.option("--page", type=int, default=1, help="Page number (default: 1)")
@click.option("--page-size", type=int, default=50, help="Items per page (default: 50)")
@click.option("--json", "as_json", is_flag=True, help="Emit raw JSON")
def list_versions(resource_type: str, resource_id: str, page: int, page_size: int, as_json: bool):
    """List version history for a resource.

    RESOURCE_TYPE is one of: datasets, contracts.

    RESOURCE_ID is the UUID of the resource.

    \b
    Examples:
        datahub versioning list datasets abc-123
        datahub versioning list contracts def-456 --page 2 --page-size 20
    """
    backend_type = _backend_resource_type(resource_type)
    params = {
        "resource_type": backend_type,
        "resource_id": resource_id,
        "page": page,
        "page_size": page_size,
    }
    data = api_client.get(_BACKEND_LIST, params=params)
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        items = data.get("results", data) if isinstance(data, dict) else data
        if isinstance(items, list):
            if not items:
                click.echo("No versions found.")
                return
            click.echo(f"{'VERSION':<38} {'NUMBER':>8} {'CREATED':<26} {'STATUS':<14}")
            click.echo("-" * 90)
            for v in items:
                if isinstance(v, dict):
                    vid = v.get("id", "")[:36]
                    vnum = v.get("version", v.get("version_number", "?"))
                    vcreated = v.get("created_at", "?")
                    vstatus = v.get("status", "?")
                    click.echo(f"{vid:<38} {vnum!s:>8} {vcreated!s:<26} {vstatus!s:<14}")
                else:
                    click.echo(str(v))
        else:
            click.echo(json.dumps(data, indent=2, default=str))


@versioning.command("get")
@click.argument("resource_type", type=click.Choice(["datasets", "contracts"]))
@click.argument("version_id")
@click.option("--json", "as_json", is_flag=True, help="Emit raw JSON")
def get_version(resource_type: str, version_id: str, as_json: bool):
    """Get a specific version's details.

    VERSION_ID is the UUID of the version record (not a sequential number).

    \b
    Examples:
        datahub versioning get datasets abc-123-def
        datahub versioning get contracts def-456-ghi --json
    """
    # resource_type is accepted for CLI ergonomics but the backend resolves
    # the type from the version record itself — the version UUID is globally
    # unique across types.
    _ = _backend_resource_type(resource_type)  # validate
    data = api_client.get(_version_detail_url(version_id))
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Version:     {data.get('id', '?')}")
        click.echo(f"Type:        {data.get('resource_type', '?')}")
        click.echo(f"Number:      {data.get('version', data.get('version_number', '?'))}")
        click.echo(f"Status:      {data.get('status', '?')}")
        click.echo(f"Created:     {data.get('created_at', '?')}")
        if data.get("schema"):
            click.echo(f"Schema:      {json.dumps(data['schema'], indent=2)}")


@versioning.command("diff")
@click.argument("resource_type", type=click.Choice(["datasets", "contracts"]))
@click.argument("version1_id")
@click.argument("version2_id")
@click.option("--json", "as_json", is_flag=True, help="Emit raw JSON")
def diff_versions(resource_type: str, version1_id: str, version2_id: str, as_json: bool):
    """Compare two versions and show differences.

    \b
    Examples:
        datahub versioning diff datasets abc-123 def-456
        datahub versioning diff contracts abc-123 def-456 --json
    """
    backend_type = _backend_resource_type(resource_type)
    params = {
        "resource_type": backend_type,
        "id_a": version1_id,
        "id_b": version2_id,
    }
    data = api_client.get(_BACKEND_COMPARE, params=params)
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Comparing {version1_id} → {version2_id}")
        click.echo(f"Type: {resource_type}")
        changes = data.get("changes", data.get("differences", []))
        if isinstance(changes, list):
            if not changes:
                click.echo("No differences found.")
                return
            for i, change in enumerate(changes, 1):
                if isinstance(change, dict):
                    field = change.get("field", change.get("path", f"change-{i}"))
                    old_val = change.get("old", change.get("from", "?"))
                    new_val = change.get("new", change.get("to", "?"))
                    click.echo(f"  [{field}]  {old_val}  →  {new_val}")
                else:
                    click.echo(f"  Change {i}: {change}")
        elif isinstance(changes, dict):
            for field, detail in changes.items():
                if isinstance(detail, dict):
                    click.echo(
                        f"  [{field}]  {detail.get('old', '?')}  →  {detail.get('new', '?')}"
                    )
                else:
                    click.echo(f"  [{field}]  {detail}")
        else:
            click.echo(json.dumps(data, indent=2, default=str))


@versioning.command("rollback")
@click.argument("resource_type", type=click.Choice(["datasets", "contracts"]))
@click.argument("resource_id")
@click.argument("version_id")
@click.option("--reason", required=True, help="Reason for rollback (audited)")
@click.option("--confirm", is_flag=True, help="Skip interactive confirmation")
@click.option("--json", "as_json", is_flag=True, help="Emit raw JSON")
def rollback_version(
    resource_type: str,
    resource_id: str,
    version_id: str,
    reason: str,
    confirm: bool,
    as_json: bool,
):
    """Rollback a resource to a previous version.

    This is a destructive operation that reverts the resource state
    to the specified version. A rollback reason is REQUIRED and audited.

    **Note:** The rollback REST endpoint is not yet available in the backend
    (tracked for Phase 286). This command uses the dataset-level rollback
    path as a temporary bridge.

    \b
    Examples:
        datahub versioning rollback datasets abc-123 v-001 --reason "Incorrect schema change"
        datahub versioning rollback contracts def-456 v-003 --reason "Bad clause" --confirm
    """
    _ = _backend_resource_type(resource_type)
    if not confirm:
        click.echo(
            f"WARNING: This will rollback {resource_type}/{resource_id} to version {version_id}."
        )
        click.echo(f"Reason: {reason}")
        if not click.confirm("Continue?"):
            click.echo("Aborted.")
            return

    # The versioning app has no dedicated rollback REST endpoint yet.
    # Route through the dataset rollback service until Phase 286 adds one.
    payload = {"version_id": version_id, "reason": reason}
    resp = api_client.request(
        "POST",
        f"{resource_type}/{resource_id}/rollback/",
        json_data=payload,
    )
    if not resp.ok:
        click.echo(
            f"Error: rollback failed ({resp.status_code}): {resp.text[:500]}",
            err=True,
        )
        raise SystemExit(1)
    data = resp.json() if resp.text else {}
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo("Rollback complete.")
        click.echo(f"  New version: {data.get('new_version_id', data.get('id', '?'))}")
        click.echo(f"  Status:      {data.get('status', '?')}")
