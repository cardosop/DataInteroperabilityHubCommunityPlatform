"""
Phase 228.F3.18 — Dispatcher tests (REQ-LIN-F3-005).

Coverage of the spec scenarios:

* HIGH severity dispatched to HIGH subscriber.
* HIGH severity skipped for CRITICAL-only subscriber.
* Debounce holds (no second notification in the window).
* Cross-tenant content respects detail tier (summary-only).
* Per-tenant rate limit drops the 1001st in a window AND records
  an audit row.

The dispatcher uses a real Redis client when REDIS_URL is set, and
no-ops otherwise.  These tests exercise the dispatcher with the
real LineageSubscription / Contract / LineageEdge objects but use
a fake in-memory Redis client (a thin shim, NOT a generic mock —
it's a controlled test double of the small Redis surface the
dispatcher actually touches: ``exists``, ``setex``, ``get``,
``incr``, ``expire``).  This is the bare minimum surface needed to
exercise debounce + rate-limit semantics deterministically without
a live Redis.
"""
from __future__ import annotations

import time
import uuid
from typing import Dict

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.lineage_impact_dispatcher import (
    F3_PER_TENANT_RATE_LIMIT,
    handle_contract_updated,
)
from hub.apps.contracts.lineage_severity import Severity
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class FakeRedis:
    """In-memory shim covering the surface
    :mod:`hub.apps.contracts.lineage_impact_dispatcher` actually uses.

    This is NOT a mock of the dispatcher's behaviour — it's a real
    deterministic Redis-shaped store keyed by string with TTL
    semantics implemented via a wall-clock comparison.  The
    dispatcher's debounce + rate-limit logic is exercised end-to-end
    against this store with no internal-code mocking.
    """

    def __init__(self):
        self._data: Dict[str, bytes] = {}
        self._expires_at: Dict[str, float] = {}

    # Helpers ----------------------------------------------------------------

    def _expired(self, key: str) -> bool:
        exp = self._expires_at.get(key)
        return exp is not None and exp < time.time()

    def _gc(self, key: str) -> None:
        if self._expired(key):
            self._data.pop(key, None)
            self._expires_at.pop(key, None)

    # Surface ----------------------------------------------------------------

    def exists(self, key: str) -> int:
        self._gc(key)
        return 1 if key in self._data else 0

    def get(self, key: str):
        self._gc(key)
        return self._data.get(key)

    def setex(self, key: str, ttl: int, value) -> bool:
        self._data[key] = str(value).encode()
        self._expires_at[key] = time.time() + ttl
        return True

    def incr(self, key: str) -> int:
        self._gc(key)
        current = int(self._data.get(key, b"0"))
        new = current + 1
        self._data[key] = str(new).encode()
        return new

    def expire(self, key: str, ttl: int) -> bool:
        if key in self._data:
            self._expires_at[key] = time.time() + ttl
            return True
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_tenant(slug_prefix: str = "f3d") -> Tenant:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{slug_prefix}-{suffix}",
        slug=f"{slug_prefix}-{suffix}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _make_user(tenant: Tenant) -> "User":  # type: ignore[name-defined]  # test: edge-case type exercise
    suffix = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"u-{suffix}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _make_contract(tenant: Tenant, name: str = "c"):
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
    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.1.0",
        original_format=OriginalFormat.JSON,
        original_raw="{}",
        hub_contract_json={"info": {"name": name}, "models": []},
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status=ContractStatus.ACTIVE,
    )


def _seed_derivation_edge(tenant, source_contract, target_contract):
    """A derivation edge → severity classifier returns HIGH."""
    from hub.apps.contracts.models import LineageEdge
    return LineageEdge.objects.create(
        tenant=tenant,
        source_contract_id=source_contract.id,
        target_contract_id=target_contract.id,
        source_model="default", source_field="x",
        target_model="default", target_field="x",
        edge_type="derivation",
    )


def _patch_redis(monkeypatch_or_self) -> FakeRedis:
    fake = FakeRedis()
    from hub.apps.contracts import lineage_impact_dispatcher as mod

    # Patch the module-level _get_redis_client; we inject the fake
    # client directly so the dispatcher uses it for both debounce +
    # rate limit.
    mod._get_redis_client = lambda: fake  # type: ignore[assignment]  # test: edge-case type exercise
    return fake


# ---------------------------------------------------------------------------
# Severity gate
# ---------------------------------------------------------------------------


class DispatcherSeverityGateTests(TestCase):

    def test_high_severity_dispatched_to_high_threshold_subscriber(self):
        from hub.apps.contracts.models import LineageSubscription
        from hub.apps.notifications.models import UserNotification

        tenant = _make_tenant()
        user = _make_user(tenant)
        c_src = _make_contract(tenant, name="src")
        c_tgt = _make_contract(tenant, name="tgt")
        _seed_derivation_edge(tenant, c_src, c_tgt)
        LineageSubscription.objects.create(
            user=user, source_contract=c_src,
            severity_threshold="HIGH", in_app=True, email=False,
        )
        _patch_redis(self)

        result = handle_contract_updated(
            contract_id=str(c_src.id),
            tenant_id=str(tenant.id),
            old_lineage_hash="old", new_lineage_hash="new",
        )
        self.assertEqual(result["severity"], Severity.HIGH.value)
        self.assertEqual(result["dispatched"], 1)
        # The in-app row landed.
        self.assertEqual(
            UserNotification.objects.filter(
                user=user, category="LINEAGE_IMPACT",
            ).count(),
            1,
        )

    def test_high_severity_skipped_for_critical_only_subscriber(self):
        from hub.apps.contracts.models import LineageSubscription
        from hub.apps.notifications.models import UserNotification

        tenant = _make_tenant()
        user = _make_user(tenant)
        c_src = _make_contract(tenant, name="src")
        c_tgt = _make_contract(tenant, name="tgt")
        _seed_derivation_edge(tenant, c_src, c_tgt)
        LineageSubscription.objects.create(
            user=user, source_contract=c_src,
            severity_threshold="CRITICAL",
        )
        _patch_redis(self)

        result = handle_contract_updated(
            contract_id=str(c_src.id),
            tenant_id=str(tenant.id),
            old_lineage_hash="old", new_lineage_hash="new",
        )
        self.assertEqual(result["skipped_below_threshold"], 1)
        self.assertEqual(
            UserNotification.objects.filter(
                user=user, category="LINEAGE_IMPACT",
            ).count(),
            0,
        )


# ---------------------------------------------------------------------------
# Debounce
# ---------------------------------------------------------------------------


class DispatcherDebounceTests(TestCase):

    def test_second_dispatch_within_window_is_debounced(self):
        from hub.apps.contracts.models import LineageSubscription
        from hub.apps.notifications.models import UserNotification

        tenant = _make_tenant()
        user = _make_user(tenant)
        c_src = _make_contract(tenant, name="src")
        c_tgt = _make_contract(tenant, name="tgt")
        _seed_derivation_edge(tenant, c_src, c_tgt)
        LineageSubscription.objects.create(
            user=user, source_contract=c_src,
            severity_threshold="HIGH",
        )
        _patch_redis(self)

        first = handle_contract_updated(
            contract_id=str(c_src.id), tenant_id=str(tenant.id),
            old_lineage_hash="a", new_lineage_hash="b",
        )
        self.assertEqual(first["dispatched"], 1)

        # Second event for the same source within the debounce window.
        second = handle_contract_updated(
            contract_id=str(c_src.id), tenant_id=str(tenant.id),
            old_lineage_hash="b", new_lineage_hash="c",
        )
        self.assertEqual(second["debounced"], 1)
        self.assertEqual(second["dispatched"], 0)
        # Only one notification row.
        self.assertEqual(
            UserNotification.objects.filter(
                user=user, category="LINEAGE_IMPACT",
            ).count(),
            1,
        )


# ---------------------------------------------------------------------------
# Per-tenant rate limit
# ---------------------------------------------------------------------------


class DispatcherRateLimitTests(TransactionTestCase):
    """``TransactionTestCase`` (not ``TestCase``) because the
    rate-limit drop emits an audit row via ``create_audit_event(
    tenant=None, action='DISPATCH_RATE_LIMITED', ...)`` which routes
    through the ``admin`` DB alias (B-RLS-0.5).  Django's ``TestCase``
    enters ``transaction.atomic()`` for every alias in
    ``cls._databases_names()`` so the admin INSERT gets stranded
    inside admin's open transaction — invisible to the default-alias
    reader under READ COMMITTED.  TransactionTestCase runs in
    TRUNCATE-isolation mode where admin commits land immediately.
    """

    def test_rate_limit_drops_1001st(self):
        """Pre-seed the rate counter to the cap so the next dispatch
        is dropped — exercises the rate-limit path without spawning
        1000 subscribers."""
        from hub.apps.contracts.models import LineageSubscription
        from hub.apps.notifications.models import UserNotification

        tenant = _make_tenant()
        user = _make_user(tenant)
        c_src = _make_contract(tenant, name="src")
        c_tgt = _make_contract(tenant, name="tgt")
        _seed_derivation_edge(tenant, c_src, c_tgt)
        LineageSubscription.objects.create(
            user=user, source_contract=c_src,
            severity_threshold="HIGH",
        )
        fake = _patch_redis(self)
        # Pre-seed the rate counter at the cap.
        rate_key = f"lineage:rate:{tenant.id}"
        fake._data[rate_key] = str(F3_PER_TENANT_RATE_LIMIT).encode()
        fake._expires_at[rate_key] = time.time() + 3600

        result = handle_contract_updated(
            contract_id=str(c_src.id), tenant_id=str(tenant.id),
            old_lineage_hash="a", new_lineage_hash="b",
        )
        self.assertEqual(result["rate_limited"], 1)
        self.assertEqual(result["dispatched"], 0)
        self.assertEqual(
            UserNotification.objects.filter(
                user=user, category="LINEAGE_IMPACT",
            ).count(),
            0,
        )

    def test_rate_limit_drop_emits_audit_row(self):
        """REQ-LIN-F3-005 spec scenario "Per-tenant rate limit" —
        dropped dispatches MUST be recorded in the audit log so
        operators can investigate via the runbook (F3.22).
        Phase 228.F3.MetaDoD audit fix."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.models import LineageSubscription

        tenant = _make_tenant()
        user = _make_user(tenant)
        c_src = _make_contract(tenant, name="src")
        c_tgt = _make_contract(tenant, name="tgt")
        _seed_derivation_edge(tenant, c_src, c_tgt)
        LineageSubscription.objects.create(
            user=user, source_contract=c_src,
            severity_threshold="HIGH",
        )
        fake = _patch_redis(self)
        rate_key = f"lineage:rate:{tenant.id}"
        fake._data[rate_key] = str(F3_PER_TENANT_RATE_LIMIT).encode()
        fake._expires_at[rate_key] = time.time() + 3600

        before_drops = AuditEvent.objects.filter(
            action="DISPATCH_RATE_LIMITED",
        ).count()
        handle_contract_updated(
            contract_id=str(c_src.id), tenant_id=str(tenant.id),
            old_lineage_hash="a", new_lineage_hash="b",
        )
        after_drops = AuditEvent.objects.filter(
            action="DISPATCH_RATE_LIMITED",
        ).count()
        # At least one new audit row recording the drop.
        self.assertGreaterEqual(after_drops - before_drops, 1)


# ---------------------------------------------------------------------------
# Downstream walk (REQ-LIN-F3-005 step 3 — Phase 228.F3.MetaDoD audit fix)
# ---------------------------------------------------------------------------


class DispatcherDownstreamWalkTests(TestCase):
    """Subscribers attached to contracts DOWNSTREAM of the changed
    contract receive notifications too — the dispatcher walks the
    LineageEdge graph BFS to enumerate affected contracts before
    pulling their subscribers.
    """

    def test_subscriber_on_downstream_contract_is_notified(self):
        from hub.apps.contracts.models import LineageEdge, LineageSubscription
        from hub.apps.notifications.models import UserNotification

        tenant = _make_tenant("ds")
        user = _make_user(tenant)
        # Graph: A → B → C (subscriber on C, change A).
        c_a = _make_contract(tenant, name="a")
        c_b = _make_contract(tenant, name="b")
        c_c = _make_contract(tenant, name="c")
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract_id=c_a.id, target_contract_id=c_b.id,
            source_model="default", source_field="x",
            target_model="default", target_field="x",
            edge_type="derivation",
        )
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract_id=c_b.id, target_contract_id=c_c.id,
            source_model="default", source_field="x",
            target_model="default", target_field="x",
            edge_type="derivation",
        )
        # Subscriber attached to C (downstream of A).
        LineageSubscription.objects.create(
            user=user, source_contract=c_c, severity_threshold="HIGH",
        )
        _patch_redis(self)

        result = handle_contract_updated(
            contract_id=str(c_a.id), tenant_id=str(tenant.id),
            old_lineage_hash="a", new_lineage_hash="b",
        )
        # The subscriber on C must have been picked up.
        self.assertEqual(result["dispatched"], 1)
        self.assertEqual(
            UserNotification.objects.filter(
                user=user, category="LINEAGE_IMPACT",
            ).count(),
            1,
        )


# ---------------------------------------------------------------------------
# What-changed summary in body (REQ-LIN-F3-006 — Phase 228.F3.MetaDoD audit)
# ---------------------------------------------------------------------------


class DispatcherBodySummaryTests(TestCase):
    """The notification body MUST surface the added / removed edge
    counts per REQ-LIN-F3-006 'What changed summary'."""

    def test_body_contains_added_edge_count(self):
        from hub.apps.contracts.models import LineageSubscription
        from hub.apps.notifications.models import UserNotification

        tenant = _make_tenant("ws")
        user = _make_user(tenant)
        c_src = _make_contract(tenant, name="src")
        c_tgt = _make_contract(tenant, name="tgt")
        # 2 derivation edges → diff.added has 2 entries.
        _seed_derivation_edge(tenant, c_src, c_tgt)
        from hub.apps.contracts.models import LineageEdge
        c_tgt2 = _make_contract(tenant, name="tgt2")
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract_id=c_src.id, target_contract_id=c_tgt2.id,
            source_model="default", source_field="x",
            target_model="default", target_field="x",
            edge_type="derivation",
        )
        LineageSubscription.objects.create(
            user=user, source_contract=c_src, severity_threshold="HIGH",
        )
        _patch_redis(self)

        handle_contract_updated(
            contract_id=str(c_src.id), tenant_id=str(tenant.id),
            old_lineage_hash="a", new_lineage_hash="b",
        )
        notif = UserNotification.objects.get(
            user=user, category="LINEAGE_IMPACT",
        )
        # The summary clause is rendered in the message body.
        self.assertIn("edges added", notif.message.lower() + " ")


# ---------------------------------------------------------------------------
# Cross-tenant detail-tier downgrade
# ---------------------------------------------------------------------------


class DispatcherCrossTenantContentTests(TestCase):

    def test_cross_tenant_subscriber_receives_summary_only(self):
        """The dispatcher computes the user-tenant vs source-tenant
        relationship at notification time; cross-tenant subscribers
        get a summary-only body (no field names, no transformation_ref).
        """
        from hub.apps.contracts.models import LineageSubscription
        from hub.apps.notifications.models import UserNotification

        tenant_a = _make_tenant("xt-a")
        tenant_b = _make_tenant("xt-b")
        user_b = _make_user(tenant_b)  # subscriber lives in tenant B
        c_src = _make_contract(tenant_a, name="src-a")  # source in tenant A
        c_tgt = _make_contract(tenant_a, name="tgt-a")
        _seed_derivation_edge(tenant_a, c_src, c_tgt)
        # Backfilled cross-tenant subscription (the API blocks creating
        # this in v1, but the dispatcher must still downgrade).
        LineageSubscription.objects.create(
            user=user_b, source_contract=c_src,
            severity_threshold="HIGH",
        )
        _patch_redis(self)

        result = handle_contract_updated(
            contract_id=str(c_src.id),
            tenant_id=str(tenant_a.id),
            old_lineage_hash="a", new_lineage_hash="b",
        )
        self.assertEqual(result["dispatched"], 1)
        notif = UserNotification.objects.get(
            user=user_b, category="LINEAGE_IMPACT",
        )
        # Summary-only body: must NOT contain the contract's name
        # (which is the in-tenant detail).
        self.assertNotIn("src-a", notif.message)
        self.assertIn("subscribe", notif.message.lower())
