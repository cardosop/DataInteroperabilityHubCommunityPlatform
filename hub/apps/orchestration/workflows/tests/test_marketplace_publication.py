"""
Unit tests for Marketplace Publication Workflow

Comprehensive tests for marketplace publication workflow including:
- Unit tests for individual tasks
- Integration tests for workflow execution
- E2E tests for complete marketplace publication journey
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus, ComplianceStatus, DQStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.core.events.models import Event
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.marketplace.models import Listing, ListingStatus, PricingModel
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.workflows.marketplace_publication import MarketplacePublicationWorkflow
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplacePublicationWorkflowUnitTest(TestCase):
    """Unit tests for marketplace publication workflow tasks"""

    def setUp(self):
        """Set up test fixtures"""
        # Use unique identifiers to avoid conflicts
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant Unit {unique_id}",
            slug=f"test-tenant-unit-{unique_id}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-unit-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-unit-{unique_id}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name=f"test-unit-{unique_id}.csv",
            storage_path=f"test/test-unit-{unique_id}.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            content_sha256=f"abc123{unique_id}",
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer", "nullable": False},
                    {"name": "name", "data_type": "string", "nullable": True},
                ]
            },
            sample_data_json=[{"id": 1, "name": "test1"}],
            row_count=100,
            format="CSV",
            created_by=self.user,
        )

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type="ODCS",
            original_spec_version="1.0",
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
            normalization_status="NORMALIZED_OK",
            hub_contract_json={
                "info": {"title": "Test Contract", "description": "Test contract description"},
                "marketplace": {
                    "license_summary": "MIT License",
                    "intended_use": ["analytics", "machine_learning"],
                    "restricted_use": ["resale"],
                },
            },
            created_by=self.user,
        )

        self.engine = WorkflowEngine()
        MarketplacePublicationWorkflow.register_tasks(self.engine)

        self.registry = WorkflowRegistry()
        MarketplacePublicationWorkflow.register_workflow(self.registry)

        workflow_def = self.registry.get_workflow(MarketplacePublicationWorkflow.WORKFLOW_NAME)
        self.workflow_instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=MarketplacePublicationWorkflow.WORKFLOW_NAME,
            workflow_version=workflow_def.version,
            tenant=self.tenant,
            created_by=self.user,
            status=WorkflowStatus.DRAFT,
            input_data={
                "tenant_id": str(self.tenant.id),
                "asset_id": str(self.asset.id),
                "metadata_json": {"title": "Test Listing", "short_description": "Test description"},
                "pricing_model": PricingModel.FREE,
            },
            state_data={},
        )

    def test_validate_asset_eligibility_task_success(self):
        """Test validate asset eligibility task with all checks passing"""
        input_data = {"tenant_id": str(self.tenant.id), "asset_id": str(self.asset.id)}

        result = MarketplacePublicationWorkflow._validate_asset_eligibility_task(
            input_data, self.workflow_instance, None
        )

        self.assertTrue(result["validation_passed"])
        self.assertTrue(result["validation_results"]["kyc_verified"])
        self.assertTrue(result["validation_results"]["asset_active"])
        self.assertTrue(result["validation_results"]["contract_valid"])
        self.assertTrue(result["validation_results"]["eligibility_passed"])
        self.assertEqual(len(result["validation_results"]["blockers"]), 0)

    def test_validate_asset_eligibility_task_kyc_failure(self):
        """Test validate asset eligibility task with KYC verification failure"""
        self.tenant.kyc_status = KYCStatus.UNVERIFIED
        self.tenant.save()

        input_data = {"tenant_id": str(self.tenant.id), "asset_id": str(self.asset.id)}

        with self.assertRaises(ValueError) as context:
            MarketplacePublicationWorkflow._validate_asset_eligibility_task(
                input_data, self.workflow_instance, None
            )

        self.assertIn("KYC status", str(context.exception))

    def test_validate_asset_eligibility_task_asset_not_active(self):
        """Test validate asset eligibility task with asset not active"""
        self.asset.status = AssetStatus.DRAFT
        self.asset.save()

        input_data = {"tenant_id": str(self.tenant.id), "asset_id": str(self.asset.id)}

        with self.assertRaises(ValueError) as context:
            MarketplacePublicationWorkflow._validate_asset_eligibility_task(
                input_data, self.workflow_instance, None
            )

        self.assertIn("Asset status must be ACTIVE", str(context.exception))

    def test_validate_asset_eligibility_task_no_contract(self):
        """Test validate asset eligibility task with no active contract"""
        self.contract.delete()

        input_data = {"tenant_id": str(self.tenant.id), "asset_id": str(self.asset.id)}

        with self.assertRaises(ValueError) as context:
            MarketplacePublicationWorkflow._validate_asset_eligibility_task(
                input_data, self.workflow_instance, None
            )

        self.assertIn("must have an ACTIVE contract", str(context.exception))

    def test_validate_asset_eligibility_task_invalid_contract(self):
        """Test validate asset eligibility task with invalid contract"""
        self.contract.validation_status = "INVALID"
        self.contract.save()

        input_data = {"tenant_id": str(self.tenant.id), "asset_id": str(self.asset.id)}

        with self.assertRaises(ValueError) as context:
            MarketplacePublicationWorkflow._validate_asset_eligibility_task(
                input_data, self.workflow_instance, None
            )

        self.assertIn("validation_status must be VALID or WARNING_ONLY", str(context.exception))

    def test_validate_asset_eligibility_task_dq_failure(self):
        """Test validate asset eligibility task with DQ status failure"""
        self.asset.dq_status = DQStatus.FAIL
        self.asset.save()

        input_data = {"tenant_id": str(self.tenant.id), "asset_id": str(self.asset.id)}

        with self.assertRaises(ValueError) as context:
            MarketplacePublicationWorkflow._validate_asset_eligibility_task(
                input_data, self.workflow_instance, None
            )

        self.assertIn("DQ status must be PASS or WARN", str(context.exception))

    def test_validate_asset_eligibility_task_compliance_failure(self):
        """Test validate asset eligibility task with compliance status failure"""
        self.asset.compliance_status = ComplianceStatus.FAIL
        self.asset.save()

        input_data = {"tenant_id": str(self.tenant.id), "asset_id": str(self.asset.id)}

        with self.assertRaises(ValueError) as context:
            MarketplacePublicationWorkflow._validate_asset_eligibility_task(
                input_data, self.workflow_instance, None
            )

        self.assertIn("Compliance status must be PASS or WARN", str(context.exception))

    def test_create_marketplace_listing_task_success(self):
        """Test create marketplace listing task"""
        self.workflow_instance.state_data = {
            "asset_id": str(self.asset.id),
            "tenant_id": str(self.tenant.id),
        }
        self.workflow_instance.save()

        input_data = {
            "asset_id": str(self.asset.id),
            "metadata_json": {"title": "Test Listing", "short_description": "Test description"},
            "pricing_model": PricingModel.FREE,
        }

        result = MarketplacePublicationWorkflow._create_marketplace_listing_task(
            input_data, self.workflow_instance, None
        )

        self.assertTrue(result["listing_created"])
        self.assertIsNotNone(result["listing_id"])

        listing = Listing.objects.get(id=result["listing_id"])
        self.assertEqual(listing.tenant, self.tenant)
        self.assertEqual(listing.asset, self.asset)
        self.assertEqual(listing.status, ListingStatus.DRAFT)
        self.assertEqual(listing.pricing_model, PricingModel.FREE)

    def test_create_marketplace_listing_task_existing_listing(self):
        """Test create marketplace listing task with existing listing"""
        existing_listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
            metadata_json={"title": "Existing Listing"},
        )

        self.workflow_instance.state_data = {
            "asset_id": str(self.asset.id),
            "tenant_id": str(self.tenant.id),
        }
        self.workflow_instance.save()

        input_data = {"asset_id": str(self.asset.id), "metadata_json": {"title": "New Listing"}}

        result = MarketplacePublicationWorkflow._create_marketplace_listing_task(
            input_data, self.workflow_instance, None
        )

        self.assertFalse(result["listing_created"])
        self.assertTrue(result["existing_listing"])
        self.assertEqual(result["listing_id"], str(existing_listing.id))

    def test_create_marketplace_listing_task_contract_prepopulate(self):
        """Test create marketplace listing task with contract metadata prepopulation"""
        self.workflow_instance.state_data = {
            "asset_id": str(self.asset.id),
            "tenant_id": str(self.tenant.id),
        }
        self.workflow_instance.save()

        input_data = {"asset_id": str(self.asset.id), "metadata_json": {"title": "Test Listing"}}

        result = MarketplacePublicationWorkflow._create_marketplace_listing_task(
            input_data, self.workflow_instance, None
        )

        listing = Listing.objects.get(id=result["listing_id"])
        self.assertIsNotNone(listing.metadata_json.get("license_summary"))
        self.assertEqual(listing.metadata_json.get("license_summary"), "MIT License")

    def test_configure_pricing_model_task_success(self):
        """Test configure pricing model task"""
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
            metadata_json={},
        )

        self.workflow_instance.state_data = {"listing_id": str(listing.id)}
        self.workflow_instance.save()

        input_data = {
            "pricing_model": PricingModel.REQUEST_APPROVAL,
            "price_amount": 100.0,
            "currency": "USD",
        }

        result = MarketplacePublicationWorkflow._configure_pricing_model_task(
            input_data, self.workflow_instance, None
        )

        self.assertTrue(result["pricing_configured"])
        self.assertEqual(result["pricing_model"], PricingModel.REQUEST_APPROVAL)

        listing.refresh_from_db()
        self.assertEqual(listing.pricing_model, PricingModel.REQUEST_APPROVAL)
        self.assertEqual(listing.metadata_json["price_amount"], 100.0)
        self.assertEqual(listing.metadata_json["currency"], "USD")

    def test_configure_pricing_model_task_request_approval_validation(self):
        """Test configure pricing model task with REQUEST_APPROVAL validation"""
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
            metadata_json={},
        )

        self.workflow_instance.state_data = {"listing_id": str(listing.id)}
        self.workflow_instance.save()

        input_data = {
            "pricing_model": PricingModel.REQUEST_APPROVAL,
            "price_amount": 0,  # Invalid: must be > 0
            "currency": "USD",
        }

        with self.assertRaises(ValueError) as context:
            MarketplacePublicationWorkflow._configure_pricing_model_task(
                input_data, self.workflow_instance, None
            )

        self.assertIn("requires a valid price_amount > 0", str(context.exception))

    def test_configure_license_information_task_success(self):
        """Test configure license information task"""
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
            metadata_json={},
        )

        self.workflow_instance.state_data = {
            "listing_id": str(listing.id),
            "asset_id": str(self.asset.id),
        }
        self.workflow_instance.save()

        input_data = {}

        result = MarketplacePublicationWorkflow._configure_license_information_task(
            input_data, self.workflow_instance, None
        )

        self.assertTrue(result["license_configured"])
        self.assertIsNotNone(result["license_info"].get("license_summary"))

        listing.refresh_from_db()
        self.assertEqual(listing.metadata_json["license_summary"], "MIT License")
        self.assertIn("intended_use", listing.metadata_json)
        self.assertIn("restricted_use", listing.metadata_json)

    def test_configure_license_information_task_no_contract(self):
        """Test configure license information task with no contract"""
        self.contract.delete()

        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
            metadata_json={},
        )

        self.workflow_instance.state_data = {
            "listing_id": str(listing.id),
            "asset_id": str(self.asset.id),
        }
        self.workflow_instance.save()

        input_data = {}

        result = MarketplacePublicationWorkflow._configure_license_information_task(
            input_data, self.workflow_instance, None
        )

        self.assertTrue(result["license_configured"])
        self.assertEqual(result["license_info"], {})

    def test_publish_listing_task_success(self):
        """Test publish listing task"""
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
            metadata_json={"title": "Test Listing"},
        )

        self.workflow_instance.state_data = {"listing_id": str(listing.id)}
        self.workflow_instance.save()

        input_data = {}

        result = MarketplacePublicationWorkflow._publish_listing_task(
            input_data, self.workflow_instance, None
        )

        self.assertTrue(result["published"])
        self.assertIsNotNone(result["published_at"])

        listing.refresh_from_db()
        self.assertEqual(listing.status, ListingStatus.PUBLISHED)
        self.assertIsNotNone(listing.published_at)

    def test_publish_listing_task_cannot_publish(self):
        """Test publish listing task when listing cannot be published"""
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
            metadata_json={},  # Missing title
        )

        self.workflow_instance.state_data = {"listing_id": str(listing.id)}
        self.workflow_instance.save()

        input_data = {}

        with self.assertRaises(ValueError) as context:
            MarketplacePublicationWorkflow._publish_listing_task(
                input_data, self.workflow_instance, None
            )

        self.assertIn("Cannot publish listing", str(context.exception))

    @patch("hub.apps.search.indexing.SearchIndexer.index_asset")
    def test_index_for_marketplace_search_task_success(self, mock_index_asset):
        """Test index for marketplace search task"""
        mock_search_index = MagicMock()
        mock_search_index.id = "search-index-id"
        mock_index_asset.return_value = mock_search_index

        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE,
            metadata_json={"title": "Test Listing"},
        )

        self.workflow_instance.state_data = {
            "listing_id": str(listing.id),
            "asset_id": str(self.asset.id),
        }
        self.workflow_instance.save()

        input_data = {}

        result = MarketplacePublicationWorkflow._index_for_marketplace_search_task(
            input_data, self.workflow_instance, None
        )

        self.assertTrue(result["indexed"])
        self.assertEqual(result["search_index_id"], "search-index-id")
        mock_index_asset.assert_called_once_with(self.asset)

    @patch("hub.apps.search.indexing.SearchIndexer.index_asset")
    def test_index_for_marketplace_search_task_failure_non_critical(self, mock_index_asset):
        """Test index for marketplace search task with indexing failure (non-critical)"""
        mock_index_asset.side_effect = Exception("Indexing failed")

        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE,
            metadata_json={"title": "Test Listing"},
        )

        self.workflow_instance.state_data = {
            "listing_id": str(listing.id),
            "asset_id": str(self.asset.id),
        }
        self.workflow_instance.save()

        input_data = {}

        result = MarketplacePublicationWorkflow._index_for_marketplace_search_task(
            input_data, self.workflow_instance, None
        )

        self.assertFalse(result["indexed"])
        self.assertIn("error", result)

    def test_send_notifications_task_success(self):
        """Test send notifications task"""
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE,
            metadata_json={"title": "Test Listing"},
        )

        self.workflow_instance.state_data = {"listing_id": str(listing.id)}
        self.workflow_instance.save()

        input_data = {"send_notifications": True}

        result = MarketplacePublicationWorkflow._send_notifications_task(
            input_data, self.workflow_instance, None
        )

        self.assertTrue(result["notifications_sent"])

    def test_send_notifications_task_disabled(self):
        """Test send notifications task with notifications disabled"""
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE,
            metadata_json={"title": "Test Listing"},
        )

        self.workflow_instance.state_data = {"listing_id": str(listing.id)}
        self.workflow_instance.save()

        input_data = {"send_notifications": False}

        result = MarketplacePublicationWorkflow._send_notifications_task(
            input_data, self.workflow_instance, None
        )

        self.assertFalse(result["notifications_sent"])
        self.assertEqual(result["reason"], "send_notifications is False")

    def test_audit_logging_task_success(self):
        """Test audit logging task"""
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE,
            metadata_json={"title": "Test Listing"},
            published_at=timezone.now(),
        )

        self.workflow_instance.state_data = {
            "listing_id": str(listing.id),
            "asset_id": str(self.asset.id),
            "validation_results": {"kyc_verified": True},
            "pricing_model": PricingModel.FREE,
            "license_info": {"license_summary": "MIT License"},
        }
        self.workflow_instance.save()

        input_data = {"tenant_id": str(self.tenant.id), "triggered_by_id": str(self.user.id)}

        result = MarketplacePublicationWorkflow._audit_logging_task(
            input_data, self.workflow_instance, None
        )

        self.assertIsNotNone(result["audit_event_id"])

        audit_event = AuditEvent.objects.get(id=result["audit_event_id"])
        self.assertEqual(audit_event.resource_type, "LISTING")
        self.assertEqual(audit_event.action, "MARKETPLACE_PUBLISHED")
        self.assertEqual(audit_event.tenant, self.tenant)

    # Compensation tasks

    def test_rollback_listing_creation_task(self):
        """Test rollback listing creation task"""
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
            metadata_json={},
        )

        self.workflow_instance.state_data = {
            "listing_id": str(listing.id),
            "existing_listing": False,
        }
        self.workflow_instance.save()

        result = MarketplacePublicationWorkflow._rollback_listing_creation_task(
            {}, self.workflow_instance, None
        )

        self.assertTrue(result["rolled_back"])
        self.assertFalse(Listing.objects.filter(id=listing.id).exists())

    def test_rollback_listing_creation_task_existing_listing(self):
        """Test rollback listing creation task with existing listing"""
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
            metadata_json={},
        )

        self.workflow_instance.state_data = {
            "listing_id": str(listing.id),
            "existing_listing": True,
        }
        self.workflow_instance.save()

        result = MarketplacePublicationWorkflow._rollback_listing_creation_task(
            {}, self.workflow_instance, None
        )

        self.assertTrue(result["rolled_back"])
        # Listing should still exist
        self.assertTrue(Listing.objects.filter(id=listing.id).exists())

    def test_rollback_publication_task(self):
        """Test rollback publication task"""
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE,
            metadata_json={"title": "Test Listing"},
            published_at=timezone.now(),
        )

        self.workflow_instance.state_data = {"listing_id": str(listing.id)}
        self.workflow_instance.save()

        result = MarketplacePublicationWorkflow._rollback_publication_task(
            {}, self.workflow_instance, None
        )

        self.assertTrue(result["rolled_back"])

        listing.refresh_from_db()
        self.assertEqual(listing.status, ListingStatus.UNLISTED)
        self.assertIsNone(listing.published_at)

    @patch("hub.apps.search.indexing.SearchIndexer.delete_index")
    def test_rollback_indexing_task(self, mock_delete_index):
        """Test rollback indexing task"""
        self.workflow_instance.state_data = {
            "search_index_id": "search-index-id",
            "asset_id": str(self.asset.id),
        }
        self.workflow_instance.save()

        result = MarketplacePublicationWorkflow._rollback_indexing_task(
            {}, self.workflow_instance, None
        )

        self.assertTrue(result["rolled_back"])


class MarketplacePublicationWorkflowIntegrationTest(TestCase):
    """Integration tests for marketplace publication workflow execution"""

    def setUp(self):
        """Set up test fixtures"""
        # Use unique identifiers to avoid conflicts
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant Integration {unique_id}",
            slug=f"test-tenant-integration-{unique_id}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-integration-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-integration-{unique_id}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name=f"test-integration-{unique_id}.csv",
            storage_path=f"test/test-integration-{unique_id}.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            content_sha256=f"abc123{unique_id}",
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "id", "data_type": "integer", "nullable": False}]},
            created_by=self.user,
        )

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type="ODCS",
            original_spec_version="1.0",
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
            normalization_status="NORMALIZED_OK",
            hub_contract_json={
                "info": {"title": "Test Contract"},
                "marketplace": {"license_summary": "MIT License", "intended_use": ["analytics"]},
            },
            created_by=self.user,
        )

    @patch("hub.apps.search.indexing.SearchIndexer.index_asset")
    def test_execute_workflow_success(self, mock_index_asset):
        """Test complete workflow execution"""
        mock_search_index = MagicMock()
        mock_search_index.id = "search-index-id"
        mock_index_asset.return_value = mock_search_index

        result = MarketplacePublicationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            asset_id=str(self.asset.id),
            metadata_json={"title": "Test Listing", "short_description": "Test description"},
            pricing_model=PricingModel.FREE,
            send_notifications=True,
            triggered_by_id=str(self.user.id),
        )

        self.assertTrue(result["success"])
        self.assertIsNotNone(result["listing_id"])
        self.assertTrue(result["published"])

        listing = Listing.objects.get(id=result["listing_id"])
        self.assertEqual(listing.status, ListingStatus.PUBLISHED)
        self.assertEqual(listing.pricing_model, PricingModel.FREE)
        self.assertIsNotNone(listing.published_at)

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="LISTING", action="MARKETPLACE_PUBLISHED", resource_id=str(listing.id)
        )
        self.assertTrue(audit_events.exists())

    def test_execute_workflow_validation_failure(self):
        """Test workflow execution with validation failure"""
        self.tenant.kyc_status = KYCStatus.UNVERIFIED
        self.tenant.save()

        with self.assertRaises(ValueError) as context:
            MarketplacePublicationWorkflow.execute(
                tenant_id=str(self.tenant.id),
                asset_id=str(self.asset.id),
                metadata_json={"title": "Test Listing"},
            )

        self.assertIn("eligibility validation failed", str(context.exception))

    def test_execute_workflow_with_pricing_model(self):
        """Test workflow execution with REQUEST_APPROVAL pricing model"""
        result = MarketplacePublicationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            asset_id=str(self.asset.id),
            metadata_json={"title": "Test Listing"},
            pricing_model=PricingModel.REQUEST_APPROVAL,
            price_amount=100.0,
            currency="USD",
        )

        listing = Listing.objects.get(id=result["listing_id"])
        self.assertEqual(listing.pricing_model, PricingModel.REQUEST_APPROVAL)
        self.assertEqual(listing.metadata_json["price_amount"], 100.0)
        self.assertEqual(listing.metadata_json["currency"], "USD")


class MarketplacePublicationWorkflowE2ETest(TestCase):
    """E2E tests for marketplace publication journey"""

    def setUp(self):
        """Set up test fixtures"""
        # Use unique identifiers to avoid conflicts
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant E2E {unique_id}",
            slug=f"test-tenant-e2e-{unique_id}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-e2e-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-e2e-{unique_id}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type="ODCS",
            original_spec_version="1.0",
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
            normalization_status="NORMALIZED_OK",
            hub_contract_json={
                "info": {"title": "Test Contract"},
                "marketplace": {
                    "license_summary": "MIT License",
                    "intended_use": ["analytics", "machine_learning"],
                    "restricted_use": ["resale"],
                },
            },
            created_by=self.user,
        )

    @patch("hub.apps.search.indexing.SearchIndexer.index_asset")
    def test_complete_marketplace_publication_journey(self, mock_index_asset):
        """Test complete marketplace publication journey from start to finish"""
        mock_search_index = MagicMock()
        mock_search_index.id = "search-index-id"
        mock_index_asset.return_value = mock_search_index

        # Execute workflow
        result = MarketplacePublicationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            asset_id=str(self.asset.id),
            metadata_json={
                "title": "Premium Data Product",
                "short_description": "High-quality dataset for analytics",
                "tags": ["analytics", "finance"],
            },
            pricing_model=PricingModel.REQUEST_APPROVAL,
            price_amount=500.0,
            currency="USD",
            send_notifications=True,
            triggered_by_id=str(self.user.id),
        )

        # Verify workflow completed successfully
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["listing_id"])
        self.assertTrue(result["published"])

        # Verify listing state
        listing = Listing.objects.get(id=result["listing_id"])
        self.assertEqual(listing.status, ListingStatus.PUBLISHED)
        self.assertEqual(listing.pricing_model, PricingModel.REQUEST_APPROVAL)
        self.assertEqual(listing.metadata_json["price_amount"], 500.0)
        self.assertEqual(listing.metadata_json["currency"], "USD")
        self.assertEqual(listing.metadata_json["title"], "Premium Data Product")
        self.assertIsNotNone(listing.published_at)

        # Verify license information was configured
        self.assertEqual(listing.metadata_json["license_summary"], "MIT License")
        self.assertIn("intended_use", listing.metadata_json)
        self.assertIn("restricted_use", listing.metadata_json)

        # Verify search indexing was called
        mock_index_asset.assert_called_once_with(self.asset)

        # Verify audit event
        audit_event = AuditEvent.objects.filter(
            resource_type="LISTING", action="MARKETPLACE_PUBLISHED", resource_id=str(listing.id)
        ).first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.actor_user, self.user)

        # Verify workflow instance
        workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)
        self.assertEqual(workflow_instance.tenant, self.tenant)

    def test_marketplace_publication_with_existing_listing(self):
        """Test marketplace publication when listing already exists"""
        existing_listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
            metadata_json={"title": "Existing Listing"},
        )

        result = MarketplacePublicationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            asset_id=str(self.asset.id),
            metadata_json={"title": "Updated Listing"},
        )

        # Should use existing listing
        self.assertEqual(result["listing_id"], str(existing_listing.id))

        # Listing should be published
        existing_listing.refresh_from_db()
        self.assertEqual(existing_listing.status, ListingStatus.PUBLISHED)


class MarketplacePublicationWorkflowStepEventsTest(TestCase):
    """Integration tests to verify MarketplacePublicationWorkflow receives step events"""

    def setUp(self):
        """Set up test fixtures"""
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant Step Events {unique_id}",
            slug=f"test-tenant-step-events-{unique_id}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-step-events-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-step-events-{unique_id}",
            name="Test Asset Step Events",
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type="ODCS",
            original_spec_version="1.0",
            status=ContractStatus.ACTIVE,
            validation_status="VALID",
            normalization_status="NORMALIZED_OK",
            hub_contract_json={
                "info": {"title": "Test Contract", "description": "Test contract description"},
                "marketplace": {
                    "license_summary": "MIT License",
                    "intended_use": "Data analysis",
                    "restricted_use": "No commercial use",
                },
            },
            created_by=self.user,
        )

    def test_marketplace_publication_workflow_receives_step_events(self):
        """Test that MarketplacePublicationWorkflow receives step.started and step.completed events"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        MarketplacePublicationWorkflow.register_workflow(registry)
        MarketplacePublicationWorkflow.register_tasks(engine)

        # Execute workflow
        result = MarketplacePublicationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            asset_id=str(self.asset.id),
            metadata_json={"title": "Test Listing"},
            pricing_model=PricingModel.FREE,
            send_notifications=False,
            triggered_by_id=str(self.user.id),
            engine=engine,
            registry=registry,
        )

        # Verify workflow completed successfully
        self.assertTrue(result["success"])
        self.assertIn("workflow_instance_id", result)

        # Get workflow instance to find its ID
        workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])

        # Query actual events from database (no mocks - real event persistence)
        step_started_events = Event.objects.filter(
            event_type="workflow.step.started", data__workflow_instance_id=str(workflow_instance.id)
        ).order_by("created_at")

        step_completed_events = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(workflow_instance.id),
        ).order_by("created_at")

        # MarketplacePublicationWorkflow has 8 steps, so we should have step events
        self.assertGreater(
            step_started_events.count(),
            0,
            f"Expected step.started events, got {step_started_events.count()}",
        )
        self.assertGreater(
            step_completed_events.count(),
            0,
            f"Expected step.completed events, got {step_completed_events.count()}",
        )

        # Collect event data
        step_started_data = [event.data for event in step_started_events]
        step_completed_data = [event.data for event in step_completed_events]

        # Verify each step event has required metadata
        for event_data in step_started_data:
            self.assertIn("workflow_instance_id", event_data)
            self.assertIn("step_index", event_data)
            self.assertIn("step_name", event_data)
            self.assertIn("step_type", event_data)
            self.assertIn("progress_percentage", event_data)
            self.assertIsInstance(event_data["step_index"], int)
            self.assertIsInstance(event_data["progress_percentage"], (int, float))
            self.assertGreaterEqual(event_data["progress_percentage"], 0.0)
            self.assertLessEqual(event_data["progress_percentage"], 100.0)

        for event_data in step_completed_data:
            self.assertIn("workflow_instance_id", event_data)
            self.assertIn("step_index", event_data)
            self.assertIn("step_name", event_data)
            self.assertIn("progress_percentage", event_data)
            self.assertIn("duration_ms", event_data)
            self.assertIsInstance(event_data["step_index"], int)
            self.assertIsInstance(event_data["progress_percentage"], (int, float))
            self.assertIsInstance(event_data["duration_ms"], int)
            self.assertGreaterEqual(event_data["progress_percentage"], 0.0)
            self.assertLessEqual(event_data["progress_percentage"], 100.0)
            self.assertGreaterEqual(event_data["duration_ms"], 0)

        # Verify step names match expected workflow steps
        expected_step_names = [
            "validate_asset_eligibility",
            "create_marketplace_listing",
            "configure_pricing_model",
            "configure_license_information",
            "publish_listing",
            "index_for_marketplace_search",
            "send_notifications",
            "audit_logging",
        ]

        actual_step_names = [event_data["step_name"] for event_data in step_started_data]
        for expected_name in expected_step_names:
            self.assertIn(
                expected_name,
                actual_step_names,
                f"Expected step '{expected_name}' not found in step events",
            )

        # Verify progress increases or stays the same as steps progress
        started_progresses = sorted(
            [e["progress_percentage"] for e in step_started_data],
            key=lambda x: step_started_data[
                [e["progress_percentage"] for e in step_started_data].index(x)
            ]["step_index"],
        )
        for i in range(1, len(started_progresses)):
            self.assertGreaterEqual(
                started_progresses[i],
                started_progresses[i - 1] - 1.0,
                "Progress should generally increase or stay the same",
            )

    def test_marketplace_publication_workflow_step_events_no_breaking_changes(self):
        """Regression test: Verify workflow execution still works correctly with step events"""

        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        MarketplacePublicationWorkflow.register_workflow(registry)
        MarketplacePublicationWorkflow.register_tasks(engine)

        # Execute workflow
        result = MarketplacePublicationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            asset_id=str(self.asset.id),
            metadata_json={"title": "Test Listing Regression"},
            pricing_model=PricingModel.FREE,
            send_notifications=False,
            triggered_by_id=str(self.user.id),
            engine=engine,
            registry=registry,
        )

        # Verify workflow completed successfully (no breaking changes)
        self.assertTrue(result["success"])
        self.assertIn("workflow_instance_id", result)
        self.assertIn("listing_id", result)

        # Verify listing was created and published
        listing = Listing.objects.get(id=result["listing_id"])
        self.assertEqual(listing.tenant, self.tenant)
        self.assertEqual(listing.asset, self.asset)
        self.assertEqual(listing.status, ListingStatus.PUBLISHED)
        self.assertIsNotNone(listing.published_at)

        # Verify workflow instance completed successfully
        workflow_instance = WorkflowInstance.objects.get(id=result["workflow_instance_id"])
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)

        # Verify progress is stored in state_data
        self.assertIn("progress_percentage", workflow_instance.state_data)
        self.assertEqual(workflow_instance.state_data["progress_percentage"], 100.0)

        # Verify audit event was created
        audit_event = AuditEvent.objects.filter(
            resource_type="LISTING", action="MARKETPLACE_PUBLISHED", resource_id=str(listing.id)
        ).first()
        self.assertIsNotNone(audit_event)
