"""
283.5.10 — Capability listing CLI commands.
"""
from __future__ import annotations

import json

import click

from ..api_client import api_client


@click.group()
def capabilities():
    """List tenant capabilities and feature flags"""
    pass


@capabilities.command("list")
def list_capabilities():
    """List all tenant capabilities"""
    data = api_client.get("capabilities/")
    click.echo(json.dumps(data, indent=2, default=str))
