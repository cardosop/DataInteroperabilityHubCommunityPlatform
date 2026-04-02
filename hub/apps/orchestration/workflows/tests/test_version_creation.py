"""
Unit tests for Version Creation Workflow

Comprehensive tests for version creation workflow including:
- Unit tests for individual tasks
- Integration tests for workflow execution
- E2E tests for complete version creation journey
"""
import uuid
import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus, StepStatus
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.version_creation import VersionCreationWorkflow
from hub.apps.datasets.models import Dataset, DatasetSnapshot, SchemaVersion
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.datasets.schema_evolution import SchemaEvolutionTracker

pytestmark = pytest.mark.django_db(transaction=True)


class VersionCreationWorkflowUnitTest(TestCase):
    """Unit tests for version creation workflow tasks"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User"
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path="test/test.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            content_sha256="abc123",
            created_by=self.user
        )
        
        # Create parent dataset version
        self.parent_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer", "nullable": False},
                    {"name": "name", "data_type": "string", "nullable": True}
                ]
            },
            sample_data_json=[{"id": 1, "name": "test1"}],
            row_count=100,
            format="CSV",
            version=1,
            created_by=self.user
        )
        
        # Initialize version history for parent
        VersionHistoryManager.create_version(
            dataset=self.parent_dataset,
            parent_version=None,
            semantic_version="1.0.0",
            is_current=True
        )
        
        # Create new dataset (will become new version)
        self.new_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer", "nullable": False},
                    {"name": "name", "data_type": "string", "nullable": True},
                    {"name": "email", "data_type": "string", "nullable": True}  # New field
                ]
            },
            sample_data_json=[{"id": 1, "name": "test1", "email": "test@example.com"}],
            row_count=150,
            format="CSV",
            version=2,
            created_by=self.user
        )
        
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        VersionCreationWorkflow.register_workflow(self.registry)
        VersionCreationWorkflow.register_tasks(self.engine)

    def test_detect_schema_changes_task_with_parent(self):
        """Test detecting schema changes with parent version"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id),
            "parent_version_id": str(self.parent_dataset.id)
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="detect_schema_changes",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._detect_schema_changes_task(
            input_data, instance, step
        )
        
        self.assertIn("schema_changes", result)
        self.assertIn("parent_version_id", result)
        schema_changes = result["schema_changes"]
        self.assertTrue(schema_changes["has_changes"])
        self.assertEqual(schema_changes["compatibility_level"], "BACKWARD_COMPATIBLE")
        self.assertGreater(len(schema_changes["non_breaking_changes"]), 0)

    def test_detect_schema_changes_task_without_parent(self):
        """Test detecting schema changes without parent version"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id)
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="detect_schema_changes",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._detect_schema_changes_task(
            input_data, instance, step
        )
        
        self.assertIn("schema_changes", result)
        schema_changes = result["schema_changes"]
        self.assertFalse(schema_changes["has_changes"])
        self.assertIsNone(result.get("parent_version_id"))

    def test_detect_schema_changes_task_missing_dataset(self):
        """Test detecting schema changes with missing dataset"""
        import uuid
        
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(uuid.uuid4())
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="detect_schema_changes",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        with self.assertRaises(Dataset.DoesNotExist):
            VersionCreationWorkflow._detect_schema_changes_task(
                input_data, instance, step
            )

    def test_calculate_semantic_version_task_with_parent(self):
        """Test calculating semantic version with parent"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id)
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "parent_version_id": str(self.parent_dataset.id)
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=1,
            step_name="calculate_semantic_version",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._calculate_semantic_version_task(
            input_data, instance, step
        )
        
        self.assertIn("semantic_version", result)
        semantic_version = result["semantic_version"]
        self.assertIsNotNone(semantic_version)
        # Should be 1.1.0 (minor increment for new field)
        self.assertEqual(semantic_version, "1.1.0")

    def test_calculate_semantic_version_task_with_override(self):
        """Test calculating semantic version with override"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id),
            "semantic_version": "2.0.0"
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=1,
            step_name="calculate_semantic_version",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._calculate_semantic_version_task(
            input_data, instance, step
        )
        
        self.assertEqual(result["semantic_version"], "2.0.0")

    def test_calculate_semantic_version_task_without_parent(self):
        """Test calculating semantic version without parent"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id)
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=1,
            step_name="calculate_semantic_version",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._calculate_semantic_version_task(
            input_data, instance, step
        )
        
        self.assertEqual(result["semantic_version"], "1.0.0")

    def test_create_version_record_task(self):
        """Test creating version record"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id),
            "version_tags": ["production"],
            "snapshot_metadata": {"source": "test"}
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "parent_version_id": str(self.parent_dataset.id),
            "semantic_version": "1.1.0"
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=2,
            step_name="create_version_record",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._create_version_record_task(
            input_data, instance, step
        )
        
        self.assertTrue(result["version_record_created"])
        self.assertEqual(result["semantic_version"], "1.1.0")
        self.assertIn("version_hash", result)
        
        # Verify dataset was updated
        self.new_dataset.refresh_from_db()
        self.assertEqual(self.new_dataset.semantic_version, "1.1.0")
        self.assertEqual(self.new_dataset.version_tags, ["production"])
        self.assertIsNotNone(self.new_dataset.version_hash)
        self.assertEqual(self.new_dataset.parent_version, self.parent_dataset)

    def test_store_version_snapshot_task_enabled(self):
        """Test storing version snapshot when enabled"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id),
            "store_snapshot": True,
            "snapshot_type": "FULL"
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=3,
            step_name="store_version_snapshot",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._store_version_snapshot_task(
            input_data, instance, step
        )
        
        self.assertTrue(result["snapshot_stored"])
        self.assertIn("snapshot_id", result)
        self.assertEqual(result["snapshot_type"], "FULL")
        
        # Verify snapshot was created
        snapshot = DatasetSnapshot.objects.get(id=result["snapshot_id"])
        self.assertEqual(snapshot.dataset, self.new_dataset)
        self.assertEqual(snapshot.snapshot_type, "FULL")
        self.assertIn("dataset_id", snapshot.snapshot_data)

    def test_store_version_snapshot_task_disabled(self):
        """Test skipping snapshot storage when disabled"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id),
            "store_snapshot": False
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=3,
            step_name="store_version_snapshot",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._store_version_snapshot_task(
            input_data, instance, step
        )
        
        self.assertFalse(result["snapshot_stored"])
        self.assertEqual(result["reason"], "store_snapshot is False")

    def test_update_version_history_task(self):
        """Test updating version history"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id)
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "parent_version_id": str(self.parent_dataset.id)
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=4,
            step_name="update_version_history",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._update_version_history_task(
            input_data, instance, step
        )
        
        self.assertTrue(result["version_history_updated"])
        self.assertIn("schema_version_id", result)
        self.assertIn("compatibility_level", result)
        
        # Verify SchemaVersion was created
        schema_version = SchemaVersion.objects.get(id=result["schema_version_id"])
        self.assertEqual(schema_version.dataset, self.new_dataset)
        self.assertEqual(schema_version.compatibility_level, result["compatibility_level"])

    def test_calculate_version_diff_task(self):
        """Test calculating version diff"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id),
            "include_data_diff": True
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "parent_version_id": str(self.parent_dataset.id)
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=5,
            step_name="calculate_version_diff",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._calculate_version_diff_task(
            input_data, instance, step
        )
        
        self.assertTrue(result["version_diff_calculated"])
        self.assertIn("diff_summary", result)
        diff_summary = result["diff_summary"]
        self.assertIn("compatibility_level", diff_summary)
        self.assertIn("breaking_changes_count", diff_summary)
        self.assertIn("row_count_diff", diff_summary)

    def test_calculate_version_diff_task_no_parent(self):
        """Test calculating version diff without parent"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id)
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=5,
            step_name="calculate_version_diff",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._calculate_version_diff_task(
            input_data, instance, step
        )
        
        self.assertFalse(result["version_diff_calculated"])
        self.assertEqual(result["reason"], "No parent version")

    def test_update_lineage_references_task(self):
        """Test updating lineage references"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id)
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=6,
            step_name="update_lineage_references",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._update_lineage_references_task(
            input_data, instance, step
        )
        
        self.assertTrue(result["lineage_references_updated"])

    def test_index_for_search_task(self):
        """Test indexing dataset for search"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id)
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=7,
            step_name="index_for_search",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._index_for_search_task(
            input_data, instance, step
        )
        
        self.assertIn("indexed", result)
        if result["indexed"]:
            self.assertIn("search_index_id", result)
            
            # Verify search index was created/updated
            from hub.apps.search.models import SearchIndex
            search_index = SearchIndex.objects.get(id=result["search_index_id"])
            self.assertEqual(search_index.resource_type, "DATASET")
            self.assertEqual(search_index.resource_id, self.new_dataset.id)

    def test_send_notifications_task(self):
        """Test sending notifications"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id),
            "send_notifications": True
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=8,
            step_name="send_notifications",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._send_notifications_task(
            input_data, instance, step
        )
        
        self.assertIn("notifications_sent", result)

    def test_send_notifications_task_disabled(self):
        """Test skipping notifications when disabled"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id),
            "send_notifications": False
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=8,
            step_name="send_notifications",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._send_notifications_task(
            input_data, instance, step
        )
        
        self.assertFalse(result["notifications_sent"])
        self.assertEqual(result["reason"], "send_notifications is False")

    def test_audit_logging_task(self):
        """Test audit logging"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "dataset_id": str(self.new_dataset.id),
            "triggered_by_id": str(self.user.id)
        }
        
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data = {
            "diff_summary": {
                "compatibility_level": "BACKWARD_COMPATIBLE",
                "breaking_changes_count": 0
            }
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=9,
            step_name="audit_logging",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._audit_logging_task(
            input_data, instance, step
        )
        
        self.assertIn("audit_event_id", result)
        
        # Verify audit event was created
        from hub.apps.audit.models import AuditEvent
        audit_event = AuditEvent.objects.get(id=result["audit_event_id"])
        self.assertEqual(audit_event.resource_type, "DATASET")
        self.assertEqual(audit_event.action, "VERSION_CREATED")
        self.assertEqual(audit_event.resource_id, self.new_dataset.id)

    def test_rollback_version_record_task(self):
        """Test rolling back version record"""
        # First create version record
        VersionHistoryManager.create_version(
            dataset=self.new_dataset,
            parent_version=self.parent_dataset,
            semantic_version="1.1.0",
            is_current=True
        )
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "dataset_id": str(self.new_dataset.id)
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=2,
            step_name="rollback_version_record",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._rollback_version_record_task(
            input_data, instance, step
        )
        
        self.assertTrue(result["rolled_back"])
        
        # Verify version fields were reverted
        self.new_dataset.refresh_from_db()
        self.assertIsNone(self.new_dataset.parent_version)
        self.assertIsNone(self.new_dataset.version_hash)
        self.assertFalse(self.new_dataset.is_current)
        self.assertIsNone(self.new_dataset.semantic_version)

    def test_rollback_version_snapshot_task(self):
        """Test rolling back version snapshot"""
        snapshot = DatasetSnapshot.objects.create(
            dataset=self.new_dataset,
            snapshot_data={"test": "data"},
            snapshot_type="FULL"
        )
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "snapshot_id": str(snapshot.id)
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=3,
            step_name="rollback_version_snapshot",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._rollback_version_snapshot_task(
            input_data, instance, step
        )
        
        self.assertTrue(result["rolled_back"])
        
        # Verify snapshot was deleted
        self.assertFalse(
            DatasetSnapshot.objects.filter(id=snapshot.id).exists()
        )

    def test_rollback_indexing_task(self):
        """Test rolling back search indexing"""
        from hub.apps.search.indexing import SearchIndexer
        search_index = SearchIndexer.index_dataset(self.new_dataset)
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=VersionCreationWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "search_index_id": str(search_index.id)
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=7,
            step_name="rollback_indexing",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = VersionCreationWorkflow._rollback_indexing_task(
            input_data, instance, step
        )
        
        self.assertTrue(result["rolled_back"])
        
        # Verify search index was deleted
        from hub.apps.search.models import SearchIndex
        self.assertFalse(
            SearchIndex.objects.filter(id=search_index.id).exists()
        )


class VersionCreationWorkflowIntegrationTest(TestCase):
    """Integration tests for version creation workflow execution"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User"
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path="test/test.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            content_sha256="abc123",
            created_by=self.user
        )
        
        # Create parent dataset
        self.parent_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"}
                ]
            },
            sample_data_json=[{"id": 1, "name": "test1"}],
            row_count=100,
            format="CSV",
            version=1,
            created_by=self.user
        )
        
        VersionHistoryManager.create_version(
            dataset=self.parent_dataset,
            parent_version=None,
            semantic_version="1.0.0",
            is_current=True
        )
        
        # Create new dataset
        self.new_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"},
                    {"name": "email", "data_type": "string"}  # New field
                ]
            },
            sample_data_json=[{"id": 1, "name": "test1", "email": "test@example.com"}],
            row_count=150,
            format="CSV",
            version=2,
            created_by=self.user
        )

    def test_execute_workflow_basic(self):
        """Test executing complete workflow"""
        result = VersionCreationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.new_dataset.id),
            parent_version_id=str(self.parent_dataset.id),
            triggered_by_id=str(self.user.id)
        )
        
        self.assertTrue(result["success"])
        self.assertIn("workflow_instance_id", result)
        self.assertIn("semantic_version", result)
        self.assertEqual(result["semantic_version"], "1.1.0")
        
        # Verify dataset was updated
        self.new_dataset.refresh_from_db()
        self.assertEqual(self.new_dataset.semantic_version, "1.1.0")
        self.assertIsNotNone(self.new_dataset.version_hash)
        self.assertEqual(self.new_dataset.parent_version, self.parent_dataset)
        self.assertTrue(self.new_dataset.is_current)
        
        # Verify parent is no longer current
        self.parent_dataset.refresh_from_db()
        self.assertFalse(self.parent_dataset.is_current)

    def test_execute_workflow_with_snapshot(self):
        """Test executing workflow with snapshot storage"""
        result = VersionCreationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.new_dataset.id),
            parent_version_id=str(self.parent_dataset.id),
            store_snapshot=True,
            snapshot_type="FULL",
            triggered_by_id=str(self.user.id)
        )
        
        self.assertTrue(result["success"])
        
        # Verify snapshot was created
        snapshots = DatasetSnapshot.objects.filter(dataset=self.new_dataset)
        self.assertEqual(snapshots.count(), 1)
        snapshot = snapshots.first()
        self.assertEqual(snapshot.snapshot_type, "FULL")

    def test_execute_workflow_with_version_tags(self):
        """Test executing workflow with version tags"""
        result = VersionCreationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.new_dataset.id),
            parent_version_id=str(self.parent_dataset.id),
            version_tags=["production", "stable"],
            triggered_by_id=str(self.user.id)
        )
        
        self.assertTrue(result["success"])
        
        # Verify version tags were set
        self.new_dataset.refresh_from_db()
        self.assertIn("production", self.new_dataset.version_tags)
        self.assertIn("stable", self.new_dataset.version_tags)

    def test_execute_workflow_with_semantic_version_override(self):
        """Test executing workflow with semantic version override"""
        result = VersionCreationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.new_dataset.id),
            parent_version_id=str(self.parent_dataset.id),
            semantic_version="2.0.0",
            triggered_by_id=str(self.user.id)
        )
        
        self.assertTrue(result["success"])
        self.assertEqual(result["semantic_version"], "2.0.0")
        
        # Verify semantic version was set
        self.new_dataset.refresh_from_db()
        self.assertEqual(self.new_dataset.semantic_version, "2.0.0")

    def test_execute_workflow_without_parent(self):
        """Test executing workflow without parent version"""
        result = VersionCreationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.new_dataset.id),
            triggered_by_id=str(self.user.id)
        )
        
        self.assertTrue(result["success"])
        self.assertEqual(result["semantic_version"], "1.0.0")
        
        # Verify dataset was updated
        self.new_dataset.refresh_from_db()
        self.assertEqual(self.new_dataset.semantic_version, "1.0.0")
        self.assertIsNone(self.new_dataset.parent_version)

    def test_execute_workflow_invalid_dataset(self):
        """Test executing workflow with invalid dataset"""
        import uuid
        
        with self.assertRaises(ValueError):
            VersionCreationWorkflow.execute(
                tenant_id=str(self.tenant.id),
                dataset_id=str(uuid.uuid4()),
                triggered_by_id=str(self.user.id)
            )


class VersionCreationWorkflowE2ETest(TestCase):
    """End-to-end tests for version creation journey"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User"
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path="test/test.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            content_sha256="abc123",
            created_by=self.user
        )
        
        # Create parent dataset
        self.parent_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"}
                ]
            },
            sample_data_json=[{"id": 1, "name": "test1"}],
            row_count=100,
            format="CSV",
            version=1,
            created_by=self.user
        )
        
        VersionHistoryManager.create_version(
            dataset=self.parent_dataset,
            parent_version=None,
            semantic_version="1.0.0",
            is_current=True
        )

    def test_e2e_version_creation_journey(self):
        """Test complete version creation journey"""
        # Get next available version number
        latest_dataset = Dataset.objects.filter(
            tenant=self.tenant,
            asset=self.asset
        ).order_by('-version').first()
        next_version = (latest_dataset.version + 1) if latest_dataset else 1
        
        # Create new dataset with breaking change (removed field)
        new_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"}  # Removed "name" field
                ]
            },
            sample_data_json=[{"id": 1}],
            row_count=150,
            format="CSV",
            version=next_version,
            created_by=self.user
        )
        
        # Execute workflow
        result = VersionCreationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            dataset_id=str(new_dataset.id),
            parent_version_id=str(self.parent_dataset.id),
            store_snapshot=True,
            version_tags=["production"],
            triggered_by_id=str(self.user.id)
        )
        
        # Verify workflow completed successfully
        self.assertTrue(result["success"])
        self.assertIn("semantic_version", result)
        
        # Verify version was created correctly
        new_dataset.refresh_from_db()
        self.assertEqual(new_dataset.semantic_version, "2.0.0")  # Major increment for breaking change
        self.assertEqual(new_dataset.version_tags, ["production"])
        self.assertIsNotNone(new_dataset.version_hash)
        self.assertEqual(new_dataset.parent_version, self.parent_dataset)
        self.assertTrue(new_dataset.is_current)
        
        # Verify parent is no longer current
        self.parent_dataset.refresh_from_db()
        self.assertFalse(self.parent_dataset.is_current)
        
        # Verify snapshot was created
        snapshots = DatasetSnapshot.objects.filter(dataset=new_dataset)
        self.assertEqual(snapshots.count(), 1)
        
        # Verify SchemaVersion was created
        schema_versions = SchemaVersion.objects.filter(dataset=new_dataset)
        self.assertEqual(schema_versions.count(), 1)
        schema_version = schema_versions.first()
        # Removing a field is FORWARD_COMPATIBLE (old consumers can still read, just won't see removed field)
        # but it's still a breaking change for semantic versioning (major increment)
        self.assertEqual(schema_version.compatibility_level, "FORWARD_COMPATIBLE")
        
        # Verify search index was created/updated
        from hub.apps.search.models import SearchIndex
        search_indices = SearchIndex.objects.filter(
            tenant=self.tenant,
            resource_type="DATASET",
            resource_id=new_dataset.id
        )
        self.assertGreaterEqual(search_indices.count(), 1)
        
        # Verify audit trail
        from hub.apps.audit.models import AuditEvent
        audit_events = AuditEvent.objects.filter(
            tenant=self.tenant,
            resource_type="DATASET",
            resource_id=str(new_dataset.id),
            action="VERSION_CREATED"
        )
        self.assertGreaterEqual(audit_events.count(), 1)

    def test_e2e_version_creation_with_non_breaking_change(self):
        """Test version creation with non-breaking change"""
        # Create new dataset with non-breaking change (added field)
        new_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"},
                    {"name": "email", "data_type": "string"}  # New field
                ]
            },
            sample_data_json=[{"id": 1, "name": "test1", "email": "test@example.com"}],
            row_count=150,
            format="CSV",
            version=2,
            created_by=self.user
        )
        
        # Execute workflow
        result = VersionCreationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            dataset_id=str(new_dataset.id),
            parent_version_id=str(self.parent_dataset.id),
            triggered_by_id=str(self.user.id)
        )
        
        # Verify semantic version is minor increment
        self.assertEqual(result["semantic_version"], "1.1.0")
        
        # Verify SchemaVersion compatibility level
        schema_version = SchemaVersion.objects.filter(dataset=new_dataset).first()
        self.assertEqual(schema_version.compatibility_level, "BACKWARD_COMPATIBLE")

    def test_e2e_version_creation_first_version(self):
        """Test creating first version (no parent)"""
        # Get next available version number
        latest_dataset = Dataset.objects.filter(
            tenant=self.tenant,
            asset=self.asset
        ).order_by('-version').first()
        next_version = (latest_dataset.version + 1) if latest_dataset else 1
        
        new_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"}
                ]
            },
            sample_data_json=[{"id": 1, "name": "test1"}],
            row_count=100,
            format="CSV",
            version=next_version,
            created_by=self.user
        )
        
        # Execute workflow without parent
        result = VersionCreationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            dataset_id=str(new_dataset.id),
            triggered_by_id=str(self.user.id)
        )
        
        # Verify semantic version is 1.0.0
        self.assertEqual(result["semantic_version"], "1.0.0")
        
        # Verify dataset was updated
        new_dataset.refresh_from_db()
        self.assertEqual(new_dataset.semantic_version, "1.0.0")
        self.assertIsNone(new_dataset.parent_version)
        self.assertTrue(new_dataset.is_current)


