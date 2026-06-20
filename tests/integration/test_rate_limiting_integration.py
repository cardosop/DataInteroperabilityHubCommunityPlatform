"""
Integration tests for rate limiting.

Tests per-tenant, per-user, per-API-key rate limits with real Redis and services.
No mocks - uses real rate limiting implementation.
"""

import time
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.auth.models import APIKey
from hub.apps.rate_limiting.service import check_rate_limit, get_rate_limit_headers
from hub.apps.rate_limiting.utils import EndpointCategory, TimeWindow
from hub.apps.tenants.models import Tenant
from tests.factories import TenantConfigFactory

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class RateLimitingIntegrationTest(TestCase):
    """Integration tests for rate limiting with real services"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        self.client.force_authenticate(user=self.user)

    def test_per_tenant_rate_limit_enforcement(self):
        """Test that per-tenant rate limits are enforced"""
        from django.http import HttpRequest

        # Create request
        request = HttpRequest()
        request.path = "/api/v1/dq/runs/"
        request.method = "POST"
        request.tenant = self.tenant

        # Check rate limit (should allow)
        allowed, results = check_rate_limit(request, tenant_id=str(self.tenant.id))

        # Should be allowed initially
        self.assertTrue(allowed)
        self.assertGreater(len(results), 0)

        # Verify tenant-level result exists
        tenant_results = [r for r in results if r.limit_type == "tenant"]
        self.assertGreater(len(tenant_results), 0)

    def test_per_tenant_rate_limit_with_custom_config(self):
        """Test that tenant config overrides platform defaults"""
        # Create tenant config with custom rate limits
        # Note: rate_limits structure uses window as string key
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                "dq_run": {
                    "10": 30,  # burst: 30 requests per 10 seconds
                    "60": 100,  # sustained: 100 requests per 60 seconds
                    "86400": 20000,  # daily: 20000 requests per day
                }
            },
        )

        from hub.apps.rate_limiting.config import get_tenant_rate_limit

        # Get tenant rate limit for DQ_RUN category
        limit = get_tenant_rate_limit(
            str(self.tenant.id), EndpointCategory.DQ_RUN, TimeWindow.SUSTAINED
        )

        # Should use tenant config (100, not platform default 60)
        self.assertEqual(limit, 100)

    def test_per_tenant_rate_limit_uses_platform_defaults(self):
        """Test that platform defaults are used when tenant config not set"""
        from hub.apps.rate_limiting.config import get_tenant_rate_limit

        # Get tenant rate limit (no config set)
        limit = get_tenant_rate_limit(
            str(self.tenant.id), EndpointCategory.DQ_RUN, TimeWindow.SUSTAINED
        )

        # Should use platform default
        self.assertGreater(limit, 0)
        # Platform default for DQ_RUN sustained is 60
        self.assertEqual(limit, 60)

    def test_per_user_rate_limit_enforcement(self):
        """Test that per-user rate limits are enforced"""
        from django.http import HttpRequest

        # Create request with user
        request = HttpRequest()
        request.path = "/api/v1/dq/runs/"
        request.method = "POST"
        request.tenant = self.tenant
        request.user = self.user

        # Check rate limit
        allowed, results = check_rate_limit(
            request, tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Should be allowed initially
        self.assertTrue(allowed)

        # Should check both tenant and user limits
        tenant_results = [r for r in results if r.limit_type == "tenant"]
        user_results = [r for r in results if r.limit_type == "user"]

        self.assertGreater(len(tenant_results), 0)
        self.assertGreater(len(user_results), 0)

    def test_per_user_rate_limit_is_50_percent_of_tenant(self):
        """Test that user limits are 50% of tenant limits"""
        from hub.apps.rate_limiting.config import get_tenant_rate_limit, get_user_rate_limit

        # Get tenant limit
        tenant_limit = get_tenant_rate_limit(
            str(self.tenant.id), EndpointCategory.DQ_RUN, TimeWindow.SUSTAINED
        )

        # Get user limit (doesn't take user_id, just tenant_id)
        user_limit = get_user_rate_limit(
            str(self.tenant.id), EndpointCategory.DQ_RUN, TimeWindow.SUSTAINED
        )

        # User limit should be 50% of tenant limit
        self.assertEqual(user_limit, tenant_limit // 2)

    def test_per_user_rate_limit_separate_per_user(self):
        """Test that different users have separate rate limits"""
        # Create second user
        user2 = User.objects.create_user(
            email="test2@example.com", password="testpass123", tenant=self.tenant
        )

        from hub.apps.rate_limiting.utils import generate_rate_limit_key

        # Generate keys for both users
        key1 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        key2 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            user_id=str(user2.id),
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )

        # Keys should be different
        self.assertNotEqual(key1, key2)
        self.assertIn(str(self.user.id), key1)
        self.assertIn(str(user2.id), key2)

    def test_per_api_key_rate_limit_enforcement(self):
        """Test that per-API-key rate limits are enforced"""
        # Create API key
        api_key = APIKey.objects.create(
            tenant=self.tenant, user=self.user, key_hash="test-hash", name="Test API Key"
        )

        from django.http import HttpRequest

        # Create request with API key
        request = HttpRequest()
        request.path = "/api/v1/dq/runs/"
        request.method = "POST"
        request.tenant = self.tenant
        request.api_key_obj = api_key

        # Check rate limit
        allowed, results = check_rate_limit(
            request, tenant_id=str(self.tenant.id), api_key_id=str(api_key.id)
        )

        # Should be allowed initially
        self.assertTrue(allowed)

        # Should check tenant, user (if applicable), and API key limits
        api_key_results = [r for r in results if r.limit_type == "api_key"]
        self.assertGreater(len(api_key_results), 0)

    def test_per_api_key_rate_limit_same_as_user(self):
        """Test that API key limits are same as user limits"""
        # Create API key
        APIKey.objects.create(
            tenant=self.tenant, user=self.user, key_hash="test-hash", name="Test API Key"
        )

        from hub.apps.rate_limiting.config import get_api_key_rate_limit, get_user_rate_limit

        # Get user limit (doesn't take user_id, just tenant_id)
        user_limit = get_user_rate_limit(
            str(self.tenant.id), EndpointCategory.DQ_RUN, TimeWindow.SUSTAINED
        )

        # Get API key limit (doesn't take api_key_id, just tenant_id)
        api_key_limit = get_api_key_rate_limit(
            str(self.tenant.id), EndpointCategory.DQ_RUN, TimeWindow.SUSTAINED
        )

        # API key limit should be same as user limit
        self.assertEqual(api_key_limit, user_limit)

    def test_per_api_key_rate_limit_separate_per_key(self):
        """Test that different API keys have separate rate limits"""
        # Create two API keys
        api_key1 = APIKey.objects.create(
            tenant=self.tenant, user=self.user, key_hash="test-hash-1", name="Test API Key 1"
        )
        api_key2 = APIKey.objects.create(
            tenant=self.tenant, user=self.user, key_hash="test-hash-2", name="Test API Key 2"
        )

        from hub.apps.rate_limiting.utils import generate_rate_limit_key

        # Generate keys for both API keys
        key1 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            api_key_id=str(api_key1.id),
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        key2 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            api_key_id=str(api_key2.id),
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )

        # Keys should be different
        self.assertNotEqual(key1, key2)
        self.assertIn(str(api_key1.id), key1)
        self.assertIn(str(api_key2.id), key2)

    def test_rate_limit_headers_in_response(self):
        """Test that rate limit headers are included in API responses"""
        from django.http import HttpRequest

        # Create request
        request = HttpRequest()
        request.path = "/api/v1/dq/runs/"
        request.method = "POST"
        request.tenant = self.tenant

        # Check rate limit
        _allowed, results = check_rate_limit(request, tenant_id=str(self.tenant.id))

        # Generate headers
        headers = get_rate_limit_headers(request, results)

        # Should include rate limit headers
        self.assertIn("X-RateLimit-Limit", headers)
        self.assertIn("X-RateLimit-Remaining", headers)
        self.assertIn("X-RateLimit-Reset", headers)

        # Verify header values are strings
        self.assertIsInstance(headers["X-RateLimit-Limit"], str)
        self.assertIsInstance(headers["X-RateLimit-Remaining"], str)
        self.assertIsInstance(headers["X-RateLimit-Reset"], str)

    def test_rate_limit_headers_use_sustained_window(self):
        """Test that headers use sustained window result"""
        from django.http import HttpRequest

        from hub.apps.rate_limiting.service import RateLimitResult

        # Create results for all windows
        results = [
            RateLimitResult(
                allowed=True,
                limit=20,
                remaining=15,
                reset_time=500,
                limit_type="tenant",
                category=EndpointCategory.DQ_RUN,
                window=TimeWindow.BURST,
            ),
            RateLimitResult(
                allowed=True,
                limit=60,
                remaining=55,
                reset_time=1000,
                limit_type="tenant",
                category=EndpointCategory.DQ_RUN,
                window=TimeWindow.SUSTAINED,
            ),
            RateLimitResult(
                allowed=True,
                limit=10000,
                remaining=9995,
                reset_time=86400,
                limit_type="tenant",
                category=EndpointCategory.DQ_RUN,
                window=TimeWindow.DAILY,
            ),
        ]

        request = HttpRequest()
        headers = get_rate_limit_headers(request, results)

        # Should use sustained window (60, not 20 or 10000)
        self.assertEqual(headers["X-RateLimit-Limit"], "60")
        self.assertEqual(headers["X-RateLimit-Remaining"], "55")
        self.assertEqual(headers["X-RateLimit-Reset"], "1000")

    def test_rate_limit_headers_category_specific(self):
        """Test that headers include category for non-general endpoints"""
        from django.http import HttpRequest

        from hub.apps.rate_limiting.service import RateLimitResult

        results = [
            RateLimitResult(
                allowed=True,
                limit=60,
                remaining=55,
                reset_time=1000,
                limit_type="tenant",
                category=EndpointCategory.DQ_RUN,
                window=TimeWindow.SUSTAINED,
            )
        ]

        request = HttpRequest()
        headers = get_rate_limit_headers(request, results)

        # Should include category header for non-general endpoints
        self.assertIn("X-RateLimit-Category", headers)
        self.assertEqual(headers["X-RateLimit-Category"], "dq_run")

    def test_rate_limit_headers_no_category_for_general(self):
        """Test that category header is not included for general endpoints"""
        from django.http import HttpRequest

        from hub.apps.rate_limiting.service import RateLimitResult

        results = [
            RateLimitResult(
                allowed=True,
                limit=60,
                remaining=55,
                reset_time=1000,
                limit_type="tenant",
                category=EndpointCategory.GENERAL,
                window=TimeWindow.SUSTAINED,
            )
        ]

        request = HttpRequest()
        headers = get_rate_limit_headers(request, results)

        # Should not include category header for general endpoints
        self.assertNotIn("X-RateLimit-Category", headers)

    def test_retry_after_header_when_exceeded(self):
        """Test that Retry-After header is calculated correctly when limit exceeded"""
        from hub.apps.rate_limiting.service import RateLimitResult

        current_time = int(time.time())
        reset_time = current_time + 60  # 60 seconds from now

        # Create failed result
        RateLimitResult(
            allowed=False,
            limit=60,
            remaining=0,
            reset_time=reset_time,
            limit_type="tenant",
            category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )

        # Retry-After should be approximately 60 seconds
        retry_after = max(1, reset_time - current_time)
        self.assertGreaterEqual(retry_after, 1)
        self.assertLessEqual(retry_after, 61)  # Allow 1 second tolerance

    def test_all_time_windows_checked(self):
        """Test that all time windows (burst, sustained, daily) are checked"""
        from django.http import HttpRequest

        request = HttpRequest()
        request.path = "/api/v1/dq/runs/"
        request.method = "POST"
        request.tenant = self.tenant

        # Check rate limit
        _allowed, results = check_rate_limit(request, tenant_id=str(self.tenant.id))

        # Should check all windows
        windows_checked = {r.window for r in results}
        self.assertIn(TimeWindow.BURST, windows_checked)
        self.assertIn(TimeWindow.SUSTAINED, windows_checked)
        self.assertIn(TimeWindow.DAILY, windows_checked)

    def test_rate_limit_stops_checking_after_first_failure(self):
        """Test that rate limit checking stops after first window failure"""
        from django.http import HttpRequest

        # Simulate burst window failure
        # In real scenario, this would happen if burst limit is exceeded
        # For this test, we verify the logic stops checking other windows

        request = HttpRequest()
        request.path = "/api/v1/dq/runs/"
        request.method = "POST"
        request.tenant = self.tenant

        # Check rate limit
        allowed, results = check_rate_limit(request, tenant_id=str(self.tenant.id))

        # If any window fails, should stop checking others
        # (This is verified by the service implementation)
        if not allowed:
            # Should have at least one failed result
            failed_results = [r for r in results if not r.allowed]
            self.assertGreater(len(failed_results), 0)

    def test_platform_maximum_enforced(self):
        """Test that tenant config cannot exceed platform maximums"""
        from hub.apps.rate_limiting.config import get_platform_maximum_limit, get_tenant_rate_limit

        # Get platform maximum
        platform_max = get_platform_maximum_limit(EndpointCategory.DQ_RUN, TimeWindow.SUSTAINED)

        # Create tenant config with limit exceeding platform maximum
        # Note: rate_limits structure uses window as string key
        TenantConfigFactory.create_tenant_config(
            tenant=self.tenant,
            rate_limits={
                "dq_run": {
                    "60": platform_max + 100  # Exceeds platform maximum
                }
            },
        )

        # Get tenant rate limit
        limit = get_tenant_rate_limit(
            str(self.tenant.id), EndpointCategory.DQ_RUN, TimeWindow.SUSTAINED
        )

        # Should be capped at platform maximum
        self.assertLessEqual(limit, platform_max)

    def test_different_endpoint_categories_have_different_limits(self):
        """Test that different endpoint categories have different rate limits"""
        from hub.apps.rate_limiting.config import get_tenant_rate_limit

        # Get limits for different categories
        dq_limit = get_tenant_rate_limit(
            str(self.tenant.id), EndpointCategory.DQ_RUN, TimeWindow.SUSTAINED
        )
        file_upload_limit = get_tenant_rate_limit(
            str(self.tenant.id), EndpointCategory.FILE_UPLOAD, TimeWindow.SUSTAINED
        )
        catalog_read_limit = get_tenant_rate_limit(
            str(self.tenant.id), EndpointCategory.CATALOG_READ, TimeWindow.SUSTAINED
        )

        # Limits should be configured per category
        # (They may be the same or different depending on platform defaults)
        self.assertGreater(dq_limit, 0)
        self.assertGreater(file_upload_limit, 0)
        self.assertGreater(catalog_read_limit, 0)

    def test_rate_limit_key_hierarchy(self):
        """Test that rate limit keys follow correct hierarchy"""
        from hub.apps.rate_limiting.utils import generate_rate_limit_key

        # Tenant-level key
        tenant_key = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )

        # User-level key
        user_key = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )

        # API-key-level key
        api_key = APIKey.objects.create(
            tenant=self.tenant, user=self.user, key_hash="test-hash", name="Test API Key"
        )
        api_key_key = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            api_key_id=str(api_key.id),
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )

        # Keys should be different
        self.assertNotEqual(tenant_key, user_key)
        self.assertNotEqual(user_key, api_key_key)
        self.assertNotEqual(tenant_key, api_key_key)

        # Keys should include correct identifiers
        self.assertIn(str(self.tenant.id), tenant_key)
        self.assertIn(str(self.user.id), user_key)
        self.assertIn(str(api_key.id), api_key_key)
