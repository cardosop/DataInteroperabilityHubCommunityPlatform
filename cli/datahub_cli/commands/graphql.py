"""
GraphQL query commands (Phase 286).

Provides CLI access to the three GraphQL endpoints:
  - Strawberry:  POST /graphql/
  - Graphene:    POST /graphql-graphene/
  - Linked-Data: POST /api/v1/semantic/graphql
"""

import json

import click

from ..api_client import api_client


@click.group()
def graphql():
    """GraphQL query commands"""


@graphql.command("query")
@click.option(
    "--query",
    "query_str",
    help="GraphQL query string",
)
@click.option(
    "--file",
    "query_file",
    type=click.Path(exists=True),
    help="File containing GraphQL query",
)
@click.option(
    "--variables",
    "-v",
    default="{}",
    help="JSON-encoded query variables",
)
@click.option(
    "--endpoint",
    "-e",
    type=click.Choice(["strawberry", "graphene", "ld"]),
    default="strawberry",
    help="GraphQL endpoint to target",
)
@click.option(
    "--context",
    "jsonld_context",
    default=None,
    help="JSON-LD @context for the ld endpoint (inline JSON or hub context URL)",
)
def query(query_str, query_file, variables, endpoint, jsonld_context):
    """Execute a GraphQL query.

    \b
    Examples:
      datahub graphql query --query "{ assets { id name } }"
      datahub graphql query --endpoint ld -q "{ assets { id } }"
      datahub graphql query --endpoint graphene -f query.gql
    """
    if query_file:
        with open(query_file) as f:
            query_str = f.read()

    if not query_str:
        raise click.UsageError("Either --query or --file is required")

    try:
        variables_dict = json.loads(variables)
    except json.JSONDecodeError:
        raise click.UsageError(f"Invalid JSON for --variables: {variables}")

    endpoint_paths = {
        "strawberry": "/graphql/",
        "graphene": "/graphql-graphene/",
        "ld": "/api/v1/semantic/graphql",
    }
    url = endpoint_paths[endpoint]

    body = {"query": query_str, "variables": variables_dict}
    if jsonld_context:
        try:
            body["context"] = json.loads(jsonld_context)
        except json.JSONDecodeError:
            body["context"] = jsonld_context

    resp = api_client.post(url, json=body)
    click.echo(json.dumps(resp, indent=2))
