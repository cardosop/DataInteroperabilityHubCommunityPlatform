"""
Unit tests for AssetService.

Tests cover all service methods with 100% coverage target.
"""

import uuid
import pytest
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.services import AssetService
from hub.apps.core.services.base import ConflictError, NotFoundError, ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class AssetServiceTest(TestCase):
    """Test AssetService operations"""

    def setUp(self):
        """Set up test data"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )
        self.service = AssetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_create_asset_success_returns_asset(self):
        """Test successful asset creation returns asset."""
        asset = self.service.create_asset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            key="test-asset",
            name="Test Asset",
            description="Test description",
            domain="test-domain",
        )

        self.assertIsNotNone(asset)

    def test_create_asset_success_sets_key(self):
        """Test successful asset creation sets key."""
        asset = self.service.create_asset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            key="test-asset",
            name="Test Asset",
            description="Test description",
            domain="test-domain",
        )

        self.assertEqual(asset.key, "test-asset")

    def test_create_asset_success_sets_name(self):
        """Test successful asset creation sets name."""
        asset = self.service.create_asset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            key="test-asset",
            name="Test Asset",
            description="Test description",
            domain="test-domain",
        )

        self.assertEqual(asset.name, "Test Asset")

    def test_create_asset_success_sets_draft_status(self):
        """Test successful asset creation sets DRAFT status."""
        asset = self.service.create_asset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            key="test-asset",
            name="Test Asset",
            description="Test description",
            domain="test-domain",
        )

        self.assertEqual(asset.status, AssetStatus.DRAFT)

    def test_create_asset_duplicate_key(self):
        """Test asset creation with duplicate key"""
        # Create first asset
        self.service.create_asset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            key="test-asset",
            name="Test Asset",
        )

        # Try to create duplicate
        with self.assertRaises(ConflictError) as cm:
            self.service.create_asset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                key="test-asset",
                name="Another Asset",
            )

        self.assertEqual(cm.exception.code, "ASSET_KEY_EXISTS")

    def test_update_asset_success_updates_name(self):
        """Test successful asset update updates name"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Original Name", status=AssetStatus.DRAFT
        )

        updated = self.service.update_asset(
            asset_id=str(asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Name",
            version=asset.version,
        )

        updated.refresh_from_db()
        self.assertEqual(updated.name, "Updated Name")

    def test_update_asset_success_increments_version(self):
        """Test successful asset update increments version"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Original Name", status=AssetStatus.DRAFT
        )
        original_version = asset.version

        updated = self.service.update_asset(
            asset_id=str(asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Name",
            version=asset.version,
        )

        updated.refresh_from_db()
        self.assertEqual(updated.version, original_version + 1)

    def test_update_asset_version_mismatch(self):
        """Test asset update with version mismatch"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Original Name", status=AssetStatus.DRAFT
        )

        with self.assertRaises(ConflictError) as cm:
            self.service.update_asset(
                asset_id=str(asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Updated Name",
                version=999,  # Wrong version
            )

        self.assertIn(
            cm.exception.code,
            ("CONFLICT", "ASSET_CONCURRENT_MODIFICATION"),
            msg="Version mismatch should raise conflict or concurrent modification",
        )

    def test_update_asset_activation_blocked_raises_validation_error(self):
        """Test asset activation when requirements not met raises ValidationError"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.DRAFT
        )

        # Asset without contract/dataset cannot be activated
        with self.assertRaises(ValidationError) as cm:
            self.service.update_asset(
                asset_id=str(asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                status=AssetStatus.ACTIVE,
                version=asset.version,
            )

        # Service raises BUSINESS_RULES_VALIDATION when AssetsBusinessRules reject activation
        self.assertEqual(cm.exception.code, "BUSINESS_RULES_VALIDATION")

    def test_update_asset_activation_blocked_includes_message_or_details(self):
        """Test asset activation when requirements not met includes message or details"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.DRAFT
        )

        # Asset without contract/dataset cannot be activated
        with self.assertRaises(ValidationError) as cm:
            self.service.update_asset(
                asset_id=str(asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                status=AssetStatus.ACTIVE,
                version=asset.version,
            )

        # Should include message or details from business rules
        self.assertTrue(
            cm.exception.message or cm.exception.details,
            msg="Expected message or details from business rules",
        )

    def test_delete_asset_success(self):
        """Test successful asset deletion"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

        self.service.delete_asset(
            asset_id=str(asset.id), tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.RETIRED)

    def test_get_asset_success_returns_correct_asset(self):
        """Test successful asset retrieval returns correct asset"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

        retrieved = self.service.get_asset(asset_id=str(asset.id), tenant_id=str(self.tenant.id))

        self.assertEqual(retrieved.id, asset.id)
        self.assertEqual(retrieved.key, asset.key)

    # ========== FAILURE SCENARIOS ==========

    def test_get_asset_not_found(self):
        """Test retrieving non-existent asset (failure scenario)"""
        import uuid

        fake_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.service.get_asset(asset_id=fake_id, tenant_id=str(self.tenant.id))

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    def test_get_asset_wrong_tenant(self):
        """Test retrieving asset from wrong tenant (failure scenario)"""
        # Create another tenant and asset
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}")
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset", name="Other Asset"
        )

        with self.assertRaises(NotFoundError) as cm:
            self.service.get_asset(asset_id=str(other_asset.id), tenant_id=str(self.tenant.id))

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    def test_update_asset_not_found(self):
        """Test updating non-existent asset (failure scenario)"""
        import uuid

        fake_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.service.update_asset(
                asset_id=fake_id,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Updated Name",
                version=1,
            )

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    def test_delete_asset_not_found(self):
        """Test deleting non-existent asset (failure scenario)"""
        import uuid

        fake_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.service.delete_asset(
                asset_id=fake_id, tenant_id=str(self.tenant.id), user_id=str(self.user.id)
            )

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    # ========== EDGE CASES ==========

    def test_create_asset_empty_key(self):
        """Test creating asset with empty key (edge case)"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_asset(
                tenant_id=str(self.tenant.id), user_id=str(self.user.id), key="", name="Test Asset"
            )

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")

    def test_create_asset_very_long_key(self):
        """Very long key (300 chars) is rejected by service validation."""
        long_key = "a" * 300  # Exceeds CharField max_length=255

        with self.assertRaises(ValidationError):
            self.service.create_asset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                key=long_key,
                name="Test Asset",
            )

    def test_create_asset_special_characters_in_key(self):
        """Service layer accepts non-standard key chars (no model-level validator).

        NOTE: The AssetCreateSerializer enforces a strict ^[a-z0-9]+(-[a-z0-9]+)*$
        key format at the API boundary.  The service layer and model CharField do
        NOT independently revalidate this constraint — internal callers (management
        commands, signals) that bypass the serializer could create assets with keys
        that API consumers cannot reference.  This is a known defense-in-depth gap.
        """
        special_key = "test-asset_123.test"
        asset = self.service.create_asset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            key=special_key,
            name="Test Asset",
        )
        self.assertEqual(asset.key, special_key)

    def test_update_asset_empty_name(self):
        """Updating asset with empty name is rejected (blank=False)."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Original Name",
            status=AssetStatus.DRAFT,
        )

        with self.assertRaises(ValidationError):
            self.service.update_asset(
                asset_id=str(asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="",
                version=asset.version,
            )

    def test_get_asset_with_invalid_uuid(self):
        """Test retrieving asset with invalid UUID format (edge case)"""
        with self.assertRaises((NotFoundError, ValueError)) as cm:
            self.service.get_asset(asset_id="invalid-uuid", tenant_id=str(self.tenant.id))

        # Should raise NotFoundError or ValueError
        if isinstance(cm.exception, NotFoundError):
            self.assertEqual(cm.exception.code, "NOT_FOUND")

    def test_create_asset_max_version_number(self):
        """Test creating asset and checking version starts at 1 (edge case)"""
        asset = self.service.create_asset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            key="test-asset",
            name="Test Asset",
        )

        # Version should start at 1
        self.assertEqual(asset.version, 1)

    def test_update_asset_version_overflow(self):
        """Test updating asset with very large version number (edge case)"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.DRAFT
        )

        # Try with very large version number — must raise ConflictError
        with self.assertRaises(ConflictError) as cm:
            self.service.update_asset(
                asset_id=str(asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Updated Name",
                version=999999999,
            )
        self.assertIn(
            cm.exception.code,
            ("CONFLICT", "ASSET_CONCURRENT_MODIFICATION"),
        )
