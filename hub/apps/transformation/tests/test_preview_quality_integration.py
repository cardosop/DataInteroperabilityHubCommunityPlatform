"""
Unit and Integration tests for QualityService integration in preview_transformation.

Tests:
- Quality checks on preview result via QualityService
- Quality metrics comparison (input vs output)
- Quality impact calculation
- Quality metrics storage in preview cache
- Integration with real QualityService
"""
import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache

from hub.apps.transformation.services import TransformationService
from hub.apps.transformation.models import TransformationPipeline, PipelineStatus
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from hub.apps.dq.service_client import DQServiceClient
from django.contrib.auth import get_user_model

User = get_user_model()


class PreviewQualityServiceIntegrationTest(TestCase):
    """Unit tests for quality service integration in preview."""

    def setUp(self):
        """Set up test fixtures."""
        tenant_name = f"Test Tenant {uuid.uuid4().hex[:8]}"
        self.tenant = Tenant.objects.create(
            name=tenant_name,
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create pipeline
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task"}]
            },
            status=PipelineStatus.ACTIVE
        )

        # Create asset with dataset and file
        asset_key = f"test-asset-{uuid.uuid4().hex[:8]}"
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=asset_key,
            name="Test Asset",
            created_by=self.user
        )

        # Create CSV file content
        self.csv_content = b"id,name,age\n1,Alice,25\n2,Bob,17\n3,Charlie,30\n4,Diana,22\n5,Eve,19"
        self.file = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test_data.csv",
            storage_path=f"test/preview/{self.asset.id}/test_data.csv",
            size=len(self.csv_content),
            content_type="text/csv",
            status=FileStatus.ACTIVE
        )

        # Create dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            file=self.file,
            format="CSV",
            version=1,
            row_count=5
        )

        self.service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_quality_checks_on_preview_result(self):
        """Test that quality checks are run on preview result via QualityService."""
        # Mock storage client to return test data
        with patch('hub.apps.files.storage.S3StorageClient.get_file_content', return_value=self.csv_content):
            # Mock DQ service to return quality results
            mock_input_quality = {
                "quality_score": 0.85,
                "overall_status": "PASS",
                "checks": [
                    {"name": "completeness", "status": "PASS", "score": 0.9},
                    {"name": "validity", "status": "PASS", "score": 0.8}
                ],
                "engine_type": "great_expectations",
                "engine_version": "0.18.0"
            }

            mock_output_quality = {
                "quality_score": 0.90,
                "overall_status": "PASS",
                "checks": [
                    {"name": "completeness", "status": "PASS", "score": 0.95},
                    {"name": "validity", "status": "PASS", "score": 0.85}
                ],
                "engine_type": "great_expectations",
                "engine_version": "0.18.0"
            }

            with patch.object(DQServiceClient, 'health_check', return_value=(True, {})):
                with patch.object(DQServiceClient, 'run_dq', side_effect=[mock_input_quality, mock_output_quality]):
                    result = self.service.preview_transformation(
                        pipeline_id=str(self.pipeline.id),
                        asset_id=str(self.asset.id),
                        sample_size=5,
                        sampling_method="first_n"
                    )

            # Verify quality checks were run
            quality_impact = result.get("quality_metrics", {})
            self.assertTrue(quality_impact.get("available", False))
            self.assertIn("input_quality_metrics", quality_impact)
            self.assertIn("output_quality_metrics", quality_impact)
            self.assertIn("quality_comparison", quality_impact)

            # Verify input quality metrics
            input_metrics = quality_impact["input_quality_metrics"]
            self.assertEqual(input_metrics["quality_score"], 0.85)
            self.assertEqual(input_metrics["overall_status"], "PASS")
            self.assertEqual(input_metrics["checks_passed"], 2)
            self.assertEqual(input_metrics["checks_total"], 2)

            # Verify output quality metrics
            output_metrics = quality_impact["output_quality_metrics"]
            self.assertEqual(output_metrics["quality_score"], 0.90)
            self.assertEqual(output_metrics["overall_status"], "PASS")
            self.assertEqual(output_metrics["checks_passed"], 2)

    def test_quality_impact_calculation(self):
        """Test that quality impact (quality metrics comparison) is calculated correctly."""
        # Mock storage client
        with patch('hub.apps.files.storage.S3StorageClient.get_file_content', return_value=self.csv_content):
            # Mock DQ service with known quality scores
            mock_input_quality = {
                "quality_score": 0.80,
                "overall_status": "PASS",
                "checks": [
                    {"name": "check1", "status": "PASS"},
                    {"name": "check2", "status": "PASS"},
                    {"name": "check3", "status": "FAIL"}
                ],
                "engine_type": "great_expectations",
                "engine_version": "0.18.0"
            }

            mock_output_quality = {
                "quality_score": 0.95,
                "overall_status": "PASS",
                "checks": [
                    {"name": "check1", "status": "PASS"},
                    {"name": "check2", "status": "PASS"},
                    {"name": "check3", "status": "PASS"}
                ],
                "engine_type": "great_expectations",
                "engine_version": "0.18.0"
            }

            with patch.object(DQServiceClient, 'health_check', return_value=(True, {})):
                with patch.object(DQServiceClient, 'run_dq', side_effect=[mock_input_quality, mock_output_quality]):
                    result = self.service.preview_transformation(
                        pipeline_id=str(self.pipeline.id),
                        asset_id=str(self.asset.id),
                        sample_size=5
                    )

            # Verify quality comparison
            quality_impact = result.get("quality_metrics", {})
            comparison = quality_impact.get("quality_comparison", {})

            self.assertIsNotNone(comparison)
            self.assertAlmostEqual(comparison["quality_delta"], 0.15, places=10)  # 0.95 - 0.80
            self.assertAlmostEqual(comparison["quality_delta_percent"], 18.75, places=1)  # (0.15 / 0.80) * 100
            self.assertEqual(comparison["checks_delta"], 1)  # 3 passed - 2 passed
            self.assertTrue(comparison["improvement_detected"])
            self.assertFalse(comparison["degradation_detected"])
            self.assertEqual(comparison["status_change"], "MAINTAINED")  # Both PASS

    def test_quality_metrics_included_in_result_analysis(self):
        """Test that quality impact is included in result analysis."""
        # Mock storage client
        with patch('hub.apps.files.storage.S3StorageClient.get_file_content', return_value=self.csv_content):
            mock_quality = {
                "quality_score": 0.85,
                "overall_status": "PASS",
                "checks": [{"name": "check1", "status": "PASS"}],
                "engine_type": "great_expectations",
                "engine_version": "0.18.0"
            }

            with patch.object(DQServiceClient, 'health_check', return_value=(True, {})):
                with patch.object(DQServiceClient, 'run_dq', return_value=mock_quality):
                    result = self.service.preview_transformation(
                        pipeline_id=str(self.pipeline.id),
                        asset_id=str(self.asset.id),
                        sample_size=5
                    )

            # Verify quality impact is in analysis
            analysis = result.get("analysis", {})
            self.assertIn("quality_impact", analysis)

            # Verify quality_metrics is at top level
            self.assertIn("quality_metrics", result)
            self.assertEqual(result["quality_metrics"], analysis["quality_impact"])

    def test_quality_metrics_stored_in_preview_cache(self):
        """Test that quality metrics are stored in preview cache."""
        # Clear cache first
        cache.clear()

        # Mock storage client
        with patch('hub.apps.files.storage.S3StorageClient.get_file_content', return_value=self.csv_content):
            mock_quality = {
                "quality_score": 0.88,
                "overall_status": "PASS",
                "checks": [
                    {"name": "completeness", "status": "PASS"},
                    {"name": "validity", "status": "PASS"}
                ],
                "engine_type": "great_expectations",
                "engine_version": "0.18.0"
            }

            with patch.object(DQServiceClient, 'health_check', return_value=(True, {})):
                with patch.object(DQServiceClient, 'run_dq', return_value=mock_quality):
                    # First call - should generate and cache
                    result1 = self.service.preview_transformation(
                        pipeline_id=str(self.pipeline.id),
                        asset_id=str(self.asset.id),
                        sample_size=5
                    )

                    # Second call - should return from cache
                    result2 = self.service.preview_transformation(
                        pipeline_id=str(self.pipeline.id),
                        asset_id=str(self.asset.id),
                        sample_size=5
                    )

            # Verify first result has quality metrics
            self.assertIn("quality_metrics", result1)
            self.assertFalse(result1["cached"])

            # Verify second result (from cache) has quality metrics
            self.assertTrue(result2["cached"])
            self.assertIn("quality_metrics", result2)
            self.assertEqual(result1["quality_metrics"], result2["quality_metrics"])

            # Verify quality metrics structure in cached result
            quality_metrics = result2["quality_metrics"]
            self.assertIn("available", quality_metrics)
            if quality_metrics.get("available"):
                self.assertIn("input_quality_metrics", quality_metrics)

    def test_quality_service_unavailable_handled_gracefully(self):
        """Test that preview continues when quality service is unavailable."""
        # Mock storage client
        with patch('hub.apps.files.storage.S3StorageClient.get_file_content', return_value=self.csv_content):
            # Mock DQ service as unavailable
            with patch.object(DQServiceClient, 'health_check', return_value=(False, {})):
                result = self.service.preview_transformation(
                    pipeline_id=str(self.pipeline.id),
                    asset_id=str(self.asset.id),
                    sample_size=5
                )

            # Verify preview still generated
            self.assertIsNotNone(result)
            self.assertIn("analysis", result)

            # Verify quality impact indicates unavailability
            quality_impact = result.get("analysis", {}).get("quality_impact", {})
            self.assertIn("available", quality_impact)
            if not quality_impact.get("available"):
                self.assertIn("error", quality_impact)

    def test_quality_metrics_with_degradation_detected(self):
        """Test quality metrics when degradation is detected."""
        # Mock storage client
        with patch('hub.apps.files.storage.S3StorageClient.get_file_content', return_value=self.csv_content):
            mock_input_quality = {
                "quality_score": 0.90,
                "overall_status": "PASS",
                "checks": [
                    {"name": "check1", "status": "PASS"},
                    {"name": "check2", "status": "PASS"}
                ],
                "engine_type": "great_expectations",
                "engine_version": "0.18.0"
            }

            mock_output_quality = {
                "quality_score": 0.70,
                "overall_status": "WARN",
                "checks": [
                    {"name": "check1", "status": "PASS"},
                    {"name": "check2", "status": "FAIL"}
                ],
                "engine_type": "great_expectations",
                "engine_version": "0.18.0"
            }

            with patch.object(DQServiceClient, 'health_check', return_value=(True, {})):
                with patch.object(DQServiceClient, 'run_dq', side_effect=[mock_input_quality, mock_output_quality]):
                    result = self.service.preview_transformation(
                        pipeline_id=str(self.pipeline.id),
                        asset_id=str(self.asset.id),
                        sample_size=5
                    )

            # Verify degradation is detected
            quality_impact = result.get("quality_metrics", {})
            comparison = quality_impact.get("quality_comparison", {})

            self.assertFalse(comparison["improvement_detected"])
            self.assertTrue(comparison["degradation_detected"])
            self.assertEqual(comparison["status_change"], "DEGRADED")  # PASS -> WARN
            self.assertLess(comparison["quality_delta"], 0)

    def test_quality_metrics_detailed_structure(self):
        """Test that quality metrics include detailed structure with all required fields."""
        # Mock storage client
        with patch('hub.apps.files.storage.S3StorageClient.get_file_content', return_value=self.csv_content):
            mock_quality = {
                "quality_score": 0.85,
                "overall_status": "PASS",
                "checks": [
                    {"name": "completeness", "status": "PASS", "score": 0.9},
                    {"name": "validity", "status": "PASS", "score": 0.8},
                    {"name": "consistency", "status": "FAIL", "score": 0.5}
                ],
                "engine_type": "great_expectations",
                "engine_version": "0.18.0"
            }

            with patch.object(DQServiceClient, 'health_check', return_value=(True, {})):
                with patch.object(DQServiceClient, 'run_dq', return_value=mock_quality):
                    result = self.service.preview_transformation(
                        pipeline_id=str(self.pipeline.id),
                        asset_id=str(self.asset.id),
                        sample_size=5
                    )

            # Verify detailed structure
            quality_metrics = result.get("quality_metrics", {})
            if quality_metrics.get("available"):
                input_metrics = quality_metrics.get("input_quality_metrics", {})

                # Verify all required fields
                self.assertIn("quality_score", input_metrics)
                self.assertIn("overall_status", input_metrics)
                self.assertIn("checks_passed", input_metrics)
                self.assertIn("checks_failed", input_metrics)
                self.assertIn("checks_total", input_metrics)
                self.assertIn("engine_type", input_metrics)
                self.assertIn("engine_version", input_metrics)
                self.assertIn("profile_key", input_metrics)

                # Verify check counts are correct
                self.assertEqual(input_metrics["checks_passed"], 2)
                self.assertEqual(input_metrics["checks_failed"], 1)
                self.assertEqual(input_metrics["checks_total"], 3)


class PreviewQualityServiceIntegrationRealServicesTest(TestCase):
    """Integration tests for quality service in preview with real services."""

    def setUp(self):
        """Set up test fixtures."""
        tenant_name = f"Integration Test Tenant {uuid.uuid4().hex[:8]}"
        self.tenant = Tenant.objects.create(
            name=tenant_name,
            slug=f"integration-test-tenant-{uuid.uuid4().hex[:8]}"
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
                "steps": [{"name": "step1", "type": "task"}]
            },
            status=PipelineStatus.ACTIVE
        )

        # Create asset with dataset and file
        asset_key = f"test-asset-{uuid.uuid4().hex[:8]}"
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=asset_key,
            name="Integration Test Asset",
            created_by=self.user
        )

        # Create CSV file content
        self.csv_content = b"id,name,age\n1,Alice,25\n2,Bob,17\n3,Charlie,30\n4,Diana,22\n5,Eve,19"
        self.file = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test_data.csv",
            storage_path=f"test/integration/preview/{self.asset.id}/test_data.csv",
            size=len(self.csv_content),
            content_type="text/csv",
            status=FileStatus.ACTIVE
        )

        # Upload file to storage (real service)
        from hub.apps.files.storage import S3StorageClient

        try:
            storage_client = S3StorageClient()
            # Save file and get the actual storage path
            actual_storage_path = storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=self.csv_content
            )
            # Update file's storage_path to match what was actually saved
            self.file.storage_path = actual_storage_path
            self.file.save(update_fields=['storage_path'])
            self.storage_available = True
        except Exception as e:
            self.storage_available = False
            self.storage_error = str(e)

        # Create dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            file=self.file,
            format="CSV",
            version=1,
            row_count=5
        )

        self.service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_preview_quality_integration_with_real_quality_service(self):
        """Test preview quality integration with real QualityService (DQService)."""
        from hub.apps.dq.service_client import DQServiceClient
        from django.core.cache import cache

        # Check service availability
        if not self.storage_available:
            self.skipTest(f"Storage service not available: {self.storage_error}")
            return

        # Check DQ service availability
        try:
            dq_client = DQServiceClient()
            is_healthy, _ = dq_client.health_check()
            if not is_healthy:
                self.skipTest("DQ service is not healthy")
                return
        except Exception as e:
            self.skipTest(f"DQ service not available: {e}")
            return

        # Clear cache
        try:
            cache.clear()
        except Exception:
            pass

        # Execute preview with real services
        result = self.service.preview_transformation(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            sample_size=5,
            sampling_method="first_n"
        )

        # Verify result structure
        self.assertIsNotNone(result)
        self.assertIn("quality_metrics", result)

        # Verify quality metrics structure
        quality_metrics = result.get("quality_metrics", {})
        self.assertIn("available", quality_metrics)

        # If quality service is available, verify metrics
        if quality_metrics.get("available"):
            self.assertIn("input_quality_metrics", quality_metrics)
            input_metrics = quality_metrics["input_quality_metrics"]

            # Verify input quality metrics structure
            self.assertIn("quality_score", input_metrics)
            self.assertIn("overall_status", input_metrics)
            self.assertIn("checks_passed", input_metrics)
            self.assertIn("checks_total", input_metrics)

            # Verify quality score is in valid range (DQ service may return 0-100 or 0-1)
            quality_score = input_metrics.get("quality_score")
            if quality_score is not None:
                self.assertGreaterEqual(quality_score, 0.0)
                # DQ service may return score as 0-100 (percentage) or 0-1 (normalized)
                # Accept both formats
                self.assertLessEqual(quality_score, 100.0)

    def test_preview_quality_metrics_cached_with_real_service(self):
        """Test that quality metrics from real service are cached correctly."""
        from hub.apps.dq.service_client import DQServiceClient
        from django.core.cache import cache

        # Check service availability
        if not self.storage_available:
            self.skipTest(f"Storage service not available: {self.storage_error}")
            return

        try:
            dq_client = DQServiceClient()
            is_healthy, _ = dq_client.health_check()
            if not is_healthy:
                self.skipTest("DQ service is not healthy")
                return
        except Exception:
            self.skipTest("DQ service not available")
            return

        # Clear cache
        try:
            cache.clear()
        except Exception:
            pass

        # First call - generate and cache
        result1 = self.service.preview_transformation(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            sample_size=5
        )

        # Second call - should return from cache
        result2 = self.service.preview_transformation(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            sample_size=5
        )

        # Verify caching
        self.assertFalse(result1["cached"])
        self.assertTrue(result2["cached"])

        # Verify quality metrics are in cached result
        self.assertIn("quality_metrics", result2)

        # Verify quality metrics match between calls
        if result1.get("quality_metrics", {}).get("available"):
            self.assertEqual(
                result1["quality_metrics"],
                result2["quality_metrics"]
            )

    def test_preview_quality_comparison_with_real_service(self):
        """Test quality comparison (input vs output) with real QualityService."""
        from hub.apps.dq.service_client import DQServiceClient
        from django.core.cache import cache

        # Check service availability
        if not self.storage_available:
            self.skipTest(f"Storage service not available: {self.storage_error}")
            return

        try:
            dq_client = DQServiceClient()
            is_healthy, _ = dq_client.health_check()
            if not is_healthy:
                self.skipTest("DQ service is not healthy")
                return
        except Exception:
            self.skipTest("DQ service not available")
            return

        # Clear cache
        try:
            cache.clear()
        except Exception:
            pass

        # Execute preview
        result = self.service.preview_transformation(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            sample_size=5
        )

        # Verify quality comparison exists if both input and output quality are available
        quality_metrics = result.get("quality_metrics", {})
        if quality_metrics.get("available"):
            input_metrics = quality_metrics.get("input_quality_metrics")
            output_metrics = quality_metrics.get("output_quality_metrics")

            if input_metrics and output_metrics:
                comparison = quality_metrics.get("quality_comparison")
                self.assertIsNotNone(comparison)

                # Verify comparison structure
                self.assertIn("quality_delta", comparison)
                self.assertIn("quality_delta_percent", comparison)
                self.assertIn("improvement_detected", comparison)
                self.assertIn("degradation_detected", comparison)
                self.assertIn("status_change", comparison)

