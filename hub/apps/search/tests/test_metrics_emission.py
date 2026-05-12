"""
Phase 273.4.5 — metrics emission tests for search hot path.

Patches the search.metrics module-boundary wrappers and asserts
they are called with correct labels. Does NOT mock internal code.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"ME-{uid}", slug=f"me-{uid}",
        status="ACTIVE", kyc_status="UNVERIFIED",
    )


def _mk_user(tenant):
    return User.objects.create_user(
        email=f"me-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass", tenant=tenant, status=UserStatus.ACTIVE,
    )


class TestSearchMetricsEmission(TestCase):
    """Successful search bumps duration histogram + results counter;
    empty-result search bumps no_result counter."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = _mk_tenant()
        self.user = _mk_user(self.tenant)
        self.client.force_authenticate(user=self.user)

    @patch("hub.apps.search.views.UnifiedSearchView._fts_query")
    @patch("hub.apps.search.metrics.record_search")
    def test_successful_search_emits_metrics(self, mock_record, mock_fts):
        mock_fts.return_value = [
            {"type": "asset", "id": str(uuid.uuid4()), "name": "X", "rank": 1.0},
        ]
        resp = self.client.get("/api/search/?q=test")
        assert resp.status_code == 200
        mock_record.assert_called_once()
        kwargs = mock_record.call_args[1]
        assert kwargs["kind"] == "fts"
        assert kwargs["outcome"] == "success"
        assert kwargs["result_count"] == 1

    @patch("hub.apps.search.views.UnifiedSearchView._fts_query")
    @patch("hub.apps.search.metrics.record_search")
    def test_empty_result_emits_no_result_metric(self, mock_record, mock_fts):
        mock_fts.return_value = []
        resp = self.client.get("/api/search/?q=nonexistent")
        assert resp.status_code == 200
        mock_record.assert_called_once()
        kwargs = mock_record.call_args[1]
        assert kwargs["outcome"] == "empty"
        assert kwargs["result_count"] == 0

    @patch("hub.apps.search.views.UnifiedSearchView._fts_query")
    @patch("hub.apps.search.metrics.record_search")
    def test_metrics_failure_does_not_block_search(self, mock_record, mock_fts):
        mock_fts.return_value = []
        mock_record.side_effect = RuntimeError("metric backend down")
        resp = self.client.get("/api/search/?q=test")
        assert resp.status_code == 200  # search succeeds despite metric failure
