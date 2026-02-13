"""
Phase 26 SDK Integration Tests

Tests for new SDK methods: scheduled export, billing, tenants, GDPR.

All tests use real backend API - no mocks/stubs.
"""

import asyncio
import os
from typing import Any, Dict

import pytest

from datahub_interoperability import DataHubClient, DataHubClientConfig

pytestmark = [
    pytest.mark.integration,
    pytest.mark.cli_sdk,
]

# Test configuration
HUB_BASE_URL = os.getenv("HUB_BASE_URL", "http://localhost:8000/api/v1")
API_KEY = os.getenv("DATAHUB_API_KEY", "")


@pytest.fixture(scope="module")
def client():
    """Create SDK client for testing"""
    if not API_KEY:
        pytest.skip("DATAHUB_API_KEY not set")

    config = DataHubClientConfig(base_url=HUB_BASE_URL, api_token=API_KEY)
    return DataHubClient(config)


@pytest.mark.asyncio
class TestScheduledExportSDK:
    """Test scheduled export SDK methods"""

    async def test_list_scheduled_exports(self, client):
        """Test listing scheduled exports"""
        result = await client.scheduled_export.list()
        assert isinstance(result, dict)
        # Should have results or be empty
        assert "results" in result or isinstance(result.get("results"), list)

    async def test_get_scheduled_export(self, client):
        """Test getting scheduled export"""
        # Requires existing export ID
        pytest.skip("Requires test data setup")


@pytest.mark.asyncio
class TestBillingSDK:
    """Test billing SDK methods (Phase 25)"""

    async def test_get_subscription(self, client):
        """Test getting subscription"""
        from datahub_interoperability.errors import NotFoundError, ServerError

        try:
            result = await client.billing.get_subscription()
            assert isinstance(result, dict)
            # Should have subscription fields if subscription exists
            assert "id" in result or "status" in result
        except (NotFoundError, ServerError) as e:
            # Expected when no subscription exists (404)
            error_msg = str(e).lower()
            assert "not found" in error_msg or "404" in error_msg or "no subscription" in error_msg
        except Exception as e:
            # Other exceptions should be re-raised
            raise

    async def test_list_invoices(self, client):
        """Test listing invoices"""
        result = await client.billing.list_invoices()
        assert isinstance(result, dict)
        assert "results" in result or isinstance(result.get("results"), list)


@pytest.mark.asyncio
class TestTenantsSDK:
    """Test tenants SDK methods (Phase 25)"""

    async def test_get_usage(self, client):
        """Test getting tenant usage"""
        result = await client.tenants.get_usage()
        assert isinstance(result, dict)
        # Should have usage metrics
        assert "asset_count" in result or "plan_limits" in result


@pytest.mark.asyncio
class TestGDPRSDK:
    """Test GDPR SDK methods (Phase 25)"""

    async def test_list_export_jobs(self, client):
        """Test listing export jobs"""
        result = await client.gdpr.list_export_jobs()
        assert isinstance(result, dict)
        assert "results" in result or isinstance(result.get("results"), list)

    async def test_list_erasure_requests(self, client):
        """Test listing erasure requests"""
        result = await client.gdpr.list_erasure_requests()
        assert isinstance(result, dict)
        assert "results" in result or isinstance(result.get("results"), list)
