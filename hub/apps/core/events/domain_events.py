"""
Canonical façade for ``domain.*`` events (Phase 232.0 / D232.18).

Subsystems (consent, DSAR, breach, RoPA, etc.) SHOULD publish via
:class:`DomainEventPublisher` so payloads share a single audited envelope shape
validated in :func:`hub.apps.core.events.event_types.validate_event_data`.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from hub.apps.core.events.event_types import DOMAIN_EVENT_PREFIX
from hub.apps.core.events.publisher import EventPublisher


def domain_event_type(leaf_type: str) -> str:
    """
    Normalize a leaf type into the ``domain.<bounded_context>.<verb>``
    namespace.

    Args:
        leaf_type: Segment after ``domain.`` — MUST contain at least one dot.

    Raises:
        ValueError: Invalid leaf naming.
    """
    leaf_type = leaf_type.strip().strip(".").strip()
    if leaf_type.startswith(DOMAIN_EVENT_PREFIX):
        remainder = leaf_type[len(DOMAIN_EVENT_PREFIX):]
    else:
        remainder = leaf_type
    if not remainder:
        raise ValueError("leaf_type cannot be empty")
    if "." not in remainder:
        raise ValueError(
            "domain leaf_type requires at least two segments "
            "(e.g. consent.record.revoked)"
        )
    if not remainder.replace(".", "").replace("_", "").isalnum():
        # Allow alphanumeric + dots + underscores only.
        raise ValueError("leaf_type contains illegal characters")
    return f"{DOMAIN_EVENT_PREFIX}{remainder}"


def build_domain_event_envelope(
    *,
    tenant_id: str,
    aggregate: str,
    payload: Dict[str, Any],
    schema_version: str = "1",
) -> Dict[str, Any]:
    """Return envelope dict validated by ``validate_event_data`` for domain events."""
    return {
        "tenant_id": str(tenant_id),
        "aggregate": aggregate,
        "schema_version": schema_version,
        "payload": dict(payload),
    }


class DomainEventPublisher(EventPublisher):
    """EventPublisher façade for validated ``domain.*`` envelopes."""

    def publish_domain(
        self,
        leaf_event_type: str,
        *,
        tenant_id: str,
        aggregate: str,
        payload: Dict[str, Any],
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        skip_deduplication: bool = False,
        schema_version: str = "1",
    ) -> str:
        event_type = domain_event_type(leaf_event_type)
        data = build_domain_event_envelope(
            tenant_id=tenant_id,
            aggregate=aggregate,
            payload=payload,
            schema_version=schema_version,
        )
        return self.publish(
            event_type,
            data,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            tags=tags,
            skip_deduplication=skip_deduplication,
        )
