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


# ── Bulk RDF export (Phase 230.2.12 / REQ-SEM-EXPORT-001) ────


@semantic.command("export")
@click.option(
    "--format", "fmt",
    type=click.Choice(["n-triples", "turtle", "rdf-xml", "ld+json"]),
    default="n-triples",
    show_default=True,
    help="RDF serialization format.",
)
@click.option(
    "--output", "-o", "output_path",
    type=click.Path(dir_okay=False, writable=True),
    help="Write the body to this file (default: stdout).",
)
def export_rdf(fmt: str, output_path: Optional[str]):
    """Bulk-export the tenant's full semantic graph.

    Calls ``POST /api/v1/semantic/export`` on the configured Hub
    instance and writes the body to a file (``--output``) or
    stdout. The Hub throttles to 5 requests / 5 minutes / user; on
    HTTP 429 the Retry-After header is surfaced in the error.
    """
    try:
        # Use the streaming request path so very large bodies don't
        # buffer in memory before reaching the file handle.
        response = api_client.request(
            "POST", "semantic/export", json_data={"format": fmt},
        )
        if response.status_code == 200:
            body = response.content
            if output_path:
                with open(output_path, "wb") as fh:
                    fh.write(body)
                click.echo(
                    f"Wrote {len(body)} bytes to {output_path} ({fmt})",
                    err=True,
                )
            else:
                # stdout — write bytes directly so binary formats
                # (xml) round-trip cleanly.
                import sys
                sys.stdout.buffer.write(body)
        elif response.status_code == 413:
            try:
                detail = response.json()
            except Exception:
                detail = {"raw": response.text[:500]}
            raise click.ClickException(
                f"Export exceeds the 100M-triple cap; use SPARQL "
                f"pagination instead. Server response: {detail}"
            )
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "")
            raise click.ClickException(
                f"Throttled (5 req / 5 min / user). Retry after: {retry_after}"
            )
        else:
            raise click.ClickException(
                f"Export failed: HTTP {response.status_code} "
                f"{response.text[:500]}"
            )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to export RDF: {e}")


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


# ── JSON-LD context (Phase 230.6 / REQ-SEM-CONTEXT-ALIAS-001) ────


@semantic.command("context")
def context():
    """Get the JSON-LD context document.

    Calls ``GET /api/v1/semantic/context`` (the Phase 230.6 alias for
    ``context.jsonld``). The response body is the JSON-LD ``@context``
    object that maps Meshant fields to standard vocabularies (DCAT,
    PROV, SKOS, etc.) and is what ``meshant.com/ontology/`` resolves
    to for content negotiation.

    Closes the doc-vs-reality drift in
    ``docs/mvpdocs/concepts/semantic-resources.md`` line 118 — that
    table has long advertised this command, but no implementation
    existed prior to Phase 230.6 self-audit.
    """
    try:
        data = api_client.get("semantic/context")
        click.echo(json.dumps(data, indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(
            f"Failed to get JSON-LD context: {e}"
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
