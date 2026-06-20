"""
Phase 74 (74.1.3) — Auth Business Rules Tests

4 tests per method × 4 methods = 16 tests.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.auth.business_rules import AuthBusinessRules


@pytest.mark.django_db(transaction=True)
class TestValidateRegistration(TestCase):
    def setUp(self):
        self.rules = AuthBusinessRules(enable_caching=False, enable_metrics=False)
        from hub.apps.tenants.models import Tenant

        self.tenant, _ = Tenant.objects.get_or_create(
            name="auth-br-test", defaults={"slug": "auth-br-test"}
        )

    def test_valid_registration(self):
        r = self.rules.validate_registration(f"new-{uuid.uuid4().hex[:8]}@example.com")
        self.assertTrue(r.is_valid)

    def test_invalid_email_format(self):
        r = self.rules.validate_registration("not-an-email")
        self.assertFalse(r.is_valid)
        self.assertIn("Invalid email", r.errors[0])

    def test_duplicate_email_rejected(self):
        from hub.apps.users.models import User

        email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
        User.objects.create_user(email=email, password="Test1234!", tenant=self.tenant)
        r = self.rules.validate_registration(email)
        self.assertFalse(r.is_valid)
        self.assertIn("already registered", r.errors[0])

    def test_suspended_tenant_rejected(self):
        from hub.apps.tenants.models import Tenant

        t = Tenant.objects.create(name="suspended-t", slug="suspended-t", status="SUSPENDED")
        r = self.rules.validate_registration("ok@example.com", tenant_id=str(t.id))
        self.assertFalse(r.is_valid)
        self.assertIn("suspended", r.errors[0].lower())


@pytest.mark.django_db(transaction=True)
class TestValidateLoginAttempt(TestCase):
    def setUp(self):
        self.rules = AuthBusinessRules(enable_caching=False, enable_metrics=False)
        from hub.apps.tenants.models import Tenant

        self.tenant, _ = Tenant.objects.get_or_create(
            name="auth-br-login", defaults={"slug": "auth-br-login"}
        )

    def test_valid_login(self):
        r = self.rules.validate_login_attempt("user@example.com")
        self.assertTrue(r.is_valid)

    def test_invalid_email(self):
        r = self.rules.validate_login_attempt("")
        self.assertFalse(r.is_valid)

    @override_settings(LOGIN_MAX_ATTEMPTS=3, LOGIN_LOCKOUT_WINDOW_MINUTES=15)
    def test_locked_account_rejected(self):
        from hub.apps.auth.models import LoginAttempt

        email = f"locked-{uuid.uuid4().hex[:8]}@example.com"
        for _ in range(3):
            LoginAttempt.objects.create(email=email, ip_address="127.0.0.1", success=False)
        r = self.rules.validate_login_attempt(email)
        self.assertFalse(r.is_valid)
        self.assertIn("locked", r.errors[0].lower())

    def test_suspended_tenant_rejected(self):
        from hub.apps.tenants.models import Tenant

        t = Tenant.objects.create(name="susp-login", slug="susp-login", status="SUSPENDED")
        r = self.rules.validate_login_attempt("user@example.com", tenant_id=str(t.id))
        self.assertFalse(r.is_valid)
        self.assertIn("suspended", r.errors[0].lower())


@pytest.mark.django_db(transaction=True)
class TestValidateInvitationAcceptance(TestCase):
    def setUp(self):
        self.rules = AuthBusinessRules(enable_caching=False, enable_metrics=False)
        from hub.apps.tenants.models import Tenant

        self.tenant, _ = Tenant.objects.get_or_create(
            name="auth-br-invite", defaults={"slug": "auth-br-invite"}
        )

    def test_valid_invitation(self):
        from hub.apps.auth.utils import sha256_hex
        from hub.apps.users.models import User

        email = f"invite-{uuid.uuid4().hex[:8]}@example.com"
        token = uuid.uuid4().hex
        user = User.objects.create_user(email=email, password="Test1234!", tenant=self.tenant)
        user.status = "INVITED"
        user.invitation_token = sha256_hex(token)
        user.save(update_fields=["status", "invitation_token"])
        r = self.rules.validate_invitation_acceptance(token, email)
        self.assertTrue(r.is_valid)

    def test_empty_token(self):
        r = self.rules.validate_invitation_acceptance("", "a@b.com")
        self.assertFalse(r.is_valid)

    def test_invalid_token(self):
        r = self.rules.validate_invitation_acceptance("bogus-token", "a@b.com")
        self.assertFalse(r.is_valid)
        self.assertIn("Invalid invitation", r.errors[0])

    def test_email_mismatch(self):
        from hub.apps.auth.utils import sha256_hex
        from hub.apps.users.models import User

        email = f"invite2-{uuid.uuid4().hex[:8]}@example.com"
        token = uuid.uuid4().hex
        user = User.objects.create_user(email=email, password="Test1234!", tenant=self.tenant)
        user.status = "INVITED"
        user.invitation_token = sha256_hex(token)
        user.save(update_fields=["status", "invitation_token"])
        r = self.rules.validate_invitation_acceptance(token, "wrong@example.com")
        self.assertFalse(r.is_valid)
        self.assertIn("does not match", r.errors[0])


@pytest.mark.django_db(transaction=True)
class TestValidateTokenRefresh(TestCase):
    def setUp(self):
        self.rules = AuthBusinessRules(enable_caching=False, enable_metrics=False)
        from hub.apps.tenants.models import Tenant

        self.tenant, _ = Tenant.objects.get_or_create(
            name="auth-br-refresh", defaults={"slug": "auth-br-refresh"}
        )

    def test_valid_refresh_token(self):
        from hub.apps.auth.models import RefreshToken
        from hub.apps.users.models import User

        user = User.objects.create_user(
            email=f"ref-{uuid.uuid4().hex[:8]}@test.com",
            password="Test1234!",
            tenant=self.tenant,
        )
        token_str = RefreshToken.generate_token()
        token_hash = RefreshToken.hash_token(token_str)
        RefreshToken.objects.create(
            user=user,
            token_hash=token_hash,
            expires_at=timezone.now() + timedelta(days=1),
        )
        r = self.rules.validate_token_refresh(token_str)
        self.assertTrue(r.is_valid)

    def test_empty_token(self):
        r = self.rules.validate_token_refresh("")
        self.assertFalse(r.is_valid)

    def test_invalid_token(self):
        r = self.rules.validate_token_refresh("nonexistent-token")
        self.assertFalse(r.is_valid)
        self.assertIn("Invalid refresh", r.errors[0])

    def test_expired_token(self):
        from hub.apps.auth.models import RefreshToken
        from hub.apps.users.models import User

        user = User.objects.create_user(
            email=f"exp-{uuid.uuid4().hex[:8]}@test.com",
            password="Test1234!",
            tenant=self.tenant,
        )
        token_str = RefreshToken.generate_token()
        token_hash = RefreshToken.hash_token(token_str)
        RefreshToken.objects.create(
            user=user,
            token_hash=token_hash,
            expires_at=timezone.now() - timedelta(days=1),
        )
        r = self.rules.validate_token_refresh(token_str)
        self.assertFalse(r.is_valid)
        self.assertIn("expired", r.errors[0].lower())
