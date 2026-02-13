"""
Phase 18.1.2 — Integration tests: REST API invokes business rules (no mocks).

When create/update/delete is performed via REST (real HTTP, real DB), the relevant
business rule is invoked. When validation fails, API returns 400 (or appropriate
error) and no mutation occurs. Tests use real DB and real business rule classes;
no mocks/stubs of business rules or persistence. Rule execution is asserted via
validation failure path (invalid data -> 400 and no mutation) or success path
(valid data -> success and mutation).

Implementation order: Contracts (18.2) -> Assets (18.3) -> Datasets (18.4) ->
Marketplace (18.5) -> Files (18.6) -> remaining apps (18.7).
"""

import json

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.assets.tests.factories import AssetFactory
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.tenants.models import KYCStatus
from hub.apps.users.models import Role, UserRole, UserStatus
from tests.factories import TenantFactory, UserFactory


def _minimal_odcs_raw():
    """Minimal valid ODCS contract content (JSON)."""
    return json.dumps(
        {
            "id": "test-contract",
            "info": {"version": "1.0", "name": "Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string", "nullable": False}]},
        }
    )


def _valid_odps_raw():
    """Minimal valid ODPS document (JSON) for create_product / create_odps."""
    return json.dumps(
        {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-phase18",
                        "name": "Test Product",
                        "description": "Phase 18 ODPS test",
                    }
                },
                "dataSchema": {
                    "fields": [
                        {"name": "id", "type": "string", "description": "ID"},
                        {"name": "name", "type": "string", "description": "Name"},
                    ]
                },
            },
        }
    )


class TestContractsRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.2 — Contracts: REST create/update/delete invokes ContractsBusinessRules.

    Tests use real DB and real ContractsBusinessRules; no mocks.
    """

    def setUp(self):
        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant()
        self.tenant_b = TenantFactory.create_tenant()
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        self.user_b = UserFactory.create_user(tenant=self.tenant_b, status=UserStatus.ACTIVE)
        self.asset_a = AssetFactory.create_asset(tenant=self.tenant_a)
        # Grant TENANT_ADMIN to user_a so contract delete is allowed by service
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant_a,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator"},
        )
        UserRole.objects.get_or_create(user=self.user_a, role=role)

    def test_contract_create_rejects_asset_from_other_tenant_returns_400_no_mutation(self):
        """
        When contract create is called with asset_id belonging to another tenant,
        business rule rejects; API returns 400 and no contract is created.
        """
        self.client.force_authenticate(user=self.user_b)
        count_before = Contract.objects.count()

        payload = {
            "original_raw": _minimal_odcs_raw(),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODCS,
            "asset_id": str(self.asset_a.id),
        }
        response = self.client.post("/api/v1/contracts/", data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Contract.objects.count(), count_before)
        self.assertIn("error", response.json())
        # Business rule error: asset does not exist for tenant
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            response.json().get("code", ""),
            msg="Expected business rules validation code",
        )

    def test_contract_create_valid_succeeds_and_rule_invoked(self):
        """
        Valid contract create (asset in same tenant) succeeds; business rule
        is invoked (no rejection) and contract is created.
        """
        self.client.force_authenticate(user=self.user_a)
        count_before = Contract.objects.count()

        payload = {
            "original_raw": _minimal_odcs_raw(),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODCS,
            "asset_id": str(self.asset_a.id),
        }
        response = self.client.post("/api/v1/contracts/", data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Contract.objects.count(), count_before + 1)
        self.assertIn("id", response.json())

    def test_contract_update_rejects_retired_returns_400_no_mutation(self):
        """
        When contract update is called on a RETIRED contract, business rule
        rejects; API returns 400 and contract is not updated.
        """
        self.client.force_authenticate(user=self.user_a)
        contract = Contract.objects.create(
            tenant=self.tenant_a,
            asset=self.asset_a,
            version=1,
            original_raw=_minimal_odcs_raw(),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            status=ContractStatus.RETIRED,
        )
        original_raw_before = contract.original_raw
        new_raw = json.dumps(
            {
                "id": "updated",
                "info": {"version": "1.0", "name": "Updated"},
                "schema": {"fields": [{"name": "id", "data_type": "string", "nullable": False}]},
            }
        )

        response = self.client.patch(
            f"/api/v1/contracts/{contract.id}/",
            data={"original_raw": new_raw, "original_format": OriginalFormat.JSON},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        contract.refresh_from_db()
        self.assertEqual(contract.original_raw, original_raw_before)
        self.assertIn("BUSINESS_RULES_VALIDATION", response.json().get("code", ""))

    def test_contract_delete_rejects_when_referenced_by_scheduled_ingestion_returns_400(self):
        """
        When contract delete is called and contract is referenced by a scheduled
        ingestion, business rule rejects; API returns 400 and contract is not deleted.
        """
        self.client.force_authenticate(user=self.user_a)
        contract = Contract.objects.create(
            tenant=self.tenant_a,
            asset=self.asset_a,
            version=1,
            original_raw=_minimal_odcs_raw(),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            status=ContractStatus.DRAFT,
        )
        ScheduledIngestion.objects.create(
            tenant=self.tenant_a,
            contract=contract,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket", "region": "us-east-1"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=r".*\.csv",  # Valid regex: match .csv files
            status=ScheduledIngestionStatus.ACTIVE,
        )
        count_before = Contract.objects.count()

        response = self.client.delete(f"/api/v1/contracts/{contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Contract.objects.count(), count_before)
        self.assertIn("BUSINESS_RULES_VALIDATION", response.json().get("code", ""))

    def test_contract_delete_valid_succeeds(self):
        """
        Valid contract delete (not referenced) succeeds; business rule allows
        and contract is soft-deleted (status RETIRED).
        """
        self.client.force_authenticate(user=self.user_a)
        contract = Contract.objects.create(
            tenant=self.tenant_a,
            asset=self.asset_a,
            version=1,
            original_raw=_minimal_odcs_raw(),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            status=ContractStatus.DRAFT,
        )

        response = self.client.delete(f"/api/v1/contracts/{contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        contract.refresh_from_db()
        self.assertEqual(contract.status, ContractStatus.RETIRED)


class TestODPSCreateProductBusinessRulesAlignment(TestCase):
    """
    Phase 18.2.4 — create_product / ODPS create: REST invokes ODPSBusinessRules.

    Before ODPS create, validate_odps_structure and validate_odps_version are
    invoked; invalid ODPS returns 400 with BUSINESS_RULES_VALIDATION.
    Tests use real DB and real ODPSBusinessRules; no mocks.
    """

    def setUp(self):
        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant()
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        # Ensure user has tenant for create_product
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])

    def test_create_product_rejects_invalid_odps_structure_returns_400(self):
        """
        When create_product is called with ODPS missing required 'product' field,
        ODPSBusinessRules rejects; API returns 400 and no workflow is started
        with invalid payload (validation happens before workflow).
        """
        self.client.force_authenticate(user=self.user_a)
        invalid_odps = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                # missing "product" -> structure validation fails
            }
        )
        payload = {
            "original_raw": invalid_odps,
            "original_format": OriginalFormat.JSON,
        }
        response = self.client.post(
            "/api/v1/contracts/products/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            data.get("code", ""),
            msg="Expected business rules validation code for invalid ODPS structure",
        )

    def test_create_product_accepts_valid_odps_returns_202(self):
        """
        When create_product is called with valid ODPS, business rules pass and
        workflow is started; API returns 202 with workflow_instance_id.
        """
        self.client.force_authenticate(user=self.user_a)
        payload = {
            "original_raw": _valid_odps_raw(),
            "original_format": OriginalFormat.JSON,
        }
        response = self.client.post(
            "/api/v1/contracts/products/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()
        self.assertIn("workflow_instance_id", data)
        self.assertEqual(data.get("status"), "RUNNING")


class TestODPSServiceCreateOdpsBusinessRulesAlignment(TestCase):
    """
    Phase 18.2.4 — ODPSService.create_odps invokes ODPSBusinessRules.

    When create_odps is called with invalid ODPS, service raises ValidationError
    with code BUSINESS_RULES_VALIDATION before any contract is created.
    Tests use real DB and real ODPSBusinessRules; no mocks.
    """

    def setUp(self):
        self.tenant_a = TenantFactory.create_tenant()
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)

    def test_create_odps_rejects_invalid_structure_raises_validation_error(self):
        """
        ODPSService.create_odps with ODPS missing 'product' raises ValidationError
        with code BUSINESS_RULES_VALIDATION; no contract is created.
        """
        from hub.apps.contracts.services import ODPSService
        from hub.apps.core.services.base import ValidationError as ServiceValidationError

        odps_service = ODPSService(
            tenant_id=str(self.tenant_a.id),
            user_id=str(self.user_a.id),
        )
        invalid_odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
            }
        )
        count_before = Contract.objects.count()
        with self.assertRaises(ServiceValidationError) as ctx:
            odps_service.create_odps(
                odps_raw=invalid_odps_raw,
                odps_format="json",
                tenant_id=str(self.tenant_a.id),
                user_id=str(self.user_a.id),
            )
        self.assertEqual(ctx.exception.code, "BUSINESS_RULES_VALIDATION")
        self.assertEqual(Contract.objects.count(), count_before)

    def test_create_odps_accepts_valid_odps_creates_contract(self):
        """
        ODPSService.create_odps with valid ODPS passes business rules and creates contract.
        """
        from hub.apps.contracts.services import ODPSService

        odps_service = ODPSService(
            tenant_id=str(self.tenant_a.id),
            user_id=str(self.user_a.id),
        )
        count_before = Contract.objects.filter(
            tenant_id=self.tenant_a.id,
            original_spec_type=OriginalSpecType.ODPS,
        ).count()
        contract = odps_service.create_odps(
            odps_raw=_valid_odps_raw(),
            odps_format="json",
            tenant_id=str(self.tenant_a.id),
            user_id=str(self.user_a.id),
        )
        self.assertIsNotNone(contract.id)
        self.assertEqual(contract.original_spec_type, OriginalSpecType.ODPS)
        self.assertEqual(
            Contract.objects.filter(
                tenant_id=self.tenant_a.id,
                original_spec_type=OriginalSpecType.ODPS,
            ).count(),
            count_before + 1,
        )


# Phase 18.3 — Assets: REST create/update/delete invokes AssetsBusinessRules.


class TestAssetsRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.3 — Assets: REST create/update/delete invokes AssetsBusinessRules.

    Tests use real DB and real AssetsBusinessRules; no mocks.
    """

    def setUp(self):
        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant(kyc_status=KYCStatus.VERIFIED)
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])

    def test_asset_create_rejects_duplicate_key_returns_4xx_no_mutation(self):
        """
        When asset create is called with duplicate key (same tenant),
        service rejects; API returns 4xx and no second asset is created.
        """
        self.client.force_authenticate(user=self.user_a)
        AssetFactory.create_asset(
            tenant=self.tenant_a,
            key="duplicate-key-asset",
            name="First Asset",
        )
        count_before = Asset.objects.filter(tenant_id=self.tenant_a.id).count()

        payload = {
            "key": "duplicate-key-asset",
            "name": "Second Asset",
            "description": "Description",
        }
        response = self.client.post("/api/v1/assets/", data=payload, format="json")

        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT),
            msg="Expected 400 or 409 for duplicate key",
        )
        self.assertEqual(
            Asset.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before,
        )
        data = response.json()
        self.assertIn("error", data)
        self.assertIn(
            data.get("code", ""),
            ("CONFLICT", "CONFLICT_ERROR", "BUSINESS_RULES_VALIDATION"),
            msg="Expected conflict or validation code for duplicate key",
        )

    def test_asset_create_valid_succeeds(self):
        """
        Valid asset create succeeds; business rules pass and asset is created.
        """
        self.client.force_authenticate(user=self.user_a)
        count_before = Asset.objects.filter(tenant_id=self.tenant_a.id).count()

        payload = {
            "key": "test-asset-phase18",
            "name": "Test Asset Phase 18",
            "description": "Description",
            "domain": "test",
        }
        response = self.client.post("/api/v1/assets/", data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Asset.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before + 1,
        )
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["key"], "test-asset-phase18")
        self.assertEqual(data["name"], "Test Asset Phase 18")

    def test_asset_update_rejects_invalid_status_transition_returns_400(self):
        """
        When asset update is called with invalid status transition (e.g. DRAFT -> PUBLIC),
        business rule rejects; API returns 400 and asset is not updated.
        """
        from hub.apps.assets.models import AssetStatus

        self.client.force_authenticate(user=self.user_a)
        asset = AssetFactory.create_asset(
            tenant=self.tenant_a,
            status=AssetStatus.DRAFT,
            created_by=self.user_a,
        )
        original_name = asset.name

        # DRAFT -> PUBLIC is invalid (only DRAFT -> ACTIVE or RETIRED allowed)
        response = self.client.patch(
            f"/api/v1/assets/{asset.id}/",
            data={"status": AssetStatus.PUBLIC, "version": asset.version},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.DRAFT)
        self.assertEqual(asset.name, original_name)
        data = response.json()
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            data.get("code", ""),
            msg="Expected business rules validation code for invalid status transition",
        )

    def test_asset_delete_rejects_when_active_listings_returns_400(self):
        """
        When asset delete is called and asset has active marketplace listings,
        business rule rejects; API returns 400 and asset is not retired.
        """
        from hub.apps.assets.models import AssetStatus
        from hub.apps.marketplace.models import Listing, ListingStatus

        self.client.force_authenticate(user=self.user_a)
        asset = AssetFactory.create_asset(tenant=self.tenant_a, status=AssetStatus.ACTIVE)
        Listing.objects.create(
            asset=asset,
            tenant=self.tenant_a,
            status=ListingStatus.PUBLISHED,
        )

        response = self.client.delete(f"/api/v1/assets/{asset.id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        data = response.json()
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            data.get("code", ""),
            msg="Expected business rules validation code when retirement blocked by listings",
        )

    def test_asset_delete_valid_succeeds(self):
        """
        Valid asset delete (no active listings) succeeds; business rules pass
        and asset is soft-deleted (status RETIRED).
        """
        from hub.apps.assets.models import AssetStatus

        self.client.force_authenticate(user=self.user_a)
        asset = AssetFactory.create_asset(tenant=self.tenant_a, status=AssetStatus.ACTIVE)

        response = self.client.delete(f"/api/v1/assets/{asset.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.RETIRED)


# Placeholder test classes for Phase 18.4–18.7 (datasets, marketplace,
# files, governance, compliance, dq, mesh, virtualization, scheduled_ingestion,
# integrations, social). Add tests as each app’s service layer is aligned
# with business rules (tasks 18.2–18.7).


class TestDatasetsRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.4 — Datasets: REST create/update/delete invokes DatasetsBusinessRules.
    Tests use real DB and real DatasetsBusinessRules; no mocks.
    """

    def setUp(self):
        from hub.apps.files.models import FileStatus
        from hub.apps.files.tests.factories import FileFactory

        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant(kyc_status=KYCStatus.VERIFIED)
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])
        self.asset_a = AssetFactory.create_asset(tenant=self.tenant_a)
        self.file_a = FileFactory.create_file(
            tenant=self.tenant_a,
            name="dataset-phase18.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            created_by=self.user_a,
        )

    def test_dataset_create_valid_succeeds(self):
        """Valid dataset create succeeds; business rules pass and dataset is created."""
        self.client.force_authenticate(user=self.user_a)
        from hub.apps.datasets.models import Dataset

        count_before = Dataset.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {"file_id": str(self.file_a.id), "asset_id": str(self.asset_a.id)}
        response = self.client.post("/api/v1/datasets/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Dataset.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before + 1,
        )
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data.get("format"), "CSV")

    def test_dataset_delete_when_current_succeeds(self):
        """Delete on current version succeeds; business rule allows it (with warning), service unsets is_current before deletion."""
        from hub.apps.datasets.models import Dataset
        from hub.apps.datasets.tests.factories import DatasetFactory

        self.client.force_authenticate(user=self.user_a)
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant_a,
            file=self.file_a,
            asset=self.asset_a,
            format="CSV",
            version=1,
            created_by=self.user_a,
        )
        # Ensure dataset is marked as current
        dataset.is_current = True
        dataset.save(update_fields=["is_current"])

        count_before = Dataset.objects.filter(tenant_id=self.tenant_a.id).count()
        response = self.client.delete(f"/api/v1/datasets/{dataset.id}/")
        # Business rule allows deletion of current versions (with warning), service unsets is_current before deletion
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            Dataset.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before - 1,
        )

    def test_dataset_delete_when_has_child_versions_returns_400(self):
        """Delete on version with child versions is rejected; API returns 400 BUSINESS_RULES_VALIDATION."""
        from hub.apps.datasets.models import Dataset
        from hub.apps.datasets.tests.factories import DatasetFactory

        self.client.force_authenticate(user=self.user_a)
        parent = DatasetFactory.create_dataset(
            tenant=self.tenant_a,
            file=self.file_a,
            asset=self.asset_a,
            format="CSV",
            version=1,
            created_by=self.user_a,
        )
        parent.is_current = False
        parent.save(update_fields=["is_current"])
        child = DatasetFactory.create_dataset(
            tenant=self.tenant_a,
            file=self.file_a,
            asset=self.asset_a,
            format="CSV",
            version=2,
            created_by=self.user_a,
        )
        child.parent_version = parent
        child.is_current = True
        child.save(update_fields=["parent_version_id", "is_current"])
        count_before = Dataset.objects.filter(tenant_id=self.tenant_a.id).count()
        response = self.client.delete(f"/api/v1/datasets/{parent.id}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Dataset.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before,
        )
        self.assertIn("BUSINESS_RULES_VALIDATION", response.json().get("code", ""))


class TestMarketplaceRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.5 — Marketplace: REST create/update/delete invokes MarketplaceBusinessRules.

    Tests use real DB and real MarketplaceBusinessRules; no mocks.
    """

    def setUp(self):
        from hub.apps.assets.models import AssetStatus

        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant(kyc_status=KYCStatus.VERIFIED)
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])
        self.asset_a = AssetFactory.create_asset(tenant=self.tenant_a, status=AssetStatus.ACTIVE)

    def test_listing_create_valid_succeeds(self):
        """Valid listing create (ACTIVE asset, KYC VERIFIED tenant) succeeds; business rules pass."""
        from hub.apps.marketplace.models import Listing

        self.client.force_authenticate(user=self.user_a)
        count_before = Listing.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "asset_id": str(self.asset_a.id),
            "title": "Test Listing Phase 18",
            "short_description": "Short desc",
            "pricing_model": "FREE",
        }
        response = self.client.post("/api/v1/marketplace/listings/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Listing.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before + 1,
        )
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data.get("metadata_json", {}).get("title"), "Test Listing Phase 18")

    def test_listing_create_invalid_asset_not_active_returns_400(self):
        """Listing create with non-ACTIVE asset is rejected; API returns 400 BUSINESS_RULES_VALIDATION."""
        from hub.apps.assets.models import AssetStatus
        from hub.apps.marketplace.models import Listing

        self.client.force_authenticate(user=self.user_a)
        draft_asset = AssetFactory.create_asset(tenant=self.tenant_a, status=AssetStatus.DRAFT)
        count_before = Listing.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "asset_id": str(draft_asset.id),
            "title": "Test Listing",
            "short_description": "Short",
            "pricing_model": "FREE",
        }
        response = self.client.post("/api/v1/marketplace/listings/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Listing.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before,
        )
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            response.json().get("code", ""),
            msg="Expected business rules validation code when asset not ACTIVE",
        )

    def test_listing_delete_when_active_orders_returns_400(self):
        """Delete published listing with active orders is rejected; API returns 400 BUSINESS_RULES_VALIDATION."""
        from hub.apps.marketplace.models import Listing, ListingStatus, Order, OrderStatus

        self.client.force_authenticate(user=self.user_a)
        listing = Listing.objects.create(
            tenant=self.tenant_a,
            asset=self.asset_a,
            status=ListingStatus.PUBLISHED,
            pricing_model="FREE",
            metadata_json={"title": "Published", "short_description": "Short"},
        )
        Order.objects.create(
            tenant=self.tenant_a,
            listing=listing,
            created_by=self.user_a,
            status=OrderStatus.REQUESTED,
        )
        response = self.client.delete(f"/api/v1/marketplace/listings/{listing.id}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        listing.refresh_from_db()
        self.assertNotEqual(listing.status, ListingStatus.DELETED)
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            response.json().get("code", ""),
            msg="Expected business rules validation code when listing has active orders",
        )

    def test_listing_delete_valid_succeeds(self):
        """Valid listing delete (draft, or published with no active orders) succeeds."""
        from hub.apps.marketplace.models import Listing, ListingStatus

        self.client.force_authenticate(user=self.user_a)
        listing = Listing.objects.create(
            tenant=self.tenant_a,
            asset=self.asset_a,
            status=ListingStatus.DRAFT,
            pricing_model="FREE",
            metadata_json={"title": "Draft", "short_description": "Short"},
        )
        response = self.client.delete(f"/api/v1/marketplace/listings/{listing.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        listing.refresh_from_db()
        self.assertEqual(listing.status, ListingStatus.DELETED)


class TestFilesRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.6 — Files: REST create/update/delete invokes FilesBusinessRules.

    Tests use real DB and real FilesBusinessRules; no mocks.
    """

    def setUp(self):
        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant()
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])

    def test_file_create_valid_succeeds(self):
        """Valid file init (allowed type, size within limit) succeeds; business rules pass."""
        from hub.apps.files.models import File

        self.client.force_authenticate(user=self.user_a)
        count_before = File.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "name": "data.csv",
            "content_type": "text/csv",
            "size": 1024,
            "upload_method": "browser",
        }
        response = self.client.post("/api/v1/files/init/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            File.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before + 1,
        )
        data = response.json()
        self.assertIn("file_id", data)

    def test_file_create_invalid_type_returns_400(self):
        """File init with disallowed file type is rejected; API returns 400 BUSINESS_RULES_VALIDATION."""
        from hub.apps.files.models import File

        self.client.force_authenticate(user=self.user_a)
        count_before = File.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "name": "script.exe",
            "content_type": "application/octet-stream",
            "size": 100,
            "upload_method": "browser",
        }
        response = self.client.post("/api/v1/files/init/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            File.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before,
        )
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            response.json().get("code", ""),
            msg="Expected business rules validation code for disallowed file type",
        )

    def test_file_complete_invalid_state_returns_400(self):
        """Complete upload when file is already ACTIVE is rejected; API returns 400 BUSINESS_RULES_VALIDATION."""
        from hub.apps.files.models import File, FileStatus

        self.client.force_authenticate(user=self.user_a)
        file_obj = File.objects.create(
            tenant=self.tenant_a,
            name="done.csv",
            content_type="text/csv",
            size=100,
            storage_path=f"{self.tenant_a.id}/test-uuid/done.csv",
            status=FileStatus.ACTIVE,
            metadata_json={},
        )
        response = self.client.post(
            f"/api/v1/files/{file_obj.id}/complete/",
            data={"content_sha256": "a" * 64},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            response.json().get("code", ""),
            msg="Expected business rules validation code when file not PENDING/UPLOADING",
        )

    def test_file_delete_valid_succeeds(self):
        """Valid file delete (same-tenant file) succeeds; soft delete applied."""
        from hub.apps.files.models import File, FileStatus

        self.client.force_authenticate(user=self.user_a)
        file_obj = File.objects.create(
            tenant=self.tenant_a,
            name="to_delete.csv",
            content_type="text/csv",
            size=100,
            storage_path=f"{self.tenant_a.id}/test-uuid/to_delete.csv",
            status=FileStatus.ACTIVE,
            metadata_json={},
        )
        response = self.client.delete(f"/api/v1/files/{file_obj.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.DELETED)


class TestGovernanceRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.7.1 — Governance: REST create/approve/reject invokes GovernanceBusinessRules.

    Tests use real DB and real GovernanceBusinessRules; no mocks.
    """

    def setUp(self):
        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant()
        self.tenant_b = TenantFactory.create_tenant()
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        self.user_b = UserFactory.create_user(tenant=self.tenant_b, status=UserStatus.ACTIVE)
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])
        if not getattr(self.user_b, "tenant", None):
            self.user_b.tenant = self.tenant_b
            self.user_b.save(update_fields=["tenant_id"])
        self.asset_a = AssetFactory.create_asset(tenant=self.tenant_a)
        self.asset_b = AssetFactory.create_asset(tenant=self.tenant_b)

    def test_governance_create_valid_succeeds(self):
        """Valid access request create (same-tenant asset, reason) succeeds; business rules pass."""
        from hub.apps.governance.models import AccessRequest

        self.client.force_authenticate(user=self.user_a)
        count_before = AccessRequest.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "asset_id": str(self.asset_a.id),
            "reason": "Need read access for analysis",
            "requested_access_type": "READ",
        }
        response = self.client.post(
            "/api/v1/governance/access-requests/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            AccessRequest.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before + 1,
        )
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data.get("status"), "PENDING")

    def test_governance_create_asset_from_other_tenant_returns_400(self):
        """Create with asset_id from another tenant is rejected; API returns 400 BUSINESS_RULES_VALIDATION."""
        from hub.apps.governance.models import AccessRequest

        self.client.force_authenticate(user=self.user_a)
        count_before = AccessRequest.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "asset_id": str(self.asset_b.id),
            "reason": "Need access",
            "requested_access_type": "READ",
        }
        response = self.client.post(
            "/api/v1/governance/access-requests/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            AccessRequest.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before,
        )
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            response.json().get("code", ""),
            msg="Expected business rules validation when asset not in tenant",
        )

    def test_governance_approve_when_not_pending_returns_400(self):
        """Approve when access request is not PENDING is rejected; API returns 400 BUSINESS_RULES_VALIDATION."""
        from hub.apps.governance.models import AccessRequest, AccessRequestStatus

        self.client.force_authenticate(user=self.user_a)
        ar = AccessRequest.objects.create(
            tenant=self.tenant_a,
            requested_by=self.user_a,
            asset=self.asset_a,
            reason="Need access",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED.value,
        )
        response = self.client.post(
            f"/api/v1/governance/access-requests/{ar.id}/approve/",
            data={},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            response.json().get("code", ""),
            msg="Expected business rules validation when approving non-pending request",
        )

    def test_governance_approve_valid_succeeds(self):
        """Valid approve (PENDING request, same-tenant approver with role) succeeds."""
        from hub.apps.governance.models import AccessRequest, AccessRequestStatus
        from hub.apps.users.models import Role, UserRole

        self.client.force_authenticate(user=self.user_a)
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant_a,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant admin"},
        )
        UserRole.objects.get_or_create(user=self.user_a, role=role)
        ar = AccessRequest.objects.create(
            tenant=self.tenant_a,
            requested_by=self.user_b,
            asset=self.asset_a,
            reason="Need access",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING.value,
        )
        response = self.client.post(
            f"/api/v1/governance/access-requests/{ar.id}/approve/",
            data={},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ar.refresh_from_db()
        self.assertEqual(ar.status, AccessRequestStatus.APPROVED.value)


class TestComplianceRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.7.2 — Compliance: REST create invokes ComplianceBusinessRules.

    Tests use real DB and real ComplianceBusinessRules; no mocks.
    """

    def setUp(self):
        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant()
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])
        self.asset_a = AssetFactory.create_asset(tenant=self.tenant_a)

    def test_compliance_run_create_valid_succeeds(self):
        """Valid compliance run create (same-tenant asset) succeeds; business rules pass."""
        from hub.apps.compliance.models import ComplianceRun

        self.client.force_authenticate(user=self.user_a)
        count_before = ComplianceRun.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "asset_id": str(self.asset_a.id),
            "scan_mode": "internal",
        }
        response = self.client.post(
            "/api/v1/compliance/runs/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            ComplianceRun.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before + 1,
        )
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data.get("status"), "PENDING")

    def test_compliance_run_create_no_resource_returns_400(self):
        """Create with no asset/dataset/file is rejected; API returns 400 BUSINESS_RULES_VALIDATION."""
        from hub.apps.compliance.models import ComplianceRun

        self.client.force_authenticate(user=self.user_a)
        count_before = ComplianceRun.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {"scan_mode": "internal"}
        response = self.client.post(
            "/api/v1/compliance/runs/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            ComplianceRun.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before,
        )
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            response.json().get("code", ""),
            msg="Expected business rules validation when no resource provided",
        )


class TestMeshRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.7.4 — Mesh: REST create/update/delete invokes DataMeshBusinessRules.

    Tests use real DB and real DataMeshBusinessRules; no mocks.
    """

    def setUp(self):
        from hub.apps.users.models import Role, UserRole

        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant()
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant_a,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant admin"},
        )
        UserRole.objects.get_or_create(user=self.user_a, role=role)

    def test_mesh_domain_create_valid_succeeds(self):
        """Valid domain create succeeds; DataMeshBusinessRules pass and domain is created."""
        from hub.apps.mesh.models import DataMeshDomain

        self.client.force_authenticate(user=self.user_a)
        count_before = DataMeshDomain.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "name": "phase18-mesh-domain",
            "description": "Phase 18 mesh domain",
        }
        response = self.client.post(
            "/api/v1/mesh/domains/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            DataMeshDomain.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before + 1,
        )
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data.get("name"), "phase18-mesh-domain")

    def test_mesh_domain_update_empty_name_returns_400(self):
        """Update domain with empty name is rejected; API returns 400."""
        from hub.apps.mesh.models import DataMeshDomain, DomainStatus

        self.client.force_authenticate(user=self.user_a)
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant_a,
            name="to-update-empty",
            description="Desc",
            status=DomainStatus.ACTIVE,
        )
        response = self.client.patch(
            f"/api/v1/mesh/domains/{domain.id}/",
            data={"name": "   ", "description": "Desc"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        domain.refresh_from_db()
        self.assertEqual(domain.name, "to-update-empty")
        data = response.json()
        self.assertIn("error", data)
        self.assertIn(data.get("code", ""), ("VALIDATION_ERROR", "BUSINESS_RULES_VALIDATION"))


class TestDQRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.7.3 — DQ: REST create invokes DQBusinessRules.

    Tests use real DB and real DQBusinessRules; no mocks.
    """

    def setUp(self):
        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant()
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])
        self.asset_a = AssetFactory.create_asset(tenant=self.tenant_a)

    def test_dq_run_create_valid_succeeds(self):
        """Valid DQ run create (same-tenant asset) succeeds; business rules pass."""
        from hub.apps.dq.models import DQRun

        self.client.force_authenticate(user=self.user_a)
        count_before = DQRun.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {"asset_id": str(self.asset_a.id)}
        response = self.client.post(
            "/api/v1/dq/runs/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            DQRun.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before + 1,
        )
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data.get("status"), "PENDING")

    def test_dq_run_create_no_resource_returns_400(self):
        """Create with no asset/dataset/file is rejected; API returns 400 BUSINESS_RULES_VALIDATION."""
        from hub.apps.dq.models import DQRun

        self.client.force_authenticate(user=self.user_a)
        count_before = DQRun.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {}
        response = self.client.post(
            "/api/v1/dq/runs/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            DQRun.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before,
        )
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            response.json().get("code", ""),
            msg="Expected business rules validation when no resource provided",
        )


class TestVirtualizationRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.7.5 — Virtualization: REST create/update invokes VirtualizationBusinessRules.

    Tests use real DB and real VirtualizationBusinessRules; no mocks.
    """

    def setUp(self):
        from hub.apps.users.models import Role, UserRole

        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant()
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant_a,
            name="DATA_PROVIDER",
            defaults={"description": "Data provider"},
        )
        UserRole.objects.get_or_create(user=self.user_a, role=role)

    def test_virtualization_dataset_create_valid_succeeds(self):
        """Valid virtual dataset create succeeds; VirtualizationBusinessRules pass."""
        from hub.apps.virtualization.models import VirtualDataset

        self.client.force_authenticate(user=self.user_a)
        count_before = VirtualDataset.objects.filter(tenant_id=self.tenant_a.id).count()
        # Use SPARQL so sources are optional (SQL would require sources)
        payload = {
            "name": "phase18-virtual-dataset",
            "query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 1",
            "query_type": "SPARQL",
            "description": "Phase 18 test",
        }
        response = self.client.post(
            "/api/v1/virtualization/datasets/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            VirtualDataset.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before + 1,
        )
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data.get("name"), "phase18-virtual-dataset")

    def test_virtualization_dataset_update_empty_name_returns_400(self):
        """Update virtual dataset with empty name is rejected; API returns 400."""
        from hub.apps.virtualization.models import QueryType, VirtualDataset, VirtualDatasetStatus

        self.client.force_authenticate(user=self.user_a)
        vd = VirtualDataset.objects.create(
            tenant=self.tenant_a,
            name="to-update-empty",
            query="SELECT 1",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
            version="1.0.0",
        )
        response = self.client.patch(
            f"/api/v1/virtualization/datasets/{vd.id}/",
            data={"name": "   ", "description": "Desc"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        vd.refresh_from_db()
        self.assertEqual(vd.name, "to-update-empty")
        data = response.json()
        self.assertIn("error", data)
        self.assertIn(data.get("code", ""), ("VALIDATION_ERROR", "BUSINESS_RULES_VALIDATION"))


class TestScheduledIngestionRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.7.6 — Scheduled ingestion: REST create invokes ScheduledIngestionBusinessRules.

    Tests use real DB and real ScheduledIngestionBusinessRules; no mocks.
    """

    def setUp(self):
        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant()
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])

    def test_scheduled_ingestion_create_valid_succeeds(self):
        """Valid scheduled ingestion create succeeds; business rules pass."""
        self.client.force_authenticate(user=self.user_a)
        count_before = ScheduledIngestion.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "name": "phase18-scheduled-ingestion",
            "source_type": "S3",
            "source_config": {"bucket": "test-bucket", "region": "us-east-1"},
            "schedule_type": "DAILY",
            "schedule_config": {"time": "00:00"},
            "file_pattern": r".*\.csv",
        }
        response = self.client.post(
            "/api/v1/scheduled-ingestions/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            ScheduledIngestion.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before + 1,
        )
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data.get("name"), "phase18-scheduled-ingestion")

    def test_scheduled_ingestion_create_empty_name_returns_400(self):
        """Create with empty name is rejected; API returns 400 BUSINESS_RULES_VALIDATION."""
        self.client.force_authenticate(user=self.user_a)
        count_before = ScheduledIngestion.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "name": "   ",
            "source_type": "S3",
            "source_config": {"bucket": "b", "region": "us-east-1"},
            "schedule_type": "DAILY",
            "schedule_config": {"time": "00:00"},
            "file_pattern": r".*\.csv",
        }
        response = self.client.post(
            "/api/v1/scheduled-ingestions/",
            data=payload,
            format="json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY),
            msg="Expected 400 or 422 for empty name",
        )
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            self.assertIn(
                "BUSINESS_RULES_VALIDATION",
                response.json().get("code", ""),
                msg="Expected business rules validation when name empty",
            )
        self.assertEqual(
            ScheduledIngestion.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before,
        )


class TestIntegrationsRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.7.7 — Integrations: REST connection create invokes MarketplaceIntegrationBusinessRules.

    Tests use real DB and real MarketplaceIntegrationBusinessRules; no mocks.
    """

    def setUp(self):
        from hub.apps.users.models import Role, UserRole

        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant()
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant_a,
            name="DATA_PROVIDER",
            defaults={"description": "Data provider"},
        )
        UserRole.objects.get_or_create(user=self.user_a, role=role)

    def test_connection_create_valid_succeeds(self):
        """Valid connection create succeeds; MarketplaceIntegrationBusinessRules pass."""
        from hub.apps.integrations.base import MarketplaceType
        from hub.apps.integrations.models import MarketplaceConnection

        self.client.force_authenticate(user=self.user_a)
        count_before = MarketplaceConnection.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
            "name": "phase18-connection",
            "config": {"base_url": "https://example.com", "api_key": "test"},
        }
        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            MarketplaceConnection.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before + 1,
        )
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data.get("name"), "phase18-connection")

    def test_connection_create_empty_name_returns_400(self):
        """Create connection with empty name is rejected; API returns 400 BUSINESS_RULES_VALIDATION."""
        from hub.apps.integrations.base import MarketplaceType
        from hub.apps.integrations.models import MarketplaceConnection

        self.client.force_authenticate(user=self.user_a)
        count_before = MarketplaceConnection.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
            "name": "   ",
            "config": {"base_url": "https://example.com"},
        }
        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            MarketplaceConnection.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before,
        )
        data = response.json()
        self.assertIn("error", data)
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            data.get("code", ""),
            msg="Expected business rules validation when connection name empty",
        )


class TestSocialRestBusinessRulesAlignment(TestCase):
    """
    Phase 18.7.8 — Social: REST rating create invokes SocialBusinessRules.

    Tests use real DB and real SocialBusinessRules; no mocks.
    """

    def setUp(self):
        self.client = APIClient()
        self.tenant_a = TenantFactory.create_tenant()
        self.user_a = UserFactory.create_user(tenant=self.tenant_a, status=UserStatus.ACTIVE)
        if not getattr(self.user_a, "tenant", None):
            self.user_a.tenant = self.tenant_a
            self.user_a.save(update_fields=["tenant_id"])
        self.asset_a = AssetFactory.create_asset(tenant=self.tenant_a)

    def test_social_rating_create_valid_succeeds(self):
        """Valid rating create (ACTIVE asset, same tenant) succeeds; business rules pass."""
        from hub.apps.assets.models import AssetStatus
        from hub.apps.social.models import Rating

        self.asset_a.status = AssetStatus.ACTIVE
        self.asset_a.save(update_fields=["status"])
        self.client.force_authenticate(user=self.user_a)
        count_before = Rating.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "asset_id": str(self.asset_a.id),
            "rating": 4,
            "comment": "Good dataset",
        }
        response = self.client.post(
            "/api/v1/social/ratings/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Rating.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before + 1,
        )
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data.get("rating"), 4)

    def test_social_rating_create_asset_not_active_returns_400(self):
        """Rating for non-ACTIVE asset is rejected; API returns 400 BUSINESS_RULES_VALIDATION."""
        from hub.apps.assets.models import AssetStatus
        from hub.apps.social.models import Rating

        self.asset_a.status = AssetStatus.DRAFT
        self.asset_a.save(update_fields=["status"])
        self.client.force_authenticate(user=self.user_a)
        count_before = Rating.objects.filter(tenant_id=self.tenant_a.id).count()
        payload = {
            "asset_id": str(self.asset_a.id),
            "rating": 4,
        }
        response = self.client.post(
            "/api/v1/social/ratings/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Rating.objects.filter(tenant_id=self.tenant_a.id).count(),
            count_before,
        )
        data = response.json()
        self.assertIn("error", data)
        self.assertIn(
            "BUSINESS_RULES_VALIDATION",
            data.get("code", ""),
            msg="Expected business rules validation when asset not ACTIVE",
        )
