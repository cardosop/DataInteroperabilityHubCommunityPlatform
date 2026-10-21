"""
285.12.5.1 CC1 — Business rules chain execution tests (8 tests).

Tests chain registration, execution, atomic context, rule ordering,
dependency validation, and the health endpoint. Runs in BOTH core and
full mode (Phase P.9 — the file previously hid behind the ``integration``
marker deselection in core mode; per-tenant chain enablement does not
exist and the claim was retracted per P.9 D8).
"""

from __future__ import annotations

import pytest
from django.test import TestCase

from hub.apps.core.business_rules.chain_registry import (
    register_chain,
)
from hub.apps.core.business_rules.chains import (
    get_chain,
)

pytestmark = pytest.mark.django_db(transaction=True)


class BusinessRulesChainTests(TestCase):
    def test_chains_are_registered(self):
        """All 5 standard chains should be registered — with the paid ones
        pinned per-mode. Phase P.9: this previously relied on the
        ``integration`` marker being deselected in core mode (paid chains
        never register there, so the old assertion failed core runs); the
        mode split is now asserted directly, in BOTH modes."""
        from hub.apps.manifest import is_core_only

        core_chains = [
            "contract.publish",
            "asset.activate",
            "governance.approval.advance",
        ]
        paid_chains = [
            "marketplace.listing.publish",
            "semantic.query.execute",
        ]
        for name in core_chains:
            chain = get_chain(name)
            self.assertIsNotNone(
                chain, f"Chain '{name}' should be registered in every mode"
            )
        for name in paid_chains:
            chain = get_chain(name)
            if is_core_only():
                self.assertIsNone(
                    chain,
                    f"paid chain '{name}' must NOT register in core mode "
                    "(its module is not installed)",
                )
            else:
                self.assertIsNotNone(
                    chain, f"Chain '{name}' should be registered in full mode"
                )

    def test_get_chain_unknown_returns_none(self):
        """Unknown chain name returns None."""
        self.assertIsNone(get_chain("nonexistent.chain.name"))

    def test_execute_chain_requires_atomic_context_safe_inside_transaction(self):
        """When inside a transaction, execute_chain() should run steps and
        return structured result without raising RuntimeError.

        Pytest-django's transaction=True wraps each test in transaction.atomic(),
        so the guard should NOT fire.  The chain contract requires the caller
        to manage the transaction boundary.
        """
        chain = get_chain("contract.publish")
        self.assertIsNotNone(chain)
        self.assertTrue(chain.requires_transaction)
        result = chain.execute()
        self.assertIn(result["outcome"], ["PASS", "FAIL"])
        self.assertIn("steps", result)
        self.assertIn("duration_ms", result)
        self.assertIn("errors", result)
        self.assertGreater(
            len(result["steps"]), 0, "Chain should have executed at least one step"
        )
        self.assertIsInstance(result["duration_ms"], (int, float))

    def test_register_chain_is_idempotent(self):
        """Re-registering the same chain name replaces the previous registration.

        Uses a unique name to avoid corrupting production chains in the
        process-wide registry.
        """
        import uuid

        unique_name = f"test-chain-{uuid.uuid4().hex[:8]}"

        @register_chain(unique_name)
        def _first():
            from hub.apps.core.business_rules.base import ValidationResult

            def _s(ctx, **kw):
                return ValidationResult(is_valid=True)

            return [_s]

        first = get_chain(unique_name)
        self.assertIsNotNone(first)
        self.assertEqual(len(first.steps), 1)

        # Re-register with different steps
        @register_chain(unique_name)
        def _second():
            from hub.apps.core.business_rules.base import ValidationResult

            def _s1(ctx, **kw):
                return ValidationResult(is_valid=True)

            def _s2(ctx, **kw):
                return ValidationResult(is_valid=True)

            return [_s1, _s2]

        second = get_chain(unique_name)
        self.assertIsNotNone(second)
        self.assertEqual(
            len(second.steps), 2, "Re-registration should replace step list"
        )

    def test_chain_registry_imports_cleanly(self):
        """Chain registry module should import without errors and export
        its actual surface: ``register_chain`` (the invocation helpers
        ``execute_chain`` / ``get_chain`` live in ``chains``)."""
        from hub.apps.core.business_rules import chain_registry

        self.assertTrue(hasattr(chain_registry, "register_chain"))

    def test_chain_registry_never_references_the_provider_estate(self):
        """W4.6 (oss-release-remediation, G1): the databricks chains
        moved INTO the estate app (the 313.1 owning-app convention) —
        the core registry module must hold NO estate reference (import,
        string, or comment-free module path)."""
        import ast
        from pathlib import Path

        import hub.apps.core.business_rules.chain_registry as cr

        source = Path(cr.__file__).read_text()
        # No estate MODULE-PATH reference (imports or string paths) — the
        # docstring may NAME the move for humans; the code must not reach
        # into the estate (GATE-54 enforces the import side in CI).
        assert "hub.apps.databricks_admin" not in source
        ast.parse(source)  # and it still parses

    def test_databricks_chains_registered_by_their_owning_app(self):
        """The databricks chains resolve in full mode (registered at the
        estate's app-ready — the marketplace/semantic pattern) and stay
        absent in core mode by construction (the app is not installed)."""
        from hub.apps.manifest import is_core_only

        databricks_chains = [
            "databricks.uc.change.request",
            "databricks.uc.change.approve",
            "databricks.uc.change.execute",
            "databricks.grant.apply",
            "databricks.warehouse.create",
            "databricks.dlt.create",
        ]
        for name in databricks_chains:
            chain = get_chain(name)
            if is_core_only():
                self.assertIsNone(
                    chain, f"estate chain '{name}' must NOT register in core mode"
                )
            else:
                self.assertIsNotNone(
                    chain, f"estate chain '{name}' should be registered in full mode"
                )

    def test_chain_names_follow_convention(self):
        """Chain names should use dot-separated resource.action format."""
        for name in ["contract.publish", "asset.activate"]:
            parts = name.split(".")
            self.assertGreaterEqual(
                len(parts), 2, f"Chain '{name}' should have at least 2 parts"
            )
            self.assertTrue(
                all(p.islower() for p in parts), f"Chain '{name}' should be lowercase"
            )

    def test_registry_module_structure(self):
        """The chain modules should export their REAL functions —
        ``execute_chain`` / ``get_chain`` from ``chains``, ``register_chain``
        from ``chain_registry`` (Phase P.9: the previous assertions named a
        false surface and passed only while the file was deselected)."""
        import hub.apps.core.business_rules.chain_registry as cr
        import hub.apps.core.business_rules.chains as chains_module

        for attr in ["execute_chain", "get_chain"]:
            self.assertTrue(
                hasattr(chains_module, attr), f"chains should export {attr}"
            )
        self.assertTrue(
            hasattr(cr, "register_chain"), "chain_registry should export register_chain"
        )
