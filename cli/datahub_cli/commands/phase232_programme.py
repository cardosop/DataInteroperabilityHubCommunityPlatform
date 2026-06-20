"""CLI helpers for Phase 232 compliance programme API routes."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

import click

from ..api_client import api_client

# Order matches OpenSpec D232 subsystem list + compliance runs driver.
_PHASE232_LIST_ROUTES: tuple[tuple[str, str, str], ...] = (
    ("consent_purposes", "GET", "governance/consent-purposes/"),
    ("dsar_requests", "GET", "governance/dsar-requests/"),
    ("breach_incidents", "GET", "governance/breach-incidents/"),
    ("dpia_records", "GET", "dpia/records/"),
    ("ropa_generations", "GET", "ropa/generations/"),
    ("processor_agreements", "GET", "governance/processor-agreements/"),
    ("compliance_runs", "GET", "compliance/runs/"),
)


def _format_catalogue_json(rows: Iterable[tuple[str, str, str]]) -> str:
    payload = [
        {"subsystem": name, "method": method, "relative_path": path} for name, method, path in rows
    ]
    return json.dumps(payload, indent=2)


def format_phase232_catalogue_table(rows: Iterable[tuple[str, str, str]]) -> str:
    lines = [
        f"{'subsystem':<22} {'method':<8} path",
        "-" * 72,
    ]
    for name, method, path in rows:
        lines.append(f"{name:<22} {method:<8} {path}")
    return "\n".join(lines)


@click.group(name="phase232")
def phase232_group() -> None:
    """Phase 232 compliance programme — catalogue and lightweight list probes."""


@phase232_group.command("catalogue")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format.",
)
def phase232_catalogue(fmt: str) -> None:
    """Print canonical list endpoints for all seven programme surfaces (no HTTP)."""
    if fmt == "json":
        click.echo(_format_catalogue_json(_PHASE232_LIST_ROUTES))
    else:
        click.echo(format_phase232_catalogue_table(_PHASE232_LIST_ROUTES))


@phase232_group.command("probe-lists")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format.",
)
@click.option("--limit", default=1, help="Pagination limit forwarded to each list endpoint.")
def phase232_probe_lists(fmt: str, limit: int) -> None:
    """GET each list endpoint with `--limit` (requires `datahub login` or API key)."""
    results: list[dict[str, Any]] = []
    for name, _method, path in _PHASE232_LIST_ROUTES:
        try:
            data = api_client.get(path, params={"limit": limit})
            results.append({"subsystem": name, "path": path, "ok": True, "sample": data})
        except Exception as exc:
            results.append({"subsystem": name, "path": path, "ok": False, "error": str(exc)})
    if fmt == "json":
        click.echo(json.dumps(results, indent=2, default=str))
    else:
        for row in results:
            status = "OK" if row.get("ok") else "ERR"
            click.echo(f"[{status}] {row['subsystem']}: {row.get('error', 'received payload')}")


__all__ = ["_PHASE232_LIST_ROUTES", "format_phase232_catalogue_table", "phase232_group"]
