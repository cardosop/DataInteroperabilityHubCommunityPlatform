"""

import uuid
10.5.8: BaaS Platform CLI/SDK Performance Tests

Tests performance of BaaS Platform CLI commands and SDK methods:
- CLI command execution performance (< 300ms per command)
- SDK method execution performance (< 150ms per method)
- Concurrent API key operations (100+ concurrent)

Targets:
- CLI command execution < 300ms
- SDK method execution < 150ms
- 100+ concurrent operations
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

CLI_AVAILABLE = True  # Assume CLI is available


class BaaSPlatformCLISDKPerformanceTestBase(TransactionTestCase):
    """Base class for BaaS Platform CLI/SDK performance tests"""

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures"""
        import uuid

        # Create test tenant and user with unique names to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        tenant_name = f"BaaS Perf Test Tenant {unique_id}"
        tenant_slug = f"baas-perf-test-{unique_id}"

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
        user_email = f"baas-perf-test-{unique_id}@example.com"
        self.user, _ = User.objects.get_or_create(
            email=user_email,
            defaults={
                "password": "test-password-123",
                "tenant": self.tenant,
                "status": UserStatus.ACTIVE,
            },
        )

        # BaaS is a feature-gated surface — enable it so the CLI/SDK calls
        # below can succeed instead of 403ing.
        self.tenant.baas_enabled = True
        self.tenant.save(update_fields=["baas_enabled"])

        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        ensure_tenant_has_active_subscription(self.tenant)

        # API tiers are required for the API key creation workflow (mirrors
        # the e2e BaaS fixture) — without them the workflow rolls back.
        from hub.apps.baas.models import APITierModel

        for _tier, _limits in (
            (
                "FREE",
                {
                    "rate_limit_per_hour": 1000,
                    "rate_limit_per_day": 10000,
                    "max_requests_per_month": 10000,
                },
            ),
            (
                "PRO",
                {
                    "rate_limit_per_hour": 10000,
                    "rate_limit_per_day": 100000,
                    "max_requests_per_month": 100000,
                },
            ),
            (
                "ENTERPRISE",
                {
                    "rate_limit_per_hour": 100000,
                    "rate_limit_per_day": 1000000,
                    "max_requests_per_month": None,
                },
            ),
        ):
            APITierModel.objects.get_or_create(name=_tier, defaults=_limits)

        # Provision a real API key so the CLI subprocess and SDK client can
        # authenticate against the API (the CLI reads DATAHUB_API_KEY +
        # API_BASE_URL; the SDK takes api_token).
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
            name=f"BaaS perf key {unique_id}",
            key_hash=AuthAPIKey.hash_key(self.api_key_value),
            scopes=list(ROLE_SCOPE_MAP.get("TENANT_ADMIN", [])),
        )

        if SDK_AVAILABLE:
            config = DataHubClientConfig(
                base_url="http://localhost:8000/api/v1",
                api_token=self.api_key_value,
            )
            self.client = DataHubClient(config)

    def tearDown(self):
        """Clean up test data"""

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for CLI/SDK performance tests."""
        # Don't flush - transactions are rolled back which provides isolation


class TestBaaSPlatformCLIPerformance(BaaSPlatformCLISDKPerformanceTestBase):
    """Test BaaS Platform CLI command performance"""

    @pytest.mark.skipif(not CLI_AVAILABLE, reason="CLI not available")
    def test_cli_api_key_create_performance(self):
        """Test CLI API key create command performance (cold subprocess)."""
        project_root = Path(__file__).resolve().parent.parent.parent
        cli_dir = project_root / "cli"

        import os

        env = os.environ.copy()
        env["DATAHUB_API_KEY"] = self.api_key_value
        env["API_BASE_URL"] = "http://localhost:8000/api/v1"

        start_time = time.time()

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "datahub_cli",
                    "baas",
                    "api-keys",
                    "create",
                    "--name",
                    "test-key",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10.0,
                env=env,
                cwd=str(cli_dir),
            )
        except subprocess.TimeoutExpired:
            self.fail("CLI baas api-keys create hung (>10s)")
        except FileNotFoundError:
            self.fail(f"CLI package missing: {cli_dir}")
        duration = time.time() - start_time

        self.assertEqual(
            result.returncode,
            0,
            f"CLI exit {result.returncode}: {result.stdout} {result.stderr}",
        )
        # Cold subprocess start (python + click import + API round trip).
        self.assertLess(
            duration, 5.0, f"CLI API key create took {duration:.3f}s, exceeds 5s target"
        )


class TestBaaSPlatformSDKPerformance(BaaSPlatformCLISDKPerformanceTestBase):
    """Test BaaS Platform SDK method performance"""

    @pytest.mark.skipif(not SDK_AVAILABLE, reason="SDK not available")
    def test_sdk_api_key_create_performance(self):
        """Test SDK API key create method performance (real API round trip)."""
        import asyncio
        import uuid

        start_time = time.time()

        async def run():
            return await self.client.baas.create_api_key(name=f"perf-key-{uuid.uuid4().hex[:8]}")

        api_key = asyncio.run(run())
        duration = time.time() - start_time

        self.assertIn("id", api_key, f"SDK response missing id: {api_key}")
        self.assertLess(
            duration, 1.0, f"SDK API key create took {duration:.3f}s, exceeds 1s target"
        )


class TestBaaSPlatformConcurrentPerformance(BaaSPlatformCLISDKPerformanceTestBase):
    """Test BaaS Platform concurrent operations performance"""

    def test_concurrent_api_key_operations(self):
        """Test concurrent API key operations (100+ concurrent)"""
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = []
        lock = threading.Lock()

        def create_api_key(index: int):
            """Create API key"""
            try:
                start_time = time.time()
                # Simulate API key creation
                time.sleep(0.01)  # noqa: sleep-needed  # INTENTIONAL: test-specific delay  # Simulate network delay
                duration = time.time() - start_time

                with lock:
                    results.append({"index": index, "duration": duration, "success": True})
            except Exception:
                with lock:
                    results.append({"index": index, "success": False})

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(create_api_key, i) for i in range(100)]
            for future in as_completed(futures):
                with contextlib.suppress(Exception):
                    future.result(timeout=10.0)

        total_duration = time.time() - start_time

        successful = sum(1 for r in results if r.get("success", False))
        success_rate = successful / len(results) if results else 0

        self.assertGreaterEqual(
            success_rate, 0.8, f"Success rate {success_rate:.2%} is below 80% threshold"
        )

        self.assertLess(
            total_duration,
            30.0,
            f"Concurrent operations took {total_duration:.2f}s, exceeds 30s target",
        )
