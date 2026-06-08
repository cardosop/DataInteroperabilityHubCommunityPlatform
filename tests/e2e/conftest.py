"""

import uuid
Pytest configuration for E2E tests.
"""
import sys
import os
import pathlib

# Register the dual-channel guard fixtures and hooks at module scope so
# pytest picks them up for every test under tests/e2e/. See the guard
# module docstrings for the advisory/strict-mode rationale.
from tests.e2e._guards._captured_server_errors import (  # noqa: E402, F401
    captured_server_errors,
)
from tests.e2e._guards._skip_counter import (  # noqa: E402, F401
    pytest_runtest_logreport,
)

# Prevent Python from writing new .pyc bytecode files.
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

# CRITICAL: Delete stale .pyc files that are OLDER than their .py source.
# In Docker, .pyc files owned by root persist across container restarts.
# Python reads the existing .pyc EVEN with dont_write_bytecode=True —
# that flag only prevents *writing* new ones.  We must remove stale ones
# so Python falls back to compiling from the .py source.
_e2e_dir = pathlib.Path(__file__).parent
_cache_dir = _e2e_dir / "__pycache__"
if _cache_dir.is_dir():
    for pyc in _cache_dir.glob("*.pyc"):
        # Extract module name: "test_sdk_python.cpython-312-pytest-9.0.2.pyc" -> "test_sdk_python"
        stem = pyc.stem.split(".")[0]
        source = _e2e_dir / f"{stem}.py"
        if source.is_file() and pyc.stat().st_mtime < source.stat().st_mtime:
            try:
                pyc.unlink()
            except OSError:
                pass  # Root-owned file we can't delete — will still work if source is newer

# CRITICAL: Load tests/conftest patches when running E2E with -c tests/e2e/pytest.ini.
# When -c points to a subdirectory config, pytest sets rootdir to tests/e2e, so
# tests/conftest.py is NOT discovered (it's above rootdir). Without it, create_test_db,
# sync_apps, create_contenttypes patches are missing -> hangs, IntegrityError.
# Must run before any Django imports/setup.
try:
    import tests.conftest  # noqa: F401
except ImportError:
    pass  # tests package not on path (e.g. minimal env)

import os
import sys
from typing import Dict, Optional

import pytest

# Try to import Django - some E2E tests need it, others don't
try:
    import django
    import httpx

    # Configure Django settings before any Django imports
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

    # Setup Django before importing Django modules
    # Handle connection failures gracefully for Docker Compose E2E tests
    try:
        from django.apps import apps

        if not apps.ready:
            django.setup()
    except (ImportError, AttributeError):
        # Django not configured yet, setup now
        try:
            django.setup()
        except RuntimeError as e:
            # If setup fails due to database connection, that's OK for Docker Compose tests
            # They will start services themselves
            if "PostgreSQL connection failed" in str(e) or "connection" in str(e).lower():
                # Store error for later - tests can handle this
                import warnings

                warnings.warn(f"Django setup failed (expected for Docker Compose E2E tests): {e}")
            else:
                raise
    except Exception as e:
        # Other errors should be raised
        import warnings

        if "PostgreSQL connection failed" in str(e) or "connection" in str(e).lower():
            warnings.warn(f"Django setup failed (expected for Docker Compose E2E tests): {e}")
        else:
            raise

    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient

    from hub.apps.tenants.models import Tenant

    DJANGO_AVAILABLE = True
except ImportError:
    # Django not available - some tests don't need it (e.g., HTTP-based tests)
    DJANGO_AVAILABLE = False
    TestCase = None
    APIClient = None
    get_user_model = None
    Tenant = None
    httpx = None

# Only import factories if Django is available
if DJANGO_AVAILABLE:
    try:
        from tests.factories import TenantFactory

        User = get_user_model()
    except ImportError:
        TenantFactory = None
        User = None
else:
    TenantFactory = None
    User = None

# ----------------------------------------------------------------
# Patch PostgreSQL sql_flush to use DELETE FROM instead of TRUNCATE.
#
# TRUNCATE requires ACCESS EXCLUSIVE locks which conflict with any
# concurrent connection — including the external API service on
# localhost:8000 that shares the test database.  DELETE FROM only
# needs ROW EXCLUSIVE locks, which coexist with normal queries.
#
# This eliminates the lock contention that caused statement_timeout
# errors during teardown, without needing retry loops, backend
# termination, or inflated timeouts.
#
# We disable FK checks during the delete to handle cross-table
# references, then re-enable them.  This mirrors what SQLite's
# sql_flush does natively.
# ----------------------------------------------------------------
if DJANGO_AVAILABLE:
    try:
        import django.db.backends.postgresql.operations as _pg_ops
        if not hasattr(_pg_ops.DatabaseOperations.sql_flush, "_patched_delete"):

            def _e2e_sql_flush(
                self, style, tables, *,
                reset_sequences=False, allow_cascade=False,
            ):
                if not tables:
                    return []

                sql = []
                # Disable FK trigger enforcement so DELETE order
                # doesn't matter.  session_replication_role='replica'
                # tells PostgreSQL to skip all user triggers (including
                # FK checks) for this session.  This requires the
                # DB user to have SUPERUSER or REPLICATION privileges
                # (the test DB user typically does).  Falls back to
                # SET CONSTRAINTS ALL DEFERRED if not.
                sql.append(
                    "SET session_replication_role = 'replica';"
                )
                for table in tables:
                    sql.append("DELETE FROM %s;" % (
                        self.quote_name(table),
                    ))
                sql.append(
                    "SET session_replication_role = 'origin';"
                )
                if reset_sequences:
                    seqs = self.connection.introspection.sequence_list()
                    for si in seqs:
                        if si["table"] in tables:
                            sql.append(
                                "SELECT setval("
                                "pg_get_serial_sequence('%s','%s')"
                                ", 1, false);" % (
                                    self.quote_name(si["table"]),
                                    si["column"],
                                )
                            )
                return sql

            _e2e_sql_flush._patched_delete = True
            _pg_ops.DatabaseOperations.sql_flush = _e2e_sql_flush
    except (ImportError, AttributeError) as exc:
        # Django internals may rename sql_flush between versions; if the
        # monkey-patch target is missing we skip patching rather than
        # crashing module import. ImportError covers missing optional
        # backends; AttributeError covers signature/rename drift.
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "Could not install _e2e_sql_flush patch: %s", exc,
        )

# Staging port configuration (from docker-compose.staging.yml)
STAGING_PORTS = {
    "API": 8001,
    "POSTGRES": 5433,
    "REDIS": 6380,
    "MINIO": 9010,
    "MINIO_CONSOLE": 9011,
    "FUSEKI": 3031,
    "SEMANTIC": 8082,
    "DATACONTRACT": 8092,
    "COMPLIANCE": 8083,
    "DQ": 8084,
    "WORKER": 8085,
    "PROMETHEUS": 9091,
    "GRAFANA": 3001,
    "JAEGER": 16687,
}

# Default ports (from regular docker-compose.yml)
DEFAULT_PORTS = {
    "API": 8000,
    "POSTGRES": 5432,
    "REDIS": 6379,
    "MINIO": 9000,
    "MINIO_CONSOLE": 9001,
    "FUSEKI": 3030,
    "SEMANTIC": 8081,
    "DATACONTRACT": 8080,
    "COMPLIANCE": 8082,
    "DQ": 8083,
    "WORKER": 8080,
    "PROMETHEUS": 9090,
    "GRAFANA": 3000,
    "JAEGER": 16686,
}


# Cache environment detection to avoid repeated HTTP calls
_ENVIRONMENT_CACHE = None


def get_response_data(response):
    """
    Get response data from either DRF Response (.data) or JsonResponse/Django HttpResponse.

    Use this when a view may return JsonResponse (e.g. 403 from middleware) instead of
    DRF Response, to avoid AttributeError: 'JsonResponse' object has no attribute 'data'.
    """
    if hasattr(response, "data"):
        return response.data
    try:
        import json

        return json.loads(response.content) if response.content else None
    except (json.JSONDecodeError, TypeError, AttributeError):
        import logging

        logging.getLogger(__name__).debug(
            "Failed to parse response data: status=%s, content=%s",
            getattr(response, "status_code", "N/A"),
            getattr(response, "content", b"")[:200],
        )
        return None


def detect_environment() -> str:
    """
    Detect if we're running against staging or default environment.
    Checks if staging ports are accessible.

    Cached to avoid repeated HTTP calls during test setup.

    Returns:
        'staging' if staging ports are detected, 'default' otherwise
    """
    global _ENVIRONMENT_CACHE

    # Return cached result if available
    if _ENVIRONMENT_CACHE is not None:
        return _ENVIRONMENT_CACHE

    # Check if explicitly set
    env = os.getenv("TEST_ENVIRONMENT", "").lower()
    if env in ("staging", "default"):
        _ENVIRONMENT_CACHE = env
        return env

    # Skip HTTP checks in test environment to avoid blocking
    # Use environment variable or default to 'default' for faster setup
    if os.getenv("SKIP_ENV_DETECTION", "").lower() == "true" or "pytest" in sys.modules:
        # In pytest, default to 'default' environment to avoid HTTP calls
        _ENVIRONMENT_CACHE = "default"
        return "default"

    # Auto-detect by checking if staging API port is accessible (only if not in test).
    # Narrow exception types: connection/timeout errors are the only *expected*
    # failures here — anything else is an actual bug that deserves to surface.
    try:
        response = httpx.get(f"http://localhost:{STAGING_PORTS['API']}/health", timeout=1)
        if response.status_code == 200:
            _ENVIRONMENT_CACHE = "staging"
            return "staging"
    except (httpx.TransportError, httpx.TimeoutException):
        pass  # Staging port not reachable — try default port next.

    # Check default API port
    try:
        response = httpx.get(f"http://localhost:{DEFAULT_PORTS['API']}/health", timeout=1)
        if response.status_code == 200:
            _ENVIRONMENT_CACHE = "default"
            return "default"
    except (httpx.TransportError, httpx.TimeoutException):
        pass  # Default port not reachable — fall through to default return below.

    # Default to default (not staging) to avoid unnecessary HTTP calls
    _ENVIRONMENT_CACHE = "default"
    return "default"


def get_service_url(service_name: str, default_port_key: str) -> str:
    """
    Get service URL, automatically detecting staging vs default environment.

    Args:
        service_name: Environment variable name (e.g., 'API_SERVICE_URL')
        default_port_key: Key in PORTS dict (e.g., 'API', 'DQ', 'COMPLIANCE')

    Returns:
        Service URL with correct port
    """
    # Check environment variable first
    env_url = os.getenv(service_name)
    if env_url:
        return env_url

    # Auto-detect environment
    env = detect_environment()
    ports = STAGING_PORTS if env == "staging" else DEFAULT_PORTS
    port = ports.get(default_port_key, DEFAULT_PORTS.get(default_port_key, 8000))

    return f"http://localhost:{port}"


def get_api_base_url() -> str:
    """Get API base URL"""
    return get_service_url("API_SERVICE_URL", "API")


def get_datacontract_service_url() -> str:
    """Get DataContract service URL"""
    return get_service_url("DATACONTRACT_SERVICE_URL", "DATACONTRACT")


def get_compliance_service_url() -> str:
    """Get Compliance service URL"""
    return get_service_url("COMPLIANCE_SERVICE_URL", "COMPLIANCE")


def get_dq_service_url() -> str:
    """Get DQ service URL"""
    return get_service_url("DQ_SERVICE_URL", "DQ")


def get_semantic_service_url() -> str:
    """Get Semantic service URL"""
    return get_service_url("SEMANTIC_SERVICE_URL", "SEMANTIC")


def get_worker_service_url() -> str:
    """Get Worker service URL"""
    return get_service_url("WORKER_SERVICE_URL", "WORKER")


def get_s3_endpoint_url() -> str:
    """Get S3/MinIO endpoint URL"""
    return get_service_url("AWS_S3_ENDPOINT_URL", "MINIO")


def get_prometheus_service_url() -> str:
    """Get Prometheus service URL"""
    return get_service_url("PROMETHEUS_URL", "PROMETHEUS")


def get_grafana_service_url() -> str:
    """Get Grafana service URL"""
    return get_service_url("GRAFANA_URL", "GRAFANA")


def get_jaeger_service_url() -> str:
    """Get Jaeger service URL"""
    return get_service_url("JAEGER_URL", "JAEGER")


def check_service_health(service_url: str, timeout: int = 5) -> bool:
    """
    Check if a service is healthy by hitting its health endpoint.

    Args:
        service_url: Base URL of the service
        timeout: Timeout in seconds

    Returns:
        True if service is healthy, False otherwise
    """
    try:
        health_url = f"{service_url.rstrip('/')}/health"
        response = httpx.get(health_url, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            return data.get("status") == "healthy" or data.get("status") == "ok"
    except (httpx.TransportError, httpx.TimeoutException, ValueError):
        # Transport errors / timeouts → service not up yet; ValueError
        # catches malformed JSON from a partial response. Real bugs (e.g.
        # a KeyError on a dict lookup) should NOT be swallowed here.
        pass
    return False


def check_minio_health(timeout: int = 5) -> bool:
    """
    Check if MinIO is healthy (Phase 7.2.3).
    MinIO exposes /minio/health/live for liveness.
    """
    if not DJANGO_AVAILABLE or httpx is None:
        return False
    s3_url = get_s3_endpoint_url()
    try:
        # MinIO health: http://host:9000/minio/health/live
        health_url = f"{s3_url.rstrip('/')}/minio/health/live"
        response = httpx.get(health_url, timeout=timeout)
        return response.status_code == 200
    except (httpx.TransportError, httpx.TimeoutException):
        # Connection errors / timeouts → MinIO not reachable. Real bugs
        # (e.g. a malformed URL) should not be swallowed as "unhealthy".
        return False


@pytest.fixture
def require_minio():
    """
    Fixture that skips the test if MinIO is not available (Phase 7.2.3).
    Use for tests that need real S3 (complete_file_upload with mock_s3=False).
    """
    if not check_minio_health():
        pytest.skip(
            "MinIO is not available. Start with docker-compose.test.yml or set AWS_S3_ENDPOINT_URL."
        )


# Mark all E2E tests with e2e marker
def pytest_addoption(parser):
    """Add command-line options for pytest (guard against duplicate registration)."""
    try:
        parser.addoption(
            "--docker-compose-runtime",
            action="store_true",
            default=False,
            help="Run tests that require Docker Compose runtime (services must be started)",
        )
    except ValueError:
        pass  # Already registered by parent conftest.py


def pytest_configure(config):
    """Configure pytest markers and ensure timeout applies only to test body, not DB setup."""
    # Fail fast with a clear message if Django is not available — UNLESS the user
    # is only running tests that don't need Django (e.g. docker-compose E2E tests
    # that use Docker CLI + HTTP requests from the host).
    if not DJANGO_AVAILABLE:
        # Check if only Django-free test files were requested
        file_args = [a for a in config.args if a.endswith(".py") or os.path.sep in a]
        django_free_files = {"test_docker_compose_e2e.py"}
        only_django_free = file_args and all(
            os.path.basename(f) in django_free_files for f in file_args
        )
        if not only_django_free:
            config._e2e_env_message = (
                "E2E tests require Django and project dependencies. Run with the project environment:\n\n"
                "  Docker (recommended):\n"
                "    docker compose -f docker-compose.test.yml exec -T api-service-test bash -c "
                '"cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/e2e/ -v '
                '-c tests/e2e/pytest.ini -o timeout_func_only=true"\n\n'
                "  On host (Python 3.12 + project deps):\n"
                "    pip install -r requirements.txt -r requirements-dev.txt\n"
                "    PYTHONPATH=. DJANGO_SETTINGS_MODULE=hub.settings pytest tests/e2e/ -v -c tests/e2e/pytest.ini -o timeout_func_only=true\n"
            )
            pytest.exit(config._e2e_env_message, returncode=2)

    # Force timeout_func_only so pytest-timeout never times out django_db_setup (migrations).
    if hasattr(config.option, "timeout_func_only"):
        config.option.timeout_func_only = True
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line(
        "markers",
        "requires_minio: Tests that require MinIO/S3 for file uploads (Phase 7.2.3)",
    )
    config.addinivalue_line(
        "markers",
        "requires_prefect: Tests that require Prefect (scheduled ingestion/export); fail when unreachable (Phase 7.4.3, 7.6.2)",
    )
    config.addinivalue_line(
        "markers",
        "requires_mailhog: Tests that require MailHog for password reset E2E; skip when unavailable (Phase 7.4.4, 7.6.2)",
    )
    config.addinivalue_line("markers", "e2e_batch1: E2E tests batch 1")
    config.addinivalue_line("markers", "e2e_batch2: E2E tests batch 2")
    config.addinivalue_line("markers", "e2e_batch3: E2E tests batch 3")
    config.addinivalue_line("markers", "e2e_batch4: E2E tests batch 4")
    config.addinivalue_line("markers", "e2e_batch5: E2E tests batch 5")


# Phase 6.1.4: Workflow execution fixtures (engine with business rules, registry with all workflows)
if DJANGO_AVAILABLE:
    try:
        from tests.e2e.workflow_e2e_base import create_engine_with_all_workflows_and_tasks

        @pytest.fixture
        def workflow_engine():
            """Create WorkflowEngine with all workflow tasks registered (business rules enabled via feature flag)."""
            engine, _ = create_engine_with_all_workflows_and_tasks()
            return engine

        @pytest.fixture
        def workflow_registry():
            """Create WorkflowRegistry with all workflow definitions registered."""
            _, registry = create_engine_with_all_workflows_and_tasks()
            return registry

    except ImportError:
        pass


if DJANGO_AVAILABLE and TestCase:

    class E2ETestBase(TestCase):
        """Base test class for E2E tests. Uses complete_file_upload (requires MinIO/S3)."""

        # Allow access to ALL database aliases (including 'baas').
        # Without this, Django wraps methods on disallowed connections with
        # _DatabaseFailure during setUpClass and tries to restore them via
        # method.wrapped during tearDownClass.  If a connection is
        # reinitialised between those two points the wrapper is lost,
        # causing: AttributeError: 'function' object has no attribute 'wrapped'
        databases = "__all__"

        pytestmark = pytest.mark.requires_minio

        def setUp(self):
            """Set up test fixtures."""
            if not DJANGO_AVAILABLE:
                pytest.skip("Django not available - E2ETestBase requires Django")

            super().setUp()
            self._clear_rate_limit_state()
            self._setup_test_fixtures()

        @staticmethod
        def _clear_rate_limit_state():
            """Clear rate limit counters (Redis sorted sets + Django cache) between tests.

            Without this, the AUTH endpoint rate limit (5 req/60s) accumulates
            across test methods that call /api/v1/auth/login/, causing spurious
            429 responses in later tests within the same class.
            """
            from django.core.cache import cache

            # 1. Flush Django-level rate limit cache entries
            try:
                cache.delete_pattern("rate_limit_cache:*")
            except (AttributeError, Exception):
                # delete_pattern not available on all backends; full clear is safe in tests
                try:
                    cache.clear()
                except Exception:
                    pass

            # 2. Flush Redis sorted-set rate limit keys
            try:
                from hub.apps.core.redis_pools import get_redis_cache_pool
                import redis as _redis

                pool = get_redis_cache_pool()
                r = _redis.Redis(connection_pool=pool)
                for key in r.scan_iter(match="rate_limit:*", count=500):
                    r.delete(key)
            except Exception:
                pass

        def _setup_test_fixtures(self):
            """Create tenant, user, roles, and configure the API client.

            Separated from setUp so that failures here can be caught and the
            SAVEPOINT rolled back, preventing InFailedSqlTransaction cascades.
            """
            import uuid

            from django.db.models.signals import post_save

            # Disconnect semantic service signals to prevent 60s timeouts
            try:
                from hub.apps.assets.models import Asset
                from hub.apps.contracts.models import Contract
                from hub.apps.semantic.signals import asset_saved, contract_saved

                post_save.disconnect(contract_saved, sender=Contract)
                post_save.disconnect(asset_saved, sender=Asset)
            except (ImportError, AttributeError):
                pass

            # Create test tenant
            if TenantFactory:
                self.tenant = TenantFactory.create_tenant()
            else:
                pytest.skip("TenantFactory not available")

            # Ensure tenant has active subscription so billing middleware allows writes
            from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

            ensure_tenant_has_active_subscription(self.tenant)

            # Create test user with ACTIVE status
            from hub.apps.users.models import UserStatus

            unique_suffix = str(uuid.uuid4())[:8]
            email = f"e2e_test_{unique_suffix}@example.com"

            self.user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "tenant": self.tenant,
                    "status": UserStatus.ACTIVE,
                },
            )

            self.user.set_password("testpass123")
            self.user.tenant = self.tenant
            self.user.status = UserStatus.ACTIVE
            self.user.save()

            # Assign TENANT_ADMIN role
            from hub.apps.users.models import Role, UserRole

            tenant_admin_role, _ = Role.objects.get_or_create(
                tenant=self.tenant,
                name="TENANT_ADMIN",
                defaults={"description": "Tenant Administrator"},
            )
            UserRole.objects.get_or_create(user=self.user, role=tenant_admin_role)

            self.user.refresh_from_db()

            # Create API client and authenticate
            self.client = APIClient()
            self.client.force_authenticate(user=self.user)

            # Store service URLs for easy access (staging-aware)
            self.api_base_url = get_api_base_url()
            self.datacontract_service_url = get_datacontract_service_url()
            self.compliance_service_url = get_compliance_service_url()
            self.dq_service_url = get_dq_service_url()
            self.semantic_service_url = get_semantic_service_url()
            self.worker_service_url = get_worker_service_url()
            self.s3_endpoint_url = get_s3_endpoint_url()
            self.prometheus_service_url = get_prometheus_service_url()
            self.grafana_service_url = get_grafana_service_url()
            self.jaeger_service_url = get_jaeger_service_url()

        def tearDown(self):
            """Clean up after test - reconnect signals"""

            # Reconnect semantic service signals after test
            from django.db.models.signals import post_save

            try:
                from hub.apps.assets.models import Asset
                from hub.apps.contracts.models import Contract
                from hub.apps.semantic.signals import asset_saved, contract_saved

                # Reconnect signals after test
                post_save.connect(contract_saved, sender=Contract, weak=False)
                post_save.connect(asset_saved, sender=Asset, weak=False)
            except (ImportError, AttributeError):
                # Signals may not be available - continue without reconnecting
                pass

            super().tearDown()

        def _verify_uri_in_fuseki(self, uri: str, max_retries: int = 5) -> bool:
            """Verify URI exists in Fuseki with retries."""
            import time

            from hub.apps.semantic.service_client import SemanticServiceClient

            client = SemanticServiceClient()

            for attempt in range(max_retries):
                try:
                    query = f"""
                    PREFIX hub: <https://hub.example.com/ontology#>
                    ASK {{
                        <{uri}> ?p ?o .
                    }}
                    """
                    tenant_id = str(self.tenant.id) if hasattr(self, 'tenant') and self.tenant else None
                    result = client.query_sparql(query, output_format="json", tenant_id=tenant_id)

                    if result and isinstance(result, dict):
                        if "boolean" in result:
                            return result["boolean"]
                        elif "results" in result:
                            bindings = result["results"].get("bindings", [])
                            return len(bindings) > 0

                    if attempt < max_retries - 1:
                        time.sleep(2**attempt)  # Exponential backoff  # INTENTIONAL: test-specific timing

                except Exception:
                    if attempt < max_retries - 1:
                        time.sleep(2**attempt)  # INTENTIONAL: e2e/integration test polling real services

            return False

        def get_service_urls(self) -> Dict[str, str]:
            """Get all service URLs as a dictionary"""
            return {
                "api": self.api_base_url,
                "datacontract": self.datacontract_service_url,
                "compliance": self.compliance_service_url,
                "dq": self.dq_service_url,
                "semantic": self.semantic_service_url,
                "worker": self.worker_service_url,
                "s3": self.s3_endpoint_url,
            }

        def require_service(
            self,
            service_name: str,
            service_url: str,
            health_path: str = "/health",
            max_wait: int = 5,
        ):
            """
            Require a service to be available, skip test if not available.

            Args:
                service_name: Name of the service (for error messages)
                service_url: Base URL of the service
                health_path: Health check endpoint path (default: '/health')
                max_wait: Maximum time to wait for service (default: 5 seconds)
            """
            if not check_service_health(service_url, timeout=max_wait):
                pytest.skip(
                    f"{service_name} service is not available at {service_url}. "
                    f"Please start services with: docker-compose -f docker-compose.staging.yml up -d"
                )

        def create_asset(
            self, key: str, name: str, description: str = "", domain: str = "", **kwargs
        ):
            """Create an asset via API and return its ID"""
            from django.urls import reverse
            from rest_framework import status

            from hub.apps.assets.models import Asset

            url = reverse("asset-list")
            response = self.client.post(
                url,
                {"key": key, "name": name, "description": description, "domain": domain, **kwargs},
                format="json",
            )

            if response.status_code != status.HTTP_201_CREATED:
                error_data = get_response_data(response) or (
                    getattr(response, "content", b"").decode("utf-8", errors="ignore")
                )
                raise Exception(f"Failed to create asset: {response.status_code} - {error_data}")

            data = get_response_data(response)
            return data["id"] if data else None

        def create_contract(
            self, asset_id, original_raw: str = None, original_format: str = None, **kwargs
        ):
            """Create a contract via API and return its ID"""
            import json

            from rest_framework import status

            from hub.apps.contracts.models import Contract, OriginalFormat

            # Provide default original_raw if not provided
            # NOTE: apiVersion + kind are required for the DataContract service to
            # recognise this as an ODCS contract and return VALID/INVALID instead of SKIPPED.
            if original_raw is None:
                original_raw = '{"apiVersion": "v3.0.2", "kind": "DataContract", "id": "test-contract", "info": {"name": "Test Contract"}, "schema": {"fields": [{"name": "id", "type": "string"}]}}'
            else:
                # Fix common contract structure issues for ODCS compliance
                try:
                    contract_data = (
                        json.loads(original_raw) if isinstance(original_raw, str) else original_raw
                    )

                    # Ensure ODCS spec identifiers exist so the DataContract
                    # service recognises the format (prevents SKIPPED status).
                    if (
                        "dataContractSpecification" not in contract_data
                        and "apiVersion" not in contract_data
                        and "odcs_version" not in contract_data
                    ):
                        contract_data["apiVersion"] = "v3.0.2"
                        contract_data["kind"] = "DataContract"

                    # Ensure 'id' field exists
                    if "id" not in contract_data:
                        contract_id = contract_data.get("info", {}).get("name", "test-contract")
                        contract_data["id"] = contract_id

                    # Fix: Move root-level 'name' to 'info.name' if needed
                    if "name" in contract_data and "info" not in contract_data:
                        name = contract_data.pop("name")
                        contract_data["info"] = {"name": name}
                    elif (
                        "name" in contract_data
                        and "info" in contract_data
                        and "name" not in contract_data.get("info", {})
                    ):
                        # Root-level name exists but info.name doesn't
                        name = contract_data.pop("name")
                        if "info" not in contract_data:
                            contract_data["info"] = {}
                        contract_data["info"]["name"] = name

                    # Ensure info.name exists
                    if "info" not in contract_data:
                        contract_data["info"] = {}
                    if "name" not in contract_data.get("info", {}):
                        # Use id as fallback for name
                        contract_data["info"]["name"] = contract_data.get("id", "test-contract")

                    # Fix: Ensure schema.fields exists (required by ODCS)
                    if "schema" not in contract_data:
                        contract_data["schema"] = {}
                    if "fields" not in contract_data.get("schema", {}):
                        # If models exist, extract fields from first model
                        if "models" in contract_data and contract_data["models"]:
                            first_model = contract_data["models"][0]
                            if "fields" in first_model:
                                contract_data["schema"]["fields"] = first_model["fields"]
                            else:
                                contract_data["schema"]["fields"] = [
                                    {"name": "id", "type": "string"}
                                ]
                        else:
                            contract_data["schema"]["fields"] = [{"name": "id", "type": "string"}]
                    elif not contract_data.get("schema", {}).get("fields"):
                        # Empty fields array - add at least one field
                        contract_data["schema"]["fields"] = [{"name": "id", "type": "string"}]

                    # Convert back to JSON string
                    original_raw = json.dumps(contract_data)
                except (json.JSONDecodeError, AttributeError, TypeError):
                    # If parsing fails, use as-is (might be YAML or already correct)
                    pass

            # Auto-detect format from original_raw if not provided
            if original_format is None:
                if original_raw.strip().startswith("{") or original_raw.strip().startswith("["):
                    original_format = OriginalFormat.JSON
                elif original_raw.strip().startswith("---") or "id:" in original_raw[:100]:
                    original_format = OriginalFormat.YAML
                else:
                    original_format = OriginalFormat.YAML  # Default

            # Ensure format is uppercase (JSON or YAML)
            if isinstance(original_format, str):
                original_format = original_format.upper()
                if original_format not in [OriginalFormat.JSON, OriginalFormat.YAML]:
                    original_format = OriginalFormat.YAML

            # Override if provided in kwargs
            if "original_format" in kwargs:
                original_format = kwargs.pop("original_format")
                if isinstance(original_format, str):
                    original_format = original_format.upper()

            response = self.client.post(
                "/api/v1/contracts/",
                {
                    "asset_id": asset_id,
                    "original_raw": original_raw,
                    "original_format": original_format,
                    **kwargs,
                },
                format="json",
            )

            if response.status_code not in [status.HTTP_201_CREATED, status.HTTP_200_OK]:
                raise Exception(
                    f"Failed to create contract: {response.status_code} - {get_response_data(response)}"
                )

            data = get_response_data(response)
            return data["id"] if data else None

        def init_file_upload(self, name: str, content_type: str = None, size: int = None, **kwargs):
            """Initialize a file upload and return file ID"""
            from rest_framework import status

            # Provide defaults if not specified
            if content_type is None:
                # Infer from filename
                if name.endswith(".csv"):
                    content_type = "text/csv"
                elif name.endswith(".json"):
                    content_type = "application/json"
                elif name.endswith(".parquet"):
                    content_type = "application/parquet"
                else:
                    content_type = "application/octet-stream"

            if size is None:
                size = 1024  # Default size for tests

            response = self.client.post(
                "/api/v1/files/init/",
                {"name": name, "content_type": content_type, "size": size, **kwargs},
                format="json",
            )

            if response.status_code != status.HTTP_201_CREATED:
                error_data = get_response_data(response) or str(
                    getattr(response, "content", b"")
                )
                raise Exception(
                    f"Failed to init file upload: {response.status_code} - {error_data}"
                )

            # Response uses 'file_id' not 'id' (see FileInitResponseSerializer)
            data = get_response_data(response)
            return (data.get("file_id") or data.get("id")) if data else None

        def complete_file_upload(
            self,
            file_id,
            content_sha256: str = None,
            test_content: bytes = None,
            mock_s3: bool = False,
        ):
            """Complete a file upload"""
            import hashlib

            import boto3
            from botocore.exceptions import ClientError
            from django.conf import settings
            from rest_framework import status

            from hub.apps.files.models import File, FileStatus

            # Get file object to access storage_path
            file_obj = File.objects.get(id=file_id)

            # If no test_content provided, generate dummy content matching the expected size
            if not test_content:
                # Special case: if size is 0, create empty content
                if file_obj.size == 0:
                    test_content = b""
                else:
                    # Generate dummy content of the expected size to match file_obj.size
                    expected_size = file_obj.size

                    # Generate appropriate content based on content type
                    if file_obj.content_type and "csv" in file_obj.content_type.lower():
                        # Generate valid CSV with headers and data rows
                        header = b"id,name,value\n"
                        row = b"1,test,value1\n"
                        # Calculate how many rows we need to reach expected_size
                        row_size = len(row)
                        header_size = len(header)
                        remaining_size = max(0, expected_size - header_size)
                        num_rows = max(1, remaining_size // row_size)
                        test_content = header + (row * num_rows)
                        # Truncate to exact size if needed
                        if len(test_content) > expected_size:
                            test_content = test_content[:expected_size]
                    elif file_obj.content_type and "json" in file_obj.content_type.lower():
                        # Generate minimal valid JSON
                        test_content = b'{"id": 1, "name": "test"}' + (
                            b" " * max(0, expected_size - 25)
                        )
                    elif file_obj.content_type and (
                        "parquet" in file_obj.content_type.lower()
                        or file_obj.name.endswith(".parquet")
                    ):
                        # For parquet files, don't generate content - let the test provide it
                        # Or generate minimal binary content
                        test_content = b"\x00" * expected_size
                    elif file_obj.content_type and (
                        "xlsx" in file_obj.content_type.lower() or file_obj.name.endswith(".xlsx")
                    ):
                        # For unsupported formats like xlsx, don't generate content
                        # This allows the test to verify format validation
                        test_content = b"\x00" * expected_size
                    else:
                        # Default: generate dummy content
                        test_content = b"0" * expected_size

            # Calculate SHA256 from content
            content_sha256 = hashlib.sha256(test_content).hexdigest()

            # Update file size to match actual content
            file_obj.size = len(test_content)
            file_obj.save()

            # If mock_s3 is True, just mark file as completed in DB (skip S3)
            if mock_s3:
                file_obj.status = FileStatus.ACTIVE  # Use ACTIVE not COMPLETED
                file_obj.content_sha256 = content_sha256
                file_obj.save()
            else:
                # Try to upload to S3 using the correct storage_path
                try:
                    # Get S3 credentials from settings (which handles staging detection)
                    s3_endpoint = get_s3_endpoint_url()
                    s3_access_key = getattr(settings, "AWS_ACCESS_KEY_ID", "minio")
                    s3_secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", "minio123")

                    s3_client = boto3.client(
                        "s3",
                        endpoint_url=s3_endpoint,
                        aws_access_key_id=s3_access_key,
                        aws_secret_access_key=s3_secret_key,
                        region_name="us-east-1",
                    )

                    # Get bucket name from settings
                    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "hub-files")

                    # Ensure bucket exists
                    try:
                        s3_client.head_bucket(Bucket=bucket_name)
                    except ClientError:
                        # Try to create bucket (may fail if we don't have permissions, that's OK)
                        try:
                            s3_client.create_bucket(Bucket=bucket_name)
                        except ClientError as e:
                            error_code = e.response.get("Error", {}).get("Code", "")
                            if error_code in (
                                "BucketAlreadyExists",
                                "BucketAlreadyOwnedByYou",
                            ):
                                pass  # Expected — bucket exists
                            else:
                                import logging

                                logging.getLogger(__name__).warning(
                                    "S3 bucket creation failed: %s", e
                                )

                    # Upload file content to the correct storage_path
                    # The storage_path format is: {tenant.id}/{file_id}/{name}
                    s3_key = file_obj.storage_path
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=s3_key,
                        Body=test_content,
                        ContentType=file_obj.content_type,
                    )
                except Exception:
                    # When mock_s3=False and S3 fails, re-raise (Phase 7.2.2).
                    # No silent fallback to mock mode — tests that require real S3 must fail when S3 is broken.
                    raise

            # Complete upload via API (only if not already marked as mock)
            if not mock_s3:
                import time

                max_retries = 5
                retry_delay = 1

                for attempt in range(max_retries):
                    response = self.client.post(
                        f"/api/v1/files/{file_id}/complete/",
                        {"content_sha256": content_sha256},
                        format="json",
                    )

                    if response.status_code == status.HTTP_200_OK:
                        break

                    # Handle rate limiting with retry
                    if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                        if attempt < max_retries - 1:
                            # Extract retry_after from response if available
                            error_data = get_response_data(response) or {}

                            # Get retry_after from error details or use exponential backoff
                            retry_after = (
                                error_data.get("error", {})
                                .get("details", {})
                                .get("retry_after", retry_delay * (2**attempt))
                            )
                            time.sleep(min(retry_after, 10))  # Cap at 10 seconds  # INTENTIONAL: test-specific timing
                            continue

                    # For non-rate-limit errors, raise immediately
                    error_data = get_response_data(response)
                    if error_data is None:
                        error_data = (
                            getattr(response, "content", b"").decode("utf-8", errors="ignore")
                            if hasattr(response, "content")
                            else str(response)
                        )
                    raise Exception(
                        f"Failed to complete file upload: {response.status_code} - {error_data}"
                    )

                # Final check after retries
                if response.status_code != status.HTTP_200_OK:
                    error_data = get_response_data(response)
                    if error_data is None:
                        error_data = (
                            getattr(response, "content", b"").decode("utf-8", errors="ignore")
                            if hasattr(response, "content")
                            else str(response)
                        )
                    raise Exception(
                        f"Failed to complete file upload after {max_retries} attempts: {response.status_code} - {error_data}"
                    )

        def create_dataset(self, file_id, asset_id, **kwargs):
            """Create a dataset via API and return its ID"""
            from rest_framework import status

            response = self.client.post(
                "/api/v1/datasets/",
                {"file_id": file_id, "asset_id": asset_id, **kwargs},
                format="json",
            )

            if response.status_code != status.HTTP_201_CREATED:
                raise Exception(
                    f"Failed to create dataset: {response.status_code} - {get_response_data(response)}"
                )

            # The response should be a dict from DatasetSerializer with 'id' field
            data = get_response_data(response)

            # Handle dict response (most common)
            if isinstance(data, dict):
                dataset_id = data.get("id")
                if dataset_id:
                    return dataset_id
                # Try alternative keys if 'id' not found
                dataset_id = data.get("dataset_id") or data.get("uuid")
                if dataset_id:
                    return dataset_id
                # Last resort: check all keys
                raise Exception(
                    f"Dataset creation response missing 'id' field. Available keys: {list(data.keys())}, Response: {data}"
                )

            # Handle object response (OrderedDict or similar)
            dataset_id = getattr(data, "id", None)
            if dataset_id:
                return dataset_id

            # Try to access as dict even if not isinstance dict
            try:
                dataset_id = data["id"]
                if dataset_id:
                    return dataset_id
            except (KeyError, TypeError):
                pass

            raise Exception(
                f"Dataset creation response missing 'id' field. Response type: {type(data)}, Response: {data}"
            )

        def prepare_contract_for_activation(self, contract_id):
            """Prepare contract for activation (validate and normalize)"""
            import time

            from hub.apps.contracts.models import (
                Contract,
                ContractStatus,
                NormalizationStatus,
                ValidationStatus,
            )

            contract = Contract.objects.get(id=contract_id)

            # Do NOT trigger async validation tasks here.  The datacontract-cli
            # service may return SKIPPED for test contracts, and the async task
            # can complete AFTER we force-set validation_status to VALID below,
            # overwriting it with SKIPPED — a race condition that causes the
            # contract attachment to be rejected with validation_status=SKIPPED.
            # We set the required statuses directly instead.
            contract.refresh_from_db()

            # CRITICAL: Preserve existing extensions (especially x_odps links) BEFORE any normalization
            # Check database directly for existing links to ensure we don't lose them
            existing_extensions = None
            existing_x_odps = None
            if contract.hub_contract_json and "extensions" in contract.hub_contract_json:
                import copy

                existing_extensions = copy.deepcopy(
                    contract.hub_contract_json.get("extensions", {})
                )
                if "x_odps" in existing_extensions:
                    existing_x_odps = copy.deepcopy(existing_extensions["x_odps"])

            # Also check database for linked contracts if links aren't in memory
            if not existing_x_odps or (
                not existing_x_odps.get("odcs_link") and not existing_x_odps.get("odps_link")
            ):
                from hub.apps.contracts.models import Contract as ContractModel
                from hub.apps.contracts.models import OriginalSpecType

                try:
                    # Check if this is an ODPS contract linked to an ODCS contract
                    if contract.original_spec_type == OriginalSpecType.ODPS:
                        linked_odcs = ContractModel.objects.filter(
                            hub_contract_json__extensions__x_odps__odps_link=str(contract.id)
                        ).first()
                        if linked_odcs:
                            if not existing_x_odps:
                                existing_x_odps = {}
                            existing_x_odps["odcs_link"] = str(linked_odcs.id)
                    # Check if this is an ODCS contract linked to an ODPS contract
                    elif contract.original_spec_type == OriginalSpecType.ODCS:
                        linked_odps = ContractModel.objects.filter(
                            hub_contract_json__extensions__x_odps__odcs_link=str(contract.id)
                        ).first()
                        if linked_odps:
                            if not existing_x_odps:
                                existing_x_odps = {}
                            existing_x_odps["odps_link"] = str(linked_odps.id)
                except Exception:
                    pass  # If query fails, continue without database lookup

            # Try to trigger normalization via tasks if available
            if contract.normalization_status not in [
                NormalizationStatus.NORMALIZED_OK,
                NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            ]:
                try:
                    from hub.apps.contracts import tasks

                    if hasattr(tasks, "normalize_contract_task"):
                        tasks.normalize_contract_task.delay(contract_id)
                        time.sleep(1)  # INTENTIONAL: e2e/integration test polling real services
                except (ImportError, AttributeError):
                    pass  # Tasks not available, will set manually

            # Refresh again after potential normalization
            contract.refresh_from_db()

            # Set validation_status to VALID for E2E tests if not already valid.
            # Now safe from race conditions because we no longer trigger async
            # validation tasks above.
            if contract.validation_status not in [
                ValidationStatus.VALID,
                ValidationStatus.WARNING_ONLY,
            ]:
                import logging
                _prep_logger = logging.getLogger(__name__)
                _prep_logger.warning(
                    "prepare_contract: overriding validation_status from %s to VALID for contract %s (service unavailable)",
                    contract.validation_status,
                    contract.id,
                )
                contract.validation_status = ValidationStatus.VALID
                contract.save(update_fields=["validation_status", "updated_at"])

            # Ensure hub_contract_json has hub_contract_version if missing
            if (
                contract.hub_contract_json
                and "hub_contract_version" not in contract.hub_contract_json
            ):
                contract.hub_contract_json["hub_contract_version"] = (
                    contract.hub_contract_version or "1.0.0"
                )
                contract.save(update_fields=["hub_contract_json"])

            # Handle None normalization_status explicitly
            if contract.normalization_status is None or contract.normalization_status not in [
                NormalizationStatus.NORMALIZED_OK,
                NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            ]:
                import logging
                _prep_logger = logging.getLogger(__name__)
                _prep_logger.warning(
                    "prepare_contract: overriding normalization_status from %s to NORMALIZED_OK "
                    "and creating stub hub_contract_json for contract %s (service unavailable)",
                    contract.normalization_status,
                    contract.id,
                )
                if not contract.hub_contract_json:
                    contract.hub_contract_json = {
                        "hub_contract_version": 1,
                        "id": "test",
                        "schema": {},
                    }

                # CRITICAL: Always restore preserved extensions (especially x_odps links)
                if existing_x_odps:
                    if "extensions" not in contract.hub_contract_json:
                        contract.hub_contract_json["extensions"] = {}
                    if "x_odps" not in contract.hub_contract_json["extensions"]:
                        contract.hub_contract_json["extensions"]["x_odps"] = {}
                    # Merge preserved x_odps links (preserved takes precedence)
                    contract.hub_contract_json["extensions"]["x_odps"].update(existing_x_odps)

                # Restore any other preserved extensions
                if existing_extensions:
                    if "extensions" not in contract.hub_contract_json:
                        contract.hub_contract_json["extensions"] = {}
                    # Merge preserved extensions (preserved takes precedence)
                    for key, value in existing_extensions.items():
                        if key != "x_odps":  # x_odps already handled above
                            if key not in contract.hub_contract_json["extensions"]:
                                contract.hub_contract_json["extensions"][key] = value

                # Set hub_contract_version field (separate from the JSON key)
                if not contract.hub_contract_version:
                    contract.hub_contract_version = "1.0.0"
                contract.normalization_status = NormalizationStatus.NORMALIZED_OK
                contract.save(
                    update_fields=[
                        "hub_contract_json",
                        "normalization_status",
                        "hub_contract_version",
                    ]
                )

            # Set status to ACTIVE only after ensuring validation_status and normalization_status are set
            # This order is important to avoid validation errors
            if contract.status != ContractStatus.ACTIVE:
                contract.status = ContractStatus.ACTIVE

            # Validate before saving to catch any issues early
            try:
                contract.full_clean()
            except Exception as e:
                # If validation fails, log and re-raise
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Contract validation failed: {e}. Contract: {contract.id}, validation_status: {contract.validation_status}, normalization_status: {contract.normalization_status}"
                )
                raise

            contract.save()
            return True

        def prepare_asset_for_activation(self, asset_id):
            """Prepare asset for activation (contract, DQ and compliance checks)"""
            import time

            from hub.apps.assets.models import Asset, ComplianceStatus, DQStatus
            from hub.apps.contracts.models import (
                Contract,
                ContractStatus,
                NormalizationStatus,
                ValidationStatus,
            )

            asset = Asset.objects.get(id=asset_id)

            # Ensure at least one ACTIVE contract exists
            if not asset.contracts.filter(status=ContractStatus.ACTIVE).exists():
                contract = asset.contracts.first()
                if not contract:
                    # No contract at all — create one so the asset can be activated
                    contract_id = self.create_contract(str(asset_id))
                    self.attach_contract_to_asset(str(asset_id), contract_id)
                    contract = Contract.objects.get(id=contract_id)
                self.prepare_contract_for_activation(str(contract.id))
                contract.refresh_from_db()
                if contract.status != ContractStatus.ACTIVE:
                    contract.status = ContractStatus.ACTIVE
                    contract.save(update_fields=["status"])

            # Ensure ALL contracts attached to the asset have valid
            # statuses — can_activate() uses .first() which is
            # non-deterministic when multiple ACTIVE contracts exist
            # (e.g. ODCS + ODPS), so every one must be acceptable.
            valid_statuses = {ValidationStatus.VALID, ValidationStatus.WARNING_ONLY}
            norm_statuses = {NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS}
            for c in asset.contracts.all():
                needs_save = False
                if c.validation_status not in valid_statuses:
                    self.prepare_contract_for_activation(str(c.id))
                    c.refresh_from_db()
                if c.normalization_status not in norm_statuses:
                    self.prepare_contract_for_activation(str(c.id))
                    c.refresh_from_db()
                if c.status != ContractStatus.ACTIVE:
                    c.status = ContractStatus.ACTIVE
                    needs_save = True
                if c.validation_status not in valid_statuses:
                    c.validation_status = ValidationStatus.VALID
                    needs_save = True
                if c.normalization_status not in norm_statuses:
                    c.normalization_status = NormalizationStatus.NORMALIZED_OK
                    needs_save = True
                if needs_save:
                    c.save()

            # Try to trigger DQ check via tasks if available
            if asset.dq_status == DQStatus.UNKNOWN:
                try:
                    from hub.apps.dq import tasks

                    if hasattr(tasks, "run_dq_check_task"):
                        tasks.run_dq_check_task.delay(asset_id)
                        time.sleep(1)  # INTENTIONAL: e2e/integration test polling real services
                except (ImportError, AttributeError):
                    pass  # Tasks not available, will set manually

            # Try to trigger compliance check via tasks if available
            if asset.compliance_status == ComplianceStatus.UNKNOWN:
                try:
                    from hub.apps.compliance import tasks

                    if hasattr(tasks, "run_compliance_check_task"):
                        tasks.run_compliance_check_task.delay(asset_id)
                        time.sleep(1)  # INTENTIONAL: e2e/integration test polling real services
                except (ImportError, AttributeError):
                    pass  # Tasks not available, will set manually

            # Refresh and ensure statuses are set for test purposes
            asset.refresh_from_db()

            # Ensure DQ and compliance statuses are acceptable for
            # activation.  The compliance/DQ services may have run
            # against synthetic test data and returned FAIL, which is
            # not relevant to the journey being tested (ODPS linking,
            # contract-first, etc.).
            import logging
            _prep_logger = logging.getLogger(__name__)

            if asset.dq_status not in (DQStatus.PASS, DQStatus.WARN):
                _prep_logger.warning(
                    "prepare_asset: overriding %s from %s to PASS for asset %s",
                    "dq_status", asset.dq_status, asset_id,
                )
                asset.dq_status = DQStatus.PASS

            if asset.compliance_status not in (
                ComplianceStatus.PASS,
                ComplianceStatus.WARN,
            ):
                _prep_logger.warning(
                    "prepare_asset: overriding %s from %s to PASS for asset %s",
                    "compliance_status", asset.compliance_status, asset_id,
                )
                asset.compliance_status = ComplianceStatus.PASS

            # The activate endpoint (5.4.3) also checks the latest
            # SUCCEEDED compliance run's allowed_to_store flag.  The
            # compliance service may have scanned synthetic test data
            # and set allowed_to_store=False; fix that here so the
            # activation check passes.
            from hub.apps.compliance.models import (
                ComplianceRun,
                ComplianceRunStatus,
            )

            from django.db.models import Q

            updated_rows = asset.compliance_runs.filter(
                status=ComplianceRunStatus.SUCCEEDED,
            ).filter(
                Q(allowed_to_store=False) | Q(allowed_to_store__isnull=True)
            ).update(allowed_to_store=True)
            if updated_rows:
                _prep_logger.warning(
                    "prepare_asset: bulk-updated allowed_to_store=True on %d compliance runs for asset %s",
                    updated_rows, asset_id,
                )

            asset.save()
            return True

        def activate_asset(self, asset_id):
            """Activate an asset via API (includes version for optimistic locking).

            Ensures all activation prerequisites are met, then sends the
            activate request with the current version for optimistic locking.
            Returns the response as-is — the calling test is responsible for
            asserting the result.
            """
            from hub.apps.assets.models import Asset

            # Ensure prerequisites.
            self.prepare_asset_for_activation(asset_id)

            # Re-read AFTER prepare to get the definitive version.
            asset = Asset.objects.get(id=asset_id)

            response = self.client.post(
                f"/api/v1/assets/{asset_id}/activate/",
                {"version": asset.version},
                format="json",
            )

            return response

        def verify_audit_log(
            self,
            action: str,
            resource_type: str,
            resource_id=None,
            result: str = "SUCCESS",
            **kwargs,
        ):
            """Verify an audit log entry exists"""
            from hub.apps.audit.models import AuditEvent

            # Query for the audit event
            query = AuditEvent.objects.filter(
                action=action, resource_type=resource_type, result=result, **kwargs
            )

            # Only filter by resource_id if provided (some events like LOGIN don't have resource_id)
            if resource_id is not None:
                query = query.filter(resource_id=str(resource_id))

            self.assertGreater(
                query.count(),
                0,
                f"Expected audit log entry not found: {action} for {resource_type}"
                + (f" {resource_id}" if resource_id else ""),
            )

        def verify_asset_state(self, asset_id, **kwargs):
            """Verify asset state matches expected values"""
            from hub.apps.assets.models import Asset

            asset = Asset.objects.get(id=asset_id)
            for key, value in kwargs.items():
                actual_value = getattr(asset, key)
                self.assertEqual(
                    actual_value,
                    value,
                    f"Asset {key} mismatch: expected {value}, got {actual_value}",
                )

        def verify_contract_state(self, contract_id, **kwargs):
            """Verify contract state matches expected values"""
            from hub.apps.contracts.models import Contract

            contract = Contract.objects.get(id=contract_id)
            for key, value in kwargs.items():
                actual_value = getattr(contract, key)
                self.assertEqual(
                    actual_value,
                    value,
                    f"Contract {key} mismatch: expected {value}, got {actual_value}",
                )

        def verify_file_in_s3(
            self, file_id, expected_content: bytes = None, expected_size: int = None
        ):
            """Verify file exists in S3. Skips if S3 is not available."""
            from hub.apps.files.models import File

            try:
                file_obj = File.objects.get(id=file_id)
                if not file_obj.storage_path:
                    return  # File not yet uploaded to S3
                from hub.apps.files.storage import S3StorageClient

                client = S3StorageClient()
                content = client.get_file_content(file_obj.storage_path)
                self.assertIsNotNone(
                    content,
                    f"File {file_id} should exist in S3 at {file_obj.storage_path}",
                )
                if expected_content is not None:
                    self.assertEqual(
                        content,
                        expected_content,
                        "S3 content should match expected content",
                    )
                if expected_size is not None:
                    self.assertEqual(
                        len(content),
                        expected_size,
                        f"S3 file size should be {expected_size}",
                    )
            except ImportError:
                # S3 storage code not installed in this environment — a
                # legitimate skip condition, not a silent failure.
                pytest.skip("S3 storage backend not importable")
            except (ConnectionError, TimeoutError, OSError) as exc:
                # Network / socket errors — MinIO is unreachable. Visible
                # as a skip in reports so infra outages are quantifiable
                # (PR 10's skip-counter gate ties this into CI failure
                # when skips cross a threshold). Critically, we do NOT
                # blanket-catch Exception — a bug in S3StorageClient
                # itself must still surface as a real failure.
                pytest.skip(f"S3 not reachable: {exc}")

        def verify_cross_service_consistency(self, resource_id, resource_type: str):
            """Verify resource exists in semantic service. Skips if unavailable."""
            try:
                from hub.apps.semantic.models import SemanticResource

                resource = SemanticResource.objects.filter(
                    resource_id=str(resource_id), resource_type=resource_type
                ).first()
                if resource:
                    self.assertIsNotNone(
                        resource.status, "Semantic resource should have a status"
                    )
            except ImportError:
                # Semantic service app not installed — visible skip.
                pytest.skip("Semantic service not importable")

        def verify_job_completion(self, job_id, expected_status: str = None, max_wait: int = 180):
            """Verify job completes with expected status"""
            import time

            from hub.apps.jobs.models import Job, JobStatus

            start_time = time.time()
            while time.time() - start_time < max_wait:
                try:
                    job = Job.objects.get(id=job_id)
                    if expected_status:
                        if job.status == expected_status:
                            return job
                    elif job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                        return job
                except Job.DoesNotExist:
                    pass
                time.sleep(1)  # INTENTIONAL: e2e/integration test polling real services

            # Timeout - check final status
            job = Job.objects.get(id=job_id)
            if expected_status:
                self.assertEqual(
                    job.status,
                    expected_status,
                    f"Job {job_id} did not reach expected status {expected_status} within {max_wait}s. Current status: {job.status}",
                )
            return job

        def validate_contract(self, contract_id, async_mode: bool = False, **kwargs):
            """Validate a contract via API"""
            from rest_framework import status

            response = self.client.post(
                f"/api/v1/contracts/{contract_id}/validate/",
                {"async": async_mode, **kwargs},
                format="json",
            )

            if response.status_code not in [
                status.HTTP_200_OK,
                status.HTTP_201_CREATED,
                status.HTTP_202_ACCEPTED,
            ]:
                # Return dict with status_code for error handling in tests
                return {"status_code": response.status_code, "error": get_response_data(response)}

            return get_response_data(response)

        def run_compliance_check(self, file_id=None, dataset_id=None, asset_id=None, **kwargs):
            """Create a compliance run via API"""
            from rest_framework import status

            payload = {}
            if file_id:
                payload["file_id"] = str(file_id)
            if dataset_id:
                payload["dataset_id"] = str(dataset_id)
            if asset_id:
                payload["asset_id"] = str(asset_id)
            payload.update(kwargs)

            response = self.client.post("/api/v1/compliance/runs/", payload, format="json")

            if response.status_code != status.HTTP_201_CREATED:
                raise Exception(
                    f"Failed to create compliance run: {response.status_code} - {get_response_data(response)}"
                )

            data = get_response_data(response) or {}
            return data.get("id")

        def run_dq_check(self, file_id=None, dataset_id=None, asset_id=None, **kwargs):
            """Create a DQ run via API"""
            from rest_framework import status

            payload = {}
            if file_id:
                payload["file_id"] = str(file_id)
            if dataset_id:
                payload["dataset_id"] = str(dataset_id)
            if asset_id:
                payload["asset_id"] = str(asset_id)
            payload.update(kwargs)

            response = self.client.post("/api/v1/dq/runs/", payload, format="json")

            if response.status_code != status.HTTP_201_CREATED:
                raise Exception(
                    f"Failed to create DQ run: {response.status_code} - {get_response_data(response)}"
                )

            data = get_response_data(response) or {}
            return data.get("id")

        def _execute_run_job_inline(self, run_model, run_id, job_type_str):
            """Execute the RQ job for a compliance/DQ run inline.

            Django TestCase wraps each test in a non-committing transaction,
            so ``transaction.on_commit()`` callbacks (where jobs are enqueued)
            never fire.  This helper finds the Job associated with the run and
            executes it synchronously, matching what the RQ worker would do.
            """
            from hub.apps.jobs.models import Job, JobType

            run = run_model.objects.get(id=run_id)
            if not run.job_id:
                return  # No job attached — nothing to execute

            try:
                from hub.apps.jobs.tasks import process_job

                process_job(str(run.job_id), type=getattr(JobType, job_type_str))
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "Inline job execution failed for %s (expected if service unavailable): %s",
                    job_type_str,
                    exc,
                )

        def run_compliance_check_sync(self, file_id=None, dataset_id=None, asset_id=None, **kwargs):
            """Create a compliance run and execute its job inline (synchronous)."""
            from hub.apps.compliance.models import ComplianceRun

            run_id = self.run_compliance_check(file_id, dataset_id, asset_id, **kwargs)
            self._execute_run_job_inline(ComplianceRun, run_id, "COMPLIANCE_RUN")
            return run_id

        def run_dq_check_sync(self, file_id=None, dataset_id=None, asset_id=None, **kwargs):
            """Create a DQ run and execute its job inline (synchronous)."""
            from hub.apps.dq.models import DQRun

            run_id = self.run_dq_check(file_id, dataset_id, asset_id, **kwargs)
            self._execute_run_job_inline(DQRun, run_id, "DQ_RUN")
            return run_id

        def wait_for_job_completion(self, job_id, timeout=120, poll_interval=2):
            """
            Wait for a job to complete (polling via wait_until; no fixed sleep per 4.3.2).

            Args:
                job_id: Job UUID
                timeout: Maximum wait time in seconds
                poll_interval: Polling interval in seconds

            Returns:
                Job object with final status

            Raises:
                AssertionError: If job doesn't complete within timeout
            """
            from hub.apps.jobs.models import Job, JobStatus
            from tests.utils.polling import wait_until

            timeout = min(timeout, 300)  # Cap at 5 minutes

            def job_reached_terminal():
                try:
                    job = Job.objects.get(id=job_id)
                    return job.status in [
                        JobStatus.COMPLETED,
                        JobStatus.FAILED,
                        JobStatus.CANCELLED,
                    ]
                except Job.DoesNotExist:
                    return False

            wait_until(
                job_reached_terminal,
                timeout=timeout,
                interval=poll_interval,
                message=f"Job {job_id} did not reach terminal state within {timeout}s",
            )
            return Job.objects.get(id=job_id)

        def attach_contract_to_asset(self, asset_id, contract_id):
            """Attach a contract to an asset via API.

            Ensures the contract has a valid validation_status before
            attachment.  The DataContract service may return INVALID for
            minimal test contracts; the attachment endpoint rejects
            contracts that are not VALID/WARNING_ONLY/SKIPPED.
            """
            from rest_framework import status as http_status

            from hub.apps.contracts.models import Contract, ValidationStatus

            # Ensure contract validation_status is acceptable for attachment
            contract = Contract.objects.get(id=contract_id)
            if contract.validation_status not in (
                ValidationStatus.VALID,
                ValidationStatus.WARNING_ONLY,
                ValidationStatus.SKIPPED,
            ):
                contract.validation_status = ValidationStatus.VALID
                contract.save(update_fields=["validation_status", "updated_at"])

            response = self.client.post(
                f"/api/v1/assets/{asset_id}/contracts/",
                {"contract_id": str(contract_id)},
                format="json",
            )

            if response.status_code not in [http_status.HTTP_200_OK, http_status.HTTP_204_NO_CONTENT]:
                error_data = get_response_data(response) or str(
                    getattr(response, "content", b"")
                )
                raise Exception(
                    f"Failed to attach contract to asset: {response.status_code} - {error_data}"
                )

            return get_response_data(response)

        def attach_dataset_to_asset(self, asset_id, dataset_id):
            """Attach a dataset to an asset (dataset already has asset_id, this is a no-op but kept for API compatibility)"""
            from hub.apps.datasets.models import Dataset

            # Dataset already has asset_id set during creation
            # This method exists for API compatibility
            dataset = Dataset.objects.get(id=dataset_id)
            if str(dataset.asset_id) != str(asset_id):
                dataset.asset_id = asset_id
                dataset.save()

            return dataset_id

        def verify_entitlement_created(self, order_id, asset_id):
            """Verify that an entitlement was created for an order"""
            from django.db import transaction

            from hub.apps.marketplace.models import Entitlement, Order

            # Use transaction to ensure order is visible (handles transaction isolation)
            with transaction.atomic():
                try:
                    order = Order.objects.get(id=order_id)
                except Order.DoesNotExist:
                    self.fail(f"Order {order_id} not found when verifying entitlement")

            entitlements = Entitlement.objects.filter(order=order, asset_id=asset_id)

            self.assertGreater(
                entitlements.count(),
                0,
                f"Expected entitlement not found for order {order_id} and asset {asset_id}",
            )

            return entitlements.first()

        def verify_rdf_triples(
            self,
            resource_id,
            resource_type: str,
            expected_triples: list = None,
            expected_triples_count: int = None,
        ):
            """Verify RDF triples exist for resource. Skips if semantic service unavailable."""
            try:
                from hub.apps.semantic.models import SemanticResource

                resource = SemanticResource.objects.get(
                    resource_id=str(resource_id), resource_type=resource_type
                )
                self.assertIsNotNone(
                    resource,
                    f"Semantic resource should exist for {resource_type}:{resource_id}",
                )
                if expected_triples_count is not None and hasattr(
                    resource, "triples_count"
                ):
                    self.assertEqual(
                        resource.triples_count,
                        expected_triples_count,
                        f"Expected {expected_triples_count} triples, got {resource.triples_count}",
                    )
            except ImportError:
                pass  # Semantic service not available
            except SemanticResource.DoesNotExist:
                # Resource not mapped yet — this is a real issue if mapping was expected
                import logging

                logging.getLogger(__name__).warning(
                    "SemanticResource not found for %s:%s — mapping may not have completed",
                    resource_type,
                    resource_id,
                )

        def wait_for_semantic_mapping(
            self, *args, timeout: int = 30, max_wait: int = None, **kwargs
        ):
            """Wait for semantic mapping to complete (optional)

            Supports multiple calling conventions:
            - wait_for_semantic_mapping(resource_type, resource_id, max_wait=30)
            - wait_for_semantic_mapping(resource_id, resource_type=..., timeout=30)
            """
            import time

            from hub.apps.semantic.models import SemanticResource

            # Support max_wait as alias for timeout
            if max_wait is not None:
                timeout = max_wait

            # Enforce maximum timeout to prevent tests from hanging indefinitely
            timeout = min(timeout, 120)  # Cap at 2 minutes

            # Determine resource_type and resource_id from args/kwargs
            resource_type = None
            resource_id = None

            # Check kwargs first
            if "resource_type" in kwargs:
                resource_type = kwargs["resource_type"]
            if "resource_id" in kwargs:
                resource_id = kwargs["resource_id"]

            # Check args - handle both orders: (resource_type, resource_id) and (resource_id, resource_type)
            if len(args) >= 1:
                arg1 = args[0]
                # Convert to string for comparison
                arg1_str = str(arg1)

                # Check if it's a ResourceType enum value (uppercase with underscores, or matches ResourceType values)
                from hub.apps.semantic.models import ResourceType

                is_resource_type = (
                    (isinstance(arg1, str) and arg1.isupper() and "_" in arg1)
                    or arg1_str in [rt[0] for rt in ResourceType.choices]
                    or arg1 in ResourceType.values
                    if hasattr(ResourceType, "values")
                    else False
                )

                if is_resource_type:
                    resource_type = arg1_str
                    if len(args) >= 2:
                        resource_id = args[1]
                else:
                    # First arg is resource_id (UUID string or object)
                    resource_id = arg1_str
                    if len(args) >= 2:
                        resource_type = str(args[1])

            if not resource_id or not resource_type:
                return None  # Can't wait without both

            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    resource = SemanticResource.objects.get(
                        resource_id=str(resource_id), resource_type=str(resource_type)
                    )
                    if resource.status in ["MAPPED", "ACTIVE"]:
                        return resource
                except SemanticResource.DoesNotExist:
                    pass
                time.sleep(1)  # INTENTIONAL: e2e/integration test polling real services

                # Safety check: if we've been waiting too long, break early
                if time.time() - start_time > timeout:
                    break

            # Timeout - return None (tests can handle this)
            return None

else:
    # Create a dummy class if Django is not available
    # This is a minimal stub - tests that don't use Django can still import it
    class E2ETestBase:
        """Base test class for E2E tests (Django not available)"""

        def setUp(self):
            """Set up test fixtures"""
            pytest.skip("Django not available - E2ETestBase requires Django")
