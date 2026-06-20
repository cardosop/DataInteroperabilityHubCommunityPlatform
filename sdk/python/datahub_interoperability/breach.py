"""
283.3.4.1 — Breach Notification SDK.

Covers the full breach workflow: create → notify → SLA tracking → resolution.
"""

from typing import Any, Dict, List, Optional

from .client import DataHubClient


class BreachAPI:
    """Breach incident management — create, track, notify, resolve."""

    def __init__(self, client: DataHubClient):
        self.client = client

    # ── Create ────────────────────────────────────────────────────────

    async def create_incident(
        self,
        title: str,
        description: str,
        sla_level: str = "STANDARD",
        affected_data_categories: Optional[List[str]] = None,
        affected_subjects_count: Optional[int] = None,
        discovered_at: Optional[str] = None,
        notification_deadline: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new breach incident.

        Args:
            title: Incident title.
            description: Detailed description of the breach.
            sla_level: One of ``STANDARD``, ``HIGH``, ``CRITICAL``.
            affected_data_categories: e.g. ``["PII", "financial"]``.
            affected_subjects_count: Estimated number of affected subjects.
            discovered_at: ISO-8601 timestamp of discovery.
            notification_deadline: ISO-8601 statutory deadline override.
        """
        payload: Dict[str, Any] = {
            "title": title,
            "description": description,
            "sla_level": sla_level,
        }
        if affected_data_categories:
            payload["affected_data_categories"] = affected_data_categories
        if affected_subjects_count is not None:
            payload["affected_subjects_count"] = affected_subjects_count
        if discovered_at:
            payload["discovered_at"] = discovered_at
        if notification_deadline:
            payload["notification_deadline"] = notification_deadline
        return await self.client.post("governance/breach-incidents/", data=payload)

    # ── List / Get ───────────────────────────────────────────────────

    async def list_incidents(
        self,
        status: Optional[str] = None,
        sla_level: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List breach incidents with optional filters."""
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        if sla_level:
            params["sla_level"] = sla_level
        return await self.client.get("governance/breach-incidents/", params=params)

    async def get_incident(self, incident_id: str) -> Dict[str, Any]:
        """Get full details of a breach incident."""
        return await self.client.get(f"governance/breach-incidents/{incident_id}/")

    # ── Update status ────────────────────────────────────────────────

    async def update_status(
        self,
        incident_id: str,
        status: str,
        resolution_note: str = "",
    ) -> Dict[str, Any]:
        """Update the status of a breach incident.

        Args:
            incident_id: UUID of the incident.
            status: New status (``OPEN``, ``INVESTIGATING``, ``NOTIFIED_DPA``,
                ``NOTIFIED_SUBJECTS``, ``RESOLVED``, ``CLOSED``).
            resolution_note: Required when status is ``RESOLVED`` or ``CLOSED``.
        """
        return await self.client.patch(
            f"governance/breach-incidents/{incident_id}/status/",
            data={"status": status, "notes": resolution_note},
        )

    # ── Notifications ────────────────────────────────────────────────

    async def list_notifications(
        self,
        incident_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List notifications sent for a breach incident."""
        return await self.client.get(
            "governance/breach-notifications/",
            params={"incident": incident_id, "page": page, "page_size": page_size},
        )

    async def send_notification(
        self,
        notification_id: str,
        outbound_reference: str,
    ) -> Dict[str, Any]:
        """Mark a breach notification as sent.

        Args:
            notification_id: UUID of the BreachNotification row.
            outbound_reference: External reference (e.g. DPA portal case ID).
        """
        return await self.client.post(
            f"governance/breach-notifications/{notification_id}/mark-sent/",
            data={"outbound_reference": outbound_reference},
        )

    # ── Dashboard / SLA ──────────────────────────────────────────────

    async def get_dashboard(self) -> Dict[str, Any]:
        """Get breach dashboard summary with SLA metrics.

        Returns ``{total, open, overdue, by_sla_level, approaching_deadline}``.
        Maps to ``GET governance/breach-dashboard/``.
        """
        return await self.client.get("governance/breach-dashboard/")

    async def get_sla_status(self, incident_id: str) -> Dict[str, Any]:
        """Get SLA compliance status for a breach incident.

        SLA data is derived from the incident detail + dashboard clock scan.
        Returns ``{sla_level, deadline, time_remaining, is_overdue}``.
        """
        incident = await self.get_incident(incident_id)
        return {
            "sla_level": incident.get("sla_level"),
            "deadline": incident.get("notification_deadline"),
            "status": incident.get("status"),
        }
