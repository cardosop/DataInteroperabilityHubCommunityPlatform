"""
Test Data Management Verification

Verifies that test data factories, generators, and fixtures work correctly.
"""

import pytest
from django.test import TestCase

from hub.apps.assets.tests.factories import AssetFactory
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from hub.apps.datasets.tests.factories import DatasetFactory
from hub.apps.files.tests.factories import FileFactory
from tests.factories import JobFactory, TenantFactory, UserFactory
from tests.fixtures.test_data_fixtures import SampleTestData
from tests.test_data_generators import TestDataGenerator

pytestmark = pytest.mark.django_db(transaction=True)


class TestDataFactoriesVerification(TestCase):
    """Verify test data factories work correctly"""

    def test_tenant_factory(self):
        """Test TenantFactory creates tenants"""
        tenant = TenantFactory.create_tenant()
        self.assertIsNotNone(tenant)
        self.assertIsNotNone(tenant.id)
        self.assertIsNotNone(tenant.name)
        self.assertIsNotNone(tenant.slug)

    def test_user_factory(self):
        """Test UserFactory creates users"""
        tenant = TenantFactory.create_tenant()
        user = UserFactory.create_user(tenant=tenant)
        self.assertIsNotNone(user)
        self.assertIsNotNone(user.id)
        self.assertEqual(user.tenant, tenant)

    def test_asset_factory(self):
        """Test AssetFactory creates assets"""
        tenant = TenantFactory.create_tenant()
        user = UserFactory.create_user(tenant=tenant)
        asset = AssetFactory.create_asset(tenant=tenant, created_by=user)
        self.assertIsNotNone(asset)
        self.assertIsNotNone(asset.id)
        self.assertEqual(asset.tenant, tenant)

    def test_contract_factory(self):
        """Test ContractFactoryEnhanced creates contracts"""
        tenant = TenantFactory.create_tenant()
        user = UserFactory.create_user(tenant=tenant)
        asset = AssetFactory.create_asset(tenant=tenant, created_by=user)
        contract = ContractFactoryEnhanced.create_contract(
            tenant=tenant, created_by=user, asset=asset
        )
        self.assertIsNotNone(contract)
        self.assertIsNotNone(contract.id)
        self.assertEqual(contract.tenant, tenant)
        self.assertEqual(contract.asset, asset)

    def test_file_factory(self):
        """Test FileFactory creates files"""
        tenant = TenantFactory.create_tenant()
        user = UserFactory.create_user(tenant=tenant)
        file = FileFactory.create_file(tenant=tenant, created_by=user)
        self.assertIsNotNone(file)
        self.assertIsNotNone(file.id)
        self.assertEqual(file.tenant, tenant)

    def test_dataset_factory(self):
        """Test DatasetFactory creates datasets"""
        tenant = TenantFactory.create_tenant()
        user = UserFactory.create_user(tenant=tenant)
        asset = AssetFactory.create_asset(tenant=tenant, created_by=user)
        file = FileFactory.create_file(tenant=tenant, created_by=user)
        dataset = DatasetFactory.create_dataset(
            tenant=tenant, file=file, asset=asset, created_by=user
        )
        self.assertIsNotNone(dataset)
        self.assertIsNotNone(dataset.id)
        self.assertEqual(dataset.tenant, tenant)
        self.assertEqual(dataset.asset, asset)

    def test_job_factory(self):
        """Test JobFactory creates jobs"""
        tenant = TenantFactory.create_tenant()
        user = UserFactory.create_user(tenant=tenant)
        job = JobFactory.create_job(tenant=tenant, created_by=user)
        self.assertIsNotNone(job)
        self.assertIsNotNone(job.id)
        self.assertEqual(job.tenant, tenant)


class TestDataGeneratorsVerification(TestCase):
    """Verify test data generators work correctly"""

    def test_generate_tenant(self):
        """Test TestDataGenerator.generate_tenant"""
        tenant = TestDataGenerator.generate_tenant()
        self.assertIsNotNone(tenant)
        self.assertIsNotNone(tenant.id)

    def test_generate_user(self):
        """Test TestDataGenerator.generate_user"""
        tenant = TestDataGenerator.generate_tenant()
        user = TestDataGenerator.generate_user(tenant=tenant)
        self.assertIsNotNone(user)
        self.assertEqual(user.tenant, tenant)

    def test_generate_asset(self):
        """Test TestDataGenerator.generate_asset"""
        tenant = TestDataGenerator.generate_tenant()
        user = TestDataGenerator.generate_user(tenant=tenant)
        asset = TestDataGenerator.generate_asset(tenant=tenant, created_by=user)
        self.assertIsNotNone(asset)
        self.assertEqual(asset.tenant, tenant)

    def test_generate_contract(self):
        """Test TestDataGenerator.generate_contract"""
        tenant = TestDataGenerator.generate_tenant()
        user = TestDataGenerator.generate_user(tenant=tenant)
        contract = TestDataGenerator.generate_contract(tenant=tenant, created_by=user)
        self.assertIsNotNone(contract)
        self.assertEqual(contract.tenant, tenant)

    def test_generate_multiple_assets(self):
        """Test TestDataGenerator.generate_assets"""
        tenant = TestDataGenerator.generate_tenant()
        user = TestDataGenerator.generate_user(tenant=tenant)
        assets = TestDataGenerator.generate_assets(tenant=tenant, created_by=user, count=5)
        self.assertEqual(len(assets), 5)
        for asset in assets:
            self.assertEqual(asset.tenant, tenant)

    def test_generate_complete_environment(self):
        """Test TestDataGenerator.generate_complete_test_environment"""
        env = TestDataGenerator.generate_complete_test_environment(
            num_users=3, num_assets=5, num_contracts=3, num_datasets=3, num_jobs=5
        )
        self.assertIn("tenant", env)
        self.assertIn("users", env)
        self.assertIn("assets", env)
        self.assertIn("contracts", env)
        self.assertIn("datasets", env)
        self.assertIn("jobs", env)
        self.assertEqual(len(env["users"]), 3)
        self.assertEqual(len(env["assets"]), 5)
        self.assertEqual(len(env["contracts"]), 3)
        self.assertEqual(len(env["datasets"]), 3)
        self.assertEqual(len(env["jobs"]), 5)


class TestDataFixturesVerification(TestCase):
    """Verify test data fixtures work correctly"""

    def test_sample_tenant_verified(self):
        """Test SampleTestData.create_sample_tenant_verified"""
        tenant = SampleTestData.create_sample_tenant_verified()
        self.assertIsNotNone(tenant)
        self.assertEqual(tenant.kyc_status, "VERIFIED")

    def test_sample_asset_customer_data(self):
        """Test SampleTestData.create_sample_asset_customer_data"""
        tenant = SampleTestData.create_sample_tenant_verified()
        user = SampleTestData.create_sample_user(tenant)
        asset = SampleTestData.create_sample_asset_customer_data(tenant, user)
        self.assertIsNotNone(asset)
        self.assertEqual(asset.key, "customer-data")

    def test_sample_contract_customer(self):
        """Test SampleTestData.create_sample_contract_customer"""
        tenant = SampleTestData.create_sample_tenant_verified()
        user = SampleTestData.create_sample_user(tenant)
        contract = SampleTestData.create_sample_contract_customer(tenant, user)
        self.assertIsNotNone(contract)
        self.assertIsNotNone(contract.id)
        # Contract name is in hub_contract_json
        if contract.hub_contract_json:
            info = contract.hub_contract_json.get("info", {})
            if "name" in info:
                self.assertEqual(info.get("name"), "Customer Data Contract")

    def test_sample_environment_basic(self):
        """Test SampleTestData.create_sample_environment_basic"""
        env = SampleTestData.create_sample_environment_basic()
        self.assertIn("tenant", env)
        self.assertIn("user", env)
        self.assertIn("assets", env)
        self.assertIn("contracts", env)
        self.assertIn("datasets", env)
        self.assertGreater(len(env["assets"]), 0)
        self.assertGreater(len(env["contracts"]), 0)
        self.assertGreater(len(env["datasets"]), 0)
