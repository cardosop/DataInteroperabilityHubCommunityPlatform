"""
Job operations for DataHub SDK.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, FrozenSet, Optional

from .client import DataHubClient


class JobsAPI:
    """SDK surface for the ``/jobs/`` endpoint family."""

    #: Phase 250.4.2 — terminal job statuses recognised by
    #: :meth:`wait_for`. Mirrors
    #: ``hub/apps/jobs/models.py::JobStatus`` lines 60-66:
    #: ``PENDING`` / ``RUNNING`` are non-terminal; ``COMPLETED`` /
    #: ``FAILED`` / ``CANCELLED`` are terminal. Published as a
    #: class constant so a deployment with non-canonical job
    #: statuses can subclass ``JobsAPI`` and override this set
    #: without re-implementing the poll loop.
    TERMINAL_STATUSES: FrozenSet[str] = frozenset({
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    })

    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return await self.client.get("jobs/", params=params)

    async def get_job(self, job_id: str) -> Dict[str, Any]:
        return await self.client.get(f"jobs/{job_id}/")

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        return await self.client.post(f"jobs/{job_id}/cancel/")

    async def wait_for(
        self,
        job_id: str,
        timeout: float = 300.0,
        interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Phase 250.4.2 — poll ``GET /jobs/{id}/`` until terminal status.

        Args:
            job_id: The job UUID to poll.
            timeout: Total seconds to poll before giving up.
                Default 300s — covers the slow-end tail of
                long-running ingestion + compliance scans on
                multi-MB payloads. The DE-1 SLO (250.4.10)
                targets P95 ≤ 60s, so 300s gives a 5× safety
                margin.
            interval: Seconds between polls. Default 2.0s — fast
                enough that completion is observed within one
                interval of the worker writing the terminal
                status, slow enough that a stuck job doesn't
                spam the API at request-rate-limited tenants.

        Returns:
            The final job payload (terminal status). Returns the
            payload even on FAILED / CANCELLED — the caller
            decides whether failure is an exception.

        Raises:
            asyncio.TimeoutError: ``timeout`` elapsed before the
                job reached a terminal status. The error carries
                the ``job_id`` so the caller can surface it.
        """
        elapsed = 0.0
        while elapsed < timeout:
            job = await self.get_job(job_id)
            if job.get("status") in self.TERMINAL_STATUSES:
                return job
            await asyncio.sleep(interval)
            elapsed += interval
        raise TimeoutError(
            f"Job {job_id} did not reach a terminal status "
            f"({sorted(self.TERMINAL_STATUSES)}) within {timeout}s."
        )
