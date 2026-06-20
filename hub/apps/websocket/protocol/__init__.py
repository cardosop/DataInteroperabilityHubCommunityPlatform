"""
WebSocket Protocol Definitions

Defines the message protocol for WebSocket communication.
"""

import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class WebSocketMessageType(str, Enum):
    """WebSocket message types."""

    # Client to server
    AUTHENTICATE = "authenticate"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    LIST_SUBSCRIPTIONS = "list_subscriptions"
    PING = "ping"

    # Server to client
    AUTH_CONFIRMED = "auth_confirmed"
    EVENT = "event"
    SUBSCRIPTION_CONFIRMED = "subscription_confirmed"
    SUBSCRIPTION_ERROR = "subscription_error"
    SUBSCRIPTIONS_LIST = "subscriptions_list"
    ERROR = "error"
    PONG = "pong"


@dataclass
class WebSocketMessage:
    """WebSocket message structure."""

    type: str
    data: dict[str, Any] | None = None
    error: str | None = None
    request_id: str | None = None
    timestamp: str | None = None

    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(asdict(self), default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "WebSocketMessage":
        """Create message from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class SubscribeMessage:
    """Subscribe message structure."""

    event_types: list[str]
    filters: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {"event_types": self.event_types}
        if self.filters:
            result["filters"] = self.filters
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubscribeMessage":
        """Create from dictionary."""
        return cls(
            event_types=data.get("event_types", []),
            filters=data.get("filters"),
        )


@dataclass
class EventMessage:
    """Event message structure."""

    event_id: str
    event_type: str
    event_version: str
    timestamp: str
    source: dict[str, Any]
    data: dict[str, Any]
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "timestamp": self.timestamp,
            "source": self.source,
            "data": self.data,
        }
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventMessage":
        """Create from dictionary."""
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            event_version=data["event_version"],
            timestamp=data["timestamp"],
            source=data["source"],
            data=data["data"],
            metadata=data.get("metadata"),
        )
