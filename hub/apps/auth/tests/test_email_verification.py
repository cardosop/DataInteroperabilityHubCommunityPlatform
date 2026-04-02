"""
Phase 204 — email verification (registration token, verify, resend, login gate).

Uses real views, ORM, cache, and token helpers (no mocked hub services).
"""

import uuid
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.auth.email_verification import (
    issue_verification_token_plaintext,
    verify_plaintext_token,
)
from hub.apps.notifications.models import EmailDelivery, EmailDeliveryStatus, EmailType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


def _ensure_default_plans():
    from django.db import transaction as db_transaction

    from hub.apps.tenants.models import TenantPlan

    plans = [
        {"slug": "free", "name": "Free Plan", "tier": "FREE"},
        {"slug": "pro", "name": "Pro Plan", "tier": "PRO"},
        {"slug": "enterprise", "name": "Enterprise Plan", "tier": "ENTERPRISE"},
    ]
    for p in plans:
        try:
            with db_transaction.atomic():
                TenantPlan.objects.get_or_create(
                    slug=p["slug"],
                    defaults={
                        "name": p["name"],
                        "tier": p["tier"],
                        "is_active": True,
                    },
                )
        except Exception:
            pass


class EmailVerificationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
        _ensure_default_plans()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"EV Tenant {uid}",
            slug=f"ev-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

    def test_registration_sets_pending_verification_and_token(self):
        email = f"reg-{uuid.uuid4().hex[:8]}@example.com"
        r = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": email,
                "password": "SecurePass123",
                "name": "Reg User",
                "tenant_id": str(self.tenant.id),
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=email)
        self.assertFalse(user.email_verified)
        self.assertIsNotNone(user.email_verification_token)
        self.assertIsNotNone(user.email_verification_sent_at)

    def test_registration_sends_verification_email_delivery_record(self):
        """RQ runs synchronously under tests (settings); delivery row proves send path ran."""
        email = f"deliver-{uuid.uuid4().hex[:8]}@example.com"
        before = EmailDelivery.objects.filter(
            email_type=EmailType.EMAIL_VERIFICATION,
            to_email__iexact=email,
        ).count()
        r = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": email,
                "password": "SecurePass123",
                "name": "Delivery User",
                "tenant_id": str(self.tenant.id),
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        after = EmailDelivery.objects.filter(
            email_type=EmailType.EMAIL_VERIFICATION,
            to_email__iexact=email,
        ).count()
        self.assertGreater(after, before)
        row = (
            EmailDelivery.objects.filter(
                email_type=EmailType.EMAIL_VERIFICATION,
                to_email__iexact=email,
            )
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(row)
        self.assertEqual(row.status, EmailDeliveryStatus.SENT)

    def test_verify_email_valid_token(self):
        user = User.objects.create_user(
            email=f"v-{uuid.uuid4().hex[:8]}@example.com",
            password="SecurePass123",
            tenant=self.tenant,
            display_name="V",
            status=UserStatus.ACTIVE,
        )
        user.email_verified = False
        user.save(update_fields=["email_verified", "updated_at"])
        token = issue_verification_token_plaintext(user)
        resp = self.client.post("/api/v1/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertIsNotNone(user.email_verified_at)
        self.assertIsNone(user.email_verification_token)

    def test_verify_email_expired_after_72h(self):
        user = User.objects.create_user(
            email=f"exp-{uuid.uuid4().hex[:8]}@example.com",
            password="SecurePass123",
            tenant=self.tenant,
            display_name="E",
            status=UserStatus.ACTIVE,
        )
        user.email_verified = False
        user.save(update_fields=["email_verified", "updated_at"])
        token = issue_verification_token_plaintext(user)
        User.objects.filter(pk=user.pk).update(
            email_verification_sent_at=timezone.now() - timedelta(hours=73)
        )
        resp = self.client.post("/api/v1/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_generates_new_token_hash(self):
        user = User.objects.create_user(
            email=f"rs-{uuid.uuid4().hex[:8]}@example.com",
            password="SecurePass123",
            tenant=self.tenant,
            display_name="R",
            status=UserStatus.ACTIVE,
        )
        user.email_verified = False
        user.save(update_fields=["email_verified", "updated_at"])
        issue_verification_token_plaintext(user)
        user.refresh_from_db()
        h1 = user.email_verification_token
        r = self.client.post(
            "/api/v1/auth/resend-verification/",
            {"email": user.email},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertNotEqual(user.email_verification_token, h1)

    def test_resend_rate_limit_fourth_request_429(self):
        email = f"rl-{uuid.uuid4().hex[:8]}@example.com"
        user = User.objects.create_user(
            email=email,
            password="SecurePass123",
            tenant=self.tenant,
            display_name="RL",
            status=UserStatus.ACTIVE,
        )
        user.email_verified = False
        user.save(update_fields=["email_verified", "updated_at"])
        for _ in range(3):
            resp = self.client.post(
                "/api/v1/auth/resend-verification/",
                {"email": email},
                format="json",
            )
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp4 = self.client.post(
            "/api/v1/auth/resend-verification/",
            {"email": email},
            format="json",
        )
        self.assertEqual(resp4.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_login_within_grace_period_unverified_succeeds(self):
        user = User.objects.create_user(
            email=f"gr-{uuid.uuid4().hex[:8]}@example.com",
            password="SecurePass123",
            tenant=self.tenant,
            display_name="G",
            status=UserStatus.ACTIVE,
        )
        user.email_verified = False
        user.save(update_fields=["email_verified", "updated_at"])
        resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "SecurePass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_login_after_grace_unverified_returns_403(self):
        user = User.objects.create_user(
            email=f"blk-{uuid.uuid4().hex[:8]}@example.com",
            password="SecurePass123",
            tenant=self.tenant,
            display_name="B",
            status=UserStatus.ACTIVE,
        )
        user.email_verified = False
        user.save(update_fields=["email_verified", "updated_at"])
        past = timezone.now() - timedelta(hours=25)
        User.objects.filter(pk=user.pk).update(created_at=past)
        resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "SecurePass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        body = resp.json()
        self.assertEqual(body.get("code"), "EMAIL_NOT_VERIFIED")
        self.assertEqual(body.get("error"), "EMAIL_NOT_VERIFIED")
        self.assertEqual(body.get("resend_url"), "/api/v1/auth/resend-verification/")
        self.assertIn("resend_url", body.get("details", {}))

    def test_login_verified_succeeds_after_grace_window(self):
        user = User.objects.create_user(
            email=f"ok-{uuid.uuid4().hex[:8]}@example.com",
            password="SecurePass123",
            tenant=self.tenant,
            display_name="O",
            status=UserStatus.ACTIVE,
        )
        user.email_verified = True
        user.save(update_fields=["email_verified", "updated_at"])
        past = timezone.now() - timedelta(hours=48)
        User.objects.filter(pk=user.pk).update(created_at=past)
        resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "SecurePass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_platform_admin_unverified_old_account_can_login(self):
        user = User.objects.create_user(
            email=f"pa-{uuid.uuid4().hex[:8]}@example.com",
            password="SecurePass123",
            tenant=None,
            display_name="PA",
            status=UserStatus.ACTIVE,
        )
        user.is_platform_admin = True
        user.email_verified = False
        user.save(update_fields=["is_platform_admin", "email_verified", "updated_at"])
        User.objects.filter(pk=user.pk).update(
            created_at=timezone.now() - timedelta(hours=48)
        )
        resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "SecurePass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_verify_plaintext_token_helper_returns_user(self):
        user = User.objects.create_user(
            email=f"h-{uuid.uuid4().hex[:8]}@example.com",
            password="SecurePass123",
            tenant=self.tenant,
            display_name="H",
            status=UserStatus.ACTIVE,
        )
        user.email_verified = False
        user.save(update_fields=["email_verified", "updated_at"])
        token = issue_verification_token_plaintext(user)
        found = verify_plaintext_token(token)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, user.id)
