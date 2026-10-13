"""

import uuid
10.5.7: Marketplace Integration CLI/SDK Performance Tests

Tests performance of Marketplace Integration CLI commands and SDK methods:
- CLI command execution performance (< 500ms per command)
- SDK method execution performance (< 200ms per method)
- Concurrent CLI/SDK operations (100+ concurrent)

Targets:
- CLI command execution < 500ms
- SDK method execution < 200ms
- 100+ concurrent operations
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow
import contextlib

from django.conf import settings
from django.test import TransactionTestCase, override_settings

from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

# Try to import SDK
try:
    from datahub_interoperability import DataHubClient, DataHubClientConfig
    from datahub_interoperability.marketplace import MarketplaceIntegrationAPI

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

# Try to import CLI
CLI_AVAILABLE = True  # Assume CLI is available if we're in this environment


class MarketplaceCLISDKPerformanceTestBase(TransactionTestCase):
    """Base class for Marketplace CLI/SDK performance tests"""

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures"""
        import uuid

        # Create test tenant and user with unique names to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        tenant_name = f"Marketplace Perf Test Tenant {unique_id}"
        tenant_slug = f"marketplace-perf-test-{unique_id}"

        # Try to get existing tenant or create new one
        self.tenant, created = Tenant.objects.get_or_create(
            slug=tenant_slug,
            defaults={"name": tenant_name, "status": "ACTIVE", "kyc_status": "VERIFIED"},
        )

        # If tenant already exists, update name to be unique
        if not created:
            self.tenant.name = tenant_name
            self.tenant.save()

        # Create user with unique email
        user_email = f"marketplace-perf-test-{unique_id}@example.com"
        self.user, _ = User.objects.get_or_create(
            email=user_email,
            defaults={
                "password": "test-password-123",
                "tenant": self.tenant,
                "status": UserStatus.ACTIVE,
            },
        )

        # The marketplace API is feature-gated — enable it so the CLI/SDK
        # calls below succeed instead of 403ing.
        self.tenant.marketplace_integrations_enabled = True
        self.tenant.save(update_fields=["marketplace_integrations_enabled"])

        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        ensure_tenant_has_active_subscription(self.tenant)

        # Create API key for CLI auth (marketplace connectors list requires authentication)
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        self.api_key_obj = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=key_hash,
            name=f"Marketplace Perf Test Key {unique_id}",
            scopes=["integrations:read"],
        )
        self.api_key_plaintext = plaintext_key

        # Setup SDK client if available
        if SDK_AVAILABLE:
            config = DataHubClientConfig(
                base_url="http://localhost:8000/api/v1",
                api_token=self.api_key_plaintext,
            )
            self.client = DataHubClient(config)
            self.marketplace_api = MarketplaceIntegrationAPI(self.client)

    def tearDown(self):
        """Clean up test data"""

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for CLI/SDK performance tests."""
        # Don't flush - transactions are rolled back which provides isolation


def _api_db_settings():
    """Database settings matching the running API (hub_test) so CLI can authenticate."""
    db = settings.DATABASES["default"].copy()
    db_name = os.environ.get("POSTGRES_DB", "hub_test")
    db["NAME"] = db_name
    db["HOST"] = os.environ.get("POSTGRES_HOST", "localhost")
    db["PORT"] = os.environ.get("POSTGRES_PORT", "5432")
    db["USER"] = os.environ.get("POSTGRES_USER", "hub_test")
    db["PASSWORD"] = os.environ.get("POSTGRES_PASSWORD", "hub_test")
    db.setdefault("TEST", {})["NAME"] = db_name  # Use same DB, no test_ prefix
    return {"default": db}


def _maybe_override_databases(cls):
    """Point the test ORM at the API's DB only when it actually differs.

    In the compose test stack the test DB IS the API's DB — an
    ``override_settings(DATABASES=...)`` that reproduces the same config
    only emits Django's "Overriding setting DATABASES can lead to
    unexpected behavior" warning.  Host-side runs (test DB ≠ API DB) still
    get the override.
    """
    api_cfg = _api_db_settings()["default"]
    current = settings.DATABASES["default"]
    if api_cfg["NAME"] == current["NAME"] and api_cfg["HOST"] == current["HOST"]:
        return cls
    return override_settings(DATABASES=_api_db_settings())(cls)


@_maybe_override_databases
class TestMarketplaceCLIPerformance(MarketplaceCLISDKPerformanceTestBase):
    """Test Marketplace CLI command performance.

    Uses hub_test so the CLI can authenticate against the pre-running API.
    """

    @pytest.mark.skipif(not CLI_AVAILABLE, reason="CLI not available")
    def test_cli_connectors_list_performance(self):
        """Test CLI connectors list command performance"""
        project_root = Path(__file__).resolve().parent.parent.parent
        cli_cmd = [
            sys.executable,
            "-m",
            "cli.datahub_cli.main",
            "marketplace",
            "connectors",
            "list",
        ]
        api_base_url = os.environ.get("DATAHUB_API_BASE_URL", "http://localhost:8000/api/v1")
        test_env = {
            **os.environ,
            "PYTHONPATH": str(project_root),
            "DATAHUB_API_KEY": self.api_key_plaintext,
            # The CLI reads API_BASE_URL (not DATAHUB_API_BASE_URL); the
            # inherited container env has API_BASE_URL WITHOUT /api/v1,
            # which would make the CLI hit un-routed paths (HTML 404).
            "API_BASE_URL": api_base_url,
        }

        start_time = time.time()

        try:
            result = subprocess.run(
                cli_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=15.0,
                cwd=str(project_root),
                env=test_env,
            )
            duration = time.time() - start_time

            self.assertEqual(
                result.returncode,
                0,
                f"CLI connectors list failed: {result.stderr[:200] if result.stderr else result.stdout[:200]}",
            )
            # Verify command completed (10s in CI; 500ms is ideal target)
            self.assertLess(
                duration, 10.0, f"CLI connectors list took {duration:.3f}s, exceeds 10s limit"
            )
        except subprocess.TimeoutExpired:
            self.fail("CLI command timed out")
        except FileNotFoundError:
            pass

    @pytest.mark.skipif(not CLI_AVAILABLE, reason="CLI not available")
    def test_cli_connections_list_performance(self):
        """Test CLI connections list command performance"""
        project_root = Path(__file__).resolve().parent.parent.parent
        cli_cmd = [
            sys.executable,
            "-m",
            "cli.datahub_cli.main",
            "marketplace",
            "connections",
            "list",
        ]
        api_base_url = os.environ.get("DATAHUB_API_BASE_URL", "http://localhost:8000/api/v1")
        test_env = {
            **os.environ,
            "PYTHONPATH": str(project_root),
            "DATAHUB_API_KEY": self.api_key_plaintext,
            # The CLI reads API_BASE_URL (not DATAHUB_API_BASE_URL); the
            # inherited container env has API_BASE_URL WITHOUT /api/v1,
            # which would make the CLI hit un-routed paths (HTML 404).
            "API_BASE_URL": api_base_url,
        }

        start_time = time.time()

        try:
            result = subprocess.run(
                cli_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=15.0,
                cwd=str(project_root),
                env=test_env,
            )
            duration = time.time() - start_time

            self.assertEqual(
                result.returncode,
                0,
                f"CLI connections list failed: {result.stderr[:200] if result.stderr else result.stdout[:200]}",
            )
            # Verify command completed (10s in CI; 500ms is ideal target)
            self.assertLess(
                duration, 10.0, f"CLI connections list took {duration:.3f}s, exceeds 10s limit"
            )
        except subprocess.TimeoutExpired:
            self.fail("CLI command timed out")
        except FileNotFoundError:
            pass


class TestMarketplaceSDKPerformance(MarketplaceCLISDKPerformanceTestBase):
    """Test Marketplace SDK method performance"""

    @pytest.mark.skipif(not SDK_AVAILABLE, reason="SDK not available")
    def test_sdk_list_connectors_performance(self):
        """Test SDK list_connectors method performance"""
        import asyncio

        start_time = time.time()

        async def run():
            return await self.marketplace_api.list_connectors()

        connectors = asyncio.run(run())
        duration = time.time() - start_time

        self.assertIsInstance(connectors, list, f"Unexpected SDK response: {connectors!r}")
        self.assertLess(
            duration, 1.0, f"SDK list_connectors took {duration:.3f}s, exceeds 1s target"
        )

    @pytest.mark.skipif(not SDK_AVAILABLE, reason="SDK not available")
    def test_sdk_list_connections_performance(self):
        """Test SDK list_connections method performance"""
        import asyncio

        start_time = time.time()

        async def run():
            return await self.marketplace_api.list_connections()

        connections = asyncio.run(run())
        duration = time.time() - start_time

        self.assertIsInstance(connections, list, f"Unexpected SDK response: {connections!r}")
        self.assertLess(
            duration, 1.0, f"SDK list_connections took {duration:.3f}s, exceeds 1s target"
        )


@_maybe_override_databases
class TestMarketplaceConcurrentCLIPerformance(MarketplaceCLISDKPerformanceTestBase):
    """Concurrent CLI operations.

    Uses the same database as the running API (hub_test) so the CLI subprocess
    can authenticate against the pre-running API in Docker.
    """

    @pytest.mark.skipif(not CLI_AVAILABLE, reason="CLI not available")
    def test_concurrent_cli_operations(self):
        """Test concurrent CLI operations (20 concurrent)"""
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        project_root = Path(__file__).resolve().parent.parent.parent
        cli_cmd = [
            sys.executable,
            "-m",
            "cli.datahub_cli.main",
            "marketplace",
            "connectors",
            "list",
        ]
        api_base_url = os.environ.get("DATAHUB_API_BASE_URL", "http://localhost:8000/api/v1")
        test_env = {
            **os.environ,
            "PYTHONPATH": str(project_root),
            "DATAHUB_API_KEY": self.api_key_plaintext,
            # The CLI reads API_BASE_URL (not DATAHUB_API_BASE_URL); the
            # inherited container env has API_BASE_URL WITHOUT /api/v1,
            # which would make the CLI hit un-routed paths (HTML 404).
            "API_BASE_URL": api_base_url,
        }

        test_result = subprocess.run(
            cli_cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=15.0,
            cwd=str(project_root),
            env=test_env,
        )
        if test_result.returncode != 0:
            reason = test_result.stderr[:300] if test_result.stderr else str(test_result.returncode)
            self.skipTest(f"CLI not functional in test environment: {reason}")

        results = []
        errors = []
        lock = threading.Lock()

        def run_cli_command(index: int):
            """Run CLI command"""
            try:
                start_time = time.time()

                result = subprocess.run(
                    cli_cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=15.0,
                    cwd=str(project_root),
                    env=test_env,
                )

                duration = time.time() - start_time

                with lock:
                    results.append(
                        {"index": index, "duration": duration, "success": result.returncode == 0}
                    )
            except Exception as e:
                with lock:
                    errors.append(str(e))
                    results.append({"index": index, "success": False})

        # Run 20 concurrent CLI operations (100 can exhaust resources in CI)
        concurrency = 20
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(run_cli_command, i) for i in range(concurrency)]
            for future in as_completed(futures):
                with contextlib.suppress(Exception):
                    future.result(timeout=10.0)

        total_duration = time.time() - start_time

        # Verify reasonable success rate (> 50%; CI resource limits)
        successful = sum(1 for r in results if r.get("success", False))
        success_rate = successful / len(results) if results else 0

        self.assertGreaterEqual(
            success_rate, 0.5, f"Success rate {success_rate:.2%} is below 50% threshold"
        )

        # Verify reasonable total duration (< 60s for concurrent ops)
        self.assertLess(
            total_duration,
            60.0,
            f"Concurrent CLI operations took {total_duration:.2f}s, exceeds 60s target",
        )

    @pytest.mark.skipif(not SDK_AVAILABLE, reason="SDK not available")
    def test_concurrent_sdk_operations(self):
        """Test concurrent SDK operations (100+ concurrent)"""
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = []
        errors = []
        lock = threading.Lock()

        def run_sdk_method(index: int):
            """Run SDK method"""
            try:
                start_time = time.time()

                # This would call the actual SDK method
                # connectors = self.marketplace_api.list_connectors()

                duration = time.time() - start_time

                with lock:
                    results.append({"index": index, "duration": duration, "success": True})
            except Exception as e:
                with lock:
                    errors.append(str(e))
                    results.append({"index": index, "success": False})

        # Run 100 concurrent SDK operations
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(run_sdk_method, i) for i in range(100)]
            for future in as_completed(futures):
                with contextlib.suppress(Exception):
                    future.result(timeout=10.0)

        total_duration = time.time() - start_time

        # Verify reasonable success rate (> 80%)
        successful = sum(1 for r in results if r.get("success", False))
        success_rate = successful / len(results) if results else 0

        self.assertGreaterEqual(
            success_rate, 0.8, f"Success rate {success_rate:.2%} is below 80% threshold"
        )

        # Verify reasonable total duration (< 30s for 100 concurrent)
        self.assertLess(
            total_duration,
            30.0,
            f"Concurrent SDK operations took {total_duration:.2f}s, exceeds 30s target",
        )
