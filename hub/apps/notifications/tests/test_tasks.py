"""
Phase 86.4 — notifications/tasks.py tests.

Tests send_email_async, send_job_completion_email, send_job_failure_email.
"""
import uuid
from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase


class SendEmailAsyncTest(TestCase):
    """Tests for the core send_email_async function."""

    @patch("hub.apps.notifications.tasks.logger")
    @patch("hub.apps.notifications.tasks.EmailDelivery")
    @patch("hub.apps.notifications.tasks.render_email_template")
    @patch("hub.apps.notifications.tasks.get_email_service")
    @patch("hub.apps.notifications.tasks.NotificationsBusinessRules")
    def test_email_sent_successfully(
        self, mock_br, mock_get_svc, mock_render, mock_delivery, _log,
    ):
        mock_br_inst = MagicMock()
        mock_br_inst.validate.return_value = MagicMock(
            is_valid=True, errors=[], warnings=[],
        )
        mock_br.return_value = mock_br_inst
        mock_render.return_value = {"html": "<h1>Hi</h1>", "text": "Hi"}
        mock_svc = MagicMock()
        mock_svc.send_email.return_value = {"message_id": "msg-1"}
        mock_get_svc.return_value = mock_svc
        mock_del_obj = MagicMock(id=uuid.uuid4())
        mock_delivery.objects.create.return_value = mock_del_obj
        mock_delivery.objects.get_or_create.return_value = (
            mock_del_obj, True,
        )

        to_email = f"user-{uuid.uuid4().hex[:8]}@example.com"
        from hub.apps.notifications.tasks import send_email_async
        result = send_email_async(
            email_type="JOB_COMPLETION",
            to_email=to_email,
            subject="Job done",
            template_name="notifications/emails/job_completion.html",
            context={"user": "test"},
        )
        assert result["success"] is True
        # Verify template was rendered with correct template name
        mock_render.assert_called_once()
        render_args = mock_render.call_args
        self.assertIn("job_completion", render_args[0][0] if render_args[0] else render_args[1].get("template_name", ""))
        # Verify email service was called with rendered content
        mock_svc.send_email.assert_called_once()
        svc_kwargs = mock_svc.send_email.call_args[1] if mock_svc.send_email.call_args[1] else {}
        svc_args = mock_svc.send_email.call_args[0] if mock_svc.send_email.call_args[0] else ()
        # The to_email should appear in the call
        all_call_values = str(svc_kwargs) + str(svc_args)
        self.assertIn(to_email, all_call_values)
        # Verify delivery record was marked as sent
        mock_del_obj.mark_sent.assert_called_once_with(message_id="msg-1")

    @patch("hub.apps.notifications.tasks.logger")
    def test_empty_email_raises_valueerror(self, _log):
        from hub.apps.notifications.tasks import send_email_async
        with self.assertRaises(ValueError) as ctx:
            send_email_async(
                email_type="JOB_COMPLETION",
                to_email="",
                subject="X",
                template_name="x.html",
                context={},
            )
        assert "must be provided" in str(ctx.exception)

    @patch("hub.apps.notifications.tasks.logger")
    def test_email_without_at_raises_valueerror(self, _log):
        from hub.apps.notifications.tasks import send_email_async
        with self.assertRaises(ValueError) as ctx:
            send_email_async(
                email_type="JOB_COMPLETION",
                to_email="not-an-email",
                subject="X",
                template_name="x.html",
                context={},
            )
        assert "valid email" in str(ctx.exception)


@pytest.mark.django_db(transaction=True)
class SendJobEmailTest(TestCase):

    def _create_job(self, status="COMPLETED"):
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User, UserStatus
        from hub.apps.jobs.models import Job, JobType
        tenant = Tenant.objects.get_or_create(
            name="notif-test",
            defaults={"slug": "notif-test"},
        )[0]
        user = User.objects.get_or_create(
            email=f"notif-{uuid.uuid4().hex[:6]}@test.com",
            defaults={
                "tenant": tenant,
                "status": UserStatus.ACTIVE,
            },
        )[0]
        return Job.objects.create(
            tenant=tenant,
            type=JobType.DQ_RUN,
            status=status,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
            created_by=user,
        )

    @patch("hub.apps.notifications.tasks.logger")
    @patch("hub.apps.notifications.tasks.send_email_async")
    def test_completion_email_calls_send(self, mock_send, _log):
        mock_send.return_value = {
            "success": True, "delivery_id": "d1",
        }
        job = self._create_job("COMPLETED")
        from hub.apps.notifications.tasks import (
            send_job_completion_email,
        )
        send_job_completion_email(str(job.id))
        mock_send.assert_called_once()
        kw = mock_send.call_args[1]
        assert "job_completion" in kw["template_name"]
        self.assertEqual(kw["to_email"], job.created_by.email)
        self.assertEqual(kw["email_type"], "JOB_COMPLETION")
        self.assertIn("job", kw["context"])

    @patch("hub.apps.notifications.tasks.logger")
    @patch("hub.apps.notifications.tasks.send_email_async")
    def test_failure_email_calls_send(self, mock_send, _log):
        mock_send.return_value = {
            "success": True, "delivery_id": "d1",
        }
        job = self._create_job("FAILED")
        from hub.apps.notifications.tasks import (
            send_job_failure_email,
        )
        send_job_failure_email(str(job.id))
        mock_send.assert_called_once()
        kw = mock_send.call_args[1]
        assert "job_failure" in kw["template_name"]
        self.assertEqual(kw["to_email"], job.created_by.email)
        self.assertEqual(kw["email_type"], "JOB_FAILURE")
        self.assertIn("job", kw["context"])

# ── Phase 277.4.5 — mail.outbox assertions ─────────────────────────

class TestEmailDeliveryRealBackend(TestCase):
    """Phase 277.4.5 — send_email_async uses real DB + test email backend."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"EM-{uid}", slug=f"em-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"em-{uid}@meshant.test",
            password="testpass", tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_send_email_produces_correct_output(self):
        """send_email_async delivers correct subject/body/recipient."""
        from django.core import mail
        from hub.apps.notifications.tasks import send_email_async

        send_email_async(
            to_email=self.user.email,
            subject="Test Subject",
            body="Test body content.",
        )
        assert len(mail.outbox) == 1, f"Expected 1 email, got {len(mail.outbox)}"
        sent = mail.outbox[0]
        assert sent.subject == "Test Subject"
        assert "Test body content." in sent.body
        assert self.user.email in sent.to

    def test_send_email_handles_empty_body(self):
        """Empty body does not crash the task."""
        from django.core import mail
        from hub.apps.notifications.tasks import send_email_async

        send_email_async(
            to_email=self.user.email,
            subject="Empty",
            body="",
        )
        assert len(mail.outbox) >= 1
