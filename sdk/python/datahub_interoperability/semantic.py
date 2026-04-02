"""
Semantic operations for DataHub SDK.
"""
from typing import Any, Dict, Optional

from .client import DataHubClient


class SemanticAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def sparql_query(
        self,
        query: str,
        accept: str = "application/sparql-results+json",
    ) -> Dict[str, Any]:
        return await self.client.post(
            "semantic/sparql/query/",
            data={"query": query},
            headers={"Accept": accept},
        )

    async def sparql_construct(
        self,
        query: str,
        accept: str = "application/ld+json",
    ) -> Dict[str, Any]:
        return await self.client.post(
            "semantic/sparql/construct/",
            data={"query": query},
            headers={"Accept": accept},
        )

    async def rdf_ingest(
        self,
        data: str,
        content_type: str = "text/turtle",
    ) -> Dict[str, Any]:
        return await self.client.post(
            "semantic/rdf/ingest/",
            data={"data": data, "content_type": content_type},
        )

    async def get_ontology(self) -> Dict[str, Any]:
        return await self.client.get("semantic/ontology/")

    async def get_void(self) -> Dict[str, Any]:
        return await self.client.get("semantic/void/")

    async def shacl_validate(
        self,
        data: str,
        shapes: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"data": data}
        if shapes:
            payload["shapes"] = shapes
        return await self.client.post("semantic/shacl/validate/", data=payload)

    async def resource_resolve(self, uri: str) -> Dict[str, Any]:
        return await self.client.get("semantic/resource/resolve/", params={"uri": uri})
