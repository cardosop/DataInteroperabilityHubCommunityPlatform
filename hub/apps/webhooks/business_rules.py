"""
Webhooks Business Rules

Comprehensive business rules validation for webhook operations, including:
- Webhook subscription validation
- Webhook delivery validation
- Webhook payload validation (size, structure, content)
- Tenant and user context validation

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import json
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING, Union
from dataclasses import dataclass
from django.conf import settings

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookStatus,
    WebhookEventType,
    DeliveryStatus,
)
from hub.apps.users.models import User

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)

# Maximum payload size in bytes (1MB default, configurable via settings)
MAX_PAYLOAD_SIZE = getattr(settings, 'WEBHOOK_MAX_PAYLOAD_SIZE', 1024 * 1024)  # 1MB

# Required payload fields
REQUIRED_PAYLOAD_FIELDS = ["event_type", "resource_type", "resource_id", "timestamp", "data"]


@dataclass
class WebhookRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for webhook business rules.

    Adds webhook-specific context:
    - webhook_subscription: The webhook subscription being validated
    - delivery: Optional webhook delivery instance
    - tenant: Optional tenant instance for validation
    - user: Optional user instance for permission validation
    """
    webhook_subscription: Optional[Webhook] = None
    delivery: Optional[WebhookDelivery] = None
    tenant: Optional[Any] = None  # Using Any to avoid circular import
    user: Optional[User] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        # Add webhook-specific fields
        base_dict.update({
            'webhook_id': str(self.webhook_subscription.id) if self.webhook_subscription else None,
            'webhook_name': self.webhook_subscription.name if self.webhook_subscription else None,
            'webhook_status': self.webhook_subscription.status if self.webhook_subscription else None,
            'webhook_url': self.webhook_subscription.url if self.webhook_subscription else None,
            'delivery_id': str(self.delivery.id) if self.delivery else None,
            'delivery_status': self.delivery.status if self.delivery else None,
            'delivery_event_type': self.delivery.event_type if self.delivery else None,
        })
        # Add tenant and user IDs from objects if provided
        if self.tenant:
            base_dict['tenant_id_from_object'] = str(self.tenant.id)
        if self.user:
            base_dict['user_id_from_object'] = str(self.user.id)
        return base_dict


@register_rule(
    rule_name="webhooks_validation",
    description="Validates webhook subscriptions, deliveries, and tenant context",
    tags=["webhooks", "validation", "subscription", "delivery"],
    priority=10,

    openspec_ref="specs/webhooks-business-rules/spec.md",
)
class WebhooksBusinessRules(BusinessRules):
    """
    Business rules validator for webhook operations.

    Extends BusinessRules base class with webhook-specific validation:
    - Webhook subscription validation
    - Webhook delivery validation
    - Tenant context consistency
    - User permissions and access validation
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "WebhooksBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all webhook validation checks.
        It can be called with a WebhookRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        webhook_subscription, delivery, tenant, and user from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - webhook_subscription: Webhook instance (optional)
                - delivery: WebhookDelivery instance (optional)
                - tenant: Optional tenant instance
                - user: Optional user instance
                - validation_type: Optional validation type filter
                    ('webhook_subscription', 'delivery', 'tenant_context', 'permissions', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract webhook_subscription, delivery, tenant, and user from context or kwargs
        if isinstance(context, WebhookRuleExecutionContext):
            webhook_subscription = context.webhook_subscription
            delivery = context.delivery
            tenant = context.tenant
            user = context.user
        else:
            # Try to get from kwargs first
            webhook_subscription = kwargs.get('webhook_subscription')
            delivery = kwargs.get('delivery')
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')

            # If not in kwargs, try to get from context.metadata or context.resource
            if context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                webhook_subscription = webhook_subscription or context.metadata.get('webhook_subscription')
                delivery = delivery or context.metadata.get('delivery')
                tenant = tenant or context.metadata.get('tenant')
                user = user or context.metadata.get('user')

            # Also check context.resource
            if not webhook_subscription and context and hasattr(context, 'resource'):
                if isinstance(context.resource, Webhook):
                    webhook_subscription = context.resource
                elif isinstance(context.resource, WebhookDelivery):
                    delivery = context.resource
                    webhook_subscription = delivery.webhook if delivery else None

        # Determine what to validate based on what's provided
        validation_type = kwargs.get('validation_type', 'all')

        # Initialize result
        result = ValidationResult(is_valid=True)
        result.details['webhooks_validation'] = 'webhooks'

        # Track what was validated
        validated_items = []

        # Validate webhook subscription if provided
        if webhook_subscription and validation_type in ('webhook_subscription', 'all'):
            webhook_result = self._validate_webhook_subscription(webhook_subscription, tenant, user)
            result = result.combine(webhook_result)
            validated_items.append('webhook_subscription')

        # Validate delivery if provided
        if delivery and validation_type in ('delivery', 'all'):
            delivery_result = self._validate_delivery(delivery, tenant, user)
            result = result.combine(delivery_result)
            validated_items.append('delivery')

        # Validate payload if provided
        payload = kwargs.get('payload')
        if payload and validation_type in ('payload', 'all'):
            payload_result = self._validate_payload(payload, delivery)
            result = result.combine(payload_result)
            validated_items.append('payload')

        # Validate tenant context if provided
        if tenant and validation_type in ('tenant_context', 'all'):
            tenant_result = self._validate_tenant_context(webhook_subscription, delivery, tenant)
            result = result.combine(tenant_result)
            validated_items.append('tenant_context')

        # Validate permissions if user provided
        if user and validation_type in ('permissions', 'all'):
            permissions_result = self._validate_permissions(webhook_subscription, delivery, user)
            result = result.combine(permissions_result)
            validated_items.append('permissions')

        # If nothing was validated, add a warning
        if not validated_items:
            result.warnings.append(
                "No webhook subscription or delivery provided for validation. "
                "Provide webhook_subscription, delivery, tenant, or user in kwargs or context."
            )

        result.details['validated_items'] = validated_items
        return result

    def _validate_webhook_subscription(
        self,
        webhook: Webhook,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Comprehensive webhook subscription validation including:
        - Subscription URL validation (valid URL, accessible endpoint)
        - Subscription event type validation (valid event types)
        - Subscription filter validation (valid filter expressions via event_types)
        - Subscription security validation (authentication, signature)

        Args:
            webhook: Webhook instance to validate
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with comprehensive validation status and details
        """
        errors = []
        warnings = []
        details = {
            'webhook_subscription_validation': 'webhook_subscription',
            'validation_checks': {}
        }

        # Validate webhook is not None
        if webhook is None:
            errors.append("Webhook subscription cannot be None")
            details['webhook_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['webhook_id'] = str(webhook.id)
        details['webhook_name'] = webhook.name
        details['webhook_status'] = webhook.status

        # Validate webhook has required fields
        if not webhook.name:
            errors.append("Webhook subscription must have a name")
            details['name_valid'] = False
        else:
            details['name_valid'] = True

        # 1. URL validation (valid URL, accessible endpoint)
        url_result = self._validate_subscription_url(webhook)
        errors.extend(url_result.errors)
        warnings.extend(url_result.warnings)
        details['validation_checks']['url'] = url_result.details

        # 2. Event type validation (valid event types)
        event_type_result = self._validate_subscription_event_types(webhook)
        errors.extend(event_type_result.errors)
        warnings.extend(event_type_result.warnings)
        details['validation_checks']['event_types'] = event_type_result.details

        # 3. Filter validation (valid filter expressions via event_types)
        filter_result = self._validate_subscription_filters(webhook)
        errors.extend(filter_result.errors)
        warnings.extend(filter_result.warnings)
        details['validation_checks']['filters'] = filter_result.details

        # 4. Security validation (authentication, signature)
        security_result = self._validate_subscription_security(webhook)
        errors.extend(security_result.errors)
        warnings.extend(security_result.warnings)
        details['validation_checks']['security'] = security_result.details

        # Validate status
        if webhook.status not in [choice[0] for choice in WebhookStatus.choices]:
            errors.append(f"Invalid webhook status: {webhook.status}")
            details['status_valid'] = False
        else:
            details['status_valid'] = True

        # Validate max_retries
        if webhook.max_retries < 0:
            errors.append("Webhook max_retries must be non-negative")
            details['max_retries_valid'] = False
        else:
            details['max_retries_valid'] = True

        # Validate retry_intervals
        if webhook.retry_intervals:
            if not isinstance(webhook.retry_intervals, list):
                errors.append("Webhook retry_intervals must be a list")
                details['retry_intervals_valid'] = False
            else:
                retry_intervals_valid = True
                for interval in webhook.retry_intervals:
                    if not isinstance(interval, (int, float)) or interval < 0:
                        errors.append(f"Webhook retry interval must be a non-negative number: {interval}")
                        retry_intervals_valid = False
                details['retry_intervals_valid'] = retry_intervals_valid
        else:
            details['retry_intervals_valid'] = True

        # Validate tenant consistency if tenant provided
        if tenant:
            if webhook.tenant_id != tenant.id:
                errors.append(
                    f"Webhook tenant_id ({webhook.tenant_id}) does not match provided tenant ({tenant.id})"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True

        # Validate user permissions if user provided
        if user:
            # Check if user belongs to the same tenant as webhook
            if user.tenant_id != webhook.tenant_id:
                warnings.append(
                    f"User ({user.id}) belongs to different tenant ({user.tenant_id}) "
                    f"than webhook ({webhook.tenant_id})"
                )
                details['user_tenant_match'] = False
            else:
                details['user_tenant_match'] = True

        details['webhook_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_subscription_url(
        self,
        webhook: Webhook
    ) -> ValidationResult:
        """
        Validate subscription URL: valid URL format and accessible endpoint.

        Args:
            webhook: Webhook instance

        Returns:
            ValidationResult with URL validation status
        """
        errors = []
        warnings = []
        details = {
            'url_validation': 'subscription_url',
            'url_format_valid': False,
            'url_accessible': False
        }

        if not webhook.url:
            errors.append("Webhook subscription must have a URL")
            details['url_format_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['url'] = webhook.url

        # Validate URL format
        try:
            from django.core.validators import URLValidator
            validator = URLValidator()
            validator(webhook.url)
            details['url_format_valid'] = True
        except Exception as e:
            errors.append(f"Webhook subscription URL is invalid: {str(e)}")
            details['url_format_valid'] = False
            details['url_format_error'] = str(e)
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate URL scheme (should be HTTPS in production)
        from urllib.parse import urlparse
        parsed_url = urlparse(webhook.url)
        if parsed_url.scheme not in ['http', 'https']:
            errors.append(f"Webhook URL must use http or https scheme, got: {parsed_url.scheme}")
            details['url_scheme_valid'] = False
        else:
            details['url_scheme_valid'] = True
            details['url_scheme'] = parsed_url.scheme
            if parsed_url.scheme == 'http':
                warnings.append(
                    "Webhook URL uses HTTP instead of HTTPS. "
                    "HTTPS is recommended for production environments."
                )

        # Test URL accessibility (HEAD request with timeout)
        try:
            import httpx
            with httpx.Client(timeout=5.0, follow_redirects=True) as client:
                try:
                    response = client.head(webhook.url)
                    details['url_accessible'] = response.status_code < 500
                    details['http_status_code'] = response.status_code
                    if response.status_code >= 500:
                        errors.append(
                            f"Webhook URL returned error status {response.status_code}. "
                            f"Endpoint may not be accessible."
                        )
                    elif response.status_code == 404:
                        warnings.append(
                            f"Webhook URL returned 404. Endpoint may not exist or may require authentication."
                        )
                    elif response.status_code == 401 or response.status_code == 403:
                        warnings.append(
                            f"Webhook URL returned {response.status_code}. "
                            f"Endpoint requires authentication (this is expected for webhook endpoints)."
                        )
                except httpx.TimeoutException:
                    warnings.append(
                        "Webhook URL accessibility check timed out. "
                        "Endpoint may be slow or unreachable."
                    )
                    details['url_accessible'] = False
                    details['accessibility_timeout'] = True
                except httpx.ConnectError:
                    warnings.append(
                        "Could not connect to webhook URL. "
                        "Endpoint may be unreachable or firewall may be blocking connections."
                    )
                    details['url_accessible'] = False
                    details['connectivity_error'] = True
                except Exception as e:
                    warnings.append(f"Webhook URL accessibility check failed: {str(e)}")
                    details['url_accessible'] = False
                    details['accessibility_error'] = str(e)
        except ImportError:
            warnings.append(
                "httpx not available - URL accessibility check skipped. "
                "Install httpx to enable accessibility validation."
            )
            details['url_accessible'] = None
            details['accessibility_check_skipped'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_subscription_event_types(
        self,
        webhook: Webhook
    ) -> ValidationResult:
        """
        Validate subscription event types: valid event types.

        Args:
            webhook: Webhook instance

        Returns:
            ValidationResult with event type validation status
        """
        errors = []
        warnings = []
        details = {
            'event_type_validation': 'subscription_event_types',
            'event_types_valid': False,
            'event_types_count': 0
        }

        if not webhook.event_types:
            errors.append("Webhook subscription must have at least one event type")
            details['event_types_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['event_types_count'] = len(webhook.event_types)
        details['event_types'] = webhook.event_types

        # Get valid event types
        valid_event_types = [choice[0] for choice in WebhookEventType.choices]
        details['valid_event_types_count'] = len(valid_event_types)

        # Validate each event type
        invalid_event_types = []
        for event_type in webhook.event_types:
            # Normalize event type (handle tuples, enums, strings)
            if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
                event_type_value = event_type[0]
            elif isinstance(event_type, WebhookEventType):
                event_type_value = getattr(event_type, 'value', str(event_type))
            else:
                event_type_value = str(event_type)

            if event_type_value not in valid_event_types:
                invalid_event_types.append(event_type_value)
                errors.append(f"Invalid event type: {event_type_value}")

        if invalid_event_types:
            details['invalid_event_types'] = invalid_event_types
            details['event_types_valid'] = False
        else:
            details['event_types_valid'] = True

        # Check for duplicate event types
        normalized_types = []
        for event_type in webhook.event_types:
            if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
                normalized_types.append(event_type[0])
            elif isinstance(event_type, WebhookEventType):
                normalized_types.append(getattr(event_type, 'value', str(event_type)))
            else:
                normalized_types.append(str(event_type))

        if len(normalized_types) != len(set(normalized_types)):
            duplicates = [t for t in normalized_types if normalized_types.count(t) > 1]
            warnings.append(f"Duplicate event types found: {set(duplicates)}")
            details['has_duplicates'] = True
            details['duplicate_event_types'] = list(set(duplicates))
        else:
            details['has_duplicates'] = False

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_subscription_filters(
        self,
        webhook: Webhook
    ) -> ValidationResult:
        """
        Validate subscription filters: valid filter expressions via event_types.

        Event types act as filters - webhooks only receive events matching subscribed types.

        Args:
            webhook: Webhook instance

        Returns:
            ValidationResult with filter validation status
        """
        errors = []
        warnings = []
        details = {
            'filter_validation': 'subscription_filters',
            'filters_valid': False
        }

        # Event types act as filters - validate they form valid filter expressions
        if not webhook.event_types:
            errors.append("Webhook subscription must have at least one event type filter")
            details['filters_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate event types are valid (already validated in event type validation)
        # Here we validate they can be used as filters
        valid_event_types = [choice[0] for choice in WebhookEventType.choices]
        filter_expressions = []

        for event_type in webhook.event_types:
            # Normalize event type
            if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
                event_type_value = event_type[0]
            elif isinstance(event_type, WebhookEventType):
                event_type_value = getattr(event_type, 'value', str(event_type))
            else:
                event_type_value = str(event_type)

            # Validate filter expression format (event types should match pattern: "category.action")
            if '.' not in event_type_value:
                errors.append(
                    f"Invalid filter expression format: '{event_type_value}'. "
                    f"Event types should follow pattern 'category.action' (e.g., 'contract.created')."
                )
            else:
                parts = event_type_value.split('.')
                if len(parts) != 2:
                    warnings.append(
                        f"Event type '{event_type_value}' does not follow standard pattern 'category.action'. "
                        f"Expected format: 'category.action'."
                    )
                filter_expressions.append(event_type_value)

        if filter_expressions:
            details['filter_expressions'] = filter_expressions
            details['filter_count'] = len(filter_expressions)

        # Check if filters are too broad (all event types)
        if len(filter_expressions) >= len(valid_event_types) * 0.8:
            warnings.append(
                f"Webhook subscribes to {len(filter_expressions)} out of {len(valid_event_types)} event types. "
                f"Consider using more specific filters to reduce unnecessary webhook deliveries."
            )
            details['filters_too_broad'] = True
        else:
            details['filters_too_broad'] = False

        details['filters_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_subscription_security(
        self,
        webhook: Webhook
    ) -> ValidationResult:
        """
        Validate subscription security: authentication and signature generation.

        Args:
            webhook: Webhook instance

        Returns:
            ValidationResult with security validation status
        """
        errors = []
        warnings = []
        details = {
            'security_validation': 'subscription_security',
            'secret_valid': False,
            'signature_generation_valid': False
        }

        if not webhook.secret:
            errors.append("Webhook subscription must have a secret")
            details['secret_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate secret strength (use decrypted secret since the model
        # encrypts the secret on save — we need the original length)
        secret = webhook.decrypted_secret
        details['secret_length'] = len(secret)

        # Minimum secret length check
        if len(secret) < 16:
            errors.append(
                f"Webhook secret is too short ({len(secret)} characters). "
                f"Minimum recommended length is 16 characters for security."
            )
            details['secret_valid'] = False
        elif len(secret) < 32:
            warnings.append(
                f"Webhook secret length ({len(secret)} characters) is below recommended minimum (32 characters). "
                f"Consider using a longer secret for better security."
            )
            details['secret_valid'] = True
        else:
            details['secret_valid'] = True

        # Validate secret contains sufficient entropy (basic check)
        import string
        has_lower = any(c in string.ascii_lowercase for c in secret)
        has_upper = any(c in string.ascii_uppercase for c in secret)
        has_digit = any(c in string.digits for c in secret)
        has_special = any(c in string.punctuation for c in secret)

        entropy_score = sum([has_lower, has_upper, has_digit, has_special])
        details['secret_entropy_score'] = entropy_score
        details['secret_has_lower'] = has_lower
        details['secret_has_upper'] = has_upper
        details['secret_has_digit'] = has_digit
        details['secret_has_special'] = has_special

        if entropy_score < 2:
            warnings.append(
                "Webhook secret has low entropy. "
                "Consider using a secret with a mix of lowercase, uppercase, digits, and special characters."
            )

        # Test signature generation capability
        try:
            test_payload = '{"test": "payload"}'
            signature = webhook.generate_signature(test_payload)
            if len(signature) != 64:  # SHA256 hex digest length
                errors.append(
                    f"Webhook signature generation produced invalid signature length ({len(signature)}). "
                    f"Expected 64 characters (SHA256 hex digest)."
                )
                details['signature_generation_valid'] = False
            else:
                details['signature_generation_valid'] = True
                details['signature_length'] = len(signature)
        except Exception as e:
            errors.append(f"Webhook signature generation failed: {str(e)}")
            details['signature_generation_valid'] = False
            details['signature_generation_error'] = str(e)

        # Validate URL uses HTTPS (security best practice)
        if webhook.url:
            from urllib.parse import urlparse
            parsed_url = urlparse(webhook.url)
            if parsed_url.scheme == 'http':
                warnings.append(
                    "Webhook URL uses HTTP instead of HTTPS. "
                    "HTTPS is required for secure webhook delivery in production environments."
                )
                details['url_uses_https'] = False
            else:
                details['url_uses_https'] = parsed_url.scheme == 'https'

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_delivery(
        self,
        delivery: WebhookDelivery,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate a webhook delivery.

        Args:
            delivery: WebhookDelivery instance to validate
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['delivery_validation'] = 'delivery'

        # Validate delivery is not None
        if delivery is None:
            result.is_valid = False
            result.errors.append("Webhook delivery cannot be None")
            return result

        # Validate delivery has required fields
        if not delivery.webhook_id:
            result.is_valid = False
            result.errors.append("Webhook delivery must have a webhook reference")
        else:
            # Validate webhook exists
            try:
                webhook = delivery.webhook
                if webhook is None:
                    result.is_valid = False
                    result.errors.append("Webhook delivery references a non-existent webhook")
            except Exception as e:
                result.is_valid = False
                result.errors.append(f"Error accessing webhook delivery's webhook: {str(e)}")

        if not delivery.event_type:
            result.is_valid = False
            result.errors.append("Webhook delivery must have an event type")

        if delivery.payload is None:
            result.is_valid = False
            result.errors.append("Webhook delivery must have a payload")
        else:
            # Validate payload automatically when validating delivery
            payload_result = self._validate_payload(delivery.payload, delivery)
            result = result.combine(payload_result)

        if not delivery.signature:
            result.is_valid = False
            result.errors.append("Webhook delivery must have a signature")

        # Validate status
        if delivery.status not in [choice[0] for choice in DeliveryStatus.choices]:
            result.is_valid = False
            result.errors.append(f"Invalid delivery status: {delivery.status}")

        # Validate attempt_number
        if delivery.attempt_number < 0:
            result.is_valid = False
            result.errors.append("Webhook delivery attempt_number must be non-negative")

        # Validate tenant consistency if tenant provided
        if tenant and delivery.webhook and delivery.webhook.tenant_id != tenant.id:
            result.is_valid = False
            result.errors.append(
                f"Delivery's webhook tenant_id ({delivery.webhook.tenant_id}) "
                f"does not match provided tenant ({tenant.id})"
            )

        # Validate user permissions if user provided
        if user and delivery.webhook:
            # Check if user belongs to the same tenant as delivery's webhook
            if user.tenant_id != delivery.webhook.tenant_id:
                result.warnings.append(
                    f"User ({user.id}) belongs to different tenant ({user.tenant_id}) "
                    f"than delivery's webhook ({delivery.webhook.tenant_id})"
                )

        result.details['delivery_id'] = str(delivery.id)
        result.details['delivery_status'] = delivery.status
        result.details['delivery_event_type'] = delivery.event_type
        return result

    def _validate_tenant_context(
        self,
        webhook: Optional[Webhook] = None,
        delivery: Optional[WebhookDelivery] = None,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate tenant context consistency.

        Args:
            webhook: Optional webhook instance
            delivery: Optional delivery instance
            tenant: Tenant instance to validate against

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['tenant_context_validation'] = 'tenant_context'

        if tenant is None:
            result.warnings.append("No tenant provided for tenant context validation")
            return result

        # Validate webhook tenant consistency
        if webhook and webhook.tenant_id != tenant.id:
            result.is_valid = False
            result.errors.append(
                f"Webhook tenant_id ({webhook.tenant_id}) does not match provided tenant ({tenant.id})"
            )

        # Validate delivery tenant consistency
        if delivery and delivery.webhook:
            if delivery.webhook.tenant_id != tenant.id:
                result.is_valid = False
                result.errors.append(
                    f"Delivery's webhook tenant_id ({delivery.webhook.tenant_id}) "
                    f"does not match provided tenant ({tenant.id})"
                )

        result.details['tenant_id'] = str(tenant.id)
        return result

    def _validate_permissions(
        self,
        webhook: Optional[Webhook] = None,
        delivery: Optional[WebhookDelivery] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate user permissions for webhook operations.

        Args:
            webhook: Optional webhook instance
            delivery: Optional delivery instance
            user: User instance to validate permissions for

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['permissions_validation'] = 'permissions'

        if user is None:
            result.warnings.append("No user provided for permissions validation")
            return result

        # Validate user belongs to same tenant as webhook
        if webhook and user.tenant_id != webhook.tenant_id:
            result.warnings.append(
                f"User ({user.id}) belongs to different tenant ({user.tenant_id}) "
                f"than webhook ({webhook.tenant_id})"
            )

        # Validate user belongs to same tenant as delivery's webhook
        if delivery and delivery.webhook and user.tenant_id != delivery.webhook.tenant_id:
            result.warnings.append(
                f"User ({user.id}) belongs to different tenant ({user.tenant_id}) "
                f"than delivery's webhook ({delivery.webhook.tenant_id})"
            )

        result.details['user_id'] = str(user.id)
        result.details['user_tenant_id'] = str(user.tenant_id)
        return result

    def _validate_payload(
        self,
        payload: Union[Dict[str, Any], Any],
        delivery: Optional[WebhookDelivery] = None
    ) -> ValidationResult:
        """
        Validate webhook payload (size, structure, and content).

        Args:
            payload: Payload dictionary or any value to validate
            delivery: Optional WebhookDelivery instance (for context)

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['payload_validation'] = 'payload'

        # If payload is None, it's already validated in delivery validation
        if payload is None:
            result.warnings.append("Payload is None - validation skipped")
            return result

        # Validate payload size
        size_result = self._validate_payload_size(payload)
        result = result.combine(size_result)

        # Validate payload structure
        structure_result = self._validate_payload_structure(payload)
        result = result.combine(structure_result)

        # Only validate content if structure is valid
        if structure_result.is_valid and isinstance(payload, dict):
            content_result = self._validate_payload_content(payload, delivery)
            result = result.combine(content_result)

        return result

    def _validate_payload_size(
        self,
        payload: Any
    ) -> ValidationResult:
        """
        Validate payload size is within limits.

        Args:
            payload: Payload to validate

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['payload_size_validation'] = 'payload_size'

        try:
            # Serialize payload to JSON to get accurate size
            payload_json = json.dumps(payload, sort_keys=True, default=str)
            payload_size = len(payload_json.encode('utf-8'))

            result.details['payload_size_bytes'] = payload_size
            result.details['max_payload_size_bytes'] = MAX_PAYLOAD_SIZE

            if payload_size > MAX_PAYLOAD_SIZE:
                result.is_valid = False
                result.errors.append(
                    f"Payload size ({payload_size} bytes) exceeds maximum "
                    f"({MAX_PAYLOAD_SIZE} bytes / {MAX_PAYLOAD_SIZE / 1024 / 1024:.1f}MB)"
                )
            elif payload_size == 0:
                result.warnings.append("Payload is empty (0 bytes)")
            else:
                # Add info about payload size
                size_mb = payload_size / 1024 / 1024
                if size_mb > 0.5:  # Warn if payload is larger than 500KB
                    result.warnings.append(
                        f"Payload is large ({payload_size} bytes / {size_mb:.2f}MB). "
                        f"Consider reducing payload size for better performance."
                    )

        except (TypeError, ValueError) as e:
            result.is_valid = False
            result.errors.append(
                f"Failed to serialize payload for size validation: {str(e)}"
            )
            result.details['serialization_error'] = str(e)

        return result

    def _validate_payload_structure(
        self,
        payload: Any
    ) -> ValidationResult:
        """
        Validate payload structure (must be valid JSON-serializable dict).

        Args:
            payload: Payload to validate

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['payload_structure_validation'] = 'payload_structure'

        # Validate payload is a dictionary
        if not isinstance(payload, dict):
            result.is_valid = False
            result.errors.append(
                f"Payload must be a dictionary, got {type(payload).__name__}"
            )
            result.details['actual_type'] = type(payload).__name__
            result.details['expected_type'] = 'dict'
            return result

        # Validate payload can be serialized to JSON
        try:
            json.dumps(payload, sort_keys=True, default=str)
            result.details['is_json_serializable'] = True
        except (TypeError, ValueError) as e:
            result.is_valid = False
            result.errors.append(
                f"Payload cannot be serialized to JSON: {str(e)}"
            )
            result.details['serialization_error'] = str(e)
            return result

        # Validate payload is not empty
        if not payload:
            result.warnings.append("Payload is empty (no fields)")

        return result

    def _validate_payload_content(
        self,
        payload: Dict[str, Any],
        delivery: Optional[WebhookDelivery] = None
    ) -> ValidationResult:
        """
        Validate payload content (required fields, valid data).

        Args:
            payload: Payload dictionary to validate
            delivery: Optional WebhookDelivery instance (for context validation)

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['payload_content_validation'] = 'payload_content'

        # Validate required fields are present
        missing_fields = []
        for field in REQUIRED_PAYLOAD_FIELDS:
            if field not in payload:
                missing_fields.append(field)
                result.is_valid = False
                result.errors.append(f"Required field '{field}' is missing from payload")

        if missing_fields:
            result.details['missing_fields'] = missing_fields
            return result  # Don't continue validation if required fields are missing

        # Validate field types and values
        # event_type
        event_type = payload.get('event_type')
        if event_type is None:
            result.is_valid = False
            result.errors.append("Field 'event_type' cannot be None")
        elif not isinstance(event_type, str):
            result.is_valid = False
            result.errors.append(
                f"Field 'event_type' must be a string, got {type(event_type).__name__}"
            )
        elif not event_type.strip():
            result.is_valid = False
            result.errors.append("Field 'event_type' cannot be empty")
        else:
            result.details['event_type'] = event_type

        # resource_type
        resource_type = payload.get('resource_type')
        if resource_type is None:
            result.is_valid = False
            result.errors.append("Field 'resource_type' cannot be None")
        elif not isinstance(resource_type, str):
            result.is_valid = False
            result.errors.append(
                f"Field 'resource_type' must be a string, got {type(resource_type).__name__}"
            )
        elif not resource_type.strip():
            result.is_valid = False
            result.errors.append("Field 'resource_type' cannot be empty")
        else:
            result.details['resource_type'] = resource_type

        # resource_id
        resource_id = payload.get('resource_id')
        if resource_id is None:
            result.is_valid = False
            result.errors.append("Field 'resource_id' cannot be None")
        elif not isinstance(resource_id, str):
            result.is_valid = False
            result.errors.append(
                f"Field 'resource_id' must be a string, got {type(resource_id).__name__}"
            )
        elif not resource_id.strip():
            result.is_valid = False
            result.errors.append("Field 'resource_id' cannot be empty")
        else:
            result.details['resource_id'] = resource_id

        # timestamp
        timestamp = payload.get('timestamp')
        if timestamp is None:
            result.is_valid = False
            result.errors.append("Field 'timestamp' cannot be None")
        elif not isinstance(timestamp, str):
            result.is_valid = False
            result.errors.append(
                f"Field 'timestamp' must be a string (ISO format), got {type(timestamp).__name__}"
            )
        elif not timestamp.strip():
            result.is_valid = False
            result.errors.append("Field 'timestamp' cannot be empty")
        else:
            # Validate timestamp format (basic check - should be ISO format)
            try:
                from datetime import datetime
                datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                result.details['timestamp'] = timestamp
            except (ValueError, AttributeError):
                result.warnings.append(
                    f"Field 'timestamp' may not be in valid ISO format: {timestamp}"
                )

        # data
        data = payload.get('data')
        if data is None:
            result.is_valid = False
            result.errors.append("Field 'data' cannot be None")
        elif not isinstance(data, dict):
            result.warnings.append(
                f"Field 'data' is expected to be a dictionary, got {type(data).__name__}"
            )
        else:
            result.details['data_type'] = type(data).__name__
            result.details['data_keys'] = list(data.keys()) if isinstance(data, dict) else None

        # Validate event_type matches delivery if delivery is provided
        if delivery and event_type:
            if delivery.event_type != event_type:
                result.warnings.append(
                    f"Payload event_type ('{event_type}') does not match "
                    f"delivery event_type ('{delivery.event_type}')"
                )

        return result

