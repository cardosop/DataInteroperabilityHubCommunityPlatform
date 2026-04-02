"""
Unit tests for Asset model.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from hub.apps.assets.models import (
    Asset,
    AssetStatus,
    AssetVisibility,
    ComplianceStatus,
    DQStatus,
)
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    ValidationStatus,
)
from hub.apps.tenants.models import Tenant
import uuid

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetModelTest(TestCase):
    """Test Asset model"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

    def test_create_asset_sets_tenant(self):
        """Test asset creation sets tenant."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test description",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.assertEqual(asset.tenant, self.tenant)

    def test_create_asset_sets_key(self):
        """Test asset creation sets key."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test description",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.assertEqual(asset.key, "test-asset")

    def test_create_asset_sets_name(self):
        """Test asset creation sets name."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test description",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.assertEqual(asset.name, "Test Asset")

    def test_create_asset_sets_default_status_values(self):
        """Test asset creation sets default status values correctly"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test description",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.assertEqual(asset.status, AssetStatus.DRAFT)
        self.assertEqual(asset.dq_status, DQStatus.UNKNOWN)
        self.assertEqual(asset.compliance_status, ComplianceStatus.UNKNOWN)

    def test_asset_status_choices(self):
        """Test asset status enum"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
        )

        asset.status = AssetStatus.ACTIVE
        asset.save()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    def test_asset_clean_validation(self):
        """Test asset clean() validation for ACTIVE status"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
        )

        # DRAFT status should not require validation
        asset.clean()

        # ACTIVE status requires active contract
        asset.status = AssetStatus.ACTIVE
        with self.assertRaises(ValidationError) as cm:
            asset.clean()
        self.assertIn("ACTIVE contract", str(cm.exception))

    def test_can_activate_returns_false_without_contract(self):
        """Test can_activate method returns False without contract"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
        )

        # No contract - cannot activate
        can_activate, blockers = asset.can_activate()
        self.assertFalse(can_activate)

    def test_can_activate_returns_blockers_without_contract(self):
        """Test can_activate method returns blockers without contract"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
        )

        # No contract - cannot activate
        can_activate, blockers = asset.can_activate()
        self.assertGreater(len(blockers), 0)

    def test_can_activate_returns_true_with_valid_contract(self):
        """Test can_activate method returns True with valid contract"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
        )

        # Add valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
            original_format="JSON",
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1},
        )

        # Contract-only asset can activate
        can_activate, blockers = asset.can_activate()
        self.assertTrue(can_activate)

    def test_can_activate_returns_no_blockers_with_valid_contract(self):
        """Test can_activate method returns no blockers with valid contract"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
        )

        # Add valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
            original_format="JSON",
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1},
        )

        # Contract-only asset can activate
        can_activate, blockers = asset.can_activate()
        self.assertEqual(len(blockers), 0)

    def test_increment_version(self):
        """Test increment_version method"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            version=1,
        )

        initial_version = asset.version
        asset.increment_version()
        asset.refresh_from_db()

        self.assertEqual(asset.version, initial_version + 1)

    # ========== FAILURE SCENARIOS ==========

    def test_create_asset_duplicate_key(self):
        """Duplicate key within same tenant raises IntegrityError."""
        from django.db import IntegrityError, transaction

        Asset.objects.create(
            tenant=self.tenant,
            key="duplicate-key",
            name="First Asset",
            created_by=self.user,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Asset.objects.create(
                    tenant=self.tenant,
                    key="duplicate-key",
                    name="Second Asset",
                    created_by=self.user,
                )

    def test_asset_clean_validation_fails_without_contract(self):
        """Test asset clean() validation fails for ACTIVE without contract (failure scenario)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
        )

        # Try to activate without contract
        asset.status = AssetStatus.ACTIVE
        with self.assertRaises(ValidationError) as cm:
            asset.clean()

        self.assertIn("ACTIVE contract", str(cm.exception))

    def test_can_activate_fails_without_contract(self):
        """Test can_activate returns False without contract (failure scenario)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
        )

        can_activate, blockers = asset.can_activate()

        self.assertFalse(can_activate)
        self.assertGreater(len(blockers), 0)
        self.assertIn("contract", str(blockers).lower())

    # ========== EDGE CASES ==========

    def test_create_asset_empty_key(self):
        """Empty key is accepted by the model (CharField allows blank)."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="",
            name="Test Asset",
            created_by=self.user,
        )
        self.assertEqual(asset.key, "")

    def test_create_asset_very_long_key(self):
        """Key exceeding max_length is rejected at DB level."""
        from django.db import DataError, transaction

        long_key = "a" * 300  # CharField max_length=255
        with self.assertRaises(DataError):
            with transaction.atomic():
                Asset.objects.create(
                    tenant=self.tenant,
                    key=long_key,
                    name="Test Asset",
                    created_by=self.user,
                )

    def test_create_asset_special_characters_in_key(self):
        """Key with hyphens, underscores, dots is accepted."""
        special_key = "test-asset_123.test"
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=special_key,
            name="Test Asset",
            created_by=self.user,
        )
        self.assertEqual(asset.key, special_key)

    def test_increment_version_max_value(self):
        """Test incrementing version to very large number (edge case)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            version=999999,
            created_by=self.user,
        )

        initial_version = asset.version
        asset.increment_version()
        asset.refresh_from_db()

        # Should increment successfully
        self.assertEqual(asset.version, initial_version + 1)

    def test_asset_status_transitions(self):
        """Test asset status transitions (edge case)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        # Test all status transitions
        for status_value in [AssetStatus.DRAFT, AssetStatus.ACTIVE, AssetStatus.RETIRED]:
            asset.status = status_value
            asset.save()
            asset.refresh_from_db()
            self.assertEqual(asset.status, status_value)

    def test_asset_default_values(self):
        """Test asset default values (edge case)"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", created_by=self.user
        )

        # Verify defaults
        self.assertEqual(asset.status, AssetStatus.DRAFT)
        self.assertEqual(asset.dq_status, DQStatus.UNKNOWN)
        self.assertEqual(asset.compliance_status, ComplianceStatus.UNKNOWN)
        self.assertEqual(asset.version, 1)
        self.assertEqual(asset.view_count, 0)
        self.assertEqual(asset.download_count, 0)
