"""
Tests for warehouse signal handlers.

Verifies that LIVE_QUERY assets trigger search indexing on save
and that errors are handled gracefully.
"""

from unittest import mock

import pytest
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.warehouses.models import WarehouseConnection


@pytest.mark.django_db(transaction=True)
class LiveQueryAssetIndexSignalTests(TestCase):
    """Tests for the LIVE_QUERY asset post_save signal handler.

    The signal handler in ``hub.apps.warehouses.signals`` listens on
    ``post_save`` for sender ``assets.Asset`` and calls
    ``SearchIndexer.index_asset()`` for LIVE_QUERY strategy assets.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="signal-test-tenant",
            slug="signal-test-tenant",
        )
        self.connection = WarehouseConnection.objects.create(
            tenant=self.tenant,
            name="test-conn",
            warehouse_type="snowflake",
            config={"account": "test"},
        )

    @mock.patch("hub.apps.search.indexing.SearchIndexer")
    def test_index_called_for_live_query_asset(self, mock_indexer_class):
        """Saving a LIVE_QUERY asset triggers SearchIndexer.index_asset."""
        from hub.apps.assets.models import Asset, DataStrategy

        Asset.objects.create(
            tenant=self.tenant,
            name="test-asset",
            data_strategy=DataStrategy.LIVE_QUERY,
            warehouse_connection=self.connection,
        )
        # Signal fires on create.  SearchIndexer is called as
        # SearchIndexer.index_asset(instance) — static-style call.
        mock_indexer_class.index_asset.assert_called_once()

    @mock.patch("hub.apps.search.indexing.SearchIndexer")
    def test_index_not_called_for_non_live_query_asset(self, mock_indexer_class):
        """Saving a non-LIVE_QUERY asset does NOT trigger search indexing."""
        from hub.apps.assets.models import Asset, DataStrategy

        Asset.objects.create(
            tenant=self.tenant,
            name="batch-asset",
            data_strategy=DataStrategy.METADATA_ONLY,
            warehouse_connection=None,
        )
        mock_indexer_class.index_asset.assert_not_called()

    @mock.patch("hub.apps.search.indexing.SearchIndexer")
    def test_indexer_error_handled_gracefully(self, mock_indexer_class):
        """If SearchIndexer.index_asset raises, the asset save still succeeds."""
        from hub.apps.assets.models import Asset, DataStrategy

        mock_indexer_class.index_asset.side_effect = RuntimeError("search down")

        # Should not raise — signal handler catches exceptions
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="resilient-asset",
            data_strategy=DataStrategy.LIVE_QUERY,
            warehouse_connection=self.connection,
        )
        assert asset.id is not None
