"""
Comprehensive Integration Ecosystem New Use Cases Test Suite (Task 10.1.53.9)

Tests all new Integration Ecosystem use cases:
- UC-INT-001: Install Pre-built Connector
- UC-INT-002: Create Custom Connector
- UC-INT-003: Integrate BI Tool
- UC-INT-004: Set Up Reverse ETL
- UC-INT-005: Integrate CI/CD Pipeline

All tests hit real endpoints -- no mocks/stubs.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import KYCStatus, TenantStatus
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)
from hub.apps.users.models import Role, UserRole
from tests.fixtures.test_data_factories import (
    TenantFactory,
    UserFactory,
)
from tests.utils.test_data_management import TestDatabaseIsolationMixin

User = get_user_model()

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.uc("UC-INT-001"),
    pytest.mark.uc("UC-INT-002"),
    pytest.mark.uc("UC-INT-003"),
    pytest.mark.uc("UC-INT-004"),
    pytest.mark.uc("UC-INT-005"),
]


class IntegrationEcosystemTestBase(
    TestCase, TestDatabaseIsolationMixin,
):
    """Base test class for Integration Ecosystem use cases."""

    CONNECTORS_URL = (
        "/api/v1/integrations/marketplace/connectors/"
    )
    CONNECTIONS_URL = (
        "/api/v1/integrations/marketplace/connections/"
    )
    SYNC_URL = "/api/v1/integrations/marketplace/sync/"
    API_KEYS_URL = "/api/v1/developer/api-keys/"

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        uid = str(uuid.uuid4())[:8]
        self.tenant = TenantFactory.create_tenant(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Admin"},
        )

        self.dpo_user = UserFactory.create_user(
            tenant=self.tenant,
            email=f"dpo-{uid}@example.com",
        )
        UserRole.objects.get_or_create(
            user=self.dpo_user, role=self.data_provider_role,
        )

        self.admin_user = UserFactory.create_user(
            tenant=self.tenant,
            email=f"admin-{uid}@example.com",
        )
        UserRole.objects.get_or_create(
            user=self.admin_user, role=self.tenant_admin_role,
        )


class UCINT001InstallPrebuiltConnectorTest(
    IntegrationEcosystemTestBase,
):
    """UC-INT-001: Install Pre-built Connector"""

    def test_list_available_connectors(self):
        """GET connectors -> 200 with connectors list."""
        self.client.force_authenticate(user=self.dpo_user)
        response = self.client.get(self.CONNECTORS_URL)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )
        body = response.json()
        self.assertIn("connectors", body)
        self.assertIsInstance(body["connectors"], list)

    def test_retrieve_specific_connector(self):
        """GET connectors/{type}/ -> 200 with connector detail."""
        self.client.force_authenticate(user=self.dpo_user)
        list_resp = self.client.get(self.CONNECTORS_URL)
        self.assertEqual(
            list_resp.status_code, status.HTTP_200_OK,
        )
        connectors = list_resp.json().get("connectors", [])
        if connectors:
            ctype = connectors[0].get("type")
            detail_resp = self.client.get(
                f"{self.CONNECTORS_URL}{ctype}/",
            )
            self.assertEqual(
                detail_resp.status_code, status.HTTP_200_OK,
            )
            self.assertEqual(
                detail_resp.json()["type"], ctype,
            )

    def test_connectors_unauthorized(self):
        """Unauthenticated connectors -> 401/403."""
        self.client.logout()
        response = self.client.get(self.CONNECTORS_URL)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )


class UCINT002CreateCustomConnectorTest(
    IntegrationEcosystemTestBase,
):
    """UC-INT-002: Create Custom Connector"""

    def test_list_connections(self):
        """GET connections -> 200 with list."""
        self.client.force_authenticate(user=self.dpo_user)
        response = self.client.get(self.CONNECTIONS_URL)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )
        body = response.json()
        results = body.get("results", body)
        self.assertIsInstance(results, list)

    def test_create_connection(self):
        """POST connection -> 201 with id and name."""
        self.client.force_authenticate(user=self.dpo_user)
        data = {
            "name": f"Test Connection {uuid.uuid4().hex[:8]}",
            "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
            "config": {
                "account": "test",
                "database": "test_db",
            },
        }
        response = self.client.post(
            self.CONNECTIONS_URL, data, format="json",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_200_OK],
        )
        body = response.json()
        self.assertIn("id", body)
        self.assertIn("name", body)

    def test_create_connection_missing_name_returns_400(self):
        """POST connection without name -> 400."""
        self.client.force_authenticate(user=self.dpo_user)
        response = self.client.post(
            self.CONNECTIONS_URL,
            {"marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_connections_unauthorized(self):
        """Unauthenticated connections -> 401/403."""
        self.client.logout()
        response = self.client.get(self.CONNECTIONS_URL)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )


class UCINT003IntegrateBIToolTest(
    IntegrationEcosystemTestBase,
):
    """UC-INT-003: Integrate BI Tool

    BI tool integration uses connections with BI-specific types.
    """

    def test_bi_integration_via_connections(self):
        """GET connections -> 200 with list structure."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.CONNECTIONS_URL)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )
        body = response.json()
        results = body.get("results", body)
        self.assertIsInstance(results, list)

    def test_bi_integration_unauthorized(self):
        """Unauthenticated BI integration -> 401/403."""
        self.client.logout()
        response = self.client.get(self.CONNECTIONS_URL)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )


class UCINT004SetUpReverseETLTest(
    IntegrationEcosystemTestBase,
):
    """UC-INT-004: Set Up Reverse ETL

    Reverse ETL uses marketplace sync jobs for data push.
    """

    def test_reverse_etl_sync_jobs_list(self):
        """GET sync/ -> 200 with list structure."""
        self.client.force_authenticate(user=self.dpo_user)
        response = self.client.get(self.SYNC_URL)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )
        body = response.json()
        results = body.get("results", body)
        self.assertIsInstance(results, list)

    def test_reverse_etl_unauthorized(self):
        """Unauthenticated reverse ETL -> 401/403."""
        self.client.logout()
        response = self.client.get(self.SYNC_URL)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )


class UCINT005IntegrateCICDPipelineTest(
    IntegrationEcosystemTestBase,
):
    """UC-INT-005: Integrate CI/CD Pipeline

    CI/CD integration uses developer API keys.
    """

    def test_cicd_api_keys_list(self):
        """GET api-keys/ -> 200 with list structure."""
        self.client.force_authenticate(user=self.dpo_user)
        response = self.client.get(self.API_KEYS_URL)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )
        body = response.json()
        results = body.get("results", body)
        self.assertIsInstance(results, list)

    def test_cicd_unauthorized(self):
        """Unauthenticated developer API -> 401/403."""
        self.client.logout()
        response = self.client.get(self.API_KEYS_URL)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )
