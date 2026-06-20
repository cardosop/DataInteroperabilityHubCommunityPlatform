"""
Search commands.

Provides CLI commands for full-text search across contracts, assets, and datasets.
Uses real hub API - no mocks/stubs.
"""

import json

import click

from ..api_client import api_client


@click.group()
def search():
    """Search commands"""


@search.command("search")
@click.option("--query", "-q", required=True, help="Search query string")
@click.option("--type", help="Filter by resource type (CONTRACT, ASSET, DATASET)")
@click.option("--classification", help="Filter by data classification")
@click.option("--owner", help="Filter by owner ID")
@click.option("--tags", help="Filter by tags (comma-separated)")
@click.option("--domain", help="Filter by domain")
@click.option("--quality-status", help="Filter by quality status")
@click.option("--compliance-status", help="Filter by compliance status")
@click.option("--limit", type=int, default=20, help="Results per page (default: 20, max: 100)")
@click.option("--offset", type=int, default=0, help="Pagination offset (default: 0)")
@click.option(
    "--sort-by",
    type=click.Choice(["relevance", "created_at", "indexed_at"]),
    default="relevance",
    help="Sort field",
)
@click.option("--sort-order", type=click.Choice(["asc", "desc"]), default="desc", help="Sort order")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def search_resources(
    query: str,
    type: str | None,
    classification: str | None,
    owner: str | None,
    tags: str | None,
    domain: str | None,
    quality_status: str | None,
    compliance_status: str | None,
    limit: int,
    offset: int,
    sort_by: str,
    sort_order: str,
    output_format: str,
):
    """Perform full-text search across contracts, assets, and datasets"""
    params = {
        "q": query,
        "limit": limit,
        "offset": offset,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }
    if type:
        params["type"] = type
    if classification:
        params["classification"] = classification
    if owner:
        params["owner"] = owner
    if tags:
        params["tags"] = tags
    if domain:
        params["domain"] = domain
    if quality_status:
        params["quality_status"] = quality_status
    if compliance_status:
        params["compliance_status"] = compliance_status

    try:
        data = api_client.get("search/search/", params=params)

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            results = data.get("results", [])
            total = data.get("count", len(results))

            click.echo(f"Found {total} result(s)")
            if not results:
                return

            click.echo(f"\n{'Type':<15} {'ID':<40} {'Name':<40} {'Score':<10}")
            click.echo("-" * 105)
            for result in results:
                resource_type = str(result.get("type", ""))[:13] if result.get("type") else ""
                resource_id = str(result.get("id", ""))[:38] if result.get("id") else ""
                name = str(result.get("name", ""))[:38] if result.get("name") else ""
                score = f"{result.get('score', 0):.2f}" if result.get("score") else "N/A"
                click.echo(f"{resource_type:<15} {resource_id:<40} {name:<40} {score:<10}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to search: {e}")


@search.command("suggestions")
@click.option("--query", "-q", required=True, help="Search query string")
@click.option("--limit", type=int, default=10, help="Maximum suggestions (default: 10)")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_suggestions(query: str, limit: int, output_format: str):
    """Get search suggestions/autocomplete"""
    params = {
        "q": query,
        "limit": limit,
    }

    try:
        data = api_client.get("search/suggestions/", params=params)

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            # API returns a list directly, not a dict with "suggestions" key
            suggestions = data if isinstance(data, list) else []
            if not suggestions:
                click.echo("No suggestions found.")
                return

            click.echo("Suggestions:")
            for suggestion in suggestions:
                # Handle both string suggestions and dict suggestions
                if isinstance(suggestion, dict):
                    text = suggestion.get("text", "")
                    suggestion_type = suggestion.get("type", "")
                    click.echo(f"  - {text} ({suggestion_type})")
                else:
                    click.echo(f"  - {suggestion}")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get suggestions: {e}")


@search.command("analytics")
@click.option("--start-date", help="Start date (ISO 8601 format)")
@click.option("--end-date", help="End date (ISO 8601 format)")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def get_analytics(start_date: str | None, end_date: str | None, output_format: str):
    """Get search analytics"""
    params = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date

    try:
        data = api_client.get("search/analytics/", params=params)

        if output_format == "json":
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo("Search Analytics:")
            click.echo(f"Total Searches: {data.get('total_searches', 0)}")
            click.echo(f"Unique Queries: {data.get('unique_queries', 0)}")
            if data.get("top_queries"):
                click.echo("\nTop Queries:")
                for query_item in data.get("top_queries", [])[:10]:
                    click.echo(f"  - {query_item.get('query')}: {query_item.get('count')} searches")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to get analytics: {e}")
