"""
Performance tests for Versioning API.

Measures list endpoint latency. Uses real implementations - no mocks or stubs.
Versioning list requires resource_type and resource_id (asset UUID).
"""
import pytest

pytestmark = pytest.mark.slow

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract, OriginalFormat, OriginalSpecType
from tests.performance.performance_test_base import APIPerformanceTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.performance]


class VersioningAPIPerformanceTest(APIPerformanceTestBase):
    """Performance tests for /api/v1/versioning/versions/."""

    def setUp(self):
        """Create asset and contract for versioning list endpoint."""
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="perf-versioning-asset",
            name="Perf Versioning Asset",
            status="DRAFT",
        )
        Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            version=1,
            original_raw='{"info": {"name": "perf"}}',
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
        )

    def test_versions_list_p95_latency(self):
        """List versions endpoint P95 < 500ms."""
        url = (
            f"/api/v1/versioning/versions/"
            f"?resource_type=contract&resource_id={self.asset.id}"
        )
        self.assert_list_endpoint_p95(url)
