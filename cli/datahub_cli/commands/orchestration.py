"""
285.11.4.6 — Pipeline dependency CLI commands.
"""
import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def orchestration():
    """Pipeline dependency management commands"""
    pass


@orchestration.group("dependencies")
def dependencies_group():
    """Manage pipeline dependencies"""
    pass


@dependencies_group.command("list")
@click.option("--pipeline-type", help="Filter by upstream pipeline type")
@click.option("--pipeline-id", help="Filter by pipeline ID")
@click.option("--direction", type=click.Choice(["upstream", "downstream", "both"]),
              default="both", help="Dependency direction")
@click.option("--format", "output_format",
              type=click.Choice(["json", "table"]), default="table",
              help="Output format")
def list_deps(pipeline_type, pipeline_id, direction, output_format):
    """List pipeline dependencies as a graph {nodes, links}."""
    params = {"direction": direction}
    if pipeline_type:
        params["pipeline_type"] = pipeline_type
    if pipeline_id:
        params["pipeline_id"] = pipeline_id

    try:
        data = api_client.get("workflows/dependencies/", params=params)

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            links = data.get("links", [])
            if not links:
                click.echo("No dependencies found.")
                return
            click.echo(f"Found {len(links)} dependency link(s):\n")
            for link in links:
                click.echo(
                    f"  {link['source_type']}:{link['source_id'][:8]}... "
                    f"→[{link['dependency_type']}]→ "
                    f"{link['target_type']}:{link['target_id'][:8]}..."
                    f"  (priority={link.get('priority', 0)})"
                )
    except Exception as e:
        raise click.ClickException(f"Failed to list dependencies: {e}")


@dependencies_group.command("add")
@click.option("--upstream-type", required=True,
              type=click.Choice(["scheduled_ingestion", "scheduled_export",
                                 "transformation", "dq", "compliance"]))
@click.option("--upstream-id", required=True)
@click.option("--downstream-type", required=True,
              type=click.Choice(["scheduled_ingestion", "scheduled_export",
                                 "transformation", "dq", "compliance"]))
@click.option("--downstream-id", required=True)
@click.option("--dependency-type",
              type=click.Choice(["DATA", "TRIGGER", "MANUAL"]),
              default="DATA")
@click.option("--priority", type=int, default=0)
@click.option("--format", "output_format",
              type=click.Choice(["json", "table"]), default="table")
def add_dep(upstream_type, upstream_id, downstream_type, downstream_id,
            dependency_type, priority, output_format):
    """Add a manual pipeline dependency."""
    payload = {
        "pipeline_type": upstream_type,
        "pipeline_id": upstream_id,
        "dependency_type": dependency_type,
        "downstream_pipeline_type": downstream_type,
        "downstream_pipeline_id": downstream_id,
        "priority": priority,
        "created_by": "MANUAL",
    }
    try:
        result = api_client.post("workflows/dependencies/", json_data=payload)
        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Dependency created: {result.get('id', '?')}")
    except Exception as e:
        raise click.ClickException(f"Failed to add dependency: {e}")


@dependencies_group.command("preview")
@click.option("--pipeline-type", required=True,
              type=click.Choice(["scheduled_ingestion", "scheduled_export",
                                 "transformation", "dq", "compliance"]))
@click.option("--pipeline-id", required=True)
@click.option("--max-depth", type=int, default=5)
@click.option("--format", "output_format",
              type=click.Choice(["json", "table"]), default="table")
def preview_deps(pipeline_type, pipeline_id, max_depth, output_format):
    """Preview the trigger chain for a pipeline execution."""
    params = {
        "pipeline_type": pipeline_type,
        "pipeline_id": pipeline_id,
        "max_depth": max_depth,
    }
    try:
        data = api_client.get("workflows/dependencies/preview/", params=params)
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            nodes = data.get("nodes", [])
            click.echo(
                f"Trigger chain for {pipeline_type}:{pipeline_id[:8]}..."
                f" (cycle_free={data.get('cycle_free')}):"
            )
            if not nodes:
                click.echo("  (no downstream dependencies)")
                return
            for node in nodes:
                click.echo(
                    f"  {node['pipeline_type']}:{node['pipeline_id'][:8]}..."
                    f"  [{node.get('status', '?')}]"
                )
    except Exception as e:
        raise click.ClickException(f"Failed to preview dependencies: {e}")
