"""P0-4 (close-oss-release-conditions) — the probe-creator seam.

Registry inversion for the IDOR probe engine (``idor_synthesis.py``):
the W11.3 synthesis table covers tenant-scoped models across every app.
Its ONLY estate coupling is the ``DatabricksWorkspace`` probe creator,
and its paid-model couplings (billing/marketplace/ml/baas object
factories) follow the SAME inversion — the creators live WITH their
owning apps (``hub.apps/<paid>/idor_probe_creators.py``) and register
at app-ready (the W4.6 owning-app convention, same shape as
``hub/apps/jobs/estate_handlers.py``). This module defines the consumer
side only; the estate registers its creator from
``hub.apps.databricks_admin/e2e_tooling/idor_probe_fixtures.py``.

Unregistered → ``get_probe_creator`` returns None — the W4.6 default: a
core-only process never installs the paid apps, so their models are
absent from the app registry and the key is never consulted there.
When the app IS installed but registration is missing, the synthesis
wrapper raises the classified ``ProbeCreatorUnregistered`` — loud,
never a silent generic fallback.

This module imports only stdlib — it must stay bare-importable without
``django.setup()`` (the W4.6 standalone-pin contract).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


class ProbeCreatorUnregistered(LookupError):
    """Raised when the synthesis engine asks for a probe creator that no
    owning app registered (an app-installed process whose ``ready()``
    registration is missing)."""


class EstateProbeCreatorUnregistered(ProbeCreatorUnregistered):
    """The estate-specific refusal shape (kept for the W4.6 pins and the
    databricks_admin fixture's exception handling)."""


#: A probe creator constructs one real tenant-scoped row: (tenant, user) -> obj.
ProbeCreator = Callable[[Any, Any], Any]

_registered_creators: dict[str, ProbeCreator] = {}
_registry_lock = threading.Lock()


def register_probe_creator(model_key: str, creator: ProbeCreator) -> None:
    """Register an owning-app probe creator under its synthesis key
    (``"billing.Subscription"``-shaped). Idempotent — ``ready()`` may run
    more than once per process."""
    with _registry_lock:
        _registered_creators[model_key] = creator


def get_probe_creator(model_key: str) -> ProbeCreator | None:
    """The registered creator for a model key, or None when no owning
    app registered one."""
    with _registry_lock:
        return _registered_creators.get(model_key)


# ── Estate aliases (W4.6 shape; the estate fixture and its pins use
#    these names) ────────────────────────────────────────────────────
EstateProbeCreator = ProbeCreator


def register_estate_probe_creator(model_key: str, creator: ProbeCreator) -> None:
    """Register a provider estate probe creator under its synthesis key
    (``"databricks_admin.DatabricksWorkspace"``-shaped)."""
    register_probe_creator(model_key, creator)


def get_estate_probe_creator(model_key: str) -> ProbeCreator | None:
    """The registered creator for a model key, or None when no provider
    registered one."""
    return get_probe_creator(model_key)
