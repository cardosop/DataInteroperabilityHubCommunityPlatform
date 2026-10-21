"""
W1.18 (oss-release-remediation) — ClamAV outage policy seam.

Single choke-point for "may this SCAN_UNAVAILABLE file proceed?" —
shared by the dataset-source gate (``hub.apps.datasets``) and the file
download view (``hub.apps.files``), so the policy cannot drift between
surfaces.

Policy decision (recorded in docs/runbooks/file-virus-scan-incident.md):
default ``allow`` (availability; SRE alerting on the
``FILE_MALWARE_SCAN_UNAVAILABLE`` audit + scan metrics) with ``block``
available for fail-closed deployments.
"""

from __future__ import annotations

import structlog
from django.conf import settings

from hub.apps.files.models import FileScanStatus

logger = structlog.get_logger(__name__)


def scan_unavailable_blocked(file_obj) -> bool:
    """
    True when the file is SCAN_UNAVAILABLE and the policy is ``block``.

    ``file_obj`` is a File (or File-shaped) instance with a
    ``scan_status`` attribute.
    """
    if file_obj.scan_status != FileScanStatus.SCAN_UNAVAILABLE:
        return False
    return getattr(settings, "SCAN_UNAVAILABLE_POLICY", "allow") == "block"


def audit_scan_unavailable_blocked(file_obj) -> None:
    """
    Emit ``FILE_SCAN_UNAVAILABLE_BLOCKED`` for a blocked file.

    Convention 8 (enforcement points emit audit events); audit-DB
    outages must never break the response — failures are logged only.
    """
    try:
        from hub.apps.audit import event_types
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="FILE",
            action=event_types.FILE_SCAN_UNAVAILABLE_BLOCKED,
            tenant=file_obj.tenant,
            resource_id=str(file_obj.id),
            result="FAILURE",
            details={
                "reason": "scan_unavailable_policy_block",
                "scan_status": FileScanStatus.SCAN_UNAVAILABLE,
            },
        )
    except Exception as exc:  # noqa: BLE001 — audit side-effect
        # isolation (Phase 273 contract: an audit-DB outage must never
        # block the response); pragma: no cover — outage path only.
        logger.warning(
            "scan_unavailable_blocked_audit_failed",
            file_id=str(getattr(file_obj, "id", None)),
            error=str(exc),
        )
