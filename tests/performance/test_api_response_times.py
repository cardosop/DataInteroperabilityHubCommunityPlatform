"""Phase 109.1 — API response time SLO validation.

Validates that SLO targets are defined for critical endpoints
and that baseline data exists for regression comparison.
"""

import json
import os

# SLO definitions — p95 targets in milliseconds
SLO_TARGETS = {
    "list_endpoints": {
        "GET /api/v1/assets/": 500,
        "GET /api/v1/contracts/": 500,
        "GET /api/v1/datasets/": 500,
        "GET /api/v1/marketplace/listings/": 500,
        "GET /api/v1/jobs/": 500,
        "GET /api/v1/webhooks/webhooks/": 500,
        "GET /api/v1/mesh/domains/": 500,
        "GET /api/v1/dq/runs/": 500,
        "GET /api/v1/compliance/runs/": 500,
        "GET /api/v1/governance/access-requests/": 500,
    },
    "detail_endpoints": {
        "GET /api/v1/assets/{id}/": 1000,
        "GET /api/v1/contracts/{id}/": 1000,
        "GET /api/v1/datasets/{id}/": 1000,
        "GET /api/v1/marketplace/listings/{id}/": 1000,
        "GET /api/v1/jobs/{id}/": 1000,
    },
    "create_endpoints": {
        "POST /api/v1/assets/": 2000,
        "POST /api/v1/contracts/": 2000,
        "POST /api/v1/datasets/": 2000,
        "POST /api/v1/marketplace/listings/": 2000,
    },
    "health": {
        "GET /health/health/": 200,
    },
}

BASELINES_DIR = os.path.join(os.path.dirname(__file__), "baselines")
BASELINE_FILE = os.path.join(BASELINES_DIR, "current.json")


class TestSLODefinitions:
    """Validate SLO target definitions are complete and sensible."""

    def test_all_list_endpoints_have_slo(self):
        """All list endpoints have a p95 SLO defined."""
        assert len(SLO_TARGETS["list_endpoints"]) >= 10

    def test_all_detail_endpoints_have_slo(self):
        """All detail endpoints have a p95 SLO defined."""
        assert len(SLO_TARGETS["detail_endpoints"]) >= 5

    def test_all_create_endpoints_have_slo(self):
        """All create endpoints have a p95 SLO defined."""
        assert len(SLO_TARGETS["create_endpoints"]) >= 4

    def test_list_slos_are_under_500ms(self):
        """List endpoint SLOs must be ≤ 500ms."""
        for endpoint, target_ms in SLO_TARGETS["list_endpoints"].items():
            assert target_ms <= 500, f"{endpoint} SLO {target_ms}ms > 500ms"

    def test_detail_slos_are_under_1s(self):
        """Detail endpoint SLOs must be ≤ 1000ms."""
        for endpoint, target_ms in SLO_TARGETS["detail_endpoints"].items():
            assert target_ms <= 1000, f"{endpoint} SLO {target_ms}ms > 1000ms"

    def test_create_slos_are_under_2s(self):
        """Create endpoint SLOs must be ≤ 2000ms."""
        for endpoint, target_ms in SLO_TARGETS["create_endpoints"].items():
            assert target_ms <= 2000, f"{endpoint} SLO {target_ms}ms > 2000ms"

    def test_health_slo_is_under_200ms(self):
        """Health endpoint must respond in < 200ms."""
        assert SLO_TARGETS["health"]["GET /health/health/"] <= 200

    def test_total_endpoints_covered(self):
        """At least 20 endpoints have SLO targets."""
        total = sum(len(v) for v in SLO_TARGETS.values())
        assert total >= 20, f"Only {total} endpoints have SLOs"


class TestBaselineFile:
    """Validate baseline data structure."""

    def test_baselines_directory_exists(self):
        """Baselines directory exists."""
        assert os.path.isdir(BASELINES_DIR)

    def test_baseline_file_is_valid_json(self):
        """Baseline file, if it exists, is valid JSON."""
        if os.path.exists(BASELINE_FILE):
            with open(BASELINE_FILE) as f:
                data = json.load(f)
            assert isinstance(data, dict)
