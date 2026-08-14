"""Phase 313.1 — commercial-layer hooks (core-owned, paid-registered).

Core owns the call sites; the paid layer registers providers from its
``AppConfig.ready()``. Every hook has a no-op default so core-only mode is
well-defined:

- entitlement check → **fail open** (OSS deployments have no paywall);
  the paid marketplace registers ``require_entitlement`` and its
  ``PermissionDenied`` semantics propagate unchanged;
- tenant SPARQL endpoint routes → absent (semantic registers the view);
- ontology-based query expansion → no expansion (semantic registers the
  graph builder; search returns no bridges when no provider exists);
- tombstones → no-op (semantic registers the tombstone writer);
- order entitlement revocation → no-op (marketplace registers the revoker);
- service client factories → absent (test helpers fall back to mocks).

State lives in a module-level dict so providers register without ``global``
statements; ``reset_hooks()`` exists for tests and reloads.

Pure module — no Django imports — so standalone scripts and tests can use it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

# Tombstone reason constants — core-owned so core signal handlers reference
# them without importing the paid semantic app. semantic/tombstone.py keeps
# its own definitions for compatibility.
REASON_ASSET_RETIRED = "asset_retired"
REASON_CONTRACT_DELETED = "contract_deleted"
REASON_DATASET_ARCHIVED = "dataset_archived"
REASON_GDPR_PURGE = "gdpr_purge"

_HOOKS: dict[str, Any] = {}
_SERVICE_CLIENT_FACTORIES: dict[str, Any] = {}


def reset_hooks() -> None:
    """Clear every registration (tests, reloads). Core-only defaults restored."""
    _HOOKS.clear()
    _SERVICE_CLIENT_FACTORIES.clear()


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


def check_entitlement(
    *, consumer_tenant_id: str, asset_id: str, provider_tenant_id: str
) -> Any:
    """Enforce marketplace entitlement for cross-tenant asset access.

    Fail-open contract: with no provider registered (OSS core-only), this
    returns None and access proceeds — the OSS build has no paywall. With a
    provider, it delegates and any exception (``PermissionDenied`` incl.
    ``ENTITLEMENT_REQUIRED``/revoked/expired codes) propagates to the caller,
    preserving the exact pre-split behaviour. The provider's return value
    passes through unchanged.
    """
    provider = _HOOKS.get("entitlement_provider")
    if provider is None:
        return None
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
    return provider(
        resource_type=resource_type, resource_id=resource_id, reason=reason
    )


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
