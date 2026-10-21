"""
W4.5 — Caches (R2-I2): contracts-list page≥2 double-slice, lineage-edit
cache invalidation, on_commit invalidation for ``update_contract``,
lineage key cleanup, and ``.update()`` transitions funneled through
invalidation.

Pinned contracts:

1.  **Page ≥ 2 (NAMED EVIDENCE)** — the list endpoint's cached branch
    must return the CACHED page as-is: pre-fix it re-sliced the
    already-paginated cached list with ``[start:end]``, so the second
    fetch of page ≥ 2 returned an empty page (the double-slice bug).
2.  **on_commit invalidation** — ``update_contract`` must defer its
    post-save cache cascade until AFTER the transaction commits.
    Pre-fix the cascade ran pre-commit, so a concurrent reader could
    re-cache the old row between the writer's invalidation and its
    commit, leaving the cache permanently stale (until TTL).
3.  **Lineage edit (NAMED EVIDENCE)** — a lineage PATCH must invalidate
    the contract's lineage caches; pre-fix the lineage GET kept
    serving the pre-patch snapshot from cache.
4.  **Scoped-key cleanup** — ``invalidate_lineage_cache`` must evict
    the model- and field-scoped keys too; pre-fix those keys were
    never deletable (the ``pass`` branch) and lingered until TTL.
5.  **Sync funnel** — ``LineageEdge`` ``.update()`` transitions made by
    the post-save lineage sync must invalidate the affected contract's
    lineage cache when the edge set actually changed.

No mocks — real Postgres rows, real DRF requests, real cache reads and
writes. The scoped-key cleanup pin runs against a real Redis configured
exactly like production (django_redis + KEY_PREFIX), the same convention
as ``test_caching_behavior_validation.py``.
"""

from __future__ import annotations

import os
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant(slug_prefix: str = "w45") -> Tenant:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{slug_prefix}-{suffix}",
        slug=f"{slug_prefix}-{suffix}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _make_user(tenant: Tenant) -> User:
    suffix = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"u-{suffix}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _grant_tenant_admin(user, tenant):
    from hub.apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


def _make_contract(
    tenant: Tenant,
    *,
    name: str,
    field_name: str = "id",
    lineage: list | None = None,
):
    """A structurally-sound Contract (same shape as the lineage-edit
    endpoint suite's fixture), optionally carrying lineage entries."""
    from hub.apps.contracts.models import (
        Contract,
        ContractStatus,
        OriginalFormat,
        OriginalSpecType,
    )

    asset = Asset.objects.create(
        tenant=tenant,
        key=f"asset-{uuid.uuid4().hex[:6]}",
        name=name,
        status=AssetStatus.DRAFT,
    )
    hub_contract = {
        "info": {"name": name},
        "models": [
            {
                "name": "default",
                "fields": [
                    {"name": field_name, "data_type": "string", "nullable": False},
                ],
            }
        ],
    }
    if lineage is not None:
        hub_contract["lineage"] = lineage
    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.1.0",
        original_format=OriginalFormat.JSON,
        original_raw="{}",
        hub_contract_json=hub_contract,
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status=ContractStatus.ACTIVE,
    )


def _client(user) -> APIClient:
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _etag(contract) -> str:
    from hub.apps.contracts.views_crud import _contract_etag

    return _contract_etag(contract)


def _redis_caches_override():
    """CACHES override: the production-shaped django_redis backend with
    KEY_PREFIX, pointed at the real REDIS_CACHE_URL instance."""
    from django.conf import settings

    redis_url = getattr(settings, "REDIS_CACHE_URL", "") or os.environ.get(
        "REDIS_CACHE_URL", ""
    )
    if not redis_url:
        return None
    try:
        from django_redis.cache import RedisCache  # type: ignore[import-untyped]

        probe = RedisCache(redis_url, {"KEY_PREFIX": "hub"})
        probe.set("w45-probe", 1, timeout=10)
        probe.delete("w45-probe")
    except Exception:  # noqa: BLE001 - the probe's contract IS the exception
        return None
    return override_settings(
        CACHES={
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": redis_url,
                "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
                "KEY_PREFIX": "hub",
                "TIMEOUT": 300,
            }
        }
    )


# ---------------------------------------------------------------------------
# 1. Page ≥ 2 (named evidence)
# ---------------------------------------------------------------------------


class TestContractsListPage2Cache(TestCase):
    def test_page_2_cached_results_non_empty(self):
        """The second fetch of page 2 must return the SAME non-empty page.

        Pre-fix, the cached branch re-sliced the already-paginated
        cached page with ``[start_idx:end_idx]`` — page 1 looked right
        by accident (slice [0:size] on a size-length list), page ≥ 2
        came back EMPTY on every cache hit.
        """
        tenant = _make_tenant("p2")
        user = _make_user(tenant)
        names = ["alpha", "bravo", "charlie", "delta"]
        for name in names:
            _make_contract(tenant, name=name)
        client = _client(user)

        url = "/api/v1/contracts/?page_size=2"

        # Page 1: warm the cache.
        r1 = client.get(f"{url}&page=1")
        assert r1.status_code == 200, r1.content
        assert len(r1.json()["results"]) == 2

        # Page 1 again: cached path.
        r1b = client.get(f"{url}&page=1")
        assert r1b.status_code == 200
        assert r1b.json().get("_cached") is True
        assert len(r1b.json()["results"]) == 2

        # Page 2 first fetch: uncached, real rows.
        r2 = client.get(f"{url}&page=2")
        assert r2.status_code == 200, r2.content
        first_ids = {row["id"] for row in r2.json()["results"]}
        assert len(first_ids) == 2, "page 2 must carry the remaining contracts"
        assert r2.json().get("has_next") is False

        # Page 2 second fetch: cached path — MUST NOT re-slice to empty.
        r2b = client.get(f"{url}&page=2")
        assert r2b.status_code == 200
        body = r2b.json()
        assert body.get("_cached") is True
        cached_ids = {row["id"] for row in body["results"]}
        assert cached_ids == first_ids, (
            "cached page 2 must return the same non-empty page as the "
            "uncached fetch (pre-fix: the double-slice returned [])"
        )
        assert body.get("has_next") is False
        assert body.get("has_previous") is True


# ---------------------------------------------------------------------------
# 2. on_commit invalidation for update_contract
# ---------------------------------------------------------------------------


class TestUpdateContractOnCommitInvalidation(TransactionTestCase):
    """TransactionTestCase: the deferral pins need REAL commits — the
    ``on_commit`` hook only drains when the atomic block actually
    commits (a rolled-back TestCase atomic never does)."""

    def test_caches_survive_until_commit(self):
        """The post-save cache cascade must run AFTER commit.

        Pre-fix, ``update_contract`` invalidated pre-commit: a
        concurrent reader that missed after the invalidation re-cached
        the OLD row, and the cache stayed stale past the commit.
        """
        from hub.apps.contracts.caching import (
            cache_contract,
            cache_lineage,
            get_cached_contract,
            get_cached_lineage,
        )
        from hub.apps.contracts.services.contract_service import ContractService

        tenant = _make_tenant("oc")
        user = _make_user(tenant)
        contract = _make_contract(tenant, name="oncommit")

        # Warm both caches with the current state.
        cache_contract(str(contract.id), {"id": str(contract.id), "status": "ACTIVE"})
        cache_lineage(str(contract.id), {"contracts": [], "entries": []})
        assert get_cached_contract(str(contract.id)) is not None
        assert get_cached_lineage(str(contract.id)) is not None

        service = ContractService(tenant_id=str(tenant.id), user_id=str(user.id))
        with transaction.atomic():
            service.update_contract(
                contract_id=str(contract.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                status="RETIRED",
            )
            # Inside the still-open transaction the invalidation MUST be
            # deferred — the cascade's own docstring requires the row to
            # be committed first.
            assert (
                get_cached_contract(str(contract.id)) is not None
            ), "contract cache must survive until commit (deferred cascade)"
            assert (
                get_cached_lineage(str(contract.id)) is not None
            ), "lineage cache must survive until commit (deferred cascade)"

        # After the commit the deferred cascade fires and both caches go.
        assert get_cached_contract(str(contract.id)) is None
        assert get_cached_lineage(str(contract.id)) is None

    def test_update_contract_still_invalidates_without_outer_atomic(self):
        """Contract guard: in the normal request flow (no outer atomic)
        the invalidation still fires — the deferral must not lose the
        invalidation entirely."""
        from hub.apps.contracts.caching import (
            cache_contract,
            get_cached_contract,
        )
        from hub.apps.contracts.services.contract_service import ContractService

        tenant = _make_tenant("oc2")
        user = _make_user(tenant)
        contract = _make_contract(tenant, name="oncommit2")
        cache_contract(str(contract.id), {"id": str(contract.id), "status": "ACTIVE"})

        service = ContractService(tenant_id=str(tenant.id), user_id=str(user.id))
        service.update_contract(
            contract_id=str(contract.id),
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            status="RETIRED",
        )

        assert get_cached_contract(str(contract.id)) is None


# ---------------------------------------------------------------------------
# 3. Lineage edit invalidation (named evidence)
# ---------------------------------------------------------------------------


class TestLineageEditInvalidation(TransactionTestCase):
    """TransactionTestCase: the patch's invalidation is registered
    ``on_commit`` — real commits are required for the hook to drain."""

    def test_lineage_patch_refreshes_cached_lineage(self):
        """PATCH lineage → the next lineage GET reflects the new edges.

        Pre-fix, ``apply_lineage_patch`` mutated the edges and the
        reserialised payload but never invalidated the lineage caches —
        the GET kept serving the pre-patch snapshot.
        """
        from hub.apps.contracts.caching import get_cached_lineage

        tenant = _make_tenant("le")
        user = _make_user(tenant)
        _grant_tenant_admin(user, tenant)
        c_src = _make_contract(tenant, name="orders", field_name="customer_id")
        c_tgt = _make_contract(tenant, name="customers", field_name="customer_id")
        client = _client(user)

        # Fill the contract-level lineage cache (pre-patch state).
        r_get1 = client.get(f"/api/v1/contracts/{c_tgt.id}/lineage/contracts/")
        assert r_get1.status_code == 200, r_get1.content
        assert r_get1.json()["entries"] == []
        assert (
            get_cached_lineage(str(c_tgt.id)) is not None
        ), "the GET must have cached the pre-patch lineage"

        # Patch: add one edge.
        body = {
            "edges": [
                {
                    "source_contract": str(c_src.id),
                    "source_model": "default",
                    "source_field": "customer_id",
                    "target_contract": str(c_tgt.id),
                    "target_model": "default",
                    "target_field": "customer_id",
                    "edge_type": "reference",
                },
            ],
        }
        r_patch = client.patch(
            f"/api/v1/contracts/{c_tgt.id}/lineage/",
            data=body,
            format="json",
            HTTP_IF_MATCH=_etag(c_tgt),
        )
        assert r_patch.status_code == 200, r_patch.content
        assert r_patch.json()["added"] == 1

        # The cached pre-patch snapshot must be gone.
        assert (
            get_cached_lineage(str(c_tgt.id)) is None
        ), "lineage edit must invalidate the contract's lineage cache"

        # The next GET reflects the patch.
        r_get2 = client.get(f"/api/v1/contracts/{c_tgt.id}/lineage/contracts/")
        assert r_get2.status_code == 200
        entries = r_get2.json()["entries"]
        assert len(entries) == 1, f"expected 1 lineage entry post-patch, got {entries}"


# ---------------------------------------------------------------------------
# 4. Scoped-key cleanup (no-TTL/never-invalidated keys)
# ---------------------------------------------------------------------------


class TestLineageScopedKeyCleanup(TestCase):
    def test_invalidate_lineage_cache_evicts_model_and_field_scoped_keys(self):
        """``invalidate_lineage_cache`` must evict EVERY lineage key for
        the contract — the contract-level key AND the model/field-scoped
        keys written by the field-level lineage reads.

        Pre-fix, the scoped keys were never deletable (the invalidation
        body was literally ``pass`` with a "maintain a key registry"
        TODO) — they lingered until TTL and served stale field-level
        lineage after every edit.
        """
        from hub.apps.contracts.caching import (
            cache_lineage,
            get_cached_lineage,
            invalidate_lineage_cache,
        )

        override_ctx = _redis_caches_override()
        if override_ctx is None:
            self.skipTest("Redis at REDIS_CACHE_URL unreachable")
        with override_ctx:
            tenant = _make_tenant("sk")
            contract = _make_contract(tenant, name="scoped")

            cache_lineage(str(contract.id), {"contracts": [], "entries": []})
            cache_lineage(
                str(contract.id),
                {"model": "default", "entries": []},
                model_name="default",
            )
            cache_lineage(
                str(contract.id),
                {"field": "id", "entries": []},
                model_name="default",
                field_name="id",
            )
            assert get_cached_lineage(str(contract.id)) is not None
            assert (
                get_cached_lineage(str(contract.id), model_name="default") is not None
            )
            assert (
                get_cached_lineage(
                    str(contract.id), model_name="default", field_name="id"
                )
                is not None
            )

            invalidate_lineage_cache(str(contract.id))

            assert get_cached_lineage(str(contract.id)) is None
            assert (
                get_cached_lineage(str(contract.id), model_name="default") is None
            ), "model-scoped lineage key must be evicted (pre-fix: leaked until TTL)"
            assert (
                get_cached_lineage(
                    str(contract.id), model_name="default", field_name="id"
                )
                is None
            ), "field-scoped lineage key must be evicted (pre-fix: leaked until TTL)"


# ---------------------------------------------------------------------------
# 5. .update() transitions funneled through invalidation
# ---------------------------------------------------------------------------


class TestSyncTransitionInvalidation(TransactionTestCase):
    """TransactionTestCase: the post-save lineage sync runs on_commit —
    real commits are required for the hook to drain."""

    def test_lineage_sync_edge_updates_invalidate_lineage_cache(self):
        """The post-save lineage sync closes/opens ``LineageEdge`` rows
        via queryset ``.update()`` — when the edge set actually changes,
        the affected contract's lineage cache must be invalidated.

        Pre-fix the sync's transitions bypassed every cache path, so a
        save that changed the payload lineage left the lineage cache
        serving the old edges.
        """
        from hub.apps.contracts.caching import (
            cache_lineage,
            get_cached_lineage,
        )
        from hub.apps.contracts.models import LineageEdge

        tenant = _make_tenant("sync")
        user = _make_user(tenant)
        c_src = _make_contract(tenant, name="orders", field_name="cid")
        contract = _make_contract(tenant, name="cust", field_name="cid")
        assert user.id  # keep the fixture user alive

        # Warm the lineage cache with the current (edge-less) state.
        cache_lineage(str(contract.id), {"contracts": [], "entries": []})
        assert get_cached_lineage(str(contract.id)) is not None

        # Mutate the payload lineage and save directly — the post-save
        # sync diffs against the edge table and inserts a new edge row
        # (a real write transition outside update_contract).
        payload = dict(contract.hub_contract_json or {})
        payload["lineage"] = {
            "contracts": [],
            "models": [],
            "entries": [
                {
                    "input_fields": [
                        {
                            "name": "default",
                            "field": "cid",
                            "namespace": str(c_src.id),
                        },
                    ],
                    "output_fields": [
                        {"name": "default", "field": "cid"},
                    ],
                },
            ],
        }
        contract.hub_contract_json = payload
        # The post-save lineage sync is registered via on_commit; those
        # hooks only drain at a real atomic commit — wrap the save so
        # the sync actually executes within the test (the same reason
        # the service paths all use @transaction.atomic).
        with transaction.atomic():
            contract.save(update_fields=["hub_contract_json", "updated_at"])

        assert LineageEdge.objects.filter(
            target_contract_id=contract.id,
            valid_to__isnull=True,
        ).exists(), "the sync must have materialised the new edge"
        assert (
            get_cached_lineage(str(contract.id)) is None
        ), "the sync's edge transitions must invalidate the lineage cache"
