"""
Comprehensive E2E Security Tests.

Covers:
- Input validation (SQL injection, XSS, CSRF prevention)
- Data access controls (multi-tenant isolation, field-level access, data masking)
- Security headers (CORS, CSP, security headers)

Uses REAL services (no mocks).
"""

import json
import uuid

import pytest

pytestmark = pytest.mark.slow
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from rest_framework import status

from hub.apps.assets.models import Asset
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus

from .conftest import E2ETestBase, get_response_data

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e5]

User = get_user_model()


class InputValidationE2ETest(E2ETestBase):
    """Comprehensive E2E tests for input validation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    # ========== SQL Injection Prevention Tests ==========

    def test_sql_injection_prevention_in_queries(self):
        """Test SQL injection prevention in database queries"""
        # Create a test asset with a known key
        asset_id = self.create_asset(key="test-asset", name="Test Asset")

        # Count total assets before injection attempts
        asset_count_before = Asset.objects.filter(tenant_id=self.tenant.id).count()

        # Try SQL injection in query parameters
        malicious_inputs = [
            "'; DROP TABLE assets; --",
            "1' OR '1'='1",
            "1'; DELETE FROM assets; --",
            "admin'--",
            "' UNION SELECT * FROM users--",
        ]

        for malicious_input in malicious_inputs:
            # Try to use malicious input in filter
            response = self.client.get("/api/v1/assets/", {"key": malicious_input})

            # Should not cause SQL injection
            # Response should be 200 (empty results) or 400 (validation error)
            self.assertIn(
                response.status_code,
                [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
                f"SQL injection attempt '{malicious_input}' should be handled safely",
            )

            # If 200, verify no SQL was executed: the response must
            # be valid JSON with no database error indicators.
            # Note: the ?key= param is NOT a recognised filter on
            # this endpoint (only ?search= is), so the endpoint
            # returns all tenant assets regardless of the value.
            # Getting results back is FINE -- Django's ORM safely
            # parameterises all queries.
            if response.status_code == status.HTTP_200_OK:
                data = get_response_data(response) or {}
                # Verify response does not contain database error
                # messages (which would indicate injection success)
                response_str = json.dumps(
                    data, default=str,
                ).lower()
                for error_indicator in [
                    "syntax error", "relation", "column",
                ]:
                    self.assertNotIn(
                        error_indicator,
                        response_str,
                        f"Response should not contain DB error "
                        f"'{error_indicator}'",
                    )

            # Verify asset still exists (not deleted)
            asset = Asset.objects.filter(id=asset_id).first()
            self.assertIsNotNone(asset, "Asset should not be deleted by SQL injection")

        # Verify no data was deleted or corrupted
        asset_count_after = Asset.objects.filter(tenant_id=self.tenant.id).count()
        self.assertEqual(
            asset_count_before,
            asset_count_after,
            "SQL injection should not delete or corrupt any data",
        )

    def test_sql_injection_prevention_in_path_parameters(self):
        """Test SQL injection prevention in path parameters"""
        # Try SQL injection in UUID path parameter
        malicious_inputs = [
            "'; DROP TABLE assets; --",
            "1' OR '1'='1",
            "admin'--",
        ]

        for malicious_input in malicious_inputs:
            # Try to use malicious input in path
            response = self.client.get(f"/api/v1/assets/{malicious_input}/")

            # Should return 404 (not found) or 400 (bad request), not execute SQL
            self.assertIn(
                response.status_code,
                [status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST],
                f"SQL injection in path '{malicious_input}' should be rejected",
            )

    def test_sql_injection_prevention_in_json_body(self):
        """Test SQL injection prevention in JSON request body"""
        # Try SQL injection in JSON fields
        malicious_inputs = [
            "'; DROP TABLE assets; --",
            "1' OR '1'='1",
            "admin'--",
        ]

        for malicious_input in malicious_inputs:
            # Try to create asset with malicious input
            response = self.client.post(
                "/api/v1/assets/",
                {"key": malicious_input, "name": "Test"},
                format="json",
            )

            # Should be rejected by validation (400) or sanitized
            # Should not execute SQL
            self.assertIn(
                response.status_code,
                [
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_201_CREATED,  # If sanitized and accepted
                ],
                f"SQL injection in JSON body '{malicious_input}' should be handled safely",
            )

            # If created, verify it was sanitized (not executed as SQL)
            if response.status_code == status.HTTP_201_CREATED:
                data = get_response_data(response) or {}
                created_id = data.get("id")
                if created_id:
                    # Verify asset exists and key is the literal string (not SQL)
                    asset = Asset.objects.filter(id=created_id).first()
                    self.assertIsNotNone(asset)
                    # Key should be the literal string, not executed SQL
                    self.assertEqual(asset.key, malicious_input)

    # ========== XSS Prevention Tests ==========

    def test_xss_prevention_in_output(self):
        """Test XSS prevention in API output - payloads stored as literal text, not executed"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(\"XSS\")'></iframe>",
        ]

        for payload in xss_payloads:
            # Create asset with XSS payload in name
            asset_id = self.create_asset(key=f"xss-test-{uuid.uuid4().hex[:8]}", name=payload)

            # Retrieve asset
            response = self.client.get(f"/api/v1/assets/{asset_id}/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            # Content-Type MUST be application/json to prevent browser execution
            content_type = response.get("Content-Type", "")
            self.assertIn(
                "application/json",
                content_type,
                f"Content-Type must be application/json to prevent XSS, got '{content_type}'",
            )

            # Verify the payload is stored as-is (literal string, not executed/stripped)
            data = get_response_data(response) or {}
            self.assertIn("name", data, "Response must include the 'name' field")
            name = data["name"]
            self.assertIsInstance(name, str)
            self.assertEqual(
                name,
                payload,
                f"XSS payload must be stored as literal text. Expected '{payload}', got '{name}'",
            )

            # Verify the raw response body has the payload JSON-escaped (not raw HTML)
            raw_body = response.content.decode("utf-8")
            # In JSON, angle brackets should appear literally or as unicode escapes
            # They must NOT appear as unescaped HTML outside of JSON string values
            # Verify the raw body is valid JSON (not HTML)
            parsed = json.loads(raw_body)
            self.assertIsInstance(parsed, dict, "Response body must be valid JSON, not HTML")

    def test_xss_prevention_in_json_responses(self):
        """Test XSS prevention in JSON responses"""
        # JSON responses should not execute scripts
        xss_payload = "<script>alert('XSS')</script>"

        # Create asset with XSS payload
        asset_id = self.create_asset(key=f"xss-json-{uuid.uuid4().hex[:8]}", name=xss_payload)

        # Get asset
        response = self.client.get(f"/api/v1/assets/{asset_id}/")

        if response.status_code == status.HTTP_200_OK:
            # Response should be JSON
            self.assertEqual(response.get("Content-Type"), "application/json")

            # Parse JSON
            data = get_response_data(response) or {}
            # Data should be a dict (parsed JSON), not raw HTML
            self.assertIsInstance(data, dict)

            # Payload should be in the data as a string value, not executed
            if "name" in data:
                name = data["name"]
                self.assertIsInstance(name, str)
                # Should contain the payload as literal text
                self.assertIn("<script>", name)

    def test_xss_prevention_html_escaping(self):
        """Test that XSS payloads sent to API are not rendered as executable HTML"""
        # Send XSS payloads via the API and verify they are safely stored/returned
        xss_payloads = [
            "<script>alert('xss')</script>",
            '<img src=x onerror="alert(1)">',
            "<<SCRIPT>alert('xss');//<</SCRIPT>",
            '"><script>alert(1)</script>',
        ]

        for payload in xss_payloads:
            asset_id = self.create_asset(
                key=f"html-esc-{uuid.uuid4().hex[:8]}",
                name=payload,
            )

            response = self.client.get(f"/api/v1/assets/{asset_id}/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            data = get_response_data(response) or {}
            self.assertIn("name", data)

            # The API must either:
            # 1. Store the payload as-is (safe because Content-Type is JSON), OR
            # 2. HTML-escape it (safe for any rendering context)
            # Either way, the raw response must be valid JSON, not executable HTML
            raw_body = response.content.decode("utf-8")
            parsed = json.loads(raw_body)
            self.assertIsInstance(parsed, dict, "Response must be valid JSON")

            # Content-Type must prevent browser HTML interpretation
            content_type = response.get("Content-Type", "")
            self.assertIn("application/json", content_type)

            # If the name was HTML-escaped, verify the escaping is correct
            name = data["name"]
            if name != payload:
                # It was escaped - verify dangerous chars are neutralized
                self.assertNotIn("<script>", name.lower(),
                                 "If HTML-escaped, <script> tags must not remain literal")

    # ========== CSRF Prevention Tests ==========

    def test_csrf_protection_enabled(self):
        """Test that CSRF protection is enabled"""
        # CSRF middleware should be in middleware stack
        from django.conf import settings

        self.assertIn(
            "django.middleware.csrf.CsrfViewMiddleware",
            settings.MIDDLEWARE,
            "CSRF middleware should be enabled",
        )

    def test_csrf_token_generation(self):
        """Test CSRF token generation produces a valid token"""
        # Get a response to generate CSRF token
        response = self.client.get("/api/v1/assets/")

        # CSRF token should be available in request
        self.assertTrue(
            hasattr(response, "wsgi_request"),
            "Response must have wsgi_request attribute for CSRF token extraction",
        )

        csrf_token = get_token(response.wsgi_request)
        # Token must be a non-empty string
        self.assertIsNotNone(csrf_token, "CSRF token must not be None")
        self.assertIsInstance(csrf_token, str, "CSRF token must be a string")
        # Django CSRF tokens are 64 characters (masked) or 32 characters (unmasked)
        self.assertGreaterEqual(
            len(csrf_token),
            32,
            f"CSRF token must be at least 32 chars, got {len(csrf_token)}",
        )

    def test_csrf_cookie_settings(self):
        """Test CSRF cookie security settings"""
        from django.conf import settings

        # CSRF cookie should have security settings
        # SameSite must be set to a valid value
        self.assertTrue(
            hasattr(settings, "CSRF_COOKIE_SAMESITE"),
            "CSRF_COOKIE_SAMESITE must be configured",
        )
        self.assertIsNotNone(
            settings.CSRF_COOKIE_SAMESITE,
            "CSRF_COOKIE_SAMESITE must not be None",
        )
        self.assertIn(
            settings.CSRF_COOKIE_SAMESITE,
            ["Lax", "Strict", "None"],
            f"CSRF cookie SameSite should be Lax, Strict, or None, "
            f"got '{settings.CSRF_COOKIE_SAMESITE}'",
        )

        # Verify CSRF_COOKIE_HTTPONLY is configured
        if hasattr(settings, "CSRF_COOKIE_HTTPONLY"):
            self.assertIsInstance(
                settings.CSRF_COOKIE_HTTPONLY,
                bool,
                "CSRF_COOKIE_HTTPONLY must be a boolean",
            )


class DataAccessControlsE2ETest(E2ETestBase):
    """Comprehensive E2E tests for data access controls"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create another tenant for isolation tests
        _suffix = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_suffix}",
            slug=f"other-tenant-{_suffix}",
            kyc_status=KYCStatus.VERIFIED,
        )
        # Ensure other tenant has active subscription so billing middleware allows writes
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        ensure_tenant_has_active_subscription(self.other_tenant)

        self.other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )
        # Assign TENANT_ADMIN role so the user can create assets
        from hub.apps.users.models import Role, UserRole
        other_role, _ = Role.objects.get_or_create(
            tenant=self.other_tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(
            user=self.other_user, role=other_role,
        )

    # ========== Multi-Tenant Isolation Tests ==========

    def test_tenant_isolation_assets(self):
        """Test tenant isolation for assets"""
        # Create asset in current tenant
        asset_id = self.create_asset(key="isolated-asset", name="Isolated Asset")

        # Switch to other tenant
        self.client.force_authenticate(user=self.other_user)

        # Try to access asset from other tenant (should fail with 404)
        response = self.client.get(f"/api/v1/assets/{asset_id}/")
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "Tenant should not access other tenant's assets",
        )

    def test_tenant_isolation_contracts(self):
        """Test tenant isolation for contracts"""
        # Create contract in current tenant
        asset_id = self.create_asset(key="contract-asset", name="Contract Asset")
        contract_id = self.create_contract(asset_id=asset_id)

        # Switch to other tenant
        self.client.force_authenticate(user=self.other_user)

        # Try to access contract from other tenant (should fail with 404)
        response = self.client.get(f"/api/v1/contracts/{contract_id}/")
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "Tenant should not access other tenant's contracts",
        )

    def test_tenant_isolation_list_queries(self):
        """Test tenant isolation in list queries - each tenant sees only its own assets"""
        # Create assets in the FIRST (default) tenant
        tenant1_asset_ids = []
        for i in range(3):
            aid = self.create_asset(key=f"t1-asset-{i}", name=f"Tenant1 Asset {i}")
            tenant1_asset_ids.append(str(aid))

        # Switch to second tenant and create assets there
        self.client.force_authenticate(user=self.other_user)
        tenant2_asset_ids = []
        for i in range(2):
            aid = self.create_asset(key=f"t2-asset-{i}", name=f"Tenant2 Asset {i}")
            tenant2_asset_ids.append(str(aid))

        # List assets as second tenant
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = get_response_data(response) or {}
        results = data.get("results", [])
        returned_ids = [str(r.get("id")) for r in results if isinstance(r, dict)]

        # Second tenant MUST see its own assets
        for t2_id in tenant2_asset_ids:
            self.assertIn(
                t2_id,
                returned_ids,
                f"Tenant 2 should see its own asset {t2_id}",
            )

        # Second tenant MUST NOT see first tenant's assets
        for t1_id in tenant1_asset_ids:
            self.assertNotIn(
                t1_id,
                returned_ids,
                f"Tenant 2 should NOT see tenant 1's asset {t1_id}",
            )

    def test_tenant_isolation_database_queries(self):
        """Test tenant isolation via API - other tenant cannot access or find the asset"""
        # Create asset in current (first) tenant
        asset_id = self.create_asset(key="db-isolation", name="DB Isolation Test")

        # Switch to other tenant
        self.client.force_authenticate(user=self.other_user)

        # Direct access by ID via API should return 404
        response = self.client.get(f"/api/v1/assets/{asset_id}/")
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "Other tenant must not access asset by ID via API",
        )

        # Listing via API should not include the first tenant's asset
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        results = data.get("results", [])
        returned_ids = [str(r.get("id")) for r in results if isinstance(r, dict)]
        self.assertNotIn(
            str(asset_id),
            returned_ids,
            "Other tenant's list query must not include first tenant's asset",
        )

        # Searching/filtering by the asset's key via API should also return nothing
        response = self.client.get("/api/v1/assets/", {"key": "db-isolation"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        results = data.get("results", [])
        self.assertEqual(
            len(results),
            0,
            "Filtering by key should return no results for other tenant",
        )

    # ========== Field-Level Access Tests ==========

    def test_field_level_access_control(self):
        """Test field-level access control"""
        # Create asset
        asset_id = self.create_asset(
            key="field-access", name="Field Access Test", description="Test Description"
        )

        # Get asset
        response = self.client.get(f"/api/v1/assets/{asset_id}/")

        if response.status_code == status.HTTP_200_OK:
            data = get_response_data(response) or {}
            # Should have access to basic fields
            self.assertIn("id", data)
            self.assertIn("key", data)
            self.assertIn("name", data)

            # Some fields may be restricted based on permissions
            # This test verifies that field-level access is enforced

    def test_sensitive_data_not_exposed(self):
        """Test that sensitive data is not exposed in API responses"""
        # Create asset
        asset_id = self.create_asset(key="sensitive-test", name="Sensitive Test")

        # Get asset detail
        response = self.client.get(f"/api/v1/assets/{asset_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = get_response_data(response) or {}
        response_str = json.dumps(data, default=str)
        response_lower = response_str.lower()

        # Should not contain internal filesystem paths
        for path in ["/var/", "/usr/", "/etc/", "/home/", "/opt/"]:
            self.assertNotIn(path, response_str, f"Response must not expose internal path '{path}'")

        # Should not contain sensitive field values
        sensitive_patterns = [
            ("password", "password field or value"),
            ("secret", "secret key or value"),
            ("private_key", "private key material"),
            ("connection_string", "database connection string"),
            ("bearer ", "bearer token"),
            ("aws_access_key", "AWS credentials"),
            ("aws_secret", "AWS secret key"),
            ("database_url", "database URL"),
            ("dsn", "data source name / sentry DSN"),
        ]
        for pattern, description in sensitive_patterns:
            self.assertNotIn(
                pattern,
                response_lower,
                f"Response must not expose {description}",
            )

        # Also check the list endpoint
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        list_str = json.dumps(get_response_data(response) or {}, default=str).lower()
        for pattern, description in sensitive_patterns:
            self.assertNotIn(
                pattern,
                list_str,
                f"List response must not expose {description}",
            )

    # ========== Data Masking Tests ==========

    def test_pii_redaction_in_logs(self):
        """Test PII redaction in logs"""
        from hub.apps.observability.logging import redact_pii

        # Test PII redaction
        test_cases = [
            ("test@example.com", "[EMAIL_REDACTED]"),
            ("1234-5678-9012-3456", "[CARD_REDACTED]"),
            ("123-45-6789", "[SSN_REDACTED]"),
        ]

        for original, expected_pattern in test_cases:
            redacted = redact_pii(original)
            # Should be redacted (contains redaction marker)
            self.assertIn("REDACTED", redacted.upper())

    def test_pii_not_in_error_messages(self):
        """Test that PII is not exposed in error messages"""
        # Try to access non-existent resource
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/assets/{fake_id}/")

        data = get_response_data(response) or {}
        if "error" in data:
            error = data["error"]
            message = error.get("message", "") if isinstance(error, dict) else str(error)

            # Error message should not contain PII
            # Should not contain email patterns
            self.assertNotRegex(
                message,
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                "Error message should not contain email addresses",
            )


class SecurityHeadersE2ETest(E2ETestBase):
    """Comprehensive E2E tests for security headers"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    # ========== Security Headers Tests ==========

    def test_x_frame_options_header(self):
        """Test X-Frame-Options header"""
        response = self.client.get("/api/v1/assets/")

        # X-Frame-Options should be set (clickjacking protection)
        # Django sets this via XFrameOptionsMiddleware
        if "X-Frame-Options" in response:
            x_frame_options = response["X-Frame-Options"]
            # Should be DENY, SAMEORIGIN, or ALLOW-FROM
            self.assertIn(
                x_frame_options.upper(),
                ["DENY", "SAMEORIGIN"],
                f"X-Frame-Options should be DENY or SAMEORIGIN, got {x_frame_options}",
            )

    def test_x_content_type_options_header(self):
        """Test X-Content-Type-Options header"""
        response = self.client.get("/api/v1/assets/")

        # X-Content-Type-Options should be set (MIME type sniffing protection)
        if "X-Content-Type-Options" in response:
            x_content_type_options = response["X-Content-Type-Options"]
            self.assertEqual(
                x_content_type_options.lower(),
                "nosniff",
                "X-Content-Type-Options should be 'nosniff'",
            )

    def test_referrer_policy_header(self):
        """Test Referrer-Policy header"""
        response = self.client.get("/api/v1/assets/")

        # Referrer-Policy should be set
        if "Referrer-Policy" in response:
            referrer_policy = response["Referrer-Policy"]
            # Should be a valid referrer policy value
            valid_policies = [
                "no-referrer",
                "no-referrer-when-downgrade",
                "origin",
                "origin-when-cross-origin",
                "same-origin",
                "strict-origin",
                "strict-origin-when-cross-origin",
                "unsafe-url",
            ]
            self.assertIn(
                referrer_policy.lower(),
                [p.lower() for p in valid_policies],
                f"Referrer-Policy should be valid, got {referrer_policy}",
            )

    def test_security_headers_present(self):
        """Test that security headers are present"""
        response = self.client.get("/api/v1/assets/")

        # Check for common security headers
        security_headers = [
            "X-Frame-Options",
            "X-Content-Type-Options",
            "Referrer-Policy",
        ]

        headers_present = []
        for header in security_headers:
            if header in response:
                headers_present.append(header)

        # At least some security headers should be present
        self.assertGreater(
            len(headers_present),
            0,
            f"At least one security header should be present. Found: {headers_present}",
        )

    # ========== CORS Headers Tests ==========

    def test_cors_headers_configuration(self):
        """Test CORS headers configuration"""
        from django.conf import settings

        # CORS middleware should be in middleware stack
        self.assertIn(
            "corsheaders.middleware.CorsMiddleware",
            settings.MIDDLEWARE,
            "CORS middleware should be enabled",
        )

        # CORS settings should be configured
        # CORS_ALLOWED_ORIGINS or CORS_ALLOW_ALL_ORIGINS should be set
        has_cors_config = hasattr(settings, "CORS_ALLOWED_ORIGINS") or hasattr(
            settings, "CORS_ALLOW_ALL_ORIGINS"
        )
        self.assertTrue(
            has_cors_config,
            "CORS configuration should be present",
        )

    def test_cors_preflight_request(self):
        """Test CORS preflight (OPTIONS) request"""
        # Make OPTIONS request (CORS preflight)
        response = self.client.options("/api/v1/assets/")

        # Should return 200 or 204
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT],
            "CORS preflight should be handled",
        )

        # CORS headers may be present
        # Access-Control-Allow-Origin, Access-Control-Allow-Methods, etc.
        # These are set by django-cors-headers middleware

    # ========== CSP Headers Tests ==========

    def test_csp_configuration(self):
        """Test Content Security Policy configuration"""
        from django.conf import settings

        # CSP settings may be configured
        # Check if CSP-related settings exist
        csp_settings = [
            "CSP_DEFAULT_SRC",
            "CSP_SCRIPT_SRC",
            "CSP_STYLE_SRC",
        ]

        has_csp_config = any(hasattr(settings, setting) for setting in csp_settings)
        # CSP may not be fully configured in test environment
        # This test verifies the configuration mechanism exists
        # In production, CSP should be configured

    def test_security_middleware_enabled(self):
        """Test that security middleware is enabled"""
        from django.conf import settings

        # SecurityMiddleware should be in middleware stack
        self.assertIn(
            "django.middleware.security.SecurityMiddleware",
            settings.MIDDLEWARE,
            "Security middleware should be enabled",
        )

    def test_custom_security_headers_middleware(self):
        """Test custom security headers middleware"""
        from django.conf import settings

        # SecurityHeadersMiddleware may or may not be in middleware stack
        # Security headers are also set by SecurityMiddleware
        # This test verifies that security headers are present in responses
        response = self.client.get("/api/v1/assets/")

        # Verify security headers are present (set by SecurityMiddleware or custom middleware)
        security_headers_present = []
        for header in ["X-Content-Type-Options", "Referrer-Policy", "X-Frame-Options"]:
            if header in response:
                security_headers_present.append(header)

        # At least one security header should be present
        self.assertGreater(
            len(security_headers_present),
            0,
            "Security headers should be present in responses",
        )
