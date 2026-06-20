"""Tests for API-key rotation reminder & expiry notification sweep (277.B.069)."""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.auth.management.commands.api_key_rotation_reminder import (
    _resolve_recipient,
    run_api_key_rotation_reminder_scan,
)
from hub.apps.auth.models import APIKey
from hub.apps.jobs.models import Job, JobType
from hub.apps.notifications.models import EmailType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ResolveRecipientTest(TestCase):
    """Unit tests for recipient resolution."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Recipient Tenant {uid}",
            slug=f"recipient-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"recipient-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def _make_key(self, **kwargs):
        kwargs.setdefault("tenant", self.tenant)
        kwargs.setdefault("user", self.user)
        kwargs.setdefault("key_hash", APIKey.hash_key(APIKey.generate_key()))
        kwargs.setdefault("name", f"test-key-{uuid.uuid4().hex[:6]}")
        return APIKey.objects.create(**kwargs)

    @pytest.mark.integration
    def test_uses_customer_email_when_set(self):
        api_key = self._make_key(customer_email="billing@customer.com")
        self.assertEqual(_resolve_recipient(api_key), "billing@customer.com")

    @pytest.mark.integration
    def test_falls_back_to_user_email(self):
        api_key = self._make_key()
        self.assertEqual(_resolve_recipient(api_key), self.user.email)

    @pytest.mark.integration
    def test_returns_none_when_no_email_available(self):
        api_key = self._make_key(user=None)
        self.assertIsNone(_resolve_recipient(api_key))


class RotationReminderScanTest(TestCase):
    """Integration tests for run_api_key_rotation_reminder_scan()."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Scan Tenant {uid}",
            slug=f"scan-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"scan-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def _make_key(self, **kwargs):
        kwargs.setdefault("tenant", self.tenant)
        kwargs.setdefault("user", self.user)
        kwargs.setdefault("key_hash", APIKey.hash_key(APIKey.generate_key()))
        kwargs.setdefault("name", f"test-key-{uuid.uuid4().hex[:6]}")
        return APIKey.objects.create(**kwargs)

    @pytest.mark.integration
    def test_scans_only_active_keys_with_expires_at(self):
        """Irrelevant keys (revoked, no expiry) are ignored."""
        now = timezone.now()
        # Active key with expiry within the widest threshold — should be scanned
        # and receive a reminder (30d threshold, the default widest).
        active = self._make_key(expires_at=now + timedelta(days=30))
        # Revoked
        self._make_key(expires_at=now + timedelta(days=60), revoked_at=now)
        # No expiry
        self._make_key(expires_at=None)

        counters = run_api_key_rotation_reminder_scan(now=now)
        self.assertEqual(counters["scanned"], 1)
        self.assertEqual(
            APIKey.objects.get(pk=active.pk).last_rotation_reminder_at.date(),
            now.date(),
        )

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[30, 14, 7, 1])
    @pytest.mark.integration
    def test_sends_30_day_reminder(self):
        now = timezone.now()
        self._make_key(expires_at=now + timedelta(days=30))

        with patch("hub.apps.notifications.tasks.send_email_async") as mock_send:
            counters = run_api_key_rotation_reminder_scan(now=now)

        self.assertEqual(counters["reminder_30d"], 1)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["email_type"], EmailType.API_KEY_EXPIRING)
        self.assertIn("30 day", call_kwargs["subject"])

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[30, 14, 7, 1])
    @pytest.mark.integration
    def test_sends_14_day_reminder_after_30_day_already_sent(self):
        now = timezone.now()
        api_key = self._make_key(expires_at=now + timedelta(days=60))

        # First scan: send 30d reminder (at 60 days out, 60 > 30 so nothing)
        # Actually at 60 days remaining, no threshold applies
        counters1 = run_api_key_rotation_reminder_scan(now=now)
        self.assertEqual(counters1["scanned"], 1)
        # No reminder — 60 > 30
        api_key.refresh_from_db()
        self.assertIsNone(api_key.last_rotation_reminder_at)

        # Advance to 25 days remaining — 30d threshold
        now2 = now + timedelta(days=35)
        counters2 = run_api_key_rotation_reminder_scan(now=now2)
        self.assertEqual(counters2["reminder_30d"], 1)
        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.last_rotation_reminder_at)

        # Advance to 14 days remaining — 14d threshold
        now3 = now + timedelta(days=46)
        with patch("hub.apps.notifications.tasks.send_email_async") as mock_send:
            counters3 = run_api_key_rotation_reminder_scan(now=now3)
        self.assertEqual(counters3["reminder_14d"], 1)
        mock_send.assert_called_once()
        self.assertIn("14 day", mock_send.call_args.kwargs["subject"])

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[30, 14, 7, 1])
    @pytest.mark.integration
    def test_idempotent_within_same_threshold_window(self):
        """A second scan on the same day does NOT re-send the same threshold."""
        now = timezone.now()
        self._make_key(expires_at=now + timedelta(days=7))

        counters1 = run_api_key_rotation_reminder_scan(now=now)
        self.assertEqual(counters1["reminder_7d"], 1)

        # Same day, second scan
        counters2 = run_api_key_rotation_reminder_scan(now=now)
        self.assertEqual(counters2["reminder_7d"], 0)

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[30, 14, 7, 1])
    @pytest.mark.integration
    def test_sends_most_urgent_threshold_when_multiple_apply(self):
        """When a key has 3 days remaining, send 7d (not 14d or 30d)."""
        now = timezone.now()
        self._make_key(expires_at=now + timedelta(days=3))

        with patch("hub.apps.notifications.tasks.send_email_async") as mock_send:
            counters = run_api_key_rotation_reminder_scan(now=now)

        self.assertEqual(counters["reminder_7d"], 1)
        self.assertEqual(counters["reminder_30d"], 0)
        # Subject includes the actual days_remaining (3), not the threshold label.
        self.assertIn("3 day", mock_send.call_args.kwargs["subject"])

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[30, 14, 7, 1])
    @pytest.mark.integration
    def test_sends_expired_notification(self):
        now = timezone.now()
        self._make_key(expires_at=now - timedelta(days=1))

        with patch("hub.apps.notifications.tasks.send_email_async") as mock_send:
            counters = run_api_key_rotation_reminder_scan(now=now)

        self.assertEqual(counters["expired"], 1)
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["email_type"], EmailType.API_KEY_EXPIRED)

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[30, 14, 7, 1])
    @pytest.mark.integration
    def test_expired_notification_sent_only_once(self):
        now = timezone.now()
        self._make_key(expires_at=now - timedelta(days=1))

        counters1 = run_api_key_rotation_reminder_scan(now=now)
        self.assertEqual(counters1["expired"], 1)

        counters2 = run_api_key_rotation_reminder_scan(now=now)
        self.assertEqual(counters2["expired"], 0)
        self.assertGreaterEqual(counters2["already_reminded"], 1)

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[30, 14, 7, 1])
    @pytest.mark.integration
    def test_key_without_recipient_still_updates_reminder_timestamp(self):
        """Keys without a recipient should still mark as reminded to avoid
        repeated DB writes on every scan."""
        now = timezone.now()
        api_key = self._make_key(
            expires_at=now + timedelta(days=14),
            user=None,
            customer_email=None,
        )

        counters = run_api_key_rotation_reminder_scan(now=now)
        self.assertEqual(counters["no_recipient"], 1)
        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.last_rotation_reminder_at)

        # Second scan: already reminded
        counters2 = run_api_key_rotation_reminder_scan(now=now)
        self.assertEqual(counters2["no_recipient"], 0)

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[30, 14, 7, 1])
    @pytest.mark.integration
    def test_cascading_reminders_across_thresholds(self):
        """Key receives 30d, 14d, 7d, and 1d reminders as time passes."""
        now = timezone.now()
        self._make_key(expires_at=now + timedelta(days=30))

        # Day 0 (30 days out): exactly at the 30d window
        counters = run_api_key_rotation_reminder_scan(now=now)
        self.assertEqual(counters["reminder_30d"], 1)

        # Advance to 14 days
        now14 = now + timedelta(days=16)
        counters14 = run_api_key_rotation_reminder_scan(now=now14)
        self.assertEqual(counters14["reminder_14d"], 1)

        # Advance to 7 days
        now7 = now + timedelta(days=23)
        counters7 = run_api_key_rotation_reminder_scan(now=now7)
        self.assertEqual(counters7["reminder_7d"], 1)

        # Advance to 1 day
        now1 = now + timedelta(days=29)
        counters1 = run_api_key_rotation_reminder_scan(now=now1)
        self.assertEqual(counters1["reminder_1d"], 1)

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[])
    @pytest.mark.integration
    def test_empty_thresholds_skips_all(self):
        now = timezone.now()
        self._make_key(expires_at=now + timedelta(days=10))

        counters = run_api_key_rotation_reminder_scan(now=now)
        self.assertIn("skipped (no thresholds configured)", counters)

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[14, 7])
    @pytest.mark.integration
    def test_custom_thresholds_respected(self):
        now = timezone.now()
        self._make_key(expires_at=now + timedelta(days=30))

        counters = run_api_key_rotation_reminder_scan(now=now)
        # 30 days remaining is > 14, so no reminder
        self.assertEqual(counters.get("reminder_14d", 0), 0)

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[30, 14, 7, 1])
    @pytest.mark.integration
    def test_send_email_async_failure_does_not_abort_sweep(self):
        """A single email failure must not prevent other keys from being processed."""
        now = timezone.now()
        key_a = self._make_key(expires_at=now + timedelta(days=14))
        key_b = self._make_key(expires_at=now + timedelta(days=14))

        call_count = [0]

        def failing_send(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("SMTP down")
            # Second call succeeds

        with patch(
            "hub.apps.notifications.tasks.send_email_async",
            side_effect=failing_send,
        ):
            run_api_key_rotation_reminder_scan(now=now)

        # Both keys should be marked as reminded
        key_a.refresh_from_db()
        key_b.refresh_from_db()
        self.assertIsNotNone(key_a.last_rotation_reminder_at)
        self.assertIsNotNone(key_b.last_rotation_reminder_at)


class ManagementCommandTest(TestCase):
    """Tests for the api_key_rotation_reminder management command."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"MgmtCmd Tenant {uid}",
            slug=f"mgmtcmd-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"mgmtcmd-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_command_creates_job_row_by_default(self):
        with patch(
            "hub.apps.auth.management.commands.api_key_rotation_reminder.run_api_key_rotation_reminder_scan",
            return_value={"scanned": 0},
        ):
            call_command("api_key_rotation_reminder")

        job = Job.objects.filter(type=JobType.API_KEY_ROTATION_REMINDER).latest("created_at")
        self.assertIsNotNone(job)

    @pytest.mark.integration
    def test_command_skip_job_row(self):
        before = Job.objects.filter(type=JobType.API_KEY_ROTATION_REMINDER).count()

        with patch(
            "hub.apps.auth.management.commands.api_key_rotation_reminder.run_api_key_rotation_reminder_scan",
            return_value={"scanned": 0},
        ):
            call_command("api_key_rotation_reminder", "--skip-job-row")

        after = Job.objects.filter(type=JobType.API_KEY_ROTATION_REMINDER).count()
        self.assertEqual(before, after)

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[30, 14, 7, 1])
    @pytest.mark.integration
    def test_command_output_includes_counters(self):
        from io import StringIO

        buf = StringIO()
        with patch(
            "hub.apps.auth.management.commands.api_key_rotation_reminder.run_api_key_rotation_reminder_scan",
            return_value={"scanned": 5, "reminder_30d": 2},
        ):
            call_command("api_key_rotation_reminder", "--skip-job-row", stdout=buf)

        output = buf.getvalue()
        self.assertIn("scanned", output)
        self.assertIn("reminder_30d", output)

    @override_settings(API_KEY_ROTATION_REMINDER_DAYS=[30, 14, 7, 1])
    @pytest.mark.integration
    def test_command_marks_job_failed_on_exception(self):
        Job.objects.filter(type=JobType.API_KEY_ROTATION_REMINDER).count()

        with patch(
            "hub.apps.auth.management.commands.api_key_rotation_reminder.run_api_key_rotation_reminder_scan",
            side_effect=RuntimeError("DB connection lost"),
        ):
            with self.assertRaises(RuntimeError):
                call_command("api_key_rotation_reminder")

        job = Job.objects.filter(type=JobType.API_KEY_ROTATION_REMINDER).latest("created_at")
        self.assertEqual(job.status, "FAILED")
        self.assertIn("DB connection lost", job.error_message or "")
