"""P.2a — the paid↔core seam proven LIVE, not merely degradable.

Phase 313/313-H pinned the core-only direction exhaustively: with no
provider registered, every commercial hook degrades through a documented
no-op/fail-open default, and 14 boundary modules prove it. The inverse
direction — "in a full paid process, is every hook slot actually populated
by the paid provider?" — had exactly ONE assertion repo-wide
(virtualization's SPARQL factory check). A ``set_*`` call deleted from any
paid ``AppConfig.ready()`` was caught by nothing, and three fallbacks are
fail-open (``check_entitlement`` → allow, ``has_active_billing_setup`` →
True, ``validate_plan_downgrade`` → valid), so a dropped registration
silently removes the paywall in production.

This module pins the full-mode shape:

- GREEN — every registry slot declared in ``HOOK_API_CONTRACT`` is
  populated, and each provider's module is a ``hub.apps.*`` module other
  than ``commercial_hooks`` itself (a future "core registers a default"
  refactor fails here). Slots are enumerated FROM the contract table — no
  second hand-maintained list that can drift.
- RED — the same helper, run inside ``hooks_snapshot()`` + ``reset_hooks()``,
  must report EVERY slot missing. This is guard-the-guard discipline: the
  check is proven to fail exactly in the dropped-registration scenario.

The module skips (not passes) under ``HUB_CORE_ONLY=1`` — there are no paid
providers to assert and a vacuous pass would be worse than no test.

This also absorbs the lone pre-existing liveness assertion
(``virtualization/tests/test_core_mode_boundaries.py``'s SPARQL factory
check): the factory registry is asserted here, next to the rest of the
seam, and the virtualization test's full-mode half keeps its degradation
focus.
"""

from __future__ import annotations

import pytest

from hub.apps.core import commercial_hooks
from hub.apps.manifest import is_core_only

pytestmark = pytest.mark.skipif(
    is_core_only(),
    reason="paid providers register only in full mode (no paid apps installed)",
)

#: A row in HOOK_API_CONTRACT is (function_name, param_spec, setter_pair,
#: registry_key). Setter rows carry their registry_key with setter_pair=None;
#: utility rows and the runtime-keyed service-factory rows carry None. The
#: paid-populated slots are therefore exactly: registry_key is not None AND
#: setter_pair is None.


def _provider_slots() -> dict[str, str]:
    """Map contract registry_key → setter function name (single source)."""
    return {
        row[3]: row[0]
        for row in commercial_hooks.HOOK_API_CONTRACT
        if row[3] is not None and row[2] is None
    }


def _missing_provider_slots() -> list[str]:
    """Return the contract slots with NO registered provider in this process."""
    return [slot for slot in _provider_slots() if commercial_hooks._HOOKS.get(slot) is None]


def _non_paid_module_slots() -> list[str]:
    """Slots populated by something that is not a paid-app module.

    Core never registers defaults into ``_HOOKS`` (fallbacks are inline in
    the callers), so any populated slot with a module outside ``hub.apps.*``
    — or inside ``commercial_hooks`` itself — is a boundary violation.
    """
    violations = []
    for slot in _provider_slots():
        provider = commercial_hooks._HOOKS.get(slot)
        if provider is None:
            continue
        module = getattr(provider, "__module__", "")
        if not module.startswith("hub.apps.") or module == commercial_hooks.__name__:
            violations.append(f"{slot}: {module or type(provider).__name__}")
    return violations


class TestFullModeProviderCoverage:
    """Every contract slot is populated by a paid provider in full mode."""

    def test_all_contract_slots_are_populated(self):
        missing = _missing_provider_slots()
        assert not missing, (
            "Full paid mode must register a provider for every contract slot. "
            "These slots are empty — a deleted/renamed set_* call in a paid "
            f"AppConfig.ready() is the usual cause: {sorted(missing)}"
        )

    def test_every_provider_comes_from_a_paid_hub_module(self):
        violations = _non_paid_module_slots()
        assert not violations, (
            "Every registered provider must live in a hub.apps.* module other "
            "than commercial_hooks itself (core never registers defaults — "
            f"fallbacks are inline in the callers). Violations: {violations}"
        )

    def test_semantic_service_client_factory_is_registered(self):
        """Absorbed from test_core_mode_boundaries.py:124-126 (P.2a)."""
        assert commercial_hooks.get_service_client_factory("SEMANTIC") is not None

    # ── RED drill: the check must fail exactly in the dropped-registration
    # scenario, otherwise the GREEN assertions are unfalsifiable. ──────────

    def test_missing_slots_helper_reports_every_slot_when_hooks_reset(self):
        """Guard-the-guard: with all registrations wiped, NO slot is missed."""
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            missing = _missing_provider_slots()
        assert set(missing) == set(_provider_slots()), (
            "hooks_snapshot()+reset_hooks() simulates every paid ready() being "
            "dropped; the helper must report EVERY contract slot missing, or "
            "the GREEN test could not detect a real dropped registration."
        )

    def test_non_paid_module_helper_flags_a_core_registered_provider(self):
        """Guard-the-guard for the module-boundary check (synthetic site)."""

        def fake_provider():
            return None

        fake_provider.__module__ = "hub.apps.core.commercial_hooks"
        slot = next(iter(_provider_slots()))
        with commercial_hooks.hooks_snapshot():
            commercial_hooks._HOOKS[slot] = fake_provider
            violations = _non_paid_module_slots()
        assert slot in {v.split(":")[0] for v in violations}
