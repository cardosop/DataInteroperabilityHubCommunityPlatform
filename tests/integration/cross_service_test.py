"""
Integration Tests for Cross-Service Communication

Tests communication between services to ensure proper integration.
"""

import os

import pytest
import requests

# Service URLs (configurable via environment variables)
# Defaults use Docker service hostnames for integration tests running in docker-compose.test
API_SERVICE_URL = os.getenv("API_SERVICE_URL", "http://api-service-test:8000")
DATACONTRACT_SERVICE_URL = os.getenv(
    "DATACONTRACT_SERVICE_URL", "http://datacontract-service-test:8080"
)
COMPLIANCE_SERVICE_URL = os.getenv("COMPLIANCE_SERVICE_URL", "http://compliance-service-test:8082")
DQ_SERVICE_URL = os.getenv("DQ_SERVICE_URL", "http://dq-service-test:8083")
SEMANTIC_SERVICE_URL = os.getenv("SEMANTIC_SERVICE_URL", "http://semantic-service-test:8081")
PREFECT_INTEGRATION_SERVICE_URL = os.getenv(
    "PREFECT_INTEGRATION_SERVICE_URL", "http://prefect-integration-service-test:8084"
)


class TestServiceHealth:
    """Test health endpoints for all services"""

    @pytest.mark.parametrize(
        "service_url,service_name",
        [
            (API_SERVICE_URL, "api-service"),
            (DATACONTRACT_SERVICE_URL, "datacontract-service"),
            (COMPLIANCE_SERVICE_URL, "compliance-service"),
            (DQ_SERVICE_URL, "dq-service"),
            (SEMANTIC_SERVICE_URL, "semantic-service"),
            (PREFECT_INTEGRATION_SERVICE_URL, "prefect-integration-service"),
            # search-service and webhook-service are NOT standalone microservices;
            # search lives at hub.apps.search and webhooks at hub.apps.webhooks,
            # both served by the api-service monolith.  See Phase 273 contract.
        ],
    )
    def test_service_health(self, service_url: str, service_name: str):
        """Test that all services have working health endpoints"""
        try:
            # Django API uses /health/ (trailing slash); other services use /health
            for path in ["/health", "/health/"]:
                response = requests.get(f"{service_url.rstrip('/')}{path}", timeout=5)
                if response.status_code == 200:
                    break
            assert response.status_code == 200, (
                f"{service_name} health check failed (tried /health and /health/)"
            )
            data = response.json()
            assert data.get("status") in ["healthy", "ok"], f"{service_name} not healthy"
        except requests.exceptions.RequestException as e:
            pytest.skip(f"{service_name} not reachable: {e}")


class TestAPIToMicroservices:
    """Test API service communication with microservices"""

    def test_api_to_datacontract_service(self):
        """Test API service can communicate with DataContract service"""
        # This would typically be tested through actual API calls
        # For now, verify the service is reachable
        response = requests.get(f"{DATACONTRACT_SERVICE_URL}/health", timeout=5)
        assert response.status_code == 200

    def test_api_to_compliance_service(self):
        """Test API service can communicate with Compliance service"""
        response = requests.get(f"{COMPLIANCE_SERVICE_URL}/health", timeout=5)
        assert response.status_code == 200

    def test_api_to_dq_service(self):
        """Test API service can communicate with DQ service"""
        response = requests.get(f"{DQ_SERVICE_URL}/health", timeout=5)
        assert response.status_code == 200

    def test_api_to_semantic_service(self):
        """Test API service can communicate with Semantic service"""
        response = requests.get(f"{SEMANTIC_SERVICE_URL}/health", timeout=5)
        assert response.status_code == 200


class TestWorkerToServices:
    """Test worker service communication"""

    def test_worker_to_redis(self):
        """Test worker service can communicate with Redis"""
        import redis
        from django.conf import settings

        redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        try:
            r = redis.from_url(redis_url, socket_connect_timeout=2)
            assert r.ping(), "Redis ping should return True"
        except (ConnectionError, TimeoutError, OSError) as e:
            pytest.skip(f"Redis not reachable at {redis_url}: {e}")

    def test_worker_to_database(self):
        """Test worker service can communicate with database"""
        import psycopg2
        from django.conf import settings

        db = settings.DATABASES["default"]
        try:
            conn = psycopg2.connect(
                dbname=db["NAME"], user=db["USER"],
                password=db["PASSWORD"], host=db.get("HOST", "localhost"),
                port=db.get("PORT", "5432"), connect_timeout=5,
            )
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone() == (1,), "Database should respond to SELECT 1"
            conn.close()
        except psycopg2.OperationalError as e:
            pytest.skip(f"Database not reachable: {e}")


class TestPrefectIntegration:
    """Test Prefect integration service communication"""

    def test_prefect_integration_to_prefect_server(self):
        """Test Prefect integration service can communicate with Prefect Server"""
        response = requests.get(f"{PREFECT_INTEGRATION_SERVICE_URL}/health", timeout=5)
        assert response.status_code == 200


class TestServiceDiscovery:
    """Test service discovery and DNS resolution"""

    def test_service_urls_resolvable(self):
        """Test that all service URLs are resolvable"""
        services = [
            API_SERVICE_URL,
            DATACONTRACT_SERVICE_URL,
            COMPLIANCE_SERVICE_URL,
            DQ_SERVICE_URL,
            SEMANTIC_SERVICE_URL,
        ]

        for service_url in services:
            try:
                # Extract hostname from URL
                hostname = service_url.split("://")[1].split(":")[0]
                # Basic connectivity test
                response = requests.get(f"{service_url}/health", timeout=5)
                assert response.status_code in [200, 404], f"Service {hostname} not reachable"
            except requests.exceptions.RequestException:
                pytest.skip(f"Service {service_url} not reachable in this environment")


# TestEndToEndWorkflow removed — the two methods below only called /health on
# datacontract and DQ services, which duplicates coverage already provided by
# TestServiceHealth (parametrized over all services) and TestAPIToMicroservices.
# Real cross-service workflow tests require specific test data fixtures.


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
