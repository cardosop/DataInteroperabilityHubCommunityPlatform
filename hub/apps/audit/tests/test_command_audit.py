"""P0-17 (W105-MGMT-COMMAND-AUDIT) — the AuditedCommand chokepoint.

Behavioral pins, no mocks: a REAL Command subclass inheriting the real
:class:`hub.apps.audit.command_audit.AuditedCommand` runs through the
real ``call_command`` path (Django's own execution machinery), and the
resulting rows are read back from the real ``AuditEvent`` table.

Contract pinned:
  * SUCCESS → one MANAGEMENT_COMMAND_EXECUTED row, system-scoped
    (tenant=NULL), identifiers-only details (command name + duration +
    option KEYS — never option values);
  * FAILURE → one MANAGEMENT_COMMAND_FAILED row AND the original
    exception still propagates (audit is a side channel, never a
    catch-and-swallow);
  * option VALUES never reach the audit row (commands take secrets).
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.test import TestCase

from hub.apps.audit.command_audit import AuditedCommand
from hub.apps.audit.event_types import (
    MANAGEMENT_COMMAND_EXECUTED,
    MANAGEMENT_COMMAND_FAILED,
    MANAGEMENT_COMMAND_RESOURCE_TYPE,
)
from hub.apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db(transaction=True)


class _ProbeCommand(AuditedCommand):
    help = "probe command for the audit chokepoint pins"

    def add_arguments(self, parser):
        parser.add_argument("--secret-option")

    def handle(self, *args, **options):
        # A command body that touches nothing — the chokepoint is what
        # is under test.
        return None


class _ExplodingCommand(AuditedCommand):
    help = "probe command whose handle raises"

    def handle(self, *args, **options):
        raise RuntimeError("probe explosion")


class AuditedCommandTest(TestCase):
    def test_success_emits_executed_row(self):
        call_command(_ProbeCommand(), secret_option="do-not-leak", verbosity=0)

        rows = list(
            AuditEvent.objects.filter(resource_type=MANAGEMENT_COMMAND_RESOURCE_TYPE)
        )
        assert len(rows) == 1
        row = rows[0]
        assert row.action == MANAGEMENT_COMMAND_EXECUTED
        assert row.result == "SUCCESS"
        assert row.tenant is None  # system-scoped: no request cycle exists
        assert row.details_json["command"].endswith("_ProbeCommand")
        assert "duration_ms" in row.details_json
        # identifiers only — the option VALUES never reach the row
        assert "do-not-leak" not in str(row.details_json)
        assert "secret_option" in row.details_json["options"]

    def test_failure_emits_failed_row_and_propagates(self):
        with pytest.raises(RuntimeError, match="probe explosion"):
            call_command(_ExplodingCommand(), verbosity=0)

        rows = list(
            AuditEvent.objects.filter(resource_type=MANAGEMENT_COMMAND_RESOURCE_TYPE)
        )
        assert len(rows) == 1
        assert rows[0].action == MANAGEMENT_COMMAND_FAILED
        assert rows[0].result == "FAILURE"
        assert rows[0].details_json["command"].endswith("_ExplodingCommand")
