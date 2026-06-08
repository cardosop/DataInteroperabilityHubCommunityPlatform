"""Processor Agreements (Phase 232.6) operations for DataHub SDK.

283.3.6.1 — processor register, Article 28 agreements, and asset–processor links.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

BASE = "governance"


class ProcessorAgreementsAPI:
    """Processor registry, agreements, and asset–processor links."""

    def __init__(self, client) -> None:
        self.client = client

    # ── Processor CRUD ──────────────────────────────────────────────────────

    async def list_processors(self, page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        return await self.client.get(
            f"{BASE}/processors/", params={"page": page, "page_size": page_size}
        )

    async def get_processor(self, processor_id: str) -> Dict[str, Any]:
        return await self.client.get(f"{BASE}/processors/{processor_id}/")

    async def create_processor(
        self, name: str, legal_name: str = "", country_code: str = "",
        website: str = "", notes: str = "",
    ) -> Dict[str, Any]:
        return await self.client.post(
            f"{BASE}/processors/",
            data={"name": name, "legal_name": legal_name, "country_code": country_code,
                  "website": website, "notes": notes},
        )

    async def update_processor(
        self, processor_id: str, **fields: Any,
    ) -> Dict[str, Any]:
        return await self.client.patch(
            f"{BASE}/processors/{processor_id}/", data=fields,
        )

    async def delete_processor(self, processor_id: str) -> Optional[Dict[str, Any]]:
        return await self.client.delete(f"{BASE}/processors/{processor_id}/")

    # ── Agreement CRUD ──────────────────────────────────────────────────────

    async def list_agreements(self, page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        return await self.client.get(
            f"{BASE}/processor-agreements/", params={"page": page, "page_size": page_size}
        )

    async def get_agreement(self, agreement_id: str) -> Dict[str, Any]:
        return await self.client.get(f"{BASE}/processor-agreements/{agreement_id}/")

    async def create_agreement(
        self,
        processor_id: str,
        agreement_type: str,
        document_uri: str,
        document_hash: str,
        effective_from: str,
        expires_on: Optional[str] = None,
        sub_processors_declared: Optional[list[Dict[str, Any]]] = None,
        jurisdiction_region: str = "",
        registration_reference: str = "",
        transfer_mechanism_summary: str = "",
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "processor": processor_id,
            "agreement_type": agreement_type,
            "document_uri": document_uri,
            "document_hash": document_hash,
            "effective_from": effective_from,
        }
        if expires_on:
            data["expires_on"] = expires_on
        if sub_processors_declared is not None:
            data["sub_processors_declared"] = sub_processors_declared
        if jurisdiction_region:
            data["jurisdiction_region"] = jurisdiction_region
        if registration_reference:
            data["registration_reference"] = registration_reference
        if transfer_mechanism_summary:
            data["transfer_mechanism_summary"] = transfer_mechanism_summary
        return await self.client.post(f"{BASE}/processor-agreements/", data=data)

    async def update_agreement(
        self, agreement_id: str, **fields: Any,
    ) -> Dict[str, Any]:
        return await self.client.patch(
            f"{BASE}/processor-agreements/{agreement_id}/", data=fields,
        )

    async def delete_agreement(self, agreement_id: str) -> Optional[Dict[str, Any]]:
        return await self.client.delete(f"{BASE}/processor-agreements/{agreement_id}/")

    # ── Asset–Processor Links ───────────────────────────────────────────────

    async def list_links(self, page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        return await self.client.get(
            f"{BASE}/asset-processor-links/",
            params={"page": page, "page_size": page_size},
        )

    async def create_link(self, asset_id: str, processor_id: str) -> Dict[str, Any]:
        return await self.client.post(
            f"{BASE}/asset-processor-links/",
            data={"asset": asset_id, "processor": processor_id},
        )

    async def delete_link(self, link_id: str) -> Optional[Dict[str, Any]]:
        return await self.client.delete(f"{BASE}/asset-processor-links/{link_id}/")
