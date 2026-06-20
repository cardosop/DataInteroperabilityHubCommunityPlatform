"""
283.3.7.1 — Data Retention SDK.

Covers retention policy management, sweep status, and per-event-type overrides.
Backend endpoints verified against ``hub/apps/audit/urls.py`` (mounted at
``/api/v1/audit/`` via ``hub/apps/api/urls.py:40``).
"""

from typing import Any, Dict

from .client import DataHubClient

AUDIT_PREFIX = "audit"


class RetentionAPI:
    """Data retention policy management and sweep operations."""

    def __init__(self, client: DataHubClient):
        self.client = client

    # ── Event retention policies ─────────────────────────────────────

    async def list_policies(
        self,
        page: int = 1,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        """List per-event-type retention policy overrides.

        Maps to ``GET audit/event-retention-policies/``.
        """
        return await self.client.get(
            f"{AUDIT_PREFIX}/event-retention-policies/",
            params={"page": page, "page_size": page_size},
        )

    async def get_policy(self, policy_id: str) -> Dict[str, Any]:
        """Get a single retention policy override."""
        return await self.client.get(f"{AUDIT_PREFIX}/event-retention-policies/{policy_id}/")

    async def create_policy(
        self,
        event_type: str,
        retention_days: int,
        description: str = "",
    ) -> Dict[str, Any]:
        """Create a per-event-type retention policy override.

        Args:
            event_type: Audit event type (e.g. ``TENANT_FEATURE_FLAG_CHANGED``).
            retention_days: Retention period in days (overrides category default).
            description: Human-readable justification.
        """
        return await self.client.post(
            f"{AUDIT_PREFIX}/event-retention-policies/",
            data={
                "event_type": event_type,
                "retention_days": retention_days,
                "description": description,
            },
        )

    async def update_policy(
        self,
        policy_id: str,
        retention_days: int,
        description: str = "",
    ) -> Dict[str, Any]:
        """Update an existing retention policy override."""
        payload: Dict[str, Any] = {"retention_days": retention_days}
        if description:
            payload["description"] = description
        return await self.client.patch(
            f"{AUDIT_PREFIX}/event-retention-policies/{policy_id}/",
            data=payload,
        )

    async def delete_policy(self, policy_id: str) -> None:
        """Delete a retention policy override."""
        await self.client.delete(f"{AUDIT_PREFIX}/event-retention-policies/{policy_id}/")

    # ── Sweep status ─────────────────────────────────────────────────

    async def get_sweep_status(self) -> Dict[str, Any]:
        """Get the most recent audit events for sweep activity inspection.

        Returns the raw audit event list. Sweep metrics (records deleted,
        categories processed) are available via the ``enforce_retention``
        management command output (structlog) and the
        ``retention_enforcement_total`` Prometheus counter.
        """
        return await self.client.get(f"{AUDIT_PREFIX}/audit-events/", params={"page_size": 10})

    async def trigger_sweep(self, dry_run: bool = True, category: str = "") -> Dict[str, Any]:
        """Document the retention enforcement sweep interface.

        Retention enforcement runs as a Django management command
        (``python manage.py enforce_retention --execute``) scheduled daily
        at 03:00 UTC via cron.  This method returns the documented command
        interface for client awareness — actual execution requires shell
        access to the API pod.

        For programmatic retention policy management, use the
        ``event-retention-policies`` CRUD methods above.
        """
        return {
            "message": "Retention sweep is a management command.",
            "command": "python manage.py enforce_retention"
            + (" --dry-run" if dry_run else " --execute"),
            "category": category or "all",
            "schedule": "daily at 03:00 UTC (cron)",
            "metrics": "retention_enforcement_total (Prometheus)",
        }
