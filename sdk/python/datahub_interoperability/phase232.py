"""Phase 232.8.15 — async list helpers mirroring the JS `Phase232ProgrammeAPI`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .client import DataHubClient


class Phase232ProgrammeAPI:
    """Seven compliance-programme list endpoints (authenticated hub API)."""

    def __init__(self, client: DataHubClient) -> None:
        self._client = client

    async def list_compliance_runs(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self._client.get("compliance/runs/", params=params or {})

    async def list_dpia_records(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self._client.get("dpia/records/", params=params or {})

    async def list_ropa_generations(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self._client.get("ropa/generations/", params=params or {})

    async def list_breach_incidents(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self._client.get("governance/breach-incidents/", params=params or {})

    async def list_dsar_requests(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self._client.get("governance/dsar-requests/", params=params or {})

    async def list_consent_purposes(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self._client.get("governance/consent-purposes/", params=params or {})

    async def list_processor_agreements(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self._client.get("governance/processor-agreements/", params=params or {})
