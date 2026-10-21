"""P0-17 (W105-MGMT-COMMAND-AUDIT) — the management-command audit chokepoint.

Cross-tenant management commands are the one execution surface with no
request cycle to arm the RLS context; the CLAUDE.md contract requires
them audited. Instead of sprinkling per-command audit calls (the
databricks-lane style works for lifecycle-rich surfaces but 100+
commands would drift), every cross-tenant command inherits
:class:`AuditedCommand`: ``execute()`` wraps the run, times it, and
emits one ``MANAGEMENT_COMMAND_EXECUTED`` / ``MANAGEMENT_COMMAND_FAILED``
row per invocation.

Emission is best-effort try/except wrapped (the Phase 273 audit-DB
contract: an audit outage must never block the command) and carries
IDENTIFIERS ONLY — the command name, result, duration and the option
KEYS. Option VALUES never reach the audit row (commands take secrets
as options: ``--api-key``, ``--token``, connection strings).

The gate ``scripts/check_mgmt_command_audit.py`` enforces coverage:
every command inherits this base (or calls :func:`emit_command_audit`
/ ``create_audit_event`` directly) or is read-only allowlisted.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from django.core.management.base import BaseCommand

from hub.apps.audit.event_types import (
    MANAGEMENT_COMMAND_EXECUTED,
    MANAGEMENT_COMMAND_FAILED,
    MANAGEMENT_COMMAND_RESOURCE_TYPE,
)

logger = logging.getLogger(__name__)


def emit_command_audit(
    command_name: str,
    result: str,
    *,
    duration_ms: int,
    option_keys: list[str],
) -> None:
    """Emit one system-scoped MANAGEMENT_COMMAND audit row (never raises)."""
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type=MANAGEMENT_COMMAND_RESOURCE_TYPE,
            action=MANAGEMENT_COMMAND_EXECUTED if result == "SUCCESS" else MANAGEMENT_COMMAND_FAILED,
            tenant=None,
            result=result,
            details={
                "command": command_name,
                "duration_ms": duration_ms,
                "options": option_keys,
            },
            infer_tenant_from_actor=False,
        )
    except Exception:
        # Audit-DB outage must never block the command (Phase 273).
        logger.exception("management_command_audit_emit_failed command=%s", command_name)


class AuditedCommand(BaseCommand):
    """BaseCommand whose every invocation emits a MANAGEMENT_COMMAND row.

    Subclasses override ``handle()`` as usual. ``execute()`` must not be
    overridden without calling :func:`emit_command_audit` (the coverage
    gate accepts either evidence).
    """

    def execute(self, *args: Any, **options: Any) -> Any:
        command_name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        started = time.monotonic()
        try:
            result = super().execute(*args, **options)
        except BaseException:
            emit_command_audit(
                command_name,
                "FAILURE",
                duration_ms=int((time.monotonic() - started) * 1000),
                option_keys=sorted(options.keys()),
            )
            raise
        emit_command_audit(
            command_name,
            "SUCCESS",
            duration_ms=int((time.monotonic() - started) * 1000),
            option_keys=sorted(options.keys()),
        )
        return result
