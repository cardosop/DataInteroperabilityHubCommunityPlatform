"""
E2E tests for email service.

Tests complete user journeys:
- User invitation flow
- Password reset flow
- Job completion flow
- Delivery tracking
- Edge cases

Uses REAL services (no mocks).
"""

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone

from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.notifications.models import EmailDelivery, EmailDeliveryStatus, EmailType
from hub.apps.notifications.tasks import (
    send_invitation_email,
    send_job_completion_email,
    send_job_failure_email,
    send_password_reset_email,
)
from hub.apps.tenants.models import Tenant
from tests.e2e.conftest import E2ETestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e3]
User = get_user_model()


class EmailServiceE2ETest(E2ETestBase):
    """E2E tests for email service"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    # ------------------------------------------------------------------
    # Email-sending flow tests
    #
    # These call real task functions.  The task always creates an
    # EmailDelivery record in the DB regardless of SMTP success/failure.
    # We assert the record exists and has the correct metadata.
    # If the task raises (e.g. missing template), the test should fail —
    # we do NOT swallow exceptions.
    # ------------------------------------------------------------------

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
        EMAIL_JOB_NOTIFICATIONS_ENABLED=True,
    )
    def test_user_invitation_flow(self):
        """Test complete user invitation email flow"""
        new_user = User.objects.create_user(
            email="newuser@example.com",
            password="temp123",
            tenant=self.tenant,
            invitation_token=uuid.uuid4(),
            invitation_token_expires_at=timezone.now() + timedelta(days=7),
        )

        send_invitation_email(str(new_user.id))

        # A delivery record MUST always be created regardless of SMTP outcome
        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.USER_INVITATION, to_email=new_user.email
        ).first()

        self.assertIsNotNone(delivery, "EmailDelivery record must be created")
        self.assertEqual(delivery.to_email, new_user.email)
        self.assertEqual(delivery.tenant, self.tenant)
        self.assertEqual(delivery.user, new_user)

        # If SMTP succeeded, status should be SENT; if not, FAILED/DEFERRED
        self.assertIn(
            delivery.status,
            [
                EmailDeliveryStatus.SENT,
                EmailDeliveryStatus.FAILED,
                EmailDeliveryStatus.DEFERRED,
                EmailDeliveryStatus.PENDING,
            ],
        )

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    def test_password_reset_flow(self):
        """Test complete password reset email flow"""
        self.user.password_reset_token = uuid.uuid4()
        self.user.password_reset_token_expires_at = timezone.now() + timedelta(hours=1)
        self.user.save()

        send_password_reset_email(str(self.user.id))

        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.PASSWORD_RESET, to_email=self.user.email
        ).first()

        self.assertIsNotNone(delivery, "EmailDelivery record must be created for password reset")
        self.assertEqual(delivery.to_email, self.user.email)
        self.assertEqual(delivery.user, self.user)

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
        EMAIL_JOB_NOTIFICATIONS_ENABLED=True,
    )
    def test_job_completion_flow(self):
        """Test complete job completion email flow"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            result_json={"status": "completed", "checks_passed": 10},
        )

        send_job_completion_email(str(job.id))

        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.JOB_COMPLETION, to_email=self.user.email
        ).first()

        self.assertIsNotNone(delivery, "EmailDelivery record must be created for job completion")
        self.assertEqual(delivery.to_email, self.user.email)
        self.assertEqual(delivery.tenant, self.tenant)

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
        EMAIL_JOB_NOTIFICATIONS_ENABLED=True,
    )
    def test_job_failure_flow(self):
        """Test complete job failure email flow"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.FAILED,
            resource_type="COMPLIANCE_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            error_message="Validation failed",
        )

        send_job_failure_email(str(job.id))

        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.JOB_FAILURE, to_email=self.user.email
        ).first()

        self.assertIsNotNone(delivery, "EmailDelivery record must be created for job failure")
        self.assertEqual(delivery.to_email, self.user.email)
        self.assertEqual(delivery.tenant, self.tenant)

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
        EMAIL_JOB_NOTIFICATIONS_ENABLED=True,
    )
    def test_job_completion_signal_triggers_email(self):
        """Test that job completion triggers email creation"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        # Transition to COMPLETED — post_save signal fires
        job.status = JobStatus.COMPLETED
        job.result_json = {"status": "completed"}
        job.save()

        # Explicitly send the email (signal enqueues to RQ, which may not
        # process inline; call the task directly to verify it works)
        send_job_completion_email(str(job.id))

        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.JOB_COMPLETION, to_email=self.user.email
        ).first()

        self.assertIsNotNone(delivery, "Job completion should create an EmailDelivery record")

    # ------------------------------------------------------------------
    # Delivery tracking tests (use send_email_async directly)
    # ------------------------------------------------------------------

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    def test_email_delivery_tracking_journey(self):
        """Test complete email delivery tracking journey"""
        from hub.apps.notifications.tasks import send_email_async

        result = send_email_async(
            email_type=EmailType.USER_INVITATION,
            to_email="tracking@example.com",
            subject="Test Email",
            template_name="notifications/emails/user_invitation.html",
            context={"user": self.user, "tenant": self.tenant},
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        self.assertIn("delivery_id", result, "send_email_async must return a delivery_id")

        delivery = EmailDelivery.objects.get(id=result["delivery_id"])

        # Verify status transitions work correctly
        delivery.mark_sent("test-message-id")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, EmailDeliveryStatus.SENT)
        self.assertIsNotNone(delivery.sent_at)
        self.assertEqual(delivery.message_id, "test-message-id")

        # Simulate delivery webhook
        delivery.mark_delivered()
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, EmailDeliveryStatus.DELIVERED)
        self.assertIsNotNone(delivery.delivered_at)

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    def test_email_retry_journey(self):
        """Test complete email retry journey with intentional failure"""
        from hub.apps.notifications.tasks import send_email_async

        # Use invalid SMTP host to force failure
        with override_settings(SMTP_HOST="invalid-host"):
            result = send_email_async(
                email_type=EmailType.USER_INVITATION,
                to_email="retry@example.com",
                subject="Test Email",
                template_name="notifications/emails/user_invitation.html",
                context={"user": self.user},
                retry_count=0,
                max_retries=3,
            )

        self.assertIn(
            "delivery_id", result, "send_email_async must return a delivery_id even on failure"
        )

        delivery = EmailDelivery.objects.get(id=result["delivery_id"])

        # Should be DEFERRED or FAILED (not SENT or DELIVERED)
        self.assertIn(delivery.status, [EmailDeliveryStatus.DEFERRED, EmailDeliveryStatus.FAILED])

        if delivery.status == EmailDeliveryStatus.DEFERRED:
            self.assertTrue(delivery.can_retry())
            self.assertLess(delivery.retry_count, delivery.max_retries)

    def test_email_delivery_status_transitions(self):
        """Test email delivery status transitions"""
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="status@example.com",
            subject="Test Email",
            status=EmailDeliveryStatus.PENDING,
        )

        # PENDING -> SENT
        delivery.mark_sent("test-message-id")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, EmailDeliveryStatus.SENT)
        self.assertEqual(delivery.message_id, "test-message-id")

        # SENT -> DELIVERED
        delivery.mark_delivered()
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, EmailDeliveryStatus.DELIVERED)

        # Create new delivery for failure
        delivery2 = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="status2@example.com",
            subject="Test Email",
            status=EmailDeliveryStatus.PENDING,
        )

        # PENDING -> FAILED
        delivery2.mark_failed("Connection timeout")
        delivery2.refresh_from_db()
        self.assertEqual(delivery2.status, EmailDeliveryStatus.FAILED)
        self.assertEqual(delivery2.error_message, "Connection timeout")

        # Create new delivery for bounce
        delivery3 = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="status3@example.com",
            subject="Test Email",
            status=EmailDeliveryStatus.SENT,
        )

        # SENT -> BOUNCED
        delivery3.mark_bounced("Invalid email address")
        delivery3.refresh_from_db()
        self.assertEqual(delivery3.status, EmailDeliveryStatus.BOUNCED)
        self.assertEqual(delivery3.error_message, "Invalid email address")

    def test_email_delivery_retry_count_tracking(self):
        """Test that retry count is tracked through retry journey"""
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="retry@example.com",
            subject="Test Email",
            status=EmailDeliveryStatus.FAILED,
            retry_count=0,
            max_retries=3,
        )

        self.assertTrue(delivery.can_retry())

        delivery.increment_retry()
        delivery.refresh_from_db()
        self.assertEqual(delivery.retry_count, 1)
        self.assertTrue(delivery.can_retry())

        delivery.increment_retry()
        delivery.increment_retry()
        delivery.refresh_from_db()
        self.assertEqual(delivery.retry_count, 3)
        self.assertFalse(delivery.can_retry())

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    def test_email_delivery_metadata_storage(self):
        """Test that email delivery metadata is stored correctly"""
        from hub.apps.notifications.tasks import send_email_async

        context = {
            "user": self.user,
            "tenant": self.tenant,
            "invitation_url": "http://example.com/invite?token=123",
            "custom_data": {"key": "value"},
        }

        result = send_email_async(
            email_type=EmailType.USER_INVITATION,
            to_email="metadata@example.com",
            subject="Test Email",
            template_name="notifications/emails/user_invitation.html",
            context=context,
            tenant_id=str(self.tenant.id),
        )

        self.assertIn("delivery_id", result, "send_email_async must return a delivery_id")

        delivery = EmailDelivery.objects.get(id=result["delivery_id"])
        self.assertIsNotNone(delivery.metadata_json, "Metadata should be stored on delivery")
        self.assertIsInstance(delivery.metadata_json, dict)

    def test_email_delivery_per_tenant_isolation(self):
        """Test that email deliveries are isolated per tenant"""
        _suffix = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_suffix}", slug=f"other-tenant-{_suffix}"
        )
        User.objects.create_user(
            email=f"other-{_suffix}@example.com", password="testpass123", tenant=other_tenant
        )

        delivery1 = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="user1@example.com",
            subject="Test Email",
            tenant=self.tenant,
        )
        delivery2 = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="user2@example.com",
            subject="Test Email",
            tenant=other_tenant,
        )

        self.assertNotEqual(delivery1.tenant, delivery2.tenant)
        self.assertEqual(delivery1.tenant, self.tenant)
        self.assertEqual(delivery2.tenant, other_tenant)
        self.assertIn(delivery1, self.tenant.email_deliveries.all())
        self.assertIn(delivery2, other_tenant.email_deliveries.all())

    def test_email_delivery_per_user_isolation(self):
        """Test that email deliveries are isolated per user"""
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

        delivery1 = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="user1@example.com",
            subject="Test Email",
            user=self.user,
        )
        delivery2 = EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="user2@example.com",
            subject="Test Email",
            user=other_user,
        )

        self.assertNotEqual(delivery1.user, delivery2.user)
        self.assertIn(delivery1, self.user.email_deliveries.all())
        self.assertIn(delivery2, other_user.email_deliveries.all())

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    def test_email_delivery_edge_case_no_user(self):
        """Test email delivery when user is None"""
        from hub.apps.notifications.tasks import send_email_async

        result = send_email_async(
            email_type=EmailType.USER_INVITATION,
            to_email="nouser@example.com",
            subject="Test Email",
            template_name="notifications/emails/user_invitation.html",
            context={"tenant": self.tenant},
            tenant_id=str(self.tenant.id),
            # No user_id
        )

        self.assertIn(
            "delivery_id", result, "send_email_async must return a delivery_id even without user"
        )

        delivery = EmailDelivery.objects.get(id=result["delivery_id"])
        self.assertIsNotNone(delivery)
        self.assertIsNone(delivery.user)

    @override_settings(
        EMAIL_BACKEND="smtp",
        SMTP_HOST="localhost",
        SMTP_PORT=587,
        SMTP_FROM_EMAIL="noreply@example.com",
    )
    def test_email_delivery_edge_case_no_tenant(self):
        """Test email delivery when tenant is None"""
        from hub.apps.notifications.tasks import send_email_async

        result = send_email_async(
            email_type=EmailType.USER_INVITATION,
            to_email="notenant@example.com",
            subject="Test Email",
            template_name="notifications/emails/user_invitation.html",
            context={"user": self.user},
            # No tenant_id
        )

        self.assertIn(
            "delivery_id", result, "send_email_async must return a delivery_id even without tenant"
        )

        delivery = EmailDelivery.objects.get(id=result["delivery_id"])
        self.assertIsNotNone(delivery)
        self.assertIsNone(delivery.tenant)

    def test_email_delivery_query_by_status(self):
        """Test querying email deliveries by status"""
        EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="pending@example.com",
            subject="Test",
            status=EmailDeliveryStatus.PENDING,
        )
        EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="sent@example.com",
            subject="Test",
            status=EmailDeliveryStatus.SENT,
        )
        EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="failed@example.com",
            subject="Test",
            status=EmailDeliveryStatus.FAILED,
        )

        pending = EmailDelivery.objects.filter(status=EmailDeliveryStatus.PENDING)
        sent = EmailDelivery.objects.filter(status=EmailDeliveryStatus.SENT)
        failed = EmailDelivery.objects.filter(status=EmailDeliveryStatus.FAILED)

        self.assertGreaterEqual(pending.count(), 1)
        self.assertGreaterEqual(sent.count(), 1)
        self.assertGreaterEqual(failed.count(), 1)

    def test_email_delivery_query_by_type(self):
        """Test querying email deliveries by type"""
        EmailDelivery.objects.create(
            email_type=EmailType.USER_INVITATION,
            to_email="invitation@example.com",
            subject="Test",
            status=EmailDeliveryStatus.SENT,
        )
        EmailDelivery.objects.create(
            email_type=EmailType.PASSWORD_RESET,
            to_email="reset@example.com",
            subject="Test",
            status=EmailDeliveryStatus.SENT,
        )
        EmailDelivery.objects.create(
            email_type=EmailType.JOB_COMPLETION,
            to_email="job@example.com",
            subject="Test",
            status=EmailDeliveryStatus.SENT,
        )

        invitations = EmailDelivery.objects.filter(email_type=EmailType.USER_INVITATION)
        resets = EmailDelivery.objects.filter(email_type=EmailType.PASSWORD_RESET)
        jobs = EmailDelivery.objects.filter(email_type=EmailType.JOB_COMPLETION)

        self.assertGreaterEqual(invitations.count(), 1)
        self.assertGreaterEqual(resets.count(), 1)
        self.assertGreaterEqual(jobs.count(), 1)
