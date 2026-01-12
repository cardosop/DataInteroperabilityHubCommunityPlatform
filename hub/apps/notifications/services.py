"""
Email Service Abstraction

Provides a unified interface for sending emails via multiple backends:
- SendGrid
- AWS SES
- Generic SMTP
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.smtp import EmailBackend
import structlog

from hub.apps.core.services.base import BaseService

# Optional imports for email backends
try:
    import sendgrid
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    sendgrid = None

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None
    ClientError = Exception  # Fallback for type hints

logger = structlog.get_logger(__name__)


class EmailService(ABC):
    """
    Abstract base class for email service implementations.

    All email services must implement the send_email method.
    """

    @abstractmethod
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Send an email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text email body (optional, auto-generated from HTML if not provided)
            from_email: Sender email address (optional, uses default if not provided)
            from_name: Sender name (optional)
            reply_to: Reply-to email address (optional)
            attachments: List of attachment dicts with 'filename' and 'content' keys (optional)

        Returns:
            Dict with 'success' (bool), 'message_id' (str, optional), and 'error' (str, optional)

        Raises:
            EmailServiceError: If email sending fails
        """
        pass


class EmailServiceError(Exception):
    """Base exception for email service errors"""
    pass


class SendGridEmailService(BaseService, EmailService):
    """
    SendGrid email service implementation.

    Requires SENDGRID_API_KEY in settings.
    """

    service_name = "sendgrid_email_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """Initialize SendGridEmailService with BaseService support."""
        # Set BaseService attributes
        self.tenant_id = tenant_id
        self.user_id = user_id
        if not SENDGRID_AVAILABLE:
            raise EmailServiceError("sendgrid package not installed. Install with: pip install sendgrid")
        api_key = getattr(settings, 'SENDGRID_API_KEY', None)
        if not api_key:
            raise EmailServiceError("SENDGRID_API_KEY not configured in settings")
        self.client = sendgrid.SendGridAPIClient(api_key=api_key)
        self.from_email = getattr(settings, 'SENDGRID_FROM_EMAIL', None)
        self.from_name = getattr(settings, 'SENDGRID_FROM_NAME', 'Data Interoperability Hub')

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send email via SendGrid"""
        try:
            # Use configured from_email or provided one
            sender_email = from_email or self.from_email
            if not sender_email:
                raise EmailServiceError("from_email not configured and not provided")

            sender_name = from_name or self.from_name
            from_addr = Email(sender_email, sender_name)
            to_addr = To(to_email)  # Use To object for recipient

            # Create mail object
            mail = Mail(
                from_email=from_addr,
                to_emails=to_addr,  # Pass To object directly
                subject=subject,
                html_content=html_content
            )

            # Add text content if provided
            if text_content:
                mail.content = [
                    Content("text/plain", text_content),
                    Content("text/html", html_content)
                ]
            else:
                mail.content = Content("text/html", html_content)

            # Add reply-to if provided
            if reply_to:
                mail.reply_to = Email(reply_to)

            # Add attachments if provided
            if attachments:
                if not SENDGRID_AVAILABLE:
                    raise EmailServiceError("sendgrid package not installed")
                from sendgrid.helpers.mail import Attachment
                for attachment in attachments:
                    mail.add_attachment(
                        Attachment(
                            file_content=attachment['content'],
                            file_name=attachment['filename'],
                            file_type=attachment.get('content_type', 'application/octet-stream'),
                            disposition='attachment'
                        )
                    )

            # Send email
            response = self.client.send(mail)

            # Extract message ID from response headers
            message_id = None
            if hasattr(response, 'headers') and 'X-Message-Id' in response.headers:
                message_id = response.headers['X-Message-Id']

            logger.info(
                "email_sent_sendgrid",
                to_email=to_email,
                subject=subject,
                status_code=response.status_code,
                message_id=message_id
            )

            return {
                'success': True,
                'message_id': message_id,
                'status_code': response.status_code
            }

        except Exception as e:
            logger.error(
                "email_send_failed_sendgrid",
                to_email=to_email,
                subject=subject,
                error=str(e),
                exc_info=True
            )
            raise EmailServiceError(f"SendGrid email sending failed: {str(e)}") from e


class SESEmailService(BaseService, EmailService):
    """
    AWS SES email service implementation.

    Requires AWS credentials and SES region in settings.
    """

    service_name = "ses_email_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """Initialize SESEmailService with BaseService support."""
        # Set BaseService attributes
        self.tenant_id = tenant_id
        self.user_id = user_id
        if not BOTO3_AVAILABLE:
            raise EmailServiceError("boto3 package not installed. Install with: pip install boto3")
        region = getattr(settings, 'AWS_SES_REGION', None)
        if not region:
            raise EmailServiceError("AWS_SES_REGION not configured in settings")

        # Use boto3 session with credentials from settings or environment
        self.client = boto3.client(
            'ses',
            region_name=region,
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        )
        self.from_email = getattr(settings, 'AWS_SES_FROM_EMAIL', None)
        self.from_name = getattr(settings, 'AWS_SES_FROM_NAME', 'Data Interoperability Hub')

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send email via AWS SES"""
        try:
            # Use configured from_email or provided one
            sender_email = from_email or self.from_email
            if not sender_email:
                raise EmailServiceError("from_email not configured and not provided")

            # Format from address with name if provided
            sender_name = from_name or self.from_name
            if sender_name:
                from_addr = f"{sender_name} <{sender_email}>"
            else:
                from_addr = sender_email

            # Build message body
            message_body = {
                'Html': {
                    'Data': html_content,
                    'Charset': 'UTF-8'
                }
            }

            if text_content:
                message_body['Text'] = {
                    'Data': text_content,
                    'Charset': 'UTF-8'
                }

            # Build destination
            destination = {
                'ToAddresses': [to_email]
            }

            # Build message
            message = {
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': message_body
            }

            # Build send email parameters
            send_params = {
                'Source': from_addr,
                'Destination': destination,
                'Message': message
            }

            # Add reply-to if provided
            if reply_to:
                send_params['ReplyToAddresses'] = [reply_to]

            # Note: SES doesn't support attachments in the same way as SendGrid
            # Attachments would need to be handled via SES Raw Email API or S3
            if attachments:
                logger.warning(
                    "email_attachments_not_supported_ses",
                    to_email=to_email,
                    subject=subject,
                    message="SES send_email API doesn't support attachments directly"
                )

            # Send email
            response = self.client.send_email(**send_params)

            message_id = response.get('MessageId')

            logger.info(
                "email_sent_ses",
                to_email=to_email,
                subject=subject,
                message_id=message_id
            )

            return {
                'success': True,
                'message_id': message_id
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(
                "email_send_failed_ses",
                to_email=to_email,
                subject=subject,
                error_code=error_code,
                error_message=error_message,
                exc_info=True
            )
            raise EmailServiceError(f"AWS SES email sending failed: {error_code} - {error_message}") from e
        except Exception as e:
            logger.error(
                "email_send_failed_ses",
                to_email=to_email,
                subject=subject,
                error=str(e),
                exc_info=True
            )
            raise EmailServiceError(f"AWS SES email sending failed: {str(e)}") from e


class SMTPEmailService(BaseService, EmailService):
    """
    Generic SMTP email service implementation.

    Uses Django's email backend with SMTP configuration.
    """

    service_name = "smtp_email_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """Initialize SMTPEmailService with BaseService support."""
        # Set BaseService attributes
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.host = getattr(settings, 'SMTP_HOST', 'localhost')
        self.port = getattr(settings, 'SMTP_PORT', 587)
        self.username = getattr(settings, 'SMTP_USERNAME', None)
        self.password = getattr(settings, 'SMTP_PASSWORD', None)
        self.use_tls = getattr(settings, 'SMTP_USE_TLS', True)
        self.use_ssl = getattr(settings, 'SMTP_USE_SSL', False)
        self.from_email = getattr(settings, 'SMTP_FROM_EMAIL', None)
        self.from_name = getattr(settings, 'SMTP_FROM_NAME', 'Data Interoperability Hub')

    def _get_connection(self):
        """Get SMTP connection"""
        return get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            use_tls=self.use_tls,
            use_ssl=self.use_ssl,
            fail_silently=False
        )

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send email via SMTP"""
        try:
            # Use configured from_email or provided one
            sender_email = from_email or self.from_email
            if not sender_email:
                raise EmailServiceError("from_email not configured and not provided")

            # Format from address with name if provided
            sender_name = from_name or self.from_name
            if sender_name:
                from_addr = f"{sender_name} <{sender_email}>"
            else:
                from_addr = sender_email

            # Create email message with HTML and text alternatives
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content or html_content,  # Use text as primary, fallback to HTML
                from_email=from_addr,
                to=[to_email],
                connection=self._get_connection()
            )

            # Attach HTML alternative
            email.attach_alternative(html_content, 'text/html')

            # Add reply-to if provided
            if reply_to:
                email.reply_to = [reply_to]

            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    email.attach(
                        filename=attachment['filename'],
                        content=attachment['content'],
                        mimetype=attachment.get('content_type', 'application/octet-stream')
                    )

            # Send email
            result = email.send()

            # Django's send() returns number of emails sent (1 if successful)
            success = result == 1

            logger.info(
                "email_sent_smtp",
                to_email=to_email,
                subject=subject,
                success=success,
                result=result
            )

            return {
                'success': success,
                'message_id': None  # SMTP doesn't provide message IDs
            }

        except Exception as e:
            logger.error(
                "email_send_failed_smtp",
                to_email=to_email,
                subject=subject,
                error=str(e),
                exc_info=True
            )
            raise EmailServiceError(f"SMTP email sending failed: {str(e)}") from e


def get_email_service() -> EmailService:
    """
    Factory function to get the configured email service.

    Returns:
        EmailService instance based on EMAIL_BACKEND setting

    Raises:
        EmailServiceError: If EMAIL_BACKEND is not configured or invalid
    """
    backend = getattr(settings, 'EMAIL_BACKEND', None)

    if not backend:
        raise EmailServiceError("EMAIL_BACKEND not configured in settings")

    if backend == 'sendgrid':
        return SendGridEmailService()
    elif backend == 'ses':
        return SESEmailService()
    elif backend == 'smtp':
        return SMTPEmailService()
    else:
        raise EmailServiceError(f"Invalid EMAIL_BACKEND: {backend}. Must be 'sendgrid', 'ses', or 'smtp'")

