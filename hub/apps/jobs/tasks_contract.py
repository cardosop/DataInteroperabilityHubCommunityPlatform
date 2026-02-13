"""
Contract Job Handlers

Handlers for Contract-related job execution (validation, semantic mapping, migration).

SAVING CHECKPOINT: This module contains Contract job handlers (< 700 lines per project rule).
"""

from .models import Job


def _execute_contract_validation_job(job_obj: Job) -> dict:
    """
    Execute CONTRACT_VALIDATION job.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with validation results

    Raises:
        ValueError: If contract_id is missing or contract not found
        ConnectionError: If DataContract CLI service is unavailable
        TimeoutError: If validation times out
        Exception: For other errors
    """
    # Get contract ID from resource_id
    contract_id = job_obj.resource_id

    # Convert to string if it's a UUID object, handle None case
    if contract_id is not None:
        contract_id = str(contract_id)

    if not contract_id:
        raise ValueError("Contract ID is required")

    try:
        # Import here to avoid circular imports
        from hub.apps.contracts.cli_client import (
            SYNC_TIMEOUT,
            DataContractCLIClient,
            group_errors_by_category,
            interpret_validation_status,
        )
        from hub.apps.contracts.models import Contract, ValidationStatus

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"Contract {contract_id} not found")

        if not contract.original_raw or contract.original_raw.strip() == "":
            raise ValueError(f"Contract {contract_id} has no original_raw content")

        # Check if DataContract CLI service is available
        cli_client = DataContractCLIClient()
        try:
            health = cli_client.health_check()
            # DataContractCLIClient returns Dict[str, Any] with 'status' key
            if isinstance(health, dict) and health.get("status") != "healthy":
                raise ConnectionError("DataContract CLI service is unavailable")
        except ConnectionError:
            raise  # Re-raise connection errors
        except Exception as e:
            raise ConnectionError(f"DataContract CLI service health check failed: {str(e)}")

        # Validate contract
        try:
            validation_result = cli_client.validate(
                raw_contract=contract.original_raw,
                format=contract.original_format,
                tenant_id=str(contract.tenant.id) if contract.tenant else None,
                use_cache=True,
                timeout=SYNC_TIMEOUT,
            )
        except Exception as e:
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                raise TimeoutError(f"Contract validation timed out after {SYNC_TIMEOUT} seconds")
            raise ConnectionError(f"Contract validation service error: {str(e)}")

        # Interpret validation status
        validation_status, errors, warnings = interpret_validation_status(validation_result)

        # Group errors by category
        grouped_errors = group_errors_by_category(errors)

        return {
            "status": "completed",
            "validation_status": validation_status,
            "errors": errors,
            "warnings": warnings,
            "grouped_errors": grouped_errors,
            "cli_version": validation_result.get("cli_version", "unknown"),
            "contract_id": str(contract_id),
        }

    except (ConnectionError, TimeoutError, ValueError):
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        raise Exception(f"Contract validation failed: {str(e)}") from e


def _execute_semantic_mapping_job(job_obj: Job) -> dict:
    """
    Execute SEMANTIC_MAPPING job.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with semantic mapping results

    Raises:
        ValueError: If resource_type or resource_id is missing, or resource not found
        ConnectionError: If semantic service is unavailable
        Exception: For other errors
    """
    # Get resource details from job
    resource_type = job_obj.details_json.get("resource_type")
    resource_id = job_obj.details_json.get("resource_id")

    if not resource_type:
        raise ValueError("Resource type is required for SEMANTIC_MAPPING job")

    if not resource_id:
        raise ValueError("Resource ID is required for SEMANTIC_MAPPING job")

    try:
        # Import here to avoid circular imports
        from hub.apps.semantic.service_client import SemanticServiceClient
        from hub.apps.semantic.utils import map_asset_to_semantic, map_contract_to_semantic

        # Validate resource type first (before service health check)
        if resource_type not in ["CONTRACT", "ASSET"]:
            raise ValueError(f"Unknown resource type: {resource_type}")

        # Validate resource exists before checking service health
        if resource_type == "CONTRACT":
            from hub.apps.contracts.models import Contract

            try:
                # Convert resource_id to UUID if it's a string
                if isinstance(resource_id, str):
                    import uuid as uuid_module

                    resource_id = uuid_module.UUID(resource_id)
                contract = Contract.objects.get(id=resource_id)
            except Contract.DoesNotExist:
                raise ValueError(f"Contract {resource_id} not found")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid contract ID format: {resource_id}") from e

        elif resource_type == "ASSET":
            from hub.apps.assets.models import Asset

            try:
                # Convert resource_id to UUID if it's a string
                if isinstance(resource_id, str):
                    import uuid as uuid_module

                    resource_id = uuid_module.UUID(resource_id)
                asset = Asset.objects.get(id=resource_id)
            except Asset.DoesNotExist:
                raise ValueError(f"Asset {resource_id} not found")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid asset ID format: {resource_id}") from e

        # Check if semantic service is available (after resource validation)
        semantic_client = SemanticServiceClient()
        try:
            # SemanticServiceClient.health_check() returns Tuple[bool, str]
            is_healthy, _ = semantic_client.health_check()
            if not is_healthy:
                raise ConnectionError("Semantic service is unavailable")
        except ConnectionError:
            raise  # Re-raise connection errors
        except Exception as e:
            raise ConnectionError(f"Semantic service health check failed: {str(e)}")

        # Execute mapping (resource already validated above)
        if resource_type == "CONTRACT":
            semantic_resource = map_contract_to_semantic(contract, tenant=contract.tenant)

            return {
                "status": "completed",
                "resource_type": "CONTRACT",
                "resource_id": str(resource_id),
                "semantic_resource_id": str(semantic_resource.id) if semantic_resource else None,
            }

        elif resource_type == "ASSET":
            semantic_resource = map_asset_to_semantic(asset, tenant=asset.tenant)

            return {
                "status": "completed",
                "resource_type": "ASSET",
                "resource_id": str(resource_id),
                "semantic_resource_id": str(semantic_resource.id) if semantic_resource else None,
            }

    except (ConnectionError, ValueError):
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        raise Exception(f"Semantic mapping failed: {str(e)}") from e


def _execute_contract_migration_job(job_obj: Job) -> dict:
    """
    Execute CONTRACT_MIGRATION job.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with migration results

    Raises:
        ValueError: If contract_id is missing or contract not found
        Exception: For other errors
    """
    # Get contract ID from resource_id
    contract_id = job_obj.resource_id

    if not contract_id:
        raise ValueError("Contract ID is required for CONTRACT_MIGRATION job")

    try:
        # Import here to avoid circular imports
        from hub.apps.contracts.migration_manager import ContractMigrationManager
        from hub.apps.contracts.models import Contract

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"Contract {contract_id} not found")

        # Perform migration
        migrated, hub_contract, warnings = ContractMigrationManager.migrate_on_write(contract)

        if not migrated:
            return {
                "status": "completed",
                "migrated": False,
                "message": "Migration not needed or already completed",
                "warnings": warnings,
                "contract_id": str(contract_id),
            }

        return {
            "status": "completed",
            "migrated": True,
            "source_version": job_obj.details_json.get("source_version"),
            "target_version": job_obj.details_json.get("target_version"),
            "warnings": warnings,
            "contract_id": str(contract_id),
        }

    except ValueError:
        raise  # Re-raise validation errors
    except Exception as e:
        # Wrap other exceptions
        raise Exception(f"Contract migration failed: {str(e)}") from e
