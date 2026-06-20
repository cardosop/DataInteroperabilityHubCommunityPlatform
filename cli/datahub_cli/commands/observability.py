"""
Observability commands (Phase 278.AA.6).

Provides CLI commands for freshness, SLA, and incident monitoring.
Uses real hub API - no mocks/stubs.
"""

import json

import click

from ..api_client import api_client


@click.group()
def observability():
    """Observability and monitoring commands"""


@observability.command("freshness")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def freshness(output_format: str):
    """Get data freshness dashboard"""
    try:
        data = api_client.get("observability/freshness/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            summary = data.get("summary", {})
            click.echo("Data Freshness Report")
            click.echo(f"  Total datasets:      {summary.get('total_datasets', '—')}")
            click.echo(f"  Fresh (within SLA):  {summary.get('fresh_count', '—')}")
            click.echo(f"  Stale (breach SLA):  {summary.get('stale_count', '—')}")
            click.echo(f"  Unknown:             {summary.get('unknown_count', '—')}")

            stale = data.get("stale", [])
            if stale:
                click.echo(f"\nStale Datasets ({len(stale)}):")
                for s in stale[:20]:
                    if isinstance(s, dict):
                        name = s.get("name", s.get("dataset_name", "—"))
                        last_updated = s.get("last_updated", s.get("last_updated_at", "—"))
                        click.echo(f"  • {name} — last updated {last_updated}")
                if len(stale) > 20:
                    click.echo(f"  ... and {len(stale) - 20} more")

    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get freshness: {e}")


@observability.command("sla")
@click.option("--type", "sla_type", help="SLA type filter (FRESHNESS, AVAILABILITY, QUALITY)")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def sla(sla_type: str, output_format: str):
    """Get SLA compliance dashboard"""
    try:
        params = {}
        if sla_type:
            params["sla_type"] = sla_type
        data = api_client.get("observability/slas/", params=params)

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("SLA Compliance Dashboard")
            summary = data.get("summary", {}) if isinstance(data, dict) else {}
            if summary:
                click.echo(f"  Overall compliance:  {summary.get('overall_compliance_pct', '—')}%")
                click.echo(f"  Within SLA:          {summary.get('within_sla', '—')}")
                click.echo(f"  Breaching SLA:       {summary.get('breaching_sla', '—')}")
                click.echo(f"  Total monitored:     {summary.get('total_monitored', '—')}")

            slas = data.get("slas", data.get("results", [])) if isinstance(data, dict) else data
            if isinstance(slas, list) and slas:
                click.echo(f"\nSLA Details ({len(slas)}):")
                click.echo(f"{'Name':<30} {'Type':<15} {'Status':<12} {'Compliance'}")
                click.echo("-" * 75)
                for s in slas[:20]:
                    if isinstance(s, dict):
                        name = str(s.get("name", "—"))[:28]
                        stype = str(s.get("sla_type", s.get("type", "—")))[:13]
                        status = str(s.get("status", "—"))[:10]
                        compliance = s.get("compliance_pct", s.get("compliance", "—"))
                        click.echo(f"{name:<30} {stype:<15} {status:<12} {compliance}")
                if len(slas) > 20:
                    click.echo(f"  ... and {len(slas) - 20} more")

    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get SLA data: {e}")


@observability.group()
def incidents():
    """Incident monitoring commands"""


@incidents.command("list")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def list_incidents(output_format: str):
    """List stale/breaching data (potential incidents)"""
    try:
        data = api_client.get("observability/freshness/stale/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            results = data.get("results", data) if isinstance(data, dict) else data
            if isinstance(results, list):
                if not results:
                    click.echo("No stale data — all datasets within SLA.")
                    return
                click.echo(f"Stale Data Incidents ({len(results)}):")
                click.echo(f"{'Dataset':<35} {'Last Updated':<22} {'SLA (hours)'}")
                click.echo("-" * 75)
                for r in results[:20]:
                    if isinstance(r, dict):
                        name = str(r.get("name", r.get("dataset_name", "—")))[:33]
                        updated = str(r.get("last_updated", r.get("last_updated_at", "—")))[:20]
                        sla_hours = r.get("sla_hours", r.get("freshness_sla_hours", "—"))
                        click.echo(f"{name:<35} {updated:<22} {sla_hours}")
                if len(results) > 20:
                    click.echo(f"  ... and {len(results) - 20} more")
            elif isinstance(data, dict):
                click.echo(json.dumps(data, indent=2))

    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list incidents: {e}")


@incidents.command("get")
@click.argument("dataset_id")
def get_incident(dataset_id: str):
    """Get incident details for a specific dataset"""
    try:
        data = api_client.get(f"observability/freshness/stale/?dataset_id={dataset_id}")

        click.echo(json.dumps(data, indent=2))

    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get incident: {e}")
