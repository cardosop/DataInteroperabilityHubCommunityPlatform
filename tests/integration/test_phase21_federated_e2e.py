"""
Phase 21 — Virtualization Federated Asset E2E integration tests.

Re-exports hub virtualization federated asset E2E tests so they run when executing
tests/integration/ with real_virtualization_e2e marker.
Uses real demo.ckan.org (no mocks/stubs). See docs/runbooks/REAL_VIRTUALIZATION_E2E.md.
"""

from hub.apps.virtualization.tests.test_virtualization_real_federated_e2e import (
    VirtualizationFederatedAssetE2ETest,
)

__all__ = ["VirtualizationFederatedAssetE2ETest"]
