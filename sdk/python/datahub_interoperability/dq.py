"""
Data Quality operations for DataHub SDK.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, FrozenSet, Optional

from .client import DataHubClient


class DQAPI:
    """SDK surface for the ``/dq/`` endpoint family."""

    #: Phase 250.4.4 — terminal DQ-run statuses recognised by
    #: :meth:`wait_for`. The hub exposes both an uppercase variant
    #: (``PASS`` / ``FAIL`` / ``WARN`` from the Great Expectations
    #: result mapping) AND a lowercase ``completed`` / ``failed``
    #: variant from the worker-service status field. The helper
    #: accepts both so the contract works against any hub version
    #: regardless of which serializer the deployment uses.
    TERMINAL_STATUSES: FrozenSet[str] = frozenset({
        "PASS",
        "FAIL",
        "WARN",
        "completed",
        "failed",
        "cancelled",
    })

    def __init__(self, client: DataHubClient):
        self.client = client

    async def create_run(
        self,
        asset_id: str,
        dataset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        profile_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {"asset_id": asset_id}
        if dataset_id:
            data["dataset_id"] = dataset_id
        if file_id:
            data["file_id"] = file_id
        if profile_key:
            data["profile_key"] = profile_key
        return await self.client.post("dq/runs/", data=data)

    async def list_runs(
        self,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if asset_id:
            params["asset_id"] = asset_id
        if dataset_id:
            params["dataset_id"] = dataset_id
        if status:
            params["status"] = status
        return await self.client.get("dq/runs/", params=params)

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        return await self.client.get(f"dq/runs/{run_id}/")

    async def get_scorecard(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(f"dq/scorecards/{asset_id}/")

    async def list_alerts(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get("dq/alerts/", params={"asset_id": asset_id})

    async def create_alert(
        self,
        asset_id: str,
        threshold: float,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "asset_id": asset_id,
            "threshold": threshold,
        }
        return await self.client.post("dq/alerts/", data=data)

    async def get_anomalies(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(f"dq/anomalies/{asset_id}/")

    async def get_trends(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(f"dq/trends/{asset_id}/")

    async def wait_for(
        self,
        asset_id: str,
        timeout: float = 180.0,
        interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Phase 250.4.4 — poll the latest DQ run on an asset
        until it reaches a terminal status.

        The DE-1 programmatic flow doesn't know the run_id ahead
        of time — the workflow creates the run asynchronously
        when the dataset is intaken. This helper polls the
        ``/dq/runs/?asset_id=<id>`` listing for the most recent
        run; if no run has been created yet, it keeps polling
        until one appears, then waits for it to terminate.

        Args:
            asset_id: The asset UUID to poll for DQ runs.
            timeout: Total seconds to poll before giving up.
                Default 180s — covers the slow-end tail of DQ
                checks on multi-MB payloads. The DE-1 SLO
                (250.4.10) targets P95 ≤ 60s for the FULL
                sequence; 180s for DQ alone is a generous
                individual-step budget.
            interval: Seconds between polls. Default 2.0s.

        Returns:
            The final DQ-run payload (terminal status). Returns
            the payload for any of ``PASS`` / ``FAIL`` / ``WARN``
            / ``completed`` / ``failed`` / ``cancelled`` — the
            caller's policy decides whether non-PASS is an
            exception. WARN in particular is intentionally
            terminal-but-not-failure.

        Raises:
            asyncio.TimeoutError: ``timeout`` elapsed before a
                run appeared OR before an existing run reached
                a terminal status.
        """
        elapsed = 0.0
        while elapsed < timeout:
            response = await self.list_runs(
                asset_id=asset_id, limit=1,
            )
            results = response.get("results") or []
            if results:
                latest: Dict[str, Any] = results[0]
                if latest.get("status") in self.TERMINAL_STATUSES:
                    return latest
            await asyncio.sleep(interval)
            elapsed += interval
        raise TimeoutError(
            f"No terminal DQ run for asset {asset_id} "
            f"within {timeout}s "
            f"(terminal statuses: {sorted(self.TERMINAL_STATUSES)})."
        )
