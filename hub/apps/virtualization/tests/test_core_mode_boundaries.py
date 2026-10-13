"""
Phase 313.H.3 — virtualization paid-layer boundaries.

Cross-tenant source access (marketplace entitlements) and SPARQL
execution (semantic service) resolve through commercial hooks; both
FAIL CLOSED in core-only mode: the cross-tenant source validation
reports the missing entitlement, and SPARQL execution raises a
structured ValidationError instead of an import crash.

NO MOCKS at contract boundaries: real Postgres, real ORM, real
business rules; core-only mode simulated by unregistering the paid
providers (the exact runtime shape of a core-only process).
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.core import commercial_hooks
from hub.apps.core.services.base import ValidationError
from hub.apps.marketplace.models import (
    Entitlement,
    EntitlementStatus,
    Listing,
    ListingStatus,
    PricingModel,
)
from hub.apps.tenants.models import Tenant
from hub.apps.virtualization.business_rules import VirtualizationBusinessRules
from hub.apps.virtualization.models import QueryType, VirtualDataset, VirtualDatasetStatus
from hub.apps.virtualization.services.query_service import QueryServiceMixin

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class VirtualizationCoreModeBoundaryTests(TestCase):
    """Paid-layer boundaries fail closed in core-only mode."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.owner_tenant = Tenant.objects.create(
            name=f"Owner-{uid}", slug=f"owner-{uid}", status="ACTIVE"
        )
        self.consumer_tenant = Tenant.objects.create(
            name=f"Consumer-{uid}", slug=f"consumer-{uid}", status="ACTIVE"
        )
        self.owner = User.objects.create_user(
            email=f"owner-{uid}@meshant.test", password="testpass", tenant=self.owner_tenant
        )
        self.consumer = User.objects.create_user(
            email=f"consumer-{uid}@meshant.test", password="testpass", tenant=self.consumer_tenant
        )
        self.owner_asset = Asset.objects.create(
            tenant=self.owner_tenant,
            key=f"asset-{uid}",
            name="Cross-Tenant Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.owner,
        )

    def _virtual_dataset(self):
        return VirtualDataset.objects.create(
            tenant=self.consumer_tenant,
            created_by=self.consumer,
            name=f"vd-{uuid.uuid4().hex[:8]}",
            query="SELECT * FROM federated_source",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
            sources=[{"type": "federated_asset", "asset_id": str(self.owner_asset.id)}],
        )

    def _rules(self):
        return VirtualizationBusinessRules(
            tenant_id=str(self.consumer_tenant.id),
            user_id=str(self.consumer.id),
        )

    # ── Cross-tenant source validation ──────────────────────────────

    def test_core_only_cross_tenant_source_fails_closed(self):
        """Core-only: no marketplace → cross-tenant source denied."""
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            result = self._rules().validate_source_configuration(self._virtual_dataset())
        assert any("without entitlement" in e for e in result.errors)

    def test_full_mode_unentitled_cross_tenant_source_denied(self):
        result = self._rules().validate_source_configuration(self._virtual_dataset())
        assert any("without entitlement" in e for e in result.errors)

    def test_full_mode_entitled_cross_tenant_source_allowed(self):
        listing = Listing.objects.create(
            tenant=self.owner_tenant,
            asset=self.owner_asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
        )
        Entitlement.objects.create(
            tenant=self.consumer_tenant,
            listing=listing,
            asset=self.owner_asset,
            status=EntitlementStatus.ACTIVE,
        )
        result = self._rules().validate_source_configuration(self._virtual_dataset())
        assert not any("without entitlement" in e for e in result.errors)

    # ── SPARQL execution ────────────────────────────────────────────

    def test_core_only_sparql_execution_fails_closed(self):
        """Core-only: no semantic client factory → structured error, no crash."""
        mixin = QueryServiceMixin()
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            with pytest.raises(ValidationError) as excinfo:
                mixin._execute_sparql_query("SELECT * WHERE { ?s ?p ?o }", 30)
        assert "not available in core-only" in str(excinfo.value)

    # The full-mode liveness half ("SEMANTIC factory is registered") moved to
    # hub/apps/core/tests/test_hook_provider_coverage.py (P.2a), which asserts
    # the factory registry next to every other seam slot in one place.
