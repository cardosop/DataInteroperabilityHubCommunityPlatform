"""
Event Schema Definitions

Defines JSON Schema for all system events to ensure consistency and validation.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

# Import CURRENT_EVENT_VERSION early to avoid circular import issues
from .event_types import CURRENT_EVENT_VERSION

# Base event schema (JSON Schema)
BASE_EVENT_SCHEMA = {
    "type": "object",
    "required": ["event_id", "event_type", "event_version", "timestamp", "source", "data"],
    "properties": {
        "event_id": {
            "type": "string",
            "format": "uuid",
            "description": "Unique identifier for this event instance",
        },
        "event_type": {
            "type": "string",
            "pattern": "^[a-z]+\\.[a-z_]+(\\.[a-z_]+)*$",
            "description": "Event type in dot notation (e.g., 'contract.created', 'asset.activated')",
        },
        "event_version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
            "description": "Schema version (semantic versioning)",
        },
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601 timestamp when event occurred",
        },
        "source": {
            "type": "object",
            "required": ["service", "tenant_id"],
            "properties": {
                "service": {"type": "string", "description": "Service that generated the event"},
                "tenant_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Tenant UUID (null for system events)",
                },
                "user_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "User UUID who triggered the event (optional)",
                },
                "request_id": {
                    "type": "string",
                    "description": "Request ID for tracing (optional)",
                },
            },
        },
        "data": {"type": "object", "description": "Event-specific data payload"},
        "metadata": {
            "type": "object",
            "description": "Additional metadata (tags, correlation_id, etc.)",
            "properties": {
                "correlation_id": {
                    "type": "string",
                    "description": "Correlation ID for tracing related events",
                },
                "causation_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Event ID that caused this event",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for filtering and categorization",
                },
            },
        },
    },
}


class EventSchema:
    """Event schema validator and builder."""

    @staticmethod
    def validate_event(event: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate event against base schema.

        Args:
            event: Event dictionary to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        required_fields = ["event_id", "event_type", "event_version", "timestamp", "source", "data"]
        for field in required_fields:
            if field not in event:
                return False, f"Missing required field: {field}"

        # Validate event_id is UUID
        try:
            uuid.UUID(event["event_id"])
        except (ValueError, TypeError):
            return False, "event_id must be a valid UUID"

        # Validate timestamp is ISO 8601
        try:
            datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return False, "timestamp must be a valid ISO 8601 datetime"

        # Validate event_type format
        import re

        if not re.match(r"^[a-z]+\.[a-z_]+(\.[a-z_]+)*$", event["event_type"]):
            return False, "event_type must match pattern: 'domain.action' or 'domain.entity.action'"

        # Validate event_version is semantic version
        if not re.match(r"^\d+\.\d+\.\d+$", event["event_version"]):
            return False, "event_version must be semantic version (e.g., '1.0.0')"

        # Validate source
        if not isinstance(event["source"], dict):
            return False, "source must be an object"

        if "service" not in event["source"]:
            return False, "source.service is required"

        if "tenant_id" not in event["source"]:
            return False, "source.tenant_id is required"

        # Validate tenant_id is UUID or null
        tenant_id = event["source"]["tenant_id"]
        if tenant_id is not None:
            try:
                uuid.UUID(str(tenant_id))
            except (ValueError, TypeError):
                return False, "source.tenant_id must be a valid UUID or null"

        return True, None

    @staticmethod
    def build_event(
        event_type: str,
        data: dict[str, Any],
        tenant_id: str | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        tags: list[str] | None = None,
        event_version: str = CURRENT_EVENT_VERSION,
        service_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Build a valid event dictionary.

        Args:
            event_type: Event type (e.g., 'contract.created')
            data: Event data payload
            tenant_id: Tenant UUID (optional)
            user_id: User UUID (optional)
            request_id: Request ID for tracing (optional)
            correlation_id: Correlation ID for tracing (optional)
            causation_id: Event ID that caused this event (optional)
            tags: Tags for filtering (optional)
            event_version: Schema version (default: '1.0.0')
            service_name: Service name publishing the event (default: 'hub')

        Returns:
            Valid event dictionary
        """
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "event_version": event_version,
            "timestamp": datetime.now(UTC).isoformat(),
            "source": {
                "service": service_name or "hub",
                "tenant_id": tenant_id,
            },
            "data": data,
        }

        if user_id:
            event["source"]["user_id"] = user_id

        if request_id:
            event["source"]["request_id"] = request_id

        metadata = {}
        if correlation_id:
            metadata["correlation_id"] = correlation_id
        if causation_id:
            metadata["causation_id"] = causation_id
        if tags:
            metadata["tags"] = tags

        if metadata:
            event["metadata"] = metadata

        return event


# Import event type schemas from event_types module
from .event_types import (
    get_event_schema as _get_event_schema,
)


def get_event_schema(event_type: str) -> dict[str, Any]:
    """
    Get schema for specific event type.

    Args:
        event_type: Event type (e.g., 'contract.created')

    Returns:
        Event schema dictionary (merged with base schema)
    """
    schema = BASE_EVENT_SCHEMA.copy()
    type_schema = _get_event_schema(event_type)
    if type_schema:
        # Merge event type-specific schema with base schema
        schema["properties"]["data"] = {**schema["properties"]["data"], **type_schema["data"]}
    return schema
