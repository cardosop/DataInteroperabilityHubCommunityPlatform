"""
Unit tests for tenant middleware.
"""

import uuid
from unittest.mock import Mock

import pytest
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, TestCase

from hub.apps.tenants.middleware import TenantSuspensionMiddleware
from hub.apps.tenants.models import Tenant, TenantStatus

pytestmark = pytest.mark.django_db(transaction=True)


class TenantSuspensionMiddlewareTest(TestCase):
    """Test TenantSuspensionMiddleware"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = TenantSuspensionMiddleware(self.get_response)
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        # Ensure tenant has an active subscription (required by Phase 25.2.4 subscription check)
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        ensure_tenant_has_active_subscription(self.tenant)

    def test_suspended_tenant_blocks_writes(self):
        """Test that suspended tenant blocks write operations with meaningful error."""
        self.tenant.suspend()

        request = self.factory.post("/api/assets/")
        request.tenant = self.tenant

        response = self.middleware.process_request(request)

        self.assertIsNotNone(response, "Middleware should block write on suspended tenant")
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)
        # Verify response body contains actionable error info
        import json

        body = json.loads(response.content)
        self.assertIn("error", body, "403 response must include 'error' field")
        self.assertIn("suspended", body["error"].lower(), "Error should mention suspension")

    def test_suspended_tenant_allows_reads(self):
        """Test that suspended tenant allows read operations"""
        self.tenant.suspend()

        request = self.factory.get("/api/assets/")
        request.tenant = self.tenant

        response = self.middleware.process_request(request)

        self.assertIsNone(response)  # Middleware allows request to continue

    def test_deleted_tenant_blocks_all(self):
        """Test that deleted tenant blocks all operations"""
        self.tenant.soft_delete()

        request = self.factory.get("/api/assets/")
        request.tenant = self.tenant

        response = self.middleware.process_request(request)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)

    def test_active_tenant_allows_all(self):
        """Test that active tenant allows all operations"""
        request = self.factory.post("/api/assets/")
        request.tenant = self.tenant

        response = self.middleware.process_request(request)

        self.assertIsNone(response)  # Middleware allows request to continue

    def test_allowed_paths_bypass_middleware(self):
        """Test that allowed paths bypass middleware"""
        self.tenant.suspend()

        request = self.factory.post("/health/")
        request.tenant = self.tenant

        response = self.middleware.process_request(request)

        self.assertIsNone(response)  # Health check is allowed

    def test_auth_paths_bypass_middleware(self):
        """Test that /api/v1/auth/ paths bypass subscription/suspension checks."""
        self.tenant.suspend()
        request = self.factory.post("/api/v1/auth/logout/")
        request.tenant = self.tenant
        request.tenant_id = str(self.tenant.id)
        response = self.middleware.process_request(request)
        self.assertIsNone(
            response, "Auth paths must be allowed regardless of subscription/suspension"
        )

    def test_auth_sessions_revoke_bypass_middleware(self):
        """Test that POST /api/v1/auth/sessions/<id>/revoke/ bypasses subscription check."""
        self.tenant.suspend()
        request = self.factory.post(
            "/api/v1/auth/sessions/00000000-0000-0000-0000-000000000001/revoke/"
        )
        request.tenant = self.tenant
        request.tenant_id = str(self.tenant.id)
        response = self.middleware.process_request(request)
        self.assertIsNone(
            response, "Session revoke must be allowed regardless of subscription/suspension"
        )

    def test_middleware_is_callable(self):
        """Test that middleware is callable (Django 6 pattern)"""
        request = self.factory.get("/api/v1/assets/")
        request.tenant = self.tenant

        response = self.middleware(request)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, HttpResponse)
        self.get_response.assert_called_once()

    def test_middleware_performance(self):
        """Test middleware performance (should be fast)"""
        import time

        request = self.factory.get("/api/v1/assets/")
        request.tenant = self.tenant

        start = time.time()
        for _ in range(100):
            self.middleware.process_request(request)
        elapsed = time.time() - start

        # 2s budget avoids flakes on slow CI machines
        self.assertLess(
            elapsed,
            2.0,
            f"Middleware too slow: {elapsed:.3f}s for 100 requests",
        )

    # ── C8: Subscription enforcement tests ───────────────────────
    def test_no_subscription_blocks_writes(self):
        """Middleware blocks writes when tenant has no subscription."""
        from hub.apps.billing.models import Subscription

        Subscription.objects.filter(tenant=self.tenant).delete()

        request = self.factory.post("/api/v1/assets/")
        request.tenant = self.tenant

        response = self.middleware.process_request(request)

        self.assertIsNotNone(
            response,
            "Should block writes without subscription",
        )
        self.assertEqual(response.status_code, 403)
        import json

        body = json.loads(response.content)
        self.assertEqual(body["code"], "subscription_inactive")

    def test_no_subscription_allows_reads(self):
        """Middleware allows reads when tenant has no subscription."""
        from hub.apps.billing.models import Subscription

        Subscription.objects.filter(tenant=self.tenant).delete()

        request = self.factory.get("/api/v1/assets/")
        request.tenant = self.tenant

        response = self.middleware.process_request(request)
        self.assertIsNone(response)

    def test_past_due_subscription_blocks_writes(self):
        """Middleware blocks writes for PAST_DUE subscription."""
        from hub.apps.billing.models import Subscription, SubscriptionStatus

        sub = Subscription.objects.filter(tenant=self.tenant).first()
        if sub:
            sub.status = SubscriptionStatus.PAST_DUE
            sub.save()

        request = self.factory.post("/api/v1/assets/")
        request.tenant = self.tenant

        response = self.middleware.process_request(request)

        self.assertIsNotNone(
            response,
            "Should block writes for PAST_DUE subscription",
        )
        self.assertEqual(response.status_code, 403)
        import json

        body = json.loads(response.content)
        self.assertEqual(body["code"], "subscription_inactive")

    def test_canceled_subscription_blocks_writes(self):
        """Middleware blocks writes for CANCELED subscription."""
        from hub.apps.billing.models import Subscription, SubscriptionStatus

        sub = Subscription.objects.filter(tenant=self.tenant).first()
        if sub:
            sub.status = SubscriptionStatus.CANCELED
            sub.save()

        request = self.factory.post("/api/v1/assets/")
        request.tenant = self.tenant

        response = self.middleware.process_request(request)

        self.assertIsNotNone(
            response,
            "Should block writes for CANCELED subscription",
        )
        self.assertEqual(response.status_code, 403)

    def test_active_subscription_allows_writes(self):
        """Middleware allows writes for ACTIVE subscription (control)."""
        # setUp already ensures active subscription
        request = self.factory.post("/api/v1/assets/")
        request.tenant = self.tenant

        response = self.middleware.process_request(request)
        self.assertIsNone(
            response,
            "Active subscription should allow writes",
        )

    # ── H11+H10+H13: Middleware tenant resolution via __call__ ───
    def test_call_resolves_tenant_from_user(self):
        """__call__ resolves tenant from authenticated user object."""
        from django.contrib.auth import get_user_model

        from hub.apps.users.models import UserStatus

        User = get_user_model()

        uid = uuid.uuid4().hex[:8]
        user = User.objects.create_user(
            email=f"mw-user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        request = self.factory.get("/api/v1/assets/")
        request._force_auth_user = user
        # Do NOT set request.tenant — middleware must resolve it

        response = self.middleware(request)

        self.assertIsNotNone(response)
        # Middleware should have set request.tenant
        self.assertEqual(
            getattr(request, "tenant", None),
            self.tenant,
        )


class TenantSuspensionMiddlewareExtendedTests(TestCase):
    """Additional middleware coverage: ALLOWED_PATHS, cache paths,
    exception handling, and edge cases."""

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.middleware = TenantSuspensionMiddleware(lambda r: None)
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Ext-Tenant {uid}",
            slug=f"ext-tenant-{uid}",
            status=TenantStatus.ACTIVE,
        )

    # ── ALLOWED_PATHS ────────────────────────────────────────────────

    def test_platform_path_bypasses_middleware(self):
        """Requests to /api/v1/platform/ are allowed through."""
        request = self.factory.get("/api/v1/platform/some-endpoint/")
        response = self.middleware.process_request(request)
        self.assertIsNone(response)

    def test_onboarding_path_bypasses_middleware(self):
        """Requests to /api/v1/tenants/onboarding/ are allowed through."""
        request = self.factory.post("/api/v1/tenants/onboarding/")
        response = self.middleware.process_request(request)
        self.assertIsNone(response)

    # ── Tenant-not-found ──────────────────────────────────────────────

    def test_nonexistent_tenant_returns_none(self):
        """When the tenant ID is set but doesn't exist, middleware returns None."""
        request = self.factory.post("/api/v1/assets/")
        request.tenant_id = "00000000-0000-0000-0000-000000000000"
        response = self.middleware.process_request(request)
        # Middleware can't resolve the tenant → falls through to next
        # middleware.  The view should return 404/403 on its own.
        self.assertIsNone(response)

    # ── Subscription cache hit ───────────────────────────────────────

    def test_subscription_cache_hit_blocked_status(self):
        """Cache hit with PAST_DUE status returns 403 without DB query."""
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )

        ensure_tenant_has_active_subscription(self.tenant)
        # Prime the cache with a blocked status.
        cache_key = f"tenant_sub_check:{self.tenant.id}"
        from django.core.cache import cache as _cache

        _cache.set(cache_key, "PAST_DUE", 30)

        request = self.factory.post("/api/v1/assets/")
        request.tenant_id = str(self.tenant.id)
        response = self.middleware.process_request(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)

    def test_subscription_cache_hit_active_allows_write(self):
        """Cache hit with ACTIVE status allows the write."""
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )

        ensure_tenant_has_active_subscription(self.tenant)
        cache_key = f"tenant_sub_check:{self.tenant.id}"
        from django.core.cache import cache as _cache

        _cache.set(cache_key, "ACTIVE", 30)

        request = self.factory.post("/api/v1/assets/")
        request.tenant_id = str(self.tenant.id)
        response = self.middleware.process_request(request)
        self.assertIsNone(response)

    # ── Exception handling ────────────────────────────────────────────

    def test_read_requests_allowed_without_subscription(self):
        """GET requests pass through even when no subscription exists
        (subscription check only gates write methods)."""
        request = self.factory.get("/api/v1/assets/")
        request.tenant_id = str(self.tenant.id)
        response = self.middleware.process_request(request)
        self.assertIsNone(response)
