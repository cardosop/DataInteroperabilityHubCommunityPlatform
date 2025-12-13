"""
Contract Creation Workflow

Orchestrates the contract creation process with proper error handling,
retry logic, and compensation.
"""
import structlog
from typing import Dict, Any, Optional
from django.db import transaction
from django.utils import timezone

from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.contracts.models import Contract, ContractStatus, NormalizationStatus
from hub.apps.contracts.normalization import normalize_contract, validate_hubcontract_schema
from hub.apps.search.indexing import SearchIndexer
from hub.apps.semantic.utils import map_contract_to_semantic
from hub.apps.audit.utils import create_audit_event
from hub.apps.notifications.tasks import send_email_async
from hub.apps.notifications.models import EmailType

logger = structlog.get_logger(__name__)


class ContractCreationWorkflow:
    """
    Contract creation workflow orchestrator.
    
    Manages the complete contract creation process:
    1. Validate input contract
    2. Normalize contract (ODCS → HubContract)
    3. Extract objects (Contact, Server, Terms, etc.)
    4. Create contract record
    5. Index for search
    6. Generate semantic mapping (RDF)
    7. Send notifications
    8. Audit logging
    """
    
    WORKFLOW_NAME = "contract_creation"
    
    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the contract creation workflow definition.
        
        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": "1.0.0",
            "dependencies": [],
            "steps": [
                {
                    "name": "validate_input",
                    "type": "task",
                    "task": "contract_creation.validate_input"
                },
                {
                    "name": "normalize_contract",
                    "type": "task",
                    "task": "contract_creation.normalize_contract",
                    "compensation": {
                        "type": "task",
                        "task": "contract_creation.rollback_normalization"
                    }
                },
                {
                    "name": "validate_hubcontract",
                    "type": "task",
                    "task": "contract_creation.validate_hubcontract",
                    "compensation": {
                        "type": "task",
                        "task": "contract_creation.rollback_validation"
                    }
                },
                {
                    "name": "create_contract_record",
                    "type": "task",
                    "task": "contract_creation.create_contract_record",
                    "compensation": {
                        "type": "task",
                        "task": "contract_creation.rollback_contract_record"
                    }
                },
                {
                    "name": "index_for_search",
                    "type": "task",
                    "task": "contract_creation.index_for_search",
                    "compensation": {
                        "type": "task",
                        "task": "contract_creation.rollback_indexing"
                    }
                },
                {
                    "name": "generate_semantic_mapping",
                    "type": "task",
                    "task": "contract_creation.generate_semantic_mapping"
                },
                {
                    "name": "send_notifications",
                    "type": "task",
                    "task": "contract_creation.send_notifications"
                },
                {
                    "name": "audit_logging",
                    "type": "task",
                    "task": "contract_creation.audit_logging"
                }
            ],
            "compensation": {
                "enabled": True
            }
        }
        
        registry.register_workflow(
            workflow_name=cls.WORKFLOW_NAME,
            dsl_json=workflow_dsl,
            description="Orchestrates contract creation with validation, normalization, indexing, and notifications"
        )
    
    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow task functions.
        
        Args:
            engine: WorkflowEngine instance
        """
        engine.register_task("contract_creation.validate_input", cls._validate_input_task)
        engine.register_task("contract_creation.normalize_contract", cls._normalize_contract_task)
        engine.register_task("contract_creation.validate_hubcontract", cls._validate_hubcontract_task)
        engine.register_task("contract_creation.create_contract_record", cls._create_contract_record_task)
        engine.register_task("contract_creation.index_for_search", cls._index_for_search_task)
        engine.register_task("contract_creation.generate_semantic_mapping", cls._generate_semantic_mapping_task)
        engine.register_task("contract_creation.send_notifications", cls._send_notifications_task)
        engine.register_task("contract_creation.audit_logging", cls._audit_logging_task)
        
        # Compensation tasks
        engine.register_task("contract_creation.rollback_normalization", cls._rollback_normalization_task)
        engine.register_task("contract_creation.rollback_validation", cls._rollback_validation_task)
        engine.register_task("contract_creation.rollback_contract_record", cls._rollback_contract_record_task)
        engine.register_task("contract_creation.rollback_indexing", cls._rollback_indexing_task)
    
    @staticmethod
    def _validate_input_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate input contract data.
        
        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with validated data
        """
        original_raw = input_data.get("original_raw")
        original_format = input_data.get("original_format")
        tenant_id = input_data.get("tenant_id")
        user_id = input_data.get("user_id")
        
        # Validate required fields
        if not original_raw:
            raise ValueError("original_raw is required")
        if not original_format:
            raise ValueError("original_format is required")
        if original_format not in ["JSON", "YAML"]:
            raise ValueError(f"original_format must be JSON or YAML, got {original_format}")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not user_id:
            raise ValueError("user_id is required")
        
        logger.info(
            "Contract input validated",
            workflow_instance_id=str(instance.id),
            tenant_id=tenant_id,
            format=original_format
        )
        
        return {
            "validated": True,
            "original_raw": original_raw,
            "original_format": original_format,
            "tenant_id": tenant_id,
            "user_id": user_id
        }
    
    @staticmethod
    def _normalize_contract_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Normalize contract (ODCS → HubContract).
        
        Args:
            input_data: Workflow input data (includes validated input)
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with normalization results
        """
        original_raw = input_data.get("original_raw")
        original_format = input_data.get("original_format")
        original_spec_type = input_data.get("original_spec_type")
        
        # Normalize contract
        hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = normalize_contract(
            raw_contract=original_raw,
            format=original_format,
            spec_type=original_spec_type
        )
        
        # Check for critical errors (parsing errors, DCS rejection, or any normalization failure)
        if norm_status == NormalizationStatus.NORMALIZATION_FAILED:
            if norm_errors:
                parsing_errors = [
                    e for e in norm_errors
                    if any(keyword in e.lower() for keyword in [
                        'parsing failed', 'jsondecodeerror', 'yamlerror',
                        'failed to normalize contract'
                    ])
                ]
                dcs_rejection_errors = [
                    e for e in norm_errors
                    if any(keyword in e.lower() for keyword in [
                        'data contract specification', 'dcs', 'no longer supported'
                    ])
                ]
                
                if parsing_errors or dcs_rejection_errors:
                    error_code = 'DCS_NOT_SUPPORTED' if dcs_rejection_errors else 'INVALID_SPEC_FORMAT'
                    raise ValueError(f"{error_code}: {norm_errors[0]}")
                else:
                    # Generic normalization failure
                    raise ValueError(f"INVALID_SPEC_FORMAT: {norm_errors[0] if norm_errors else 'Contract normalization failed'}")
            else:
                # Normalization failed but no error messages (shouldn't happen, but handle gracefully)
                raise ValueError("INVALID_SPEC_FORMAT: Contract normalization failed")
        
        logger.info(
            "Contract normalized",
            workflow_instance_id=str(instance.id),
            spec_type=detected_spec_type,
            spec_version=detected_spec_version,
            status=norm_status.value
        )
        
        return {
            "hub_contract": hub_contract,
            "detected_spec_type": detected_spec_type,
            "detected_spec_version": detected_spec_version,
            "normalization_status": norm_status.value,
            "normalization_errors": norm_errors,
            "normalization_warnings": norm_warnings,
            "state": {
                "hub_contract": hub_contract,  # Also store in state for subsequent steps
                "detected_spec_type": detected_spec_type,
                "detected_spec_version": detected_spec_version,
                "normalization_status": norm_status.value
            }
        }
    
    @staticmethod
    def _validate_hubcontract_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate HubContract schema.
        
        Args:
            input_data: Workflow input data (includes normalization results)
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with validation results
        """
        hub_contract = input_data.get("hub_contract")
        
        if not hub_contract:
            # If normalization failed, skip validation
            return {
                "validation_skipped": True,
                "reason": "No hub_contract to validate"
            }
        
        # Validate HubContract schema
        is_valid, validation_errors = validate_hubcontract_schema(hub_contract)
        
        if not is_valid:
            # Update normalization status to failed
            return {
                "validation_passed": False,
                "validation_errors": validation_errors,
                "normalization_status": NormalizationStatus.NORMALIZATION_FAILED.value
            }
        
        logger.info(
            "HubContract validated",
            workflow_instance_id=str(instance.id),
            valid=True
        )
        
        return {
            "validation_passed": True,
            "validation_errors": []
        }
    
    @staticmethod
    @transaction.atomic
    def _create_contract_record_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create contract record in database.
        
        Args:
            input_data: Workflow input data (includes validation results)
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with contract ID
        """
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Get data from state_data (which accumulates from previous steps) or input_data
        tenant_id = instance.state_data.get("tenant_id") or input_data.get("tenant_id")
        user_id = instance.state_data.get("user_id") or input_data.get("user_id")
        asset_id = instance.state_data.get("asset_id") or input_data.get("asset_id")
        original_raw = instance.state_data.get("original_raw") or input_data.get("original_raw")
        original_format = instance.state_data.get("original_format") or input_data.get("original_format")
        original_spec_type = instance.state_data.get("original_spec_type") or input_data.get("original_spec_type")
        detected_spec_type = instance.state_data.get("detected_spec_type") or input_data.get("detected_spec_type")
        detected_spec_version = instance.state_data.get("detected_spec_version") or input_data.get("detected_spec_version")
        hub_contract = instance.state_data.get("hub_contract") or input_data.get("hub_contract")
        normalization_status_str = instance.state_data.get("normalization_status") or input_data.get("normalization_status")
        normalization_errors = instance.state_data.get("normalization_errors", []) or input_data.get("normalization_errors", [])
        normalization_warnings = instance.state_data.get("normalization_warnings", []) or input_data.get("normalization_warnings", [])
        validation_errors = instance.state_data.get("validation_errors", []) or input_data.get("validation_errors", [])
        
        # Get tenant and user
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id)
        
        # Get asset if provided
        asset = None
        if asset_id:
            from hub.apps.assets.models import Asset
            asset = Asset.objects.get(id=asset_id, tenant=tenant)
        
        # Calculate version
        version = 1
        if asset:
            latest_contract = Contract.objects.filter(
                tenant=tenant,
                asset=asset
            ).order_by('-version').first()
            if latest_contract:
                version = latest_contract.version + 1
        
        # Determine final spec type and version
        # Use detected_spec_type if available, otherwise fall back to original_spec_type or default to ODCS
        final_spec_type = detected_spec_type or original_spec_type or "ODCS"
        final_spec_version = detected_spec_version or "3.0.2"
        
        # Determine final normalization status
        # Handle case where normalization_status might be None or a string
        if normalization_status_str:
            try:
                final_norm_status = NormalizationStatus(normalization_status_str)
            except (ValueError, TypeError):
                # If it's not a valid status, default based on hub_contract presence
                final_norm_status = NormalizationStatus.NORMALIZED_OK if hub_contract else NormalizationStatus.NORMALIZATION_FAILED
        else:
            # Default based on hub_contract presence
            final_norm_status = NormalizationStatus.NORMALIZED_OK if hub_contract else NormalizationStatus.NORMALIZATION_FAILED
        
        if validation_errors and len(validation_errors) > 0:
            final_norm_status = NormalizationStatus.NORMALIZATION_FAILED
            normalization_errors.extend(validation_errors)
            hub_contract = None
        
        # Create contract
        contract = Contract.objects.create(
            tenant=tenant,
            asset=asset,
            version=version,
            status=ContractStatus.DRAFT,
            original_spec_type=final_spec_type,
            original_spec_version=final_spec_version,
            original_format=original_format,
            original_raw=original_raw,
            hub_contract_version="1.0.0" if hub_contract else None,
            hub_contract_json=hub_contract,
            normalization_status=final_norm_status,
            normalization_errors=normalization_errors,
            normalization_warnings=normalization_warnings,
            created_by=user
        )
        
        logger.info(
            "Contract record created",
            workflow_instance_id=str(instance.id),
            contract_id=str(contract.id),
            tenant_id=tenant_id
        )
        
        # Store contract_id in state for subsequent steps
        # Return contract_id both at top level and in state for subsequent steps
        return {
            "contract_id": str(contract.id),
            "state": {
                "contract_id": str(contract.id)
            }
        }
    
    @staticmethod
    @transaction.atomic
    def _index_for_search_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Index contract for search.
        
        Args:
            input_data: Workflow input data (includes contract_id from state)
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with indexing results
        """
        # Get contract_id from state_data (set by previous step)
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")
        
        if not contract_id:
            raise ValueError("contract_id is required for indexing")
        
        # Get contract
        contract = Contract.objects.get(id=contract_id)
        
        # Index contract
        search_index = SearchIndexer.index_contract(contract)
        
        logger.info(
            "Contract indexed for search",
            workflow_instance_id=str(instance.id),
            contract_id=contract_id,
            search_index_id=str(search_index.id)
        )
        
        return {
            "indexed": True,
            "search_index_id": str(search_index.id)
        }
    
    @staticmethod
    def _generate_semantic_mapping_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Generate semantic mapping (RDF) for contract.
        
        Args:
            input_data: Workflow input data (includes contract_id from state)
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with semantic mapping results
        """
        # Get contract_id from state_data (set by previous step)
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")
        
        if not contract_id:
            raise ValueError("contract_id is required for semantic mapping")
        
        # Get contract
        contract = Contract.objects.get(id=contract_id)
        
        # Skip if normalization failed (no hub_contract_json)
        if not contract.hub_contract_json:
            logger.info(
                "Semantic mapping skipped (no hub_contract_json)",
                workflow_instance_id=str(instance.id),
                contract_id=contract_id
            )
            return {
                "semantic_mapping_skipped": True,
                "reason": "No hub_contract_json to map"
            }
        
        # Generate semantic mapping
        # Wrap in try-except to handle service failures gracefully
        try:
            semantic_resource = map_contract_to_semantic(
                contract=contract,
                tenant=contract.tenant,
                use_cache=False
            )
            
            if semantic_resource:
                logger.info(
                    "Semantic mapping generated",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id,
                    semantic_resource_id=str(semantic_resource.id),
                    uri=semantic_resource.uri
                )
                return {
                    "semantic_mapping_generated": True,
                    "semantic_resource_id": str(semantic_resource.id),
                    "uri": semantic_resource.uri
                }
            else:
                # Service returned None (likely service unavailable)
                logger.warning(
                    "Semantic mapping service unavailable or returned None",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id
                )
                return {
                    "semantic_mapping_generated": False,
                    "semantic_mapping_skipped": True,
                    "reason": "Semantic service unavailable"
                }
        except Exception as e:
            # Don't fail workflow on semantic service errors - log and continue
            logger.warning(
                "Semantic mapping failed (non-critical)",
                workflow_instance_id=str(instance.id),
                contract_id=contract_id,
                error=str(e)
            )
            return {
                "semantic_mapping_generated": False,
                "semantic_mapping_skipped": True,
                "reason": f"Semantic service error: {str(e)}"
            }
    
    @staticmethod
    def _send_notifications_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Send notifications about contract creation.
        
        Args:
            input_data: Workflow input data (includes contract_id from state)
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with notification results
        """
        # Get contract_id from state_data (set by previous step)
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")
        user_id = input_data.get("user_id")
        tenant_id = input_data.get("tenant_id")
        
        if not contract_id or not user_id:
            logger.warning(
                "Notifications skipped (missing contract_id or user_id)",
                workflow_instance_id=str(instance.id)
            )
            return {
                "notifications_sent": False,
                "reason": "Missing required data"
            }
        
        # Get contract and user
        contract = Contract.objects.get(id=contract_id)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(id=user_id)
        
        # Log notification (email template can be added later)
        try:
            contract_title = "Untitled Contract"
            if contract.hub_contract_json and isinstance(contract.hub_contract_json, dict):
                info = contract.hub_contract_json.get('info', {})
                if isinstance(info, dict):
                    contract_title = info.get('title', 'Untitled Contract')
            
            logger.info(
                "Contract creation notification logged",
                workflow_instance_id=str(instance.id),
                contract_id=contract_id,
                user_id=user_id,
                contract_title=contract_title,
                user_email=user.email
            )
            
            return {
                "notifications_sent": True,
                "notification_type": "logged"
            }
        except Exception as e:
            logger.error(
                "Failed to log contract creation notification",
                workflow_instance_id=str(instance.id),
                contract_id=contract_id,
                error=str(e),
                exc_info=True
            )
            # Don't fail workflow on notification errors
            return {
                "notifications_sent": False,
                "error": str(e)
            }
    
    @staticmethod
    def _audit_logging_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create audit log entry for contract creation.
        
        Args:
            input_data: Workflow input data (includes contract_id from state)
            instance: Workflow instance
            step: Workflow step
            
        Returns:
            Task output with audit log results
        """
        # Get contract_id from state_data (set by previous step)
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")
        user_id = input_data.get("user_id")
        tenant_id = input_data.get("tenant_id")
        detected_spec_type = instance.state_data.get("detected_spec_type") or input_data.get("detected_spec_type")
        detected_spec_version = instance.state_data.get("detected_spec_version") or input_data.get("detected_spec_version")
        normalization_status = instance.state_data.get("normalization_status") or input_data.get("normalization_status")
        asset_id = input_data.get("asset_id")
        
        if not contract_id or not user_id or not tenant_id:
            raise ValueError("contract_id, user_id, and tenant_id are required for audit logging")
        
        # Get contract, user, and tenant
        contract = Contract.objects.get(id=contract_id)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(id=user_id)
        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id)
        
        # Create audit event
        create_audit_event(
            resource_type="CONTRACT",
            action="CONTRACT_CREATED",
            actor_user=user,
            tenant=tenant,
            resource_id=contract_id,
            details={
                'original_spec_type': detected_spec_type,
                'original_spec_version': detected_spec_version,
                'normalization_status': normalization_status,
                'asset_id': asset_id
            },
            request=None  # No request object in workflow context
        )
        
        logger.info(
            "Audit log created for contract creation",
            workflow_instance_id=str(instance.id),
            contract_id=contract_id
        )
        
        return {
            "audit_logged": True
        }
    
    # Compensation tasks
    
    @staticmethod
    def _rollback_normalization_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback normalization (no-op, normalization is stateless)"""
        logger.info(
            "Normalization rollback (no-op)",
            workflow_instance_id=str(instance.id)
        )
        return {"rolled_back": True}
    
    @staticmethod
    def _rollback_validation_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback validation (no-op, validation is stateless)"""
        logger.info(
            "Validation rollback (no-op)",
            workflow_instance_id=str(instance.id)
        )
        return {"rolled_back": True}
    
    @staticmethod
    @transaction.atomic
    def _rollback_contract_record_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback contract record creation (delete contract)"""
        contract_id = input_data.get("contract_id")
        
        if contract_id:
            try:
                contract = Contract.objects.get(id=contract_id)
                contract.delete()
                logger.info(
                    "Contract record rolled back (deleted)",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id
                )
            except Contract.DoesNotExist:
                logger.warning(
                    "Contract record not found for rollback",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id
                )
        
        return {"rolled_back": True}
    
    @staticmethod
    @transaction.atomic
    def _rollback_indexing_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback search indexing (delete search index)"""
        search_index_id = input_data.get("search_index_id")
        
        if search_index_id:
            try:
                from hub.apps.search.models import SearchIndex
                search_index = SearchIndex.objects.get(id=search_index_id)
                search_index.delete()
                logger.info(
                    "Search index rolled back (deleted)",
                    workflow_instance_id=str(instance.id),
                    search_index_id=search_index_id
                )
            except Exception as e:
                logger.warning(
                    "Search index rollback failed",
                    workflow_instance_id=str(instance.id),
                    search_index_id=search_index_id,
                    error=str(e)
                )
        
        return {"rolled_back": True}
    
    @classmethod
    @transaction.atomic
    def execute(
        cls,
        original_raw: str,
        original_format: str,
        tenant_id: str,
        user_id: str,
        asset_id: Optional[str] = None,
        original_spec_type: Optional[str] = None,
        engine: Optional[WorkflowEngine] = None,
        registry: Optional[WorkflowRegistry] = None
    ) -> Contract:
        """
        Execute contract creation workflow.
        
        Args:
            original_raw: Raw contract content
            original_format: Contract format (JSON or YAML)
            tenant_id: Tenant ID
            user_id: User ID who created the contract
            asset_id: Optional asset ID
            original_spec_type: Optional spec type (auto-detected if not provided)
            engine: Optional WorkflowEngine instance (creates new if not provided)
            registry: Optional WorkflowRegistry instance (creates new if not provided)
            
        Returns:
            Created Contract instance
            
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
        
        # Prepare workflow input
        workflow_input = {
            "original_raw": original_raw,
            "original_format": original_format,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "asset_id": asset_id,
            "original_spec_type": original_spec_type
        }
        
        # Create workflow instance
        workflow_instance = engine.create_instance(
            workflow_name=cls.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=tenant_id,
            created_by_id=user_id
        )
        
        # Start and execute workflow
        workflow_instance = engine.start_instance(str(workflow_instance.id))
        workflow_instance = engine.execute_instance(str(workflow_instance.id))
        
        # Check workflow status
        if workflow_instance.status == WorkflowStatus.COMPLETED:
            # Get contract ID from workflow state (stored during create_contract_record step)
            contract_id = workflow_instance.state_data.get("contract_id")
            if not contract_id:
                # Try output_data as fallback
                contract_id = workflow_instance.output_data.get("contract_id")
            
            if not contract_id:
                raise ValueError("Workflow completed but contract_id not found in state or output")
            
            # Refresh contract from database to ensure we have latest data
            contract = Contract.objects.get(id=contract_id)
            contract.refresh_from_db()
            logger.info(
                "Contract creation workflow completed",
                workflow_instance_id=str(workflow_instance.id),
                contract_id=contract_id
            )
            return contract
        elif workflow_instance.status == WorkflowStatus.FAILED:
            # Workflow failed - raise error with details
            error_message = workflow_instance.error_message or "Contract creation workflow failed"
            error_details = workflow_instance.error_details or {}
            
            # Extract error code if available
            error_code = error_details.get("error_code") or error_details.get("code")
            if error_code:
                raise ValueError(f"{error_code}: {error_message}")
            else:
                raise ValueError(error_message)
        else:
            # Workflow in unexpected state
            raise ValueError(
                f"Workflow ended in unexpected state: {workflow_instance.status}. "
                f"Error: {workflow_instance.error_message or 'Unknown error'}"
            )

