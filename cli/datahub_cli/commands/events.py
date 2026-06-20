"""
283.5.9 — Event / Dead Letter Queue CLI commands.
"""

from __future__ import annotations

import json

import click

from ..api_client import api_client


@click.group()
def events():
    """Event replay and Dead Letter Queue management"""


# ── Event replay ────────────────────────────────────────────────────────────


@events.command("replay")
@click.argument("event_id")
def replay(event_id):
    """Replay a specific event"""
    data = api_client.post(f"events/{event_id}/replay/")
    click.echo(json.dumps(data, indent=2, default=str))


# ── Dead Letter Queue ───────────────────────────────────────────────────────


@events.group("dlq")
def dlq():
    """Dead Letter Queue operations"""


@dlq.command("list")
def dlq_list():
    """List DLQ entries"""
    data = api_client.get("events/dlq/")
    results = data if isinstance(data, list) else data.get("results", [])
    if not results:
        click.echo("DLQ is empty.")
        return
    for r in results:
        click.echo(f"{r.get('id', '')}  {r.get('event_type', '')}  {r.get('status', '')}")


@dlq.command("retry")
@click.argument("event_id")
def dlq_retry(event_id):
    """Retry a DLQ event"""
    data = api_client.post(f"events/dlq/{event_id}/retry/")
    click.echo(json.dumps(data, indent=2, default=str))


@dlq.command("resolve")
@click.argument("event_id")
def dlq_resolve(event_id):
    """Resolve/mark a DLQ event as handled"""
    data = api_client.post(f"events/dlq/{event_id}/resolve/")
    click.echo(json.dumps(data, indent=2, default=str))
