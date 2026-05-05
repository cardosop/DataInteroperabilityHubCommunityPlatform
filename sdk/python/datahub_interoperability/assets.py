"""
Asset operations for DataHub SDK.
"""
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from .client import DataHubClient
from .idempotency import (
    IDEMPOTENCY_HEADER,
    canonical_body_bytes,
    compose_idempotency_key,
)


class AssetsAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_assets(
        self,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if domain:
            params["domain"] = domain
        return await self.client.get("assets/", params=params)

    async def get_asset(
        self,
        asset_id: str,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if include:
            params["include"] = ",".join(include)
        return await self.client.get(f"assets/{asset_id}/", params=params)

    async def create_asset(
        self,
        name: str,
        key: str,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        visibility: str = "private",
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "name": name,
            "key": key,
            "visibility": visibility,
        }
        if description:
            data["description"] = description
        if domain:
            data["domain"] = domain
        return await self.client.post("assets/", data=data)

    async def update_asset(self, asset_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self.client.patch(f"assets/{asset_id}/", data=kwargs)

    async def delete_asset(self, asset_id: str) -> None:
        await self.client.delete(f"assets/{asset_id}/")

    async def activate_asset(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.post(f"assets/{asset_id}/activate/")

    async def get_health_score(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(f"assets/{asset_id}/health-score/")

    async def get_recommendations(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(f"assets/{asset_id}/recommendations/")

    async def get_popularity(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(f"assets/{asset_id}/popularity/")

    async def classify_asset(
        self,
        asset_id: str,
        classification: Dict[str, Any],
    ) -> Dict[str, Any]:
        return await self.client.post(f"assets/{asset_id}/classify/", data=classification)

    async def create_data_first(
        self,
        *,
        tenant_uuid: Union[str, UUID],
        file_id: str,
        key: str,
        name: str,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        visibility: str = "INTERNAL",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /assets/data-first/ with an Idempotency-Key auto-composed.

        Phase 250.1.D.5 — wraps the data-first endpoint with the
        D250.8 idempotency contract. ``Idempotency-Key`` is composed
        deterministically from ``tenant_uuid`` + the canonical body
        bytes; a duplicate retry within 24 h returns the original
        response without re-running the workflow.

        Args:
            tenant_uuid: The tenant UUID this request belongs to.
                Used as the prefix in the composed key. The server
                rejects keys whose tenant prefix doesn't match the
                authenticated request tenant.
            file_id, key, name, description, domain, visibility:
                Standard data-first request fields. ``key`` is the
                tenant-scoped asset key (NOT the idempotency key).
            idempotency_key: Optional override. When set, used
                verbatim — useful for SDK consumers that already
                have a deterministic key from an outer system.
                When ``None`` (default) the SDK composes one from
                ``tenant_uuid`` + the request body.

        Returns:
            Dict with ``asset_id`` / ``dataset_id`` / ``contract_id``
            on success, or the server's error response on failure.

        Raises:
            ValueError: ``tenant_uuid`` is not a valid UUID.
        """
        body: Dict[str, Any] = {
            "file_id": file_id,
            "key": key,
            "name": name,
            "visibility": visibility,
        }
        if description is not None:
            body["description"] = description
        if domain is not None:
            body["domain"] = domain

        # The server validates the body hash against the key suffix
        # using ``canonical_body_bytes`` — we MUST send the SAME bytes
        # the SDK hashed, otherwise the server returns 409
        # IDEMPOTENCY_KEY_MISMATCH. The httpx default JSON encoding
        # may differ in whitespace / key order, so we serialise
        # explicitly here and pass as ``content`` rather than
        # ``json``.
        canonical_bytes = canonical_body_bytes(body)
        effective_key = idempotency_key or compose_idempotency_key(
            tenant_uuid, canonical_bytes
        )

        response = await self.client.request(
            "POST",
            "assets/data-first/",
            content=canonical_bytes,
            headers={
                IDEMPOTENCY_HEADER: effective_key,
                "Content-Type": "application/json",
            },
        )
        return response.json()
