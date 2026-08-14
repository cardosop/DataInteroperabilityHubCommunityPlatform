"""Phase 313.1.6 — commercial hook defaults (pure, no Django).

These lock the fail-open contract: core-only mode must behave exactly like
"no paid layer registered", and registered providers must be delegated to
without any core-side transformation of arguments or exceptions.
"""

from hub.apps.core import commercial_hooks


def _restore():
    commercial_hooks.reset_hooks()


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


def test_entitlement_fails_open_without_provider():
    """OSS core-only: no paywall — returns without touching the arguments."""
    _restore()
    result = commercial_hooks.check_entitlement(
        consumer_tenant_id="consumer",
        asset_id="asset",
        provider_tenant_id="provider",
    )
    assert result is None


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
        assert raised is not None and raised.args[0]["code"] == "ENTITLEMENT_REQUIRED"
    finally:
        _restore()


def test_ontology_expansion_defaults_to_none():
    _restore()
    assert commercial_hooks.get_ontology_expansion_provider() is None


def test_ontology_expansion_roundtrip():
    _restore()
    sentinel = lambda tenant_id: f"graph-{tenant_id}"  # noqa: E731
    try:
        commercial_hooks.set_ontology_expansion_provider(sentinel)
        assert commercial_hooks.get_ontology_expansion_provider()("t1") == "graph-t1"
    finally:
        _restore()
