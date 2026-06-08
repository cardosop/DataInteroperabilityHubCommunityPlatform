"""
Test Data Fixtures

Pre-defined sample test data (contracts, assets, datasets, users, tenants).
These fixtures provide ready-to-use test data for common test scenarios.

Uses REAL factories (no mocks).
"""

import uuid
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model

from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, ComplianceStatus, DQStatus
from hub.apps.assets.tests.factories import AssetFactory
from hub.apps.contracts.models import Contract
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.factories import DatasetFactory
from hub.apps.files.models import File
from hub.apps.files.tests.factories import FileFactory
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus

# Import factories and generators
from tests.factories import JobFactory, TenantFactory, UserFactory
from tests.test_data_generators import TestDataGenerator

User = get_user_model()


class SampleTestData:
    """Pre-defined sample test data"""

    # ========== Sample Tenants ==========

    @staticmethod
    def create_sample_tenant_verified() -> Tenant:
        """Create a sample verified tenant"""
        return TenantFactory.create_tenant(
            name=f"Sample Verified Tenant {uuid.uuid4().hex[:8]}",
            slug=f"sample-verified-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

    @staticmethod
    def create_sample_tenant_unverified() -> Tenant:
        """Create a sample unverified tenant"""
        return TenantFactory.create_tenant(
            name=f"Sample Unverified Tenant {uuid.uuid4().hex[:8]}",
            slug=f"sample-unverified-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )

    # ========== Sample Users ==========

    @staticmethod
    def create_sample_user(tenant: Tenant) -> User:
        """Create a sample user"""
        return UserFactory.create_user(
            tenant=tenant,
            email=f"sample.user-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Sample User",
        )

    @staticmethod
    def create_sample_admin_user(tenant: Tenant) -> User:
        """Create a sample admin user"""
        return UserFactory.create_user(
            tenant=tenant,
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Admin User",
        )

    # ========== Sample Assets ==========

    @staticmethod
    def create_sample_asset_customer_data(tenant: Tenant, created_by: User) -> Asset:
        """Create a sample customer data asset"""
        return AssetFactory.create_asset(
            tenant=tenant,
            created_by=created_by,
            key="customer-data",
            name="Customer Data Asset",
            description="Sample customer data asset for testing",
            domain="sales",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.INTERNAL,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )

    @staticmethod
    def create_sample_asset_orders(tenant: Tenant, created_by: User) -> Asset:
        """Create a sample orders asset"""
        return AssetFactory.create_asset(
            tenant=tenant,
            created_by=created_by,
            key="orders-data",
            name="Orders Data Asset",
            description="Sample orders data asset for testing",
            domain="commerce",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.INTERNAL,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )

    @staticmethod
    def create_sample_asset_products(tenant: Tenant, created_by: User) -> Asset:
        """Create a sample products asset"""
        return AssetFactory.create_asset(
            tenant=tenant,
            created_by=created_by,
            key="products-data",
            name="Products Data Asset",
            description="Sample products data asset for testing",
            domain="catalog",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.INTERNAL,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )

    # ========== Sample Contracts ==========

    @staticmethod
    def create_sample_contract_customer(
        tenant: Tenant, created_by: User, asset: Optional[Asset] = None
    ) -> Contract:
        """Create a sample customer data contract"""
        if asset is None:
            asset = SampleTestData.create_sample_asset_customer_data(tenant, created_by)

        return ContractFactoryEnhanced.create_contract(
            tenant=tenant,
            created_by=created_by,
            asset=asset,
            name="Customer Data Contract",
            schema_fields=[
                {
                    "name": "customer_id",
                    "data_type": "string",
                    "nullable": False,
                    "description": "Unique customer identifier",
                    "semantic_type": "CUSTOMER_ID",
                    "format": None,
                    "pattern": "^CUST-[0-9]{8}$",
                    "min_length": 12,
                    "max_length": 12,
                },
                {
                    "name": "email",
                    "data_type": "string",
                    "nullable": False,
                    "description": "Customer email address",
                    "semantic_type": "EMAIL",
                    "format": "email",
                    "max_length": 255,
                },
                {
                    "name": "name",
                    "data_type": "string",
                    "nullable": False,
                    "description": "Customer full name",
                    "semantic_type": "PERSON_NAME",
                    "max_length": 200,
                },
                {
                    "name": "created_at",
                    "data_type": "timestamp",
                    "nullable": False,
                    "description": "Account creation timestamp",
                    "semantic_type": "TIMESTAMP",
                },
            ],
            primary_key=["customer_id"],
        )

    @staticmethod
    def create_sample_contract_orders(
        tenant: Tenant, created_by: User, asset: Optional[Asset] = None
    ) -> Contract:
        """Create a sample orders contract"""
        if asset is None:
            asset = SampleTestData.create_sample_asset_orders(tenant, created_by)

        return ContractFactoryEnhanced.create_contract(
            tenant=tenant,
            created_by=created_by,
            asset=asset,
            name="Orders Data Contract",
            schema_fields=[
                {
                    "name": "order_id",
                    "data_type": "string",
                    "nullable": False,
                    "description": "Unique order identifier",
                    "semantic_type": "ORDER_ID",
                    "pattern": "^ORD-[0-9]{8}$",
                },
                {
                    "name": "customer_id",
                    "data_type": "string",
                    "nullable": False,
                    "description": "Customer identifier",
                    "semantic_type": "CUSTOMER_ID",
                },
                {
                    "name": "order_date",
                    "data_type": "date",
                    "nullable": False,
                    "description": "Order date",
                    "semantic_type": "DATE",
                },
                {
                    "name": "total_amount",
                    "data_type": "number",
                    "nullable": False,
                    "description": "Order total amount",
                    "semantic_type": "CURRENCY",
                    "minimum": 0.0,
                },
            ],
            primary_key=["order_id"],
        )

    # ========== Sample Datasets ==========

    @staticmethod
    def create_sample_dataset_customer(
        tenant: Tenant, created_by: User, asset: Optional[Asset] = None
    ) -> Dataset:
        """Create a sample customer dataset"""
        if asset is None:
            asset = SampleTestData.create_sample_asset_customer_data(tenant, created_by)

        file = FileFactory.create_file(
            tenant=tenant,
            created_by=created_by,
            name="customer_data.csv",
            content_type="text/csv",
            size=50000,  # 50 KB
        )

        return DatasetFactory.create_dataset(
            tenant=tenant,
            file=file,
            asset=asset,
            created_by=created_by,
            schema_json={
                "fields": [
                    {
                        "name": "customer_id",
                        "type": "string",
                        "nullable": False,
                        "description": "Unique customer identifier",
                    },
                    {
                        "name": "email",
                        "type": "string",
                        "nullable": False,
                        "description": "Customer email address",
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "nullable": False,
                        "description": "Customer full name",
                    },
                ]
            },
            sample_data_json=[
                {
                    "customer_id": "CUST-00000001",
                    "email": "john.doe@example.com",
                    "name": "John Doe",
                },
                {
                    "customer_id": "CUST-00000002",
                    "email": "jane.smith@example.com",
                    "name": "Jane Smith",
                },
            ],
            row_count=1000,
            format="CSV",
        )

    @staticmethod
    def create_sample_dataset_orders(
        tenant: Tenant, created_by: User, asset: Optional[Asset] = None
    ) -> Dataset:
        """Create a sample orders dataset"""
        if asset is None:
            asset = SampleTestData.create_sample_asset_orders(tenant, created_by)

        file = FileFactory.create_file(
            tenant=tenant,
            created_by=created_by,
            name="orders_data.csv",
            content_type="text/csv",
            size=100000,  # 100 KB
        )

        return DatasetFactory.create_dataset(
            tenant=tenant,
            file=file,
            asset=asset,
            created_by=created_by,
            schema_json={
                "fields": [
                    {
                        "name": "order_id",
                        "type": "string",
                        "nullable": False,
                        "description": "Unique order identifier",
                    },
                    {
                        "name": "customer_id",
                        "type": "string",
                        "nullable": False,
                        "description": "Customer identifier",
                    },
                    {
                        "name": "order_date",
                        "type": "date",
                        "nullable": False,
                        "description": "Order date",
                    },
                    {
                        "name": "total_amount",
                        "type": "number",
                        "nullable": False,
                        "description": "Order total amount",
                    },
                ]
            },
            sample_data_json=[
                {
                    "order_id": "ORD-00000001",
                    "customer_id": "CUST-00000001",
                    "order_date": "2025-01-15",
                    "total_amount": 99.99,
                },
                {
                    "order_id": "ORD-00000002",
                    "customer_id": "CUST-00000002",
                    "order_date": "2025-01-16",
                    "total_amount": 149.50,
                },
            ],
            row_count=5000,
            format="CSV",
        )

    # ========== Sample Jobs ==========

    @staticmethod
    def create_sample_job_dq_run(tenant: Tenant, created_by: User) -> Job:
        """Create a sample DQ run job"""
        return JobFactory.create_job(
            tenant=tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            created_by=created_by,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
        )

    @staticmethod
    def create_sample_job_compliance_run(tenant: Tenant, created_by: User) -> Job:
        """Create a sample compliance run job"""
        return JobFactory.create_job(
            tenant=tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            created_by=created_by,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
        )

    # ========== Complete Sample Environments ==========

    @staticmethod
    def create_sample_environment_basic() -> Dict[str, Any]:
        """
        Create a basic sample test environment.

        Returns:
            Dictionary with tenant, user, assets, contracts, datasets
        """
        tenant = SampleTestData.create_sample_tenant_verified()
        user = SampleTestData.create_sample_user(tenant)

        # Create assets
        customer_asset = SampleTestData.create_sample_asset_customer_data(tenant, user)
        orders_asset = SampleTestData.create_sample_asset_orders(tenant, user)
        products_asset = SampleTestData.create_sample_asset_products(tenant, user)

        # Create contracts
        customer_contract = SampleTestData.create_sample_contract_customer(
            tenant, user, customer_asset
        )
        orders_contract = SampleTestData.create_sample_contract_orders(tenant, user, orders_asset)

        # Create datasets
        customer_dataset = SampleTestData.create_sample_dataset_customer(
            tenant, user, customer_asset
        )
        orders_dataset = SampleTestData.create_sample_dataset_orders(tenant, user, orders_asset)

        return {
            "tenant": tenant,
            "user": user,
            "assets": [customer_asset, orders_asset, products_asset],
            "contracts": [customer_contract, orders_contract],
            "datasets": [customer_dataset, orders_dataset],
        }

    @staticmethod
    def create_sample_environment_complete() -> Dict[str, Any]:
        """
        Create a complete sample test environment with all data types.

        Returns:
            Dictionary with all test data
        """
        # Use generator for complete environment
        return TestDataGenerator.generate_complete_test_environment(
            num_users=5,
            num_assets=20,
            num_contracts=10,
            num_datasets=10,
            num_jobs=20,
        )
