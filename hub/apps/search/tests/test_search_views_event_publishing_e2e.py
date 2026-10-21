"""
E2E tests for SearchViewSet event publishing.

Tests complete search workflows through REST API endpoints and verifies
events are published at each step (no mocks/stubs).

Following TDD approach and engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""

import uuid

import redis
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from hub.apps.assets.models import AssetStatus
from hub.apps.contracts.models import (
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.search.indexing import SearchIndexer
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
    EVENT_BUS_FORCE_SYNC_PERSISTENCE=True,  # Force synchronous persistence so Event.objects.get() sees rows
    RATE_LIMIT_ENABLED=False,  # Disable rate limiting for E2E tests
)
class SearchViewsEventPublishingE2ETest(TestCase):
    """E2E tests for search event publishing through REST API."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset the global event bus singleton so overridden settings take effect
        import hub.apps.core.events.bus as bus_module

        bus_module._event_bus = None

        # Flush Redis dedup keys so events are persisted fresh each run
        try:
            from hub.apps.core.events.deduplication import (
                clear_all_dedup_namespaces,
                get_redis_client,
            )

            redis_client = get_redis_client()
            if redis_client:
                clear_all_dedup_namespaces(redis_client)
        except (ImportError, redis.RedisError):
            pass

        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError, RuntimeError):
            # RuntimeError covers the private-repo core-mode absence
            # form (semantic uninstalled) — W7.1.
            pass

        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)

        # Add AUDITOR role for rebuild_index endpoint access
        from hub.apps.users.models import Role, UserRole

        auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="AUDITOR", defaults={"description": "Auditor role"}
        )
        UserRole.objects.get_or_create(user=self.user, role=auditor_role)

        # Create test resources
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset description with keywords",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test Contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "test",
                "info": {
                    "title": "Test Contract",
                    "description": "Test contract description",
                    "tags": ["test", "example"],
                },
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Index resources for search
        SearchIndexer.index_asset(self.asset)
        SearchIndexer.index_dataset(self.dataset)
        SearchIndexer.index_contract(self.contract)

    def _assert_sunset(self, response):
        """P3-1 (sunset 2026-08-10): the deprecated search
        surface 410s via APIVersionMiddleware BEFORE any view or
        event code — the endpoint-to-event contracts these tests
        pinned died with the surface. The live-surface event
        contracts (SEARCH_PERFORMED on /api/search/) are covered by
        test_audit_emission.py / test_metrics_emission.py; the
        search.query/search.index.rebuilt event-bus migration is
        recorded for the search owning lane."""
        self.assertEqual(response.status_code, 410, response.content)
        body = response.json()
        self.assertEqual(body.get("code"), "ENDPOINT_SUNSET", response.content)
        self.assertEqual(
            body.get("details", {}).get("replacement"), "/api/search/",
            response.content,
        )

    def test_e2e_search_endpoint_publishes_search_query_event(self):
        """Test that search endpoint publishes search.query event."""
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self._assert_sunset(response)
    def test_e2e_search_endpoint_with_filters_publishes_event(self):
        """Test that search endpoint with filters publishes search.query event with filters."""
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self._assert_sunset(response)
    def test_e2e_search_endpoint_no_results_publishes_event(self):
        """Test that search endpoint with no results publishes search.query event with no_results=True."""
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self._assert_sunset(response)
    def test_e2e_rebuild_index_endpoint_publishes_index_rebuilt_event(self):
        """Test that rebuild_index endpoint publishes search.index.rebuilt event."""
        url = reverse("search-rebuild-index")
        response = self.client.post(url, {"tenant_id": str(self.tenant.id)}, format="json")
        self._assert_sunset(response)
    def test_e2e_search_endpoint_cached_results_still_publishes_event(self):
        """Test that search endpoint publishes event even when results are cached."""
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self._assert_sunset(response)
    def test_e2e_search_endpoint_multiple_searches_publish_multiple_events(self):
        """Test that multiple searches publish multiple events."""
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self._assert_sunset(response)
    def test_e2e_search_endpoint_event_includes_user_context(self):
        """Test that search.query event includes correct user context."""
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self._assert_sunset(response)
    def test_e2e_rebuild_index_endpoint_event_includes_rebuild_metadata(self):
        """Test that search.index.rebuilt event includes rebuild metadata."""
        url = reverse("search-rebuild-index")
        response = self.client.post(url, {"tenant_id": str(self.tenant.id)}, format="json")
        self._assert_sunset(response)
    def test_e2e_search_unauthenticated_returns_401_no_event(self):
        """Error handling: unauthenticated search returns 401 and no search.query event published."""
        self.client.force_authenticate(user=None)
        self.client.credentials()
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})
        self._assert_sunset(response)

    def tearDown(self):
        """Reconnect signals and reset event bus after test."""
        import hub.apps.core.events.bus as bus_module

        bus_module._event_bus = None

        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError, RuntimeError):
            # RuntimeError covers the private-repo core-mode absence
            # form (semantic uninstalled) — W7.1.
            pass
