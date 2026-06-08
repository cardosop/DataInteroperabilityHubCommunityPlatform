"""311.21 — INotificationService interface."""
from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class INotificationService(Protocol):
    """Notification service interface — consumed by billing, compliance, DQ."""

    def send(self, tenant_id: str, template_key: str,
             context: Optional[Dict[str, Any]] = None) -> bool: ...
    def send_to_user(self, user_id: str, template_key: str,
                     context: Optional[Dict[str, Any]] = None) -> bool: ...
