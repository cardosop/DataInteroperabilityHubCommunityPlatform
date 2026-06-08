"""
Compliance operations for DataHub SDK.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, FrozenSet, List, Optional

from .client import DataHubClient


class ComplianceAPI:
    """SDK surface for the ``/compliance/runs/`` endpoint family."""

    #: Phase 250.4.3 — terminal compliance-run statuses recognised
    #: by :meth:`wait_for`. Mirrors the existing ``poll_async``
    #: terminal set on this class. Published as a class constant
    #: so non-canonical deployments can subclass + override.
    TERMINAL_STATUSES: FrozenSet[str] = frozenset({
        "completed",
        "failed",
        "cancelled",
        "SUCCEEDED",
    })

    def __init__(self, client: DataHubClient):
        self.client = client

    async def create_run(
        self,
        asset_id: str,
        scan_mode: str = "full",
        regulations: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "asset_id": asset_id,
            "scan_mode": scan_mode,
        }
        if regulations:
            data["regulations"] = regulations
        return await self.client.post("compliance/runs/", data=data)

    async def list_runs(
        self,
        page: int = 1,
        page_size: int = 50,
        asset_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if asset_id:
            params["asset_id"] = asset_id
        if status:
            params["status"] = status
        return await self.client.get("compliance/runs/", params=params)

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        return await self.client.get(f"compliance/runs/{run_id}/")

    async def get_results(self, run_id: str) -> Dict[str, Any]:
        return await self.client.get(f"compliance/runs/{run_id}/results/")

    async def poll_async(
        self,
        run_id: str,
        interval: float = 2.0,
        timeout: float = 300.0,
    ) -> Dict[str, Any]:
        elapsed = 0.0
        while elapsed < timeout:
            run = await self.get_run(run_id)
            if run.get("status") in self.TERMINAL_STATUSES:
                return run
            await asyncio.sleep(interval)
            elapsed += interval
        raise TimeoutError(f"Compliance run {run_id} did not complete within {timeout}s")

    async def wait_for(
        self,
        asset_id: str,
        timeout: float = 180.0,
        interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Phase 250.4.3 — poll the latest compliance run on an
        asset until it reaches a terminal status.

        The DE-1 programmatic flow doesn't know the run_id ahead
        of time — the workflow creates the run asynchronously
        when the asset is intaken. This helper polls the
        ``/compliance/runs/?asset_id=<id>`` listing for the most
        recent run; if no run has been created yet, it keeps
        polling until one appears, then waits for it to terminate.

        Args:
            asset_id: The asset UUID to poll for compliance runs.
            timeout: Total seconds to poll before giving up.
                Default 180s — covers the slow-end tail of
                compliance scans (regulator-rules + PII-detect
                + DLP) on multi-MB payloads. The DE-1 SLO
                (250.4.10) targets P95 ≤ 60s for the FULL
                sequence, so 180s for compliance alone is a
                generous individual-step budget.
            interval: Seconds between polls. Default 2.0s.

        Returns:
            The final compliance-run payload (terminal status).
            Returns the payload even on ``failed`` / ``cancelled``
            — the caller decides whether failure is an exception.

        Raises:
            asyncio.TimeoutError: ``timeout`` elapsed before a
                run appeared OR before an existing run reached
                a terminal status.
        """
        elapsed = 0.0
        while elapsed < timeout:
            response = await self.list_runs(
                asset_id=asset_id, page_size=1,
            )
            results = response.get("results") or []
            if results:
                latest: Dict[str, Any] = results[0]
                run_asset_id = latest.get("asset_id") or latest.get("asset")
                if (run_asset_id and str(run_asset_id) == str(asset_id)
                        and latest.get("status") in self.TERMINAL_STATUSES):
                    return latest
            await asyncio.sleep(interval)
            elapsed += interval
        raise TimeoutError(
            f"No terminal compliance run for asset {asset_id} "
            f"within {timeout}s "
            f"(terminal statuses: {sorted(self.TERMINAL_STATUSES)})."
        )
