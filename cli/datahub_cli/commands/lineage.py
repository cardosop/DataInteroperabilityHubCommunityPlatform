"""
Lineage management commands.
"""

import json

import click

from ..api_client import api_client


@click.group()
def lineage():
    """Lineage management commands"""


@lineage.command("contract")
@click.argument("contract_id")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_contract_lineage(contract_id: str, output_format: str):
    """Get contract-level lineage"""
    try:
        data = api_client.get(f"contracts/{contract_id}/lineage/contracts/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Contract Lineage for {contract_id}")
            contracts = data.get("contracts", [])
            if contracts:
                click.echo(f"\nUpstream Contracts ({len(contracts)}):")
                for contract in contracts:
                    click.echo(f"  - {contract.get('namespace', '')}/{contract.get('name', '')}")
            else:
                click.echo("No upstream contracts found.")
    except Exception as e:
        raise click.ClickException(f"Failed to get contract lineage: {e}")


@lineage.command("model")
@click.argument("contract_id")
@click.argument("model_name")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_model_lineage(contract_id: str, model_name: str, output_format: str):
    """Get model-level lineage"""
    try:
        data = api_client.get(f"contracts/{contract_id}/models/{model_name}/lineage/")

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Model Lineage: {model_name}")
            lineage = data.get("lineage", {})
            models = lineage.get("models", [])
            if models:
                click.echo(f"\nUpstream Models ({len(models)}):")
                for model in models:
                    click.echo(
                        f"  - {model.get('namespace', '')}/{model.get('name', '')}/{model.get('model_name', '')}"
                    )
            else:
                click.echo("No upstream models found.")
    except Exception as e:
        raise click.ClickException(f"Failed to get model lineage: {e}")


@lineage.command("field")
@click.argument("contract_id")
@click.argument("model_name")
@click.argument("field_name")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_field_lineage(contract_id: str, model_name: str, field_name: str, output_format: str):
    """Get field-level lineage"""
    try:
        data = api_client.get(
            f"contracts/{contract_id}/fields/{field_name}/lineage/",
            params={"model_name": model_name},
        )

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Field Lineage: {model_name}.{field_name}")
            lineage = data.get("lineage", {})
            input_fields = lineage.get("input_fields", [])
            if input_fields:
                click.echo(f"\nInput Fields ({len(input_fields)}):")
                for field in input_fields:
                    click.echo(
                        f"  - {field.get('namespace', '')}/{field.get('name', '')}/{field.get('model_name', '')}.{field.get('field', '')}"
                    )
            else:
                click.echo("No input fields found.")
    except Exception as e:
        raise click.ClickException(f"Failed to get field lineage: {e}")


@lineage.command("full")
@click.argument("contract_id")
@click.option("--max-contract-depth", type=int, default=10, help="Maximum contract depth")
@click.option("--max-model-depth", type=int, default=10, help="Maximum model depth")
@click.option("--max-field-depth", type=int, default=10, help="Maximum field depth")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_full_lineage(
    contract_id: str,
    max_contract_depth: int,
    max_model_depth: int,
    max_field_depth: int,
    output_format: str,
):
    """Get complete hierarchical lineage"""
    try:
        params = {
            "max_contract_depth": max_contract_depth,
            "max_model_depth": max_model_depth,
            "max_field_depth": max_field_depth,
        }
        data = api_client.get(f"contracts/{contract_id}/lineage/full/", params=params)

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Full Lineage for {contract_id}")
            upstream = data.get("upstream", {})
            downstream = data.get("downstream", {})

            if upstream:
                click.echo("\nUpstream:")
                click.echo(json.dumps(upstream, indent=2))

            if downstream:
                click.echo("\nDownstream:")
                click.echo(json.dumps(downstream, indent=2))
    except Exception as e:
        raise click.ClickException(f"Failed to get full lineage: {e}")


@lineage.command("visualize")
@click.argument("contract_id")
@click.option(
    "--format",
    type=click.Choice(["json", "dot", "mermaid"]),
    default="json",
    help="Visualization format",
)
def visualize_lineage(contract_id: str, format: str):
    """Get lineage visualization"""
    try:
        params = {"format": format}
        response = api_client.request(
            "GET", f"contracts/{contract_id}/lineage/visualization/", params=params
        )

        if format in ["dot", "mermaid"]:
            click.echo(response.text if hasattr(response, "text") else str(response))
        else:
            click.echo(
                json.dumps(response.json() if hasattr(response, "json") else response, indent=2)
            )
    except Exception as e:
        raise click.ClickException(f"Failed to get lineage visualization: {e}")


@lineage.command("impact")
@click.argument("contract_id")
@click.option("--depth", type=int, default=10, help="Traversal depth")
@click.option("--include-fields", is_flag=True, default=True, help="Include field-level impact")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_impact_analysis(contract_id: str, depth: int, include_fields: bool, output_format: str):
    """Get impact analysis"""
    try:
        params = {
            "depth": depth,
            "include_fields": include_fields,
        }
        data = api_client.get(f"contracts/{contract_id}/impact-analysis/", params=params)

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Impact Analysis for {contract_id}")
            impact_score = data.get("impact_score", 0)
            affected_assets = data.get("affected_assets", [])
            click.echo(f"\nImpact Score: {impact_score}")
            click.echo(f"Affected Assets: {len(affected_assets)}")
            if affected_assets:
                for asset in affected_assets[:10]:
                    click.echo(f"  - {asset.get('id', '')}")
                if len(affected_assets) > 10:
                    click.echo(f"  ... and {len(affected_assets) - 10} more")
    except Exception as e:
        raise click.ClickException(f"Failed to get impact analysis: {e}")
