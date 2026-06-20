"""
Integration tests for LineageService event publishing.

Tests event publishing using real LineageService and EventBus (no mocks/stubs).
All tests use real services and models following engineering best practices.
"""

import json

from django.test import override_settings

from hub.apps.contracts.lineage_service import LineageService
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.contracts.tests.test_base import ContractsTestBase
from hub.apps.core.events.models import Event


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
    EVENT_BUS_ENABLE_PERSISTENCE=True,
)
class LineageServiceEventPublishingTest(ContractsTestBase):
    """Integration tests for LineageService event publishing using real EventPublisher."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Reset event bus singleton so override_settings takes effect
        import hub.apps.core.events.bus as _bus_mod

        _bus_mod._event_bus = None

        self.service = LineageService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create a test contract with lineage
        self.test_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=None,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(
                {
                    "info": {"name": "test_contract", "namespace": "test_namespace"},
                    "lineage": {
                        "contracts": [{"namespace": "source_namespace", "name": "source_contract"}],
                        "entries": [
                            {
                                "input_fields": [
                                    {
                                        "namespace": "source_namespace",
                                        "name": "source_contract",
                                        "model": "SourceModel",
                                        "field": "source_field",
                                    }
                                ]
                            }
                        ],
                    },
                    "models": [
                        {
                            "name": "TestModel",
                            "fields": [
                                {
                                    "name": "test_field",
                                    "lineage": {
                                        "input_fields": [
                                            {
                                                "namespace": "source_namespace",
                                                "name": "source_contract",
                                                "model": "SourceModel",
                                                "field": "source_field",
                                            }
                                        ]
                                    },
                                }
                            ],
                        }
                    ],
                }
            ),
            hub_contract_json={
                "info": {"name": "test_contract", "namespace": "test_namespace"},
                "lineage": {
                    "contracts": [{"namespace": "source_namespace", "name": "source_contract"}],
                    "entries": [
                        {
                            "input_fields": [
                                {
                                    "namespace": "source_namespace",
                                    "name": "source_contract",
                                    "model": "SourceModel",
                                    "field": "source_field",
                                }
                            ]
                        }
                    ],
                },
                "models": [
                    {
                        "name": "TestModel",
                        "lineage": {
                            "models": [
                                {
                                    "namespace": "source_namespace",
                                    "name": "source_contract",
                                    "model": "SourceModel",
                                }
                            ],
                            "entries": [],
                        },
                        "fields": [
                            {
                                "name": "test_field",
                                "lineage": {
                                    "input_fields": [
                                        {
                                            "namespace": "source_namespace",
                                            "name": "source_contract",
                                            "model": "SourceModel",
                                            "field": "source_field",
                                        }
                                    ],
                                    "transformations": [],
                                },
                            }
                        ],
                    }
                ],
            },
        )

    def test_get_contract_lineage_publishes_updated_event(self):
        """Test that get_contract_lineage() publishes lineage.updated event."""
        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        result = self.service.get_contract_lineage(
            contract_id=str(self.test_contract.id), use_cache=False
        )

        # Verify lineage was retrieved
        self.assertIn("contracts", result)
        self.assertIn("entries", result)

        # Verify lineage.updated event was published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data["contract_id"], str(self.test_contract.id))
        self.assertEqual(event.data["lineage_type"], "contract")
        self.assertIsNotNone(event.data.get("relationship_count"))
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))

    def test_get_model_lineage_publishes_updated_event(self):
        """Test that get_model_lineage() publishes lineage.updated event."""
        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        result = self.service.get_model_lineage(
            contract_id=str(self.test_contract.id), model_name="TestModel", use_cache=False
        )

        # Verify lineage was retrieved
        self.assertIn("model_name", result)
        self.assertIn("lineage", result)

        # Verify lineage.updated event was published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data["contract_id"], str(self.test_contract.id))
        self.assertEqual(event.data["model_name"], "TestModel")
        self.assertEqual(event.data["lineage_type"], "model")
        self.assertIsNotNone(event.data.get("relationship_count"))

    def test_get_field_lineage_publishes_updated_event(self):
        """Test that get_field_lineage() publishes lineage.updated event."""
        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        result = self.service.get_field_lineage(
            contract_id=str(self.test_contract.id),
            field_name="test_field",
            model_name="TestModel",
            use_cache=False,
        )

        # Verify lineage was retrieved
        self.assertIn("field_name", result)
        self.assertIn("lineage", result)

        # Verify lineage.updated event was published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data["contract_id"], str(self.test_contract.id))
        self.assertEqual(event.data["model_name"], "TestModel")
        self.assertEqual(event.data["field_name"], "test_field")
        self.assertEqual(event.data["lineage_type"], "field")
        self.assertIsNotNone(event.data.get("relationship_count"))

    def test_get_full_lineage_publishes_updated_event(self):
        """Test that get_full_lineage() publishes lineage.updated event."""
        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        result = self.service.get_full_lineage(
            contract_id=str(self.test_contract.id), use_cache=False
        )

        # Verify lineage was retrieved
        self.assertIn("upstream", result)
        self.assertIn("downstream", result)

        # Verify lineage.updated event was published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data["contract_id"], str(self.test_contract.id))
        self.assertEqual(event.data["lineage_type"], "full")
        self.assertIsNotNone(event.data.get("relationship_count"))
        self.assertIn("changes", event.data)
        self.assertIn("upstream_count", event.data["changes"])
        self.assertIn("downstream_count", event.data["changes"])

    def test_analyze_impact_publishes_updated_event(self):
        """Test that analyze_impact() publishes lineage.updated event."""
        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        result = self.service.analyze_impact(contract_id=str(self.test_contract.id))

        # Verify impact analysis was performed
        self.assertIsNotNone(result)

        # Verify lineage.updated event was published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data["contract_id"], str(self.test_contract.id))
        self.assertEqual(event.data["lineage_type"], "impact_analysis")
        self.assertIsNotNone(event.data.get("relationship_count"))
        self.assertIn("changes", event.data)
        self.assertIn("impact_score", event.data["changes"])

    def test_get_contract_lineage_handles_event_publishing_failure_gracefully(self):
        """Test that get_contract_lineage() handles event publishing failures gracefully."""
        # Mock event publishing to fail
        original_publish = self.service.publish_lineage_updated

        def failing_publish(*args, **kwargs):
            raise Exception("Event publishing failed")

        self.service.publish_lineage_updated = failing_publish

        # Operation should still succeed
        result = self.service.get_contract_lineage(
            contract_id=str(self.test_contract.id), use_cache=False
        )

        self.assertIn("contracts", result)
        self.assertIn("entries", result)

        # Restore original method
        self.service.publish_lineage_updated = original_publish

    def test_event_source_includes_tenant_and_user(self):
        """Test that events include tenant_id and user_id in source."""
        self.service.get_contract_lineage(contract_id=str(self.test_contract.id), use_cache=False)

        event = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp").first()
        self.assertIsNotNone(event)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "lineage_service")

    def test_multiple_lineage_operations_publish_multiple_events(self):
        """Test that multiple lineage operations publish multiple events."""
        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        # Perform multiple operations
        self.service.get_contract_lineage(contract_id=str(self.test_contract.id), use_cache=False)
        self.service.get_model_lineage(
            contract_id=str(self.test_contract.id), model_name="TestModel", use_cache=False
        )
        self.service.get_field_lineage(
            contract_id=str(self.test_contract.id),
            field_name="test_field",
            model_name="TestModel",
            use_cache=False,
        )

        # Verify multiple events were published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before + 3)

        # Verify each event has correct lineage_type
        events = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp")[:3]
        lineage_types = {event.data["lineage_type"] for event in events}
        self.assertIn("contract", lineage_types)
        self.assertIn("model", lineage_types)
        self.assertIn("field", lineage_types)

    def test_get_contract_lineage_with_cache_does_not_publish_event(self):
        """Test that get_contract_lineage() with cache hit does not publish event."""
        # First call - should publish event
        self.service.get_contract_lineage(contract_id=str(self.test_contract.id), use_cache=True)

        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        # Second call with cache - should not publish event (returns cached result)
        result = self.service.get_contract_lineage(
            contract_id=str(self.test_contract.id), use_cache=True
        )

        # Verify result is returned
        self.assertIn("contracts", result)

        # Verify no new event was published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before)

    def test_get_model_lineage_with_cache_does_not_publish_event(self):
        """Test that get_model_lineage() with cache hit does not publish event."""
        # First call - should publish event
        self.service.get_model_lineage(
            contract_id=str(self.test_contract.id), model_name="TestModel", use_cache=True
        )

        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        # Second call with cache - should not publish event (returns cached result)
        result = self.service.get_model_lineage(
            contract_id=str(self.test_contract.id), model_name="TestModel", use_cache=True
        )

        # Verify result is returned
        self.assertIn("model_name", result)

        # Verify no new event was published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before)
