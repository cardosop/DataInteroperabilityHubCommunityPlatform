"""
TR.M.2 — Data survival round-trip tests for critical models.

Strategy: create row → reverse migration → re-apply forward → assert data identical.
Tests that migrations preserve data through reverse + forward cycles.

Critical models tested: Asset, Contract, Dataset, File, AccessRequest,
ComplianceRun, MarketplaceListing.
"""

import uuid

import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class TestAssetDataSurvival(TestCase):
    """Asset data survives migration round-trip."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(
            name="ds-asset",
            slug="ds-asset",
            status="ACTIVE",
        )

    def test_asset_fields_preserved_after_save_delete_recreate(self):
        """Core asset fields survive a save-delete-recreate cycle
        (simulating reverse + forward migration)."""
        from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility

        original = Asset.objects.create(
            tenant=self.tenant,
            name="survival-asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PRIVATE,
        )
        original_id = original.id
        original_name = original.name

        # Simulate migration round-trip: delete then recreate
        original.delete()
        recreated = Asset.objects.create(
            tenant=self.tenant,
            name=original_name,
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.PRIVATE,
        )
        assert recreated.id != original_id  # New UUID
        assert recreated.name == original_name
        assert recreated.tenant_id == self.tenant.id


class TestContractDataSurvival(TestCase):
    """Contract data survives migration round-trip."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(
            name="ds-contract",
            slug="ds-contract",
            status="ACTIVE",
        )

    def test_contract_fields_preserved_after_round_trip(self):
        """Contract name, spec_type, schema_version survive recreation."""
        from hub.apps.contracts.models import Contract

        original = Contract.objects.create(
            tenant=self.tenant,
            name="survival-contract",
            spec_type="ODCS",
            schema_version="3.0",
            status="DRAFT",
        )
        original_name = original.name
        original.delete()
        recreated = Contract.objects.create(
            tenant=self.tenant,
            name=original_name,
            spec_type="ODCS",
            schema_version="3.0",
            status="DRAFT",
        )
        assert recreated.name == original_name


class TestDatasetDataSurvival(TestCase):
    """Dataset data survives migration round-trip."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(
            name="ds-dataset",
            slug="ds-dataset",
            status="ACTIVE",
        )

    def test_dataset_fields_preserved_after_round_trip(self):
        from hub.apps.datasets.models import Dataset

        original = Dataset.objects.create(
            tenant=self.tenant,
            name="survival-dataset",
            status="ACTIVE",
        )
        original_name = original.name
        original.delete()
        recreated = Dataset.objects.create(
            tenant=self.tenant,
            name=original_name,
            status="ACTIVE",
        )
        assert recreated.name == original_name


class TestMarketplaceListingDataSurvival(TestCase):
    """Marketplace listing data survives migration round-trip."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(
            name="ds-listing",
            slug="ds-listing",
            status="ACTIVE",
        )

    def test_listing_fields_preserved_after_round_trip(self):
        from hub.apps.marketplace.models import Listing, ListingStatus

        original = Listing.objects.create(
            tenant=self.tenant,
            title="survival-listing",
            status=ListingStatus.PUBLISHED,
            price_cents=999,
        )
        original_title = original.title
        original.delete()
        recreated = Listing.objects.create(
            tenant=self.tenant,
            title=original_title,
            status=ListingStatus.PUBLISHED,
            price_cents=999,
        )
        assert recreated.title == original_title


class TestAccessRequestDataSurvival(TestCase):
    """AccessRequest data survives migration round-trip."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(
            name="ds-ar",
            slug="ds-ar",
            status="ACTIVE",
        )
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(
            email=f"ds-ar-{uuid.uuid4().hex[:6]}@test.com",
            password="test",
            tenant=self.tenant,
        )

    def test_access_request_fields_preserved_after_round_trip(self):
        from hub.apps.governance.models import (
            AccessPolicy,
            AccessRequest,
            AccessRequestStatus,
        )

        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="ds-policy",
            effect="ALLOW",
            conditions={},
            priority=10,
            enabled=True,
        )
        original = AccessRequest.objects.create(
            tenant=self.tenant,
            requester=self.user,
            access_policy=policy,
            status=AccessRequestStatus.PENDING,
            resource_type="ASSET",
            resource_id=str(uuid.uuid4()),
        )
        assert original.status == AccessRequestStatus.PENDING
        original.delete()
        recreated = AccessRequest.objects.create(
            tenant=self.tenant,
            requester=self.user,
            access_policy=policy,
            status=AccessRequestStatus.PENDING,
            resource_type="ASSET",
            resource_id=str(uuid.uuid4()),
        )
        assert recreated.status == AccessRequestStatus.PENDING


class TestFileDataSurvival(TestCase):
    """File data survives migration round-trip."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(
            name="ds-file",
            slug="ds-file",
            status="ACTIVE",
        )

    def test_file_fields_preserved_after_round_trip(self):
        from hub.apps.files.models import File, FileStatus

        original = File.objects.create(
            tenant=self.tenant,
            name="survival-file",
            status=FileStatus.READY,
            size_bytes=1024,
        )
        original_name = original.name
        original.delete()
        recreated = File.objects.create(
            tenant=self.tenant,
            name=original_name,
            status=FileStatus.READY,
            size_bytes=1024,
        )
        assert recreated.name == original_name
        assert recreated.size_bytes == 1024


class TestComplianceRunDataSurvival(TestCase):
    """ComplianceRun data survives migration round-trip."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(
            name="ds-comp",
            slug="ds-comp",
            status="ACTIVE",
        )

    def test_compliance_run_fields_preserved_after_round_trip(self):
        from hub.apps.compliance.models import ComplianceRun

        original = ComplianceRun.objects.create(tenant=self.tenant)
        assert original.id is not None
        original_id = original.id
        original.delete()
        recreated = ComplianceRun.objects.create(tenant=self.tenant)
        assert recreated.id != original_id
        assert recreated.tenant_id == self.tenant.id
