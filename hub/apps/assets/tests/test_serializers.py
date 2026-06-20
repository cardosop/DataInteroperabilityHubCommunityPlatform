"""
Unit tests for asset serializers.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility
from hub.apps.assets.serializers import (
    AssetCreateSerializer,
    AssetSerializer,
    AssetUpdateSerializer,
    AttachContractSerializer,
    AttachDatasetSerializer,
    DataFirstAssetCreateSerializer,
    ExternalResourceSerializer,
)
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


class AssetSerializerTest(TestCase):
    """Test asset serializers"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test description",
            status=AssetStatus.DRAFT,
            # visibility is a derived @property (Phase 250.3.B);
            # DRAFT status → INTERNAL automatically.  Explicit
            # visibility= is the deprecated write path and emits
            # DeprecationWarning — omit it.
            created_by=self.user,
        )

    def test_asset_serializer_serializes_id(self):
        """Test AssetSerializer serializes id correctly."""
        serializer = AssetSerializer(self.asset)
        data = serializer.data

        self.assertEqual(data["id"], str(self.asset.id))

    def test_asset_serializer_serializes_key(self):
        """Test AssetSerializer serializes key correctly."""
        serializer = AssetSerializer(self.asset)
        data = serializer.data

        self.assertEqual(data["key"], "test-asset")

    def test_asset_serializer_serializes_name(self):
        """Test AssetSerializer serializes name correctly."""
        serializer = AssetSerializer(self.asset)
        data = serializer.data

        self.assertEqual(data["name"], "Test Asset")

    def test_asset_serializer_serializes_status(self):
        """Test AssetSerializer serializes status correctly"""
        serializer = AssetSerializer(self.asset)
        data = serializer.data

        self.assertEqual(data["status"], AssetStatus.DRAFT)

    def test_asset_create_serializer_is_valid(self):
        """Test AssetCreateSerializer validation returns True for valid data"""
        serializer = AssetCreateSerializer(
            data={
                "key": "new-asset",
                "name": "New Asset",
                "description": "New description",
                "visibility": "INTERNAL",
            }
        )

        self.assertTrue(serializer.is_valid())

    def test_asset_create_serializer_validates_key_and_name(self):
        """Test AssetCreateSerializer validates key and name correctly"""
        serializer = AssetCreateSerializer(
            data={
                "key": "new-asset",
                "name": "New Asset",
                "description": "New description",
                "visibility": "INTERNAL",
            }
        )

        serializer.is_valid()
        self.assertEqual(serializer.validated_data["key"], "new-asset")
        self.assertEqual(serializer.validated_data["name"], "New Asset")

    def test_asset_update_serializer_is_valid(self):
        """Test AssetUpdateSerializer validation returns True for valid data"""
        serializer = AssetUpdateSerializer(
            instance=self.asset,
            data={"name": "Updated Asset", "description": "Updated description"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid())

    def test_asset_update_serializer_updates_name(self):
        """Test AssetUpdateSerializer updates name correctly"""
        serializer = AssetUpdateSerializer(
            instance=self.asset,
            data={"name": "Updated Asset", "description": "Updated description"},
            partial=True,
        )

        serializer.is_valid()
        updated = serializer.save()
        self.assertEqual(updated.name, "Updated Asset")

    # ========== FAILURE SCENARIOS ==========

    def test_asset_create_serializer_invalid_data(self):
        """Test AssetCreateSerializer with invalid data (failure scenario)"""
        serializer = AssetCreateSerializer(data={"key": "", "name": "Test Asset"})  # Empty key

        self.assertFalse(serializer.is_valid())
        self.assertIn("key", serializer.errors)

    def test_asset_create_serializer_missing_required_fields(self):
        """Test AssetCreateSerializer with missing required fields (failure scenario)"""
        serializer = AssetCreateSerializer(
            data={
                "name": "Test Asset"
                # Missing key
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("key", serializer.errors)

    def test_asset_update_serializer_invalid_status(self):
        """AssetUpdateSerializer rejects invalid status values."""
        serializer = AssetUpdateSerializer(
            instance=self.asset,
            data={"status": "INVALID_STATUS"},
            partial=True,
        )

        self.assertFalse(
            serializer.is_valid(),
            "Serializer should reject invalid status value",
        )
        self.assertIn("status", serializer.errors)

    # ========== EDGE CASES ==========

    def test_asset_serializer_empty_description(self):
        """Test AssetSerializer with empty description (edge case)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="empty-desc-asset",
            name="Empty Desc Asset",
            description="",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        serializer = AssetSerializer(asset)
        data = serializer.data

        self.assertEqual(data["description"], "")

    def test_asset_serializer_none_values(self):
        """Test AssetSerializer with None values (edge case)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="none-values-asset",
            name="None Values Asset",
            description=None,
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        serializer = AssetSerializer(asset)
        data = serializer.data

        # Should handle None values gracefully
        self.assertIsNotNone(data["id"])
        self.assertEqual(data["key"], "none-values-asset")

    def test_asset_create_serializer_rejects_invalid_key_format(self):
        """AssetCreateSerializer enforces the lowercase-hyphen key format.

        Locks in the contract for the JOURNEY-DPO-001 e2e test that posts
        `Invalid_Key_With_Underscore` and expects a 4xx with a message
        mentioning the key field. Without this validator the API was
        accepting any 255-char string and returning 201, which silently
        violated the documented key rule and broke downstream URL routing.
        """
        invalid_keys = [
            "Invalid_Key_With_Underscore",  # underscore + uppercase
            "UPPER",  # uppercase
            "with space",  # space
            "trailing-",  # trailing hyphen
            "-leading",  # leading hyphen
            "double--hyphen",  # consecutive hyphens
            "punc!",  # punctuation
            "",  # empty (covered by required, but redundant guard)
        ]
        for key in invalid_keys:
            serializer = AssetCreateSerializer(data={"key": key, "name": "X"})
            self.assertFalse(
                serializer.is_valid(),
                f"Serializer should reject invalid key {key!r}",
            )
            self.assertIn("key", serializer.errors)

    def test_asset_create_serializer_accepts_valid_key_format(self):
        """AssetCreateSerializer accepts canonical slug-format keys."""
        valid_keys = [
            "test-asset",
            "a",
            "1",
            "asset-1",
            "my-asset-with-many-segments",
            "1-2-3",
            "abc123",
        ]
        for key in valid_keys:
            serializer = AssetCreateSerializer(data={"key": key, "name": "X"})
            self.assertTrue(
                serializer.is_valid(),
                f"Serializer should accept valid key {key!r}: {serializer.errors}",
            )

    def test_asset_create_serializer_very_long_key(self):
        """AssetCreateSerializer rejects key exceeding max_length."""
        long_key = "a" * 300  # max_length=255
        serializer = AssetCreateSerializer(
            data={"key": long_key, "name": "Test Asset"},
        )

        self.assertFalse(
            serializer.is_valid(),
            "Serializer should reject key longer than max_length",
        )
        self.assertIn("key", serializer.errors)

    def test_asset_update_serializer_partial_update(self):
        """Test AssetUpdateSerializer with partial update (edge case)"""
        serializer = AssetUpdateSerializer(
            instance=self.asset, data={"name": "Partially Updated"}, partial=True
        )

        self.assertTrue(serializer.is_valid())
        updated = serializer.save()
        self.assertEqual(updated.name, "Partially Updated")
        # Other fields should remain unchanged
        self.assertEqual(updated.key, self.asset.key)

    def test_asset_update_serializer_no_changes(self):
        """Test AssetUpdateSerializer with no changes (edge case)"""
        serializer = AssetUpdateSerializer(instance=self.asset, data={}, partial=True)

        self.assertTrue(serializer.is_valid())
        updated = serializer.save()
        # Should not change anything
        self.assertEqual(updated.name, self.asset.name)

    # ========== ERROR HANDLING ==========

    def test_asset_serializer_serializes_valid_asset(self):
        """AssetSerializer serializes a valid asset without error."""
        serializer = AssetSerializer(self.asset)
        data = serializer.data
        self.assertEqual(data["key"], self.asset.key)
        self.assertEqual(data["name"], self.asset.name)
        self.assertIn("id", data)

    def test_asset_create_serializer_ignores_unknown_fields(self):
        """AssetCreateSerializer ignores unknown fields (DRF default)."""
        serializer = AssetCreateSerializer(
            data={
                "key": "test-asset",
                "name": "Test Asset",
                "status": "INVALID_STATUS",
            }
        )
        # DRF ignores unknown fields — serializer is valid
        self.assertTrue(
            serializer.is_valid(),
            f"Extra fields should be ignored: {serializer.errors}",
        )

    def test_asset_update_serializer_missing_instance_raises(self):
        """Saving AssetUpdateSerializer without an instance raises ValueError."""
        serializer = AssetUpdateSerializer(data={"name": "Updated"})
        self.assertTrue(serializer.is_valid())
        with self.assertRaises(ValueError) as ctx:
            serializer.save()
        self.assertIn("Instance is required", str(ctx.exception))

    # ----- Phase 226 G7a — canonical_iri SerializerMethodField -----------

    def test_asset_serializer_emits_canonical_iri_field(self):
        """canonical_iri must be present on every serialized asset."""
        from django.test import override_settings

        with override_settings(SEMANTIC_BASE_IRI="https://meshant.io"):
            serializer = AssetSerializer(self.asset)
            data = dict(serializer.data)

            self.assertIn("canonical_iri", data)
            self.assertEqual(
                data.get("canonical_iri"),
                f"https://meshant.io/id/asset/{self.asset.id}",
            )

    def test_asset_canonical_iri_strips_base_trailing_slash(self):
        """Trailing slash on SEMANTIC_BASE_IRI must not double up the IRI."""
        from django.test import override_settings

        with override_settings(SEMANTIC_BASE_IRI="https://meshant.io/"):
            serializer = AssetSerializer(self.asset)
            iri = dict(serializer.data).get("canonical_iri")
            self.assertIsInstance(iri, str)
            self.assertNotIn("//id/", iri)
            self.assertEqual(iri, f"https://meshant.io/id/asset/{self.asset.id}")

    def test_asset_canonical_iri_is_read_only(self):
        """Clients cannot write canonical_iri on update."""
        # canonical_iri is in read_only_fields; passing it on input is silently
        # ignored, not stored. AssetUpdateSerializer does not list it at all
        # but the AssetSerializer itself must reject it as a writable field.
        serializer = AssetSerializer(
            self.asset,
            data={"canonical_iri": "https://attacker.example/id/asset/00000000"},
            partial=True,
        )
        # Validation passes (read-only fields are silently dropped, not errored)
        # and the original value remains unchanged on the instance.
        self.assertTrue(
            serializer.is_valid(),
            f"Serializer must be valid when only read-only fields are sent; "
            f"errors: {serializer.errors}",
        )
        instance = serializer.save()
        self.assertIsNotNone(instance, "Serializer save must return the instance when valid")
        # The persisted IRI is computed from the instance's id,
        # not the inbound payload — attacker-controlled IRIs cannot
        # land in the database.
        refreshed = dict(AssetSerializer(instance).data)
        self.assertNotIn("attacker.example", str(refreshed.get("canonical_iri", "")))

    # ------------------------------------------------------------------
    # SerializerMethodField coverage
    # ------------------------------------------------------------------

    def test_get_visibility_draft_returns_internal(self):
        """get_visibility returns INTERNAL when asset status is DRAFT."""
        self.asset.status = AssetStatus.DRAFT
        self.asset.save()
        data = AssetSerializer(self.asset).data
        self.assertEqual(data["visibility"], AssetVisibility.INTERNAL)

    def test_get_visibility_public_when_status_public(self):
        """get_visibility returns PUBLIC when asset status is PUBLIC."""
        self.asset.status = AssetStatus.PUBLIC
        self.asset.save()
        data = AssetSerializer(self.asset).data
        self.assertEqual(data["visibility"], AssetVisibility.PUBLIC)

    def test_get_contract_id_returns_none_without_contracts(self):
        """get_contract_id returns None for asset with no contracts."""
        data = AssetSerializer(self.asset).data
        self.assertIsNone(data["contract_id"])

    def test_get_dataset_id_returns_none_without_datasets(self):
        """get_dataset_id returns None for asset with no datasets."""
        data = AssetSerializer(self.asset).data
        self.assertIsNone(data["dataset_id"])

    def test_get_dataset_id_returns_latest_dataset(self):
        """get_dataset_id returns the latest dataset ID."""
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus

        f = File.objects.create(
            tenant=self.tenant, name="ds.csv", content_type="text/csv",
            size=1000, status=FileStatus.ACTIVE, storage_path="t/ds.csv",
            content_sha256="abc", created_by=self.user,
        )
        ds = Dataset.objects.create(
            tenant=self.tenant, asset=self.asset, file=f,
            schema_json={"fields": []}, format="CSV", version=1,
            created_by=self.user,
        )

        data = AssetSerializer(self.asset).data
        self.assertEqual(data["dataset_id"], str(ds.id))

    def test_get_contract_id_returns_active_contract(self):
        """get_contract_id returns the active contract ID."""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw='{"id":"test"}',
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_version="2.0.0",
            hub_contract_json={"id": "test"},
            created_by=self.user,
        )

        data = AssetSerializer(self.asset).data
        self.assertEqual(data["contract_id"], str(contract.id))

    def test_get_contract_id_returns_none_without_active(self):
        """get_contract_id returns None for asset with non-active contracts."""
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            NormalizationStatus,
            OriginalFormat,
            OriginalSpecType,
            ValidationStatus,
        )

        Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"id":"test"}',
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            status=ContractStatus.DRAFT,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_version="2.0.0",
            hub_contract_json={"id": "test"},
            created_by=self.user,
        )

        data = AssetSerializer(self.asset).data
        self.assertIsNone(data["contract_id"])

    def test_get_latest_compliance_run_returns_none_without_runs(self):
        """get_latest_compliance_run returns None for asset without runs."""
        data = AssetSerializer(self.asset).data
        self.assertIsNone(data["latest_compliance_run"])

    def test_get_latest_compliance_run_returns_succeeded(self):
        """get_latest_compliance_run returns the latest SUCCEEDED run."""
        from hub.apps.compliance.models import ComplianceRun

        ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset,
            status="SUCCEEDED", risk_level="LOW", allowed_to_store=True,
        )

        data = AssetSerializer(self.asset).data
        self.assertIsNotNone(data["latest_compliance_run"])
        self.assertEqual(data["latest_compliance_run"]["risk_level"], "LOW")

    def test_get_latest_compliance_run_excludes_failed(self):
        """get_latest_compliance_run excludes FAILED runs."""
        from hub.apps.compliance.models import ComplianceRun

        ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset,
            status="FAILED", risk_level="HIGH", allowed_to_store=True,
        )
        ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset,
            status="SUCCEEDED", risk_level="LOW", allowed_to_store=True,
        )

        data = AssetSerializer(self.asset).data
        self.assertIsNotNone(data["latest_compliance_run"])
        self.assertEqual(data["latest_compliance_run"]["risk_level"], "LOW")


# ---------------------------------------------------------------------------
# Untested serializer classes
# ---------------------------------------------------------------------------


class DataFirstAssetCreateSerializerTest(TestCase):
    """Test DataFirstAssetCreateSerializer."""

    def test_valid_data_first_asset_create(self):
        """Valid file_id + key + name passes validation."""
        serializer = DataFirstAssetCreateSerializer(data={
            "file_id": str(uuid.uuid4()),
            "key": "valid-key",
            "name": "Test Asset",
        })
        self.assertTrue(serializer.is_valid(), f"Errors: {serializer.errors}")

    def test_missing_file_id_is_invalid(self):
        """Missing file_id is rejected."""
        serializer = DataFirstAssetCreateSerializer(data={
            "key": "valid-key",
            "name": "Test Asset",
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("file_id", serializer.errors)

    def test_invalid_key_format_is_rejected(self):
        """Invalid key format is rejected."""
        serializer = DataFirstAssetCreateSerializer(data={
            "file_id": str(uuid.uuid4()),
            "key": "INVALID_KEY_WITH_UPPERCASE",
            "name": "Test Asset",
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("key", serializer.errors)


class AttachDatasetSerializerTest(TestCase):
    """Test AttachDatasetSerializer."""

    def test_valid_uuid_passes(self):
        """Valid dataset_id UUID passes validation."""
        serializer = AttachDatasetSerializer(data={
            "dataset_id": str(uuid.uuid4()),
        })
        self.assertTrue(serializer.is_valid(), f"Errors: {serializer.errors}")

    def test_missing_dataset_id_is_invalid(self):
        """Missing dataset_id is rejected."""
        serializer = AttachDatasetSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("dataset_id", serializer.errors)


class AttachContractSerializerTest(TestCase):
    """Test AttachContractSerializer."""

    def test_valid_uuid_passes(self):
        """Valid contract_id UUID passes validation."""
        serializer = AttachContractSerializer(data={
            "contract_id": str(uuid.uuid4()),
        })
        self.assertTrue(serializer.is_valid(), f"Errors: {serializer.errors}")

    def test_missing_contract_id_is_invalid(self):
        """Missing contract_id is rejected."""
        serializer = AttachContractSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("contract_id", serializer.errors)


class ExternalResourceSerializerTest(TestCase):
    """Test ExternalResourceSerializer read-only structure."""

    def test_readonly_fields_present(self):
        """Serializer exposes all expected read-only fields."""
        serializer = ExternalResourceSerializer()
        fields = set(serializer.fields.keys())
        expected = {
            "id", "resource_id", "name", "url", "format", "size_bytes",
            "marketplace_type", "metadata", "created_at", "updated_at",
            "is_downloaded", "file_id", "dataset_id",
        }
        self.assertEqual(fields, expected)
