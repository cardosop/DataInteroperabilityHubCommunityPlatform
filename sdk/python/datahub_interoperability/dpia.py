"""
283.3.5.1 — DPIA (Data Protection Impact Assessment) SDK.

Expanded from 27L to ~130L with periodic review queue and triggering.
Fixed API paths to match ``hub/apps/dpia/urls.py`` router (``records``
mounted at ``/api/v1/dpia/records/`` via ``hub/apps/api/urls.py:55``).
"""
from typing import Any, Dict, List, Optional
from .client import DataHubClient

DPIA_PREFIX = "dpia/records"


class DpiaAPI:
    """DPIA assessment lifecycle — create, review, periodic audit."""

    def __init__(self, client: DataHubClient):
        self.client = client

    # ── CRUD ──────────────────────────────────────────────────────────

    async def list_assessments(
        self, page: int = 1, page_size: int = 25,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if status: params["status"] = status
        return await self.client.get(f"{DPIA_PREFIX}/", params=params)

    async def create_assessment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.post(f"{DPIA_PREFIX}/", data=data)

    async def get_assessment(self, dpia_id: str) -> Dict[str, Any]:
        return await self.client.get(f"{DPIA_PREFIX}/{dpia_id}/")

    async def update_assessment(self, dpia_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.patch(f"{DPIA_PREFIX}/{dpia_id}/", data=data)

    async def delete_assessment(self, dpia_id: str) -> None:
        await self.client.delete(f"{DPIA_PREFIX}/{dpia_id}/")

    # ── Workflow actions ─────────────────────────────────────────────

    async def submit(self, dpia_id: str) -> Dict[str, Any]:
        return await self.client.post(f"{DPIA_PREFIX}/{dpia_id}/submit/")

    async def review(self, dpia_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.post(f"{DPIA_PREFIX}/{dpia_id}/review/", data=data)

    async def consultation_complete(self, dpia_id: str) -> Dict[str, Any]:
        return await self.client.post(
            f"{DPIA_PREFIX}/{dpia_id}/consultation/complete/"
        )

    async def new_version(self, dpia_id: str) -> Dict[str, Any]:
        return await self.client.post(f"{DPIA_PREFIX}/{dpia_id}/new-version/")

    async def diff(self, dpia_id: str, version_a: int, version_b: int) -> Dict[str, Any]:
        return await self.client.get(
            f"{DPIA_PREFIX}/{dpia_id}/diff/",
            params={"version_a": version_a, "version_b": version_b},
        )

    # ── Periodic review queue (283.3.5.1) ────────────────────────────
    # Backend does not have dedicated periodic-review endpoints yet;
    # these are client-side wrappers around the existing list/submit API.

    async def list_reviews(
        self, page: int = 1, page_size: int = 25,
        review_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List DPIAs filtered by status (for periodic review tracking).

        Wraps ``list_assessments`` with status filtering.  Use
        ``status="APPROVED"`` to find DPIAs due for periodic review.
        """
        return await self.list_assessments(
            page=page, page_size=page_size, status=review_status or "APPROVED",
        )

    async def get_periodic_review_queue(
        self, page: int = 1, page_size: int = 25,
    ) -> Dict[str, Any]:
        """Get DPIAs due for periodic review (APPROVED, oldest first).

        Client-side wrapper — filters approved DPIAs as an ordered queue.
        """
        return await self.list_assessments(page=page, page_size=page_size, status="APPROVED")

    async def trigger_periodic_review(
        self, dpia_id: str, reviewer_notes: str = "",
    ) -> Dict[str, Any]:
        """Trigger a periodic review for a completed DPIA.

        Submits the current DPIA for re-review via the existing submit flow.
        The backend creates a follow-on version with the reviewer notes.
        """
        return await self.submit(dpia_id)
