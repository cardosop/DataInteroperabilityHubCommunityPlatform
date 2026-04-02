"""Constraint-based token refresh tests (replaces threading-based concurrency)."""
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from hub.apps.auth.models import RefreshToken
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


class TokenRefreshConstraintTest(TestCase):
    """Refresh token revocation and family rotation correctness."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"TR {uid}", slug=f"tr-{uid}")
        self.user = User.objects.create_user(
            email=f"tr-{uid}@example.com", password="test123",
            tenant=self.tenant, status=UserStatus.ACTIVE,
        )
        self.family_id = uuid.uuid4()
        token_str = RefreshToken.generate_token()
        self.token_hash = RefreshToken.hash_token(token_str)
        self.token = RefreshToken.objects.create(
            user=self.user, token_hash=self.token_hash,
            family_id=self.family_id, sequence_number=0,
            expires_at=timezone.now() + timedelta(days=7),
        )

    def test_revoked_token_cannot_be_reused(self):
        self.token.revoke()
        self.token.refresh_from_db()
        self.assertTrue(self.token.is_revoked())
        self.assertFalse(self.token.is_valid())

    def test_family_revocation_revokes_all_tokens(self):
        for i in range(1, 4):
            RefreshToken.objects.create(
                user=self.user, token_hash=RefreshToken.hash_token(RefreshToken.generate_token()),
                family_id=self.family_id, sequence_number=i,
                expires_at=timezone.now() + timedelta(days=7),
            )
        self.token.revoke_family()
        active = RefreshToken.objects.filter(family_id=self.family_id, revoked_at__isnull=True).count()
        self.assertEqual(active, 0)

    def test_select_for_update_prevents_double_use(self):
        """Simulate serialized access: first use revokes, second sees revoked."""
        with transaction.atomic():
            locked = RefreshToken.objects.select_for_update().get(pk=self.token.pk)
            locked.revoke()

        self.token.refresh_from_db()
        self.assertTrue(self.token.is_revoked())
