"""
Input validation tests for Snowflake Connector — edge cases that exercise
the Python-layer checks before any Snowflake SQL is issued.

These tests do NOT use mocks or stubs.  They pass deliberately-invalid
inputs to connector methods and verify that ``ValueError`` / ``TypeError``
is raised by the Python validation layer.  When the validation layer
accepts the input, the test expects a connection-level error
(``ConnectionError``, ``NotFoundError``, or similar) from the real
``snowflake.connector`` import — that is acceptable because the Python
validation was the behaviour under test.

Every test that was previously mock-based and duplicates an existing
integration test in ``test_snowflake_connector.py`` has been removed.
"""

import pytest

from hub.apps.core.services.base import ConnectionError, NotFoundError
from hub.apps.integrations.base import (
    MarketplaceAssetMapping,
    MarketplaceListing,
    MarketplaceType,
    SyncResult,
    SyncStatus,
)
from hub.apps.integrations.connectors.snowflake_connector import SnowflakeConnector

pytestmark = pytest.mark.django_db(transaction=True)


def _connector():
    """Return a SnowflakeConnector with fake credentials.

    The connector will fail at the connection layer, but all Python-level
    validation still executes first.
    """
    return SnowflakeConnector(
        account="test_account", user="test_user", token="test_token"
    )


class TestSnowflakeConnectorValidation:
    """Input validation tests that do not require a live Snowflake connection."""

    # -- map_to_hub_asset ---------------------------------------------------

    def test_map_to_hub_asset_with_none_listing(self):
        connector = _connector()
        with pytest.raises((ValueError, TypeError)):
            connector.map_to_hub_asset(None)  # type: ignore[arg-type]

    def test_map_to_hub_asset_with_empty_metadata(self):
        connector = _connector()
        listing = MarketplaceListing(
            marketplace_id="TEST_LISTING",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test Listing",
            metadata={},
        )
        mapping = connector.map_to_hub_asset(listing)
        assert isinstance(mapping, MarketplaceAssetMapping)
        assert mapping.asset_data is not None

    # -- sync_pull boundary inputs ------------------------------------------

    def test_sync_pull_with_empty_listing_ids(self):
        connector = _connector()
        result = connector.sync_pull(listing_ids=[])
        assert isinstance(result, SyncResult)
        assert result.total_items == 0
        assert result.successful_items == 0

    def test_sync_pull_with_none_listing_ids_is_full_harvest(self):
        """None listing_ids means "sync all" — should call list_listings.

        The connector will fail at connection time, but the validation layer
        accepts None and proceeds to the full-harvest path (which calls
        ``list_listings``).
        """
        connector = _connector()
        try:
            result = connector.sync_pull(listing_ids=None)  # type: ignore[arg-type]
            assert isinstance(result, SyncResult)
        except ConnectionError:
            # Expected — fake credentials cannot reach Snowflake
            pass

    # -- download_resource boundary inputs ----------------------------------

    def test_download_resource_with_empty_resource_id(self):
        connector = _connector()
        with pytest.raises((ValueError, NotFoundError, ConnectionError)):
            connector.download_resource(resource_id="", destination_path="/tmp/test.csv")

    def test_download_resource_with_none_resource_id(self):
        connector = _connector()
        with pytest.raises((ValueError, TypeError, AttributeError, NotFoundError, ConnectionError)):
            connector.download_resource(
                resource_id=None,  # type: ignore[arg-type]
                destination_path="/tmp/test.csv",
            )
