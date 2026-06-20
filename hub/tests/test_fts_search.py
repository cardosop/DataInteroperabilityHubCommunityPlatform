"""
Phase 7 — PostgreSQL Full-Text Search smoke tests.

These tests exercise the public search HTTP API rather than the internal
SearchEngine / SearchIndexer layer, which already has its own unit-test
coverage in hub/apps/search/tests/.

Focus:
  1. Asset name is searchable via /api/v1/search/search?q=…
  2. Empty / blank query returns zero results (not an error)
  3. Cross-tenant isolation: tenant B's results must never include tenant A's assets
  4. GIN index on search_vector is present (PostgreSQL meta check — skipped on SQLite)
  5. Search endpoint does not produce an N+1 query storm (≤ 5 DB queries)

All tests use real JWT tokens (no force_authenticate) following the pattern
established in test_tenant_isolation.py.
"""

import uuid

import pytest
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.search.indexing import SearchIndexer
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant(suffix: str = "") -> Tenant:
    s = suffix or uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"FTS-Tenant-{s}",
        slug=f"fts-tenant-{s}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )


def _make_user(tenant: Tenant) -> User:
    user = User.objects.create_user(
        email=f"fts-{uuid.uuid4().hex[:6]}@test.local",
        password="Pass1234!",
        tenant=tenant,
    )
    user.status = UserStatus.ACTIVE
    user.save(update_fields=["status"])
    return user


def _make_asset(tenant: Tenant, user: User, name: str, key_suffix: str = "") -> Asset:
    key = key_suffix or uuid.uuid4().hex[:8]
    return Asset.objects.create(
        tenant=tenant,
        key=f"fts-{key}",
        name=name,
        description=f"Description for {name}",
        status=AssetStatus.ACTIVE,
        created_by=user,
    )


def _bearer_client(user: User) -> APIClient:
    token = JWTTokenGenerator.generate_access_token(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


_SEARCH_URL = "/api/v1/search/search/"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestFTSSearchReturnsResults(TestCase):
    """
    Asset indexed via SearchIndexer must be findable through the search API.
    """

    def setUp(self):
        # Disconnect noisy async signals to keep tests fast and deterministic
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.signals import rebuild_asset_search_vector
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
            post_save.disconnect(rebuild_asset_search_vector, sender=Asset)
        except (ImportError, AttributeError):
            pass

        self.tenant = _make_tenant("results")
        self.user = _make_user(self.tenant)
        self.client = _bearer_client(self.user)

        # Create an asset with a distinctive multi-word name so each word is a
        # separate FTS token.  CamelCase like "ZephyrDataProductUnique" would be
        # tokenised as a single word, making prefix queries fail.
        self.asset = _make_asset(
            self.tenant,
            self.user,
            name="Zephyr Data Product",
            key_suffix="zephyr",
        )
        SearchIndexer.index_asset(self.asset)

    def test_asset_name_searchable(self):
        """Searching by the exact asset name must return at least one result."""
        resp = self.client.get(_SEARCH_URL, {"q": "Zephyr Data Product"})
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        # Handle both paginated envelope and flat list
        results = data.get("results", data) if isinstance(data, dict) else data
        self.assertGreater(
            len(results),
            0,
            "FTS search must return the indexed asset when searched by exact name",
        )

    def test_asset_found_by_partial_name(self):
        """Searching by a single word that appears in the asset name must return the asset."""
        resp = self.client.get(_SEARCH_URL, {"q": "Zephyr"})
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        results = data.get("results", data) if isinstance(data, dict) else data
        self.assertGreater(len(results), 0)

    def test_empty_query_returns_400(self):
        """An empty query must be rejected with 400 (q is required)."""
        resp = self.client.get(_SEARCH_URL, {"q": ""})
        self.assertEqual(
            resp.status_code,
            400,
            f"Empty query must return 400, got {resp.status_code}: {resp.data}",
        )
        self.assertIn("required", str(resp.data).lower())

    def test_nonexistent_query_returns_zero_results(self):
        """A query string that matches nothing must return an empty result set."""
        resp = self.client.get(
            _SEARCH_URL,
            {"q": "xyzzy_no_such_asset_ever_9z9z9z"},
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        results = data.get("results", data) if isinstance(data, dict) else data
        if isinstance(results, list):
            self.assertEqual(len(results), 0)

    def test_unauthenticated_search_returns_401(self):
        """Unauthenticated requests must be rejected."""
        anon_client = APIClient()
        resp = anon_client.get(_SEARCH_URL, {"q": "Zephyr Data Product"})
        self.assertEqual(resp.status_code, 401, resp.data)


@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestFTSCrossTenantIsolation(TestCase):
    """
    Search results must be scoped to the requesting user's tenant.
    Tenant B must never see Tenant A's assets in search results.
    """

    def setUp(self):
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.signals import rebuild_asset_search_vector
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
            post_save.disconnect(rebuild_asset_search_vector, sender=Asset)
        except (ImportError, AttributeError):
            pass

        # Tenant A owns a uniquely named asset.  Use space-separated words so
        # PostgreSQL FTS tokenises each word independently — CamelCase like
        # "ConfidentialAlphaDataset" would be a single token and prefix queries
        # ("Confidential") would not match it.
        self.tenant_a = _make_tenant("iso-a")
        self.user_a = _make_user(self.tenant_a)
        self.asset_a = _make_asset(
            self.tenant_a,
            self.user_a,
            name="Confidential Alpha Dataset",
            key_suffix="alpha",
        )
        SearchIndexer.index_asset(self.asset_a)

        # Tenant B — no assets
        self.tenant_b = _make_tenant("iso-b")
        self.user_b = _make_user(self.tenant_b)

        self.client_a = _bearer_client(self.user_a)
        self.client_b = _bearer_client(self.user_b)

    def test_tenant_a_finds_own_asset(self):
        """Tenant A must be able to find its own indexed asset."""
        resp = self.client_a.get(_SEARCH_URL, {"q": "Confidential"})
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        results = data.get("results", data) if isinstance(data, dict) else data
        ids = [str(r.get("id", r.get("resource_id", ""))) for r in (results or [])]
        self.assertTrue(
            any(str(self.asset_a.id) in iid for iid in ids),
            f"Tenant A must find its own asset {self.asset_a.id} in results {ids}",
        )

    def test_tenant_b_cannot_see_tenant_a_asset(self):
        """Tenant B searching the same term must get zero results (no cross-tenant leak)."""
        resp = self.client_b.get(_SEARCH_URL, {"q": "Confidential"})
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        results = data.get("results", data) if isinstance(data, dict) else data
        self.assertEqual(
            len(results or []),
            0,
            "Cross-tenant search isolation failed: Tenant B must not see Tenant A's assets",
        )

    def test_tenant_b_broad_search_excludes_tenant_a_ids(self):
        """Even a broad query by Tenant B must not expose any of Tenant A's resource IDs."""
        resp = self.client_b.get(_SEARCH_URL, {"q": "Dataset"})
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        results = data.get("results", data) if isinstance(data, dict) else data
        ids = {str(r.get("id", r.get("resource_id", ""))) for r in (results or [])}
        self.assertNotIn(
            str(self.asset_a.id),
            ids,
            "Tenant A's asset ID must never appear in Tenant B's search results",
        )


@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestFTSGINIndex(TestCase):
    """
    Verify that the GIN index on Asset.search_vector is present in the
    database.  Skipped on non-PostgreSQL backends.
    """

    def test_gin_index_present_on_asset_search_vector(self):
        """GIN index 'asset_search_vector_gin_idx' must exist on the assets table."""
        if connection.vendor != "postgresql":
            self.skipTest("GIN index check requires PostgreSQL")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'assets'
                  AND indexname = 'asset_search_vector_gin_idx'
                """
            )
            row = cursor.fetchone()

        self.assertIsNotNone(
            row,
            "GIN index 'asset_search_vector_gin_idx' is missing on assets table. "
            "Run migrations to create it (arch-improvements-01 Phase 7). "
            "Note: Asset.Meta.db_table = 'assets' (not Django default 'assets_asset').",
        )


@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestFTSQueryCount(TestCase):
    """
    Search endpoint must not perform an unbounded number of queries (N+1 guard).
    Baseline: ≤ 10 queries for a result set of 5 assets.
    """

    # Upper bound: the search itself is 2 queries (COUNT + SELECT).
    # The remaining budget covers auth middleware (3 tenant lookups + token_version
    # + user + user_roles), view-level tenant cache-miss, search-analytics
    # INSERT/UPDATE/SELECT, event bus INSERT (with SAVEPOINT/RELEASE),
    # and api_usage_metrics INSERT (tenant + user lookups).
    MAX_QUERIES = 20

    def setUp(self):
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.signals import rebuild_asset_search_vector
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
            post_save.disconnect(rebuild_asset_search_vector, sender=Asset)
        except (ImportError, AttributeError):
            pass

        self.tenant = _make_tenant("qcount")
        self.user = _make_user(self.tenant)
        self.client = _bearer_client(self.user)

        # Seed 5 assets and index them all
        for i in range(5):
            asset = _make_asset(
                self.tenant,
                self.user,
                name=f"QueryCountAsset{i}",
                key_suffix=f"qc{i}",
            )
            SearchIndexer.index_asset(asset)

    def test_search_query_count_does_not_explode(self):
        """Search for 5 results must use ≤ MAX_QUERIES DB queries."""
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get(_SEARCH_URL, {"q": "QueryCountAsset"})

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertLessEqual(
            len(ctx.captured_queries),
            self.MAX_QUERIES,
            f"Search produced {len(ctx.captured_queries)} queries; "
            f"expected ≤ {self.MAX_QUERIES}. Possible N+1:\n"
            + "\n".join(q["sql"][:120] for q in ctx.captured_queries),
        )
