"""
Unit tests for Scheduled Ingestion serializers.

Covers ScheduledIngestionSerializer, ScheduledIngestionRunSerializer,
ScheduledIngestionCreateSerializer, ScheduledIngestionTriggerSerializer.
All tests use real DB and no mocks.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.scheduled_ingestion.serializers import (
    ScheduledIngestionCreateSerializer,
    ScheduledIngestionRunSerializer,
    ScheduledIngestionSerializer,
    ScheduledIngestionTriggerSerializer,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _tenant_user():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Serializer Test Tenant {uid}",
        slug=f"serializer-test-tenant-{uid}",
        status="ACTIVE",
        kyc_status="VERIFIED",
    )
    user = User.objects.create_user(
        email=f"serializer-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    return tenant, user


class ScheduledIngestionSerializerSuccessTest(TestCase):
    """ScheduledIngestionSerializer success scenarios."""

    def test_serialize_valid_scheduled_ingestion(self):
        """Serialize valid ScheduledIngestion; all expected fields present."""
        tenant, user = _tenant_user()
        si = ScheduledIngestion.objects.create(
            tenant=tenant,
            name="Daily Sync",
            description="Daily sync",
            source_type=SourceType.S3,
            source_config={"bucket": "my-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "02:00"},
            file_pattern=r".*\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=user,
        )
        serializer = ScheduledIngestionSerializer(si)
        data = serializer.data
        self.assertEqual(data["name"], "Daily Sync")
        self.assertEqual(data["source_type"], SourceType.S3)
        self.assertEqual(data["schedule_type"], ScheduleType.DAILY)
        self.assertIn("id", data)
        self.assertIn("tenant_name", data)
        self.assertIn("asset_name", data)
        self.assertIn("created_by_username", data)

    def test_deserialize_valid_data(self):
        """Valid input deserializes and validates successfully."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "Weekly Load",
            "source_type": SourceType.GCS,
            "source_config": {"bucket": "gcs-bucket"},
            "schedule_type": ScheduleType.WEEKLY,
            "schedule_config": {"days_of_week": [0, 1], "time": "03:00"},
            "file_pattern": ".*",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["name"], "Weekly Load")
        self.assertEqual(serializer.validated_data["source_type"], SourceType.GCS)


class ScheduledIngestionSerializerFailureTest(TestCase):
    """ScheduledIngestionSerializer failure and validation error scenarios."""

    def test_invalid_file_pattern_regex(self):
        """Invalid regex in file_pattern raises ValidationError."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "Test",
            "source_type": SourceType.S3,
            "source_config": {"bucket": "b"},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": "[invalid",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("file_pattern", serializer.errors)

    def test_custom_cron_missing_cron_expression(self):
        """CUSTOM_CRON without cron in schedule_config raises ValidationError."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "Cron Job",
            "source_type": SourceType.S3,
            "source_config": {"bucket": "b"},
            "schedule_type": ScheduleType.CUSTOM_CRON,
            "schedule_config": {},
            "file_pattern": ".*",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertTrue(
            "schedule_config" in serializer.errors or "cron" in str(serializer.errors).lower()
        )

    def test_custom_cron_invalid_cron_expression(self):
        """Invalid cron expression raises ValidationError."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "Cron Job",
            "source_type": SourceType.S3,
            "source_config": {"bucket": "b"},
            "schedule_type": ScheduleType.CUSTOM_CRON,
            "schedule_config": {"cron": "not a cron"},
            "file_pattern": ".*",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("schedule_config", serializer.errors)

    def test_s3_missing_bucket(self):
        """S3 source_type without bucket raises ValidationError."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "S3 Job",
            "source_type": SourceType.S3,
            "source_config": {},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("source_config", serializer.errors)

    def test_gcs_missing_bucket(self):
        """GCS source_type without bucket raises ValidationError."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "GCS Job",
            "source_type": SourceType.GCS,
            "source_config": {},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("source_config", serializer.errors)

    def test_azure_blob_missing_account_or_container(self):
        """AZURE_BLOB without account_name or container raises ValidationError."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "Azure Job",
            "source_type": SourceType.AZURE_BLOB,
            "source_config": {},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("source_config", serializer.errors)

    def test_http_missing_base_url(self):
        """HTTP source_type without base_url raises ValidationError."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "HTTP Job",
            "source_type": SourceType.HTTP,
            "source_config": {},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("source_config", serializer.errors)

    def test_ftp_missing_host(self):
        """FTP source_type without host raises ValidationError."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "FTP Job",
            "source_type": SourceType.FTP,
            "source_config": {},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("source_config", serializer.errors)

    def test_database_missing_host_or_database(self):
        """DATABASE without host or database in source_config raises ValidationError."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "DB Job",
            "source_type": SourceType.DATABASE,
            "source_config": {},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("source_config", serializer.errors)

    def test_asset_id_nonexistent_raises_validation_error(self):
        """Providing non-existent asset_id raises ValidationError."""
        _tenant, _user = _tenant_user()
        fake_uuid = uuid.uuid4()
        data = {
            "name": "With Asset",
            "source_type": SourceType.S3,
            "source_config": {"bucket": "b"},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
            "asset_id": fake_uuid,
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("asset_id", serializer.errors)


class ScheduledIngestionSerializerEdgeCasesTest(TestCase):
    """ScheduledIngestionSerializer edge cases."""

    def test_allow_blank_name(self):
        """Serializer allows blank name; business rules may enforce non-blank."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "",
            "source_type": SourceType.S3,
            "source_config": {"bucket": "b"},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["name"], "")

    def test_asset_id_null_allowed(self):
        """asset_id can be omitted (optional)."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "No Asset",
            "source_type": SourceType.S3,
            "source_config": {"bucket": "b"},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("asset", serializer.validated_data)

    def test_asset_id_valid_resolves_to_asset(self):
        """Valid asset_id is resolved to asset instance."""
        tenant, user = _tenant_user()
        asset = Asset.objects.create(
            tenant=tenant,
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=user,
        )
        data = {
            "name": "With Asset",
            "source_type": SourceType.S3,
            "source_config": {"bucket": "b"},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
            "asset_id": asset.id,
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["asset"], asset)


class ScheduledIngestionRunSerializerTest(TestCase):
    """ScheduledIngestionRunSerializer success and read-only behavior."""

    def test_serialize_run(self):
        """Run serialization includes scheduled_ingestion_name and all fields."""
        tenant, user = _tenant_user()
        si = ScheduledIngestion.objects.create(
            tenant=tenant,
            name="Run Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "b"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*",
            created_by=user,
        )
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=si,
            status=ScheduledIngestionRunStatus.COMPLETED,
            files_found=5,
            files_processed=5,
            files_failed=0,
            datasets_created=5,
        )
        serializer = ScheduledIngestionRunSerializer(run)
        data = serializer.data
        self.assertEqual(data["status"], ScheduledIngestionRunStatus.COMPLETED)
        self.assertEqual(data["scheduled_ingestion_name"], "Run Test Ingestion")
        self.assertEqual(data["files_processed"], 5)
        self.assertIn("id", data)
        self.assertIn("scheduled_ingestion", data)


class ScheduledIngestionCreateSerializerSuccessTest(TestCase):
    """CreateSerializer success with test_connection=False (no connector)."""

    def test_create_serializer_valid_with_test_connection_false(self):
        """Valid data with test_connection=False passes validation."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "Create Test",
            "source_type": SourceType.S3,
            "source_config": {"bucket": "create-bucket"},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
            "test_connection": False,
        }
        serializer = ScheduledIngestionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("test_connection", serializer.validated_data)

    def test_create_removes_test_connection_from_validated_data(self):
        """Validated data does not contain test_connection (popped in validate); create() never receives it."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "Create Test",
            "source_type": SourceType.S3,
            "source_config": {"bucket": "b"},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
            "test_connection": False,
        }
        serializer = ScheduledIngestionCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.assertNotIn("test_connection", serializer.validated_data)


class ScheduledIngestionCreateSerializerFailureTest(TestCase):
    """ScheduledIngestionCreateSerializer validation failures."""

    def test_invalid_source_config_fails_validation(self):
        """Invalid source_config (e.g. S3 no bucket) fails even with test_connection=True."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "Bad Config",
            "source_type": SourceType.S3,
            "source_config": {},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*",
            "test_connection": True,
        }
        serializer = ScheduledIngestionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("source_config", serializer.errors)


class ScheduledIngestionTriggerSerializerTest(TestCase):
    """ScheduledIngestionTriggerSerializer success and edge cases."""

    def test_trigger_serializer_empty_parameters(self):
        """Empty or default parameters validate."""
        data = {}
        serializer = ScheduledIngestionTriggerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data.get("parameters"), {})

    def test_trigger_serializer_with_parameters(self):
        """Optional parameters dict is accepted and validated."""
        data = {"parameters": {"key": "value"}}
        serializer = ScheduledIngestionTriggerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["parameters"], {"key": "value"})


class ScheduledIngestionSerializerErrorHandlingTest(TestCase):
    """Error handling and invalid input scenarios."""

    def test_missing_required_fields(self):
        """Missing required fields produce validation errors."""
        data: dict = {}
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        # Model has default for schedule_type, so it may not appear in errors.
        # source_config has default=dict on the model so may not appear in errors.
        errors = serializer.errors
        self.assertIn("name", errors)
        self.assertIn("source_type", errors)
        self.assertIn("schedule_config", errors)
        self.assertIn("file_pattern", errors)
        # At least these four are required; source_config may be omitted when model has default
        self.assertGreaterEqual(len(errors), 4)

    def test_valid_cron_expression_passes(self):
        """Valid cron expression passes schedule_config validation."""
        _tenant, _user = _tenant_user()
        data = {
            "name": "Cron Job",
            "source_type": SourceType.S3,
            "source_config": {"bucket": "b"},
            "schedule_type": ScheduleType.CUSTOM_CRON,
            "schedule_config": {"cron": "0 0 * * *"},
            "file_pattern": ".*",
        }
        serializer = ScheduledIngestionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
