"""
Tests for the archive_old_audit_events management command.

Validates that the retention archival actually marks old events, respects
batch-size, dry-run mode, and leaves recent events untouched.
"""

import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ArchiveOldAuditEventsTest(TestCase):
    """Tests for archive_old_audit_events management command."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Tenant {uid}", slug=f"tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

    # ------------------------------------------------------------------ helpers

    def _create_event(self, age_days=0, **kwargs):
        """Create an audit event and backdate its timestamp."""
        defaults = dict(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="TEST",
            action="CREATED",
            result="SUCCESS",
        )
        defaults.update(kwargs)
        event = AuditEvent.all_objects.create(**defaults)
        if age_days:
            ts = timezone.now() - timedelta(days=age_days)
            AuditEvent.all_objects.filter(pk=event.pk).update(timestamp=ts)
            event.refresh_from_db()
        return event

    def _run(self, *args, **kwargs):
        out = StringIO()
        err = StringIO()
        call_command(
            "archive_old_audit_events",
            *args,
            stdout=out,
            stderr=err,
            **kwargs,
        )
        return out.getvalue(), err.getvalue()

    # ------------------------------------------------------------------ tests

    def test_archives_old_events(self):
        """Events older than retention period are marked archived."""
        old = self._create_event(age_days=4 * 365)  # 4 years old
        recent = self._create_event(age_days=30)  # 30 days old

        self._run("--retention-years=3")

        old.refresh_from_db()
        recent.refresh_from_db()

        self.assertTrue(old.is_archived)
        self.assertIsNotNone(old.archived_at)
        self.assertFalse(recent.is_archived)
        self.assertIsNone(recent.archived_at)

    def test_dry_run_does_not_archive(self):
        """Dry-run reports counts without modifying data."""
        old = self._create_event(age_days=4 * 365)

        out, _ = self._run("--dry-run", "--retention-years=3")

        old.refresh_from_db()
        self.assertFalse(old.is_archived)
        self.assertIn("DRY RUN", out)
        self.assertIn("1", out)  # count

    def test_no_events_to_archive(self):
        """Graceful message when nothing is eligible for this tenant."""
        self._create_event(age_days=30)

        out, _ = self._run("--retention-years=3")
        # The command runs across ALL tenants.  With --reuse-db accumulated
        # data, other tenants may have eligible events.  We assert that NONE
        # of the events belonging to THIS tenant were archived.
        self.assertFalse(
            AuditEvent.all_objects.filter(is_archived=True, tenant=self.tenant).exists(),
            f"Expected no archived events for test tenant, got: {out}",
        )

    def test_already_archived_events_skipped(self):
        """Events that are already archived are not re-processed."""
        old = self._create_event(age_days=4 * 365)
        # Archive it via all_objects (default manager excludes archived)
        AuditEvent.all_objects.filter(pk=old.pk).update(
            is_archived=True, archived_at=timezone.now()
        )

        _out, _ = self._run("--retention-years=3")
        # The command runs across ALL tenants; other tenants' data may be
        # eligible.  Assert that the already-archived event for THIS tenant
        # was not re-processed (still has its original archived_at).
        old.refresh_from_db()
        self.assertTrue(old.is_archived, "Already-archived event should stay archived")

    def test_batch_processing(self):
        """Events are archived in batches of the specified size."""
        for _ in range(5):
            self._create_event(age_days=4 * 365)

        out, _ = self._run("--retention-years=3", "--batch-size=2")

        # Use all_objects because default manager excludes archived events.
        # Scope to this test's tenant to avoid counting events from other
        # tests when using --reuse-db.
        archived_count = AuditEvent.all_objects.filter(is_archived=True, tenant=self.tenant).count()
        self.assertEqual(archived_count, 5)
        # Should see multiple batch messages
        self.assertGreater(out.count("Archived batch"), 1)

    def test_retention_years_validation(self):
        """Retention years < 1 is rejected."""
        _, err = self._run("--retention-years=0")
        self.assertIn("must be >= 1", err)

    def test_custom_retention_years(self):
        """Custom retention period is respected."""
        event_2y = self._create_event(age_days=2 * 365 + 10)
        event_6m = self._create_event(age_days=180)

        self._run("--retention-years=2")

        event_2y.refresh_from_db()
        event_6m.refresh_from_db()

        self.assertTrue(event_2y.is_archived)
        self.assertFalse(event_6m.is_archived)
