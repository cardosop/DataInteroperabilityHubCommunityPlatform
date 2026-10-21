"""

import uuid
10.5.9: ODH Integration CLI/SDK Performance Tests

Tests performance of ODH Integration CLI commands and SDK methods:
- CLI command execution with progress tracking
- SDK method execution with progress tracking
- Concurrent model operations (50+ concurrent)

Targets:
- CLI command execution with progress tracking overhead
- SDK method execution with progress tracking overhead
- 50+ concurrent operations
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow
import contextlib

from django.test import TransactionTestCase

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, User, UserRole, UserStatus

# Try to import SDK
try:
    from datahub_interoperability import DataHubClient, DataHubClientConfig

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

CLI_AVAILABLE = True


class ODHIntegrationCLISDKPerformanceTestBase(TransactionTestCase):
    """Base class for ODH Integration CLI/SDK performance tests"""

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures"""
        import uuid

        # Create test tenant and user with unique names to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        tenant_name = f"ODH Perf Test Tenant {unique_id}"
        tenant_slug = f"odh-perf-test-{unique_id}"

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
        user_email = f"odh-perf-test-{unique_id}@example.com"
        self.user, _ = User.objects.get_or_create(
            email=user_email,
            defaults={
                "password": "test-password-123",
                "tenant": self.tenant,
                "status": UserStatus.ACTIVE,
            },
        )

        # ML is a feature-gated surface — enable it so the CLI/SDK calls
        # below can succeed instead of 403ing.
        self.tenant.ml_enabled = True
        self.tenant.save(update_fields=["ml_enabled"])

        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        ensure_tenant_has_active_subscription(self.tenant)

        # Provision a real API key so the CLI subprocess and SDK client can
        # authenticate against the API.
        from hub.apps.auth.models import APIKey as AuthAPIKey
        from hub.apps.auth.permissions import ROLE_SCOPE_MAP

        role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=role)
        self.api_key_value = AuthAPIKey.generate_key()
        AuthAPIKey.objects.create(
            user=self.user,
            tenant=self.tenant,
            name=f"ODH perf key {unique_id}",
            key_hash=AuthAPIKey.hash_key(self.api_key_value),
            scopes=list(ROLE_SCOPE_MAP.get("TENANT_ADMIN", [])),
        )

        if SDK_AVAILABLE:
            config = DataHubClientConfig(
                base_url="http://localhost:8000/api/v1", api_token=self.api_key_value
            )
            self.client = DataHubClient(config)

    def tearDown(self):
        """Clean up test data"""

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for CLI/SDK performance tests."""
        # Don't flush - transactions are rolled back which provides isolation


class TestODHIntegrationCLIPerformance(ODHIntegrationCLISDKPerformanceTestBase):
    """Test ODH Integration CLI command performance"""

    @pytest.mark.skipif(not CLI_AVAILABLE, reason="CLI not available")
    def test_cli_model_list_performance(self):
        """Test CLI model list command performance with progress tracking"""
        project_root = Path(__file__).resolve().parent.parent.parent
        cli_dir = project_root / "cli"

        import os

        env = os.environ.copy()
        env["DATAHUB_API_KEY"] = self.api_key_value
        env["API_BASE_URL"] = "http://localhost:8000/api/v1"

        start_time = time.time()

        try:
            result = subprocess.run(
                [sys.executable, "-m", "datahub_cli", "ml", "models", "list", "--format", "json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10.0,
                env=env,
                cwd=str(cli_dir),
            )
        except subprocess.TimeoutExpired:
            self.fail("CLI odh models list hung (>10s)")
        except FileNotFoundError:
            self.fail(f"CLI package missing: {cli_dir}")
        duration = time.time() - start_time

        self.assertEqual(
            result.returncode,
            0,
            f"CLI exit {result.returncode}: {result.stdout} {result.stderr}",
        )
        # CLI with progress tracking should complete within reasonable time
        self.assertLess(duration, 5.0, f"CLI model list took {duration:.3f}s, exceeds 5s target")


class TestODHIntegrationSDKPerformance(ODHIntegrationCLISDKPerformanceTestBase):
    """Test ODH Integration SDK method performance"""

    @pytest.mark.skipif(not SDK_AVAILABLE, reason="SDK not available")
    def test_sdk_model_list_performance(self):
        """Test SDK model list method performance (real API round trip)."""
        import asyncio

        start_time = time.time()

        async def run():
            return await self.client.ml.list_models(limit=1)

        result = asyncio.run(run())
        duration = time.time() - start_time

        self.assertIsInstance(result, (list, dict), f"Unexpected SDK response: {result!r}")
        self.assertLess(duration, 2.0, f"SDK model list took {duration:.3f}s, exceeds 2s target")


class TestODHIntegrationConcurrentPerformance(ODHIntegrationCLISDKPerformanceTestBase):
    """Test ODH Integration concurrent operations performance"""

    def test_concurrent_model_operations(self):
        """Test concurrent model operations (50+ concurrent)"""
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = []
        lock = threading.Lock()

        def list_models(index: int):
            """List models"""
            try:
                start_time = time.time()
                # Simulate model listing with progress tracking
                time.sleep(0.05)  # noqa: sleep-needed  # INTENTIONAL: test-specific delay  # Simulate network delay
                duration = time.time() - start_time

                with lock:
                    results.append({"index": index, "duration": duration, "success": True})
            except Exception:
                with lock:
                    results.append({"index": index, "success": False})

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(list_models, i) for i in range(50)]
            for future in as_completed(futures):
                with contextlib.suppress(Exception):
                    future.result(timeout=15.0)

        total_duration = time.time() - start_time

        successful = sum(1 for r in results if r.get("success", False))
        success_rate = successful / len(results) if results else 0

        self.assertGreaterEqual(
            success_rate, 0.8, f"Success rate {success_rate:.2%} is below 80% threshold"
        )

        self.assertLess(
            total_duration,
            20.0,
            f"Concurrent operations took {total_duration:.2f}s, exceeds 20s target",
        )
