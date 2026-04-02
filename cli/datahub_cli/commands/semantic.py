"""
Semantic / SPARQL / Ontology commands (Phase 118E).

Provides CLI commands for SPARQL queries, ontology exploration,
and SHACL validation.
"""

import json
from typing import Optional

import click

from ..api_client import api_client


@click.group()
def semantic():
    """Semantic layer, SPARQL, and ontology commands"""
    pass


# ── SPARQL ───────────────────────────────────────────────


@semantic.group("sparql")
def sparql():
    """SPARQL query commands"""
    pass


@sparql.command("query")
@click.option(
    "--query", "query_str",
    help="SPARQL query string",
)
@click.option(
    "--file", "query_file",
    type=click.Path(exists=True),
    help="File containing SPARQL query",
)
@click.option(
    "--accept",
    default="application/sparql-results+json",
    help="Accept header for results format",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def sparql_query(
    query_str: Optional[str],
    query_file: Optional[str],
    accept: str,
    output_format: str,
):
    """Execute a SPARQL query"""
    if not query_str and not query_file:
        raise click.ClickException(
            "Provide --query or --file"
        )

    if query_file:
        with open(query_file, "r") as f:
            query_str = f.read()

    try:
        resp = api_client.request(
            "POST",
            "semantic/sparql/",
            json_data={
                "query": query_str,
                "accept": accept,
            },
            timeout=120,
        )
        data = resp.json() if resp.text else {}

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            results = data.get("results", {})
            bindings = results.get("bindings", [])
            if not bindings:
                click.echo("No results.")
                return
            cols = list(bindings[0].keys())
            header = "  ".join(f"{c:<30}" for c in cols)
            click.echo(header)
            click.echo("-" * len(header))
            for row in bindings:
                vals = [
                    str(row.get(c, {}).get("value", ""))[:28]
                    for c in cols
                ]
                click.echo(
                    "  ".join(f"{v:<30}" for v in vals)
                )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"SPARQL query failed: {e}"
        )


@sparql.command("service-description")
def service_description():
    """Get SPARQL service description"""
    try:
        data = api_client.get(
            "semantic/sparql/service-description/",
        )
        click.echo(json.dumps(data, indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to get service description: {e}"
        )


# ── Ontology / VoID / SHACL ─────────────────────────────


@semantic.command("ontology")
def ontology():
    """Get ontology definition"""
    try:
        data = api_client.get("semantic/ontology/")
        click.echo(json.dumps(data, indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to get ontology: {e}"
        )


@semantic.command("void")
def void_description():
    """Get VoID dataset description"""
    try:
        data = api_client.get("semantic/void/")
        click.echo(json.dumps(data, indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to get VoID description: {e}"
        )


@semantic.group("shacl")
def shacl():
    """SHACL validation commands"""
    pass


@shacl.command("validate")
@click.option(
    "--data", "data_file",
    type=click.Path(exists=True),
    help="RDF data file to validate",
)
@click.option(
    "--shapes", "shapes_file",
    type=click.Path(exists=True),
    help="SHACL shapes file",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def shacl_validate(
    data_file: Optional[str],
    shapes_file: Optional[str],
    output_format: str,
):
    """Validate RDF data against SHACL shapes"""
    payload = {}
    if data_file:
        with open(data_file, "r") as f:
            payload["data"] = f.read()
    if shapes_file:
        with open(shapes_file, "r") as f:
            payload["shapes"] = f.read()

    try:
        data = api_client.post(
            "semantic/shacl/validate/",
            json_data=payload,
            timeout=120,
        )
        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            conforms = data.get("conforms", False)
            click.echo(
                f"Conforms: {'Yes' if conforms else 'No'}"
            )
            violations = data.get("violations", [])
            if violations:
                click.echo(
                    f"\nViolations ({len(violations)}):"
                )
                for v in violations:
                    click.echo(
                        f"  - {v.get('message', 'N/A')} "
                        f"({v.get('severity', 'N/A')})"
                    )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"SHACL validation failed: {e}"
        )
