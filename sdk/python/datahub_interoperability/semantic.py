"""
Semantic operations for DataHub SDK.
"""

from typing import Any

from .client import DataHubClient


class SemanticAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def sparql_query(
        self,
        query: str,
        accept: str = "application/sparql-results+json",
    ) -> dict[str, Any]:
        return await self.client.post(
            "semantic/sparql/query/",
            data={"query": query},
            headers={"Accept": accept},
        )

    async def sparql_construct(
        self,
        query: str,
        accept: str = "application/ld+json",
    ) -> dict[str, Any]:
        return await self.client.post(
            "semantic/sparql/construct/",
            data={"query": query},
            headers={"Accept": accept},
        )

    async def rdf_ingest(
        self,
        data: str,
        content_type: str = "text/turtle",
    ) -> dict[str, Any]:
        return await self.client.post(
            "semantic/rdf/ingest/",
            data={"data": data, "content_type": content_type},
        )

    async def get_ontology(self) -> dict[str, Any]:
        return await self.client.get("semantic/ontology/")

    async def get_jsonld_context(self) -> dict[str, Any]:
        """Return the JSON-LD ``@context`` document.

        Phase 230.6 (REQ-SEM-CONTEXT-ALIAS-001) — calls the
        extension-less alias ``GET /api/v1/semantic/context`` so the
        SDK's URL matches the public docs at
        ``docs/mvpdocs/concepts/semantic-resources.md`` line 118.
        Both alias and canonical (``context.jsonld``) routes return
        byte-identical bodies, so the choice is documentation
        consistency, not capability.
        """
        return await self.client.get("semantic/context")

    async def get_void(self) -> dict[str, Any]:
        return await self.client.get("semantic/void/")

    async def shacl_validate(
        self,
        data: str,
        shapes: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"data": data}
        if shapes:
            payload["shapes"] = shapes
        return await self.client.post("semantic/shacl/validate/", data=payload)

    async def resource_resolve(self, uri: str) -> dict[str, Any]:
        return await self.client.get("semantic/resource/resolve/", params={"uri": uri})

    async def execute_graphql_ld(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL-LD query against the semantic graph.

        Args:
            query: GraphQL-LD query string (must be non-empty).
            variables: Optional variables dict for parameterised queries.

        Returns:
            Response dict with ``data`` and/or ``errors`` keys.

        Raises:
            ValueError: If *query* is empty or None.
        """
        if not query or not query.strip():
            raise ValueError("GraphQL-LD query must be non-empty")
        body: dict[str, Any] = {"query": query}
        if variables is not None:
            body["variables"] = variables
        return await self.client.post("semantic/graphql", data=body)
