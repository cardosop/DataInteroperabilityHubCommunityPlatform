"""
Transformation Error Hierarchy

Provides a comprehensive error hierarchy for transformation pipeline operations
with structured error information, error codes, and context.

Error Hierarchy:
- TransformationError (base class, extends ServiceError)
  - TransformationValidationError
  - TransformationExecutionError
  - PipelineNotFoundError
  - AssetCompatibilityError
  - ResourceQuotaExceededError

All errors include:
- error_code: Machine-readable error code for programmatic handling
- message: Human-readable error message
- details: Additional context information (dict)
- http_status: HTTP status code for API responses
"""

import time
from typing import Any

from hub.apps.core.services.base import ServiceError


class TransformationError(ServiceError):
    """
    Base exception class for all transformation-related errors.

    Extends ServiceError with transformation-specific error codes and context.

    Attributes:
        error_code: Machine-readable error code for programmatic handling
        message: Human-readable error message
        details: Additional context information (dict)
        http_status: HTTP status code for API responses
        tenant_id: Tenant ID (if applicable)
        user_id: User ID (if applicable)
        timestamp: Error timestamp (Unix timestamp)
    """

    # Common error codes
    ERROR_CODE_UNKNOWN = "TRANSFORMATION_UNKNOWN_ERROR"
    ERROR_CODE_VALIDATION_FAILED = "TRANSFORMATION_VALIDATION_FAILED"
    ERROR_CODE_EXECUTION_FAILED = "TRANSFORMATION_EXECUTION_FAILED"
    ERROR_CODE_PIPELINE_NOT_FOUND = "PIPELINE_NOT_FOUND"
    ERROR_CODE_ASSET_INCOMPATIBLE = "ASSET_INCOMPATIBLE"
    ERROR_CODE_QUOTA_EXCEEDED = "RESOURCE_QUOTA_EXCEEDED"

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        http_status: int = 500,
        tenant_id: str | None = None,
        user_id: str | None = None,
        cause: Exception | None = None,
    ):
        """
        Initialize TransformationError.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code (defaults to ERROR_CODE_UNKNOWN)
            details: Additional context information
            http_status: HTTP status code for API responses
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            cause: Original exception that caused this error
        """
        if error_code is None:
            error_code = TransformationError.ERROR_CODE_UNKNOWN

        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.http_status = http_status
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.timestamp = int(time.time())
        self.cause = cause

        # Store cause in details for better error tracking
        if cause:
            self.details["cause_type"] = type(cause).__name__
            self.details["cause_message"] = str(cause)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert error to dictionary for API responses and logging.

        Returns:
            Dictionary with error details
        """
        result = {
            "error": self.error_code,
            "message": self.message,
            "http_status": self.http_status,
            "timestamp": self.timestamp,
            "details": self.details,
        }

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
            f"http_status={self.http_status}, "
            f"details={self.details!r}"
            f")"
        )


class TransformationValidationError(TransformationError):
    """
    Exception raised when transformation validation fails.

    Used for pipeline definition validation, node configuration validation,
    and schema validation errors.
    """

    ERROR_CODE_INVALID_PIPELINE_DEFINITION = "INVALID_PIPELINE_DEFINITION"
    ERROR_CODE_INVALID_NODE_CONFIG = "INVALID_NODE_CONFIG"
    ERROR_CODE_INVALID_NODE_TYPE = "INVALID_NODE_TYPE"
    ERROR_CODE_MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    ERROR_CODE_INVALID_FIELD_VALUE = "INVALID_FIELD_VALUE"
    ERROR_CODE_SCHEMA_MISMATCH = "SCHEMA_MISMATCH"

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        field_path: str | None = None,
        expected: Any | None = None,
        actual: Any | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        cause: Exception | None = None,
    ):
        """
        Initialize TransformationValidationError.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional context information
            field_path: Path to the field that failed validation
            expected: Expected value or type
            actual: Actual value that failed validation
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            cause: Original exception that caused this error
        """
        if error_code is None:
            error_code = TransformationValidationError.ERROR_CODE_VALIDATION_FAILED

        if details is None:
            details = {}

        if field_path:
            details["field_path"] = field_path
        if expected is not None:
            details["expected"] = expected
        if actual is not None:
            details["actual"] = actual

        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            http_status=400,
            tenant_id=tenant_id,
            user_id=user_id,
            cause=cause,
        )


class TransformationExecutionError(TransformationError):
    """
    Exception raised when transformation pipeline execution fails.

    Used for runtime errors during pipeline execution, node execution failures,
    and data processing errors.
    """

    ERROR_CODE_EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    ERROR_CODE_NODE_EXECUTION_FAILED = "NODE_EXECUTION_FAILED"
    ERROR_CODE_DATA_PROCESSING_FAILED = "DATA_PROCESSING_FAILED"
    ERROR_CODE_OUTPUT_GENERATION_FAILED = "OUTPUT_GENERATION_FAILED"
    ERROR_CODE_INTERNAL_ERROR = "INTERNAL_EXECUTION_ERROR"

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        pipeline_id: str | None = None,
        execution_id: str | None = None,
        node_id: str | None = None,
        step_name: str | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        cause: Exception | None = None,
    ):
        """
        Initialize TransformationExecutionError.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional context information
            pipeline_id: Pipeline ID where execution failed
            execution_id: Execution ID where error occurred
            node_id: Node ID where execution failed
            step_name: Step name where execution failed
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            cause: Original exception that caused this error
        """
        if error_code is None:
            error_code = TransformationExecutionError.ERROR_CODE_EXECUTION_FAILED

        if details is None:
            details = {}

        if pipeline_id:
            details["pipeline_id"] = pipeline_id
        if execution_id:
            details["execution_id"] = execution_id
        if node_id:
            details["node_id"] = node_id
        if step_name:
            details["step_name"] = step_name

        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            http_status=500,
            tenant_id=tenant_id,
            user_id=user_id,
            cause=cause,
        )


class PipelineNotFoundError(TransformationError):
    """
    Exception raised when a transformation pipeline is not found.

    Used when attempting to access, update, or delete a non-existent pipeline.
    """

    ERROR_CODE_PIPELINE_NOT_FOUND = "PIPELINE_NOT_FOUND"
    ERROR_CODE_PIPELINE_DELETED = "PIPELINE_DELETED"
    ERROR_CODE_PIPELINE_ARCHIVED = "PIPELINE_ARCHIVED"

    def __init__(
        self,
        message: str,
        pipeline_id: str | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        cause: Exception | None = None,
    ):
        """
        Initialize PipelineNotFoundError.

        Args:
            message: Human-readable error message
            pipeline_id: Pipeline ID that was not found
            error_code: Machine-readable error code
            details: Additional context information
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            cause: Original exception that caused this error
        """
        if error_code is None:
            error_code = PipelineNotFoundError.ERROR_CODE_PIPELINE_NOT_FOUND

        if details is None:
            details = {}

        if pipeline_id:
            details["pipeline_id"] = pipeline_id

        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            http_status=404,
            tenant_id=tenant_id,
            user_id=user_id,
            cause=cause,
        )


class AssetCompatibilityError(TransformationError):
    """
    Exception raised when an asset is incompatible with a transformation pipeline.

    Used for schema mismatches, data type incompatibilities, and format mismatches
    between source/target assets and pipeline requirements.
    """

    ERROR_CODE_SCHEMA_INCOMPATIBLE = "SCHEMA_INCOMPATIBLE"
    ERROR_CODE_DATA_TYPE_MISMATCH = "DATA_TYPE_MISMATCH"
    ERROR_CODE_FORMAT_INCOMPATIBLE = "FORMAT_INCOMPATIBLE"
    ERROR_CODE_VERSION_MISMATCH = "VERSION_MISMATCH"
    ERROR_CODE_REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING_IN_ASSET"

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        pipeline_id: str | None = None,
        asset_id: str | None = None,
        source_asset_id: str | None = None,
        target_asset_id: str | None = None,
        field_path: str | None = None,
        expected_schema: dict[str, Any] | None = None,
        actual_schema: dict[str, Any] | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        cause: Exception | None = None,
    ):
        """
        Initialize AssetCompatibilityError.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional context information
            pipeline_id: Pipeline ID
            asset_id: Asset ID that is incompatible
            source_asset_id: Source asset ID
            target_asset_id: Target asset ID
            field_path: Path to the incompatible field
            expected_schema: Expected schema structure
            actual_schema: Actual schema structure
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            cause: Original exception that caused this error
        """
        if error_code is None:
            error_code = AssetCompatibilityError.ERROR_CODE_ASSET_INCOMPATIBLE

        if details is None:
            details = {}

        if pipeline_id:
            details["pipeline_id"] = pipeline_id
        if asset_id:
            details["asset_id"] = asset_id
        if source_asset_id:
            details["source_asset_id"] = source_asset_id
        if target_asset_id:
            details["target_asset_id"] = target_asset_id
        if field_path:
            details["field_path"] = field_path
        if expected_schema:
            details["expected_schema"] = expected_schema
        if actual_schema:
            details["actual_schema"] = actual_schema

        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            http_status=400,
            tenant_id=tenant_id,
            user_id=user_id,
            cause=cause,
        )


class ResourceQuotaExceededError(TransformationError):
    """
    Exception raised when resource quotas are exceeded.

    Used for execution time limits, memory limits, storage limits, and
    concurrent execution limits.
    """

    ERROR_CODE_EXECUTION_TIME_LIMIT = "EXECUTION_TIME_LIMIT_EXCEEDED"
    ERROR_CODE_MEMORY_LIMIT = "MEMORY_LIMIT_EXCEEDED"
    ERROR_CODE_STORAGE_LIMIT = "STORAGE_LIMIT_EXCEEDED"
    ERROR_CODE_CONCURRENT_EXECUTIONS_LIMIT = "CONCURRENT_EXECUTIONS_LIMIT_EXCEEDED"
    ERROR_CODE_NODE_COUNT_LIMIT = "NODE_COUNT_LIMIT_EXCEEDED"

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        quota_type: str | None = None,
        limit: float | None = None,
        current: float | None = None,
        pipeline_id: str | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        cause: Exception | None = None,
    ):
        """
        Initialize ResourceQuotaExceededError.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional context information
            quota_type: Type of quota exceeded (execution_time, memory, storage, etc.)
            limit: Quota limit value
            current: Current usage value
            pipeline_id: Pipeline ID (if applicable)
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            cause: Original exception that caused this error
        """
        if error_code is None:
            error_code = ResourceQuotaExceededError.ERROR_CODE_QUOTA_EXCEEDED

        if details is None:
            details = {}

        if quota_type:
            details["quota_type"] = quota_type
        if limit is not None:
            details["limit"] = limit
        if current is not None:
            details["current"] = current
        if pipeline_id:
            details["pipeline_id"] = pipeline_id

        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            http_status=429,  # Too Many Requests
            tenant_id=tenant_id,
            user_id=user_id,
            cause=cause,
        )
