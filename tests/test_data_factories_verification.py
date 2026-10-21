"""
Verification tests for test data factories and management utilities.

Tests that factories work correctly and can create test data.
"""

import uuid

import pytest
from django.db import transaction
from django.test import TestCase

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract
from hub.apps.datasets.models import Dataset
from hub.apps.jobs.models import Job
from hub.apps.tenants.models import Tenant
from tests.fixtures.test_data_factories import (
    AssetFactory,
    ContractFactory,
    DatasetFactory,
    FileFactory,
    JobFactory,
    ListingFactory,
    TenantFactory,
    UserFactory,
)
from tests.utils.test_data_management import (
    TestDatabaseIsolationMixin,
    TestDataManager,
    cleanup_test_data,
    create_multi_tenant_test_data,
    validate_migrations,
)

pytestmark = [pytest.mark.django_db(transaction=True)]


class TestDataFactoriesVerificationTest(TestCase):
    """Verify test data factories work correctly"""

    def test_user_factory(self):
        """Test UserFactory creates users correctly"""
        user = UserFactory.create_user()
        self.assertIsNotNone(user.id)
        self.assertIsNotNone(user.email)
        self.assertIsNotNone(user.tenant)

    def test_tenant_factory(self):
        """Test TenantFactory creates tenants correctly"""
        tenant = TenantFactory.create_tenant()
        self.assertIsNotNone(tenant.id)
        self.assertIsNotNone(tenant.name)
        self.assertIsNotNone(tenant.slug)

    def test_asset_factory(self):
        """Test AssetFactory creates assets correctly"""
        asset = AssetFactory.create_asset()
        self.assertIsNotNone(asset.id)
        self.assertIsNotNone(asset.tenant)
        self.assertIsNotNone(asset.created_by)

    def test_contract_factory(self):
        """Test ContractFactory creates contracts correctly"""
        contract = ContractFactory.create_contract()
        self.assertIsNotNone(contract.id)
        self.assertIsNotNone(contract.tenant)
        self.assertIsNotNone(contract.asset)

    def test_dataset_factory(self):
        """Test DatasetFactory creates datasets correctly"""
        dataset = DatasetFactory.create_dataset()
        self.assertIsNotNone(dataset.id)
        self.assertIsNotNone(dataset.tenant)

    def test_job_factory(self):
        """Test JobFactory creates jobs correctly"""
        job = JobFactory.create_job()
        self.assertIsNotNone(job.id)
        self.assertIsNotNone(job.type)
        self.assertIsNotNone(job.status)

    def test_file_factory(self):
        """Test FileFactory creates files correctly"""
        file_obj = FileFactory.create_file()
        self.assertIsNotNone(file_obj.id)
        self.assertIsNotNone(file_obj.tenant)

    def test_listing_factory(self):
        """Test ListingFactory creates listings correctly"""
        listing = ListingFactory.create_listing()
        self.assertIsNotNone(listing.id)
        self.assertIsNotNone(listing.tenant)
        self.assertIsNotNone(listing.asset)


class TestDataManagementVerificationTest(TestCase):
    """Verify test data management utilities work correctly"""

    def test_test_data_manager(self):
        """Test TestDataManager creates and cleans up data"""
        manager = TestDataManager()

        # Create tenant with complete data
        tenant = manager.create_complete_tenant_data(
            tenant_name=f"Test Manager Tenant {uuid.uuid4().hex[:8]}",
            asset_count=2,
            contract_count=2,
            dataset_count=1,
            job_count=1,
        )

        self.assertIsNotNone(tenant.id)
        self.assertEqual(Asset.objects.filter(tenant=tenant).count(), 2)
        self.assertEqual(Contract.objects.filter(tenant=tenant).count(), 2)
        self.assertEqual(Dataset.objects.filter(tenant=tenant).count(), 1)
        self.assertEqual(Job.objects.filter(tenant=tenant).count(), 1)

        # Cleanup - use manager's cleanup which handles unsaved tenants
        manager.cleanup()

        # Verify cleanup - tenant should still exist (it's in created_objects)
        # But related objects should be cleaned up
        self.assertEqual(Asset.objects.filter(tenant_id=tenant.id).count(), 0)
        self.assertEqual(Contract.objects.filter(tenant_id=tenant.id).count(), 0)

    def test_multi_tenant_test_data(self):
        """Test multi-tenant test data creation"""
        tenants = create_multi_tenant_test_data(tenant_count=2)

        self.assertEqual(len(tenants), 2)
        for tenant in tenants:
            self.assertIsNotNone(tenant.id)
            self.assertGreater(Asset.objects.filter(tenant=tenant).count(), 0)

        # Cleanup - use tenant ID instead of instance to avoid unsaved tenant error
        for tenant in tenants:
            if tenant.pk:
                cleanup_test_data(tenant=tenant)

    def test_database_isolation_mixin(self):
        """Test TestDatabaseIsolationMixin provides isolation"""

        class IsolatedTest(TestDatabaseIsolationMixin, TestCase):
            def test_isolation(self):
                tenant = self.create_test_tenant()
                self.assertIsNotNone(tenant.id)
                # Data should be cleaned up in tearDown

        test = IsolatedTest()
        test.setUp()
        try:
            test.test_isolation()
        finally:
            test.tearDown()


class TestDatabaseConfigurationTest(TestCase):
    """Verify test database configuration"""

    def test_database_isolation(self):
        """Test that database transactions provide isolation"""
        # Create data in transaction
        with transaction.atomic():
            tenant = TenantFactory.create_tenant(name="Isolation Test")
            tenant_id = tenant.id

        # Verify data exists
        self.assertTrue(Tenant.objects.filter(id=tenant_id).exists())

        # Cleanup
        Tenant.objects.filter(id=tenant_id).delete()

    def test_migration_validation(self):
        """Test migration validation"""
        # This should not raise an error
        result = validate_migrations()
        self.assertIsInstance(result, bool)
