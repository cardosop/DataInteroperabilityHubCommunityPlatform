"""
Unit tests for SearchEventPublisher.

Tests event publishing using real EventPublisher and EventBus (no mocks/stubs).
All tests use real services and models following engineering best practices.
"""

from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.core.events.models import Event
from hub.apps.core.events.service_publishers import SearchEventPublisher
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus
import uuid


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
    EVENT_BUS_FORCE_SYNC_PERSISTENCE=True,  # Force synchronous persistence so Event.objects.get() sees rows
)
class SearchEventPublisherTest(TestCase):
    """Unit tests for SearchEventPublisher using real EventPublisher."""

    def setUp(self):
        """Set up test fixtures.

        Reset the global event bus singleton so that the overridden
        EVENT_BUS_FORCE_SYNC_PERSISTENCE setting takes effect for this
        test class.  Flush Redis deduplication keys so that events with
        identical payloads from previous runs are not silently skipped.
        """
        import hub.apps.core.events.bus as bus_module
        bus_module._event_bus = None

        # Flush Redis dedup keys so events are persisted fresh each run
        try:
            from hub.apps.core.events.deduplication import get_redis_client, DEDUPLICATION_KEY_PREFIX
            redis_client = get_redis_client()
            if redis_client:
                for key in redis_client.scan_iter(f"{DEDUPLICATION_KEY_PREFIX}:*"):
                    redis_client.delete(key)
        except Exception:
            pass

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create a test service with SearchEventPublisher
        class _SearchServiceStub(SearchEventPublisher):
            def __init__(self, tenant_id=None, user_id=None):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__(tenant_id=tenant_id, user_id=user_id)

        self.service = _SearchServiceStub(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def tearDown(self):
        """Reset global event bus singleton after tests."""
        import hub.apps.core.events.bus as bus_module
        bus_module._event_bus = None

    def test_publish_search_query_event(self):
        """Test publishing search.query event with real EventPublisher."""
        event_id = self.service.publish_search_query(
            query="test query",
            query_type="full_text",
            filters={"resource_type": "CONTRACT"},
            result_count=10,
            no_results=False,
            execution_time_ms=150,
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted to database
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "search.query")
        self.assertEqual(event.data["query"], "test query")
        self.assertEqual(event.data["query_type"], "full_text")
        self.assertEqual(event.data["filters"], {"resource_type": "CONTRACT"})
        self.assertEqual(event.data["result_count"], 10)
        self.assertEqual(event.data["no_results"], False)
        self.assertEqual(event.data["execution_time_ms"], 150)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "search_service")

    def test_publish_search_query_with_minimal_data(self):
        """Test publishing search.query event with only required fields."""
        event_id = self.service.publish_search_query(query="minimal query")

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "search.query")
        self.assertEqual(event.data["query"], "minimal query")
        self.assertIsNone(event.data.get("query_type"))
        self.assertEqual(event.data["filters"], {})
        self.assertIsNone(event.data.get("result_count"))
        self.assertIsNone(event.data.get("no_results"))
        self.assertIsNone(event.data.get("execution_time_ms"))

    def test_publish_search_query_with_no_results(self):
        """Test publishing search.query event with no results."""
        event_id = self.service.publish_search_query(
            query="no results query", result_count=0, no_results=True, execution_time_ms=50
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "search.query")
        self.assertEqual(event.data["query"], "no results query")
        self.assertEqual(event.data["result_count"], 0)
        self.assertEqual(event.data["no_results"], True)
        self.assertEqual(event.data["execution_time_ms"], 50)

    def test_publish_index_updated_event(self):
        """Test publishing search.index.updated event with real EventPublisher."""
        event_id = self.service.publish_index_updated(
            resource_type="CONTRACT",
            resource_id="test-resource-id-123",
            index_id="index-123",
            title="Test Contract Title",
            update_type="updated",
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted to database
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "search.index.updated")
        self.assertEqual(event.data["resource_type"], "CONTRACT")
        self.assertEqual(event.data["resource_id"], "test-resource-id-123")
        self.assertEqual(event.data["index_id"], "index-123")
        self.assertEqual(event.data["title"], "Test Contract Title")
        self.assertEqual(event.data["update_type"], "updated")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "search_service")

    def test_publish_index_updated_with_minimal_data(self):
        """Test publishing search.index.updated event with only required fields."""
        event_id = self.service.publish_index_updated(
            resource_type="ASSET", resource_id="asset-123"
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "search.index.updated")
        self.assertEqual(event.data["resource_type"], "ASSET")
        self.assertEqual(event.data["resource_id"], "asset-123")
        self.assertIsNone(event.data.get("index_id"))
        self.assertIsNone(event.data.get("title"))
        self.assertIsNone(event.data.get("update_type"))

    def test_publish_index_updated_with_created_type(self):
        """Test publishing search.index.updated event with update_type='created'."""
        event_id = self.service.publish_index_updated(
            resource_type="DATASET", resource_id="dataset-456", update_type="created"
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "search.index.updated")
        self.assertEqual(event.data["update_type"], "created")

    def test_publish_index_updated_with_deleted_type(self):
        """Test publishing search.index.updated event with update_type='deleted'."""
        event_id = self.service.publish_index_updated(
            resource_type="CONTRACT", resource_id="contract-789", update_type="deleted"
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "search.index.updated")
        self.assertEqual(event.data["update_type"], "deleted")

    def test_publish_index_rebuilt_event(self):
        """Test publishing search.index.rebuilt event with real EventPublisher."""
        event_id = self.service.publish_index_rebuilt(
            tenant_id=str(self.tenant.id),
            resource_count=1000,
            duration_ms=5000,
            resource_types=["CONTRACT", "ASSET", "DATASET"],
            success=True,
            errors=[],
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted to database
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "search.index.rebuilt")
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        self.assertEqual(event.data["resource_count"], 1000)
        self.assertEqual(event.data["duration_ms"], 5000)
        self.assertEqual(event.data["resource_types"], ["CONTRACT", "ASSET", "DATASET"])
        self.assertEqual(event.data["success"], True)
        self.assertEqual(event.data["errors"], [])
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "search_service")

    def test_publish_index_rebuilt_with_minimal_data(self):
        """Test publishing search.index.rebuilt event with only required fields."""
        event_id = self.service.publish_index_rebuilt(tenant_id=str(self.tenant.id))

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "search.index.rebuilt")
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        self.assertIsNone(event.data.get("resource_count"))
        self.assertIsNone(event.data.get("duration_ms"))
        self.assertEqual(event.data["resource_types"], [])
        self.assertIsNone(event.data.get("success"))
        self.assertEqual(event.data["errors"], [])

    def test_publish_index_rebuilt_with_failure(self):
        """Test publishing search.index.rebuilt event with failure."""
        errors = ["Error 1", "Error 2"]
        event_id = self.service.publish_index_rebuilt(
            tenant_id=str(self.tenant.id),
            resource_count=500,
            duration_ms=3000,
            success=False,
            errors=errors,
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "search.index.rebuilt")
        self.assertEqual(event.data["success"], False)
        self.assertEqual(event.data["errors"], errors)

    def test_publish_index_rebuilt_with_partial_success(self):
        """Test publishing search.index.rebuilt event with partial success."""
        event_id = self.service.publish_index_rebuilt(
            tenant_id=str(self.tenant.id),
            resource_count=750,
            duration_ms=4000,
            resource_types=["CONTRACT", "ASSET"],
            success=True,
            errors=["Warning: Some resources skipped"],
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "search.index.rebuilt")
        self.assertEqual(event.data["success"], True)
        self.assertEqual(event.data["errors"], ["Warning: Some resources skipped"])

    def test_event_source_includes_tenant_and_user(self):
        """Test that events include tenant_id and user_id in source."""
        event_id = self.service.publish_search_query(query="test query")

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "search_service")

    def test_event_timestamp_is_set(self):
        """Test that events have timestamp set."""
        before_publish = timezone.now()
        event_id = self.service.publish_search_query(query="test query")
        after_publish = timezone.now()

        event = Event.objects.get(event_id=event_id)
        self.assertIsNotNone(event.timestamp)
        # Verify timestamp is between before and after
        self.assertGreaterEqual(event.timestamp, before_publish)
        self.assertLessEqual(event.timestamp, after_publish)

    def test_event_tags_are_set(self):
        """Test that events have correct tags set."""
        # Test search.query tags
        event_id = self.service.publish_search_query(query="test")
        event = Event.objects.get(event_id=event_id)
        tags = event.metadata.get("tags", []) if event.metadata else []
        self.assertIn("search", tags)
        self.assertIn("query", tags)

        # Test search.index.updated tags
        event_id = self.service.publish_index_updated(
            resource_type="CONTRACT", resource_id="test-123"
        )
        event = Event.objects.get(event_id=event_id)
        tags = event.metadata.get("tags", []) if event.metadata else []
        self.assertIn("search", tags)
        self.assertIn("index", tags)

        # Test search.index.rebuilt tags
        event_id = self.service.publish_index_rebuilt(tenant_id=str(self.tenant.id))
        event = Event.objects.get(event_id=event_id)
        tags = event.metadata.get("tags", []) if event.metadata else []
        self.assertIn("search", tags)
        self.assertIn("index", tags)
        self.assertIn("rebuild", tags)

    def test_service_initialization_without_tenant_and_user(self):
        """Test SearchEventPublisher initialization without tenant_id and user_id."""
        service = _SearchServiceStub()
        self.assertIsNotNone(service._event_publisher)
        self.assertIsNone(service._event_publisher.default_tenant_id)
        self.assertIsNone(service._event_publisher.default_user_id)

    def test_service_initialization_with_tenant_and_user(self):
        """Test SearchEventPublisher initialization with tenant_id and user_id."""
        service = _SearchServiceStub(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.assertIsNotNone(service._event_publisher)
        self.assertEqual(service._event_publisher.default_tenant_id, str(self.tenant.id))
        self.assertEqual(service._event_publisher.default_user_id, str(self.user.id))

    def test_published_event_has_required_structure_tdd(self):
        """TDD: Published search.query event has required structure (event_type, data, tenant_id, etc.)."""
        event_id = self.service.publish_search_query(query="structure check")
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)
        event = Event.objects.get(event_id=event_id)
        self.assertIsNotNone(event.event_type)
        self.assertEqual(event.event_type, "search.query")
        self.assertIsNotNone(event.data)
        self.assertIn("query", event.data)
        self.assertIsNotNone(event.tenant_id)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "search_service")
        self.assertIsNotNone(event.timestamp)


# Helper class for testing
class _SearchServiceStub(SearchEventPublisher):
    """Test service class for SearchEventPublisher."""

    def __init__(self, tenant_id=None, user_id=None):
        self.tenant_id = tenant_id
        self.user_id = user_id
        super().__init__(tenant_id=tenant_id, user_id=user_id)
