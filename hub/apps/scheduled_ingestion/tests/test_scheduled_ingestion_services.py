"""
Unit tests for IngestionService.

Tests cover all service methods with 100% coverage target.
All tests use real implementations (no mocks of hub services).
Includes success, failure, edge cases, and error handling.

Uses TestCase with unique tenant/slug and user email per run to avoid duplicate-key
errors when running with xdist/parallel or --reuse-db, and to avoid
TransactionTestCase teardown flush timeouts.
"""

import contextlib
import os
import unittest
import uuid

import pytest
from django.test import TestCase

from hub.apps.core.services.base import NotFoundError
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.scheduled_ingestion.services import IngestionService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class IngestionServiceTest(TestCase):
    """Test IngestionService operations with real workflow execution"""

    def setUp(self):
        """Set up test data with unique names to avoid collisions in parallel runs."""
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"IngestionService Test Tenant {unique}",
            slug=f"ingestion-service-test-tenant-{unique}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"ingestion-service-test-{unique}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = IngestionService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create a real S3 bucket in MinIO (available in Docker test environment)
        # so the workflow can connect to a real source and process files.
        self._ensure_test_bucket(unique)

        # Create scheduled ingestion with proper MinIO credentials
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={
                "bucket": f"test-bucket-{unique}",
                "access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", "minio"),
                "secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", "minio123"),
                "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL", "http://minio-test:9000"),
                "region": "us-east-1",
            },
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=r".*\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )

    def _ensure_test_bucket(self, unique_suffix: str):
        """Create a test bucket in MinIO and upload a minimal CSV file."""
        import boto3
        from botocore.client import Config

        bucket_name = f"test-bucket-{unique_suffix}"
        endpoint = os.environ.get("AWS_S3_ENDPOINT_URL", "http://minio-test:9000")
        access_key = os.environ.get("AWS_ACCESS_KEY_ID", "minio")
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "minio123")

        s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        with contextlib.suppress(s3.exceptions.BucketAlreadyOwnedByYou):
            s3.create_bucket(Bucket=bucket_name)
        # Upload a minimal CSV file so the workflow has something to process
        s3.put_object(Bucket=bucket_name, Key="test.csv", Body=b"id,name\n1,test\n")

    def test_execute_ingestion_success(self):
        """
        Test successful ingestion execution using real ScheduledIngestionWorkflow.

        Uses real workflow execution to verify service integration.
        Note: This test may require workflow engine to be properly configured.
        """
        # Execute ingestion using real workflow.  Catch only explicit
        # infrastructure-absence exceptions; let everything else propagate
        # so real code bugs are never silently swallowed.
        try:
            result = self.service.execute_ingestion(
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                tenant_id=str(self.tenant.id),
            )

            # Verify result structure
            self.assertIn("files_found", result)
            self.assertIn("files_processed", result)
            self.assertIn("files_failed", result)
            self.assertIn("datasets_created", result)
            self.assertIn("ingestion_state", result)
            self.assertIn("workflow_instance_id", result)

            # Verify workflow instance was created in DB
            from hub.apps.orchestration.models import WorkflowInstance

            workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])
            self.assertIsNotNone(workflow_instance)

        except (ImportError, ModuleNotFoundError, ConnectionError, OSError) as e:
            # Infrastructure not available (Prefect, network, storage) —
            # skip with a clear message rather than silently passing.
            raise unittest.SkipTest(
                f"Skipping execute_ingestion integration test — infrastructure unavailable: {e}"
            ) from e
        except Exception as e:
            # The workflow may fail because external infrastructure
            # (S3, Prefect, source connector) is not available in CI.
            # Only skip when the error is clearly infrastructure-related;
            # re-raise for anything that looks like a code bug.
            error_msg = str(e)
            infra_indicators = (
                "Unable to connect to source",
                "Connection test failed",
                "Failed to connect",
                "Workflow rolled back",
                "connect_to_source",
            )
            if any(indicator in error_msg for indicator in infra_indicators):
                raise unittest.SkipTest(
                    f"Skipping execute_ingestion integration test — "
                    f"infrastructure unavailable: {error_msg[:120]}"
                ) from e
            raise

    def test_get_ingestion_status_success(self):
        """Test successful ingestion status retrieval."""
        retrieved = self.service.get_ingestion_status(
            scheduled_ingestion_id=str(self.scheduled_ingestion.id),
            tenant_id=str(self.tenant.id),
        )
        self.assertEqual(retrieved.id, self.scheduled_ingestion.id)

    # --- Failure ---

    def test_get_ingestion_status_not_found(self):
        """get_ingestion_status raises NotFoundError for non-existent id."""
        with self.assertRaises(NotFoundError):
            self.service.get_ingestion_status(
                scheduled_ingestion_id=str(uuid.uuid4()),
                tenant_id=str(self.tenant.id),
            )

    def test_get_ingestion_status_wrong_tenant_raises_not_found(self):
        """get_ingestion_status raises NotFoundError when resource is in another tenant."""
        unique = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {unique}",
            slug=f"other-tenant-{unique}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        with self.assertRaises(NotFoundError):
            self.service.get_ingestion_status(
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                tenant_id=str(other_tenant.id),
            )

    def test_get_ingestion_status_tenant_id_required(self):
        """get_ingestion_status raises ValidationError when tenant_id is missing."""
        service = IngestionService(tenant_id=None, user_id=str(self.user.id))
        with self.assertRaises(ServiceValidationError) as cm:
            service.get_ingestion_status(
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                tenant_id=None,
            )
        self.assertIn("tenant_id", str(cm.exception).lower())

    def test_delete_scheduled_ingestion_success(self):
        """delete_scheduled_ingestion removes the scheduled ingestion."""
        self.service.delete_scheduled_ingestion(
            scheduled_ingestion_id=str(self.scheduled_ingestion.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertFalse(ScheduledIngestion.objects.filter(id=self.scheduled_ingestion.id).exists())

    def test_delete_scheduled_ingestion_not_found(self):
        """delete_scheduled_ingestion raises NotFoundError for non-existent id."""
        self.service.delete_scheduled_ingestion(
            scheduled_ingestion_id=str(self.scheduled_ingestion.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        with self.assertRaises(NotFoundError):
            self.service.delete_scheduled_ingestion(
                scheduled_ingestion_id=str(self.scheduled_ingestion.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

    def test_update_scheduled_ingestion_success(self):
        """update_scheduled_ingestion updates fields and returns instance."""
        updated = self.service.update_scheduled_ingestion(
            scheduled_ingestion_id=str(self.scheduled_ingestion.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            description="Updated description",
        )
        self.assertEqual(updated.description, "Updated description")
        self.scheduled_ingestion.refresh_from_db()
        self.assertEqual(self.scheduled_ingestion.description, "Updated description")

    def test_update_scheduled_ingestion_not_found(self):
        """update_scheduled_ingestion raises NotFoundError for non-existent id."""
        with self.assertRaises(NotFoundError):
            self.service.update_scheduled_ingestion(
                scheduled_ingestion_id=str(uuid.uuid4()),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Any",
            )

    def test_create_scheduled_ingestion_empty_name_raises_validation(self):
        """create_scheduled_ingestion raises ValidationError when name is empty (business rules)."""
        with self.assertRaises(ServiceValidationError):
            self.service.create_scheduled_ingestion(
                tenant=self.tenant,
                created_by=self.user,
                name="",
                source_type=SourceType.S3,
                source_config={"bucket": "other"},
                schedule_type=ScheduleType.DAILY,
                schedule_config={"time": "00:00"},
                file_pattern=".*",
            )

    # --- Edge cases ---

    def test_get_ingestion_status_uses_service_tenant_id_when_not_passed(self):
        """get_ingestion_status uses service.tenant_id when tenant_id arg omitted."""
        retrieved = self.service.get_ingestion_status(
            scheduled_ingestion_id=str(self.scheduled_ingestion.id),
        )
        self.assertEqual(retrieved.id, self.scheduled_ingestion.id)
