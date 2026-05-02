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


# ── Custom ontology management (Phase 230.10 / REQ-SEM-ONTO-001) ───


@semantic.group("custom-ontology")
def custom_ontology():
    """Manage tenant custom ontologies (TENANT_ADMIN).

    Distinct from ``semantic ontology`` (which fetches the static
    hub ontology). The ``custom-ontology`` group lets a TENANT_ADMIN
    upload, list, activate, and deactivate per-tenant Turtle / RDF/XML
    / JSON-LD ontologies.
    """
    pass


@custom_ontology.command("upload")
@click.option("--name", required=True, help="Short, URL-safe ontology name.")
@click.option(
    "--namespace", "namespace_iri", required=True,
    help="Declared namespace IRI (e.g. https://acme.example/ontology/).",
)
@click.option(
    "--format", "fmt",
    type=click.Choice(["turtle", "rdf_xml", "json_ld"]),
    default="turtle",
    show_default=True,
)
@click.option(
    "--file", "rdf_file",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=True,
    help="Path to the RDF body file (≤ 10 MB).",
)
def upload_custom_ontology(name: str, namespace_iri: str, fmt: str, rdf_file: str):
    """Upload a custom ontology row. Rejected with exit 1 on
    validation failure (size / parse / namespace / reserved-
    namespace) — the response body's ``code`` field carries the
    machine-readable reason."""
    with open(rdf_file, "r", encoding="utf-8") as fh:
        rdf_content = fh.read()
    try:
        resp = api_client.request(
            "POST",
            "semantic/ontologies/",
            json_data={
                "name": name,
                "namespace_iri": namespace_iri,
                "format": fmt,
                "rdf_content": rdf_content,
            },
            timeout=60,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            click.echo(json.dumps(data, indent=2))
        else:
            try:
                detail = resp.json()
            except Exception:
                detail = {"raw": resp.text[:500]}
            raise click.ClickException(
                f"Upload failed: HTTP {resp.status_code} {detail}"
            )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to upload ontology: {e}")


@custom_ontology.command("list")
def list_custom_ontologies():
    """List the tenant's custom ontologies."""
    try:
        data = api_client.get("semantic/ontologies/")
        click.echo(json.dumps(data, indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list ontologies: {e}")


@custom_ontology.command("activate")
@click.argument("ontology_id")
def activate_custom_ontology(ontology_id: str):
    """Activate an ontology — loads it into Fuseki at
    ``urn:tenant:{id}:ontology:{name}``."""
    try:
        resp = api_client.request(
            "PATCH",
            f"semantic/ontologies/{ontology_id}/",
            json_data={"is_active": True},
            timeout=30,
        )
        click.echo(json.dumps(resp.json(), indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to activate ontology: {e}")


@custom_ontology.command("deactivate")
@click.argument("ontology_id")
def deactivate_custom_ontology(ontology_id: str):
    """Deactivate an ontology — drops the Fuseki named graph."""
    try:
        resp = api_client.request(
            "PATCH",
            f"semantic/ontologies/{ontology_id}/",
            json_data={"is_active": False},
            timeout=30,
        )
        click.echo(json.dumps(resp.json(), indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to deactivate ontology: {e}")


# ── LDN (Phase 230.12 / REQ-SEM-LDN-001) ────────────────


@semantic.group("ldn")
def ldn():
    """W3C Linked Data Notifications — inbox + subscriptions."""
    pass


@ldn.command("inbox-list")
@click.argument("tenant_id")
def ldn_inbox_list_cmd(tenant_id: str):
    """List inbox entries for a tenant (TENANT_ADMIN/AUDITOR)."""
    try:
        data = api_client.get(f"semantic/ldn/inbox/{tenant_id}/")
        click.echo(json.dumps(data, indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to list inbox: {e}")


@ldn.command("subscribe")
@click.option("--target-url", required=True, help="Partner inbox URL.")
@click.option(
    "--resource-type",
    type=click.Choice(["", "asset", "contract", "dataset"]),
    default="",
    help="Restrict deliveries to a single resource type. Empty = all.",
)
def ldn_subscribe(target_url: str, resource_type: str):
    """Create an outbound LDN subscription for the current tenant."""
    try:
        resp = api_client.request(
            "POST",
            "semantic/ldn/subscriptions/",
            json_data={
                "target_inbox_url": target_url,
                "resource_type_filter": resource_type,
                "is_active": True,
            },
            timeout=30,
        )
        click.echo(json.dumps(resp.json(), indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to create subscription: {e}")


@ldn.command("unsubscribe")
@click.argument("subscription_id")
def ldn_unsubscribe(subscription_id: str):
    """Deactivate (soft-delete) an outbound LDN subscription."""
    try:
        resp = api_client.request(
            "PATCH",
            f"semantic/ldn/subscriptions/{subscription_id}/",
            json_data={"is_active": False},
            timeout=30,
        )
        click.echo(json.dumps(resp.json(), indent=2))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to deactivate subscription: {e}")


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


# ── Federation allowlist (Phase 230.8 / REQ-SEM-FED-001) ────


@semantic.group("federation")
def federation():
    """Manage the per-tenant SPARQL federation allowlist.

    SPARQL ``SERVICE`` clauses are blocked unless the target endpoint
    is on the calling tenant's active allowlist.  Use these commands
    to add, list, or revoke endpoints — all mutations are written to
    the audit log and require TENANT_ADMIN role.
    """


@federation.command("add")
@click.option("--tenant-id", required=True, help="Tenant UUID.")
@click.option("--name", required=True, help="Human-readable label (e.g. partner-X).")
@click.option(
    "--endpoint-url", required=True,
    help="Public HTTPS SPARQL endpoint URL.",
)
def federation_add(tenant_id: str, name: str, endpoint_url: str):
    """Add a SPARQL endpoint to the tenant allowlist.

    The Hub validates the URL against the same SSRF policy used by
    webhooks (loopback / link-local / RFC1918 rejected unless
    SEMANTIC_FEDERATION_ALLOW_PRIVATE is True on the deployment).
    """
    try:
        response = api_client.request(
            "POST",
            f"tenants/{tenant_id}/sparql-endpoints/",
            json_data={"name": name, "endpoint_url": endpoint_url},
        )
        if response.status_code == 201:
            click.echo(json.dumps(response.json(), indent=2))
        else:
            try:
                body = response.json()
            except Exception:
                body = {"raw": response.text[:500]}
            raise click.ClickException(
                f"federation add failed: HTTP {response.status_code} {body}"
            )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"federation add failed: {e}")


@federation.command("list")
@click.option("--tenant-id", required=True, help="Tenant UUID.")
@click.option(
    "--format", "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
)
def federation_list(tenant_id: str, output_format: str):
    """List SPARQL endpoints on the tenant allowlist."""
    try:
        data = api_client.get(f"tenants/{tenant_id}/sparql-endpoints/")
        rows = data.get("results", data) if isinstance(data, dict) else data
        if output_format == "json":
            click.echo(json.dumps(rows, indent=2))
            return
        if not rows:
            click.echo("No endpoints registered.")
            return
        header = f"{'id':<38}  {'name':<24}  {'is_active':<9}  endpoint_url"
        click.echo(header)
        click.echo("-" * len(header))
        for row in rows:
            click.echo(
                f"{row.get('id', ''):<38}  "
                f"{row.get('name', ''):<24}  "
                f"{str(row.get('is_active', '')):<9}  "
                f"{row.get('endpoint_url', '')}"
            )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"federation list failed: {e}")


@federation.command("remove")
@click.option("--tenant-id", required=True, help="Tenant UUID.")
@click.option("--id", "endpoint_id", required=True, help="Endpoint UUID.")
def federation_remove(tenant_id: str, endpoint_id: str):
    """Remove an endpoint from the tenant allowlist (audit-logged)."""
    try:
        response = api_client.request(
            "DELETE",
            f"tenants/{tenant_id}/sparql-endpoints/{endpoint_id}/",
        )
        if response.status_code in (200, 204):
            click.echo(f"Removed {endpoint_id}.")
        else:
            try:
                body = response.json()
            except Exception:
                body = {"raw": response.text[:500]}
            raise click.ClickException(
                f"federation remove failed: HTTP {response.status_code} {body}"
            )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"federation remove failed: {e}")
