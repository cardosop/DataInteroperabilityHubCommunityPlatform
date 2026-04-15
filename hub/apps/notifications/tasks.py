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

from .business_rules import NotificationsBusinessRules
from .services import get_email_service, EmailServiceError
from .templates import (
    render_email_template,
    build_invitation_url,
    build_email_verification_url,
    build_password_reset_url,
    build_job_url,
    build_contract_url,
    build_marketplace_sync_job_url,
    build_marketplace_connection_url
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
    # Validate via NotificationsBusinessRules before sending (Phase 75.1)
    #
    # Guard: reject empty / missing-@ recipients upfront because the
    # base validate() truthiness guard (``if recipient``) silently
    # skips falsy values like "".
    if not to_email or not to_email.strip():
        raise ValueError(
            "Notification business rules validation failed: "
            "Recipient email must be provided"
        )
    if "@" not in to_email:
        raise ValueError(
            "Notification business rules validation failed: "
            f"Recipient '{to_email}' does not appear to be a "
            "valid email address"
        )

    rules = NotificationsBusinessRules(
        tenant_id=tenant_id, user_id=user_id,
    )
    validation_result = rules.validate(
        recipient=to_email,
        template=template_name,
        validation_type="all",
    )
    if not validation_result.is_valid:
        error_msg = "; ".join(validation_result.errors)
        logger.error(
            "email_validation_failed",
            email_type=email_type,
            to_email=to_email,
            errors=validation_result.errors,
        )
        raise ValueError(
            f"Notification business rules validation failed: "
            f"{error_msg}"
        )

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
def send_invitation_email(user_id: str, plaintext_token: str = None):
    """
    Send user invitation email.

    Args:
        user_id: User UUID
        plaintext_token: Plaintext invitation UUID to embed in the URL (11.3).
            When provided this value is used directly; the field stored in DB
            is now a SHA-256 hash so it can no longer be used for the link.
    """
    try:
        user = User.objects.get(id=user_id)

        if not user.invitation_token and not plaintext_token:
            logger.warning(
                "invitation_email_no_token",
                user_id=user_id,
                message="User has no invitation token"
            )
            return

        # Use the supplied plaintext token when available (11.3); fall back to
        # the DB value for legacy rows created before the hash migration.
        token_for_url = plaintext_token or str(user.invitation_token)

        # Build invitation URL
        invitation_url = build_invitation_url(token_for_url)

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
            subject=f"Invitation to join {user.tenant.name if user.tenant else getattr(settings, 'APP_NAME', 'Meshant')}",
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
def send_password_reset_email(user_id: str, plaintext_token: str = None):
    """
    Send password reset email.

    Args:
        user_id: User UUID
        plaintext_token: Plaintext reset UUID to embed in the URL (11.3).
            The DB column now stores a SHA-256 hash; this argument carries
            the un-hashed value for link construction.
    """
    try:
        user = User.objects.get(id=user_id)

        if not user.password_reset_token and not plaintext_token:
            logger.warning(
                "password_reset_email_no_token",
                user_id=user_id,
                message="User has no password reset token"
            )
            return

        token_for_url = plaintext_token or str(user.password_reset_token)

        # Build password reset URL
        reset_url = build_password_reset_url(token_for_url)

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
def send_email_verification_email(user_id: str, plaintext_token: str = None):
    """
    Send email verification link (Phase 204).

    Args:
        user_id: User UUID
        plaintext_token: Signed token for the verify URL (DB stores SHA-256 hash).
    """
    try:
        user = User.objects.get(id=user_id)

        if not user.email_verification_token and not plaintext_token:
            logger.warning(
                "email_verification_no_token",
                user_id=user_id,
                message="User has no email verification token",
            )
            return

        token_for_url = plaintext_token
        if not token_for_url:
            logger.warning(
                "email_verification_missing_plaintext",
                user_id=user_id,
            )
            return

        verify_url = build_email_verification_url(token_for_url)
        context = {
            "user": user,
            "verify_url": verify_url,
        }

        result = send_email_async(
            email_type=EmailType.EMAIL_VERIFICATION,
            to_email=user.email,
            subject=f"Verify your email — {getattr(settings, 'APP_NAME', 'Meshant')}",
            template_name="notifications/emails/email_verification.html",
            context=context,
            tenant_id=str(user.tenant.id) if user.tenant else None,
            user_id=str(user.id),
        )

        logger.info(
            "email_verification_sent",
            user_id=user_id,
            email=user.email,
            success=result.get("success", False),
        )
        return result

    except User.DoesNotExist:
        logger.error("email_verification_user_not_found", user_id=user_id)
        raise
    except Exception as e:
        logger.error(
            "email_verification_error",
            user_id=user_id,
            error=str(e),
            exc_info=True,
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

        # Phase 223.1 — in-app inbox notification (complements email).
        try:
            from hub.apps.notifications.utils import create_user_notification
            if job.tenant is not None:
                create_user_notification(
                    user=job.created_by,
                    tenant=job.tenant,
                    title=f"Job completed: {job.get_type_display()}",
                    message="Your job finished successfully.",
                    notification_type="SUCCESS",
                    category="JOBS",
                    resource_type="JOB",
                    resource_id=job.id,
                )
        except Exception:
            logger.warning("in_app_job_completion_notification_failed", job_id=job_id, exc_info=True)

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

        # Phase 223.1 — in-app inbox notification.
        try:
            from hub.apps.notifications.utils import create_user_notification
            if job.tenant is not None:
                create_user_notification(
                    user=job.created_by,
                    tenant=job.tenant,
                    title=f"Job failed: {job.get_type_display()}",
                    message=job.error_message or "Your job failed. See details in the job log.",
                    notification_type="ERROR",
                    category="JOBS",
                    resource_type="JOB",
                    resource_id=job.id,
                )
        except Exception:
            logger.warning("in_app_job_failure_notification_failed", job_id=job_id, exc_info=True)

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

        # Phase 223.1 — in-app inbox notification.
        try:
            from hub.apps.notifications.utils import create_user_notification
            if contract.tenant is not None:
                create_user_notification(
                    user=contract.created_by,
                    tenant=contract.tenant,
                    title="Contract normalized",
                    message="Your contract was normalized and is ready to use.",
                    notification_type="SUCCESS",
                    category="CONTRACTS",
                    resource_type="CONTRACT",
                    resource_id=contract.id,
                )
        except Exception:
            logger.warning("in_app_contract_creation_notification_failed", contract_id=contract_id, exc_info=True)

        logger.info(
            "odps_creation_completion_email_sent",
            contract_id=contract_id,
            email=contract.created_by.email,
            success=result.get('success', False)
        )

        # Propagate failure to caller so synchronous callers (e.g. tests, CLI) get an exception
        if not result.get('success'):
            raise EmailServiceError(result.get('error', 'Email send failed'))

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

        # Phase 223.1 — in-app inbox notification.
        try:
            from hub.apps.notifications.utils import create_user_notification
            if contract.tenant is not None:
                create_user_notification(
                    user=contract.created_by,
                    tenant=contract.tenant,
                    title="Contract normalization failed",
                    message=error_message or "Normalization failed. See details on the contract page.",
                    notification_type="ERROR",
                    category="CONTRACTS",
                    resource_type="CONTRACT",
                    resource_id=contract.id,
                )
        except Exception:
            logger.warning("in_app_contract_normalization_failure_notification_failed", contract_id=contract_id, exc_info=True)

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
def send_marketplace_sync_completion_email(sync_job_id: str):
    """
    Send marketplace sync completion notification email.

    Args:
        sync_job_id: Marketplace sync job UUID
    """
    if sync_job_id is None:
        raise ValueError("sync_job_id is required")
    try:
        from hub.apps.integrations.models import MarketplaceSyncJob

        sync_job = MarketplaceSyncJob.objects.select_related(
            'connection', 'connection__tenant', 'tenant'
        ).get(id=sync_job_id)

        # Get user from connection or tenant
        user = None
        if sync_job.connection and hasattr(sync_job.connection, 'created_by') and sync_job.connection.created_by:
            user = sync_job.connection.created_by
        elif sync_job.tenant and hasattr(sync_job.tenant, 'users') and sync_job.tenant.users.exists():
            user = sync_job.tenant.users.first()

        if not user:
            logger.warning(
                "marketplace_sync_completion_email_no_user",
                sync_job_id=sync_job_id,
                message="Sync job has no associated user"
            )
            return

        # Build sync job URL
        sync_job_url = build_marketplace_sync_job_url(str(sync_job.id))

        # Calculate duration
        duration_seconds = None
        duration_formatted = None
        if sync_job.completed_at and sync_job.created_at:
            duration_seconds = (sync_job.completed_at - sync_job.created_at).total_seconds()
            if duration_seconds > 0:
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
            'sync_job_id': str(sync_job.id),
            'marketplace_type': sync_job.connection.marketplace_type if sync_job.connection else 'Unknown',
            'direction': sync_job.direction,
            'connection_name': sync_job.connection.name if sync_job.connection else 'Unknown',
            'items_synced': sync_job.items_synced,
            'duration_formatted': duration_formatted,
            'sync_job_url': sync_job_url
        }

        # Send email
        result = send_email_async(
            email_type=EmailType.MARKETPLACE_SYNC_COMPLETION.value,
            to_email=user.email,
            subject=f"Marketplace Sync Completed: {sync_job.connection.name if sync_job.connection else 'Sync Job'}",
            template_name='notifications/emails/marketplace_sync_completion.html',
            context=context,
            tenant_id=str(sync_job.tenant.id) if sync_job.tenant else None,
            user_id=str(user.id)
        )

        logger.info(
            "marketplace_sync_completion_email_sent",
            sync_job_id=sync_job_id,
            email=user.email,
            success=result.get('success', False)
        )

        return result

    except MarketplaceSyncJob.DoesNotExist:
        logger.error(
            "marketplace_sync_completion_email_sync_job_not_found",
            sync_job_id=sync_job_id
        )
        raise
    except Exception as e:
        logger.error(
            "marketplace_sync_completion_email_error",
            sync_job_id=sync_job_id,
            error=str(e),
            exc_info=True
        )
        raise


@job('job_low', timeout=60)
def send_marketplace_sync_failure_email(sync_job_id: str):
    """
    Send marketplace sync failure notification email.

    Args:
        sync_job_id: Marketplace sync job UUID
    """
    if sync_job_id is None:
        raise ValueError("sync_job_id is required")
    try:
        from hub.apps.integrations.models import MarketplaceSyncJob

        sync_job = MarketplaceSyncJob.objects.select_related(
            'connection', 'connection__tenant', 'tenant'
        ).get(id=sync_job_id)

        # Get user from connection or tenant
        user = None
        if sync_job.connection and hasattr(sync_job.connection, 'created_by') and sync_job.connection.created_by:
            user = sync_job.connection.created_by
        elif sync_job.tenant and hasattr(sync_job.tenant, 'users') and sync_job.tenant.users.exists():
            user = sync_job.tenant.users.first()

        if not user:
            logger.warning(
                "marketplace_sync_failure_email_no_user",
                sync_job_id=sync_job_id,
                message="Sync job has no associated user"
            )
            return

        # Build sync job URL
        sync_job_url = build_marketplace_sync_job_url(str(sync_job.id))

        # Get error message from errors list
        error_message = None
        if sync_job.errors:
            if isinstance(sync_job.errors, list):
                if len(sync_job.errors) > 0:
                    error_entry = sync_job.errors[0]
                    if isinstance(error_entry, dict):
                        error_message = error_entry.get('message', str(error_entry))
                    else:
                        error_message = str(error_entry)
            else:
                error_message = str(sync_job.errors)

        # Prepare template context
        context = {
            'user': user,
            'sync_job_id': str(sync_job.id),
            'marketplace_type': sync_job.connection.marketplace_type if sync_job.connection else 'Unknown',
            'direction': sync_job.direction,
            'connection_name': sync_job.connection.name if sync_job.connection else 'Unknown',
            'items_synced': sync_job.items_synced,
            'items_failed': sync_job.items_failed,
            'error_message': error_message,
            'sync_job_url': sync_job_url
        }

        # Send email
        result = send_email_async(
            email_type=EmailType.MARKETPLACE_SYNC_FAILURE.value,
            to_email=user.email,
            subject=f"Marketplace Sync Failed: {sync_job.connection.name if sync_job.connection else 'Sync Job'}",
            template_name='notifications/emails/marketplace_sync_failure.html',
            context=context,
            tenant_id=str(sync_job.tenant.id) if sync_job.tenant else None,
            user_id=str(user.id)
        )

        logger.info(
            "marketplace_sync_failure_email_sent",
            sync_job_id=sync_job_id,
            email=user.email,
            success=result.get('success', False)
        )

        return result

    except MarketplaceSyncJob.DoesNotExist:
        logger.error(
            "marketplace_sync_failure_email_sync_job_not_found",
            sync_job_id=sync_job_id
        )
        raise
    except Exception as e:
        logger.error(
            "marketplace_sync_failure_email_error",
            sync_job_id=sync_job_id,
            error=str(e),
            exc_info=True
        )
        raise


@job('job_low', timeout=60)
def send_marketplace_connection_test_failure_email(
    connection_id: str,
    error_message: str,
    tested_at: Optional[str] = None,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None
):
    """
    Send marketplace connection test failure notification email.

    Args:
        connection_id: Connection UUID
        error_message: Error message from connection test
        tested_at: Optional ISO format timestamp of when test was performed
        user_id: Optional user ID (if not provided, will try to get from connection)
        tenant_id: Optional tenant ID (if not provided, will try to get from connection)
    """
    if connection_id is None:
        raise ValueError("connection_id is required")
    if error_message is None:
        raise ValueError("error_message is required")
    try:
        from hub.apps.integrations.models import MarketplaceConnection
        from django.contrib.auth import get_user_model

        User = get_user_model()

        connection = MarketplaceConnection.objects.select_related('tenant').get(id=connection_id)

        # Determine user - prefer provided user_id, fallback to connection.created_by
        user = None
        effective_user_id = user_id
        if effective_user_id:
            try:
                user = User.objects.get(id=effective_user_id)
            except User.DoesNotExist:
                pass

        if not user and hasattr(connection, 'created_by') and connection.created_by:
            user = connection.created_by
            effective_user_id = str(connection.created_by.id)

        if not user:
            logger.warning(
                "marketplace_connection_test_failure_email_no_user",
                connection_id=connection_id,
                message="No user found for connection test failure email"
            )
            return

        # Determine effective tenant_id
        effective_tenant_id = tenant_id or (str(connection.tenant.id) if connection.tenant else None)

        # Build connection URL
        connection_url = build_marketplace_connection_url(str(connection.id))

        # Prepare template context
        context = {
            'user': user,
            'connection_name': connection.name,
            'connection_id': str(connection.id),
            'marketplace_type': connection.marketplace_type,
            'error_message': error_message,
            'tested_at': tested_at,
            'connection_url': connection_url
        }

        # Send email
        result = send_email_async(
            email_type=EmailType.MARKETPLACE_CONNECTION_TEST_FAILURE.value,
            to_email=user.email,
            subject=f"Connection Test Failed: {connection.name}",
            template_name='notifications/emails/marketplace_connection_test_failure.html',
            context=context,
            tenant_id=effective_tenant_id,
            user_id=effective_user_id
        )

        logger.info(
            "marketplace_connection_test_failure_email_sent",
            connection_id=connection_id,
            email=user.email,
            success=result.get('success', False)
        )

        return result

    except MarketplaceConnection.DoesNotExist:
        logger.error(
            "marketplace_connection_test_failure_email_connection_not_found",
            connection_id=connection_id
        )
        raise
    except Exception as e:
        logger.error(
            "marketplace_connection_test_failure_email_error",
            connection_id=connection_id,
            error=str(e),
            exc_info=True
        )
        raise

