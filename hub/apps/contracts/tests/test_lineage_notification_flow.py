"""
Phase 228.F3.19 — End-to-end integration test for the lineage
notification flow.

Walks the full pipeline:

1. Create contract A (subscriber's source).
2. Create user B in the same tenant; subscribe B to A at HIGH.
3. Save A with a modified ``hub_contract_json.lineage`` — the
   post_save signal fires.
4. Manually drain the ``transaction.on_commit`` callback (in test
   the dispatcher runs synchronously when the transaction commits).
5. Assert a ``UserNotification`` row landed for user B with
   category ``LINEAGE_IMPACT``.

The signal hook is wired in the contracts AppConfig at app-ready
time, and the test relies on the same hook firing here.  No mocks
of internal code: the entire path is exercised against the real
Contract / LineageEdge / LineageSubscription / UserNotification
models.
"""
from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts import lineage_impact_dispatcher as dispatcher_mod
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class FakeRedis:
    """Minimal Redis surface — same shape as the dispatcher tests."""

    def __init__(self):
        self._data = {}
        self._exp = {}

    def exists(self, key):
        return 1 if key in self._data else 0

    def get(self, key):
        return self._data.get(key)

    def setex(self, key, ttl, value):
        self._data[key] = str(value).encode()
        return True

    def incr(self, key):
        new = int(self._data.get(key, b"0")) + 1
        self._data[key] = str(new).encode()
        return new

    def expire(self, key, ttl):
        return True


class LineageNotificationFlowTests(TransactionTestCase):
    """End-to-end flow covering REQ-LIN-F3-001 through REQ-LIN-F3-006."""

    def setUp(self):
        # Replace the Redis client at the dispatcher module level so
        # debounce + rate-limit have a deterministic store.  This is
        # NOT a mock of the dispatcher's logic — it's a controlled
        # backend the dispatcher uses identically to production.
        self._fake_redis = FakeRedis()
        dispatcher_mod._get_redis_client = lambda: self._fake_redis

    def _make_tenant(self, slug_prefix="f3-flow"):
        suffix = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"{slug_prefix}-{suffix}",
            slug=f"{slug_prefix}-{suffix}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(tenant)
        return tenant

    def _make_user(self, tenant):
        suffix = uuid.uuid4().hex[:8]
        return User.objects.create_user(
            email=f"u-{suffix}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )

    def test_lineage_save_dispatches_notification(self):
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            LineageEdge,
            LineageSubscription,
            OriginalFormat,
            OriginalSpecType,
        )
        from hub.apps.notifications.models import UserNotification

        tenant = self._make_tenant()
        author = self._make_user(tenant)
        subscriber = self._make_user(tenant)

        asset_src = Asset.objects.create(
            tenant=tenant,
            key=f"asset-{uuid.uuid4().hex[:6]}",
            name="src",
            status=AssetStatus.DRAFT,
        )
        asset_tgt = Asset.objects.create(
            tenant=tenant,
            key=f"asset-{uuid.uuid4().hex[:6]}",
            name="tgt",
            status=AssetStatus.DRAFT,
        )
        c_src = Contract.objects.create(
            tenant=tenant,
            asset=asset_src,
            version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.1.0",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            hub_contract_json={"info": {"name": "src"}, "models": []},
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status=ContractStatus.ACTIVE,
        )
        c_tgt = Contract.objects.create(
            tenant=tenant,
            asset=asset_tgt,
            version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.1.0",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            hub_contract_json={"info": {"name": "tgt"}, "models": []},
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status=ContractStatus.ACTIVE,
        )

        # Seed a derivation edge so the classifier returns HIGH.
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract_id=c_src.id, target_contract_id=c_tgt.id,
            source_model="default", source_field="x",
            target_model="default", target_field="x",
            edge_type="derivation",
        )

        # Subscribe the user.
        LineageSubscription.objects.create(
            user=subscriber, source_contract=c_src,
            severity_threshold="HIGH", in_app=True,
        )

        # Mutate the lineage subtree — the post_save signal fires
        # the dispatcher via transaction.on_commit.  TransactionTestCase
        # runs each test outside a wrapping transaction so on_commit
        # callbacks execute immediately on save.
        c_src.hub_contract_json = {
            **c_src.hub_contract_json,
            "lineage": {"version": 1, "edges": [{"placeholder": True}]},
        }
        c_src._f3_actor_user_id = str(author.id)
        c_src.save()

        # The dispatcher runs synchronously after commit; the
        # UserNotification row should now exist.
        notifications = UserNotification.objects.filter(
            user=subscriber, category="LINEAGE_IMPACT",
        )
        self.assertGreaterEqual(notifications.count(), 1)
        notif = notifications.first()
        self.assertIn("Lineage updated", notif.title)


# ---------------------------------------------------------------------------
# F3.20 — Load test (REQ-LIN-F3-007)
# ---------------------------------------------------------------------------
#
# Full 1000-subscriber load test lives in tests/load/notification_storm.py
# (a separate runner — pytest's default suite avoids the 60-second
# wall-clock budget).  This in-suite test runs a SCALED-DOWN
# version (50 subscribers) to verify the dispatcher's batching logic
# without taxing CI.
# ---------------------------------------------------------------------------


class LineageNotificationLoadSmokeTests(TransactionTestCase):
    """Scaled-down variant of the F3.20 load test — runs in CI."""

    SUBSCRIBER_COUNT = 50

    def setUp(self):
        self._fake_redis = FakeRedis()
        dispatcher_mod._get_redis_client = lambda: self._fake_redis

    def test_50_subscribers_all_dispatched(self):
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            LineageEdge,
            LineageSubscription,
            OriginalFormat,
            OriginalSpecType,
        )
        from hub.apps.notifications.models import UserNotification

        suffix = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"f3-load-{suffix}",
            slug=f"f3-load-{suffix}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(tenant)

        asset_src = Asset.objects.create(
            tenant=tenant, key=f"asset-{uuid.uuid4().hex[:6]}",
            name="load-src", status=AssetStatus.DRAFT,
        )
        asset_tgt = Asset.objects.create(
            tenant=tenant, key=f"asset-{uuid.uuid4().hex[:6]}",
            name="load-tgt", status=AssetStatus.DRAFT,
        )
        c_src = Contract.objects.create(
            tenant=tenant, asset=asset_src, version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.1.0",
            original_format=OriginalFormat.JSON, original_raw="{}",
            hub_contract_json={"info": {"name": "src"}, "models": []},
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status=ContractStatus.ACTIVE,
        )
        c_tgt = Contract.objects.create(
            tenant=tenant, asset=asset_tgt, version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.1.0",
            original_format=OriginalFormat.JSON, original_raw="{}",
            hub_contract_json={"info": {"name": "tgt"}, "models": []},
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status=ContractStatus.ACTIVE,
        )
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract_id=c_src.id, target_contract_id=c_tgt.id,
            source_model="default", source_field="x",
            target_model="default", target_field="x",
            edge_type="derivation",
        )

        # Bulk-create the subscribers.
        users = []
        for i in range(self.SUBSCRIBER_COUNT):
            users.append(User.objects.create_user(
                email=f"loaduser-{i}-{suffix}@example.com",
                password="testpass123",
                tenant=tenant,
                status=UserStatus.ACTIVE,
            ))
        LineageSubscription.objects.bulk_create([
            LineageSubscription(
                user=u, source_contract=c_src,
                severity_threshold="HIGH", in_app=True,
            )
            for u in users
        ])

        # Trigger the dispatch by saving the contract with new lineage.
        c_src.hub_contract_json = {
            **c_src.hub_contract_json,
            "lineage": {"version": 1, "edges": [{"placeholder": True}]},
        }
        c_src.save()

        # All subscribers should have a notification.
        delivered = UserNotification.objects.filter(
            category="LINEAGE_IMPACT",
            user_id__in=[u.id for u in users],
        ).count()
        self.assertEqual(delivered, self.SUBSCRIBER_COUNT)

        # Re-saving WITHOUT a lineage change must NOT produce a
        # second notification per subscriber (the signal's hash
        # comparison short-circuits).
        c_src.save()
        post_resave_count = UserNotification.objects.filter(
            category="LINEAGE_IMPACT",
            user_id__in=[u.id for u in users],
        ).count()
        self.assertEqual(post_resave_count, self.SUBSCRIBER_COUNT)


# ---------------------------------------------------------------------------
# F3.21 — Chaos test (REQ-LIN-F3-005 idempotency)
# ---------------------------------------------------------------------------


class LineageDispatcherIdempotencyTests(TransactionTestCase):
    """If the dispatcher is invoked twice for the same event (e.g. a
    worker restart re-queues the job), the debounce key prevents
    duplicate notifications.

    This is the chaos-resilience invariant — REQ-LIN-F3-005 mandates
    "no duplicate notifications" even when the dispatcher pod is
    killed mid-batch.  The debounce SETEX is the durability hook.
    """

    def setUp(self):
        self._fake_redis = FakeRedis()
        dispatcher_mod._get_redis_client = lambda: self._fake_redis

    def test_double_invocation_yields_one_notification(self):
        from hub.apps.contracts.lineage_impact_dispatcher import (
            handle_contract_updated,
        )
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            LineageEdge,
            LineageSubscription,
            OriginalFormat,
            OriginalSpecType,
        )
        from hub.apps.notifications.models import UserNotification

        suffix = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"chaos-{suffix}", slug=f"chaos-{suffix}",
            status="ACTIVE", kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(tenant)
        user = User.objects.create_user(
            email=f"chaos-{suffix}@example.com",
            password="testpass123",
            tenant=tenant, status=UserStatus.ACTIVE,
        )
        asset_src = Asset.objects.create(
            tenant=tenant, key=f"asset-{uuid.uuid4().hex[:6]}",
            name="chaos-src", status=AssetStatus.DRAFT,
        )
        asset_tgt = Asset.objects.create(
            tenant=tenant, key=f"asset-{uuid.uuid4().hex[:6]}",
            name="chaos-tgt", status=AssetStatus.DRAFT,
        )
        c_src = Contract.objects.create(
            tenant=tenant, asset=asset_src, version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.1.0",
            original_format=OriginalFormat.JSON, original_raw="{}",
            hub_contract_json={"info": {"name": "s"}, "models": []},
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status=ContractStatus.ACTIVE,
        )
        c_tgt = Contract.objects.create(
            tenant=tenant, asset=asset_tgt, version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.1.0",
            original_format=OriginalFormat.JSON, original_raw="{}",
            hub_contract_json={"info": {"name": "t"}, "models": []},
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status=ContractStatus.ACTIVE,
        )
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract_id=c_src.id, target_contract_id=c_tgt.id,
            source_model="default", source_field="x",
            target_model="default", target_field="x",
            edge_type="derivation",
        )
        LineageSubscription.objects.create(
            user=user, source_contract=c_src, severity_threshold="HIGH",
        )

        # Invoke the dispatcher twice as if a worker re-queued the job.
        handle_contract_updated(
            contract_id=str(c_src.id), tenant_id=str(tenant.id),
            old_lineage_hash="a", new_lineage_hash="b",
        )
        handle_contract_updated(
            contract_id=str(c_src.id), tenant_id=str(tenant.id),
            old_lineage_hash="a", new_lineage_hash="b",
        )

        delivered = UserNotification.objects.filter(
            user=user, category="LINEAGE_IMPACT",
        ).count()
        self.assertEqual(delivered, 1)
