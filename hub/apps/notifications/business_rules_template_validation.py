"""
Notifications Template Validation Business Rules.

Extracted from business_rules.py — template-specific validation methods
for the NotificationsBusinessRules class.
"""

import logging
from typing import Any

from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.notifications.business_rules import NotificationsBusinessRules

logger = logging.getLogger(__name__)


class NotificationsTemplateValidationRules(NotificationsBusinessRules):
    """Template validation rules — extracted from NotificationsBusinessRules."""

    def validate_template_structure(self, template_name: str) -> ValidationResult:
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
        details = {"template": template_name, "validation_type": "template_structure"}

        # Basic template validation first
        basic_result = self._validate_template_basic(template_name)
        if not basic_result.is_valid:
            return basic_result

        # Try to load template
        try:
            from django.template.loader import get_template

            template = get_template(template_name)
            details["template_exists"] = True
            details["template_loaded"] = True
        except Exception as e:
            errors.append(f"Template '{template_name}' cannot be loaded: {e!s}")
            details["template_exists"] = False
            details["template_loaded"] = False
            details["load_error"] = str(e)
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        # Read template source to check structure
        try:
            template_source = template.source
            details["has_source"] = True

            # Check if template extends base.html
            if "{% extends" in template_source:
                if (
                    "notifications/emails/base.html" in template_source
                    or "base.html" in template_source
                ):
                    details["extends_base"] = True
                else:
                    warnings.append(
                        f"Template '{template_name}' extends a template but may not extend base.html. "
                        "Expected: '{% extends \"notifications/emails/base.html\" %}'"
                    )
                    details["extends_base"] = False
            else:
                warnings.append(
                    f"Template '{template_name}' does not extend base.html. "
                    f"All email templates should extend 'notifications/emails/base.html'"
                )
                details["extends_base"] = False

            # Check for content block
            if "{% block content" in template_source:
                details["has_content_block"] = True
            else:
                errors.append(
                    f"Template '{template_name}' must have a '{{% block content %}}' block"
                )
                details["has_content_block"] = False

            # Check for title block (optional but recommended)
            if "{% block title" in template_source:
                details["has_title_block"] = True
            else:
                warnings.append(
                    f"Template '{template_name}' should have a '{{% block title %}}' block for email subject"
                )
                details["has_title_block"] = False

            # Validate Django template syntax (basic check)
            try:
                from django.template import Template, TemplateSyntaxError

                Template(template_source)
                details["syntax_valid"] = True
            except TemplateSyntaxError as e:
                errors.append(f"Template '{template_name}' has syntax errors: {e!s}")
                details["syntax_valid"] = False
                details["syntax_error"] = str(e)
            except Exception as e:
                warnings.append(f"Could not validate template syntax: {e!s}")
                details["syntax_valid"] = None
                details["syntax_error"] = str(e)

        except Exception as e:
            warnings.append(f"Could not read template source: {e!s}")
            details["has_source"] = False
            details["source_error"] = str(e)

        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def validate_template_variables(
        self, template_name: str, context: Dict[str, Any]
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
            "template": template_name,
            "validation_type": "template_variables",
            "context_keys": list(context.keys()) if context else [],
        }

        # Basic template validation first
        basic_result = self._validate_template_basic(template_name)
        if not basic_result.is_valid:
            return basic_result

        # Try to render template with context to check for undefined variables
        try:
            from django.template.loader import render_to_string

            rendered = render_to_string(template_name, context)
            details["rendered_successfully"] = True
            details["rendered_length"] = len(rendered)
        except Exception as e:
            # Check if error is due to missing variables
            error_str = str(e).lower()
            if "variable" in error_str or "undefined" in error_str:
                errors.append(f"Template '{template_name}' has undefined variables: {e!s}")
                details["rendered_successfully"] = False
                details["render_error"] = str(e)
                details["error_type"] = "undefined_variable"
            else:
                errors.append(f"Template '{template_name}' rendering failed: {e!s}")
                details["rendered_successfully"] = False
                details["render_error"] = str(e)
                details["error_type"] = "render_error"

            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        # Extract variables from template source
        try:
            from django.template.loader import get_template

            template = get_template(template_name)
            template_source = template.source

            # Find all variable references in template (basic regex)
            import re

            # Match {{ variable }} and {{ variable.attribute }}
            variable_pattern = r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}"
            variables_in_template = set(re.findall(variable_pattern, template_source))
            details["variables_in_template"] = list(variables_in_template)

            # Check for required variables (common ones)
            common_required = ["user", "tenant"]
            missing_required = []
            for var in common_required:
                if var in variables_in_template and var not in context:
                    missing_required.append(var)

            if missing_required:
                warnings.append(
                    f"Template '{template_name}' uses variables that are not in context: {', '.join(missing_required)}"
                )
                details["missing_variables"] = missing_required
            else:
                details["missing_variables"] = []

            # Check for variables with filters (should be safe)
            filter_pattern = r"\{\{\s*[^|]+\|[^}]+\s*\}\}"
            variables_with_filters = re.findall(filter_pattern, template_source)
            details["variables_with_filters"] = len(variables_with_filters)

            details["variables_validated"] = True

        except Exception as e:
            warnings.append(f"Could not extract variables from template: {e!s}")
            details["variables_validated"] = False
            details["variable_extraction_error"] = str(e)

        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def validate_template_content(
        self, template_name: str, context: Dict[str, Any]
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
        details = {"template": template_name, "validation_type": "template_content"}

        # Basic template validation first
        basic_result = self._validate_template_basic(template_name)
        if not basic_result.is_valid:
            return basic_result

        # Render template to check content
        try:
            from django.template.loader import render_to_string

            rendered = render_to_string(template_name, context)
            details["rendered_successfully"] = True
            details["rendered_length"] = len(rendered)
        except Exception as e:
            errors.append(f"Template '{template_name}' rendering failed: {e!s}")
            details["rendered_successfully"] = False
            details["render_error"] = str(e)
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        # Validate content length
        MAX_CONTENT_LENGTH = 500000  # 500KB max for email content
        MIN_CONTENT_LENGTH = 50  # Minimum reasonable content length

        if len(rendered) > MAX_CONTENT_LENGTH:
            errors.append(
                f"Template '{template_name}' renders to content that is too long ({len(rendered)} bytes). "
                f"Maximum allowed: {MAX_CONTENT_LENGTH} bytes"
            )
            details["content_length_valid"] = False
        elif len(rendered) < MIN_CONTENT_LENGTH:
            warnings.append(
                f"Template '{template_name}' renders to very short content ({len(rendered)} bytes). "
                f"Minimum recommended: {MIN_CONTENT_LENGTH} bytes"
            )
            details["content_length_valid"] = True
            details["content_too_short"] = True
        else:
            details["content_length_valid"] = True
            details["content_too_short"] = False

        details["content_length"] = len(rendered)
        details["max_content_length"] = MAX_CONTENT_LENGTH
        details["min_content_length"] = MIN_CONTENT_LENGTH

        # Check for prohibited content patterns
        prohibited_patterns = [
            (r"<iframe[^>]*>", "iframe tags are not allowed in emails"),
            (r"<object[^>]*>", "object tags are not allowed in emails"),
            (r"<embed[^>]*>", "embed tags are not allowed in emails"),
            (r"<form[^>]*>", "form tags are not allowed in emails"),
        ]

        found_prohibited = []
        import re

        for pattern, description in prohibited_patterns:
            if re.search(pattern, rendered, re.IGNORECASE):
                errors.append(
                    f"Template '{template_name}' contains prohibited content: {description}"
                )
                found_prohibited.append(description)

        details["prohibited_content_found"] = found_prohibited
        details["prohibited_content_valid"] = len(found_prohibited) == 0

        # Check for empty content blocks
        if "{% block content" in rendered or "block content" in rendered.lower():
            # Check if content block is effectively empty
            content_match = re.search(r'<div class="content">(.*?)</div>', rendered, re.DOTALL)
            if content_match:
                content_text = content_match.group(1)
                # Remove HTML tags and whitespace
                text_only = re.sub(r"<[^>]+>", "", content_text).strip()
                if len(text_only) < 10:
                    warnings.append(
                        f"Template '{template_name}' content block appears to be empty or very short"
                    )
                    details["content_block_empty"] = True
                else:
                    details["content_block_empty"] = False
            else:
                details["content_block_empty"] = None
        else:
            details["content_block_empty"] = None

        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def validate_template_security(
        self, template_name: str, context: Dict[str, Any]
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
        details = {"template": template_name, "validation_type": "template_security"}

        # Basic template validation first
        basic_result = self._validate_template_basic(template_name)
        if not basic_result.is_valid:
            return basic_result

        # Render template to check security
        try:
            from django.template.loader import render_to_string

            rendered = render_to_string(template_name, context)
            details["rendered_successfully"] = True
            details["rendered_length"] = len(rendered)
        except Exception as e:
            errors.append(f"Template '{template_name}' rendering failed: {e!s}")
            details["rendered_successfully"] = False
            details["render_error"] = str(e)
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        import re

        # Check for script tags (should be escaped by Django)
        script_patterns = [
            (r"<script[^>]*>.*?</script>", "script tags"),
            (r"<script[^>]*>", "opening script tags"),
        ]

        found_scripts = []
        for pattern, description in script_patterns:
            matches = re.findall(pattern, rendered, re.IGNORECASE | re.DOTALL)
            if matches:
                # Check if they're escaped (should contain &lt; or &#60;)
                unescaped = [m for m in matches if not ("&lt;" in m or "&#60;" in m)]
                if unescaped:
                    errors.append(
                        f"Template '{template_name}' contains unescaped {description} in rendered content. "
                        f"This is a security vulnerability."
                    )
                    found_scripts.extend(unescaped)
                else:
                    # Escaped scripts are OK (Django auto-escaping working)
                    details["scripts_escaped"] = True

        details["script_tags_found"] = len(found_scripts)
        details["script_tags_valid"] = len(found_scripts) == 0

        # Check for javascript: URLs
        javascript_url_pattern = r'javascript:\s*[^"\'<>]*'
        javascript_urls = re.findall(javascript_url_pattern, rendered, re.IGNORECASE)
        if javascript_urls:
            errors.append(
                f"Template '{template_name}' contains javascript: URLs which are a security risk"
            )
            details["javascript_urls_found"] = javascript_urls
            details["javascript_urls_valid"] = False
        else:
            details["javascript_urls_found"] = []
            details["javascript_urls_valid"] = True

        # Check for on* event handlers (onclick, onerror, etc.)
        event_handler_pattern = r'\bon\w+\s*=\s*["\'][^"\']*["\']'
        event_handlers = re.findall(event_handler_pattern, rendered, re.IGNORECASE)
        if event_handlers:
            warnings.append(
                f"Template '{template_name}' contains event handlers (onclick, onerror, etc.) "
                f"which may be a security concern"
            )
            details["event_handlers_found"] = event_handlers
            details["event_handlers_valid"] = False
        else:
            details["event_handlers_found"] = []
            details["event_handlers_valid"] = True

        # Check for data: URLs (may be used for XSS)
        data_url_pattern = r'data:\s*[^"\'<>]*'
        data_urls = re.findall(data_url_pattern, rendered, re.IGNORECASE)
        if data_urls:
            warnings.append(
                f"Template '{template_name}' contains data: URLs which may be a security concern"
            )
            details["data_urls_found"] = data_urls
            details["data_urls_valid"] = False
        else:
            details["data_urls_found"] = []
            details["data_urls_valid"] = True

        # Check if Django auto-escaping is working (look for escaped HTML entities)
        # If we find &lt; or &#60; in rendered content, escaping is likely working
        escaped_patterns = [r"&lt;", r"&#60;", r"&gt;", r"&#62;", r"&amp;", r"&#38;"]
        escaped_found = any(re.search(pattern, rendered) for pattern in escaped_patterns)
        details["auto_escaping_detected"] = escaped_found

        if not escaped_found and ("<" in rendered or ">" in rendered):
            warnings.append(
                f"Template '{template_name}' may not be using Django auto-escaping. "
                "Ensure variables use {{ variable }} not {{ variable|safe }} unless necessary"
            )

        details["security_validated"] = len(errors) == 0
        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )
