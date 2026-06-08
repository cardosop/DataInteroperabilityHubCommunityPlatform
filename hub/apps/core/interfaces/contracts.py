"""311.21 — IContractService interface for circular import resolution."""
from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class IContractService(Protocol):
    """Contract service interface — consumed by lineage, marketplace, governance."""

    def validate_contract(self, contract_id: str) -> Dict[str, Any]: ...
    def get_contract_schema(self, contract_id: str) -> Dict[str, Any]: ...
    def normalize_contract(self, data: Dict[str, Any]) -> Dict[str, Any]: ...
