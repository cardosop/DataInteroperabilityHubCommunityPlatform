"""
Unit tests for WebSocket mesh event publishing and replay.

Tests WebSocket event consumer handling of mesh events.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User
from hub.apps.core.events.models import Event
from hub.apps.core.events.bus import EventBus
from hub.apps.websocket.consumers.event_consumer import EventConsumer


pytestmark = pytest.mark.django_db(transaction=True)


class MeshEventWebSocketTest(TestCase):
    """Test WebSocket mesh event publishing and replay"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )

    def test_mesh_domain_created_event_published(self):
        """Test that mesh.domain.created event can be published and persisted"""
        from hub.apps.core.events.publisher import publish_event
        from django.test import override_settings

        # Use sync persistence for tests to ensure immediate persistence
        with override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False):
            event_id = publish_event(
                event_type="mesh.domain.created",
                data={
                    "domain_id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "Test Domain",
                    "status": "ACTIVE",
                    "owner_id": str(self.user.id),
                    "tenant_id": str(self.tenant.id),
                },
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

            self.assertIsNotNone(event_id)

            # Verify event was persisted (sync persistence ensures immediate persistence)
            event = Event.objects.get(event_id=event_id)
            self.assertEqual(event.event_type, "mesh.domain.created")
            self.assertEqual(event.data["domain_id"], "123e4567-e89b-12d3-a456-426614174000")
            self.assertEqual(event.data["name"], "Test Domain")

    def test_mesh_domain_updated_event_published(self):
        """Test that mesh.domain.updated event can be published and persisted"""
        from hub.apps.core.events.publisher import publish_event
        from django.test import override_settings

        # Use sync persistence for tests to ensure immediate persistence
        with override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False):
            event_id = publish_event(
                event_type="mesh.domain.updated",
                data={
                "domain_id": "123e4567-e89b-12d3-a456-426614174000",
                "changes": {"name": {"old": "Old Name", "new": "New Name"}},
                "previous_status": "ACTIVE",
                "new_status": "INACTIVE",
                "tenant_id": str(self.tenant.id),
            },
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

            self.assertIsNotNone(event_id)

            # Verify event was persisted (sync persistence ensures immediate persistence)
            event = Event.objects.get(event_id=event_id)
            self.assertEqual(event.event_type, "mesh.domain.updated")
            self.assertEqual(event.data["domain_id"], "123e4567-e89b-12d3-a456-426614174000")

    def test_mesh_policy_applied_event_published(self):
        """Test that mesh.policy.applied event can be published and persisted"""
        from hub.apps.core.events.publisher import publish_event
        from django.test import override_settings

        # Use sync persistence for tests to ensure immediate persistence
        with override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False):
            event_id = publish_event(
                event_type="mesh.policy.applied",
                data={
                    "policy_application_id": "123e4567-e89b-12d3-a456-426614174001",
                    "domain_id": "123e4567-e89b-12d3-a456-426614174000",
                    "policy_id": "123e4567-e89b-12d3-a456-426614174002",
                    "status": "APPLIED",
                    "tenant_id": str(self.tenant.id),
                },
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

            self.assertIsNotNone(event_id)

            # Verify event was persisted (sync persistence ensures immediate persistence)
            event = Event.objects.get(event_id=event_id)
            self.assertEqual(event.event_type, "mesh.policy.applied")
            self.assertEqual(event.data["policy_application_id"], "123e4567-e89b-12d3-a456-426614174001")

    def test_mesh_compliance_checked_event_published(self):
        """Test that mesh.compliance.checked event can be published and persisted"""
        from hub.apps.core.events.publisher import publish_event
        from django.test import override_settings

        # Use sync persistence for tests to ensure immediate persistence
        with override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False):
            event_id = publish_event(
                event_type="mesh.compliance.checked",
                data={
                    "domain_id": "123e4567-e89b-12d3-a456-426614174000",
                    "compliance_status": "COMPLIANT",
                    "violation_count": 0,
                    "checked_at": timezone.now().isoformat(),
                    "tenant_id": str(self.tenant.id),
                },
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

            self.assertIsNotNone(event_id)

            # Verify event was persisted (sync persistence ensures immediate persistence)
            event = Event.objects.get(event_id=event_id)
            self.assertEqual(event.event_type, "mesh.compliance.checked")
            self.assertEqual(event.data["domain_id"], "123e4567-e89b-12d3-a456-426614174000")

    def test_mesh_topology_updated_event_published(self):
        """Test that mesh.topology.updated event can be published and persisted"""
        from hub.apps.core.events.publisher import publish_event
        from django.test import override_settings

        # Use sync persistence for tests to ensure immediate persistence
        with override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False):
            event_id = publish_event(
                event_type="mesh.topology.updated",
                data={
                    "tenant_id": str(self.tenant.id),
                    "domain_count": 5,
                    "relationship_count": 10,
                    "updated_at": timezone.now().isoformat(),
                    "user_id": str(self.user.id),
                },
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

            self.assertIsNotNone(event_id)

            # Verify event was persisted (sync persistence ensures immediate persistence)
            event = Event.objects.get(event_id=event_id)
            self.assertEqual(event.event_type, "mesh.topology.updated")
            self.assertEqual(event.data["domain_count"], 5)

    def test_mesh_health_status_changed_event_published(self):
        """Test that mesh.health.status_changed event can be published and persisted"""
        from hub.apps.core.events.publisher import publish_event
        from django.test import override_settings

        # Use sync persistence for tests to ensure immediate persistence
        with override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False):
            event_id = publish_event(
                event_type="mesh.health.status_changed",
                data={
                    "domain_id": "123e4567-e89b-12d3-a456-426614174000",
                    "previous_status": "HEALTHY",
                    "new_status": "DEGRADED",
                    "health_metrics": {"cpu": 85, "memory": 70},
                    "changed_at": timezone.now().isoformat(),
                    "tenant_id": str(self.tenant.id),
                },
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

            self.assertIsNotNone(event_id)

            # Verify event was persisted (sync persistence ensures immediate persistence)
            event = Event.objects.get(event_id=event_id)
            self.assertEqual(event.event_type, "mesh.health.status_changed")
            self.assertEqual(event.data["domain_id"], "123e4567-e89b-12d3-a456-426614174000")
            self.assertEqual(event.data["new_status"], "DEGRADED")

    def test_all_mesh_event_types_have_schemas(self):
        """Test that all mesh event types have defined schemas"""
        from hub.apps.core.events.event_types import get_event_schema

        mesh_event_types = [
            "mesh.domain.created",
            "mesh.domain.updated",
            "mesh.policy.applied",
            "mesh.compliance.checked",
            "mesh.topology.updated",
            "mesh.health.status_changed",
        ]

        for event_type in mesh_event_types:
            schema = get_event_schema(event_type)
            self.assertIsNotNone(schema, f"Schema missing for {event_type}")
            self.assertIn("data", schema)

