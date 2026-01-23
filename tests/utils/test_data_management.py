"""
Test Data Management Utilities

Comprehensive utilities for test data cleanup, seeding, and isolation.
Supports multi-tenant test data and proper database isolation.

Features:
- Test data cleanup utilities
- Test data seeding scripts
- Multi-tenant test data support
- Database isolation utilities
- Migration validation
"""
import os
import logging
from typing import List, Optional, Dict, Any, Set
from django.db import transaction, connection
from django.core.management import call_command
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model

from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract
from hub.apps.datasets.models import Dataset
from hub.apps.jobs.models import Job
from hub.apps.files.models import File
from hub.apps.marketplace.models import Listing
from hub.apps.notifications.models import EmailDelivery

from tests.fixtures.test_data_factories import (
    UserFactory,
    TenantFactory,
    AssetFactory,
    ContractFactory,
    DatasetFactory,
    JobFactory,
    FileFactory,
    ListingFactory,
    EmailDeliveryFactory,
)

User = get_user_model()

logger = logging.getLogger(__name__)


class TestDataManager:
    """
    Comprehensive test data management utility.

    Provides methods for:
    - Cleaning up test data
    - Seeding test data
    - Creating multi-tenant test scenarios
    - Database isolation
    """

    def __init__(self, tenant: Optional[Tenant] = None):
        """
        Initialize test data manager.

        Args:
            tenant: Optional tenant to scope operations to
        """
        self.tenant = tenant
        self.created_objects: Dict[str, List[Any]] = {
            "tenants": [],
            "users": [],
            "assets": [],
            "contracts": [],
            "datasets": [],
            "jobs": [],
            "files": [],
            "listings": [],
            "email_deliveries": [],
        }

    def create_tenant_with_users(
        self,
        tenant_name: Optional[str] = None,
        user_count: int = 3,
        **tenant_kwargs
    ) -> Tenant:
        """
        Create a tenant with multiple users.

        Args:
            tenant_name: Tenant name
            user_count: Number of users to create
            **tenant_kwargs: Additional tenant fields

        Returns:
            Created Tenant instance
        """
        tenant = TenantFactory.create_tenant(name=tenant_name, **tenant_kwargs)
        self.created_objects["tenants"].append(tenant)

        users = UserFactory.create_users_for_tenant(tenant, count=user_count)
        self.created_objects["users"].extend(users)

        return tenant

    def create_tenant_with_assets(
        self,
        tenant_name: Optional[str] = None,
        asset_count: int = 3,
        **kwargs
    ) -> Tenant:
        """
        Create a tenant with multiple assets.

        Args:
            tenant_name: Tenant name
            asset_count: Number of assets to create
            **kwargs: Additional fields

        Returns:
            Created Tenant instance
        """
        tenant = TenantFactory.create_tenant(name=tenant_name)
        self.created_objects["tenants"].append(tenant)

        user = UserFactory.create_user(tenant=tenant)
        self.created_objects["users"].append(user)

        assets = []
        for _ in range(asset_count):
            asset = AssetFactory.create_asset(tenant=tenant, created_by=user, **kwargs)
            assets.append(asset)
            self.created_objects["assets"].append(asset)

        return tenant

    def create_complete_tenant_data(
        self,
        tenant_name: Optional[str] = None,
        asset_count: int = 2,
        contract_count: int = 2,
        dataset_count: int = 2,
        job_count: int = 2,
        listing_count: int = 1,
        **kwargs
    ) -> Tenant:
        """
        Create a tenant with complete test data (assets, contracts, datasets, jobs, listings).

        Args:
            tenant_name: Tenant name
            asset_count: Number of assets to create
            contract_count: Number of contracts to create
            dataset_count: Number of datasets to create
            job_count: Number of jobs to create
            listing_count: Number of listings to create
            **kwargs: Additional fields

        Returns:
            Created Tenant instance
        """
        tenant = TenantFactory.create_tenant(name=tenant_name)
        self.created_objects["tenants"].append(tenant)

        user = UserFactory.create_user(tenant=tenant)
        self.created_objects["users"].append(user)

        # Create assets
        assets = []
        for _ in range(asset_count):
            asset = AssetFactory.create_asset(tenant=tenant, created_by=user, **kwargs)
            assets.append(asset)
            self.created_objects["assets"].append(asset)

        # Create contracts
        for i in range(contract_count):
            asset = assets[i % len(assets)] if assets else None
            contract = ContractFactory.create_contract(tenant=tenant, asset=asset, **kwargs)
            self.created_objects["contracts"].append(contract)

        # Create datasets
        for i in range(dataset_count):
            asset = assets[i % len(assets)] if assets else None
            dataset = DatasetFactory.create_dataset(tenant=tenant, asset=asset, **kwargs)
            self.created_objects["datasets"].append(dataset)

        # Create jobs
        for i in range(job_count):
            asset = assets[i % len(assets)] if assets else None
            resource_id = asset.id if asset else None
            job = JobFactory.create_job(
                tenant=tenant,
                resource_type="ASSET" if asset else "CONTRACT",
                resource_id=resource_id,
                created_by=user,
                **kwargs
            )
            self.created_objects["jobs"].append(job)

        # Create listings
        for i in range(listing_count):
            asset = assets[i % len(assets)] if assets else None
            if asset:
                listing = ListingFactory.create_listing(tenant=tenant, asset=asset, **kwargs)
                self.created_objects["listings"].append(listing)

        return tenant

    def cleanup(self, tenant: Optional[Tenant] = None):
        """
        Clean up all created test data.

        Args:
            tenant: Optional tenant to scope cleanup to
        """
        cleanup_tenant = tenant or self.tenant

        # Clean up in reverse order of dependencies
        # Listings depend on assets
        if cleanup_tenant and cleanup_tenant.pk:
            Listing.objects.filter(tenant=cleanup_tenant).delete()
        else:
            for listing in self.created_objects["listings"]:
                if listing.pk:
                    listing.delete()

        # Jobs
        if cleanup_tenant and cleanup_tenant.pk:
            Job.objects.filter(tenant=cleanup_tenant).delete()
        else:
            for job in self.created_objects["jobs"]:
                if job.pk:
                    job.delete()

        # Datasets
        if cleanup_tenant and cleanup_tenant.pk:
            Dataset.objects.filter(tenant=cleanup_tenant).delete()
        else:
            for dataset in self.created_objects["datasets"]:
                if dataset.pk:
                    dataset.delete()

        # Contracts
        if cleanup_tenant and cleanup_tenant.pk:
            Contract.objects.filter(tenant=cleanup_tenant).delete()
        else:
            for contract in self.created_objects["contracts"]:
                if contract.pk:
                    contract.delete()

        # Assets
        if cleanup_tenant and cleanup_tenant.pk:
            Asset.objects.filter(tenant=cleanup_tenant).delete()
        else:
            for asset in self.created_objects["assets"]:
                if asset.pk:
                    asset.delete()

        # Files
        if cleanup_tenant and cleanup_tenant.pk:
            File.objects.filter(tenant=cleanup_tenant).delete()
        else:
            for file_obj in self.created_objects["files"]:
                if file_obj.pk:
                    file_obj.delete()

        # Email deliveries (no tenant FK, but clean up created ones)
        for email in self.created_objects["email_deliveries"]:
            if email.pk:
                email.delete()

        # Users (delete before tenants to avoid restricted foreign key issues)
        if cleanup_tenant and cleanup_tenant.pk:
            # Delete users for this tenant first
            User.objects.filter(tenant=cleanup_tenant).delete()
        else:
            for user in self.created_objects["users"]:
                if user.pk:
                    try:
                        user.delete()
                    except Exception:
                        # If deletion fails (e.g., restricted FK), try to clear the reference first
                        pass

        # Tenants (last, as everything depends on them)
        # Only delete if no users reference it (to avoid restricted FK errors)
        if cleanup_tenant and cleanup_tenant.pk:
            # Check if there are any users still referencing this tenant
            if not User.objects.filter(tenant=cleanup_tenant).exists():
                try:
                    cleanup_tenant.delete()
                except Exception:
                    # If deletion fails due to restricted FK, skip it
                    # The test framework will handle cleanup via transaction rollback
                    pass
        else:
            for tenant_obj in self.created_objects["tenants"]:
                if tenant_obj.pk:
                    # Check if there are any users still referencing this tenant
                    if not User.objects.filter(tenant=tenant_obj).exists():
                        try:
                            tenant_obj.delete()
                        except Exception:
                            # If deletion fails due to restricted FK, skip it
                            pass

        # Clear tracking
        for key in self.created_objects:
            self.created_objects[key].clear()

    def get_created_objects(self) -> Dict[str, List[Any]]:
        """Get all created objects"""
        return self.created_objects.copy()


def cleanup_test_data(
    tenant: Optional[Tenant] = None,
    models: Optional[List[str]] = None
):
    """
    Clean up test data for specified models or tenant.

    Args:
        tenant: Optional tenant to scope cleanup to
        models: Optional list of model names to clean up
    """
    if models is None:
        models = ["listings", "jobs", "datasets", "contracts", "assets", "files", "users", "tenants"]

    cleanup_order = {
        "listings": Listing,
        "jobs": Job,
        "datasets": Dataset,
        "contracts": Contract,
        "assets": Asset,
        "files": File,
        "email_deliveries": EmailDelivery,
        "users": User,
        "tenants": Tenant,
    }

    for model_name in models:
        if model_name in cleanup_order:
            model = cleanup_order[model_name]
            if tenant and tenant.pk and hasattr(model, "tenant"):
                model.objects.filter(tenant=tenant).delete()
            else:
                # Clean up all test data (be careful in production!)
                if model_name == "tenants":
                    # Only delete test tenants (those with "test" in name)
                    model.objects.filter(name__icontains="test").delete()
                else:
                    model.objects.all().delete()


def seed_test_data(
    tenant_count: int = 2,
    users_per_tenant: int = 3,
    assets_per_tenant: int = 2,
    contracts_per_tenant: int = 2,
    datasets_per_tenant: int = 2,
    jobs_per_tenant: int = 2,
    listings_per_tenant: int = 1,
) -> List[Tenant]:
    """
    Seed test database with comprehensive test data.

    Args:
        tenant_count: Number of tenants to create
        users_per_tenant: Number of users per tenant
        assets_per_tenant: Number of assets per tenant
        contracts_per_tenant: Number of contracts per tenant
        datasets_per_tenant: Number of datasets per tenant
        jobs_per_tenant: Number of jobs per tenant
        listings_per_tenant: Number of listings per tenant

    Returns:
        List of created tenants
    """
    tenants = []

    for i in range(tenant_count):
        manager = TestDataManager()
        tenant = manager.create_complete_tenant_data(
            tenant_name=f"Test Tenant {i+1}",
            asset_count=assets_per_tenant,
            contract_count=contracts_per_tenant,
            dataset_count=datasets_per_tenant,
            job_count=jobs_per_tenant,
            listing_count=listings_per_tenant,
        )
        tenants.append(tenant)

        # Create additional users
        for _ in range(users_per_tenant - 1):
            UserFactory.create_user(tenant=tenant)

    logger.info(f"Seeded test data: {len(tenants)} tenants with complete data")
    return tenants


def create_multi_tenant_test_data(
    tenant_count: int = 3,
    **kwargs
) -> List[Tenant]:
    """
    Create multi-tenant test data scenario.

    Args:
        tenant_count: Number of tenants to create
        **kwargs: Additional fields for test data

    Returns:
        List of created tenants
    """
    tenants = []

    for i in range(tenant_count):
        manager = TestDataManager()
        tenant = manager.create_complete_tenant_data(
            tenant_name=f"Multi-Tenant Test {i+1}",
            **kwargs
        )
        tenants.append(tenant)

    logger.info(f"Created multi-tenant test data: {len(tenants)} tenants")
    return tenants


def validate_migrations() -> bool:
    """
    Validate that all migrations are applied correctly.

    Returns:
        True if migrations are valid, False otherwise
    """
    try:
        # Check for unapplied migrations
        from django.core.management import call_command
        from io import StringIO

        output = StringIO()
        call_command("showmigrations", "--plan", stdout=output)
        output_str = output.getvalue()

        # Check for unapplied migrations
        if "[ ]" in output_str:
            logger.warning("Unapplied migrations detected")
            return False

        logger.info("All migrations are applied")
        return True

    except Exception as e:
        logger.error(f"Error validating migrations: {e}")
        return False


def reset_test_database(
    keep_db: bool = False,
    verbosity: int = 1
):
    """
    Reset test database (drop and recreate).

    Args:
        keep_db: If True, keep the database (don't drop it)
        verbosity: Verbosity level (0=minimal, 1=normal, 2=verbose)
    """
    try:
        # Flush database (remove all data)
        call_command("flush", "--no-input", verbosity=verbosity)

        if not keep_db:
            # Drop and recreate test database
            call_command("migrate", "--run-syncdb", verbosity=verbosity)

        logger.info("Test database reset successfully")

    except Exception as e:
        logger.error(f"Error resetting test database: {e}")
        raise


class TestDatabaseIsolationMixin:
    """
    Mixin for test classes to ensure proper database isolation.

    Usage:
        class MyTest(TestDatabaseIsolationMixin, TestCase):
            def setUp(self):
                super().setUp()
                # Your test setup
    """

    def setUp(self):
        """Set up test isolation"""
        super().setUp()
        self.test_data_manager = TestDataManager()

    def tearDown(self):
        """Clean up test data"""
        if hasattr(self, "test_data_manager"):
            self.test_data_manager.cleanup()
        super().tearDown()

    @transaction.atomic
    def create_test_tenant(self, **kwargs) -> Tenant:
        """Create a test tenant with proper isolation"""
        return self.test_data_manager.create_tenant_with_users(**kwargs)

    @transaction.atomic
    def create_test_data(self, **kwargs) -> Tenant:
        """Create complete test data with proper isolation"""
        return self.test_data_manager.create_complete_tenant_data(**kwargs)

