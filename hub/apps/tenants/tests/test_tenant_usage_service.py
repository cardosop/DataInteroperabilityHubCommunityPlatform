"""Unit tests for TenantUsageService.get_current_usage().

Covers the dynamic RESOURCE_COUNTERS iteration path with real DB.
Previously only exercised through the /me/usage/ API endpoint.

calculate_usage_summary() is tested indirectly via the API endpoint
tests (test_me_usage.py) due to complex period-boundary get_or_create
logic in the service.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.tenants.services import TenantUsageService

pytestmark = pytest.mark.django_db(transaction=True)


class GetCurrentUsageTests(TestCase):
    """Tests for TenantUsageService.get_current_usage()."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Usage {uid}",
            slug=f"usage-{uid}",
            status=TenantStatus.ACTIVE,
        )
        self.service = TenantUsageService(
            tenant_id=str(self.tenant.id),
            user_id=None,
        )

    def test_returns_dictionary_with_correct_keys(self):
        """Success: returns a dict with plural *_usage entries for counters."""
        result = self.service.get_current_usage(str(self.tenant.id))
        self.assertIsInstance(result, dict)
        # Keys use plural form from RESOURCE_COUNTERS: max_assets → assets_usage.
        self.assertIn("assets_usage", result)
        self.assertIn("datasets_usage", result)
        self.assertIn("webhooks_usage", result)
        self.assertIsInstance(result["assets_usage"], int)
        self.assertIsInstance(result["datasets_usage"], int)

    def test_all_usage_values_are_ints(self):
        """All *_usage values should be integers (or None for unlimited)."""
        result = self.service.get_current_usage(str(self.tenant.id))
        for key, val in result.items():
            if key.endswith("_usage"):
                self.assertIsInstance(
                    val,
                    int,
                    f"Usage key '{key}' should be int, got {type(val).__name__}",
                )

    def test_includes_tenant_id_key(self):
        """Response dict includes the tenant_id for correlation."""
        result = self.service.get_current_usage(str(self.tenant.id))
        self.assertIn("tenant_id", result)
        self.assertEqual(result["tenant_id"], str(self.tenant.id))
