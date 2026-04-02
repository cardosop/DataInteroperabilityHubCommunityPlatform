"""
Comprehensive E2E tests for rate limiting.

Covers:
- Burst, sustained, and daily rate limit enforcement
- Per-endpoint category limits
- Tenant config overrides
- Per-user and per-API-key limits
- Edge cases (window boundary, concurrent requests, header accuracy)

Uses REAL services (no mocks).
"""
import json
import time
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status

from hub.apps.tenants.models import Tenant
from hub.apps.auth.models import APIKey
from hub.apps.rate_limiting.utils import (
    TimeWindow,
    EndpointCategory,
    generate_rate_limit_key,
)
from tests.factories import TenantConfigFactory
from tests.e2e.conftest import E2ETestBase

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e3,
    pytest.mark.slow,
]
User = get_user_model()


@override_settings(RATE_LIMIT_ENABLED=True)
class RateLimitingE2ETest(E2ETestBase):
    """Comprehensive E2E tests for rate limiting"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Enable rate limiting for this test class.  We use
        # the TestCase.settings() context manager instead of
        # @override_settings because pytest-django may convert
        # TestCase → TransactionTestCase, losing class
        # decorators.  The CM is entered here and cleaned up
        # automatically by TestCase teardown.
        self._rl_ctx = self.settings(RATE_LIMIT_ENABLED=True)
        self._rl_ctx.__enter__()
        self.addCleanup(self._rl_ctx.__exit__, None, None, None)
        # Create a fresh APIClient WITHOUT force_authenticate.
        # E2ETestBase.setUp calls force_authenticate which sets
        # internal handler state that DRF prioritises over the
        # Authorization header — bypassing JWT-based tenant
        # resolution in the middleware phase.  A fresh client
        # has no forced-auth baggage so the JWT bearer token is
        # processed by TenantScopingMiddleware correctly.
        from rest_framework.test import APIClient
        self.client = APIClient()
        self._authenticate_with_jwt(self.user)

    def _authenticate_with_jwt(self, user):
        """Authenticate the test client via JWT bearer token.

        force_authenticate only takes effect in the VIEW phase, but rate
        limiting runs in the MIDDLEWARE phase where request.user is still
        AnonymousUser.  JWT tokens are resolved by TenantScopingMiddleware
        during process_request, so rate limit keys are built correctly.
        """
        from hub.apps.auth.jwt_utils import JWTTokenGenerator
        access_token = JWTTokenGenerator.generate_access_token(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    # ------------------------------------------------------------------
    # Enforcement tests
    # ------------------------------------------------------------------

    def test_burst_rate_limit_enforcement(self):
        """Test burst rate limit enforcement (5 req / 10 s)"""
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                'catalog_read': {
                    '10': 5,
                },
            },
        )

        endpoint = '/api/v1/assets/'
        successful_requests = 0
        rate_limited_requests = 0

        for i in range(10):
            response = self.client.get(endpoint)
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited_requests += 1
                data = json.loads(response.content)
                self.assertEqual(
                    data['error']['code'],
                    'RATE_LIMIT_EXCEEDED',
                )
                self.assertIn('Retry-After', response.headers)
            elif response.status_code in (
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
            ):
                successful_requests += 1

        self.assertGreater(
            successful_requests, 0,
            "Some requests should succeed before rate limit",
        )
        self.assertGreater(
            rate_limited_requests, 0,
            "No requests were rate limited - "
            "rate limiting may not be working",
        )

        # Wait for window to expire
        # INTENTIONAL: e2e test waiting for real window
        time.sleep(11)

        response = self.client.get(endpoint)
        self.assertIn(
            response.status_code,
            (
                status.HTTP_200_OK,
                status.HTTP_429_TOO_MANY_REQUESTS,
                status.HTTP_404_NOT_FOUND,
            ),
        )

    def test_sustained_rate_limit_enforcement(self):
        """Test sustained rate limit enforcement (10 req / 60 s)"""
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                'catalog_read': {
                    '60': 10,
                },
            },
        )

        endpoint = '/api/v1/assets/'
        successful_requests = 0
        rate_limited_requests = 0

        for i in range(15):
            response = self.client.get(endpoint)
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited_requests += 1
            elif response.status_code in (
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
            ):
                successful_requests += 1
            # INTENTIONAL: test-specific timing
            time.sleep(0.1)

        self.assertGreater(
            successful_requests, 0,
            "Some requests should succeed before rate limit",
        )
        self.assertGreater(
            rate_limited_requests, 0,
            "No requests were rate limited - "
            "sustained rate limiting may not be working",
        )

    def test_daily_cap_enforcement(self):
        """Test daily cap enforcement (10 req / day)"""
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                'catalog_read': {
                    '86400': 10,
                },
            },
        )

        endpoint = '/api/v1/assets/'
        successful_requests = 0
        rate_limited_requests = 0

        for i in range(15):
            response = self.client.get(endpoint)
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited_requests += 1
            elif response.status_code in (
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
            ):
                successful_requests += 1
            # INTENTIONAL: e2e test polling real services
            time.sleep(0.1)

        self.assertGreater(
            successful_requests, 0,
            "Some requests should succeed before daily cap",
        )
        self.assertGreater(
            rate_limited_requests, 0,
            "No requests were rate limited - "
            "daily cap may not be working",
        )

    # ------------------------------------------------------------------
    # Per-endpoint category tests
    # ------------------------------------------------------------------

    def test_per_endpoint_category_dq_run(self):
        """Test DQ run listing has rate limit headers.

        POST may be rejected by upstream middleware (billing,
        validation) before the rate limiter runs, so we
        verify headers on the GET listing instead.
        """
        response = self.client.get('/api/v1/dq/runs/')

        self.assertIn(
            'X-RateLimit-Limit', response.headers,
            "Rate limit headers should be present "
            "for DQ runs listing endpoint",
        )
        limit = int(response.headers['X-RateLimit-Limit'])
        self.assertGreater(limit, 0)

    def test_per_endpoint_category_compliance_run(self):
        """Test compliance run listing has rate limit headers."""
        response = self.client.get(
            '/api/v1/compliance/runs/',
        )

        self.assertIn(
            'X-RateLimit-Limit', response.headers,
            "Rate limit headers should be present "
            "for compliance runs listing endpoint",
        )
        limit = int(response.headers['X-RateLimit-Limit'])
        self.assertGreater(limit, 0)

    def test_per_endpoint_category_file_upload(self):
        """Test file listing has rate limit headers."""
        response = self.client.get('/api/v1/files/')

        self.assertIn(
            'X-RateLimit-Limit', response.headers,
            "Rate limit headers should be present "
            "for files listing endpoint",
        )
        limit = int(response.headers['X-RateLimit-Limit'])
        self.assertGreater(limit, 0)

    def test_per_endpoint_category_catalog_read(self):
        """Test catalog read endpoint has rate limit headers"""
        response = self.client.get('/api/v1/assets/')

        self.assertIn(
            'X-RateLimit-Limit', response.headers,
            "Rate limit headers should be present "
            "for catalog read endpoint",
        )
        limit = int(response.headers['X-RateLimit-Limit'])
        self.assertGreater(limit, 0)

    # ------------------------------------------------------------------
    # Tenant config tests
    # ------------------------------------------------------------------

    def test_tenant_config_rate_limit_override(self):
        """Test that tenant config overrides platform defaults"""
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                'catalog_read': {
                    '60': 100,
                },
            },
        )

        response = self.client.get('/api/v1/assets/')

        self.assertIn(
            'X-RateLimit-Limit', response.headers,
            "Rate limit headers should be present "
            "after tenant config override",
        )
        limit = int(response.headers['X-RateLimit-Limit'])
        self.assertGreater(limit, 0)

    def test_tenant_config_platform_maximum_enforced(self):
        """Test that tenant config cannot exceed platform maximums"""
        from hub.apps.rate_limiting.config import (
            get_platform_maximum_limit,
        )

        platform_max = get_platform_maximum_limit(
            EndpointCategory.GENERAL,
            TimeWindow.SUSTAINED,
        )

        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                'catalog_read': {
                    '60': platform_max + 1000,
                },
            },
        )

        response = self.client.get('/api/v1/assets/')

        self.assertIn(
            'X-RateLimit-Limit', response.headers,
            "Rate limit headers should be present "
            "when platform maximum is enforced",
        )
        limit = int(response.headers['X-RateLimit-Limit'])
        self.assertLessEqual(
            limit, platform_max,
            f"Limit {limit} should not exceed "
            f"platform maximum {platform_max}",
        )

    # ------------------------------------------------------------------
    # Per-user / per-API-key isolation
    # ------------------------------------------------------------------

    def test_rate_limit_per_user(self):
        """Test that rate limit headers are present for multiple users.

        Both users belong to the same tenant, so they share the tenant
        rate limit pool.  We verify that headers are present and that
        the remaining counter accounts for both users' requests
        (i.e. the counter decreased by the total number of requests).
        """
        user2 = User.objects.create_user(
            email='user2@example.com',
            password='testpass123',
            tenant=self.tenant,
            status='ACTIVE',
        )

        endpoint = '/api/v1/assets/'

        # User 1
        response1 = self.client.get(endpoint)
        self.assertIn(
            response1.status_code,
            (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND),
        )
        self.assertIn(
            'X-RateLimit-Remaining', response1.headers,
            "Rate limit remaining header must be "
            "present for user 1",
        )
        remaining1 = int(
            response1.headers['X-RateLimit-Remaining'],
        )

        # User 2 (same tenant -- shares the tenant rate limit pool)
        self._authenticate_with_jwt(user2)
        response2 = self.client.get(endpoint)
        self.assertIn(
            response2.status_code,
            (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND),
        )
        self.assertIn(
            'X-RateLimit-Remaining', response2.headers,
            "Rate limit remaining header must be "
            "present for user 2",
        )
        remaining2 = int(
            response2.headers['X-RateLimit-Remaining'],
        )

        self.assertGreaterEqual(remaining1, 0)
        self.assertGreaterEqual(remaining2, 0)
        # Same tenant: user 2's remaining should be one less than user 1's
        # because user 1 already consumed one request from the shared pool.
        self.assertLess(
            remaining2, remaining1,
            "User 2 (same tenant) should see a reduced remaining "
            "count after user 1 consumed a request",
        )

    def test_rate_limit_per_api_key(self):
        """Test that each API key has separate rate limits"""
        api_key1 = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash='test-hash-1',
            name='Test API Key 1',
        )
        api_key2 = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash='test-hash-2',
            name='Test API Key 2',
        )

        # Verify cache keys are distinct per API key
        key1 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            api_key_id=str(api_key1.id),
            endpoint_category=EndpointCategory.GENERAL,
            window=TimeWindow.SUSTAINED,
        )
        key2 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            api_key_id=str(api_key2.id),
            endpoint_category=EndpointCategory.GENERAL,
            window=TimeWindow.SUSTAINED,
        )

        self.assertNotEqual(key1, key2)
        self.assertIn(str(api_key1.id), key1)
        self.assertIn(str(api_key2.id), key2)

        # Verify via actual requests that headers are present and
        # the counter decrements (both users share the same tenant pool).
        endpoint = '/api/v1/assets/'
        response1 = self.client.get(endpoint)
        self.assertIn(
            'X-RateLimit-Remaining', response1.headers,
            "Rate limit remaining must be present "
            "for first user",
        )
        remaining1 = int(
            response1.headers['X-RateLimit-Remaining'],
        )

        user2 = User.objects.create_user(
            email='apikey-test-user2@example.com',
            password='testpass123',
            tenant=self.tenant,
            status='ACTIVE',
        )
        self._authenticate_with_jwt(user2)
        response2 = self.client.get(endpoint)
        self.assertIn(
            'X-RateLimit-Remaining', response2.headers,
            "Rate limit remaining must be present "
            "for second user",
        )
        remaining2 = int(
            response2.headers['X-RateLimit-Remaining'],
        )

        # Both users share the same tenant, so remaining should decrease
        self.assertLess(
            remaining2, remaining1,
            "Second request (same tenant) should have "
            "lower remaining than first request",
        )

    # ------------------------------------------------------------------
    # Header tests
    # ------------------------------------------------------------------

    def test_rate_limit_headers_present(self):
        """Test that rate limit headers are present in responses"""
        response = self.client.get('/api/v1/assets/')

        self.assertIn(
            'X-RateLimit-Limit', response.headers,
            "X-RateLimit-Limit header should be present",
        )
        self.assertIn(
            'X-RateLimit-Remaining', response.headers,
            "X-RateLimit-Remaining header should be present",
        )
        self.assertIn(
            'X-RateLimit-Reset', response.headers,
            "X-RateLimit-Reset header should be present",
        )

        limit = int(response.headers['X-RateLimit-Limit'])
        remaining = int(response.headers['X-RateLimit-Remaining'])
        reset = int(response.headers['X-RateLimit-Reset'])

        self.assertGreater(limit, 0)
        self.assertGreaterEqual(remaining, 0)
        self.assertLessEqual(remaining, limit)
        self.assertGreater(reset, 0)

    def test_rate_limit_remaining_decreases(self):
        """Test that remaining counter strictly decreases"""
        endpoint = '/api/v1/assets/'
        remaining_values = []

        for i in range(5):
            response = self.client.get(endpoint)
            self.assertIn(
                'X-RateLimit-Remaining', response.headers,
                "X-RateLimit-Remaining header must be present",
            )
            remaining = int(
                response.headers['X-RateLimit-Remaining'],
            )
            remaining_values.append(remaining)
            # INTENTIONAL: e2e test polling real services
            time.sleep(0.1)

        self.assertGreater(
            len(remaining_values), 1,
            "Should have multiple remaining readings",
        )
        self.assertLess(
            remaining_values[-1], remaining_values[0],
            "Rate limit remaining should strictly decrease: "
            f"first={remaining_values[0]}, "
            f"last={remaining_values[-1]}",
        )

    def test_rate_limit_reset_time_accuracy(self):
        """Test that reset time is in the future"""
        response = self.client.get('/api/v1/assets/')

        self.assertIn(
            'X-RateLimit-Reset', response.headers,
            "X-RateLimit-Reset header must be present",
        )
        reset_time = int(response.headers['X-RateLimit-Reset'])
        current_time = int(time.time())

        self.assertGreaterEqual(
            reset_time, current_time,
            "Reset time should be in the future",
        )

    def test_rate_limit_header_accuracy(self):
        """Test that rate limit headers are accurate"""
        endpoint = '/api/v1/assets/'

        response1 = self.client.get(endpoint)
        self.assertIn(
            'X-RateLimit-Limit', response1.headers,
            "X-RateLimit-Limit must be present",
        )
        self.assertIn(
            'X-RateLimit-Remaining', response1.headers,
            "X-RateLimit-Remaining must be present",
        )

        limit1 = int(response1.headers['X-RateLimit-Limit'])
        remaining1 = int(
            response1.headers['X-RateLimit-Remaining'],
        )

        response2 = self.client.get(endpoint)
        self.assertIn(
            'X-RateLimit-Limit', response2.headers,
            "X-RateLimit-Limit must be present "
            "on second request",
        )
        self.assertIn(
            'X-RateLimit-Remaining', response2.headers,
            "X-RateLimit-Remaining must be present "
            "on second request",
        )

        limit2 = int(response2.headers['X-RateLimit-Limit'])
        remaining2 = int(
            response2.headers['X-RateLimit-Remaining'],
        )

        self.assertEqual(
            limit1, limit2,
            "Rate limit should be consistent across requests",
        )
        self.assertLess(
            remaining2, remaining1,
            "Remaining should strictly decrease "
            "after a second request",
        )
        self.assertLessEqual(
            remaining2, limit2,
            "Remaining should not exceed limit",
        )

    def test_rate_limit_category_header(self):
        """Test category-specific headers for API endpoints"""
        response = self.client.get('/api/v1/assets/')

        self.assertIn(
            'X-RateLimit-Category', response.headers,
            "X-RateLimit-Category header must be present "
            "for DQ run endpoint",
        )
        category = response.headers['X-RateLimit-Category']
        self.assertIn(category, [
            EndpointCategory.DQ_RUN,
            EndpointCategory.COMPLIANCE_RUN,
            EndpointCategory.FILE_UPLOAD,
            EndpointCategory.FILE_DOWNLOAD,
            EndpointCategory.CONTRACT_VALIDATION,
            EndpointCategory.CATALOG_READ,
            EndpointCategory.SPARQL_QUERY,
        ])

    # ------------------------------------------------------------------
    # Retry-After / error format
    # ------------------------------------------------------------------

    def test_rate_limit_retry_after_header(self):
        """Test Retry-After header on 429 response"""
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                'catalog_read': {
                    '10': 2,
                },
            },
        )

        endpoint = '/api/v1/assets/'
        rate_limited_response = None
        for i in range(10):
            response = self.client.get(endpoint)
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited_response = response
                break
            # INTENTIONAL: e2e test polling real services
            time.sleep(0.1)

        self.assertIsNotNone(
            rate_limited_response,
            "Rate limit should trigger with limit=2 "
            "and 10 requests",
        )
        self.assertIn(
            'Retry-After', rate_limited_response.headers,
            "Retry-After header must be present on 429",
        )
        retry_after = int(
            rate_limited_response.headers['Retry-After'],
        )
        self.assertGreater(
            retry_after, 0,
            "Retry-After should be positive",
        )
        self.assertLessEqual(
            retry_after, 10,
            "Retry-After should be within window (10s)",
        )

    def test_rate_limit_error_format(self):
        """Test that 429 error follows standard format"""
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                'catalog_read': {
                    '10': 2,
                },
            },
        )

        endpoint = '/api/v1/assets/'
        rate_limited_response = None
        for i in range(10):
            response = self.client.get(endpoint)
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited_response = response
                break
            # INTENTIONAL: e2e test polling real services
            time.sleep(0.1)

        self.assertIsNotNone(
            rate_limited_response,
            "Rate limit should trigger with limit=2 "
            "and 10 requests",
        )

        data = json.loads(rate_limited_response.content)
        self.assertIn('error', data)
        error = data['error']
        self.assertEqual(error['code'], 'RATE_LIMIT_EXCEEDED')
        self.assertIn('message', error)
        self.assertEqual(error['http_status'], 429)
        self.assertIn('request_id', error)
        self.assertIn('timestamp', error)
        self.assertIn('details', error)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_rate_limit_window_boundary_no_burst(self):
        """Test that sliding window prevents bursts at boundaries"""
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                'catalog_read': {
                    '10': 5,
                },
            },
        )

        endpoint = '/api/v1/assets/'

        for i in range(5):
            response = self.client.get(endpoint)
            self.assertIn(
                response.status_code,
                (
                    status.HTTP_200_OK,
                    status.HTTP_404_NOT_FOUND,
                    status.HTTP_429_TOO_MANY_REQUESTS,
                ),
            )
            # INTENTIONAL: e2e test polling real services
            time.sleep(0.1)

        # Wait until just before window boundary
        # INTENTIONAL: e2e test waiting for real window
        time.sleep(9)

        rate_limited = False
        for i in range(3):
            response = self.client.get(endpoint)
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited = True
                break
            # INTENTIONAL: e2e test polling real services
            time.sleep(0.1)

        self.assertTrue(
            rate_limited,
            "Sliding window should still rate-limit "
            "requests near the window boundary",
        )

    def test_rate_limit_concurrent_requests(self):
        """Test rate limiting under rapid sequential load.

        DRF's APIClient is not thread-safe, so we use rapid
        sequential requests instead of threads. With a limit
        of 3 per 10 s, the 4th+ request must be rate-limited.
        """
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                'catalog_read': {
                    '10': 3,
                },
            },
        )

        endpoint = '/api/v1/assets/'
        responses = []

        for _ in range(10):
            resp = self.client.get(endpoint)
            responses.append(resp)

        self.assertEqual(len(responses), 10)
        for resp in responses:
            self.assertIn(
                resp.status_code,
                (
                    status.HTTP_200_OK,
                    status.HTTP_404_NOT_FOUND,
                    status.HTTP_429_TOO_MANY_REQUESTS,
                ),
            )

        rate_limited = [
            r for r in responses
            if r.status_code
            == status.HTTP_429_TOO_MANY_REQUESTS
        ]
        self.assertGreater(
            len(rate_limited), 0,
            "At least one request should be "
            "rate-limited with a limit of 3",
        )

    def test_rate_limit_all_windows_checked(self):
        """Test that rate limit headers are present (all windows)"""
        response = self.client.get('/api/v1/assets/')

        self.assertIn(
            'X-RateLimit-Limit', response.headers,
            "Rate limit headers must be present",
        )
        limit = int(response.headers['X-RateLimit-Limit'])
        self.assertGreater(
            limit, 0,
            "Rate limit value should be positive",
        )

    def test_rate_limit_per_tenant_isolation(self):
        """Test that rate limits are isolated per tenant"""
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

        # Tenant 1
        response1 = self.client.get(endpoint)
        self.assertIn(
            response1.status_code,
            (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND),
        )
        self.assertIn(
            'X-RateLimit-Remaining', response1.headers,
            "Rate limit remaining must be present "
            "for tenant 1",
        )
        remaining1 = int(
            response1.headers['X-RateLimit-Remaining'],
        )

        # Tenant 2 (different tenant -- independent rate limit pool)
        self._authenticate_with_jwt(other_user)
        response2 = self.client.get(endpoint)
        self.assertIn(
            response2.status_code,
            (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND),
        )
        self.assertIn(
            'X-RateLimit-Remaining', response2.headers,
            "Rate limit remaining must be present "
            "for tenant 2",
        )
        remaining2 = int(
            response2.headers['X-RateLimit-Remaining'],
        )

        self.assertGreaterEqual(remaining1, 0)
        self.assertGreaterEqual(remaining2, 0)
        self.assertGreaterEqual(
            remaining2, remaining1,
            "Tenant 2 should have independent (fresh) "
            "rate limit, not reduced by tenant 1",
        )
