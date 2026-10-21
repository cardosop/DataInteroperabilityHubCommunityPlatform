"""
Enhanced tests for ReferenceService with batch operations and UUID-based references.

Tests cover:
- Batch reference validation
- Batch reference retrieval
- Bulk validation
- Performance optimization
- Error handling
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.core.services.reference import ReferenceService
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.tenants.models import Tenant

User = get_user_model()

uid = uuid.uuid4().hex[:8]


class ReferenceServiceEnhancedTest(TestCase):
    """Test enhanced ReferenceService functionality."""

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", tenant=self.tenant, status="ACTIVE"
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset-1", name="Test Asset", domain="test"
        )
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path.csv",
            status="ACTIVE",
        )
        self.dataset = Dataset.objects.create(tenant=self.tenant, file=self.file, format="CSV")
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
        )

    def test_get_multiple_references_success(self):
        """Test getting multiple references successfully."""
        service = ReferenceService(tenant_id=str(self.tenant.id))

        references = [
            {"app_name": "assets", "model_name": "Asset", "resource_id": str(self.asset.id)},
            {"app_name": "files", "model_name": "File", "resource_id": str(self.file.id)},
            {"app_name": "datasets", "model_name": "Dataset", "resource_id": str(self.dataset.id)},
        ]

        results = service.get_multiple_references(references, tenant_id=str(self.tenant.id))

        self.assertEqual(len(results), 3)
        self.assertIn(str(self.asset.id), results)
        self.assertIn(str(self.file.id), results)
        self.assertIn(str(self.dataset.id), results)
        self.assertEqual(results[str(self.asset.id)], self.asset)
        self.assertEqual(results[str(self.file.id)], self.file)
        self.assertEqual(results[str(self.dataset.id)], self.dataset)

    def test_get_multiple_references_not_found(self):
        """Test getting multiple references with one not found."""
        service = ReferenceService(tenant_id=str(self.tenant.id))

        references = [
            {"app_name": "assets", "model_name": "Asset", "resource_id": str(self.asset.id)},
            {
                "app_name": "assets",
                "model_name": "Asset",
                "resource_id": "00000000-0000-0000-0000-000000000000",  # Non-existent
            },
        ]

        with self.assertRaises(NotFoundError):
            service.get_multiple_references(references, tenant_id=str(self.tenant.id))

    def test_get_multiple_references_tenant_isolation(self):
        """Test that get_multiple_references respects tenant isolation."""
        # Create another tenant and asset
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}"
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset-1", name="Other Asset", domain="other"
        )

        service = ReferenceService(tenant_id=str(self.tenant.id))

        references = [
            {
                "app_name": "assets",
                "model_name": "Asset",
                "resource_id": str(self.asset.id),  # Same tenant - should work
            },
            {
                "app_name": "assets",
                "model_name": "Asset",
                "resource_id": str(other_asset.id),  # Different tenant - should fail
            },
        ]

        # Should not find other_tenant's asset
        with self.assertRaises(NotFoundError):
            service.get_multiple_references(references, tenant_id=str(self.tenant.id))

    def test_bulk_validate_success(self):
        """Test bulk validation of multiple references."""
        service = ReferenceService(tenant_id=str(self.tenant.id))

        # Create multiple assets
        asset2 = Asset.objects.create(
            tenant=self.tenant, key="test-asset-2", name="Asset 2", domain="test"
        )
        asset3 = Asset.objects.create(
            tenant=self.tenant, key="test-asset-3", name="Asset 3", domain="test"
        )

        resource_ids = [
            str(self.asset.id),
            str(asset2.id),
            str(asset3.id),
            "00000000-0000-0000-0000-000000000000",  # Non-existent
        ]

        results = service.bulk_validate(
            app_name="assets",
            model_name="Asset",
            resource_ids=resource_ids,
            tenant_id=str(self.tenant.id),
        )

        self.assertEqual(len(results), 4)
        self.assertTrue(results[str(self.asset.id)])
        self.assertTrue(results[str(asset2.id)])
        self.assertTrue(results[str(asset3.id)])
        self.assertFalse(results["00000000-0000-0000-0000-000000000000"])

    def test_bulk_validate_tenant_isolation(self):
        """Test that bulk_validate respects tenant isolation."""
        # Create another tenant and asset
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}"
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset-1", name="Other Asset", domain="other"
        )

        service = ReferenceService(tenant_id=str(self.tenant.id))

        resource_ids = [
            str(self.asset.id),  # Same tenant - should validate
            str(other_asset.id),  # Different tenant - should not validate
        ]

        results = service.bulk_validate(
            app_name="assets",
            model_name="Asset",
            resource_ids=resource_ids,
            tenant_id=str(self.tenant.id),
        )

        self.assertTrue(results[str(self.asset.id)])
        self.assertFalse(results[str(other_asset.id)])

    def test_bulk_validate_with_filters(self):
        """Test bulk validation with additional filters."""
        service = ReferenceService(tenant_id=str(self.tenant.id))

        # Create assets with different statuses
        active_asset = Asset.objects.create(
            tenant=self.tenant,
            key="active-asset-1",
            name="Active Asset",
            domain="test",
            status="ACTIVE",
        )
        draft_asset = Asset.objects.create(
            tenant=self.tenant,
            key="draft-asset-1",
            name="Draft Asset",
            domain="test",
            status="DRAFT",
        )

        resource_ids = [str(active_asset.id), str(draft_asset.id)]

        # Validate only ACTIVE assets
        results = service.bulk_validate(
            app_name="assets",
            model_name="Asset",
            resource_ids=resource_ids,
            tenant_id=str(self.tenant.id),
            status="ACTIVE",
        )

        self.assertTrue(results[str(active_asset.id)])
        self.assertFalse(results[str(draft_asset.id)])

    def test_bulk_validate_unregistered_model(self):
        """Test bulk validation with unregistered model."""
        service = ReferenceService(tenant_id=str(self.tenant.id))

        with self.assertRaises(ValidationError) as cm:
            service.bulk_validate(
                app_name="nonexistent",
                model_name="Model",
                resource_ids=["00000000-0000-0000-0000-000000000000"],
            )

        self.assertIn("not registered", str(cm.exception))

    def test_validate_multiple_references_mixed_types(self):
        """Test validating multiple references of different types."""
        service = ReferenceService(tenant_id=str(self.tenant.id))

        references = [
            {"app_name": "assets", "model_name": "Asset", "resource_id": str(self.asset.id)},
            {"app_name": "files", "model_name": "File", "resource_id": str(self.file.id)},
            {"app_name": "datasets", "model_name": "Dataset", "resource_id": str(self.dataset.id)},
            {
                "app_name": "assets",
                "model_name": "Asset",
                "resource_id": "00000000-0000-0000-0000-000000000000",  # Invalid
            },
        ]

        results = service.validate_multiple_references(references, tenant_id=str(self.tenant.id))

        self.assertEqual(len(results), 4)
        self.assertTrue(results[str(self.asset.id)])
        self.assertTrue(results[str(self.file.id)])
        self.assertTrue(results[str(self.dataset.id)])
        self.assertFalse(results["00000000-0000-0000-0000-000000000000"])

    def test_performance_batch_vs_individual(self):
        """Test that batch operations are more efficient than individual calls."""
        service = ReferenceService(tenant_id=str(self.tenant.id))

        # Create multiple assets
        assets = []
        for i in range(10):
            asset = Asset.objects.create(
                tenant=self.tenant, key=f"perf-asset-{i}", name=f"Asset {i}", domain="test"
            )
            assets.append(asset)

        resource_ids = [str(asset.id) for asset in assets]

        # Batch operation should use single query
        with self.assertNumQueries(1):
            results = service.bulk_validate(
                app_name="assets",
                model_name="Asset",
                resource_ids=resource_ids,
                tenant_id=str(self.tenant.id),
            )

        # All should be valid
        self.assertTrue(all(results.values()))
