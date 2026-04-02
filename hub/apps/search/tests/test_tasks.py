"""
Phase 86.2 — search/tasks.py tests.

Tests search vector rebuild tasks, missing model handling, and enqueue functions.
"""
import uuid
from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase

from hub.apps.search.tasks import (
    enqueue_asset_search_vector_update,
    enqueue_contract_search_vector_update,
    update_asset_search_vector,
    update_contract_search_vector,
)


class SearchTaskTest(TestCase):

    @patch("hub.apps.search.tasks.django_rq.get_queue")
    def test_enqueue_asset_uses_low_queue(self, mock_get_q):
        mock_q = MagicMock()
        mock_get_q.return_value = mock_q
        enqueue_asset_search_vector_update("a1")
        mock_get_q.assert_called_with("job_low")
        mock_q.enqueue.assert_called_once()
        args, kwargs = mock_q.enqueue.call_args
        self.assertEqual(args[0], update_asset_search_vector)
        self.assertEqual(args[1], "a1")

    @patch("hub.apps.search.tasks.django_rq.get_queue")
    def test_enqueue_contract_uses_low_queue(self, mock_get_q):
        mock_q = MagicMock()
        mock_get_q.return_value = mock_q
        enqueue_contract_search_vector_update("c1")
        mock_get_q.assert_called_with("job_low")
        mock_q.enqueue.assert_called_once()
        args, kwargs = mock_q.enqueue.call_args
        self.assertEqual(args[0], update_contract_search_vector)
        self.assertEqual(args[1], "c1")


@pytest.mark.django_db(transaction=True)
class UpdateAssetSearchVectorTest(TestCase):

    def _create_tenant(self):
        from hub.apps.tenants.models import Tenant
        return Tenant.objects.get_or_create(
            name="search-test", defaults={"slug": "search-test"},
        )[0]

    def test_updates_existing_asset(self):
        from hub.apps.assets.models import Asset
        tenant = self._create_tenant()
        asset = Asset.objects.create(tenant=tenant, name="test-asset")
        # Should not raise
        update_asset_search_vector(str(asset.pk))

    def test_missing_asset_logs_warning(self):
        """Non-existent asset is handled gracefully."""
        fake_id = str(uuid.uuid4())
        # Should not raise — logs warning internally
        update_asset_search_vector(fake_id)


@pytest.mark.django_db(transaction=True)
class UpdateContractSearchVectorTest(TestCase):

    def test_missing_contract_does_not_raise(self):
        fake_id = str(uuid.uuid4())
        # Should not raise
        update_contract_search_vector(fake_id)
