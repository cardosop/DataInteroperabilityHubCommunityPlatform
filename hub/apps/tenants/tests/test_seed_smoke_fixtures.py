"""
pilot-readiness 3.4 — seed_smoke_fixtures contract tests.

The smoke seeder is the durable recovery path for the shared E2E DB —
it runs in the stack's migrate-test-db service on every API bring-up.
A peer session's tests can drift the deterministic fixture rows (e.g.
flip the CRITICAL asset's status away from ACTIVE); the seeder MUST
heal that drift — otherwise ``Listing.full_clean``'s "Only ACTIVE
assets can be listed in the marketplace" aborts the whole stack
bring-up (the 3.4 live incident: the migrate service exited 1 and the
API container was left Created-but-not-started).
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus

# Marketplace is the paid layer — guarded for both core-only absence
# forms (W7.1); the listing assertions skip when it is absent.
try:
    from hub.apps.marketplace.models import Listing, ListingStatus
except (RuntimeError, ModuleNotFoundError):
    Listing = ListingStatus = None  # type: ignore[assignment]
from hub.apps.tenants.management.commands.seed_smoke_fixtures import (
    ADMIN_EMAIL,
    CRITICAL_ASSET_ID,
    CRITICAL_LISTING_ID,
    FEDERATED_SOURCE_LISTING_ID,
    SOURCE_ASSET_ID,
)
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User

COMMAND = "seed_smoke_fixtures"


@pytest.mark.django_db(transaction=True)
class SeedSmokeFixturesTest(TestCase):
    def setUp(self):
        # The command's prerequisite: the platform admin user with an
        # active subscription on its home tenant (the E2E persona seed).
        # Users require a tenant — create one explicitly.
        from hub.apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(
            name="Smoke Admin Tenant",
            slug="smoke-admin",
            status="ACTIVE",
        )
        self.admin = User.objects.create_user(
            email=ADMIN_EMAIL,
            password="test-pass-123!",
            display_name="E2E Platform Admin",
            tenant=self.tenant,
        )
        ensure_tenant_has_active_subscription(self.admin.tenant)

    def _run(self):
        out = StringIO()
        call_command(COMMAND, stdout=out)
        return out.getvalue()

    def test_seeds_listings_and_is_idempotent(self):
        if Listing is None:
            pytest.skip("marketplace (paid layer) not installed in core-only mode")
        self._run()
        self._run()
        assert Listing.objects.filter(id=CRITICAL_LISTING_ID).count() == 1
        assert Listing.objects.filter(id=FEDERATED_SOURCE_LISTING_ID).count() == 1
        critical = Listing.objects.get(id=CRITICAL_LISTING_ID)
        assert critical.status == ListingStatus.DRAFT
        assert critical.asset.status == AssetStatus.ACTIVE
        assert critical.asset.tenant_id == self.admin.tenant_id

    def test_heals_drifted_critical_asset_status(self):
        if Listing is None:
            pytest.skip("marketplace (paid layer) not installed in core-only mode")
        """A peer session flipped the CRITICAL asset to DRAFT — the seeder
        must heal it before the listing row is touched, or full_clean
        aborts the whole bring-up (the 3.4 live incident)."""
        Asset.objects.create(
            id=CRITICAL_ASSET_ID,
            tenant=self.admin.tenant,
            key="smoke-critical-asset",
            name="Smoke Critical Asset",
            domain="smoke",
            status=AssetStatus.DRAFT,
            created_by=self.admin,
        )
        self._run()
        asset = Asset.objects.get(id=CRITICAL_ASSET_ID)
        assert asset.status == AssetStatus.ACTIVE
        listing = Listing.objects.get(id=CRITICAL_LISTING_ID)
        assert listing.status == ListingStatus.DRAFT

    def test_heals_drifted_source_asset_status(self):
        if Listing is None:
            pytest.skip("marketplace (paid layer) not installed in core-only mode")
        """The federated source's PUBLISHED listing has the same
        ACTIVE-asset constraint — drift there aborts the bring-up too."""
        from hub.apps.tenants.management.commands.seed_smoke_fixtures import (
            SOURCE_TENANT_ID,
            SOURCE_USER_ID,
        )
        from hub.apps.tenants.models import KYCStatus, Tenant

        source_tenant = Tenant.objects.create(
            id=SOURCE_TENANT_ID,
            name="Smoke Federated Source",
            slug="smoke-federated-source",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        source_user = User.objects.create_user(
            id=SOURCE_USER_ID,
            email="smoke-federated-source@example.com",
            password="test-pass-123!",
            tenant=source_tenant,
        )
        Asset.objects.create(
            id=SOURCE_ASSET_ID,
            tenant=source_tenant,
            key="smoke-federated-source-asset",
            name="Smoke Federated Source Asset",
            domain="smoke",
            status=AssetStatus.RETIRED,
            created_by=source_user,
        )
        self._run()
        asset = Asset.objects.get(id=SOURCE_ASSET_ID)
        assert asset.status == AssetStatus.ACTIVE
        listing = Listing.objects.get(id=FEDERATED_SOURCE_LISTING_ID)
        assert listing.status == ListingStatus.PUBLISHED
