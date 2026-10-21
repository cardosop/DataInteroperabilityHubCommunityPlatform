"""
Performance tests for Lineage API (contract lineage).

Measures lineage visualization endpoint latency. Uses real implementations - no mocks or stubs.
"""

import json

import pytest

pytestmark = pytest.mark.slow

from hub.apps.contracts.models import (
    Contract,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class LineageAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/contracts/{id}/lineage/visualization/."""

    def setUp(self):
        """Create minimal contract for lineage endpoint."""
        super().setUp()
        minimal_odcs = {
            "id": "perf-lineage-contract",
            "info": {"title": "Perf Test", "version": "1.0.0"},
            "schema": {"fields": []},
        }
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(minimal_odcs),
            hub_contract_json={"id": "perf-lineage-contract", "info": {}, "schema": {}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

    def test_lineage_visualization_p95_latency(self):
        """Lineage visualization endpoint P95 < 1000ms (graph computation)."""
        self.assert_list_endpoint_p95(
            f"/api/v1/contracts/{self.contract.id}/lineage/visualization/",
            target_ms=1000.0,
        )
