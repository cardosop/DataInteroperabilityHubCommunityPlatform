"""W4.6 (openspec oss-release-remediation, G1) — TDD pins for the
provider-agnostic M2M token-cache seam.

No mocks: the REAL registry + facade. The ready()-wiring pin proves the
inversion end-to-end — after Django app population the estate's
``M2MTokenCache`` factory IS registered (a consumer with no injected
cache resolves the REAL cache). The stand-in pin uses a REAL dict-backed
cache implementation (the consumer contract is get/set — the
execution_targets "consumer-side stand-in" convention) and restores the
estate registration in ``finally`` so the process state is honest for
every later test (module-global registries persist across a batch).
The unregistered default (None) is pinned in
``scripts/tests/test_w46_provider_seams_standalone.py`` — under Django
the estate always registers at app-ready, so the unregistered state only
exists OUTSIDE a populated app registry.
"""

from __future__ import annotations

import pytest

from hub.apps.integrations.m2m_token_cache import (
    default_m2m_token_cache,
    register_m2m_token_cache_factory,
)

pytestmark = pytest.mark.django_db(transaction=True)

# P3-1: the ready()-wiring + lazy-singleton contracts are FULL-mode
# behaviors — in core-only mode the estate app never registers, so the
# unregistered default (None) is the CORRECT state and these tests'
# premises cannot hold. The core-mode default itself is pinned by
# scripts/tests/test_w46_provider_seams_standalone.py.
from hub.apps.manifest import is_core_only

_core_only_skip = pytest.mark.skipif(
    is_core_only(), reason="estate ready()-wiring requires the paid layer"
)


class DictTokenCache:
    """A real in-memory cache honoring the consumer contract (get/set)."""

    def __init__(self):
        self._store = {}

    def get(self, workspace_key: str, credential_ref: str) -> str | None:
        return self._store.get((workspace_key, credential_ref))

    def set(self, workspace_key: str, credential_ref: str, value: str) -> None:
        self._store[(workspace_key, credential_ref)] = value


def _restore_estate_factory():
    try:
        from hub.apps.databricks_admin.token_cache import M2MTokenCache
    except (RuntimeError, ModuleNotFoundError):
        pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

    register_m2m_token_cache_factory(M2MTokenCache)


class TestM2MTokenCacheSeam:
    @_core_only_skip
    def test_ready_wiring_registers_the_estate_factory(self):
        """After Django app population, the default cache resolves to the
        REAL estate M2MTokenCache — the inversion works end-to-end."""
        try:
            from hub.apps.databricks_admin.token_cache import M2MTokenCache
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

        cache = default_m2m_token_cache()
        assert cache is not None
        assert isinstance(cache, M2MTokenCache)

    @_core_only_skip
    def test_default_is_a_lazy_singleton(self):
        cache_a = default_m2m_token_cache()
        cache_b = default_m2m_token_cache()
        assert cache_a is not None
        assert cache_a is cache_b

    def test_registered_factory_supplies_the_default(self):
        """A provider registering its own factory owns the default (the
        future-provider contract) — restored to the estate afterward."""
        stand_in = DictTokenCache()
        try:
            register_m2m_token_cache_factory(lambda: stand_in)
            assert default_m2m_token_cache() is stand_in
        finally:
            _restore_estate_factory()

    def test_reregistration_invalidates_the_singleton(self):
        first = DictTokenCache()
        second = DictTokenCache()
        try:
            register_m2m_token_cache_factory(lambda: first)
            assert default_m2m_token_cache() is first
            register_m2m_token_cache_factory(lambda: second)
            assert default_m2m_token_cache() is second
        finally:
            _restore_estate_factory()
