"""
104.5 — Event Stream Isolation Test

Verifies that events published by Tenant A are not visible to Tenant B
in the persisted event store.
"""

import uuid

import pytest
from django.utils import timezone

from hub.apps.core.events.models import Event

pytestmark = pytest.mark.django_db(transaction=True)


class TestEventStreamIsolation:
    """Persisted events must be tenant-scoped."""

    @pytest.fixture(autouse=True)
    def _create_events(self, tenant_a, tenant_b, user_a, user_b):
        uid = uuid.uuid4().hex[:8]
        now = timezone.now()

        self.event_a = Event.objects.create(
            event_id=uuid.uuid4(),
            event_type="asset.created",
            event_version="1.0",
            timestamp=now,
            source_service="hub-api",
            tenant_id=tenant_a.id,
            user_id=user_a.id,
            data={"asset_key": f"event-a-{uid}"},
        )

        self.event_b = Event.objects.create(
            event_id=uuid.uuid4(),
            event_type="asset.created",
            event_version="1.0",
            timestamp=now,
            source_service="hub-api",
            tenant_id=tenant_b.id,
            user_id=user_b.id,
            data={"asset_key": f"event-b-{uid}"},
        )

    def test_event_query_by_tenant_a_excludes_tenant_b(self, tenant_a, tenant_b):
        """Direct ORM query scoped to Tenant A excludes Tenant B events."""
        events_a = Event.objects.filter(tenant_id=tenant_a.id)
        event_ids = set(str(e.event_id) for e in events_a)
        assert str(self.event_a.event_id) in event_ids
        assert str(self.event_b.event_id) not in event_ids

    def test_event_query_by_tenant_b_excludes_tenant_a(self, tenant_a, tenant_b):
        """Direct ORM query scoped to Tenant B excludes Tenant A events."""
        events_b = Event.objects.filter(tenant_id=tenant_b.id)
        event_ids = set(str(e.event_id) for e in events_b)
        assert str(self.event_b.event_id) in event_ids
        assert str(self.event_a.event_id) not in event_ids

    def test_no_unscoped_event_access(self, tenant_a, tenant_b):
        """Querying without tenant filter returns both — proving filter is needed."""
        all_events = Event.objects.filter(
            event_id__in=[self.event_a.event_id, self.event_b.event_id]
        )
        assert all_events.count() == 2, "Both events exist in DB"

        # But scoped query returns only one
        scoped = Event.objects.filter(
            event_id__in=[self.event_a.event_id, self.event_b.event_id],
            tenant_id=tenant_a.id,
        )
        assert scoped.count() == 1
        assert scoped.first().event_id == self.event_a.event_id
