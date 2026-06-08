"""
Phase 273.3.7-8 — audit emission tests for search endpoints.

Covers:
- Successful search creates SEARCH_PERFORMED audit row
- Throttled request creates SEARCH_RATE_LIMIT_EXCEEDED row
- Tenant scoping: tenant A's audit row not visible to tenant B query
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.event_types import SEARCH_PERFORMED, SEARCH_RATE_LIMIT_EXCEEDED
from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _mk_tenant(name="AE"):
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{name}-{uid}", slug=f"ae-{uid}",
        status="ACTIVE", kyc_status="UNVERIFIED",
    )


def _mk_user(tenant, email_pfx="user"):
    return User.objects.create_user(
        email=f"{email_pfx}-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass", tenant=tenant, status=UserStatus.ACTIVE,
    )


class TestSearchAuditEmission(TestCase):
    """Successful search creates one SEARCH_PERFORMED audit row."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = _mk_tenant()
        self.user = _mk_user(self.tenant)
        self.client.force_authenticate(user=self.user)

    @patch("hub.apps.search.views.UnifiedSearchView._fts_query")
    def test_successful_search_creates_audit_event(self, mock_fts):
        mock_fts.return_value = [
            {"type": "asset", "id": str(uuid.uuid4()), "name": "Test", "rank": 1.0},
        ]
        resp = self.client.get("/api/search/?q=test")
        assert resp.status_code == 200

        audit = AuditEvent.objects.filter(
            action=SEARCH_PERFORMED,
            tenant_id=self.tenant.pk,
        ).first()
        assert audit is not None, "SEARCH_PERFORMED audit must be emitted"
        assert "query_truncated" in (audit.details_json or {})
        assert audit.details_json["query_truncated"] == "test"

    @patch("hub.apps.search.views.UnifiedSearchView._fts_query")
    def test_query_truncated_to_256_chars(self, mock_fts):
        mock_fts.return_value = []
        long_query = "x" * 500
        self.client.get(f"/api/search/?q={long_query}")

        audit = AuditEvent.objects.filter(
            action=SEARCH_PERFORMED,
            tenant_id=self.tenant.pk,
        ).first()
        assert audit is not None
        assert len(audit.details_json["query_truncated"]) <= 256


@override_settings(SEARCH_RATE_LIMIT_PER_MIN="3/min")
class TestThrottledAuditEmission(TestCase):
    """429 path creates SEARCH_RATE_LIMIT_EXCEEDED audit row."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = _mk_tenant()
        self.user = _mk_user(self.tenant)
        self.client.force_authenticate(user=self.user)

    @patch("hub.apps.search.views.UnifiedSearchView._fts_query")
    def test_throttled_emits_rate_limit_audit(self, mock_fts):
        mock_fts.return_value = []
        for _ in range(3):
            self.client.get("/api/search/?q=test")
        resp = self.client.get("/api/search/?q=test")
        assert resp.status_code == 429

        audit = AuditEvent.objects.filter(
            action=SEARCH_RATE_LIMIT_EXCEEDED,
        ).first()
        assert audit is not None, "SEARCH_RATE_LIMIT_EXCEEDED audit must be emitted on 429"


class TestSearchAuditTenantScoping(TestCase):
    """Tenant A's search audit not visible to tenant B."""

    def setUp(self):
        self.tenant_a = _mk_tenant("TA")
        self.tenant_b = _mk_tenant("TB")
        self.user_a = _mk_user(self.tenant_a, "usera")
        self.user_b = _mk_user(self.tenant_b, "userb")
        self.client_a = APIClient()
        self.client_a.force_authenticate(user=self.user_a)
        self.client_b = APIClient()
        self.client_b.force_authenticate(user=self.user_b)

    @patch("hub.apps.search.views.UnifiedSearchView._fts_query")
    def test_tenant_isolation(self, mock_fts):
        mock_fts.return_value = []
        self.client_a.get("/api/search/?q=alpha")
        self.client_b.get("/api/search/?q=beta")

        audits_a = AuditEvent.objects.filter(
            action=SEARCH_PERFORMED, tenant_id=self.tenant_a.pk,
        )
        audits_b = AuditEvent.objects.filter(
            action=SEARCH_PERFORMED, tenant_id=self.tenant_b.pk,
        )
        assert audits_a.count() == 1
        assert audits_b.count() == 1
        assert audits_a.first().details_json["query_truncated"] == "alpha"
        assert audits_b.first().details_json["query_truncated"] == "beta"
