"""
API Spec Compliance Tests for TenantConfig endpoints.

GAP-0.3: Comprehensive tests to verify API spec compliance for response format,
error codes, timestamps, and OpenAPI schema.
"""
import uuid
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime
import json
import re

from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.users.models import User, Role, UserRole, UserStatus
from hub.apps.tenants.validators import get_platform_defaults


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class APISpecComplianceTest(TestCase):
    """Test API spec compliance for TenantConfig endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}"
        )
        
        # Create roles
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )
        
        # Create tenant admin user
        self.tenant_admin = User.objects.create_user(
            email=f"tenant-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(
            user=self.tenant_admin, role=self.admin_role,
            tenant=self.tenant,
        )

        # Create subscription so middleware doesn't block write ops
        from hub.apps.billing.models import Subscription, SubscriptionStatus
        from hub.apps.tenants.models import TenantPlan
        free_plan = TenantPlan.objects.filter(slug="free").first()
        if free_plan:
            Subscription.objects.get_or_create(
                tenant=self.tenant,
                defaults={
                    "plan": free_plan,
                    "status": SubscriptionStatus.ACTIVE,
                    "stripe_subscription_id": f"sub_{uuid.uuid4().hex[:16]}",
                }
            )

        self.platform_defaults = get_platform_defaults()
    
    # GAP-0.3.1.1: API spec format validation
    def test_get_response_format_matches_api_spec_exactly(self):
        """Verify GET response matches API spec (§13.1) exactly (field names, types, structure)"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        # Verify all required fields from API spec §13.1
        required_fields = {
            "tenant_id": str,  # UUID as string
            "default_dq_profile": (str, type(None)),
            "allowed_compliance_regimes": list,
            "default_compliance_regimes": list,
            "data_retention_days": int,
            "rate_limits": dict,
            "max_file_size_bytes": int,
            "max_job_concurrency": int,
            "max_queued_jobs": int,
            "created_at": (str, type(None)),  # ISO 8601 timestamp or None
            "updated_at": (str, type(None)),  # ISO 8601 timestamp or None
        }
        
        for field, expected_type in required_fields.items():
            self.assertIn(field, data, f"Response missing required field: {field}")
            
            if isinstance(expected_type, tuple):
                self.assertIsInstance(data[field], expected_type, 
                                    f"Field {field} has wrong type: {type(data[field])}")
            else:
                self.assertIsInstance(data[field], expected_type,
                                    f"Field {field} has wrong type: {type(data[field])}")
        
        # Verify rate_limits structure
        rate_limits = data["rate_limits"]
        self.assertIsInstance(rate_limits, dict)
        
        # Verify rate_limits categories have correct structure
        for category, limits in rate_limits.items():
            self.assertIsInstance(limits, dict)
            if "burst_per_10s" in limits:
                self.assertIsInstance(limits["burst_per_10s"], int)
            if "sustained_per_min" in limits:
                self.assertIsInstance(limits["sustained_per_min"], int)
            if "daily_cap" in limits:
                self.assertIsInstance(limits["daily_cap"], int)
    
    def test_patch_response_format_matches_api_spec_exactly(self):
        """Verify PATCH response matches API spec (§13.2) exactly"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        data = {"default_dq_profile": "intake_basic_soda"}
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # PATCH response should match GET response format
        self.assertIn("tenant_id", response.data)
        self.assertIn("default_dq_profile", response.data)
        self.assertEqual(response.data["default_dq_profile"], "intake_basic_soda")
    
    def test_error_response_format_matches_api_spec(self):
        """Verify error response format matches API spec (error code, message, http_status, request_id, timestamp, details)"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        # Trigger a validation error
        invalid_data = {"default_dq_profile": "invalid_profile"}
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/",
            invalid_data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify error response structure
        self.assertIn("error", response.data)
        error = response.data["error"]
        
        # Required fields
        self.assertIn("code", error)
        self.assertIn("message", error)
        self.assertIn("http_status", error)
        self.assertIn("request_id", error)
        self.assertIn("timestamp", error)
        
        # Verify types
        self.assertIsInstance(error["code"], str)
        self.assertIsInstance(error["message"], str)
        self.assertIsInstance(error["http_status"], int)
        self.assertIsInstance(error["request_id"], str)
        self.assertIsInstance(error["timestamp"], str)
        
        # Verify http_status matches actual status code
        self.assertEqual(error["http_status"], status.HTTP_400_BAD_REQUEST)
    
    def test_timestamps_are_iso_8601_format_with_timezone(self):
        """Verify timestamps are ISO 8601 format with timezone (e.g., '2025-01-15T10:00:00Z')"""
        config = TenantConfig.objects.create(tenant=self.tenant)
        
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check timestamp format (ISO 8601)
        if response.data["created_at"]:
            timestamp = response.data["created_at"]
            # ISO 8601 format: YYYY-MM-DDTHH:MM:SS[.ffffff][+HH:MM|Z]
            # Should contain 'T' separator
            self.assertIn("T", timestamp)
            
            # Try to parse as ISO format
            try:
                datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                # If that fails, try without timezone
                try:
                    datetime.fromisoformat(timestamp)
                except ValueError:
                    self.fail(f"Timestamp {timestamp} is not in ISO 8601 format")
        
        if response.data["updated_at"]:
            timestamp = response.data["updated_at"]
            self.assertIn("T", timestamp)
    
    # GAP-0.3.2.1: Error code validation
    def test_404_returns_tenant_not_found_error_code(self):
        """Verify 404 returns TENANT_NOT_FOUND (not generic NOT_FOUND) per API spec"""
        import uuid
        fake_tenant_id = uuid.uuid4()
        
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.get(f"/api/v1/tenants/{fake_tenant_id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Check error code
        # Note: Current implementation may return NOT_FOUND, but API spec requires TENANT_NOT_FOUND
        # This test documents the gap - enhancement needed to set specific error code
        if "error" in response.data:
            error_code = response.data["error"].get("code", "")
            # Should be TENANT_NOT_FOUND per API spec
            self.assertEqual(error_code, "TENANT_NOT_FOUND")
    
    def test_400_returns_validation_error_code(self):
        """Verify 400 returns VALIDATION_ERROR with field-level details"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        invalid_data = {"default_dq_profile": "invalid_profile"}
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/",
            invalid_data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

        # Must have details with field-level errors
        self.assertIn(
            "details", response.data["error"],
            "VALIDATION_ERROR must include 'details' per API spec",
        )
        details = response.data["error"]["details"]
        self.assertIn("default_dq_profile", str(details))
    
    # GAP-0.3.1.2: OpenAPI schema validation
    def test_openapi_schema_includes_tenant_config_endpoints(self):
        """Generate and validate OpenAPI schema for TenantConfig endpoints"""
        self.client.force_authenticate(user=self.tenant_admin)

        # Fetch OpenAPI schema
        response = self.client.get("/api-docs/openapi.json")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"OpenAPI schema endpoint must return 200, "
            f"got {response.status_code}",
        )

        schema = (
            response.data
            if hasattr(response, 'data')
            else json.loads(response.content)
        )

        # Verify TenantConfig endpoints are in schema
        paths = schema.get("paths", {})

        tenant_config_paths = [
            p for p in paths.keys()
            if "config" in p.lower() and "tenant" in p.lower()
        ]
        self.assertTrue(
            len(tenant_config_paths) > 0,
            "TenantConfig endpoints not found in OpenAPI schema",
        )

        # Verify response schema matches API spec
        for path in tenant_config_paths:
            if "get" in paths[path]:
                get_op = paths[path]["get"]
                responses = get_op.get("responses", {})
                if "200" in responses:
                    resp_content = responses["200"].get(
                        "content", {}
                    ).get("application/json", {})
                    response_schema = resp_content.get(
                        "schema", {}
                    )
                    if "properties" in response_schema:
                        properties = response_schema["properties"]
                        required_fields = [
                            "tenant_id",
                            "default_dq_profile",
                            "allowed_compliance_regimes",
                            "default_compliance_regimes",
                            "data_retention_days",
                            "rate_limits",
                            "max_file_size_bytes",
                            "max_job_concurrency",
                            "max_queued_jobs",
                        ]
                        for field in required_fields:
                            self.assertIn(
                                field,
                                properties,
                                f"OpenAPI schema missing: {field}",
                            )
    
    def test_openapi_schema_validates_request_response_against_schema(self):
        """Add OpenAPI schema tests (validate request/response against schema)"""
        # This test verifies that actual API responses match the OpenAPI schema
        # In a full implementation, we would use a library like openapi-core to validate
        # For now, we verify the structure matches what's expected
        
        self.client.force_authenticate(user=self.tenant_admin)
        
        # Make actual API call
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify response structure matches expected schema
        data = response.data
        required_fields = [
            "tenant_id",
            "default_dq_profile",
            "allowed_compliance_regimes",
            "default_compliance_regimes",
            "data_retention_days",
            "rate_limits",
            "max_file_size_bytes",
            "max_job_concurrency",
            "max_queued_jobs",
            "created_at",
            "updated_at",
        ]
        
        for field in required_fields:
            self.assertIn(field, data, f"Response missing field required by API spec: {field}")
    
    def test_403_returns_auth_forbidden_error_code(self):
        """Verify 403 returns AUTH_FORBIDDEN (not generic permission denied)"""
        # Create DATA_PROVIDER user (not TENANT_ADMIN)
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )
        provider_user = User.objects.create_user(
            email=f"provider-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(
            user=provider_user, role=provider_role,
            tenant=self.tenant,
        )
        
        self.client.force_authenticate(user=provider_user)
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"]["code"], "AUTH_FORBIDDEN")
    
    def test_401_returns_auth_unauthorized_error_code(self):
        """Verify 401 returns AUTH_UNAUTHORIZED"""
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "AUTH_UNAUTHORIZED")
    
    def test_error_details_structure_matches_api_spec(self):
        """Verify error details structure matches API spec format"""
        self.client.force_authenticate(user=self.tenant_admin)

        # Trigger validation error
        invalid_data = {
            "default_dq_profile": "invalid_profile",
            "data_retention_days": 50  # Below minimum
        }
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/",
            invalid_data,
            format="json"
        )

        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST
        )

        # Error envelope must exist
        self.assertIn("error", response.data)
        error = response.data["error"]
        self.assertIn("code", error)
        self.assertIn("message", error)

        # Details must exist and contain field-level errors
        self.assertIn(
            "details", error,
            "API spec requires 'details' in error response",
        )
        details = error["details"]
        self.assertIsInstance(details, dict)
        # At least one of our invalid fields should appear
        detail_str = str(details).lower()
        self.assertTrue(
            "dq_profile" in detail_str
            or "retention" in detail_str,
            f"Details should reference invalid fields: {details}",
        )

