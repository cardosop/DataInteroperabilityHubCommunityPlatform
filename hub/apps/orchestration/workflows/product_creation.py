"""
Product Creation Workflow (ODPS)

Orchestrates the ODPS product creation process with proper error handling,
retry logic, and compensation. This workflow implements the Product-First flow
where ODPS documents are ingested and linked to ODCS contracts.

Workflow Steps:
1. parse_odps: Parse ODPS document, validate schema, detect version
2. resolve_refs: Resolve $ref references (internal, local, external)
3. extract_contract: Extract ODCS from product.contract (required)
4. validate_odcs: Validate extracted ODCS contract
5. normalize_odcs: Normalize ODCS → HubContract (technical)
6. normalize_odps: Normalize ODPS → HubContract (marketplace)
7. create_odcs_contract: Create ODCS contract record
8. create_odps_contract: Create ODPS contract record
9. link_contracts: Establish bidirectional link (ODPS ↔ ODCS)
10. index_for_search: Index for search (ODPS product + ODCS technical)
11. semantic_mapping: Map ODPS to RDF (async job)
"""
import structlog
from typing import Dict, Any, Optional
from django.db import transaction
from django.utils import timezone

from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.contracts.models import Contract, ContractStatus, NormalizationStatus, OriginalSpecType
from hub.apps.contracts.odps_parser import ODPSParser
from hub.apps.contracts.odps_errors import ODPSValidationError
from hub.apps.contracts.odps_version_detection import detect_odps_version
from hub.apps.contracts.ref_resolver import RefResolver, ExternalRefHandling
from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
from hub.apps.contracts.odps_errors import (
    ODPSRefResolutionError,
    ODPSNormalizationError,
    ODPSLinkingError
)
from hub.apps.contracts.linking_validation import validate_linking, LinkingValidationError
from hub.apps.search.indexing import SearchIndexer
from hub.apps.semantic.utils import map_contract_to_semantic
from hub.apps.audit.utils import create_audit_event
from hub.apps.observability.otel_metrics import odps_ingestion_total

logger = structlog.get_logger(__name__)


class ProductCreationWorkflow:
    """
    Product creation workflow orchestrator (ODPS Product-First flow).

    Manages the complete ODPS product creation process:
    1. Parse and validate ODPS document
    2. Resolve $ref references
    3. Extract ODCS contract from product.contract
    4. Validate ODCS contract
    5. Normalize ODCS → HubContract (technical)
    6. Normalize ODPS → HubContract (marketplace)
    7. Create ODCS contract record
    8. Create ODPS contract record
    9. Link contracts bidirectionally
    10. Index for search
    11. Generate semantic mapping (RDF)
    """

    WORKFLOW_NAME = "product_creation"

    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the product creation workflow definition.

        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": "1.0.0",
            "dependencies": [],
            "steps": [
                {
                    "name": "parse_odps",
                    "type": "task",
                    "task": "product_creation.parse_odps"
                },
                {
                    "name": "resolve_refs",
                    "type": "task",
                    "task": "product_creation.resolve_refs"
                },
                {
                    "name": "extract_contract",
                    "type": "task",
                    "task": "product_creation.extract_contract"
                },
                {
                    "name": "validate_odcs",
                    "type": "task",
                    "task": "product_creation.validate_odcs"
                },
                {
                    "name": "normalize_odcs",
                    "type": "task",
                    "task": "product_creation.normalize_odcs",
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_normalize_odcs"
                    }
                },
                {
                    "name": "normalize_odps",
                    "type": "task",
                    "task": "product_creation.normalize_odps",
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_normalize_odps"
                    }
                },
                {
                    "name": "create_odcs_contract",
                    "type": "task",
                    "task": "product_creation.create_odcs_contract",
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_odcs_contract"
                    }
                },
                {
                    "name": "create_odps_contract",
                    "type": "task",
                    "task": "product_creation.create_odps_contract",
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_odps_contract"
                    }
                },
                {
                    "name": "link_contracts",
                    "type": "task",
                    "task": "product_creation.link_contracts",
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_link_contracts"
                    }
                },
                {
                    "name": "link_data_file",
                    "type": "task",
                    "task": "product_creation.link_data_file",
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_link_data_file"
                    }
                },
                {
                    "name": "index_for_search",
                    "type": "task",
                    "task": "product_creation.index_for_search"
                },
                {
                    "name": "semantic_mapping",
                    "type": "task",
                    "task": "product_creation.semantic_mapping"
                }
            ],
            "compensation": {
                "enabled": True
            }
        }

        registry.register_workflow(
            workflow_name=cls.WORKFLOW_NAME,
            dsl_json=workflow_dsl,
            description="Orchestrates ODPS product creation with validation, normalization, linking, indexing, and semantic mapping"
        )

    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow task functions.

        Args:
            engine: WorkflowEngine instance
        """
        engine.register_task("product_creation.parse_odps", cls._parse_odps_task)
        engine.register_task("product_creation.resolve_refs", cls._resolve_refs_task)
        engine.register_task("product_creation.extract_contract", cls._extract_contract_task)
        engine.register_task("product_creation.validate_odcs", cls._validate_odcs_task)
        engine.register_task("product_creation.normalize_odcs", cls._normalize_odcs_task)
        engine.register_task("product_creation.normalize_odps", cls._normalize_odps_task)
        engine.register_task("product_creation.create_odcs_contract", cls._create_odcs_contract_task)
        engine.register_task("product_creation.create_odps_contract", cls._create_odps_contract_task)
        engine.register_task("product_creation.link_contracts", cls._link_contracts_task)
        engine.register_task("product_creation.link_data_file", cls._link_data_file_task)
        engine.register_task("product_creation.index_for_search", cls._index_for_search_task)
        engine.register_task("product_creation.semantic_mapping", cls._semantic_mapping_task)

        # Compensation tasks
        engine.register_task("product_creation.rollback_normalize_odcs", cls._rollback_normalize_odcs_task)
        engine.register_task("product_creation.rollback_normalize_odps", cls._rollback_normalize_odps_task)
        engine.register_task("product_creation.rollback_odcs_contract", cls._rollback_odcs_contract_task)
        engine.register_task("product_creation.rollback_odps_contract", cls._rollback_odps_contract_task)
        engine.register_task("product_creation.rollback_link_contracts", cls._rollback_link_contracts_task)
        engine.register_task("product_creation.rollback_link_data_file", cls._rollback_link_data_file_task)

    @staticmethod
    def _parse_odps_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Parse ODPS document, validate schema, detect version.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with parsed ODPS document and version
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

        try:
            # Parse ODPS document
            odps_doc = ODPSParser.parse(
                content=original_raw,
                format=original_format.lower()
            )

            # Detect version
            odps_version = detect_odps_version(odps_doc)
            if not odps_version or odps_version == "unknown":
                odps_version = "4.1"  # Default to 4.1

            # Validate ODPS document
            is_valid, validation_errors = ODPSParser.validate(
                odps_document=odps_doc,
                version=odps_version
            )

            if not is_valid:
                error_messages = [
                    f"{err.get('path', '')}: {err.get('message', '')}"
                    for err in validation_errors
                ]
                # Extract field names from validation errors for context
                field_names = [err.get('path', '').split('/')[-1] for err in validation_errors if err.get('path')]
                raise ODPSValidationError(
                    message=f"ODPS validation failed: {'; '.join(error_messages)}",
                    error_code=ODPSValidationError.ERROR_CODE_SCHEMA_VALIDATION_FAILED,
                    context={
                        "field_names": list(set(field_names)),
                        "validation_errors": validation_errors,
                        "odps_version": odps_version
                    },
                    field_path="/",
                    actual=odps_doc
                )

            logger.info(
                "ODPS document parsed and validated",
                workflow_instance_id=str(instance.id),
                tenant_id=tenant_id,
                odps_version=odps_version,
                format=original_format
            )

            return {
                "odps_document": odps_doc,
                "odps_version": odps_version,
                "state": {
                    "odps_document": odps_doc,
                    "odps_version": odps_version,
                    "original_raw": original_raw,
                    "original_format": original_format,
                    "tenant_id": tenant_id,
                    "user_id": user_id
                }
            }
        except ODPSValidationError:
            # Re-raise ODPSValidationError as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ODPSValidationError(
                message=f"Failed to parse ODPS document: {str(e)}",
                error_code=ODPSValidationError.ERROR_CODE_SCHEMA_VALIDATION_FAILED,
                context={"parse_error": str(e)},
                cause=e
            ) from e

    @staticmethod
    def _resolve_refs_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Resolve $ref references (internal, local, external).

        Args:
            input_data: Workflow input data (includes parsed ODPS document)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with resolved ODPS document
        """
        odps_doc = input_data.get("odps_document")
        external_ref_handling = input_data.get("external_ref_handling", ExternalRefHandling.RESOLVE.value)

        if not odps_doc:
            raise ValueError("odps_document is required for $ref resolution")

        import time
        max_retries = 3
        retry_delays = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s

        # Publish ref progress: starting (Task 7.3.2)
        try:
            from hub.apps.core.events.service_publishers import ODPSEventPublisher
            from hub.apps.core.events.publisher import EventPublisher
            tenant_id = instance.state_data.get("tenant_id") or getattr(instance, 'tenant_id', None)
            user_id = instance.state_data.get("user_id") or getattr(instance, 'created_by_id', None)
            odps_event_publisher = ODPSEventPublisher()
            odps_event_publisher._event_publisher = EventPublisher(
                service_name="workflow_engine",
                tenant_id=str(tenant_id) if tenant_id else None,
                user_id=str(user_id) if user_id else None,
            )
            # Publish start event
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=None,  # Contract not created yet
                progress_percentage=0.0,
                refs_processed=0,
                refs_total=None,  # Unknown at start
                status_message="Starting $ref resolution",
                tenant_id=str(tenant_id) if tenant_id else None,
                user_id=str(user_id) if user_id else None,
            )
        except Exception as e:
            logger.warning(f"Failed to publish ODPS ref progress event: {e}")

        last_error = None
        for attempt in range(max_retries):
            try:
                # Create ref resolver
                resolver = RefResolver(
                    tenant_id=instance.state_data.get("tenant_id") or getattr(instance, 'tenant_id', None),
                    user_id=instance.state_data.get("user_id") or getattr(instance, 'created_by_id', None)
                )

                # Resolve all $ref references
                original_doc, resolved_doc = resolver.resolve_all_refs(
                    document=odps_doc,
                    preserve_original=True,
                    external_ref_handling=ExternalRefHandling(external_ref_handling)
                )

                # Publish ref progress: completed (Task 7.3.2)
                try:
                    from hub.apps.core.events.service_publishers import ODPSEventPublisher
                    from hub.apps.core.events.publisher import EventPublisher
                    tenant_id = instance.state_data.get("tenant_id") or getattr(instance, 'tenant_id', None)
                    user_id = instance.state_data.get("user_id") or getattr(instance, 'created_by_id', None)
                    odps_event_publisher = ODPSEventPublisher()
                    odps_event_publisher._event_publisher = EventPublisher(
                        service_name="workflow_engine",
                        tenant_id=str(tenant_id) if tenant_id else None,
                        user_id=str(user_id) if user_id else None,
                    )
                    # Publish completion event
                    odps_event_publisher.publish_odps_ref_progress(
                        contract_id=None,  # Contract not created yet
                        progress_percentage=100.0,
                        refs_processed=None,  # Unknown exact count
                        refs_total=None,
                        status_message="$ref resolution completed",
                        tenant_id=str(tenant_id) if tenant_id else None,
                        user_id=str(user_id) if user_id else None,
                    )
                except Exception as e:
                    logger.warning(f"Failed to publish ODPS ref progress event: {e}")

                logger.info(
                    "$ref references resolved",
                    workflow_instance_id=str(instance.id),
                    external_ref_handling=external_ref_handling,
                    attempt=attempt + 1
                )

                return {
                    "odps_document_resolved": resolved_doc,
                    "state": {
                        "odps_document_resolved": resolved_doc
                    }
                }
            except ODPSRefResolutionError as e:
                last_error = e
                # Check if error is transient (network, timeout) and retry
                is_transient = (
                    "timeout" in str(e).lower() or
                    "network" in str(e).lower() or
                    "connection" in str(e).lower() or
                    e.error_code in [
                        ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                        ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED
                    ]
                )

                if is_transient and attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.warning(
                        "Transient error during $ref resolution, retrying",
                        workflow_instance_id=str(instance.id),
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay_seconds=delay,
                        error=str(e),
                        ref_path=getattr(e, 'ref_path', '/'),
                        ref_type=getattr(e, 'ref_type', 'unknown')
                    )
                    time.sleep(delay)
                    continue
                else:
                    # Non-transient error or max retries reached
                    raise ODPSRefResolutionError(
                        message=f"Failed to resolve $ref references after {attempt + 1} attempts: {str(e)}",
                        ref_path=getattr(e, 'ref_path', '/'),
                        ref_type=getattr(e, 'ref_type', 'unknown'),
                        context={
                            "ref_path": getattr(e, 'ref_path', '/'),
                            "ref_type": getattr(e, 'ref_type', 'unknown'),
                            "attempts": attempt + 1,
                            "max_retries": max_retries
                        },
                        cause=e
                    ) from e
            except Exception as e:
                # Wrap unexpected errors
                raise ODPSRefResolutionError(
                    message=f"Failed to resolve $ref references: {str(e)}",
                    ref_path="/",
                    ref_type="unknown",
                    context={
                        "ref_path": "/",
                        "ref_type": "unknown",
                        "attempts": attempt + 1
                    },
                    cause=e
                ) from e

        # If we get here, all retries failed
        if last_error:
            raise last_error
        raise ODPSRefResolutionError(
            message="Failed to resolve $ref references: Unknown error",
            ref_path="/",
            ref_type="unknown"
        )

    @staticmethod
    def _extract_contract_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Extract ODCS from product.contract (required).

        Args:
            input_data: Workflow input data (includes resolved ODPS document)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with extracted ODCS contract
        """
        odps_doc = instance.state_data.get("odps_document_resolved") or input_data.get("odps_document_resolved")

        if not odps_doc:
            raise ValueError("odps_document_resolved is required for contract extraction")

        try:
            product = odps_doc.get("product", {})
            if not isinstance(product, dict):
                raise ODPSValidationError(
                    message="ODPS document must have a 'product' field",
                    error_code=ODPSValidationError.ERROR_CODE_REQUIRED_FIELD_MISSING,
                    field_path="/product",
                    context={"field_name": "product"}
                )

            contract_section = product.get("contract")
            if not isinstance(contract_section, dict):
                raise ODPSValidationError(
                    message="ODPS product.contract is required but missing",
                    error_code=ODPSValidationError.ERROR_CODE_REQUIRED_FIELD_MISSING,
                    field_path="/product/contract",
                    context={"field_name": "product.contract"}
                )

            # Extract ODCS contract from product.contract
            # Handle three formats: $ref, spec (inline), contractURL
            odcs_contract = None
            odcs_contract_url = None

            if "$ref" in contract_section:
                # Contract is referenced - should have been resolved in resolve_refs step
                contract_ref = contract_section.get("$ref")
                # If still a $ref after resolution, it's an error
                if isinstance(contract_ref, str) and contract_ref.startswith("#"):
                    # Internal ref - resolve it
                    from hub.apps.contracts.source_paths import resolve_json_pointer
                    odcs_contract = resolve_json_pointer(odps_doc, contract_ref)
                elif isinstance(contract_ref, dict):
                    # Already resolved
                    odcs_contract = contract_ref
                else:
                    raise ODPSValidationError(
                        message=f"Failed to resolve product.contract.$ref: {contract_ref}",
                        error_code=ODPSValidationError.ERROR_CODE_INVALID_VALUE,
                        field_path="/product/contract/$ref",
                        context={"ref_path": contract_ref}
                    )
            elif "spec" in contract_section:
                # Inline ODCS contract
                odcs_contract = contract_section.get("spec")
                if not isinstance(odcs_contract, dict):
                    raise ODPSValidationError(
                        message="product.contract.spec must be a dictionary",
                        error_code=ODPSValidationError.ERROR_CODE_INVALID_DATA_TYPE,
                        field_path="/product/contract/spec",
                        expected="dict",
                        actual=type(odcs_contract).__name__
                    )
            elif "contractURL" in contract_section:
                # Contract URL reference
                odcs_contract_url = contract_section.get("contractURL")
                if not isinstance(odcs_contract_url, str):
                    raise ODPSValidationError(
                        message="product.contract.contractURL must be a string",
                        error_code=ODPSValidationError.ERROR_CODE_INVALID_DATA_TYPE,
                        field_path="/product/contract/contractURL",
                        expected="str",
                        actual=type(odcs_contract_url).__name__
                    )
                # For contractURL, we would need to fetch it, but that's not implemented yet
                # For now, raise an error
                raise ODPSValidationError(
                    message="product.contract.contractURL is not yet supported. Use $ref or spec instead.",
                    error_code=ODPSValidationError.ERROR_CODE_INVALID_VALUE,
                    field_path="/product/contract/contractURL",
                    context={"contract_url": odcs_contract_url}
                )
            else:
                raise ODPSValidationError(
                    message="product.contract must have one of: $ref, spec, or contractURL",
                    error_code=ODPSValidationError.ERROR_CODE_REQUIRED_FIELD_MISSING,
                    field_path="/product/contract",
                    context={"available_fields": list(contract_section.keys())}
                )

            if not odcs_contract:
                raise ODPSValidationError(
                    message="Failed to extract ODCS contract from product.contract",
                    error_code=ODPSValidationError.ERROR_CODE_INVALID_VALUE,
                    field_path="/product/contract",
                    context={"contract_section": contract_section}
                )

            logger.info(
                "ODCS contract extracted from ODPS",
                workflow_instance_id=str(instance.id)
            )

            return {
                "odcs_contract": odcs_contract,
                "odcs_contract_url": odcs_contract_url,
                "state": {
                    "odcs_contract": odcs_contract,
                    "odcs_contract_url": odcs_contract_url
                }
            }
        except ODPSValidationError:
            # Re-raise ODPSValidationError as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ODPSValidationError(
                message=f"Failed to extract ODCS contract: {str(e)}",
                error_code=ODPSValidationError.ERROR_CODE_INVALID_VALUE,
                context={"extraction_error": str(e)},
                cause=e
            ) from e

    @staticmethod
    def _validate_odcs_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate extracted ODCS contract.

        Args:
            input_data: Workflow input data (includes extracted ODCS contract)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validation results
        """
        odcs_contract = instance.state_data.get("odcs_contract") or input_data.get("odcs_contract")

        if not odcs_contract:
            raise ValueError("odcs_contract is required for validation")

        try:
            # Convert ODCS contract dict to string for validation
            import json
            odcs_raw = json.dumps(odcs_contract)

            # Validate ODCS contract using normalize_contract (which validates)
            hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = normalize_contract(
                raw_contract=odcs_raw,
                format="JSON",
                spec_type="ODCS"
            )

            if norm_status == NormalizationStatus.NORMALIZATION_FAILED:
                error_message = norm_errors[0] if norm_errors else "ODCS validation failed"
                raise ValueError(f"ODCS_VALIDATION_ERROR: {error_message}")

            if detected_spec_type != "ODCS":
                raise ValueError(f"ODCS_VALIDATION_ERROR: Expected ODCS contract, got {detected_spec_type}")

            logger.info(
                "ODCS contract validated",
                workflow_instance_id=str(instance.id),
                spec_type=detected_spec_type,
                spec_version=detected_spec_version
            )

            return {
                "odcs_validated": True,
                "detected_spec_type": detected_spec_type,
                "detected_spec_version": detected_spec_version,
                "state": {
                    "odcs_validated": True,
                    "detected_spec_type": detected_spec_type,
                    "detected_spec_version": detected_spec_version
                }
            }
        except Exception as e:
            # Wrap errors
            raise ValueError(f"ODCS_VALIDATION_ERROR: {str(e)}") from e

    @staticmethod
    def _normalize_odcs_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Normalize ODCS → HubContract (technical).

        Args:
            input_data: Workflow input data (includes validated ODCS contract)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with normalized HubContract
        """
        odcs_contract = instance.state_data.get("odcs_contract") or input_data.get("odcs_contract")

        if not odcs_contract:
            raise ValueError("odcs_contract is required for normalization")

        # Track ODCS ingestion (Task 6.2.2 - explicit backward compatibility)
        try:
            from hub.apps.observability.otel_metrics import odcs_ingestion_total
            tenant_id = getattr(instance, 'tenant_id', None) or 'unknown'
            odcs_ingestion_total.labels(source='technical', tenant_id=tenant_id).inc()
        except Exception:
            pass  # Metrics failure should not affect workflow

        try:
            # Convert ODCS contract dict to string for normalization
            import json
            odcs_raw = json.dumps(odcs_contract)

            # Normalize ODCS → HubContract
            hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = normalize_contract(
                raw_contract=odcs_raw,
                format="JSON",
                spec_type="ODCS"
            )

            if norm_status == NormalizationStatus.NORMALIZATION_FAILED:
                error_message = norm_errors[0] if norm_errors else "ODCS normalization failed"
                raise ValueError(f"ODCS_NORMALIZATION_ERROR: {error_message}")

            logger.info(
                "ODCS contract normalized",
                workflow_instance_id=str(instance.id),
                spec_type=detected_spec_type,
                spec_version=detected_spec_version,
                status=norm_status.value
            )

            return {
                "odcs_hub_contract": hub_contract,
                "odcs_normalization_status": norm_status.value,
                "odcs_normalization_errors": norm_errors,
                "odcs_normalization_warnings": norm_warnings,
                "state": {
                    "odcs_hub_contract": hub_contract,
                    "odcs_normalization_status": norm_status.value,
                    "odcs_normalization_errors": norm_errors,
                    "odcs_normalization_warnings": norm_warnings
                }
            }
        except Exception as e:
            # Wrap errors
            raise ValueError(f"ODCS_NORMALIZATION_ERROR: {str(e)}") from e

    @staticmethod
    def _normalize_odps_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Normalize ODPS → HubContract (marketplace).

        Args:
            input_data: Workflow input data (includes resolved ODPS document)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with normalized HubContract
        """
        odps_doc = instance.state_data.get("odps_document_resolved") or input_data.get("odps_document_resolved")
        odps_version = instance.state_data.get("odps_version") or input_data.get("odps_version", "4.1")

        if not odps_doc:
            raise ValueError("odps_document_resolved is required for ODPS normalization")

        try:
            # Track ODPS ingestion (Task 6.2.1)
            try:
                tenant_id = getattr(instance, 'tenant_id', None) or 'unknown'
                odps_ingestion_total.labels(source='marketplace', tenant_id=tenant_id).inc()
            except Exception:
                pass  # Metrics failure should not affect workflow

            # Publish normalization progress: starting (Task 7.3.2)
            try:
                from hub.apps.core.events.service_publishers import ODPSEventPublisher
                from hub.apps.core.events.publisher import EventPublisher
                tenant_id = instance.state_data.get("tenant_id") or getattr(instance, 'tenant_id', None)
                user_id = instance.state_data.get("user_id") or getattr(instance, 'created_by_id', None)
                odps_event_publisher = ODPSEventPublisher()
                odps_event_publisher._event_publisher = EventPublisher(
                    service_name="workflow_engine",
                    tenant_id=str(tenant_id) if tenant_id else None,
                    user_id=str(user_id) if user_id else None,
                )
                # Publish start event
                odps_event_publisher.publish_odps_normalization_progress(
                    contract_id=None,  # Contract not created yet
                    progress_percentage=0.0,
                    current_phase="initialization",
                    total_phases=6,
                    phase_index=0,
                    status_message="Starting ODPS normalization",
                    odps_version=odps_version,
                    tenant_id=str(tenant_id) if tenant_id else None,
                    user_id=str(user_id) if user_id else None,
                )
            except Exception as e:
                logger.warning(f"Failed to publish ODPS normalization progress event: {e}")

            # Normalize ODPS → HubContract
            normalizer = ODPSNormalizer()
            result = normalizer.normalize(
                contract_data=odps_doc,
                spec_version=odps_version
            )

            # Publish normalization progress: completed (Task 7.3.2)
            try:
                from hub.apps.core.events.service_publishers import ODPSEventPublisher
                from hub.apps.core.events.publisher import EventPublisher
                tenant_id = instance.state_data.get("tenant_id") or getattr(instance, 'tenant_id', None)
                user_id = instance.state_data.get("user_id") or getattr(instance, 'created_by_id', None)
                odps_event_publisher = ODPSEventPublisher()
                odps_event_publisher._event_publisher = EventPublisher(
                    service_name="workflow_engine",
                    tenant_id=str(tenant_id) if tenant_id else None,
                    user_id=str(user_id) if user_id else None,
                )
                # Publish completion event
                odps_event_publisher.publish_odps_normalization_progress(
                    contract_id=None,  # Contract not created yet
                    progress_percentage=100.0,
                    current_phase="completed",
                    total_phases=6,
                    phase_index=6,
                    status_message=f"ODPS normalization completed: {result.status.value}",
                    odps_version=odps_version,
                    tenant_id=str(tenant_id) if tenant_id else None,
                    user_id=str(user_id) if user_id else None,
                )
            except Exception as e:
                logger.warning(f"Failed to publish ODPS normalization progress event: {e}")

            # Log result details for debugging
            logger.debug(
                "ODPS normalization result",
                workflow_instance_id=str(instance.id),
                status=result.status.value if result.status else "None",
                has_hub_contract=result.hub_contract is not None,
                errors_count=len(result.errors) if result.errors else 0,
                errors=result.errors[:3] if result.errors else []  # First 3 errors for debugging
            )

            if result.status == NormalizationStatus.NORMALIZATION_FAILED:
                # result.errors is List[str], not List[Dict]
                error_messages = result.errors if result.errors else ["Unknown normalization error"]
                error_text = '; '.join(error_messages) if error_messages else "Unknown normalization error"
                raise ODPSNormalizationError(
                    message=f"ODPS normalization failed: {error_text}",
                    error_code="ODPS_NORMALIZATION_ERROR",
                    context={"mapping_errors": error_messages, "status": result.status.value}
                )

            logger.info(
                "ODPS document normalized",
                workflow_instance_id=str(instance.id),
                odps_version=odps_version,
                status=result.status.value
            )

            return {
                "odps_hub_contract": result.hub_contract,
                "odps_normalization_status": result.status.value,
                "odps_normalization_errors": result.errors,
                "odps_normalization_warnings": result.warnings,
                "state": {
                    "odps_hub_contract": result.hub_contract,
                    "odps_normalization_status": result.status.value,
                    "odps_normalization_errors": result.errors,
                    "odps_normalization_warnings": result.warnings
                }
            }
        except ODPSNormalizationError:
            # Re-raise ODPSNormalizationError as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ODPSNormalizationError(
                message=f"Failed to normalize ODPS document: {str(e)}",
                error_code="ODPS_NORMALIZATION_ERROR",
                context={"mapping_errors": [str(e)]},
                cause=e
            ) from e

    @staticmethod
    @transaction.atomic
    def _create_odcs_contract_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create ODCS contract record.

        Args:
            input_data: Workflow input data (includes normalized HubContract)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with ODCS contract ID
        """
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Get data from state_data
        tenant_id = instance.state_data.get("tenant_id")
        user_id = instance.state_data.get("user_id")
        asset_id = instance.state_data.get("asset_id")
        odcs_contract = instance.state_data.get("odcs_contract")
        odcs_hub_contract = instance.state_data.get("odcs_hub_contract")
        detected_spec_type = instance.state_data.get("detected_spec_type", "ODCS")
        detected_spec_version = instance.state_data.get("detected_spec_version", "3.0.2")
        odcs_normalization_status = instance.state_data.get("odcs_normalization_status")
        odcs_normalization_errors = instance.state_data.get("odcs_normalization_errors", [])
        odcs_normalization_warnings = instance.state_data.get("odcs_normalization_warnings", [])

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

        # Convert ODCS contract to string for storage
        import json
        odcs_raw = json.dumps(odcs_contract)

        # Determine normalization status
        if odcs_normalization_status:
            try:
                final_norm_status = NormalizationStatus(odcs_normalization_status)
            except (ValueError, TypeError):
                final_norm_status = NormalizationStatus.NORMALIZED_OK if odcs_hub_contract else NormalizationStatus.NORMALIZATION_FAILED
        else:
            final_norm_status = NormalizationStatus.NORMALIZED_OK if odcs_hub_contract else NormalizationStatus.NORMALIZATION_FAILED

        # Create ODCS contract with error handling
        try:
            odcs_contract_obj = Contract.objects.create(
                tenant=tenant,
                asset=asset,
                version=version,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version=detected_spec_version,
                original_format="JSON",
                original_raw=odcs_raw,
                hub_contract_version="1.0.0" if odcs_hub_contract else None,
                hub_contract_json=odcs_hub_contract,
                normalization_status=final_norm_status,
                normalization_errors=odcs_normalization_errors,
                normalization_warnings=odcs_normalization_warnings,
                created_by=user
            )
        except Exception as e:
            # Database error - transaction will rollback automatically
            logger.error(
                "Database error creating ODCS contract",
                workflow_instance_id=str(instance.id),
                tenant_id=tenant_id,
                error=str(e),
                exc_info=True
            )
            raise ValueError(f"ODCS_CONTRACT_CREATION_ERROR: Database error: {str(e)}") from e

        logger.info(
            "ODCS contract record created",
            workflow_instance_id=str(instance.id),
            odcs_contract_id=str(odcs_contract_obj.id),
            tenant_id=tenant_id
        )

        return {
            "odcs_contract_id": str(odcs_contract_obj.id),
            "state": {
                "odcs_contract_id": str(odcs_contract_obj.id)
            }
        }

    @staticmethod
    @transaction.atomic
    def _create_odps_contract_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create ODPS contract record.

        Args:
            input_data: Workflow input data (includes normalized HubContract)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with ODPS contract ID
        """
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Get data from state_data
        tenant_id = instance.state_data.get("tenant_id")
        user_id = instance.state_data.get("user_id")
        asset_id = instance.state_data.get("asset_id")
        original_raw = instance.state_data.get("original_raw")
        original_format = instance.state_data.get("original_format")
        odps_document_resolved = instance.state_data.get("odps_document_resolved")
        odps_version = instance.state_data.get("odps_version", "4.1")
        odps_hub_contract = instance.state_data.get("odps_hub_contract")
        odps_normalization_status = instance.state_data.get("odps_normalization_status")
        odps_normalization_errors = instance.state_data.get("odps_normalization_errors", [])
        odps_normalization_warnings = instance.state_data.get("odps_normalization_warnings", [])

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

        # Convert ODPS document to string for storage
        import json
        odps_raw = json.dumps(odps_document_resolved) if odps_document_resolved else original_raw

        # Determine normalization status
        if odps_normalization_status:
            try:
                final_norm_status = NormalizationStatus(odps_normalization_status)
            except (ValueError, TypeError):
                final_norm_status = NormalizationStatus.NORMALIZED_OK if odps_hub_contract else NormalizationStatus.NORMALIZATION_FAILED
        else:
            final_norm_status = NormalizationStatus.NORMALIZED_OK if odps_hub_contract else NormalizationStatus.NORMALIZATION_FAILED

        # Create ODPS contract with error handling
        try:
            odps_contract_obj = Contract.objects.create(
                tenant=tenant,
                asset=asset,
                version=version,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version=odps_version,
                original_format=original_format,
                original_raw=odps_raw,
                hub_contract_version="1.0.0" if odps_hub_contract else None,
                hub_contract_json=odps_hub_contract,
                normalization_status=final_norm_status,
                normalization_errors=odps_normalization_errors,
                normalization_warnings=odps_normalization_warnings,
                created_by=user
            )
        except Exception as e:
            # Database error - transaction will rollback automatically
            logger.error(
                "Database error creating ODPS contract",
                workflow_instance_id=str(instance.id),
                tenant_id=tenant_id,
                error=str(e),
                exc_info=True
            )
            raise ValueError(f"ODPS_CONTRACT_CREATION_ERROR: Database error: {str(e)}") from e

        logger.info(
            "ODPS contract record created",
            workflow_instance_id=str(instance.id),
            odps_contract_id=str(odps_contract_obj.id),
            tenant_id=tenant_id
        )

        # Send notification email for ODPS creation completion or normalization failure (Task 8.4.4)
        if user:
            try:
                from hub.apps.notifications.tasks import (
                    send_odps_creation_completion_email,
                    send_odps_normalization_failure_email
                )
                if final_norm_status == NormalizationStatus.NORMALIZATION_FAILED:
                    # Send normalization failure notification
                    error_message = '; '.join(odps_normalization_errors) if odps_normalization_errors else "ODPS normalization failed"
                    send_odps_normalization_failure_email.delay(
                        contract_id=str(odps_contract_obj.id),
                        error_message=error_message,
                        error_code="ODPS_NORMALIZATION_ERROR",
                        errors=odps_normalization_errors,
                        field_path=None
                    )
                else:
                    # Send creation completion notification
                    send_odps_creation_completion_email.delay(str(odps_contract_obj.id))
            except Exception as e:
                # Log but don't fail ODPS creation if notification fails
                logger.warning(
                    "odps_creation_notification_failed",
                    workflow_instance_id=str(instance.id),
                    odps_contract_id=str(odps_contract_obj.id),
                    error=str(e),
                    message="Failed to send ODPS notification (non-critical)"
                )

        return {
            "odps_contract_id": str(odps_contract_obj.id),
            "state": {
                "odps_contract_id": str(odps_contract_obj.id)
            }
        }

    @staticmethod
    @transaction.atomic
    def _link_contracts_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Establish bidirectional link (ODPS ↔ ODCS).

        Args:
            input_data: Workflow input data (includes both contract IDs)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with linking results
        """
        odps_contract_id = instance.state_data.get("odps_contract_id") or input_data.get("odps_contract_id")
        odcs_contract_id = instance.state_data.get("odcs_contract_id") or input_data.get("odcs_contract_id")

        if not odps_contract_id:
            raise ValueError("odps_contract_id is required for linking")
        if not odcs_contract_id:
            raise ValueError("odcs_contract_id is required for linking")

        # Get tenant_id for validation
        tenant_id = instance.state_data.get("tenant_id")
        user_id = instance.state_data.get("user_id") or getattr(instance, 'created_by_id', None)

        # Publish linking status: starting (Task 7.3.2)
        try:
            from hub.apps.core.events.service_publishers import ODPSEventPublisher
            from hub.apps.core.events.publisher import EventPublisher
            odps_event_publisher = ODPSEventPublisher()
            odps_event_publisher._event_publisher = EventPublisher(
                service_name="workflow_engine",
                tenant_id=str(tenant_id) if tenant_id else None,
                user_id=str(user_id) if user_id else None,
            )
            # Publish start event
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="starting",
                progress_percentage=0.0,
                current_phase="validation",
                status_message="Starting contract linking",
                tenant_id=str(tenant_id) if tenant_id else None,
                user_id=str(user_id) if user_id else None,
            )
        except Exception as e:
            logger.warning(f"Failed to publish ODPS linking status event: {e}")

        try:
            # Validate linking (existence, compatibility, circular references)
            odps_contract, odcs_contract = validate_linking(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                tenant_id=tenant_id
            )

            # Publish linking status: validation passed (Task 7.3.2)
            try:
                from hub.apps.core.events.service_publishers import ODPSEventPublisher
                from hub.apps.core.events.publisher import EventPublisher
                odps_event_publisher = ODPSEventPublisher()
                odps_event_publisher._event_publisher = EventPublisher(
                    service_name="workflow_engine",
                    tenant_id=str(tenant_id) if tenant_id else None,
                    user_id=str(user_id) if user_id else None,
                )
                odps_event_publisher.publish_odps_linking_status(
                    odps_contract_id=odps_contract_id,
                    odcs_contract_id=odcs_contract_id,
                    status="validating",
                    progress_percentage=50.0,
                    current_phase="validation",
                    validation_passed=True,
                    status_message="Linking validation passed",
                    tenant_id=str(tenant_id) if tenant_id else None,
                    user_id=str(user_id) if user_id else None,
                )
            except Exception as e:
                logger.warning(f"Failed to publish ODPS linking status event: {e}")

            # Establish bidirectional link
            # ODPS → ODCS: Store in ODPS contract's hub_contract_json.extensions.x_odps_link
            if odps_contract.hub_contract_json:
                if "extensions" not in odps_contract.hub_contract_json:
                    odps_contract.hub_contract_json["extensions"] = {}
                if "x_odps" not in odps_contract.hub_contract_json["extensions"]:
                    odps_contract.hub_contract_json["extensions"]["x_odps"] = {}
                odps_contract.hub_contract_json["extensions"]["x_odps"]["odcs_link"] = str(odcs_contract_id)
                odps_contract.save(update_fields=["hub_contract_json"])

            # ODCS → ODPS: Store in ODCS contract's hub_contract_json.extensions.x_odps_link
            if odcs_contract.hub_contract_json:
                if "extensions" not in odcs_contract.hub_contract_json:
                    odcs_contract.hub_contract_json["extensions"] = {}
                if "x_odps" not in odcs_contract.hub_contract_json["extensions"]:
                    odcs_contract.hub_contract_json["extensions"]["x_odps"] = {}
                odcs_contract.hub_contract_json["extensions"]["x_odps"]["odps_link"] = str(odps_contract_id)
                odcs_contract.save(update_fields=["hub_contract_json"])

            logger.info(
                "Contracts linked bidirectionally",
                workflow_instance_id=str(instance.id),
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id
            )

            # Publish linking status: completed (Task 7.3.2)
            try:
                from hub.apps.core.events.service_publishers import ODPSEventPublisher
                from hub.apps.core.events.publisher import EventPublisher
                odps_event_publisher = ODPSEventPublisher()
                odps_event_publisher._event_publisher = EventPublisher(
                    service_name="workflow_engine",
                    tenant_id=str(tenant_id) if tenant_id else None,
                    user_id=str(user_id) if user_id else None,
                )
                odps_event_publisher.publish_odps_linking_status(
                    odps_contract_id=odps_contract_id,
                    odcs_contract_id=odcs_contract_id,
                    status="completed",
                    progress_percentage=100.0,
                    current_phase="completed",
                    validation_passed=True,
                    link_type="bidirectional",
                    status_message="Contracts linked successfully",
                    tenant_id=str(tenant_id) if tenant_id else None,
                    user_id=str(user_id) if user_id else None,
                )
            except Exception as e:
                logger.warning(f"Failed to publish ODPS linking status event: {e}")

            # Send notification email for ODPS linking status (Task 8.4.4)
            try:
                from hub.apps.notifications.tasks import send_odps_linking_status_email
                send_odps_linking_status_email.delay(
                    odps_contract_id=odps_contract_id,
                    status="completed",
                    status_message="Contracts linked successfully",
                    odcs_contract_id=odcs_contract_id,
                    progress_percentage=100.0,
                    current_phase="completed",
                    validation_passed=True,
                    user_id=str(user_id) if user_id else None,
                    tenant_id=str(tenant_id) if tenant_id else None
                )
            except Exception as e:
                # Log but don't fail linking if notification fails
                logger.warning(
                    "odps_linking_notification_failed",
                    workflow_instance_id=str(instance.id),
                    odps_contract_id=odps_contract_id,
                    error=str(e),
                    message="Failed to send ODPS linking status notification (non-critical)"
                )

            return {
                "linked": True,
                "odps_contract_id": odps_contract_id,
                "odcs_contract_id": odcs_contract_id
            }
        except LinkingValidationError as e:
            # Publish linking status: validation failed (Task 7.3.2)
            try:
                from hub.apps.core.events.service_publishers import ODPSEventPublisher
                from hub.apps.core.events.publisher import EventPublisher
                odps_event_publisher = ODPSEventPublisher()
                odps_event_publisher._event_publisher = EventPublisher(
                    service_name="workflow_engine",
                    tenant_id=str(tenant_id) if tenant_id else None,
                    user_id=str(user_id) if user_id else None,
                )
                odps_event_publisher.publish_odps_linking_status(
                    odps_contract_id=odps_contract_id,
                    odcs_contract_id=odcs_contract_id,
                    status="failed",
                    progress_percentage=50.0,
                    current_phase="validation",
                    validation_passed=False,
                    validation_errors=[str(e)],
                    status_message=f"Linking validation failed: {str(e)}",
                    tenant_id=str(tenant_id) if tenant_id else None,
                    user_id=str(user_id) if user_id else None,
                )
            except Exception as event_error:
                logger.warning(f"Failed to publish ODPS linking status event: {event_error}")

            # Send notification email for ODPS linking failure (Task 8.4.4)
            try:
                from hub.apps.notifications.tasks import send_odps_linking_status_email
                send_odps_linking_status_email.delay(
                    odps_contract_id=odps_contract_id,
                    status="failed",
                    status_message=f"Linking validation failed: {str(e)}",
                    odcs_contract_id=odcs_contract_id,
                    progress_percentage=50.0,
                    current_phase="validation",
                    validation_passed=False,
                    user_id=str(user_id) if user_id else None,
                    tenant_id=str(tenant_id) if tenant_id else None
                )
            except Exception as notify_error:
                # Log but don't fail linking if notification fails
                logger.warning(
                    "odps_linking_notification_failed",
                    workflow_instance_id=str(instance.id),
                    odps_contract_id=odps_contract_id,
                    error=str(notify_error),
                    message="Failed to send ODPS linking failure notification (non-critical)"
                )

            # Re-raise validation errors as-is (they're already ODPSLinkingError subclasses)
            raise
        except Contract.DoesNotExist as e:
            raise ODPSLinkingError(
                message=f"Contract not found: {str(e)}",
                error_code="ODPS_LINKING_ERROR"
            ) from e
        except Exception as e:
            raise ODPSLinkingError(
                message=f"Failed to link contracts: {str(e)}",
                error_code="ODPS_LINKING_ERROR",
                context={
                    "odps_contract_id": odps_contract_id,
                    "odcs_contract_id": odcs_contract_id
                }
            ) from e

    @staticmethod
    @transaction.atomic
    def _link_data_file_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Optional: Link data file (create Asset).

        Args:
            input_data: Workflow input data (includes contract IDs and optional file_id)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with asset_id (if created)
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Get data from state_data
        tenant_id = instance.state_data.get("tenant_id")
        user_id = instance.state_data.get("user_id")
        file_id = input_data.get("file_id") or instance.state_data.get("file_id")
        odps_contract_id = instance.state_data.get("odps_contract_id")
        odcs_contract_id = instance.state_data.get("odcs_contract_id")

        # Optional: asset metadata from input
        asset_key = input_data.get("asset_key")
        asset_name = input_data.get("asset_name")
        asset_description = input_data.get("asset_description")
        asset_domain = input_data.get("asset_domain")

        # Skip if no file_id provided (optional step)
        if not file_id:
            logger.info(
                "Skipping data file linking: file_id not provided",
                workflow_instance_id=str(instance.id)
            )
            return {
                "skipped": True,
                "reason": "file_id not provided"
            }

        try:
            # Get tenant and user
            tenant = Tenant.objects.get(id=tenant_id)
            user = User.objects.get(id=user_id)

            # Get file
            from hub.apps.files.models import File
            try:
                file_obj = File.objects.get(id=file_id, tenant=tenant)
            except File.DoesNotExist:
                logger.warning(
                    "File not found for asset creation",
                    workflow_instance_id=str(instance.id),
                    file_id=file_id
                )
                return {
                    "skipped": True,
                    "reason": f"File not found: {file_id}"
                }

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
                    asset_key=asset_key
                )
                return {
                    "skipped": True,
                    "reason": f"Asset with key already exists: {asset_key}"
                }

            # Create asset
            asset = Asset.objects.create(
                tenant=tenant,
                key=asset_key,
                name=asset_name,
                description=asset_description,
                domain=asset_domain,
                status=AssetStatus.DRAFT,
                visibility=AssetVisibility.INTERNAL,
                created_by=user
            )

            # Link contracts to asset
            if odps_contract_id:
                try:
                    odps_contract = Contract.objects.get(id=odps_contract_id)
                    odps_contract.asset = asset
                    # Update version if needed
                    latest_contract = Contract.objects.filter(
                        tenant=tenant,
                        asset=asset
                    ).exclude(id=odps_contract_id).order_by('-version').first()
                    if latest_contract:
                        odps_contract.version = latest_contract.version + 1
                    else:
                        odps_contract.version = 1
                    odps_contract.save(update_fields=['asset', 'version'])
                except Contract.DoesNotExist:
                    logger.warning(
                        "ODPS contract not found for asset linking",
                        workflow_instance_id=str(instance.id),
                        odps_contract_id=odps_contract_id
                    )

            if odcs_contract_id:
                try:
                    odcs_contract = Contract.objects.get(id=odcs_contract_id)
                    odcs_contract.asset = asset
                    # Update version if needed
                    latest_contract = Contract.objects.filter(
                        tenant=tenant,
                        asset=asset
                    ).exclude(id=odcs_contract_id).order_by('-version').first()
                    if latest_contract:
                        odcs_contract.version = latest_contract.version + 1
                    else:
                        odcs_contract.version = 1
                    odcs_contract.save(update_fields=['asset', 'version'])
                except Contract.DoesNotExist:
                    logger.warning(
                        "ODCS contract not found for asset linking",
                        workflow_instance_id=str(instance.id),
                        odcs_contract_id=odcs_contract_id
                    )

            logger.info(
                "Asset created and linked to contracts",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                file_id=file_id
            )

            return {
                "asset_id": str(asset.id),
                "asset_key": asset_key,
                "state": {
                    "asset_id": str(asset.id)
                }
            }
        except Exception as e:
            # Database error - transaction will rollback automatically
            logger.error(
                "Error creating asset for data file",
                workflow_instance_id=str(instance.id),
                file_id=file_id,
                error=str(e),
                exc_info=True
            )
            raise ValueError(f"ASSET_CREATION_ERROR: Failed to create asset: {str(e)}") from e

    @staticmethod
    def _index_for_search_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Index for search (ODPS product + ODCS technical).

        Args:
            input_data: Workflow input data (includes contract IDs)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with indexing results
        """
        odps_contract_id = instance.state_data.get("odps_contract_id") or input_data.get("odps_contract_id")
        odcs_contract_id = instance.state_data.get("odcs_contract_id") or input_data.get("odcs_contract_id")

        indexed_contracts = []

        # Index ODPS contract
        if odps_contract_id:
            try:
                odps_contract = Contract.objects.get(id=odps_contract_id)
                search_index = SearchIndexer.index_contract(odps_contract)
                indexed_contracts.append({
                    "contract_id": odps_contract_id,
                    "contract_type": "ODPS",
                    "search_index_id": str(search_index.id)
                })
            except Exception as e:
                logger.warning(
                    "Failed to index ODPS contract (non-critical)",
                    workflow_instance_id=str(instance.id),
                    odps_contract_id=odps_contract_id,
                    error=str(e)
                )

        # Index ODCS contract
        if odcs_contract_id:
            try:
                odcs_contract = Contract.objects.get(id=odcs_contract_id)
                search_index = SearchIndexer.index_contract(odcs_contract)
                indexed_contracts.append({
                    "contract_id": odcs_contract_id,
                    "contract_type": "ODCS",
                    "search_index_id": str(search_index.id)
                })
            except Exception as e:
                logger.warning(
                    "Failed to index ODCS contract (non-critical)",
                    workflow_instance_id=str(instance.id),
                    odcs_contract_id=odcs_contract_id,
                    error=str(e)
                )

        logger.info(
            "Contracts indexed for search",
            workflow_instance_id=str(instance.id),
            indexed_count=len(indexed_contracts)
        )

        return {
            "indexed": True,
            "indexed_contracts": indexed_contracts
        }

    @staticmethod
    def _semantic_mapping_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Map ODPS to RDF (async job).

        Args:
            input_data: Workflow input data (includes contract IDs)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with semantic mapping results
        """
        odps_contract_id = instance.state_data.get("odps_contract_id") or input_data.get("odps_contract_id")
        odcs_contract_id = instance.state_data.get("odcs_contract_id") or input_data.get("odcs_contract_id")

        mapped_contracts = []

        # Map ODPS contract to RDF
        if odps_contract_id:
            try:
                odps_contract = Contract.objects.get(id=odps_contract_id)
                if odps_contract.hub_contract_json:
                    semantic_resource = map_contract_to_semantic(
                        contract=odps_contract,
                        tenant=odps_contract.tenant,
                        use_cache=False
                    )
                    if semantic_resource:
                        mapped_contracts.append({
                            "contract_id": odps_contract_id,
                            "contract_type": "ODPS",
                            "semantic_resource_id": str(semantic_resource.id),
                            "uri": semantic_resource.uri
                        })
            except Exception as e:
                logger.warning(
                    "Failed to map ODPS contract to RDF (non-critical)",
                    workflow_instance_id=str(instance.id),
                    odps_contract_id=odps_contract_id,
                    error=str(e)
                )

        # Map ODCS contract to RDF
        if odcs_contract_id:
            try:
                odcs_contract = Contract.objects.get(id=odcs_contract_id)
                if odcs_contract.hub_contract_json:
                    semantic_resource = map_contract_to_semantic(
                        contract=odcs_contract,
                        tenant=odcs_contract.tenant,
                        use_cache=False
                    )
                    if semantic_resource:
                        mapped_contracts.append({
                            "contract_id": odcs_contract_id,
                            "contract_type": "ODCS",
                            "semantic_resource_id": str(semantic_resource.id),
                            "uri": semantic_resource.uri
                        })
            except Exception as e:
                logger.warning(
                    "Failed to map ODCS contract to RDF (non-critical)",
                    workflow_instance_id=str(instance.id),
                    odcs_contract_id=odcs_contract_id,
                    error=str(e)
                )

        logger.info(
            "Contracts mapped to RDF",
            workflow_instance_id=str(instance.id),
            mapped_count=len(mapped_contracts)
        )

        return {
            "semantic_mapping_generated": len(mapped_contracts) > 0,
            "mapped_contracts": mapped_contracts
        }

    # Compensation tasks

    @staticmethod
    def _rollback_normalize_odcs_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback ODCS normalization (no-op, normalization is stateless)"""
        logger.info(
            "ODCS normalization rollback (no-op)",
            workflow_instance_id=str(instance.id)
        )
        return {"rolled_back": True}

    @staticmethod
    def _rollback_normalize_odps_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback ODPS normalization (no-op, normalization is stateless)"""
        logger.info(
            "ODPS normalization rollback (no-op)",
            workflow_instance_id=str(instance.id)
        )
        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_odcs_contract_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback ODCS contract creation (delete contract)"""
        odcs_contract_id = instance.state_data.get("odcs_contract_id")

        if odcs_contract_id:
            try:
                contract = Contract.objects.get(id=odcs_contract_id)
                contract.delete()
                logger.info(
                    "ODCS contract rolled back (deleted)",
                    workflow_instance_id=str(instance.id),
                    odcs_contract_id=odcs_contract_id
                )
            except Contract.DoesNotExist:
                logger.warning(
                    "ODCS contract not found for rollback",
                    workflow_instance_id=str(instance.id),
                    odcs_contract_id=odcs_contract_id
                )

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_odps_contract_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback ODPS contract creation (delete contract)"""
        odps_contract_id = instance.state_data.get("odps_contract_id")

        if odps_contract_id:
            try:
                contract = Contract.objects.get(id=odps_contract_id)
                contract.delete()
                logger.info(
                    "ODPS contract rolled back (deleted)",
                    workflow_instance_id=str(instance.id),
                    odps_contract_id=odps_contract_id
                )
            except Contract.DoesNotExist:
                logger.warning(
                    "ODPS contract not found for rollback",
                    workflow_instance_id=str(instance.id),
                    odps_contract_id=odps_contract_id
                )

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_link_contracts_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback contract linking (remove links)"""
        odps_contract_id = instance.state_data.get("odps_contract_id")
        odcs_contract_id = instance.state_data.get("odcs_contract_id")

        if odps_contract_id:
            try:
                odps_contract = Contract.objects.get(id=odps_contract_id)
                if odps_contract.hub_contract_json and "extensions" in odps_contract.hub_contract_json:
                    if "x_odps" in odps_contract.hub_contract_json["extensions"]:
                        odps_contract.hub_contract_json["extensions"]["x_odps"].pop("odcs_link", None)
                        odps_contract.save(update_fields=["hub_contract_json"])
            except Contract.DoesNotExist:
                pass

        if odcs_contract_id:
            try:
                odcs_contract = Contract.objects.get(id=odcs_contract_id)
                if odcs_contract.hub_contract_json and "extensions" in odcs_contract.hub_contract_json:
                    if "x_odps" in odcs_contract.hub_contract_json["extensions"]:
                        odcs_contract.hub_contract_json["extensions"]["x_odps"].pop("odps_link", None)
                        odcs_contract.save(update_fields=["hub_contract_json"])
            except Contract.DoesNotExist:
                pass

        logger.info(
            "Contract links rolled back",
            workflow_instance_id=str(instance.id)
        )

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_link_data_file_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Rollback asset creation (delete asset and unlink contracts)"""
        asset_id = instance.state_data.get("asset_id")
        odps_contract_id = instance.state_data.get("odps_contract_id")
        odcs_contract_id = instance.state_data.get("odcs_contract_id")

        if asset_id:
            try:
                from hub.apps.assets.models import Asset
                asset = Asset.objects.get(id=asset_id)

                # Unlink contracts from asset
                if odps_contract_id:
                    try:
                        odps_contract = Contract.objects.get(id=odps_contract_id)
                        odps_contract.asset = None
                        odps_contract.save(update_fields=['asset'])
                    except Contract.DoesNotExist:
                        pass

                if odcs_contract_id:
                    try:
                        odcs_contract = Contract.objects.get(id=odcs_contract_id)
                        odcs_contract.asset = None
                        odcs_contract.save(update_fields=['asset'])
                    except Contract.DoesNotExist:
                        pass

                # Delete asset
                asset.delete()

                logger.info(
                    "Asset rolled back (deleted)",
                    workflow_instance_id=str(instance.id),
                    asset_id=asset_id
                )
            except Asset.DoesNotExist:
                logger.warning(
                    "Asset not found for rollback",
                    workflow_instance_id=str(instance.id),
                    asset_id=asset_id
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
        resolve_external_refs: bool = True,
        engine: Optional[WorkflowEngine] = None,
        registry: Optional[WorkflowRegistry] = None
    ) -> Dict[str, Any]:
        """
        Execute product creation workflow (Product-First flow).

        Args:
            original_raw: ODPS document content
            original_format: ODPS document format (JSON or YAML)
            tenant_id: Tenant ID
            user_id: User ID who created the product
            asset_id: Optional asset ID to link contracts to
            resolve_external_refs: If True, resolve external $ref references (default: True)
            engine: Optional WorkflowEngine instance (creates new if not provided)
            registry: Optional WorkflowRegistry instance (creates new if not provided)

        Returns:
            Dictionary with created contracts:
            {
                "odps_contract": Contract instance,
                "odcs_contract": Contract instance,
                "workflow_instance_id": str
            }

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

        # Determine external ref handling
        if resolve_external_refs:
            external_ref_handling = ExternalRefHandling.RESOLVE.value
        else:
            external_ref_handling = ExternalRefHandling.DISABLE.value

        # Prepare workflow input
        workflow_input = {
            "original_raw": original_raw,
            "original_format": original_format,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "asset_id": asset_id,
            "external_ref_handling": external_ref_handling
        }

        # Create workflow instance
        workflow_instance = engine.create_instance(
            workflow_name=cls.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=tenant_id,
            created_by_id=user_id
        )

        # Initialize state_data from input_data
        if not workflow_instance.state_data:
            workflow_instance.state_data = workflow_input.copy()
            workflow_instance.save(update_fields=['state_data'])

        # Start and execute workflow
        workflow_instance = engine.start_instance(str(workflow_instance.id))
        workflow_instance = engine.execute_instance(str(workflow_instance.id))

        # Check workflow status
        workflow_instance.refresh_from_db()
        if workflow_instance.status != WorkflowStatus.COMPLETED:
            error_message = f"Product creation workflow failed with status: {workflow_instance.status}"
            if workflow_instance.state_data.get("error"):
                error_message = workflow_instance.state_data.get("error")
            raise ValueError(f"Product creation workflow failed: {error_message}")

        # Get created contracts from state_data
        odps_contract_id = workflow_instance.state_data.get("odps_contract_id")
        odcs_contract_id = workflow_instance.state_data.get("odcs_contract_id")

        if not odps_contract_id or not odcs_contract_id:
            raise ValueError("Product creation workflow completed but contracts not found in state_data")

        # Retrieve contracts
        try:
            odps_contract = Contract.objects.get(id=odps_contract_id)
            odcs_contract = Contract.objects.get(id=odcs_contract_id)
        except Contract.DoesNotExist as e:
            raise ValueError(f"Contract not found after workflow completion: {str(e)}")

        logger.info(
            "Product creation workflow completed successfully",
            workflow_instance_id=str(workflow_instance.id),
            odps_contract_id=str(odps_contract.id),
            odcs_contract_id=str(odcs_contract.id),
            tenant_id=tenant_id
        )

        return {
            "odps_contract": odps_contract,
            "odcs_contract": odcs_contract,
            "workflow_instance_id": str(workflow_instance.id)
        }

