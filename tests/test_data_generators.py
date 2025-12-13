"""
Test Data Generators

Comprehensive generators for creating test data (contracts, assets, datasets, users, tenants).
These generators create realistic, varied test data for comprehensive testing.

Uses REAL factories (no mocks).
"""

import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, ComplianceStatus, DQStatus
from hub.apps.assets.tests.factories import AssetFactory
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.factories import DatasetFactory
from hub.apps.files.models import File, FileStatus
from hub.apps.files.tests.factories import FileFactory
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus

# Import factories
from tests.factories import JobFactory, TenantFactory, UserFactory

User = get_user_model()


class TestDataGenerator:
    """Comprehensive test data generator"""

    # ========== Tenant Generators ==========

    @staticmethod
    def generate_tenant(
        name: Optional[str] = None,
        slug: Optional[str] = None,
        kyc_status: Optional[KYCStatus] = None,
        **kwargs,
    ) -> Tenant:
        """
        Generate a test tenant with realistic data.

        Args:
            name: Tenant name (default: auto-generated)
            slug: Tenant slug (default: auto-generated)
            kyc_status: KYC status (default: VERIFIED)
            **kwargs: Additional fields

        Returns:
            Tenant instance
        """
        if name is None:
            company_names = [
                "Acme Corp",
                "TechStart Inc",
                "DataFlow Systems",
                "CloudAnalytics Ltd",
                "Digital Solutions",
            ]
            name = f"{random.choice(company_names)} {uuid.uuid4().hex[:6]}"

        if slug is None:
            slug = name.lower().replace(" ", "-").replace(".", "").replace(",", "")[:50]

        if kyc_status is None:
            kyc_status = KYCStatus.VERIFIED

        return TenantFactory.create_tenant(name=name, slug=slug, kyc_status=kyc_status, **kwargs)

    @staticmethod
    def generate_tenants(count: int = 5, **kwargs) -> List[Tenant]:
        """
        Generate multiple test tenants.

        Args:
            count: Number of tenants to generate
            **kwargs: Additional fields for all tenants

        Returns:
            List of Tenant instances
        """
        tenants = []
        for i in range(count):
            tenant = TestDataGenerator.generate_tenant(**kwargs)
            tenants.append(tenant)
        return tenants

    # ========== User Generators ==========

    @staticmethod
    def generate_user(
        tenant: Optional[Tenant] = None, email: Optional[str] = None, **kwargs
    ) -> User:
        """
        Generate a test user with realistic data.

        Args:
            tenant: Tenant instance (default: auto-generated)
            email: User email (default: auto-generated)
            **kwargs: Additional fields

        Returns:
            User instance
        """
        if tenant is None:
            tenant = TestDataGenerator.generate_tenant()

        if email is None:
            first_names = ["John", "Jane", "Bob", "Alice", "Charlie", "Diana"]
            last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia"]
            first = random.choice(first_names)
            last = random.choice(last_names)
            email = f"{first.lower()}.{last.lower()}.{uuid.uuid4().hex[:6]}@example.com"

        return UserFactory.create_user(tenant=tenant, email=email, **kwargs)

    @staticmethod
    def generate_users(tenant: Tenant, count: int = 5, **kwargs) -> List[User]:
        """
        Generate multiple test users for a tenant.

        Args:
            tenant: Tenant instance
            count: Number of users to generate
            **kwargs: Additional fields for all users

        Returns:
            List of User instances
        """
        users = []
        for i in range(count):
            user = TestDataGenerator.generate_user(tenant=tenant, **kwargs)
            users.append(user)
        return users

    # ========== Asset Generators ==========

    @staticmethod
    def generate_asset(
        tenant: Optional[Tenant] = None,
        created_by: Optional[User] = None,
        key: Optional[str] = None,
        name: Optional[str] = None,
        **kwargs,
    ) -> Asset:
        """
        Generate a test asset with realistic data.

        Args:
            tenant: Tenant instance (default: auto-generated)
            created_by: User who created the asset (default: auto-generated)
            key: Asset key (default: auto-generated)
            name: Asset name (default: auto-generated)
            **kwargs: Additional fields

        Returns:
            Asset instance
        """
        if tenant is None:
            tenant = TestDataGenerator.generate_tenant()

        if created_by is None:
            created_by = TestDataGenerator.generate_user(tenant=tenant)

        if key is None:
            asset_types = ["customer", "orders", "products", "transactions", "analytics"]
            asset_type = random.choice(asset_types)
            key = f"{asset_type}-data-{uuid.uuid4().hex[:8]}"

        if name is None:
            name = f"{asset_type.title()} Data Asset"

        return AssetFactory.create_asset(
            tenant=tenant, created_by=created_by, key=key, name=name, **kwargs
        )

    @staticmethod
    def generate_assets(
        tenant: Optional[Tenant] = None,
        created_by: Optional[User] = None,
        count: int = 10,
        **kwargs,
    ) -> List[Asset]:
        """
        Generate multiple test assets.

        Args:
            tenant: Tenant instance (default: auto-generated)
            created_by: User who created the assets (default: auto-generated)
            count: Number of assets to generate
            **kwargs: Additional fields for all assets

        Returns:
            List of Asset instances
        """
        if tenant is None:
            tenant = TestDataGenerator.generate_tenant()

        if created_by is None:
            created_by = TestDataGenerator.generate_user(tenant=tenant)

        assets = []
        for i in range(count):
            asset = TestDataGenerator.generate_asset(tenant=tenant, created_by=created_by, **kwargs)
            assets.append(asset)
        return assets

    # ========== Contract Generators ==========

    @staticmethod
    def generate_contract(
        tenant: Optional[Tenant] = None,
        created_by: Optional[User] = None,
        asset: Optional[Asset] = None,
        name: Optional[str] = None,
        field_count: int = 10,
        **kwargs,
    ) -> Contract:
        """
        Generate a test contract with realistic data.

        Args:
            tenant: Tenant instance (default: auto-generated)
            created_by: User who created the contract (default: auto-generated)
            asset: Asset instance (default: auto-generated)
            name: Contract name (default: auto-generated)
            field_count: Number of schema fields (default: 10)
            **kwargs: Additional fields

        Returns:
            Contract instance
        """
        if tenant is None:
            tenant = TestDataGenerator.generate_tenant()

        if created_by is None:
            created_by = TestDataGenerator.generate_user(tenant=tenant)

        if asset is None:
            asset = TestDataGenerator.generate_asset(tenant=tenant, created_by=created_by)

        if name is None:
            contract_names = [
                "Customer Data Contract",
                "Order Processing Contract",
                "Product Catalog Contract",
                "Analytics Data Contract",
                "Transaction Data Contract",
            ]
            name = f"{random.choice(contract_names)} {uuid.uuid4().hex[:6]}"

        # Generate schema fields
        field_types = ["string", "integer", "number", "boolean", "date", "timestamp"]
        schema_fields = []
        for i in range(field_count):
            field_type = random.choice(field_types)
            field = {
                "name": f"field_{i+1}",
                "data_type": field_type,
                "nullable": random.choice([True, False]),
                "description": f"Field {i+1} of type {field_type}",
            }

            # Add type-specific properties
            if field_type == "string":
                field["max_length"] = random.choice([50, 100, 255, 500])
            elif field_type in ["integer", "number"]:
                field["minimum"] = 0
                field["maximum"] = random.choice([100, 1000, 10000])

            schema_fields.append(field)

        return ContractFactoryEnhanced.create_contract(
            tenant=tenant,
            created_by=created_by,
            asset=asset,
            name=name,
            schema_fields=schema_fields,
            primary_key=[schema_fields[0]["name"]] if schema_fields else [],
            **kwargs,
        )

    @staticmethod
    def generate_contracts(
        tenant: Optional[Tenant] = None, created_by: Optional[User] = None, count: int = 5, **kwargs
    ) -> List[Contract]:
        """
        Generate multiple test contracts.

        Args:
            tenant: Tenant instance (default: auto-generated)
            created_by: User who created the contracts (default: auto-generated)
            count: Number of contracts to generate
            **kwargs: Additional fields for all contracts

        Returns:
            List of Contract instances
        """
        if tenant is None:
            tenant = TestDataGenerator.generate_tenant()

        if created_by is None:
            created_by = TestDataGenerator.generate_user(tenant=tenant)

        contracts = []
        for i in range(count):
            contract = TestDataGenerator.generate_contract(
                tenant=tenant, created_by=created_by, **kwargs
            )
            contracts.append(contract)
        return contracts

    # ========== Dataset Generators ==========

    @staticmethod
    def generate_dataset(
        tenant: Optional[Tenant] = None,
        created_by: Optional[User] = None,
        asset: Optional[Asset] = None,
        file: Optional[File] = None,
        row_count: Optional[int] = None,
        **kwargs,
    ) -> Dataset:
        """
        Generate a test dataset with realistic data.

        Args:
            tenant: Tenant instance (default: auto-generated)
            created_by: User who created the dataset (default: auto-generated)
            asset: Asset instance (default: auto-generated)
            file: File instance (default: auto-generated)
            row_count: Number of rows (default: random 100-10000)
            **kwargs: Additional fields

        Returns:
            Dataset instance
        """
        if tenant is None:
            tenant = TestDataGenerator.generate_tenant()

        if created_by is None:
            created_by = TestDataGenerator.generate_user(tenant=tenant)

        if asset is None:
            asset = TestDataGenerator.generate_asset(tenant=tenant, created_by=created_by)

        if file is None:
            file = FileFactory.create_file(tenant=tenant, created_by=created_by)

        if row_count is None:
            row_count = random.randint(100, 10000)

        return DatasetFactory.create_dataset(
            tenant=tenant,
            file=file,
            asset=asset,
            row_count=row_count,
            created_by=created_by,
            **kwargs,
        )

    @staticmethod
    def generate_datasets(
        tenant: Optional[Tenant] = None, created_by: Optional[User] = None, count: int = 5, **kwargs
    ) -> List[Dataset]:
        """
        Generate multiple test datasets.

        Args:
            tenant: Tenant instance (default: auto-generated)
            created_by: User who created the datasets (default: auto-generated)
            count: Number of datasets to generate
            **kwargs: Additional fields for all datasets

        Returns:
            List of Dataset instances
        """
        if tenant is None:
            tenant = TestDataGenerator.generate_tenant()

        if created_by is None:
            created_by = TestDataGenerator.generate_user(tenant=tenant)

        datasets = []
        for i in range(count):
            dataset = TestDataGenerator.generate_dataset(
                tenant=tenant, created_by=created_by, **kwargs
            )
            datasets.append(dataset)
        return datasets

    # ========== Job Generators ==========

    @staticmethod
    def generate_job(
        tenant: Optional[Tenant] = None,
        created_by: Optional[User] = None,
        job_type: Optional[JobType] = None,
        status: Optional[JobStatus] = None,
        **kwargs,
    ) -> Job:
        """
        Generate a test job with realistic data.

        Args:
            tenant: Tenant instance (default: auto-generated)
            created_by: User who created the job (default: auto-generated)
            job_type: Job type (default: random)
            status: Job status (default: PENDING)
            **kwargs: Additional fields

        Returns:
            Job instance
        """
        if tenant is None:
            tenant = TestDataGenerator.generate_tenant()

        if created_by is None:
            created_by = TestDataGenerator.generate_user(tenant=tenant)

        if job_type is None:
            job_type = random.choice(list(JobType))

        if status is None:
            status = JobStatus.PENDING

        return JobFactory.create_job(
            tenant=tenant, type=job_type, status=status, created_by=created_by, **kwargs
        )

    @staticmethod
    def generate_jobs(
        tenant: Optional[Tenant] = None,
        created_by: Optional[User] = None,
        count: int = 10,
        **kwargs,
    ) -> List[Job]:
        """
        Generate multiple test jobs.

        Args:
            tenant: Tenant instance (default: auto-generated)
            created_by: User who created the jobs (default: auto-generated)
            count: Number of jobs to generate
            **kwargs: Additional fields for all jobs

        Returns:
            List of Job instances
        """
        if tenant is None:
            tenant = TestDataGenerator.generate_tenant()

        if created_by is None:
            created_by = TestDataGenerator.generate_user(tenant=tenant)

        jobs = []
        for i in range(count):
            job = TestDataGenerator.generate_job(tenant=tenant, created_by=created_by, **kwargs)
            jobs.append(job)
        return jobs

    # ========== Complete Test Data Generators ==========

    @staticmethod
    def generate_complete_test_environment(
        tenant: Optional[Tenant] = None,
        num_users: int = 3,
        num_assets: int = 10,
        num_contracts: int = 5,
        num_datasets: int = 5,
        num_jobs: int = 10,
    ) -> Dict[str, Any]:
        """
        Generate a complete test environment with all types of data.

        Args:
            tenant: Tenant instance (default: auto-generated)
            num_users: Number of users to generate
            num_assets: Number of assets to generate
            num_contracts: Number of contracts to generate
            num_datasets: Number of datasets to generate
            num_jobs: Number of jobs to generate

        Returns:
            Dictionary with all generated test data
        """
        if tenant is None:
            tenant = TestDataGenerator.generate_tenant()

        # Generate users
        users = TestDataGenerator.generate_users(tenant, count=num_users)
        primary_user = users[0] if users else TestDataGenerator.generate_user(tenant=tenant)

        # Generate assets
        assets = TestDataGenerator.generate_assets(
            tenant=tenant, created_by=primary_user, count=num_assets
        )

        # Generate contracts (linked to assets)
        contracts = []
        for i, asset in enumerate(assets[:num_contracts]):
            contract = TestDataGenerator.generate_contract(
                tenant=tenant, created_by=primary_user, asset=asset
            )
            contracts.append(contract)

        # Generate datasets (linked to assets)
        datasets = []
        for i, asset in enumerate(assets[:num_datasets]):
            dataset = TestDataGenerator.generate_dataset(
                tenant=tenant, created_by=primary_user, asset=asset
            )
            datasets.append(dataset)

        # Generate jobs
        jobs = TestDataGenerator.generate_jobs(
            tenant=tenant, created_by=primary_user, count=num_jobs
        )

        return {
            "tenant": tenant,
            "users": users,
            "primary_user": primary_user,
            "assets": assets,
            "contracts": contracts,
            "datasets": datasets,
            "jobs": jobs,
        }
