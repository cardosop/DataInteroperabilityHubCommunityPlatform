"""
Data Quality Check Workflow

Orchestrates data quality check execution, including:
- Loading contract and dataset
- Executing quality rules
- Calculating quality scores
- Detecting anomalies
- Generating alerts
- Updating quality metrics
- Storing results
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction
import structlog

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.dq.models import (
    DQRun, DQRunStatus, DQEngine, DQAnomaly, DQAnomalySeverity,
    DQAlertingRule, DQAlertChannel
)
from hub.apps.dq.service_client import DQServiceClient
from hub.apps.dq.contract_integration import ContractQualityRulesExtractor
from hub.apps.dq.anomaly_detection import AnomalyDetector
from hub.apps.dq.alerting import DQAlertingService
from hub.apps.dq.scorecards import DQScorecardService
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.models import File as FileModel
from hub.apps.contracts.models import Contract
from hub.apps.datasets.models import Dataset
from hub.apps.assets.models import Asset, DQStatus as AssetDQStatus
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.utils import create_job, get_job_timeout
from hub.apps.audit.utils import create_audit_event
from hub.apps.notifications.models import EmailType
from hub.apps.notifications.tasks import send_email_async

logger = structlog.get_logger(__name__)


class DataQualityCheckWorkflow:
    """
    Data quality check workflow orchestrator.
    
    Orchestrates the complete data quality check process:
    1. Trigger DQ check (scheduled/manual)
    2. Load contract and dataset
    3. Execute quality rules
    4. Calculate quality scores
    5. Detect anomalies
    6. Generate alerts (if thresholds exceeded)
    7. Update quality metrics
    8. Store results
    """
    
    WORKFLOW_NAME = "data_quality_check"
    
    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the data quality check workflow definition.
        
        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": "1.0.0",
            "dependencies": [],
            "steps": [
                {
                    "name": "create_dq_run",
                    "type": "task",
                    "task": "data_quality.create_dq_run"
                },
                {
                    "name": "load_contract_and_dataset",
                    "type": "task",
                    "task": "data_quality.load_contract_and_dataset"
                },
                {
                    "name": "execute_quality_rules",
                    "type": "task",
                    "task": "data_quality.execute_quality_rules"
                },
                {
                    "name": "calculate_quality_scores",
                    "type": "task",
                    "task": "data_quality.calculate_quality_scores"
                },
                {
                    "name": "detect_anomalies",
                    "type": "task",
                    "task": "data_quality.detect_anomalies"
                },
                {
                    "name": "generate_alerts",
                    "type": "task",
                    "task": "data_quality.generate_alerts"
                },
                {
                    "name": "update_quality_metrics",
                    "type": "task",
                    "task": "data_quality.update_quality_metrics"
                },
                {
                    "name": "store_results",
                    "type": "task",
                    "task": "data_quality.store_results"
                },
                {
                    "name": "audit_logging",
                    "type": "task",
                    "task": "data_quality.audit_logging"
                }
            ],
            "compensation": {"enabled": True}
        }
        registry.register_workflow(
            cls.WORKFLOW_NAME,
            workflow_dsl
        )
    
    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow task functions.
        
        Args:
            engine: WorkflowEngine instance
        """
        engine.register_task(
            "data_quality.create_dq_run",
            cls._create_dq_run_task
        )
        engine.register_task(
            "data_quality.load_contract_and_dataset",
            cls._load_contract_and_dataset_task
        )
        engine.register_task(
            "data_quality.execute_quality_rules",
            cls._execute_quality_rules_task
        )
        engine.register_task(
            "data_quality.calculate_quality_scores",
            cls._calculate_quality_scores_task
        )
        engine.register_task(
            "data_quality.detect_anomalies",
            cls._detect_anomalies_task
        )
        engine.register_task(
            "data_quality.generate_alerts",
            cls._generate_alerts_task
        )
        engine.register_task(
            "data_quality.update_quality_metrics",
            cls._update_quality_metrics_task
        )
        engine.register_task(
            "data_quality.store_results",
            cls._store_results_task
        )
        engine.register_task(
            "data_quality.audit_logging",
            cls._audit_logging_task
        )
    
    @staticmethod
    def _create_dq_run_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create DQ run record.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with dq_run_id
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        asset_id = input_data.get("asset_id")
        dataset_id = input_data.get("dataset_id")
        file_id = input_data.get("file_id")
        profile_key = input_data.get("profile_key", "intake_basic_gx")
        triggered_by_id = input_data.get("triggered_by_id") or instance.created_by_id
        
        if not tenant_id:
            raise ValueError("tenant_id is required")
        
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User
        
        tenant = Tenant.objects.get(id=tenant_id)
        triggered_by = User.objects.get(id=triggered_by_id) if triggered_by_id else None
        
        # Resolve resources
        asset = None
        dataset = None
        file_obj = None
        
        if asset_id:
            asset = Asset.objects.get(id=asset_id, tenant=tenant)
        if dataset_id:
            dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)
            if asset and dataset.asset != asset:
                raise ValueError("Dataset does not belong to the specified asset")
            if not asset and dataset.asset:
                asset = dataset.asset
        if file_id:
            file_obj = FileModel.objects.get(id=file_id, tenant=tenant)
        
        # Determine engine from profile key
        if profile_key.endswith('_gx') or 'gx' in profile_key.lower():
            engine = DQEngine.GREAT_EXPECTATIONS
        elif profile_key.endswith('_soda') or 'soda' in profile_key.lower():
            engine = DQEngine.SODA
        else:
            engine = DQEngine.GREAT_EXPECTATIONS
        
        # Create job
        job = create_job(
            tenant=tenant,
            user=triggered_by,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(instance.id),  # Temporary, will be updated
            details_json={},
            timeout_seconds=get_job_timeout(JobType.DQ_RUN)
        )
        
        # Create DQ run
        dq_run = DQRun.objects.create(
            tenant=tenant,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            job=job,
            profile_key=profile_key,
            engine=engine,
            status=DQRunStatus.PENDING
        )
        
        # Update job with dq_run_id
        job.resource_id = str(dq_run.id)
        job.details_json['dq_run_id'] = str(dq_run.id)
        job.save(update_fields=['resource_id', 'details_json'])
        
        logger.info(
            "DQ run created",
            workflow_instance_id=str(instance.id),
            dq_run_id=str(dq_run.id),
            profile_key=profile_key,
            engine=engine
        )
        
        return {
            "dq_run_id": str(dq_run.id),
            "job_id": str(job.id),
            "profile_key": profile_key,
            "engine": engine,
            "state": {
                "dq_run_id": str(dq_run.id),
                "job_id": str(job.id),
                "asset_id": str(asset.id) if asset else None,
                "dataset_id": str(dataset.id) if dataset else None,
                "file_id": str(file_obj.id) if file_obj else None
            }
        }
    
    @staticmethod
    def _load_contract_and_dataset_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Load contract and dataset for DQ check.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with contract and dataset info
        """
        dq_run_id = instance.state_data.get("dq_run_id")
        
        if not dq_run_id:
            raise ValueError("dq_run_id is required")
        
        dq_run = DQRun.objects.get(id=dq_run_id)
        
        # Load contract
        contract = None
        if dq_run.asset:
            contract = dq_run.asset.contracts.filter(status="ACTIVE").first()
        elif dq_run.dataset and dq_run.dataset.asset:
            contract = dq_run.dataset.asset.contracts.filter(status="ACTIVE").first()
        
        # Load dataset/file
        dataset = dq_run.dataset
        file_obj = None
        
        if dataset and dataset.file:
            file_obj = dataset.file
        elif dq_run.file:
            file_obj = dq_run.file
        elif dq_run.asset:
            # Get latest dataset for asset
            latest_dataset = dq_run.asset.datasets.order_by('-version').first()
            if latest_dataset and latest_dataset.file:
                dataset = latest_dataset
                file_obj = latest_dataset.file
        
        if not file_obj:
            raise ValueError("No file found for DQ check")
        
        # Download file content
        storage_client = S3StorageClient()
        file_content = storage_client.get_file_content(file_obj.storage_path)
        file_format = file_obj.name.split('.')[-1].lower() if '.' in file_obj.name else 'csv'
        
        logger.info(
            "Contract and dataset loaded",
            workflow_instance_id=str(instance.id),
            dq_run_id=str(dq_run.id),
            contract_id=str(contract.id) if contract else None,
            dataset_id=str(dataset.id) if dataset else None,
            file_id=str(file_obj.id),
            file_format=file_format
        )
        
        return {
            "contract_id": str(contract.id) if contract else None,
            "dataset_id": str(dataset.id) if dataset else None,
            "file_id": str(file_obj.id),
            "file_format": file_format,
            "file_size_bytes": len(file_content),
            "state": {
                "contract_id": str(contract.id) if contract else None,
                "dataset_id": str(dataset.id) if dataset else None,
                "file_id": str(file_obj.id),
                "file_format": file_format,
                "file_content_size": len(file_content)
            }
        }
    
    @staticmethod
    def _execute_quality_rules_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Execute quality rules on dataset.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with DQ results
        """
        dq_run_id = instance.state_data.get("dq_run_id")
        contract_id = instance.state_data.get("contract_id")
        file_format = instance.state_data.get("file_format")
        file_content_size = instance.state_data.get("file_content_size")
        
        if not dq_run_id:
            raise ValueError("dq_run_id is required")
        
        dq_run = DQRun.objects.get(id=dq_run_id)
        
        # Get file content (stored in state or re-download)
        file_obj = None
        if dq_run.file:
            file_obj = dq_run.file
        elif dq_run.dataset and dq_run.dataset.file:
            file_obj = dq_run.dataset.file
        elif dq_run.asset:
            latest_dataset = dq_run.asset.datasets.order_by('-version').first()
            if latest_dataset and latest_dataset.file:
                file_obj = latest_dataset.file
        
        if not file_obj:
            raise ValueError("No file found for DQ check")
        
        # Download file content
        storage_client = S3StorageClient()
        file_content = storage_client.get_file_content(file_obj.storage_path)
        
        # Get contract if available
        contract = None
        if contract_id:
            contract = Contract.objects.get(id=contract_id)
        elif dq_run.asset:
            contract = dq_run.asset.contracts.filter(status="ACTIVE").first()
        
        # Initialize DQ client
        dq_client = DQServiceClient()
        
        # Check DQ service health
        is_healthy, _ = dq_client.health_check()
        if not is_healthy:
            raise ValueError("DQ service is unavailable")
        
        # Update DQ run status
        dq_run.status = DQRunStatus.RUNNING
        dq_run.started_at = timezone.now()
        dq_run.save(update_fields=['status', 'started_at'])
        
        # Run DQ check
        dq_result = dq_client.run_dq(
            file_content=file_content,
            file_format=file_format.lower(),
            profile_key=dq_run.profile_key,
            contract=contract
        )
        
        logger.info(
            "Quality rules executed",
            workflow_instance_id=str(instance.id),
            dq_run_id=str(dq_run.id),
            overall_status=dq_result.get("overall_status"),
            quality_score=dq_result.get("quality_score"),
            checks_count=len(dq_result.get("checks", []))
        )
        
        return {
            "dq_result": dq_result,
            "overall_status": dq_result.get("overall_status"),
            "quality_score": dq_result.get("quality_score", 0.0),
            "checks": dq_result.get("checks", []),
            "engine_type": dq_result.get("engine_type"),
            "engine_version": dq_result.get("engine_version"),
            "state": {
                "dq_result": dq_result,
                "overall_status": dq_result.get("overall_status"),
                "quality_score": dq_result.get("quality_score", 0.0),
                "checks": dq_result.get("checks", [])
            }
        }
    
    @staticmethod
    def _calculate_quality_scores_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Calculate quality scores from DQ results.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with calculated scores
        """
        dq_result = instance.state_data.get("dq_result", {})
        quality_score = dq_result.get("quality_score", 0.0)
        checks = dq_result.get("checks", [])
        
        # Calculate category-specific scores
        category_scores = {}
        category_counts = {}
        
        for check in checks:
            category = check.get("category", "unknown")
            status = check.get("status", "").upper()
            
            if category not in category_scores:
                category_scores[category] = {"passed": 0, "total": 0}
                category_counts[category] = 0
            
            category_counts[category] += 1
            if status in ["PASS", "SUCCESS"]:
                category_scores[category]["passed"] += 1
            category_scores[category]["total"] += 1
        
        # Calculate percentage scores per category
        category_percentages = {}
        for category, counts in category_scores.items():
            if counts["total"] > 0:
                category_percentages[category] = (counts["passed"] / counts["total"]) * 100
            else:
                category_percentages[category] = 100.0
        
        logger.info(
            "Quality scores calculated",
            workflow_instance_id=str(instance.id),
            overall_score=quality_score,
            category_scores=category_percentages
        )
        
        return {
            "overall_score": quality_score,
            "category_scores": category_percentages,
            "category_counts": category_counts,
            "state": {
                "overall_score": quality_score,
                "category_scores": category_percentages,
                "category_counts": category_counts
            }
        }
    
    @staticmethod
    def _detect_anomalies_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Detect anomalies in quality metrics.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with detected anomalies
        """
        dq_run_id = instance.state_data.get("dq_run_id")
        quality_score = instance.state_data.get("overall_score", 0.0)
        
        if not dq_run_id:
            raise ValueError("dq_run_id is required")
        
        dq_run = DQRun.objects.get(id=dq_run_id)
        
        # Initialize anomaly detector
        anomaly_detector = AnomalyDetector()
        
        # Detect anomalies
        anomalies = anomaly_detector.detect_anomalies(
            dq_run=dq_run,
            metric_type="quality_score"
        )
        
        logger.info(
            "Anomalies detected",
            workflow_instance_id=str(instance.id),
            dq_run_id=str(dq_run.id),
            anomalies_count=len(anomalies)
        )
        
        return {
            "anomalies": [
                {
                    "id": str(anomaly.id),
                    "metric_type": anomaly.metric_type,
                    "severity": anomaly.severity,
                    "anomaly_type": anomaly.anomaly_type,
                    "actual_value": anomaly.actual_value,
                    "expected_value": anomaly.expected_value,
                    "deviation": anomaly.deviation
                }
                for anomaly in anomalies
            ],
            "anomalies_count": len(anomalies),
            "state": {
                "anomalies": [
                    {
                        "id": str(anomaly.id),
                        "metric_type": anomaly.metric_type,
                        "severity": anomaly.severity
                    }
                    for anomaly in anomalies
                ],
                "anomalies_count": len(anomalies)
            }
        }
    
    @staticmethod
    def _generate_alerts_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Generate alerts if thresholds exceeded.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with alert details
        """
        dq_run_id = instance.state_data.get("dq_run_id")
        quality_score = instance.state_data.get("overall_score", 0.0)
        anomalies = instance.state_data.get("anomalies", [])
        
        if not dq_run_id:
            raise ValueError("dq_run_id is required")
        
        dq_run = DQRun.objects.get(id=dq_run_id)
        
        # Initialize alerting service
        alerting_service = DQAlertingService()
        
        # Evaluate rules and generate alerts
        alerts_generated = []
        
        # Evaluate quality_score alerts
        quality_score_alerts = alerting_service.evaluate_rules(
            dq_run=dq_run,
            metric_type="quality_score"
        )
        alerts_generated.extend(quality_score_alerts)
        
        # Evaluate alerts for other metric types from anomalies
        anomaly_metric_types = set(a.get("metric_type") for a in anomalies)
        for metric_type in anomaly_metric_types:
            if metric_type != "quality_score":
                metric_alerts = alerting_service.evaluate_rules(
                    dq_run=dq_run,
                    metric_type=metric_type
                )
                alerts_generated.extend(metric_alerts)
        
        logger.info(
            "Alerts generated",
            workflow_instance_id=str(instance.id),
            dq_run_id=str(dq_run.id),
            alerts_count=len(alerts_generated)
        )
        
        return {
            "alerts_generated": alerts_generated,
            "alerts_count": len(alerts_generated),
            "has_alerts": len(alerts_generated) > 0,
            "state": {
                "alerts_generated": alerts_generated,
                "alerts_count": len(alerts_generated),
                "has_alerts": len(alerts_generated) > 0
            }
        }
    
    @staticmethod
    def _update_quality_metrics_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Update quality metrics (scorecards, trends).
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with updated metrics
        """
        dq_run_id = instance.state_data.get("dq_run_id")
        quality_score = instance.state_data.get("overall_score", 0.0)
        
        if not dq_run_id:
            raise ValueError("dq_run_id is required")
        
        dq_run = DQRun.objects.get(id=dq_run_id)
        
        # Scorecard is automatically updated when DQ run is stored
        # The scorecard service reads from DQ runs, so no explicit update needed
        # We can verify scorecard data is available
        scorecard_service = DQScorecardService()
        
        if dq_run.asset:
            scorecard_data = scorecard_service.get_asset_scorecard(
                asset_id=str(dq_run.asset.id),
                tenant_id=str(dq_run.tenant.id),
                days=30
            )
        else:
            scorecard_data = None
        
        logger.info(
            "Quality metrics updated",
            workflow_instance_id=str(instance.id),
            dq_run_id=str(dq_run.id),
            quality_score=quality_score
        )
        
        return {
            "scorecard_available": scorecard_data is not None,
            "quality_score": quality_score,
            "state": {
                "scorecard_available": scorecard_data is not None,
                "quality_score": quality_score
            }
        }
    
    @staticmethod
    def _store_results_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Store DQ results in database.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with stored results
        """
        dq_run_id = instance.state_data.get("dq_run_id")
        dq_result = instance.state_data.get("dq_result", {})
        quality_score = instance.state_data.get("overall_score", 0.0)
        
        if not dq_run_id:
            raise ValueError("dq_run_id is required")
        
        dq_run = DQRun.objects.get(id=dq_run_id)
        
        # Calculate execution time
        execution_time = 0.0
        if dq_run.started_at:
            execution_time = (timezone.now() - dq_run.started_at).total_seconds()
        
        # Get metadata
        metadata = dq_result.get("metadata", {})
        row_count = metadata.get("total_rows", 0)
        column_count = metadata.get("total_columns", 0)
        
        # Update DQ run with results
        dq_run.status = DQRunStatus.SUCCEEDED
        dq_run.overall_status = dq_result.get("overall_status")
        dq_run.quality_score = quality_score
        dq_run.checks_json = dq_result.get("checks", [])
        dq_run.details_json = {
            "engine_type": dq_result.get("engine_type"),
            "engine_version": dq_result.get("engine_version"),
            "profile_key": dq_result.get("profile_key"),
            "metadata": metadata,
            "metering": {
                "operation_type": "DQ_RUN",
                "rows_inspected": row_count,
                "columns_inspected": column_count,
                "execution_time_seconds": round(execution_time, 2),
                "engine_type": dq_result.get("engine_type"),
                "profile_key": dq_result.get("profile_key"),
                "quality_score": quality_score,
                "checks_count": len(dq_result.get("checks", []))
            }
        }
        dq_run.completed_at = timezone.now()
        dq_run.save(update_fields=[
            'status', 'overall_status', 'quality_score', 'checks_json',
            'details_json', 'completed_at'
        ])
        
        # Update asset DQ status if applicable
        if dq_run.asset:
            if dq_run.overall_status == 'PASS':
                dq_status = AssetDQStatus.PASS
            elif dq_run.overall_status == 'WARN':
                dq_status = AssetDQStatus.WARN
            elif dq_run.overall_status == 'FAIL':
                dq_status = AssetDQStatus.FAIL
            else:
                dq_status = AssetDQStatus.UNKNOWN
            
            dq_run.asset.dq_status = dq_status
            dq_run.asset.save(update_fields=['dq_status'])
        
        logger.info(
            "DQ results stored",
            workflow_instance_id=str(instance.id),
            dq_run_id=str(dq_run.id),
            overall_status=dq_run.overall_status,
            quality_score=quality_score
        )
        
        return {
            "dq_run_id": str(dq_run.id),
            "overall_status": dq_run.overall_status,
            "quality_score": quality_score,
            "execution_time_seconds": execution_time,
            "state": {
                "dq_run_id": str(dq_run.id),
                "overall_status": dq_run.overall_status,
                "quality_score": quality_score
            }
        }
    
    @staticmethod
    def _audit_logging_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create audit log entry for DQ check.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with audit event ID
        """
        dq_run_id = instance.state_data.get("dq_run_id")
        quality_score = instance.state_data.get("overall_score", 0.0)
        overall_status = instance.state_data.get("overall_status")
        
        if not dq_run_id:
            raise ValueError("dq_run_id is required")
        
        dq_run = DQRun.objects.get(id=dq_run_id)
        
        # Create audit event
        audit_event = create_audit_event(
            resource_type="DQ_RUN",
            action="DQ_RUN_COMPLETED",
            actor_user=None,  # System-initiated
            tenant=dq_run.tenant,
            resource_id=str(dq_run.id),
            details={
                "profile_key": dq_run.profile_key,
                "engine": dq_run.engine,
                "overall_status": overall_status,
                "quality_score": quality_score,
                "asset_id": str(dq_run.asset.id) if dq_run.asset else None,
                "dataset_id": str(dq_run.dataset.id) if dq_run.dataset else None,
                "file_id": str(dq_run.file.id) if dq_run.file else None
            }
        )
        
        logger.info(
            "Audit log created",
            workflow_instance_id=str(instance.id),
            dq_run_id=str(dq_run.id),
            audit_event_id=str(audit_event.id) if audit_event else None
        )
        
        return {
            "audit_event_id": str(audit_event.id) if audit_event else None,
            "state": {
                "audit_event_id": str(audit_event.id) if audit_event else None
            }
        }
    
    @classmethod
    @transaction.atomic
    def execute(
        cls,
        tenant_id: str,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        profile_key: str = "intake_basic_gx",
        triggered_by_id: Optional[str] = None,
        engine: Optional[WorkflowEngine] = None,
        registry: Optional[WorkflowRegistry] = None
    ) -> Dict[str, Any]:
        """
        Execute data quality check workflow.
        
        Args:
            tenant_id: Tenant ID
            asset_id: Optional asset ID
            dataset_id: Optional dataset ID
            file_id: Optional file ID
            profile_key: DQ profile key
            triggered_by_id: User ID who triggered the check
            engine: Optional WorkflowEngine instance
            registry: Optional WorkflowRegistry instance
            
        Returns:
            Workflow execution result dictionary
            
        Raises:
            ValueError: If workflow execution fails
        """
        # Check DQ service availability before starting workflow
        dq_client = DQServiceClient()
        is_healthy, error_msg = dq_client.health_check()
        if not is_healthy:
            logger.warning(
                "DQ service is unavailable, workflow will fail",
                extra={
                    'error': error_msg,
                    'tenant_id': tenant_id,
                    'asset_id': asset_id
                }
            )
            raise ValueError(f"DQ service is unavailable: {error_msg}")
        
        # Create engine and registry if not provided
        if engine is None:
            engine = WorkflowEngine()
            cls.register_tasks(engine)
        
        if registry is None:
            registry = WorkflowRegistry()
            cls.register_workflow(registry)
        
        # Prepare workflow input
        workflow_input = {
            "tenant_id": tenant_id,
            "asset_id": asset_id,
            "dataset_id": dataset_id,
            "file_id": file_id,
            "profile_key": profile_key,
            "triggered_by_id": triggered_by_id
        }
        
        # Create workflow instance
        workflow_instance = engine.create_instance(
            workflow_name=cls.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=tenant_id,
            created_by_id=triggered_by_id
        )
        
        # Start and execute workflow
        workflow_instance = engine.start_instance(str(workflow_instance.id))
        workflow_instance = engine.execute_instance(str(workflow_instance.id))
        
        # Check workflow status
        if workflow_instance.status == WorkflowStatus.COMPLETED:
            logger.info(
                "Data quality check workflow completed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id
            )
            return {
                "success": True,
                "workflow_instance_id": str(workflow_instance.id),
                "output_data": workflow_instance.output_data
            }
        else:
            error_message = workflow_instance.error_message or "Workflow execution failed"
            logger.error(
                "Data quality check workflow failed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                error=error_message
            )
            raise ValueError(f"Data quality check workflow failed: {error_message}")

