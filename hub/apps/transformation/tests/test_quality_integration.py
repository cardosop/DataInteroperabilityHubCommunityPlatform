"""
Tests for Transformation Quality Integration

Tests for quality checks integration in transformation pipeline execution.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from decimal import Decimal

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
from hub.apps.contracts.models import Contract


class TransformationQualityIntegrationTestCase(TestCase):
    """Test cases for TransformationQualityIntegration."""

    def setUp(self):
        """Set up test fixtures."""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

        # Create pipeline
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
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
            key="input-asset",
            name="Input Asset",
            status=AssetStatus.ACTIVE
        )

        # Create result asset
        self.result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
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

    def test_run_input_quality_check_success(self):
        """Test successful input quality check with real services."""
        # Create dataset and file for input asset
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="input.csv",
            content_type="text/csv",
            size=1000,
            storage_path="test/input.csv",
            status=FileStatus.ACTIVE
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.input_asset,
            file=file_obj,
            format="CSV",
            version=1
        )

        # Upload test file to storage
        from hub.apps.files.storage import S3StorageClient
        storage_client = S3StorageClient()
        try:
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(file_obj.id),
                file_content=b"id,name,value\n1,Test,100\n2,Sample,200"
            )
        except Exception as e:
            # Skip test if storage is not available
            self.skipTest(f"Storage service not available: {e}")

        # Check if DQ service is available
        from hub.apps.dq.service_client import DQServiceClient
        dq_client = DQServiceClient()
        is_healthy, _ = dq_client.health_check()
        if not is_healthy:
            self.skipTest("DQ service not available")

        # Run input quality check with real services
        result = self.quality_integration.run_input_quality_check()

        # Assertions - validate structure (actual values depend on DQ service)
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

    def test_run_input_quality_check_no_dataset(self):
        """Test input quality check when no dataset exists."""
        # No dataset created for input asset

        # Run input quality check
        result = self.quality_integration.run_input_quality_check()

        # Assertions
        self.assertIsNotNone(result)
        self.assertIsNone(result["quality_score"])
        self.assertEqual(result["overall_status"], "UNKNOWN")
        self.assertEqual(len(result["checks"]), 0)
        self.assertIn("error", result["metadata"])

    def test_run_input_quality_check_dq_service_unavailable(self):
        """Test input quality check when DQ service is unavailable."""
        # Create dataset and file
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="input.csv",
            content_type="text/csv",
            size=1000,
            storage_path="test/input.csv",
            status=FileStatus.ACTIVE
        )

        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.input_asset,
            file=file_obj,
            format="CSV",
            version=1
        )

        # Temporarily replace DQ client with one that reports unavailable
        original_dq_client = self.quality_integration.dq_client
        from unittest.mock import Mock
        mock_dq_instance = Mock()
        mock_dq_instance.health_check.return_value = (False, "dq-service")
        self.quality_integration.dq_client = mock_dq_instance

        try:
            # Run input quality check
            result = self.quality_integration.run_input_quality_check()

            # Assertions
            self.assertIsNotNone(result)
            self.assertIsNone(result["quality_score"])
            self.assertEqual(result["overall_status"], "UNKNOWN")
            self.assertIn("error", result["metadata"])
            mock_dq_instance.health_check.assert_called_once()
            mock_dq_instance.run_dq.assert_not_called()
        finally:
            # Restore original client
            self.quality_integration.dq_client = original_dq_client

    def test_run_output_quality_check_success(self):
        """Test successful output quality check with real services."""
        # Create dataset and file for result asset
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="output.csv",
            content_type="text/csv",
            size=1000,
            storage_path="test/output.csv",
            status=FileStatus.ACTIVE
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.result_asset,
            file=file_obj,
            format="CSV",
            version=1
        )

        # Upload test file to storage
        from hub.apps.files.storage import S3StorageClient
        storage_client = S3StorageClient()
        try:
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(file_obj.id),
                file_content=b"id,name,value\n1,Test,100\n2,Sample,200"
            )
        except Exception as e:
            # Skip test if storage is not available
            self.skipTest(f"Storage service not available: {e}")

        # Check if DQ service is available
        from hub.apps.dq.service_client import DQServiceClient
        dq_client = DQServiceClient()
        is_healthy, _ = dq_client.health_check()
        if not is_healthy:
            self.skipTest("DQ service not available")

        # Run output quality check with real services
        result = self.quality_integration.run_output_quality_check(self.result_asset)

        # Assertions - validate structure (actual values depend on DQ service)
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

    def test_compare_quality_metrics_improvement(self):
        """Test quality metrics comparison showing improvement."""
        input_metrics = {
            "quality_score": 0.80,
            "overall_status": "PASS",
            "checks": [
                {"check_id": "check1", "name": "Null Check", "status": "PASS", "value": 0.85}
            ]
        }

        output_metrics = {
            "quality_score": 0.90,
            "overall_status": "PASS",
            "checks": [
                {"check_id": "check1", "name": "Null Check", "status": "PASS", "value": 0.95}
            ]
        }

        comparison = self.quality_integration.compare_quality_metrics(
            input_metrics,
            output_metrics
        )

        # Assertions
        self.assertIsNotNone(comparison)
        self.assertAlmostEqual(comparison["quality_score_delta"], 0.10, places=10)
        self.assertGreater(comparison["quality_score_delta_percent"], 0)
        self.assertTrue(comparison["improvement_detected"])
        self.assertFalse(comparison["degradation_detected"])
        self.assertEqual(comparison["status_change"], "UNCHANGED")

    def test_compare_quality_metrics_degradation(self):
        """Test quality metrics comparison showing degradation."""
        input_metrics = {
            "quality_score": 0.90,
            "overall_status": "PASS",
            "checks": [
                {"check_id": "check1", "name": "Null Check", "status": "PASS", "value": 0.95}
            ]
        }

        output_metrics = {
            "quality_score": 0.75,
            "overall_status": "WARN",
            "checks": [
                {"check_id": "check1", "name": "Null Check", "status": "WARN", "value": 0.80}
            ]
        }

        comparison = self.quality_integration.compare_quality_metrics(
            input_metrics,
            output_metrics
        )

        # Assertions
        self.assertIsNotNone(comparison)
        self.assertAlmostEqual(comparison["quality_score_delta"], -0.15, places=10)
        self.assertLess(comparison["quality_score_delta_percent"], 0)
        self.assertTrue(comparison["degradation_detected"])
        self.assertFalse(comparison["improvement_detected"])
        self.assertEqual(comparison["status_change"], "DEGRADED")

    def test_compare_quality_metrics_missing_scores(self):
        """Test quality metrics comparison with missing scores."""
        input_metrics = {
            "quality_score": None,
            "overall_status": "UNKNOWN"
        }

        output_metrics = {
            "quality_score": 0.90,
            "overall_status": "PASS"
        }

        comparison = self.quality_integration.compare_quality_metrics(
            input_metrics,
            output_metrics
        )

        # Assertions
        self.assertIsNotNone(comparison)
        self.assertIsNone(comparison["quality_score_delta"])
        self.assertIsNone(comparison["quality_score_delta_percent"])
        self.assertFalse(comparison["degradation_detected"])
        self.assertFalse(comparison["improvement_detected"])
        self.assertIn("error", comparison["metadata"])

    def test_store_quality_metrics_in_execution_log(self):
        """Test storing quality metrics in execution_log."""
        input_metrics = {
            "quality_score": 0.85,
            "overall_status": "PASS",
            "checks": [{"check_id": "check1", "name": "Test Check"}],
            "engine_type": "great_expectations",
            "engine_version": "0.18.0"
        }

        output_metrics = {
            "quality_score": 0.90,
            "overall_status": "PASS",
            "checks": [{"check_id": "check1", "name": "Test Check"}],
            "engine_type": "great_expectations",
            "engine_version": "0.18.0"
        }

        comparison = {
            "quality_score_delta": 0.05,
            "quality_score_delta_percent": 5.88,
            "status_change": "UNCHANGED",
            "degradation_detected": False,
            "improvement_detected": True,
            "input_quality_score": 0.85,
            "output_quality_score": 0.90
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

        # Check input log entry
        input_log = self.execution.execution_log[0]
        self.assertEqual(input_log["type"], "quality_check")
        self.assertEqual(input_log["stage"], "input")
        self.assertEqual(input_log["quality_score"], 0.85)

        # Check output log entry
        output_log = self.execution.execution_log[1]
        self.assertEqual(output_log["type"], "quality_check")
        self.assertEqual(output_log["stage"], "output")
        self.assertEqual(output_log["quality_score"], 0.90)

        # Check comparison log entry
        comparison_log = self.execution.execution_log[2]
        self.assertEqual(comparison_log["type"], "quality_comparison")
        self.assertAlmostEqual(comparison_log["quality_score_delta"], 0.05, places=10)
        self.assertTrue(comparison_log["improvement_detected"])

    def test_publish_quality_degradation_alerts(self):
        """Test publishing quality degradation alerts."""
        # Set result asset on execution
        self.execution.result_asset = self.result_asset
        self.execution.save()

        comparison = {
            "quality_score_delta": -0.10,
            "quality_score_delta_percent": -11.11,
            "status_change": "DEGRADED",
            "degradation_detected": True,
            "improvement_detected": False,
            "input_quality_score": 0.90,
            "output_quality_score": 0.80,
            "input_status": "PASS",
            "output_status": "WARN"
        }

        # Publish alerts with real services
        alerts = self.quality_integration.publish_quality_degradation_alerts(
            comparison,
            threshold=0.05
        )

        # Assertions
        self.assertIsInstance(alerts, list)
        self.assertGreater(len(alerts), 0)

        # Check custom alert
        custom_alert = alerts[0]
        self.assertEqual(custom_alert["type"], "transformation_quality_degradation")
        self.assertEqual(custom_alert["execution_id"], str(self.execution.id))
        self.assertAlmostEqual(custom_alert["quality_score_delta"], -0.10, places=10)
        self.assertIn("message", custom_alert)

    def test_publish_quality_degradation_alerts_no_degradation(self):
        """Test that alerts are not published when no degradation detected."""
        comparison = {
            "quality_score_delta": 0.10,
            "quality_score_delta_percent": 11.11,
            "degradation_detected": False,
            "improvement_detected": True
        }

        # Publish alerts
        alerts = self.quality_integration.publish_quality_degradation_alerts(
            comparison,
            threshold=0.05
        )

        # Assertions
        self.assertEqual(len(alerts), 0)

    def test_publish_quality_degradation_alerts_below_threshold(self):
        """Test that alerts are not published when degradation is below threshold."""
        comparison = {
            "quality_score_delta": -0.02,
            "quality_score_delta_percent": -2.0,
            "degradation_detected": True,
            "improvement_detected": False
        }

        # Publish alerts (threshold is 0.05 = 5%)
        alerts = self.quality_integration.publish_quality_degradation_alerts(
            comparison,
            threshold=0.05
        )

        # Assertions
        self.assertEqual(len(alerts), 0)

    def test_determine_file_format_from_dataset(self):
        """Test file format determination from dataset."""
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.json",
            content_type="application/json",
            size=1000,
            storage_path="test/test.json",
            status=FileStatus.ACTIVE
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.input_asset,
            file=file_obj,
            format="JSON",
            version=1
        )

        format_result = self.quality_integration._determine_file_format(file_obj, dataset)
        self.assertEqual(format_result, "json")

    def test_determine_file_format_from_content_type(self):
        """Test file format determination from content type."""
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.unknown",
            content_type="text/csv",
            size=1000,
            storage_path="test/test.unknown",
            status=FileStatus.ACTIVE
        )

        format_result = self.quality_integration._determine_file_format(file_obj)
        self.assertEqual(format_result, "csv")

    def test_determine_file_format_from_filename(self):
        """Test file format determination from filename."""
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.parquet",
            content_type="application/octet-stream",
            size=1000,
            storage_path="test/test.parquet",
            status=FileStatus.ACTIVE
        )

        format_result = self.quality_integration._determine_file_format(file_obj)
        self.assertEqual(format_result, "parquet")

    def test_compare_status_improved(self):
        """Test status comparison showing improvement."""
        result = self.quality_integration._compare_status("FAIL", "PASS")
        self.assertEqual(result, "IMPROVED")

    def test_compare_status_degraded(self):
        """Test status comparison showing degradation."""
        result = self.quality_integration._compare_status("PASS", "FAIL")
        self.assertEqual(result, "DEGRADED")

    def test_compare_status_unchanged(self):
        """Test status comparison showing no change."""
        result = self.quality_integration._compare_status("PASS", "PASS")
        self.assertEqual(result, "UNCHANGED")

    def test_compare_checks(self):
        """Test individual checks comparison."""
        input_checks = [
            {"check_id": "check1", "name": "Null Check", "status": "PASS", "value": 0.95},
            {"check_id": "check2", "name": "Uniqueness Check", "status": "PASS", "value": 0.90}
        ]

        output_checks = [
            {"check_id": "check1", "name": "Null Check", "status": "WARN", "value": 0.85},
            {"check_id": "check2", "name": "Uniqueness Check", "status": "PASS", "value": 0.90},
            {"check_id": "check3", "name": "New Check", "status": "PASS", "value": 0.80}
        ]

        comparisons = self.quality_integration._compare_checks(input_checks, output_checks)

        # Assertions
        self.assertEqual(len(comparisons), 3)  # check1, check2, check3

        # Check check1 comparison (degraded)
        check1_comp = next(c for c in comparisons if c["check_id"] == "check1")
        self.assertEqual(check1_comp["status_change"], "DEGRADED")
        self.assertAlmostEqual(check1_comp["value_delta"], -0.10, places=10)

        # Check check2 comparison (unchanged)
        check2_comp = next(c for c in comparisons if c["check_id"] == "check2")
        self.assertEqual(check2_comp["status_change"], "UNCHANGED")
        self.assertAlmostEqual(check2_comp["value_delta"], 0.0, places=10)

        # Check check3 comparison (new check)
        check3_comp = next(c for c in comparisons if c["check_id"] == "check3")
        self.assertIsNone(check3_comp["input_status"])
        self.assertEqual(check3_comp["output_status"], "PASS")

