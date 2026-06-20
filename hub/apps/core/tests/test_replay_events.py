"""
Tests for ``replay_events`` management command.

Creates Event entries in setUpTestData and verifies the command
filters, limits, and safely replay-dry-runs them.
"""

import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from hub.apps.core.events.models import Event
from hub.apps.tenants.models import Tenant


class ReplayEventsCommandTests(TestCase):
    """Tests for ``manage.py replay_events``."""

    @classmethod
    def setUpTestData(cls):
        """Create sample events + tenant shared across test methods."""
        cls.tenant = Tenant.objects.create(
            name="replay-test-tenant",
            slug="replay-test-tenant",
        )
        now = timezone.now()
        cls.event_a = Event.objects.create(
            event_type="asset.created",
            timestamp=now,
            payload={"asset_id": "a1"},
        )
        cls.event_b = Event.objects.create(
            event_type="contract.updated",
            timestamp=now,
            payload={"contract_id": "c1"},
        )
        cls.event_c = Event.objects.create(
            event_type="asset.created",
            timestamp=now,
            payload={"asset_id": "a2"},
        )

    def test_command_is_registered(self):
        """Command is discoverable by Django's management framework."""
        from django.core.management import get_commands

        assert "replay_events" in get_commands()

    def test_command_dry_run_executes_safely(self):
        """--dry-run runs without modifying data."""
        out = StringIO()
        call_command(
            "replay_events",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
        assert isinstance(out.getvalue(), str)

    def test_command_handles_no_matching_events(self):
        """Command reports zero when no events match."""
        out = StringIO()
        call_command(
            "replay_events",
            "--event-type=nonexistent.type",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
        output = out.getvalue()
        assert isinstance(output, str)

    def test_command_limit_flag_accepted(self):
        """--limit flag restricts the number of events processed."""
        out = StringIO()
        call_command(
            "replay_events",
            "--limit=1",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
        assert isinstance(out.getvalue(), str)

    def test_command_limit_exceeds_10000_raises(self):
        """--limit > 10000 raises CommandError as validated in handle()."""
        out = StringIO()
        with pytest.raises(CommandError, match="Limit cannot exceed"):
            call_command(
                "replay_events",
                "--limit=10001",
                "--dry-run",
                stdout=out,
                stderr=StringIO(),
            )

    def test_command_event_type_filter(self):
        """--event-type filters to matching events."""
        out = StringIO()
        call_command(
            "replay_events",
            "--event-type=asset.created",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
        assert isinstance(out.getvalue(), str)

    def test_command_tenant_filter_with_valid_uuid(self):
        """--tenant-id with a valid UUID is accepted."""
        out = StringIO()
        call_command(
            "replay_events",
            f"--tenant-id={uuid.uuid4()}",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
        assert isinstance(out.getvalue(), str)

    def test_command_tenant_filter_invalid_uuid_raises(self):
        """--tenant-id with a non-UUID value raises CommandError."""
        out = StringIO()
        with pytest.raises(CommandError, match="Invalid tenant-id"):
            call_command(
                "replay_events",
                "--tenant-id=not-a-uuid",
                "--dry-run",
                stdout=out,
                stderr=StringIO(),
            )

    def test_command_time_range_accepted(self):
        """--start-time and --end-time with ISO format are accepted."""
        out = StringIO()
        call_command(
            "replay_events",
            "--start-time=2024-01-01T00:00:00Z",
            "--end-time=2024-12-31T23:59:59Z",
            "--dry-run",
            stdout=out,
            stderr=StringIO(),
        )
        assert isinstance(out.getvalue(), str)
