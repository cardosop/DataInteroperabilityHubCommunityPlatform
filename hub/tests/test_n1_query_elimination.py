"""
Phase 12 — N+1 Query Elimination & Docker Hardening Tests
==========================================================

12.1  assertNumQueries(≤5) for 50-asset list endpoint
12.2  assertNumQueries(1) for 10 has_role() calls on same user
12.3  get_request_tenant() does NOT mutate request attributes
12.4  UserRole unique (user, tenant, role) constraint raises IntegrityError
12.5  No data-store port is bound to 0.0.0.0 in docker-compose.yml
"""

import os
import re
import uuid

import pytest
import yaml
from django.db import IntegrityError, connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_tenant(name=None):
    from hub.apps.tenants.models import Tenant
    slug = name or f"tenant-{uuid.uuid4().hex[:8]}"
    return Tenant.objects.create(name=slug, slug=slug)


def _create_user(tenant, email=None, is_platform_admin=False):
    from hub.apps.users.models import User
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    return User.objects.create_user(
        email=email,
        password="Test1234!",
        tenant=tenant,
        is_platform_admin=is_platform_admin,
    )


def _create_role(tenant, name="DATA_PROVIDER"):
    from hub.apps.users.models import Role
    role, _ = Role.objects.get_or_create(tenant=tenant, name=name)
    return role


def _assign_role(user, tenant, role):
    from hub.apps.users.models import UserRole
    ur, _ = UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)
    return ur


# ---------------------------------------------------------------------------
# 12.1 — Asset list endpoint: ≤ 5 queries for 50 assets
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAssetListN1Queries(TestCase):
    """
    A 50-asset list page must issue ≤ 5 queries regardless of how many
    contracts or datasets each asset has:
      1. Auth / user lookup (session / JWT middleware)
      2. Tenant resolution
      3. Asset SELECT with prefetch for contracts
      4. Prefetch for datasets
      5. (Optional) count query for pagination

    The select_related("tenant", "created_by") and
    prefetch_related("contracts", "datasets") added to get_queryset() in
    12.1 collapses what was previously O(N) queries into ≤ 5.
    """

    def setUp(self):
        from hub.apps.assets.models import Asset
        self.tenant = _create_tenant("asset-test-tenant")
        self.user = _create_user(self.tenant)
        self.user.status = "ACTIVE"
        self.user.save()

        for i in range(50):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-key-{i:03d}",
                name=f"Asset {i:03d}",
                created_by=self.user,
            )

    def test_asset_list_queryset_max_5_queries(self):
        """
        get_queryset() with select_related + prefetch_related must resolve
        a 50-asset result-set in ≤ 5 DB round-trips.
        """
        from rest_framework.request import Request as DRFRequest

        from hub.apps.assets.views import AssetViewSet

        factory = RequestFactory()
        raw_request = factory.get("/api/v1/assets/")
        raw_request.tenant_id = str(self.tenant.id)
        drf_request = DRFRequest(raw_request)
        drf_request.user = self.user  # DRF Request.user setter bypasses auth

        viewset = AssetViewSet()
        viewset.request = drf_request
        viewset.kwargs = {}
        viewset.action = "list"
        viewset.format_kwarg = None

        with CaptureQueriesContext(connection) as ctx:
            qs = viewset.get_queryset()
            # Force evaluation + prefetch
            assets = list(qs)
            # Simulate serializer accessing contracts and datasets
            for asset in assets:
                list(asset.contracts.all())
                list(asset.datasets.all())

        self.assertEqual(len(assets), 50, f"Expected 50 assets, got {len(assets)}")
        self.assertLessEqual(
            len(ctx), 5,
            f"Expected ≤ 5 queries for 50-asset list page, "
            f"got {len(ctx)}:\n"
            + "\n".join(q["sql"] for q in ctx),
        )


# ---------------------------------------------------------------------------
# 12.2 — has_role() cache: 10 calls → exactly 1 DB query
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHasRoleInstanceCache(TestCase):
    """
    After the first has_role() call for a given frozenset of role names,
    subsequent calls must return from the in-process cache without hitting
    the database again.  10 calls on the same user/tenant/role combination
    must issue exactly 1 DB query.
    """

    def setUp(self):
        self.tenant = _create_tenant("role-cache-tenant")
        self.user = _create_user(self.tenant)
        self.user.status = "ACTIVE"
        self.user.save()
        role = _create_role(self.tenant, "DATA_PROVIDER")
        _assign_role(self.user, self.tenant, role)

        # Clear any cached state left from setUp queries
        self.user.__dict__.pop("_role_cache", None)
        # Detach prefetched user_roles so the first call re-queries
        self.user.__dict__.pop("user_roles", None)

    def test_10_has_role_calls_issue_1_query(self):
        with CaptureQueriesContext(connection) as ctx:
            results = [self.user.has_role("DATA_PROVIDER") for _ in range(10)]

        assert all(results), "has_role('DATA_PROVIDER') must be True for all 10 calls"
        assert len(ctx) == 1, (
            f"Expected exactly 1 DB query for 10 has_role() calls, "
            f"got {len(ctx)}:\n"
            + "\n".join(q["sql"] for q in ctx)
        )

    def test_cache_invalidated_after_role_deletion(self):
        """Deleting a UserRole must clear the cache so the next call re-queries."""
        from hub.apps.users.models import UserRole

        # Prime the cache
        assert self.user.has_role("DATA_PROVIDER") is True
        assert "_role_cache" in self.user.__dict__

        # Delete the UserRole — signal should clear the cache
        UserRole.objects.filter(user=self.user).delete()
        assert "_role_cache" not in self.user.__dict__, (
            "Signal handler must clear _role_cache on UserRole deletion"
        )

        # Next call should query DB and return False
        assert self.user.has_role("DATA_PROVIDER") is False


# ---------------------------------------------------------------------------
# 12.3 — get_request_tenant() must NOT mutate request attributes
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGetRequestTenantNoMutation(TestCase):
    """
    get_request_tenant() is a read-only helper.  It must not set
    request.tenant_id or request.tenant as a side-effect; those are
    exclusively the responsibility of TenantScopingMiddleware.
    """

    def test_get_request_tenant_does_not_set_tenant_id_on_request(self):
        from hub.apps.tenants.request_tenant import get_request_tenant

        tenant = _create_tenant("no-mutation-tenant")
        user = _create_user(tenant)

        factory = RequestFactory()
        request = factory.get("/")
        request.user = user
        # Ensure request does NOT have tenant_id/tenant pre-set
        assert not hasattr(request, "tenant_id")
        assert not hasattr(request, "tenant")

        tenant_id_str, tenant_obj = get_request_tenant(request)

        assert tenant_id_str == str(tenant.id)
        assert tenant_obj == tenant

        # THE FIX: function must NOT have mutated request
        assert not hasattr(request, "tenant_id"), (
            "get_request_tenant() must not set request.tenant_id"
        )
        assert not hasattr(request, "tenant"), (
            "get_request_tenant() must not set request.tenant"
        )

    def test_get_request_tenant_returns_none_for_anonymous(self):
        from django.contrib.auth.models import AnonymousUser
        from hub.apps.tenants.request_tenant import get_request_tenant

        factory = RequestFactory()
        request = factory.get("/")
        request.user = AnonymousUser()

        tenant_id_str, tenant_obj = get_request_tenant(request)

        assert tenant_id_str is None
        assert tenant_obj is None
        # Still no mutation
        assert not hasattr(request, "tenant_id")
        assert not hasattr(request, "tenant")


# ---------------------------------------------------------------------------
# 12.4 — UserRole (user, tenant, role) unique constraint
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUserRoleUniqueConstraint(TestCase):
    """
    The DB-level unique constraint on (user, tenant, role) must prevent
    duplicate role assignments and raise IntegrityError on a second INSERT.
    Application code must use get_or_create to stay idempotent.
    """

    def setUp(self):
        self.tenant = _create_tenant("constraint-tenant")
        self.user = _create_user(self.tenant)
        self.role = _create_role(self.tenant, "TENANT_ADMIN")

    def test_duplicate_insert_raises_integrity_error(self):
        from hub.apps.users.models import UserRole

        UserRole.objects.create(user=self.user, tenant=self.tenant, role=self.role)

        with pytest.raises(IntegrityError):
            UserRole.objects.create(
                user=self.user, tenant=self.tenant, role=self.role
            )

    def test_get_or_create_is_idempotent(self):
        from hub.apps.users.models import UserRole

        ur1, created1 = UserRole.objects.get_or_create(
            user=self.user, tenant=self.tenant, role=self.role
        )
        ur2, created2 = UserRole.objects.get_or_create(
            user=self.user, tenant=self.tenant, role=self.role
        )

        assert created1 is True
        assert created2 is False
        assert ur1.pk == ur2.pk
        assert UserRole.objects.filter(user=self.user, role=self.role).count() == 1


# ---------------------------------------------------------------------------
# 12.5 — docker-compose.yml: no data-store port bound to 0.0.0.0
# ---------------------------------------------------------------------------

class TestDockerComposePortBinding:
    """
    All data-store port mappings in docker-compose.yml must be bound to
    127.0.0.1 so they are not reachable from the host network in development.

    A port mapping is compliant if it matches one of:
      - "127.0.0.1:HOST:CONTAINER"
      - "${VAR:-default}:CONTAINER"   (no host-bind → Docker default = 0.0.0.0 → FAIL)
      - Any mapping without an explicit host that exposes a data-store port → FAIL
    """

    # Data-store services whose host ports must be loopback-only
    DATA_STORE_SERVICES = {
        "postgres",
        "postgres-baas",
        "redis-cache",
        "redis-queue",
        "redis-events",
        "redis-channels",
        "redis-baas",
        "minio",
        "fuseki",
    }

    @pytest.fixture(scope="class")
    def compose(self):
        repo_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        compose_path = os.path.join(repo_root, "docker-compose.yml")
        with open(compose_path) as f:
            return yaml.safe_load(f)

    def test_data_store_ports_bound_to_loopback(self, compose):
        violations = []
        services = compose.get("services", {})

        for svc_name in self.DATA_STORE_SERVICES:
            svc = services.get(svc_name)
            if svc is None:
                continue
            for port_entry in svc.get("ports", []):
                port_str = str(port_entry)
                # Parse: could be "127.0.0.1:X:Y", "X:Y", "${VAR:-default}:Y"
                if not port_str.startswith("127.0.0.1:"):
                    violations.append(
                        f"Service '{svc_name}' port '{port_str}' is not bound "
                        f"to 127.0.0.1 — it would be accessible on 0.0.0.0"
                    )

        assert not violations, (
            "The following data-store ports are NOT loopback-bound:\n"
            + "\n".join(f"  • {v}" for v in violations)
        )

    def test_required_passwords_use_error_syntax(self, compose):
        """
        Critical secret env vars must use ${VAR:?message} (error if unset),
        not ${VAR:-default} (silent fallback).
        """
        services = compose.get("services", {})
        secret_vars = [
            "POSTGRES_PASSWORD",
            "MINIO_ROOT_PASSWORD",
            "FUSEKI_ADMIN_PASSWORD",
        ]
        violations = []

        for svc_name, svc in services.items():
            env = svc.get("environment") or {}
            # environment can be a list of "KEY=VALUE" or a dict
            if isinstance(env, list):
                env = dict(
                    (e.split("=", 1)[0], e.split("=", 1)[1])
                    for e in env
                    if "=" in e
                )
            for var in secret_vars:
                val = env.get(var, "")
                # Check for silent-fallback pattern: ${VAR:-...}
                if re.search(r"\$\{" + re.escape(var) + r":-", str(val)):
                    violations.append(
                        f"Service '{svc_name}': {var} uses silent fallback "
                        f"(:-) — change to (:?) to fail fast on unset secrets"
                    )

        assert not violations, "\n".join(violations)

    def test_postgres_healthcheck_start_period_le_60s(self, compose):
        """PostgreSQL start_period must be ≤ 60s (was incorrectly 1800s)."""
        postgres = compose["services"]["postgres"]
        start_period = postgres["healthcheck"]["start_period"]
        # Accept "60s", "30s", etc. — reject "1800s"
        seconds = int(re.sub(r"[^0-9]", "", str(start_period)))
        assert seconds <= 60, (
            f"postgres healthcheck start_period is {start_period}; "
            f"must be ≤ 60s to detect crashes promptly"
        )
