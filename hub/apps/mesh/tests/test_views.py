"""
Unit tests for Data Mesh Views.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import json
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.auth.models import APIKey
from hub.apps.governance.models import AccessPolicy
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.mesh.models import (
    ComplianceReport,
    DataMeshDomain,
    DomainStatus,
    PolicyApplication,
    PolicyApplicationStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

User = get_user_model()


class DomainViewSetTestCase(TestCase):
    """Base test case for DomainViewSet tests"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
            data_mesh_enabled=True,
        )

        # Create roles
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )

        # Create users
        self.admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Admin User",
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.admin_user, role=self.admin_role)

        self.regular_user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Regular User",
            status=UserStatus.ACTIVE,
        )

        # Create API keys
        admin_key_value = APIKey.generate_key()
        admin_key_hash = APIKey.hash_key(admin_key_value)
        self.admin_api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.admin_user,
            name="Admin API Key",
            key_hash=admin_key_hash,
            scopes=["mesh:write", "mesh:read"],
        )
        self.admin_api_key._plaintext_key = admin_key_value  # Store for use in tests

        user_key_value = APIKey.generate_key()
        user_key_hash = APIKey.hash_key(user_key_value)
        self.user_api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.regular_user,
            name="User API Key",
            key_hash=user_key_hash,
            scopes=["mesh:read"],
        )
        self.user_api_key._plaintext_key = user_key_value  # Store for use in tests

        # Active subscription required so TenantSuspensionMiddleware allows API writes
        ensure_tenant_has_active_subscription(self.tenant)

        # ABAC: create_domain requires an ALLOW policy for DATA_MESH_DOMAIN (default deny)
        AccessPolicy.objects.get_or_create(
            tenant=self.tenant,
            name="Allow Domain Creation (Mesh Views Test)",
            defaults={
                "conditions": {
                    "user": {"tenant_id": str(self.tenant.id)},
                    "resource": {"type": "DATA_MESH_DOMAIN"},
                },
                "effect": "ALLOW",
                "priority": 100,
                "enabled": True,
            },
        )

        # Create test domain
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            description="Test domain description",
            owner=self.admin_user,
            status=DomainStatus.ACTIVE,
            boundaries={"data_products": ["product1"]},
            capabilities={"apis": ["api1"]},
            resource_quota={"storage_gb": 100},
            resource_usage={"storage_gb_used": 50},
        )

    def _authenticate_user(self, api_key):
        """Helper method to authenticate user and set tenant context"""
        # Refresh user from DB to ensure tenant_id is available
        user = api_key.user
        user.refresh_from_db()

        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {api_key._plaintext_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )


class DomainCreationEndpointTest(DomainViewSetTestCase):
    """Test domain creation endpoint"""

    def test_create_domain_success(self):
        """Test successful domain creation"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {
            "name": "New Domain",
            "description": "New domain description",
            "owner_id": str(self.admin_user.id),
            "boundaries": {"data_products": ["product1"]},
            "capabilities": {"apis": ["api1"]},
            "resource_quota": {"storage_gb": 100},
            "status": DomainStatus.ACTIVE,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["name"], "New Domain")
        self.assertEqual(response.data["description"], "New domain description")
        self.assertEqual(response.data["status"], DomainStatus.ACTIVE)

        # Verify domain was created in database
        domain = DataMeshDomain.objects.get(id=response.data["id"])
        self.assertEqual(domain.name, "New Domain")
        self.assertEqual(domain.tenant, self.tenant)
        self.assertEqual(domain.owner, self.admin_user)

    def test_create_domain_without_authentication(self):
        """Test domain creation without authentication"""
        url = reverse("domain-list")
        data = {"name": "New Domain"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_domain_without_permission(self):
        """Test domain creation without proper permissions"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {"name": "New Domain"}

        response = self.client.post(url, data, format="json")

        # User is authenticated (API key) but lacks TENANT_ADMIN role + mesh:write scope → 403
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_domain_duplicate_name(self):
        """Test domain creation with duplicate name"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {
            "name": self.domain.name,  # Duplicate name
            "description": "Duplicate domain",
        }

        response = self.client.post(url, data, format="json")

        # Duplicate name: ConflictError → handle_service_exception → 409
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already exists", response.data.get("detail", ""))

    def test_create_domain_invalid_data(self):
        """Test domain creation with invalid data"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {
            "name": "",  # Empty name
            "resource_quota": {"storage_gb": -10},  # Negative quota
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DomainListingEndpointTest(DomainViewSetTestCase):
    """Test domain listing endpoint"""

    def test_list_domains_success(self):
        """Test successful domain listing"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], self.domain.name)

    def test_list_domains_with_pagination(self):
        """Test domain listing with pagination"""
        # Create additional domains
        for i in range(5):
            DataMeshDomain.objects.create(
                tenant=self.tenant,
                name=f"Domain {i}",
                status=DomainStatus.ACTIVE,
            )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list")
        response = self.client.get(url, {"page_size": 3, "page": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 6)  # 1 original + 5 new
        self.assertEqual(len(response.data["results"]), 3)
        self.assertIsNotNone(response.data["next"])

    def test_list_domains_with_status_filter(self):
        """Test domain listing with status filter"""
        # Create inactive domain
        inactive_domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Inactive Domain",
            status=DomainStatus.INACTIVE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list")
        response = self.client.get(url, {"status": DomainStatus.ACTIVE})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["status"], DomainStatus.ACTIVE)

    def test_list_domains_with_owner_filter(self):
        """Test domain listing with owner filter"""
        # Create domain with different owner
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        other_domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Other Domain",
            owner=other_user,
            status=DomainStatus.ACTIVE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list")
        response = self.client.get(url, {"owner_id": str(self.admin_user.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["owner"], str(self.admin_user.id))

    def test_list_domains_tenant_isolation(self):
        """Test that users can only see domains in their tenant"""
        # Create another tenant and domain
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_domain = DataMeshDomain.objects.create(
            tenant=other_tenant,
            name="Other Tenant Domain",
            status=DomainStatus.ACTIVE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see domains from self.tenant
        domain_ids = [d["id"] for d in response.data["results"]]
        self.assertIn(str(self.domain.id), domain_ids)
        self.assertNotIn(str(other_domain.id), domain_ids)


class DomainRetrieveEndpointTest(DomainViewSetTestCase):
    """Test domain retrieval endpoint"""

    def test_retrieve_domain_success(self):
        """Test successful domain retrieval"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-detail", kwargs={"id": str(self.domain.id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.domain.id))
        self.assertEqual(response.data["name"], self.domain.name)
        self.assertEqual(response.data["description"], self.domain.description)
        self.assertEqual(response.data["status"], self.domain.status)

    def test_retrieve_domain_not_found(self):
        """Test retrieving non-existent domain"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        import uuid

        url = reverse("domain-detail", kwargs={"id": str(uuid.uuid4())})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_domain_tenant_isolation(self):
        """Test that users can only retrieve domains from their tenant"""
        # Create another tenant and domain
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_domain = DataMeshDomain.objects.create(
            tenant=other_tenant,
            name="Other Tenant Domain",
            status=DomainStatus.ACTIVE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-detail", kwargs={"id": str(other_domain.id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DomainUpdateEndpointTest(DomainViewSetTestCase):
    """Test domain update endpoint"""

    def test_update_domain_success(self):
        """Test successful domain update"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-detail", kwargs={"id": str(self.domain.id)})
        data = {
            "name": "Updated Domain",
            "description": "Updated description",
            "status": DomainStatus.INACTIVE,
        }

        response = self.client.put(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Domain")
        self.assertEqual(response.data["description"], "Updated description")
        self.assertEqual(response.data["status"], DomainStatus.INACTIVE)

        # Verify domain was updated in database
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.name, "Updated Domain")
        self.assertEqual(self.domain.status, DomainStatus.INACTIVE)

    def test_update_domain_without_permission(self):
        """Test domain update without proper permissions"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-detail", kwargs={"id": str(self.domain.id)})
        data = {"name": "Updated Domain"}

        response = self.client.put(url, data, format="json")

        # User is authenticated (API key) but lacks TENANT_ADMIN role + mesh:write scope → 403
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DomainDeleteEndpointTest(DomainViewSetTestCase):
    """Test domain deletion endpoint"""

    def test_delete_domain_success(self):
        """Test successful domain deletion"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-detail", kwargs={"id": str(self.domain.id)})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify domain was deleted
        self.assertFalse(DataMeshDomain.objects.filter(id=self.domain.id).exists())

    def test_delete_domain_without_permission(self):
        """Test domain deletion without proper permissions"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-detail", kwargs={"id": str(self.domain.id)})
        response = self.client.delete(url)

        # User is authenticated (API key) but lacks TENANT_ADMIN role + mesh:write scope → 403
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify domain was not deleted
        self.assertTrue(DataMeshDomain.objects.filter(id=self.domain.id).exists())


class TransferOwnershipEndpointTest(DomainViewSetTestCase):
    """Test transfer ownership endpoint"""

    def test_transfer_ownership_success(self):
        """Test successful ownership transfer"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-transfer-ownership", kwargs={"id": str(self.domain.id)})
        data = {"new_owner_id": str(self.regular_user.id)}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["owner"], str(self.regular_user.id))

        # Verify ownership was transferred
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.owner, self.regular_user)

    def test_transfer_ownership_remove_owner(self):
        """Test removing owner (setting to None)"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-transfer-ownership", kwargs={"id": str(self.domain.id)})
        data = {"new_owner_id": None}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["owner"])

        # Verify owner was removed
        self.domain.refresh_from_db()
        self.assertIsNone(self.domain.owner)

    def test_transfer_ownership_without_permission(self):
        """Test ownership transfer without proper permissions"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-transfer-ownership", kwargs={"id": str(self.domain.id)})
        data = {"new_owner_id": str(self.regular_user.id)}

        response = self.client.post(url, data, format="json")

        # User is authenticated (API key) but lacks TENANT_ADMIN role + mesh:write scope → 403
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DomainAnalyticsEndpointTest(DomainViewSetTestCase):
    """Test domain analytics endpoint"""

    def test_get_analytics_success(self):
        """Test successful analytics retrieval"""
        # Create policy application
        from hub.apps.governance.models import AccessPolicy

        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            enabled=True,
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
        )
        PolicyApplication.objects.create(
            domain=self.domain,
            policy=policy,
            applied_by=self.admin_user,
            status=PolicyApplicationStatus.APPLIED,
        )

        # Create compliance report
        ComplianceReport.objects.create(
            domain=self.domain,
            compliance_status="COMPLIANT",
            violations={"items": []},
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-analytics", kwargs={"id": str(self.domain.id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["domain_id"], str(self.domain.id))
        self.assertEqual(response.data["domain_name"], self.domain.name)
        self.assertIn("total_policies", response.data)
        self.assertIn("applied_policies", response.data)
        self.assertIn("compliance_status", response.data)
        self.assertIn("resource_usage_percentages", response.data)

    def test_get_analytics_without_authentication(self):
        """Test analytics retrieval without authentication"""
        url = reverse("domain-analytics", kwargs={"id": str(self.domain.id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DomainManagementIntegrationTest(DomainViewSetTestCase):
    """Integration tests for domain management API"""

    def test_full_crud_workflow(self):
        """Test complete CRUD workflow"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        # Create
        url = reverse("domain-list")
        data = {
            "name": "CRUD Test Domain",
            "description": "Testing CRUD operations",
            "status": DomainStatus.ACTIVE,
        }
        create_response = self.client.post(url, data, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        domain_id = create_response.data["id"]

        # Read
        url = reverse("domain-detail", kwargs={"id": domain_id})
        read_response = self.client.get(url)
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(read_response.data["name"], "CRUD Test Domain")

        # Update
        update_data = {
            "name": "Updated CRUD Domain",
            "description": "Updated description",
            "status": DomainStatus.INACTIVE,
        }
        update_response = self.client.put(url, update_data, format="json")
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["name"], "Updated CRUD Domain")

        # Delete
        delete_response = self.client.delete(url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        verify_response = self.client.get(url)
        self.assertEqual(verify_response.status_code, status.HTTP_404_NOT_FOUND)


class DomainE2ETest(DomainViewSetTestCase):
    """End-to-end tests for domain CRUD operations"""

    def test_e2e_domain_lifecycle(self):
        """Test complete domain lifecycle"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        # 1. Create domain
        url = reverse("domain-list")
        data = {
            "name": "E2E Test Domain",
            "description": "End-to-end test domain",
            "owner_id": str(self.admin_user.id),
            "boundaries": {"data_products": ["product1", "product2"]},
            "capabilities": {"apis": ["api1"]},
            "resource_quota": {"storage_gb": 200, "compute_hours": 100},
            "status": DomainStatus.ACTIVE,
        }
        create_response = self.client.post(url, data, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        domain_id = create_response.data["id"]

        # 2. List domains and verify it appears
        list_response = self.client.get(url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        domain_ids = [d["id"] for d in list_response.data["results"]]
        self.assertIn(domain_id, domain_ids)

        # 3. Get domain details
        detail_url = reverse("domain-detail", kwargs={"id": domain_id})
        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["name"], "E2E Test Domain")
        self.assertEqual(detail_response.data["resource_quota"]["storage_gb"], 200)

        # 4. Transfer ownership
        transfer_url = reverse("domain-transfer-ownership", kwargs={"id": domain_id})
        transfer_data = {"new_owner_id": str(self.regular_user.id)}
        transfer_response = self.client.post(transfer_url, transfer_data, format="json")
        self.assertEqual(transfer_response.status_code, status.HTTP_200_OK)
        self.assertEqual(transfer_response.data["owner"], str(self.regular_user.id))

        # 5. Get analytics
        analytics_url = reverse("domain-analytics", kwargs={"id": domain_id})
        analytics_response = self.client.get(analytics_url)
        self.assertEqual(analytics_response.status_code, status.HTTP_200_OK)
        self.assertEqual(analytics_response.data["domain_id"], domain_id)
        self.assertIn("resource_usage_percentages", analytics_response.data)

        # 6. Update domain
        update_data = {
            "name": "Updated E2E Domain",
            "description": "Updated description",
            "status": DomainStatus.INACTIVE,
        }
        update_response = self.client.put(detail_url, update_data, format="json")
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["name"], "Updated E2E Domain")
        self.assertEqual(update_response.data["status"], DomainStatus.INACTIVE)

        # 7. Delete domain
        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        # 8. Verify domain is deleted
        verify_response = self.client.get(detail_url)
        self.assertEqual(verify_response.status_code, status.HTTP_404_NOT_FOUND)


class PolicyApplicationEndpointTest(DomainViewSetTestCase):
    """Test policy application endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create access policy
        from hub.apps.governance.models import AccessPolicy

        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            description="Test policy description",
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
            enabled=True,
        )

    def test_apply_policy_success(self):
        """Test successful policy application"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-apply-policy", kwargs={"id": str(self.domain.id)})
        data = {"policy_id": str(self.policy.id), "overrides": {"priority": 50}}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["policy_id"], str(self.policy.id))
        self.assertEqual(response.data["status"], PolicyApplicationStatus.APPLIED)
        self.assertIsNotNone(response.data["id"])

        # Verify policy application was created
        policy_app = PolicyApplication.objects.get(id=response.data["id"])
        self.assertEqual(policy_app.domain, self.domain)
        self.assertEqual(policy_app.policy, self.policy)
        self.assertEqual(policy_app.status, PolicyApplicationStatus.APPLIED)

    def test_apply_policy_without_permission(self):
        """Test policy application without proper permissions"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-apply-policy", kwargs={"id": str(self.domain.id)})
        data = {"policy_id": str(self.policy.id)}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_apply_policy_invalid_policy(self):
        """Test policy application with invalid policy ID"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-apply-policy", kwargs={"id": str(self.domain.id)})
        data = {"policy_id": "00000000-0000-0000-0000-000000000000"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_policies_success(self):
        """Test successful policy listing"""
        # Create policy applications
        policy_app1 = PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.admin_user,
            status=PolicyApplicationStatus.APPLIED,
        )

        # Create another policy
        from hub.apps.governance.models import AccessPolicy

        policy2 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy 2",
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
            enabled=True,
        )
        policy_app2 = PolicyApplication.objects.create(
            domain=self.domain,
            policy=policy2,
            applied_by=self.admin_user,
            status=PolicyApplicationStatus.APPLIED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list-policies", kwargs={"id": str(self.domain.id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_list_policies_with_status_filter(self):
        """Test policy listing with status filter"""
        # Create policy applications with different statuses
        policy_app1 = PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.admin_user,
            status=PolicyApplicationStatus.APPLIED,
        )
        policy_app2 = PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.admin_user,
            status=PolicyApplicationStatus.PENDING,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list-policies", kwargs={"id": str(self.domain.id)})
        response = self.client.get(url, {"status": PolicyApplicationStatus.APPLIED})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["status"], PolicyApplicationStatus.APPLIED)

    def test_remove_policy_success(self):
        """Test successful policy removal"""
        # Create policy application
        policy_app = PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.admin_user,
            status=PolicyApplicationStatus.APPLIED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse(
            "domain-remove-policy",
            kwargs={"id": str(self.domain.id), "policy_id": str(self.policy.id)},
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], PolicyApplicationStatus.REVOKED)

        # Verify policy application was revoked
        policy_app.refresh_from_db()
        self.assertEqual(policy_app.status, PolicyApplicationStatus.REVOKED)

    def test_remove_policy_without_permission(self):
        """Test policy removal without proper permissions"""
        # Create policy application
        policy_app = PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.admin_user,
            status=PolicyApplicationStatus.APPLIED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse(
            "domain-remove-policy",
            kwargs={"id": str(self.domain.id), "policy_id": str(self.policy.id)},
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_remove_policy_not_found(self):
        """Test removing non-existent policy"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse(
            "domain-remove-policy",
            kwargs={"id": str(self.domain.id), "policy_id": "00000000-0000-0000-0000-000000000000"},
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ComplianceCheckEndpointTest(DomainViewSetTestCase):
    """Test compliance check endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create access policy and application
        from hub.apps.governance.models import AccessPolicy

        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
            enabled=True,
        )
        self.policy_app = PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.admin_user,
            status=PolicyApplicationStatus.APPLIED,
        )

    def test_check_compliance_success(self):
        """Test successful compliance check"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-check-compliance", kwargs={"id": str(self.domain.id)})
        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("compliance_status", response.data)
        self.assertIn("violations", response.data)
        self.assertIsNotNone(response.data["id"])

        # Verify compliance report was created
        compliance_report = ComplianceReport.objects.get(id=response.data["id"])
        self.assertEqual(compliance_report.domain, self.domain)

    def test_check_compliance_with_asset(self):
        """Test compliance check with asset ID"""
        # Create asset
        from hub.apps.assets.models import Asset

        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            description="Test asset",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-check-compliance", kwargs={"id": str(self.domain.id)})
        data = {"asset_id": str(asset.id)}
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["asset_id"], str(asset.id))

    def test_check_compliance_without_permission(self):
        """Test compliance check without proper permissions"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-check-compliance", kwargs={"id": str(self.domain.id)})
        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_compliance_reports_success(self):
        """Test successful compliance report listing"""
        # Create compliance reports
        report1 = ComplianceReport.objects.create(
            domain=self.domain,
            compliance_status="COMPLIANT",
            violations={"items": []},
        )
        report2 = ComplianceReport.objects.create(
            domain=self.domain,
            compliance_status="NON_COMPLIANT",
            violations={"items": [{"type": "TEST_VIOLATION"}]},
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list-compliance-reports", kwargs={"id": str(self.domain.id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_list_compliance_reports_with_status_filter(self):
        """Test compliance report listing with status filter"""
        # Create compliance reports with different statuses
        report1 = ComplianceReport.objects.create(
            domain=self.domain,
            compliance_status="COMPLIANT",
            violations={"items": []},
        )
        report2 = ComplianceReport.objects.create(
            domain=self.domain,
            compliance_status="NON_COMPLIANT",
            violations={"items": [{"type": "TEST_VIOLATION"}]},
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list-compliance-reports", kwargs={"id": str(self.domain.id)})
        response = self.client.get(url, {"status": "COMPLIANT"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["compliance_status"], "COMPLIANT")

    def test_get_compliance_report_success(self):
        """Test successful compliance report retrieval"""
        # Create compliance report
        report = ComplianceReport.objects.create(
            domain=self.domain,
            compliance_status="COMPLIANT",
            violations={"items": []},
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse(
            "domain-get-compliance-report",
            kwargs={"id": str(self.domain.id), "report_id": str(report.id)},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(report.id))
        self.assertEqual(response.data["compliance_status"], "COMPLIANT")

    def test_get_compliance_report_not_found(self):
        """Test retrieving non-existent compliance report"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse(
            "domain-get-compliance-report",
            kwargs={"id": str(self.domain.id), "report_id": "00000000-0000-0000-0000-000000000000"},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FederatedGovernanceIntegrationTest(DomainViewSetTestCase):
    """Integration tests for federated governance API"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create access policies
        from hub.apps.governance.models import AccessPolicy

        self.policy1 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Policy 1",
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
            enabled=True,
        )
        self.policy2 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Policy 2",
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
            enabled=True,
        )

    def test_full_governance_workflow(self):
        """Test complete federated governance workflow"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        # 1. Apply first policy
        apply_url = reverse("domain-apply-policy", kwargs={"id": str(self.domain.id)})
        apply_response = self.client.post(
            apply_url, {"policy_id": str(self.policy1.id)}, format="json"
        )
        self.assertEqual(apply_response.status_code, status.HTTP_201_CREATED)
        policy_app1_id = apply_response.data["id"]

        # 2. Apply second policy with overrides
        apply_response2 = self.client.post(
            apply_url,
            {"policy_id": str(self.policy2.id), "overrides": {"priority": 50}},
            format="json",
        )
        self.assertEqual(apply_response2.status_code, status.HTTP_201_CREATED)

        # 3. List policies
        list_url = reverse("domain-list-policies", kwargs={"id": str(self.domain.id)})
        list_response = self.client.get(list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 2)

        # 4. Check compliance
        check_url = reverse("domain-check-compliance", kwargs={"id": str(self.domain.id)})
        check_response = self.client.post(check_url, {}, format="json")
        self.assertEqual(check_response.status_code, status.HTTP_200_OK)
        self.assertIn("compliance_status", check_response.data)

        # 5. List compliance reports
        reports_url = reverse("domain-list-compliance-reports", kwargs={"id": str(self.domain.id)})
        reports_response = self.client.get(reports_url)
        self.assertEqual(reports_response.status_code, status.HTTP_200_OK)
        self.assertEqual(reports_response.data["count"], 1)

        # 6. Get specific compliance report
        report_id = check_response.data["id"]
        get_report_url = reverse(
            "domain-get-compliance-report",
            kwargs={"id": str(self.domain.id), "report_id": report_id},
        )
        get_report_response = self.client.get(get_report_url)
        self.assertEqual(get_report_response.status_code, status.HTTP_200_OK)
        self.assertEqual(get_report_response.data["id"], report_id)

        # 7. Remove first policy
        remove_url = reverse(
            "domain-remove-policy",
            kwargs={"id": str(self.domain.id), "policy_id": str(self.policy1.id)},
        )
        remove_response = self.client.delete(remove_url)
        self.assertEqual(remove_response.status_code, status.HTTP_200_OK)
        self.assertEqual(remove_response.data["status"], PolicyApplicationStatus.REVOKED)

        # 8. Verify policy was removed
        list_response2 = self.client.get(list_url, {"status": PolicyApplicationStatus.APPLIED})
        self.assertEqual(list_response2.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response2.data["count"], 1)


class DomainViewSetEdgeCasesTest(DomainViewSetTestCase):
    """Test edge cases for domain views"""

    def test_create_domain_with_very_long_name(self):
        """Test domain creation with very long name"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {"name": "A" * 300}  # Exceeds max_length

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_domain_with_special_characters(self):
        """Test domain creation with special characters in name"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {"name": "Domain!@#$%^&*()"}

        response = self.client.post(url, data, format="json")
        # Special characters are allowed in domain names — no serializer/model restriction
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Domain!@#$%^&*()")

    def test_create_domain_with_unicode_name(self):
        """Test domain creation with unicode characters"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {"name": "ドメイン测试"}

        response = self.client.post(url, data, format="json")
        # Unicode is allowed in domain names
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "ドメイン测试")

    def test_create_domain_with_null_boundaries(self):
        """Test domain creation with null boundaries"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {"name": "Domain with Null Boundaries", "boundaries": None}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_domain_with_empty_boundaries(self):
        """Test domain creation with empty boundaries"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {"name": "Domain with Empty Boundaries", "boundaries": {}}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_domain_with_large_resource_quota(self):
        """Test domain creation with very large resource quota"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {"name": "Domain with Large Quota", "resource_quota": {"storage_gb": 999999999999}}

        response = self.client.post(url, data, format="json")
        # Quota exceeds tenant plan limit — 400 with quota violation error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quota", response.data.get("detail", "").lower())

    def test_create_domain_with_zero_resource_quota(self):
        """Test domain creation with zero resource quota"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {"name": "Domain with Zero Quota", "resource_quota": {"storage_gb": 0}}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_domain_with_invalid_owner_id_format(self):
        """Test domain creation with invalid owner ID format"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {"name": "Domain with Invalid Owner", "owner_id": "not-a-uuid"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_domain_with_nonexistent_owner_id(self):
        """Test domain creation with nonexistent owner ID"""
        import uuid

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        data = {"name": "Domain with Nonexistent Owner", "owner_id": str(uuid.uuid4())}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_domain_with_invalid_json(self):
        """Test domain update with invalid JSON in boundaries"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-detail", kwargs={"id": str(self.domain.id)})
        # Send invalid JSON structure
        data = {"boundaries": "not-a-dict"}

        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_domain_with_malformed_data(self):
        """Test domain update with malformed data"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-detail", kwargs={"id": str(self.domain.id)})
        data = {"name": None, "status": "INVALID_STATUS"}  # None is not allowed for name

        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_domains_with_invalid_pagination(self):
        """Test domain listing with invalid pagination parameters"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list")
        response = self.client.get(url, {"page": -1, "page_size": -1})

        # Negative page parameters are rejected as invalid input — 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_domains_with_invalid_status(self):
        """Test domain listing with invalid status filter"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list")
        response = self.client.get(url, {"status": "INVALID_STATUS"})

        # Invalid status filter returns empty queryset — 200 with zero results
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_retrieve_domain_with_invalid_uuid(self):
        """Test retrieving domain with invalid UUID format"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-detail", kwargs={"id": "not-a-uuid"})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transfer_ownership_with_invalid_uuid(self):
        """Test ownership transfer with invalid UUID"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-transfer-ownership", kwargs={"id": str(self.domain.id)})
        data = {"new_owner_id": "not-a-uuid"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transfer_ownership_to_nonexistent_user(self):
        """Test ownership transfer to nonexistent user"""
        import uuid

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-transfer-ownership", kwargs={"id": str(self.domain.id)})
        data = {"new_owner_id": str(uuid.uuid4())}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_policy_with_invalid_policy_id_format(self):
        """Test applying policy with invalid policy ID format"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-apply-policy", kwargs={"id": str(self.domain.id)})
        data = {"policy_id": "not-a-uuid"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_policy_with_invalid_overrides(self):
        """Test applying policy with invalid overrides"""
        from hub.apps.governance.models import AccessPolicy

        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
            enabled=True,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-apply-policy", kwargs={"id": str(self.domain.id)})
        data = {"policy_id": str(policy.id), "overrides": "not-a-dict"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_check_compliance_with_invalid_asset_id_format(self):
        """Test compliance check with invalid asset ID format"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-check-compliance", kwargs={"id": str(self.domain.id)})
        data = {"asset_id": "not-a-uuid"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_analytics_for_nonexistent_domain(self):
        """Test getting analytics for nonexistent domain"""
        import uuid

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-analytics", kwargs={"id": str(uuid.uuid4())})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_domain_twice(self):
        """Test deleting domain twice (idempotency)"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Domain to Delete Twice", status=DomainStatus.ACTIVE
        )
        domain_id = str(domain.id)

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-detail", kwargs={"id": domain_id})

        # First delete
        response1 = self.client.delete(url)
        self.assertEqual(response1.status_code, status.HTTP_204_NO_CONTENT)

        # Second delete - should return 404
        response2 = self.client.delete(url)
        self.assertEqual(response2.status_code, status.HTTP_404_NOT_FOUND)


class DomainViewSetErrorHandlingTest(DomainViewSetTestCase):
    """Test error handling scenarios for domain views"""

    def test_create_domain_service_error_handling(self):
        """Test error handling when service raises exception"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-list")
        # Create domain with invalid tenant_id (cross-tenant access)
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )

        data = {
            "name": "Cross Tenant Domain",
            "tenant_id": str(other_tenant.id),  # Try to create in other tenant
        }

        response = self.client.post(url, data, format="json")
        # Should fail - cannot create domain in other tenant
        self.assertIn(
            response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]
        )

    def test_update_domain_concurrent_modification(self):
        """Test handling concurrent domain modifications"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-detail", kwargs={"id": str(self.domain.id)})

        # Simulate concurrent update by updating domain directly in DB
        self.domain.name = "Concurrent Update"
        self.domain.save()

        # Then try to update via API
        data = {"name": "API Update"}
        response = self.client.put(url, data, format="json")

        # Should succeed - last write wins
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_domains_database_error_simulation(self):
        """Test error handling for database errors"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list")
        # Use invalid filter that might cause database error
        response = self.client.get(url, {"owner_id": "invalid-uuid"})

        # Invalid UUID filter returns empty queryset — 200 with zero results
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_retrieve_domain_database_error(self):
        """Test error handling when retrieving domain fails"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        # Use valid UUID format but non-existent domain
        import uuid

        url = reverse("domain-detail", kwargs={"id": str(uuid.uuid4())})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_transfer_ownership_validation_error(self):
        """Test error handling for ownership transfer validation errors"""
        # Create user in different tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com", password="testpass123", tenant=other_tenant
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-transfer-ownership", kwargs={"id": str(self.domain.id)})
        data = {"new_owner_id": str(other_user.id)}

        response = self.client.post(url, data, format="json")
        # User in different tenant: ValidationError → handle_service_exception → 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tenant", response.data.get("detail", "").lower())

    def test_apply_policy_domain_not_found(self):
        """Test error handling when domain not found for policy application"""
        import uuid

        from hub.apps.governance.models import AccessPolicy

        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
            enabled=True,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-apply-policy", kwargs={"id": str(uuid.uuid4())})
        data = {"policy_id": str(policy.id)}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_apply_policy_policy_not_found(self):
        """Test error handling when policy not found"""
        import uuid

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-apply-policy", kwargs={"id": str(self.domain.id)})
        data = {"policy_id": str(uuid.uuid4())}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_check_compliance_domain_not_found(self):
        """Test error handling when domain not found for compliance check"""
        import uuid

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse("domain-check-compliance", kwargs={"id": str(uuid.uuid4())})
        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_compliance_reports_invalid_filter(self):
        """Test error handling for invalid compliance report filters"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("domain-list-compliance-reports", kwargs={"id": str(self.domain.id)})
        response = self.client.get(url, {"status": "INVALID_STATUS"})

        # Invalid status filter returns 200 with empty results (graceful degradation)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_get_compliance_report_not_found(self):
        """Test error handling when compliance report not found"""
        import uuid

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse(
            "domain-get-compliance-report",
            kwargs={"id": str(self.domain.id), "report_id": str(uuid.uuid4())},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_remove_policy_not_applied(self):
        """Test error handling when removing policy that was never applied"""
        from hub.apps.governance.models import AccessPolicy

        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Never Applied Policy",
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
            enabled=True,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}")

        url = reverse(
            "domain-remove-policy", kwargs={"id": str(self.domain.id), "policy_id": str(policy.id)}
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# =============================================================================
# MeshGovernanceViewSet tests (4 endpoints, previously uncovered)
# =============================================================================


class MeshGovernanceViewSetTest(DomainViewSetTestCase):
    """Tests for the MeshGovernanceViewSet (governance summary, policies,
    compliance, reports endpoints)."""

    def setUp(self):
        super().setUp()
        # Apply a policy so governance endpoints have data to report
        from hub.apps.governance.models import AccessPolicy

        self.gov_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Governance Test Policy",
            conditions={"type": "test"},
            effect="ALLOW",
            enabled=True,
        )
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        self.gov_application = PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.gov_policy,
            applied_by=self.admin_user,
            status=PolicyApplicationStatus.APPLIED,
        )
        from hub.apps.mesh.models import ComplianceReport, MeshComplianceStatus

        self.gov_report = ComplianceReport.objects.create(
            domain=self.domain,
            compliance_status=MeshComplianceStatus.COMPLIANT,
            violations={},
        )

    # -- Governance list --------------------------------------------------

    def test_governance_list_success(self):
        """GET /api/v1/mesh/governance/ returns domain and policy counts."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}"
        )
        url = reverse("mesh-governance-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("domain_count", response.data)
        self.assertEqual(response.data["domain_count"], 1)
        self.assertEqual(response.data["applied_policies_count"], 1)

    def test_governance_list_tenant_isolation(self):
        """Governance list only returns data for the authenticated tenant."""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        DataMeshDomain.objects.create(
            tenant=other_tenant,
            name="Other Tenant Domain",
            status=DomainStatus.ACTIVE,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}"
        )
        url = reverse("mesh-governance-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Domain count should only include this tenant's domains
        self.assertEqual(
            response.data["domain_count"],
            DataMeshDomain.objects.filter(tenant=self.tenant).count(),
        )

    def test_governance_list_unauthenticated(self):
        """Unauthenticated requests to governance endpoint return 401."""
        url = reverse("mesh-governance-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # -- Governance policies ----------------------------------------------

    def test_governance_policies_list(self):
        """GET /api/v1/mesh/governance/policies/ returns applied policies."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}"
        )
        url = reverse("mesh-governance-policies")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)

    def test_governance_policies_tenant_isolation(self):
        """Policies from other tenants are excluded from governance policies list."""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        other_domain = DataMeshDomain.objects.create(
            tenant=other_tenant, name="Other Domain", status=DomainStatus.ACTIVE
        )
        other_policy = AccessPolicy.objects.create(
            tenant=other_tenant,
            name="Other Policy",
            conditions={},
            effect="ALLOW",
            enabled=True,
        )
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        PolicyApplication.objects.create(
            domain=other_domain,
            policy=other_policy,
            applied_by=None,
            status=PolicyApplicationStatus.APPLIED,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}"
        )
        url = reverse("mesh-governance-policies")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # No results should reference the other tenant's domain
        other_domain_ids = {str(other_domain.id)}
        for item in response.data["results"]:
            self.assertNotIn(item["domain_id"], other_domain_ids)

    # -- Governance compliance -------------------------------------------

    def test_governance_compliance_list(self):
        """GET /api/v1/mesh/governance/compliance/ returns compliance summary."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}"
        )
        url = reverse("mesh-governance-compliance")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("domain_count", response.data)
        self.assertIn("compliant_count", response.data)
        self.assertIn("reports", response.data)

    # -- Governance reports ----------------------------------------------

    def test_governance_reports_list(self):
        """GET /api/v1/mesh/governance/reports/ returns compliance reports."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}"
        )
        url = reverse("mesh-governance-reports")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("reports", response.data)
        self.assertEqual(len(response.data["reports"]), 1)

    def test_governance_reports_tenant_isolation(self):
        """Compliance reports from other tenants are excluded."""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        other_domain = DataMeshDomain.objects.create(
            tenant=other_tenant, name="Other Domain", status=DomainStatus.ACTIVE
        )
        from hub.apps.mesh.models import ComplianceReport, MeshComplianceStatus

        ComplianceReport.objects.create(
            domain=other_domain,
            compliance_status=MeshComplianceStatus.COMPLIANT,
            violations={},
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}"
        )
        url = reverse("mesh-governance-reports")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        other_domain_ids = {str(other_domain.id)}
        for item in response.data["reports"]:
            self.assertNotIn(item["domain_id"], other_domain_ids)


# =============================================================================
# Partial update (PATCH) tests — previously uncovered
# =============================================================================


class DomainPartialUpdateEndpointTest(DomainViewSetTestCase):
    """Tests for PATCH (partial_update) on DomainViewSet."""

    def test_partial_update_domain_success(self):
        """PATCH updates only provided fields and returns 200."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}"
        )
        url = reverse("domain-detail", kwargs={"id": str(self.domain.id)})
        response = self.client.patch(
            url, {"description": "Updated via PATCH"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["description"], "Updated via PATCH")
        # Name should remain unchanged
        self.assertEqual(response.data["name"], "Test Domain")

    def test_partial_update_domain_invalid_data(self):
        """PATCH with invalid data returns 400 with error message."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}"
        )
        url = reverse("domain-detail", kwargs={"id": str(self.domain.id)})
        response = self.client.patch(
            url, {"resource_quota": "not-a-dict"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # DRF serializer returns field-level errors; resource_quota is the invalid field
        self.assertIn("resource_quota", response.data)

    def test_partial_update_domain_no_permission(self):
        """PATCH without admin role returns 403."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}"
        )
        url = reverse("domain-detail", kwargs={"id": str(self.domain.id)})
        response = self.client.patch(
            url, {"description": "Nope"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# =============================================================================
# Platform admin bypass tests — previously uncovered
# =============================================================================


class PlatformAdminBypassTest(DomainViewSetTestCase):
    """Tests verifying platform admin tenant-isolation bypass paths."""

    def setUp(self):
        super().setUp()
        # Make admin_user a platform admin
        self.admin_user.is_platform_admin = True
        self.admin_user.save()

        # Create a second tenant with its own domain
        _uid = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.other_domain = DataMeshDomain.objects.create(
            tenant=self.other_tenant,
            name="Other Tenant Domain",
            status=DomainStatus.ACTIVE,
        )

    def test_platform_admin_can_list_all_tenants_domains(self):
        """Platform admin sees domains from all tenants in list."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}"
        )
        url = reverse("domain-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        domain_ids = [item["id"] for item in response.data["results"]]
        self.assertIn(str(self.domain.id), domain_ids)
        self.assertIn(str(self.other_domain.id), domain_ids)

    def test_platform_admin_can_retrieve_other_tenant_domain(self):
        """Platform admin can retrieve a domain from any tenant."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}"
        )
        url = reverse(
            "domain-detail", kwargs={"id": str(self.other_domain.id)}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Other Tenant Domain")


# =============================================================================
# Tenant isolation gaps — policy/compliance operations
# =============================================================================


class PolicyComplianceTenantIsolationTest(DomainViewSetTestCase):
    """Tests for tenant isolation of policy and compliance operations."""

    def setUp(self):
        super().setUp()
        _uid = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.other_domain = DataMeshDomain.objects.create(
            tenant=self.other_tenant,
            name="Other Domain",
            status=DomainStatus.ACTIVE,
        )
        self.other_policy = AccessPolicy.objects.create(
            tenant=self.other_tenant,
            name="Other Policy",
            conditions={},
            effect="ALLOW",
            enabled=True,
        )
        from hub.apps.mesh.models import ComplianceReport, MeshComplianceStatus

        self.other_report = ComplianceReport.objects.create(
            domain=self.other_domain,
            compliance_status=MeshComplianceStatus.COMPLIANT,
            violations={},
        )

    def test_apply_policy_cross_tenant_blocked(self):
        """Applying another tenant's policy fails with 400 (tenant mismatch)."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}"
        )
        url = reverse(
            "domain-apply-policy", kwargs={"id": str(self.domain.id)}
        )
        response = self.client.post(
            url, {"policy_id": str(self.other_policy.id)}, format="json"
        )
        # Policy from another tenant → ValidationError (400)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_policies_tenant_isolation(self):
        """Listing policies only returns policies for the authenticated tenant."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}"
        )
        url = reverse(
            "domain-list-policies", kwargs={"id": str(self.domain.id)}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        other_policy_ids = {str(self.other_policy.id)}
        for item in response.data.get("results", []):
            self.assertNotIn(item.get("policy_id"), other_policy_ids)

    def test_check_compliance_cross_tenant_blocked(self):
        """Checking compliance for another tenant's domain fails with 404."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.admin_api_key._plaintext_key}"
        )
        url = reverse(
            "domain-check-compliance",
            kwargs={"id": str(self.other_domain.id)},
        )
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_compliance_report_tenant_isolation(self):
        """Getting another tenant's compliance report fails with 404."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}"
        )
        url = reverse(
            "domain-get-compliance-report",
            kwargs={
                "id": str(self.domain.id),
                "report_id": str(self.other_report.id),
            },
        )
        response = self.client.get(url)
        # Report exists but belongs to another tenant → 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
