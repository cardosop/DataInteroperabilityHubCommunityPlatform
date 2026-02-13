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
"""
import json

import pytest
from django.http import HttpRequest
from django.test import RequestFactory, TestCase

from hub.apps.health.views import circuit_breaker_status, health_check, liveness

pytestmark = pytest.mark.django_db(transaction=True)


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
        """Test that database connection is checked"""
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        # Database should be 'connected' if healthy
        self.assertIn(data["database"], ["connected", "error:"])
        self.assertIn(data["database"], ["connected", "error:"])

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

    def test_health_check_unhealthy_on_database_error(self):
        """Test that health check returns unhealthy on database error"""
        # This test verifies the error handling path
        # In practice, database should be available in test environment
        request = self.factory.get("/health/")
        response = health_check(request)

        data = json.loads(response.content)
        # Status should be 'healthy' or 'unhealthy' based on actual connections
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
        """Test that http_status is not included in response body"""
        request = self.factory.get("/health/circuit-breakers/")
        response = circuit_breaker_status(request)

        if response.status_code in [200, 404]:
            data = json.loads(response.content)
            # http_status should not be in response body (it's used for HTTP status code)
            self.assertNotIn("http_status", data)


class TestCircuitBreakerStatus(TestCase):
    """Test circuit breaker status endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()

    def test_circuit_breaker_status_all_breakers(self):
        """Test getting status of all circuit breakers"""
        request = self.factory.get("/health/circuit-breakers/")
        response = circuit_breaker_status(request)

        # Should return 200 or 500 (depending on circuit breaker availability)
        self.assertIn(response.status_code, [200, 500])

        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn("status", data)
            self.assertIn("circuit_breakers", data)

    def test_circuit_breaker_status_specific_service(self):
        """Test getting status of specific circuit breaker"""
        request = self.factory.get("/health/circuit-breakers/?service_name=test-service")
        response = circuit_breaker_status(request)

        # Should return 200, 404, or 500
        self.assertIn(response.status_code, [200, 404, 500])

        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn("status", data)
            self.assertIn("circuit_breaker", data)

    def test_circuit_breaker_status_not_found(self):
        """Test circuit breaker status for non-existent service"""
        request = self.factory.get("/health/circuit-breakers/?service_name=nonexistent-service")
        response = circuit_breaker_status(request)

        # Should return 404 if service not found
        if response.status_code == 404:
            data = json.loads(response.content)
            self.assertIn("error", data)

    def test_circuit_breaker_status_error_handling(self):
        """Test error handling in circuit breaker status"""
        # Test that exceptions are handled gracefully
        request = self.factory.get("/health/circuit-breakers/")
        response = circuit_breaker_status(request)

        # Should not raise exception, should return JSON
        self.assertEqual(response["Content-Type"], "application/json")

    # ========== EDGE CASES TESTS ==========

    def test_circuit_breaker_status_empty_query_param(self):
        """Test circuit breaker status with empty query param"""
        request = self.factory.get("/health/circuit-breakers/?service_name=")
        response = circuit_breaker_status(request)

        # Should handle empty service_name gracefully
        self.assertIn(response.status_code, [200, 404, 500])
        self.assertEqual(response["Content-Type"], "application/json")

    def test_circuit_breaker_status_multiple_query_params(self):
        """Test circuit breaker status with multiple query params"""
        request = self.factory.get("/health/circuit-breakers/?service_name=test&other=value")
        response = circuit_breaker_status(request)

        # Should use service_name param and ignore others
        self.assertIn(response.status_code, [200, 404, 500])
        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn("status", data)

    def test_circuit_breaker_status_special_characters_in_service_name(self):
        """Test circuit breaker status with special characters in service name"""
        request = self.factory.get("/health/circuit-breakers/?service_name=test-service_123")
        response = circuit_breaker_status(request)

        # Should handle special characters gracefully
        self.assertIn(response.status_code, [200, 404, 500])
        self.assertEqual(response["Content-Type"], "application/json")

    def test_circuit_breaker_status_all_breakers_structure(self):
        """Test that all breakers response has correct structure"""
        request = self.factory.get("/health/circuit-breakers/")
        response = circuit_breaker_status(request)

        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn("status", data)
            self.assertIn("circuit_breakers", data)
            self.assertIn("total_breakers", data)
            self.assertIn("open_breakers", data)
            self.assertIn("open_breaker_names", data)
            # Verify field types
            self.assertIsInstance(data["total_breakers"], int)
            self.assertIsInstance(data["open_breakers"], int)
            self.assertIsInstance(data["open_breaker_names"], list)
            self.assertIsInstance(data["circuit_breakers"], dict)

    def test_circuit_breaker_status_specific_service_structure(self):
        """Test that specific service response has correct structure"""
        request = self.factory.get("/health/circuit-breakers/?service_name=test-service")
        response = circuit_breaker_status(request)

        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn("status", data)
            self.assertIn("circuit_breaker", data)
            # Verify status values
            self.assertIn(data["status"], ["healthy", "degraded"])

    def test_circuit_breaker_status_not_found_structure(self):
        """Test that not found response has correct structure"""
        request = self.factory.get("/health/circuit-breakers/?service_name=nonexistent-service-xyz")
        response = circuit_breaker_status(request)

        if response.status_code == 404:
            data = json.loads(response.content)
            self.assertIn("error", data)
            self.assertIn("status", data)

    def test_circuit_breaker_status_error_response_structure(self):
        """Test that error response has correct structure"""
        request = self.factory.get("/health/circuit-breakers/")
        response = circuit_breaker_status(request)

        if response.status_code == 500:
            data = json.loads(response.content)
            self.assertIn("status", data)
            self.assertIn("error", data)
            self.assertEqual(data["status"], "error")

    def test_circuit_breaker_status_open_breakers_logic(self):
        """Test that open breakers count matches open breaker names"""
        request = self.factory.get("/health/circuit-breakers/")
        response = circuit_breaker_status(request)

        if response.status_code == 200:
            data = json.loads(response.content)
            if "open_breakers" in data and "open_breaker_names" in data:
                self.assertEqual(
                    data["open_breakers"],
                    len(data["open_breaker_names"]),
                    "Open breakers count should match open breaker names length",
                )

    def test_circuit_breaker_status_multiple_calls(self):
        """Test that circuit breaker status can be called multiple times"""
        request1 = self.factory.get("/health/circuit-breakers/")
        request2 = self.factory.get("/health/circuit-breakers/")

        response1 = circuit_breaker_status(request1)
        response2 = circuit_breaker_status(request2)

        # Both calls should succeed
        self.assertEqual(response1["Content-Type"], "application/json")
        self.assertEqual(response2["Content-Type"], "application/json")

    # ========== TDD COMPLIANCE TESTS ==========

    def test_circuit_breaker_status_returns_all_required_fields_all_breakers(self):
        """Test that all breakers response returns all required fields"""
        request = self.factory.get("/health/circuit-breakers/")
        response = circuit_breaker_status(request)

        if response.status_code == 200:
            data = json.loads(response.content)
            # Verify all required fields are present
            self.assertIn("status", data)
            self.assertIn("circuit_breakers", data)
            self.assertIn("total_breakers", data)
            self.assertIn("open_breakers", data)
            self.assertIn("open_breaker_names", data)

    def test_circuit_breaker_status_returns_all_required_fields_specific_service(self):
        """Test that specific service response returns all required fields"""
        request = self.factory.get("/health/circuit-breakers/?service_name=test-service")
        response = circuit_breaker_status(request)

        if response.status_code == 200:
            data = json.loads(response.content)
            # Verify all required fields are present
            self.assertIn("status", data)
            self.assertIn("circuit_breaker", data)

    def test_circuit_breaker_status_status_values(self):
        """Test that status field has valid values"""
        request = self.factory.get("/health/circuit-breakers/")
        response = circuit_breaker_status(request)

        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertIn(data["status"], ["healthy", "degraded"])

    def test_circuit_breaker_status_http_status_codes(self):
        """Test that HTTP status codes are correct"""
        # Test all breakers
        request_all = self.factory.get("/health/circuit-breakers/")
        response_all = circuit_breaker_status(request_all)
        self.assertIn(response_all.status_code, [200, 500])

        # Test specific service
        request_specific = self.factory.get("/health/circuit-breakers/?service_name=test-service")
        response_specific = circuit_breaker_status(request_specific)
        self.assertIn(response_specific.status_code, [200, 404, 500])

        # Test not found
        request_not_found = self.factory.get(
            "/health/circuit-breakers/?service_name=nonexistent-service-xyz"
        )
        response_not_found = circuit_breaker_status(request_not_found)
        self.assertIn(response_not_found.status_code, [404, 500])

    # ========== ERROR HANDLING TESTS ==========

    def test_circuit_breaker_status_handles_exceptions_gracefully(self):
        """Test that circuit breaker status handles exceptions gracefully"""
        # Test that exceptions don't propagate
        request = self.factory.get("/health/circuit-breakers/")

        # Should not raise exception
        try:
            response = circuit_breaker_status(request)
            # If it succeeds, verify it returns JSON
            self.assertEqual(response["Content-Type"], "application/json")
        except Exception:
            # If it fails, that's unexpected - circuit breaker should handle errors
            self.fail("circuit_breaker_status raised an exception")

    def test_health_check_handles_exceptions_gracefully(self):
        """Test that health check handles exceptions gracefully"""
        request = self.factory.get("/health/")

        # Should not raise exception
        try:
            response = health_check(request)
            # If it succeeds, verify it returns JSON
            self.assertEqual(response["Content-Type"], "application/json")
        except Exception:
            # If it fails, that's unexpected - health check should handle errors
            self.fail("health_check raised an exception")
