"""311.21 — IContractService interface for circular import resolution."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IContractService(Protocol):
    """Contract service interface — consumed by lineage, marketplace, governance."""

    def validate_contract(self, contract_id: str) -> dict[str, Any]: ...
    def get_contract_schema(self, contract_id: str) -> dict[str, Any]: ...
    def normalize_contract(self, data: dict[str, Any]) -> dict[str, Any]: ...
