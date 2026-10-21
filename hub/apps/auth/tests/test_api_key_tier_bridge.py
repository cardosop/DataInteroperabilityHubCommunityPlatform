"""P.2c — the API-key tier bridge, both directions (Phase 313 paid-ward FK).

Core ``auth.APIKey.tier`` is a PROPERTY delegating to the paid layer:
the real link lives in ``baas.APIKeyTierAssignment`` (OneToOne → the
core key). The provider/setter/resolver/filter are registered by
``baas.AppConfig.ready()``. Before this module, NONE of the four
``api_key_tier_*`` hook paths had a behavioral test in either mode.

Full mode (paid providers live):
- ``key.tier = tier`` persists a ``baas_api_key_tier_assignments`` row;
- reading the property returns the real tier; ``tier_id`` mirrors it;
- the unsaved-key stash flushes through ``save()``;
- clearing the tier deletes the assignment;
- ``filter_api_keys_by_tier`` narrows a queryset via the assignment;
- ``resolve_api_key_tier("unknown")`` raises ``LookupError``.

Core-only simulation (``hooks_snapshot`` + ``reset_hooks`` — the exact
runtime shape of a core-only process):
- reads return None;
- a non-null write raises ``RuntimeError`` (fail-closed contract).

NO MOCKS at contract boundaries: real Postgres, real ORM, real rows in
the paid assignment table.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.auth.models import APIKey
from hub.apps.core import commercial_hooks
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
UserModel = get_user_model()


def _import_paid_module(module_path: str):
    """GATE-29 — core-tree tests must not statically import paid modules.

    The dynamic import runs inside the test method that needs it: the paid
    apps ARE installed in the full-mode suite where these tests run, and
    core-only test methods skip before ever reaching the call.
    """
    import importlib

    return importlib.import_module(module_path)


def _make_tenant() -> Tenant:
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"T-{uid}",
        slug=f"t-{uid}",
        status=TenantStatus.ACTIVE,
    )


def _make_key(tenant, user=None) -> APIKey:
    plaintext = APIKey.generate_key()
    return APIKey.objects.create(
        tenant=tenant,
        user=user,
        key_hash=APIKey.hash_key(plaintext),
        name="Tier bridge key",
        scopes=["assets:read"],
    )


class ApiKeyTierBridgeTests(TestCase):
    def setUp(self):
        from hub.apps.manifest import is_core_only

        if is_core_only():
            self.skipTest("BaaS tier assignment exists only in full mode")
        super().setUp()
        self.tenant = _make_tenant()
        self.user = UserModel.objects.create_user(
            email=f"u-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def _make_tier(self, name: str = "PRO"):
        APITierModel = _import_paid_module("hub.apps.baas.models").APITierModel

        tier, _ = APITierModel.objects.get_or_create(
            name=name,
            defaults={"rate_limit_per_hour": 1000, "rate_limit_per_day": 10000},
        )
        return tier

    def test_saved_key_tier_round_trips_through_assignment(self):
        APIKeyTierAssignment = _import_paid_module("hub.apps.baas.models").APIKeyTierAssignment

        key = _make_key(self.tenant, self.user)
        tier = self._make_tier()

        key.tier = tier

        assert key.tier == tier
        assert key.tier_id == tier.id
        assert APIKeyTierAssignment.objects.filter(
            api_key=key, tier=tier, tenant=self.tenant
        ).exists(), "the assignment row must persist in the paid table"

    def test_unsaved_key_stashes_tier_until_save(self):
        tier = self._make_tier()
        key = APIKey(
            tenant=self.tenant,
            user=self.user,
            key_hash=APIKey.hash_key(APIKey.generate_key()),
            name="Unsaved key",
            scopes=[],
        )

        key.tier = tier
        assert key.tier == tier  # stashed — the paid read path is untouched

        key.save()

        key.refresh_from_db()
        assert key.tier == tier, "save() must flush the stashed tier"

    def test_clearing_tier_deletes_assignment(self):
        APIKeyTierAssignment = _import_paid_module("hub.apps.baas.models").APIKeyTierAssignment

        key = _make_key(self.tenant, self.user)
        tier = self._make_tier()
        key.tier = tier
        assert key.tier == tier

        key.tier = None

        assert key.tier is None
        assert not APIKeyTierAssignment.objects.filter(api_key=key).exists()

    def test_filter_api_keys_by_tier_narrows_queryset(self):
        APITierModel = _import_paid_module("hub.apps.baas.models").APITierModel

        pro = self._make_tier("PRO")
        free = self._make_tier("FREE")
        pro_key = _make_key(self.tenant, self.user)
        pro_key.tier = pro
        free_key = _make_key(self.tenant, self.user)
        free_key.tier = free
        untiered = _make_key(self.tenant, self.user)

        filtered = commercial_hooks.filter_api_keys_by_tier(
            APIKey.objects.filter(tenant=self.tenant), "PRO"
        )

        assert set(filtered.values_list("id", flat=True)) == {pro_key.id}
        assert free_key.id not in filtered.values_list("id", flat=True)
        assert untiered.id not in filtered.values_list("id", flat=True)
        assert APITierModel.objects.filter(name="PRO").exists()  # sanity

    def test_resolve_unknown_tier_raises_lookup_error(self):
        with pytest.raises(LookupError):
            commercial_hooks.resolve_api_key_tier("NO_SUCH_TIER")


class ApiKeyTierBridgeCoreModeTests(TestCase):
    """Core-sim half: the documented fail-closed contract of the hooks."""

    def setUp(self):
        super().setUp()
        self.tenant = _make_tenant()
        self.key = _make_key(self.tenant)

    def test_core_only_read_returns_none(self):
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            assert self.key.tier is None
            assert self.key.tier_id is None

    def test_core_only_non_null_write_raises(self):
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            with pytest.raises(RuntimeError):
                self.key.tier = "SOMETHING"

    def test_core_only_null_write_is_a_noop(self):
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            self.key.tier = None  # clearing nothing is safe in core
