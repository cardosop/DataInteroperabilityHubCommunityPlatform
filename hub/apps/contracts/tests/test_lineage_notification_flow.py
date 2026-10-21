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


_ORIG_GET_REDIS = None


def _save_and_patch_redis(test_case):
    """Replace ``dispatcher_mod._get_redis_client`` with a FakeRedis,
    saving the original so tearDown can restore it."""
    global _ORIG_GET_REDIS
    if _ORIG_GET_REDIS is None:
        _ORIG_GET_REDIS = dispatcher_mod._get_redis_client
    test_case._fake_redis = FakeRedis()
    dispatcher_mod._get_redis_client = lambda: test_case._fake_redis


def _restore_redis():
    global _ORIG_GET_REDIS
    if _ORIG_GET_REDIS is not None:
        dispatcher_mod._get_redis_client = _ORIG_GET_REDIS
        _ORIG_GET_REDIS = None


class LineageNotificationFlowTests(TransactionTestCase):
    """End-to-end flow covering REQ-LIN-F3-001 through REQ-LIN-F3-006."""

    def setUp(self):
        super().setUp()
        _save_and_patch_redis(self)

    def tearDown(self):
        _restore_redis()
        super().tearDown()

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
            source_contract_id=c_src.id,
            target_contract_id=c_tgt.id,
            source_model="default",
            source_field="x",
            target_model="default",
            target_field="x",
            edge_type="derivation",
        )

        # Subscribe the user.
        LineageSubscription.objects.create(
            user=subscriber,
            source_contract=c_src,
            severity_threshold="HIGH",
            in_app=True,
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
            user=subscriber,
            category="LINEAGE_IMPACT",
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
        super().setUp()
        _save_and_patch_redis(self)

    def tearDown(self):
        _restore_redis()
        super().tearDown()

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
            tenant=tenant,
            key=f"asset-{uuid.uuid4().hex[:6]}",
            name="load-src",
            status=AssetStatus.DRAFT,
        )
        asset_tgt = Asset.objects.create(
            tenant=tenant,
            key=f"asset-{uuid.uuid4().hex[:6]}",
            name="load-tgt",
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
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract_id=c_src.id,
            target_contract_id=c_tgt.id,
            source_model="default",
            source_field="x",
            target_model="default",
            target_field="x",
            edge_type="derivation",
        )

        # Bulk-create the subscribers.
        users = []
        for i in range(self.SUBSCRIBER_COUNT):
            users.append(
                User.objects.create_user(
                    email=f"loaduser-{i}-{suffix}@example.com",
                    password="testpass123",
                    tenant=tenant,
                    status=UserStatus.ACTIVE,
                )
            )
        LineageSubscription.objects.bulk_create(
            [
                LineageSubscription(
                    user=u,
                    source_contract=c_src,
                    severity_threshold="HIGH",
                    in_app=True,
                )
                for u in users
            ]
        )

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
        super().setUp()
        _save_and_patch_redis(self)

    def tearDown(self):
        _restore_redis()
        super().tearDown()

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
            name=f"chaos-{suffix}",
            slug=f"chaos-{suffix}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(tenant)
        user = User.objects.create_user(
            email=f"chaos-{suffix}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        asset_src = Asset.objects.create(
            tenant=tenant,
            key=f"asset-{uuid.uuid4().hex[:6]}",
            name="chaos-src",
            status=AssetStatus.DRAFT,
        )
        asset_tgt = Asset.objects.create(
            tenant=tenant,
            key=f"asset-{uuid.uuid4().hex[:6]}",
            name="chaos-tgt",
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
            hub_contract_json={"info": {"name": "s"}, "models": []},
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
            hub_contract_json={"info": {"name": "t"}, "models": []},
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status=ContractStatus.ACTIVE,
        )
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract_id=c_src.id,
            target_contract_id=c_tgt.id,
            source_model="default",
            source_field="x",
            target_model="default",
            target_field="x",
            edge_type="derivation",
        )
        LineageSubscription.objects.create(
            user=user,
            source_contract=c_src,
            severity_threshold="HIGH",
        )

        # Invoke the dispatcher twice as if a worker re-queued the job.
        handle_contract_updated(
            contract_id=str(c_src.id),
            tenant_id=str(tenant.id),
            old_lineage_hash="a",
            new_lineage_hash="b",
        )
        handle_contract_updated(
            contract_id=str(c_src.id),
            tenant_id=str(tenant.id),
            old_lineage_hash="a",
            new_lineage_hash="b",
        )

        delivered = UserNotification.objects.filter(
            user=user,
            category="LINEAGE_IMPACT",
        ).count()
        self.assertEqual(delivered, 1)


# ---------------------------------------------------------------------------
# REQ-LIN-F3-001 — Contract Update Event Publication
#
# Phase 228.F3.DoD.1-E audit fix.  The integration test above
# exercises the signal indirectly; these tests pin the SIGNAL-LEVEL
# semantics — fires-iff-lineage-changes — so a regression in
# ``signals.publish_contract_updated_for_lineage`` (e.g. always-fire,
# never-fire, or wrong-hash-comparison) is caught immediately.
# ---------------------------------------------------------------------------


class ContractUpdatedSignalTests(TransactionTestCase):
    """REQ-LIN-F3-001 spec scenarios:

    * ``Event fires on lineage change`` — saving with a modified
      lineage subtree fires the dispatcher exactly once.
    * ``Event suppressed on no-op`` — saving with an unchanged
      lineage subtree (or non-lineage field churn) does NOT fire.
    """

    def setUp(self):
        # Replace the dispatcher with a recorder so we can count
        # invocations without mocking — the recorder is a small
        # closure that captures (contract_id, old_hash, new_hash)
        # tuples for assertion.  Reverted in tearDown.
        from hub.apps.contracts import signals as signals_mod

        self._calls = []

        def _recorder(
            *,
            contract_id,
            tenant_id,
            old_lineage_hash,
            new_lineage_hash,
            version=None,
            actor_user_id="",
        ):
            self._calls.append(
                {
                    "contract_id": contract_id,
                    "old": old_lineage_hash,
                    "new": new_lineage_hash,
                }
            )

        # We patch via the lazy-import path the signal uses.  The
        # signal reads `from hub.apps.contracts.lineage_impact_dispatcher
        # import handle_contract_updated` at call-time, so we patch
        # the module attribute the signal will resolve.
        from hub.apps.contracts import lineage_impact_dispatcher as disp

        self._orig_handler = disp.handle_contract_updated
        disp.handle_contract_updated = _recorder
        self._signals_mod = signals_mod
        self._disp_mod = disp

    def tearDown(self):
        self._disp_mod.handle_contract_updated = self._orig_handler

    def _make_tenant(self):
        suffix = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"sig-{suffix}",
            slug=f"sig-{suffix}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(tenant)
        return tenant

    def _make_contract(self, tenant, *, lineage=None, name="c"):
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
        body = {"info": {"name": name}, "models": []}
        if lineage is not None:
            body["lineage"] = lineage
        return Contract.objects.create(
            tenant=tenant,
            asset=asset,
            version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.1.0",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            hub_contract_json=body,
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status=ContractStatus.ACTIVE,
        )

    def test_event_fires_on_lineage_change(self):
        tenant = self._make_tenant()
        contract = self._make_contract(tenant, lineage={"version": 1})
        self._calls.clear()

        # Mutate the lineage subtree and save.  The signal must fire
        # exactly once with old_hash != new_hash.
        contract.hub_contract_json = {
            **contract.hub_contract_json,
            "lineage": {"version": 2, "edges": [{"placeholder": True}]},
        }
        contract.save()

        self.assertEqual(len(self._calls), 1)
        call = self._calls[0]
        self.assertEqual(call["contract_id"], str(contract.id))
        self.assertNotEqual(call["old"], call["new"])

    def test_event_suppressed_on_lineage_unchanged(self):
        """Saving with the SAME lineage subtree must NOT fire the
        dispatcher — REQ-LIN-F3-001 'Event suppressed on no-op'."""
        tenant = self._make_tenant()
        contract = self._make_contract(
            tenant,
            lineage={"version": 1, "edges": []},
        )
        self._calls.clear()

        # Re-save without touching hub_contract_json.lineage.
        contract.save()
        self.assertEqual(len(self._calls), 0)

    def test_event_suppressed_on_non_lineage_field_change(self):
        """Saving with a status flip but no lineage change must NOT
        fire — non-lineage churn is REQ-LIN-F3-001 explicit no-op."""
        from hub.apps.contracts.models import ContractStatus

        tenant = self._make_tenant()
        contract = self._make_contract(
            tenant,
            lineage={"version": 1, "edges": []},
        )
        self._calls.clear()

        # Flip status without touching the lineage subtree.
        contract.status = ContractStatus.RETIRED
        contract.save()
        self.assertEqual(len(self._calls), 0)
