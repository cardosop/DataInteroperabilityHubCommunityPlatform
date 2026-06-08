"""311.21 — IAssetService interface."""
from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class IAssetService(Protocol):
    """Asset service interface — consumed by contracts, DQ, compliance."""

    def get_asset(self, asset_id: str) -> Dict[str, Any]: ...
    def activate_asset(self, asset_id: str) -> Dict[str, Any]: ...
    def get_asset_schema(self, asset_id: str) -> Optional[Dict[str, Any]]: ...
