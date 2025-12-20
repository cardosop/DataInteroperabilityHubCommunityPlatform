"""
Asset Activation Saga Workflow

Implements asset activation using the Saga pattern with the following steps:
1. Contract validation
2. Data quality check
3. Compliance check
4. Activation

Compensation:
- Rollback activation
- Reset status
"""
import logging
from typing import Dict, Any

from hub.apps.orchestration.saga import (
    SagaStep,
    SagaStepResult,
    SagaOrchestrator,
    SagaExecutionError
)
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract
from hub.apps.jobs.models import Job, JobType, JobStatus

logger = logging.getLogger(__name__)


def validate_contract(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Step 1: Validate contract for asset activation.

    Args:
        input_data: Contains 'asset_id' and optionally 'contract_id'

    Returns:
        SagaStepResult with contract validation result
    """
    asset_id = input_data.get('asset_id')
    if not asset_id:
        return SagaStepResult.failure_result("asset_id is required")

    try:
        asset = Asset.objects.get(id=asset_id)

        # Get primary contract (first active contract)
        contract = asset.contracts.filter(status="ACTIVE").first()

        if not contract:
            return SagaStepResult.failure_result(
                "No active contract found for asset",
                {"asset_id": str(asset_id)}
            )

        # Validate contract is ready for activation
        if contract.status != "ACTIVE":
            return SagaStepResult.failure_result(
                f"Contract status is {contract.status}, expected ACTIVE",
                {"contract_id": str(contract.id), "contract_status": contract.status}
            )

        logger.info(
            "asset_activation_contract_validated",
            extra={
                "asset_id": str(asset_id),
                "contract_id": str(contract.id)
            }
        )

        return SagaStepResult.success_result({
            "contract_id": str(contract.id),
            "contract_status": contract.status,
            "asset_id": str(asset_id),
            "original_asset_status": asset.status.value if hasattr(asset.status, 'value') else str(asset.status)
        })

    except Asset.DoesNotExist:
        return SagaStepResult.failure_result(
            f"Asset not found: {asset_id}",
            {"asset_id": str(asset_id)}
        )
    except Exception as e:
        logger.exception("asset_activation_contract_validation_error")
        return SagaStepResult.failure_result(
            f"Contract validation failed: {str(e)}",
            {"exception_type": type(e).__name__}
        )


def compensate_contract_validation(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Compensation for contract validation step.

    No action needed - contract validation is read-only.
    """
    return SagaStepResult.success_result()


def check_data_quality(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Step 2: Check data quality for asset.

    Args:
        input_data: Contains 'asset_id' and previous step outputs

    Returns:
        SagaStepResult with DQ check result
    """
    asset_id = input_data.get('asset_id')
    if not asset_id:
        return SagaStepResult.failure_result("asset_id is required")

    try:
        asset = Asset.objects.get(id=asset_id)

        # Check if DQ job exists and is successful
        dq_jobs = Job.objects.filter(
            resource_type="ASSET",
            resource_id=asset.id,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED
        ).order_by('-created_at')

        if not dq_jobs.exists():
            return SagaStepResult.failure_result(
                "No successful DQ job found for asset",
                {"asset_id": str(asset_id)}
            )

        latest_dq_job = dq_jobs.first()

        # Check asset DQ status
        if asset.dq_status == "FAIL":
            return SagaStepResult.failure_result(
                "Asset data quality check failed",
                {
                    "asset_id": str(asset_id),
                    "dq_status": asset.dq_status,
                    "dq_job_id": str(latest_dq_job.id)
                }
            )

        logger.info(
            "asset_activation_dq_check_passed",
            extra={
                "asset_id": str(asset_id),
                "dq_status": asset.dq_status,
                "dq_job_id": str(latest_dq_job.id)
            }
        )

        return SagaStepResult.success_result({
            "dq_status": asset.dq_status,
            "dq_job_id": str(latest_dq_job.id)
        })

    except Asset.DoesNotExist:
        return SagaStepResult.failure_result(
            f"Asset not found: {asset_id}",
            {"asset_id": str(asset_id)}
        )
    except Exception as e:
        logger.exception("asset_activation_dq_check_error")
        return SagaStepResult.failure_result(
            f"DQ check failed: {str(e)}",
            {"exception_type": type(e).__name__}
        )


def compensate_dq_check(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Compensation for DQ check step.

    No action needed - DQ check is read-only.
    """
    return SagaStepResult.success_result()


def check_compliance(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Step 3: Check compliance for asset.

    Args:
        input_data: Contains 'asset_id' and previous step outputs

    Returns:
        SagaStepResult with compliance check result
    """
    asset_id = input_data.get('asset_id')
    if not asset_id:
        return SagaStepResult.failure_result("asset_id is required")

    try:
        asset = Asset.objects.get(id=asset_id)

        # Check if compliance job exists and is successful
        compliance_jobs = Job.objects.filter(
            resource_type="ASSET",
            resource_id=asset.id,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED
        ).order_by('-created_at')

        if not compliance_jobs.exists():
            return SagaStepResult.failure_result(
                "No successful compliance job found for asset",
                {"asset_id": str(asset_id)}
            )

        latest_compliance_job = compliance_jobs.first()

        # Check asset compliance status
        if asset.compliance_status == "FAIL":
            return SagaStepResult.failure_result(
                "Asset compliance check failed",
                {
                    "asset_id": str(asset_id),
                    "compliance_status": asset.compliance_status,
                    "compliance_job_id": str(latest_compliance_job.id)
                }
            )

        logger.info(
            "asset_activation_compliance_check_passed",
            extra={
                "asset_id": str(asset_id),
                "compliance_status": asset.compliance_status,
                "compliance_job_id": str(latest_compliance_job.id)
            }
        )

        return SagaStepResult.success_result({
            "compliance_status": asset.compliance_status,
            "compliance_job_id": str(latest_compliance_job.id)
        })

    except Asset.DoesNotExist:
        return SagaStepResult.failure_result(
            f"Asset not found: {asset_id}",
            {"asset_id": str(asset_id)}
        )
    except Exception as e:
        logger.exception("asset_activation_compliance_check_error")
        return SagaStepResult.failure_result(
            f"Compliance check failed: {str(e)}",
            {"exception_type": type(e).__name__}
        )


def compensate_compliance_check(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Compensation for compliance check step.

    No action needed - compliance check is read-only.
    """
    return SagaStepResult.success_result()


def activate_asset(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Step 4: Activate the asset.

    Args:
        input_data: Contains 'asset_id' and previous step outputs

    Returns:
        SagaStepResult with activation result
    """
    asset_id = input_data.get('asset_id')
    original_status = input_data.get('original_asset_status')

    if not asset_id:
        return SagaStepResult.failure_result("asset_id is required")

    try:
        asset = Asset.objects.get(id=asset_id)

        # Store original status for compensation
        if not original_status:
            original_status = asset.status

        # Activate asset
        asset.status = AssetStatus.ACTIVE
        asset.save(update_fields=['status', 'updated_at'])

        logger.info(
            "asset_activation_completed",
            extra={
                "asset_id": str(asset_id),
                "original_status": original_status,
                "new_status": asset.status
            }
        )

        return SagaStepResult.success_result({
            "asset_id": str(asset_id),
            "original_status": original_status.value if hasattr(original_status, 'value') else str(original_status),
            "new_status": asset.status.value if hasattr(asset.status, 'value') else str(asset.status)
        })

    except Asset.DoesNotExist:
        return SagaStepResult.failure_result(
            f"Asset not found: {asset_id}",
            {"asset_id": str(asset_id)}
        )
    except Exception as e:
        logger.exception("asset_activation_error")
        return SagaStepResult.failure_result(
            f"Asset activation failed: {str(e)}",
            {"exception_type": type(e).__name__}
        )


def compensate_activation(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Compensation for activation step: rollback activation and reset status.

    Args:
        input_data: Contains 'asset_id', 'original_status', and step output

    Returns:
        SagaStepResult with compensation result
    """
    asset_id = input_data.get('asset_id')
    # Try to get original_status from various sources
    original_status = (
        input_data.get('original_status') or
        input_data.get('step_output', {}).get('original_status') or
        input_data.get('original_asset_status')
    )

    if not asset_id:
        return SagaStepResult.failure_result("asset_id is required for compensation")

    try:
        asset = Asset.objects.get(id=asset_id)

        # Reset to original status
        if original_status:
            # Handle both string and enum values
            if isinstance(original_status, str):
                try:
                    asset.status = AssetStatus(original_status)
                except ValueError:
                    # If not a valid status, default to DRAFT
                    asset.status = AssetStatus.DRAFT
            else:
                asset.status = original_status
        else:
            # Default to DRAFT if no original status
            asset.status = AssetStatus.DRAFT

        asset.save(update_fields=['status', 'updated_at'])

        logger.info(
            "asset_activation_compensated",
            extra={
                "asset_id": str(asset_id),
                "original_status": str(original_status),
                "reset_status": asset.status.value
            }
        )

        return SagaStepResult.success_result({
            "asset_id": str(asset_id),
            "reset_status": asset.status.value if hasattr(asset.status, 'value') else str(asset.status)
        })

    except Asset.DoesNotExist:
        logger.warning(
            "asset_activation_compensation_asset_not_found",
            extra={"asset_id": str(asset_id)}
        )
        return SagaStepResult.success_result({
            "warning": "Asset not found during compensation",
            "asset_id": str(asset_id)
        })
    except Exception as e:
        logger.exception("asset_activation_compensation_error")
        return SagaStepResult.failure_result(
            f"Activation compensation failed: {str(e)}",
            {"exception_type": type(e).__name__}
        )


def create_asset_activation_saga(asset_id: str) -> SagaOrchestrator:
    """
    Create and configure asset activation saga.

    Args:
        asset_id: ID of the asset to activate

    Returns:
        Configured SagaOrchestrator instance
    """
    steps = [
        SagaStep(
            name="validate_contract",
            forward_action=validate_contract,
            compensation_action=compensate_contract_validation,
            description="Validate contract for asset activation"
        ),
        SagaStep(
            name="check_data_quality",
            forward_action=check_data_quality,
            compensation_action=compensate_dq_check,
            description="Check data quality for asset"
        ),
        SagaStep(
            name="check_compliance",
            forward_action=check_compliance,
            compensation_action=compensate_compliance_check,
            description="Check compliance for asset"
        ),
        SagaStep(
            name="activate_asset",
            forward_action=activate_asset,
            compensation_action=compensate_activation,
            description="Activate the asset"
        )
    ]

    orchestrator = SagaOrchestrator()
    orchestrator.context.state = {
        "asset_id": asset_id
    }

    return orchestrator


def execute_asset_activation(asset_id: str) -> Dict[str, Any]:
    """
    Execute asset activation saga workflow.

    Args:
        asset_id: ID of the asset to activate

    Returns:
        Dictionary with execution results

    Raises:
        SagaExecutionError: If activation fails
    """
    orchestrator = create_asset_activation_saga(asset_id)

    steps = [
        SagaStep(
            name="validate_contract",
            forward_action=validate_contract,
            compensation_action=compensate_contract_validation,
            description="Validate contract for asset activation"
        ),
        SagaStep(
            name="check_data_quality",
            forward_action=check_data_quality,
            compensation_action=compensate_dq_check,
            description="Check data quality for asset"
        ),
        SagaStep(
            name="check_compliance",
            forward_action=check_compliance,
            compensation_action=compensate_compliance_check,
            description="Check compliance for asset"
        ),
        SagaStep(
            name="activate_asset",
            forward_action=activate_asset,
            compensation_action=compensate_activation,
            description="Activate the asset"
        )
    ]

    try:
        context = orchestrator.execute(steps, initial_state={"asset_id": asset_id})

        return {
            "success": True,
            "saga_id": orchestrator.saga_id,
            "status": orchestrator.status.value,
            "context": {
                "asset_id": asset_id,
                "final_state": context.state
            }
        }
    except SagaExecutionError as e:
        logger.error(
            "asset_activation_saga_failed",
            extra={
                "saga_id": orchestrator.saga_id,
                "asset_id": asset_id,
                "error": str(e)
            }
        )
        return {
            "success": False,
            "saga_id": orchestrator.saga_id,
            "status": orchestrator.status.value,
            "error": str(e),
            "context": orchestrator.context
        }

