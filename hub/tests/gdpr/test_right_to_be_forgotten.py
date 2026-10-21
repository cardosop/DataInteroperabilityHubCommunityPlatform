"""Phase 110: GDPR right to be forgotten."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.gdpr.models import ErasureRequest, ErasureRequestStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


class RightToBeForgottenTest(TestCase):
    """Verify GDPR erasure request model and workflow."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"GDPR {uid}",
            slug=f"gdpr-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"gdpr-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_erasure_request_can_be_created(self):
        """Erasure request record created for user."""
        req = ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.PENDING,
        )
        self.assertEqual(req.status, ErasureRequestStatus.PENDING)
        self.assertEqual(req.user, self.user)

    def test_erasure_request_status_transitions(self):
        """Erasure request can move through status lifecycle."""
        req = ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.PENDING,
        )
        req.status = ErasureRequestStatus.PROCESSING
        req.save()
        req.refresh_from_db()
        self.assertEqual(req.status, ErasureRequestStatus.PROCESSING)

    def test_user_data_accessible_before_erasure(self):
        """User data is accessible before erasure request."""
        user = User.objects.get(pk=self.user.pk)
        self.assertEqual(user.email, self.user.email)
        self.assertTrue(user.is_active())
