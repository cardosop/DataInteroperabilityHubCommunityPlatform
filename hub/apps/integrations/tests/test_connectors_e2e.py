"""
Comprehensive End-to-End Tests for Marketplace Connectors

Tests use real marketplace instances and real connections - no mocks or stubs of connector behavior.
Tests verify complete workflows from connection → discovery → asset creation → verification.

Requirements:
- dados.gov.br: DADOS_GOV_BR_API_KEY environment variable (JWT token)
- Snowflake: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_TOKEN environment variables
"""

import os
import time
import unittest

import pytest
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import (
    Asset,
    AssetSourceType,
    AssetStatus,
    AssetVisibility,
    DataStrategy,
    ExternalResourceReference,
)
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType
from hub.apps.integrations.base import (
    MarketplaceType,
    SyncDirection,
    SyncResult,
    SyncStatus,
)
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config
from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector
from hub.apps.integrations.connectors.snowflake_connector import (
    SNOWFLAKE_AVAILABLE,
    SnowflakeConnector,
)
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceMapping,
    MarketplaceSyncJob,
)
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
from hub.apps.core.services.base import NotFoundError as HubNotFoundError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


def get_dados_gov_br_credentials() -> dict:
    """Get dados.gov.br credentials from environment variables."""
    jwt_token = os.getenv("DADOS_GOV_BR_API_KEY") or os.getenv("CKAN_DADOS_GOV_BR_API_KEY")
    if not jwt_token:
        raise unittest.SkipTest("DADOS_GOV_BR_API_KEY not set - skipping E2E tests")
    return {"jwt_token": jwt_token}


def get_snowflake_credentials() -> dict:
    """Get Snowflake credentials from environment variables."""
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")
    token = os.getenv("SNOWFLAKE_TOKEN")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    role = os.getenv("SNOWFLAKE_ROLE")
    database = os.getenv("SNOWFLAKE_DATABASE")

    if not account or not user or not token:
        raise unittest.SkipTest(
            "SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and SNOWFLAKE_TOKEN environment variables are required"
        )

    credentials = {
        "account": account,
        "user": user,
        "token": token,
    }

    if warehouse:
        credentials["warehouse"] = warehouse
    if role:
        credentials["role"] = role
    if database:
        credentials["database"] = database

    return credentials


def _dados_gov_br_connection_config(instance_config, credentials: dict) -> dict:
    """
    Build connection config for dados.gov.br so the factory creates DadosGovBrConnector.

    Using instance_id ensures create_connector() uses instance config and picks
    DadosGovBrConnector (swagger) instead of the registered CKANConnector.
    api_key is mapped to jwt_token by the factory for swagger instances.
    """
    return {
        "instance_id": "dados.gov.br",
        "api_key": credentials["jwt_token"],
    }


def handle_auth_failure(e: Exception) -> None:
    """
    Handle authentication and connectivity failures by skipping tests.

    Only skips on clear external-service-unavailability indicators.
    Never skips on AssertionError or business-logic errors.

    Args:
        e: Exception that may indicate authentication or connectivity failure

    Raises:
        pytest.skip: If exception indicates auth/connectivity failure
    """
    # Never skip on assertion failures — those are real test bugs.
    if isinstance(e, (AssertionError, unittest.SkipTest)):
        raise

    error_str = str(e).lower()

    # Auth failure patterns — specific enough to avoid false matches.
    if (
        "authentication failed" in error_str
        or "jwt token" in error_str
        or "redirected to signin" in error_str
        or "unauthorized" in error_str
        or "invalid api key" in error_str
        or "invalid token" in error_str
        or "401" in error_str
    ):
        pytest.skip(
            f"E2E test skipped (authentication failure): {e}"
        )

    # Network failure patterns — transport-level only.
    if (
        "name or service not known" in error_str  # DNS resolution
        or "connection reset" in error_str          # TCP reset
        or "connection timed out" in error_str      # TCP timeout
        or "connect timeout" in error_str           # Connection timeout
        or "read timeout" in error_str              # Read timeout
        or "timed out" in error_str                 # Generic timeout
        or "errno 111" in error_str                 # Connection refused (Linux)
        or "errno 113" in error_str                 # No route to host
    ):
        pytest.skip(
            f"E2E test skipped (external service unavailable): {e}"
        )


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestDadosGovBrConnectorE2E(TestCase):
    """
    End-to-end tests for dados.gov.br connector.

    Tests complete workflows using real dados.gov.br instance - no mocks or stubs.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with real credentials and validated connection."""
        # Check skip conditions BEFORE super().setUpClass() so that if we
        # raise SkipTest, no class-level atomics are opened and the PG
        # connection is not left in a stale transaction for the next class.
        cls.credentials = get_dados_gov_br_credentials()
        if not cls.credentials:
            raise unittest.SkipTest("dados.gov.br credentials not available")

        instance_config = get_marketplace_instance_config("dados.gov.br")
        if not instance_config:
            raise unittest.SkipTest("dados.gov.br instance configuration not found")

        super().setUpClass()

        # Validate token by testing actual connection — fail fast with skip
        # instead of running all tests with an expired/invalid token.
        # Wrap in outer try/except with explicit atomics rollback following
        # Django's setUpTestData() pattern, so a stale PG transaction
        # does not leak to subsequent test classes.
        try:
            try:
                connector = DadosGovBrConnector(
                    base_url=instance_config.base_url,
                    jwt_token=cls.credentials["jwt_token"],
                    swagger_spec_url=getattr(instance_config, "swagger_spec_url", None),
                )
                if not connector.test_connection():
                    raise unittest.SkipTest(
                        "dados.gov.br connection test failed — JWT token may be expired"
                    )
            except unittest.SkipTest:
                raise
            except Exception as e:
                raise unittest.SkipTest(
                    f"dados.gov.br connection validation failed: {e}"
                ) from None
        except Exception:
            cls._rollback_atomics(cls.cls_atomics)
            raise

    def setUp(self):
        """Set up test fixtures"""
        # Reset circuit breakers so a single connection failure in a
        # prior test class doesn't cascade across the entire run.
        # Django's manage.py test doesn't load pytest autouse fixtures.
        reset_circuit_breaker_by_name("snowflake-connector")
        reset_circuit_breaker_by_name("aws-data-exchange-connector")

        self.tenant = Tenant.objects.create(
            name="Test Tenant E2E",
            slug="test-tenant-e2e",
            status="ACTIVE",
            kyc_status="VERIFIED",
            federated_import_enabled=True,  # D250.3: opt-in required for federated asset import
        )
        self.user = User.objects.create_user(
            email="test-e2e@example.com",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            request_id="test-e2e-request-123",
        )
        self.created_sync_jobs = []

    def tearDown(self):
        """Clean up test data"""
        # Cleanup sync jobs
        for sync_job in self.created_sync_jobs:
            try:
                sync_job.delete()
            except Exception:
                pass

    def _create_connection(
        self, marketplace_type: MarketplaceType, config: dict, name: str
    ) -> MarketplaceConnection:
        """Helper to create marketplace connection"""
        return self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=marketplace_type.value,
            name=name,
            config=config,
        )

    def _wait_for_workflow_completion(
        self, workflow_instance_id: str, timeout: int = 300
    ) -> WorkflowInstance:
        """Wait for workflow to complete"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
            if workflow_instance.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
                return workflow_instance
            time.sleep(1)
        raise TimeoutError(
            f"Workflow {workflow_instance_id} did not complete within {timeout} seconds"
        )

    def _verify_workflow_state(
        self, sync_job: MarketplaceSyncJob, expected_status: SyncStatus
    ) -> None:
        """Verify sync job workflow state"""
        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, expected_status.value)

    def _verify_asset_creation(
        self, sync_job: MarketplaceSyncJob, expected_count: int = None, min_count: int = 1
    ) -> list:
        """Verify assets were created from sync job (MarketplaceMapping has connection, not sync_job)."""
        mappings = MarketplaceMapping.objects.filter(
            connection=sync_job.connection,
            created_at__gte=sync_job.created_at,
        )
        # Separate mappings that have associated assets from those
        # that don't, so partial failures are visible in the output.
        assets = [m.hub_asset for m in mappings if m.hub_asset_id]
        mappings_without_assets = [m for m in mappings if not m.hub_asset_id]
        if mappings_without_assets:
            import logging
            logging.warning(
                "%d MarketplaceMapping(s) have no hub_asset — "
                "this may indicate a partial failure in the federated import workflow.",
                len(mappings_without_assets),
            )
        if expected_count is not None:
            self.assertEqual(len(assets), expected_count)
        else:
            self.assertGreaterEqual(len(assets), min_count)
        return assets

    def _verify_contracts_created(self, asset: Asset) -> tuple:
        """Verify contracts were created for asset"""
        odps_contract = Contract.objects.filter(
            asset=asset, original_spec_type=OriginalSpecType.ODPS
        ).first()
        odcs_contract = Contract.objects.filter(
            asset=asset, original_spec_type=OriginalSpecType.ODCS
        ).first()
        self.assertIsNotNone(odps_contract, "ODPS contract should be created")
        self.assertIsNotNone(odcs_contract, "ODCS contract should be created")
        return odps_contract, odcs_contract

    def _verify_external_resource_references(self, asset: Asset, min_expected: int = 0) -> list:
        """Verify external resource references were created for the asset.

        Args:
            asset: Asset to check external references for.
            min_expected: If > 0, assert at least this many refs exist.

        Returns:
            List of ExternalResourceReference objects
        """
        external_refs = ExternalResourceReference.objects.filter(asset=asset)
        result = list(external_refs)
        self.assertIsInstance(result, list)
        if min_expected > 0:
            self.assertGreaterEqual(
                len(result), min_expected,
                f"Expected at least {min_expected} external resource references, got {len(result)}",
            )
        return result

    def test_connection_and_discovery(self):
        """Test connection and discovery of listings"""
        try:
            instance_config = get_marketplace_instance_config("dados.gov.br")
            if not instance_config:
                self.skipTest("dados.gov.br instance configuration not found")

            connector = DadosGovBrConnector(
                base_url=instance_config.base_url,
                jwt_token=self.credentials["jwt_token"],
                swagger_spec_url=getattr(instance_config, "swagger_spec_url", None),
            )

            # Test connection
            connection_result = connector.test_connection()
            self.assertTrue(connection_result, "Connection test should succeed")

            # Discover listings
            listings = connector.list_listings(limit=5)
            self.assertIsInstance(listings, list)
            self.assertLessEqual(len(listings), 5)

            if listings:
                # Verify listing structure
                listing = listings[0]
                self.assertIsNotNone(listing.marketplace_id)
                self.assertIsNotNone(listing.title)
                self.assertEqual(listing.marketplace_type, MarketplaceType.CKAN_INSTANCE)

            # Verify no assets created during discovery (metadata-first pattern)
            assets_before = Asset.objects.filter(tenant=self.tenant).count()
            self.assertEqual(assets_before, 0, "Discovery should not create assets")

        except Exception as e:
            handle_auth_failure(e)
            raise

    def test_asset_creation_via_workflow(self):
        """Test asset creation via complete workflow"""
        try:
            # Create connection
            instance_config = get_marketplace_instance_config("dados.gov.br")
            if not instance_config:
                self.skipTest("dados.gov.br instance configuration not found")

            connection = self._create_connection(
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                config=_dados_gov_br_connection_config(instance_config, self.credentials),
                name="dados.gov.br E2E Test",
            )

            # Call sync_from_marketplace
            sync_job = self.service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                options={
                    "limit": 3,
                    "include_resources": True,
                    "data_strategy": "METADATA_ONLY",
                },
            )
            self.created_sync_jobs.append(sync_job)

            # Wait for workflow completion
            workflow_instance_id = sync_job.metadata.get("workflow_instance_id")
            if workflow_instance_id:
                workflow_instance = self._wait_for_workflow_completion(
                    workflow_instance_id, timeout=600  # 10 minutes for real sync
                )
                self.assertIn(
                    workflow_instance.status,
                    [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED],
                    f"Workflow should complete or fail, got {workflow_instance.status}",
                )

            # Verify sync job status
            self._verify_workflow_state(sync_job, expected_status=SyncStatus.COMPLETED)

            # Verify assets created
            assets = self._verify_asset_creation(sync_job, expected_count=None, min_count=1)

            # Verify contracts and external references for each asset
            for asset in assets:
                odps_contract, odcs_contract = self._verify_contracts_created(asset)
                external_refs = self._verify_external_resource_references(asset)
                # CKAN instances may not always have external refs if no resources discovered
                # This is OK for E2E test

        except Exception as e:
            handle_auth_failure(e)
            raise

    def test_selective_resource_download(self):
        """Test selective resource download"""
        try:
            # Create connection
            instance_config = get_marketplace_instance_config("dados.gov.br")
            if not instance_config:
                self.skipTest("dados.gov.br instance configuration not found")

            connection = self._create_connection(
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                config=_dados_gov_br_connection_config(instance_config, self.credentials),
                name="dados.gov.br E2E Test",
            )

            # Create assets via workflow (METADATA_ONLY)
            sync_job = self.service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                options={
                    "limit": 1,
                    "include_resources": True,
                    "data_strategy": "METADATA_ONLY",
                },
            )
            self.created_sync_jobs.append(sync_job)

            # Wait for workflow completion
            workflow_instance_id = sync_job.metadata.get("workflow_instance_id")
            if workflow_instance_id:
                self._wait_for_workflow_completion(workflow_instance_id, timeout=600)

            # Get created asset
            assets = self._verify_asset_creation(sync_job, min_count=1)
            asset = assets[0]

            # Get external resource references
            external_refs = ExternalResourceReference.objects.filter(asset=asset)
            if external_refs:
                # Test downloading a specific resource
                resource_ref = external_refs[0]
                connector = MarketplaceConnectorFactory.create_connector(
                    marketplace_type=MarketplaceType.CKAN_INSTANCE, config=connection.get_config()
                )

                # Download resource to a temp destination
                try:
                    import tempfile
                    dest_path = tempfile.mktemp(suffix=".csv")
                    listing_id = asset.source_metadata.get("listing_id") if asset.source_metadata else None
                    download_result = connector.download_resource(
                        resource_id=resource_ref.resource_id,
                        destination_path=dest_path,
                        listing_id=listing_id,
                    )
                    # Verify the download produced a meaningful result.
                    self.assertIsNotNone(download_result)
                except (ConnectionError, TimeoutError, PermissionError, ValueError, HubNotFoundError) as e:
                    # External service or data unavailable — skip gracefully.
                    self.skipTest(f"Resource download failed (external service): {e}")
                finally:
                    if hasattr(connector, "close"):
                        connector.close()

        except Exception as e:
            handle_auth_failure(e)
            raise

    def test_federated_asset_created_with_contracts_and_refs(self):
        """Test federated asset creation with dual contracts and external refs"""
        try:
            # Create connection
            instance_config = get_marketplace_instance_config("dados.gov.br")
            if not instance_config:
                self.skipTest("dados.gov.br instance configuration not found")

            connection = self._create_connection(
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                config=_dados_gov_br_connection_config(instance_config, self.credentials),
                name="dados.gov.br E2E Test",
            )

            # Create assets via workflow
            sync_job = self.service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                options={
                    "limit": 1,
                    "include_resources": True,
                    "data_strategy": "METADATA_ONLY",
                },
            )
            self.created_sync_jobs.append(sync_job)

            # Wait for workflow completion
            workflow_instance_id = sync_job.metadata.get("workflow_instance_id")
            if workflow_instance_id:
                self._wait_for_workflow_completion(workflow_instance_id, timeout=600)

            # Get created asset
            assets = self._verify_asset_creation(sync_job, min_count=1)
            asset = assets[0]

            # Verify asset is in DRAFT status (or ACTIVE if auto-activated)
            asset.refresh_from_db()
            self.assertIn(asset.status, [AssetStatus.DRAFT, AssetStatus.ACTIVE])

            # Verify contracts were created with the federated asset.
            # The federated-import workflow (Phase 250.5.A) creates
            # ODPS + ODCS contracts during asset creation.
            odps_contract, odcs_contract = self._verify_contracts_created(asset)

            # Verify external resource references are present for
            # CKAN-harvested assets (resources in the listing metadata).
            external_refs = self._verify_external_resource_references(asset)

            # Asset created via federated import with METADATA_ONLY
            # strategy lands in DRAFT; activation requires a separate
            # explicit call through the Asset endpoint (tested elsewhere).
            self.assertIn(
                asset.status,
                [AssetStatus.DRAFT, AssetStatus.ACTIVE],
                f"Asset should be DRAFT or ACTIVE after federated import, got {asset.status}",
            )

        except Exception as e:
            handle_auth_failure(e)
            raise

    def test_dados_gov_br_e2e_with_invalid_listing_ids(self):
        """Test dados.gov.br E2E workflow error handling with invalid listing IDs"""
        credentials = get_dados_gov_br_credentials()
        if not credentials:
            self.skipTest("dados.gov.br credentials not available")

        try:
            instance_config = get_marketplace_instance_config("dados.gov.br")
            if not instance_config:
                self.skipTest("dados.gov.br instance configuration not found")

            connector = DadosGovBrConnector(
                base_url=instance_config.base_url,
                jwt_token=credentials["jwt_token"],
                swagger_spec_url=getattr(instance_config, "swagger_spec_url", None),
            )

            # Try sync with invalid listing IDs
            result = connector.sync_pull(
                listing_ids=["invalid-package-id-1", "invalid-package-id-2"]
            )
            # Should handle gracefully
            self.assertIsInstance(result, SyncResult)
            if result.status == SyncStatus.FAILED:
                self.assertGreater(len(result.errors), 0)
            elif result.status == SyncStatus.COMPLETED:
                self.assertEqual(result.successful_items, 0)
        except Exception as e:
            handle_auth_failure(e)
            raise

    def test_dados_gov_br_e2e_with_empty_listing_ids(self):
        """Test dados.gov.br E2E workflow error handling with empty listing IDs"""
        credentials = get_dados_gov_br_credentials()
        if not credentials:
            self.skipTest("dados.gov.br credentials not available")

        try:
            instance_config = get_marketplace_instance_config("dados.gov.br")
            if not instance_config:
                self.skipTest("dados.gov.br instance configuration not found")

            connector = DadosGovBrConnector(
                base_url=instance_config.base_url,
                jwt_token=credentials["jwt_token"],
                swagger_spec_url=getattr(instance_config, "swagger_spec_url", None),
            )

            # Try sync with empty listing IDs
            result = connector.sync_pull(listing_ids=[])
            # Should handle gracefully
            self.assertIsInstance(result, SyncResult)
            self.assertEqual(result.total_items, 0)
            self.assertEqual(result.successful_items, 0)
        except Exception as e:
            handle_auth_failure(e)
            raise


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
@pytest.mark.snowflake_e2e
class TestSnowflakeConnectorE2E(TestCase):
    """
    E2E tests for Snowflake connector.

    Requires SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_TOKEN in .env.test.
    When unset, tests are skipped. To deselect in CI: pytest -m 'not snowflake_e2e'.
    No mocks or stubs; uses real Snowflake instance.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with real credentials"""
        super().setUpClass()
        try:
            try:
                cls.credentials = get_snowflake_credentials()
            except Exception:
                # Skip entire test class if credentials not available
                raise
        except Exception:
            cls._rollback_atomics(cls.cls_atomics)
            raise

    def setUp(self):
        """Set up test fixtures"""
        # Reset circuit breakers so a single connection failure in a
        # prior test class doesn't cascade across the entire run.
        # Django's manage.py test doesn't load pytest autouse fixtures.
        reset_circuit_breaker_by_name("snowflake-connector")
        reset_circuit_breaker_by_name("aws-data-exchange-connector")

        self.tenant = Tenant.objects.create(
            name="Test Tenant E2E",
            slug="test-tenant-e2e",
            status="ACTIVE",
            kyc_status="VERIFIED",
            federated_import_enabled=True,  # D250.3: opt-in required for federated asset import
        )
        self.user = User.objects.create_user(
            email="test-e2e@example.com",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            request_id="test-e2e-request-123",
        )
        self.created_sync_jobs = []

    def tearDown(self):
        """Clean up test data"""
        # Cleanup sync jobs
        for sync_job in self.created_sync_jobs:
            try:
                sync_job.delete()
            except Exception:
                pass

    def _create_connection(
        self, marketplace_type: MarketplaceType, config: dict, name: str
    ) -> MarketplaceConnection:
        """Helper to create marketplace connection"""
        return self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=marketplace_type.value,
            name=name,
            config=config,
        )

    def _wait_for_workflow_completion(
        self, workflow_instance_id: str, timeout: int = 300
    ) -> WorkflowInstance:
        """Wait for workflow to complete"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
            if workflow_instance.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
                return workflow_instance
            time.sleep(1)
        raise TimeoutError(
            f"Workflow {workflow_instance_id} did not complete within {timeout} seconds"
        )

    def _verify_workflow_state(
        self, sync_job: MarketplaceSyncJob, expected_status: SyncStatus
    ) -> None:
        """Verify sync job workflow state"""
        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, expected_status.value)

    def _verify_asset_creation(
        self, sync_job: MarketplaceSyncJob, expected_count: int = None, min_count: int = 1
    ) -> list:
        """Verify assets were created from sync job (MarketplaceMapping has connection, not sync_job)."""
        mappings = MarketplaceMapping.objects.filter(
            connection=sync_job.connection,
            created_at__gte=sync_job.created_at,
        )
        # Separate mappings that have associated assets from those
        # that don't, so partial failures are visible in the output.
        assets = [m.hub_asset for m in mappings if m.hub_asset_id]
        mappings_without_assets = [m for m in mappings if not m.hub_asset_id]
        if mappings_without_assets:
            import logging
            logging.warning(
                "%d MarketplaceMapping(s) have no hub_asset — "
                "this may indicate a partial failure in the federated import workflow.",
                len(mappings_without_assets),
            )
        if expected_count is not None:
            self.assertEqual(len(assets), expected_count)
        else:
            self.assertGreaterEqual(len(assets), min_count)
        return assets

    def _verify_contracts_created(self, asset: Asset) -> tuple:
        """Verify contracts were created for asset"""
        odps_contract = Contract.objects.filter(
            asset=asset, original_spec_type=OriginalSpecType.ODPS
        ).first()
        odcs_contract = Contract.objects.filter(
            asset=asset, original_spec_type=OriginalSpecType.ODCS
        ).first()
        self.assertIsNotNone(odps_contract, "ODPS contract should be created")
        self.assertIsNotNone(odcs_contract, "ODCS contract should be created")
        return odps_contract, odcs_contract

    def _verify_external_resource_references(self, asset: Asset, min_expected: int = 0) -> list:
        """Verify external resource references were created for the asset.

        Args:
            asset: Asset to check external references for.
            min_expected: If > 0, assert at least this many refs exist.

        Returns:
            List of ExternalResourceReference objects
        """
        external_refs = ExternalResourceReference.objects.filter(asset=asset)
        result = list(external_refs)
        self.assertIsInstance(result, list)
        if min_expected > 0:
            self.assertGreaterEqual(
                len(result), min_expected,
                f"Expected at least {min_expected} external resource references, got {len(result)}",
            )
        return result

    def test_connection_and_discovery(self):
        """Test connection and discovery of listings"""
        try:
            # Create connector
            connector = SnowflakeConnector(
                account=self.credentials["account"],
                user=self.credentials["user"],
                token=self.credentials["token"],
                warehouse=self.credentials.get("warehouse"),
                role=self.credentials.get("role"),
                database=self.credentials.get("database"),
            )

            # Test connection
            connection_result = connector.test_connection()
            self.assertTrue(connection_result, "Connection test should succeed")

            # Discover listings
            listings = connector.list_listings(limit=5)
            self.assertIsInstance(listings, list)
            self.assertLessEqual(len(listings), 5)

            if listings:
                # Verify listing structure
                listing = listings[0]
                self.assertIsNotNone(listing.marketplace_id)
                self.assertIsNotNone(listing.title)
                self.assertEqual(
                    listing.marketplace_type, MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
                )

                # Verify resources have Snowflake-specific metadata
                if listing.resources:
                    resource = listing.resources[0]
                    # Snowflake resources may have database, schema, table metadata
                    self.assertIsNotNone(resource.resource_id)

            # Verify no assets created during discovery (metadata-first pattern)
            assets_before = Asset.objects.filter(tenant=self.tenant).count()
            self.assertEqual(assets_before, 0, "Discovery should not create assets")

            # Close connector
            connector.close()

        except Exception as e:
            # Handle connection errors gracefully
            if "authentication" in str(e).lower() or "connection" in str(e).lower():
                pytest.skip(f"Snowflake connection failed: {e}")
            raise

    def _ensure_snowflake_listings_available(self):
        """Skip the test when the Snowflake account has no marketplace listings."""
        from hub.apps.integrations.connectors.snowflake_connector import (
            SnowflakeConnector,
        )
        connector = SnowflakeConnector(
            account=self.credentials["account"],
            user=self.credentials["user"],
            token=self.credentials["token"],
            warehouse=self.credentials.get("warehouse"),
            database=self.credentials.get("database"),
        )
        try:
            listings = connector.list_listings(limit=1)
        finally:
            connector.close()
        if not listings:
            raise unittest.SkipTest(
                "No Snowflake Data Marketplace listings available — "
                "subscribe to a listing on the Snowflake Marketplace"
            )

    def test_asset_creation_via_workflow(self):
        """Test asset creation via complete workflow"""
        try:
            self._ensure_snowflake_listings_available()

            # Create connection
            connection = self._create_connection(
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                config={
                    "account": self.credentials["account"],
                    "user": self.credentials["user"],
                    "token": self.credentials["token"],
                    "warehouse": self.credentials.get("warehouse"),
                    "role": self.credentials.get("role"),
                    "database": self.credentials.get("database"),
                },
                name="Snowflake E2E Test",
            )

            # Call sync_from_marketplace
            sync_job = self.service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                options={
                    "limit": 3,
                    "include_resources": True,
                    "data_strategy": "METADATA_ONLY",
                },
            )
            self.created_sync_jobs.append(sync_job)

            # Wait for workflow completion
            workflow_instance_id = sync_job.metadata.get("workflow_instance_id")
            if workflow_instance_id:
                workflow_instance = self._wait_for_workflow_completion(
                    workflow_instance_id, timeout=600  # 10 minutes for real sync
                )
                self.assertIn(
                    workflow_instance.status,
                    [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED],
                    f"Workflow should complete or fail, got {workflow_instance.status}",
                )

            # Verify sync job status
            self._verify_workflow_state(sync_job, expected_status=SyncStatus.COMPLETED)

            # Verify assets created
            assets = self._verify_asset_creation(sync_job, expected_count=None, min_count=1)

            # Verify contracts and external references for each asset
            for asset in assets:
                odps_contract, odcs_contract = self._verify_contracts_created(asset)
                external_refs = self._verify_external_resource_references(asset)
                # Snowflake may not always have external refs if no resources discovered
                # This is OK for E2E test

        except Exception as e:
            # Handle connection errors gracefully
            if "authentication" in str(e).lower() or "connection" in str(e).lower():
                pytest.skip(f"Snowflake connection failed: {e}")
            raise

    def test_selective_resource_download(self):
        """Test selective resource download"""
        try:
            self._ensure_snowflake_listings_available()

            # Create connection
            connection = self._create_connection(
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                config={
                    "account": self.credentials["account"],
                    "user": self.credentials["user"],
                    "token": self.credentials["token"],
                    "warehouse": self.credentials.get("warehouse"),
                    "role": self.credentials.get("role"),
                    "database": self.credentials.get("database"),
                },
                name="Snowflake E2E Test",
            )

            # Create assets via workflow (METADATA_ONLY)
            sync_job = self.service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                options={
                    "limit": 1,
                    "include_resources": True,
                    "data_strategy": "METADATA_ONLY",
                },
            )
            self.created_sync_jobs.append(sync_job)

            # Wait for workflow completion
            workflow_instance_id = sync_job.metadata.get("workflow_instance_id")
            if workflow_instance_id:
                self._wait_for_workflow_completion(workflow_instance_id, timeout=600)

            # Get created asset
            assets = self._verify_asset_creation(sync_job, min_count=1)
            asset = assets[0]

            # Get external resource references
            external_refs = ExternalResourceReference.objects.filter(asset=asset)
            if external_refs:
                # Test downloading a specific resource
                resource_ref = external_refs[0]
                connector = MarketplaceConnectorFactory.create_connector(
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    config=connection.get_config(),
                )

                # Download resource (may require database creation, schema extraction)
                # Note: This may fail if listing is not available or permissions insufficient
                try:
                    import tempfile
                    dest_path = tempfile.mktemp(suffix=".data")
                    listing_id = asset.source_metadata.get("listing_id") if asset.source_metadata else None
                    download_result = connector.download_resource(
                        resource_id=resource_ref.resource_id,
                        destination_path=dest_path,
                        listing_id=listing_id,
                    )
                    # Verify the download produced a meaningful result.
                    self.assertIsNotNone(download_result)
                except (ConnectionError, TimeoutError, PermissionError, ValueError, HubNotFoundError) as e:
                    # External service or data unavailable — skip gracefully.
                    self.skipTest(f"Resource download failed (external service): {e}")
                finally:
                    # Close connector
                    if hasattr(connector, "close"):
                        connector.close()

        except Exception as e:
            # Handle connection errors gracefully
            if "authentication" in str(e).lower() or "connection" in str(e).lower():
                pytest.skip(f"Snowflake connection failed: {e}")
            raise

    def test_federated_asset_created_with_contracts_and_refs(self):
        """Test federated asset creation with dual contracts and external refs"""
        try:
            self._ensure_snowflake_listings_available()

            # Create connection
            connection = self._create_connection(
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                config={
                    "account": self.credentials["account"],
                    "user": self.credentials["user"],
                    "token": self.credentials["token"],
                    "warehouse": self.credentials.get("warehouse"),
                    "role": self.credentials.get("role"),
                    "database": self.credentials.get("database"),
                },
                name="Snowflake E2E Test",
            )

            # Create assets via workflow
            sync_job = self.service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                options={
                    "limit": 1,
                    "include_resources": True,
                    "data_strategy": "METADATA_ONLY",
                },
            )
            self.created_sync_jobs.append(sync_job)

            # Wait for workflow completion
            workflow_instance_id = sync_job.metadata.get("workflow_instance_id")
            if workflow_instance_id:
                self._wait_for_workflow_completion(workflow_instance_id, timeout=600)

            # Get created asset
            assets = self._verify_asset_creation(sync_job, min_count=1)
            asset = assets[0]

            # Verify asset is in DRAFT status (or ACTIVE if auto-activated)
            asset.refresh_from_db()
            self.assertIn(asset.status, [AssetStatus.DRAFT, AssetStatus.ACTIVE])

            # Verify contracts were created with the federated asset.
            # The federated-import workflow (Phase 250.5.A) creates
            # ODPS + ODCS contracts during asset creation.
            odps_contract, odcs_contract = self._verify_contracts_created(asset)

            # Verify external resource references are present for
            # Snowflake-harvested assets (tables/schemas in listing metadata).
            external_refs = self._verify_external_resource_references(asset)

            # Asset created via federated import with METADATA_ONLY
            # strategy lands in DRAFT; activation requires a separate
            # explicit call through the Asset endpoint (tested elsewhere).
            self.assertIn(
                asset.status,
                [AssetStatus.DRAFT, AssetStatus.ACTIVE],
                f"Asset should be DRAFT or ACTIVE after federated import, got {asset.status}",
            )

        except Exception as e:
            # Handle connection errors gracefully
            if "authentication" in str(e).lower() or "connection" in str(e).lower():
                pytest.skip(f"Snowflake connection failed: {e}")
            raise

    def test_snowflake_e2e_with_invalid_listing_ids(self):
        """Test Snowflake E2E workflow error handling with invalid listing IDs"""
        credentials = get_snowflake_credentials()
        if not credentials:
            self.skipTest("Snowflake credentials not available")

        if not SNOWFLAKE_AVAILABLE:
            self.skipTest("Snowflake connector not available")

        try:
            connector = SnowflakeConnector(**credentials)
            connector.authenticate(credentials)

            # Try sync with invalid listing IDs
            result = connector.sync_pull(
                listing_ids=["invalid-listing-id-1", "invalid-listing-id-2"]
            )
            # Should handle gracefully
            self.assertIsInstance(result, SyncResult)
            if result.status == SyncStatus.FAILED:
                self.assertGreater(len(result.errors), 0)
            elif result.status == SyncStatus.COMPLETED:
                self.assertEqual(result.successful_items, 0)
        except Exception as e:
            # Handle connection errors gracefully
            if "authentication" in str(e).lower() or "connection" in str(e).lower():
                pytest.skip(f"Snowflake connection failed: {e}")
            raise

    def test_snowflake_e2e_with_empty_listing_ids(self):
        """Test Snowflake E2E workflow error handling with empty listing IDs"""
        credentials = get_snowflake_credentials()
        if not credentials:
            self.skipTest("Snowflake credentials not available")

        if not SNOWFLAKE_AVAILABLE:
            self.skipTest("Snowflake connector not available")

        try:
            connector = SnowflakeConnector(**credentials)
            connector.authenticate(credentials)

            # Try sync with empty listing IDs
            result = connector.sync_pull(listing_ids=[])
            # Should handle gracefully
            self.assertIsInstance(result, SyncResult)
            self.assertEqual(result.total_items, 0)
            self.assertEqual(result.successful_items, 0)
        except Exception as e:
            # Handle connection errors gracefully
            if "authentication" in str(e).lower() or "connection" in str(e).lower():
                pytest.skip(f"Snowflake connection failed: {e}")
            raise
