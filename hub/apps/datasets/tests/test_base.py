"""
Base test classes for datasets tests to follow DRY principle.

This module provides common base classes to eliminate code duplication
in setUp methods across test files.
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.datasets.services import DatasetService
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

User = get_user_model()


class DatasetsTestBase(TestCase):
    """Base test class for datasets tests with common setUp code."""

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        uid = str(uuid.uuid4())[:8]
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create service
        self.service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create file with real S3 content so schema inference can run.
        file_id = uuid.uuid4()
        storage_path = f"{self.tenant.id}/{file_id}/test.csv"
        csv_body = b"id,name\n1,alice\n2,bob\n"
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=len(csv_body),
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=storage_path,
            created_by=self.user,
        )
        # Upload the CSV to S3/MinIO so dataset service schema inference
        # has real bytes to work with (D93 removed the mock fallback).
        # Surface failures via ``storage_available`` so downstream tests
        # can skip rather than failing with an opaque storage error.
        self.storage_available = False
        try:
            import boto3
            from django.conf import settings
            s3 = boto3.client(
                "s3",
                endpoint_url=getattr(settings, "AWS_S3_ENDPOINT_URL", None),
                aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", ""),
                aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", ""),
            )
            s3.put_object(
                Bucket=getattr(settings, "AWS_STORAGE_BUCKET_NAME", "hub-test"),
                Key=storage_path,
                Body=csv_body,
                ContentType="text/csv",
            )
            self.storage_available = True
        except Exception:
            pass


class DatasetsTransactionTestBase(TestCase):
    """Base test class for datasets tests requiring TransactionTestCase."""

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        uid = str(uuid.uuid4())[:8]
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create service
        self.service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create file with real S3 content so schema inference can run.
        file_id = uuid.uuid4()
        storage_path = f"{self.tenant.id}/{file_id}/test.csv"
        csv_body = b"id,name\n1,alice\n2,bob\n"
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=len(csv_body),
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=storage_path,
            created_by=self.user,
        )
        self.storage_available = False
        try:
            import boto3
            from django.conf import settings
            s3 = boto3.client(
                "s3",
                endpoint_url=getattr(settings, "AWS_S3_ENDPOINT_URL", None),
                aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", ""),
                aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", ""),
            )
            s3.put_object(
                Bucket=getattr(settings, "AWS_STORAGE_BUCKET_NAME", "hub-test"),
                Key=storage_path,
                Body=csv_body,
                ContentType="text/csv",
            )
            self.storage_available = True
        except Exception:
            pass


class DatasetsAPITestBase(DatasetsTestBase):
    """Base test class for API tests with authenticated client."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        # Ensure tenant has active subscription so TenantSuspensionMiddleware allows writes (POST/PUT/PATCH/DELETE)
        ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)


class DatasetsAPITransactionTestBase(DatasetsTransactionTestBase):
    """Base test class for API tests requiring TransactionTestCase."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        # Ensure tenant has active subscription so TenantSuspensionMiddleware allows writes (POST/PUT/PATCH/DELETE)
        ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
