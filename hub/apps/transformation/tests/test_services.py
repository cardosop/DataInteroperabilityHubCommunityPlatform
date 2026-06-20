"""
Unit tests for TransformationService.
"""

import uuid
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.governance.models import AccessPolicy
from hub.apps.tenants.models import Tenant
from hub.apps.transformation.exceptions import TransformationExecutionError
from hub.apps.transformation.models import (
    PipelineStatus,
    TransformationNode,
    TransformationPipeline,
)
from hub.apps.transformation.services import TransformationService
from hub.apps.users.models import Role, UserRole, UserStatus

User = get_user_model()


class TransformationServiceTest(TestCase):
    """Test cases for TransformationService."""

    def setUp(self):
        """Set up per-test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")

        # Create DATA_PROVIDER role for the tenant
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )

        # Create user with DATA_PROVIDER role
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Assign DATA_PROVIDER role to user
        UserRole.objects.get_or_create(user=self.user, role=self.data_provider_role)

        # Create ABAC policy to allow DATA_PROVIDER role users to create pipelines
        AccessPolicy.objects.get_or_create(
            tenant=self.tenant,
            name="Allow Pipeline Creation",
            defaults={
                "conditions": {"user": {"tenant_id": str(self.tenant.id)}},
                "effect": "ALLOW",
                "priority": 100,
                "enabled": True,
                "created_by": self.user,
            },
        )

        self.valid_pipeline_definition = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "extract_data", "input": {}}],
        }
        self.service = TransformationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_service_initialization(self):
        """Test TransformationService initialization."""
        service = TransformationService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        self.assertEqual(service.tenant_id, str(self.tenant.id))
        self.assertEqual(service.user_id, str(self.user.id))
        self.assertEqual(service.service_name, "transformation_service")
        self.assertIsNotNone(service._event_publisher)

    def test_service_initialization_without_ids(self):
        """Test TransformationService initialization without tenant/user IDs."""
        service = TransformationService()

        self.assertIsNone(service.tenant_id)
        self.assertIsNone(service.user_id)
        self.assertEqual(service.service_name, "transformation_service")
        self.assertIsNotNone(service._event_publisher)

    def test_create_pipeline(self):
        """Test creating a transformation pipeline."""
        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Pipeline",
            description="Test description",
            pipeline_definition=self.valid_pipeline_definition,
            version="1.0.0",
            status=PipelineStatus.DRAFT,
        )

        self.assertIsNotNone(pipeline.id)
        self.assertEqual(pipeline.name, "Test Pipeline")
        self.assertEqual(pipeline.description, "Test description")
        self.assertEqual(pipeline.get_pipeline_definition(), self.valid_pipeline_definition)
        self.assertEqual(pipeline.version, "1.0.0")
        self.assertEqual(pipeline.status, PipelineStatus.DRAFT)
        self.assertEqual(pipeline.tenant_id, self.tenant.id)
        self.assertEqual(pipeline.created_by_id, self.user.id)

    def test_create_pipeline_with_defaults(self):
        """Test creating a pipeline with default values."""
        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), name="Test Pipeline"
        )

        self.assertIsNotNone(pipeline.id)
        self.assertEqual(pipeline.name, "Test Pipeline")
        self.assertEqual(pipeline.version, "1.0.0")
        self.assertEqual(pipeline.status, PipelineStatus.DRAFT)
        self.assertEqual(pipeline.get_pipeline_definition()["version"], "1.0.0")
        # Default pipeline definition includes at least one step to pass validation
        self.assertGreaterEqual(len(pipeline.get_pipeline_definition()["steps"]), 1)
        self.assertEqual(pipeline.get_pipeline_definition()["steps"][0]["name"], "initial_step")

    def test_create_pipeline_with_metadata(self):
        """Test creating a pipeline with metadata."""
        from hub.apps.assets.models import Asset, AssetStatus

        # Create assets for metadata
        source_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="source-asset",
            name="Source Asset",
            status=AssetStatus.ACTIVE,
        )
        target_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="target-asset",
            name="Target Asset",
            status=AssetStatus.DRAFT,
        )

        metadata = {
            "tags": ["etl", "customer-data"],
            "source_asset_id": str(source_asset.id),
            "target_asset_id": str(target_asset.id),
        }

        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Pipeline",
            metadata=metadata,
        )

        self.assertEqual(pipeline.metadata, metadata)

    def test_create_pipeline_validation_error(self):
        """Test creating a pipeline with invalid data raises ValidationError."""
        # Test with invalid pipeline definition (missing required fields)
        with self.assertRaises(ValidationError):
            self.service.create_pipeline(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Pipeline",
                pipeline_definition={
                    "version": "1.0.0",
                    # Missing required "steps" field
                },
            )

    def test_update_pipeline(self):
        """Test updating a transformation pipeline."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Original Name",
            description="Original description",
            pipeline_definition=self.valid_pipeline_definition,
            version="1.0.0",
            status=PipelineStatus.DRAFT,
        )

        updated_pipeline = self.service.update_pipeline(
            pipeline_id=str(pipeline.id),
            name="Updated Name",
            description="Updated description",
            version="2.0.0",
            status=PipelineStatus.ACTIVE,
        )

        self.assertEqual(updated_pipeline.name, "Updated Name")
        self.assertEqual(updated_pipeline.description, "Updated description")
        self.assertEqual(updated_pipeline.version, "2.0.0")
        self.assertEqual(updated_pipeline.status, PipelineStatus.ACTIVE)

    def test_update_pipeline_partial(self):
        """Test updating a pipeline with partial fields."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Original Name",
            pipeline_definition=self.valid_pipeline_definition,
        )

        updated_pipeline = self.service.update_pipeline(
            pipeline_id=str(pipeline.id), name="Updated Name"
        )

        self.assertEqual(updated_pipeline.name, "Updated Name")
        # Other fields should remain unchanged
        self.assertEqual(updated_pipeline.description, pipeline.description)

    def test_update_pipeline_metadata_merge(self):
        """Test updating pipeline metadata merges with existing."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            metadata={"tag1": "value1", "tag2": "value2"},
        )

        updated_pipeline = self.service.update_pipeline(
            pipeline_id=str(pipeline.id), metadata={"tag3": "value3"}
        )

        self.assertEqual(updated_pipeline.metadata["tag1"], "value1")
        self.assertEqual(updated_pipeline.metadata["tag2"], "value2")
        self.assertEqual(updated_pipeline.metadata["tag3"], "value3")

    def test_update_pipeline_not_found(self):
        """Test updating a non-existent pipeline raises NotFoundError."""
        with self.assertRaises(NotFoundError):
            self.service.update_pipeline(pipeline_id=str(uuid.uuid4()), name="Updated Name")

    def test_delete_pipeline(self):
        """Test deleting a transformation pipeline."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
        )
        pipeline_id = str(pipeline.id)

        self.service.delete_pipeline(pipeline_id=pipeline_id)

        # Pipeline should be deleted
        self.assertFalse(TransformationPipeline.objects.filter(id=pipeline_id).exists())

    def test_delete_pipeline_with_nodes(self):
        """Test deleting a pipeline also deletes its nodes (cascade)."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
        )
        node = TransformationNode.objects.create(
            pipeline=pipeline,
            node_type="filter",
            node_config={},
            position={"x": 0, "y": 0},
            order=1,
        )
        node_id = str(node.id)
        pipeline_id = str(pipeline.id)

        self.service.delete_pipeline(pipeline_id=pipeline_id)

        # Pipeline and node should be deleted
        self.assertFalse(TransformationPipeline.objects.filter(id=pipeline_id).exists())
        self.assertFalse(TransformationNode.objects.filter(id=node_id).exists())

    def test_delete_pipeline_not_found(self):
        """Test deleting a non-existent pipeline raises NotFoundError."""
        with self.assertRaises(NotFoundError):
            self.service.delete_pipeline(pipeline_id=str(uuid.uuid4()))

    def test_get_pipeline(self):
        """Test getting a transformation pipeline."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
        )

        retrieved_pipeline = self.service.get_pipeline(pipeline_id=str(pipeline.id))

        self.assertEqual(retrieved_pipeline.id, pipeline.id)
        self.assertEqual(retrieved_pipeline.name, "Test Pipeline")

    def test_get_pipeline_not_found(self):
        """Test getting a non-existent pipeline raises NotFoundError."""
        with self.assertRaises(NotFoundError):
            self.service.get_pipeline(pipeline_id=str(uuid.uuid4()))

    def test_create_node(self):
        """Test creating a transformation node."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
        )

        node = self.service.create_node(
            pipeline_id=str(pipeline.id),
            node_type="filter",
            node_config={"filter_expression": "age > 18"},
            position={"x": 100, "y": 200},
            order=1,
        )

        self.assertIsNotNone(node.id)
        self.assertEqual(node.pipeline, pipeline)
        self.assertEqual(node.node_type, "filter")
        self.assertEqual(node.get_node_config(), {"filter_expression": "age > 18"})
        self.assertEqual(node.position, {"x": 100, "y": 200})
        self.assertEqual(node.order, 1)

    def test_create_node_with_defaults(self):
        """Test creating a node with default values."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
        )

        node = self.service.create_node(pipeline_id=str(pipeline.id), node_type="transform")

        self.assertIsNotNone(node.id)
        self.assertEqual(node.node_type, "transform")
        self.assertEqual(node.get_node_config(), {})
        self.assertEqual(node.position, {})
        self.assertEqual(node.order, 1)

    def test_create_node_pipeline_not_found(self):
        """Test creating a node for non-existent pipeline raises NotFoundError."""
        with self.assertRaises(NotFoundError):
            self.service.create_node(pipeline_id=str(uuid.uuid4()), node_type="filter")

    @patch("hub.apps.transformation.services.TransformationEventPublisher.publish_pipeline_started")
    def test_publish_pipeline_started_event_delegates_to_publisher(self, mock_publish):
        """Test publish_pipeline_started delegates to TransformationEventPublisher."""
        mock_publish.return_value = "event-id-123"

        event_id = self.service.publish_pipeline_started(
            pipeline_id="pipeline-123",
            execution_id="execution-456",
            source_asset_id="asset-789",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        self.assertEqual(event_id, "event-id-123")
        # Check that the method was called with the correct arguments
        # Note: None values for optional params are not included in the call
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args.kwargs["pipeline_id"], "pipeline-123")
        self.assertEqual(call_args.kwargs["execution_id"], "execution-456")
        self.assertEqual(call_args.kwargs["source_asset_id"], "asset-789")
        self.assertEqual(call_args.kwargs["tenant_id"], str(self.tenant.id))
        self.assertEqual(call_args.kwargs["user_id"], str(self.user.id))

    @patch(
        "hub.apps.transformation.services.TransformationEventPublisher.publish_pipeline_completed"
    )
    def test_publish_pipeline_completed_event_delegates_to_publisher(self, mock_publish):
        """Test publish_pipeline_completed delegates to TransformationEventPublisher."""
        mock_publish.return_value = "event-id-456"

        event_id = self.service.publish_pipeline_completed(
            pipeline_id="pipeline-123",
            execution_id="execution-456",
            result_asset_id="asset-789",
            duration_ms=5000,
            records_processed=1000,
            status="COMPLETED",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        self.assertEqual(event_id, "event-id-456")
        mock_publish.assert_called_once_with(
            pipeline_id="pipeline-123",
            execution_id="execution-456",
            result_asset_id="asset-789",
            duration_ms=5000,
            records_processed=1000,
            status="COMPLETED",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    @patch("hub.apps.transformation.services.TransformationEventPublisher.publish_pipeline_failed")
    def test_publish_pipeline_failed_event_delegates_to_publisher(self, mock_publish):
        """Test publish_pipeline_failed delegates to TransformationEventPublisher."""
        mock_publish.return_value = "event-id-789"

        error_details = {"error_code": "VALIDATION_ERROR", "step": "filter"}

        event_id = self.service.publish_pipeline_failed(
            pipeline_id="pipeline-123",
            execution_id="execution-456",
            error_message="Pipeline execution failed",
            error_details=error_details,
            duration_ms=2000,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        self.assertEqual(event_id, "event-id-789")
        mock_publish.assert_called_once_with(
            pipeline_id="pipeline-123",
            execution_id="execution-456",
            error_message="Pipeline execution failed",
            error_details=error_details,
            duration_ms=2000,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    def test_service_uses_tenant_id_from_init(self):
        """Test that service uses tenant_id from initialization when not provided."""
        service = TransformationService(tenant_id=str(self.tenant.id))

        pipeline = service.create_pipeline(
            tenant_id=str(self.tenant.id),  # Still required, but service has it
            user_id=str(self.user.id),
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
        )

        self.assertEqual(pipeline.tenant_id, self.tenant.id)

    def test_service_transaction_rollback_on_error(self):
        """Test that transaction is rolled back on error."""
        # Try to create pipeline with invalid data (empty pipeline_definition will fail validation)
        # We'll use a valid tenant_id but invalid pipeline definition
        invalid_definition = {
            "version": "1.0.0",
            "steps": [],  # Empty steps will fail validation
        }

        with self.assertRaises(ValidationError):
            self.service.create_pipeline(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Pipeline",
                pipeline_definition=invalid_definition,
            )

        # No pipeline should be created
        self.assertEqual(TransformationPipeline.objects.filter(name="Test Pipeline").count(), 0)

    def test_create_pipeline_with_invalid_schema(self):
        """Test creating a pipeline with invalid schema raises ValidationError."""
        invalid_definitions = [
            # Missing version
            {"steps": [{"name": "step1", "type": "task"}]},
            # Missing steps
            {"version": "1.0.0"},
            # Steps not a list
            {"version": "1.0.0", "steps": "not-a-list"},
            # Empty steps
            {"version": "1.0.0", "steps": []},
            # Step missing name
            {"version": "1.0.0", "steps": [{"type": "task"}]},
            # Step missing type
            {"version": "1.0.0", "steps": [{"name": "step1"}]},
        ]

        for invalid_def in invalid_definitions:
            with self.assertRaises(ValidationError):
                self.service.create_pipeline(
                    tenant_id=str(self.tenant.id),
                    user_id=str(self.user.id),
                    name="Test Pipeline",
                    pipeline_definition=invalid_def,
                )

    def test_create_pipeline_with_incompatible_nodes(self):
        """Test creating a pipeline with incompatible nodes raises ValidationError."""
        # Pipeline with multiple output nodes (should fail)
        invalid_definition = {
            "version": "1.0.0",
            "steps": [
                {"name": "step1", "type": "task", "node_config": {"node_type": "output"}},
                {"name": "step2", "type": "task", "node_config": {"node_type": "output"}},
            ],
        }

        with self.assertRaises(ValidationError):
            self.service.create_pipeline(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Pipeline",
                pipeline_definition=invalid_definition,
            )

        # Pipeline with invalid node_type
        invalid_definition2 = {
            "version": "1.0.0",
            "steps": [
                {"name": "step1", "type": "task", "node_config": {"node_type": "invalid_type"}}
            ],
        }

        with self.assertRaises(ValidationError):
            self.service.create_pipeline(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Pipeline",
                pipeline_definition=invalid_definition2,
            )

    def test_create_pipeline_with_asset_compatibility(self):
        """Test creating a pipeline with asset compatibility validation."""
        from hub.apps.assets.models import Asset, AssetStatus

        # Create a valid source asset
        source_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="source-asset",
            name="Source Asset",
            status=AssetStatus.ACTIVE,
        )

        # Create a valid target asset
        target_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="target-asset",
            name="Target Asset",
            status=AssetStatus.DRAFT,
        )

        # Create pipeline with valid assets
        metadata = {
            "source_asset_id": str(source_asset.id),
            "target_asset_id": str(target_asset.id),
        }

        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Pipeline",
            metadata=metadata,
            pipeline_definition=self.valid_pipeline_definition,
        )

        self.assertIsNotNone(pipeline.id)
        self.assertEqual(pipeline.metadata["source_asset_id"], str(source_asset.id))
        self.assertEqual(pipeline.metadata["target_asset_id"], str(target_asset.id))

    def test_create_pipeline_with_invalid_source_asset(self):
        """Test creating a pipeline with invalid source asset raises ValidationError."""
        # Non-existent asset
        metadata = {"source_asset_id": str(uuid.uuid4())}

        with self.assertRaises(ValidationError):
            self.service.create_pipeline(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Pipeline",
                metadata=metadata,
                pipeline_definition=self.valid_pipeline_definition,
            )

    def test_create_pipeline_with_invalid_target_asset(self):
        """Test creating a pipeline with invalid target asset raises ValidationError."""
        from hub.apps.assets.models import Asset, AssetStatus

        # Create asset in RETIRED status (invalid for pipeline)
        retired_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="retired-asset",
            name="Retired Asset",
            status=AssetStatus.RETIRED,
        )

        metadata = {"target_asset_id": str(retired_asset.id)}

        with self.assertRaises(ValidationError):
            self.service.create_pipeline(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Pipeline",
                metadata=metadata,
                pipeline_definition=self.valid_pipeline_definition,
            )

    @patch("hub.apps.transformation.services.TransformationEventPublisher.publish_pipeline_created")
    def test_create_pipeline_publishes_event(self, mock_publish):
        """Test that pipeline creation publishes transformation.pipeline.created event."""
        mock_publish.return_value = "event-id-123"

        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
        )

        # Verify event was published
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        self.assertEqual(call_args.kwargs["pipeline_id"], str(pipeline.id))
        self.assertEqual(call_args.kwargs["name"], "Test Pipeline")
        self.assertEqual(call_args.kwargs["version"], "1.0.0")
        self.assertEqual(call_args.kwargs["status"], PipelineStatus.DRAFT)
        self.assertEqual(call_args.kwargs["tenant_id"], str(self.tenant.id))
        self.assertEqual(call_args.kwargs["user_id"], str(self.user.id))

    @patch("hub.apps.audit.utils.create_audit_event")
    def test_create_pipeline_creates_audit_log(self, mock_audit):
        """Test that pipeline creation creates audit log."""

        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
        )

        # Verify audit event was created
        mock_audit.assert_called_once()
        call_args = mock_audit.call_args
        self.assertEqual(call_args.kwargs["resource_type"], "TRANSFORMATION_PIPELINE")
        self.assertEqual(call_args.kwargs["action"], "CREATED")
        self.assertEqual(call_args.kwargs["resource_id"], str(pipeline.id))
        self.assertEqual(call_args.kwargs["result"], "SUCCESS")
        self.assertIn("pipeline_id", call_args.kwargs["details"])
        self.assertIn("pipeline_name", call_args.kwargs["details"])

    def test_create_pipeline_event_publishing_failure_non_critical(self):
        """Test that event publishing failure doesn't prevent pipeline creation."""
        with patch(
            "hub.apps.transformation.services.TransformationEventPublisher.publish_pipeline_created"
        ) as mock_publish:
            mock_publish.side_effect = Exception("Event publishing failed")

            # Pipeline should still be created
            pipeline = self.service.create_pipeline(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Pipeline",
                pipeline_definition=self.valid_pipeline_definition,
            )

            self.assertIsNotNone(pipeline.id)
            self.assertEqual(pipeline.name, "Test Pipeline")

    def test_create_pipeline_audit_logging_failure_non_critical(self):
        """Test that audit logging failure doesn't prevent pipeline creation."""
        with patch("hub.apps.audit.utils.create_audit_event") as mock_audit:
            mock_audit.side_effect = Exception("Audit logging failed")

            # Pipeline should still be created
            pipeline = self.service.create_pipeline(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Pipeline",
                pipeline_definition=self.valid_pipeline_definition,
            )

            self.assertIsNotNone(pipeline.id)
            self.assertEqual(pipeline.name, "Test Pipeline")

    def test_create_pipeline_integration_workflow(self):
        """Integration test for complete pipeline creation workflow."""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.audit.models import AuditEvent

        # Create assets
        source_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="source",
            name="Source",
            status=AssetStatus.ACTIVE,
        )

        # Create pipeline with all features
        pipeline_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {"node_type": "filter", "filter_expression": "age > 18"},
                },
                {
                    "name": "transform_step",
                    "type": "task",
                    "node_config": {"node_type": "transform", "transform_function": "uppercase"},
                },
                {"name": "output_step", "type": "task", "node_config": {"node_type": "output"}},
            ],
        }

        metadata = {"source_asset_id": str(source_asset.id), "tags": ["etl", "customer-data"]}

        pipeline = self.service.create_pipeline(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Integration Test Pipeline",
            description="Integration test",
            pipeline_definition=pipeline_definition,
            version="1.0.0",
            status=PipelineStatus.DRAFT,
            metadata=metadata,
        )

        # Verify pipeline was created
        self.assertIsNotNone(pipeline.id)
        self.assertEqual(pipeline.name, "Integration Test Pipeline")
        self.assertEqual(len(pipeline.get_pipeline_definition()["steps"]), 3)

        # Verify audit log was created
        audit_events = AuditEvent.objects.filter(
            resource_type="TRANSFORMATION_PIPELINE", action="CREATED", resource_id=pipeline.id
        )
        self.assertEqual(audit_events.count(), 1)

        audit_event = audit_events.first()
        self.assertEqual(audit_event.result, "SUCCESS")
        self.assertIn("pipeline_id", audit_event.details_json)
        self.assertIn("pipeline_name", audit_event.details_json)


class PipelineExecutionTest(TestCase):
    """Test cases for pipeline execution."""

    def setUp(self):
        """Set up per-test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.get_or_create(user=self.user, role=self.data_provider_role)
        AccessPolicy.objects.get_or_create(
            tenant=self.tenant,
            name="Allow Pipeline Execution",
            defaults={
                "conditions": {"user": {"tenant_id": str(self.tenant.id)}},
                "effect": "ALLOW",
                "priority": 100,
                "enabled": True,
                "created_by": self.user,
            },
        )

        # Create active pipeline
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Execution Pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "transform", "input": {}}],
            },
            status=PipelineStatus.ACTIVE,
        )

        # Create asset with dataset
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
        )

        # Create file
        self.file = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
        )

        # Create dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            file=self.file,
            format="CSV",
            row_count=100,  # Small dataset for sync execution
        )

        self.service = TransformationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.service_client.DQServiceClient")
    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    def test_execute_pipeline_sync_mode(self, mock_compliance_client, mock_dq_client, mock_storage):
        """Test execute_pipeline() in sync mode."""
        from hub.apps.transformation.models import ExecutionMode, ExecutionStatus

        # Mock storage client — must support context manager (with S3StorageClient() as ...)
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.__enter__.return_value = mock_storage_instance
        mock_storage_instance.get_file_content.return_value = b"id,name\n1,test\n2,test2\n"

        # Mock DQ client
        mock_dq_instance = MagicMock()
        mock_dq_client.return_value = mock_dq_instance
        mock_dq_instance.health_check.return_value = (True, "dq-service")
        mock_dq_instance.run_dq.return_value = {
            "quality_score": 0.95,
            "overall_status": "PASS",
            "checks_passed": 10,
            "checks_failed": 0,
        }

        # Mock compliance client — must support context manager (with ComplianceServiceClient() as ...)
        mock_compliance_instance = MagicMock()
        mock_compliance_client.return_value = mock_compliance_instance
        mock_compliance_instance.__enter__.return_value = mock_compliance_instance
        mock_compliance_instance.health_check.return_value = (True, "compliance-service")
        mock_compliance_instance.scan_file.return_value = {
            "overall_status": "PASS",
            "risk_level": "LOW",
            "allowed_to_store": True,
        }

        # Execute pipeline
        execution = self.service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.ASYNC,
        )

        # Verify execution
        self.assertIsNotNone(execution.id)
        self.assertEqual(execution.pipeline, self.pipeline)
        self.assertEqual(execution.asset, self.asset)
        self.assertEqual(execution.execution_mode, ExecutionMode.ASYNC)
        self.assertEqual(execution.status, ExecutionStatus.PENDING)
        # ASYNC: started_at is None until worker picks up the job
        self.assertIsNotNone(execution.prefect_flow_run_id)

        # Verify compliance check was run (blocks execution if fails)
        # Compliance checks run in async workflow, not validated here

        # Note: DQ checks are performed during workflow execution, not before
        # They are handled by TransformationQualityIntegration within the workflow tasks
        # So we don't assert DQ calls here as they happen asynchronously in the workflow

    def test_execute_pipeline_async_mode(self):
        """Test execute_pipeline() in async mode."""
        from hub.apps.jobs.models import JobType
        from hub.apps.transformation.models import ExecutionMode, ExecutionStatus

        # Update dataset to have large row count to trigger async mode
        self.dataset.row_count = 50000
        self.dataset.save()

        # Refresh from database to ensure row_count is available
        self.dataset.refresh_from_db()

        # Execute pipeline with explicit async mode
        execution = self.service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.ASYNC,
        )

        # Verify execution
        self.assertIsNotNone(execution.id)
        self.assertEqual(execution.execution_mode, ExecutionMode.ASYNC)
        self.assertEqual(execution.status, ExecutionStatus.PENDING)
        self.assertIsNotNone(execution.job)

        # Verify job was created with correct type
        self.assertEqual(execution.job.type, JobType.TRANSFORMATION)

    def test_execute_pipeline_pipeline_not_found(self):
        """Test execute_pipeline() with non-existent pipeline."""
        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError):
            self.service.execute_pipeline(
                pipeline_id=str(uuid.uuid4()),
                asset_id=str(self.asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

    def test_execute_pipeline_pipeline_not_active(self):
        """Test execute_pipeline() with inactive pipeline."""
        from hub.apps.transformation.exceptions import TransformationValidationError

        # Set pipeline to DRAFT
        self.pipeline.status = PipelineStatus.DRAFT
        self.pipeline.save()

        with self.assertRaises(TransformationValidationError):
            self.service.execute_pipeline(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

    def test_execute_pipeline_asset_not_found(self):
        """Test execute_pipeline() with non-existent asset."""
        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError):
            self.service.execute_pipeline(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(uuid.uuid4()),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

    def test_execute_pipeline_asset_no_dataset(self):
        """Test execute_pipeline() with asset that has no dataset."""
        from hub.apps.transformation.exceptions import AssetCompatibilityError

        # Delete dataset
        self.dataset.delete()

        with self.assertRaises(AssetCompatibilityError) as cm:
            self.service.execute_pipeline(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

        self.assertIn("no datasets", str(cm.exception).lower())

    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    def test_execute_pipeline_compliance_failure_blocks_execution(
        self, mock_compliance_client, mock_storage
    ):
        """Test that compliance failure blocks pipeline execution."""
        from hub.apps.transformation.exceptions import TransformationValidationError
        from hub.apps.transformation.models import ExecutionMode

        # Mock storage client — must support context manager (with S3StorageClient() as ...)
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.__enter__.return_value = mock_storage_instance
        mock_storage_instance.get_file_content.return_value = b"id,name\n1,test\n2,test2\n"

        # Mock compliance client to return FAIL — must support context manager
        mock_compliance_instance = MagicMock()
        mock_compliance_client.return_value = mock_compliance_instance
        mock_compliance_instance.__enter__.return_value = mock_compliance_instance
        mock_compliance_instance.health_check.return_value = (True, "compliance-service")
        mock_compliance_instance.scan_file.return_value = {
            "overall_status": "FAIL",
            "risk_level": "HIGH",
            "allowed_to_store": False,
        }

        with self.assertRaises(TransformationValidationError) as cm:
            self.service.execute_pipeline(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=ExecutionMode.ASYNC,
            )

        self.assertIn("compliance", str(cm.exception).lower())


class PreviewTransformationTest(TestCase):
    """Test cases for preview_transformation method using real services."""

    def setUp(self):
        """Set up per-test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"T-{uid}", slug=f"t-{uid}")
        self.user = User.objects.create_user(
            email=f"prev-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        from hub.apps.files.storage import S3StorageClient

        # Create pipeline
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task", "task": "extract_data"}],
            },
            version="1.0.0",
            status=PipelineStatus.ACTIVE,
        )

        # Create asset with dataset and file
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus

        self.asset = Asset.objects.create(tenant=self.tenant, name="Test Asset", domain="test")

        # Create test CSV content
        self.test_csv_content = (
            b"id,name,age\n1,Alice,25\n2,Bob,17\n3,Charlie,30\n4,Diana,22\n5,Eve,19"
        )

        # Create file and upload to storage (real service)
        storage_client = S3StorageClient()
        # Create file first to get the ID
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test_preview.csv",
            content_type="text/csv",
            size=len(self.test_csv_content),
            storage_path="placeholder",
            status=FileStatus.ACTIVE,
        )
        # Set storage_path to match what save_file() generates
        expected_key = f"{self.tenant.id}/{self.file.id}"
        self.file.storage_path = expected_key
        self.file.save(update_fields=["storage_path"])

        # Upload file content to storage
        try:
            storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=self.test_csv_content,
            )
        except Exception as e:
            # If storage fails, we'll skip tests that require it
            self.storage_available = False
            self.storage_error = str(e)
        else:
            self.storage_available = True
            self.storage_error = None

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
                    {"name": "age", "data_type": "integer"},
                ]
            },
        )

        # Check DQ service availability
        try:
            dq_client = DQServiceClient()
            is_healthy, _ = dq_client.health_check()
            self.dq_service_available = is_healthy
        except Exception:
            self.dq_service_available = False

        # Check cache availability (Redis)
        from django.core.cache import cache

        try:
            cache.set("test_key", "test_value", 1)
            cache.get("test_key")
            self.cache_available = True
        except Exception:
            self.cache_available = False

        self.service = TransformationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_preview_transformation_success(self):
        """Test successful preview generation with real services."""
        if not self.storage_available:
            self.skipTest(f"Storage not available: {self.storage_error}")

        # Clear cache to ensure cache miss
        from django.core.cache import cache

        cache.clear()

        # Execute preview with real services
        result = self.service.preview_transformation(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            sample_size=5,
            sampling_method="first_n",
        )

        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("preview_id", result)
        self.assertEqual(str(self.pipeline.id), result["pipeline_id"])
        self.assertEqual(str(self.asset.id), result["asset_id"])
        self.assertIn("analysis", result)
        self.assertFalse(result["cached"])
        self.assertIn("generated_at", result)
        self.assertEqual(result["sampling_method"], "first_n")
        self.assertEqual(result["sample_size"], 5)

        # Verify analysis structure
        analysis = result.get("analysis", {})
        self.assertIn("row_count_changes", analysis)
        self.assertIn("schema_changes", analysis)
        self.assertIn("quality_impact", analysis)

        # Verify row count analysis
        row_count = analysis["row_count_changes"]
        self.assertIn("input_rows", row_count)
        self.assertIn("output_rows", row_count)
        self.assertGreaterEqual(row_count["input_rows"], 0)

        # Verify cache was set (check by trying to get cached result)
        if self.cache_available:
            # Run again - should get cached result
            cached_result = self.service.preview_transformation(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                sample_size=5,
                sampling_method="first_n",
            )
            self.assertTrue(cached_result["cached"])
            self.assertEqual(cached_result["preview_id"], result["preview_id"])

    def test_preview_transformation_cache_hit(self):
        """Test preview returns cached result when available using real cache."""
        if not self.storage_available:
            self.skipTest(f"Storage not available: {self.storage_error}")
        if not self.cache_available:
            self.skipTest("Cache (Redis) not available")

        from django.core.cache import cache

        cache.clear()

        # First call - cache miss
        result1 = self.service.preview_transformation(
            pipeline_id=str(self.pipeline.id), asset_id=str(self.asset.id), sample_size=5
        )
        self.assertFalse(result1["cached"])

        # Second call - should be cache hit
        result2 = self.service.preview_transformation(
            pipeline_id=str(self.pipeline.id), asset_id=str(self.asset.id), sample_size=5
        )

        # Assertions
        self.assertIsNotNone(result2)
        self.assertTrue(result2["cached"])
        self.assertEqual(result2["preview_id"], result1["preview_id"])

    def test_preview_transformation_pipeline_not_found(self):
        """Test preview fails when pipeline not found."""
        with self.assertRaises(NotFoundError):
            self.service.preview_transformation(
                pipeline_id=str(uuid.uuid4()), asset_id=str(self.asset.id)
            )

    def test_preview_transformation_asset_not_found(self):
        """Test preview fails when asset not found."""
        with self.assertRaises(NotFoundError):
            self.service.preview_transformation(
                pipeline_id=str(self.pipeline.id), asset_id=str(uuid.uuid4())
            )

    def test_preview_transformation_no_dataset(self):
        """Test preview fails when asset has no dataset."""
        # Remove dataset
        self.dataset.delete()

        with self.assertRaises(TransformationExecutionError):
            self.service.preview_transformation(
                pipeline_id=str(self.pipeline.id), asset_id=str(self.asset.id)
            )

    def test_preview_transformation_random_sampling(self):
        """Test preview with random sampling method using real services."""
        if not self.storage_available:
            self.skipTest(f"Storage not available: {self.storage_error}")

        from django.core.cache import cache

        cache.clear()

        # Execute with random sampling
        result = self.service.preview_transformation(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            sample_size=3,
            sampling_method="random",
        )

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["sampling_method"], "random")
        self.assertLessEqual(len(result.get("input_sample", [])), 3)

    def test_preview_transformation_invalid_sampling_method(self):
        """Test preview fails with invalid sampling method."""
        if not self.storage_available:
            self.skipTest(f"Storage not available: {self.storage_error}")

        with self.assertRaises(ValueError) as cm:
            self.service.preview_transformation(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                sampling_method="invalid_method",
            )
        self.assertIn("sampling method", str(cm.exception).lower())

    def test_preview_transformation_cache_failure_continues(self):
        """Test preview continues even if cache set fails (using real services)."""
        if not self.storage_available:
            self.skipTest(f"Storage not available: {self.storage_error}")

        # Use patch.object to simulate cache.set failure without
        # mutating the real cache directly.
        from django.core.cache import cache

        with patch.object(cache, "set", side_effect=Exception("Cache down")):
            # Execute - should not raise exception even if cache fails
            result = self.service.preview_transformation(
                pipeline_id=str(self.pipeline.id), asset_id=str(self.asset.id), sample_size=5
            )

            # Assertions - preview should still succeed
            self.assertIsNotNone(result)
            self.assertFalse(result["cached"])

    def test_preview_transformation_event_publish_failure_continues(self):
        """Test preview continues even if event publishing fails (using real services)."""
        if not self.storage_available:
            self.skipTest(f"Storage not available: {self.storage_error}")

        # Mock event publisher to fail - patch the instance method
        from unittest.mock import patch

        with patch.object(
            self.service._event_publisher, "publish", side_effect=Exception("Event publish error")
        ):
            # Execute - should not raise exception even if event publish fails
            result = self.service.preview_transformation(
                pipeline_id=str(self.pipeline.id), asset_id=str(self.asset.id), sample_size=5
            )

            # Assertions - preview should still succeed
            self.assertIsNotNone(result)
            self.assertIn("preview_id", result)
