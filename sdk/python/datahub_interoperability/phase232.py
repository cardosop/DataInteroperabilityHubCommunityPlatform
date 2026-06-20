"""Phase 232.8.15 — async list helpers mirroring the JS `Phase232ProgrammeAPI`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Optional

if TYPE_CHECKING:
    from .client import DataHubClient


class Phase232ProgrammeAPI:
    """Seven compliance-programme list endpoints (authenticated hub API)."""

    def __init__(self, client: DataHubClient) -> None:
        self._client = client

    async def list_compliance_runs(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return await self._client.get("compliance/runs/", params=params or {})

    async def list_dpia_records(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return await self._client.get("dpia/records/", params=params or {})

    async def list_ropa_generations(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return await self._client.get("ropa/generations/", params=params or {})

    async def list_breach_incidents(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return await self._client.get("governance/breach-incidents/", params=params or {})

    async def list_dsar_requests(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return await self._client.get("governance/dsar-requests/", params=params or {})

    async def list_consent_purposes(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return await self._client.get("governance/consent-purposes/", params=params or {})

    async def list_processor_agreements(self, params: Optional[Mapping[str, Any]] = None) -> Any:
        return await self._client.get("governance/processor-agreements/", params=params or {})
