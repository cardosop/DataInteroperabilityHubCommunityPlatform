"""
Phase 20 — Integration tests vs real PostgreSQL.

Re-exports hub virtualization real source tests so they run when executing
tests/integration/ with real_virtualization_e2e marker.
Uses real PostgreSQL (no mocks/stubs). See docs/runbooks/REAL_VIRTUALIZATION_E2E.md.
"""

from hub.apps.virtualization.tests.test_real_source_integration import (
    RealPostgreSQLSourceIntegrationTest,
    RealRESTSourceIntegrationTest,
    RealSPARQLSourceIntegrationTest,
)

__all__ = [
    "RealPostgreSQLSourceIntegrationTest",
    "RealRESTSourceIntegrationTest",
    "RealSPARQLSourceIntegrationTest",
]
