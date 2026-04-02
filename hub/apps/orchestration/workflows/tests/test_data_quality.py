"""
Unit tests for Data Quality Check Workflow
"""
import uuid
import unittest
from unittest.mock import patch, MagicMock, Mock
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus, StepStatus
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.data_quality import DataQualityCheckWorkflow
from hub.apps.dq.models import (
    DQRun, DQRunStatus, DQEngine, DQAnomaly, DQAnomalySeverity,
    DQAlertingRule, DQAlertChannel
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File as FileModel
from hub.apps.contracts.models import Contract
from hub.apps.jobs.models import Job, JobType, JobStatus


class DataQualityCheckWorkflowUnitTest(TestCase):
    """Unit tests for data quality check workflow tasks"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant, _ = Tenant.objects.get_or_create(name=f"Test Tenant {uid}")
        self.user, _ = User.objects.get_or_create(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            defaults={"display_name": "Test User"}
        )
        
        self.asset, _ = Asset.objects.get_or_create(
            tenant=self.tenant,
            name="Test Asset",
            defaults={"description": "A test asset", "created_by": self.user}
        )
        
        self.file_obj, _ = FileModel.objects.get_or_create(
            tenant=self.tenant,
            name="test.csv",
            defaults={
                "storage_path": "test/test.csv",
                "size": 1024,
                "content_type": "text/csv",
                "status": "ACTIVE"
            }
        )
        
        self.dataset, _ = Dataset.objects.get_or_create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file_obj,
            is_current=True,
            defaults={"created_by": self.user, "format": "CSV"}
        )
        
        self.contract, _ = Contract.objects.get_or_create(
            tenant=self.tenant,
            defaults={"created_by": self.user}
        )
        
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        DataQualityCheckWorkflow.register_workflow(self.registry)
        DataQualityCheckWorkflow.register_tasks(self.engine)

    def _get_workflow_definition(self):
        return self.registry.get_workflow(DataQualityCheckWorkflow.WORKFLOW_NAME)

    @patch('hub.apps.dq.service_client.DQServiceClient')
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.jobs.utils.create_job')
    @patch('hub.apps.audit.utils.create_audit_event')
    def test_create_dq_run_task(self, mock_audit, mock_create_job, mock_storage, mock_dq_client):
        """Test creating DQ run"""
        mock_job = MagicMock(id="job-123")
        mock_create_job.return_value = mock_job
        mock_audit.return_value = MagicMock(id="audit-123")
        
        input_data = {
            "tenant_id": str(self.tenant.id),
            "asset_id": str(self.asset.id),
            "profile_key": "intake_basic_gx",
            "triggered_by_id": str(self.user.id)
        }
        
        instance = self.engine.create_instance(
            workflow_name=DataQualityCheckWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="create_dq_run",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = DataQualityCheckWorkflow._create_dq_run_task(
            input_data, instance, step
        )
        
        self.assertIn("dq_run_id", result)
        self.assertIn("job_id", result)
        self.assertEqual(result["profile_key"], "intake_basic_gx")
        self.assertEqual(result["engine"], DQEngine.GREAT_EXPECTATIONS)
        
        # Verify DQ run was created
        dq_run = DQRun.objects.get(id=result["dq_run_id"])
        self.assertEqual(dq_run.tenant, self.tenant)
        self.assertEqual(dq_run.asset, self.asset)
        self.assertEqual(dq_run.profile_key, "intake_basic_gx")
        self.assertEqual(dq_run.status, DQRunStatus.PENDING)

    @patch('hub.apps.orchestration.workflows.data_quality.S3StorageClient')
    def test_load_contract_and_dataset_task(self, mock_storage_class):
        """Test loading contract and dataset"""
        mock_storage_client = MagicMock()
        mock_storage_client.get_file_content.return_value = b"test,data\n1,2"
        mock_storage_class.return_value = mock_storage_client
        
        # Create DQ run
        from hub.apps.jobs.utils import create_job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(self.asset.id)
        )
        
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        # Link file to dataset
        self.dataset.file = self.file_obj
        self.dataset.save()
        
        # Link contract to asset
        self.contract.asset = self.asset
        self.contract.status = "ACTIVE"
        self.contract.save()
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=DataQualityCheckWorkflow.WORKFLOW_NAME,
            input_data={"dq_run_id": str(dq_run.id)},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["dq_run_id"] = str(dq_run.id)
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=1,
            step_name="load_contract_and_dataset",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = DataQualityCheckWorkflow._load_contract_and_dataset_task(
            input_data, instance, step
        )
        
        self.assertIn("contract_id", result)
        self.assertIn("dataset_id", result)
        self.assertIn("file_id", result)
        self.assertEqual(result["contract_id"], str(self.contract.id))
        self.assertEqual(result["dataset_id"], str(self.dataset.id))
        self.assertEqual(result["file_id"], str(self.file_obj.id))
        self.assertEqual(result["file_format"], "csv")

    @patch('hub.apps.orchestration.workflows.data_quality.DQServiceClient')
    @patch('hub.apps.orchestration.workflows.data_quality.S3StorageClient')
    def test_execute_quality_rules_task(self, mock_storage_class, mock_dq_client_class):
        """Test executing quality rules"""
        mock_storage_client = MagicMock()
        mock_storage_client.get_file_content.return_value = b"test,data\n1,2"
        mock_storage_class.return_value = mock_storage_client
        
        mock_dq_client = MagicMock()
        mock_dq_client.health_check.return_value = (True, "dq-service")
        mock_dq_client.run_dq.return_value = {
            "overall_status": "PASS",
            "quality_score": 0.95,
            "checks": [
                {"check_id": "check1", "status": "PASS", "category": "completeness"},
                {"check_id": "check2", "status": "PASS", "category": "accuracy"}
            ],
            "engine_type": "GREAT_EXPECTATIONS",
            "engine_version": "0.18.0",
            "profile_key": "intake_basic_gx",
            "metadata": {"total_rows": 100, "total_columns": 2}
        }
        mock_dq_client_class.return_value = mock_dq_client
        
        # Create DQ run
        from hub.apps.jobs.utils import create_job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(self.asset.id)
        )
        
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        self.dataset.file = self.file_obj
        self.dataset.save()
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=DataQualityCheckWorkflow.WORKFLOW_NAME,
            input_data={"dq_run_id": str(dq_run.id)},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["dq_run_id"] = str(dq_run.id)
        instance.state_data["contract_id"] = str(self.contract.id)
        instance.state_data["dataset_id"] = str(self.dataset.id)
        instance.state_data["file_id"] = str(self.file_obj.id)
        instance.state_data["file_format"] = "csv"
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=2,
            step_name="execute_quality_rules",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = DataQualityCheckWorkflow._execute_quality_rules_task(
            input_data, instance, step
        )
        
        self.assertIn("dq_result", result)
        self.assertEqual(result["overall_status"], "PASS")
        self.assertEqual(result["quality_score"], 0.95)
        self.assertEqual(len(result["checks"]), 2)
        
        # Verify DQ run was updated
        dq_run.refresh_from_db()
        self.assertEqual(dq_run.status, DQRunStatus.RUNNING)
        self.assertIsNotNone(dq_run.started_at)

    def test_calculate_quality_scores_task(self):
        """Test calculating quality scores"""
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=DataQualityCheckWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        
        instance.state_data["dq_result"] = {
            "quality_score": 0.85,
            "checks": [
                {"check_id": "check1", "status": "PASS", "category": "completeness"},
                {"check_id": "check2", "status": "PASS", "category": "completeness"},
                {"check_id": "check3", "status": "FAIL", "category": "accuracy"},
                {"check_id": "check4", "status": "PASS", "category": "accuracy"}
            ]
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=3,
            step_name="calculate_quality_scores",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = DataQualityCheckWorkflow._calculate_quality_scores_task(
            input_data, instance, step
        )
        
        self.assertEqual(result["overall_score"], 0.85)
        self.assertIn("category_scores", result)
        self.assertIn("completeness", result["category_scores"])
        self.assertIn("accuracy", result["category_scores"])
        self.assertEqual(result["category_scores"]["completeness"], 100.0)  # 2/2 passed
        self.assertEqual(result["category_scores"]["accuracy"], 50.0)  # 1/2 passed

    @patch('hub.apps.orchestration.workflows.data_quality.AnomalyDetector')
    def test_detect_anomalies_task(self, mock_detector_class):
        """Test detecting anomalies"""
        mock_detector = MagicMock()
        anomaly = DQAnomaly(
            id="anomaly-123",
            tenant=self.tenant,
            asset=self.asset,
            metric_type="quality_score",
            actual_value=0.75,
            expected_value=0.90,
            deviation=0.15,
            severity=DQAnomalySeverity.HIGH,
            anomaly_type="sudden_drop"
        )
        mock_detector.detect_anomalies.return_value = [anomaly]
        mock_detector_class.return_value = mock_detector
        
        # Create DQ run
        from hub.apps.jobs.utils import create_job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(self.asset.id)
        )
        
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            quality_score=0.75
        )
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=DataQualityCheckWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["dq_run_id"] = str(dq_run.id)
        instance.state_data["overall_score"] = 0.75
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=4,
            step_name="detect_anomalies",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = DataQualityCheckWorkflow._detect_anomalies_task(
            input_data, instance, step
        )
        
        self.assertIn("anomalies", result)
        self.assertEqual(result["anomalies_count"], 1)
        self.assertEqual(result["anomalies"][0]["metric_type"], "quality_score")
        self.assertEqual(result["anomalies"][0]["severity"], DQAnomalySeverity.HIGH)

    @patch('hub.apps.orchestration.workflows.data_quality.DQAlertingService')
    def test_generate_alerts_task(self, mock_alerting_class):
        """Test generating alerts"""
        mock_alerting_service = MagicMock()
        mock_alerting_service.evaluate_rules.return_value = [
            {
                "rule_id": "rule-123",
                "rule_name": "Low Quality Score",
                "severity": "HIGH",
                "metric_type": "quality_score",
                "metric_value": 0.75,
                "threshold": 0.80,
                "comparison_operator": "<",
                "dq_run_id": "dq-run-123",
                "triggered_at": timezone.now().isoformat(),
                "message": "Low Quality Score alert"
            }
        ]
        mock_alerting_class.return_value = mock_alerting_service
        
        # Create DQ run
        from hub.apps.jobs.utils import create_job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(self.asset.id)
        )
        
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            quality_score=0.75
        )
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=DataQualityCheckWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["dq_run_id"] = str(dq_run.id)
        instance.state_data["overall_score"] = 0.75
        instance.state_data["anomalies"] = [
            {"id": "anomaly-123", "metric_type": "quality_score", "severity": "HIGH"}
        ]
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=5,
            step_name="generate_alerts",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = DataQualityCheckWorkflow._generate_alerts_task(
            input_data, instance, step
        )
        
        self.assertIn("alerts_generated", result)
        self.assertGreater(result["alerts_count"], 0)
        self.assertTrue(result["has_alerts"])

    @patch('hub.apps.orchestration.workflows.data_quality.DQScorecardService')
    def test_update_quality_metrics_task(self, mock_scorecard_class):
        """Test updating quality metrics"""
        mock_scorecard_service = MagicMock()
        mock_scorecard_service.get_asset_scorecard.return_value = {
            "asset_id": str(self.asset.id),
            "metrics": {"avg_quality_score": 0.85}
        }
        mock_scorecard_class.return_value = mock_scorecard_service
        
        # Create DQ run
        from hub.apps.jobs.utils import create_job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(self.asset.id)
        )
        
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.RUNNING,
            quality_score=0.85
        )
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=DataQualityCheckWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        instance.state_data["dq_run_id"] = str(dq_run.id)
        instance.state_data["overall_score"] = 0.85
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=6,
            step_name="update_quality_metrics",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = DataQualityCheckWorkflow._update_quality_metrics_task(
            input_data, instance, step
        )
        
        self.assertTrue(result["scorecard_available"])
        self.assertEqual(result["quality_score"], 0.85)


class DataQualityCheckWorkflowIntegrationTest(TestCase):
    """Integration tests for data quality check workflow"""

    def setUp(self):
        """Set up test fixtures"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant Integration {unique_id}",
            slug=f"test-tenant-integration-{unique_id}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-integration-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User"
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            description="A test asset",
            created_by=self.user
        )
        
        self.file_obj = FileModel.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path="test/test.csv",
            size=1024,
            content_type="text/csv",
            status="ACTIVE"
        )
        
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file_obj,
            is_current=True,
            created_by=self.user,
            format="CSV"
        )
        
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            status="ACTIVE"
        )
        self.contract.asset = self.asset
        self.contract.save()

    @patch('hub.apps.orchestration.workflows.data_quality.DQServiceClient')
    @patch('hub.apps.orchestration.workflows.data_quality.S3StorageClient')
    @patch('hub.apps.orchestration.workflows.data_quality.AnomalyDetector')
    @patch('hub.apps.orchestration.workflows.data_quality.DQAlertingService')
    @patch('hub.apps.orchestration.workflows.data_quality.DQScorecardService')
    @patch('hub.apps.orchestration.workflows.data_quality.create_audit_event')
    def test_full_workflow_execution_success(self, mock_audit, mock_scorecard, mock_alerting, mock_detector, mock_storage, mock_dq_client):
        """Test full workflow execution end-to-end"""
        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.get_file_content.return_value = b"test,data\n1,2"
        mock_storage.return_value = mock_storage_client
        
        mock_dq_client_instance = MagicMock()
        mock_dq_client_instance.health_check.return_value = (True, "dq-service")
        mock_dq_client_instance.run_dq.return_value = {
            "overall_status": "PASS",
            "quality_score": 0.95,
            "checks": [
                {"check_id": "check1", "status": "PASS", "category": "completeness"},
                {"check_id": "check2", "status": "PASS", "category": "accuracy"}
            ],
            "engine_type": "GREAT_EXPECTATIONS",
            "engine_version": "0.18.0",
            "profile_key": "intake_basic_gx",
            "metadata": {"total_rows": 100, "total_columns": 2}
        }
        mock_dq_client.return_value = mock_dq_client_instance
        
        mock_detector_instance = MagicMock()
        mock_detector_instance.detect_anomalies.return_value = []
        mock_detector.return_value = mock_detector_instance
        
        mock_alerting_instance = MagicMock()
        mock_alerting_instance.evaluate_rules.return_value = []
        mock_alerting.return_value = mock_alerting_instance
        
        mock_scorecard_instance = MagicMock()
        mock_scorecard_instance.get_asset_scorecard.return_value = {
            "asset_id": str(self.asset.id),
            "metrics": {"avg_quality_score": 0.95}
        }
        mock_scorecard.return_value = mock_scorecard_instance
        
        mock_audit.return_value = MagicMock(id="audit-123")
        
        # Execute workflow
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        DataQualityCheckWorkflow.register_workflow(registry)
        DataQualityCheckWorkflow.register_tasks(engine)
        
        result = DataQualityCheckWorkflow.execute(
            tenant_id=str(self.tenant.id),
            asset_id=str(self.asset.id),
            profile_key="intake_basic_gx",
            triggered_by_id=str(self.user.id),
            engine=engine,
            registry=registry
        )
        
        # Verify workflow completed successfully
        self.assertTrue(result["success"])
        self.assertIn("workflow_instance_id", result)
        self.assertIn("output_data", result)
        
        # Get workflow instance to access state_data
        workflow_instance_id = result["workflow_instance_id"]
        from hub.apps.orchestration.models import WorkflowInstance
        workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
        
        # Verify DQ run was created (stored in state_data during workflow execution)
        dq_run_id = workflow_instance.state_data.get("dq_run_id")
        self.assertIsNotNone(dq_run_id)
        
        dq_run = DQRun.objects.get(id=dq_run_id)
        self.assertEqual(dq_run.tenant, self.tenant)
        self.assertEqual(dq_run.asset, self.asset)
        self.assertEqual(dq_run.status, DQRunStatus.SUCCEEDED)
        self.assertEqual(dq_run.overall_status, "PASS")
        self.assertEqual(dq_run.quality_score, 0.95)
        
        # Verify asset DQ status was updated
        self.asset.refresh_from_db()
        from hub.apps.assets.models import DQStatus as AssetDQStatus
        self.assertEqual(self.asset.dq_status, AssetDQStatus.PASS)
        
        # Verify audit log was created
        mock_audit.assert_called()

    @patch('hub.apps.orchestration.workflows.data_quality.DQServiceClient')
    @patch('hub.apps.orchestration.workflows.data_quality.S3StorageClient')
    def test_workflow_execution_with_dq_service_unavailable(self, mock_storage, mock_dq_client):
        """Test workflow execution when DQ service is unavailable"""
        mock_storage_client = MagicMock()
        mock_storage_client.get_file_content.return_value = b"test,data\n1,2"
        mock_storage.return_value = mock_storage_client
        
        mock_dq_client_instance = MagicMock()
        mock_dq_client_instance.health_check.return_value = (False, "dq-service")
        mock_dq_client.return_value = mock_dq_client_instance
        
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        DataQualityCheckWorkflow.register_workflow(registry)
        DataQualityCheckWorkflow.register_tasks(engine)
        
        with self.assertRaises(ValueError) as context:
            DataQualityCheckWorkflow.execute(
                tenant_id=str(self.tenant.id),
                asset_id=str(self.asset.id),
                profile_key="intake_basic_gx",
                triggered_by_id=str(self.user.id),
                engine=engine,
                registry=registry
            )
        
        self.assertIn("DQ service is unavailable", str(context.exception))

    @patch('hub.apps.orchestration.workflows.data_quality.DQServiceClient')
    @patch('hub.apps.orchestration.workflows.data_quality.S3StorageClient')
    @patch('hub.apps.orchestration.workflows.data_quality.AnomalyDetector')
    @patch('hub.apps.orchestration.workflows.data_quality.DQAlertingService')
    @patch('hub.apps.orchestration.workflows.data_quality.DQScorecardService')
    @patch('hub.apps.orchestration.workflows.data_quality.create_audit_event')
    def test_workflow_execution_with_dataset(self, mock_audit, mock_scorecard, mock_alerting, mock_detector, mock_storage, mock_dq_client):
        """Test workflow execution with dataset specified"""
        mock_storage_client = MagicMock()
        mock_storage_client.get_file_content.return_value = b"test,data\n1,2"
        mock_storage.return_value = mock_storage_client
        
        mock_dq_client_instance = MagicMock()
        mock_dq_client_instance.health_check.return_value = (True, "dq-service")
        mock_dq_client_instance.run_dq.return_value = {
            "overall_status": "PASS",
            "quality_score": 0.90,
            "checks": [],
            "engine_type": "GREAT_EXPECTATIONS",
            "engine_version": "0.18.0",
            "profile_key": "intake_basic_gx",
            "metadata": {}
        }
        mock_dq_client.return_value = mock_dq_client_instance
        
        mock_detector_instance = MagicMock()
        mock_detector_instance.detect_anomalies.return_value = []
        mock_detector.return_value = mock_detector_instance
        
        mock_alerting_instance = MagicMock()
        mock_alerting_instance.evaluate_rules.return_value = []
        mock_alerting.return_value = mock_alerting_instance
        
        mock_scorecard_instance = MagicMock()
        mock_scorecard_instance.get_asset_scorecard.return_value = None
        mock_scorecard.return_value = mock_scorecard_instance
        
        mock_audit.return_value = MagicMock(id="audit-123")
        
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        DataQualityCheckWorkflow.register_workflow(registry)
        DataQualityCheckWorkflow.register_tasks(engine)
        
        result = DataQualityCheckWorkflow.execute(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.dataset.id),
            profile_key="intake_basic_gx",
            triggered_by_id=str(self.user.id),
            engine=engine,
            registry=registry
        )
        
        self.assertTrue(result["success"])
        
        # Get workflow instance to access state_data
        workflow_instance_id = result["workflow_instance_id"]
        from hub.apps.orchestration.models import WorkflowInstance
        workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
        
        dq_run_id = workflow_instance.state_data.get("dq_run_id")
        self.assertIsNotNone(dq_run_id)
        dq_run = DQRun.objects.get(id=dq_run_id)
        self.assertEqual(dq_run.dataset, self.dataset)

    def test_workflow_execution_with_invalid_tenant(self):
        """Test workflow execution with invalid tenant_id"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        DataQualityCheckWorkflow.register_workflow(registry)
        DataQualityCheckWorkflow.register_tasks(engine)
        
        with self.assertRaises(Exception):
            DataQualityCheckWorkflow.execute(
                tenant_id="00000000-0000-0000-0000-000000000000",  # Invalid UUID
                asset_id=str(self.asset.id),
                profile_key="intake_basic_gx",
                triggered_by_id=str(self.user.id),
                engine=engine,
                registry=registry
            )


class DataQualityCheckWorkflowE2ETest(TestCase):
    """End-to-end tests for data quality check workflow via API"""
    
    def setUp(self):
        """Set up test fixtures"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant E2E {unique_id}",
            slug=f"test-tenant-e2e-{unique_id}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-e2e-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User"
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            description="A test asset",
            created_by=self.user
        )
        
        self.file_obj = FileModel.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path="test/test.csv",
            size=1024,
            content_type="text/csv",
            status="ACTIVE"
        )
        
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file_obj,
            is_current=True,
            created_by=self.user,
            format="CSV"
        )

    @patch('hub.apps.orchestration.workflows.data_quality.DQServiceClient')
    @patch('hub.apps.orchestration.workflows.data_quality.S3StorageClient')
    @patch('hub.apps.orchestration.workflows.data_quality.AnomalyDetector')
    @patch('hub.apps.orchestration.workflows.data_quality.DQAlertingService')
    @patch('hub.apps.orchestration.workflows.data_quality.DQScorecardService')
    @patch('hub.apps.orchestration.workflows.data_quality.create_audit_event')
    def test_dq_run_creation_via_workflow(self, mock_audit, mock_scorecard, mock_alerting, mock_detector, mock_storage, mock_dq_client):
        """
        Test creating DQ run via workflow execution.
        
        This simulates the E2E flow where a user triggers a DQ check
        and the workflow orchestrates the entire process.
        """
        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.get_file_content.return_value = b"test,data\n1,2"
        mock_storage.return_value = mock_storage_client
        
        mock_dq_client_instance = MagicMock()
        mock_dq_client_instance.health_check.return_value = (True, "dq-service")
        mock_dq_client_instance.run_dq.return_value = {
            "overall_status": "PASS",
            "quality_score": 0.92,
            "checks": [
                {"check_id": "check1", "status": "PASS", "category": "completeness"},
                {"check_id": "check2", "status": "PASS", "category": "accuracy"},
                {"check_id": "check3", "status": "PASS", "category": "validity"}
            ],
            "engine_type": "GREAT_EXPECTATIONS",
            "engine_version": "0.18.0",
            "profile_key": "intake_basic_gx",
            "metadata": {"total_rows": 1000, "total_columns": 5}
        }
        mock_dq_client.return_value = mock_dq_client_instance
        
        mock_detector_instance = MagicMock()
        mock_detector_instance.detect_anomalies.return_value = []
        mock_detector.return_value = mock_detector_instance
        
        mock_alerting_instance = MagicMock()
        mock_alerting_instance.evaluate_rules.return_value = []
        mock_alerting.return_value = mock_alerting_instance
        
        mock_scorecard_instance = MagicMock()
        mock_scorecard_instance.get_asset_scorecard.return_value = {
            "asset_id": str(self.asset.id),
            "metrics": {"avg_quality_score": 0.92}
        }
        mock_scorecard.return_value = mock_scorecard_instance
        
        mock_audit.return_value = MagicMock(id="audit-123")
        
        # Execute workflow
        result = DataQualityCheckWorkflow.execute(
            tenant_id=str(self.tenant.id),
            asset_id=str(self.asset.id),
            profile_key="intake_basic_gx",
            triggered_by_id=str(self.user.id)
        )
        
        # Verify complete workflow execution
        self.assertTrue(result["success"])
        self.assertIn("workflow_instance_id", result)
        
        # Get workflow instance to access state_data
        workflow_instance_id = result["workflow_instance_id"]
        from hub.apps.orchestration.models import WorkflowInstance
        workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
        
        # Verify DQ run exists and is complete (stored in state_data during workflow execution)
        dq_run_id = workflow_instance.state_data.get("dq_run_id")
        self.assertIsNotNone(dq_run_id)
        dq_run = DQRun.objects.get(id=dq_run_id)
        
        self.assertEqual(dq_run.status, DQRunStatus.SUCCEEDED)
        self.assertEqual(dq_run.overall_status, "PASS")
        self.assertEqual(dq_run.quality_score, 0.92)
        self.assertIsNotNone(dq_run.completed_at)
        self.assertIsNotNone(dq_run.started_at)
        
        # Verify all workflow steps completed
        workflow_instance_id = result["workflow_instance_id"]
        from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
        workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)
        
        # Verify asset status updated
        self.asset.refresh_from_db()
        from hub.apps.assets.models import DQStatus as AssetDQStatus
        self.assertEqual(self.asset.dq_status, AssetDQStatus.PASS)

