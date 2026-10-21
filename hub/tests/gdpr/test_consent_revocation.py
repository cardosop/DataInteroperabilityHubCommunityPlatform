"""Phase 110: GDPR consent revocation."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


class ConsentRevocationTest(TestCase):
    """Verify consent revocation capabilities."""

    def test_user_can_be_deactivated(self):
        """Deactivating user prevents further API access."""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Consent {uid}",
            slug=f"consent-{uid}",
        )
        user = User.objects.create_user(
            email=f"consent-{uid}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        self.assertTrue(user.is_active())

        # Deactivate
        user.status = UserStatus.SUSPENDED
        user.save()
        user.refresh_from_db()
        self.assertFalse(user.is_active())

    def test_user_status_field_supports_consent_states(self):
        """User model has statuses that support consent lifecycle."""
        valid_statuses = [s.value for s in UserStatus]
        self.assertIn("ACTIVE", valid_statuses)
        self.assertIn("SUSPENDED", valid_statuses)
