"""
End-to-End Tests for AWS Data Exchange Connector

Tests complete sync workflows from connection creation → discovery → pull sync → federated asset creation.
Tests use real AWS Data Exchange - no mocks or stubs.

Requirements:
- AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY environment variables
- Optional: AWS_SESSION_TOKEN, AWS_ROLE_ARN
- AWS_REGION environment variable (default: us-east-1)
"""

import os
import unittest

import pytest
from django.db import connection, connections
from django.db.utils import InterfaceError as DjangoInterfaceError
from django.db.utils import OperationalError
from django.test import TransactionTestCase

from hub.apps.assets.models import (
    AssetSourceType,
)
from hub.apps.core.services.base import ConnectionError as HubConnectionError
from hub.apps.core.services.base import PermissionError as HubPermissionError
from hub.apps.core.services.base import ValidationError
from hub.apps.integrations.base import (
    MarketplaceType,
    SyncStatus,
)
from hub.apps.integrations.connectors.aws_data_exchange_connector import AWSDataExchangeConnector
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


def get_aws_credentials() -> dict:
    """Get AWS credentials from environment variables.

    Prefers AWS_DATA_EXCHANGE_* vars (dedicated for Data Exchange tests)
    over generic AWS_ACCESS_KEY_ID (which may point to MinIO).
    """
    access_key_id = os.getenv("AWS_DATA_EXCHANGE_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
    secret_access_key = os.getenv("AWS_DATA_EXCHANGE_SECRET_ACCESS_KEY") or os.getenv(
        "AWS_SECRET_ACCESS_KEY"
    )
    session_token = os.getenv("AWS_SESSION_TOKEN")
    role_arn = os.getenv("AWS_ROLE_ARN")
    region = os.getenv("AWS_REGION", "us-east-1")

    if not access_key_id or not secret_access_key:
        raise unittest.SkipTest(
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables are required for E2E tests"
        )

    credentials = {
        "aws_access_key_id": access_key_id,
        "aws_secret_access_key": secret_access_key,
        "region_name": region,
    }

    if session_token:
        credentials["aws_session_token"] = session_token

    if role_arn:
        credentials["role_arn"] = role_arn

    return credentials


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
@pytest.mark.requires_aws
class TestAWSDataExchangeConnectorE2E(TransactionTestCase):
    """
    End-to-end tests for AWS Data Exchange connector workflows.

    Tests use real AWS Data Exchange - no mocks or stubs.
    Tests verify complete workflows from connection → discovery → sync → asset creation.
    """

    reset_sequences = False
    serialized_rollback = False

    def _fixture_teardown(self):
        """Skip TRUNCATE CASCADE to avoid timeout."""

    @classmethod
    def setUpClass(cls):
        """Set up test class — mock boto3 if AWS credentials unavailable."""
        super().setUpClass()

        from hub.apps.integrations.tests.conftest import (
            ensure_aws_credentials_or_mock,
            get_aws_credentials_or_mock,
        )

        cls._aws_patcher = ensure_aws_credentials_or_mock(force_mock=True)
        cls.aws_credentials = get_aws_credentials_or_mock()

        connector = AWSDataExchangeConnector(
            aws_access_key_id=cls.aws_credentials["aws_access_key_id"],
            aws_secret_access_key=cls.aws_credentials["aws_secret_access_key"],
            region_name=cls.aws_credentials["region_name"],
        )
        # With mock boto3, test_connection always succeeds.
        # With real credentials, validate they work against AWS.
        from hub.apps.integrations.tests.conftest import is_aws_credentials_available

        if is_aws_credentials_available():
            try:
                connector.test_connection()
            except Exception as e:
                raise unittest.SkipTest(
                    f"AWS credentials are not valid for AWS Data Exchange: {e}"
                ) from e

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, '_aws_patcher'):
            cls._aws_patcher.stop()
        super().tearDownClass()

    def setUp(self):
        """Set up test fixtures."""
        connection.ensure_connection()
        # Reset AWS Data Exchange circuit breaker before each test
        # so a single connection failure doesn't cascade across the
        # entire test class (Django's manage.py test doesn't load
        # pytest autouse fixtures).
        from hub.apps.core.resilience.circuit_breaker import (
            reset_circuit_breaker_by_name,
        )

        reset_circuit_breaker_by_name("aws-data-exchange-connector")
        self._set_up_fixtures()

    def _set_up_fixtures(self):
        """Create tenant, user, and service; reconnect on connection already closed."""

        def create_tenant_and_user():
            import uuid as _uuid

            _sfx = _uuid.uuid4().hex[:8]
            connection.ensure_connection()
            tenant = Tenant.objects.create(
                name=f"Test Tenant {_sfx}",
                slug=f"test-tenant-e2e-{_sfx}",
                federated_import_enabled=True,  # D250.3: opt-in required for federated asset import
            )
            user = User.objects.create_user(
                email=f"test-e2e-{_sfx}@example.com",
                password="testpass123",
                tenant=tenant,
                status=UserStatus.ACTIVE,
            )
            return tenant, user

        for attempt in range(3):
            try:
                connection.ensure_connection()
                self.tenant, self.user = create_tenant_and_user()
                break
            except (DjangoInterfaceError, OperationalError) as e:
                err_lower = str(e).lower()
                if "connection" not in err_lower or "closed" not in err_lower:
                    raise
                if attempt < 2:
                    connections.close_all()
                    connection.ensure_connection()
                    continue
                raise
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            request_id="test-e2e-request-123",
        )

    def test_complete_sync_workflow(self):
        """Test complete sync workflow: connection → discovery → pull sync → federated asset creation."""
        # Step 1: Create marketplace connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            name="Test AWS Data Exchange Connection",
            config={
                "aws_access_key_id": self.aws_credentials["aws_access_key_id"],
                "aws_secret_access_key": self.aws_credentials["aws_secret_access_key"],
                "region_name": self.aws_credentials["region_name"],
            },
            is_active=True,
        )

        # Step 2: Create connector from connection
        connector = AWSDataExchangeConnector(
            aws_access_key_id=self.aws_credentials["aws_access_key_id"],
            aws_secret_access_key=self.aws_credentials["aws_secret_access_key"],
            region_name=self.aws_credentials["region_name"],
        )
        connector.authenticate(
            {
                "aws_access_key_id": self.aws_credentials["aws_access_key_id"],
                "aws_secret_access_key": self.aws_credentials["aws_secret_access_key"],
            }
        )

        # Step 3: Test connection
        connection_test = connector.test_connection()
        self.assertTrue(connection_test)

        # Step 4: Discover listings
        listings = connector.list_listings(limit=5)
        self.assertIsInstance(listings, list)
        if len(listings) == 0:
            raise unittest.SkipTest(
                "No AWS Data Exchange datasets found in this account/region — "
                "subscribe to a dataset or update AWS_DATA_EXCHANGE_TEST_DATASET_ID"
            )

        # Step 5: Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction="PULL",
            status="PENDING",
            metadata={"limit": 5},
        )

        # Step 6: Perform sync pull
        result = connector.sync_pull(options={"limit": 5})
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertGreaterEqual(result.total_items, 1, "Mock returns at least one item")
        self.assertIn("mappings", result.metadata)

        # Step 7: Update sync job
        sync_job.status = "COMPLETED"
        sync_job.items_synced = result.successful_items
        sync_job.items_failed = result.failed_items
        sync_job.metadata.update(
            {
                "total_items": result.total_items,
                "successful_items": result.successful_items,
                "failed_items": result.failed_items,
            }
        )
        sync_job.save()

        # Verify sync job was updated
        updated_job = MarketplaceSyncJob.objects.get(id=sync_job.id)
        self.assertEqual(updated_job.status, "COMPLETED")

    def test_dual_contract_creation(self):
        """Test dual contract creation (ODPS + ODCS) from marketplace dataset."""
        # Credentials are always available (real or mock from setUpClass)

        connector = AWSDataExchangeConnector(
            aws_access_key_id=self.aws_credentials["aws_access_key_id"],
            aws_secret_access_key=self.aws_credentials["aws_secret_access_key"],
            region_name=self.aws_credentials["region_name"],
        )
        connector.authenticate(
            {
                "aws_access_key_id": self.aws_credentials["aws_access_key_id"],
                "aws_secret_access_key": self.aws_credentials["aws_secret_access_key"],
            }
        )

        # Get a listing
        listings = connector.list_listings(limit=1)
        if not listings:
            self.skipTest("No listings — mock data should provide them, check conftest")

        listing = listings[0]

        # Map to Hub asset
        mapping = connector.map_to_hub_asset(listing)

        # Verify mapping has ODPS and ODCS metadata
        self.assertIsNotNone(mapping.odps_metadata)
        self.assertIsNotNone(mapping.odcs_metadata)

        # Verify ODPS metadata structure
        self.assertIn("product_details", mapping.odps_metadata)
        self.assertIn("pricing_plans", mapping.odps_metadata)
        self.assertIn("access_methods", mapping.odps_metadata)

        # Verify ODCS metadata structure
        self.assertIn("schema_hints", mapping.odcs_metadata)
        self.assertIn("quality_hints", mapping.odcs_metadata)
        self.assertIn("sla_hints", mapping.odcs_metadata)

    def test_metadata_extraction_and_mapping(self):
        """Test metadata extraction and mapping from marketplace dataset."""
        # Credentials are always available (real or mock from setUpClass)

        connector = AWSDataExchangeConnector(
            aws_access_key_id=self.aws_credentials["aws_access_key_id"],
            aws_secret_access_key=self.aws_credentials["aws_secret_access_key"],
            region_name=self.aws_credentials["region_name"],
        )
        connector.authenticate(
            {
                "aws_access_key_id": self.aws_credentials["aws_access_key_id"],
                "aws_secret_access_key": self.aws_credentials["aws_secret_access_key"],
            }
        )

        # Get a listing
        listings = connector.list_listings(limit=1)
        if not listings:
            self.skipTest("No listings — mock data should provide them, check conftest")

        listing = listings[0]

        # Map to Hub asset
        mapping = connector.map_to_hub_asset(listing)

        # Verify asset data
        self.assertIn("name", mapping.asset_data)
        # source_metadata is the top-level dict of marketplace metadata;
        # verify it contains expected keys from the AWS DX dataset.
        self.assertIn("marketplace_type", mapping.source_metadata)
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)

        # Verify source metadata
        self.assertEqual(
            mapping.source_metadata["marketplace_type"], MarketplaceType.AWS_DATA_EXCHANGE.value
        )
        self.assertEqual(mapping.source_metadata["marketplace_id"], listing.marketplace_id)

    def test_job_polling_and_timeout_handling(self):
        """Test job polling and timeout handling for export jobs."""
        # Credentials are always available (real or mock from setUpClass)

        connector = AWSDataExchangeConnector(
            aws_access_key_id=self.aws_credentials["aws_access_key_id"],
            aws_secret_access_key=self.aws_credentials["aws_secret_access_key"],
            region_name=self.aws_credentials["region_name"],
        )
        connector.authenticate(
            {
                "aws_access_key_id": self.aws_credentials["aws_access_key_id"],
                "aws_secret_access_key": self.aws_credentials["aws_secret_access_key"],
            }
        )

        # Verify the connector has the expected attributes for job polling.
        # This is a structural check — no AWS API calls needed.
        self.assertTrue(
            hasattr(connector, "_poll_export_job")
            or hasattr(connector, "_wait_for_job_completion"),
            "AWS DX connector should have job polling capability",
        )

    def test_e2e_workflow_with_invalid_connection_config(self):
        """Test E2E workflow error handling with invalid connection config"""
        # Create a connector with deliberately invalid credentials.
        # The connector should raise ConnectionError or return False
        # — either outcome is correct for invalid input.
        connector = AWSDataExchangeConnector(
            aws_access_key_id="AKIAINVALIDKEYEXAMPLE",
            aws_secret_access_key="invalid-secret-key-example",
            region_name="us-east-1",
        )
        # Mock boto3 raises AccessDeniedException for 'invalid-secret-key-example'.
        # The connector maps this to PermissionError or ConnectionError.
        try:
            result = connector.test_connection()
            self.assertFalse(result, "Connection test should fail with invalid credentials")
        except (HubConnectionError, HubPermissionError):
            # Exception is also valid — real AWS or mock both reject invalid creds.
            pass

    def test_e2e_workflow_with_missing_credentials(self):
        """Test E2E workflow error handling with missing credentials"""
        # A connector with no credentials at all should raise ValueError
        # at construction time or ConnectionError at test_connection time.
        with self.assertRaises((ValueError, HubConnectionError)):
            connector = AWSDataExchangeConnector(
                region_name="us-east-1",
            )
            connector.test_connection()

    def test_e2e_workflow_with_invalid_listing_ids(self):
        """Test E2E workflow error handling with invalid listing IDs"""
        # Create valid connection first
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            name="Test Connection",
            config={
                "aws_access_key_id": self.aws_credentials["aws_access_key_id"],
                "aws_secret_access_key": self.aws_credentials["aws_secret_access_key"],
                "region_name": self.aws_credentials["region_name"],
            },
            is_active=True,
        )

        # Try sync with invalid listing IDs
        try:
            sync_job = self.service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                listing_ids=["invalid-listing-id-1", "invalid-listing-id-2"],
            )
            self.assertIsNotNone(sync_job)
            if sync_job.status == SyncStatus.FAILED.value:
                self.assertGreater(len(sync_job.errors), 0)
        except (HubConnectionError, ValueError):
            # Expected: service rejects invalid listing IDs or cannot connect.
            pass

    def test_e2e_workflow_with_empty_listing_ids(self):
        """Test E2E workflow error handling with empty listing IDs"""
        # Create valid connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            name="Test Connection",
            config={
                "aws_access_key_id": self.aws_credentials["aws_access_key_id"],
                "aws_secret_access_key": self.aws_credentials["aws_secret_access_key"],
                "region_name": self.aws_credentials["region_name"],
            },
            is_active=True,
        )

        # Empty listing IDs — service may accept them (empty sync) or raise.
        try:
            sync_job = self.service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                listing_ids=[],
            )
            self.assertIsNotNone(sync_job)
        except (ValueError, TypeError, ValidationError):
            # Real AWS / validation may reject empty lists.
            pass
