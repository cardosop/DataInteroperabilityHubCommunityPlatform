"""
Phase 279.H.8 — SDK PA persona journey mirror tests.

SDK-side equivalents of the CLI journey tests in
``cli/tests/use_cases/test_pa_admin_journey.py``.  Requires ``DATAHUB_BASE_URL``
and ``DATAHUB_API_TOKEN`` env vars.  All tests skip when no
backend is detected.

Usage:
  DATAHUB_BASE_URL=http://localhost:8000/api/v1 \
  DATAHUB_API_TOKEN=<token> \
  pytest sdk/python/tests/use_cases/test_pa_admin_journey.py -v
"""

import os

import pytest

pytestmark = [
    pytest.mark.journey("JOURNEY-PA-001"),
]

DATAHUB_BASE_URL = os.environ.get("DATAHUB_BASE_URL", "")


def _api_token():
    return (
        os.environ.get("DATAHUB_API_TOKEN")
        or os.environ.get("TEST_API_KEY")
        or os.environ.get("DATAHUB_API_KEY")
        or ""
    )


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
class TestSDKPAJourney:
    """SDK PA persona journey."""

    async def test_sdk_client_creation(self):
        """SDK client can be instantiated with the backend URL."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            assert client is not None

    async def test_tenants_list(self):
        """SDK platform ``list_tenants()`` returns valid response."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig
        from datahub_interoperability.platform import PlatformAPI

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            api = PlatformAPI(client)
            data = await api.list_tenants()
            assert data is not None

    async def test_users_list(self):
        """SDK platform ``list_users()`` returns valid response."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig
        from datahub_interoperability.platform import PlatformAPI

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            api = PlatformAPI(client)
            data = await api.list_users()
            assert data is not None

    async def test_capabilities_list(self):
        """SDK ``capabilities.list_capabilities()`` returns valid response."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig
        from datahub_interoperability.capabilities import CapabilitiesAPI

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            api = CapabilitiesAPI(client)
            data = await api.list_capabilities()
            assert data is not None
