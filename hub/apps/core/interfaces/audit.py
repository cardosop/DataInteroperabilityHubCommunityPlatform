"""311.21 — IAuditService interface."""
from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class IAuditService(Protocol):
    """Audit service interface — consumed by all apps for audit trail."""

    def create_event(self, action: str, tenant_id: Optional[str], resource_id: str,
                     details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]: ...
    def query_events(self, resource_type: str, resource_id: str,
                     limit: int = 50) -> list[Dict[str, Any]]: ...
