"""
ODPS Error Hierarchy

Provides a comprehensive error hierarchy for ODPS (Open Data Product Specification) processing
with error recovery strategies and structured error information.

Error Hierarchy:
- ODPSError (base class)
  - ODPSValidationError
  - ODPSRefResolutionError
  - ODPSNormalizationError
  - ODPSExportError
  - ODPSLinkingError

All errors include:
- error_code: Machine-readable error code for programmatic handling
- user_message: Human-readable error message for end users
- context: Additional context information (dict)
- recoverable: Whether the error can be recovered from
- recovery_strategy: Suggested recovery strategy
"""
import time
from typing import Optional, Dict, Any, Callable
from enum import Enum
from abc import ABC, abstractmethod
import structlog

logger = structlog.get_logger(__name__)


class RecoveryStrategy(str, Enum):
    """Error recovery strategies"""
    RETRY = "retry"
    FALLBACK = "fallback"
    COMPENSATION = "compensation"
    SKIP = "skip"
    FAIL = "fail"


class ODPSError(Exception):
    """
    Base exception class for all ODPS-related errors.

    Provides structured error information with error codes, user messages,
    context, and recovery strategies.

    Attributes:
        error_code: Machine-readable error code for programmatic handling
        user_message: Human-readable error message for end users
        message: Technical error message (same as user_message by default)
        context: Additional context information (dict)
        recoverable: Whether the error can be recovered from
        recovery_strategy: Suggested recovery strategy
        tenant_id: Tenant ID (if applicable)
        user_id: User ID (if applicable)
        timestamp: Error timestamp (Unix timestamp)
    """

    # Common error codes
    ERROR_CODE_UNKNOWN = "UNKNOWN_ERROR"
    ERROR_CODE_INVALID_INPUT = "INVALID_INPUT"
    ERROR_CODE_VALIDATION_FAILED = "VALIDATION_FAILED"
    ERROR_CODE_PROCESSING_FAILED = "PROCESSING_FAILED"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        user_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = False,
        recovery_strategy: Optional[RecoveryStrategy] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        """
        Initialize ODPS error.

        Args:
            message: Technical error message
            error_code: Machine-readable error code
            user_message: Human-readable error message (defaults to message if not provided)
            context: Additional context information
            recoverable: Whether the error can be recovered from
            recovery_strategy: Suggested recovery strategy
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            cause: Original exception that caused this error
        """
        if error_code is None:
            error_code = ODPSError.ERROR_CODE_UNKNOWN
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.user_message = user_message or message
        self.context = context or {}
        self.recoverable = recoverable
        self.recovery_strategy = recovery_strategy
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.timestamp = int(time.time())
        self.cause = cause

        # Store cause in context for better error tracking
        if cause:
            self.context["cause_type"] = type(cause).__name__
            self.context["cause_message"] = str(cause)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to dictionary for API responses and logging.

        Returns:
            Dictionary with error details
        """
        result = {
            "error": self.error_code,
            "message": self.user_message,
            "technical_message": self.message,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp,
        }

        if self.recovery_strategy:
            result["recovery_strategy"] = self.recovery_strategy.value

        if self.context:
            result["context"] = self.context

        if self.tenant_id:
            result["tenant_id"] = self.tenant_id

        if self.user_id:
            result["user_id"] = self.user_id

        return result

    def __str__(self) -> str:
        """String representation of the error"""
        return f"{self.__class__.__name__}({self.error_code}): {self.message}"

    def __repr__(self) -> str:
        """Detailed representation of the error"""
        return (
            f"{self.__class__.__name__}("
            f"error_code={self.error_code!r}, "
            f"message={self.message!r}, "
            f"recoverable={self.recoverable}, "
            f"recovery_strategy={self.recovery_strategy}, "
            f"context={self.context!r}"
            f")"
        )


class ODPSValidationError(ODPSError):
    """
    Exception raised when ODPS document validation fails.

    Used for schema validation, required field validation, and data type validation.
    """

    ERROR_CODE_SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
    ERROR_CODE_REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING"
    ERROR_CODE_INVALID_DATA_TYPE = "INVALID_DATA_TYPE"
    ERROR_CODE_INVALID_VALUE = "INVALID_VALUE"
    ERROR_CODE_VERSION_MISMATCH = "VERSION_MISMATCH"

    def __init__(
        self,
        message: str,
        error_code: str = None,
        user_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        field_path: Optional[str] = None,
        expected: Optional[Any] = None,
        actual: Optional[Any] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        """
        Initialize ODPS validation error.

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
            cause: Original exception that caused this error
        """
        if error_code is None:
            error_code = ODPSValidationError.ERROR_CODE_VALIDATION_FAILED
        if context is None:
            context = {}

        if field_path:
            context["field_path"] = field_path
        if expected is not None:
            context["expected"] = expected
        if actual is not None:
            context["actual"] = actual

        super().__init__(
            message=message,
            error_code=error_code,
            user_message=user_message,
            context=context,
            recoverable=False,  # Validation errors are typically not recoverable
            recovery_strategy=RecoveryStrategy.FAIL,
            tenant_id=tenant_id,
            user_id=user_id,
            cause=cause,
        )


class ODPSRefResolutionError(ODPSError):
    """
    Exception raised when ODPS $ref resolution fails.

    Used for internal, local, and external reference resolution errors.
    """

    ERROR_CODE_RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    ERROR_CODE_RESOLUTION_FAILED = "RESOLUTION_FAILED"
    ERROR_CODE_INVALID_REF = "INVALID_REF"
    ERROR_CODE_SECURITY_VIOLATION = "SECURITY_VIOLATION"
    ERROR_CODE_TIMEOUT = "TIMEOUT"
    ERROR_CODE_SIZE_LIMIT_EXCEEDED = "SIZE_LIMIT_EXCEEDED"
    ERROR_CODE_CIRCULAR_REF = "CIRCULAR_REF"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        user_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
        ref_path: Optional[str] = None,
        ref_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        """
        Initialize ODPS ref resolution error.

        Args:
            message: Technical error message
            error_code: Machine-readable error code
            user_message: Human-readable error message
            context: Additional context information
            retry_after: Unix timestamp when the rate limit resets (for rate limit errors)
            ref_path: The $ref path that failed to resolve
            ref_type: Type of reference (internal, local, external)
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            cause: Original exception that caused this error
        """
        if context is None:
            context = {}

        if retry_after:
            context["retry_after"] = retry_after
            context["retry_after_timestamp"] = retry_after
            # Calculate seconds until retry
            current_time = int(time.time())
            context["retry_after_seconds"] = max(0, retry_after - current_time)

        if ref_path:
            context["ref_path"] = ref_path
        if ref_type:
            context["ref_type"] = ref_type

        if error_code is None:
            error_code = ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED

        # Determine recoverability and recovery strategy
        recoverable = error_code in {
            self.ERROR_CODE_RATE_LIMIT_EXCEEDED,
            self.ERROR_CODE_TIMEOUT,
            self.ERROR_CODE_RESOLUTION_FAILED,
        }
        recovery_strategy = None
        if error_code == self.ERROR_CODE_RATE_LIMIT_EXCEEDED:
            recovery_strategy = RecoveryStrategy.RETRY
        elif error_code == self.ERROR_CODE_TIMEOUT:
            recovery_strategy = RecoveryStrategy.RETRY
        elif error_code == self.ERROR_CODE_RESOLUTION_FAILED:
            recovery_strategy = RecoveryStrategy.FALLBACK
        elif error_code == self.ERROR_CODE_SECURITY_VIOLATION:
            recovery_strategy = RecoveryStrategy.FAIL
        elif error_code == self.ERROR_CODE_INVALID_REF:
            recovery_strategy = RecoveryStrategy.FAIL

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

        self.retry_after = retry_after

    def get_retry_after_header(self) -> Optional[str]:
        """
        Get Retry-After header value (seconds until retry).

        Returns:
            Retry-After header value as string (seconds), or None if not applicable
        """
        if self.retry_after is None:
            return None

        current_time = int(time.time())
        retry_seconds = max(0, self.retry_after - current_time)
        return str(retry_seconds)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary, including retry_after information"""
        result = super().to_dict()

        if self.retry_after:
            result["retry_after"] = self.context.get("retry_after_seconds", 0)
            result["retry_after_timestamp"] = self.retry_after

        return result


class ODPSNormalizationError(ODPSError):
    """
    Exception raised when ODPS document normalization fails.

    Used for errors during the normalization process (converting ODPS to HubContract format).
    """

    ERROR_CODE_NORMALIZATION_FAILED = "NORMALIZATION_FAILED"
    ERROR_CODE_FIELD_MAPPING_FAILED = "FIELD_MAPPING_FAILED"
    ERROR_CODE_TYPE_CONVERSION_FAILED = "TYPE_CONVERSION_FAILED"
    ERROR_CODE_MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    ERROR_CODE_INVALID_FIELD_VALUE = "INVALID_FIELD_VALUE"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        user_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        field_path: Optional[str] = None,
        source_path: Optional[str] = None,
        target_path: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        """
        Initialize ODPS normalization error.

        Args:
            message: Technical error message
            error_code: Machine-readable error code
            user_message: Human-readable error message
            context: Additional context information
            field_path: Path to the field that failed normalization
            source_path: Source field path in ODPS document
            target_path: Target field path in HubContract
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            cause: Original exception that caused this error
        """
        if context is None:
            context = {}

        if field_path:
            context["field_path"] = field_path
        if source_path:
            context["source_path"] = source_path
        if target_path:
            context["target_path"] = target_path

        if error_code is None:
            error_code = ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED

        super().__init__(
            message=message,
            error_code=error_code,
            user_message=user_message,
            context=context,
            recoverable=True,  # Normalization errors may be recoverable with fallback
            recovery_strategy=RecoveryStrategy.FALLBACK,
            tenant_id=tenant_id,
            user_id=user_id,
            cause=cause,
        )


class ODPSExportError(ODPSError):
    """
    Exception raised when ODPS document export fails.

    Used for errors during export to various formats (JSON, YAML, etc.).
    """

    ERROR_CODE_EXPORT_FAILED = "EXPORT_FAILED"
    ERROR_CODE_SERIALIZATION_FAILED = "SERIALIZATION_FAILED"
    ERROR_CODE_FORMAT_NOT_SUPPORTED = "FORMAT_NOT_SUPPORTED"
    ERROR_CODE_FILE_WRITE_FAILED = "FILE_WRITE_FAILED"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        user_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        export_format: Optional[str] = None,
        file_path: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        """
        Initialize ODPS export error.

        Args:
            message: Technical error message
            error_code: Machine-readable error code
            user_message: Human-readable error message
            context: Additional context information
            export_format: Export format that failed (json, yaml, etc.)
            file_path: File path where export was attempted
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            cause: Original exception that caused this error
        """
        if context is None:
            context = {}

        if export_format:
            context["export_format"] = export_format
        if file_path:
            context["file_path"] = file_path

        if error_code is None:
            error_code = ODPSExportError.ERROR_CODE_EXPORT_FAILED

        super().__init__(
            message=message,
            error_code=error_code,
            user_message=user_message,
            context=context,
            recoverable=True,  # Export errors may be recoverable with different format
            recovery_strategy=RecoveryStrategy.FALLBACK,
            tenant_id=tenant_id,
            user_id=user_id,
            cause=cause,
        )


class ODPSLinkingError(ODPSError):
    """
    Exception raised when ODPS document linking fails.

    Used for errors during link resolution, validation, and indexing.
    """

    ERROR_CODE_LINKING_FAILED = "LINKING_FAILED"
    ERROR_CODE_LINK_RESOLUTION_FAILED = "LINK_RESOLUTION_FAILED"
    ERROR_CODE_LINK_VALIDATION_FAILED = "LINK_VALIDATION_FAILED"
    ERROR_CODE_CIRCULAR_REFERENCE = "CIRCULAR_REFERENCE"
    ERROR_CODE_INVALID_LINK = "INVALID_LINK"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        user_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        link_path: Optional[str] = None,
        link_type: Optional[str] = None,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        """
        Initialize ODPS linking error.

        Args:
            message: Technical error message
            error_code: Machine-readable error code
            user_message: Human-readable error message
            context: Additional context information
            link_path: Path to the link that failed
            link_type: Type of link (contract, asset, etc.)
            source_id: Source entity ID
            target_id: Target entity ID
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            cause: Original exception that caused this error
        """
        if context is None:
            context = {}

        if link_path:
            context["link_path"] = link_path
        if link_type:
            context["link_type"] = link_type
        if source_id:
            context["source_id"] = source_id
        if target_id:
            context["target_id"] = target_id

        if error_code is None:
            error_code = ODPSLinkingError.ERROR_CODE_LINKING_FAILED

        super().__init__(
            message=message,
            error_code=error_code,
            user_message=user_message,
            context=context,
            recoverable=True,  # Linking errors may be recoverable with skip
            recovery_strategy=RecoveryStrategy.SKIP,
            tenant_id=tenant_id,
            user_id=user_id,
            cause=cause,
        )


# Error Recovery Strategies


class ErrorRecoveryHandler(ABC):
    """
    Abstract base class for error recovery handlers.

    Implementations should provide specific recovery logic for different error types.
    """

    @abstractmethod
    def can_handle(self, error: ODPSError) -> bool:
        """
        Check if this handler can handle the given error.

        Args:
            error: The error to check

        Returns:
            True if this handler can handle the error
        """
        pass

    @abstractmethod
    def recover(self, error: ODPSError, context: Dict[str, Any]) -> Any:
        """
        Attempt to recover from the error.

        Args:
            error: The error to recover from
            context: Additional context for recovery

        Returns:
            Recovered result or raises exception if recovery fails

        Raises:
            ODPSError: If recovery fails
        """
        pass


class RetryRecoveryHandler(ErrorRecoveryHandler):
    """
    Recovery handler that retries the operation.

    Implements exponential backoff retry strategy.
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
    ):
        """
        Initialize retry recovery handler.

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds before first retry
            max_delay: Maximum delay in seconds between retries
            backoff_factor: Factor to multiply delay by after each retry
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def can_handle(self, error: ODPSError) -> bool:
        """Check if error is recoverable with retry"""
        return (
            error.recoverable
            and error.recovery_strategy == RecoveryStrategy.RETRY
        )

    def recover(
        self,
        error: ODPSError,
        context: Dict[str, Any],
        operation: Optional[Callable] = None,
    ) -> Any:
        """
        Retry the operation with exponential backoff.

        Args:
            error: The error to recover from
            context: Additional context (must include 'operation' callable)
            operation: Optional operation to retry (can also be in context)

        Returns:
            Result of the operation

        Raises:
            ODPSError: If all retries fail
        """
        if operation is None:
            operation = context.get("operation")
        if operation is None:
            raise ValueError("Operation must be provided for retry recovery")

        delay = self.initial_delay
        last_error = error

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    "retry_recovery_attempt",
                    error_code=error.error_code,
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    delay=delay,
                )
                return operation()
            except ODPSError as e:
                last_error = e
                if not self.can_handle(e):
                    # Error changed to non-retryable, stop retrying
                    raise e
                if attempt < self.max_retries - 1:
                    time.sleep(delay)
                    delay = min(delay * self.backoff_factor, self.max_delay)
                else:
                    # Last attempt failed
                    raise e
            except Exception as e:
                # Non-ODPS error, wrap and raise
                raise ODPSError(
                    message=f"Retry recovery failed: {str(e)}",
                    error_code=ODPSError.ERROR_CODE_PROCESSING_FAILED,
                    cause=e,
                ) from e

        raise last_error


class FallbackRecoveryHandler(ErrorRecoveryHandler):
    """
    Recovery handler that uses a fallback operation.
    """

    def can_handle(self, error: ODPSError) -> bool:
        """Check if error is recoverable with fallback"""
        return (
            error.recoverable
            and error.recovery_strategy == RecoveryStrategy.FALLBACK
        )

    def recover(
        self,
        error: ODPSError,
        context: Dict[str, Any],
        fallback_operation: Optional[Callable] = None,
    ) -> Any:
        """
        Use fallback operation to recover.

        Args:
            error: The error to recover from
            context: Additional context (must include 'fallback_operation' callable)
            fallback_operation: Optional fallback operation (can also be in context)

        Returns:
            Result of the fallback operation

        Raises:
            ODPSError: If fallback operation fails
        """
        if fallback_operation is None:
            fallback_operation = context.get("fallback_operation")
        if fallback_operation is None:
            raise ValueError("Fallback operation must be provided for fallback recovery")

        try:
            logger.info(
                "fallback_recovery_attempt",
                error_code=error.error_code,
                message="Attempting fallback recovery",
            )
            return fallback_operation()
        except Exception as e:
            raise ODPSError(
                message=f"Fallback recovery failed: {str(e)}",
                error_code=ODPSError.ERROR_CODE_PROCESSING_FAILED,
                cause=e,
            ) from e


class CompensationRecoveryHandler(ErrorRecoveryHandler):
    """
    Recovery handler that compensates for a failed operation.

    Used for rollback, cleanup, or alternative processing.
    """

    def can_handle(self, error: ODPSError) -> bool:
        """Check if error can be compensated"""
        return (
            error.recoverable
            and error.recovery_strategy == RecoveryStrategy.COMPENSATION
        )

    def recover(
        self,
        error: ODPSError,
        context: Dict[str, Any],
        compensation_operation: Optional[Callable] = None,
    ) -> Any:
        """
        Execute compensation operation.

        Args:
            error: The error to compensate for
            context: Additional context (must include 'compensation_operation' callable)
            compensation_operation: Optional compensation operation (can also be in context)

        Returns:
            Result of the compensation operation

        Raises:
            ODPSError: If compensation fails
        """
        if compensation_operation is None:
            compensation_operation = context.get("compensation_operation")
        if compensation_operation is None:
            raise ValueError("Compensation operation must be provided for compensation recovery")

        try:
            logger.info(
                "compensation_recovery_attempt",
                error_code=error.error_code,
                message="Attempting compensation recovery",
            )
            return compensation_operation()
        except Exception as e:
            raise ODPSError(
                message=f"Compensation recovery failed: {str(e)}",
                error_code=ODPSError.ERROR_CODE_PROCESSING_FAILED,
                cause=e,
            ) from e


def recover_from_error(
    error: ODPSError,
    context: Dict[str, Any],
    handlers: Optional[list[ErrorRecoveryHandler]] = None,
) -> Any:
    """
    Attempt to recover from an ODPS error using available recovery handlers.

    Args:
        error: The error to recover from
        context: Additional context for recovery
        handlers: List of recovery handlers (defaults to standard handlers)

    Returns:
        Recovered result

    Raises:
        ODPSError: If recovery fails or error is not recoverable
    """
    if not error.recoverable:
        raise error

    if handlers is None:
        handlers = [
            RetryRecoveryHandler(),
            FallbackRecoveryHandler(),
            CompensationRecoveryHandler(),
        ]

    for handler in handlers:
        if handler.can_handle(error):
            try:
                return handler.recover(error, context)
            except ODPSError:
                # Handler failed, try next handler
                continue
            except Exception as e:
                # Non-ODPS error, wrap and raise
                raise ODPSError(
                    message=f"Recovery failed: {str(e)}",
                    error_code=ODPSError.ERROR_CODE_PROCESSING_FAILED,
                    cause=e,
                ) from e

    # No handler could recover
    raise error

