"""
Contract Creation Workflow

Orchestrates the contract creation process with proper error handling,
retry logic, and compensation.
"""

from typing import Any

import structlog
from django.db import transaction

from hub.apps.audit.utils import create_audit_event
from hub.apps.contracts.business_rules import ContractsBusinessRules
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalSpecType,
)
from hub.apps.contracts.normalization import normalize_contract, validate_hubcontract_schema
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.search.indexing import SearchIndexer
from hub.apps.semantic.utils import map_contract_to_semantic

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
                    "task": "contract_creation.validate_input",
                },
                {
                    "name": "normalize_contract",
                    "type": "task",
                    "task": "contract_creation.normalize_contract",
                    "compensation": {
                        "type": "task",
                        "task": "contract_creation.rollback_normalization",
                    },
                },
                {
                    "name": "validate_hubcontract",
                    "type": "task",
                    "task": "contract_creation.validate_hubcontract",
                    "compensation": {
                        "type": "task",
                        "task": "contract_creation.rollback_validation",
                    },
                },
                {
                    "name": "create_contract_record",
                    "type": "task",
                    "task": "contract_creation.create_contract_record",
                    "compensation": {
                        "type": "task",
                        "task": "contract_creation.rollback_contract_record",
                    },
                },
                {
                    "name": "link_odps",
                    "type": "task",
                    "task": "contract_creation.link_odps",
                    "compensation": {
                        "type": "task",
                        "task": "contract_creation.rollback_odps_linking",
                    },
                },
                {
                    "name": "link_data_file",
                    "type": "task",
                    "task": "contract_creation.link_data_file",
                    "compensation": {
                        "type": "task",
                        "task": "contract_creation.rollback_link_data_file",
                    },
                },
                {
                    "name": "index_for_search",
                    "type": "task",
                    "task": "contract_creation.index_for_search",
                    "compensation": {"type": "task", "task": "contract_creation.rollback_indexing"},
                },
                {
                    "name": "generate_semantic_mapping",
                    "type": "task",
                    "task": "contract_creation.generate_semantic_mapping",
                },
                {
                    "name": "send_notifications",
                    "type": "task",
                    "task": "contract_creation.send_notifications",
                },
                {
                    "name": "audit_logging",
                    "type": "task",
                    "task": "contract_creation.audit_logging",
                },
            ],
            "compensation": {"enabled": True},
        }

        registry.register_workflow(
            workflow_name=cls.WORKFLOW_NAME,
            dsl_json=workflow_dsl,
            description="Orchestrates contract creation with validation, normalization, indexing, and notifications",
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
        engine.register_task(
            "contract_creation.validate_hubcontract", cls._validate_hubcontract_task
        )
        engine.register_task(
            "contract_creation.create_contract_record", cls._create_contract_record_task
        )
        engine.register_task("contract_creation.index_for_search", cls._index_for_search_task)
        engine.register_task(
            "contract_creation.generate_semantic_mapping", cls._generate_semantic_mapping_task
        )
        engine.register_task("contract_creation.send_notifications", cls._send_notifications_task)
        engine.register_task("contract_creation.audit_logging", cls._audit_logging_task)

        # ODPS and data file linking tasks
        engine.register_task("contract_creation.link_odps", cls._link_odps_task)
        engine.register_task("contract_creation.link_data_file", cls._link_data_file_task)

        # Compensation tasks
        engine.register_task(
            "contract_creation.rollback_normalization", cls._rollback_normalization_task
        )
        engine.register_task("contract_creation.rollback_validation", cls._rollback_validation_task)
        engine.register_task(
            "contract_creation.rollback_contract_record", cls._rollback_contract_record_task
        )
        engine.register_task(
            "contract_creation.rollback_odps_linking", cls._rollback_odps_linking_task
        )
        engine.register_task(
            "contract_creation.rollback_link_data_file", cls._rollback_link_data_file_task
        )
        engine.register_task("contract_creation.rollback_indexing", cls._rollback_indexing_task)

    @staticmethod
    def _validate_input_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
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

        # Validate contract creation using ContractsBusinessRules
        contracts_rules = ContractsBusinessRules(
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(user_id) if user_id else None,
        )

        # Prepare contract data for validation
        contract_data = {
            "tenant_id": str(tenant_id),
            "original_raw": original_raw,
            "original_format": original_format,
            "original_spec_type": input_data.get("original_spec_type") or "ODCS",
        }

        # Validate contract creation
        contract_validation_result = contracts_rules.validate_contract_creation(contract_data)
        if not contract_validation_result.is_valid:
            error_messages = contract_validation_result.errors
            raise ValueError(f"Contract input validation failed: {'; '.join(error_messages)}")

        # Log validation warnings if any
        if contract_validation_result.warnings:
            logger.warning(
                "Contract input validation warnings",
                workflow_instance_id=str(instance.id),
                tenant_id=tenant_id,
                warnings=contract_validation_result.warnings,
            )

        logger.info(
            "Contract input validated",
            workflow_instance_id=str(instance.id),
            tenant_id=tenant_id,
            format=original_format,
        )

        return {
            "validated": True,
            "original_raw": original_raw,
            "original_format": original_format,
            "tenant_id": tenant_id,
            "user_id": user_id,
        }

    @staticmethod
    def _normalize_contract_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
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
        (
            hub_contract,
            detected_spec_type,
            detected_spec_version,
            norm_status,
            norm_errors,
            norm_warnings,
        ) = normalize_contract(
            raw_contract=original_raw, format=original_format, spec_type=original_spec_type
        )

        # Check for critical errors (parsing errors or any normalization failure)
        if norm_status == NormalizationStatus.NORMALIZATION_FAILED:
            if norm_errors:
                parsing_errors = [
                    e
                    for e in norm_errors
                    if any(
                        keyword in e.lower()
                        for keyword in [
                            "parsing failed",
                            "jsondecodeerror",
                            "yamlerror",
                            "failed to normalize contract",
                        ]
                    )
                ]

                if parsing_errors:
                    error_code = "INVALID_SPEC_FORMAT"
                    raise ValueError(f"{error_code}: {norm_errors[0]}")
                else:
                    # Generic normalization failure
                    raise ValueError(
                        f"INVALID_SPEC_FORMAT: {norm_errors[0] if norm_errors else 'Contract normalization failed'}"
                    )
            else:
                # Normalization failed but no error messages (shouldn't happen, but handle gracefully)
                raise ValueError("INVALID_SPEC_FORMAT: Contract normalization failed")

        logger.info(
            "Contract normalized",
            workflow_instance_id=str(instance.id),
            spec_type=detected_spec_type,
            spec_version=detected_spec_version,
            status=norm_status.value,
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
                "normalization_status": norm_status.value,
            },
        }

    @staticmethod
    def _validate_hubcontract_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
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
            return {"validation_skipped": True, "reason": "No hub_contract to validate"}

        # Validate HubContract schema
        is_valid, validation_errors = validate_hubcontract_schema(hub_contract)

        if not is_valid:
            # Update normalization status to failed
            return {
                "validation_passed": False,
                "validation_errors": validation_errors,
                "normalization_status": NormalizationStatus.NORMALIZATION_FAILED.value,
            }

        logger.info("HubContract validated", workflow_instance_id=str(instance.id), valid=True)

        return {"validation_passed": True, "validation_errors": []}

    @staticmethod
    @transaction.atomic
    def _create_contract_record_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Create contract record in database.

        Args:
            input_data: Workflow input data (includes validation results)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with contract ID
        """
        from django.contrib.auth import get_user_model

        from hub.apps.tenants.models import Tenant

        User = get_user_model()

        # Get data from state_data (which accumulates from previous steps) or input_data
        tenant_id = instance.state_data.get("tenant_id") or input_data.get("tenant_id")
        user_id = instance.state_data.get("user_id") or input_data.get("user_id")
        asset_id = instance.state_data.get("asset_id") or input_data.get("asset_id")
        original_raw = instance.state_data.get("original_raw") or input_data.get("original_raw")
        original_format = instance.state_data.get("original_format") or input_data.get(
            "original_format"
        )
        original_spec_type = instance.state_data.get("original_spec_type") or input_data.get(
            "original_spec_type"
        )
        detected_spec_type = instance.state_data.get("detected_spec_type") or input_data.get(
            "detected_spec_type"
        )
        detected_spec_version = instance.state_data.get("detected_spec_version") or input_data.get(
            "detected_spec_version"
        )
        hub_contract = instance.state_data.get("hub_contract") or input_data.get("hub_contract")
        normalization_status_str = instance.state_data.get(
            "normalization_status"
        ) or input_data.get("normalization_status")
        normalization_errors = instance.state_data.get(
            "normalization_errors", []
        ) or input_data.get("normalization_errors", [])
        normalization_warnings = instance.state_data.get(
            "normalization_warnings", []
        ) or input_data.get("normalization_warnings", [])
        validation_errors = instance.state_data.get("validation_errors", []) or input_data.get(
            "validation_errors", []
        )

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
            latest_contract = (
                Contract.objects.filter(tenant=tenant, asset=asset).order_by("-version").first()
            )
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
                final_norm_status = (
                    NormalizationStatus.NORMALIZED_OK
                    if hub_contract
                    else NormalizationStatus.NORMALIZATION_FAILED
                )
        else:
            # Default based on hub_contract presence
            final_norm_status = (
                NormalizationStatus.NORMALIZED_OK
                if hub_contract
                else NormalizationStatus.NORMALIZATION_FAILED
            )

        if validation_errors and len(validation_errors) > 0:
            final_norm_status = NormalizationStatus.NORMALIZATION_FAILED
            normalization_errors.extend(validation_errors)
            hub_contract = None

        # Validate contract before creation using ContractsBusinessRules
        contracts_rules = ContractsBusinessRules(
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(user_id) if user_id else None,
        )

        # Prepare contract data for validation
        contract_data = {
            "tenant_id": str(tenant_id),
            "original_raw": original_raw,
            "original_format": original_format,
            "original_spec_type": final_spec_type,
            "original_spec_version": final_spec_version,
            "asset_id": str(asset_id) if asset_id else None,
        }

        # Validate contract creation
        contract_creation_result = contracts_rules.validate_contract_creation(contract_data)
        if not contract_creation_result.is_valid:
            error_messages = contract_creation_result.errors
            raise ValueError(f"Contract creation validation failed: {'; '.join(error_messages)}")

        # Log validation warnings if any
        if contract_creation_result.warnings:
            logger.warning(
                "Contract creation validation warnings",
                workflow_instance_id=str(instance.id),
                tenant_id=tenant_id,
                warnings=contract_creation_result.warnings,
            )

        # Validate contract lifecycle (if contract already exists for this asset)
        if asset:
            existing_contracts = Contract.objects.filter(tenant=tenant, asset=asset)
            if existing_contracts.exists():
                # Validate contract update
                latest_contract = existing_contracts.order_by("-version").first()
                contract_update_result = contracts_rules.validate_contract_update(
                    contract=latest_contract, contract_data=contract_data
                )
                if not contract_update_result.is_valid:
                    error_messages = contract_update_result.errors
                    raise ValueError(
                        f"Contract update validation failed: {'; '.join(error_messages)}"
                    )

                # Log validation warnings if any
                if contract_update_result.warnings:
                    logger.warning(
                        "Contract update validation warnings",
                        workflow_instance_id=str(instance.id),
                        tenant_id=tenant_id,
                        warnings=contract_update_result.warnings,
                    )

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
            created_by=user,
        )

        logger.info(
            "Contract record created",
            workflow_instance_id=str(instance.id),
            contract_id=str(contract.id),
            tenant_id=tenant_id,
        )

        # Store contract_id in state for subsequent steps
        # Return contract_id both at top level and in state for subsequent steps
        return {"contract_id": str(contract.id), "state": {"contract_id": str(contract.id)}}

    @staticmethod
    @transaction.atomic
    def _link_data_file_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Optional: Link data file (create Asset).

        Args:
            input_data: Workflow input data (includes contract_id and optional file_id)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with asset_id (if created)
        """
        from django.contrib.auth import get_user_model

        from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility
        from hub.apps.tenants.models import Tenant

        User = get_user_model()

        # Get data from state_data (with fallback to input_data)
        tenant_id = instance.state_data.get("tenant_id") or input_data.get("tenant_id")
        user_id = instance.state_data.get("user_id") or input_data.get("user_id")
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")
        file_id = input_data.get("file_id") or instance.state_data.get("file_id")

        # Optional: asset metadata from input
        asset_key = input_data.get("asset_key")
        asset_name = input_data.get("asset_name")
        asset_description = input_data.get("asset_description")
        asset_domain = input_data.get("asset_domain")

        # Skip if no file_id provided (optional step)
        if not file_id:
            logger.info(
                "Skipping data file linking: file_id not provided",
                workflow_instance_id=str(instance.id),
            )
            return {"skipped": True, "reason": "file_id not provided"}

        if not contract_id:
            raise ValueError("contract_id is required for data file linking")

        try:
            # Get contract first (needed for tenant/user fallback)
            contract = Contract.objects.get(id=contract_id)

            # Get tenant (from state/input or from contract)
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
            else:
                # Fallback to contract's tenant
                tenant = contract.tenant
                tenant_id = str(tenant.id)

            # Get user (from state/input or from contract)
            if user_id:
                user = User.objects.get(id=user_id)
            else:
                # Fallback to contract's creator
                user = contract.created_by
                if not user:
                    raise ValueError(
                        "user_id is required for asset creation (not available from contract)"
                    )

            # Verify contract belongs to tenant (already retrieved above)
            if contract.tenant != tenant:
                raise ValueError(f"Contract {contract_id} does not belong to tenant {tenant_id}")

            # Get file
            from hub.apps.files.models import File

            try:
                file_obj = File.objects.get(id=file_id, tenant=tenant)
            except File.DoesNotExist:
                logger.warning(
                    "File not found for asset creation",
                    workflow_instance_id=str(instance.id),
                    file_id=file_id,
                )
                return {"skipped": True, "reason": f"File not found: {file_id}"}

            # Generate asset key and name if not provided
            if not asset_key:
                # Use file name or generate from contract
                asset_key = file_obj.name or f"asset-{file_id[:8]}"
            if not asset_name:
                asset_name = file_obj.name or "Data Asset"

            # Check if asset with key already exists
            if Asset.objects.filter(tenant=tenant, key=asset_key).exists():
                logger.warning(
                    "Asset with key already exists, skipping creation",
                    workflow_instance_id=str(instance.id),
                    asset_key=asset_key,
                )
                return {"skipped": True, "reason": f"Asset with key already exists: {asset_key}"}

            # Create asset
            asset = Asset.objects.create(
                tenant=tenant,
                key=asset_key,
                name=asset_name,
                description=asset_description,
                domain=asset_domain,
                status=AssetStatus.DRAFT,
                visibility=AssetVisibility.INTERNAL,
                created_by=user,
            )

            # Link contract to asset
            contract.asset = asset

            # Get next version for asset
            latest_contract = (
                Contract.objects.filter(tenant=tenant, asset=asset)
                .exclude(id=contract_id)
                .order_by("-version")
                .first()
            )
            if latest_contract:
                contract.version = latest_contract.version + 1
            else:
                contract.version = 1

            contract.save(update_fields=["asset", "version"])

            # If ODPS contract is linked, also link it to asset
            odps_contract_id = instance.state_data.get("odps_contract_id")
            if odps_contract_id:
                try:
                    odps_contract = Contract.objects.get(id=odps_contract_id, tenant=tenant)
                    odps_contract.asset = asset
                    # Update version if needed
                    latest_contract = (
                        Contract.objects.filter(tenant=tenant, asset=asset)
                        .exclude(id=odps_contract_id)
                        .order_by("-version")
                        .first()
                    )
                    if latest_contract:
                        odps_contract.version = latest_contract.version + 1
                    else:
                        odps_contract.version = 1
                    odps_contract.save(update_fields=["asset", "version"])
                except Contract.DoesNotExist:
                    logger.warning(
                        "ODPS contract not found for asset linking",
                        workflow_instance_id=str(instance.id),
                        odps_contract_id=odps_contract_id,
                    )

            logger.info(
                "Asset created and linked to contracts",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                contract_id=contract_id,
                file_id=file_id,
            )

            return {
                "asset_id": str(asset.id),
                "asset_key": asset_key,
                "state": {"asset_id": str(asset.id)},
            }
        except Exception as e:
            # Database error - transaction will rollback automatically
            logger.error(
                "Error creating asset for data file",
                workflow_instance_id=str(instance.id),
                file_id=file_id,
                contract_id=contract_id,
                error=str(e),
                exc_info=True,
            )
            raise ValueError(f"ASSET_CREATION_ERROR: Failed to create asset: {e!s}") from e

    @staticmethod
    @transaction.atomic
    def _index_for_search_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Index contract for search (ODCS technical + ODPS marketplace if linked).

        Args:
            input_data: Workflow input data (includes contract_id from state)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with indexing results
        """
        # Get contract_id from state_data (set by previous step)
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")
        odps_contract_id = instance.state_data.get("odps_contract_id")

        indexed_contracts = []

        if not contract_id:
            raise ValueError("contract_id is required for indexing")

        # Index ODCS contract (technical)
        try:
            contract = Contract.objects.get(id=contract_id)
            search_index = SearchIndexer.index_contract(contract)
            indexed_contracts.append(
                {
                    "contract_id": contract_id,
                    "contract_type": "ODCS",
                    "search_index_id": str(search_index.id),
                }
            )
        except Exception as e:
            logger.warning(
                "Failed to index ODCS contract (non-critical)",
                workflow_instance_id=str(instance.id),
                contract_id=contract_id,
                error=str(e),
            )

        # Index ODPS contract (marketplace) if linked
        if odps_contract_id:
            try:
                odps_contract = Contract.objects.get(id=odps_contract_id)
                search_index = SearchIndexer.index_contract(odps_contract)
                indexed_contracts.append(
                    {
                        "contract_id": odps_contract_id,
                        "contract_type": "ODPS",
                        "search_index_id": str(search_index.id),
                    }
                )
            except Exception as e:
                logger.warning(
                    "Failed to index ODPS contract (non-critical)",
                    workflow_instance_id=str(instance.id),
                    odps_contract_id=odps_contract_id,
                    error=str(e),
                )

        logger.info(
            "Contracts indexed for search",
            workflow_instance_id=str(instance.id),
            indexed_count=len(indexed_contracts),
        )

        return {"indexed": True, "indexed_contracts": indexed_contracts}

    @staticmethod
    def _generate_semantic_mapping_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Generate semantic mapping (RDF) for contract (ODCS technical + ODPS marketplace if linked).

        Args:
            input_data: Workflow input data (includes contract_id from state)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with semantic mapping results
        """
        # Get contract_id from state_data (set by previous step)
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")
        odps_contract_id = instance.state_data.get("odps_contract_id")

        mapped_contracts = []

        if not contract_id:
            raise ValueError("contract_id is required for semantic mapping")

        # Map ODCS contract to RDF (technical)
        try:
            contract = Contract.objects.get(id=contract_id)

            # Skip if normalization failed (no hub_contract_json)
            if not contract.hub_contract_json:
                logger.info(
                    "ODCS semantic mapping skipped (no hub_contract_json)",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id,
                )
            else:
                semantic_resource = map_contract_to_semantic(
                    contract=contract, tenant=contract.tenant, use_cache=False
                )

                if semantic_resource:
                    mapped_contracts.append(
                        {
                            "contract_id": contract_id,
                            "contract_type": "ODCS",
                            "semantic_resource_id": str(semantic_resource.id),
                            "uri": semantic_resource.uri,
                        }
                    )
        except Exception as e:
            logger.warning(
                "Failed to map ODCS contract to RDF (non-critical)",
                workflow_instance_id=str(instance.id),
                contract_id=contract_id,
                error=str(e),
            )

        # Map ODPS contract to RDF (marketplace) if linked
        if odps_contract_id:
            try:
                odps_contract = Contract.objects.get(id=odps_contract_id)
                if odps_contract.hub_contract_json:
                    semantic_resource = map_contract_to_semantic(
                        contract=odps_contract, tenant=odps_contract.tenant, use_cache=False
                    )
                    if semantic_resource:
                        mapped_contracts.append(
                            {
                                "contract_id": odps_contract_id,
                                "contract_type": "ODPS",
                                "semantic_resource_id": str(semantic_resource.id),
                                "uri": semantic_resource.uri,
                            }
                        )
            except Exception as e:
                logger.warning(
                    "Failed to map ODPS contract to RDF (non-critical)",
                    workflow_instance_id=str(instance.id),
                    odps_contract_id=odps_contract_id,
                    error=str(e),
                )

        logger.info(
            "Contracts mapped to RDF",
            workflow_instance_id=str(instance.id),
            mapped_count=len(mapped_contracts),
        )

        return {
            "semantic_mapping_generated": len(mapped_contracts) > 0,
            "mapped_contracts": mapped_contracts,
        }

    @staticmethod
    def _send_notifications_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
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
        input_data.get("tenant_id")

        if not contract_id or not user_id:
            logger.warning(
                "Notifications skipped (missing contract_id or user_id)",
                workflow_instance_id=str(instance.id),
            )
            return {"notifications_sent": False, "reason": "Missing required data"}

        # Get contract and user
        contract = Contract.objects.get(id=contract_id)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.get(id=user_id)

        # Log notification (email template can be added later)
        try:
            contract_title = "Untitled Contract"
            if contract.hub_contract_json and isinstance(contract.hub_contract_json, dict):
                info = contract.hub_contract_json.get("info", {})
                if isinstance(info, dict):
                    contract_title = info.get("title", "Untitled Contract")

            logger.info(
                "Contract creation notification logged",
                workflow_instance_id=str(instance.id),
                contract_id=contract_id,
                user_id=user_id,
                contract_title=contract_title,
                user_email=user.email,
            )

            return {"notifications_sent": True, "notification_type": "logged"}
        except Exception as e:
            logger.error(
                "Failed to log contract creation notification",
                workflow_instance_id=str(instance.id),
                contract_id=contract_id,
                error=str(e),
                exc_info=True,
            )
            # Don't fail workflow on notification errors
            return {"notifications_sent": False, "error": str(e)}

    @staticmethod
    def _audit_logging_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
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
        detected_spec_type = instance.state_data.get("detected_spec_type") or input_data.get(
            "detected_spec_type"
        )
        detected_spec_version = instance.state_data.get("detected_spec_version") or input_data.get(
            "detected_spec_version"
        )
        normalization_status = instance.state_data.get("normalization_status") or input_data.get(
            "normalization_status"
        )
        asset_id = input_data.get("asset_id")

        if not contract_id or not user_id or not tenant_id:
            raise ValueError("contract_id, user_id, and tenant_id are required for audit logging")

        # Get contract, user, and tenant
        Contract.objects.get(id=contract_id)
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
                "original_spec_type": detected_spec_type,
                "original_spec_version": detected_spec_version,
                "normalization_status": normalization_status,
                "asset_id": asset_id,
            },
            request=None,  # No request object in workflow context
        )

        logger.info(
            "Audit log created for contract creation",
            workflow_instance_id=str(instance.id),
            contract_id=contract_id,
        )

        return {"audit_logged": True}

    # Compensation tasks

    @staticmethod
    def _rollback_normalization_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """Rollback normalization (no-op, normalization is stateless)"""
        logger.info("Normalization rollback (no-op)", workflow_instance_id=str(instance.id))
        return {"rolled_back": True}

    @staticmethod
    def _rollback_validation_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """Rollback validation (no-op, validation is stateless)"""
        logger.info("Validation rollback (no-op)", workflow_instance_id=str(instance.id))
        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_contract_record_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """Rollback contract record creation (delete contract)"""
        contract_id = input_data.get("contract_id")

        if contract_id:
            try:
                contract = Contract.objects.get(id=contract_id)
                contract.delete()
                logger.info(
                    "Contract record rolled back (deleted)",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id,
                )
            except Contract.DoesNotExist:
                logger.warning(
                    "Contract record not found for rollback",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id,
                )

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _link_odps_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Link ODPS contract (optional step for marketplace).

        Supports three modes:
        1. upload: Parse and validate uploaded ODPS, create ODPS contract, link it
        2. generate: Generate ODPS from HubContract, create ODPS contract, link it
        3. link: Link to existing ODPS contract by ID

        Args:
            input_data: Workflow input data (includes contract_id from state)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with ODPS contract ID and linking results
        """
        from django.contrib.auth import get_user_model

        from hub.apps.contracts.linking_validation import validate_linking
        from hub.apps.contracts.models import OriginalFormat
        from hub.apps.contracts.normalization import parse_contract
        from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract
        from hub.apps.contracts.odps_parser import ODPSParser
        from hub.apps.contracts.odps_version_detection import detect_odps_version

        User = get_user_model()

        # Get contract_id from state_data
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")
        if not contract_id:
            raise ValueError("contract_id is required for ODPS linking")

        # Get ODPS action from input_data
        odps_action = input_data.get("odps_action")
        if not odps_action or odps_action not in ["upload", "generate", "link"]:
            # Skip if no ODPS action specified
            logger.info(
                "ODPS linking skipped (no action specified)",
                workflow_instance_id=str(instance.id),
                contract_id=contract_id,
            )
            return {"odps_linking_skipped": True, "reason": "No ODPS action specified"}

        # Get contract and related data
        contract = Contract.objects.get(id=contract_id)
        tenant_id = str(contract.tenant_id)
        user_id = instance.state_data.get("user_id") or input_data.get("user_id")
        user = User.objects.get(id=user_id) if user_id else contract.created_by

        # Get asset if available
        asset = contract.asset

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
                normalization_result = normalizer.normalize(odps_doc, spec_version=odps_version)
                hub_contract_from_odps = normalization_result.hub_contract

                # Create ODPS contract record
                odps_contract = Contract.objects.create(
                    tenant=contract.tenant,
                    asset=asset,
                    version=1,  # ODPS contracts start at version 1
                    status=ContractStatus.DRAFT,
                    original_spec_type=OriginalSpecType.ODPS,
                    original_spec_version=odps_version,
                    original_format=OriginalFormat.JSON
                    if odps_format.upper() == "JSON"
                    else OriginalFormat.YAML,
                    original_raw=odps_raw,
                    hub_contract_version="1.0.0",
                    hub_contract_json=hub_contract_from_odps,
                    normalization_status=NormalizationStatus.NORMALIZED_OK,
                    normalization_errors=[],
                    normalization_warnings=[],
                    created_by=user,
                )
                odps_contract_id = str(odps_contract.id)

                logger.info(
                    "ODPS contract created from upload",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id,
                    odps_contract_id=odps_contract_id,
                )

            elif odps_action == "generate":
                # Generate ODPS from HubContract
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
                import json

                odps_raw = json.dumps(odps_doc, indent=2)

                # Create ODPS contract record
                odps_contract = Contract.objects.create(
                    tenant=contract.tenant,
                    asset=asset,
                    version=1,
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
                    created_by=user,
                )
                odps_contract_id = str(odps_contract.id)

                logger.info(
                    "ODPS contract generated from HubContract",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id,
                    odps_contract_id=odps_contract_id,
                )

            elif odps_action == "link":
                # Link to existing ODPS contract
                existing_odps_contract_id = input_data.get("odps_contract_id")
                if not existing_odps_contract_id:
                    raise ValueError("odps_contract_id is required for ODPS linking")

                # Validate linking (existence, compatibility, circular references)
                odps_contract, _odcs_contract = validate_linking(
                    odps_contract_id=existing_odps_contract_id,
                    odcs_contract_id=contract_id,
                    tenant_id=tenant_id,
                )
                odps_contract_id = str(odps_contract.id)

                logger.info(
                    "ODPS contract validated for linking",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id,
                    odps_contract_id=odps_contract_id,
                )

            # Establish bidirectional link
            # ODPS → ODCS: Store in ODPS contract's hub_contract_json.extensions.x_odps.odcs_link
            if odps_contract and odps_contract.hub_contract_json:
                if "extensions" not in odps_contract.hub_contract_json:
                    odps_contract.hub_contract_json["extensions"] = {}
                if "x_odps" not in odps_contract.hub_contract_json["extensions"]:
                    odps_contract.hub_contract_json["extensions"]["x_odps"] = {}
                odps_contract.hub_contract_json["extensions"]["x_odps"]["odcs_link"] = contract_id
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
                contract_id=contract_id,
                odps_contract_id=odps_contract_id,
                action=odps_action,
            )

            return {
                "odps_linked": True,
                "odps_contract_id": odps_contract_id,
                "action": odps_action,
                "state": {"odps_contract_id": odps_contract_id},
            }

        except Exception as e:
            logger.error(
                "ODPS linking failed",
                workflow_instance_id=str(instance.id),
                contract_id=contract_id,
                action=odps_action,
                error=str(e),
                exc_info=True,
            )
            raise ValueError(f"ODPS linking failed: {e!s}")

    @staticmethod
    @transaction.atomic
    def _rollback_odps_linking_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """Rollback ODPS linking (remove links and delete created ODPS contract if needed)"""
        contract_id = input_data.get("contract_id")
        odps_contract_id = input_data.get("odps_contract_id")
        odps_action = input_data.get("odps_action")

        if contract_id:
            try:
                contract = Contract.objects.get(id=contract_id)
                # Remove ODPS link from contract
                if contract.hub_contract_json and "extensions" in contract.hub_contract_json:
                    x_odps = contract.hub_contract_json["extensions"].get("x_odps", {})
                    if "odps_link" in x_odps:
                        del x_odps["odps_link"]
                        contract.save(update_fields=["hub_contract_json"])
            except Contract.DoesNotExist:
                pass

        if odps_contract_id:
            try:
                odps_contract = Contract.objects.get(id=odps_contract_id)
                # Remove ODCS link from ODPS contract
                if (
                    odps_contract.hub_contract_json
                    and "extensions" in odps_contract.hub_contract_json
                ):
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
                        odps_contract_id=odps_contract_id,
                    )
            except Contract.DoesNotExist:
                pass

        logger.info(
            "ODPS linking rolled back",
            workflow_instance_id=str(instance.id),
            contract_id=contract_id,
            odps_contract_id=odps_contract_id,
        )

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_link_data_file_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """Rollback asset creation (delete asset and unlink contracts)"""
        asset_id = instance.state_data.get("asset_id")
        contract_id = instance.state_data.get("contract_id")
        odps_contract_id = instance.state_data.get("odps_contract_id")

        if asset_id:
            try:
                from hub.apps.assets.models import Asset

                asset = Asset.objects.get(id=asset_id)

                # Unlink contracts from asset
                if contract_id:
                    try:
                        contract = Contract.objects.get(id=contract_id)
                        contract.asset = None
                        contract.save(update_fields=["asset"])
                    except Contract.DoesNotExist:
                        pass

                if odps_contract_id:
                    try:
                        odps_contract = Contract.objects.get(id=odps_contract_id)
                        odps_contract.asset = None
                        odps_contract.save(update_fields=["asset"])
                    except Contract.DoesNotExist:
                        pass

                # Delete asset
                asset.delete()

                logger.info(
                    "Asset rolled back (deleted)",
                    workflow_instance_id=str(instance.id),
                    asset_id=asset_id,
                )
            except Asset.DoesNotExist:
                logger.warning(
                    "Asset not found for rollback",
                    workflow_instance_id=str(instance.id),
                    asset_id=asset_id,
                )

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_indexing_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """Rollback search indexing (delete search indices)"""
        indexed_contracts = input_data.get("indexed_contracts", [])

        for indexed_contract in indexed_contracts:
            search_index_id = indexed_contract.get("search_index_id")
            if search_index_id:
                try:
                    from hub.apps.search.models import SearchIndex

                    search_index = SearchIndex.objects.get(id=search_index_id)
                    search_index.delete()
                    logger.info(
                        "Search index rolled back (deleted)",
                        workflow_instance_id=str(instance.id),
                        search_index_id=search_index_id,
                    )
                except Exception as e:
                    logger.warning(
                        "Search index rollback failed",
                        workflow_instance_id=str(instance.id),
                        search_index_id=search_index_id,
                        error=str(e),
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
        asset_id: str | None = None,
        original_spec_type: str | None = None,
        odps_action: str | None = None,
        odps_raw: str | None = None,
        odps_format: str | None = None,
        odps_contract_id: str | None = None,
        file_id: str | None = None,
        asset_key: str | None = None,
        asset_name: str | None = None,
        asset_description: str | None = None,
        asset_domain: str | None = None,
        engine: WorkflowEngine | None = None,
        registry: WorkflowRegistry | None = None,
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
            odps_action: Optional ODPS action: 'upload', 'generate', or 'link'
            odps_raw: Optional ODPS content (required if odps_action='upload')
            odps_format: Optional ODPS format (JSON or YAML, required if odps_action='upload')
            odps_contract_id: Optional existing ODPS contract ID (required if odps_action='link')
            file_id: Optional file ID for data file linking (creates Asset)
            asset_key: Optional asset key (auto-generated if not provided)
            asset_name: Optional asset name (auto-generated if not provided)
            asset_description: Optional asset description
            asset_domain: Optional asset domain
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

        # Prepare workflow input (omit None values so dict.get() defaults fire correctly)
        workflow_input = {
            k: v
            for k, v in {
                "original_raw": original_raw,
                "original_format": original_format,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "asset_id": asset_id,
                "original_spec_type": original_spec_type,
                "odps_action": odps_action,
                "odps_raw": odps_raw,
                "odps_format": odps_format,
                "odps_contract_id": odps_contract_id,
                "file_id": file_id,
                "asset_key": asset_key,
                "asset_name": asset_name,
                "asset_description": asset_description,
                "asset_domain": asset_domain,
            }.items()
            if v is not None
        }

        # Create workflow instance
        workflow_instance = engine.create_instance(
            workflow_name=cls.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=tenant_id,
            created_by_id=user_id,
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
                contract_id=contract_id,
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
