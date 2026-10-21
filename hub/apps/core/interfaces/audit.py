"""311.21 — IAuditService interface."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IAuditService(Protocol):
    """Audit service interface — consumed by all apps for audit trail."""

    def create_event(
        self,
        action: str,
        tenant_id: str | None,
        resource_id: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...
    def query_events(
        self, resource_type: str, resource_id: str, limit: int = 50
    ) -> list[dict[str, Any]]: ...
