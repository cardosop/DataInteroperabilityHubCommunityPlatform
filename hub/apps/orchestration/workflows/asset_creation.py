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
from hub.apps.assets.business_rules import AssetsBusinessRules
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
                    "name": "infer_schema",
                    "type": "task",
                    "task": "asset_creation.infer_schema",
                    "condition": {
                        "if": "{{ file_id != null && contract_id == null }}"
                    }
                },
                {
                    "name": "generate_odcs_from_schema",
                    "type": "task",
                    "task": "asset_creation.generate_odcs_from_schema",
                    "condition": {
                        "if": "{{ schema_json != null && contract_id == null }}"
                    }
                },
                {
                    "name": "validate_generated_odcs",
                    "type": "task",
                    "task": "asset_creation.validate_generated_odcs",
                    "condition": {
                        "if": "{{ odcs_contract_json != null && contract_id == null }}"
                    }
                },
                {
                    "name": "normalize_generated_odcs",
                    "type": "task",
                    "task": "asset_creation.normalize_generated_odcs",
                    "condition": {
                        "if": "{{ odcs_contract_json != null && contract_id == null }}"
                    }
                },
                {
                    "name": "create_odcs_contract_from_schema",
                    "type": "task",
                    "task": "asset_creation.create_odcs_contract_from_schema",
                    "condition": {
                        "if": "{{ odcs_contract_json != null && hub_contract_json != null && contract_id == null }}"
                    }
                },
                {
                    "name": "create_asset_record",
                    "type": "task",
                    "task": "asset_creation.create_asset_record"
                },
                {
                    "name": "attach_contract",
                    "type": "task",
                    "task": "asset_creation.attach_contract"
                    # No condition - task will check internally if contract_id exists in state_data
                },
                {
                    "name": "create_dataset_from_file",
                    "type": "task",
                    "task": "asset_creation.create_dataset_from_file",
                    "condition": {
                        "if": "{{ file_id != null && dataset_id == null }}"
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
                    "name": "link_odps",
                    "type": "task",
                    "task": "asset_creation.link_odps",
                    "condition": {
                        "if": "{{ odps_action != null }}"
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
        engine.register_task("asset_creation.infer_schema", cls._infer_schema_task)
        engine.register_task("asset_creation.generate_odcs_from_schema", cls._generate_odcs_from_schema_task)
        engine.register_task("asset_creation.validate_generated_odcs", cls._validate_generated_odcs_task)
        engine.register_task("asset_creation.normalize_generated_odcs", cls._normalize_generated_odcs_task)
        engine.register_task("asset_creation.create_odcs_contract_from_schema", cls._create_odcs_contract_from_schema_task)
        engine.register_task("asset_creation.create_asset_record", cls._create_asset_record_task)
        engine.register_task("asset_creation.create_dataset_from_file", cls._create_dataset_from_file_task)
        engine.register_task("asset_creation.attach_contract", cls._attach_contract_task)
        engine.register_task("asset_creation.attach_dataset", cls._attach_dataset_task)
        engine.register_task("asset_creation.run_dq_checks", cls._run_dq_checks_task)
        engine.register_task("asset_creation.run_compliance_checks", cls._run_compliance_checks_task)
        engine.register_task("asset_creation.validate_contract", cls._validate_contract_task)
        engine.register_task("asset_creation.link_odps", cls._link_odps_task)
        engine.register_task("asset_creation.rollback_odps_linking", cls._rollback_odps_linking_task)
        engine.register_task("asset_creation.activate_asset", cls._activate_asset_task)
        engine.register_task("asset_creation.index_for_search", cls._index_for_search_task)
        engine.register_task("asset_creation.send_notifications", cls._send_notifications_task)
        engine.register_task("asset_creation.audit_logging", cls._audit_logging_task)

    @staticmethod
    def _infer_schema_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Infer schema from data file (Data-First flow step 2).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with inferred schema
        """
        from hub.apps.files.models import File
        from hub.apps.datasets.schema_inference import (
            infer_schema_from_csv,
            infer_schema_from_json,
            infer_schema_from_parquet
        )
        from hub.apps.files.storage import S3StorageClient

        file_id = input_data.get("file_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id

        if not file_id:
            raise ValueError("file_id is required for schema inference")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id)
        file_obj = File.objects.get(id=file_id, tenant=tenant)

        # Get file format
        file_format = input_data.get("file_format") or file_obj.content_type
        if not file_format:
            # Try to infer from file extension
            if file_obj.name:
                ext = file_obj.name.split('.')[-1].upper()
                format_map = {
                    'CSV': 'CSV',
                    'JSON': 'JSON',
                    'PARQUET': 'PARQUET',
                    'XLSX': 'XLSX',
                    'XLS': 'XLS'
                }
                file_format = format_map.get(ext, 'CSV')
            else:
                file_format = 'CSV'

        # Download file from storage
        storage_client = S3StorageClient()
        try:
            file_content = storage_client.get_file_content(file_obj.storage_path)
        except Exception as e:
            logger.error(
                "Failed to download file for schema inference",
                workflow_instance_id=str(instance.id),
                file_id=str(file_id),
                error=str(e)
            )
            raise ValueError(f"Failed to download file: {str(e)}")

        # Infer schema based on format
        schema_json = {}
        try:
            if file_format.upper() == 'CSV':
                schema_json = infer_schema_from_csv(file_content)
            elif file_format.upper() == 'JSON':
                schema_json = infer_schema_from_json(file_content)
            elif file_format.upper() == 'PARQUET':
                schema_json = infer_schema_from_parquet(file_content)
            else:
                raise ValueError(f"Unsupported file format for schema inference: {file_format}")
        except Exception as e:
            logger.error(
                "Schema inference failed",
                workflow_instance_id=str(instance.id),
                file_id=str(file_id),
                file_format=file_format,
                error=str(e),
                exc_info=True
            )
            raise ValueError(f"Schema inference failed: {str(e)}")

        # Store schema in state_data
        instance.state_data["schema_json"] = schema_json
        instance.state_data["file_id"] = str(file_id)
        instance.state_data["file_format"] = file_format
        instance.save(update_fields=['state_data'])

        logger.info(
            "Schema inferred from data",
            workflow_instance_id=str(instance.id),
            file_id=str(file_id),
            file_format=file_format,
            fields_count=len(schema_json.get('fields', []))
        )

        return {
            "schema_json": schema_json,
            "file_id": str(file_id),
            "file_format": file_format
        }

    @staticmethod
    def _generate_odcs_from_schema_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Generate ODCS contract from inferred schema (Data-First flow step 3).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with generated ODCS contract
        """
        from hub.apps.contracts.odcs_generator import generate_odcs_from_schema

        schema_json = instance.state_data.get("schema_json") or input_data.get("schema_json")
        if not schema_json:
            raise ValueError("schema_json is required (from previous step)")

        contract_id = input_data.get("contract_id")
        contract_name = input_data.get("contract_name") or input_data.get("name") or "Generated Contract from Data"
        contract_description = input_data.get("contract_description") or input_data.get("description")
        contract_version = input_data.get("contract_version", "1.0.0")
        odcs_version = input_data.get("odcs_version", "v3")

        # Generate ODCS contract
        odcs_contract = generate_odcs_from_schema(
            inferred_schema=schema_json,
            contract_id=contract_id,
            contract_name=contract_name,
            contract_description=contract_description,
            contract_version=contract_version,
            odcs_version=odcs_version
        )

        # Store ODCS contract in state_data
        instance.state_data["odcs_contract_json"] = odcs_contract
        instance.state_data["odcs_contract_id"] = odcs_contract.get("id")
        instance.save(update_fields=['state_data'])

        logger.info(
            "ODCS contract generated from schema",
            workflow_instance_id=str(instance.id),
            contract_id=odcs_contract.get("id"),
            fields_count=len(odcs_contract.get("schema", {}).get("fields", []))
        )

        return {
            "odcs_contract_json": odcs_contract,
            "odcs_contract_id": odcs_contract.get("id")
        }

    @staticmethod
    def _validate_generated_odcs_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate generated ODCS contract (Data-First flow step 4).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validation status
        """
        from hub.apps.contracts.normalization import parse_contract
        from hub.apps.contracts.models import OriginalFormat

        odcs_contract_json = instance.state_data.get("odcs_contract_json")
        if not odcs_contract_json:
            raise ValueError("odcs_contract_json is required (from previous step)")

        # Convert to JSON string for validation
        import json
        odcs_raw = json.dumps(odcs_contract_json)

        # Parse and validate ODCS contract
        try:
            parsed_contract = parse_contract(odcs_raw, OriginalFormat.JSON)
            # Basic validation - check required fields
            if not parsed_contract.get("id"):
                raise ValueError("ODCS contract missing required field: id")
            if not parsed_contract.get("name"):
                raise ValueError("ODCS contract missing required field: name")
            if not parsed_contract.get("schema"):
                raise ValueError("ODCS contract missing required field: schema")

            validation_status = "VALID"
            validation_errors = []
        except Exception as e:
            validation_status = "INVALID"
            validation_errors = [str(e)]
            logger.error(
                "ODCS contract validation failed",
                workflow_instance_id=str(instance.id),
                error=str(e),
                exc_info=True
            )
            raise ValueError(f"ODCS contract validation failed: {str(e)}")

        # Store validation status in state_data
        instance.state_data["odcs_validation_status"] = validation_status
        instance.state_data["odcs_validation_errors"] = validation_errors
        instance.save(update_fields=['state_data'])

        logger.info(
            "ODCS contract validated",
            workflow_instance_id=str(instance.id),
            validation_status=validation_status
        )

        return {
            "validation_status": validation_status,
            "validation_errors": validation_errors
        }

    @staticmethod
    def _normalize_generated_odcs_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Normalize generated ODCS → HubContract (Data-First flow step 5).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with normalized HubContract
        """
        from hub.apps.contracts.normalization import normalize_contract
        from hub.apps.contracts.models import OriginalSpecType, OriginalFormat

        odcs_contract_json = instance.state_data.get("odcs_contract_json")
        if not odcs_contract_json:
            raise ValueError("odcs_contract_json is required (from previous step)")

        # Track ODCS ingestion (Task 6.2.2 - explicit backward compatibility)
        try:
            from hub.apps.observability.otel_metrics import odcs_ingestion_total
            tenant_id = getattr(instance, 'tenant_id', None) or 'unknown'
            odcs_ingestion_total.labels(source='technical', tenant_id=tenant_id).inc()
        except Exception:
            pass  # Metrics failure should not affect workflow

        # Convert to JSON string for normalization
        import json
        odcs_raw = json.dumps(odcs_contract_json)

        # Normalize ODCS → HubContract
        try:
            # normalize_contract returns: (hub_contract, spec_type, spec_version, status, errors, warnings)
            hub_contract, detected_spec_type, detected_spec_version, status, errors, warnings = normalize_contract(
                raw_contract=odcs_raw,
                format="JSON",
                spec_type=OriginalSpecType.ODCS.value
            )

            if status.value == "NORMALIZATION_FAILED":
                error_text = "; ".join(errors) if errors else "Unknown normalization error"
                raise ValueError(f"ODCS normalization failed: {error_text}")

            if not hub_contract:
                raise ValueError("Normalization succeeded but hub_contract is None")

        except Exception as e:
            logger.error(
                "ODCS normalization failed",
                workflow_instance_id=str(instance.id),
                error=str(e),
                exc_info=True
            )
            raise ValueError(f"ODCS normalization failed: {str(e)}")

        # Store HubContract in state_data
        instance.state_data["hub_contract_json"] = hub_contract
        instance.state_data["normalization_status"] = status.value
        instance.state_data["normalization_errors"] = errors
        instance.state_data["normalization_warnings"] = warnings
        instance.save(update_fields=['state_data'])

        logger.info(
            "ODCS contract normalized to HubContract",
            workflow_instance_id=str(instance.id),
            normalization_status=status.value,
            errors_count=len(errors),
            warnings_count=len(warnings)
        )

        return {
            "hub_contract_json": hub_contract,
            "normalization_status": status.value,
            "normalization_errors": errors,
            "normalization_warnings": warnings
        }

    @staticmethod
    @transaction.atomic
    def _create_odcs_contract_from_schema_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create ODCS Contract record from generated contract (Data-First flow step 6).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with created contract ID
        """
        from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat, NormalizationStatus
        from django.contrib.auth import get_user_model
        import json

        User = get_user_model()

        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        odcs_contract_json = instance.state_data.get("odcs_contract_json")
        hub_contract_json = instance.state_data.get("hub_contract_json")
        normalization_status = instance.state_data.get("normalization_status", "NORMALIZED_OK")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not odcs_contract_json:
            raise ValueError("odcs_contract_json is required (from previous step)")
        if not hub_contract_json:
            raise ValueError("hub_contract_json is required (from previous step)")

        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id)
        user_id = instance.created_by_id or input_data.get("created_by_id")
        user = User.objects.get(id=user_id) if user_id else None

        # Convert ODCS contract to string for storage
        odcs_raw = json.dumps(odcs_contract_json, indent=2)

        # Determine ODCS version from contract
        odcs_version = odcs_contract_json.get("apiVersion", "odcs/v3").split("/")[-1] if odcs_contract_json.get("apiVersion") else "3.0.2"

        # Create ODCS contract record (asset will be set later in attach_contract step)
        contract = Contract.objects.create(
            tenant=tenant,
            asset=None,  # Will be set when asset is created and attached
            version=1,  # Will be updated when attached to asset
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version=odcs_version,
            original_format=OriginalFormat.JSON,
            original_raw=odcs_raw,
            hub_contract_version="1.0.0",
            hub_contract_json=hub_contract_json,
            normalization_status=NormalizationStatus(normalization_status) if normalization_status else NormalizationStatus.NORMALIZED_OK,
            normalization_errors=instance.state_data.get("normalization_errors", []),
            normalization_warnings=instance.state_data.get("normalization_warnings", []),
            created_by=user
        )

        # Store contract_id in state_data
        instance.state_data["contract_id"] = str(contract.id)
        instance.save(update_fields=['state_data'])

        logger.info(
            "ODCS contract created from schema",
            workflow_instance_id=str(instance.id),
            contract_id=str(contract.id),
            odcs_version=odcs_version
        )

        return {
            "contract_id": str(contract.id),
            "contract_version": contract.version,
            "normalization_status": normalization_status
        }

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

        # Validate required fields before creation
        if not key or not name:
            raise ValueError("Asset key and name are required")

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

        # Validate created asset using AssetsBusinessRules
        assets_rules = AssetsBusinessRules(
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(created_by_id) if created_by_id else None
        )

        asset_validation_result = assets_rules.validate(
            asset=asset,
            tenant=tenant,
            user=created_by,
            validation_type="all"
        )

        if not asset_validation_result.is_valid:
            error_messages = asset_validation_result.errors
            # Log errors but don't fail - asset is already created
            logger.warning(
                "Asset validation warnings after creation",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                warnings=asset_validation_result.warnings,
                errors=error_messages,
            )
        elif asset_validation_result.warnings:
            logger.warning(
                "Asset validation warnings",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                warnings=asset_validation_result.warnings,
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
    @transaction.atomic
    def _create_dataset_from_file_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create dataset from file and link to asset (Data-First flow step 9).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with dataset_id
        """
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.datasets.schema_inference import (
            infer_schema_from_csv,
            infer_schema_from_json,
            infer_schema_from_parquet
        )
        from hub.apps.files.storage import S3StorageClient

        asset_id = instance.state_data.get("asset_id")
        file_id = instance.state_data.get("file_id") or input_data.get("file_id")
        file_format = instance.state_data.get("file_format") or input_data.get("file_format")
        schema_json = instance.state_data.get("schema_json")

        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not file_id:
            raise ValueError("file_id is required for dataset creation")

        asset = Asset.objects.get(id=asset_id)
        file_obj = File.objects.get(id=file_id, tenant=asset.tenant)

        # Determine file format if not provided
        if not file_format:
            format_map = {
                'text/csv': 'CSV',
                'application/csv': 'CSV',
                'application/json': 'JSON',
                'text/json': 'JSON',
                'application/parquet': 'PARQUET',
                'application/x-parquet': 'PARQUET',
            }
            file_format = format_map.get(file_obj.content_type, 'CSV')

            # Infer from filename if still not determined
            if file_format == 'CSV' and file_obj.name:
                filename_lower = file_obj.name.lower()
                if filename_lower.endswith('.json') or filename_lower.endswith('.ndjson'):
                    file_format = 'JSON'
                elif filename_lower.endswith('.parquet'):
                    file_format = 'PARQUET'

        # Infer schema if not already inferred
        if not schema_json:
            storage_client = S3StorageClient()
            try:
                file_content = storage_client.get_file_content(file_obj.storage_path)
            except Exception as e:
                logger.error(
                    "Failed to download file for schema inference",
                    workflow_instance_id=str(instance.id),
                    file_id=str(file_id),
                    error=str(e)
                )
                raise ValueError(f"Failed to download file: {str(e)}")

            # Infer schema based on format
            try:
                if file_format.upper() == 'CSV':
                    schema_json = infer_schema_from_csv(file_content)
                elif file_format.upper() == 'JSON':
                    schema_json = infer_schema_from_json(file_content)
                elif file_format.upper() == 'PARQUET':
                    schema_json = infer_schema_from_parquet(file_content)
                else:
                    schema_json = {"fields": []}
            except Exception as e:
                logger.warning(
                    "Schema inference failed, creating dataset without schema",
                    workflow_instance_id=str(instance.id),
                    file_id=str(file_id),
                    error=str(e)
                )
                schema_json = {"fields": []}

        # Get next version for asset
        latest_dataset = asset.datasets.order_by('-version').first()
        next_version = latest_dataset.version + 1 if latest_dataset else 1

        # Create dataset
        user_id = instance.created_by_id or input_data.get("created_by_id")
        from hub.apps.users.models import User
        created_by = User.objects.get(id=user_id) if user_id else None

        dataset = Dataset.objects.create(
            tenant=asset.tenant,
            asset=asset,
            file=file_obj,
            version=next_version,
            format=file_format,
            is_current=True,
            created_by=created_by,
            schema_json=schema_json
        )

        # Store dataset_id in state_data
        instance.state_data["dataset_id"] = str(dataset.id)
        instance.save(update_fields=['state_data'])

        logger.info(
            "Dataset created from file",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            dataset_id=str(dataset.id),
            file_id=str(file_id),
            version=next_version
        )

        return {
            "dataset_id": str(dataset.id),
            "dataset_version": next_version,
            "file_id": str(file_id)
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
        # Get contract_id from state_data (for data-first flow) or input_data (for contract-first flow)
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")

        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not contract_id:
            # Skip if contract_id not provided
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
            error_str = str(e)
            # When DQ service is unavailable (e.g. in tests without dq-service-test),
            # skip DQ checks instead of failing the workflow (matches scheduled_ingestion behavior)
            if "DQ service is unavailable" in error_str or "Connection refused" in error_str:
                logger.warning(
                    "DQ service unavailable, skipping DQ checks",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    error=error_str
                )
                asset.dq_status = DQStatus.UNKNOWN
                asset.save(update_fields=['dq_status'])
                instance.state_data["dq_status"] = asset.dq_status
                instance.save(update_fields=['state_data'])
                return {"skipped": True, "reason": "DQ service unavailable", "dq_status": asset.dq_status}
            logger.error(
                "Failed to run DQ checks",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                error=error_str
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
    @transaction.atomic
    def _link_odps_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Link ODPS contract (optional step for marketplace).

        Supports three modes:
        1. upload: Parse and validate uploaded ODPS, create ODPS contract, link it
        2. generate: Generate ODPS from HubContract, create ODPS contract, link it
        3. link: Link to existing ODPS contract by ID

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with ODPS contract ID and linking results
        """
        from hub.apps.contracts.odps_parser import ODPSParser
        from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract
        from hub.apps.contracts.linking_validation import validate_linking
        from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat, NormalizationStatus
        from hub.apps.contracts.normalization import parse_contract
        from hub.apps.contracts.odps_version_detection import detect_odps_version
        from django.contrib.auth import get_user_model
        import json

        User = get_user_model()

        # Get asset_id from state_data
        asset_id = instance.state_data.get("asset_id")
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")

        asset = Asset.objects.get(id=asset_id)
        tenant_id = str(asset.tenant_id)
        user_id = instance.created_by_id or input_data.get("created_by_id")
        user = User.objects.get(id=user_id) if user_id else None

        # Get ODPS action from input_data
        odps_action = input_data.get("odps_action")
        if not odps_action or odps_action not in ["upload", "generate", "link"]:
            # Skip if no ODPS action specified
            logger.info(
                "ODPS linking skipped (no action specified)",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {
                "odps_linking_skipped": True,
                "reason": "No ODPS action specified"
            }

        # Get contract_id from state_data if available (for data-first flow)
        # Also check if contract is already attached to asset (for contract-first flow)
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")
        contract = None

        # First, try to get contract from contract_id
        if contract_id:
            try:
                contract = Contract.objects.get(id=contract_id, tenant=asset.tenant)
            except Contract.DoesNotExist:
                logger.warning(
                    "Contract not found for ODPS linking",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id
                )

        # If no contract found by ID, try to get from asset's contracts
        if not contract:
            # Try to get ODCS contract from asset (for data-first flow where contract was just created)
            odcs_contract = asset.contracts.filter(
                original_spec_type=OriginalSpecType.ODCS
            ).order_by('-version').first()
            if odcs_contract:
                contract = odcs_contract
                contract_id = str(contract.id)
                logger.info(
                    "Using ODCS contract from asset for ODPS linking",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    contract_id=contract_id
                )

        odps_contract = None
        odps_contract_id = None

        try:
            if odps_action == "upload":
                # Parse and validate uploaded ODPS
                odps_raw = input_data.get("odps_raw")
                odps_format = input_data.get("odps_format", "JSON")

                if not odps_raw:
                    raise ValueError("odps_raw is required for ODPS upload")

                # Parse ODPS
                odps_doc = ODPSParser.parse(odps_raw, format=odps_format.lower())

                # Detect version
                odps_version = detect_odps_version(odps_doc) or "4.1"

                # Validate ODPS
                is_valid, validation_errors = ODPSParser.validate(odps_doc, version=odps_version)
                if not is_valid:
                    raise ValueError(f"ODPS validation failed: {validation_errors}")

                # Normalize ODPS to HubContract
                from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
                normalizer = ODPSNormalizer()
                normalize_result = normalizer.normalize(contract_data=odps_doc, spec_version=odps_version)
                hub_contract_from_odps = normalize_result.hub_contract

                # Get next version for asset
                latest_contract = asset.contracts.order_by('-version').first()
                next_version = latest_contract.version + 1 if latest_contract else 1

                # Create ODPS contract record
                odps_contract = Contract.objects.create(
                    tenant=asset.tenant,
                    asset=asset,
                    version=next_version,
                    status=ContractStatus.DRAFT,
                    original_spec_type=OriginalSpecType.ODPS,
                    original_spec_version=odps_version,
                    original_format=OriginalFormat.JSON if odps_format.upper() == "JSON" else OriginalFormat.YAML,
                    original_raw=odps_raw,
                    hub_contract_version="1.0.0",
                    hub_contract_json=hub_contract_from_odps,
                    normalization_status=NormalizationStatus.NORMALIZED_OK,
                    normalization_errors=[],
                    normalization_warnings=[],
                    created_by=user
                )
                odps_contract_id = str(odps_contract.id)

                logger.info(
                    "ODPS contract created from upload",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    odps_contract_id=odps_contract_id
                )

            elif odps_action == "generate":
                # Generate ODPS from HubContract
                if not contract:
                    raise ValueError("No contract available. Cannot generate ODPS from HubContract.")
                if not contract.hub_contract_json:
                    raise ValueError("Contract has no hub_contract_json. Cannot generate ODPS.")

                # Get original ODCS contract if available (for embedding in ODPS)
                original_odcs_contract = None
                if contract.original_raw and contract.original_spec_type == OriginalSpecType.ODCS:
                    try:
                        original_odcs_contract = parse_contract(
                            contract.original_raw, contract.original_format
                        )
                    except Exception:
                        # If parsing fails, continue without original ODCS
                        pass

                # Generate ODPS document
                odps_doc = generate_odps_from_hubcontract(
                    hub_contract=contract.hub_contract_json,
                    target_version="4.1",
                    original_odcs_contract=original_odcs_contract,
                    original_odcs_url=None,
                )

                # Format as JSON for storage
                odps_raw = json.dumps(odps_doc, indent=2)

                # Get next version for asset
                latest_contract = asset.contracts.order_by('-version').first()
                next_version = latest_contract.version + 1 if latest_contract else 1

                # Create ODPS contract record
                odps_contract = Contract.objects.create(
                    tenant=asset.tenant,
                    asset=asset,
                    version=next_version,
                    status=ContractStatus.DRAFT,
                    original_spec_type=OriginalSpecType.ODPS,
                    original_spec_version="4.1",
                    original_format=OriginalFormat.JSON,
                    original_raw=odps_raw,
                    hub_contract_version="1.0.0",
                    hub_contract_json=contract.hub_contract_json,  # Use same HubContract
                    normalization_status=NormalizationStatus.NORMALIZED_OK,
                    normalization_errors=[],
                    normalization_warnings=[],
                    created_by=user
                )
                odps_contract_id = str(odps_contract.id)

                logger.info(
                    "ODPS contract generated from HubContract",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    odps_contract_id=odps_contract_id
                )

            elif odps_action == "link":
                # Link to existing ODPS contract
                existing_odps_contract_id = input_data.get("odps_contract_id")
                if not existing_odps_contract_id:
                    raise ValueError("odps_contract_id is required for ODPS linking")

                # Get existing ODPS contract
                try:
                    existing_odps_contract = Contract.objects.get(
                        id=existing_odps_contract_id,
                        tenant=asset.tenant,
                        original_spec_type=OriginalSpecType.ODPS
                    )
                except Contract.DoesNotExist:
                    raise ValueError(f"ODPS contract {existing_odps_contract_id} not found or not an ODPS contract")

                # If there's an ODCS contract, validate linking
                if contract:
                    validate_linking(
                        odps_contract_id=existing_odps_contract_id,
                        odcs_contract_id=str(contract.id),
                        tenant_id=tenant_id
                    )

                # Attach ODPS contract to asset
                existing_odps_contract.asset = asset
                # Get next version for asset
                latest_contract = asset.contracts.order_by('-version').first()
                if latest_contract:
                    existing_odps_contract.version = latest_contract.version + 1
                else:
                    existing_odps_contract.version = 1
                existing_odps_contract.save(update_fields=['asset', 'version'])

                odps_contract = existing_odps_contract
                odps_contract_id = str(odps_contract.id)

                logger.info(
                    "ODPS contract validated for linking",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    odps_contract_id=odps_contract_id
                )

            # Establish bidirectional link if both ODPS and ODCS contracts exist
            if odps_contract and contract:
                # ODPS → ODCS: Store in ODPS contract's hub_contract_json.extensions.x_odps.odcs_link
                if odps_contract.hub_contract_json:
                    if "extensions" not in odps_contract.hub_contract_json:
                        odps_contract.hub_contract_json["extensions"] = {}
                    if "x_odps" not in odps_contract.hub_contract_json["extensions"]:
                        odps_contract.hub_contract_json["extensions"]["x_odps"] = {}
                    odps_contract.hub_contract_json["extensions"]["x_odps"]["odcs_link"] = str(contract.id)
                    odps_contract.save(update_fields=["hub_contract_json"])

                # ODCS → ODPS: Store in ODCS contract's hub_contract_json.extensions.x_odps.odps_link
                if contract.hub_contract_json:
                    if "extensions" not in contract.hub_contract_json:
                        contract.hub_contract_json["extensions"] = {}
                    if "x_odps" not in contract.hub_contract_json["extensions"]:
                        contract.hub_contract_json["extensions"]["x_odps"] = {}
                    contract.hub_contract_json["extensions"]["x_odps"]["odps_link"] = odps_contract_id
                    contract.save(update_fields=["hub_contract_json"])

                logger.info(
                    "ODPS-ODCS contracts linked bidirectionally",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    contract_id=str(contract.id),
                    odps_contract_id=odps_contract_id,
                    action=odps_action
                )

            # Publish ODPS events
            from hub.apps.core.events.service_publishers import ODPSEventPublisher
            # Create ODPSEventPublisher instance with tenant_id and user_id
            # ODPSEventPublisher uses getattr to get tenant_id and user_id in __init__
            class TempODPSEventPublisher(ODPSEventPublisher):
                pass

            odps_event_publisher = TempODPSEventPublisher()
            odps_event_publisher.tenant_id = tenant_id
            odps_event_publisher.user_id = str(user_id) if user_id else None
            # Re-initialize _event_publisher with correct tenant/user
            from hub.apps.core.events.publisher import EventPublisher
            odps_event_publisher._event_publisher = EventPublisher(
                service_name="contract_service",
                tenant_id=tenant_id,
                user_id=str(user_id) if user_id else None,
            )

            # Publish ODPS created event (if this is a new contract from upload or generate)
            if odps_contract and odps_contract_id and odps_action in ["upload", "generate"]:
                # Get original_format as string
                original_format_str = None
                if odps_contract.original_format:
                    if hasattr(odps_contract.original_format, 'value'):
                        original_format_str = odps_contract.original_format.value
                    elif isinstance(odps_contract.original_format, str):
                        original_format_str = odps_contract.original_format
                    else:
                        original_format_str = str(odps_contract.original_format)

                odps_event_publisher.publish_odps_created(
                    contract_id=odps_contract_id,
                    asset_id=str(asset.id),
                    status=odps_contract.status,
                    odps_version=odps_contract.original_spec_version,
                    original_format=original_format_str
                )

            # Publish ODPS linked event (if both contracts exist)
            if odps_contract and odps_contract_id and contract:
                odps_event_publisher.publish_odps_linked(
                    odps_contract_id=odps_contract_id,
                    odcs_contract_id=str(contract.id),
                    link_type="bidirectional"
                )

            # Store ODPS contract ID and action in state_data for compensation
            instance.state_data["odps_contract_id"] = odps_contract_id
            instance.state_data["odps_action"] = odps_action
            if contract:
                instance.state_data["contract_id"] = str(contract.id)
            instance.save(update_fields=['state_data'])

            return {
                "odps_linked": True,
                "odps_contract_id": odps_contract_id,
                "action": odps_action,
                "state": {
                    "odps_contract_id": odps_contract_id
                }
            }

        except Exception as e:
            logger.error(
                "ODPS linking failed",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                action=odps_action,
                error=str(e),
                exc_info=True
            )
            raise ValueError(f"ODPS linking failed: {str(e)}")

    @staticmethod
    @transaction.atomic
    def _rollback_odps_linking_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Rollback ODPS linking (remove links and delete created ODPS contract if needed).

        This compensation task is called when a subsequent step fails and the workflow
        needs to rollback the ODPS linking operation.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with rollback status
        """
        from hub.apps.contracts.models import Contract

        # Get ODPS linking information from state_data
        contract_id = instance.state_data.get("contract_id")
        odps_contract_id = instance.state_data.get("odps_contract_id")
        odps_action = instance.state_data.get("odps_action")

        # Remove ODPS link from ODCS contract
        if contract_id:
            try:
                contract = Contract.objects.get(id=contract_id)
                # Remove ODPS link from contract
                if contract.hub_contract_json and "extensions" in contract.hub_contract_json:
                    x_odps = contract.hub_contract_json["extensions"].get("x_odps", {})
                    if "odps_link" in x_odps:
                        del x_odps["odps_link"]
                        contract.save(update_fields=["hub_contract_json"])
                        logger.info(
                            "ODPS link removed from ODCS contract during rollback",
                            workflow_instance_id=str(instance.id),
                            contract_id=contract_id
                        )
            except Contract.DoesNotExist:
                logger.warning(
                    "ODCS contract not found during ODPS linking rollback",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id
                )

        # Remove ODCS link from ODPS contract and delete if created during workflow
        if odps_contract_id:
            try:
                odps_contract = Contract.objects.get(id=odps_contract_id)
                # Remove ODCS link from ODPS contract
                if odps_contract.hub_contract_json and "extensions" in odps_contract.hub_contract_json:
                    x_odps = odps_contract.hub_contract_json["extensions"].get("x_odps", {})
                    if "odcs_link" in x_odps:
                        del x_odps["odcs_link"]
                        odps_contract.save(update_fields=["hub_contract_json"])

                # If ODPS contract was created during this workflow (upload or generate), delete it
                if odps_action in ["upload", "generate"]:
                    odps_contract.delete()
                    logger.info(
                        "ODPS contract rolled back (deleted)",
                        workflow_instance_id=str(instance.id),
                        odps_contract_id=odps_contract_id
                    )
                else:
                    # For "link" action, just remove the link but keep the contract
                    logger.info(
                        "ODPS link removed from existing ODPS contract during rollback",
                        workflow_instance_id=str(instance.id),
                        odps_contract_id=odps_contract_id
                    )
            except Contract.DoesNotExist:
                logger.warning(
                    "ODPS contract not found during rollback",
                    workflow_instance_id=str(instance.id),
                    odps_contract_id=odps_contract_id
                )

        logger.info(
            "ODPS linking rolled back",
            workflow_instance_id=str(instance.id),
            contract_id=contract_id,
            odps_contract_id=odps_contract_id,
            odps_action=odps_action
        )

        return {"rolled_back": True}

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

        # Validate asset lifecycle transition using AssetsBusinessRules
        tenant_id = str(asset.tenant_id) if asset.tenant_id else None
        user_id = str(instance.created_by_id) if instance.created_by_id else None

        assets_rules = AssetsBusinessRules(
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Validate status transition
        old_status = asset.status
        new_status = AssetStatus.ACTIVE

        lifecycle_validation_result = assets_rules.validate(
            asset=asset,
            tenant=asset.tenant,
            user=instance.created_by,
            validation_type="lifecycle",
            old_status=old_status,
            new_status=new_status
        )

        if not lifecycle_validation_result.is_valid:
            error_messages = lifecycle_validation_result.errors
            raise ValueError(
                f"Asset activation validation failed: {'; '.join(error_messages)}"
            )

        # Log validation warnings if any
        if lifecycle_validation_result.warnings:
            logger.warning(
                "Asset activation validation warnings",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                warnings=lifecycle_validation_result.warnings,
            )

        # Activate asset
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
        file_id: Optional[str] = None,
        file_format: Optional[str] = None,
        odps_action: Optional[str] = None,
        odps_raw: Optional[str] = None,
        odps_format: str = "JSON",
        odps_contract_id: Optional[str] = None,
        contract_name: Optional[str] = None,
        contract_description: Optional[str] = None,
        contract_version: str = "1.0.0",
        odcs_version: str = "v3",
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
            file_id: File ID for data-first flow (optional, required for data-first flow)
            file_format: File format: "CSV", "JSON", "PARQUET" (optional, auto-detected if not provided)
            odps_action: ODPS action: "upload", "generate", or "link" (optional, for marketplace)
            odps_raw: ODPS document content (required if odps_action="upload")
            odps_format: ODPS format: "JSON" or "YAML" (default: "JSON", used if odps_action="upload")
            odps_contract_id: Existing ODPS contract ID (required if odps_action="link")
            contract_name: Contract name for generated ODCS (optional, used in data-first flow)
            contract_description: Contract description for generated ODCS (optional, used in data-first flow)
            contract_version: Contract version for generated ODCS (default: "1.0.0", used in data-first flow)
            odcs_version: ODCS version for generated contract (default: "v3", used in data-first flow)
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
        # Only include non-None values to avoid condition evaluation issues
        workflow_input = {
            "tenant_id": tenant_id,
            "key": key,
            "name": name,
        }
        if description is not None:
            workflow_input["description"] = description
        if domain is not None:
            workflow_input["domain"] = domain
        if visibility is not None:
            workflow_input["visibility"] = visibility
        if contract_id is not None:
            workflow_input["contract_id"] = contract_id
        if dataset_id is not None:
            workflow_input["dataset_id"] = dataset_id
        if file_id is not None:
            workflow_input["file_id"] = file_id
        if file_format is not None:
            workflow_input["file_format"] = file_format
        if profile_key is not None:
            workflow_input["profile_key"] = profile_key
        if scan_mode is not None:
            workflow_input["scan_mode"] = scan_mode
        workflow_input["applicable_regulations"] = applicable_regulations or []
        workflow_input["auto_activate"] = auto_activate
        workflow_input["send_notifications"] = send_notifications
        if created_by_id is not None:
            workflow_input["created_by_id"] = created_by_id
        if odps_action is not None:
            workflow_input["odps_action"] = odps_action
        if odps_raw is not None:
            workflow_input["odps_raw"] = odps_raw
        if odps_format is not None:
            workflow_input["odps_format"] = odps_format
        if odps_contract_id is not None:
            workflow_input["odps_contract_id"] = odps_contract_id
        if contract_name is not None:
            workflow_input["contract_name"] = contract_name
        if contract_description is not None:
            workflow_input["contract_description"] = contract_description
        if contract_version is not None:
            workflow_input["contract_version"] = contract_version
        if odcs_version is not None:
            workflow_input["odcs_version"] = odcs_version

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

