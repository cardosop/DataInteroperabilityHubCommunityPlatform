"""
E2E Tests for Phase 25 Billing Features

End-to-end tests for billing and subscription features.
Uses real implementations - no mocks/stubs per development best practices.

Coverage:
- Subscription management
- Invoice listing and retrieval
- Subscription state enforcement (PAST_DUE blocking mutations)
- Tenant suspension blocking mutations
"""

import pytest

pytestmark = pytest.mark.slow
import uuid

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import AssetStatus
from hub.apps.billing.models import Invoice, Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantPlan, TenantStatus
from hub.apps.users.models import Role, User, UserRole, UserStatus

from .conftest import get_response_data

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e,
    pytest.mark.saas_platform,
]


class Phase25BillingE2ETest(TestCase):
    """E2E tests for Phase 25 billing features"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Billing E2E Tenant {uuid.uuid4().hex[:8]}",
            slug=f"billing-e2e-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"billinge2e-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create plan
        self.plan = TenantPlan.objects.create(
            name="E2E Test Plan",
            slug="e2e-test-plan",
            tier="PRO",
            limits_json={"max_assets": 10},
            is_active=True,
        )

        # Assign plan to tenant
        self.tenant.plan = self.plan
        self.tenant.save()

        # Create subscription
        self.subscription = Subscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
        )

        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=tenant_admin_role)

        self.client.force_authenticate(user=self.user)

    def test_complete_billing_workflow(self):
        """Test complete billing workflow: subscription → invoices → asset creation"""
        # Step 1: Get current subscription
        response = self.client.get("/api/v1/billing/subscription/current/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertEqual(data["status"], SubscriptionStatus.ACTIVE)

        # Step 2: Create invoice
        invoice = Invoice.objects.create(
            tenant=self.tenant,
            subscription=self.subscription,
            stripe_invoice_id=f"inv_e2e_{timezone.now().timestamp()}",
            amount_due=100.00,
            currency="USD",
            status="open",
            due_date=timezone.now() + timezone.timedelta(days=30),
        )

        # Step 3: List invoices
        response = self.client.get("/api/v1/billing/invoices/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertIn("results", data)
        invoice_ids = [inv["id"] for inv in data["results"]]
        self.assertIn(str(invoice.id), invoice_ids)

        # Step 4: Get invoice detail
        response = self.client.get(f"/api/v1/billing/invoices/{invoice.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertEqual(float(data["amount_due"]), 100.00)

        # Step 5: Create asset (should succeed with ACTIVE subscription)
        response = self.client.post(
            "/api/v1/assets/",
            {
                "key": "billing-test-asset",
                "name": "Billing Test Asset",
                "status": AssetStatus.ACTIVE.value,
            },
            format="json",
        )

        # Should succeed with ACTIVE subscription
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_past_due_subscription_blocks_mutations(self):
        """Test that PAST_DUE subscription blocks non-read mutations"""
        # Update subscription to PAST_DUE
        self.subscription.status = SubscriptionStatus.PAST_DUE
        self.subscription.save()

        # Try to create asset (should be blocked)
        response = self.client.post(
            "/api/v1/assets/",
            {
                "key": "blocked-asset",
                "name": "Blocked Asset",
                "status": AssetStatus.ACTIVE.value,
            },
            format="json",
        )

        # Should return 403 with subscription_inactive
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        data = get_response_data(response) or {}
        error_str = str(data.get("error", "")).lower()
        self.assertTrue(
            "subscription" in error_str or "inactive" in error_str or "past_due" in error_str
        )

        # Read operations should still work
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_suspended_tenant_blocks_mutations(self):
        """Test that SUSPENDED tenant blocks mutations"""
        # Suspend tenant
        self.tenant.status = TenantStatus.SUSPENDED
        self.tenant.save()

        # Try to create asset (should be blocked)
        response = self.client.post(
            "/api/v1/assets/",
            {
                "key": "suspended-asset",
                "name": "Suspended Asset",
                "status": AssetStatus.ACTIVE.value,
            },
            format="json",
        )

        # Should return 403 with tenant_suspended
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        data = get_response_data(response) or {}
        error_str = str(data.get("error", "")).lower()
        self.assertTrue("tenant" in error_str or "suspended" in error_str)

        # Read operations should still work even for suspended tenants
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
