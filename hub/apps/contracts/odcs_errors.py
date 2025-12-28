"""
ODCS Error Hierarchy

Provides a comprehensive error hierarchy for ODCS (Open Data Contract Standard) processing
with error recovery strategies and structured error information.

Error Hierarchy:
- ODCSError (base class)
  - ODCSValidationError
  - ODCSGenerationError
  - ODCSExportError

All errors include:
- error_code: Machine-readable error code for programmatic handling
- user_message: Human-readable error message for end users
- context: Additional context information (dict)
- recoverable: Whether the error can be recovered from
- recovery_strategy: Suggested recovery strategy
"""
import time
from typing import Optional, Dict, Any
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class RecoveryStrategy(str, Enum):
    """Error recovery strategies"""
    RETRY = "retry"
    FALLBACK = "fallback"
    COMPENSATION = "compensation"
    SKIP = "skip"
    FAIL = "fail"


class ODCSError(Exception):
    """
    Base exception class for all ODCS-related errors.

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
        Initialize ODCS error.

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
            error_code = ODCSError.ERROR_CODE_UNKNOWN
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


class ODCSValidationError(ODCSError):
    """
    Exception raised when ODCS document validation fails.

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
        Initialize ODCS validation error.

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
            error_code = ODCSValidationError.ERROR_CODE_VALIDATION_FAILED
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


class ODCSGenerationError(ODCSError):
    """
    Exception raised when ODCS document generation fails.

    Used for errors during the generation process (converting HubContract to ODCS format).
    """

    ERROR_CODE_GENERATION_FAILED = "GENERATION_FAILED"
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
        Initialize ODCS generation error.

        Args:
            message: Technical error message
            error_code: Machine-readable error code
            user_message: Human-readable error message
            context: Additional context information
            field_path: Path to the field that failed generation
            source_path: Source field path in HubContract
            target_path: Target field path in ODCS document
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
            error_code = ODCSGenerationError.ERROR_CODE_GENERATION_FAILED

        super().__init__(
            message=message,
            error_code=error_code,
            user_message=user_message,
            context=context,
            recoverable=True,  # Generation errors may be recoverable with fallback
            recovery_strategy=RecoveryStrategy.FALLBACK,
            tenant_id=tenant_id,
            user_id=user_id,
            cause=cause,
        )


class ODCSExportError(ODCSError):
    """
    Exception raised when ODCS document export fails.

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
        Initialize ODCS export error.

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
            error_code = ODCSExportError.ERROR_CODE_EXPORT_FAILED

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

