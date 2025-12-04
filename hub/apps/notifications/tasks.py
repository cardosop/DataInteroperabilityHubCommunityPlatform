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
    build_job_url
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
        delay_seconds = 60 * (2 ** retry_count)
        
        queue = get_queue('job_low')  # Use low priority queue for email retries
        queue.enqueue_in(
            delay_seconds,
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

