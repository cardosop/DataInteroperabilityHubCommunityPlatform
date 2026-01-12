"""
Notifications Business Rules

Comprehensive business rules validation for notification operations, including:
- Notification creation validation
- Notification delivery validation
- Template validation
- Recipient validation
- Tenant and user context validation

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.notifications.models import EmailDelivery, EmailType, EmailDeliveryStatus
from hub.apps.users.models import User

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


@dataclass
class NotificationsRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for notifications business rules.

    Adds notification-specific context:
    - notification: The EmailDelivery instance being validated
    - template: Optional template name/path for validation
    - recipient: Optional recipient email address
    - tenant: Optional tenant instance for validation
    - user: Optional user instance for permission validation
    """
    notification: Optional[EmailDelivery] = None
    template: Optional[str] = None
    recipient: Optional[str] = None
    tenant: Optional[Any] = None  # Using Any to avoid circular import
    user: Optional[User] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update({
            'notification_id': str(self.notification.id) if self.notification else None,
            'template': self.template,
            'recipient': self.recipient,
            'tenant_id_from_instance': str(self.tenant.id) if self.tenant else None,
            'user_id_from_instance': str(self.user.id) if self.user else None,
        })
        return base_dict


@register_rule(
    rule_name="notifications_validation",
    description="Validates notification creation, delivery, templates, recipients, tenant context, and user permissions",
    tags=["notifications", "validation"],
    priority=10
)
class NotificationsBusinessRules(BusinessRules):
    """
    Business rules validator for notification operations.

    Extends BusinessRules base class with notification-specific validation:
    - Notification creation validation
    - Notification delivery validation
    - Template validation
    - Recipient validation
    - Tenant context consistency
    - User permissions and access validation
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "NotificationsBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all notification validation checks.
        It can be called with a NotificationsRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        notification, template, recipient, tenant, and user from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - notification: EmailDelivery instance (optional)
                - template: Template name/path (optional)
                - recipient: Recipient email address (optional)
                - tenant: Optional tenant instance
                - user: Optional user instance
                - validation_type: Optional validation type filter
                    ('notification_creation', 'notification_delivery', 'template', 'recipient', 'tenant_context', 'permissions', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract notification, template, recipient, tenant, and user from context or kwargs
        if isinstance(context, NotificationsRuleExecutionContext):
            notification = context.notification
            template = context.template
            recipient = context.recipient
            tenant = context.tenant
            user = context.user
        else:
            # Try to get from kwargs first
            notification = kwargs.get('notification')
            template = kwargs.get('template')
            recipient = kwargs.get('recipient')
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')

            # If not in kwargs, try to get from context.metadata or context.resource
            if context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                notification = notification or context.metadata.get('notification')
                template = template or context.metadata.get('template')
                recipient = recipient or context.metadata.get('recipient')
                tenant = tenant or context.metadata.get('tenant')
                user = user or context.metadata.get('user')

            # Also check context.resource
            if not notification and context and hasattr(context, 'resource'):
                if isinstance(context.resource, EmailDelivery):
                    notification = context.resource

        # Determine what to validate based on what's provided
        validation_type = kwargs.get('validation_type', 'all')

        # Initialize result
        result = ValidationResult(is_valid=True)

        # Track what was validated
        validated_items = []

        # Validate notification if provided
        if notification and validation_type in ('notification_creation', 'notification_delivery', 'all'):
            notification_result = self._validate_notification_basic(notification, tenant, user)
            result = result.combine(notification_result)
            validated_items.append('notification_basic')

        # Validate template if provided
        if template and validation_type in ('template', 'all'):
            template_result = self._validate_template_basic(template)
            result = result.combine(template_result)
            validated_items.append('template_basic')

        # Validate recipient if provided
        if recipient and validation_type in ('recipient', 'all'):
            recipient_result = self._validate_recipient_basic(recipient)
            result = result.combine(recipient_result)
            validated_items.append('recipient_basic')

        # Validate tenant context if tenant provided
        if tenant and validation_type in ('tenant_context', 'all'):
            tenant_context_result = self._validate_tenant_context(tenant)
            result = result.combine(tenant_context_result)
            validated_items.append('tenant_context')

        # Validate permissions if user provided
        if user and validation_type in ('permissions', 'all'):
            permissions_result = self._validate_permissions(user, tenant)
            result = result.combine(permissions_result)
            validated_items.append('permissions')

        # If nothing was validated, return appropriate result
        if not validated_items:
            return ValidationResult(
                is_valid=False,
                errors=["At least one of notification, template, recipient, tenant, or user must be provided"],
                details={'validation_type': validation_type}
            )

        # Add validation summary to details
        result.details['validated_items'] = validated_items
        result.details['validation_type'] = validation_type

        return result

    def _validate_notification_basic(
        self,
        notification: EmailDelivery,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate basic notification structure and context.

        Validates:
        - Notification has required fields (email_type, to_email, subject, status)
        - Email type is valid
        - Status is valid
        - Tenant context consistency
        - User context consistency

        Args:
            notification: EmailDelivery instance to validate
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'notification_id': str(notification.id),
            'email_type': notification.email_type,
            'status': notification.status,
        }

        # Validate tenant context consistency
        if self.tenant_id and notification.tenant_id:
            if str(notification.tenant_id) != str(self.tenant_id):
                errors.append(
                    f"Notification tenant ({notification.tenant_id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True

        # Validate tenant context if provided
        if tenant and notification.tenant_id:
            if str(tenant.id) != str(notification.tenant_id):
                errors.append(
                    f"Notification tenant ({notification.tenant_id}) does not match "
                    f"provided tenant ({tenant.id})"
                )
                details['provided_tenant_match'] = False
            else:
                details['provided_tenant_match'] = True

        # Validate email type
        valid_email_types = [choice[0] for choice in EmailType.choices]
        if notification.email_type not in valid_email_types:
            errors.append(
                f"Notification has invalid email_type: {notification.email_type}. "
                f"Valid email types are: {', '.join(valid_email_types)}"
            )
            details['email_type_valid'] = False
        else:
            details['email_type_valid'] = True

        # Validate status
        valid_statuses = [choice[0] for choice in EmailDeliveryStatus.choices]
        if notification.status not in valid_statuses:
            errors.append(
                f"Notification has invalid status: {notification.status}. "
                f"Valid statuses are: {', '.join(valid_statuses)}"
            )
            details['status_valid'] = False
        else:
            details['status_valid'] = True

        # Validate required fields
        if not notification.to_email or not notification.to_email.strip():
            errors.append("Notification must have a to_email")
            details['has_to_email'] = False
        else:
            details['has_to_email'] = True
            details['to_email'] = notification.to_email

        if not notification.subject or not notification.subject.strip():
            errors.append("Notification must have a subject")
            details['has_subject'] = False
        else:
            details['has_subject'] = True
            details['subject'] = notification.subject

        # Validate user context if user provided
        if user and notification.user:
            if str(user.id) != str(notification.user.id):
                warnings.append(
                    f"Provided user ({user.id}) does not match "
                    f"notification user ({notification.user.id})"
                )
                details['user_match'] = False
            else:
                details['user_match'] = True

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_template_basic(
        self,
        template: str
    ) -> ValidationResult:
        """
        Validate basic template structure.

        Validates:
        - Template name/path is provided
        - Template name format is valid

        Args:
            template: Template name/path to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'template': template,
        }

        # Validate template is provided
        if not template or not template.strip():
            errors.append("Template name/path must be provided")
            details['has_template'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['has_template'] = True

        # Validate template format (basic check - should be a string path)
        if not isinstance(template, str):
            errors.append("Template must be a string")
            details['template_format_valid'] = False
        else:
            details['template_format_valid'] = True

            # Warn if template doesn't look like a valid path
            if not ('.html' in template or '/' in template):
                warnings.append(
                    f"Template '{template}' does not look like a valid template path. "
                    f"Expected format: 'notifications/emails/template_name.html'"
                )
                details['template_path_looks_valid'] = False
            else:
                details['template_path_looks_valid'] = True

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_recipient_basic(
        self,
        recipient: str
    ) -> ValidationResult:
        """
        Validate basic recipient structure.

        Validates:
        - Recipient email is provided
        - Recipient email format is valid

        Args:
            recipient: Recipient email address to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'recipient': recipient,
        }

        # Validate recipient is provided
        if not recipient or not recipient.strip():
            errors.append("Recipient email must be provided")
            details['has_recipient'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['has_recipient'] = True

        # Basic email format validation
        if '@' not in recipient:
            errors.append(f"Recipient '{recipient}' does not appear to be a valid email address")
            details['email_format_valid'] = False
        else:
            details['email_format_valid'] = True

            # Warn if email looks suspicious
            if recipient.count('@') > 1:
                warnings.append(f"Recipient '{recipient}' has multiple @ symbols")
                details['email_suspicious'] = True
            else:
                details['email_suspicious'] = False

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_tenant_context(self, tenant: Any) -> ValidationResult:
        """
        Validate tenant context consistency.

        Args:
            tenant: Tenant instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        details = {
            'tenant_id': str(tenant.id),
            'tenant_name': tenant.name if hasattr(tenant, 'name') else None
        }

        # Validate tenant context consistency
        if self.tenant_id:
            if str(tenant.id) != str(self.tenant_id):
                errors.append(
                    f"Provided tenant ({tenant.id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True

        details['is_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            details=details
        )

    def _validate_permissions(
        self,
        user: User,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate user permissions.

        Args:
            user: User instance to validate
            tenant: Optional tenant instance

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'user_id': str(user.id),
            'user_email': user.email
        }

        # Validate user context consistency
        if self.user_id:
            if str(user.id) != str(self.user_id):
                warnings.append(
                    f"Provided user ({user.id}) does not match "
                    f"context user ({self.user_id})"
                )
                details['user_match'] = False
            else:
                details['user_match'] = True

        # Validate user has tenant if tenant provided
        if tenant and hasattr(user, 'tenant_id') and user.tenant_id:
            if str(user.tenant_id) != str(tenant.id):
                errors.append(
                    f"User tenant ({user.tenant_id}) does not match "
                    f"provided tenant ({tenant.id})"
                )
                details['user_tenant_match'] = False
            else:
                details['user_tenant_match'] = True

        # Validate user tenant matches context tenant if both provided
        if self.tenant_id and hasattr(user, 'tenant_id') and user.tenant_id:
            if str(user.tenant_id) != str(self.tenant_id):
                warnings.append(
                    f"User tenant ({user.tenant_id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details['user_context_tenant_match'] = False
            else:
                details['user_context_tenant_match'] = True

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_template_structure(
        self,
        template_name: str
    ) -> ValidationResult:
        """
        Validate template structure (valid template format, extends base, has blocks).

        Validates:
        - Template exists and can be loaded
        - Template extends base.html
        - Template has required blocks (content)
        - Template has valid Django template syntax

        Args:
            template_name: Template name/path to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'template': template_name,
            'validation_type': 'template_structure'
        }

        # Basic template validation first
        basic_result = self._validate_template_basic(template_name)
        if not basic_result.is_valid:
            return basic_result

        # Try to load template
        try:
            from django.template.loader import get_template
            template = get_template(template_name)
            details['template_exists'] = True
            details['template_loaded'] = True
        except Exception as e:
            errors.append(f"Template '{template_name}' cannot be loaded: {str(e)}")
            details['template_exists'] = False
            details['template_loaded'] = False
            details['load_error'] = str(e)
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Read template source to check structure
        try:
            # Get template file path and read source
            from django.template.loader import get_template
            from django.template.loaders.filesystem import Loader as FilesystemLoader
            from django.template.loaders.app_directories import Loader as AppDirectoriesLoader
            import os
            from django.conf import settings

            # Try to find template file
            template_source = None
            template_file_path = None

            # Check template directories
            template_dirs = getattr(settings, 'TEMPLATES', [{}])[0].get('DIRS', [])
            for template_dir in template_dirs:
                template_path = os.path.join(template_dir, template_name)
                if os.path.exists(template_path):
                    template_file_path = template_path
                    with open(template_path, 'r', encoding='utf-8') as f:
                        template_source = f.read()
                    break

            # If not found in DIRS, check app directories
            if not template_source:
                from django.apps import apps
                for app_config in apps.get_app_configs():
                    app_template_dir = os.path.join(app_config.path, 'templates')
                    if os.path.exists(app_template_dir):
                        template_path = os.path.join(app_template_dir, template_name)
                        if os.path.exists(template_path):
                            template_file_path = template_path
                            with open(template_path, 'r', encoding='utf-8') as f:
                                template_source = f.read()
                            break

            if not template_source:
                raise ValueError(f"Could not find template file for '{template_name}'")

            details['has_source'] = True
            details['template_file_path'] = template_file_path

            # Check if template extends base.html
            if '{% extends' in template_source:
                if 'notifications/emails/base.html' in template_source or 'base.html' in template_source:
                    details['extends_base'] = True
                else:
                    warnings.append(
                        f"Template '{template_name}' extends a template but may not extend base.html. "
                        "Expected: '{% extends \"notifications/emails/base.html\" %}'"
                    )
                    details['extends_base'] = False
            else:
                warnings.append(
                    f"Template '{template_name}' does not extend base.html. "
                    f"All email templates should extend 'notifications/emails/base.html'"
                )
                details['extends_base'] = False

            # Check for content block
            if '{% block content' in template_source:
                details['has_content_block'] = True
            else:
                errors.append(
                    f"Template '{template_name}' must have a '{{% block content %}}' block"
                )
                details['has_content_block'] = False

            # Check for title block (optional but recommended)
            if '{% block title' in template_source:
                details['has_title_block'] = True
            else:
                warnings.append(
                    f"Template '{template_name}' should have a '{{% block title %}}' block for email subject"
                )
                details['has_title_block'] = False

            # Validate Django template syntax (basic check)
            try:
                from django.template import Template, TemplateSyntaxError
                Template(template_source)
                details['syntax_valid'] = True
            except TemplateSyntaxError as e:
                errors.append(f"Template '{template_name}' has syntax errors: {str(e)}")
                details['syntax_valid'] = False
                details['syntax_error'] = str(e)
            except Exception as e:
                warnings.append(f"Could not validate template syntax: {str(e)}")
                details['syntax_valid'] = None
                details['syntax_error'] = str(e)

        except Exception as e:
            warnings.append(f"Could not read template source: {str(e)}")
            details['has_source'] = False
            details['source_error'] = str(e)

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_template_variables(
        self,
        template_name: str,
        context: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate template variables (valid variable placeholders, no undefined variables).

        Validates:
        - Required variables are provided in context
        - Variables are used correctly in template
        - No undefined variable references (warnings only, as Django handles this)

        Args:
            template_name: Template name/path to validate
            context: Template context variables

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'template': template_name,
            'validation_type': 'template_variables',
            'context_keys': list(context.keys()) if context else []
        }

        # Basic template validation first
        basic_result = self._validate_template_basic(template_name)
        if not basic_result.is_valid:
            return basic_result

        # Try to render template with context to check for undefined variables
        try:
            from django.template.loader import render_to_string
            rendered = render_to_string(template_name, context)
            details['rendered_successfully'] = True
            details['rendered_length'] = len(rendered)
        except Exception as e:
            # Check if error is due to missing variables
            error_str = str(e).lower()
            if 'variable' in error_str or 'undefined' in error_str:
                errors.append(f"Template '{template_name}' has undefined variables: {str(e)}")
                details['rendered_successfully'] = False
                details['render_error'] = str(e)
                details['error_type'] = 'undefined_variable'
            else:
                errors.append(f"Template '{template_name}' rendering failed: {str(e)}")
                details['rendered_successfully'] = False
                details['render_error'] = str(e)
                details['error_type'] = 'render_error'

            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Extract variables from template source
        try:
            # Read template file directly
            from django.template.loader import get_template
            import os
            from django.conf import settings

            template_source = None
            # Check template directories
            template_dirs = getattr(settings, 'TEMPLATES', [{}])[0].get('DIRS', [])
            for template_dir in template_dirs:
                template_path = os.path.join(template_dir, template_name)
                if os.path.exists(template_path):
                    with open(template_path, 'r', encoding='utf-8') as f:
                        template_source = f.read()
                    break

            # If not found in DIRS, check app directories
            if not template_source:
                from django.apps import apps
                for app_config in apps.get_app_configs():
                    app_template_dir = os.path.join(app_config.path, 'templates')
                    if os.path.exists(app_template_dir):
                        template_path = os.path.join(app_template_dir, template_name)
                        if os.path.exists(template_path):
                            with open(template_path, 'r', encoding='utf-8') as f:
                                template_source = f.read()
                            break

            if not template_source:
                raise ValueError(f"Could not find template file for '{template_name}'")

            # Find all variable references in template (basic regex)
            import re
            # Match {{ variable }} and {{ variable.attribute }}
            variable_pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}'
            variables_in_template = set(re.findall(variable_pattern, template_source))
            details['variables_in_template'] = list(variables_in_template)

            # Check for required variables (common ones)
            common_required = ['user', 'tenant']
            missing_required = []
            for var in common_required:
                if var in variables_in_template and var not in context:
                    missing_required.append(var)

            if missing_required:
                warnings.append(
                    f"Template '{template_name}' uses variables that are not in context: {', '.join(missing_required)}"
                )
                details['missing_variables'] = missing_required
            else:
                details['missing_variables'] = []

            # Check for variables with filters (should be safe)
            filter_pattern = r'\{\{\s*[^|]+\|[^}]+\s*\}\}'
            variables_with_filters = re.findall(filter_pattern, template_source)
            details['variables_with_filters'] = len(variables_with_filters)

            details['variables_validated'] = True

        except Exception as e:
            warnings.append(f"Could not extract variables from template: {str(e)}")
            details['variables_validated'] = False
            details['variable_extraction_error'] = str(e)

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_template_content(
        self,
        template_name: str,
        context: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate template content (content length, prohibited content).

        Validates:
        - Rendered content length is within limits
        - No prohibited content patterns
        - Content structure is valid

        Args:
            template_name: Template name/path to validate
            context: Template context variables

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'template': template_name,
            'validation_type': 'template_content'
        }

        # Basic template validation first
        basic_result = self._validate_template_basic(template_name)
        if not basic_result.is_valid:
            return basic_result

        # Render template to check content
        try:
            from django.template.loader import render_to_string
            rendered = render_to_string(template_name, context)
            details['rendered_successfully'] = True
            details['rendered_length'] = len(rendered)
        except Exception as e:
            errors.append(f"Template '{template_name}' rendering failed: {str(e)}")
            details['rendered_successfully'] = False
            details['render_error'] = str(e)
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate content length
        MAX_CONTENT_LENGTH = 500000  # 500KB max for email content
        MIN_CONTENT_LENGTH = 50  # Minimum reasonable content length

        if len(rendered) > MAX_CONTENT_LENGTH:
            errors.append(
                f"Template '{template_name}' renders to content that is too long ({len(rendered)} bytes). "
                f"Maximum allowed: {MAX_CONTENT_LENGTH} bytes"
            )
            details['content_length_valid'] = False
        elif len(rendered) < MIN_CONTENT_LENGTH:
            warnings.append(
                f"Template '{template_name}' renders to very short content ({len(rendered)} bytes). "
                f"Minimum recommended: {MIN_CONTENT_LENGTH} bytes"
            )
            details['content_length_valid'] = True
            details['content_too_short'] = True
        else:
            details['content_length_valid'] = True
            details['content_too_short'] = False

        details['content_length'] = len(rendered)
        details['max_content_length'] = MAX_CONTENT_LENGTH
        details['min_content_length'] = MIN_CONTENT_LENGTH

        # Check for prohibited content patterns
        prohibited_patterns = [
            (r'<iframe[^>]*>', 'iframe tags are not allowed in emails'),
            (r'<object[^>]*>', 'object tags are not allowed in emails'),
            (r'<embed[^>]*>', 'embed tags are not allowed in emails'),
            (r'<form[^>]*>', 'form tags are not allowed in emails'),
        ]

        found_prohibited = []
        import re
        for pattern, description in prohibited_patterns:
            if re.search(pattern, rendered, re.IGNORECASE):
                errors.append(
                    f"Template '{template_name}' contains prohibited content: {description}"
                )
                found_prohibited.append(description)

        details['prohibited_content_found'] = found_prohibited
        details['prohibited_content_valid'] = len(found_prohibited) == 0

        # Check for empty content blocks
        if '{% block content' in rendered or 'block content' in rendered.lower():
            # Check if content block is effectively empty
            content_match = re.search(r'<div class="content">(.*?)</div>', rendered, re.DOTALL)
            if content_match:
                content_text = content_match.group(1)
                # Remove HTML tags and whitespace
                text_only = re.sub(r'<[^>]+>', '', content_text).strip()
                if len(text_only) < 10:
                    warnings.append(
                        f"Template '{template_name}' content block appears to be empty or very short"
                    )
                    details['content_block_empty'] = True
                else:
                    details['content_block_empty'] = False
            else:
                details['content_block_empty'] = None
        else:
            details['content_block_empty'] = None

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_template_security(
        self,
        template_name: str,
        context: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate template security (no injection vulnerabilities, XSS protection).

        Validates:
        - No script tags in rendered content
        - No javascript: URLs
        - No on* event handlers
        - Django auto-escaping is working
        - No dangerous HTML patterns

        Args:
            template_name: Template name/path to validate
            context: Template context variables

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'template': template_name,
            'validation_type': 'template_security'
        }

        # Basic template validation first
        basic_result = self._validate_template_basic(template_name)
        if not basic_result.is_valid:
            return basic_result

        # Render template to check security
        try:
            from django.template.loader import render_to_string
            rendered = render_to_string(template_name, context)
            details['rendered_successfully'] = True
            details['rendered_length'] = len(rendered)
        except Exception as e:
            errors.append(f"Template '{template_name}' rendering failed: {str(e)}")
            details['rendered_successfully'] = False
            details['render_error'] = str(e)
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        import re

        # Check for script tags (should be escaped by Django)
        script_patterns = [
            (r'<script[^>]*>.*?</script>', 'script tags'),
            (r'<script[^>]*>', 'opening script tags'),
        ]

        found_scripts = []
        for pattern, description in script_patterns:
            matches = re.findall(pattern, rendered, re.IGNORECASE | re.DOTALL)
            if matches:
                # Check if they're escaped (should contain &lt; or &#60;)
                unescaped = [m for m in matches if not ('&lt;' in m or '&#60;' in m)]
                if unescaped:
                    errors.append(
                        f"Template '{template_name}' contains unescaped {description} in rendered content. "
                        f"This is a security vulnerability."
                    )
                    found_scripts.extend(unescaped)
                else:
                    # Escaped scripts are OK (Django auto-escaping working)
                    details['scripts_escaped'] = True

        details['script_tags_found'] = len(found_scripts)
        details['script_tags_valid'] = len(found_scripts) == 0

        # Check for javascript: URLs
        javascript_url_pattern = r'javascript:\s*[^"\'<>]*'
        javascript_urls = re.findall(javascript_url_pattern, rendered, re.IGNORECASE)
        if javascript_urls:
            errors.append(
                f"Template '{template_name}' contains javascript: URLs which are a security risk"
            )
            details['javascript_urls_found'] = javascript_urls
            details['javascript_urls_valid'] = False
        else:
            details['javascript_urls_found'] = []
            details['javascript_urls_valid'] = True

        # Check for on* event handlers (onclick, onerror, etc.)
        event_handler_pattern = r'\bon\w+\s*=\s*["\'][^"\']*["\']'
        event_handlers = re.findall(event_handler_pattern, rendered, re.IGNORECASE)
        if event_handlers:
            warnings.append(
                f"Template '{template_name}' contains event handlers (onclick, onerror, etc.) "
                f"which may be a security concern"
            )
            details['event_handlers_found'] = event_handlers
            details['event_handlers_valid'] = False
        else:
            details['event_handlers_found'] = []
            details['event_handlers_valid'] = True

        # Check for data: URLs (may be used for XSS)
        data_url_pattern = r'data:\s*[^"\'<>]*'
        data_urls = re.findall(data_url_pattern, rendered, re.IGNORECASE)
        if data_urls:
            warnings.append(
                f"Template '{template_name}' contains data: URLs which may be a security concern"
            )
            details['data_urls_found'] = data_urls
            details['data_urls_valid'] = False
        else:
            details['data_urls_found'] = []
            details['data_urls_valid'] = True

        # Check if Django auto-escaping is working (look for escaped HTML entities)
        # If we find &lt; or &#60; in rendered content, escaping is likely working
        escaped_patterns = [r'&lt;', r'&#60;', r'&gt;', r'&#62;', r'&amp;', r'&#38;']
        escaped_found = any(re.search(pattern, rendered) for pattern in escaped_patterns)
        details['auto_escaping_detected'] = escaped_found

        if not escaped_found and ('<' in rendered or '>' in rendered):
            warnings.append(
                f"Template '{template_name}' may not be using Django auto-escaping. "
                "Ensure variables use {{ variable }} not {{ variable|safe }} unless necessary"
            )

        details['security_validated'] = len(errors) == 0
        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_delivery_channel(
        self,
        channel: str,
        notification: Optional[EmailDelivery] = None
    ) -> ValidationResult:
        """
        Validate delivery channel (valid delivery channels: EMAIL, SMS, PUSH, IN_APP).

        Validates:
        - Channel is one of the supported channels
        - Channel is appropriate for the notification type
        - Channel configuration is valid

        Args:
            channel: Delivery channel to validate (EMAIL, SMS, PUSH, IN_APP)
            notification: Optional EmailDelivery instance for context

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'channel': channel,
            'validation_type': 'delivery_channel'
        }

        # Define supported delivery channels
        SUPPORTED_CHANNELS = ['EMAIL', 'SMS', 'PUSH', 'IN_APP']

        # Currently only EMAIL is fully implemented
        IMPLEMENTED_CHANNELS = ['EMAIL']

        # Validate channel is provided
        if not channel or not channel.strip():
            errors.append("Delivery channel must be provided")
            details['has_channel'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['has_channel'] = True
        channel_upper = channel.upper().strip()

        # Validate channel is supported
        if channel_upper not in SUPPORTED_CHANNELS:
            errors.append(
                f"Invalid delivery channel '{channel}'. "
                f"Supported channels are: {', '.join(SUPPORTED_CHANNELS)}"
            )
            details['channel_supported'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['channel_supported'] = True

        # Check if channel is implemented
        if channel_upper not in IMPLEMENTED_CHANNELS:
            warnings.append(
                f"Delivery channel '{channel}' is supported but not yet fully implemented. "
                f"Currently implemented channels: {', '.join(IMPLEMENTED_CHANNELS)}"
            )
            details['channel_implemented'] = False
        else:
            details['channel_implemented'] = True

        # Validate channel-specific requirements
        if channel_upper == 'EMAIL':
            # For EMAIL channel, validate that notification has email address if provided
            if notification and not notification.to_email:
                errors.append(
                    "EMAIL channel requires a valid recipient email address"
                )
                details['email_recipient_valid'] = False
            elif notification:
                details['email_recipient_valid'] = True
        elif channel_upper == 'SMS':
            # SMS would require phone number (not yet implemented)
            warnings.append(
                "SMS channel requires a valid phone number. "
                "Phone number validation not yet implemented."
            )
        elif channel_upper == 'PUSH':
            # PUSH would require device token (not yet implemented)
            warnings.append(
                "PUSH channel requires a valid device token. "
                "Device token validation not yet implemented."
            )
        elif channel_upper == 'IN_APP':
            # IN_APP would require user ID (not yet implemented)
            warnings.append(
                "IN_APP channel requires a valid user ID. "
                "User ID validation not yet implemented."
            )

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_recipient(
        self,
        recipient: str,
        channel: str = 'EMAIL'
    ) -> ValidationResult:
        """
        Validate recipient address (valid recipient addresses for the channel).

        Validates:
        - Email format for EMAIL channel
        - Phone number format for SMS channel (when implemented)
        - Device token format for PUSH channel (when implemented)
        - User ID format for IN_APP channel (when implemented)

        Args:
            recipient: Recipient address to validate
            channel: Delivery channel (EMAIL, SMS, PUSH, IN_APP)

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'recipient': recipient,
            'channel': channel,
            'validation_type': 'recipient'
        }

        # Validate recipient is provided
        if not recipient or not recipient.strip():
            errors.append("Recipient address must be provided")
            details['has_recipient'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['has_recipient'] = True
        recipient = recipient.strip()
        channel_upper = channel.upper().strip()

        # Validate based on channel
        if channel_upper == 'EMAIL':
            # Use Django's email validator
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError

            try:
                validate_email(recipient)
                details['email_format_valid'] = True
            except ValidationError as e:
                errors.append(
                    f"Invalid email address '{recipient}': {', '.join(e.messages)}"
                )
                details['email_format_valid'] = False
                details['validation_error'] = str(e)

            # Additional email checks (only if Django validator passed)
            if '@' not in recipient:
                errors.append(f"Recipient '{recipient}' does not appear to be a valid email address")
            else:
                local_part, domain = recipient.split('@', 1)

                # Check local part
                if not local_part or len(local_part) > 64:
                    errors.append(
                        f"Email local part '{local_part}' is invalid. "
                        f"Must be between 1 and 64 characters."
                    )

                # Check domain
                if not domain or '.' not in domain:
                    errors.append(
                        f"Email domain '{domain}' is invalid. "
                        f"Must contain at least one dot."
                    )
                elif len(domain) > 255:
                    errors.append(
                        f"Email domain '{domain}' is too long. "
                        f"Maximum length is 255 characters."
                    )

                # Check for suspicious patterns (only if validation passed)
                if recipient.count('@') > 1:
                    errors.append(f"Email address '{recipient}' contains multiple @ symbols")

                # Note: Django validator already rejects consecutive dots, so this won't be reached
                # But we keep it for completeness in case validation logic changes
                if '..' in recipient and details['email_format_valid']:
                    warnings.append(f"Email address '{recipient}' contains consecutive dots")

        elif channel_upper == 'SMS':
            # Basic phone number validation (E.164 format)
            import re
            phone_pattern = r'^\+?[1-9]\d{1,14}$'
            if re.match(phone_pattern, recipient.replace(' ', '').replace('-', '')):
                details['phone_format_valid'] = True
            else:
                errors.append(
                    f"Invalid phone number '{recipient}'. "
                    f"Expected E.164 format (e.g., +1234567890)"
                )
                details['phone_format_valid'] = False

        elif channel_upper == 'PUSH':
            # Device token validation (basic format check)
            if len(recipient) >= 32 and len(recipient) <= 256:
                # Basic check - device tokens are typically 32-256 characters
                details['device_token_format_valid'] = True
            else:
                errors.append(
                    f"Invalid device token '{recipient}'. "
                    f"Device tokens should be between 32 and 256 characters."
                )
                details['device_token_format_valid'] = False

        elif channel_upper == 'IN_APP':
            # User ID validation (should be UUID)
            import uuid
            try:
                uuid.UUID(recipient)
                details['user_id_format_valid'] = True
            except ValueError:
                errors.append(
                    f"Invalid user ID '{recipient}'. "
                    f"User ID must be a valid UUID."
                )
                details['user_id_format_valid'] = False

        else:
            errors.append(
                f"Unknown delivery channel '{channel}'. "
                f"Cannot validate recipient format."
            )

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_delivery_rate_limiting(
        self,
        recipient: str,
        channel: str = 'EMAIL',
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate delivery rate limiting (rate limits not exceeded).

        Validates:
        - Rate limit per recipient
        - Rate limit per tenant
        - Rate limit per user
        - Rate limit per channel

        Args:
            recipient: Recipient address
            channel: Delivery channel (EMAIL, SMS, PUSH, IN_APP)
            tenant_id: Optional tenant ID
            user_id: Optional user ID

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'recipient': recipient,
            'channel': channel,
            'tenant_id': tenant_id,
            'user_id': user_id,
            'validation_type': 'rate_limiting'
        }

        from django.conf import settings
        from django.utils import timezone
        from datetime import timedelta

        # Get rate limit settings (with defaults)
        RATE_LIMIT_PER_RECIPIENT = getattr(
            settings, 'NOTIFICATION_RATE_LIMIT_PER_RECIPIENT', 10
        )  # per hour
        RATE_LIMIT_PER_TENANT = getattr(
            settings, 'NOTIFICATION_RATE_LIMIT_PER_TENANT', 100
        )  # per hour
        RATE_LIMIT_PER_USER = getattr(
            settings, 'NOTIFICATION_RATE_LIMIT_PER_USER', 20
        )  # per hour
        RATE_LIMIT_WINDOW = getattr(
            settings, 'NOTIFICATION_RATE_LIMIT_WINDOW', 3600
        )  # seconds (1 hour)

        details['rate_limit_per_recipient'] = RATE_LIMIT_PER_RECIPIENT
        details['rate_limit_per_tenant'] = RATE_LIMIT_PER_TENANT
        details['rate_limit_per_user'] = RATE_LIMIT_PER_USER
        details['rate_limit_window'] = RATE_LIMIT_WINDOW

        window_start = timezone.now() - timedelta(seconds=RATE_LIMIT_WINDOW)

        # Check rate limit per recipient (for EMAIL channel)
        if channel.upper() == 'EMAIL':
            recent_deliveries = EmailDelivery.objects.filter(
                to_email=recipient,
                created_at__gte=window_start
            ).count()

            if recent_deliveries >= RATE_LIMIT_PER_RECIPIENT:
                errors.append(
                    f"Rate limit exceeded for recipient '{recipient}'. "
                    f"Sent {recent_deliveries} emails in the last {RATE_LIMIT_WINDOW} seconds. "
                    f"Limit: {RATE_LIMIT_PER_RECIPIENT} per {RATE_LIMIT_WINDOW} seconds."
                )
                details['recipient_rate_limit_exceeded'] = True
            else:
                details['recipient_rate_limit_exceeded'] = False
                details['recipient_deliveries_count'] = recent_deliveries

            # Warn if approaching limit
            if recent_deliveries >= RATE_LIMIT_PER_RECIPIENT * 0.8:
                warnings.append(
                    f"Approaching rate limit for recipient '{recipient}'. "
                    f"Sent {recent_deliveries}/{RATE_LIMIT_PER_RECIPIENT} emails."
                )

        # Check rate limit per tenant
        if tenant_id:
            recent_deliveries = EmailDelivery.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=window_start
            ).count()

            if recent_deliveries >= RATE_LIMIT_PER_TENANT:
                errors.append(
                    f"Rate limit exceeded for tenant '{tenant_id}'. "
                    f"Sent {recent_deliveries} notifications in the last {RATE_LIMIT_WINDOW} seconds. "
                    f"Limit: {RATE_LIMIT_PER_TENANT} per {RATE_LIMIT_WINDOW} seconds."
                )
                details['tenant_rate_limit_exceeded'] = True
            else:
                details['tenant_rate_limit_exceeded'] = False
                details['tenant_deliveries_count'] = recent_deliveries

            # Warn if approaching limit
            if recent_deliveries >= RATE_LIMIT_PER_TENANT * 0.8:
                warnings.append(
                    f"Approaching rate limit for tenant '{tenant_id}'. "
                    f"Sent {recent_deliveries}/{RATE_LIMIT_PER_TENANT} notifications."
                )

        # Check rate limit per user
        if user_id:
            recent_deliveries = EmailDelivery.objects.filter(
                user_id=user_id,
                created_at__gte=window_start
            ).count()

            if recent_deliveries >= RATE_LIMIT_PER_USER:
                errors.append(
                    f"Rate limit exceeded for user '{user_id}'. "
                    f"Sent {recent_deliveries} notifications in the last {RATE_LIMIT_WINDOW} seconds. "
                    f"Limit: {RATE_LIMIT_PER_USER} per {RATE_LIMIT_WINDOW} seconds."
                )
                details['user_rate_limit_exceeded'] = True
            else:
                details['user_rate_limit_exceeded'] = False
                details['user_deliveries_count'] = recent_deliveries

            # Warn if approaching limit
            if recent_deliveries >= RATE_LIMIT_PER_USER * 0.8:
                warnings.append(
                    f"Approaching rate limit for user '{user_id}'. "
                    f"Sent {recent_deliveries}/{RATE_LIMIT_PER_USER} notifications."
                )

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_delivery_status(
        self,
        notification: EmailDelivery,
        new_status: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate delivery status transitions (PENDING → SENT/FAILED).

        Validates:
        - Status transition is valid
        - Status transition timing is appropriate
        - Required fields are set for the new status

        Args:
            notification: EmailDelivery instance
            new_status: Optional new status to validate transition to

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'notification_id': str(notification.id),
            'current_status': notification.status,
            'new_status': new_status,
            'validation_type': 'delivery_status'
        }

        # Define valid status transitions
        VALID_TRANSITIONS = {
            EmailDeliveryStatus.PENDING: [
                EmailDeliveryStatus.SENT,
                EmailDeliveryStatus.FAILED,
                EmailDeliveryStatus.DEFERRED
            ],
            EmailDeliveryStatus.SENT: [
                EmailDeliveryStatus.DELIVERED,
                EmailDeliveryStatus.BOUNCED,
                EmailDeliveryStatus.FAILED
            ],
            EmailDeliveryStatus.DEFERRED: [
                EmailDeliveryStatus.SENT,
                EmailDeliveryStatus.FAILED,
                EmailDeliveryStatus.PENDING
            ],
            EmailDeliveryStatus.DELIVERED: [],  # Final state
            EmailDeliveryStatus.BOUNCED: [],  # Final state
            EmailDeliveryStatus.FAILED: [
                EmailDeliveryStatus.PENDING  # Can retry
            ]
        }

        current_status = notification.status
        target_status = new_status or current_status

        # Validate current status is valid
        valid_statuses = [choice[0] for choice in EmailDeliveryStatus.choices]
        if current_status not in valid_statuses:
            errors.append(
                f"Invalid current status '{current_status}'. "
                f"Valid statuses are: {', '.join(valid_statuses)}"
            )
            details['current_status_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['current_status_valid'] = True

        # If new_status is provided, validate transition
        if new_status:
            if new_status not in valid_statuses:
                errors.append(
                    f"Invalid new status '{new_status}'. "
                    f"Valid statuses are: {', '.join(valid_statuses)}"
                )
                details['new_status_valid'] = False
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

            details['new_status_valid'] = True

            # Check if transition is valid
            if current_status == target_status:
                # No transition needed
                details['transition_valid'] = True
                details['transition_type'] = 'no_change'
            elif target_status in VALID_TRANSITIONS.get(current_status, []):
                details['transition_valid'] = True
                details['transition_type'] = 'valid'
            else:
                errors.append(
                    f"Invalid status transition from '{current_status}' to '{target_status}'. "
                    f"Valid transitions from '{current_status}' are: "
                    f"{', '.join(VALID_TRANSITIONS.get(current_status, []))}"
                )
                details['transition_valid'] = False
                details['transition_type'] = 'invalid'

            # Validate required fields for new status
            if target_status == EmailDeliveryStatus.SENT:
                if not notification.sent_at:
                    warnings.append(
                        "Status is SENT but sent_at timestamp is not set. "
                        "Consider calling mark_sent() method."
                    )
                    details['sent_at_set'] = False
                else:
                    details['sent_at_set'] = True

            elif target_status == EmailDeliveryStatus.DELIVERED:
                if not notification.delivered_at:
                    warnings.append(
                        "Status is DELIVERED but delivered_at timestamp is not set. "
                        "Consider calling mark_delivered() method."
                    )
                    details['delivered_at_set'] = False
                else:
                    details['delivered_at_set'] = True

            elif target_status in [EmailDeliveryStatus.FAILED, EmailDeliveryStatus.BOUNCED]:
                # Check failed_at first
                if not notification.failed_at:
                    warnings.append(
                        f"Status is {target_status} but failed_at timestamp is not set. "
                        "Consider calling mark_failed() or mark_bounced() method."
                    )
                    details['failed_at_set'] = False
                else:
                    details['failed_at_set'] = True

                # Check error_message second
                if not notification.error_message:
                    warnings.append(
                        f"Status is {target_status} but error_message is not set. "
                        "Consider providing an error message for debugging."
                    )
                    details['error_message_set'] = False
                else:
                    details['error_message_set'] = True

        # Validate retry logic
        if notification.status == EmailDeliveryStatus.FAILED:
            if notification.retry_count >= notification.max_retries:
                warnings.append(
                    f"Notification has exceeded max retries ({notification.max_retries}). "
                    f"Current retry count: {notification.retry_count}"
                )
                details['retry_limit_exceeded'] = True
            else:
                details['retry_limit_exceeded'] = False
                details['can_retry'] = notification.can_retry()

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_preference_structure(
        self,
        preferences: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate preference structure (valid preference format).

        Validates:
        - Preferences is a dictionary
        - Required fields are present
        - Channel preferences are valid (EMAIL, SMS, PUSH, IN_APP)
        - Email type preferences are valid
        - Preference values are of correct types
        - No unknown fields

        Args:
            preferences: Dictionary containing notification preferences

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'preference_structure',
            'preferences_provided': preferences is not None
        }

        # Validate preferences is provided
        if preferences is None:
            errors.append("Preferences must be provided")
            details['has_preferences'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['has_preferences'] = True

        # Validate preferences is a dictionary
        if not isinstance(preferences, dict):
            errors.append(
                f"Preferences must be a dictionary, got {type(preferences).__name__}"
            )
            details['is_dict'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['is_dict'] = True

        # Define valid channels
        VALID_CHANNELS = ['EMAIL', 'SMS', 'PUSH', 'IN_APP']

        # Define valid email types
        valid_email_types = [choice[0] for choice in EmailType.choices]

        # Validate channel preferences
        if 'channels' in preferences:
            channels = preferences['channels']
            if not isinstance(channels, dict):
                errors.append(
                    "Channel preferences must be a dictionary mapping channel names to boolean values"
                )
                details['channels_valid'] = False
            else:
                details['channels_valid'] = True
                for channel, enabled in channels.items():
                    if channel not in VALID_CHANNELS:
                        errors.append(
                            f"Invalid channel '{channel}' in preferences. "
                            f"Valid channels are: {', '.join(VALID_CHANNELS)}"
                        )
                    elif not isinstance(enabled, bool):
                        errors.append(
                            f"Channel preference '{channel}' must be a boolean, got {type(enabled).__name__}"
                        )
                details['channels'] = list(channels.keys())
        else:
            warnings.append("No channel preferences specified. Defaulting to EMAIL only.")
            details['channels'] = []

        # Validate email type preferences
        if 'email_types' in preferences:
            email_types = preferences['email_types']
            if not isinstance(email_types, dict):
                errors.append(
                    "Email type preferences must be a dictionary mapping email types to boolean values"
                )
                details['email_types_valid'] = False
            else:
                details['email_types_valid'] = True
                email_type_keys_list = []
                for email_type_key, enabled in email_types.items():
                    # Ensure email_type_key is a string (handle enum values and tuple keys from TextChoices)
                    # Django TextChoices enum members have .value attribute
                    if hasattr(email_type_key, 'value') and not isinstance(email_type_key, str):
                        # It's an enum, get the value
                        email_type = email_type_key.value
                    elif isinstance(email_type_key, tuple):
                        email_type = email_type_key[0] if len(email_type_key) > 0 else str(email_type_key)
                    else:
                        email_type = str(email_type_key)

                    # Store the normalized key for details
                    email_type_keys_list.append(email_type)

                    if email_type not in valid_email_types:
                        errors.append(
                            f"Invalid email type '{email_type}' in preferences. "
                            f"Valid email types are: {', '.join(valid_email_types)}"
                        )
                    elif not isinstance(enabled, bool):
                        errors.append(
                            f"Email type preference '{email_type}' must be a boolean, got {type(enabled).__name__}"
                        )
                details['email_types'] = email_type_keys_list
        else:
            warnings.append("No email type preferences specified. Defaulting to all email types enabled.")
            details['email_types'] = []

        # Validate opt_out flag (optional)
        if 'opt_out' in preferences:
            opt_out = preferences['opt_out']
            if not isinstance(opt_out, bool):
                errors.append(
                    f"opt_out preference must be a boolean, got {type(opt_out).__name__}"
                )
                details['opt_out_valid'] = False
            else:
                details['opt_out_valid'] = True
                details['opt_out'] = opt_out
                if opt_out:
                    warnings.append(
                        "User has opted out of all notifications. "
                        "This will override all other preference settings."
                    )
        else:
            details['opt_out'] = False

        # Validate frequency preferences (optional)
        if 'frequency' in preferences:
            frequency = preferences['frequency']
            valid_frequencies = ['IMMEDIATE', 'DAILY', 'WEEKLY', 'NEVER']
            if frequency not in valid_frequencies:
                errors.append(
                    f"Invalid frequency '{frequency}'. "
                    f"Valid frequencies are: {', '.join(valid_frequencies)}"
                )
                details['frequency_valid'] = False
            else:
                details['frequency_valid'] = True
                details['frequency'] = frequency
        else:
            details['frequency'] = 'IMMEDIATE'

        # Check for unknown fields (warn but don't error)
        known_fields = {'channels', 'email_types', 'opt_out', 'frequency'}
        unknown_fields = set(preferences.keys()) - known_fields
        if unknown_fields:
            warnings.append(
                f"Unknown preference fields found: {', '.join(unknown_fields)}. "
                f"These will be ignored."
            )
            details['unknown_fields'] = list(unknown_fields)
        else:
            details['unknown_fields'] = []

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_preference_update(
        self,
        user: User,
        preferences: Dict[str, Any],
        requesting_user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate preference update (user can update own preferences).

        Validates:
        - User is provided
        - User exists and is active
        - Requesting user can update preferences (must be the same user or admin)
        - Preference structure is valid
        - User has permission to update preferences

        Args:
            user: User whose preferences are being updated
            requesting_user: Optional user making the update request
            preferences: Dictionary containing notification preferences to update

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'preference_update',
            'user_id': str(user.id) if user else None,
            'requesting_user_id': str(requesting_user.id) if requesting_user else None
        }

        # Validate user is provided
        if not user:
            errors.append("User must be provided")
            details['has_user'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['has_user'] = True

        # Validate user exists (check if user has an ID and is saved)
        # Check both pk and id to handle different Django model states
        if not (hasattr(user, 'pk') and user.pk) and not (hasattr(user, 'id') and user.id):
            errors.append("User must be saved before updating preferences")
            details['user_saved'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['user_saved'] = True

        # Validate user is active
        if hasattr(user, 'status'):
            from hub.apps.users.models import UserStatus
            if user.status != UserStatus.ACTIVE:
                errors.append(
                    f"Cannot update preferences for user with status '{user.status}'. "
                    f"User must be ACTIVE."
                )
                details['user_active'] = False
            else:
                details['user_active'] = True
        else:
            # If status field doesn't exist, assume active
            details['user_active'] = True

        # Validate requesting user can update preferences
        if requesting_user:
            # Check if requesting user is the same as the user being updated
            if str(requesting_user.id) == str(user.id):
                details['can_update'] = True
                details['update_reason'] = 'self_update'
            # Check if requesting user is platform admin
            elif hasattr(requesting_user, 'is_platform_admin') and requesting_user.is_platform_admin:
                details['can_update'] = True
                details['update_reason'] = 'admin_update'
            # Check if requesting user is in the same tenant and has admin privileges
            elif (
                hasattr(requesting_user, 'tenant_id') and
                hasattr(user, 'tenant_id') and
                requesting_user.tenant_id == user.tenant_id
            ):
                # Check if requesting user has admin permissions
                # Note: User model extends PermissionsMixin which provides is_staff
                # Use getattr with default False to be safe
                is_admin = (
                    getattr(requesting_user, 'is_staff', False) or
                    getattr(requesting_user, 'is_tenant_admin', False)
                )
                if is_admin:
                    details['can_update'] = True
                    details['update_reason'] = 'tenant_admin_update'
                else:
                    errors.append(
                        f"User '{requesting_user.id}' does not have permission to update "
                        f"preferences for user '{user.id}'. Only the user themselves, "
                        f"platform admins, or tenant admins can update preferences."
                    )
                    details['can_update'] = False
            else:
                errors.append(
                    f"User '{requesting_user.id}' does not have permission to update "
                    f"preferences for user '{user.id}'. Users can only update their own preferences, "
                    f"or admins can update preferences for users in their tenant."
                )
                details['can_update'] = False
        else:
            # If no requesting user provided, assume self-update (but warn)
            warnings.append(
                "No requesting user provided. Assuming self-update. "
                "In production, always provide requesting_user for audit purposes."
            )
            details['can_update'] = True
            details['update_reason'] = 'assumed_self_update'

        # Validate preference structure
        structure_result = self.validate_preference_structure(preferences)
        if not structure_result.is_valid:
            errors.extend(structure_result.errors)
            details['preference_structure_valid'] = False
        else:
            details['preference_structure_valid'] = True
            warnings.extend(structure_result.warnings)

        # Validate tenant context consistency
        if self.tenant_id and hasattr(user, 'tenant_id') and user.tenant_id:
            if str(user.tenant_id) != str(self.tenant_id):
                warnings.append(
                    f"User tenant ({user.tenant_id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True
        else:
            details['tenant_match'] = None

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_preference_enforcement(
        self,
        user: User,
        email_type: str,
        channel: str = 'EMAIL',
        preferences: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate preference enforcement (preferences enforced correctly).

        Validates:
        - User preferences are checked before sending notification
        - Opt-out preferences are respected
        - Channel preferences are respected
        - Email type preferences are respected
        - Frequency preferences are considered (warnings only)

        Args:
            user: User receiving the notification
            email_type: Type of email being sent
            channel: Delivery channel (EMAIL, SMS, PUSH, IN_APP)
            preferences: Optional preferences dictionary (if not provided, will attempt to load from user)

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'preference_enforcement',
            'user_id': str(user.id) if user else None,
            'email_type': email_type,
            'channel': channel
        }

        # Validate user is provided
        if not user:
            errors.append("User must be provided")
            details['has_user'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['has_user'] = True

        # Validate email type - ensure it's a string
        # Handle Django TextChoices enum values
        if hasattr(email_type, 'value') and not isinstance(email_type, str):
            # It's an enum, get the value
            email_type = getattr(email_type, 'value', str(email_type))  # type: ignore[attr-defined]
        elif isinstance(email_type, tuple):
            # It's a tuple (choice value, label)
            email_type = email_type[0] if len(email_type) > 0 else str(email_type)
        else:
            email_type = str(email_type)

        valid_email_types = [choice[0] for choice in EmailType.choices]
        if email_type not in valid_email_types:
            errors.append(
                f"Invalid email type '{email_type}'. "
                f"Valid email types are: {', '.join(valid_email_types)}"
            )
            details['email_type_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['email_type_valid'] = True

        # Validate channel
        VALID_CHANNELS = ['EMAIL', 'SMS', 'PUSH', 'IN_APP']
        channel_upper = channel.upper().strip()
        if channel_upper not in VALID_CHANNELS:
            errors.append(
                f"Invalid channel '{channel}'. "
                f"Valid channels are: {', '.join(VALID_CHANNELS)}"
            )
            details['channel_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['channel_valid'] = True

        # Load preferences if not provided
        if preferences is None:
            # Try to get preferences from user model
            # This assumes preferences are stored in a field like user.notification_preferences
            # or user.preferences['notifications']
            if hasattr(user, 'notification_preferences'):
                preferences = user.notification_preferences
            elif hasattr(user, 'preferences') and isinstance(user.preferences, dict):
                preferences = user.preferences.get('notifications')
            else:
                # Default preferences if none found
                preferences = {
                    'channels': {'EMAIL': True},
                    'email_types': {},
                    'opt_out': False,
                    'frequency': 'IMMEDIATE'
                }
                warnings.append(
                    "No preferences found for user. Using default preferences. "
                    "Consider setting up user preferences."
                )
                details['preferences_loaded'] = False
        else:
            details['preferences_loaded'] = True

        # Ensure preferences is a dict (type guard)
        if preferences is None:
            preferences = {
                'channels': {'EMAIL': True},
                'email_types': {},
                'opt_out': False,
                'frequency': 'IMMEDIATE'
            }
            warnings.append(
                "Preferences were None, using default preferences."
            )

        # Validate preference structure first
        structure_result = self.validate_preference_structure(preferences)
        if not structure_result.is_valid:
            errors.extend(structure_result.errors)
            details['preference_structure_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['preference_structure_valid'] = True
        warnings.extend(structure_result.warnings)

        # Check opt-out preference
        opt_out = preferences.get('opt_out', False)
        if opt_out:
            errors.append(
                f"User '{user.id}' has opted out of all notifications. "
                f"Cannot send {email_type} notification via {channel} channel."
            )
            details['opt_out_enforced'] = True
            details['can_send'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['opt_out_enforced'] = False

        # Check channel preferences
        channels = preferences.get('channels', {})
        if channels:
            channel_enabled = channels.get(channel_upper, True)  # Default to enabled if not specified
            if not channel_enabled:
                errors.append(
                    f"User '{user.id}' has disabled {channel_upper} channel notifications. "
                    f"Cannot send {email_type} notification via {channel_upper} channel."
                )
                details['channel_enabled'] = False
                details['can_send'] = False
            else:
                details['channel_enabled'] = True
                details['can_send'] = True
        else:
            # If no channel preferences, default to EMAIL only
            if channel_upper != 'EMAIL':
                warnings.append(
                    f"No channel preferences specified. Defaulting to EMAIL only. "
                    f"Channel {channel_upper} may not be enabled."
                )
            details['channel_enabled'] = True
            details['can_send'] = True

        # Check email type preferences
        email_types = preferences.get('email_types', {})
        if email_types:
            # Try to get the preference, handling both string keys and enum keys
            email_type_enabled = None
            for key, value in email_types.items():
                # Normalize key to string for comparison
                if hasattr(key, 'value'):
                    # It's an enum, get the value
                    key_str = key.value
                elif isinstance(key, tuple):
                    key_str = str(key[0]) if len(key) > 0 else str(key)
                else:
                    key_str = str(key)
                if key_str.lower() == email_type.lower():
                    email_type_enabled = value
                    break

            # Default to enabled if not specified
            if email_type_enabled is None:
                email_type_enabled = True

            if not email_type_enabled:
                errors.append(
                    f"User '{user.id}' has disabled {email_type} email notifications. "
                    f"Cannot send {email_type} notification."
                )
                details['email_type_enabled'] = False
                details['can_send'] = False
            else:
                details['email_type_enabled'] = True
                # Only set can_send to True if it wasn't already set to False
                if 'can_send' not in details or details.get('can_send', True):
                    details['can_send'] = True
        else:
            # If no email type preferences, default to all enabled
            details['email_type_enabled'] = True
            # Only set can_send to True if it wasn't already set to False
            if 'can_send' not in details or details.get('can_send', True):
                details['can_send'] = True

        # Check frequency preferences (warnings only, not blocking)
        frequency = preferences.get('frequency', 'IMMEDIATE')
        if frequency == 'NEVER':
            warnings.append(
                f"User '{user.id}' has frequency preference set to NEVER. "
                f"Consider respecting this preference and not sending immediate notifications."
            )
            details['frequency_respected'] = False
        else:
            details['frequency_respected'] = True
        details['frequency'] = frequency

        # Final check: can send notification
        # Ensure can_send is set even if there were early returns
        if 'can_send' not in details:
            details['can_send'] = True

        # Update can_send based on email type enabled status (if not already False)
        if details.get('email_type_enabled', True) is False:
            details['can_send'] = False

        # Final validation: can_send must be True for valid result
        # Only update if not already explicitly set to False
        if details.get('can_send', True):
            details['can_send'] = details.get('email_type_enabled', True)

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

