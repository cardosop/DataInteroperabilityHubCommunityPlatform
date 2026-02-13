"""
Compliance Job Handlers

Handlers for Compliance job execution.

SAVING CHECKPOINT: This module contains Compliance job handlers (< 700 lines per project rule).
"""

from .models import Job


def _execute_compliance_run_job(job_obj: Job) -> dict:
    """
    Execute COMPLIANCE_RUN job.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with compliance run results

    Raises:
        ValueError: If compliance_run_id is missing or compliance run not found
        ConnectionError: If compliance service is unavailable
        Exception: For other errors
    """
    # Get compliance_run_id from job details or resource_id
    compliance_run_id = job_obj.details_json.get("compliance_run_id") or job_obj.resource_id

    # Convert to string if it's a UUID object
    if compliance_run_id:
        compliance_run_id = str(compliance_run_id)

    if not compliance_run_id:
        raise ValueError("Compliance run ID is required")

    try:
        # Import here to avoid circular imports
        from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
        from hub.apps.compliance.service_client import ComplianceServiceClient
        from hub.apps.compliance.views import execute_compliance_run

        # Check if compliance run exists before executing
        try:
            compliance_run = ComplianceRun.objects.get(id=compliance_run_id)
        except ComplianceRun.DoesNotExist:
            raise ValueError(f"Compliance run {compliance_run_id} not found")

        # Check if compliance service is available
        compliance_client = ComplianceServiceClient()
        is_healthy, _ = compliance_client.health_check()
        if not is_healthy:
            raise ConnectionError("Compliance service is unavailable")

        # Execute compliance run (this handles its own errors and updates ComplianceRun status)
        execute_compliance_run(str(compliance_run_id))

        # Get updated compliance run (refresh from DB)
        compliance_run.refresh_from_db()

        # Check if compliance run failed
        if compliance_run.status == ComplianceRunStatus.FAILED:
            error_msg = (
                compliance_run.regulation_mapping_json.get("error", "Compliance run failed")
                if compliance_run.regulation_mapping_json
                else "Compliance run failed"
            )
            raise Exception(f"Compliance run failed: {error_msg}")

        return {
            "status": compliance_run.status.lower(),
            "overall_status": compliance_run.overall_status,
            "risk_level": compliance_run.risk_level,
            "allowed_to_store": compliance_run.allowed_to_store,
            "compliance_run_id": str(compliance_run.id),
        }

    except ConnectionError:
        raise  # Re-raise connection errors
    except ValueError:
        raise  # Re-raise validation errors
    except Exception as e:
        # Wrap other exceptions
        raise Exception(f"Compliance run execution failed: {str(e)}") from e
