"""
283.5.10 — Capability listing CLI commands.
"""

from __future__ import annotations

import click

from ..api_client import api_client
from ..output import print_json_output


@click.group()
def capabilities():
    """List tenant capabilities and feature flags"""


@capabilities.command("list")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="json",
    help="Output format (capabilities are JSON-first; table renders the key list)",
)
def list_capabilities(output_format: str):
    """List all tenant capabilities"""
    data = api_client.get("capabilities/")
    if output_format == "json":
        print_json_output(data)
        return
    # Table: one flag per line, sorted for stable output.
    rows = []
    if isinstance(data, dict):
        for section, value in data.items():
            if isinstance(value, dict):
                for key, enabled in sorted(value.items()):
                    rows.append((f"{section}.{key}", str(bool(enabled))))
            else:
                rows.append((section, str(value)))
    elif isinstance(data, list):
        rows = [(str(item), "") for item in data]
    if not rows:
        click.echo("(no capabilities)")
        return
    for name, value in rows:
        click.echo(f"{name:<60} {value}")
