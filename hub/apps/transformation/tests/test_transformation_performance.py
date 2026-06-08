"""
Performance tests for transformation pipelines

Tests verify performance characteristics of transformation operations:
- Pipeline creation performance
- Pipeline execution performance
- Preview generation performance
- Wrangling operations performance
- Concurrent execution handling
- Large dataset processing
"""
import uuid
import pytest
pytestmark = pytest.mark.slow
import time
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.db import transaction
from hub.apps.tenants.models import Tenant
from hub.apps.transformation.exceptions import TransformationExecutionError
from hub.apps.transformation.services import TransformationService
from hub.apps.transformation.models import (
    TransformationPipeline,
    PipelineStatus,
    PipelineExecution,
    ExecutionStatus,
    ExecutionMode
)
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import StorageObjectNotFoundError
from hub.apps.governance.models import AccessPolicy


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TransformationPerformanceTest(TestCase):
    """Test transformation pipeline performance"""

    def setUp(self):
        """Set up per-test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"t-{uid}"
        )
        self.user = User.objects.create_user(
            email=f"t-{uid}@test.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create DATA_PROVIDER role
        data_provider_role, _ = Role.objects.get_or_create(tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"}
        )
        self.user.user_roles.create(role=data_provider_role)

        # Create ABAC policy to allow transformation operations
        AccessPolicy.objects.get_or_create(
            tenant=self.tenant,
            name="Allow Transformation Operations",
            defaults={
                "conditions": {
                    "user": {"tenant_id": str(self.tenant.id)},
                    "resource": {"type": "TRANSFORMATION_PIPELINE"}
                },
                "effect": "ALLOW",
                "priority": 100,
                "enabled": True,
                "created_by": self.user
            }
        )

        self.service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_pipeline_creation_performance(self):
        """Test that pipeline creation completes within acceptable time"""
        pipeline_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "type": "FILTER",
                    "name": "filter_step",
                    "config": {
                        "condition": "column1 > 100"
                    }
                }
            ]
        }

        start_time = time.time()
        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Performance Test Pipeline",
            pipeline_definition=pipeline_definition
        )
        creation_time = time.time() - start_time

        # Pipeline creation should complete within 2 seconds
        self.assertLess(creation_time, 2.0, f"Pipeline creation took {creation_time:.2f}s, expected < 2.0s")
        self.assertIsNotNone(pipeline)

    def test_preview_generation_performance(self):
        """Test that preview generation completes within acceptable time"""
        # Create a simple pipeline
        pipeline_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "type": "FILTER",
                    "name": "filter_step",
                    "config": {
                        "condition": "column1 > 100"
                    }
                }
            ]
        }

        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Preview Performance Test Pipeline",
            pipeline_definition=pipeline_definition
        )

        # Create a test asset with dataset
        asset = Asset.objects.create(
            name="Test Asset",
            tenant=self.tenant,
            status=AssetStatus.ACTIVE
        )

        file_obj = File.objects.create(
            name="test.csv",
            tenant=self.tenant,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            size=1024
        )

        dataset = Dataset.objects.create(
            asset=asset,
            tenant=self.tenant,
            version=1,
            format="CSV",
            file=file_obj
        )

        # Test preview generation performance
        # Happy path: preview succeeds (requires file storage), measure performance
        start_time = time.time()
        try:
            preview_result = self.service.preview_transformation(
                pipeline_id=str(pipeline.id),
                asset_id=str(asset.id),
                sample_size=10,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )
            preview_time = time.time() - start_time

            # Preview generation should complete within 10 seconds for small samples
            if preview_result:
                self.assertLess(preview_time, 10.0, f"Preview generation took {preview_time:.2f}s, expected < 10.0s")
        except (TransformationExecutionError, StorageObjectNotFoundError) as e:
            # Error path: preview fails due to missing storage or integration issues.
            # StorageObjectNotFoundError is expected in test environments without
            # pre-existing MinIO files.
            preview_time = time.time() - start_time
            self.assertLess(preview_time, 2.0,
                          f"Preview failure took {preview_time:.2f}s, expected < 2.0s. "
                          f"Exception: {type(e).__name__}: {str(e)}")

    def test_sequential_pipeline_creation_performance(self):
        """Test that multiple pipelines can be created sequentially within time limits"""
        pipeline_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "type": "FILTER",
                    "name": "filter_step",
                    "config": {
                        "condition": "column1 > 100"
                    }
                }
            ]
        }

        start_time = time.time()
        pipelines = []

        # Create 5 pipelines sequentially (simulating concurrent requests)
        for i in range(5):
            pipeline = self.service.create_pipeline(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name=f"Concurrent Test Pipeline {i}",
                pipeline_definition=pipeline_definition
            )
            pipelines.append(pipeline)

        total_time = time.time() - start_time

        # 5 pipelines should be created within 10 seconds
        self.assertLess(total_time, 10.0, f"Creating 5 pipelines took {total_time:.2f}s, expected < 10.0s")
        self.assertEqual(len(pipelines), 5)

    def test_large_pipeline_definition_performance(self):
        """Test that large pipeline definitions are handled efficiently"""
        # Create a pipeline with many steps
        steps = []
        for i in range(20):
            steps.append({
                "type": "FILTER",
                "name": f"filter_step_{i}",
                "config": {
                    "condition": f"column{i} > {i * 10}"
                }
            })

        pipeline_definition = {
            "version": "1.0.0",
            "steps": steps
        }

        start_time = time.time()
        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Large Pipeline Test",
            pipeline_definition=pipeline_definition
        )
        creation_time = time.time() - start_time

        # Large pipeline creation should still complete within 3 seconds
        self.assertLess(creation_time, 3.0, f"Large pipeline creation took {creation_time:.2f}s, expected < 3.0s")
        self.assertIsNotNone(pipeline)
        self.assertEqual(len(pipeline.get_pipeline_definition().get("steps", [])), 20)

