"""
ODPS Job Handlers

Handlers for ODPS (Open Data Product Specification) job execution.

This module contains all ODPS-related job handlers:
- Normalization: Convert ODPS to HubContract format
- Ref Resolution: Resolve $ref references in ODPS contracts
- Export: Generate ODPS from HubContract format
- Semantic Mapping: Map ODPS to RDF/semantic representation
- Linking: Establish bidirectional links between ODPS and ODCS contracts

SAVING CHECKPOINT: This module contains ODPS job handlers. Due to the complexity
and size of ODPS operations, this file exceeds 700 lines. Checkpoint comments
are added at logical boundaries (every ~500-700 lines per project rule).
"""

import structlog
from django.db import transaction
from django.utils import timezone

from .models import Job

logger = structlog.get_logger(__name__)

# SAVING CHECKPOINT: End of imports and setup (~20 lines)


# SAVING CHECKPOINT: Start of normalization handler

def _execute_odps_normalization_job(job_obj: Job) -> dict:
    """
    Execute ODPS_NORMALIZATION job.

    Normalizes an ODPS contract to HubContract format with progress tracking
    and event publishing.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with normalization results

    Raises:
        ValueError: If contract_id is missing, contract not found, or contract is not ODPS
        ConnectionError: If normalization service is unavailable
        Exception: For other errors
    """
    # Get contract ID from resource_id
    contract_id = job_obj.resource_id

    # Convert to string if it's a UUID object, handle None case
    if contract_id is not None:
        contract_id = str(contract_id)

    if not contract_id:
        raise ValueError("Contract ID is required for ODPS_NORMALIZATION job")

    try:
        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract, NormalizationStatus, OriginalSpecType
        from hub.apps.contracts.normalization_service import NormalizationService
        from hub.apps.core.events.publisher import EventPublisher
        from hub.apps.core.events.service_publishers import ODPSEventPublisher

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"Contract {contract_id} not found")

        # Validate contract is ODPS
        if contract.original_spec_type != OriginalSpecType.ODPS:
            raise ValueError(
                f"Contract {contract_id} is not an ODPS contract "
                f"(spec_type: {contract.original_spec_type})"
            )

        if not contract.original_raw or contract.original_raw.strip() == "":
            raise ValueError(f"Contract {contract_id} has no original_raw content")

        # Initialize event publisher
        odps_event_publisher = ODPSEventPublisher()
        odps_event_publisher._event_publisher = EventPublisher(
            service_name="job_service",
            tenant_id=str(contract.tenant.id) if contract.tenant else None,
            user_id=str(job_obj.created_by.id) if job_obj.created_by else None,
        )

        tenant_id = str(contract.tenant.id) if contract.tenant else None
        user_id = str(job_obj.created_by.id) if job_obj.created_by else None

        # Update progress: Starting normalization (0%)
        job_obj.details_json = job_obj.details_json or {}
        job_obj.details_json["progress_percentage"] = 0.0
        job_obj.details_json["current_phase"] = "initialization"
        job_obj.details_json["status_message"] = "Starting ODPS normalization"
        job_obj.save(update_fields=["details_json", "updated_at"])

        # Publish normalization started event
        try:
            odps_event_publisher.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percentage=0.0,
                current_phase="initialization",
                phase_index=0,
                total_phases=5,
                status_message="Starting ODPS normalization",
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_normalization_progress_event_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS normalization progress event",
            )

        # Update progress: Parsing contract (20%)
        job_obj.details_json["progress_percentage"] = 20.0
        job_obj.details_json["current_phase"] = "parsing"
        job_obj.details_json["status_message"] = "Parsing ODPS contract"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percentage=20.0,
                current_phase="parsing",
                phase_index=1,
                total_phases=5,
                status_message="Parsing ODPS contract",
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Update progress: Normalizing to HubContract (40%)
        job_obj.details_json["progress_percentage"] = 40.0
        job_obj.details_json["current_phase"] = "normalization"
        job_obj.details_json["status_message"] = "Normalizing ODPS to HubContract"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percentage=40.0,
                current_phase="normalization",
                phase_index=2,
                total_phases=5,
                status_message="Normalizing ODPS to HubContract",
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Normalize contract using NormalizationService (event publishing integrated)
        # This will publish normalization.started, normalization.completed/failed events
        from hub.apps.core.services.base import ValidationError as ServiceValidationError

        normalization_service = NormalizationService(tenant_id=tenant_id, user_id=user_id)
        try:
            (
                hub_contract,
                detected_spec_type,
                detected_spec_version,
                norm_status,
                norm_errors,
                norm_warnings,
            ) = normalization_service.normalize_contract(
                raw_contract=contract.original_raw,
                format=contract.original_format,
                spec_type="ODPS",
                tenant_id=tenant_id,
                user_id=user_id,
                contract_id=str(contract_id),  # Contract exists, so events will be published
            )
        except ServiceValidationError as e:
            # Invalid ODPS / normalization failed (e.g. missing required fields)
            error_message = str(e)
            job_obj.details_json = job_obj.details_json or {}
            job_obj.details_json["progress_percentage"] = 100.0
            job_obj.details_json["current_phase"] = "failed"
            job_obj.details_json["status_message"] = f"Normalization failed: {error_message}"
            job_obj.save(update_fields=["details_json", "updated_at"])
            try:
                odps_event_publisher.publish_odps_normalization_progress(
                    contract_id=str(contract_id),
                    progress_percentage=100.0,
                    current_phase="failed",
                    phase_index=5,
                    total_phases=5,
                    status_message=f"Normalization failed: {error_message}",
                    odps_version=contract.original_spec_version,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            except Exception as event_err:
                logger.warning(
                    "odps_job_event_publish_failed",
                    job_id=str(job_obj.id),
                    contract_id=str(contract_id),
                    extra={"error_type": type(event_err).__name__, "error": str(event_err)},
                )
            raise ValueError(f"ODPS normalization failed: {error_message}") from e

        # Update progress: Validation (60%)
        job_obj.details_json["progress_percentage"] = 60.0
        job_obj.details_json["current_phase"] = "validation"
        job_obj.details_json["status_message"] = "Validating normalized HubContract"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percentage=60.0,
                current_phase="validation",
                phase_index=3,
                total_phases=5,
                status_message="Validating normalized HubContract",
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Check normalization status
        if norm_status == NormalizationStatus.NORMALIZATION_FAILED:
            error_message = norm_errors[0] if norm_errors else "ODPS normalization failed"

            # Update progress: Failed (100%)
            job_obj.details_json["progress_percentage"] = 100.0
            job_obj.details_json["current_phase"] = "failed"
            job_obj.details_json["status_message"] = f"Normalization failed: {error_message}"
            job_obj.save(update_fields=["details_json", "updated_at"])

            # Publish failure event
            try:
                odps_event_publisher.publish_odps_normalization_progress(
                    contract_id=str(contract_id),
                    progress_percentage=100.0,
                    current_phase="failed",
                    phase_index=5,
                    total_phases=5,
                    status_message=f"Normalization failed: {error_message}",
                    odps_version=contract.original_spec_version,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            except Exception as event_err:
                logger.warning(
                    "odps_job_event_publish_failed",
                    job_id=str(job_obj.id),
                    contract_id=str(contract_id),
                    extra={"error_type": type(event_err).__name__, "error": str(event_err)},
                )
            raise ValueError(f"ODPS normalization failed: {error_message}")

        # Update progress: Saving results (80%)
        job_obj.details_json["progress_percentage"] = 80.0
        job_obj.details_json["current_phase"] = "saving"
        job_obj.details_json["status_message"] = "Saving normalized HubContract"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percentage=80.0,
                current_phase="saving",
                phase_index=4,
                total_phases=5,
                status_message="Saving normalized HubContract",
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Update contract with normalized data
        with transaction.atomic():
            contract.hub_contract_json = hub_contract
            contract.normalization_status = norm_status
            contract.save(update_fields=["hub_contract_json", "normalization_status", "updated_at"])

        # Update progress: Completed (100%)
        job_obj.details_json["progress_percentage"] = 100.0
        job_obj.details_json["current_phase"] = "completed"
        job_obj.details_json["status_message"] = "ODPS normalization completed successfully"
        job_obj.save(update_fields=["details_json", "updated_at"])

        # Publish completion event
        try:
            odps_event_publisher.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percentage=100.0,
                current_phase="completed",
                phase_index=5,
                total_phases=5,
                status_message="ODPS normalization completed successfully",
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )

            # Publish normalized event
            odps_event_publisher.publish_odps_normalized(
                contract_id=str(contract_id),
                normalization_status=norm_status.value,
                normalization_errors=norm_errors,
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_normalization_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS normalization completion event",
            )

        logger.info(
            "odps_normalization_job_completed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id),
            tenant_id=tenant_id,
            normalization_status=norm_status.value,
            detected_spec_type=detected_spec_type,
            detected_spec_version=detected_spec_version,
            warnings_count=len(norm_warnings),
            message=f"ODPS normalization job completed for contract {contract_id}",
        )

        return {
            "status": "completed",
            "normalization_status": norm_status.value,
            "detected_spec_type": detected_spec_type,
            "detected_spec_version": detected_spec_version,
            "normalization_errors": norm_errors,
            "normalization_warnings": norm_warnings,
            "contract_id": str(contract_id),
            "warnings_count": len(norm_warnings),
            "errors_count": len(norm_errors),
        }

    except (ValueError, ConnectionError):
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        logger.error(
            "odps_normalization_job_failed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id) if "contract_id" in locals() else None,
            error=str(e),
            exc_info=True,
            message=f"ODPS normalization job failed: {str(e)}",
        )
        raise Exception(f"ODPS normalization failed: {str(e)}") from e


# SAVING CHECKPOINT: Start of ref_resolution handler

def _execute_odps_ref_resolution_job(job_obj: Job) -> dict:
    """
    Execute ODPS_REF_RESOLUTION job.

    Resolves all $ref references in an ODPS contract with progress tracking
    and event publishing.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with ref resolution results

    Raises:
        ValueError: If contract_id is missing, contract not found, or contract is not ODPS
        ConnectionError: If ref resolution service is unavailable
        Exception: For other errors
    """
    # Get contract ID from resource_id
    contract_id = job_obj.resource_id

    # Convert to string if it's a UUID object, handle None case
    if contract_id is not None:
        contract_id = str(contract_id)

    if not contract_id:
        raise ValueError("Contract ID is required for ODPS_REF_RESOLUTION job")

    try:
        # Import here to avoid circular imports
        import json

        from hub.apps.contracts.models import Contract, OriginalSpecType
        from hub.apps.contracts.odps_errors import ODPSRefResolutionError
        from hub.apps.contracts.odps_parser import ODPSParser
        from hub.apps.contracts.ref_resolver import ExternalRefHandling, RefResolver
        from hub.apps.core.events.publisher import EventPublisher
        from hub.apps.core.events.service_publishers import ODPSEventPublisher

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"Contract {contract_id} not found")

        # Validate contract is ODPS
        if contract.original_spec_type != OriginalSpecType.ODPS:
            raise ValueError(
                f"Contract {contract_id} is not an ODPS contract "
                f"(spec_type: {contract.original_spec_type})"
            )

        if not contract.original_raw or contract.original_raw.strip() == "":
            raise ValueError(f"Contract {contract_id} has no original_raw content")

        # Initialize event publisher
        odps_event_publisher = ODPSEventPublisher()
        odps_event_publisher._event_publisher = EventPublisher(
            service_name="job_service",
            tenant_id=str(contract.tenant.id) if contract.tenant else None,
            user_id=str(job_obj.created_by.id) if job_obj.created_by else None,
        )

        tenant_id = str(contract.tenant.id) if contract.tenant else None
        user_id = str(job_obj.created_by.id) if job_obj.created_by else None

        # Update progress: Starting ref resolution (0%)
        job_obj.details_json = job_obj.details_json or {}
        job_obj.details_json["progress_percentage"] = 0.0
        job_obj.details_json["current_phase"] = "initialization"
        job_obj.details_json["status_message"] = "Starting ODPS $ref resolution"
        job_obj.save(update_fields=["details_json", "updated_at"])

        # Publish ref resolution started event
        try:
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percentage=0.0,
                refs_processed=0,
                refs_total=None,
                status_message="Starting ODPS $ref resolution",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_ref_progress_event_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS ref progress event",
            )

        # Update progress: Parsing document (10%)
        job_obj.details_json["progress_percentage"] = 10.0
        job_obj.details_json["current_phase"] = "parsing"
        job_obj.details_json["status_message"] = "Parsing ODPS document"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percentage=10.0,
                refs_processed=0,
                refs_total=None,
                status_message="Parsing ODPS document",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Parse ODPS document
        format_str = contract.original_format.lower() if contract.original_format else "json"
        odps_doc = ODPSParser.parse(content=contract.original_raw, format=format_str)

        # Update progress: Analyzing refs (20%)
        job_obj.details_json["progress_percentage"] = 20.0
        job_obj.details_json["current_phase"] = "analyzing"
        job_obj.details_json["status_message"] = "Analyzing $ref references"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percentage=20.0,
                refs_processed=0,
                refs_total=None,
                status_message="Analyzing $ref references",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Count refs for progress tracking (approximate)
        def count_refs(obj, count=0):
            """Recursively count $ref references in document"""
            if isinstance(obj, dict):
                if "$ref" in obj:
                    count += 1
                for value in obj.values():
                    count = count_refs(value, count)
            elif isinstance(obj, list):
                for item in obj:
                    count = count_refs(item, count)
            return count

        total_refs = count_refs(odps_doc)
        job_obj.details_json["refs_total"] = total_refs
        job_obj.save(update_fields=["details_json", "updated_at"])

        # Update progress: Resolving refs (30%)
        job_obj.details_json["progress_percentage"] = 30.0
        job_obj.details_json["current_phase"] = "resolving"
        job_obj.details_json["status_message"] = f"Resolving {total_refs} $ref references"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percentage=30.0,
                refs_processed=0,
                refs_total=total_refs,
                status_message=f"Resolving {total_refs} $ref references",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Get external ref handling mode from job details (default: RESOLVE)
        external_ref_handling_str = job_obj.details_json.get("external_ref_handling", "resolve")
        try:
            external_ref_handling = ExternalRefHandling(external_ref_handling_str.lower())
        except ValueError:
            external_ref_handling = ExternalRefHandling.RESOLVE

        # Create resolver
        resolver = RefResolver(tenant_id=tenant_id, user_id=user_id)

        # Resolve all refs
        try:
            original_doc, resolved_doc = resolver.resolve_all_refs(
                document=odps_doc,
                preserve_original=True,
                external_ref_handling=external_ref_handling,
            )
        except ODPSRefResolutionError as e:
            # Update progress: Failed (100%)
            job_obj.details_json["progress_percentage"] = 100.0
            job_obj.details_json["current_phase"] = "failed"
            job_obj.details_json["status_message"] = f"$ref resolution failed: {str(e)}"
            job_obj.save(update_fields=["details_json", "updated_at"])

            # Publish failure event
            try:
                odps_event_publisher.publish_odps_ref_failed(
                    contract_id=str(contract_id),
                    ref_path=getattr(e, "ref_path", "unknown"),
                    ref_type=getattr(e, "ref_type", "unknown"),
                    error_message=str(e),
                    error_code=getattr(e, "error_code", None),
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            except Exception as event_err:
                logger.warning(
                    "odps_job_event_publish_failed",
                    job_id=str(job_obj.id),
                    contract_id=str(contract_id),
                    extra={"error_type": type(event_err).__name__, "error": str(event_err)},
                )
            raise ValueError(f"ODPS $ref resolution failed: {str(e)}")

        # Update progress: Saving results (90%)
        job_obj.details_json["progress_percentage"] = 90.0
        job_obj.details_json["current_phase"] = "saving"
        job_obj.details_json["status_message"] = "Saving resolved document"
        job_obj.details_json["refs_processed"] = total_refs
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percentage=90.0,
                refs_processed=total_refs,
                refs_total=total_refs,
                status_message="Saving resolved document",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Serialize resolved document
        if format_str == "yaml":
            import yaml

            resolved_raw = yaml.dump(resolved_doc, default_flow_style=False, sort_keys=False)
        else:
            resolved_raw = json.dumps(resolved_doc, indent=2)

        # Update contract with resolved document
        with transaction.atomic():
            # Store resolved document in original_raw_resolved if field exists, otherwise update original_raw
            if hasattr(contract, "original_raw_resolved"):
                contract.original_raw_resolved = resolved_raw
                contract.save(update_fields=["original_raw_resolved", "updated_at"])
            else:
                # Fallback: update original_raw (this replaces the original, which may not be desired)
                # In production, original_raw_resolved should be available
                contract.original_raw = resolved_raw
                contract.save(update_fields=["original_raw", "updated_at"])

        # Update progress: Completed (100%)
        job_obj.details_json["progress_percentage"] = 100.0
        job_obj.details_json["current_phase"] = "completed"
        job_obj.details_json["status_message"] = (
            f"Successfully resolved {total_refs} $ref references"
        )
        job_obj.save(update_fields=["details_json", "updated_at"])

        # Calculate duration (use started_at if available, otherwise use job creation time)
        if job_obj.started_at:
            duration = (timezone.now() - job_obj.started_at).total_seconds()
        elif job_obj.created_at:
            duration = (timezone.now() - job_obj.created_at).total_seconds()
        else:
            duration = 0.0  # Fallback to 0 if neither is available
        duration_ms = int(duration * 1000)

        # Publish completion event
        try:
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percentage=100.0,
                refs_processed=total_refs,
                refs_total=total_refs,
                status_message=f"Successfully resolved {total_refs} $ref references",
                tenant_id=tenant_id,
                user_id=user_id,
            )

            # Publish resolved event
            odps_event_publisher.publish_odps_ref_resolved(
                contract_id=str(contract_id),
                ref_path="all",
                ref_type="all",
                resolution_status="completed",
                ref_count=total_refs,
                duration_ms=duration_ms,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_ref_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS ref resolution completion event",
            )

        logger.info(
            "odps_ref_resolution_job_completed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id),
            tenant_id=tenant_id,
            refs_resolved=total_refs,
            external_ref_handling=external_ref_handling.value,
            message=f"ODPS $ref resolution job completed for contract {contract_id}",
        )

        return {
            "status": "completed",
            "refs_resolved": total_refs,
            "external_ref_handling": external_ref_handling.value,
            "contract_id": str(contract_id),
            "format": format_str,
        }

    except (ValueError, ODPSRefResolutionError):
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        logger.error(
            "odps_ref_resolution_job_failed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id) if "contract_id" in locals() else None,
            error=str(e),
            exc_info=True,
            message=f"ODPS $ref resolution job failed: {str(e)}",
        )
        raise Exception(f"ODPS $ref resolution failed: {str(e)}") from e


# SAVING CHECKPOINT: Start of export handler

def _execute_odps_export_job(job_obj: Job) -> dict:
    """
    Execute ODPS_EXPORT job.

    Generates ODPS document from HubContract format with progress tracking
    and event publishing.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with export results

    Raises:
        ValueError: If contract_id is missing, contract not found, or contract has no hub_contract_json
        Exception: For other errors
    """
    # Get contract ID from resource_id
    contract_id = job_obj.resource_id

    # Convert to string if it's a UUID object, handle None case
    if contract_id is not None:
        contract_id = str(contract_id)

    if not contract_id:
        raise ValueError("Contract ID is required for ODPS_EXPORT job")

    try:
        # Import here to avoid circular imports
        import json

        from hub.apps.contracts.models import Contract, OriginalFormat, OriginalSpecType
        from hub.apps.contracts.normalization import parse_contract
        from hub.apps.contracts.odps_generator import (
            format_odps_as_json,
            format_odps_as_yaml,
            generate_odps_from_hubcontract,
        )
        from hub.apps.core.events.publisher import EventPublisher
        from hub.apps.core.events.service_publishers import ODPSEventPublisher

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"Contract {contract_id} not found")

        # Validate contract has hub_contract_json
        if not contract.hub_contract_json:
            raise ValueError(
                f"Contract {contract_id} has no hub_contract_json. " "Cannot export as ODPS format."
            )

        # Get export options from job details
        export_format = job_obj.details_json.get("export_format", "json").lower()
        if export_format not in ["json", "yaml"]:
            export_format = "json"  # Default to JSON

        odps_version = job_obj.details_json.get("odps_version", "4.1")

        # Initialize event publisher
        odps_event_publisher = ODPSEventPublisher()
        odps_event_publisher._event_publisher = EventPublisher(
            service_name="job_service",
            tenant_id=str(contract.tenant.id) if contract.tenant else None,
            user_id=str(job_obj.created_by.id) if job_obj.created_by else None,
        )

        tenant_id = str(contract.tenant.id) if contract.tenant else None
        user_id = str(job_obj.created_by.id) if job_obj.created_by else None

        # Update progress: Starting export (0%)
        job_obj.details_json = job_obj.details_json or {}
        job_obj.details_json["progress_percentage"] = 0.0
        job_obj.details_json["current_phase"] = "initialization"
        job_obj.details_json["status_message"] = "Starting ODPS export"
        job_obj.save(update_fields=["details_json", "updated_at"])

        # Publish export started event
        try:
            odps_event_publisher.publish_odps_export_progress(
                contract_id=str(contract_id),
                export_format=export_format,
                progress_percentage=0.0,
                current_phase="initialization",
                status_message="Starting ODPS export",
                odps_version=odps_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_export_progress_event_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS export progress event",
            )

        # Update progress: Preparing data (10%)
        job_obj.details_json["progress_percentage"] = 10.0
        job_obj.details_json["current_phase"] = "preparation"
        job_obj.details_json["status_message"] = "Preparing HubContract data"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_export_progress(
                contract_id=str(contract_id),
                export_format=export_format,
                progress_percentage=10.0,
                current_phase="preparation",
                status_message="Preparing HubContract data",
                odps_version=odps_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Get original ODCS contract if available (for embedding in ODPS)
        original_odcs_contract = None
        if contract.original_raw and contract.original_spec_type == OriginalSpecType.ODCS:
            try:
                original_odcs_contract = parse_contract(
                    contract.original_raw, contract.original_format
                )
            except Exception as parse_err:
                logger.debug(
                    "odps_export_parse_original_odcs_failed",
                    job_id=str(job_obj.id),
                    contract_id=str(contract_id),
                    extra={"error_type": type(parse_err).__name__, "error": str(parse_err)},
                )

        # Update progress: Generating ODPS (30%)
        job_obj.details_json["progress_percentage"] = 30.0
        job_obj.details_json["current_phase"] = "generation"
        job_obj.details_json["status_message"] = "Generating ODPS document"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_export_progress(
                contract_id=str(contract_id),
                export_format=export_format,
                progress_percentage=30.0,
                current_phase="generation",
                status_message="Generating ODPS document",
                odps_version=odps_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Generate ODPS document
        odps_doc = generate_odps_from_hubcontract(
            hub_contract=contract.hub_contract_json,
            target_version=odps_version,
            original_odcs_contract=original_odcs_contract,
            original_odcs_url=None,
        )

        # Update progress: Formatting output (70%)
        job_obj.details_json["progress_percentage"] = 70.0
        job_obj.details_json["current_phase"] = "formatting"
        job_obj.details_json["status_message"] = f"Formatting ODPS as {export_format.upper()}"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_export_progress(
                contract_id=str(contract_id),
                export_format=export_format,
                progress_percentage=70.0,
                current_phase="formatting",
                status_message=f"Formatting ODPS as {export_format.upper()}",
                odps_version=odps_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Format output
        if export_format == "yaml":
            odps_raw = format_odps_as_yaml(odps_doc)
        else:
            odps_raw = format_odps_as_json(odps_doc)

        # Calculate bytes for progress tracking
        bytes_processed = len(odps_raw.encode("utf-8"))
        bytes_total = bytes_processed  # Total is same as processed for export

        # Update progress: Saving results (90%)
        job_obj.details_json["progress_percentage"] = 90.0
        job_obj.details_json["current_phase"] = "saving"
        job_obj.details_json["status_message"] = "Saving exported ODPS document"
        job_obj.details_json["bytes_processed"] = bytes_processed
        job_obj.details_json["bytes_total"] = bytes_total
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_export_progress(
                contract_id=str(contract_id),
                export_format=export_format,
                progress_percentage=90.0,
                current_phase="saving",
                bytes_processed=bytes_processed,
                bytes_total=bytes_total,
                status_message="Saving exported ODPS document",
                odps_version=odps_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Update contract with exported ODPS (store in original_raw for now)
        # Note: This preserves the original_raw if it exists, but stores the exported ODPS
        # In a production system, you might want to store this separately or in a versioned format
        with transaction.atomic():
            # Store exported ODPS in original_raw (or create a new field for exported content)
            contract.original_raw = odps_raw
            # Convert export_format string to OriginalFormat enum
            if export_format == "yaml":
                contract.original_format = OriginalFormat.YAML
            else:
                contract.original_format = OriginalFormat.JSON
            contract.original_spec_type = OriginalSpecType.ODPS
            contract.original_spec_version = odps_version
            contract.save(
                update_fields=[
                    "original_raw",
                    "original_format",
                    "original_spec_type",
                    "original_spec_version",
                    "updated_at",
                ]
            )

        # Update progress: Completed (100%)
        job_obj.details_json["progress_percentage"] = 100.0
        job_obj.details_json["current_phase"] = "completed"
        job_obj.details_json["status_message"] = "ODPS export completed successfully"
        job_obj.save(update_fields=["details_json", "updated_at"])

        # Publish completion event
        try:
            odps_event_publisher.publish_odps_export_progress(
                contract_id=str(contract_id),
                export_format=export_format,
                progress_percentage=100.0,
                current_phase="completed",
                bytes_processed=bytes_processed,
                bytes_total=bytes_total,
                status_message="ODPS export completed successfully",
                odps_version=odps_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_export_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS export completion event",
            )

        logger.info(
            "odps_export_job_completed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id),
            tenant_id=tenant_id,
            export_format=export_format,
            odps_version=odps_version,
            bytes_processed=bytes_processed,
            message=f"ODPS export job completed for contract {contract_id}",
        )

        # Record export success metric (Task 6.6.4)
        try:
            from hub.apps.observability.otel_metrics import odps_export_total

            odps_export_total.labels(
                status="success", format=export_format, tenant_id=tenant_id or "unknown"
            ).inc()
        except Exception as metrics_err:
            logger.debug(
                "odps_export_metrics_failed",
                job_id=str(job_obj.id),
                extra={"error_type": type(metrics_err).__name__, "error": str(metrics_err)},
            )

        return {
            "status": "completed",
            "export_format": export_format,
            "odps_version": odps_version,
            "contract_id": str(contract_id),
            "bytes_processed": bytes_processed,
            "bytes_total": bytes_total,
        }

    except (ValueError, ConnectionError):
        # Record export failure metric (Task 6.6.4)
        try:
            from hub.apps.observability.otel_metrics import odps_export_total

            tenant_id = (
                str(contract.tenant.id) if "contract" in locals() and contract.tenant else "unknown"
            )
            export_format = (
                job_obj.details_json.get("export_format", "unknown")
                if "job_obj" in locals()
                else "unknown"
            )
            odps_export_total.labels(
                status="failure", format=export_format, tenant_id=tenant_id
            ).inc()
        except Exception as metrics_err:
            logger.debug(
                "odps_export_metrics_failed",
                job_id=str(job_obj.id),
                extra={"error_type": type(metrics_err).__name__, "error": str(metrics_err)},
            )
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        logger.error(
            "odps_export_job_failed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id) if "contract_id" in locals() else None,
            error=str(e),
            exc_info=True,
            message=f"ODPS export job failed: {str(e)}",
        )

        # Record export failure metric (Task 6.6.4)
        try:
            from hub.apps.observability.otel_metrics import odps_export_total

            tenant_id = (
                str(contract.tenant.id) if "contract" in locals() and contract.tenant else "unknown"
            )
            export_format = (
                job_obj.details_json.get("export_format", "unknown")
                if "job_obj" in locals()
                else "unknown"
            )
            odps_export_total.labels(
                status="failure", format=export_format, tenant_id=tenant_id
            ).inc()
        except Exception as metrics_err:
            logger.debug(
                "odps_export_metrics_failed",
                job_id=str(job_obj.id),
                extra={"error_type": type(metrics_err).__name__, "error": str(metrics_err)},
            )

        raise Exception(f"ODPS export failed: {str(e)}") from e


# SAVING CHECKPOINT: Start of semantic_mapping handler

def _execute_odps_semantic_mapping_job(job_obj: Job) -> dict:
    """
    Execute ODPS_SEMANTIC_MAPPING job.

    Maps an ODPS contract to RDF (semantic representation) with progress tracking
    and event publishing.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with semantic mapping results

    Raises:
        ValueError: If contract_id is missing, contract not found, or contract is not ODPS
        ConnectionError: If semantic service is unavailable
        Exception: For other errors
    """
    import time

    start_time = time.time()

    # Get contract ID from resource_id
    contract_id = job_obj.resource_id

    # Convert to string if it's a UUID object, handle None case
    if contract_id is not None:
        contract_id = str(contract_id)

    if not contract_id:
        raise ValueError("Contract ID is required for ODPS_SEMANTIC_MAPPING job")

    try:
        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract, OriginalSpecType
        from hub.apps.core.events.publisher import EventPublisher
        from hub.apps.core.events.service_publishers import ODPSEventPublisher
        from hub.apps.semantic.utils import map_odps_to_semantic

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"Contract {contract_id} not found")

        # Validate contract is ODPS
        if contract.original_spec_type != OriginalSpecType.ODPS:
            raise ValueError(
                f"Contract {contract_id} is not an ODPS contract "
                f"(spec_type: {contract.original_spec_type})"
            )

        # Initialize event publisher
        odps_event_publisher = ODPSEventPublisher()
        odps_event_publisher._event_publisher = EventPublisher(
            service_name="job_service",
            tenant_id=str(contract.tenant.id) if contract.tenant else None,
            user_id=str(job_obj.created_by.id) if job_obj.created_by else None,
        )

        tenant_id = str(contract.tenant.id) if contract.tenant else None
        user_id = str(job_obj.created_by.id) if job_obj.created_by else None

        # Update progress: Starting semantic mapping (0%)
        job_obj.details_json = job_obj.details_json or {}
        job_obj.details_json["progress_percentage"] = 0.0
        job_obj.details_json["current_phase"] = "initialization"
        job_obj.details_json["status_message"] = "Starting ODPS semantic mapping"
        job_obj.save(update_fields=["details_json", "updated_at"])

        # Publish semantic mapping started event
        try:
            odps_event_publisher.publish_odps_semantic_mapping_progress(
                contract_id=str(contract_id),
                progress_percentage=0.0,
                current_phase="initialization",
                phase_index=0,
                total_phases=4,
                status_message="Starting ODPS semantic mapping",
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_semantic_mapping_progress_event_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS semantic mapping progress event",
            )

        # Update progress: Extracting ODPS product (25%)
        job_obj.details_json["progress_percentage"] = 25.0
        job_obj.details_json["current_phase"] = "extraction"
        job_obj.details_json["status_message"] = "Extracting ODPS product structure"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_semantic_mapping_progress(
                contract_id=str(contract_id),
                progress_percentage=25.0,
                current_phase="extraction",
                phase_index=1,
                total_phases=4,
                status_message="Extracting ODPS product structure",
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Update progress: Mapping to RDF (50%)
        job_obj.details_json["progress_percentage"] = 50.0
        job_obj.details_json["current_phase"] = "mapping"
        job_obj.details_json["status_message"] = "Mapping ODPS to RDF"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_semantic_mapping_progress(
                contract_id=str(contract_id),
                progress_percentage=50.0,
                current_phase="mapping",
                phase_index=2,
                total_phases=4,
                status_message="Mapping ODPS to RDF",
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Map ODPS to semantic (RDF)
        semantic_resource = map_odps_to_semantic(
            contract=contract, tenant=contract.tenant, use_cache=False
        )

        # Update progress: Saving semantic resource (75%)
        job_obj.details_json["progress_percentage"] = 75.0
        job_obj.details_json["current_phase"] = "saving"
        job_obj.details_json["status_message"] = "Saving semantic resource"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_semantic_mapping_progress(
                contract_id=str(contract_id),
                progress_percentage=75.0,
                current_phase="saving",
                phase_index=3,
                total_phases=4,
                status_message="Saving semantic resource",
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Check if mapping was successful
        if not semantic_resource:
            # Mapping was skipped (e.g., no ODPS product data)
            raise ValueError(
                f"ODPS semantic mapping was skipped for contract {contract_id}. "
                "Contract may not have valid ODPS product data."
            )

        # Update progress: Completed (100%)
        job_obj.details_json["progress_percentage"] = 100.0
        job_obj.details_json["current_phase"] = "completed"
        job_obj.details_json["status_message"] = "ODPS semantic mapping completed"
        job_obj.save(update_fields=["details_json", "updated_at"])

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Get semantic resource metadata
        triples_count = 0
        semantic_status = "UNKNOWN"
        if semantic_resource.metadata_json:
            triples_count = semantic_resource.metadata_json.get("triples_count", 0)
        if semantic_resource.status:
            semantic_status = semantic_resource.status

        # Publish completion event
        try:
            odps_event_publisher.publish_odps_semantic_mapped(
                contract_id=str(contract_id),
                semantic_resource_id=str(semantic_resource.id),
                semantic_uri=semantic_resource.uri,
                triples_count=triples_count,
                semantic_status=semantic_status,
                duration_ms=duration_ms,
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_semantic_mapped_event_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS semantic mapped event",
            )

        logger.info(
            "odps_semantic_mapping_job_completed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id),
            tenant_id=tenant_id,
            semantic_resource_id=str(semantic_resource.id),
            triples_count=triples_count,
            message=f"ODPS semantic mapping job completed for contract {contract_id}",
        )

        return {
            "status": "completed",
            "contract_id": str(contract_id),
            "semantic_resource_id": str(semantic_resource.id),
            "semantic_uri": semantic_resource.uri,
            "triples_count": triples_count,
            "semantic_status": semantic_status,
            "duration_ms": duration_ms,
        }

    except (ValueError, ConnectionError):
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        logger.error(
            "odps_semantic_mapping_job_failed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id) if "contract_id" in locals() else None,
            error=str(e),
            exc_info=True,
            message=f"ODPS semantic mapping job failed: {str(e)}",
        )
        raise Exception(f"ODPS semantic mapping failed: {str(e)}") from e


# SAVING CHECKPOINT: Start of linking handler

def _execute_odps_linking_job(job_obj: Job) -> dict:
    """
    Execute ODPS_LINKING job.

    Validates and establishes bidirectional links between ODPS and ODCS contracts
    with progress tracking and event publishing.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with linking results

    Raises:
        ValueError: If contract IDs are missing, contracts not found, or validation fails
        Exception: For other errors
    """
    import time

    start_time = time.time()

    # Get contract IDs from job details
    odps_contract_id = job_obj.details_json.get("odps_contract_id")
    odcs_contract_id = job_obj.details_json.get("odcs_contract_id")

    # If not in details, try resource_id (for backward compatibility)
    if not odps_contract_id:
        odps_contract_id = job_obj.resource_id

    # Convert to string if it's a UUID object, handle None case
    if odps_contract_id is not None:
        odps_contract_id = str(odps_contract_id)
    if odcs_contract_id is not None:
        odcs_contract_id = str(odcs_contract_id)

    if not odps_contract_id:
        raise ValueError("ODPS contract ID is required for ODPS_LINKING job")
    if not odcs_contract_id:
        raise ValueError("ODCS contract ID is required for ODPS_LINKING job")

    try:
        # Import here to avoid circular imports
        from hub.apps.contracts.linking_validation import LinkingValidationError, validate_linking
        from hub.apps.contracts.models import Contract, NormalizationStatus, OriginalSpecType
        from hub.apps.contracts.services import ContractService
        from hub.apps.core.events.publisher import EventPublisher
        from hub.apps.core.events.service_publishers import ODPSEventPublisher

        # Get contracts
        try:
            odps_contract = Contract.objects.get(id=odps_contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"ODPS contract {odps_contract_id} not found")

        try:
            odcs_contract = Contract.objects.get(id=odcs_contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"ODCS contract {odcs_contract_id} not found")

        # Get tenant and user IDs
        tenant_id = str(odps_contract.tenant.id) if odps_contract.tenant else None
        user_id = str(job_obj.created_by.id) if job_obj.created_by else None

        # Initialize event publisher
        odps_event_publisher = ODPSEventPublisher()
        odps_event_publisher._event_publisher = EventPublisher(
            service_name="job_service",
            tenant_id=tenant_id,
            user_id=user_id,
        )

        # Update progress: Starting linking (0%)
        job_obj.details_json = job_obj.details_json or {}
        job_obj.details_json["progress_percentage"] = 0.0
        job_obj.details_json["current_phase"] = "initialization"
        job_obj.details_json["status_message"] = "Starting ODPS linking"
        job_obj.save(update_fields=["details_json", "updated_at"])

        # Publish linking started event
        try:
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="starting",
                progress_percentage=0.0,
                current_phase="initialization",
                status_message="Starting ODPS linking",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_linking_status_event_failed",
                job_id=str(job_obj.id),
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                error=str(e),
                message="Failed to publish ODPS linking status event",
            )

        # Update progress: Validating contracts (20%)
        job_obj.details_json["progress_percentage"] = 20.0
        job_obj.details_json["current_phase"] = "validation"
        job_obj.details_json["status_message"] = "Validating contracts for linking"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="validating",
                progress_percentage=20.0,
                current_phase="validation",
                status_message="Validating contracts for linking",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Validate contracts for linking
        try:
            validated_odps_contract, validated_odcs_contract = validate_linking(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                tenant_id=tenant_id,
            )
        except LinkingValidationError as e:
            # Update progress: Validation failed (100%)
            job_obj.details_json["progress_percentage"] = 100.0
            job_obj.details_json["current_phase"] = "failed"
            job_obj.details_json["status_message"] = f"Linking validation failed: {str(e)}"
            job_obj.save(update_fields=["details_json", "updated_at"])

            # Publish failure event
            try:
                odps_event_publisher.publish_odps_linking_status(
                    odps_contract_id=odps_contract_id,
                    odcs_contract_id=odcs_contract_id,
                    status="failed",
                    progress_percentage=100.0,
                    current_phase="validation",
                    validation_passed=False,
                    validation_errors=[str(e)],
                    status_message=f"Linking validation failed: {str(e)}",
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            except Exception as event_err:
                logger.warning(
                    "odps_job_event_publish_failed",
                    job_id=str(job_obj.id),
                    contract_id=str(contract_id),
                    extra={"error_type": type(event_err).__name__, "error": str(event_err)},
                )
            raise ValueError(f"ODPS linking validation failed: {str(e)}")

        # Update progress: Validation passed (40%)
        job_obj.details_json["progress_percentage"] = 40.0
        job_obj.details_json["current_phase"] = "validation"
        job_obj.details_json["status_message"] = "Linking validation passed"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="validating",
                progress_percentage=40.0,
                current_phase="validation",
                validation_passed=True,
                status_message="Linking validation passed",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Update progress: Establishing links (60%)
        job_obj.details_json["progress_percentage"] = 60.0
        job_obj.details_json["current_phase"] = "linking"
        job_obj.details_json["status_message"] = "Establishing bidirectional links"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="linking",
                progress_percentage=60.0,
                current_phase="linking",
                status_message="Establishing bidirectional links",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Establish bidirectional links using ContractService
        contract_service = ContractService(tenant_id=tenant_id, user_id=user_id)

        # Use the service method to link contracts (this handles the actual linking logic)
        linked_odps_contract = contract_service.link_odps_to_odcs(
            odcs_contract_id=odcs_contract_id,
            odps_contract_id=odps_contract_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        # Refresh contracts from DB to get updated links
        validated_odps_contract.refresh_from_db()
        validated_odcs_contract.refresh_from_db()

        # Verify links were established
        odps_hub_contract = validated_odps_contract.hub_contract_json or {}
        odcs_hub_contract = validated_odcs_contract.hub_contract_json or {}
        odps_extensions = odps_hub_contract.get("extensions", {})
        odcs_extensions = odcs_hub_contract.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        odcs_x_odps = odcs_extensions.get("x_odps", {})

        odps_to_odcs_link = odps_x_odps.get("odcs_link")
        odcs_to_odps_link = odcs_x_odps.get("odps_link")

        if not odps_to_odcs_link or str(odps_to_odcs_link) != odcs_contract_id:
            raise ValueError(
                f"ODPS → ODCS link not established correctly. "
                f"Expected {odcs_contract_id}, got {odps_to_odcs_link}"
            )

        if not odcs_to_odps_link or str(odcs_to_odps_link) != odps_contract_id:
            raise ValueError(
                f"ODCS → ODPS link not established correctly. "
                f"Expected {odps_contract_id}, got {odcs_to_odps_link}"
            )

        # Update progress: Saving results (80%)
        job_obj.details_json["progress_percentage"] = 80.0
        job_obj.details_json["current_phase"] = "saving"
        job_obj.details_json["status_message"] = "Links established successfully"
        job_obj.save(update_fields=["details_json", "updated_at"])

        try:
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="linking",
                progress_percentage=80.0,
                current_phase="saving",
                status_message="Links established successfully",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_job_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id) if contract_id else None,
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Update progress: Completed (100%)
        job_obj.details_json["progress_percentage"] = 100.0
        job_obj.details_json["current_phase"] = "completed"
        job_obj.details_json["status_message"] = "ODPS linking completed successfully"
        job_obj.save(update_fields=["details_json", "updated_at"])

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Publish completion event
        try:
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="completed",
                progress_percentage=100.0,
                current_phase="completed",
                validation_passed=True,
                link_type="bidirectional",
                status_message="ODPS linking completed successfully",
                tenant_id=tenant_id,
                user_id=user_id,
            )

            # Publish linked event
            odps_event_publisher.publish_odps_linked(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                link_type="bidirectional",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_linking_event_publish_failed",
                job_id=str(job_obj.id),
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                error=str(e),
                message="Failed to publish ODPS linking completion event",
            )

        # Send notification email for ODPS linking status (Task 8.4.4)
        try:
            from hub.apps.notifications.tasks import send_odps_linking_status_email

            send_odps_linking_status_email.delay(
                odps_contract_id=odps_contract_id,
                status="completed",
                status_message="ODPS linking completed successfully",
                odcs_contract_id=odcs_contract_id,
                progress_percentage=100.0,
                current_phase="completed",
                validation_passed=True,
                user_id=user_id,
                tenant_id=tenant_id,
            )
        except Exception as e:
            # Log but don't fail job if notification fails
            logger.warning(
                "odps_linking_notification_failed",
                job_id=str(job_obj.id),
                odps_contract_id=odps_contract_id,
                error=str(e),
                message="Failed to send ODPS linking status notification (non-critical)",
            )

        logger.info(
            "odps_linking_job_completed",
            job_id=str(job_obj.id),
            odps_contract_id=odps_contract_id,
            odcs_contract_id=odcs_contract_id,
            tenant_id=tenant_id,
            duration_ms=duration_ms,
            message=f"ODPS linking job completed for contracts {odps_contract_id} ↔ {odcs_contract_id}",
        )

        return {
            "status": "completed",
            "odps_contract_id": odps_contract_id,
            "odcs_contract_id": odcs_contract_id,
            "link_type": "bidirectional",
            "duration_ms": duration_ms,
        }

    except (ValueError, LinkingValidationError):
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        logger.error(
            "odps_linking_job_failed",
            job_id=str(job_obj.id),
            odps_contract_id=odps_contract_id if "odps_contract_id" in locals() else None,
            odcs_contract_id=odcs_contract_id if "odcs_contract_id" in locals() else None,
            error=str(e),
            exc_info=True,
            message=f"ODPS linking job failed: {str(e)}",
        )
        raise Exception(f"ODPS linking failed: {str(e)}") from e

