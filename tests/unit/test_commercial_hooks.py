"""Phase 313.1.6 — commercial hook defaults (pure, no Django).

These lock the fail-open contract: core-only mode must behave exactly like
"no paid layer registered", and registered providers must be delegated to
without any core-side transformation of arguments or exceptions.
"""

import pytest

from hub.apps.core import commercial_hooks


def _restore():
    commercial_hooks.reset_hooks()


@pytest.fixture(autouse=True, scope="module")
def _restore_registry_after_module():
    """Contain the reset-hooks churn to this module.

    Each test below clears the registry to assert core-only defaults;
    without this fixture the paid providers registered at
    ``AppConfig.ready()`` would stay WIPED for every later test module
    in the session (entitlement checks, order cascades, tier lookups).
    ``hooks_snapshot()`` restores the ready()-time state on exit.
    """
    with commercial_hooks.hooks_snapshot():
        yield


def test_tenant_sparql_view_defaults_to_none():
    _restore()
    assert commercial_hooks.get_tenant_sparql_view() is None


def test_tenant_sparql_view_roundtrip():
    _restore()
    sentinel = object()
    try:
        commercial_hooks.set_tenant_sparql_view(sentinel)
        assert commercial_hooks.get_tenant_sparql_view() is sentinel
    finally:
        _restore()


def test_entitlement_fails_closed_without_provider():
    """OSS core-only: cross-tenant reads are DENIED without a registered
    entitlement provider — the fail-closed tenant-isolation contract
    (P3-1: the old fail-open default let any authenticated user read
    any asset/dataset by id in the public tree)."""
    _restore()
    with pytest.raises(commercial_hooks.PermissionDenied) as excinfo:
        commercial_hooks.check_entitlement(
            consumer_tenant_id="consumer",
            asset_id="asset",
            provider_tenant_id="provider",
        )
    assert excinfo.value.args[0].get("code") == "ENTITLEMENT_REQUIRED"


def test_entitlement_delegates_to_registered_provider():
    _restore()
    captured: dict = {}

    def provider(**kwargs):
        captured.update(kwargs)
        return "provider-verdict"

    try:
        commercial_hooks.set_entitlement_provider(provider)
        result = commercial_hooks.check_entitlement(
            consumer_tenant_id="c1", asset_id="a1", provider_tenant_id="p1"
        )
    finally:
        _restore()
    assert result == "provider-verdict"
    assert captured == {"consumer_tenant_id": "c1", "asset_id": "a1", "provider_tenant_id": "p1"}


def test_entitlement_provider_exceptions_propagate():
    """PermissionDenied (incl. ENTITLEMENT_REQUIRED codes) must surface unchanged."""

    class FakePermissionDenied(Exception):
        pass

    def provider(**_kwargs):
        raise FakePermissionDenied({"code": "ENTITLEMENT_REQUIRED"})

    _restore()
    try:
        commercial_hooks.set_entitlement_provider(provider)
        raised = None
        try:
            commercial_hooks.check_entitlement(
                consumer_tenant_id="c", asset_id="a", provider_tenant_id="p"
            )
        except FakePermissionDenied as exc:
            raised = exc
        assert raised is not None
        assert raised.args[0]["code"] == "ENTITLEMENT_REQUIRED"
    finally:
        _restore()


def test_ontology_expansion_defaults_to_none():
    _restore()
    assert commercial_hooks.get_ontology_expansion_provider() is None


def test_ontology_expansion_roundtrip():
    _restore()

    def sentinel(tenant_id):
        return f"graph-{tenant_id}"

    try:
        commercial_hooks.set_ontology_expansion_provider(sentinel)
        assert commercial_hooks.get_ontology_expansion_provider()("t1") == "graph-t1"
    finally:
        _restore()


# ── Phase 313.H.3 batch-1 hooks ────────────────────────────────────────────


def test_listing_cache_invalidation_defaults_to_noop():
    """Core-only: no marketplace invalidator — the call is a no-op."""
    _restore()
    assert commercial_hooks.invalidate_listing_caches_for_asset("asset-1") is None


def test_listing_cache_invalidation_delegates_to_registered_provider():
    _restore()
    captured: dict = {}

    def provider(asset_pk):
        captured["asset_pk"] = asset_pk

    try:
        commercial_hooks.set_listing_cache_invalidator(provider)
        result = commercial_hooks.invalidate_listing_caches_for_asset("asset-1")
    finally:
        _restore()
    assert result is None
    assert captured == {"asset_pk": "asset-1"}


def test_listing_cache_invalidation_provider_exceptions_propagate():
    """A broken marketplace cache must not be silently swallowed here —
    the fail-soft handling belongs to the call site."""

    class FakeCacheError(Exception):
        pass

    def provider(_asset_pk):
        raise FakeCacheError("boom")

    _restore()
    try:
        commercial_hooks.set_listing_cache_invalidator(provider)
        raised = None
        try:
            commercial_hooks.invalidate_listing_caches_for_asset("asset-1")
        except FakeCacheError as exc:
            raised = exc
        assert raised is not None
    finally:
        _restore()


def test_sample_listing_seed_defaults_to_none():
    """Core-only: no marketplace seeder — no listing to seed."""
    _restore()
    assert commercial_hooks.seed_sample_listing(tenant_id="t1", asset="asset") is None


def test_sample_listing_seed_delegates_to_registered_provider():
    _restore()
    captured: dict = {}

    def provider(*, tenant_id, asset):
        captured.update(tenant_id=tenant_id, asset=asset)
        return ("listing", True)

    try:
        commercial_hooks.set_sample_listing_seeder(provider)
        result = commercial_hooks.seed_sample_listing(tenant_id="t1", asset="asset")
    finally:
        _restore()
    assert result == ("listing", True)
    assert captured == {"tenant_id": "t1", "asset": "asset"}


def test_plan_downgrade_validation_defaults_to_none():
    """Core-only: None means 'valid' — no billing limits exist to violate."""
    _restore()
    assert commercial_hooks.validate_plan_downgrade(tenant_id="t1", new_plan="plan") is None


def test_plan_downgrade_validation_delegates_to_registered_provider():
    _restore()
    captured: dict = {}

    def provider(*, tenant_id, new_plan):
        captured.update(tenant_id=tenant_id, new_plan=new_plan)
        return "verdict"

    try:
        commercial_hooks.set_plan_downgrade_validator(provider)
        result = commercial_hooks.validate_plan_downgrade(tenant_id="t1", new_plan="plan")
    finally:
        _restore()
    assert result == "verdict"
    assert captured == {"tenant_id": "t1", "new_plan": "plan"}


def test_order_approval_finalizer_defaults_to_noop():
    """Core-only: no marketplace order machinery — finalization is a no-op."""
    _restore()
    assert commercial_hooks.finalize_order_approval(order="order", approved_by_user="user") is None


def test_order_approval_finalizer_delegates_to_registered_provider():
    _restore()
    captured: dict = {}

    def provider(*, order, approved_by_user):
        captured.update(order=order, approved_by_user=approved_by_user)

    try:
        commercial_hooks.set_order_approval_finalizer(provider)
        result = commercial_hooks.finalize_order_approval(order="order", approved_by_user="user")
    finally:
        _restore()
    assert result is None
    assert captured == {"order": "order", "approved_by_user": "user"}


def test_order_rejection_finalizer_defaults_to_noop():
    """Core-only: no marketplace order machinery — rejection is a no-op."""
    _restore()
    assert (
        commercial_hooks.finalize_order_rejection(
            order="order", rejected_by_user="user", reason="reason"
        )
        is None
    )


def test_order_rejection_finalizer_delegates_to_registered_provider():
    _restore()
    captured: dict = {}

    def provider(*, order, rejected_by_user, reason):
        captured.update(order=order, rejected_by_user=rejected_by_user, reason=reason)

    try:
        commercial_hooks.set_order_rejection_finalizer(provider)
        result = commercial_hooks.finalize_order_rejection(
            order="order", rejected_by_user="user", reason="reason"
        )
    finally:
        _restore()
    assert result is None
    assert captured == {"order": "order", "rejected_by_user": "user", "reason": "reason"}


def test_hooks_snapshot_restores_registered_providers():
    """The snapshot CM restores hook state after a core-only simulation."""
    _restore()
    sentinel = object()
    commercial_hooks.set_tenant_sparql_view(sentinel)
    try:
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            assert commercial_hooks.get_tenant_sparql_view() is None
        assert commercial_hooks.get_tenant_sparql_view() is sentinel
    finally:
        _restore()


# ── Phase 313.H.3 batch-2 hooks ────────────────────────────────────────────


def test_file_asset_resolver_defaults_to_none():
    """Core-only: no marketplace asset links for files."""
    _restore()
    assert commercial_hooks.get_file_asset_id("file-1") is None


def test_file_asset_resolver_delegates():
    _restore()

    def sentinel(file_id):
        return f"asset-for-{file_id}"

    try:
        commercial_hooks.set_file_asset_resolver(sentinel)
        assert commercial_hooks.get_file_asset_id("file-1") == "asset-for-file-1"
    finally:
        _restore()


def test_payment_gateway_lister_defaults_to_none():
    """Core-only: no payment layer — no gateways to list."""
    _restore()
    assert (
        commercial_hooks.list_payment_gateways_for_contract(
            tenant_id="t1", user_id="u1", contract_id="c1"
        )
        is None
    )


def test_payment_gateway_lister_delegates():
    _restore()
    captured: dict = {}

    def provider(*, tenant_id, user_id, contract_id):
        captured.update(tenant_id=tenant_id, user_id=user_id, contract_id=contract_id)
        return {"gateway-1": {"type": "stripe"}}

    try:
        commercial_hooks.set_payment_gateway_lister(provider)
        result = commercial_hooks.list_payment_gateways_for_contract(
            tenant_id="t1", user_id="u1", contract_id="c1"
        )
    finally:
        _restore()
    assert result == {"gateway-1": {"type": "stripe"}}
    assert captured == {"tenant_id": "t1", "user_id": "u1", "contract_id": "c1"}


def test_ml_model_attributes_provider_defaults_to_none():
    """Core-only: no ML models — no ABAC attributes to enrich."""
    _restore()
    assert commercial_hooks.get_ml_model_attributes(resource_id="m1", tenant_id="t1") is None


def test_ml_model_attributes_provider_delegates():
    _restore()
    captured: dict = {}

    def provider(*, resource_id, tenant_id):
        captured.update(resource_id=resource_id, tenant_id=tenant_id)
        return {"ml_model_name": "sentinel-model"}

    try:
        commercial_hooks.set_ml_model_attributes_provider(provider)
        result = commercial_hooks.get_ml_model_attributes(resource_id="m1", tenant_id="t1")
    finally:
        _restore()
    assert result == {"ml_model_name": "sentinel-model"}
    assert captured == {"resource_id": "m1", "tenant_id": "t1"}


def test_order_owner_checker_defaults_to_false():
    """Core-only: no marketplace orders — nobody owns one."""
    _restore()
    assert commercial_hooks.is_order_owner(resource_id="o1", user="user") is False


def test_order_owner_checker_delegates():
    _restore()
    captured: dict = {}

    def provider(*, resource_id, user):
        captured.update(resource_id=resource_id, user=user)
        return True

    try:
        commercial_hooks.set_order_owner_checker(provider)
        result = commercial_hooks.is_order_owner(resource_id="o1", user="user")
    finally:
        _restore()
    assert result is True
    assert captured == {"resource_id": "o1", "user": "user"}


# ── Phase 313.H.3 batch-3 hooks ────────────────────────────────────────────


def test_cross_tenant_entitlement_check_fails_closed_by_default():
    """Core-only: no marketplace → cross-tenant access can never be verified."""
    _restore()
    result = commercial_hooks.check_cross_tenant_entitlement(
        consumer_tenant_id="c", asset_id="a", provider_tenant_id="p"
    )
    assert result == (False, "ENTITLEMENT_REQUIRED", None)


def test_cross_tenant_entitlement_check_delegates():
    _restore()
    captured: dict = {}

    def provider(*, consumer_tenant_id, asset_id, provider_tenant_id):
        captured.update(
            consumer_tenant_id=consumer_tenant_id,
            asset_id=asset_id,
            provider_tenant_id=provider_tenant_id,
        )
        return (True, None, "entitlement")

    try:
        commercial_hooks.set_cross_tenant_entitlement_checker(provider)
        result = commercial_hooks.check_cross_tenant_entitlement(
            consumer_tenant_id="c", asset_id="a", provider_tenant_id="p"
        )
    finally:
        _restore()
    assert result == (True, None, "entitlement")
    assert captured == {"consumer_tenant_id": "c", "asset_id": "a", "provider_tenant_id": "p"}


def test_entitlement_provider_getter():
    _restore()
    assert commercial_hooks.get_entitlement_provider() is None
    sentinel = object()
    try:
        commercial_hooks.set_entitlement_provider(sentinel)
        assert commercial_hooks.get_entitlement_provider() is sentinel
    finally:
        _restore()


def test_active_billing_setup_vacuously_true_in_core():
    """Core-only: no billing layer → the onboarding signal is satisfied."""
    _restore()
    assert commercial_hooks.has_active_billing_setup(tenant="t") is True


def test_active_billing_setup_delegates():
    _restore()
    captured: dict = {}

    def provider(tenant):
        captured["tenant"] = tenant
        return False

    try:
        commercial_hooks.set_active_billing_setup_checker(provider)
        result = commercial_hooks.has_active_billing_setup(tenant="t")
    finally:
        _restore()
    assert result is False
    assert captured == {"tenant": "t"}


def test_stripe_customer_resolver_defaults_to_none():
    """Core-only: no Stripe → bootstrap-not-complete (None)."""
    _restore()
    assert commercial_hooks.get_stripe_customer_id(tenant="t") is None


def test_stripe_customer_resolver_delegates():
    _restore()
    captured: dict = {}

    def provider(tenant):
        captured["tenant"] = tenant
        return "cus_123"

    try:
        commercial_hooks.set_stripe_customer_resolver(provider)
        result = commercial_hooks.get_stripe_customer_id(tenant="t")
    finally:
        _restore()
    assert result == "cus_123"
    assert captured == {"tenant": "t"}


def test_admin_billing_summary_zeroed_in_core():
    """Core-only: no billing tables → the widget shows zeroes."""
    _restore()
    result = commercial_hooks.get_admin_billing_summary()
    assert result["active"] == 0
    assert result["plan_distribution"] == {"by_tier": {}, "total_active": 0}


def test_admin_billing_summary_delegates():
    _restore()
    payload = {"active": 3, "plan_distribution": {"by_tier": {"PRO": 3}, "total_active": 3}}
    try:
        commercial_hooks.set_admin_billing_summary_provider(lambda: payload)
        assert commercial_hooks.get_admin_billing_summary() == payload
    finally:
        _restore()
