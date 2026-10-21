"""Phase 313.1 — commercial-layer hooks (core-owned, paid-registered).

Core owns the call sites; the paid layer registers providers from its
``AppConfig.ready()``. Every hook has a no-op default so core-only mode is
well-defined:

- entitlement check → **fail closed** (P3-1 — cross-tenant reads are
  denied without a provider; the paywall gates monetization, not
  tenant isolation); the paid marketplace registers
  ``require_entitlement`` and its ``PermissionDenied`` semantics
  propagate unchanged;
- tenant SPARQL endpoint routes → absent (semantic registers the view);
- ontology-based query expansion → no expansion (semantic registers the
  graph builder; search returns no bridges when no provider exists);
- tombstones → no-op (semantic registers the tombstone writer);
- order entitlement revocation → no-op (marketplace registers the revoker);
- order approval/rejection finalization → no-op (marketplace registers the
  finalizers; the governance cascades fire them only when an order exists);
- marketplace listing cache invalidation → no-op (marketplace registers the
  invalidator; the compliance signal delegates to it);
- sample-listing seeding → absent (marketplace registers the seeder);
- plan downgrade validation → None = valid (billing registers the validator;
  no billing limits exist in core);
- service client factories → absent (test helpers fall back to mocks).

State lives in a module-level dict so providers register without ``global``
statements; ``reset_hooks()`` exists for tests and reloads, and
``hooks_snapshot()`` snapshots/restores the full registry (core-only
simulations in tests).

Pure module — no Django imports — so standalone scripts and tests can use it.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, cast

from rest_framework.exceptions import PermissionDenied

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

# Tombstone reason constants — core-owned so core signal handlers reference
# them without importing the paid semantic app. semantic/tombstone.py keeps
# its own definitions for compatibility.
REASON_ASSET_RETIRED = "asset_retired"
REASON_CONTRACT_DELETED = "contract_deleted"
REASON_DATASET_ARCHIVED = "dataset_archived"
REASON_GDPR_PURGE = "gdpr_purge"

_HOOKS: dict[str, Any] = {}

# ---------------------------------------------------------------------------
# 313-H hardening 1.1 — the PAID↔CORE contract surface, pinned mechanically.
#
# Every row is (function_name, param_spec, setter_pair, registry_key):
#   * param_spec — the EXACT caller-facing parameter list, rendered the way
#     the ``def`` line reads: names in order, ``*`` before keyword-only
#     params, ``**kwargs`` for var-keyword, a trailing ``=`` on any param
#     that has a default. Annotations are deliberately NOT pinned (retyping
#     a hook breaks no call site); kind and optionality ARE (turning
#     ``f(tenant)`` into ``f(*, tenant)`` breaks every positional caller).
#   * setter_pair — the paired setter for a getter/caller row, or None when
#     the row IS the setter (or a utility).
#   * registry_key — the ``_HOOKS`` key the pair writes/reads, or None for
#     utilities and the separate ``_SERVICE_CLIENT_FACTORIES`` registry
#     (whose key is a runtime argument, not a constant).
#
# ``tests/unit/test_commercial_hooks_api_contract.py`` asserts this table
# against the module using ``inspect`` (signatures), ``ast`` (which function
# writes/reads which registry key) and a real setter round-trip. A signature
# change, a broken setter/getter pairing, a swapped registry key, an
# unlisted new function, or an unlisted new key FAILS the full-mode suite.
# Update the table deliberately when the contract changes — never silently.
#
# ``fmt: off`` — one row per hook is the point: it keeps a 57-entry contract
# diffable and scannable. Letting the formatter explode each long row into a
# 6-line tuple would triple the table and bury the pairings.
# ---------------------------------------------------------------------------
# fmt: off
HOOK_API_CONTRACT: tuple[tuple[str, str, str | None, str | None], ...] = (
    # utilities
    ("reset_hooks", "", None, None),
    ("hooks_snapshot", "", None, None),
    # tenant SPARQL endpoint view (semantic)
    ("set_tenant_sparql_view", "view_cls", None, "tenant_sparql_view"),
    ("get_tenant_sparql_view", "", "set_tenant_sparql_view", "tenant_sparql_view"),
    # cross-tenant entitlement enforcement (marketplace)
    ("set_entitlement_provider", "provider", None, "entitlement_provider"),
    ("check_entitlement", "*, consumer_tenant_id, asset_id, provider_tenant_id", "set_entitlement_provider", "entitlement_provider"),
    ("get_entitlement_provider", "", "set_entitlement_provider", "entitlement_provider"),
    # ontology search expansion (semantic)
    ("set_ontology_expansion_provider", "provider", None, "ontology_expansion_provider"),
    ("get_ontology_expansion_provider", "", "set_ontology_expansion_provider", "ontology_expansion_provider"),
    # tombstone dispatch (semantic)
    ("set_tombstone_provider", "provider", None, "tombstone_provider"),
    ("dispatch_tombstone", "*, resource_type, resource_id, reason", "set_tombstone_provider", "tombstone_provider"),
    # order entitlement revocation (marketplace)
    ("set_order_entitlement_revoker", "revoker", None, "order_entitlement_revoker"),
    ("revoke_order_entitlement", "order, reason", "set_order_entitlement_revoker", "order_entitlement_revoker"),
    # governance order cascades (marketplace)
    ("set_order_approval_finalizer", "provider", None, "order_approval_finalizer"),
    ("finalize_order_approval", "*, order, approved_by_user", "set_order_approval_finalizer", "order_approval_finalizer"),
    ("set_order_rejection_finalizer", "provider", None, "order_rejection_finalizer"),
    ("finalize_order_rejection", "*, order, rejected_by_user, reason", "set_order_rejection_finalizer", "order_rejection_finalizer"),
    # listing cache invalidation (marketplace)
    ("set_listing_cache_invalidator", "provider", None, "listing_cache_invalidator"),
    ("invalidate_listing_caches_for_asset", "asset_pk", "set_listing_cache_invalidator", "listing_cache_invalidator"),
    # sample-listing seeding (marketplace)
    ("set_sample_listing_seeder", "provider", None, "sample_listing_seeder"),
    ("seed_sample_listing", "*, tenant_id, asset", "set_sample_listing_seeder", "sample_listing_seeder"),
    # file→asset link resolution (marketplace)
    ("set_file_asset_resolver", "provider", None, "file_asset_resolver"),
    ("get_file_asset_id", "file_id", "set_file_asset_resolver", "file_asset_resolver"),
    # payment-gateway listing (marketplace)
    ("set_payment_gateway_lister", "provider", None, "payment_gateway_lister"),
    ("list_payment_gateways_for_contract", "*, tenant_id, user_id, contract_id", "set_payment_gateway_lister", "payment_gateway_lister"),
    # ML-model ABAC attributes (ml)
    ("set_ml_model_attributes_provider", "provider", None, "ml_model_attributes_provider"),
    ("get_ml_model_attributes", "*, resource_id, tenant_id", "set_ml_model_attributes_provider", "ml_model_attributes_provider"),
    # cross-tenant tuple entitlement check (marketplace)
    ("set_cross_tenant_entitlement_checker", "provider", None, "cross_tenant_entitlement_checker"),
    ("check_cross_tenant_entitlement", "*, consumer_tenant_id, asset_id, provider_tenant_id", "set_cross_tenant_entitlement_checker", "cross_tenant_entitlement_checker"),
    # billing onboarding signal (billing)
    ("set_active_billing_setup_checker", "provider", None, "active_billing_setup_checker"),
    ("has_active_billing_setup", "tenant", "set_active_billing_setup_checker", "active_billing_setup_checker"),
    # stripe customer resolution (billing)
    ("set_stripe_customer_resolver", "provider", None, "stripe_customer_resolver"),
    ("get_stripe_customer_id", "tenant", "set_stripe_customer_resolver", "stripe_customer_resolver"),
    # admin billing summary (billing)
    ("set_admin_billing_summary_provider", "provider", None, "admin_billing_summary_provider"),
    ("get_admin_billing_summary", "", "set_admin_billing_summary_provider", "admin_billing_summary_provider"),
    # order ownership (marketplace)
    ("set_order_owner_checker", "provider", None, "order_owner_checker"),
    ("is_order_owner", "*, resource_id, user", "set_order_owner_checker", "order_owner_checker"),
    # plan downgrade validation (billing)
    ("set_plan_downgrade_validator", "provider", None, "plan_downgrade_validator"),
    ("validate_plan_downgrade", "*, tenant_id, new_plan", "set_plan_downgrade_validator", "plan_downgrade_validator"),
    # subscription factory (billing — test helpers)
    ("set_subscription_factory", "factory", None, "subscription_factory"),
    ("get_subscription_factory", "", "set_subscription_factory", "subscription_factory"),
    # semantic mapper dispatcher (semantic)
    ("set_semantic_mapper", "provider", None, "semantic_mapper"),
    ("map_via_semantic", "resource_type, **kwargs", "set_semantic_mapper", "semantic_mapper"),
    # access-request→order lookup (marketplace)
    ("set_access_request_order_provider", "provider", None, "access_request_order_provider"),
    ("get_access_request_order", "access_request", "set_access_request_order_provider", "access_request_order_provider"),
    # BaaS API-key tier resolution (baas)
    ("set_api_key_tier_provider", "provider", None, "api_key_tier_provider"),
    ("get_api_key_tier", "api_key", "set_api_key_tier_provider", "api_key_tier_provider"),
    ("set_api_key_tier_setter", "setter", None, "api_key_tier_setter"),
    ("set_api_key_tier", "api_key, tier", "set_api_key_tier_setter", "api_key_tier_setter"),
    ("set_api_key_tier_resolver", "resolver", None, "api_key_tier_resolver"),
    ("resolve_api_key_tier", "tier_name", "set_api_key_tier_resolver", "api_key_tier_resolver"),
    ("set_api_key_tier_filter", "filter_fn", None, "api_key_tier_filter"),
    ("filter_api_keys_by_tier", "queryset, tier_name", "set_api_key_tier_filter", "api_key_tier_filter"),
    # product-creation workflow (marketplace)
    ("set_product_creation_workflow", "workflow_cls", None, "product_creation_workflow"),
    ("get_product_creation_workflow", "", "set_product_creation_workflow", "product_creation_workflow"),
    # service client factories (semantic — separate registry, runtime key)
    ("register_service_client_factory", "name, factory", None, None),
    ("get_service_client_factory", "name", None, None),
)
# fmt: on


_SERVICE_CLIENT_FACTORIES: dict[str, Any] = {}


def reset_hooks() -> None:
    """Clear every registration (tests, reloads). Core-only defaults restored."""
    _HOOKS.clear()
    _SERVICE_CLIENT_FACTORIES.clear()


@contextmanager
def hooks_snapshot() -> Iterator[None]:
    """Snapshot and restore the full hook registry (core-only simulations).

    Tests that simulate a core-only process (``reset_hooks()`` inside the
    block) get the exact runtime shape of a process without the paid layer,
    and the paid providers registered at ``AppConfig.ready()`` time are
    restored on exit so later tests in the same session are unaffected.
    """
    saved_hooks = dict(_HOOKS)
    saved_factories = dict(_SERVICE_CLIENT_FACTORIES)
    try:
        yield
    finally:
        _HOOKS.clear()
        _HOOKS.update(saved_hooks)
        _SERVICE_CLIENT_FACTORIES.clear()
        _SERVICE_CLIENT_FACTORIES.update(saved_factories)


# ---------------------------------------------------------------------------
# Tenant SPARQL endpoint routes (mounted by tenants/urls.py only when set)
# ---------------------------------------------------------------------------
def set_tenant_sparql_view(view_cls: Any) -> None:
    """Register the per-tenant SPARQL allowlist ViewSet (paid semantic app)."""
    _HOOKS["tenant_sparql_view"] = view_cls


def get_tenant_sparql_view() -> Any:
    """Return the registered ViewSet class, or None in core-only mode."""
    return _HOOKS.get("tenant_sparql_view")


# ---------------------------------------------------------------------------
# Cross-tenant asset entitlement enforcement
# ---------------------------------------------------------------------------
def set_entitlement_provider(provider: Callable[..., Any]) -> None:
    """Register the entitlement enforcement function (paid marketplace app)."""
    _HOOKS["entitlement_provider"] = provider


def check_entitlement(*, consumer_tenant_id: str, asset_id: str, provider_tenant_id: str) -> Any:
    """Enforce marketplace entitlement for cross-tenant asset access.

    Fail-closed contract (P3-1): with no provider registered (OSS
    core-only), this raises ``PermissionDenied`` with the
    ``ENTITLEMENT_REQUIRED`` code — a cross-tenant read is DENIED, never
    allowed. The old fail-open default let any authenticated user read
    any asset/dataset by id in the public tree (the paywall gates
    monetization, not tenant isolation — the fail-closed tenant-scoping
    contract applies in every build). With a provider, it delegates and
    any exception (``PermissionDenied`` incl. ``ENTITLEMENT_REQUIRED`` /
    revoked/expired codes) propagates to the caller, preserving the
    exact pre-split behaviour. The provider's return value passes
    through unchanged.
    """
    provider = _HOOKS.get("entitlement_provider")
    if provider is None:
        raise PermissionDenied({"code": "ENTITLEMENT_REQUIRED"})
    return provider(
        consumer_tenant_id=consumer_tenant_id,
        asset_id=asset_id,
        provider_tenant_id=provider_tenant_id,
    )


# ---------------------------------------------------------------------------
# Ontology-based search query expansion
# ---------------------------------------------------------------------------
def set_ontology_expansion_provider(provider: Callable[..., Any]) -> None:
    """Register the tenant-ontology graph builder (paid semantic app)."""
    _HOOKS["ontology_expansion_provider"] = provider


def get_ontology_expansion_provider() -> Callable[..., Any] | None:
    """Return the graph builder, or None in core-only mode (no expansion)."""
    return _HOOKS.get("ontology_expansion_provider")


# ---------------------------------------------------------------------------
# Semantic tombstone dispatch (asset retired / contract deleted / dataset
# archived / GDPR purge — fired from core signal handlers on transaction
# commit)
# ---------------------------------------------------------------------------
def set_tombstone_provider(provider: Callable[..., Any]) -> None:
    """Register the tombstone writer (paid semantic app)."""
    _HOOKS["tombstone_provider"] = provider


def dispatch_tombstone(*, resource_type: str, resource_id: Any, reason: str) -> Any:
    """Fire a tombstone event through the paid provider.

    No-op when no provider is registered (OSS core-only): the platform
    lifecycle signals still run, but no triple-store tombstone exists to
    write.
    """
    provider = _HOOKS.get("tombstone_provider")
    if provider is None:
        return None
    return provider(resource_type=resource_type, resource_id=resource_id, reason=reason)


# ---------------------------------------------------------------------------
# Order entitlement revocation (governance access-expiry cascade)
# ---------------------------------------------------------------------------
def set_order_entitlement_revoker(revoker: Callable[..., Any]) -> None:
    """Register the order-entitlement revocation function (paid marketplace)."""
    _HOOKS["order_entitlement_revoker"] = revoker


def revoke_order_entitlement(order: Any, reason: str) -> Any:
    """Revoke the marketplace entitlement tied to an order.

    No-op when no revoker is registered (OSS core-only): governance expiry
    still revokes the access request, but no marketplace entitlement exists.
    """
    revoker = _HOOKS.get("order_entitlement_revoker")
    if revoker is None:
        return None
    return revoker(order, reason=reason)


# ---------------------------------------------------------------------------
# Order approval / rejection finalization (governance cascades)
# ---------------------------------------------------------------------------
def set_order_approval_finalizer(provider: Callable[..., Any]) -> None:
    """Register the order-approval finalizer (paid marketplace app).

    The finalizer performs the REQUESTED-status check, ``order.approve()``,
    entitlement creation, and ``order.fulfill()`` — the full marketplace
    final-step cascade. Core-only mode has no provider and the cascade
    no-ops (the governance hook lookup yields no order to begin with).
    """
    _HOOKS["order_approval_finalizer"] = provider


def finalize_order_approval(*, order: Any, approved_by_user: Any) -> Any:
    """Finalize a marketplace order after a final-step governance approval."""
    provider = _HOOKS.get("order_approval_finalizer")
    if provider is None:
        return None
    return provider(order=order, approved_by_user=approved_by_user)


def set_order_rejection_finalizer(provider: Callable[..., Any]) -> None:
    """Register the order-rejection finalizer (paid marketplace app).

    The finalizer performs the REQUESTED-status check and
    ``order.reject()``. Core-only mode has no provider and the cascade
    no-ops.
    """
    _HOOKS["order_rejection_finalizer"] = provider


def finalize_order_rejection(*, order: Any, rejected_by_user: Any, reason: str) -> Any:
    """Finalize a marketplace order after a governance rejection."""
    provider = _HOOKS.get("order_rejection_finalizer")
    if provider is None:
        return None
    return provider(order=order, rejected_by_user=rejected_by_user, reason=reason)


# ---------------------------------------------------------------------------
# Marketplace listing cache invalidation (compliance signal on saves)
# ---------------------------------------------------------------------------
def set_listing_cache_invalidator(provider: Callable[..., Any]) -> None:
    """Register the listing-cache invalidator (paid marketplace app).

    The invalidator looks up every listing for an asset and busts its
    detail/list caches. Core-only mode has no provider and the call
    no-ops (no marketplace cache exists to invalidate).
    """
    _HOOKS["listing_cache_invalidator"] = provider


def invalidate_listing_caches_for_asset(asset_pk: Any) -> Any:
    """Bust marketplace listing caches for every listing of an asset."""
    provider = _HOOKS.get("listing_cache_invalidator")
    if provider is None:
        return None
    return provider(asset_pk)


# ---------------------------------------------------------------------------
# Sample-listing seeding (tenants seed-sample endpoint)
# ---------------------------------------------------------------------------
def set_sample_listing_seeder(provider: Callable[..., Any]) -> None:
    """Register the sample-listing seeder (paid marketplace app).

    The seeder idempotently creates the sample LISTING for a seeded
    sample asset and returns ``(listing, created)``. Core-only mode has
    no provider and the endpoint seeds the asset alone (``None``).
    """
    _HOOKS["sample_listing_seeder"] = provider


def seed_sample_listing(*, tenant_id: Any, asset: Any) -> Any:
    """Seed the sample listing for an asset; None in core-only mode."""
    provider = _HOOKS.get("sample_listing_seeder")
    if provider is None:
        return None
    return provider(tenant_id=tenant_id, asset=asset)


# ---------------------------------------------------------------------------
# File → asset link resolution (cross-tenant file access)
# ---------------------------------------------------------------------------
def set_file_asset_resolver(provider: Callable[..., Any]) -> None:
    """Register the file→asset link resolver (paid marketplace app).

    The resolver walks the dataset relationship to find the marketplace
    asset behind a file. Core-only mode has no provider: no marketplace
    asset links exist, and the cross-tenant probe is denied after audit.
    """
    _HOOKS["file_asset_resolver"] = provider


def get_file_asset_id(file_id: str) -> Any:
    """Resolve the marketplace asset id behind a file, or None."""
    provider = _HOOKS.get("file_asset_resolver")
    if provider is None:
        return None
    return provider(file_id)


# ---------------------------------------------------------------------------
# Payment-gateway listing (contracts ODPS endpoint)
# ---------------------------------------------------------------------------
def set_payment_gateway_lister(provider: Callable[..., Any]) -> None:
    """Register the payment-gateway lister (paid marketplace app).

    The lister returns the gateway dict configured in an ODPS contract.
    Core-only mode has no provider (no payment layer) and the endpoint
    returns an empty gateway list.
    """
    _HOOKS["payment_gateway_lister"] = provider


def list_payment_gateways_for_contract(*, tenant_id: Any, user_id: Any, contract_id: Any) -> Any:
    """List payment gateways for an ODPS contract; None in core-only mode."""
    provider = _HOOKS.get("payment_gateway_lister")
    if provider is None:
        return None
    return provider(tenant_id=tenant_id, user_id=user_id, contract_id=contract_id)


# ---------------------------------------------------------------------------
# ML-model attribute enrichment (ABAC resource attributes)
# ---------------------------------------------------------------------------
def set_ml_model_attributes_provider(provider: Callable[..., Any]) -> None:
    """Register the ML-model attribute provider (paid ml app).

    The provider returns the ABAC attribute dict for an ML_MODEL
    resource (empty dict when the model does not exist). Core-only mode
    has no provider: no ML models exist and no enrichment is added.
    """
    _HOOKS["ml_model_attributes_provider"] = provider


def get_ml_model_attributes(*, resource_id: Any, tenant_id: Any) -> Any:
    """Return ML-model ABAC attributes, or None in core-only mode."""
    provider = _HOOKS.get("ml_model_attributes_provider")
    if provider is None:
        return None
    return provider(resource_id=resource_id, tenant_id=tenant_id)


# ---------------------------------------------------------------------------
# Cross-tenant entitlement verification (tuple-returning variant)
# ---------------------------------------------------------------------------
def set_cross_tenant_entitlement_checker(provider: Callable[..., Any]) -> None:
    """Register the tuple-returning entitlement checker (paid marketplace).

    The provider returns ``(has_access, error_code, entitlement)``.
    Core-only mode FAILS CLOSED: ``(False, "ENTITLEMENT_REQUIRED", None)``
    — without the marketplace there are no cross-tenant entitlements,
    and unverifiable cross-tenant access must be denied.
    """
    _HOOKS["cross_tenant_entitlement_checker"] = provider


def check_cross_tenant_entitlement(
    *, consumer_tenant_id: Any, asset_id: Any, provider_tenant_id: Any
) -> tuple[bool, str | None, Any]:
    """Verify cross-tenant access; fail-closed in core-only mode."""
    provider = _HOOKS.get("cross_tenant_entitlement_checker")
    if provider is None:
        return False, "ENTITLEMENT_REQUIRED", None
    # The registry is untyped (``dict[str, Any]``) because it holds every
    # hook shape, so the provider's result arrives as ``Any``. Narrow it here
    # — at the one boundary where the paid layer's documented return contract
    # (``(has_access, error_code, entitlement)``) becomes a core-side type.
    return cast(
        "tuple[bool, str | None, Any]",
        provider(
            consumer_tenant_id=consumer_tenant_id,
            asset_id=asset_id,
            provider_tenant_id=provider_tenant_id,
        ),
    )


def get_entitlement_provider() -> Callable[..., Any] | None:
    """Return the registered entitlement enforcement provider, or None.

    ``check_entitlement`` itself fails CLOSED when no provider is
    registered (P3-1 — the ``ENTITLEMENT_REQUIRED`` refusal). Call
    sites that need to distinguish "no paid layer" from "no paywall"
    use this getter instead.
    """
    return _HOOKS.get("entitlement_provider")


# ---------------------------------------------------------------------------
# Billing onboarding signal (tenants onboarding completion)
# ---------------------------------------------------------------------------
def set_active_billing_setup_checker(provider: Callable[..., Any]) -> None:
    """Register the billing-setup checker (paid billing app).

    The provider returns True when a Subscription exists in an active
    billing state. Core-only mode has no billing layer, so the signal
    is vacuously satisfied (True) — onboarding must not deadlock on a
    capability that cannot exist.
    """
    _HOOKS["active_billing_setup_checker"] = provider


def has_active_billing_setup(tenant: Any) -> bool:
    """True when billing setup exists, or when no billing layer exists."""
    provider = _HOOKS.get("active_billing_setup_checker")
    if provider is None:
        return True
    return bool(provider(tenant))


# ---------------------------------------------------------------------------
# Stripe customer resolution (tax-id submission)
# ---------------------------------------------------------------------------
def set_stripe_customer_resolver(provider: Callable[..., Any]) -> None:
    """Register the stripe-customer-id resolver (paid billing app).

    The resolver walks the Subscription→Tenant chain. Core-only mode
    has no provider: None (the caller surfaces the structured
    "bootstrap not complete" error — Stripe never runs in core).
    """
    _HOOKS["stripe_customer_resolver"] = provider


def get_stripe_customer_id(tenant: Any) -> Any:
    """Resolve the Stripe customer id for a tenant, or None."""
    provider = _HOOKS.get("stripe_customer_resolver")
    if provider is None:
        return None
    return provider(tenant)


# ---------------------------------------------------------------------------
# Admin billing summary (platform admin dashboard)
# ---------------------------------------------------------------------------
def set_admin_billing_summary_provider(provider: Callable[..., Any]) -> None:
    """Register the admin billing-summary aggregator (paid billing app).

    The provider returns the subscription-counts + plan-distribution
    payload. Core-only mode returns the zeroed structure (no billing
    tables exist to aggregate).
    """
    _HOOKS["admin_billing_summary_provider"] = provider


def get_admin_billing_summary() -> dict[str, Any]:
    """Return the admin billing-summary payload (zeroed in core-only)."""
    provider = _HOOKS.get("admin_billing_summary_provider")
    if provider is None:
        return {
            "active": 0,
            "past_due": 0,
            "canceled": 0,
            "trial": 0,
            "incomplete": 0,
            "unpaid": 0,
            "plan_distribution": {"by_tier": {}, "total_active": 0},
        }
    # Narrow the untyped registry's ``Any`` to the payload shape the
    # core-only branch above already commits to.
    return cast("dict[str, Any]", provider())


# ---------------------------------------------------------------------------
# Order ownership check (audit involvement resolvers)
# ---------------------------------------------------------------------------
def set_order_owner_checker(provider: Callable[..., Any]) -> None:
    """Register the order-ownership checker (paid marketplace app).

    Core-only mode has no provider: no orders exist, so nobody owns one
    (False).
    """
    _HOOKS["order_owner_checker"] = provider


def is_order_owner(*, resource_id: Any, user: Any) -> bool:
    """Return True when *user* created the marketplace order."""
    provider = _HOOKS.get("order_owner_checker")
    if provider is None:
        return False
    return bool(provider(resource_id=resource_id, user=user))


# ---------------------------------------------------------------------------
# Plan downgrade validation (tenants self-serve plan endpoint)
# ---------------------------------------------------------------------------
def set_plan_downgrade_validator(provider: Callable[..., Any]) -> None:
    """Register the plan-downgrade validator (paid billing app).

    The validator returns a ``ValidationResult``. Core-only mode has no
    provider and the hook returns None — the contract is "None = valid"
    (no billing limits exist to violate).
    """
    _HOOKS["plan_downgrade_validator"] = provider


def validate_plan_downgrade(*, tenant_id: Any, new_plan: Any) -> Any:
    """Validate a plan downgrade; None (valid) in core-only mode."""
    provider = _HOOKS.get("plan_downgrade_validator")
    if provider is None:
        return None
    return provider(tenant_id=tenant_id, new_plan=new_plan)


# ---------------------------------------------------------------------------
# Service client factories (test helpers resolve real/mock clients without
# importing paid modules from core)
# ---------------------------------------------------------------------------
def set_subscription_factory(factory: Callable[..., Any]) -> None:
    """Register the subscription-creation factory (paid billing app).

    Core test helpers (testing.billing_support) delegate real subscription
    creation through this hook; core-only mode has no factory and the
    helper returns None (no billing in core).
    """
    _HOOKS["subscription_factory"] = factory


def get_subscription_factory() -> Callable[..., Any] | None:
    """Return the subscription factory, or None in core-only mode."""
    return _HOOKS.get("subscription_factory")


def set_semantic_mapper(provider: Callable[..., Any]) -> None:
    """Register the semantic mapping dispatcher (paid semantic app).

    The dispatcher receives (resource_type, **kwargs) and routes to
    map_asset_to_semantic / map_contract_to_semantic. Core-only mode has
    no mapper: map_via_semantic returns None and workflows keep their
    graceful-degrade contracts (mapping is non-critical by design).
    """
    _HOOKS["semantic_mapper"] = provider


def map_via_semantic(resource_type: str, **kwargs: Any) -> Any:
    """Map a resource to RDF through the paid mapper; None when absent."""
    provider = _HOOKS.get("semantic_mapper")
    if provider is None:
        return None
    return provider(resource_type=resource_type, **kwargs)


def set_access_request_order_provider(provider: Callable[..., Any]) -> None:
    """Register the access-request→order lookup (paid marketplace app).

    Core governance cascades (reject/revoke) resolve the linked order
    through this hook; core-only mode has no provider and the lookup
    returns None (no marketplace order exists to cascade to).
    """
    _HOOKS["access_request_order_provider"] = provider


def get_access_request_order(access_request: Any) -> Any:
    """Return the marketplace Order linked to an access request, or None."""
    provider = _HOOKS.get("access_request_order_provider")
    if provider is None:
        return None
    return provider(access_request)


# ---------------------------------------------------------------------------
# BaaS API-key tier resolution (Phase 313 paid-ward FK)
# ---------------------------------------------------------------------------
def set_api_key_tier_provider(provider: Callable[..., Any]) -> None:
    """Register the api-key→tier lookup (paid baas app).

    The tier link moved from the core auth APIKey onto the paid assignment
    table; core-only mode has no provider and the lookup returns None
    (no BaaS tiers exist there).
    """
    _HOOKS["api_key_tier_provider"] = provider


def get_api_key_tier(api_key: Any) -> Any:
    """Return the BaaS tier assigned to an auth APIKey, or None."""
    provider = _HOOKS.get("api_key_tier_provider")
    if provider is None:
        return None
    return provider(api_key)


def set_api_key_tier_setter(setter: Callable[..., Any]) -> None:
    """Register the api-key tier writer (paid baas app).

    Core-only mode has no setter: assigning a non-null tier raises, and
    assigning None is a no-op (no assignment row exists to clear).
    """
    _HOOKS["api_key_tier_setter"] = setter


def set_api_key_tier(api_key: Any, tier: Any) -> None:
    """Persist a BaaS tier assignment for an auth APIKey (paid baas app)."""
    setter = _HOOKS.get("api_key_tier_setter")
    if setter is None:
        if tier is not None:
            raise RuntimeError("BaaS API tier assignment is not available in core-only deployments")
        return
    setter(api_key, tier)


def set_api_key_tier_resolver(resolver: Callable[..., Any]) -> None:
    """Register the tier-name → tier lookup (paid baas app).

    The resolver raises ``LookupError`` for unknown tier names; core-only
    mode has no resolver (``resolve_api_key_tier`` returns None — no tiers
    exist there).
    """
    _HOOKS["api_key_tier_resolver"] = resolver


def resolve_api_key_tier(tier_name: str) -> Any:
    """Resolve a tier NAME to its tier object, or None in core-only mode."""
    resolver = _HOOKS.get("api_key_tier_resolver")
    if resolver is None:
        return None
    return resolver(tier_name)


def set_api_key_tier_filter(filter_fn: Callable[..., Any]) -> None:
    """Register the tier-name queryset filter (paid baas app)."""
    _HOOKS["api_key_tier_filter"] = filter_fn


def filter_api_keys_by_tier(queryset: Any, tier_name: str) -> Any:
    """Narrow an APIKey queryset to a tier name.

    Core-only mode has no tiers, so the filter returns an empty queryset
    (no key can carry a tier).
    """
    filter_fn = _HOOKS.get("api_key_tier_filter")
    if filter_fn is None:
        return queryset.none()
    return filter_fn(queryset, tier_name)


def set_product_creation_workflow(workflow_cls: Any) -> None:
    """Register the product-creation workflow class (paid marketplace app).

    The core contracts/product-creation view executes product creation
    through this hook; core-only mode has no workflow and the view returns
    a structured "feature not available" response.
    """
    _HOOKS["product_creation_workflow"] = workflow_cls


def get_product_creation_workflow() -> Any:
    """Return the registered workflow class, or None in core-only mode."""
    return _HOOKS.get("product_creation_workflow")


def register_service_client_factory(name: str, factory: Callable[..., Any]) -> None:
    """Register a service-client factory (paid apps, e.g. "SEMANTIC")."""
    _SERVICE_CLIENT_FACTORIES[name] = factory


def get_service_client_factory(name: str) -> Callable[..., Any] | None:
    """Return the factory for ``name`` or None in core-only mode."""
    return _SERVICE_CLIENT_FACTORIES.get(name)


# ── W10.3 (round-3 re-audit) — virtual-dataset SPARQL validation seam ─
# The W1.15 fix routed virtualization's three SPARQL paths through a
# hook of this name; a later refactor dropped it and the W1.15 pins
# went RED (SERVICE/GRAPH payloads passed every path).  The paid
# semantic app registers the canonical ``validate_sparql_query`` (the
# tenant federation allowlist + SSRF re-validation) for the SERVICE
# clause; GRAPH is rejected in EVERY mode (no allowlist exists for
# named-graph reads), and the unregistered default FAILS CLOSED.

def register_virtual_dataset_sparql_validator(validator: Callable[..., Any]) -> None:
    """Register the paid SPARQL validator (semantic's
    ``validate_sparql_query`` wrapper) from the app's ``ready()``."""
    _HOOKS["virtual_dataset_sparql_validator"] = validator


def validate_virtual_dataset_sparql(*, query: str, tenant_id: str | None) -> None:
    """Validate a virtual-dataset SPARQL payload.  Raises
    ``hub.apps.core.services.base.ValidationError`` with the pinned
    codes (``SPARQL_GRAPH_NOT_ALLOWED`` /
    ``SPARQL_FEDERATION_NOT_ALLOWED``) when rejected; returns None when
    allowed.  Core-only (unregistered) mode fails closed on SERVICE."""
    import re as _re

    from hub.apps.core.services.base import ValidationError as _ValidationError

    query_upper = query.upper()
    if _re.search(r"\bGRAPH\b", query_upper):
        raise _ValidationError(
            "Named-graph (GRAPH) reads are not allowed for virtual datasets",
            code="SPARQL_GRAPH_NOT_ALLOWED",
        )
    if not _re.search(r"\bSERVICE\b", query_upper):
        return None
    validator = _HOOKS.get("virtual_dataset_sparql_validator")
    if validator is not None:
        result = validator(query=query, tenant_id=tenant_id)
        if result and not result.get("valid"):
            raise _ValidationError(
                result.get("error") or "SPARQL query rejected",
                code=result.get("code") or "INVALID_SPARQL_QUERY",
            )
        return None
    raise _ValidationError(
        "SPARQL federation (SERVICE) is not allowed for virtual datasets",
        code="SPARQL_FEDERATION_NOT_ALLOWED",
    )
