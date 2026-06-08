"""
Comprehensive unit tests for ComplianceService.

Tests cover:
- create_compliance_run method
- Success scenarios
- Failure scenarios
- Edge cases
- Error handling
- Business rules integration

All tests use real implementations (no mocks/stubs).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.compliance.models import ComplianceRunStatus
from hub.apps.compliance.services import ComplianceService
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ComplianceServiceTest(TestCase):
    """Comprehensive tests for ComplianceService"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Ensure tenant has active subscription so PlanLimitService.check_limit()
        # does not raise NotFoundError("No FREE plan found").
        ensure_tenant_has_active_subscription(self.tenant)

        # Create service instance
        self.service = ComplianceService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    # ========== CREATE COMPLIANCE RUN TESTS ==========

    def test_create_compliance_run_with_asset_success(self):
        """Test creating compliance run with asset successfully"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        compliance_run = self.service.create_compliance_run(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
        )

        self.assertIsNotNone(compliance_run.id)
        self.assertEqual(compliance_run.tenant, self.tenant)
        self.assertEqual(compliance_run.asset, asset)
        self.assertEqual(compliance_run.status, ComplianceRunStatus.PENDING)
        self.assertIsNotNone(compliance_run.job)

    def test_create_compliance_run_with_dataset_success(self):
        """Test creating compliance run with dataset successfully"""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            created_by=self.user,
        )

        compliance_run = self.service.create_compliance_run(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            dataset_id=str(dataset.id),
            scan_mode="internal",
        )

        self.assertIsNotNone(compliance_run.id)
        self.assertEqual(compliance_run.dataset, dataset)
        self.assertEqual(compliance_run.asset, asset)  # Should inherit from dataset

    def test_create_compliance_run_with_file_success(self):
        """Test creating compliance run with file successfully"""
        from hub.apps.files.models import File, FileStatus

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        compliance_run = self.service.create_compliance_run(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(file_obj.id),
            scan_mode="external",
        )

        self.assertIsNotNone(compliance_run.id)
        self.assertEqual(compliance_run.file, file_obj)
        self.assertEqual(compliance_run.status, ComplianceRunStatus.PENDING)

    def test_create_compliance_run_with_applicable_regulations(self):
        """Test creating compliance run with applicable regulations"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        compliance_run = self.service.create_compliance_run(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
            applicable_regulations=["GDPR", "HIPAA"],
        )

        self.assertIsNotNone(compliance_run.id)
        # Regulations should be stored in job details
        self.assertIn("applicable_regulations", compliance_run.job.details_json)
        self.assertEqual(
            compliance_run.job.details_json["applicable_regulations"], ["GDPR", "HIPAA"]
        )

    def test_create_compliance_run_creates_job(self):
        """Test creating compliance run creates associated job"""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.jobs.models import JobType

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        compliance_run = self.service.create_compliance_run(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
        )

        self.assertIsNotNone(compliance_run.job)
        self.assertEqual(compliance_run.job.type, JobType.COMPLIANCE_RUN)
        self.assertEqual(compliance_run.job.resource_id, str(compliance_run.id))

    def test_create_compliance_run_with_resolved_instances(self):
        """Test creating compliance run with pre-resolved instances"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        compliance_run = self.service.create_compliance_run(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset=asset,
            scan_mode="internal",
        )

        self.assertIsNotNone(compliance_run.id)
        self.assertEqual(compliance_run.asset, asset)

    # ========== ERROR HANDLING TESTS ==========

    def test_create_compliance_run_asset_not_found(self):
        """Test creating compliance run with non-existent asset raises ValidationError"""
        fake_asset_id = uuid.uuid4()

        with self.assertRaises(ValidationError) as context:
            self.service.create_compliance_run(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                asset_id=str(fake_asset_id),
                scan_mode="internal",
            )

        self.assertEqual(context.exception.code, "BUSINESS_RULES_VALIDATION")
        self.assertIn("Asset not found", str(context.exception))

    def test_create_compliance_run_dataset_not_found(self):
        """Test creating compliance run with non-existent dataset raises ValidationError"""
        fake_dataset_id = uuid.uuid4()

        with self.assertRaises(ValidationError) as context:
            self.service.create_compliance_run(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                dataset_id=str(fake_dataset_id),
                scan_mode="internal",
            )

        self.assertEqual(context.exception.code, "BUSINESS_RULES_VALIDATION")
        self.assertIn("Dataset not found", str(context.exception))

    def test_create_compliance_run_file_not_found(self):
        """Test creating compliance run with non-existent file raises ValidationError"""
        fake_file_id = uuid.uuid4()

        with self.assertRaises(ValidationError) as context:
            self.service.create_compliance_run(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                file_id=str(fake_file_id),
                scan_mode="external",
            )

        self.assertEqual(context.exception.code, "BUSINESS_RULES_VALIDATION")
        self.assertIn("File not found", str(context.exception))

    def test_create_compliance_run_dataset_mismatch(self):
        """Test creating compliance run with dataset that doesn't belong to asset raises ValidationError"""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus

        asset1 = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-1",
            name="Test Asset 1",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-2",
            name="Test Asset 2",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset2,  # Belongs to asset2
            file=file_obj,
            format="CSV",
            created_by=self.user,
        )

        with self.assertRaises(ValidationError) as context:
            self.service.create_compliance_run(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                asset_id=str(asset1.id),  # Specify asset1
                dataset_id=str(dataset.id),  # But dataset belongs to asset2
                scan_mode="internal",
            )

        self.assertEqual(context.exception.code, "BUSINESS_RULES_VALIDATION")
        self.assertIn("does not belong", str(context.exception))

    def test_create_compliance_run_no_resources(self):
        """Test creating compliance run with no resources raises ValidationError via business rules"""
        # Business rules should reject when no asset, dataset, or file is provided
        with self.assertRaises(ValidationError) as context:
            self.service.create_compliance_run(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                scan_mode="internal",
            )

        self.assertEqual(context.exception.code, "BUSINESS_RULES_VALIDATION")

    def test_create_compliance_run_tenant_not_found(self):
        """Test creating compliance run with non-existent tenant raises NotFoundError"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        fake_tenant_id = uuid.uuid4()

        with self.assertRaises(NotFoundError):
            self.service.create_compliance_run(
                tenant_id=str(fake_tenant_id),
                user_id=str(self.user.id),
                asset_id=str(asset.id),
                scan_mode="internal",
            )

    def test_create_compliance_run_user_not_found(self):
        """Test creating compliance run with non-existent user raises NotFoundError"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        fake_user_id = uuid.uuid4()

        with self.assertRaises(NotFoundError):
            self.service.create_compliance_run(
                tenant_id=str(self.tenant.id),
                user_id=str(fake_user_id),
                asset_id=str(asset.id),
                scan_mode="internal",
            )

    # ========== EDGE CASES ==========

    def test_create_compliance_run_cross_tenant_asset_returns_validation_error(self):
        """Creating a compliance run for an asset that belongs to a different tenant
        raises ValidationError with code BUSINESS_RULES_VALIDATION.

        The service uses a tenant-scoped Asset lookup (``Asset.objects.get(
        id=asset_id, tenant_id=tenant_id)``), so a cross-tenant asset produces
        ``Asset.DoesNotExist`` → "Asset not found", which is the same error
        surface as a genuinely missing asset.  This is intentional from a
        security standpoint — an attacker must not learn whether an arbitrary
        UUID belongs to another tenant."""
        from hub.apps.assets.models import Asset, AssetStatus

        # Create another tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        asset = Asset.objects.create(
            tenant=other_tenant,  # Different tenant
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError) as context:
            self.service.create_compliance_run(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                asset_id=str(asset.id),
                scan_mode="internal",
            )

        self.assertEqual(context.exception.code, "BUSINESS_RULES_VALIDATION")
        self.assertIn("Asset not found", str(context.exception))
        # Confirm the rejection is from the tenant-scoped lookup, not a
        # different validation path — the asset exists in *another* tenant.
        self.assertIn(str(asset.id), str(context.exception.details.get("asset_id", "")))

    def test_create_compliance_run_default_scan_mode(self):
        """Test creating compliance run defaults scan_mode to internal"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        compliance_run = self.service.create_compliance_run(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset.id),
            # scan_mode not specified
        )

        self.assertIsNotNone(compliance_run.id)
        self.assertEqual(compliance_run.job.details_json["scan_mode"], "internal")

    def test_create_compliance_run_empty_regulations(self):
        """Test creating compliance run with empty regulations list"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        compliance_run = self.service.create_compliance_run(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
            applicable_regulations=[],
        )

        self.assertIsNotNone(compliance_run.id)
        self.assertEqual(compliance_run.job.details_json["applicable_regulations"], [])

    def test_create_compliance_run_job_resource_id_updated(self):
        """Test that job resource_id is updated after compliance run creation"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        compliance_run = self.service.create_compliance_run(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
        )

        # Job resource_id should be updated to compliance_run.id
        compliance_run.job.refresh_from_db()
        self.assertEqual(str(compliance_run.job.resource_id), str(compliance_run.id))
        self.assertIn("compliance_run_id", compliance_run.job.details_json)
        self.assertEqual(
            compliance_run.job.details_json["compliance_run_id"], str(compliance_run.id)
        )
