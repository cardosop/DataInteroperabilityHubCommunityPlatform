"""
Comprehensive unit tests for Compliance serializers.

Tests cover:
- Serialization/deserialization
- Validation (required fields, data types, constraints)
- Edge cases and error handling
- Read-only fields enforcement

All tests use real implementations (no mocks/stubs).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.compliance.serializers import (
    ComplianceRunCreateSerializer,
    ComplianceRunSerializer,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ComplianceRunSerializerTest(TestCase):
    """Comprehensive tests for ComplianceRunSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create job
        from hub.apps.jobs.models import Job, JobStatus, JobType

        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            created_by=self.user,
        )

        # Create asset (ComplianceRun requires at least one of asset, dataset, or file)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-compliance",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        # Create compliance run
        self.compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=self.job,
            asset=self.asset,
            status=ComplianceRunStatus.PENDING,
        )

    # ========== SERIALIZATION TESTS ==========

    def test_compliance_run_serializer_serializes_all_fields(self):
        """Test ComplianceRunSerializer serializes all fields"""
        serializer = ComplianceRunSerializer(self.compliance_run)
        data = serializer.data

        self.assertIn("id", data)
        self.assertIn("tenant", data)
        self.assertIn("status", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_compliance_run_serializer_read_only_fields(self):
        """Test ComplianceRunSerializer read-only fields cannot be set"""
        serializer = ComplianceRunSerializer(
            self.compliance_run,
            data={
                "id": "new-id",
                "status": ComplianceRunStatus.SUCCEEDED,
                "created_at": timezone.now(),
            },
            partial=True,
        )

        # Read-only fields should be ignored
        serializer.is_valid()
        self.assertEqual(str(self.compliance_run.id), serializer.data["id"])

    def test_compliance_run_serializer_with_asset(self):
        """Test ComplianceRunSerializer with asset"""
        from hub.apps.assets.models import Asset, AssetStatus

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.compliance_run.asset = asset
        self.compliance_run.save()

        serializer = ComplianceRunSerializer(self.compliance_run)
        data = serializer.data

        self.assertIn("asset", data)
        self.assertEqual(str(data["asset"]), str(asset.id))

    def test_compliance_run_serializer_with_dataset(self):
        """Test ComplianceRunSerializer with dataset"""
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
            tenant=self.tenant, asset=asset, file=file_obj, format="CSV", created_by=self.user
        )

        self.compliance_run.dataset = dataset
        self.compliance_run.save()

        serializer = ComplianceRunSerializer(self.compliance_run)
        data = serializer.data

        self.assertIn("dataset", data)
        self.assertEqual(str(data["dataset"]), str(dataset.id))

    def test_compliance_run_serializer_with_file(self):
        """Test ComplianceRunSerializer with file"""
        from hub.apps.files.models import File, FileStatus

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        self.compliance_run.file = file_obj
        self.compliance_run.save()

        serializer = ComplianceRunSerializer(self.compliance_run)
        data = serializer.data

        self.assertIn("file", data)
        self.assertEqual(str(data["file"]), str(file_obj.id))

    def test_compliance_run_serializer_with_status(self):
        """Test ComplianceRunSerializer with different statuses"""
        statuses = [
            ComplianceRunStatus.PENDING,
            ComplianceRunStatus.RUNNING,
            ComplianceRunStatus.SUCCEEDED,
            ComplianceRunStatus.FAILED,
        ]

        for status_value in statuses:
            self.compliance_run.status = status_value
            self.compliance_run.save()

            serializer = ComplianceRunSerializer(self.compliance_run)
            data = serializer.data

            self.assertEqual(data["status"], status_value)

    def test_compliance_run_serializer_with_risk_level(self):
        """Test ComplianceRunSerializer with risk level"""
        self.compliance_run.risk_level = RiskLevel.HIGH
        self.compliance_run.save()

        serializer = ComplianceRunSerializer(self.compliance_run)
        data = serializer.data

        self.assertIn("risk_level", data)
        self.assertEqual(data["risk_level"], RiskLevel.HIGH)

    def test_compliance_run_serializer_with_overall_status(self):
        """Test ComplianceRunSerializer with overall status"""
        self.compliance_run.overall_status = "PASS"
        self.compliance_run.save()

        serializer = ComplianceRunSerializer(self.compliance_run)
        data = serializer.data

        self.assertIn("overall_status", data)
        self.assertEqual(data["overall_status"], "PASS")

    def test_compliance_run_serializer_with_allowed_to_store(self):
        """Test ComplianceRunSerializer with allowed_to_store"""
        self.compliance_run.allowed_to_store = True
        self.compliance_run.save()

        serializer = ComplianceRunSerializer(self.compliance_run)
        data = serializer.data

        self.assertIn("allowed_to_store", data)
        self.assertTrue(data["allowed_to_store"])

    def test_compliance_run_serializer_with_json_fields(self):
        """Test ComplianceRunSerializer with JSON fields"""
        self.compliance_run.detected_categories_json = {"EMAIL": {"count": 5}}
        self.compliance_run.column_findings_json = [
            {"column": "email", "pii_categories": ["EMAIL"]}
        ]
        self.compliance_run.regulation_mapping_json = {"GDPR": {"applies": True}}
        self.compliance_run.save()

        serializer = ComplianceRunSerializer(self.compliance_run)
        data = serializer.data

        self.assertIn("detected_categories_json", data)
        self.assertIn("column_findings_json", data)
        self.assertIn("regulation_mapping_json", data)
        self.assertEqual(data["detected_categories_json"], {"EMAIL": {"count": 5}})

    def test_compliance_run_serializer_with_timestamps(self):
        """Test ComplianceRunSerializer with timestamps"""
        started_at = timezone.now()
        completed_at = timezone.now()

        self.compliance_run.started_at = started_at
        self.compliance_run.completed_at = completed_at
        self.compliance_run.save()

        serializer = ComplianceRunSerializer(self.compliance_run)
        data = serializer.data

        self.assertIn("started_at", data)
        self.assertIn("completed_at", data)
        self.assertIsNotNone(data["started_at"])
        self.assertIsNotNone(data["completed_at"])

    # ========== EDGE CASES ==========

    def test_compliance_run_serializer_with_null_fields(self):
        """Test ComplianceRunSerializer with null optional fields (dataset, file null)"""
        # Model requires at least one of asset, dataset, file; use asset only
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            job=self.job,
            asset=self.asset,
            status=ComplianceRunStatus.PENDING,
        )

        serializer = ComplianceRunSerializer(compliance_run)
        data = serializer.data

        # Asset set; dataset and file should be null
        self.assertIsNotNone(data["asset"])
        self.assertIsNone(data["dataset"])
        self.assertIsNone(data["file"])


class ComplianceRunCreateSerializerTest(TestCase):
    """Comprehensive tests for ComplianceRunCreateSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create asset
        from hub.apps.assets.models import Asset, AssetStatus

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        # Create file
        from hub.apps.files.models import File, FileStatus

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

    # ========== VALIDATION TESTS ==========

    def test_create_serializer_valid_with_asset_id(self):
        """Test ComplianceRunCreateSerializer valid with asset_id"""
        serializer = ComplianceRunCreateSerializer(
            data={"asset_id": str(self.asset.id), "scan_mode": "internal"}
        )

        self.assertTrue(serializer.is_valid())
        self.assertEqual(str(serializer.validated_data["asset_id"]), str(self.asset.id))
        self.assertEqual(serializer.validated_data["scan_mode"], "internal")

    def test_create_serializer_valid_with_dataset_id(self):
        """Test ComplianceRunCreateSerializer valid with dataset_id"""
        from hub.apps.datasets.models import Dataset

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            created_by=self.user,
        )

        serializer = ComplianceRunCreateSerializer(
            data={"dataset_id": str(dataset.id), "scan_mode": "internal"}
        )

        self.assertTrue(serializer.is_valid())
        self.assertEqual(str(serializer.validated_data["dataset_id"]), str(dataset.id))

    def test_create_serializer_valid_with_file_id(self):
        """Test ComplianceRunCreateSerializer valid with file_id"""
        serializer = ComplianceRunCreateSerializer(
            data={"file_id": str(self.file.id), "scan_mode": "external"}
        )

        self.assertTrue(serializer.is_valid())
        self.assertEqual(str(serializer.validated_data["file_id"]), str(self.file.id))
        self.assertEqual(serializer.validated_data["scan_mode"], "external")

    def test_create_serializer_valid_with_applicable_regulations(self):
        """Test ComplianceRunCreateSerializer valid with applicable_regulations"""
        serializer = ComplianceRunCreateSerializer(
            data={
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
                "applicable_regulations": ["GDPR", "HIPAA"],
            }
        )

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["applicable_regulations"], ["GDPR", "HIPAA"])

    def test_create_serializer_default_scan_mode(self):
        """Test ComplianceRunCreateSerializer defaults scan_mode to internal"""
        serializer = ComplianceRunCreateSerializer(data={"asset_id": str(self.asset.id)})

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["scan_mode"], "internal")

    def test_create_serializer_scan_mode_choices(self):
        """Test ComplianceRunCreateSerializer scan_mode choices"""
        # Valid choices
        for scan_mode in ["internal", "external"]:
            serializer = ComplianceRunCreateSerializer(
                data={"asset_id": str(self.asset.id), "scan_mode": scan_mode}
            )
            self.assertTrue(serializer.is_valid(), f"Should accept {scan_mode}")

    def test_create_serializer_invalid_scan_mode(self):
        """Test ComplianceRunCreateSerializer rejects invalid scan_mode"""
        serializer = ComplianceRunCreateSerializer(
            data={"asset_id": str(self.asset.id), "scan_mode": "invalid"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("scan_mode", serializer.errors)

    def test_create_serializer_invalid_asset_id_format(self):
        """Test ComplianceRunCreateSerializer rejects invalid UUID format"""
        serializer = ComplianceRunCreateSerializer(
            data={"asset_id": "not-a-uuid", "scan_mode": "internal"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("asset_id", serializer.errors)

    def test_create_serializer_applicable_regulations_list(self):
        """Test ComplianceRunCreateSerializer accepts list of regulations"""
        serializer = ComplianceRunCreateSerializer(
            data={
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
                "applicable_regulations": ["GDPR", "CCPA", "HIPAA"],
            }
        )

        self.assertTrue(serializer.is_valid())
        regulations = serializer.validated_data["applicable_regulations"]
        self.assertIsInstance(regulations, list)
        self.assertEqual(len(regulations), 3)

    # ========== EDGE CASES ==========

    def test_create_serializer_empty_applicable_regulations(self):
        """Test ComplianceRunCreateSerializer accepts empty applicable_regulations"""
        serializer = ComplianceRunCreateSerializer(
            data={
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
                "applicable_regulations": [],
            }
        )

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["applicable_regulations"], [])

    def test_create_serializer_no_resource_ids(self):
        """Test ComplianceRunCreateSerializer validation allows no resource IDs (validated by business rules)"""
        # Note: Business rules will validate that at least one resource is provided
        # Serializer itself doesn't enforce this
        serializer = ComplianceRunCreateSerializer(data={"scan_mode": "internal"})

        # Serializer validation passes (business rules will catch this)
        self.assertTrue(serializer.is_valid())

    def test_create_serializer_multiple_resource_ids(self):
        """Test ComplianceRunCreateSerializer accepts multiple resource IDs"""
        from hub.apps.datasets.models import Dataset

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            created_by=self.user,
        )

        serializer = ComplianceRunCreateSerializer(
            data={
                "asset_id": str(self.asset.id),
                "dataset_id": str(dataset.id),
                "file_id": str(self.file.id),
                "scan_mode": "internal",
            }
        )

        # Serializer accepts multiple IDs (business rules will validate)
        self.assertTrue(serializer.is_valid())
