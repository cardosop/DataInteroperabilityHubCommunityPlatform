"""P0.6 (openspec add-databricks-control-plane) + W4.6 (openspec
oss-release-remediation, G1) — the provider-agnostic M2M token-cache seam.

The real OAuth-M2M token cache (``M2MTokenCache``) is provider estate
code — it lives in ``hub.apps.databricks_admin.token_cache``, and the
provider-boundary contract (CLAUDE.md) forbids importing estate modules
from provider-agnostic consumers. Two consumers need the DEFAULT cache
without importing it: the dlt movement credential bridge
(``hub.data_movement.dlt_credentials``) and the transformation
credential resolver (``hub.apps.transformation.credential_resolver``
— the Appendix B "dbt adapter + introspection" row). Both therefore
ride the same registry inversion as the 7.5 cost-recording seam: this
module defines the consumer side only; ``databricks_admin`` registers
its cache factory at app-ready. A future provider estate (Snowflake,
...) registers its own factory the same way — the seam is homed here
once, never duplicated per provider.

Unregistered = NO default cache (``None``): the consumers treat the
cache as best-effort by contract — a missing cache skips the read/write
with a warning and the bearer still resolves through the production
exchange (the Phase 273 discipline — a cache outage never blocks the
movement).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

#: The cache protocol the consumers rely on — the token VALUE is never
#: logged anywhere; keys hash the credential identity (the estate
#: cache's own contract).
TokenCacheLike = Any  # get(workspace_key, credential_ref) / set(...)

#: A factory builds the provider's default cache (no args).
TokenCacheFactory = Callable[[], TokenCacheLike]

#: A one-slot registry: the most recent factory owns the default
#: (a re-registration — importlib reloads, test setups — invalidates the
#: cached instance). List-held so the slot mutates without ``global``.
_registered_factory: list[TokenCacheFactory] = []
_cached_instance: list[TokenCacheLike] = []
_registry_lock = threading.Lock()


def register_m2m_token_cache_factory(factory: TokenCacheFactory) -> None:
    """Register the provider's real token-cache factory. Idempotent —
    ``ready()`` may run more than once per process; a re-registration
    invalidates the cached instance (importlib reloads, test setups)."""
    with _registry_lock:
        _registered_factory[:] = [factory]
        _cached_instance[:] = []


def default_m2m_token_cache() -> TokenCacheLike | None:
    """The provider's default token cache — built lazily ONCE per
    registration, or ``None`` when no provider registered one (the
    best-effort no-cache mode)."""
    with _registry_lock:
        if not _registered_factory:
            return None
        if not _cached_instance:
            _cached_instance.append(_registered_factory[0]())
        return _cached_instance[0]
