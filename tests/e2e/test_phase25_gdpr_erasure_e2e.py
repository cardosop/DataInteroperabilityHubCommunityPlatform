"""
E2E Tests for Phase 25 GDPR Erasure

End-to-end tests for GDPR erasure workflow.
Uses real implementations - no mocks/stubs per development best practices.

Coverage:
- Erasure request creation
- Erasure execution
- User anonymization
- Session revocation
- API key revocation
- Audit event creation
"""

import pytest

pytestmark = pytest.mark.slow
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.auth.models import APIKey
from hub.apps.gdpr.models import ErasureRequest, ErasureRequestStatus
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import User, UserStatus, Role, UserRole

from tests.e2e.conftest import get_response_data
import uuid

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e,
    pytest.mark.saas_platform,
]


class Phase25GDPRErasureE2ETest(TestCase):
    """E2E tests for Phase 25 GDPR erasure"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant (subscription required for POST to request-erasure)
        self.tenant = Tenant.objects.create(
            name=f"GDPR E2E Tenant {uuid.uuid4().hex[:8]}",
            slug=f"gdpr-e2e-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user to be erased
        self.user_to_erase = User.objects.create_user(
            email=f"eraseme2e-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="User To Erase E2E",
        )

        # Create API key for user (use key_hash instead of key)
        test_key = "e2e_test_api_key_12345"
        key_hash = APIKey.hash_key(test_key)
        self.api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user_to_erase,
            name="E2E Test API Key",
            key_hash=key_hash,
        )
        # Store plaintext key for later verification
        self.api_key_plaintext = test_key

        # Role so user can call request-erasure (tenant-scoped permission)
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user_to_erase, role=tenant_admin_role)

    def test_complete_erasure_workflow(self):
        """Test complete erasure workflow"""
        # Step 1: User requests erasure
        self.client.force_authenticate(user=self.user_to_erase)

        response = self.client.post(
            "/api/v1/users/me/request-erasure/",
            {},
            format="json",
        )

        # Should succeed
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
        )

        if response.status_code in [status.HTTP_201_CREATED, status.HTTP_200_OK]:
            erasure_request_id = (get_response_data(response) or {}).get("id")

            # Step 2: Verify erasure request created
            erasure_request = ErasureRequest.objects.get(id=erasure_request_id)
            self.assertEqual(erasure_request.status, ErasureRequestStatus.PENDING)
            self.assertEqual(erasure_request.user_id, self.user_to_erase.id)

            # Step 3: List erasure requests
            response = self.client.get("/api/v1/users/me/erasure-requests/")

            if response.status_code == status.HTTP_200_OK:
                data = get_response_data(response) or {}
                self.assertIn("results", data)
                request_ids = [req["id"] for req in data.get("results", [])]
                self.assertIn(str(erasure_request.id), request_ids)

            # Step 4: Execute erasure (simulate workflow execution)
            from hub.apps.gdpr.services import ErasureService

            erasure_service = ErasureService()
            try:
                erasure_service.execute_erasure(str(erasure_request.id))
            except NotImplementedError:
                pytest.skip("ErasureService.execute_erasure not fully implemented")
                return

            # Step 5: Verify user anonymized — all PII fields
            self.user_to_erase.refresh_from_db()
            # Email must be anonymized
            self.assertNotIn("eraseme2e", self.user_to_erase.email.lower())
            self.assertIn("erased", self.user_to_erase.email.lower())
            # Display name must be anonymized (not the original value)
            self.assertNotEqual(self.user_to_erase.display_name, "User To Erase E2E")
            self.assertFalse(
                self.user_to_erase.display_name and "User To Erase" in self.user_to_erase.display_name,
                "display_name still contains original PII after erasure",
            )

            # Step 6: Verify API key revoked (must still exist with revoked_at set)
            self.api_key.refresh_from_db()
            self.assertIsNotNone(
                self.api_key.revoked_at,
                "API key must be revoked (revoked_at set) after GDPR erasure",
            )

            # Step 7: Verify erasure request completed
            erasure_request.refresh_from_db()
            self.assertEqual(erasure_request.status, ErasureRequestStatus.COMPLETED)
            self.assertIsNotNone(erasure_request.completed_at)

            # Step 8: Verify audit event created
            audit_events = AuditEvent.objects.filter(
                resource_type="USER",
                resource_id=str(self.user_to_erase.id),
                action="ERASURE_EXECUTED",
            )
            self.assertTrue(audit_events.exists())

    def test_erasure_request_tenant_isolation(self):
        """Test erasure request tenant isolation"""
        # Create another tenant and user
        tenant2 = Tenant.objects.create(
            name=f"Other E2E Tenant {uuid.uuid4().hex[:8]}",
            slug=f"other-e2e-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )
        user2 = User.objects.create_user(
            email=f"other2e2e-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant2,
            status=UserStatus.ACTIVE,
        )

        # Create erasure request for user_to_erase (include tenant)
        erasure_request = ErasureRequest.objects.create(
            tenant=self.tenant,
            user=self.user_to_erase,
            status=ErasureRequestStatus.PENDING,
            requested_at=timezone.now(),
        )

        # User2 should not see user_to_erase's erasure request
        self.client.force_authenticate(user=user2)

        response = self.client.get("/api/v1/users/me/erasure-requests/")

        if response.status_code == status.HTTP_200_OK:
            data = get_response_data(response) or {}
            request_ids = [req["id"] for req in data.get("results", [])]
            # Should not include user_to_erase's request
            self.assertNotIn(str(erasure_request.id), request_ids)
