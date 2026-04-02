"""
Pytest configuration for SDK Python tests.

Uses existing API service in Docker Compose instead of LiveServerTestCase for better performance.
"""

import os

# CRITICAL: Set environment variable BEFORE Django imports
# This tells settings.py to use the production database for SDK tests
os.environ["USE_PRODUCTION_DB_FOR_SDK_TESTS"] = "1"

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from tests.e2e.conftest import TenantFactory


def pytest_configure(config):
    """
    Configure pytest for SDK tests.

    Sets environment variable to use production database so API service can see test data.
    Also patches pytest-django to skip test database creation when using production DB.
    """
    # Set environment variable before Django loads settings
    os.environ["USE_PRODUCTION_DB_FOR_SDK_TESTS"] = "1"

    # Patch pytest-django to skip test database creation for SDK tests
    # This is critical: pytest-django's --create-db flag forces DB creation,
    # but we need to use the existing production database
    try:
        import pytest_django
        from pytest_django import fixtures

        # Store original django_db_setup if not already stored
        if not hasattr(fixtures, "_original_django_db_setup"):
            fixtures._original_django_db_setup = fixtures.django_db_setup

        def _patched_django_db_setup(request, django_db_blocker):
            """
            Patched django_db_setup that skips database creation when using production DB.
            """
            use_production_db = os.getenv("USE_PRODUCTION_DB_FOR_SDK_TESTS", "").lower() == "1"

            if use_production_db:
                # Skip database creation - use existing production database
                # Just ensure Django is configured
                import django
                from django.conf import settings

                if not settings.configured:
                    django.setup()
                return

            # For non-SDK tests, use original behavior
            return fixtures._original_django_db_setup(request, django_db_blocker)

        # Replace the fixture
        fixtures.django_db_setup = _patched_django_db_setup

    except Exception as e:
        # If patching fails, log but don't fail - tests might still work
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Could not patch pytest-django database setup: {e}")


def configure_sdk_test_database():
    """
    Configure tests to use the same database as the API service.

    This ensures the API service can see test data.
    CRITICAL: This must be called before Django sets up the test database.
    """
    import os

    # This will be called in setUpClass before super().setUpClass()
    # which triggers database setup
    pass


def get_api_base_url() -> str:
    """
    Get API base URL for SDK tests.

    When running inside the api-service container, the API is at http://localhost:8000.
    When running from host, it uses the environment detection from e2e.conftest.
    """
    # Check if explicitly set
    api_url = os.getenv("API_SERVICE_URL") or os.getenv("TEST_API_URL")
    if api_url:
        return api_url.rstrip("/")

    # Check if we're inside the container (API service is at localhost:8000)
    # This is the case when running tests via docker compose exec
    if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER"):
        return "http://localhost:8000"

    # Otherwise, use the e2e conftest detection (for host-based testing)
    from tests.e2e.conftest import get_api_base_url as e2e_get_api_base_url

    return e2e_get_api_base_url()


@pytest.fixture
def api_base_url():
    """Fixture providing API base URL"""
    return get_api_base_url()


class SDKTestBase(TestCase):
    """
    Base test class for SDK tests using existing API service.

    This is faster than LiveServerTestCase because it uses the existing
    API service in Docker Compose instead of starting a new server.

    Uses TransactionTestCase to ensure data is immediately visible to the
    API service (no transaction rollback between test and API service).

    CRITICAL: Uses the same database as the API service so the API can see test data.
    """

    # Use the same database as the API service (no test database)
    # This ensures the API service can see test data
    databases = {"default"}  # Use default database, not a test database

    # CRITICAL: Skip database reset/flush for SDK tests
    # We're using the production database, so we should not flush it
    # Instead, we manually clean up test data in tearDown
    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def setUpClass(cls):
        """Set up test class"""
        super().setUpClass()

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for SDK tests"""
        # Don't flush the production database - we clean up manually
        pass

    def tearDown(self):
        """Clean up test data after each test"""
        # Clean up test data to avoid interfering with API service
        # Delete in reverse order of creation (user, then tenant)
        try:
            if hasattr(self, "user") and self.user:
                try:
                    self.user.delete()
                except Exception:
                    pass

            if hasattr(self, "tenant") and self.tenant:
                try:
                    self.tenant.delete()
                except Exception:
                    pass
        except Exception:
            # Ignore cleanup errors to prevent hanging
            pass

        # Call super tearDown with timeout protection
        try:
            super().tearDown()
        except Exception as e:
            # Log but don't fail on teardown errors
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Error during tearDown: {e}")

    def setUp(self):
        """Set up test fixtures"""
        import json
        import os
        import time

        # #region agent log
        log_path = "/app/.cursor/debug.log"
        log_data = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "F",
            "location": "conftest.py:setUp:entry",
            "message": "setUp called",
            "data": {},
            "timestamp": int(time.time() * 1000),
        }
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion

        super().setUp()

        # #region agent log
        log_data = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "F",
            "location": "conftest.py:setUp:after_super",
            "message": "super().setUp() completed",
            "data": {},
            "timestamp": int(time.time() * 1000),
        }
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion

        # Create test tenant
        self.tenant = TenantFactory.create_tenant()

        # #region agent log
        log_data = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "F",
            "location": "conftest.py:setUp:after_tenant",
            "message": "Tenant created",
            "data": {"tenant_id": str(self.tenant.id) if hasattr(self.tenant, "id") else None},
            "timestamp": int(time.time() * 1000),
        }
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion

        # Create test user with ACTIVE status
        self.user = User.objects.create_user(
            email=f"sdk_test_{id(self)}@example.com",  # Unique email per test instance
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Ensure user is saved and committed to database
        # This is critical for TransactionTestCase to make data visible to API service
        self.user.save()
        from django.db import transaction

        transaction.commit()

        # #region agent log
        log_data = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "F",
            "location": "conftest.py:setUp:after_user",
            "message": "User created",
            "data": {"user_id": str(self.user.id), "user_email": self.user.email},
            "timestamp": int(time.time() * 1000),
        }
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion

        # Create API client for authentication
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # #region agent log
        log_data = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "F",
            "location": "conftest.py:setUp:after_auth",
            "message": "API client authenticated",
            "data": {},
            "timestamp": int(time.time() * 1000),
        }
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion

        # Get API base URL (uses existing service)
        self.api_base_url = get_api_base_url()
        self.base_url = f"{self.api_base_url}/api/v1"

        # #region agent log
        log_data = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "F",
            "location": "conftest.py:setUp:exit",
            "message": "setUp completed",
            "data": {"api_base_url": self.api_base_url, "base_url": self.base_url},
            "timestamp": int(time.time() * 1000),
        }
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion

    async def get_sdk_config(self):
        """
        Get SDK config with authenticated token.

        Uses httpx.AsyncClient to make async HTTP request to login endpoint.
        This is async-compatible and doesn't block the event loop.
        """
        import json
        import os
        import time

        import httpx

        # #region agent log
        log_path = "/app/.cursor/debug.log"
        log_data = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A",
            "location": "conftest.py:get_sdk_config:entry",
            "message": "get_sdk_config called (async)",
            "data": {
                "api_base_url": self.api_base_url,
                "base_url": self.base_url,
                "user_email": self.user.email,
            },
            "timestamp": int(time.time() * 1000),
        }
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion

        # Use httpx.AsyncClient to make async HTTP request to real API service
        login_url = f"{self.api_base_url}/api/v1/auth/login/"

        # #region agent log
        log_data = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "B",
            "location": "conftest.py:get_sdk_config:before_httpx_async",
            "message": "About to make httpx.AsyncClient.post request",
            "data": {"login_url": login_url},
            "timestamp": int(time.time() * 1000),
        }
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion

        start_time = time.time()
        try:
            # Increase timeout and add connection verification
            # Use a longer timeout for initial connection
            timeout_config = httpx.Timeout(30.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                # Verify API is accessible first
                try:
                    health_check = await client.get(f"{self.api_base_url}/health/", timeout=5.0)
                except Exception:
                    # Health check failed, but continue with login attempt
                    pass

                response = await client.post(
                    login_url,
                    json={"email": self.user.email, "password": "testpass123"},
                    timeout=30.0,
                )
            elapsed = time.time() - start_time

            # #region agent log
            log_data = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "B",
                "location": "conftest.py:get_sdk_config:after_httpx_async",
                "message": "httpx.AsyncClient.post completed",
                "data": {
                    "status_code": response.status_code,
                    "elapsed_seconds": elapsed,
                },
                "timestamp": int(time.time() * 1000),
            }
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
        except Exception as e:
            elapsed = time.time() - start_time

            # #region agent log
            log_data = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "B",
                "location": "conftest.py:get_sdk_config:httpx_async_exception",
                "message": "httpx.AsyncClient.post raised exception",
                "data": {
                    "exception_type": type(e).__name__,
                    "exception_message": str(e),
                    "elapsed_seconds": elapsed,
                },
                "timestamp": int(time.time() * 1000),
            }
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            raise

        if response.status_code != 200:
            # #region agent log
            log_data = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "C",
                "location": "conftest.py:get_sdk_config:login_failed",
                "message": "Login returned non-200 status",
                "data": {
                    "status_code": response.status_code,
                    "response_text": response.text[:200] if response.text else None,
                },
                "timestamp": int(time.time() * 1000),
            }
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps(log_data) + "\n")
            except Exception:
                pass
            # #endregion
            raise Exception(f"Login failed: {response.status_code} - {response.text}")

        data = response.json()
        access_token = data.get("access_token") or data.get("token")

        # #region agent log
        log_data = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "D",
            "location": "conftest.py:get_sdk_config:token_extracted",
            "message": "Token extracted from response",
            "data": {
                "has_access_token": "access_token" in data,
                "has_token": "token" in data,
                "token_length": len(access_token) if access_token else 0,
            },
            "timestamp": int(time.time() * 1000),
        }
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion

        if not access_token:
            raise Exception(f"No access token in login response: {data}")

        from datahub_interoperability import DataHubClientConfig

        config = DataHubClientConfig(base_url=self.base_url, api_token=access_token)

        # #region agent log
        log_data = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A",
            "location": "conftest.py:get_sdk_config:exit",
            "message": "get_sdk_config returning config",
            "data": {"config_base_url": config.base_url, "has_token": bool(config.api_token)},
            "timestamp": int(time.time() * 1000),
        }
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(log_data) + "\n")
        except Exception:
            pass
        # #endregion

        return config
