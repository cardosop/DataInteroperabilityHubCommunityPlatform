"""Tests for CAN-SPAM/GDPR unsubscribe in marketing emails (277.B.097)."""

import pytest
import hashlib
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.notifications.models import EmailType, is_marketing_email
from hub.apps.notifications.tasks import send_email_async
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _ensure_sub(tenant):
    from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
    ensure_tenant_has_active_subscription(tenant)


class MarketingEmailClassificationTest(TestCase):
    """is_marketing_email correctly identifies commercial email types."""

    @pytest.mark.integration
    def test_marketing_types_detected(self):
        self.assertTrue(is_marketing_email(EmailType.ASSET_CONTRACT_STRUCTURELESS_PENDING))
        self.assertTrue(is_marketing_email(EmailType.SCHEMA_EDITOR_AVAILABLE))
        self.assertTrue(is_marketing_email(EmailType.SCHEMA_EDITOR_RESIDUE_REMINDER))
        self.assertTrue(is_marketing_email(EmailType.ASSET_AUTO_REVERT_WARNING))

    @pytest.mark.integration
    def test_transactional_types_not_marketing(self):
        self.assertFalse(is_marketing_email(EmailType.PASSWORD_RESET))
        self.assertFalse(is_marketing_email(EmailType.USER_INVITATION))
        self.assertFalse(is_marketing_email(EmailType.EMAIL_VERIFICATION))
        self.assertFalse(is_marketing_email(EmailType.JOB_COMPLETION))
        self.assertFalse(is_marketing_email(EmailType.API_KEY_EXPIRING))
        self.assertFalse(is_marketing_email(EmailType.API_KEY_EXPIRED))

    @pytest.mark.integration
    def test_unknown_type_not_marketing(self):
        self.assertFalse(is_marketing_email("NONEXISTENT_TYPE"))


class UnsubscribeTokenTest(TestCase):
    """Token generation, hashing, and User model storage."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"UnsubToken {uid}", slug=f"unsub-token-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        _ensure_sub(self.tenant)
        self.user = User.objects.create_user(
            email=f"unsub-{uid}@example.com", password="testpass", tenant=self.tenant,
        )

    @pytest.mark.integration
    def test_token_generated_and_hashed(self):
        plaintext = str(uuid.uuid4())
        token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        self.assertEqual(len(token_hash), 64)
        self.user.unsubscribe_token = token_hash
        self.user.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.unsubscribe_token, token_hash)

    @pytest.mark.integration
    def test_token_null_initially(self):
        self.assertIsNone(self.user.unsubscribe_token)
        self.assertIsNone(self.user.unsubscribe_token_created_at)

    @pytest.mark.integration
    def test_token_lookup_by_hash(self):
        plaintext = str(uuid.uuid4())
        token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        self.user.unsubscribe_token = token_hash
        self.user.unsubscribe_token_created_at = "2026-01-01T00:00:00Z"
        self.user.save()

        found = User.objects.get(unsubscribe_token=token_hash)
        self.assertEqual(found.id, self.user.id)


class UnsubscribeEndpointTest(TestCase):
    """One-click unsubscribe endpoint (GET/POST /api/v1/notifications/unsubscribe/<token>/)."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"UnsubEP {uid}", slug=f"unsub-ep-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        _ensure_sub(self.tenant)
        self.user = User.objects.create_user(
            email=f"unsub-ep-{uid}@example.com", password="testpass", tenant=self.tenant,
        )
        self.plaintext = str(uuid.uuid4())
        self.user.unsubscribe_token = hashlib.sha256(self.plaintext.encode()).hexdigest()
        self.user.unsubscribe_token_created_at = "2026-01-01T00:00:00Z"
        self.user.save()
        self.client = APIClient()  # unauthenticated

    @pytest.mark.integration
    def test_get_unsubscribe_sets_opt_out(self):
        resp = self.client.get(f"/api/v1/notifications/unsubscribe/{self.plaintext}/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Unsubscribed", resp.content.decode())

        self.user.refresh_from_db()
        prefs = self.user.preferences or {}
        self.assertTrue(prefs.get("notifications", {}).get("marketing_opt_out"))

    @pytest.mark.integration
    def test_post_unsubscribe_sets_opt_out(self):
        resp = self.client.post(f"/api/v1/notifications/unsubscribe/{self.plaintext}/")
        self.assertEqual(resp.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(
            (self.user.preferences or {}).get("notifications", {}).get("marketing_opt_out")
        )

    @pytest.mark.integration
    def test_unsubscribe_clears_token(self):
        self.client.get(f"/api/v1/notifications/unsubscribe/{self.plaintext}/")
        self.user.refresh_from_db()
        self.assertIsNone(self.user.unsubscribe_token)

    @pytest.mark.integration
    def test_json_accept_returns_json(self):
        resp = self.client.get(
            f"/api/v1/notifications/unsubscribe/{self.plaintext}/",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "unsubscribed")

    @pytest.mark.integration
    def test_invalid_token_returns_success_to_avoid_enumeration(self):
        """Invalid tokens still return 200 to prevent user enumeration."""
        resp = self.client.get("/api/v1/notifications/unsubscribe/invalid-token/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Unsubscribed", resp.content.decode())

    @pytest.mark.integration
    def test_short_token_returns_success(self):
        resp = self.client.get("/api/v1/notifications/unsubscribe/abc/")
        self.assertEqual(resp.status_code, 200)

    @pytest.mark.integration
    def test_empty_token_returns_success(self):
        resp = self.client.get("/api/v1/notifications/unsubscribe//")
        self.assertEqual(resp.status_code, 200)

    @pytest.mark.integration
    def test_unsubscribe_creates_audit_event(self):
        self.client.get(f"/api/v1/notifications/unsubscribe/{self.plaintext}/")

        event = AuditEvent.objects.filter(
            action="EMAIL_UNSUBSCRIBED",
            resource_id=str(self.user.id),
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.details_json.get("method"), "one_click_link")

    @pytest.mark.integration
    def test_second_unsubscribe_is_idempotent(self):
        self.client.get(f"/api/v1/notifications/unsubscribe/{self.plaintext}/")
        # Token is now cleared, but we can still hit the endpoint
        self.user.refresh_from_db()
        self.assertTrue(
            (self.user.preferences or {}).get("notifications", {}).get("marketing_opt_out")
        )

        # Even with no token, hitting the endpoint again is harmless
        resp = self.client.get(f"/api/v1/notifications/unsubscribe/{self.plaintext}/")
        self.assertEqual(resp.status_code, 200)


class MarketingOptOutEnforcementTest(TestCase):
    """send_email_async skips marketing emails for opted-out users."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"OptOut {uid}", slug=f"opt-out-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        _ensure_sub(self.tenant)
        self.user = User.objects.create_user(
            email=f"opt-out-{uid}@example.com", password="testpass", tenant=self.tenant,
            preferences={
                "notifications": {
                    "marketing_opt_out": True,
                    "marketing_opted_out_at": "2026-01-01T00:00:00Z",
                },
            },
        )

    @pytest.mark.integration
    def test_marketing_email_skipped_for_opted_out_user(self):
        result = send_email_async(
            email_type=EmailType.SCHEMA_EDITOR_AVAILABLE,
            to_email=self.user.email,
            subject="Test Marketing",
            template_name="notifications/emails/schema_editor_available.html",
            context={},
            user_id=str(self.user.id),
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["skipped_reason"], "marketing_opt_out")

    @pytest.mark.integration
    def test_marketing_email_sends_for_non_opted_out_user(self):
        self.user.preferences = {"notifications": {"marketing_opt_out": False}}
        self.user.save()

        result = send_email_async(
            email_type=EmailType.SCHEMA_EDITOR_AVAILABLE,
            to_email=self.user.email,
            subject="Test Marketing",
            template_name="notifications/emails/schema_editor_available.html",
            context={},
            user_id=str(self.user.id),
        )
        # Should attempt to send (may fail without real email backend, but not skip)
        self.assertNotEqual(result.get("skipped_reason"), "marketing_opt_out")


class UnsubscribeURLInjectionTest(TestCase):
    """Marketing emails include unsubscribe_url in template context."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"URLInj {uid}", slug=f"url-inj-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        _ensure_sub(self.tenant)
        self.user = User.objects.create_user(
            email=f"url-inj-{uid}@example.com", password="testpass", tenant=self.tenant,
        )

    @pytest.mark.integration
    def test_marketing_email_context_gets_unsubscribe_url(self):
        """The context dict passed to send_email_async gets unsubscribe_url injected."""
        context: dict = {}
        send_email_async(
            email_type=EmailType.SCHEMA_EDITOR_AVAILABLE,
            to_email=self.user.email,
            subject="Test",
            template_name="notifications/emails/schema_editor_available.html",
            context=context,
            user_id=str(self.user.id),
        )
        self.assertIn("unsubscribe_url", context)
        self.assertIn("/api/v1/notifications/unsubscribe/", context["unsubscribe_url"])

    @pytest.mark.integration
    def test_transactional_email_does_not_get_unsubscribe_url(self):
        context: dict = {}
        send_email_async(
            email_type=EmailType.PASSWORD_RESET,
            to_email=self.user.email,
            subject="Password Reset",
            template_name="notifications/emails/password_reset.html",
            context=context,
            user_id=str(self.user.id),
        )
        self.assertNotIn("unsubscribe_url", context)

    @pytest.mark.integration
    def test_user_token_stored_as_hash_after_send(self):
        send_email_async(
            email_type=EmailType.SCHEMA_EDITOR_AVAILABLE,
            to_email=self.user.email,
            subject="Test",
            template_name="notifications/emails/schema_editor_available.html",
            context={},
            user_id=str(self.user.id),
        )
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.unsubscribe_token)
        self.assertEqual(len(self.user.unsubscribe_token), 64)  # SHA-256 hex


class GDPRIntegrationTest(TestCase):
    """GDPR erasure clears email preferences and unsubscribe token."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"GDPRUnsub {uid}", slug=f"gdpr-unsub-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        _ensure_sub(self.tenant)
        self.user = User.objects.create_user(
            email=f"gdpr-unsub-{uid}@example.com", password="testpass", tenant=self.tenant,
            preferences={"notifications": {"marketing_opt_out": False}},
            unsubscribe_token=hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest(),
            unsubscribe_token_created_at="2026-01-01T00:00:00Z",
        )

    @pytest.mark.integration
    def test_erasure_clears_preferences_and_token(self):
        from hub.apps.gdpr.models import ErasureRequest, ErasureRequestStatus
        from hub.apps.gdpr.services import ErasureService

        req = ErasureRequest.objects.create(
            tenant=self.tenant, user=self.user, status=ErasureRequestStatus.PENDING,
        )
        service = ErasureService(tenant_id=str(self.tenant.id))
        service.execute_erasure(str(req.id))

        self.user.refresh_from_db()
        prefs = self.user.preferences or {}
        self.assertTrue(prefs.get("notifications", {}).get("marketing_opt_out"))
        self.assertIsNone(self.user.unsubscribe_token)
