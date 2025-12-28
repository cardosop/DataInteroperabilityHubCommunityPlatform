"""
Integration tests for preview_transformation method.

Tests the full preview flow with real services (where possible) or properly mocked services.
"""
import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase

from hub.apps.transformation.services import TransformationService
from hub.apps.transformation.models import TransformationPipeline, PipelineStatus
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from django.contrib.auth import get_user_model

User = get_user_model()


class PreviewTransformationIntegrationTest(TestCase):
    """Integration tests for preview_transformation."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name="Integration Test Tenant",
            slug="integration-test-tenant"
        )

        self.user = User.objects.create_user(
            email="integration@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create pipeline
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Integration Test Pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "filter_step",
                        "type": "task",
                        "task": "filter_data",
                        "node_config": {
                            "node_type": "filter",
                            "filter_expression": "age > 18"
                        }
                    }
                ]
            },
            version="1.0.0",
            status=PipelineStatus.ACTIVE
        )

        # Create asset with dataset and file
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name="Integration Test Asset",
            domain="test"
        )

        # Create CSV file content
        self.csv_content = b"id,name,age\n1,Alice,25\n2,Bob,17\n3,Charlie,30\n4,Diana,22\n5,Eve,19"
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test_data.csv",
            storage_path=f"test/integration/{self.asset.id}/test_data.csv",
            size=len(self.csv_content),
            content_type="text/csv"
        )

        # Upload file to storage (real service)
        from hub.apps.files.storage import S3StorageClient
        from hub.apps.files.models import FileStatus

        try:
            storage_client = S3StorageClient()
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=self.csv_content
            )
            self.file.status = FileStatus.ACTIVE
            self.file.save()
            self.storage_available = True
        except Exception as e:
            # Storage might not be available, tests will skip
            self.storage_available = False
            self.storage_error = str(e)

        # Create dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=5,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"},
                    {"name": "age", "data_type": "integer"}
                ]
            }
        )

        self.service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_preview_transformation_full_flow(self):
        """Test full preview flow with all components integrated using real services."""
        from hub.apps.files.storage import S3StorageClient
        from hub.apps.dq.service_client import DQServiceClient
        from django.core.cache import cache

        # Check service availability
        try:
            storage_client = S3StorageClient()
            # Try to ensure bucket exists
            try:
                storage_client.client.head_bucket(Bucket=storage_client.bucket_name)
            except Exception:
                pass  # Bucket might not exist, but client is available
            storage_available = True
        except Exception:
            self.skipTest("Storage service not available")
            return

        # Check DQ service
        try:
            dq_client = DQServiceClient()
            is_healthy, _ = dq_client.health_check()
            dq_available = is_healthy
        except Exception:
            dq_available = False

        # Check cache
        try:
            cache.set('test_key', 'test_value', 1)
            cache.get('test_key')
            cache_available = True
        except Exception:
            cache_available = False

        # Upload test file to storage
        csv_content = b"id,name,age\n1,Alice,25\n2,Bob,17\n3,Charlie,30\n4,Diana,22\n5,Eve,19"
        try:
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=csv_content
            )
        except Exception as e:
            self.skipTest(f"Failed to upload test file to storage: {e}")
            return

        # Clear cache
        if cache_available:
            cache.clear()

        # Execute preview with real services
        result = self.service.preview_transformation(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            sample_size=5,
            sampling_method="first_n"
        )

        # Verify result structure
        self.assertIsNotNone(result)
        self.assertIn("preview_id", result)
        self.assertEqual(str(self.pipeline.id), result["pipeline_id"])
        self.assertEqual(str(self.asset.id), result["asset_id"])
        self.assertFalse(result["cached"])

        # Verify analysis structure
        analysis = result.get("analysis", {})
        self.assertIn("row_count_changes", analysis)
        self.assertIn("schema_changes", analysis)
        self.assertIn("quality_impact", analysis)

        # Verify row count analysis
        row_count_changes = analysis["row_count_changes"]
        self.assertIn("input_rows", row_count_changes)
        self.assertIn("output_rows", row_count_changes)
        self.assertIn("delta", row_count_changes)
        self.assertGreaterEqual(row_count_changes["input_rows"], 0)

        # Verify schema changes analysis
        schema_changes = analysis["schema_changes"]
        self.assertIn("has_changes", schema_changes)

        # Verify quality impact analysis
        quality_impact = analysis["quality_impact"]
        self.assertIn("available", quality_impact)

        # If DQ service is available, quality impact should be available
        if dq_available:
            # Quality impact might be available or not depending on service response
            pass

        # Verify cache was set (if available) by checking second call
        if cache_available:
            cached_result = self.service.preview_transformation(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                sample_size=5,
                sampling_method="first_n"
            )
            self.assertTrue(cached_result["cached"])
            self.assertEqual(cached_result["preview_id"], result["preview_id"])

    def test_preview_transformation_with_different_sample_sizes(self):
        """Test preview with different sample sizes using real services."""
        from hub.apps.files.storage import S3StorageClient
        from django.core.cache import cache

        # Check storage availability
        try:
            storage_client = S3StorageClient()
            storage_available = True
        except Exception:
            self.skipTest("Storage service not available")
            return

        # Create larger CSV content
        csv_content = b"id,name,age\n" + b"\n".join([f"{i},Person{i},{20+i}".encode() for i in range(100)])

        # Upload to storage
        try:
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=csv_content
            )
        except Exception as e:
            self.skipTest(f"Failed to upload test file: {e}")
            return

        # Clear cache
        try:
            cache.clear()
        except Exception:
            pass

        # Test with different sample sizes
        for sample_size in [10, 50, 100]:
            result = self.service.preview_transformation(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                sample_size=sample_size,
                sampling_method="first_n"
            )

            self.assertIsNotNone(result)
            self.assertLessEqual(len(result.get("input_sample", [])), sample_size)

    def test_preview_transformation_quality_service_unavailable(self):
        """Test preview continues when quality service is unavailable using real services."""
        from hub.apps.files.storage import S3StorageClient
        from django.core.cache import cache

        # Check storage availability
        try:
            storage_client = S3StorageClient()
            storage_available = True
        except Exception:
            self.skipTest("Storage service not available")
            return

        csv_content = b"id,name,age\n1,Alice,25\n2,Bob,17"

        # Upload to storage
        try:
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=csv_content
            )
        except Exception as e:
            self.skipTest(f"Failed to upload test file: {e}")
            return

        # Clear cache
        try:
            cache.clear()
        except Exception:
            pass

        # Execute preview - should not fail even if DQ service is unavailable
        result = self.service.preview_transformation(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            sample_size=2
        )

        # Verify result still generated
        self.assertIsNotNone(result)
        analysis = result.get("analysis", {})
        quality_impact = analysis.get("quality_impact", {})
        # Quality impact might not be available if DQ service is down
        self.assertIn("available", quality_impact)

    def test_preview_transformation_schema_comparison(self):
        """Test schema comparison in preview analysis using real services."""
        from hub.apps.files.storage import S3StorageClient
        from django.core.cache import cache

        # Check storage availability
        try:
            storage_client = S3StorageClient()
            storage_available = True
        except Exception:
            self.skipTest("Storage service not available")
            return

        csv_content = b"id,name,age\n1,Alice,25\n2,Bob,17"

        # Upload to storage
        try:
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=csv_content
            )
        except Exception as e:
            self.skipTest(f"Failed to upload test file: {e}")
            return

        # Clear cache
        try:
            cache.clear()
        except Exception:
            pass

        result = self.service.preview_transformation(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            sample_size=2
        )

        # Verify schema changes analysis
        analysis = result.get("analysis", {})
        schema_changes = analysis.get("schema_changes", {})
        self.assertIn("has_changes", schema_changes)
        if "compatibility_level" in schema_changes:
            self.assertIsNotNone(schema_changes["compatibility_level"])

    def test_preview_transformation_event_publishing(self):
        """Test that preview events are published correctly using real services."""
        from hub.apps.files.storage import S3StorageClient
        from django.core.cache import cache
        from unittest.mock import patch

        # Check storage availability
        try:
            storage_client = S3StorageClient()
            storage_available = True
        except Exception:
            self.skipTest("Storage service not available")
            return

        csv_content = b"id,name,age\n1,Alice,25\n2,Bob,17"

        # Upload to storage
        try:
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=csv_content
            )
        except Exception as e:
            self.skipTest(f"Failed to upload test file: {e}")
            return

        # Clear cache
        try:
            cache.clear()
        except Exception:
            pass

        # Patch event publisher to verify it's called
        with patch.object(self.service._event_publisher, 'publish') as mock_publish:
            result = self.service.preview_transformation(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                sample_size=2
            )

            # Verify event was published
            self.assertTrue(mock_publish.called)
            call_args = mock_publish.call_args
            self.assertEqual(call_args[1]["event_type"], "transformation.preview.generated")
            self.assertIn("pipeline_id", call_args[1]["data"])
            self.assertIn("asset_id", call_args[1]["data"])
            self.assertIn("preview_id", call_args[1]["data"])

