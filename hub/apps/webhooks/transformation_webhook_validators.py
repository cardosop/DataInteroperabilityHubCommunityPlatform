"""
Transformation Webhook Payload Validators

Provides comprehensive validation for transformation webhook payloads,
ensuring payloads conform to expected structure and content.
"""
import json
from typing import Any, Dict, Optional
from hub.apps.webhooks.models import WebhookEventType
from hub.apps.webhooks.odps_webhook_errors import (
    ODPSWebhookPayloadError,
    ODPSWebhookValidationError,
)

# Maximum payload size in bytes (1MB)
MAX_PAYLOAD_SIZE = 1024 * 1024


def validate_transformation_webhook_payload(
    payload: Dict[str, Any],
    event_type: str,
    tenant_id: Optional[str] = None,
    webhook_id: Optional[str] = None,
) -> None:
    """
    Validate transformation webhook payload structure and content.

    Validates:
    - Required fields are present
    - Field types are correct
    - Event data structure is valid for the event type
    - Payload size is within limits

    Args:
        payload: Webhook payload dictionary
        event_type: Transformation event type
        tenant_id: Tenant ID (for error context)
        webhook_id: Webhook ID (for error context)

    Raises:
        ODPSWebhookPayloadError: If payload validation fails
    """
    # Extract string value if event_type is a tuple (enum value)
    if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
        event_type = event_type[0]

    # Validate event type is transformation event
    if not WebhookEventType.is_transformation_event_type(event_type):
        raise ODPSWebhookValidationError(
            message=f"Event type '{event_type}' is not a transformation event type",
            error_code=ODPSWebhookValidationError.ERROR_CODE_INVALID_EVENT_TYPE,
            user_message=f"Invalid event type: '{event_type}' is not a valid transformation event type",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
        )

    # Validate payload is a dictionary
    if not isinstance(payload, dict):
        raise ODPSWebhookPayloadError(
            message=f"Payload must be a dictionary, got {type(payload).__name__}",
            error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_PAYLOAD_STRUCTURE,
            user_message="Webhook payload must be a valid JSON object",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
            actual=type(payload).__name__,
            expected="dict",
        )

    # Validate payload size
    try:
        payload_json = json.dumps(payload, sort_keys=True)
        payload_size = len(payload_json.encode('utf-8'))
        if payload_size > MAX_PAYLOAD_SIZE:
            raise ODPSWebhookPayloadError(
                message=f"Payload size ({payload_size} bytes) exceeds maximum ({MAX_PAYLOAD_SIZE} bytes)",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_PAYLOAD_TOO_LARGE,
                user_message=f"Webhook payload is too large ({payload_size} bytes). Maximum size is {MAX_PAYLOAD_SIZE} bytes",
                tenant_id=tenant_id,
                webhook_id=webhook_id,
                event_type=event_type,
                payload_size=payload_size,
                max_payload_size=MAX_PAYLOAD_SIZE,
            )
    except (TypeError, ValueError) as e:
        raise ODPSWebhookPayloadError(
            message=f"Failed to serialize payload for size validation: {str(e)}",
            error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_PAYLOAD_STRUCTURE,
            user_message="Webhook payload cannot be serialized",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
            cause=e,
        )

    # Validate required base fields
    required_fields = ["event_type", "resource_type", "resource_id", "timestamp", "data"]
    for field in required_fields:
        if field not in payload:
            raise ODPSWebhookPayloadError(
                message=f"Missing required field: {field}",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                user_message=f"Webhook payload is missing required field: {field}",
                tenant_id=tenant_id,
                webhook_id=webhook_id,
                event_type=event_type,
                field_path=field,
                expected="present",
                actual="missing",
            )

    # Validate event_type matches
    # Extract string value from payload event_type if it's a tuple
    payload_event_type = payload["event_type"]
    if isinstance(payload_event_type, (tuple, list)) and len(payload_event_type) > 0:
        payload_event_type = payload_event_type[0]

    if payload_event_type != event_type:
        raise ODPSWebhookPayloadError(
            message=f"Payload event_type '{payload_event_type}' does not match expected '{event_type}'",
            error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_VALUE,
            user_message=f"Webhook payload event type mismatch: expected '{event_type}', got '{payload_event_type}'",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
            field_path="event_type",
            expected=event_type,
            actual=payload_event_type,
        )

    # Validate field types
    if not isinstance(payload["resource_type"], str):
        raise ODPSWebhookPayloadError(
            message=f"resource_type must be a string, got {type(payload['resource_type']).__name__}",
            error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
            user_message="Webhook payload resource_type must be a string",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
            field_path="resource_type",
            expected="str",
            actual=type(payload["resource_type"]).__name__,
        )

    if not isinstance(payload["resource_id"], str):
        raise ODPSWebhookPayloadError(
            message=f"resource_id must be a string, got {type(payload['resource_id']).__name__}",
            error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
            user_message="Webhook payload resource_id must be a string",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
            field_path="resource_id",
            expected="str",
            actual=type(payload["resource_id"]).__name__,
        )

    if not isinstance(payload["timestamp"], str):
        raise ODPSWebhookPayloadError(
            message=f"timestamp must be a string, got {type(payload['timestamp']).__name__}",
            error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
            user_message="Webhook payload timestamp must be a string (ISO 8601 format)",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
            field_path="timestamp",
            expected="str",
            actual=type(payload["timestamp"]).__name__,
        )

    if not isinstance(payload["data"], dict):
        raise ODPSWebhookPayloadError(
            message=f"data must be a dictionary, got {type(payload['data']).__name__}",
            error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
            user_message="Webhook payload data must be a JSON object",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
            field_path="data",
            expected="dict",
            actual=type(payload["data"]).__name__,
        )

    # Validate event data based on event type
    validate_transformation_event_data(payload["data"], event_type, tenant_id, webhook_id)


def validate_transformation_event_data(
    event_data: Dict[str, Any],
    event_type: str,
    tenant_id: Optional[str] = None,
    webhook_id: Optional[str] = None,
) -> None:
    """
    Validate transformation event data based on event type.

    Args:
        event_data: Event data dictionary
        event_type: Transformation event type
        tenant_id: Tenant ID (for error context)
        webhook_id: Webhook ID (for error context)

    Raises:
        ODPSWebhookPayloadError: If event data validation fails
    """
    if not isinstance(event_data, dict):
        raise ODPSWebhookPayloadError(
            message=f"Event data must be a dictionary, got {type(event_data).__name__}",
            error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_EVENT_DATA,
            user_message="Transformation event data must be a JSON object",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
            field_path="data",
            expected="dict",
            actual=type(event_data).__name__,
        )

    # Event-specific validation
    if event_type == WebhookEventType.PIPELINE_CREATED:
        _validate_pipeline_created_data(event_data, tenant_id, webhook_id, event_type)
    elif event_type == WebhookEventType.PIPELINE_UPDATED:
        _validate_pipeline_updated_data(event_data, tenant_id, webhook_id, event_type)
    elif event_type == WebhookEventType.PIPELINE_DELETED:
        _validate_pipeline_deleted_data(event_data, tenant_id, webhook_id, event_type)
    elif event_type == WebhookEventType.PIPELINE_EXECUTION_STARTED:
        _validate_pipeline_execution_started_data(event_data, tenant_id, webhook_id, event_type)
    elif event_type == WebhookEventType.PIPELINE_EXECUTION_COMPLETED:
        _validate_pipeline_execution_completed_data(event_data, tenant_id, webhook_id, event_type)
    elif event_type == WebhookEventType.PIPELINE_EXECUTION_FAILED:
        _validate_pipeline_execution_failed_data(event_data, tenant_id, webhook_id, event_type)
    elif event_type == WebhookEventType.PREVIEW_GENERATED:
        _validate_preview_generated_data(event_data, tenant_id, webhook_id, event_type)
    elif event_type == WebhookEventType.WRANGLING_COMPLETED:
        _validate_wrangling_completed_data(event_data, tenant_id, webhook_id, event_type)


def _validate_pipeline_created_data(
    event_data: Dict[str, Any],
    tenant_id: Optional[str],
    webhook_id: Optional[str],
    event_type: str,
) -> None:
    """Validate data for pipeline.created event"""
    if "pipeline_id" in event_data and not isinstance(event_data["pipeline_id"], str):
        raise ODPSWebhookPayloadError(
            message="pipeline_id must be a string",
            error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
            user_message="Pipeline created event data: pipeline_id must be a string",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
            field_path="data.pipeline_id",
            expected="str",
            actual=type(event_data["pipeline_id"]).__name__,
        )


def _validate_pipeline_updated_data(
    event_data: Dict[str, Any],
    tenant_id: Optional[str],
    webhook_id: Optional[str],
    event_type: str,
) -> None:
    """Validate data for pipeline.updated event"""
    if "pipeline_id" in event_data and not isinstance(event_data["pipeline_id"], str):
        raise ODPSWebhookPayloadError(
            message="pipeline_id must be a string",
            error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
            user_message="Pipeline updated event data: pipeline_id must be a string",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
            field_path="data.pipeline_id",
            expected="str",
            actual=type(event_data["pipeline_id"]).__name__,
        )


def _validate_pipeline_deleted_data(
    event_data: Dict[str, Any],
    tenant_id: Optional[str],
    webhook_id: Optional[str],
    event_type: str,
) -> None:
    """Validate data for pipeline.deleted event"""
    # No specific required fields for deleted events
    pass


def _validate_pipeline_execution_started_data(
    event_data: Dict[str, Any],
    tenant_id: Optional[str],
    webhook_id: Optional[str],
    event_type: str,
) -> None:
    """Validate data for pipeline.execution.started event"""
    required_fields = ["pipeline_id", "execution_id"]
    for field in required_fields:
        if field not in event_data:
            raise ODPSWebhookPayloadError(
                message=f"Missing required field: {field}",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                user_message=f"Pipeline execution started event data: {field} is required",
                tenant_id=tenant_id,
                webhook_id=webhook_id,
                event_type=event_type,
                field_path=f"data.{field}",
                expected="present",
                actual="missing",
            )
        if not isinstance(event_data[field], str):
            raise ODPSWebhookPayloadError(
                message=f"{field} must be a string",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
                user_message=f"Pipeline execution started event data: {field} must be a string",
                tenant_id=tenant_id,
                webhook_id=webhook_id,
                event_type=event_type,
                field_path=f"data.{field}",
                expected="str",
                actual=type(event_data[field]).__name__,
            )


def _validate_pipeline_execution_completed_data(
    event_data: Dict[str, Any],
    tenant_id: Optional[str],
    webhook_id: Optional[str],
    event_type: str,
) -> None:
    """Validate data for pipeline.execution.completed event"""
    required_fields = ["pipeline_id", "execution_id"]
    for field in required_fields:
        if field not in event_data:
            raise ODPSWebhookPayloadError(
                message=f"Missing required field: {field}",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                user_message=f"Pipeline execution completed event data: {field} is required",
                tenant_id=tenant_id,
                webhook_id=webhook_id,
                event_type=event_type,
                field_path=f"data.{field}",
                expected="present",
                actual="missing",
            )
        if not isinstance(event_data[field], str):
            raise ODPSWebhookPayloadError(
                message=f"{field} must be a string",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
                user_message=f"Pipeline execution completed event data: {field} must be a string",
                tenant_id=tenant_id,
                webhook_id=webhook_id,
                event_type=event_type,
                field_path=f"data.{field}",
                expected="str",
                actual=type(event_data[field]).__name__,
            )


def _validate_pipeline_execution_failed_data(
    event_data: Dict[str, Any],
    tenant_id: Optional[str],
    webhook_id: Optional[str],
    event_type: str,
) -> None:
    """Validate data for pipeline.execution.failed event"""
    required_fields = ["pipeline_id", "execution_id", "error_message"]
    for field in required_fields:
        if field not in event_data:
            raise ODPSWebhookPayloadError(
                message=f"Missing required field: {field}",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                user_message=f"Pipeline execution failed event data: {field} is required",
                tenant_id=tenant_id,
                webhook_id=webhook_id,
                event_type=event_type,
                field_path=f"data.{field}",
                expected="present",
                actual="missing",
            )
        if not isinstance(event_data[field], str):
            raise ODPSWebhookPayloadError(
                message=f"{field} must be a string",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
                user_message=f"Pipeline execution failed event data: {field} must be a string",
                tenant_id=tenant_id,
                webhook_id=webhook_id,
                event_type=event_type,
                field_path=f"data.{field}",
                expected="str",
                actual=type(event_data[field]).__name__,
            )


def _validate_preview_generated_data(
    event_data: Dict[str, Any],
    tenant_id: Optional[str],
    webhook_id: Optional[str],
    event_type: str,
) -> None:
    """Validate data for preview.generated event"""
    required_fields = ["pipeline_id", "asset_id", "preview_id"]
    for field in required_fields:
        if field not in event_data:
            raise ODPSWebhookPayloadError(
                message=f"Missing required field: {field}",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                user_message=f"Preview generated event data: {field} is required",
                tenant_id=tenant_id,
                webhook_id=webhook_id,
                event_type=event_type,
                field_path=f"data.{field}",
                expected="present",
                actual="missing",
            )
        if not isinstance(event_data[field], str):
            raise ODPSWebhookPayloadError(
                message=f"{field} must be a string",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
                user_message=f"Preview generated event data: {field} must be a string",
                tenant_id=tenant_id,
                webhook_id=webhook_id,
                event_type=event_type,
                field_path=f"data.{field}",
                expected="str",
                actual=type(event_data[field]).__name__,
            )


def _validate_wrangling_completed_data(
    event_data: Dict[str, Any],
    tenant_id: Optional[str],
    webhook_id: Optional[str],
    event_type: str,
) -> None:
    """Validate data for wrangling.completed event"""
    required_fields = ["session_id", "operation_id", "asset_id", "operation_type"]
    for field in required_fields:
        if field not in event_data:
            raise ODPSWebhookPayloadError(
                message=f"Missing required field: {field}",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                user_message=f"Wrangling completed event data: {field} is required",
                tenant_id=tenant_id,
                webhook_id=webhook_id,
                event_type=event_type,
                field_path=f"data.{field}",
                expected="present",
                actual="missing",
            )
        if not isinstance(event_data[field], str):
            raise ODPSWebhookPayloadError(
                message=f"{field} must be a string",
                error_code=ODPSWebhookPayloadError.ERROR_CODE_INVALID_FIELD_TYPE,
                user_message=f"Wrangling completed event data: {field} must be a string",
                tenant_id=tenant_id,
                webhook_id=webhook_id,
                event_type=event_type,
                field_path=f"data.{field}",
                expected="str",
                actual=type(event_data[field]).__name__,
            )

