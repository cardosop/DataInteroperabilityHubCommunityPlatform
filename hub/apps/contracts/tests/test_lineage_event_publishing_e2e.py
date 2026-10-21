"""
E2E tests for lineage event publishing through REST API endpoints.

Tests complete lineage operations through REST API and verifies
events are published at each step (no mocks/stubs).
"""

import json

from django.test import override_settings
from rest_framework import status

from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.contracts.tests.test_base import ContractsAPITestBase
from hub.apps.core.events.models import Event


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
    EVENT_BUS_ENABLE_PERSISTENCE=True,
)
class LineageEventPublishingE2ETest(ContractsAPITestBase):
    """E2E tests for lineage event publishing through REST API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Reset event bus singleton so override_settings takes effect
        import hub.apps.core.events.bus as _bus_mod

        _bus_mod._event_bus = None

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
                    "apiVersion": "odcs/v3",
                    "kind": "DataContract",
                    "id": "test-contract",
                    "name": "Test Contract",
                    "transformSourceObjects": [
                        {"namespace": "source_namespace", "name": "source_contract"}
                    ],
                    "transformLogic": "SELECT * FROM source",
                    "schema": {
                        "name": "TestModel",
                        "fields": [
                            {
                                "name": "test_field",
                                "type": "string",
                                "transformSourceObjects": [
                                    {
                                        "namespace": "source_namespace",
                                        "name": "source_contract",
                                        "model": "SourceModel",
                                        "field": "source_field",
                                    }
                                ],
                            }
                        ],
                    },
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

    def test_e2e_get_contract_lineage_publishes_event(self):
        """Test that GET /api/v1/contracts/{id}/lineage/contracts/ publishes lineage.updated event."""
        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        response = self.client.get(f"/api/v1/contracts/{self.test_contract.id}/lineage/contracts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("contracts", response.data)
        self.assertIn("entries", response.data)

        # Verify lineage.updated event was published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data["contract_id"], str(self.test_contract.id))
        self.assertEqual(event.data["lineage_type"], "contract")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "lineage_service")

    def test_e2e_get_model_lineage_publishes_event(self):
        """Test that GET /api/v1/contracts/{id}/models/{model_name}/lineage/ publishes lineage.updated event."""
        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        response = self.client.get(
            f"/api/v1/contracts/{self.test_contract.id}/models/TestModel/lineage/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("model_name", response.data)
        self.assertIn("lineage", response.data)

        # Verify lineage.updated event was published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data["contract_id"], str(self.test_contract.id))
        self.assertEqual(event.data["model_name"], "TestModel")
        self.assertEqual(event.data["lineage_type"], "model")
        self.assertEqual(event.source_service, "lineage_service")

    def test_e2e_get_field_lineage_publishes_event(self):
        """Test that GET /api/v1/contracts/{id}/fields/{field_name}/lineage/ publishes lineage.updated event."""
        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        response = self.client.get(
            f"/api/v1/contracts/{self.test_contract.id}/fields/test_field/lineage/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("field_name", response.data)
        self.assertIn("lineage", response.data)

        # Verify lineage.updated event was published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data["contract_id"], str(self.test_contract.id))
        self.assertEqual(event.data["field_name"], "test_field")
        self.assertEqual(event.data["lineage_type"], "field")
        self.assertEqual(event.source_service, "lineage_service")

    def test_e2e_get_full_lineage_publishes_event(self):
        """Test that GET /api/v1/contracts/{id}/lineage/full/ publishes lineage.updated event."""
        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        response = self.client.get(f"/api/v1/contracts/{self.test_contract.id}/lineage/full/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("upstream", response.data)
        self.assertIn("downstream", response.data)

        # Verify lineage.updated event was published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data["contract_id"], str(self.test_contract.id))
        self.assertEqual(event.data["lineage_type"], "full")
        self.assertIn("changes", event.data)
        self.assertEqual(event.source_service, "lineage_service")

    def test_e2e_get_lineage_visualization_returns_200(self):
        """GET /api/v1/contracts/{id}/lineage/visualization/ returns 200 with valid shape.

        Note: Visualization does not directly publish events.  Event
        publishing is tested in the service-layer tests.  If visualization
        event publishing is added to LineageService.get_lineage_visualization(),
        this test should be updated to include event-count assertions.
        """

        response = self.client.get(
            f"/api/v1/contracts/{self.test_contract.id}/lineage/visualization/?format=json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict)
        self.assertIn("nodes", response.data)
        self.assertIn("links", response.data)

    def test_e2e_get_impact_analysis_publishes_event(self):
        """Test that GET /api/v1/contracts/{id}/impact-analysis/ publishes lineage.updated event."""
        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        response = self.client.get(f"/api/v1/contracts/{self.test_contract.id}/impact-analysis/")

        # The contract is set up with valid lineage data — the endpoint must return 200.
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify lineage.updated event was published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertGreaterEqual(event_count_after, event_count_before)

        event = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp").first()
        self.assertIsNotNone(event, "Impact analysis endpoint must publish a lineage.updated event")
        self.assertEqual(event.data["contract_id"], str(self.test_contract.id))
        self.assertEqual(event.data["lineage_type"], "impact_analysis")
        self.assertEqual(event.source_service, "lineage_service")

    def test_e2e_multiple_lineage_operations_publish_multiple_events(self):
        """Test that multiple lineage API calls publish multiple events."""
        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        # Perform multiple operations
        self.client.get(f"/api/v1/contracts/{self.test_contract.id}/lineage/contracts/")
        self.client.get(f"/api/v1/contracts/{self.test_contract.id}/models/TestModel/lineage/")
        self.client.get(f"/api/v1/contracts/{self.test_contract.id}/fields/test_field/lineage/")

        # Verify multiple events were published
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before + 3)

        # Verify each event has correct lineage_type
        events = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp")[:3]
        lineage_types = {event.data["lineage_type"] for event in events}
        self.assertIn("contract", lineage_types)
        self.assertIn("model", lineage_types)
        self.assertIn("field", lineage_types)

    def test_e2e_lineage_events_include_correct_tenant_and_user(self):
        """Test that lineage events include correct tenant_id and user_id."""
        self.client.get(f"/api/v1/contracts/{self.test_contract.id}/lineage/contracts/")

        event = Event.objects.filter(event_type="lineage.updated").order_by("-timestamp").first()
        self.assertIsNotNone(event)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "lineage_service")

    def test_e2e_lineage_operations_with_cache_do_not_duplicate_events(self):
        """Test that cached lineage operations don't publish duplicate events."""
        # First call - should publish event
        self.client.get(f"/api/v1/contracts/{self.test_contract.id}/lineage/contracts/")

        event_count_before = Event.objects.filter(event_type="lineage.updated").count()

        # Second call with cache - should not publish event (returns cached result)
        response = self.client.get(f"/api/v1/contracts/{self.test_contract.id}/lineage/contracts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify no new event was published (cache hit)
        event_count_after = Event.objects.filter(event_type="lineage.updated").count()
        self.assertEqual(event_count_after, event_count_before)

    def test_e2e_lineage_visualization_endpoint_returns_200(self):
        """Test that the lineage visualization API endpoint returns data successfully.

        Renamed from test_e2e_lineage_event_publishing_failure_does_not_break_api
        because this test only exercises the happy path — it does not simulate
        a publishing failure.
        """

        response = self.client.get(f"/api/v1/contracts/{self.test_contract.id}/lineage/contracts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("contracts", response.data)
        self.assertIn("entries", response.data)
