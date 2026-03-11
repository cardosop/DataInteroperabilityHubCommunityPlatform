"""
Phase 23 — Marketplace demo.ckan.org fixture integration tests.

Re-exports hub integrations fixture tests so they run when executing
tests/integration/ or integration batch 3.
Uses real demo.ckan.org PULL (no mocks/stubs).
See docs/runbooks/REAL_MARKETPLACE_E2E.md.
"""
import pytest

from hub.apps.integrations.tests.test_marketplace_demo_ckan_fixture import (
    MarketplaceDemoCkanFixtureTest,
)

pytestmark = [pytest.mark.integration]

__all__ = ["MarketplaceDemoCkanFixtureTest"]
