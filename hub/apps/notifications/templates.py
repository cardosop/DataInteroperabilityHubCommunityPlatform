"""
Email Template Rendering

Utilities for rendering email templates with context.
"""
from typing import Dict, Any, Optional
from django.template.loader import render_to_string
from django.conf import settings

# Optional import for HTML to text conversion
try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False
    html2text = None


def render_email_template(
    template_name: str,
    context: Dict[str, Any],
    text_template_name: Optional[str] = None
) -> Dict[str, str]:
    """
    Render email template to HTML and plain text.

    Args:
        template_name: Name of the HTML template (e.g., 'notifications/emails/user_invitation.html')
        context: Template context variables
        text_template_name: Optional name of plain text template (auto-generated from HTML if not provided)

    Returns:
        Dict with 'html' and 'text' keys containing rendered content
    """
    # Inject app_name for email templates (Phase 28.7.5 Meshant)
    ctx = dict(context)
    ctx.setdefault('app_name', getattr(settings, 'APP_NAME', 'Meshant'))
    # Render HTML template
    html_content = render_to_string(template_name, ctx)

    # Generate plain text from HTML if text template not provided
    if text_template_name:
        text_content = render_to_string(text_template_name, ctx)
    else:
        # Convert HTML to plain text
        if HTML2TEXT_AVAILABLE:
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = True
            text_content = h.handle(html_content)
        else:
            # Fallback: strip HTML tags manually if html2text not available
            import re
            # Simple HTML tag removal (not as sophisticated as html2text)
            text_content = re.sub(r'<[^>]+>', '', html_content)
            # Decode HTML entities
            import html
            text_content = html.unescape(text_content)
            # Clean up whitespace
            text_content = re.sub(r'\s+', ' ', text_content).strip()

    return {
        'html': html_content,
        'text': text_content
    }


def get_base_url() -> str:
    """
    Get base URL for email links.

    Returns:
        Base URL from settings or default
    """
    base_url = getattr(settings, 'EMAIL_BASE_URL', 'http://localhost:8000')
    # Handle case where EMAIL_BASE_URL is explicitly set to None
    if base_url is None:
        return 'http://localhost:8000'
    return base_url


def build_invitation_url(token: str) -> str:
    """
    Build invitation acceptance URL.

    Args:
        token: Invitation token

    Returns:
        Full invitation URL
    """
    base_url = get_base_url()
    return f"{base_url}/auth/accept-invitation?token={token}"


def build_password_reset_url(token: str) -> str:
    """
    Build password reset URL.

    Args:
        token: Password reset token

    Returns:
        Full password reset URL
    """
    base_url = get_base_url()
    return f"{base_url}/auth/password-reset/confirm?token={token}"


def build_job_url(job_id: str) -> str:
    """
    Build job detail URL.

    Args:
        job_id: Job UUID

    Returns:
        Full job URL
    """
    base_url = get_base_url()
    return f"{base_url}/api/v1/jobs/{job_id}"


def build_contract_url(contract_id: str) -> str:
    """
    Build contract detail URL.

    Args:
        contract_id: Contract UUID

    Returns:
        Full contract URL
    """
    base_url = get_base_url()
    return f"{base_url}/api/v1/contracts/{contract_id}"


def build_marketplace_sync_job_url(sync_job_id: str) -> str:
    """
    Build marketplace sync job detail URL.

    Args:
        sync_job_id: Sync job UUID

    Returns:
        Full marketplace sync job URL
    """
    base_url = get_base_url()
    return f"{base_url}/api/v1/integrations/marketplace/sync/{sync_job_id}/"


def build_marketplace_connection_url(connection_id: str) -> str:
    """
    Build marketplace connection detail URL.

    Args:
        connection_id: Connection UUID

    Returns:
        Full marketplace connection URL
    """
    base_url = get_base_url()
    return f"{base_url}/api/v1/integrations/marketplace/connections/{connection_id}/"

