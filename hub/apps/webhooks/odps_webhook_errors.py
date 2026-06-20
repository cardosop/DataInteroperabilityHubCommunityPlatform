"""
ODPS Webhook Error Hierarchy

Provides comprehensive error handling for ODPS webhook operations,
extending the ODPS error hierarchy with webhook-specific error types.

Error Hierarchy:
- ODPSWebhookError (base class, extends ODPSError)
  - ODPSWebhookDeliveryError
  - ODPSWebhookValidationError
  - ODPSWebhookPayloadError
"""

from typing import Any

from hub.apps.contracts.odps_errors import (
    ODPSError,
    RecoveryStrategy,
)


class ODPSWebhookError(ODPSError):
    """
    Base exception class for all ODPS webhook-related errors.

    Extends ODPSError with webhook-specific context and error codes.
    """

    ERROR_CODE_WEBHOOK_UNKNOWN = "WEBHOOK_UNKNOWN_ERROR"
    ERROR_CODE_WEBHOOK_DELIVERY_FAILED = "WEBHOOK_DELIVERY_FAILED"
    ERROR_CODE_WEBHOOK_VALIDATION_FAILED = "WEBHOOK_VALIDATION_FAILED"
    ERROR_CODE_WEBHOOK_PAYLOAD_INVALID = "WEBHOOK_PAYLOAD_INVALID"

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        user_message: str | None = None,
        context: dict[str, Any] | None = None,
        recoverable: bool = False,
        recovery_strategy: RecoveryStrategy | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        webhook_id: str | None = None,
        delivery_id: str | None = None,
        event_type: str | None = None,
        cause: Exception | None = None,
    ):
        """
        Initialize ODPS webhook error.

        Args:
            message: Technical error message
            error_code: Machine-readable error code
            user_message: Human-readable error message
            context: Additional context information
            recoverable: Whether the error can be recovered from
            recovery_strategy: Suggested recovery strategy
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            webhook_id: Webhook ID (if applicable)
            delivery_id: Delivery ID (if applicable)
            event_type: Event type (if applicable)
            cause: Original exception that caused this error
        """
        if context is None:
            context = {}

        # Add webhook-specific context
        if webhook_id:
            context["webhook_id"] = webhook_id
        if delivery_id:
            context["delivery_id"] = delivery_id
        if event_type:
            context["event_type"] = event_type

        if error_code is None:
            error_code = ODPSWebhookError.ERROR_CODE_WEBHOOK_UNKNOWN

        super().__init__(
            message=message,
            error_code=error_code,
            user_message=user_message,
            context=context,
            recoverable=recoverable,
            recovery_strategy=recovery_strategy,
            tenant_id=tenant_id,
            user_id=user_id,
            cause=cause,
        )

        self.webhook_id = webhook_id
        self.delivery_id = delivery_id
        self.event_type = event_type


class ODPSWebhookDeliveryError(ODPSWebhookError):
    """
    Exception raised when ODPS webhook delivery fails.

    Used for network errors, HTTP errors, timeout errors, and other
    delivery-related failures.
    """

    ERROR_CODE_NETWORK_ERROR = "WEBHOOK_NETWORK_ERROR"
    ERROR_CODE_HTTP_ERROR = "WEBHOOK_HTTP_ERROR"
    ERROR_CODE_TIMEOUT = "WEBHOOK_TIMEOUT"
    ERROR_CODE_CONNECTION_ERROR = "WEBHOOK_CONNECTION_ERROR"
    ERROR_CODE_SSL_ERROR = "WEBHOOK_SSL_ERROR"
    ERROR_CODE_RATE_LIMITED = "WEBHOOK_RATE_LIMITED"
    ERROR_CODE_AUTHENTICATION_FAILED = "WEBHOOK_AUTHENTICATION_FAILED"
    ERROR_CODE_INVALID_RESPONSE = "WEBHOOK_INVALID_RESPONSE"

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        user_message: str | None = None,
        context: dict[str, Any] | None = None,
        http_status_code: int | None = None,
        response_body: str | None = None,
        url: str | None = None,
        retry_after: int | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        webhook_id: str | None = None,
        delivery_id: str | None = None,
        event_type: str | None = None,
        cause: Exception | None = None,
    ):
        """
        Initialize ODPS webhook delivery error.

        Args:
            message: Technical error message
            error_code: Machine-readable error code
            user_message: Human-readable error message
            context: Additional context information
            http_status_code: HTTP status code (if applicable)
            response_body: Response body (if applicable)
            url: Webhook URL (if applicable)
            retry_after: Seconds until retry (for rate limit errors)
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            webhook_id: Webhook ID (if applicable)
            delivery_id: Delivery ID (if applicable)
            event_type: Event type (if applicable)
            cause: Original exception that caused this error
        """
        if context is None:
            context = {}

        if http_status_code:
            context["http_status_code"] = http_status_code
        if response_body:
            # Limit response body size in context
            context["response_body"] = (
                response_body[:500] if len(response_body) > 500 else response_body
            )
        if url:
            context["url"] = url
        if retry_after:
            context["retry_after"] = retry_after

        if error_code is None:
            error_code = ODPSWebhookDeliveryError.ERROR_CODE_WEBHOOK_DELIVERY_FAILED

        # Determine recoverability based on error code
        recoverable = error_code in {
            self.ERROR_CODE_NETWORK_ERROR,
            self.ERROR_CODE_TIMEOUT,
            self.ERROR_CODE_CONNECTION_ERROR,
            self.ERROR_CODE_RATE_LIMITED,
            self.ERROR_CODE_HTTP_ERROR,  # Some HTTP errors are retryable (5xx)
        }

        # Determine recovery strategy
        recovery_strategy = None
        if error_code == self.ERROR_CODE_RATE_LIMITED or error_code in {
            self.ERROR_CODE_NETWORK_ERROR,
            self.ERROR_CODE_TIMEOUT,
            self.ERROR_CODE_CONNECTION_ERROR,
        }:
            recovery_strategy = RecoveryStrategy.RETRY
        elif error_code == self.ERROR_CODE_HTTP_ERROR:
            # 5xx errors are retryable, 4xx are not
            if http_status_code and 500 <= http_status_code < 600:
                recovery_strategy = RecoveryStrategy.RETRY
            else:
                recovery_strategy = RecoveryStrategy.FAIL
                recoverable = False
        elif (
            error_code == self.ERROR_CODE_SSL_ERROR
            or error_code == self.ERROR_CODE_AUTHENTICATION_FAILED
        ):
            recovery_strategy = RecoveryStrategy.FAIL
            recoverable = False

        super().__init__(
            message=message,
            error_code=error_code,
            user_message=user_message,
            context=context,
            recoverable=recoverable,
            recovery_strategy=recovery_strategy,
            tenant_id=tenant_id,
            user_id=user_id,
            webhook_id=webhook_id,
            delivery_id=delivery_id,
            event_type=event_type,
            cause=cause,
        )

        self.http_status_code = http_status_code
        self.response_body = response_body
        self.url = url
        self.retry_after = retry_after


class ODPSWebhookValidationError(ODPSWebhookError):
    """
    Exception raised when ODPS webhook validation fails.

    Used for event type validation, webhook configuration validation,
    and other validation-related errors.
    """

    ERROR_CODE_INVALID_EVENT_TYPE = "WEBHOOK_INVALID_EVENT_TYPE"
    ERROR_CODE_INVALID_WEBHOOK_CONFIG = "WEBHOOK_INVALID_CONFIG"
    ERROR_CODE_MISSING_REQUIRED_FIELD = "WEBHOOK_MISSING_REQUIRED_FIELD"
    ERROR_CODE_INVALID_TENANT = "WEBHOOK_INVALID_TENANT"
    ERROR_CODE_WEBHOOK_INACTIVE = "WEBHOOK_INACTIVE"

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        user_message: str | None = None,
        context: dict[str, Any] | None = None,
        field_path: str | None = None,
        expected: Any | None = None,
        actual: Any | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        webhook_id: str | None = None,
        delivery_id: str | None = None,
        event_type: str | None = None,
        cause: Exception | None = None,
    ):
        """
        Initialize ODPS webhook validation error.

        Args:
            message: Technical error message
            error_code: Machine-readable error code
            user_message: Human-readable error message
            context: Additional context information
            field_path: JSON Pointer path to the field that failed validation
            expected: Expected value or type
            actual: Actual value that failed validation
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            webhook_id: Webhook ID (if applicable)
            delivery_id: Delivery ID (if applicable)
            event_type: Event type (if applicable)
            cause: Original exception that caused this error
        """
        if context is None:
            context = {}

        if field_path:
            context["field_path"] = field_path
        if expected is not None:
            context["expected"] = expected
        if actual is not None:
            context["actual"] = actual

        if error_code is None:
            error_code = ODPSWebhookValidationError.ERROR_CODE_VALIDATION_FAILED

        super().__init__(
            message=message,
            error_code=error_code,
            user_message=user_message,
            context=context,
            recoverable=False,  # Validation errors are typically not recoverable
            recovery_strategy=RecoveryStrategy.FAIL,
            tenant_id=tenant_id,
            user_id=user_id,
            webhook_id=webhook_id,
            delivery_id=delivery_id,
            event_type=event_type,
            cause=cause,
        )

        self.field_path = field_path
        self.expected = expected
        self.actual = actual


class ODPSWebhookPayloadError(ODPSWebhookError):
    """
    Exception raised when ODPS webhook payload validation fails.

    Used for payload structure validation, required field validation,
    and data type validation.
    """

    ERROR_CODE_INVALID_PAYLOAD_STRUCTURE = "WEBHOOK_INVALID_PAYLOAD_STRUCTURE"
    ERROR_CODE_MISSING_REQUIRED_FIELD = "WEBHOOK_PAYLOAD_MISSING_FIELD"
    ERROR_CODE_INVALID_FIELD_TYPE = "WEBHOOK_PAYLOAD_INVALID_TYPE"
    ERROR_CODE_INVALID_FIELD_VALUE = "WEBHOOK_PAYLOAD_INVALID_VALUE"
    ERROR_CODE_PAYLOAD_TOO_LARGE = "WEBHOOK_PAYLOAD_TOO_LARGE"
    ERROR_CODE_INVALID_EVENT_DATA = "WEBHOOK_INVALID_EVENT_DATA"

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        user_message: str | None = None,
        context: dict[str, Any] | None = None,
        field_path: str | None = None,
        expected: Any | None = None,
        actual: Any | None = None,
        payload_size: int | None = None,
        max_payload_size: int | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        webhook_id: str | None = None,
        delivery_id: str | None = None,
        event_type: str | None = None,
        cause: Exception | None = None,
    ):
        """
        Initialize ODPS webhook payload error.

        Args:
            message: Technical error message
            error_code: Machine-readable error code
            user_message: Human-readable error message
            context: Additional context information
            field_path: JSON Pointer path to the field that failed validation
            expected: Expected value or type
            actual: Actual value that failed validation
            payload_size: Size of the payload in bytes (if applicable)
            max_payload_size: Maximum allowed payload size in bytes (if applicable)
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            webhook_id: Webhook ID (if applicable)
            delivery_id: Delivery ID (if applicable)
            event_type: Event type (if applicable)
            cause: Original exception that caused this error
        """
        if context is None:
            context = {}

        if field_path:
            context["field_path"] = field_path
        if expected is not None:
            context["expected"] = expected
        if actual is not None:
            context["actual"] = actual
        if payload_size:
            context["payload_size"] = payload_size
        if max_payload_size:
            context["max_payload_size"] = max_payload_size

        if error_code is None:
            error_code = ODPSWebhookPayloadError.ERROR_CODE_INVALID_PAYLOAD_STRUCTURE

        super().__init__(
            message=message,
            error_code=error_code,
            user_message=user_message,
            context=context,
            recoverable=False,  # Payload errors are typically not recoverable
            recovery_strategy=RecoveryStrategy.FAIL,
            tenant_id=tenant_id,
            user_id=user_id,
            webhook_id=webhook_id,
            delivery_id=delivery_id,
            event_type=event_type,
            cause=cause,
        )

        self.field_path = field_path
        self.expected = expected
        self.actual = actual
        self.payload_size = payload_size
        self.max_payload_size = max_payload_size
