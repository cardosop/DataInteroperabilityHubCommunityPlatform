"""
Integration Tests for Transformation Quality Integration with Real Services

These tests use real DQ service and storage services (no mocks/stubs).
Tests will be skipped if services are not available.
"""
import pytest
import os
from django.test import TestCase
from django.utils import timezone

from hub.apps.transformation.models import (
    TransformationPipeline,
    PipelineExecution,
    ExecutionStatus,
    ExecutionMode
)
from hub.apps.transformation.quality_integration import TransformationQualityIntegration
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.dq.service_client import DQServiceClient
from hub.apps.files.storage import S3StorageClient


def check_dq_service_available():
    """Check if DQ service is available."""
    try:
        client = DQServiceClient()
        is_healthy, _ = client.health_check()
        return is_healthy
    except Exception:
        return False


def check_storage_available():
    """Check if storage service is available."""
    try:
        client = S3StorageClient()
        # The client initialization will try to ensure bucket exists
        # Try a lightweight operation to verify connectivity
        try:
            # Try to list buckets (lightweight operation)
            client.client.list_buckets()
            return True
        except Exception:
            # If list_buckets fails, try head_bucket on our bucket
            try:
                client.client.head_bucket(Bucket=client.bucket_name)
                return True
            except Exception:
                # Service might be available but we can't access it
                # Assume available if client was created (endpoint is configured)
                return client.endpoint_url is not None or True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.requires_services
class TransformationQualityIntegrationRealServicesTest(TestCase):
    """Integration tests using real services (no mocks/stubs)."""

    def setUp(self):
        """Set up test fixtures."""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant Real Services",
            slug="test-tenant-real"
        )

        # Create pipeline
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline Real Services",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [{"name": "test_step", "type": "task"}]
            },
            version="1.0.0",
            status="ACTIVE"
        )

        # Create input asset
        self.input_asset = Asset.objects.create(
            tenant=self.tenant,
            key="input-asset-real",
            name="Input Asset Real",
            status=AssetStatus.ACTIVE
        )

        # Create result asset
        self.result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset-real",
            name="Result Asset Real",
            status=AssetStatus.ACTIVE
        )

        # Create execution
        self.execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.input_asset,
            execution_mode=ExecutionMode.MANUAL,
            status=ExecutionStatus.RUNNING,
            started_at=timezone.now()
        )

        # Create quality integration instance
        self.quality_integration = TransformationQualityIntegration(self.execution)

        # Create test CSV content
        self.test_csv_content = b"id,name,value\n1,Test,100\n2,Sample,200\n3,Example,300"

    @pytest.mark.skipif(
        not check_dq_service_available() or not check_storage_available(),
        reason="DQ service or storage service not available"
    )
    def test_run_input_quality_check_with_real_services(self):
        """Test input quality check with real DQ service and storage."""
        # Create file and upload to storage
        storage_client = S3StorageClient()
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="input_real_test.csv",
            content_type="text/csv",
            size=len(self.test_csv_content),
            storage_path=f"test/quality_integration/input_{self.execution.id}.csv",
            status=FileStatus.ACTIVE
        )

        # Upload file content to storage
        try:
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(file_obj.id),
                file_content=self.test_csv_content
            )
        except Exception as e:
            pytest.skip(f"Failed to upload test file to storage: {e}")

        # Create dataset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.input_asset,
            file=file_obj,
            format="CSV",
            version=1
        )

        # Run input quality check with real services
        result = self.quality_integration.run_input_quality_check()

        # Assertions - service may return different results, so we check structure
        self.assertIsNotNone(result)
        self.assertIn("quality_score", result)
        self.assertIn("overall_status", result)
        self.assertIn("checks", result)

        # If service returned results, validate structure
        if result.get("quality_score") is not None:
            self.assertIsInstance(result["quality_score"], (int, float))
            self.assertGreaterEqual(result["quality_score"], 0.0)
            self.assertLessEqual(result["quality_score"], 1.0)
            self.assertIn(result["overall_status"], ["PASS", "WARN", "FAIL", "UNKNOWN"])

    @pytest.mark.skipif(
        not check_dq_service_available() or not check_storage_available(),
        reason="DQ service or storage service not available"
    )
    def test_run_output_quality_check_with_real_services(self):
        """Test output quality check with real DQ service and storage."""
        # Create file and upload to storage
        storage_client = S3StorageClient()
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="output_real_test.csv",
            content_type="text/csv",
            size=len(self.test_csv_content),
            storage_path=f"test/quality_integration/output_{self.execution.id}.csv",
            status=FileStatus.ACTIVE
        )

        # Upload file content to storage
        try:
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(file_obj.id),
                file_content=self.test_csv_content
            )
        except Exception as e:
            pytest.skip(f"Failed to upload test file to storage: {e}")

        # Create dataset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.result_asset,
            file=file_obj,
            format="CSV",
            version=1
        )

        # Run output quality check with real services
        result = self.quality_integration.run_output_quality_check(self.result_asset)

        # Assertions - service may return different results, so we check structure
        self.assertIsNotNone(result)
        self.assertIn("quality_score", result)
        self.assertIn("overall_status", result)
        self.assertIn("checks", result)

        # If service returned results, validate structure
        if result.get("quality_score") is not None:
            self.assertIsInstance(result["quality_score"], (int, float))
            self.assertGreaterEqual(result["quality_score"], 0.0)
            self.assertLessEqual(result["quality_score"], 1.0)
            self.assertIn(result["overall_status"], ["PASS", "WARN", "FAIL", "UNKNOWN"])

    @pytest.mark.skipif(
        not check_dq_service_available() or not check_storage_available(),
        reason="DQ service or storage service not available"
    )
    def test_full_quality_integration_workflow_real_services(self):
        """Test full quality integration workflow with real services."""
        storage_client = S3StorageClient()

        # Create input file
        input_file_obj = File.objects.create(
            tenant=self.tenant,
            name="input_workflow_test.csv",
            content_type="text/csv",
            size=len(self.test_csv_content),
            storage_path=f"test/quality_integration/workflow_input_{self.execution.id}.csv",
            status=FileStatus.ACTIVE
        )

        try:
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(input_file_obj.id),
                file_content=self.test_csv_content
            )
        except Exception as e:
            pytest.skip(f"Failed to upload input file to storage: {e}")

        input_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.input_asset,
            file=input_file_obj,
            format="CSV",
            version=1
        )

        # Create output file (simulate transformation result)
        output_file_obj = File.objects.create(
            tenant=self.tenant,
            name="output_workflow_test.csv",
            content_type="text/csv",
            size=len(self.test_csv_content),
            storage_path=f"test/quality_integration/workflow_output_{self.execution.id}.csv",
            status=FileStatus.ACTIVE
        )

        try:
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(output_file_obj.id),
                file_content=self.test_csv_content
            )
        except Exception as e:
            pytest.skip(f"Failed to upload output file to storage: {e}")

        output_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.result_asset,
            file=output_file_obj,
            format="CSV",
            version=1
        )

        # Run input quality check
        input_metrics = self.quality_integration.run_input_quality_check()
        self.assertIsNotNone(input_metrics)

        # Run output quality check
        output_metrics = self.quality_integration.run_output_quality_check(self.result_asset)
        self.assertIsNotNone(output_metrics)

        # Compare metrics
        comparison = self.quality_integration.compare_quality_metrics(
            input_metrics,
            output_metrics
        )
        self.assertIsNotNone(comparison)
        self.assertIn("quality_score_delta", comparison)
        self.assertIn("degradation_detected", comparison)
        self.assertIn("improvement_detected", comparison)

        # Store metrics in execution log
        self.quality_integration.store_quality_metrics_in_execution_log(
            input_metrics,
            output_metrics,
            comparison
        )

        # Verify metrics were stored
        self.execution.refresh_from_db()
        self.assertIsInstance(self.execution.execution_log, list)
        self.assertGreater(len(self.execution.execution_log), 0)

        # Check that we have input, output, and comparison entries
        log_types = [entry.get("type") for entry in self.execution.execution_log]
        self.assertIn("quality_check", log_types)
        self.assertIn("quality_comparison", log_types)

    def test_compare_quality_metrics_with_real_service_results(self):
        """Test quality metrics comparison using realistic service response structures."""
        # Use realistic service response structures
        input_metrics = {
            "quality_score": 0.85,
            "overall_status": "PASS",
            "checks": [
                {"check_id": "check1", "name": "Null Check", "status": "PASS", "value": 0.95}
            ],
            "engine_type": "great_expectations",
            "engine_version": "0.18.0"
        }

        output_metrics = {
            "quality_score": 0.90,
            "overall_status": "PASS",
            "checks": [
                {"check_id": "check1", "name": "Null Check", "status": "PASS", "value": 0.98}
            ],
            "engine_type": "great_expectations",
            "engine_version": "0.18.0"
        }

        comparison = self.quality_integration.compare_quality_metrics(
            input_metrics,
            output_metrics
        )

        # Assertions
        self.assertIsNotNone(comparison)
        self.assertAlmostEqual(comparison["quality_score_delta"], 0.05, places=10)
        self.assertGreater(comparison["quality_score_delta_percent"], 0)
        self.assertTrue(comparison["improvement_detected"])
        self.assertFalse(comparison["degradation_detected"])

    def test_store_quality_metrics_in_execution_log_real_structure(self):
        """Test storing quality metrics with realistic service response structures."""
        input_metrics = {
            "quality_score": 0.85,
            "overall_status": "PASS",
            "checks": [
                {"check_id": "check1", "name": "Null Check", "status": "PASS", "value": 0.95}
            ],
            "engine_type": "great_expectations",
            "engine_version": "0.18.0",
            "metadata": {}
        }

        output_metrics = {
            "quality_score": 0.90,
            "overall_status": "PASS",
            "checks": [
                {"check_id": "check1", "name": "Null Check", "status": "PASS", "value": 0.98}
            ],
            "engine_type": "great_expectations",
            "engine_version": "0.18.0",
            "metadata": {}
        }

        comparison = {
            "quality_score_delta": 0.05,
            "quality_score_delta_percent": 5.88,
            "status_change": "UNCHANGED",
            "degradation_detected": False,
            "improvement_detected": True,
            "input_quality_score": 0.85,
            "output_quality_score": 0.90,
            "checks_comparison": []
        }

        # Store metrics
        self.quality_integration.store_quality_metrics_in_execution_log(
            input_metrics,
            output_metrics,
            comparison
        )

        # Refresh execution from database
        self.execution.refresh_from_db()

        # Assertions
        self.assertIsInstance(self.execution.execution_log, list)
        self.assertEqual(len(self.execution.execution_log), 3)  # input, output, comparison

        # Verify log entries have correct structure
        for entry in self.execution.execution_log:
            self.assertIn("timestamp", entry)
            self.assertIn("type", entry)
            if entry["type"] == "quality_check":
                self.assertIn("stage", entry)
                self.assertIn("quality_score", entry)
            elif entry["type"] == "quality_comparison":
                self.assertIn("quality_score_delta", entry)
                self.assertIn("degradation_detected", entry)

