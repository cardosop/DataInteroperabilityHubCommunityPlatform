"""
Shared SDK integration-test helpers.

Provides the canonical ``setup_authentication_for_sdk_tests()``,
``check_api_available()``, and config-creation functions used by all
mesh and integration test files.  Each test file imports these and
wires them into file-local fixtures with the tenant parameters it needs.

This module eliminates the ~100-line copy that was previously duplicated
across ``test_mesh_api.py``, ``test_mesh_compliance_api.py``,
``test_mesh_domains_api.py``, ``test_mesh_policies_api.py``,
``test_mesh_topology_api.py``, and ``test_integration.py``.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Callable, Dict, List, Optional

import pytest

from datahub_interoperability import DataHubClient, DataHubClientConfig


# ── Canonical helpers ────────────────────────────────────────────────

# Session-level cache so each tenant's API key is provisioned at most once
# per pytest session.  docker compose exec takes 5–15 s; without caching
# a function-scoped fixture re-provisions the key for every single test.
_api_key_cache: Dict[str, str] = {}


def check_api_available(api_base_url: str) -> bool:
    """Return True if the API at *api_base_url* responds (any status < 600)."""
    try:
        import requests
        response = requests.get(f"{api_base_url}/", timeout=2)
        return response.status_code < 600
    except Exception:
        return False


def setup_authentication_for_sdk_tests(
    api_base_url: str,
    *,
    tenant_slug: str,
    tenant_name: str,
    api_key_name: str,
    scopes: List[str],
    extra_tenant_setup: Optional[str] = None,
) -> Optional[str]:
    """Provision a test tenant, user, and API key via ``docker compose exec``.

    Args:
        api_base_url: API base URL (used only for initial reachability check).
        tenant_slug: Unique slug for the test tenant.
        tenant_name: Human-readable tenant name.
        api_key_name: Name for the API key record.
        scopes: OAuth2-style scopes for the API key.
        extra_tenant_setup: Optional Django ORM snippet that receives
            ``tenant`` and runs **after** ``tenant.save()`` (e.g. to set
            feature flags).

    Returns:
        The plaintext API key value, or ``None`` if provisioning failed.
    """
    cache_key = f"{tenant_slug}:{api_key_name}"

    # Method 1: Session-level cache — avoid re-provisioning the same
    # tenant's API key across multiple test files (docker compose exec
    # takes 5–15 s per call).
    if cache_key in _api_key_cache:
        return _api_key_cache[cache_key]

    # Method 2: Provision via Django shell in Docker Compose.
    tenant_bootstrap = ""
    if extra_tenant_setup:
        tenant_bootstrap = f"""
# Extra tenant setup (feature flags, etc.)
{extra_tenant_setup}
"""

    django_shell_script = f"""
from datetime import timedelta

from django.utils import timezone

from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey

tenant, _ = Tenant.objects.get_or_create(
    slug='{tenant_slug}',
    defaults={{'name': '{tenant_name}'}}
)
{tenant_bootstrap}
# Ensure the tenant has an active subscription so the billing
# middleware allows writes (POST/PUT/PATCH/DELETE).
_existing_sub = (
    Subscription.objects.filter(tenant=tenant, status=SubscriptionStatus.ACTIVE)
    .order_by("-created_at")
    .first()
)
if not _existing_sub:
    _required_limits = {{
        "max_assets": 9999, "max_contracts": 9999, "max_datasets": 9999,
        "max_ml_models": 9999, "max_ml_training_jobs": 9999,
        "max_ml_deployments": 9999,
    }}
    TenantPlan.objects.get_or_create(
        slug="free",
        defaults={{
            "name": "Free", "tier": PlanTier.FREE,
            "limits_json": _required_limits, "is_active": True,
        }},
    )
    _plan, _ = TenantPlan.objects.get_or_create(
        slug="sdk-test-plan",
        defaults={{
            "name": "SDK Test Plan", "tier": PlanTier.FREE,
            "limits_json": _required_limits, "is_active": True,
        }},
    )
    Subscription.objects.create(
        tenant=tenant, plan=_plan, status=SubscriptionStatus.ACTIVE,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=365),
    )
    tenant.plan = _plan
    tenant.kyc_status = KYCStatus.VERIFIED
    tenant.save(update_fields=["plan", "kyc_status", "updated_at"])

# Get or create TENANT_ADMIN role
admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={{'description': 'Tenant Administrator'}}
)

user, _ = User.objects.get_or_create(
    email='{tenant_slug}@example.com',
    defaults={{
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }}
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Assign TENANT_ADMIN role to user
UserRole.objects.get_or_create(user=user, role=admin_role)

# Delete existing API key if it exists
APIKey.objects.filter(user=user, name='{api_key_name}').delete()

# Create new API key with required scopes
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='{api_key_name}',
    key_hash=api_key_hash,
    scopes={scopes!r}
)
print(api_key_value)
"""

    # Method 2: Provision via Django shell in Docker Compose.
    # Try the test stack first (docker-compose.test.yml, service
    # api-service-test), then fall back to the main stack
    # (docker-compose.yml, service api-service).  Both use the same
    # Django management command.
    _COMPOSE_ATTEMPTS = [
        # (compose_args, manage_py_path)
        (
            ["docker", "compose", "-f", "docker-compose.test.yml",
             "exec", "-T", "api-service-test"],
            "hub/manage.py",   # WORKDIR=/app, manage.py in hub/
        ),
        (
            ["docker", "compose", "exec", "-T", "api-service"],
            "manage.py",       # WORKDIR=/app/hub
        ),
    ]

    for compose_cmd, manage_py_path in _COMPOSE_ATTEMPTS:
        try:
            result = subprocess.run(
                compose_cmd + ["python", manage_py_path, "shell"],
                input=django_shell_script,
                text=True,
                capture_output=True,
                timeout=30,
                cwd="/home/ph/Desktop/DataInteroperabilityHub",
            )
            if result.returncode == 0:
                output_lines = result.stdout.strip().split("\n")
                for line in reversed(output_lines):
                    line = line.strip()
                    if line and len(line) > 40:
                        cleaned = line.replace("-", "").replace("_", "")
                        if cleaned.isalnum() and " " not in line:
                            _api_key_cache[cache_key] = line
                            return line
        except Exception:
            pass

    # Method 3: Use environment variables (after docker compose exec
    # so that a properly tenant-scoped key from exec takes precedence
    # over a generic platform-admin JWT from conftest auto-provisioning).
    api_key = os.environ.get("TEST_API_KEY") or os.environ.get("DATAHUB_API_KEY")
    if api_key:
        return api_key

    # Method 4: Fall back to direct API login with pre-seeded test
    # credentials.  This works when the API is running but not via
    # docker-compose (e.g. standalone runserver on the test port).
    test_email = os.environ.get(
        "TEST_USER_EMAIL", f"{tenant_slug}@example.com"
    )
    test_password = os.environ.get("TEST_USER_PASSWORD", "TestPass123!")
    try:
        import requests as _requests
        login_resp = _requests.post(
            f"{api_base_url}/auth/login/",
            json={"email": test_email, "password": test_password},
            headers={"Content-Type": "application/json",
                      "Accept": "application/json"},
            timeout=10,
        )
        if login_resp.status_code == 200:
            login_data = login_resp.json()
            access_token = login_data.get("access_token")
            if access_token:
                _api_key_cache[cache_key] = access_token
                return access_token

            # If login succeeded but no access_token, try to create
            # an API key using the session cookie.
            cookies = login_resp.cookies
            if cookies:
                api_key_resp = _requests.post(
                    f"{api_base_url}/auth/api-keys/",
                    json={"name": api_key_name},
                    cookies=cookies,
                    headers={"Accept": "application/json"},
                    timeout=10,
                )
                if api_key_resp.status_code == 201:
                    key_data = api_key_resp.json()
                    api_key_value = key_data.get("api_key")
                    if api_key_value:
                        _api_key_cache[cache_key] = api_key_value
                        return api_key_value
    except Exception:
        pass

    return None


# ── Shared config factory (not a fixture — wire in file-local fixtures) ─

def create_real_api_config(
    api_base_url: str | None = None,
    *,
    tenant_slug: str,
    tenant_name: str,
    api_key_name: str,
    scopes: List[str],
    extra_tenant_setup: Optional[str] = None,
) -> DataHubClientConfig | None:
    """Return a :class:`DataHubClientConfig` or call ``pytest.skip``.

    This is the canonical factory used by all mesh/integration test files.
    Individual files create thin fixture wrappers that call this with their
    specific tenant parameters.
    """
    if api_base_url is None:
        api_base_url = os.environ.get(
            "API_BASE_URL", "http://localhost:8000/api/v1"
        )

    if not check_api_available(api_base_url):
        pytest.skip(
            "API service is not available. "
            "Ensure Docker Compose services are running."
        )

    api_key = setup_authentication_for_sdk_tests(
        api_base_url,
        tenant_slug=tenant_slug,
        tenant_name=tenant_name,
        api_key_name=api_key_name,
        scopes=scopes,
        extra_tenant_setup=extra_tenant_setup,
    )

    if not api_key:
        pytest.skip(
            "No API key available. Set TEST_API_KEY or DATAHUB_API_KEY "
            "environment variable, or ensure Docker Compose api-service is accessible."
        )

    return DataHubClientConfig(
        base_url=api_base_url,
        api_token=api_key,
        timeout=30.0,
        max_retries=3,
        user_agent="DataHub-SDK-Test",
        enable_logging=False,
    )


async def create_real_client(config: DataHubClientConfig):
    """Async context manager yielding a :class:`DataHubClient`."""
    import asyncio
    async with DataHubClient(config) as client:
        yield client
        # Small delay to avoid rate limiting between tests
        await asyncio.sleep(0.1)
