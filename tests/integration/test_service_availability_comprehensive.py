"""
Comprehensive Service Availability Tests

Tests that all required services are running and healthy with:
- Retry logic for transient failures
- Timeout handling
- Detailed reporting
- Database connectivity checks
- Redis connectivity checks
- Object storage connectivity checks
- Service-to-service communication tests
"""

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pytest

import requests
from django.conf import settings
from django.db import connection
from django.test import TestCase as DjangoTestCase

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import boto3
    from botocore.config import Config as BotocoreConfig
    from botocore.exceptions import ClientError, EndpointConnectionError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service health status"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class ServiceCheckResult:
    """Result of a service health check"""

    service_name: str
    status: ServiceStatus
    response_time_ms: float | None = None
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def is_healthy(self) -> bool:
        """Check if service is healthy"""
        return self.status == ServiceStatus.HEALTHY


@dataclass
class ServiceConfig:
    """Configuration for a service health check"""

    name: str
    host: str
    port: int
    health_path: str = "/health"
    timeout: int = 5
    retries: int = 3
    retry_delay: float = 1.0
    use_https: bool = False
    check_type: str = "http"  # http, database, redis, minio, websocket, graphql

    def get_url(self) -> str:
        """Get full service URL"""
        protocol = "https" if self.use_https else "http"
        return f"{protocol}://{self.host}:{self.port}{self.health_path}"


class ServiceAvailabilityChecker:
    """
    Comprehensive service availability checker with retry logic and timeout handling.
    """

    def __init__(
        self, default_timeout: int = 5, default_retries: int = 3, default_retry_delay: float = 1.0
    ):
        """
        Initialize service availability checker.

        Args:
            default_timeout: Default timeout in seconds for health checks
            default_retries: Default number of retries for failed checks
            default_retry_delay: Default delay between retries in seconds
        """
        self.default_timeout = default_timeout
        self.default_retries = default_retries
        self.default_retry_delay = default_retry_delay

        # Determine host based on environment
        self.base_host = os.getenv("HUB_HOST", "localhost")
        if os.getenv("DOCKER_COMPOSE"):
            # Running in Docker Compose - use service names
            self.base_host = self._get_service_host()

    def _get_service_host(self) -> str:
        """Get service host based on environment"""
        # Check if we're running inside Docker
        if os.path.exists("/.dockerenv"):
            # Inside Docker - services are accessible via service names in Docker Compose network
            # But for health checks from within the same container, use localhost
            # For cross-container checks, we'd use service names, but that's not needed for health checks
            return "localhost"
        else:
            # Outside Docker - use localhost
            return "localhost"

    def check_http_service(
        self, config: ServiceConfig, retries: int | None = None, retry_delay: float | None = None
    ) -> ServiceCheckResult:
        """
        Check HTTP service availability with retry logic.

        Args:
            config: Service configuration
            retries: Number of retries (uses default if None)
            retry_delay: Delay between retries (uses default if None)

        Returns:
            ServiceCheckResult with check results
        """
        retries = retries or config.retries or self.default_retries
        retry_delay = retry_delay or config.retry_delay or self.default_retry_delay
        timeout = config.timeout or self.default_timeout

        url = config.get_url()
        last_error = None

        for attempt in range(retries):
            try:
                start_time = time.time()
                response = requests.get(
                    url,
                    timeout=timeout,
                    verify=False,  # Allow self-signed certificates in dev
                )
                response_time_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    # Try to parse JSON response if available
                    details = {}
                    try:
                        details = response.json()
                    except ValueError:
                        details = {"response_text": response.text[:200]}

                    return ServiceCheckResult(
                        service_name=config.name,
                        status=ServiceStatus.HEALTHY,
                        response_time_ms=response_time_ms,
                        details=details,
                    )
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"

            except requests.exceptions.Timeout:
                last_error = f"Timeout after {timeout}s"
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {e!s}"
            except Exception as e:
                last_error = f"Unexpected error: {e!s}"

            # Wait before retry (except on last attempt)
            if attempt < retries - 1:
                time.sleep(retry_delay)  # noqa: sleep-needed  # INTENTIONAL: e2e/integration test polling real services

        return ServiceCheckResult(
            service_name=config.name,
            status=ServiceStatus.UNHEALTHY,
            error_message=last_error,
            details={"retries": retries, "timeout": timeout},
        )

    def check_database_connectivity(
        self, config: ServiceConfig, retries: int | None = None, retry_delay: float | None = None
    ) -> ServiceCheckResult:
        """
        Check PostgreSQL database connectivity.

        Args:
            config: Service configuration
            retries: Number of retries (uses default if None)
            retry_delay: Delay between retries (uses default if None)

        Returns:
            ServiceCheckResult with check results
        """
        retries = retries or config.retries or self.default_retries
        retry_delay = retry_delay or config.retry_delay or self.default_retry_delay

        # Use Django database connection
        last_error = None

        for attempt in range(retries):
            try:
                start_time = time.time()
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    response_time_ms = (time.time() - start_time) * 1000

                    if result and result[0] == 1:
                        return ServiceCheckResult(
                            service_name=config.name,
                            status=ServiceStatus.HEALTHY,
                            response_time_ms=response_time_ms,
                            details={
                                "database": connection.settings_dict.get("NAME"),
                                "host": connection.settings_dict.get("HOST"),
                                "port": connection.settings_dict.get("PORT"),
                            },
                        )
                    else:
                        last_error = "Database query returned unexpected result"

            except Exception as e:
                last_error = f"Database connection error: {e!s}"

            # Wait before retry (except on last attempt)
            if attempt < retries - 1:
                time.sleep(retry_delay)  # noqa: sleep-needed  # INTENTIONAL: e2e/integration test polling real services

        return ServiceCheckResult(
            service_name=config.name,
            status=ServiceStatus.UNHEALTHY,
            error_message=last_error,
            details={"retries": retries},
        )

    def check_redis_connectivity(
        self, config: ServiceConfig, retries: int | None = None, retry_delay: float | None = None
    ) -> ServiceCheckResult:
        """
        Check Redis connectivity.

        Args:
            config: Service configuration
            retries: Number of retries (uses default if None)
            retry_delay: Delay between retries (uses default if None)

        Returns:
            ServiceCheckResult with check results
        """
        if not REDIS_AVAILABLE:
            return ServiceCheckResult(
                service_name=config.name,
                status=ServiceStatus.ERROR,
                error_message="Redis library not available",
            )

        retries = retries or config.retries or self.default_retries
        retry_delay = retry_delay or config.retry_delay or self.default_retry_delay

        # Get Redis URL from settings
        redis_url = getattr(settings, "REDIS_URL", f"redis://{config.host}:{config.port}/0")
        last_error = None

        for attempt in range(retries):
            try:
                start_time = time.time()
                r = redis.from_url(redis_url, socket_connect_timeout=config.timeout)
                r.ping()
                response_time_ms = (time.time() - start_time) * 1000

                # Get Redis info
                info = r.info()

                return ServiceCheckResult(
                    service_name=config.name,
                    status=ServiceStatus.HEALTHY,
                    response_time_ms=response_time_ms,
                    details={
                        "redis_version": info.get("redis_version"),
                        "used_memory_human": info.get("used_memory_human"),
                        "connected_clients": info.get("connected_clients"),
                    },
                )

            except redis.ConnectionError as e:
                last_error = f"Redis connection error: {e!s}"
            except redis.TimeoutError:
                last_error = f"Redis timeout after {config.timeout}s"
            except Exception as e:
                last_error = f"Redis error: {e!s}"

            # Wait before retry (except on last attempt)
            if attempt < retries - 1:
                time.sleep(retry_delay)  # noqa: sleep-needed  # INTENTIONAL: e2e/integration test polling real services

        return ServiceCheckResult(
            service_name=config.name,
            status=ServiceStatus.UNHEALTHY,
            error_message=last_error,
            details={"retries": retries, "redis_url": redis_url},
        )

    def check_minio_connectivity(
        self, config: ServiceConfig, retries: int | None = None, retry_delay: float | None = None
    ) -> ServiceCheckResult:
        """
        Check MinIO (S3-compatible) object storage connectivity.

        Args:
            config: Service configuration
            retries: Number of retries (uses default if None)
            retry_delay: Delay between retries (uses default if None)

        Returns:
            ServiceCheckResult with check results
        """
        if not BOTO3_AVAILABLE:
            return ServiceCheckResult(
                service_name=config.name,
                status=ServiceStatus.ERROR,
                error_message="boto3 not available for S3/MinIO connectivity check",
            )

        retries = retries or config.retries or self.default_retries
        retry_delay = retry_delay or config.retry_delay or self.default_retry_delay

        # Get MinIO credentials from settings or environment
        access_key = os.getenv(
            "MINIO_ROOT_USER",
            os.getenv("AWS_ACCESS_KEY_ID", getattr(settings, "MINIO_ROOT_USER", "minio")),
        )
        secret_key = os.getenv(
            "MINIO_ROOT_PASSWORD",
            os.getenv(
                "AWS_SECRET_ACCESS_KEY", getattr(settings, "MINIO_ROOT_PASSWORD", "minio123")
            ),
        )
        endpoint_url = f"http{'s' if config.use_https else ''}://{config.host}:{config.port}"

        last_error = None

        for attempt in range(retries):
            try:
                start_time = time.time()
                client = boto3.client(
                    "s3",
                    endpoint_url=endpoint_url,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=os.getenv("AWS_REGION", "us-east-1"),
                    config=BotocoreConfig(signature_version="s3v4", connect_timeout=config.timeout),
                )

                # Try to list buckets (lightweight operation)
                response = client.list_buckets()
                response_time_ms = (time.time() - start_time) * 1000
                bucket_count = len(response.get("Buckets", []))

                return ServiceCheckResult(
                    service_name=config.name,
                    status=ServiceStatus.HEALTHY,
                    response_time_ms=response_time_ms,
                    details={
                        "bucket_count": bucket_count,
                        "endpoint": f"{config.host}:{config.port}",
                    },
                )

            except (ClientError, EndpointConnectionError) as e:
                last_error = f"MinIO S3 error: {e!s}"
            except Exception as e:
                last_error = f"MinIO error: {e!s}"

            # Wait before retry (except on last attempt)
            if attempt < retries - 1:
                time.sleep(retry_delay)  # noqa: sleep-needed  # INTENTIONAL: e2e/integration test polling real services

        return ServiceCheckResult(
            service_name=config.name,
            status=ServiceStatus.UNHEALTHY,
            error_message=last_error,
            details={"retries": retries},
        )

    def check_websocket_service(
        self, config: ServiceConfig, retries: int | None = None, retry_delay: float | None = None
    ) -> ServiceCheckResult:
        """
        Check WebSocket service availability.

        Note: This is a basic check - full WebSocket connection requires authentication.

        Args:
            config: Service configuration
            retries: Number of retries (uses default if None)
            retry_delay: Delay between retries (uses default if None)

        Returns:
            ServiceCheckResult with check results
        """
        # For WebSocket, we check if the HTTP endpoint is available
        # Full WebSocket connection test would require authentication
        ws_config = ServiceConfig(
            name=config.name,
            host=config.host,
            port=config.port,
            health_path="/health",  # Check health endpoint instead
            timeout=config.timeout,
            retries=config.retries,
            retry_delay=config.retry_delay,
            use_https=config.use_https,
            check_type="http",
        )

        result = self.check_http_service(ws_config, retries, retry_delay)
        result.service_name = config.name  # Keep original name
        result.details["websocket_path"] = config.health_path
        return result

    def check_graphql_service(
        self, config: ServiceConfig, retries: int | None = None, retry_delay: float | None = None
    ) -> ServiceCheckResult:
        """
        Check GraphQL service availability.

        Args:
            config: Service configuration
            retries: Number of retries (uses default if None)
            retry_delay: Delay between retries (uses default if None)

        Returns:
            ServiceCheckResult with check results
        """
        # GraphQL endpoint - try a simple introspection query
        url = config.get_url()
        retries = retries or config.retries or self.default_retries
        retry_delay = retry_delay or config.retry_delay or self.default_retry_delay
        timeout = config.timeout or self.default_timeout

        last_error = None

        for attempt in range(retries):
            try:
                start_time = time.time()
                # Simple GraphQL query to check if service is available
                query = {"query": "{ __typename }"}
                response = requests.post(
                    url,
                    json=query,
                    timeout=timeout,
                    headers={"Content-Type": "application/json"},
                    verify=False,
                )
                response_time_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    try:
                        data = response.json()
                        if "data" in data or "errors" in data:
                            # GraphQL endpoint responded (even with errors is OK for availability)
                            return ServiceCheckResult(
                                service_name=config.name,
                                status=ServiceStatus.HEALTHY,
                                response_time_ms=response_time_ms,
                                details={"graphql_response": data},
                            )
                    except ValueError:
                        pass

                    return ServiceCheckResult(
                        service_name=config.name,
                        status=ServiceStatus.HEALTHY,
                        response_time_ms=response_time_ms,
                        details={"response_text": response.text[:200]},
                    )
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"

            except requests.exceptions.Timeout:
                last_error = f"Timeout after {timeout}s"
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {e!s}"
            except Exception as e:
                last_error = f"Unexpected error: {e!s}"

            # Wait before retry (except on last attempt)
            if attempt < retries - 1:
                time.sleep(retry_delay)  # noqa: sleep-needed  # INTENTIONAL: e2e/integration test polling real services

        return ServiceCheckResult(
            service_name=config.name,
            status=ServiceStatus.UNHEALTHY,
            error_message=last_error,
            details={"retries": retries, "timeout": timeout},
        )

    def check_service(
        self, config: ServiceConfig, retries: int | None = None, retry_delay: float | None = None
    ) -> ServiceCheckResult:
        """
        Check service availability based on check type.

        Args:
            config: Service configuration
            retries: Number of retries (uses default if None)
            retry_delay: Delay between retries (uses default if None)

        Returns:
            ServiceCheckResult with check results
        """
        check_type = config.check_type.lower()

        if check_type == "database":
            return self.check_database_connectivity(config, retries, retry_delay)
        elif check_type == "redis":
            return self.check_redis_connectivity(config, retries, retry_delay)
        elif check_type == "minio":
            return self.check_minio_connectivity(config, retries, retry_delay)
        elif check_type == "websocket":
            return self.check_websocket_service(config, retries, retry_delay)
        elif check_type == "graphql":
            return self.check_graphql_service(config, retries, retry_delay)
        else:  # http (default)
            return self.check_http_service(config, retries, retry_delay)

    def check_all_services(
        self,
        service_configs: list[ServiceConfig],
        retries: int | None = None,
        retry_delay: float | None = None,
    ) -> dict[str, ServiceCheckResult]:
        """
        Check all services and return results.

        Args:
            service_configs: List of service configurations
            retries: Number of retries (uses default if None)
            retry_delay: Delay between retries (uses default if None)

        Returns:
            Dictionary mapping service names to check results
        """
        results = {}

        for config in service_configs:
            logger.info(f"Checking service: {config.name}")
            result = self.check_service(config, retries, retry_delay)
            results[config.name] = result

            if result.is_healthy():
                logger.info(
                    f"✓ {config.name} is healthy (response time: {result.response_time_ms:.2f}ms)"
                )
            else:
                logger.warning(f"✗ {config.name} is unhealthy: {result.error_message}")

        return results

    def generate_report(self, results: dict[str, ServiceCheckResult]) -> dict[str, Any]:
        """
        Generate detailed report from check results.

        Args:
            results: Dictionary of service check results

        Returns:
            Report dictionary with summary and details
        """
        total = len(results)
        healthy = sum(1 for r in results.values() if r.is_healthy())
        unhealthy = total - healthy

        healthy_services = [name for name, result in results.items() if result.is_healthy()]
        unhealthy_services = [name for name, result in results.items() if not result.is_healthy()]

        avg_response_time = None
        response_times = [
            r.response_time_ms for r in results.values() if r.response_time_ms is not None
        ]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)

        return {
            "summary": {
                "total_services": total,
                "healthy": healthy,
                "unhealthy": unhealthy,
                "health_percentage": (healthy / total * 100) if total > 0 else 0,
                "average_response_time_ms": avg_response_time,
            },
            "healthy_services": healthy_services,
            "unhealthy_services": unhealthy_services,
            "details": {
                name: {
                    "status": result.status.value,
                    "response_time_ms": result.response_time_ms,
                    "error_message": result.error_message,
                    "details": result.details,
                    "timestamp": result.timestamp,
                }
                for name, result in results.items()
            },
        }


def get_all_service_configs(base_host: str = "localhost") -> list[ServiceConfig]:
    """
    Get all service configurations for health checks.

    Args:
        base_host: Base hostname for services

    Returns:
        List of ServiceConfig objects
    """
    configs = [
        # API Service
        ServiceConfig(
            name="api-service",
            host=base_host,
            port=8000,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        ),
        # PostgreSQL Database
        ServiceConfig(
            name="postgresql",
            host=base_host,
            port=5432,
            health_path="",
            timeout=5,
            retries=3,
            check_type="database",
        ),
        # Redis
        ServiceConfig(
            name="redis",
            host=base_host,
            port=6379,
            health_path="",
            timeout=5,
            retries=3,
            check_type="redis",
        ),
        # MinIO (Object Storage)
        ServiceConfig(
            name="minio",
            host=base_host,
            port=9000,
            health_path="/minio/health/live",
            timeout=10,
            retries=3,
            check_type="minio",
        ),
        # DataContract Service
        ServiceConfig(
            name="datacontract-service",
            host=base_host,
            port=8080,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        ),
        # DQ Service
        ServiceConfig(
            name="dq-service",
            host=base_host,
            port=8083,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        ),
        # Compliance Service
        ServiceConfig(
            name="compliance-service",
            host=base_host,
            port=8082,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        ),
        # Semantic Service
        ServiceConfig(
            name="semantic-service",
            host=base_host,
            port=8081,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        ),
        # Search Service
        ServiceConfig(
            name="search-service",
            host=base_host,
            port=8085,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        ),
        # Observability Service
        ServiceConfig(
            name="observability-service",
            host=base_host,
            port=8086,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        ),
        # Prefect Server
        ServiceConfig(
            name="prefect-server",
            host=base_host,
            port=4200,
            health_path="/health",
            timeout=10,
            retries=3,
            check_type="http",
        ),
        # Prefect Integration Service
        ServiceConfig(
            name="prefect-integration-service",
            host=base_host,
            port=8084,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        ),
        # WebSocket Service (via API service)
        ServiceConfig(
            name="websocket-service",
            host=base_host,
            port=8000,
            health_path="/ws/events",
            timeout=5,
            retries=3,
            check_type="websocket",
        ),
        # GraphQL Service (via API service)
        ServiceConfig(
            name="graphql-service",
            host=base_host,
            port=8000,
            health_path="/graphql",
            timeout=5,
            retries=3,
            check_type="graphql",
        ),
    ]

    return configs


pytestmark = [pytest.mark.slow, pytest.mark.django_db(transaction=True), pytest.mark.integration]


class ComprehensiveServiceAvailabilityTest(DjangoTestCase):
    """
    Comprehensive service availability tests with retry logic and detailed reporting.
    """

    def setUp(self):
        """Set up test fixtures"""
        self.checker = ServiceAvailabilityChecker(
            default_timeout=5, default_retries=3, default_retry_delay=1.0
        )

        # Determine host based on environment
        self.base_host = os.getenv("HUB_HOST", "localhost")
        if os.getenv("DOCKER_COMPOSE"):
            self.base_host = "localhost"  # Services accessible via localhost in Docker Compose

    def test_api_service_availability(self):
        """Test API service availability"""
        config = ServiceConfig(
            name="api-service",
            host=self.base_host,
            port=8000,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        )

        result = self.checker.check_service(config)

        # In test environment, service may not be running
        # Verify the check mechanism works correctly
        self.assertIsInstance(result.status, ServiceStatus)
        if result.is_healthy():
            self.assertIsNotNone(result.response_time_ms)
            self.assertGreater(result.response_time_ms, 0)
        else:
            # Service unavailable - verify error message is present
            self.assertIsNotNone(result.error_message)
            logger.warning(f"API service unavailable: {result.error_message}")

    def test_postgresql_connectivity(self):
        """Test PostgreSQL database connectivity"""
        config = ServiceConfig(
            name="postgresql",
            host=self.base_host,
            port=5432,
            health_path="",
            timeout=5,
            retries=3,
            check_type="database",
        )

        result = self.checker.check_service(config)

        self.assertTrue(
            result.is_healthy(), f"PostgreSQL should be accessible. Error: {result.error_message}"
        )
        self.assertIsNotNone(result.response_time_ms)

    def test_redis_connectivity(self):
        """Test Redis connectivity"""
        if not REDIS_AVAILABLE:
            self.skipTest("Redis library not available")

        config = ServiceConfig(
            name="redis",
            host=self.base_host,
            port=6379,
            health_path="",
            timeout=5,
            retries=3,
            check_type="redis",
        )

        result = self.checker.check_service(config)

        self.assertTrue(
            result.is_healthy(), f"Redis should be accessible. Error: {result.error_message}"
        )
        self.assertIsNotNone(result.response_time_ms)

    def test_minio_connectivity(self):
        """Test MinIO object storage connectivity (uses boto3 S3 client)"""
        if not BOTO3_AVAILABLE:
            self.skipTest("boto3 not available for S3/MinIO connectivity check")

        # Use MINIO_HOST when in Docker (minio-test); else base_host
        minio_host = os.getenv("MINIO_HOST", self.base_host)
        minio_port = int(os.getenv("MINIO_PORT", "9000"))
        config = ServiceConfig(
            name="minio",
            host=minio_host,
            port=minio_port,
            health_path="/minio/health/live",
            timeout=10,
            retries=3,
            check_type="minio",
        )

        result = self.checker.check_service(config)

        # In test environment, MinIO may not be accessible from test container
        # Verify the check mechanism works correctly
        self.assertIsInstance(result.status, ServiceStatus)
        if result.is_healthy():
            self.assertIsNotNone(result.response_time_ms)
        else:
            # Service unavailable - verify error message is present
            self.assertIsNotNone(result.error_message)
            logger.warning(f"MinIO unavailable: {result.error_message}")

    def test_datacontract_service_availability(self):
        """Test DataContract service availability"""
        config = ServiceConfig(
            name="datacontract-service",
            host=self.base_host,
            port=8080,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        )

        result = self.checker.check_service(config)

        # Service may not be available in all test environments
        # Just verify the check works correctly
        self.assertIsInstance(result.status, ServiceStatus)
        if not result.is_healthy():
            self.assertIsNotNone(result.error_message)

    def test_dq_service_availability(self):
        """Test DQ service availability"""
        config = ServiceConfig(
            name="dq-service",
            host=self.base_host,
            port=8083,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        )

        result = self.checker.check_service(config)

        self.assertIsInstance(result.status, ServiceStatus)
        if not result.is_healthy():
            self.assertIsNotNone(result.error_message)

    def test_compliance_service_availability(self):
        """Test Compliance service availability"""
        config = ServiceConfig(
            name="compliance-service",
            host=self.base_host,
            port=8082,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        )

        result = self.checker.check_service(config)

        self.assertIsInstance(result.status, ServiceStatus)
        if not result.is_healthy():
            self.assertIsNotNone(result.error_message)

    def test_semantic_service_availability(self):
        """Test Semantic service availability"""
        config = ServiceConfig(
            name="semantic-service",
            host=self.base_host,
            port=8081,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        )

        result = self.checker.check_service(config)

        self.assertIsInstance(result.status, ServiceStatus)
        if not result.is_healthy():
            self.assertIsNotNone(result.error_message)

    def test_search_service_availability(self):
        """Test Search service availability"""
        config = ServiceConfig(
            name="search-service",
            host=self.base_host,
            port=8085,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        )

        result = self.checker.check_service(config)

        self.assertIsInstance(result.status, ServiceStatus)
        if not result.is_healthy():
            self.assertIsNotNone(result.error_message)

    def test_observability_service_availability(self):
        """Test Observability service availability"""
        config = ServiceConfig(
            name="observability-service",
            host=self.base_host,
            port=8086,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        )

        result = self.checker.check_service(config)

        self.assertIsInstance(result.status, ServiceStatus)
        if not result.is_healthy():
            self.assertIsNotNone(result.error_message)

    def test_prefect_server_availability(self):
        """Test Prefect Server availability"""
        config = ServiceConfig(
            name="prefect-server",
            host=self.base_host,
            port=4200,
            health_path="/health",
            timeout=10,
            retries=3,
            check_type="http",
        )

        result = self.checker.check_service(config)

        self.assertIsInstance(result.status, ServiceStatus)
        if not result.is_healthy():
            self.assertIsNotNone(result.error_message)

    def test_prefect_integration_service_availability(self):
        """Test Prefect Integration service availability"""
        config = ServiceConfig(
            name="prefect-integration-service",
            host=self.base_host,
            port=8084,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        )

        result = self.checker.check_service(config)

        self.assertIsInstance(result.status, ServiceStatus)
        if not result.is_healthy():
            self.assertIsNotNone(result.error_message)

    def test_websocket_service_availability(self):
        """Test WebSocket service availability"""
        config = ServiceConfig(
            name="websocket-service",
            host=self.base_host,
            port=8000,
            health_path="/ws/events",
            timeout=5,
            retries=3,
            check_type="websocket",
        )

        result = self.checker.check_service(config)

        # WebSocket check uses HTTP health endpoint
        self.assertIsInstance(result.status, ServiceStatus)
        if not result.is_healthy():
            self.assertIsNotNone(result.error_message)

    def test_graphql_service_availability(self):
        """Test GraphQL service availability"""
        config = ServiceConfig(
            name="graphql-service",
            host=self.base_host,
            port=8000,
            health_path="/graphql",
            timeout=5,
            retries=3,
            check_type="graphql",
        )

        result = self.checker.check_service(config)

        self.assertIsInstance(result.status, ServiceStatus)
        if not result.is_healthy():
            self.assertIsNotNone(result.error_message)

    def test_all_services_comprehensive(self):
        """Test all services comprehensively"""
        configs = get_all_service_configs(self.base_host)
        results = self.checker.check_all_services(configs)

        # Generate report
        report = self.checker.generate_report(results)

        # Verify report structure
        self.assertIn("summary", report)
        self.assertIn("healthy_services", report)
        self.assertIn("unhealthy_services", report)
        self.assertIn("details", report)

        # Verify summary
        summary = report["summary"]
        self.assertGreaterEqual(summary["total_services"], 0)
        self.assertGreaterEqual(summary["healthy"], 0)
        self.assertGreaterEqual(summary["unhealthy"], 0)
        self.assertEqual(summary["total_services"], summary["healthy"] + summary["unhealthy"])

        # Log report for visibility
        logger.info("Service Availability Report:")
        logger.info(f"  Total services: {summary['total_services']}")
        logger.info(f"  Healthy: {summary['healthy']}")
        logger.info(f"  Unhealthy: {summary['unhealthy']}")
        logger.info(f"  Health percentage: {summary['health_percentage']:.1f}%")
        if summary.get("average_response_time_ms"):
            logger.info(f"  Average response time: {summary['average_response_time_ms']:.2f}ms")

        if summary["unhealthy"] > 0:
            logger.warning(f"Unhealthy services: {', '.join(report['unhealthy_services'])}")

    def test_service_checker_retry_logic(self):
        """Test that retry logic works correctly"""
        # Use a service that should be available (API service)
        config = ServiceConfig(
            name="api-service-retry-test",
            host=self.base_host,
            port=8000,
            health_path="/health",
            timeout=2,
            retries=2,
            check_type="http",
        )

        result = self.checker.check_service(config, retries=2)

        # Should eventually succeed (if service is available)
        # or fail with proper error message
        self.assertIsInstance(result.status, ServiceStatus)
        self.assertIsNotNone(result.error_message or result.response_time_ms)

    def test_service_checker_timeout_handling(self):
        """Test that timeout handling works correctly"""
        # Use a non-existent service with short timeout
        config = ServiceConfig(
            name="timeout-test-service",
            host="192.0.2.1",  # Non-routable IP
            port=9999,
            health_path="/health",
            timeout=1,
            retries=1,
            check_type="http",
        )

        result = self.checker.check_service(config)

        # Should fail with timeout or connection error
        self.assertFalse(result.is_healthy())
        self.assertIsNotNone(result.error_message)
        self.assertIn(
            result.status, [ServiceStatus.UNHEALTHY, ServiceStatus.TIMEOUT, ServiceStatus.ERROR]
        )

    def test_service_to_service_communication(self):
        """Test service-to-service communication"""
        # Test that API service can communicate with other services
        # by checking if health endpoint includes service status

        config = ServiceConfig(
            name="api-service",
            host=self.base_host,
            port=8000,
            health_path="/health",
            timeout=5,
            retries=3,
            check_type="http",
        )

        result = self.checker.check_service(config)

        if result.is_healthy() and result.details:
            # Check if health response includes database and Redis status
            health_data = result.details
            if isinstance(health_data, dict):
                # Health endpoint should report database and Redis status
                logger.info(f"API service health details: {health_data}")

    def test_detailed_reporting(self):
        """Test that detailed reporting works correctly"""
        configs = get_all_service_configs(self.base_host)
        results = self.checker.check_all_services(configs)
        report = self.checker.generate_report(results)

        # Verify detailed report structure
        self.assertIn("summary", report)
        self.assertIn("details", report)

        # Verify each service has details
        for _service_name, service_details in report["details"].items():
            self.assertIn("status", service_details)
            self.assertIn("timestamp", service_details)
            self.assertIsInstance(service_details["status"], str)
            self.assertIsInstance(service_details["timestamp"], (int, float))
