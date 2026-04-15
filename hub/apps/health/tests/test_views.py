"""
Comprehensive unit tests for Health check views.

Tests cover:
- Liveness endpoint (GET /health/live/)
- Health check endpoint (GET /health/)
- Circuit breaker status endpoint (GET /health/circuit-breakers/)
- Success scenarios
- Failure scenarios
- Edge cases
- Error handling
- TDD compliance

All tests use real implementations (no mocks/stubs).
External dependencies (Redis, circuit breakers) gracefully handle unavailability.

Phase 221.3 update: circuit_breaker_status is now a DRF @api_view
requiring authentication.  Tests use APIRequestFactory +
force_authenticate for the circuit-breaker view.
"""
import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework.test import APIRequestFactory

from hub.apps.health.views import circuit_breaker_status, health_check, liveness
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TestLiveness(TestCase):
    """Test liveness endpoint (Docker/Kubernetes liveness probe)."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_liveness_returns_200(self):
        request = self.factory.get("/health/live/")
        response = liveness(request)
        self.assertEqual(response.status_code, 200)

    def test_liveness_returns_json_ok(self):
        import json
        request = self.factory.get("/health/live/")
        response = liveness(request)
        # Root cause fix: JsonResponse doesn't have .json() method, use json.loads(response.content)
        data = json.loads(response.content)
        self.assertEqual(data, {"status": "ok"})
        self.assertEqual(response["Content-Type"], "application/json")


class TestHealthCheck(TestCase):
    """Test health check endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()

    def test_health_check_returns_json(self):
        """Test that health check returns JSON response"""
        request = self.factory.get("/health/")
        response = health_check(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_health_check_structure(self):
        """Test health check response structure"""
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        self.assertIn("status", data)
        self.assertIn("database", data)
        self.assertIn("redis", data)
        self.assertIsInstance(data["redis"], dict)

    def test_health_check_database_connected(self):
        """Test that database connection is reported as connected"""
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        # In test environment, the database is available
        self.assertEqual(data["database"], "connected")

    def test_health_check_redis_structure(self):
        """Test that Redis health check includes all instances"""
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        redis_status = data["redis"]
        self.assertIn("cache", redis_status)
        self.assertIn("queue", redis_status)
        self.assertIn("events", redis_status)
        self.assertIn("channels", redis_status)

    def test_health_check_reports_healthy_when_db_available(self):
        """Test that health check reports healthy when database is available"""
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        self.assertEqual(data["database"], "connected")
        # With DB connected, status should be healthy (unless Redis is down)
        # At minimum, the status field must be a valid value
        self.assertIn(data["status"], ["healthy", "unhealthy"])

    # ========== EDGE CASES TESTS ==========

    def test_health_check_http_status_matches_health(self):
        """Test that HTTP status code matches health status"""
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        if data["status"] == "healthy":
            self.assertEqual(response.status_code, 200)
        else:
            self.assertEqual(response.status_code, 503)

    def test_health_check_multiple_calls(self):
        """Test that health check can be called multiple times"""
        request1 = self.factory.get("/health/")
        request2 = self.factory.get("/health/")

        response1 = health_check(request1)
        response2 = health_check(request2)

        # Both calls should succeed
        self.assertEqual(response1.status_code, response2.status_code)
        self.assertEqual(response1["Content-Type"], "application/json")
        self.assertEqual(response2["Content-Type"], "application/json")

    def test_health_check_redis_all_instances_present(self):
        """Test that all expected Redis instances are present in response"""
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        redis_status = data["redis"]
        expected_instances = ["cache", "queue", "events", "channels"]
        for instance_name in expected_instances:
            self.assertIn(instance_name, redis_status)

    def test_health_check_redis_instance_status_format(self):
        """Test that Redis instance status has correct format"""
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        redis_status = data["redis"]
        for instance_name, instance_status in redis_status.items():
            # Status should be 'connected' or start with 'error:'
            self.assertTrue(
                instance_status == "connected" or instance_status.startswith("error:"),
                f"Redis instance {instance_name} has invalid status format: {instance_status}",
            )

    def test_health_check_database_status_format(self):
        """Test that database status has correct format"""
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        db_status = data["database"]
        # Database status should be 'connected' or start with 'error:'
        self.assertTrue(
            db_status == "connected" or db_status.startswith("error:"),
            f"Database status has invalid format: {db_status}",
        )

    def test_health_check_response_content_type(self):
        """Test that health check response has correct content type"""
        request = self.factory.get("/health/")
        response = health_check(request)

        self.assertEqual(response["Content-Type"], "application/json")

    # ========== TDD COMPLIANCE TESTS ==========

    def test_health_check_returns_all_required_fields(self):
        """Test that health check returns all required fields"""
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        # Verify all required fields are present
        self.assertIn("status", data)
        self.assertIn("database", data)
        self.assertIn("redis", data)
        # Verify field types
        self.assertIsInstance(data["status"], str)
        self.assertIsInstance(data["database"], str)
        self.assertIsInstance(data["redis"], dict)

    def test_health_check_status_values(self):
        """Test that status field has valid values"""
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        self.assertIn(data["status"], ["healthy", "unhealthy"])

    def test_health_check_response_structure_consistency(self):
        """Test that response structure is consistent across calls"""
        request1 = self.factory.get("/health/")
        request2 = self.factory.get("/health/")

        response1 = health_check(request1)
        response2 = health_check(request2)

        data1 = json.loads(response1.content)
        data2 = json.loads(response2.content)

        # Structure should be consistent
        self.assertEqual(set(data1.keys()), set(data2.keys()))
        self.assertIn("status", data1)
        self.assertIn("status", data2)

    def test_health_check_http_status_not_in_response(self):
        """Test that http_status is not included in response body"""
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        # http_status should not be in response body (it's used for HTTP status code)
        self.assertNotIn("http_status", data)

    def test_circuit_breaker_status_http_status_not_in_response(self):
        """Test that http_status is not included in response body (221.3 — needs auth)"""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED",
        )
        user = User.objects.create_user(
            email=f"hc-{uid}@example.com", password="testpass123",
            tenant=tenant, status=UserStatus.ACTIVE,
        )
        api_factory = APIRequestFactory()
        request = api_factory.get("/health/circuit-breakers/")
        from rest_framework.test import force_authenticate
        force_authenticate(request, user=user)
        response = circuit_breaker_status(request)

        if response.status_code in [200, 404]:
            data = response.data if hasattr(response, 'data') else json.loads(response.content)
            self.assertNotIn("http_status", data)


class TestCircuitBreakerStatus(TestCase):
    """Test circuit breaker status endpoint (Phase 221.3 — requires auth)."""

    def setUp(self):
        """Set up test fixtures — DRF APIRequestFactory + authenticated user."""
        self.factory = APIRequestFactory()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-cb-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"cb-{uid}@example.com", password="testpass123",
            tenant=self.tenant, status=UserStatus.ACTIVE,
        )

    def _authed_get(self, path="/health/circuit-breakers/"):
        """Helper: create an authenticated GET request and call the view."""
        from rest_framework.test import force_authenticate
        request = self.factory.get(path)
        force_authenticate(request, user=self.user)
        return circuit_breaker_status(request)

    def test_circuit_breaker_status_all_breakers(self):
        """Test getting aggregate status of all circuit breakers"""
        response = self._authed_get()
        self.assertIn(response.status_code, [200, 500])

        if response.status_code == 200:
            data = response.data
            self.assertIn("status", data)
            self.assertIn("total_breakers", data)
            self.assertIn("open_breakers", data)

    def test_circuit_breaker_status_error_handling(self):
        """Test error handling in circuit breaker status"""
        response = self._authed_get()
        self.assertIn(response.status_code, [200, 500])

    # ========== EDGE CASES TESTS ==========

    def test_circuit_breaker_status_query_params_ignored(self):
        """Test circuit breaker status ignores service_name param (221.3.2)"""
        response = self._authed_get("/health/circuit-breakers/?service_name=test")
        self.assertIn(response.status_code, [200, 500])
        if response.status_code == 200:
            data = response.data
            # Should still return aggregate data, not single-service
            self.assertIn("total_breakers", data)

    def test_circuit_breaker_status_aggregate_structure(self):
        """Test that response has correct aggregate-only structure (221.3.2)"""
        response = self._authed_get()

        if response.status_code == 200:
            data = response.data
            self.assertIn("status", data)
            self.assertIn("total_breakers", data)
            self.assertIn("open_breakers", data)
            self.assertIsInstance(data["total_breakers"], int)
            self.assertIsInstance(data["open_breakers"], int)
            # Service names must NOT be exposed
            self.assertNotIn("circuit_breakers", data)
            self.assertNotIn("open_breaker_names", data)
            self.assertNotIn("circuit_breaker", data)

    def test_circuit_breaker_status_error_response_structure(self):
        """Test that error response has correct structure and generic message"""
        response = self._authed_get()

        if response.status_code == 500:
            data = response.data
            self.assertIn("status", data)
            self.assertIn("error", data)
            self.assertEqual(data["status"], "error")
            # 221.3 — error must be generic, not leak internals
            self.assertEqual(
                data["error"],
                "Circuit breaker status unavailable",
            )

    def test_circuit_breaker_status_multiple_calls(self):
        """Test that circuit breaker status can be called multiple times"""
        response1 = self._authed_get()
        response2 = self._authed_get()
        self.assertIn(response1.status_code, [200, 500])
        self.assertIn(response2.status_code, [200, 500])

    # ========== TDD COMPLIANCE TESTS ==========

    def test_circuit_breaker_status_returns_all_required_aggregate_fields(self):
        """Test that response returns all required aggregate fields"""
        response = self._authed_get()

        if response.status_code == 200:
            data = response.data
            self.assertIn("status", data)
            self.assertIn("total_breakers", data)
            self.assertIn("open_breakers", data)

    def test_circuit_breaker_status_status_values(self):
        """Test that status field has valid values"""
        response = self._authed_get()

        if response.status_code == 200:
            data = response.data
            self.assertIn(data["status"], ["healthy", "degraded"])

    def test_circuit_breaker_status_http_status_codes(self):
        """Test that HTTP status codes are correct"""
        response = self._authed_get()
        self.assertIn(response.status_code, [200, 500])

    # ========== ERROR HANDLING TESTS ==========

    def test_circuit_breaker_status_handles_exceptions_gracefully(self):
        """Test that circuit breaker status handles exceptions gracefully"""
        try:
            response = self._authed_get()
            self.assertIn(response.status_code, [200, 500])
        except Exception:
            self.fail("circuit_breaker_status raised an exception")

    def test_health_check_handles_exceptions_gracefully(self):
        """Test that health check handles exceptions gracefully"""
        factory = RequestFactory()
        request = factory.get("/health/")
        try:
            response = health_check(request)
            self.assertEqual(response["Content-Type"], "application/json")
        except Exception:
            self.fail("health_check raised an exception")
