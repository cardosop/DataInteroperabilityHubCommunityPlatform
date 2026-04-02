"""
Comprehensive E2E tests for rate limiting.

Covers:
- Rate limit enforcement
- Rate limit headers
- Per-tenant rate limits
- Per-endpoint rate limits
- Rate limit exceeded responses

Uses REAL services (no mocks).
"""
import time
import uuid

import pytest
from django.test import override_settings
from rest_framework import status

from .conftest import E2ETestBase, get_response_data


pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e3,
]


@override_settings(RATE_LIMIT_ENABLED=True)
class RateLimitingE2ETest(E2ETestBase):
    """Test rate limiting operations"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self._rl_ctx = self.settings(RATE_LIMIT_ENABLED=True)
        self._rl_ctx.__enter__()
        self.addCleanup(self._rl_ctx.__exit__, None, None, None)
        # Fresh APIClient without force_authenticate baggage
        # so JWT tokens are processed by TenantScopingMiddleware.
        from rest_framework.test import APIClient
        self.client = APIClient()
        self._authenticate_with_jwt(self.user)

    def _authenticate_with_jwt(self, user):
        """Authenticate the test client via JWT bearer token."""
        from hub.apps.auth.jwt_utils import JWTTokenGenerator
        access_token = JWTTokenGenerator.generate_access_token(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    def test_rate_limit_headers_present(self):
        """Test rate limit headers are present in responses"""
        response = self.client.get('/api/v1/assets/')

        headers = response.headers
        # Check both standard and X- prefixed headers
        rl_headers = [
            'X-RateLimit-Limit',
            'X-RateLimit-Remaining',
            'X-RateLimit-Reset',
            'RateLimit-Limit',
            'RateLimit-Remaining',
            'RateLimit-Reset',
        ]

        has_header = any(h in headers for h in rl_headers)
        self.assertTrue(
            has_header,
            "At least one rate limit header should be "
            "present in the response",
        )

    def test_rate_limit_enforcement(self):
        """Test rate limit enforcement triggers after many requests"""
        from tests.factories import TenantConfigFactory
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                'catalog_read': {
                    '10': 5,
                },
            },
        )

        endpoint = '/api/v1/assets/'
        responses = []
        rate_limited = False

        for i in range(20):
            response = self.client.get(endpoint)
            responses.append(response)

            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited = True
                data = get_response_data(response) or {}
                if 'error' in data:
                    error = (
                        data['error']
                        if isinstance(data.get('error'), dict)
                        else {}
                    )
                    self.assertIn('code', error)
                    code = error.get('code', '').upper()
                    self.assertIn('RATE_LIMIT', code)
                break

        self.assertTrue(
            rate_limited,
            "Rate limiting should trigger after "
            "many rapid requests",
        )

    def test_rate_limit_per_tenant(self):
        """Test rate limits are per-tenant"""
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User  # noqa: F811
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )

        _suffix = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f'Other Tenant {_suffix}',
            slug=f'other-tenant-{_suffix}',
        )
        ensure_tenant_has_active_subscription(other_tenant)
        other_user = User.objects.create_user(
            email=f'other-{_suffix}@example.com',
            password='testpass123',
            tenant=other_tenant,
            status='ACTIVE',
        )

        endpoint = '/api/v1/assets/'

        response1 = self.client.get(endpoint)
        self.assertEqual(
            response1.status_code, status.HTTP_200_OK,
        )

        self._authenticate_with_jwt(other_user)
        response2 = self.client.get(endpoint)
        self.assertEqual(
            response2.status_code, status.HTTP_200_OK,
        )

    def test_rate_limit_exceeded_response(self):
        """Test rate limit exceeded response format"""
        from tests.factories import TenantConfigFactory
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                'catalog_read': {
                    '10': 3,
                },
            },
        )

        endpoint = '/api/v1/assets/'

        rate_limited_response = None
        for i in range(20):
            response = self.client.get(endpoint)
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited_response = response
                break
            # INTENTIONAL: e2e test polling real services
            time.sleep(0.01)

        self.assertIsNotNone(
            rate_limited_response,
            "Should trigger rate limit after "
            "rapid requests",
        )

        self.assertEqual(
            rate_limited_response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
        data = get_response_data(rate_limited_response) or {}
        self.assertIn('error', data)
        error = (
            data['error']
            if isinstance(data.get('error'), dict)
            else {}
        )
        self.assertIn('code', error)
        code = error.get('code', '').upper()
        self.assertIn('RATE_LIMIT', code)
        self.assertIn('message', error)

    def test_rate_limit_headers_consistency(self):
        """Test rate limit headers are consistent across requests"""
        endpoint = '/api/v1/assets/'

        responses = []
        for i in range(10):
            response = self.client.get(endpoint)
            responses.append(response)
            # INTENTIONAL: test-specific timing
            time.sleep(0.1)

        rate_limit_headers = []
        for response in responses:
            headers = response.headers
            for header_name in (
                'X-RateLimit-Limit',
                'RateLimit-Limit',
            ):
                if header_name in headers:
                    rate_limit_headers.append(
                        headers[header_name],
                    )

        self.assertGreater(
            len(rate_limit_headers), 0,
            "Rate limit headers should be present "
            "in at least one response",
        )
        unique_limits = set(rate_limit_headers)
        self.assertEqual(
            len(unique_limits), 1,
            "Rate limit should be the same across "
            "all requests",
        )

    def test_rate_limit_reset_header(self):
        """Test rate limit reset header is present and valid"""
        response = self.client.get('/api/v1/assets/')

        headers = response.headers
        reset_headers = [
            'X-RateLimit-Reset',
            'RateLimit-Reset',
        ]

        found = False
        for header_name in reset_headers:
            if header_name in headers:
                found = True
                reset_value = headers[header_name]
                self.assertIsNotNone(reset_value)
                # Verify it is a valid numeric timestamp
                reset_int = int(reset_value)
                self.assertGreater(
                    reset_int, 0,
                    "Reset timestamp should be positive",
                )
                break

        self.assertTrue(
            found,
            "At least one reset header should be present",
        )

    def test_rate_limit_remaining_decreases(self):
        """Test rate limit remaining decreases with requests"""
        endpoint = '/api/v1/assets/'

        remaining_values = []
        for i in range(10):
            response = self.client.get(endpoint)
            headers = response.headers

            for header_name in (
                'X-RateLimit-Remaining',
                'RateLimit-Remaining',
            ):
                if header_name in headers:
                    remaining = int(headers[header_name])
                    remaining_values.append(remaining)
                    break

            # INTENTIONAL: e2e test polling real services
            time.sleep(0.1)

        self.assertGreater(
            len(remaining_values), 1,
            "Should have multiple remaining readings",
        )
        self.assertLess(
            remaining_values[-1], remaining_values[0],
            "Rate limit remaining should strictly "
            "decrease across requests: "
            f"first={remaining_values[0]}, "
            f"last={remaining_values[-1]}",
        )

    def test_rate_limit_per_endpoint(self):
        """Test rate limits are present per endpoint"""
        endpoints = [
            '/api/v1/assets/',
            '/api/v1/contracts/',
            '/api/v1/datasets/',
        ]

        limits = {}
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            headers = response.headers

            for header_name in (
                'X-RateLimit-Limit',
                'RateLimit-Limit',
            ):
                if header_name in headers:
                    limits[endpoint] = int(headers[header_name])
                    break

        self.assertGreater(
            len(limits), 0,
            "At least one endpoint should have "
            "rate limit headers",
        )
        for ep, limit in limits.items():
            self.assertGreater(
                limit, 0,
                f"Rate limit for {ep} should be positive",
            )

    def test_rate_limit_retry_after_header(self):
        """Test Retry-After header on rate limit exceeded"""
        from tests.factories import TenantConfigFactory
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                'catalog_read': {
                    '10': 3,
                },
            },
        )

        endpoint = '/api/v1/assets/'

        rate_limited_response = None
        for i in range(20):
            response = self.client.get(endpoint)
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited_response = response
                break
            # INTENTIONAL: e2e test polling real services
            time.sleep(0.01)

        self.assertIsNotNone(
            rate_limited_response,
            "Should trigger rate limit after rapid "
            "requests",
        )
        self.assertIn(
            'Retry-After', rate_limited_response.headers,
            "Retry-After header must be present on 429",
        )
        retry_after = rate_limited_response.headers['Retry-After']
        self.assertIsNotNone(retry_after)
        retry_seconds = int(retry_after)
        self.assertGreater(
            retry_seconds, 0,
            "Retry-After should be a positive number",
        )
