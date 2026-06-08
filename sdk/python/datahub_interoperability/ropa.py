"""RoPA (Record of Processing Activities) operations for DataHub SDK.

283.3.3.1 — expanded from 16L to ~100L with create/update/delete/export/pdf/map.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


_REGULATION_MAP: Dict[str, str] = {
    "GDPR": "General Data Protection Regulation (EU) 2016/679",
    "UK_GDPR": "UK General Data Protection Regulation",
    "LGPD": "Lei Geral de Protecao de Dados (Brazil)",
    "CCPA": "California Consumer Privacy Act",
    "PIPEDA": "Personal Information Protection and Electronic Documents Act (Canada)",
    "PDPA": "Personal Data Protection Act (Singapore)",
}


class RopaAPI:
    """RoPA generation, preview, download, and lifecycle management."""

    BASE = "ropa/generations"

    def __init__(self, client) -> None:
        self.client = client

    # ── Query ──────────────────────────────────────────────────────────────

    async def list_records(self, page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        """List RoPA generations for the active tenant (paginated)."""
        return await self.client.get(
            f"{self.BASE}/", params={"page": page, "page_size": page_size}
        )

    async def get_record(self, record_id: str) -> Dict[str, Any]:
        """Retrieve a single RoPA generation by id."""
        return await self.client.get(f"{self.BASE}/{record_id}/")

    # ── Preview ────────────────────────────────────────────────────────────

    async def preview(self, regulation: str = "GDPR") -> Dict[str, Any]:
        """Preview the RoPA payload for *regulation* without persisting."""
        return await self.client.get(
            f"{self.BASE}/preview/", params={"regulation": regulation}
        )

    # ── Generate ───────────────────────────────────────────────────────────

    async def generate(
        self, regulation: str = "GDPR", output_format: str = "json"
    ) -> Dict[str, Any]:
        """Generate a new RoPA artefact (sync under threshold; async above)."""
        return await self.client.post(
            "ropa/generate/",
            params={"regulation": regulation, "format": output_format},
        )

    async def create_record(
        self,
        regulation: str = "GDPR",
        output_format: str = "json",
    ) -> Dict[str, Any]:
        """Create a new RoPA generation (convenience alias for generate)."""
        return await self.generate(regulation=regulation, output_format=output_format)

    # ── Update / Delete ────────────────────────────────────────────────────

    async def update_record(
        self, record_id: str, **fields: Any
    ) -> Dict[str, Any]:
        """Update mutable metadata on a RoPA generation (partial update)."""
        return await self.client.patch(
            f"{self.BASE}/{record_id}/update/", data=fields
        )

    async def delete_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Delete a RoPA generation."""
        return await self.client.delete(f"{self.BASE}/{record_id}/delete/")

    # ── Download ───────────────────────────────────────────────────────────

    async def download(self, record_id: str) -> Dict[str, Any]:
        """Get a presigned download URL for a completed RoPA artefact."""
        return await self.client.get(f"{self.BASE}/{record_id}/download/")

    # ── PDF export convenience ─────────────────────────────────────────────

    async def export_pdf(
        self,
        regulation: str = "GDPR",
        poll_interval_s: float = 2.0,
        max_wait_s: float = 120.0,
    ) -> Dict[str, Any]:
        """Generate a PDF RoPA artefact, poll until complete, then return
        the download URL. Raises ``TimeoutError`` if generation exceeds
        *max_wait_s*."""
        import asyncio

        gen = await self.generate(regulation=regulation, output_format="pdf")
        ropa_id = gen.get("ropa_generation_id") or gen.get("id")

        if not gen.get("async"):
            # Synchronous — artefact is already complete; download immediately.
            return await self.download(str(ropa_id))

        elapsed = 0.0
        while elapsed < max_wait_s:
            await asyncio.sleep(poll_interval_s)
            elapsed += poll_interval_s
            status_resp = await self.get_record(str(ropa_id))
            st = status_resp.get("status", "")
            if st == "COMPLETED":
                return await self.download(str(ropa_id))
            if st == "FAILED":
                raise RuntimeError(
                    f"RoPA PDF generation failed: {status_resp.get('error_message', 'unknown')}"
                )

        raise TimeoutError(
            f"RoPA PDF generation did not complete within {max_wait_s}s"
        )

    # ── Regulation map ─────────────────────────────────────────────────────

    @staticmethod
    def get_regulation_map() -> Dict[str, str]:
        """Return a dict of supported regulation keys -> human-readable names."""
        return dict(_REGULATION_MAP)

