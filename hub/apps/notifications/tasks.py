"""
Email Sending Tasks

Async tasks for sending emails via job queue.
"""
from typing import Dict, Any, Optional
from django_rq import job, get_queue
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
import structlog
import json

from .services import get_email_service, EmailServiceError
from .templates import (
    render_email_template,
    build_invitation_url,
    build_password_reset_url,
    build_job_url,
    build_contract_url,
    build_pipeline_url,
    build_pipeline_execution_url
)
from .models import EmailDelivery, EmailType, EmailDeliveryStatus

User = get_user_model()
logger = structlog.get_logger(__name__)


def _serialize_context_for_json(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize context dictionary to JSON-safe format.

    Converts Django model instances to dictionaries with their IDs and basic fields.

    Args:
        context: Template context dictionary that may contain Django model instances

    Returns:
        JSON-serializable dictionary
    """
    serialized = {}
    for key, value in context.items():
        if hasattr(value, '_meta'):  # Django model instance
            # Convert model to dict with basic fields
            model_dict = {
                'id': str(value.id),
                'model': f"{value._meta.app_label}.{value._meta.model_name}"
            }
            # Add common fields if they exist
            for field_name in ['email', 'username', 'name', 'display_name', 'title']:
                if hasattr(value, field_name):
                    model_dict[field_name] = getattr(value, field_name)
            serialized[key] = model_dict
        elif isinstance(value, (dict, list)):
            # Recursively serialize nested structures
            try:
                json.dumps(value)  # Test if already JSON-serializable
                serialized[key] = value
            except (TypeError, ValueError):
                # Contains non-serializable objects, convert to string
                serialized[key] = str(value)
        else:
            # Try to serialize directly
            try:
                json.dumps(value)
                serialized[key] = value
            except (TypeError, ValueError):
                serialized[key] = str(value)
    return serialized


def send_email_async(
    email_type: str,
    to_email: str,
    subject: str,
    template_name: str,
    context: Dict[str, Any],
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    retry_count: int = 0,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Send email asynchronously with retry logic.

    Args:
        email_type: Email type (from EmailType enum)
        to_email: Recipient email address
        subject: Email subject
        template_name: Template name (e.g., 'notifications/emails/user_invitation.html')
        context: Template context
        tenant_id: Optional tenant ID
        user_id: Optional user ID
        retry_count: Current retry attempt
        max_retries: Maximum retry attempts

    Returns:
        Dict with 'success' (bool) and 'delivery_id' (str)
    """
    try:
        # Get email service
        email_service = get_email_service()

        # Render email template
        rendered = render_email_template(template_name, context)

        # Get from_email from context or settings
        from_email = context.get('from_email')
        from_name = context.get('from_name')

        # Send email
        result = email_service.send_email(
            to_email=to_email,
            subject=subject,
            html_content=rendered['html'],
            text_content=rendered['text'],
            from_email=from_email,
            from_name=from_name,
            reply_to=context.get('reply_to')
        )

        # Serialize context for JSON storage
        serialized_context = _serialize_context_for_json(context)

        # Create or update email delivery record
        delivery, created = EmailDelivery.objects.get_or_create(
            email_type=email_type,
            to_email=to_email,
            status=EmailDeliveryStatus.PENDING,
            defaults={
                'subject': subject,
                'tenant_id': tenant_id,
                'user_id': user_id,
                'metadata_json': serialized_context,
                'retry_count': retry_count,
                'max_retries': max_retries
            }
        )

        if not created:
            delivery.retry_count = retry_count
            delivery.save(update_fields=['retry_count', 'updated_at'])

        # Mark as sent
        delivery.mark_sent(message_id=result.get('message_id'))

        logger.info(
            "email_sent_async",
            email_type=email_type,
            to_email=to_email,
            delivery_id=str(delivery.id),
            message_id=result.get('message_id'),
            success=True
        )

        return {
            'success': True,
            'delivery_id': str(delivery.id),
            'message_id': result.get('message_id')
        }

    except EmailServiceError as e:
        logger.error(
            "email_send_failed_async",
            email_type=email_type,
            to_email=to_email,
            error=str(e),
            retry_count=retry_count,
            exc_info=True
        )

        # Serialize context for JSON storage
        serialized_context = _serialize_context_for_json(context)

        # Create or update delivery record with failure
        delivery, created = EmailDelivery.objects.get_or_create(
            email_type=email_type,
            to_email=to_email,
            status=EmailDeliveryStatus.PENDING,
            defaults={
                'subject': subject,
                'tenant_id': tenant_id,
                'user_id': user_id,
                'metadata_json': serialized_context,
                'retry_count': retry_count,
                'max_retries': max_retries
            }
        )

        if not created:
            delivery.retry_count = retry_count
            delivery.save(update_fields=['retry_count', 'updated_at'])

        # Mark as failed if max retries reached
        if retry_count >= max_retries:
            delivery.mark_failed(str(e))
            return {
                'success': False,
                'delivery_id': str(delivery.id),
                'error': str(e)
            }

        # Retry with exponential backoff
        delivery.status = EmailDeliveryStatus.DEFERRED
        delivery.error_message = str(e)
        delivery.save(update_fields=['status', 'error_message', 'updated_at'])

        # Schedule retry (exponential backoff: 60s, 120s, 240s)
        from datetime import timedelta
        delay_seconds = 60 * (2 ** retry_count)

        queue = get_queue('job_low')  # Use low priority queue for email retries
        queue.enqueue_in(
            timedelta(seconds=delay_seconds),
            send_email_async,
            email_type=email_type,
            to_email=to_email,
            subject=subject,
            template_name=template_name,
            context=context,
            tenant_id=tenant_id,
            user_id=user_id,
            retry_count=retry_count + 1,
            max_retries=max_retries
        )

        return {
            'success': False,
            'delivery_id': str(delivery.id),
            'error': str(e),
            'retry_scheduled': True,
            'retry_delay': delay_seconds
        }

    except Exception as e:
        logger.error(
            "email_send_unexpected_error",
            email_type=email_type,
            to_email=to_email,
            error=str(e),
            exc_info=True
        )
        raise


@job('job_low', timeout=60)
def send_invitation_email(user_id: str):
    """
    Send user invitation email.

    Args:
        user_id: User UUID
    """
    try:
        user = User.objects.get(id=user_id)

        if not user.invitation_token:
            logger.warning(
                "invitation_email_no_token",
                user_id=user_id,
                message="User has no invitation token"
            )
            return

        # Build invitation URL
        invitation_url = build_invitation_url(str(user.invitation_token))

        # Prepare template context
        context = {
            'user': user,
            'tenant': user.tenant,
            'invitation_url': invitation_url
        }

        # Send email
        result = send_email_async(
            email_type=EmailType.USER_INVITATION,
            to_email=user.email,
            subject=f"Invitation to join {user.tenant.name if user.tenant else 'Data Interoperability Hub'}",
            template_name='notifications/emails/user_invitation.html',
            context=context,
            tenant_id=str(user.tenant.id) if user.tenant else None,
            user_id=str(user.id)
        )

        logger.info(
            "invitation_email_sent",
            user_id=user_id,
            email=user.email,
            success=result.get('success', False)
        )

        return result

    except User.DoesNotExist:
        logger.error(
            "invitation_email_user_not_found",
            user_id=user_id
        )
        raise
    except Exception as e:
        logger.error(
            "invitation_email_error",
            user_id=user_id,
            error=str(e),
            exc_info=True
        )
        raise


@job('job_low', timeout=60)
def send_password_reset_email(user_id: str):
    """
    Send password reset email.

    Args:
        user_id: User UUID
    """
    try:
        user = User.objects.get(id=user_id)

        if not user.password_reset_token:
            logger.warning(
                "password_reset_email_no_token",
                user_id=user_id,
                message="User has no password reset token"
            )
            return

        # Build password reset URL
        reset_url = build_password_reset_url(str(user.password_reset_token))

        # Prepare template context
        context = {
            'user': user,
            'reset_url': reset_url
        }

        # Send email
        result = send_email_async(
            email_type=EmailType.PASSWORD_RESET,
            to_email=user.email,
            subject="Password Reset Request",
            template_name='notifications/emails/password_reset.html',
            context=context,
            tenant_id=str(user.tenant.id) if user.tenant else None,
            user_id=str(user.id)
        )

        logger.info(
            "password_reset_email_sent",
            user_id=user_id,
            email=user.email,
            success=result.get('success', False)
        )

        return result

    except User.DoesNotExist:
        logger.error(
            "password_reset_email_user_not_found",
            user_id=user_id
        )
        raise
    except Exception as e:
        logger.error(
            "password_reset_email_error",
            user_id=user_id,
            error=str(e),
            exc_info=True
        )
        raise


@job('job_low', timeout=60)
def send_job_completion_email(job_id: str):
    """
    Send job completion notification email.

    Args:
        job_id: Job UUID
    """
    try:
        from hub.apps.jobs.models import Job

        job = Job.objects.get(id=job_id)

        if not job.created_by:
            logger.warning(
                "job_completion_email_no_user",
                job_id=job_id,
                message="Job has no created_by user"
            )
            return

        # Build job URL
        job_url = build_job_url(str(job.id))

        # Prepare template context
        context = {
            'user': job.created_by,
            'job': job,
            'job_type': job.get_type_display(),
            'resource_type': job.resource_type,
            'resource_id': str(job.resource_id),
            'job_url': job_url,
            'result_summary': str(job.result_json) if job.result_json else None
        }

        # Send email
        result = send_email_async(
            email_type=EmailType.JOB_COMPLETION,
            to_email=job.created_by.email,
            subject=f"Job Completed: {job.get_type_display()}",
            template_name='notifications/emails/job_completion.html',
            context=context,
            tenant_id=str(job.tenant.id) if job.tenant else None,
            user_id=str(job.created_by.id)
        )

        logger.info(
            "job_completion_email_sent",
            job_id=job_id,
            email=job.created_by.email,
            success=result.get('success', False)
        )

        return result

    except Job.DoesNotExist:
        logger.error(
            "job_completion_email_job_not_found",
            job_id=job_id
        )
        raise
    except Exception as e:
        logger.error(
            "job_completion_email_error",
            job_id=job_id,
            error=str(e),
            exc_info=True
        )
        raise


@job('job_low', timeout=60)
def send_job_failure_email(job_id: str):
    """
    Send job failure notification email.

    Args:
        job_id: Job UUID
    """
    try:
        from hub.apps.jobs.models import Job

        job = Job.objects.get(id=job_id)

        if not job.created_by:
            logger.warning(
                "job_failure_email_no_user",
                job_id=job_id,
                message="Job has no created_by user"
            )
            return

        # Build job URL
        job_url = build_job_url(str(job.id))

        # Prepare template context
        context = {
            'user': job.created_by,
            'job': job,
            'job_type': job.get_type_display(),
            'resource_type': job.resource_type,
            'resource_id': str(job.resource_id),
            'error_message': job.error_message,
            'job_url': job_url
        }

        # Send email
        result = send_email_async(
            email_type=EmailType.JOB_FAILURE,
            to_email=job.created_by.email,
            subject=f"Job Failed: {job.get_type_display()}",
            template_name='notifications/emails/job_failure.html',
            context=context,
            tenant_id=str(job.tenant.id) if job.tenant else None,
            user_id=str(job.created_by.id)
        )

        logger.info(
            "job_failure_email_sent",
            job_id=job_id,
            email=job.created_by.email,
            success=result.get('success', False)
        )

        return result

    except Job.DoesNotExist:
        logger.error(
            "job_failure_email_job_not_found",
            job_id=job_id
        )
        raise
    except Exception as e:
        logger.error(
            "job_failure_email_error",
            job_id=job_id,
            error=str(e),
            exc_info=True
        )
        raise


@job('job_low', timeout=60)
def send_odps_creation_completion_email(contract_id: str):
    """
    Send ODPS creation completion notification email.

    Args:
        contract_id: Contract UUID
    """
    try:
        from hub.apps.contracts.models import Contract

        contract = Contract.objects.select_related('created_by', 'tenant').get(id=contract_id)

        if not contract.created_by:
            logger.warning(
                "odps_creation_completion_email_no_user",
                contract_id=contract_id,
                message="Contract has no created_by user"
            )
            return

        # Build contract URL
        contract_url = build_contract_url(str(contract.id))

        # Prepare template context
        context = {
            'user': contract.created_by,
            'contract_id': str(contract.id),
            'contract_url': contract_url,
            'odps_version': contract.original_spec_version,
            'normalization_status': contract.get_normalization_status_display() if hasattr(contract, 'get_normalization_status_display') else str(contract.normalization_status),
            'normalization_warnings': contract.normalization_warnings if contract.normalization_warnings else []
        }

        # Send email
        result = send_email_async(
            email_type=EmailType.ODPS_CREATION_COMPLETION,
            to_email=contract.created_by.email,
            subject="ODPS Contract Created Successfully",
            template_name='notifications/emails/odps_creation_completion.html',
            context=context,
            tenant_id=str(contract.tenant.id) if contract.tenant else None,
            user_id=str(contract.created_by.id)
        )

        logger.info(
            "odps_creation_completion_email_sent",
            contract_id=contract_id,
            email=contract.created_by.email,
            success=result.get('success', False)
        )

        return result

    except Contract.DoesNotExist:
        logger.error(
            "odps_creation_completion_email_contract_not_found",
            contract_id=contract_id
        )
        raise
    except Exception as e:
        logger.error(
            "odps_creation_completion_email_error",
            contract_id=contract_id,
            error=str(e),
            exc_info=True
        )
        raise


@job('job_low', timeout=60)
def send_odps_normalization_failure_email(
    contract_id: str,
    error_message: str,
    error_code: Optional[str] = None,
    errors: Optional[list] = None,
    field_path: Optional[str] = None
):
    """
    Send ODPS normalization failure notification email.

    Args:
        contract_id: Contract UUID
        error_message: Error message
        error_code: Optional error code
        errors: Optional list of error messages
        field_path: Optional field path where error occurred
    """
    try:
        from hub.apps.contracts.models import Contract

        contract = Contract.objects.select_related('created_by', 'tenant').get(id=contract_id)

        if not contract.created_by:
            logger.warning(
                "odps_normalization_failure_email_no_user",
                contract_id=contract_id,
                message="Contract has no created_by user"
            )
            return

        # Build contract URL
        contract_url = build_contract_url(str(contract.id))

        # Prepare template context
        context = {
            'user': contract.created_by,
            'contract_id': str(contract.id),
            'contract_url': contract_url,
            'odps_version': contract.original_spec_version,
            'error_code': error_code,
            'error_message': error_message,
            'errors': errors or contract.normalization_errors or [],
            'field_path': field_path
        }

        # Send email
        result = send_email_async(
            email_type=EmailType.ODPS_NORMALIZATION_FAILURE,
            to_email=contract.created_by.email,
            subject="ODPS Normalization Failed",
            template_name='notifications/emails/odps_normalization_failure.html',
            context=context,
            tenant_id=str(contract.tenant.id) if contract.tenant else None,
            user_id=str(contract.created_by.id)
        )

        logger.info(
            "odps_normalization_failure_email_sent",
            contract_id=contract_id,
            email=contract.created_by.email,
            success=result.get('success', False)
        )

        return result

    except Contract.DoesNotExist:
        logger.error(
            "odps_normalization_failure_email_contract_not_found",
            contract_id=contract_id
        )
        raise
    except Exception as e:
        logger.error(
            "odps_normalization_failure_email_error",
            contract_id=contract_id,
            error=str(e),
            exc_info=True
        )
        raise


@job('job_low', timeout=60)
def send_odps_linking_status_email(
    odps_contract_id: str,
    status: str,
    status_message: Optional[str] = None,
    odcs_contract_id: Optional[str] = None,
    progress_percentage: Optional[float] = None,
    current_phase: Optional[str] = None,
    validation_passed: Optional[bool] = None,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None
):
    """
    Send ODPS linking status notification email.

    Args:
        odps_contract_id: ODPS Contract UUID
        status: Linking status (e.g., "linking", "completed", "failed", "validating")
        status_message: Optional status message
        odcs_contract_id: Optional ODCS Contract UUID
        progress_percentage: Optional progress percentage (0-100)
        current_phase: Optional current phase description
        validation_passed: Optional validation result
        user_id: Optional user ID (if not provided, will try to get from contract)
        tenant_id: Optional tenant ID (if not provided, will try to get from contract)
    """
    try:
        from hub.apps.contracts.models import Contract

        odps_contract = Contract.objects.select_related('created_by', 'tenant').get(id=odps_contract_id)

        # Determine user - prefer provided user_id, fallback to contract.created_by
        user = None
        effective_user_id = user_id
        if effective_user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=effective_user_id)
            except User.DoesNotExist:
                pass

        if not user and odps_contract.created_by:
            user = odps_contract.created_by
            effective_user_id = str(odps_contract.created_by.id)

        if not user:
            logger.warning(
                "odps_linking_status_email_no_user",
                odps_contract_id=odps_contract_id,
                message="No user found for linking status email"
            )
            return

        # Get ODCS contract if provided
        odcs_contract = None
        if odcs_contract_id:
            try:
                odcs_contract = Contract.objects.get(id=odcs_contract_id)
            except Contract.DoesNotExist:
                logger.warning(
                    "odps_linking_status_email_odcs_contract_not_found",
                    odcs_contract_id=odcs_contract_id
                )

        # Build contract URLs
        odps_contract_url = build_contract_url(str(odps_contract.id))
        odcs_contract_url = build_contract_url(str(odcs_contract.id)) if odcs_contract else None

        # Determine effective tenant_id
        effective_tenant_id = tenant_id or (str(odps_contract.tenant.id) if odps_contract.tenant else None)

        # Prepare template context
        context = {
            'user': user,
            'odps_contract_id': str(odps_contract.id),
            'odcs_contract_id': str(odcs_contract.id) if odcs_contract else None,
            'status': status,
            'status_message': status_message,
            'progress_percentage': progress_percentage,
            'current_phase': current_phase,
            'validation_passed': validation_passed,
            'odps_contract_url': odps_contract_url,
            'odcs_contract_url': odcs_contract_url
        }

        # Send email
        result = send_email_async(
            email_type=EmailType.ODPS_LINKING_STATUS,
            to_email=user.email,
            subject=f"ODPS Linking Status: {status.title()}",
            template_name='notifications/emails/odps_linking_status.html',
            context=context,
            tenant_id=effective_tenant_id,
            user_id=effective_user_id
        )

        logger.info(
            "odps_linking_status_email_sent",
            odps_contract_id=odps_contract_id,
            odcs_contract_id=odcs_contract_id,
            status=status,
            email=user.email,
            success=result.get('success', False)
        )

        return result

    except Contract.DoesNotExist:
        logger.error(
            "odps_linking_status_email_contract_not_found",
            odps_contract_id=odps_contract_id
        )
        raise
    except Exception as e:
        logger.error(
            "odps_linking_status_email_error",
            odps_contract_id=odps_contract_id,
            error=str(e),
            exc_info=True
        )
        raise


@job('job_low', timeout=60)
def send_pipeline_execution_completion_email(execution_id: str):
    """
    Send pipeline execution completion notification email.

    Args:
        execution_id: Pipeline execution UUID
    """
    try:
        from hub.apps.transformation.models import PipelineExecution

        execution = PipelineExecution.objects.select_related(
            'pipeline', 'pipeline__created_by', 'pipeline__tenant', 'asset', 'result_asset'
        ).get(id=execution_id)

        if not execution.pipeline.created_by:
            logger.warning(
                "pipeline_execution_completion_email_no_user",
                execution_id=execution_id,
                message="Pipeline has no created_by user"
            )
            return

        user = execution.pipeline.created_by
        pipeline = execution.pipeline
        tenant = execution.pipeline.tenant

        # Build URLs
        pipeline_url = build_pipeline_url(str(pipeline.id))
        execution_url = build_pipeline_execution_url(str(execution.id))

        # Calculate duration
        duration_seconds = execution.get_duration_seconds()
        duration_formatted = None
        if duration_seconds is not None and duration_seconds > 0:
            # Ensure duration_seconds is a numeric value
            if isinstance(duration_seconds, (int, float)):
                if duration_seconds < 60:
                    duration_formatted = f"{int(duration_seconds)} seconds"
                elif duration_seconds < 3600:
                    minutes = int(duration_seconds / 60)
                    seconds = int(duration_seconds % 60)
                    duration_formatted = f"{minutes} minute{'s' if minutes != 1 else ''} {seconds} second{'s' if seconds != 1 else ''}"
                else:
                    hours = int(duration_seconds / 3600)
                    minutes = int((duration_seconds % 3600) / 60)
                    duration_formatted = f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"

        # Prepare template context
        context = {
            'user': user,
            'pipeline': pipeline,
            'execution': execution,
            'execution_id': str(execution.id),
            'pipeline_id': str(pipeline.id),
            'pipeline_name': pipeline.name,
            'pipeline_url': pipeline_url,
            'execution_url': execution_url,
            'status': execution.get_status_display() if hasattr(execution, 'get_status_display') else str(execution.status),
            'execution_mode': execution.get_execution_mode_display() if hasattr(execution, 'get_execution_mode_display') else str(execution.execution_mode),
            'duration_seconds': duration_seconds,
            'duration_formatted': duration_formatted,
            'asset_name': execution.asset.name if execution.asset else None,
            'result_asset_name': execution.result_asset.name if execution.result_asset else None,
        }

        # Add metrics if available
        if execution.metrics and isinstance(execution.metrics, dict):
            context['metrics'] = execution.metrics
            # Extract quality_score from nested quality_metrics if available
            if 'quality_metrics' in execution.metrics:
                quality_metrics = execution.metrics['quality_metrics']
                if isinstance(quality_metrics, dict) and 'quality_score' in quality_metrics:
                    context['quality_score'] = quality_metrics.get('quality_score')
            # Extract rows_processed from metrics
            if 'rows_processed' in execution.metrics:
                context['records_processed'] = execution.metrics.get('rows_processed')

        # Send email
        result = send_email_async(
            email_type=EmailType.PIPELINE_EXECUTION_COMPLETION,
            to_email=user.email,
            subject=f"Pipeline Execution Completed: {pipeline.name}",
            template_name='notifications/emails/pipeline_execution_completion.html',
            context=context,
            tenant_id=str(tenant.id) if tenant else None,
            user_id=str(user.id)
        )

        logger.info(
            "pipeline_execution_completion_email_sent",
            execution_id=execution_id,
            pipeline_id=str(pipeline.id),
            email=user.email,
            success=result.get('success', False)
        )

        return result

    except PipelineExecution.DoesNotExist:
        logger.error(
            "pipeline_execution_completion_email_execution_not_found",
            execution_id=execution_id
        )
        raise
    except Exception as e:
        logger.error(
            "pipeline_execution_completion_email_error",
            execution_id=execution_id,
            error=str(e),
            exc_info=True
        )
        raise


@job('job_low', timeout=60)
def send_pipeline_execution_failure_email(execution_id: str):
    """
    Send pipeline execution failure notification email.

    Args:
        execution_id: Pipeline execution UUID
    """
    try:
        from hub.apps.transformation.models import PipelineExecution

        execution = PipelineExecution.objects.select_related(
            'pipeline', 'pipeline__created_by', 'pipeline__tenant', 'asset'
        ).get(id=execution_id)

        if not execution.pipeline.created_by:
            logger.warning(
                "pipeline_execution_failure_email_no_user",
                execution_id=execution_id,
                message="Pipeline has no created_by user"
            )
            return

        user = execution.pipeline.created_by
        pipeline = execution.pipeline
        tenant = execution.pipeline.tenant

        # Build URLs
        pipeline_url = build_pipeline_url(str(pipeline.id))
        execution_url = build_pipeline_execution_url(str(execution.id))

        # Calculate duration
        duration_seconds = execution.get_duration_seconds()
        duration_formatted = None
        if duration_seconds is not None and duration_seconds > 0:
            # Ensure duration_seconds is a numeric value
            if isinstance(duration_seconds, (int, float)):
                if duration_seconds < 60:
                    duration_formatted = f"{int(duration_seconds)} seconds"
                elif duration_seconds < 3600:
                    minutes = int(duration_seconds / 60)
                    seconds = int(duration_seconds % 60)
                    duration_formatted = f"{minutes} minute{'s' if minutes != 1 else ''} {seconds} second{'s' if seconds != 1 else ''}"
                else:
                    hours = int(duration_seconds / 3600)
                    minutes = int((duration_seconds % 3600) / 60)
                    duration_formatted = f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"

        # Prepare template context
        context = {
            'user': user,
            'pipeline': pipeline,
            'execution': execution,
            'execution_id': str(execution.id),
            'pipeline_id': str(pipeline.id),
            'pipeline_name': pipeline.name,
            'pipeline_url': pipeline_url,
            'execution_url': execution_url,
            'status': execution.get_status_display() if hasattr(execution, 'get_status_display') else str(execution.status),
            'execution_mode': execution.get_execution_mode_display() if hasattr(execution, 'get_execution_mode_display') else str(execution.execution_mode),
            'duration_seconds': duration_seconds,
            'duration_formatted': duration_formatted,
            'error_message': execution.error_message,
            'asset_name': execution.asset.name if execution.asset else None,
        }

        # Add error code if available
        if execution.metrics and 'error_code' in execution.metrics:
            context['error_code'] = execution.metrics['error_code']

        # Send email
        result = send_email_async(
            email_type=EmailType.PIPELINE_EXECUTION_FAILURE,
            to_email=user.email,
            subject=f"Pipeline Execution Failed: {pipeline.name}",
            template_name='notifications/emails/pipeline_execution_failure.html',
            context=context,
            tenant_id=str(tenant.id) if tenant else None,
            user_id=str(user.id)
        )

        logger.info(
            "pipeline_execution_failure_email_sent",
            execution_id=execution_id,
            pipeline_id=str(pipeline.id),
            email=user.email,
            success=result.get('success', False)
        )

        return result

    except PipelineExecution.DoesNotExist:
        logger.error(
            "pipeline_execution_failure_email_execution_not_found",
            execution_id=execution_id
        )
        raise
    except Exception as e:
        logger.error(
            "pipeline_execution_failure_email_error",
            execution_id=execution_id,
            error=str(e),
            exc_info=True
        )
        raise

