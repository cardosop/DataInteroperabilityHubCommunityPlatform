"""
Unit tests for email template rendering.

Tests user invitation, password reset, job completion, and job failure templates.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.notifications.templates import (
    build_invitation_url,
    build_job_url,
    build_password_reset_url,
    get_base_url,
    render_email_template,
)
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class EmailTemplateRenderingTest(TestCase):
    """Tests for email template rendering"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

    def test_render_user_invitation_template(self):
        """Test rendering user invitation email template"""
        context = {
            "user": self.user,
            "tenant": self.tenant,
            "invitation_url": "http://example.com/invite?token=123",
        }

        result = render_email_template("notifications/emails/user_invitation.html", context)

        self.assertIn("html", result)
        self.assertIn("text", result)
        self.assertIn("Test User", result["html"])
        self.assertIn("Test Tenant", result["html"])
        self.assertIn("http://example.com/invite?token=123", result["html"])

    def test_render_password_reset_template(self):
        """Test rendering password reset email template"""
        context = {"user": self.user, "reset_url": "http://example.com/reset?token=456"}

        result = render_email_template("notifications/emails/password_reset.html", context)

        self.assertIn("html", result)
        self.assertIn("text", result)
        self.assertIn("Test User", result["html"])
        self.assertIn("http://example.com/reset?token=456", result["html"])

    def test_render_job_completion_template(self):
        """Test rendering job completion email template"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DQ_RUN",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            created_by=self.user,
            result_json={"status": "completed", "checks_passed": 10},
        )

        context = {
            "user": self.user,
            "job": job,
            "job_type": job.get_type_display(),
            "resource_type": job.resource_type,
            "resource_id": str(job.resource_id),
            "job_url": "http://example.com/jobs/123",
            "result_summary": str(job.result_json),
        }

        result = render_email_template("notifications/emails/job_completion.html", context)

        self.assertIn("html", result)
        self.assertIn("text", result)
        self.assertIn("Job Completed", result["html"])
        self.assertIn("Data Quality Run", result["html"])
        self.assertIn("http://example.com/jobs/123", result["html"])

    def test_render_job_failure_template(self):
        """Test rendering job failure email template"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.FAILED,
            resource_type="COMPLIANCE_RUN",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            created_by=self.user,
            error_message="Validation failed",
        )

        context = {
            "user": self.user,
            "job": job,
            "job_type": job.get_type_display(),
            "resource_type": job.resource_type,
            "resource_id": str(job.resource_id),
            "error_message": job.error_message,
            "job_url": "http://example.com/jobs/456",
        }

        result = render_email_template("notifications/emails/job_failure.html", context)

        self.assertIn("html", result)
        self.assertIn("text", result)
        self.assertIn("Job Failed", result["html"])
        self.assertIn("Compliance Run", result["html"])
        self.assertIn("Validation failed", result["html"])

    def test_render_template_with_missing_context(self):
        """Test template rendering with missing context variables"""
        context = {"user": self.user}

        # Should not raise error, template should handle missing variables
        result = render_email_template("notifications/emails/user_invitation.html", context)

        self.assertIn("html", result)
        self.assertIn("text", result)

    def test_render_template_html_only(self):
        """Test rendering HTML template only"""
        context = {
            "user": self.user,
            "tenant": self.tenant,
            "invitation_url": "http://example.com/invite?token=123",
        }

        result = render_email_template("notifications/emails/user_invitation.html", context)

        # Should have both HTML and text (text auto-generated from HTML)
        self.assertIn("html", result)
        self.assertIn("text", result)
        self.assertGreater(len(result["html"]), 0)
        self.assertGreater(len(result["text"]), 0)

    def test_render_template_with_text_template(self):
        """Test rendering with explicit text template"""
        context = {"message": "Test message"}

        # Auto-generate text from HTML if text template not provided
        result = render_email_template(
            "notifications/emails/user_invitation.html", context, text_template_name=None
        )

        self.assertIn("html", result)
        self.assertIn("text", result)
        # Text should be generated from HTML
        self.assertTrue(len(result["text"]) > 0)


class EmailTemplateURLBuildingTest(TestCase):
    """Tests for email template URL building"""

    def test_get_base_url_default(self):
        """Test getting default base URL"""
        from django.test import override_settings

        with override_settings(EMAIL_BASE_URL=None):
            url = get_base_url()
            self.assertEqual(url, "http://localhost:8000")

    def test_get_base_url_from_settings(self):
        """Test getting base URL from settings"""
        from django.test import override_settings

        with override_settings(EMAIL_BASE_URL="https://hub.example.com"):
            url = get_base_url()
            self.assertEqual(url, "https://hub.example.com")

    def test_build_invitation_url(self):
        """Test building invitation URL"""
        from django.test import override_settings

        with override_settings(EMAIL_BASE_URL="https://hub.example.com"):
            url = build_invitation_url("test-token-123")
            self.assertEqual(
                url, "https://hub.example.com/auth/accept-invitation?token=test-token-123"
            )

    def test_build_password_reset_url(self):
        """Test building password reset URL — token in fragment (221.1.3)"""
        from django.test import override_settings

        with override_settings(EMAIL_BASE_URL="https://hub.example.com"):
            url = build_password_reset_url("reset-token-456")
            self.assertEqual(
                url, "https://hub.example.com/auth/password-reset/confirm#token=reset-token-456"
            )

    def test_build_job_url(self):
        """Test building job URL"""
        from django.test import override_settings

        with override_settings(EMAIL_BASE_URL="https://hub.example.com"):
            url = build_job_url("job-uuid-789")
            self.assertEqual(url, "https://hub.example.com/api/v1/jobs/job-uuid-789")

    def test_build_invitation_url_with_special_characters(self):
        """Token with special characters is included in the invitation URL.

        NOTE: ``build_invitation_url`` does NOT URL-encode the token
        value at this time — raw ``/`` and ``?`` characters appear in
        the query string.  This is a known gap; callers are expected to
        pass URL-safe tokens (e.g. JWT or base64url).
        """
        from urllib.parse import parse_qs, urlparse

        from django.test import override_settings

        with override_settings(EMAIL_BASE_URL="https://hub.example.com"):
            url = build_invitation_url("test-token-123/456?param=value")
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            self.assertIn("token", qs, "URL must contain a 'token' query parameter")

    def test_build_urls_with_different_base_urls(self):
        """Test building URLs with different base URL configurations"""
        from django.test import override_settings

        base_urls = [
            "http://localhost:8000",
            "https://hub.example.com",
            "https://staging.hub.example.com",
        ]

        for base_url in base_urls:
            with override_settings(EMAIL_BASE_URL=base_url):
                invitation_url = build_invitation_url("token")
                self.assertTrue(invitation_url.startswith(base_url))

                reset_url = build_password_reset_url("token")
                self.assertTrue(reset_url.startswith(base_url))

                job_url = build_job_url("job-id")
                self.assertTrue(job_url.startswith(base_url))


class EmailTemplateContentTest(TestCase):
    """Tests for email template content"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

    def test_user_invitation_template_contains_required_elements(self):
        """Test that user invitation template contains required elements"""
        context = {
            "user": self.user,
            "tenant": self.tenant,
            "invitation_url": "http://example.com/invite?token=123",
        }

        result = render_email_template("notifications/emails/user_invitation.html", context)

        html = result["html"]
        # Should contain user name
        self.assertIn("Test User", html)
        # Should contain tenant name
        self.assertIn("Test Tenant", html)
        # Should contain invitation URL
        self.assertIn("http://example.com/invite?token=123", html)
        # Should contain invitation button/link
        self.assertIn("invitation", html.lower())

    def test_password_reset_template_contains_required_elements(self):
        """Test that password reset template contains required elements"""
        context = {"user": self.user, "reset_url": "http://example.com/reset?token=456"}

        result = render_email_template("notifications/emails/password_reset.html", context)

        html = result["html"]
        # Should contain user name
        self.assertIn("Test User", html)
        # Should contain reset URL
        self.assertIn("http://example.com/reset?token=456", html)
        # Should contain reset button/link
        self.assertIn("reset", html.lower())

    def test_job_completion_template_contains_required_elements(self):
        """Test that job completion template contains required elements"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DQ_RUN",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            created_by=self.user,
            result_json={"status": "completed"},
        )

        context = {
            "user": self.user,
            "job": job,
            "job_type": job.get_type_display(),
            "job_url": "http://example.com/jobs/123",
        }

        result = render_email_template("notifications/emails/job_completion.html", context)

        html = result["html"]
        # Should contain job completion message
        self.assertIn("completed", html.lower())
        # Should contain job type
        self.assertIn("Data Quality Run", html)
        # Should contain job URL
        self.assertIn("http://example.com/jobs/123", html)

    def test_job_failure_template_contains_required_elements(self):
        """Test that job failure template contains required elements"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.FAILED,
            resource_type="COMPLIANCE_RUN",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            created_by=self.user,
            error_message="Validation failed",
        )

        context = {
            "user": self.user,
            "job": job,
            "job_type": job.get_type_display(),
            "error_message": job.error_message,
            "job_url": "http://example.com/jobs/456",
        }

        result = render_email_template("notifications/emails/job_failure.html", context)

        html = result["html"]
        # Should contain job failure message
        self.assertIn("failed", html.lower())
        # Should contain error message
        self.assertIn("Validation failed", html)
        # Should contain job URL
        self.assertIn("http://example.com/jobs/456", html)

    def test_template_text_generation_from_html(self):
        """Test that text content is generated from HTML"""
        context = {
            "user": self.user,
            "tenant": self.tenant,
            "invitation_url": "http://example.com/invite?token=123",
        }

        result = render_email_template("notifications/emails/user_invitation.html", context)

        # Text should be generated from HTML
        self.assertIn("text", result)
        text = result["text"]

        # Text should contain key information (without HTML tags)
        self.assertIn("Test User", text)
        self.assertIn("Test Tenant", text)
        # Should not contain HTML tags
        self.assertNotIn("<h1>", text)
        self.assertNotIn("<p>", text)

    def test_template_handles_missing_user_display_name(self):
        """Test template handles missing user display_name"""
        user = User.objects.create_user(
            email="no-display@example.com",
            password="testpass123",
            tenant=self.tenant,
            # No display_name set
        )

        context = {
            "user": user,
            "tenant": self.tenant,
            "invitation_url": "http://example.com/invite?token=123",
        }

        # Should not raise error
        result = render_email_template("notifications/emails/user_invitation.html", context)

        self.assertIn("html", result)
        self.assertIn("text", result)
