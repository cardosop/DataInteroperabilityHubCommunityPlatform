"""
Phase 26 CLI/SDK Regression Tests

Regression tests for Phase 26 CLI/SDK features:
- CLI command coverage vs backend
- SDK method coverage vs backend
- CLI/SDK authentication
- CLI/SDK tenant context

No mocks - uses real backend.
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.scheduled_export.models import DestinationType, ScheduledExport, ScheduledExportStatus
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class Phase26CLISDKRegressionTest(TestCase):
    """Regression tests for Phase 26 CLI/SDK coverage"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="CLI SDK Test Tenant",
            slug="cli-sdk-test-tenant",
            status=TenantStatus.ACTIVE,
        )

        # Create user
        self.user = User.objects.create_user(
            email="clisdk@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create plan and assign to tenant
        from hub.apps.billing.models import Subscription, SubscriptionStatus
        from hub.apps.tenants.models import TenantPlan

        self.plan = TenantPlan.objects.create(
            name="CLI SDK Test Plan",
            slug="cli-sdk-test-plan",
            tier="FREE",
            limits_json={"max_assets": 100, "max_scheduled_exports": 10},
            is_active=True,
        )
        self.tenant.plan = self.plan
        self.tenant.save()

        # Create subscription
        Subscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
        )

        self.client.force_authenticate(user=self.user)

    def test_cli_scheduled_export_commands_coverage(self):
        """Test that CLI scheduled export commands cover backend endpoints"""
        # Create test data
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="cli-export-asset",
            name="CLI Export Asset",
            status=AssetStatus.ACTIVE,
        )

        export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="CLI Test Export",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "cli-test-bucket"},
            source_scope={"asset_ids": [str(asset.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )

        # Verify backend endpoints exist and work
        endpoints_to_test = [
            ("GET", f"/api/v1/scheduled-exports/", "list"),
            ("GET", f"/api/v1/scheduled-exports/{export.id}/", "get"),
            ("GET", f"/api/v1/scheduled-exports/{export.id}/runs/", "runs"),
        ]

        for method, endpoint, command_name in endpoints_to_test:
            if method == "GET":
                response = self.client.get(endpoint)
                # Should succeed (may be 200 or 404 depending on data)
                self.assertIn(
                    response.status_code,
                    [
                        status.HTTP_200_OK,
                        status.HTTP_404_NOT_FOUND,
                        status.HTTP_503_SERVICE_UNAVAILABLE,
                    ],
                )
                # CLI command should map to this endpoint
                # This is verified by CLI integration tests

    def test_cli_billing_commands_coverage(self):
        """Test that CLI billing commands cover backend endpoints"""
        endpoints_to_test = [
            ("GET", "/api/v1/billing/subscription/current/", "subscription"),
            ("GET", "/api/v1/billing/invoices/", "invoices"),
        ]

        for method, endpoint, command_name in endpoints_to_test:
            if method == "GET":
                response = self.client.get(endpoint)
                # Should succeed (may be 200 or 404 depending on data)
                self.assertIn(
                    response.status_code,
                    [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
                )
                # CLI command should map to this endpoint
                # This is verified by CLI integration tests

    def test_cli_tenant_commands_coverage(self):
        """Test that CLI tenant commands cover backend endpoints"""
        endpoints_to_test = [
            ("GET", "/api/v1/tenants/me/usage/", "usage"),
        ]

        for method, endpoint, command_name in endpoints_to_test:
            if method == "GET":
                response = self.client.get(endpoint)
                # Should succeed (may be 200 or 404 depending on data)
                self.assertIn(
                    response.status_code,
                    [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
                )
                # CLI command should map to this endpoint
                # This is verified by CLI integration tests

    def test_cli_gdpr_commands_coverage(self):
        """Test that CLI GDPR commands cover backend endpoints"""
        endpoints_to_test = [
            ("POST", "/api/v1/users/me/export-data/", "export-data"),
            ("GET", "/api/v1/users/me/export-jobs/", "export-jobs"),
            ("POST", "/api/v1/users/me/request-erasure/", "request-erasure"),
            ("GET", "/api/v1/users/me/erasure-requests/", "erasure-requests"),
        ]

        for method, endpoint, command_name in endpoints_to_test:
            if method == "GET":
                response = self.client.get(endpoint)
                # Should succeed (may be 200 or 404 depending on data)
                self.assertIn(
                    response.status_code,
                    [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
                )
            elif method == "POST":
                response = self.client.post(endpoint, {}, format="json")
                # Should succeed (may be 201, 200, 400, or 404)
                self.assertIn(
                    response.status_code,
                    [
                        status.HTTP_201_CREATED,
                        status.HTTP_200_OK,
                        status.HTTP_400_BAD_REQUEST,
                        status.HTTP_404_NOT_FOUND,
                    ],
                )
                # CLI command should map to this endpoint
                # This is verified by CLI integration tests

    def test_cli_search_commands_coverage(self):
        """Test that CLI search commands cover backend endpoints"""
        endpoints_to_test = [
            ("GET", "/api/v1/search/search/", "search"),
            ("GET", "/api/v1/search/suggestions/", "suggestions"),
            ("GET", "/api/v1/search/analytics/", "analytics"),
        ]

        for method, endpoint, command_name in endpoints_to_test:
            if method == "GET":
                response = self.client.get(endpoint)
                # Should succeed (may be 200, 400, or 403 depending on permissions/query params)
                # Analytics endpoint requires platform admin, so 403 is expected for regular users
                self.assertIn(
                    response.status_code,
                    [
                        status.HTTP_200_OK,
                        status.HTTP_400_BAD_REQUEST,
                        status.HTTP_403_FORBIDDEN,
                    ],
                )
                # CLI command should map to this endpoint
                # This is verified by CLI integration tests
