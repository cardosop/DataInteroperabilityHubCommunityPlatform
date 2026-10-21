"""Phase 313.1.7 — event schema registration hook (pure, no Django).

Paid apps register their own event-type schemas from ready(); core keeps the
existing ``marketplace.*`` entries as the published contract.
"""

import pytest

from hub.apps.core.events.event_types import (
    EVENT_TYPE_SCHEMAS,
    get_event_schema,
    register_event_schema,
)

_TEST_TYPE = "phase313.test_event"


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    EVENT_TYPE_SCHEMAS.pop(_TEST_TYPE, None)


def test_registered_schema_resolves():
    register_event_schema(_TEST_TYPE, {"data": {"type": "object"}})
    assert get_event_schema(_TEST_TYPE) == {"data": {"type": "object"}}
    assert _TEST_TYPE in EVENT_TYPE_SCHEMAS


def test_reregistration_with_same_schema_is_idempotent():
    schema = {"data": {"type": "object"}}
    register_event_schema(_TEST_TYPE, schema)
    register_event_schema(_TEST_TYPE, schema)  # ready() reload — must not raise


def test_conflicting_schema_raises():
    register_event_schema(_TEST_TYPE, {"data": {"type": "object"}})
    with pytest.raises(ValueError, match="conflicting schema"):
        register_event_schema(_TEST_TYPE, {"data": {"type": "string"}})


def test_existing_published_marketplace_contract_untouched():
    """The 17 marketplace.* entries are the published contract — the hook
    must not require (or imply) their removal from core."""
    canonical = {
        "marketplace.connection.created",
        "marketplace.connection.deleted",
        "marketplace.connection.updated",
        "marketplace.entitlement.granted",
        "marketplace.entitlement.revoked",
        "marketplace.listing.published",
        "marketplace.listing.unpublished",
        "marketplace.mapping.created",
        "marketplace.mapping.deleted",
        "marketplace.mapping.updated",
        "marketplace.order.approved",
        "marketplace.order.created",
        "marketplace.order.fulfilled",
        "marketplace.order.rejected",
        "marketplace.sync.completed",
        "marketplace.sync.failed",
        "marketplace.sync.started",
    }
    marketplace_entries = {k for k in EVENT_TYPE_SCHEMAS if k.startswith("marketplace.")}
    assert marketplace_entries == canonical
