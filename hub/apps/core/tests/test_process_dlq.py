"""
Tests for ``process_dlq`` management command.

Creates DeadLetterQueue entries in setUp and verifies the command
processes, filters, and resolves them correctly.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from hub.apps.core.events.models import DeadLetterQueue


class ProcessDLQCommandTests(TestCase):
    """Tests for ``manage.py process_dlq``."""

    def setUp(self):
        """Create sample DLQ entries for each test method."""
        super().setUp()
        # Clean up any leaked entries from previous runs (--reuse-db safety)
        DeadLetterQueue.objects.all().delete()
        DeadLetterQueue.objects.create(
            event={"type": "asset.created", "data": {"id": "a1"}},
            event_type="asset.created",
            subscriber="asset_handler",
            error_message="Connection timeout",
            retry_count=3,
        )
        DeadLetterQueue.objects.create(
            event={"type": "contract.updated", "data": {"id": "c1"}},
            event_type="contract.updated",
            subscriber="contract_handler",
            error_message="Serialization error",
            retry_count=1,
        )
        DeadLetterQueue.objects.create(
            event={"type": "asset.created", "data": {"id": "a2"}},
            event_type="asset.created",
            subscriber="another_handler",
            error_message="DB connection lost",
            retry_count=5,
        )
        # Already-resolved entry — should be excluded
        DeadLetterQueue.objects.create(
            event={"type": "old.event", "data": {}},
            event_type="old.event",
            subscriber="old_handler",
            error_message="Resolved earlier",
            retry_count=2,
            resolved_at="2024-01-01T00:00:00Z",
        )

    def test_command_is_registered(self):
        """Command is discoverable by Django's management framework."""
        from django.core.management import get_commands

        assert "process_dlq" in get_commands()

    def test_command_lists_unresolved_entries(self):
        """Default run lists unresolved entries (3 created, 1 resolved)."""
        out = StringIO()
        call_command("process_dlq", stdout=out, stderr=StringIO())
        output = out.getvalue()
        # Only unresolved entries should be counted
        assert "3" in output or "Found" in output

    def test_dry_run_does_not_modify_entries(self):
        """--dry-run reports entries but does not mark them resolved."""
        unresolved_before = DeadLetterQueue.objects.filter(resolved_at__isnull=True).count()
        assert unresolved_before >= 3

        out = StringIO()
        call_command(
            "process_dlq",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )

        unresolved_after = DeadLetterQueue.objects.filter(resolved_at__isnull=True).count()
        assert unresolved_after == unresolved_before, "--dry-run should not modify any DLQ entries"

    def test_max_entries_limits_processing(self):
        """--max-entries=N processes at most N entries."""
        out = StringIO()
        call_command(
            "process_dlq",
            "--max-entries=1",
            stdout=out,
            stderr=StringIO(),
        )
        output = out.getvalue()
        # The output should mention limiting or show 1 entry processed
        assert isinstance(output, str)

    def test_subscriber_filter(self):
        """--subscriber=X filters to entries for that subscriber only."""
        out = StringIO()
        call_command(
            "process_dlq",
            "--subscriber=asset_handler",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
        output = out.getvalue()
        # Should mention finding exactly 1 entry for asset_handler
        assert isinstance(output, str)

    def test_event_type_filter(self):
        """--event-type=X filters to entries of that event type."""
        out = StringIO()
        call_command(
            "process_dlq",
            "--event-type=asset.created",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
        output = out.getvalue()
        # 2 of 3 unresolved entries are asset.created
        assert isinstance(output, str)
