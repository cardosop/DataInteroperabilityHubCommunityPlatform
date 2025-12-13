"""
Asset Creation/Activation Workflow

Orchestrates the asset creation and activation process with proper error handling,
retry logic, and compensation. Supports both contract-first and data-first flows.
"""
import structlog
from typing import Dict, Any, Optional
from django.db import transaction
from django.utils import timezone

from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, DQStatus, ComplianceStatus
from hub.apps.search.indexing import SearchIndexer
from hub.apps.semantic.utils import map_asset_to_semantic
from hub.apps.audit.utils import create_audit_event
from hub.apps.notifications.tasks import send_email_async
from hub.apps.notifications.models import EmailType

logger = structlog.get_logger(__name__)


class AssetCreationWorkflow:
    """
    Asset creation/activation workflow orchestrator.
    
    Manages the complete asset creation and activation process:
    1. Create asset record (draft)
    2. Attach contract (if contract-first flow)
    3. Attach dataset (if data-first flow)
    4. Run data quality checks (if dataset exists)
    5. Run compliance checks (if dataset exists)
    6. Validate contract (if contract exists and not already validated)
    7. Activate asset (if all checks pass and auto_activate=True)
    8. Index for search
    9. Send notifications
    10. Audit logging
    """
    
    WORKFLOW_NAME = "asset_creation"
    WORKFLOW_VERSION = "1.0.0"
    
    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the asset creation workflow definition.
        
        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": cls.WORKFLOW_VERSION,
            "dependencies": [],
            "steps": [
                {
                    "name": "create_asset_record",
                    "type": "task",
                    "task": "asset_creation.create_asset_record"
                },
                {
                    "name": "attach_contract",
                    "type": "task",
                    "task": "asset_creation.attach_contract",
                    "condition": {
                        "if": "{{ contract_id != null }}"
                    }
                },
                {
                    "name": "attach_dataset",
                    "type": "task",
                    "task": "asset_creation.attach_dataset",
                    "condition": {
                        "if": "{{ dataset_id != null }}"
                    }
                },
                {
                    "name": "run_dq_checks",
                    "type": "task",
                    "task": "asset_creation.run_dq_checks",
                    "condition": {
                        "if": "{{ dataset_id != null }}"
                    }
                },
                {
                    "name": "run_compliance_checks",
                    "type": "task",
                    "task": "asset_creation.run_compliance_checks",
                    "condition": {
                        "if": "{{ dataset_id != null }}"
                    }
                },
                {
                    "name": "validate_contract",
                    "type": "task",
                    "task": "asset_creation.validate_contract",
                    "condition": {
                        "if": "{{ contract_id != null && contract_validation_status != 'VALID' }}"
                    }
                },
                {
                    "name": "activate_asset",
                    "type": "task",
                    "task": "asset_creation.activate_asset",
                    "condition": {
                        "if": "{{ auto_activate == true }}"
                    }
                },
                {
                    "name": "index_for_search",
                    "type": "task",
                    "task": "asset_creation.index_for_search"
                },
                {
                    "name": "send_notifications",
                    "type": "task",
                    "task": "asset_creation.send_notifications"
                },
                {
                    "name": "audit_logging",
                    "type": "task",
                    "task": "asset_creation.audit_logging"
                }
            ],
            "compensation": {"enabled": True}
        }
        registry.register_workflow(
            workflow_name=cls.WORKFLOW_NAME,
            dsl_json=workflow_dsl,
            description="Orchestrates asset creation and activation with DQ/compliance checks",
            version=cls.WORKFLOW_VERSION
        )
    
    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow tasks with the engine.
        
        Args:
            engine: WorkflowEngine instance
        """
        engine.register_task("asset_creation.create_asset_record", cls._create_asset_record_task)
        engine.register_task("asset_creation.attach_contract", cls._attach_contract_task)
        engine.register_task("asset_creation.attach_dataset", cls._attach_dataset_task)
        engine.register_task("asset_creation.run_dq_checks", cls._run_dq_checks_task)
        engine.register_task("asset_creation.run_compliance_checks", cls._run_compliance_checks_task)
        engine.register_task("asset_creation.validate_contract", cls._validate_contract_task)
        engine.register_task("asset_creation.activate_asset", cls._activate_asset_task)
        engine.register_task("asset_creation.index_for_search", cls._index_for_search_task)
        engine.register_task("asset_creation.send_notifications", cls._send_notifications_task)
        engine.register_task("asset_creation.audit_logging", cls._audit_logging_task)
    
    @staticmethod
    def _create_asset_record_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create asset record in DRAFT status.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with asset_id
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        key = input_data.get("key")
        name = input_data.get("name")
        description = input_data.get("description")
        domain = input_data.get("domain")
        visibility = input_data.get("visibility", AssetVisibility.INTERNAL)
        created_by_id = input_data.get("created_by_id") or instance.created_by_id
        
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not key:
            raise ValueError("key is required")
        if not name:
            raise ValueError("name is required")
        
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User
        
        tenant = Tenant.objects.get(id=tenant_id)
        created_by = User.objects.get(id=created_by_id) if created_by_id else None
        
        # Check if key already exists for tenant
        if Asset.objects.filter(tenant=tenant, key=key).exists():
            raise ValueError(f'Asset with key "{key}" already exists for this tenant')
        
        # Create asset
        with transaction.atomic():
            asset = Asset.objects.create(
                tenant=tenant,
                key=key,
                name=name,
                description=description,
                domain=domain,
                status=AssetStatus.DRAFT,
                visibility=visibility,
                created_by=created_by
            )
        
        # Store asset_id in state_data for subsequent steps
        instance.state_data["asset_id"] = str(asset.id)
        instance.save(update_fields=['state_data'])
        
        logger.info(
            "Asset record created",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            key=key,
            name=name
        )
        
        return {
            "asset_id": str(asset.id),
            "status": asset.status,
            "key": asset.key
        }
    
    @staticmethod
    def _attach_contract_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Attach contract to asset.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with contract_id
        """
        asset_id = instance.state_data.get("asset_id")
        contract_id = input_data.get("contract_id")
        
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not contract_id:
            # Skip if contract_id not provided (data-first flow)
            logger.info(
                "Skipping contract attachment: contract_id not provided",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {"skipped": True, "reason": "contract_id not provided"}
        
        from hub.apps.contracts.models import Contract
        
        asset = Asset.objects.get(id=asset_id)
        contract = Contract.objects.get(id=contract_id, tenant=asset.tenant)
        
        # Attach contract to asset
        contract.asset = asset
        
        # Get next version for asset
        latest_contract = asset.contracts.order_by('-version').first()
        if latest_contract:
            contract.version = latest_contract.version + 1
        else:
            contract.version = 1
        
        contract.save(update_fields=['asset', 'version'])
        
        # Store contract_id and validation status in state_data
        instance.state_data["contract_id"] = str(contract.id)
        instance.state_data["contract_validation_status"] = contract.validation_status
        instance.state_data["contract_normalization_status"] = contract.normalization_status
        instance.save(update_fields=['state_data'])
        
        logger.info(
            "Contract attached to asset",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            contract_id=str(contract.id),
            contract_version=contract.version
        )
        
        return {
            "contract_id": str(contract.id),
            "contract_version": contract.version,
            "validation_status": contract.validation_status,
            "normalization_status": contract.normalization_status
        }
    
    @staticmethod
    def _attach_dataset_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Attach dataset to asset.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with dataset_id
        """
        asset_id = instance.state_data.get("asset_id")
        dataset_id = input_data.get("dataset_id")
        
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not dataset_id:
            # Skip if dataset_id not provided (contract-first flow)
            logger.info(
                "Skipping dataset attachment: dataset_id not provided",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {"skipped": True, "reason": "dataset_id not provided"}
        
        from hub.apps.datasets.models import Dataset
        
        asset = Asset.objects.get(id=asset_id)
        dataset = Dataset.objects.get(id=dataset_id, tenant=asset.tenant)
        
        # Attach dataset to asset
        dataset.asset = asset
        
        # Get next version for asset
        latest_dataset = asset.datasets.order_by('-version').first()
        if latest_dataset:
            dataset.version = latest_dataset.version + 1
        else:
            dataset.version = 1
        
        dataset.save(update_fields=['asset', 'version'])
        
        # Store dataset_id in state_data
        instance.state_data["dataset_id"] = str(dataset.id)
        instance.save(update_fields=['state_data'])
        
        logger.info(
            "Dataset attached to asset",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            dataset_id=str(dataset.id),
            dataset_version=dataset.version
        )
        
        return {
            "dataset_id": str(dataset.id),
            "dataset_version": dataset.version
        }
    
    @staticmethod
    def _run_dq_checks_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Run data quality checks on asset dataset.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with dq_status
        """
        asset_id = instance.state_data.get("asset_id")
        dataset_id = instance.state_data.get("dataset_id") or input_data.get("dataset_id")
        profile_key = input_data.get("profile_key", "intake_basic_gx")
        
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not dataset_id:
            # Skip if dataset_id not provided (contract-first flow)
            logger.info(
                "Skipping DQ checks: dataset_id not provided",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {"skipped": True, "reason": "dataset_id not provided"}
        
        from hub.apps.orchestration.workflows.data_quality import DataQualityCheckWorkflow
        
        asset = Asset.objects.get(id=asset_id)
        
        # Trigger DQ check workflow
        try:
            dq_result = DataQualityCheckWorkflow.execute(
                tenant_id=str(asset.tenant.id),
                asset_id=str(asset.id),
                dataset_id=dataset_id,
                profile_key=profile_key,
                triggered_by_id=str(instance.created_by_id)
            )
            
            # Get DQ run result from workflow state
            workflow_instance_id = dq_result.get("workflow_instance_id")
            if workflow_instance_id:
                from hub.apps.orchestration.models import WorkflowInstance as DQWorkflowInstance
                dq_workflow_instance = DQWorkflowInstance.objects.get(id=workflow_instance_id)
                dq_run_id = dq_workflow_instance.state_data.get("dq_run_id")
                
                if dq_run_id:
                    from hub.apps.dq.models import DQRun
                    dq_run = DQRun.objects.get(id=dq_run_id)
                    
                    # Update asset DQ status
                    if dq_run.overall_status == "PASS":
                        asset.dq_status = DQStatus.PASS
                    elif dq_run.overall_status == "WARN":
                        asset.dq_status = DQStatus.WARN
                    elif dq_run.overall_status == "FAIL":
                        asset.dq_status = DQStatus.FAIL
                    else:
                        asset.dq_status = DQStatus.UNKNOWN
                    
                    asset.save(update_fields=['dq_status'])
                    
                    # Store DQ status in state_data
                    instance.state_data["dq_status"] = asset.dq_status
                    instance.state_data["dq_run_id"] = str(dq_run.id)
                    instance.state_data["quality_score"] = dq_run.quality_score
                    instance.save(update_fields=['state_data'])
                    
                    logger.info(
                        "DQ checks completed",
                        workflow_instance_id=str(instance.id),
                        asset_id=str(asset.id),
                        dq_status=asset.dq_status,
                        quality_score=dq_run.quality_score
                    )
                    
                    return {
                        "dq_status": asset.dq_status,
                        "quality_score": dq_run.quality_score,
                        "dq_run_id": str(dq_run.id)
                    }
        except Exception as e:
            logger.error(
                "Failed to run DQ checks",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                error=str(e)
            )
            # Set DQ status to UNKNOWN on failure
            asset.dq_status = DQStatus.UNKNOWN
            asset.save(update_fields=['dq_status'])
            raise
        
        return {
            "dq_status": DQStatus.UNKNOWN,
            "quality_score": None
        }
    
    @staticmethod
    def _run_compliance_checks_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Run compliance checks on asset dataset.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with compliance_status
        """
        asset_id = instance.state_data.get("asset_id")
        dataset_id = instance.state_data.get("dataset_id") or input_data.get("dataset_id")
        scan_mode = input_data.get("scan_mode", "internal")
        applicable_regulations = input_data.get("applicable_regulations", [])
        
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not dataset_id:
            # Skip if dataset_id not provided (contract-first flow)
            logger.info(
                "Skipping compliance checks: dataset_id not provided",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {"skipped": True, "reason": "dataset_id not provided"}
        
        from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
        from hub.apps.datasets.models import Dataset
        from hub.apps.jobs.utils import create_job
        from hub.apps.jobs.models import JobType
        
        asset = Asset.objects.get(id=asset_id)
        dataset = Dataset.objects.get(id=dataset_id, tenant=asset.tenant)
        
        if not dataset.file:
            raise ValueError("Dataset must have a file for compliance checks")
        
        # Create compliance run
        triggered_by_id = instance.created_by_id
        from hub.apps.users.models import User
        triggered_by = User.objects.get(id=triggered_by_id) if triggered_by_id else None
        
        job = create_job(
            tenant=asset.tenant,
            user=triggered_by,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(asset.id),
            details_json={
                "scan_mode": scan_mode,
                "applicable_regulations": applicable_regulations
            }
        )
        
        compliance_run = ComplianceRun.objects.create(
            tenant=asset.tenant,
            asset=asset,
            dataset=dataset,
            file=dataset.file,
            job=job,
            regulations=applicable_regulations if applicable_regulations else [],
            status=ComplianceRunStatus.PENDING
        )
        
        # Execute compliance check
        try:
            from hub.apps.compliance.views import execute_compliance_run
            execute_compliance_run(str(compliance_run.id))
            
            # Refresh compliance run
            compliance_run.refresh_from_db()
            
            # Update asset compliance status
            if compliance_run.overall_status == "PASS":
                asset.compliance_status = ComplianceStatus.PASS
            elif compliance_run.overall_status == "WARN":
                asset.compliance_status = ComplianceStatus.WARN
            elif compliance_run.overall_status == "FAIL":
                asset.compliance_status = ComplianceStatus.FAIL
            else:
                asset.compliance_status = ComplianceStatus.UNKNOWN
            
            asset.save(update_fields=['compliance_status'])
            
            # Store compliance status in state_data
            instance.state_data["compliance_status"] = asset.compliance_status
            instance.state_data["compliance_run_id"] = str(compliance_run.id)
            instance.save(update_fields=['state_data'])
            
            logger.info(
                "Compliance checks completed",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                compliance_status=asset.compliance_status,
                risk_level=compliance_run.risk_level
            )
            
            return {
                "compliance_status": asset.compliance_status,
                "risk_level": compliance_run.risk_level,
                "compliance_run_id": str(compliance_run.id)
            }
        except Exception as e:
            logger.error(
                "Failed to run compliance checks",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                error=str(e)
            )
            # Set compliance status to UNKNOWN on failure
            asset.compliance_status = ComplianceStatus.UNKNOWN
            asset.save(update_fields=['compliance_status'])
            raise
    
    @staticmethod
    def _validate_contract_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate contract if not already validated.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with validation_status
        """
        asset_id = instance.state_data.get("asset_id")
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")
        contract_validation_status = instance.state_data.get("contract_validation_status")
        
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not contract_id:
            # Skip if contract_id not provided (data-first flow)
            logger.info(
                "Skipping contract validation: contract_id not provided",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {"skipped": True, "reason": "contract_id not provided"}
        
        # Skip if contract is already validated
        if contract_validation_status in ["VALID", "WARNING_ONLY"]:
            logger.info(
                "Skipping contract validation: already validated",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id),
                contract_id=str(contract_id),
                validation_status=contract_validation_status
            )
            return {
                "validation_status": contract_validation_status,
                "already_validated": True,
                "skipped": True
            }
        
        from hub.apps.contracts.models import Contract
        
        asset = Asset.objects.get(id=asset_id)
        contract = Contract.objects.get(id=contract_id, tenant=asset.tenant)
        
        # Check if contract is already validated
        if contract.validation_status in ["VALID", "WARNING_ONLY"]:
            logger.info(
                "Contract already validated",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                contract_id=str(contract.id),
                validation_status=contract.validation_status
            )
            return {
                "validation_status": contract.validation_status,
                "already_validated": True
            }
        
        # Trigger contract validation workflow if needed
        # For now, we'll just check the contract status
        # In a full implementation, this would trigger ContractCreationWorkflow.validate_contract step
        
        # Update state_data with validation status
        instance.state_data["contract_validation_status"] = contract.validation_status
        instance.save(update_fields=['state_data'])
        
        logger.info(
            "Contract validation checked",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            contract_id=str(contract.id),
            validation_status=contract.validation_status
        )
        
        return {
            "validation_status": contract.validation_status,
            "already_validated": False
        }
    
    @staticmethod
    def _activate_asset_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Activate asset if all checks pass.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with activation status
        """
        asset_id = instance.state_data.get("asset_id")
        auto_activate = input_data.get("auto_activate", False)
        
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        
        if not auto_activate:
            # Skip activation if auto_activate is False
            logger.info(
                "Auto-activation disabled, skipping activation",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {
                "activated": False,
                "reason": "auto_activate is False",
                "skipped": True
            }
        
        asset = Asset.objects.get(id=asset_id)
        
        # Check if asset can be activated
        can_activate, blockers = asset.can_activate()
        if not can_activate:
            logger.warning(
                "Cannot activate asset: requirements not met",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                blockers=blockers
            )
            return {
                "activated": False,
                "reason": "activation requirements not met",
                "blockers": blockers
            }
        
        # Activate asset
        old_status = asset.status
        asset.status = AssetStatus.ACTIVE
        asset.increment_version()
        asset.save(update_fields=['status', 'version', 'updated_at'])
        
        # Trigger semantic mapping
        try:
            map_asset_to_semantic(asset, tenant=asset.tenant)
        except Exception as e:
            logger.warning(
                "Semantic mapping failed for asset",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                error=str(e)
            )
            # Don't fail activation if semantic mapping fails
        
        # Store activation status in state_data
        instance.state_data["asset_status"] = asset.status
        instance.state_data["activated"] = True
        instance.save(update_fields=['state_data'])
        
        logger.info(
            "Asset activated",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            old_status=old_status,
            new_status=asset.status
        )
        
        return {
            "activated": True,
            "old_status": old_status,
            "new_status": asset.status
        }
    
    @staticmethod
    def _index_for_search_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Index asset for search.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with search_index_id
        """
        asset_id = instance.state_data.get("asset_id")
        
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        
        asset = Asset.objects.get(id=asset_id)
        
        try:
            search_index = SearchIndexer.index_asset(asset)
            
            logger.info(
                "Asset indexed for search",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                search_index_id=str(search_index.id)
            )
            
            return {
                "search_index_id": str(search_index.id),
                "indexed": True
            }
        except Exception as e:
            logger.error(
                "Failed to index asset for search",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                error=str(e)
            )
            # Don't fail workflow if indexing fails
            return {
                "indexed": False,
                "error": str(e)
            }
    
    @staticmethod
    def _send_notifications_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Send notifications about asset creation/activation.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with notification status
        """
        asset_id = instance.state_data.get("asset_id")
        send_notifications = input_data.get("send_notifications", True)
        
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        
        if not send_notifications:
            logger.info(
                "Notifications disabled, skipping",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {
                "notifications_sent": False,
                "reason": "send_notifications is False"
            }
        
        asset = Asset.objects.get(id=asset_id)
        activated = instance.state_data.get("activated", False)
        
        # Get creator email
        creator_email = None
        if asset.created_by and asset.created_by.email:
            creator_email = asset.created_by.email
        
        notifications_sent = []
        
        try:
            if creator_email:
                if activated:
                    subject = f"Asset '{asset.name}' Activated"
                    message = f"Your asset '{asset.name}' (key: {asset.key}) has been successfully activated."
                else:
                    subject = f"Asset '{asset.name}' Created"
                    message = f"Your asset '{asset.name}' (key: {asset.key}) has been created in DRAFT status."
                
                send_email_async(
                    email_type=EmailType.JOB_COMPLETION,
                    to_email=creator_email,
                    subject=subject,
                    template_name="job_completion",
                    context={"message": message, "asset_name": asset.name, "asset_key": asset.key},
                    tenant_id=str(asset.tenant.id)
                )
                notifications_sent.append(creator_email)
                
                logger.info(
                    "Notification sent to creator",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    email=creator_email
                )
        except Exception as e:
            logger.error(
                "Failed to send notification",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                error=str(e)
            )
            # Don't fail workflow if notification fails
        
        return {
            "notifications_sent": len(notifications_sent) > 0,
            "recipients": notifications_sent
        }
    
    @staticmethod
    def _audit_logging_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create audit log entry for asset creation/activation.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with audit_event_id
        """
        asset_id = instance.state_data.get("asset_id")
        tenant_id = instance.tenant_id
        created_by_id = instance.created_by_id
        
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User
        
        tenant = Tenant.objects.get(id=tenant_id)
        created_by = User.objects.get(id=created_by_id) if created_by_id else None
        asset = Asset.objects.get(id=asset_id)
        activated = instance.state_data.get("activated", False)
        
        action = "ASSET_ACTIVATED" if activated else "ASSET_CREATED"
        
        audit_event = create_audit_event(
            resource_type="ASSET",
            action=action,
            actor_user=created_by,
            tenant=tenant,
            resource_id=str(asset.id),
            details={
                "key": asset.key,
                "name": asset.name,
                "status": asset.status,
                "domain": asset.domain,
                "has_contract": asset.contracts.exists(),
                "has_dataset": asset.datasets.exists(),
                "dq_status": asset.dq_status,
                "compliance_status": asset.compliance_status,
                "workflow_instance_id": str(instance.id)
            }
        )
        
        logger.info(
            "Audit log created",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            audit_event_id=str(audit_event.id),
            action=action
        )
        
        return {
            "audit_event_id": str(audit_event.id),
            "action": action
        }
    
    @classmethod
    def execute(
        cls,
        tenant_id: str,
        key: str,
        name: str,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        visibility: str = AssetVisibility.INTERNAL,
        contract_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        profile_key: str = "intake_basic_gx",
        scan_mode: str = "internal",
        applicable_regulations: Optional[list] = None,
        auto_activate: bool = False,
        send_notifications: bool = True,
        created_by_id: Optional[str] = None,
        engine: Optional[WorkflowEngine] = None,
        registry: Optional[WorkflowRegistry] = None
    ) -> Dict[str, Any]:
        """
        Execute asset creation workflow.
        
        Args:
            tenant_id: Tenant ID
            key: Asset key (unique per tenant)
            name: Asset name
            description: Asset description (optional)
            domain: Asset domain (optional)
            visibility: Asset visibility (default: INTERNAL)
            contract_id: Contract ID to attach (optional, for contract-first flow)
            dataset_id: Dataset ID to attach (optional, for data-first flow)
            profile_key: DQ profile key (default: intake_basic_gx)
            scan_mode: Compliance scan mode (default: internal)
            applicable_regulations: List of regulations to check (optional)
            auto_activate: Whether to auto-activate asset if checks pass (default: False)
            send_notifications: Whether to send notifications (default: True)
            created_by_id: User ID who created the asset
            engine: Optional WorkflowEngine instance
            registry: Optional WorkflowRegistry instance
            
        Returns:
            Workflow execution result dictionary
            
        Raises:
            ValueError: If workflow execution fails
        """
        # Create engine and registry if not provided
        if engine is None:
            engine = WorkflowEngine()
            cls.register_tasks(engine)
        
        if registry is None:
            registry = WorkflowRegistry()
            cls.register_workflow(registry)
        
        # Validate tenant exists before creating workflow instance
        from hub.apps.tenants.models import Tenant
        try:
            Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise ValueError(f"Tenant matching query does not exist: {tenant_id}")
        
        # Prepare workflow input
        workflow_input = {
            "tenant_id": tenant_id,
            "key": key,
            "name": name,
            "description": description,
            "domain": domain,
            "visibility": visibility,
            "contract_id": contract_id,
            "dataset_id": dataset_id,
            "profile_key": profile_key,
            "scan_mode": scan_mode,
            "applicable_regulations": applicable_regulations or [],
            "auto_activate": auto_activate,
            "send_notifications": send_notifications,
            "created_by_id": created_by_id
        }
        
        # Create workflow instance
        try:
            workflow_instance = engine.create_instance(
                workflow_name=cls.WORKFLOW_NAME,
                input_data=workflow_input,
                tenant_id=tenant_id,
                created_by_id=created_by_id
            )
        except Exception as e:
            # Catch database integrity errors and convert to ValueError
            from django.db import IntegrityError
            if isinstance(e, IntegrityError) or "foreign key constraint" in str(e).lower():
                raise ValueError(f"Invalid tenant_id: {tenant_id}") from e
            raise
        
        # Start and execute workflow
        workflow_instance = engine.start_instance(str(workflow_instance.id))
        workflow_instance = engine.execute_instance(str(workflow_instance.id))
        
        # Check workflow status
        if workflow_instance.status == WorkflowStatus.COMPLETED:
            logger.info(
                "Asset creation workflow completed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                asset_id=workflow_instance.state_data.get("asset_id")
            )
            return {
                "success": True,
                "workflow_instance_id": str(workflow_instance.id),
                "output_data": workflow_instance.output_data
            }
        else:
            error_message = workflow_instance.error_message or "Workflow execution failed"
            # Use structlog-compatible logging format
            try:
                logger.error(
                    "Asset creation workflow failed",
                    workflow_instance_id=str(workflow_instance.id),
                    tenant_id=tenant_id,
                    error=error_message
                )
            except TypeError:
                # Fallback if structlog not configured (e.g., in tests)
                logger.error(
                    f"Asset creation workflow failed: workflow_instance_id={workflow_instance.id}, "
                    f"tenant_id={tenant_id}, error={error_message}"
                )
            raise ValueError(f"Asset creation workflow failed: {error_message}")

