"""
Phase 313.H.3 — cross-tenant file access through the entitlement hooks.

``FileViewSet._get_file_via_entitlement`` resolves the file→asset link
and enforces the marketplace entitlement through commercial hooks
(marketplace registers both providers from its ``AppConfig.ready()``).
Core-only mode has no providers → the probe is audited and denied
(404), exactly like the no-asset-link case.

NO MOCKS at contract boundaries: real Postgres, real ORM, real
marketplace entitlement checks in full mode; core-only simulated by
unregistering the paid providers (the exact runtime shape of a
core-only process).
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.core import commercial_hooks
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.files.views import FileViewSet
from hub.apps.marketplace.models import (
    Entitlement,
    EntitlementStatus,
    Listing,
    ListingStatus,
    PricingModel,
)
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class CrossTenantFileEntitlementTests(TestCase):
    """Entitlement-gated cross-tenant file resolution + IDOR auditing."""

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
        self.asset = Asset.objects.create(
            tenant=self.owner_tenant,
            key=f"asset-{uid}",
            name="Entitled Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.owner,
        )
        self.file_obj = File.objects.create(
            tenant=self.owner_tenant,
            name="entitled-data.csv",
            content_type="text/csv",
            size=42,
            created_by=self.owner,
        )
        # The file→asset link travels through the dataset relationship
        # (marketplace's get_asset_id_from_file contract).
        self.dataset = Dataset.objects.create(
            tenant=self.owner_tenant,
            asset=self.asset,
            file=self.file_obj,
            created_by=self.owner,
        )

    def _consumer_request(self):
        request = RequestFactory().get("/irrelevant")
        request.user = self.consumer
        request.tenant_id = str(self.consumer_tenant.id)
        return request

    def _resolve(self, request):
        view = FileViewSet()
        view.request = request
        return view._get_file_via_entitlement(request, str(self.file_obj.id))

    def _grant_entitlement(self):
        listing = Listing.objects.create(
            tenant=self.owner_tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
        )
        Entitlement.objects.create(
            tenant=self.consumer_tenant,
            listing=listing,
            asset=self.asset,
            status=EntitlementStatus.ACTIVE,
        )

    def test_full_mode_entitled_consumer_resolves_file(self):
        self._grant_entitlement()
        resolved = self._resolve(self._consumer_request())
        assert resolved is not None
        assert resolved.id == self.file_obj.id

    def _id_or_audit(self):
        # The probe audit is recorded under the file's OWNER tenant with
        # the consumer id inside the details (see _emit_file_idor_audit).
        return AuditEvent.objects.filter(
            action="FILE_IDOR_ATTEMPT_BLOCKED",
            resource_id=str(self.file_obj.id),
        ).first()

    def test_full_mode_unentitled_consumer_denied_and_audited(self):
        resolved = self._resolve(self._consumer_request())
        assert resolved is None
        audit = self._id_or_audit()
        assert audit is not None
        assert audit.details_json.get("reason") == "ENTITLEMENT_DENIED"
        assert audit.details_json.get("consumer_tenant_id") == str(self.consumer_tenant.id)

    def test_core_only_probe_denied_and_audited(self):
        """Core-only: no asset-link resolver → audited 404, no leak."""
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            resolved = self._resolve(self._consumer_request())
        assert resolved is None
        audit = self._id_or_audit()
        assert audit is not None
        assert audit.details_json.get("reason") == "CROSS_TENANT_PROBE"
