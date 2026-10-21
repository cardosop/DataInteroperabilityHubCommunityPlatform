"""
Phase 80.5 — Notifications signal tests.

Tests that the Job post_save signal triggers email notifications
on terminal status changes (COMPLETED/FAILED).

Callbacks are deferred via transaction.on_commit, so tests use
captureOnCommitCallbacks to flush them within TestCase.
"""

import uuid
import weakref
from unittest.mock import MagicMock, patch

import pytest
from django.db.models.signals import post_save
from django.test import TestCase, override_settings

from hub.apps.jobs.models import Job, JobStatus


@pytest.mark.django_db(transaction=True)
class NotificationsSignalTest(TestCase):
    """Tests for job_status_changed signal."""

    def test_signal_connected_to_post_save(self):
        """Signal handler is connected to Job post_save."""
        from hub.apps.notifications.signals import job_status_changed

        receivers = []
        for r in post_save.receivers:
            ref = r[1]
            if isinstance(ref, weakref.ref):
                func = ref()
                if func is not None:
                    receivers.append(func)
            else:
                receivers.append(ref)
        assert job_status_changed in receivers

    @patch("hub.apps.notifications.signals.send_job_completion_email")
    @patch("hub.apps.notifications.signals.send_job_failure_email")
    def test_created_job_skipped(self, mock_failure, mock_completion):
        """Signal does nothing when Job is created (not updated)."""
        from hub.apps.notifications.signals import job_status_changed

        instance = MagicMock(spec=Job)
        instance.status = JobStatus.COMPLETED
        instance.created_by = MagicMock()
        with self.captureOnCommitCallbacks(execute=True):
            job_status_changed(sender=Job, instance=instance, created=True)
        mock_completion.delay.assert_not_called()
        mock_failure.delay.assert_not_called()

    @override_settings(EMAIL_JOB_NOTIFICATIONS_ENABLED=False)
    @patch("hub.apps.notifications.signals.send_job_completion_email")
    def test_disabled_notifications_skipped(self, mock_completion):
        """Signal does nothing when EMAIL_JOB_NOTIFICATIONS_ENABLED=False."""
        from hub.apps.notifications.signals import job_status_changed

        instance = MagicMock(spec=Job)
        instance.status = JobStatus.COMPLETED
        instance.created_by = MagicMock()
        with self.captureOnCommitCallbacks(execute=True):
            job_status_changed(sender=Job, instance=instance, created=False)
        mock_completion.delay.assert_not_called()

    @override_settings(EMAIL_JOB_NOTIFICATIONS_ENABLED=True)
    @patch("hub.apps.notifications.signals.send_job_completion_email")
    def test_completed_job_sends_completion_email(self, mock_completion):
        """COMPLETED status triggers send_job_completion_email."""
        from hub.apps.notifications.signals import job_status_changed

        instance = MagicMock(spec=Job)
        instance.status = JobStatus.COMPLETED
        instance.created_by = MagicMock()
        instance.id = uuid.uuid4()
        with self.captureOnCommitCallbacks(execute=True):
            job_status_changed(sender=Job, instance=instance, created=False)
        mock_completion.delay.assert_called_once_with(str(instance.id))

    @override_settings(EMAIL_JOB_NOTIFICATIONS_ENABLED=True)
    @patch("hub.apps.notifications.signals.send_job_failure_email")
    def test_failed_job_sends_failure_email(self, mock_failure):
        """FAILED status triggers send_job_failure_email."""
        from hub.apps.notifications.signals import job_status_changed

        instance = MagicMock(spec=Job)
        instance.status = JobStatus.FAILED
        instance.created_by = MagicMock()
        instance.id = uuid.uuid4()
        with self.captureOnCommitCallbacks(execute=True):
            job_status_changed(sender=Job, instance=instance, created=False)
        mock_failure.delay.assert_called_once_with(str(instance.id))

    @override_settings(EMAIL_JOB_NOTIFICATIONS_ENABLED=True)
    @patch("hub.apps.notifications.signals.send_job_completion_email")
    def test_no_created_by_skips_notification(self, mock_completion):
        """No notification when job has no created_by user."""
        from hub.apps.notifications.signals import job_status_changed

        instance = MagicMock(spec=Job)
        instance.status = JobStatus.COMPLETED
        instance.created_by = None
        with self.captureOnCommitCallbacks(execute=True):
            job_status_changed(sender=Job, instance=instance, created=False)
        mock_completion.delay.assert_not_called()
