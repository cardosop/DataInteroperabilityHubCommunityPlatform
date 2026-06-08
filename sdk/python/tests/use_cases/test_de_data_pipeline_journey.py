"""
Phase 279.H.8 — SDK DE persona journey mirror tests.

SDK-side equivalents of the CLI journey tests in
``cli/tests/use_cases/test_de_data_pipeline_journey.py``.  Requires ``DATAHUB_BASE_URL``
and ``DATAHUB_API_TOKEN`` env vars.  All tests skip when no
backend is detected.

Usage:
  DATAHUB_BASE_URL=http://localhost:8000/api/v1 \
  DATAHUB_API_TOKEN=<token> \
  pytest sdk/python/tests/use_cases/test_de_data_pipeline_journey.py -v
"""
import os

import pytest

DATAHUB_BASE_URL = os.environ.get("DATAHUB_BASE_URL", "")
def _api_token():
    return os.environ.get("DATAHUB_API_TOKEN") or os.environ.get("TEST_API_KEY") or os.environ.get("DATAHUB_API_KEY") or ""


def _backend_available():
    # Use the shared conftest helper which checks the correct /health/
    # path and honours API_TEST_PORT / MESHANT_API_URL env vars.
    from tests.conftest import is_api_available
    return is_api_available()


BACKEND_AVAILABLE = _backend_available()
requires_backend = pytest.mark.skipif(
    not BACKEND_AVAILABLE,
    reason="No backend detected — set DATAHUB_BASE_URL + DATAHUB_API_TOKEN",
)


@pytest.mark.asyncio
@pytest.mark.integration
@requires_backend
class TestSDKDEJourney:
    """SDK DE persona journey."""

    async def test_sdk_client_creation(self):
        """SDK client can be instantiated with the backend URL."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig
        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            assert client is not None

    async def test_datasets_list(self):
        """SDK ``datasets.list_datasets()`` returns valid response."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig
        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            data = await client.datasets.list_datasets()
            assert data is not None

    async def test_contracts_list(self):
        """SDK ``contracts.list_contracts()`` returns valid response."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig
        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            data = await client.contracts.list()
            assert data is not None

    async def test_assets_list(self):
        """SDK ``assets.list_assets()`` returns valid response."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig
        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            data = await client.assets.list_assets()
            assert data is not None
