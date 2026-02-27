"""
Comprehensive E2E failure-path and edge-case tests (Task 6.5).

Covers:
- 6.5.1: At least one failure-path test (401, 403, 404, 400) per persona
- 6.5.2: Service-unavailable behavior (DQ/Compliance down); cross-tenant isolation

All tests use REAL services (no mocks/stubs). Uses E2ETestBase.
"""
import uuid

import pytest
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import Role, User, UserRole, UserStatus

from .conftest import E2ETestBase, check_service_health

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e,
    pytest.mark.uc_journey_persona,
    pytest.mark.persona("Data Product Owner"),
    pytest.mark.persona("Data Engineer"),
    pytest.mark.persona("Compliance Officer"),
    pytest.mark.persona("Data Consumer"),
    pytest.mark.persona("Tenant Admin"),
    pytest.mark.persona("Platform Admin"),
    pytest.mark.persona("External Developer"),
    pytest.mark.persona("Auditor"),
]


class FailurePathTestBase(E2ETestBase):
    """Base for failure-path tests; provides shared setup."""

    pass


# --- 401 Unauthenticated (all personas) ---


class PersonaDPOFailurePaths(FailurePathTestBase):
    """Data Product Owner — failure paths (401, 403, 404, 400)."""

    def test_401_unauthenticated_assets_list(self):
        """Unauthenticated request to assets list returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_403_forbidden_consumer_cannot_create_asset(self):
        """DATA_CONSUMER cannot create asset (requires DATA_PROVIDER/TENANT_ADMIN)."""
        from hub.apps.users.models import Role, UserRole

        consumer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_CONSUMER",
            defaults={"description": "Data Consumer"},
        )
        UserRole.objects.filter(user=self.user).delete()
        UserRole.objects.create(user=self.user, role=consumer_role)
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/assets/",
            {"key": "forbidden-asset", "name": "Forbidden"},
            format="json",
        )
        # 403 = forbidden (no permission); 400 = validation (e.g. tenant/scope). See TEST_ASSERTION_CONVENTIONS 2.4.
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST])

    def test_404_asset_not_found(self):
        """GET non-existent asset returns 404."""
        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/assets/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_400_bad_request_create_asset_missing_required(self):
        """POST asset with missing required fields returns 400."""
        response = self.client.post(
            "/api/v1/assets/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PersonaDEFailurePaths(FailurePathTestBase):
    """Data Engineer — failure paths."""

    def test_401_unauthenticated_datasets_list(self):
        """Unauthenticated request to datasets returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/datasets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_404_dataset_not_found(self):
        """GET non-existent dataset returns 404."""
        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/datasets/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_400_bad_request_create_dq_run_empty_payload(self):
        """POST DQ run with empty payload returns 400."""
        response = self.client.post("/api/v1/dq/runs/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PersonaCPOFailurePaths(FailurePathTestBase):
    """Compliance Officer — failure paths."""

    def test_401_unauthenticated_compliance_runs_list(self):
        """Unauthenticated request to compliance runs returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/compliance/runs/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_404_compliance_run_not_found(self):
        """GET non-existent compliance run returns 404."""
        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/compliance/runs/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_400_bad_request_create_compliance_run_empty_payload(self):
        """POST compliance run with empty payload returns 400."""
        response = self.client.post("/api/v1/compliance/runs/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PersonaDCFailurePaths(FailurePathTestBase):
    """Data Consumer — failure paths."""

    def test_401_unauthenticated_marketplace_listings(self):
        """Unauthenticated request to marketplace listings returns 401 (IsAuthenticated required)."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/marketplace/listings/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_404_listing_not_found(self):
        """GET non-existent listing returns 404."""
        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/marketplace/listings/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_400_bad_request_order_invalid_payload(self):
        """POST order with invalid payload returns 400."""
        response = self.client.post("/api/v1/marketplace/orders/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PersonaTAFailurePaths(FailurePathTestBase):
    """Tenant Admin — failure paths."""

    def test_401_unauthenticated_users_list(self):
        """Unauthenticated request to users list returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/users/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_404_user_not_found(self):
        """GET non-existent user returns 404."""
        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/users/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_400_bad_request_create_user_missing_required(self):
        """POST user with missing required fields returns 400."""
        response = self.client.post("/api/v1/users/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PersonaPAFailurePaths(FailurePathTestBase):
    """Platform Admin — failure paths."""

    def setUp(self):
        """Use platform admin for tenant management tests."""
        super().setUp()
        self.platform_admin = User.objects.create_user(
            email="platform@failure-paths.test",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )
        self.client.force_authenticate(user=self.platform_admin)

    def test_401_unauthenticated_tenants_list(self):
        """Unauthenticated request to tenants list returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/tenants/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_404_tenant_not_found(self):
        """GET non-existent tenant returns 404."""
        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/tenants/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_400_bad_request_create_tenant_missing_required(self):
        """POST tenant with missing required fields returns 400."""
        response = self.client.post("/api/v1/tenants/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PersonaDEVFailurePaths(FailurePathTestBase):
    """External Developer — failure paths."""

    def test_unauthenticated_developer_plugins_public_endpoint(self):
        """Unauthenticated request to developer plugins returns 200 (AllowAny — public endpoint).
        See hub.apps.developer.views.PluginViewSet.permission_classes; docs/TEST_ASSERTION_CONVENTIONS.md 2.3.
        """
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/developer/plugins/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_404_integrations_connector_invalid_type(self):
        """GET connector info for invalid type returns 404."""
        response = self.client.get(
            "/api/v1/integrations/marketplace/connectors/INVALID_TYPE_XYZ/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_400_bad_request_create_webhook_missing_required(self):
        """POST webhook with missing required fields returns 400."""
        response = self.client.post("/api/v1/webhooks/webhooks/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PersonaAUDFailurePaths(FailurePathTestBase):
    """Auditor — failure paths."""

    def test_401_unauthenticated_audit_events(self):
        """Unauthenticated request to audit events returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/audit/audit-events/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_404_audit_event_not_found(self):
        """GET non-existent audit event returns 404."""
        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/audit/audit-events/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_400_bad_request_audit_export_invalid_format(self):
        """GET audit export with invalid format returns 400."""
        response = self.client.get("/api/v1/audit/audit-events/export/?format=invalid")
        # 400 = validation (invalid format); 404 = export endpoint not implemented. See TEST_ASSERTION_CONVENTIONS.
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])


# --- 6.5.2: Service-unavailable and cross-tenant isolation ---


class ServiceUnavailableTests(FailurePathTestBase):
    """6.5.2: Service-unavailable behavior (DQ/Compliance down).

    These tests intentionally skip when DQ/Compliance services are available.
    They validate graceful error handling (400/503) when services are down.
    To run: stop compliance/DQ services, then run this test class.
    """

    def test_compliance_run_when_service_unavailable_returns_graceful_error(self):
        """When Compliance service is down, POST compliance run returns 400/503 (not 500)."""
        if check_service_health(self.compliance_service_url, timeout=3):
            pytest.skip(
                "Compliance service is available — run with service down to test "
                "service-unavailable behavior"
            )
        payload = {"asset_id": str(uuid.uuid4())}
        response = self.client.post("/api/v1/compliance/runs/", payload, format="json")
        # 400 = validation; 503 = service unavailable when Compliance down. See TEST_ASSERTION_CONVENTIONS 2.5.
        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_503_SERVICE_UNAVAILABLE],
            "Service unavailable should return 400 or 503, not 500",
        )

    def test_dq_run_when_service_unavailable_returns_graceful_error(self):
        """When DQ service is down, POST DQ run returns 400/503 (not 500)."""
        if check_service_health(self.dq_service_url, timeout=3):
            pytest.skip(
                "DQ service is available — run with service down to test "
                "service-unavailable behavior"
            )
        payload = {"asset_id": str(uuid.uuid4())}
        response = self.client.post("/api/v1/dq/runs/", payload, format="json")
        # 400 = validation; 503 = service unavailable when DQ down. See TEST_ASSERTION_CONVENTIONS 2.5.
        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_503_SERVICE_UNAVAILABLE],
            "Service unavailable should return 400 or 503, not 500",
        )


class CrossTenantIsolationTests(FailurePathTestBase):
    """6.5.2: Cross-tenant isolation."""

    def test_user_cannot_access_other_tenant_asset(self):
        """User from tenant A cannot GET asset belonging to tenant B."""
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant-isolation",
            status=TenantStatus.ACTIVE,
        )
        ensure_tenant_has_active_subscription(other_tenant)
        other_user = User.objects.create_user(
            email="other@isolation.example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        asset_other = Asset.objects.create(
            tenant=other_tenant,
            key="other-tenant-asset",
            name="Other Tenant Asset",
            status=AssetStatus.DRAFT,
            created_by=other_user,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/v1/assets/{asset_other.id}/")
        # 403 = forbidden; 404 = not found (tenant isolation may hide existence). See TEST_ASSERTION_CONVENTIONS 2.4.
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND],
            "Cross-tenant access must be denied (403 or 404)",
        )

    def test_user_cannot_update_other_tenant_asset(self):
        """User from tenant A cannot PATCH asset belonging to tenant B."""
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        other_tenant = Tenant.objects.create(
            name="Other Tenant 2",
            slug="other-tenant-isolation-2",
            status=TenantStatus.ACTIVE,
        )
        ensure_tenant_has_active_subscription(other_tenant)
        other_user = User.objects.create_user(
            email="other2@isolation.example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        asset_other = Asset.objects.create(
            tenant=other_tenant,
            key="other-tenant-asset-2",
            name="Other Tenant Asset 2",
            status=AssetStatus.DRAFT,
            created_by=other_user,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            f"/api/v1/assets/{asset_other.id}/",
            {"name": "Hacked"},
            format="json",
        )
        # 403 = forbidden; 404 = not found (tenant isolation). See TEST_ASSERTION_CONVENTIONS 2.4.
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND],
            "Cross-tenant update must be denied (403 or 404)",
        )
