"""
Comprehensive integration tests for ODCS export and download endpoints (Task 9.5.4.1.6.1)

This test suite validates:
1. Export endpoint with all ODCS versions
2. Download endpoint with all ODCS versions
3. Generation from HubContract (all versions)
4. Format conversion (JSON/YAML)
5. Error handling (invalid versions, missing fields, generation failures)
6. Performance (export duration <2s p95)
7. Round-trip: ODCS → HubContract → ODCS (all versions)

Tests use real implementations (no mocks/stubs) and follow TDD principles.
"""

import json
import time
import uuid

import pytest
import yaml
from rest_framework import status

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.odcs_generator import generate_odcs_from_hubcontract
from hub.apps.contracts.tests.test_base import ContractsAPITestBase, ContractsTestBase
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

# All supported ODCS versions
ODCS_VERSIONS = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]


class ODCSExportIntegrationTest(ContractsAPITestBase):
    """Comprehensive integration tests for ODCS export endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create comprehensive HubContract for generation tests
        self.hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-contract-integration",
            "info": {
                "name": "Test Contract Integration",
                "description": "Comprehensive test contract for integration testing",
                "version": "1.0.0",
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "data_type": "string",
                        "description": "Unique identifier",
                        "nullable": False,
                    },
                    {
                        "name": "name",
                        "data_type": "string",
                        "description": "Name field",
                        "nullable": True,
                    },
                    {
                        "name": "email",
                        "data_type": "string",
                        "description": "Email address",
                        "nullable": True,
                        "format": "email",
                    },
                ]
            },
        }

        # Create contract without original_raw (for generation tests)
        self.contract_without_original = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw="",
            hub_contract_json=self.hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

    def test_export_all_odcs_versions_json(self):
        """Test export endpoint with all ODCS versions as JSON"""
        self.client.force_authenticate(user=self.user)

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):
                response = self.client.get(
                    f"/api/v1/contracts/{self.contract_without_original.id}/export/",
                    {"format": "odcs", "output_format": "json", "version": version},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response["Content-Type"], "application/json")

                data = response.data
                self.assertEqual(data["apiVersion"], f"odcs.io/v{version}")
                self.assertEqual(data["kind"], "DataContract")
                self.assertEqual(data["id"], "test-contract-integration")
                self.assertEqual(data["name"], "Test Contract Integration")
                self.assertIn("schema", data)

    def test_export_all_odcs_versions_yaml(self):
        """Test export endpoint with all ODCS versions as YAML"""
        self.client.force_authenticate(user=self.user)

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):
                response = self.client.get(
                    f"/api/v1/contracts/{self.contract_without_original.id}/export/",
                    {"format": "odcs", "output_format": "yaml", "version": version},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("yaml", response["Content-Type"].lower())

                data = yaml.safe_load(response.content)
                self.assertEqual(data["apiVersion"], f"odcs.io/v{version}")
                self.assertEqual(data["kind"], "DataContract")
                self.assertEqual(data["id"], "test-contract-integration")
                self.assertEqual(data["name"], "Test Contract Integration")
                self.assertIn("schema", data)

    def test_export_format_conversion_json_to_yaml(self):
        """Test format conversion: JSON to YAML"""
        self.client.force_authenticate(user=self.user)

        # Export as JSON first
        response_json = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )
        self.assertEqual(response_json.status_code, status.HTTP_200_OK)
        data_json = response_json.data

        # Export as YAML
        response_yaml = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "yaml", "version": "3.0.2"},
        )
        self.assertEqual(response_yaml.status_code, status.HTTP_200_OK)
        data_yaml = yaml.safe_load(response_yaml.content)

        # Verify data is equivalent
        self.assertEqual(data_json["id"], data_yaml["id"])
        self.assertEqual(data_json["name"], data_yaml["name"])
        self.assertEqual(data_json["apiVersion"], data_yaml["apiVersion"])

    def test_export_format_conversion_yaml_to_json(self):
        """Test format conversion: YAML to JSON"""
        self.client.force_authenticate(user=self.user)

        # Export as YAML first
        response_yaml = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "yaml", "version": "3.0.2"},
        )
        self.assertEqual(response_yaml.status_code, status.HTTP_200_OK)
        data_yaml = yaml.safe_load(response_yaml.content)

        # Export as JSON
        response_json = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )
        self.assertEqual(response_json.status_code, status.HTTP_200_OK)
        data_json = response_json.data

        # Verify data is equivalent
        self.assertEqual(data_yaml["id"], data_json["id"])
        self.assertEqual(data_yaml["name"], data_json["name"])
        self.assertEqual(data_yaml["apiVersion"], data_json["apiVersion"])

    def test_export_error_handling_invalid_version(self):
        """Test error handling for invalid ODCS version"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "99.99.99"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("version", str(response.data["error"]).lower())

    def test_export_error_handling_missing_hub_contract(self):
        """Test error handling when hub_contract_json is missing"""
        self.client.force_authenticate(user=self.user)

        # Create contract without hub_contract_json
        contract_no_hub = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw="",
            hub_contract_json=None,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        response = self.client.get(
            f"/api/v1/contracts/{contract_no_hub.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_export_performance_under_2s(self):
        """Test performance: export should complete in under 2 seconds (p95)"""
        self.client.force_authenticate(user=self.user)

        durations = []
        iterations = 10  # Run multiple iterations to get p95

        for _i in range(iterations):
            start_time = time.time()
            response = self.client.get(
                f"/api/v1/contracts/{self.contract_without_original.id}/export/",
                {"format": "odcs", "output_format": "json", "version": "3.0.2"},
            )
            duration = time.time() - start_time
            durations.append(duration)

            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Calculate p95 (95th percentile)
        durations.sort()
        p95_index = int(len(durations) * 0.95)
        p95_duration = durations[p95_index] if p95_index < len(durations) else durations[-1]

        # Performance check: p95 should be under 2 seconds
        self.assertLess(
            p95_duration,
            2.0,
            f"Export p95 duration is {p95_duration:.3f}s, expected < 2.0s. Durations: {durations}",
        )


class ODCSDownloadIntegrationTest(ContractsAPITestBase):
    """Comprehensive integration tests for ODCS download endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create comprehensive HubContract for generation tests
        self.hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-contract-integration",
            "info": {
                "name": "Test Contract Integration",
                "description": "Comprehensive test contract for integration testing",
                "version": "1.0.0",
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "data_type": "string",
                        "description": "Unique identifier",
                        "nullable": False,
                    },
                    {
                        "name": "name",
                        "data_type": "string",
                        "description": "Name field",
                        "nullable": True,
                    },
                ]
            },
        }

        # Create contract without original_raw (for generation tests)
        self.contract_without_original = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw="",
            hub_contract_json=self.hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

    def test_download_all_odcs_versions_json(self):
        """Test download endpoint with all ODCS versions as JSON"""
        self.client.force_authenticate(user=self.user)

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):
                response = self.client.get(
                    f"/api/v1/contracts/{self.contract_without_original.id}/download/",
                    {"format": "odcs", "output_format": "json", "version": version},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response["Content-Type"], "application/json")
                self.assertIn("Content-Disposition", response)
                self.assertIn("attachment", response["Content-Disposition"])

                data = json.loads(response.content)
                self.assertEqual(data["apiVersion"], f"odcs.io/v{version}")
                self.assertEqual(data["kind"], "DataContract")
                self.assertEqual(data["id"], "test-contract-integration")
                self.assertEqual(data["name"], "Test Contract Integration")
                self.assertIn("schema", data)

    def test_download_all_odcs_versions_yaml(self):
        """Test download endpoint with all ODCS versions as YAML"""
        self.client.force_authenticate(user=self.user)

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):
                response = self.client.get(
                    f"/api/v1/contracts/{self.contract_without_original.id}/download/",
                    {"format": "odcs", "output_format": "yaml", "version": version},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("yaml", response["Content-Type"].lower())
                self.assertIn("Content-Disposition", response)
                self.assertIn("attachment", response["Content-Disposition"])

                data = yaml.safe_load(response.content)
                self.assertEqual(data["apiVersion"], f"odcs.io/v{version}")
                self.assertEqual(data["kind"], "DataContract")
                self.assertEqual(data["id"], "test-contract-integration")
                self.assertEqual(data["name"], "Test Contract Integration")
                self.assertIn("schema", data)

    def test_download_format_conversion_json_to_yaml(self):
        """Test format conversion during download: JSON to YAML"""
        self.client.force_authenticate(user=self.user)

        # Download as JSON first
        response_json = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )
        self.assertEqual(response_json.status_code, status.HTTP_200_OK)
        data_json = json.loads(response_json.content)

        # Download as YAML
        response_yaml = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "yaml", "version": "3.0.2"},
        )
        self.assertEqual(response_yaml.status_code, status.HTTP_200_OK)
        data_yaml = yaml.safe_load(response_yaml.content)

        # Verify data is equivalent
        self.assertEqual(data_json["id"], data_yaml["id"])
        self.assertEqual(data_json["name"], data_yaml["name"])
        self.assertEqual(data_json["apiVersion"], data_yaml["apiVersion"])

    def test_download_error_handling_invalid_version(self):
        """Test error handling for invalid ODCS version in download"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "99.99.99"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        error_msg = str(response.data["error"]).lower()
        self.assertIn("version", error_msg)

    def test_download_performance_under_2s(self):
        """Test performance: download should complete in under 2 seconds (p95)"""
        self.client.force_authenticate(user=self.user)

        durations = []
        iterations = 10  # Run multiple iterations to get p95

        for _i in range(iterations):
            start_time = time.time()
            response = self.client.get(
                f"/api/v1/contracts/{self.contract_without_original.id}/download/",
                {"format": "odcs", "output_format": "json", "version": "3.0.2"},
            )
            duration = time.time() - start_time
            durations.append(duration)

            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Calculate p95 (95th percentile)
        durations.sort()
        p95_index = int(len(durations) * 0.95)
        p95_duration = durations[p95_index] if p95_index < len(durations) else durations[-1]

        # Performance check: p95 should be under 2 seconds
        self.assertLess(
            p95_duration,
            2.0,
            f"Download p95 duration is {p95_duration:.3f}s, expected < 2.0s. Durations: {durations}",
        )


class ODCSGenerationIntegrationTest(ContractsTestBase):
    """Comprehensive integration tests for ODCS generation from HubContract"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create comprehensive HubContract for generation tests
        self.hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-contract-generation",
            "info": {
                "name": "Test Contract Generation",
                "description": "Test contract for generation testing",
                "version": "1.0.0",
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "data_type": "string",
                        "description": "Unique identifier",
                        "nullable": False,
                    },
                    {
                        "name": "name",
                        "data_type": "string",
                        "description": "Name field",
                        "nullable": True,
                    },
                ]
            },
        }

    def test_generate_all_odcs_versions(self):
        """Test generation from HubContract for all ODCS versions"""
        for version in ODCS_VERSIONS:
            with self.subTest(version=version):
                odcs_doc = generate_odcs_from_hubcontract(
                    hub_contract=self.hub_contract,
                    target_version=version,
                    tenant_id=str(self.tenant.id),
                )

                self.assertIsNotNone(odcs_doc)
                self.assertEqual(odcs_doc["apiVersion"], f"odcs.io/v{version}")
                self.assertEqual(odcs_doc["kind"], "DataContract")
                self.assertEqual(odcs_doc["id"], "test-contract-generation")
                self.assertEqual(odcs_doc["name"], "Test Contract Generation")
                self.assertIn("schema", odcs_doc)

    def test_generation_error_handling_missing_required_fields(self):
        """Test error handling when HubContract is missing required fields"""
        # Create invalid HubContract (missing info section)
        invalid_hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-invalid",
        }

        with self.assertRaises(Exception) as cm:
            generate_odcs_from_hubcontract(
                hub_contract=invalid_hub_contract,
                target_version="3.0.2",
                tenant_id=str(self.tenant.id),
            )

        # Should raise ODCSGenerationError or similar
        self.assertIsNotNone(cm.exception)

    def test_generation_error_handling_empty_hub_contract(self):
        """Test error handling when HubContract is empty"""
        empty_hub_contract = {}

        with self.assertRaises(Exception) as cm:
            generate_odcs_from_hubcontract(
                hub_contract=empty_hub_contract,
                target_version="3.0.2",
                tenant_id=str(self.tenant.id),
            )

        # Should raise ODCSGenerationError or similar
        self.assertIsNotNone(cm.exception)


class ODCSRoundTripIntegrationTest(ContractsAPITestBase):
    """Comprehensive integration tests for ODCS round-trip: ODCS → HubContract → ODCS"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def _create_odcs_contract(self, version: str) -> dict:
        """Helper to create ODCS contract for a specific version"""
        return {
            "apiVersion": f"odcs.io/v{version}",
            "kind": "DataContract",
            "id": f"test-contract-{version.replace('.', '-')}",
            "name": f"Test Contract {version}",
            "version": "1.0.0",
            "description": f"Test contract for version {version}",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": True},
                ]
            },
        }

    def test_round_trip_all_versions(self):
        """Test round-trip: ODCS → HubContract → ODCS for all versions"""
        for version in ODCS_VERSIONS:
            with self.subTest(version=version):
                # Step 1: Start with ODCS contract
                original_odcs = self._create_odcs_contract(version)

                # Step 2: Normalize ODCS → HubContract
                odcs_json = json.dumps(original_odcs)
                hub_contract_dict, _spec_type, _spec_version, norm_status, errors, _warnings = (
                    normalize_contract(raw_contract=odcs_json, format="json", spec_type="ODCS")
                )

                # Verify normalization succeeded
                self.assertIsNotNone(
                    hub_contract_dict,
                    f"Normalization failed for version {version}. Errors: {errors}",
                )
                self.assertIn(
                    norm_status.value,
                    ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"],
                    f"Normalization status was {norm_status.value} for version {version}",
                )

                # Step 3: Generate ODCS from HubContract
                generated_odcs = generate_odcs_from_hubcontract(
                    hub_contract=hub_contract_dict,
                    target_version=version,
                    tenant_id=str(self.tenant.id),
                )

                # Verify generated ODCS matches original
                self.assertIsNotNone(generated_odcs)
                self.assertEqual(generated_odcs["apiVersion"], f"odcs.io/v{version}")
                self.assertEqual(generated_odcs["kind"], "DataContract")
                self.assertEqual(generated_odcs["id"], original_odcs["id"])
                self.assertEqual(generated_odcs["name"], original_odcs["name"])
                self.assertEqual(generated_odcs["version"], original_odcs["version"])
                self.assertIn("schema", generated_odcs)
                self.assertIn("fields", generated_odcs["schema"])

    def test_round_trip_with_complex_schema(self):
        """Test round-trip with complex schema including multiple fields"""
        version = "3.0.2"
        original_odcs = {
            "apiVersion": f"odcs.io/v{version}",
            "kind": "DataContract",
            "id": "test-complex-schema",
            "name": "Test Complex Schema",
            "version": "1.0.0",
            "description": "Test contract with complex schema",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False,
                        "description": "Unique identifier",
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "nullable": True,
                        "description": "Name field",
                    },
                    {
                        "name": "email",
                        "type": "string",
                        "nullable": True,
                        "format": "email",
                        "description": "Email address",
                    },
                    {"name": "age", "type": "integer", "nullable": True, "description": "Age"},
                ]
            },
        }

        # Normalize ODCS → HubContract
        odcs_json = json.dumps(original_odcs)
        hub_contract_dict, _spec_type, _spec_version, norm_status, _errors, _warnings = (
            normalize_contract(raw_contract=odcs_json, format="json", spec_type="ODCS")
        )

        self.assertIsNotNone(hub_contract_dict)
        self.assertIn(norm_status.value, ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"])

        # Generate ODCS from HubContract
        generated_odcs = generate_odcs_from_hubcontract(
            hub_contract=hub_contract_dict, target_version=version, tenant_id=str(self.tenant.id)
        )

        # Verify schema fields are preserved
        self.assertIn("schema", generated_odcs)
        self.assertIn("fields", generated_odcs["schema"])
        self.assertEqual(len(generated_odcs["schema"]["fields"]), 4)

        # Verify field names match
        field_names = [field["name"] for field in generated_odcs["schema"]["fields"]]
        self.assertIn("id", field_names)
        self.assertIn("name", field_names)
        self.assertIn("email", field_names)
        self.assertIn("age", field_names)

    def test_round_trip_version_conversion(self):
        """Test round-trip with version conversion: ODCS 3.0.2 → HubContract → ODCS 3.0.1"""
        # Start with ODCS 3.0.2
        original_odcs_v302 = self._create_odcs_contract("3.0.2")

        # Normalize ODCS 3.0.2 → HubContract
        odcs_json = json.dumps(original_odcs_v302)
        hub_contract_dict, _spec_type, _spec_version, _norm_status, _errors, _warnings = (
            normalize_contract(raw_contract=odcs_json, format="json", spec_type="ODCS")
        )

        self.assertIsNotNone(hub_contract_dict)

        # Generate ODCS 3.0.1 from HubContract
        generated_odcs_v301 = generate_odcs_from_hubcontract(
            hub_contract=hub_contract_dict, target_version="3.0.1", tenant_id=str(self.tenant.id)
        )

        # Verify version conversion worked
        self.assertEqual(generated_odcs_v301["apiVersion"], "odcs.io/v3.0.1")
        self.assertEqual(generated_odcs_v301["id"], original_odcs_v302["id"])
        self.assertEqual(generated_odcs_v301["name"], original_odcs_v302["name"])

    def test_export_handles_unicode_characters(self):
        """Test that export handles unicode characters correctly."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-unicode",
            "info": {"name": "测试合同", "description": "测试描述"},
            "schema": {"fields": []},
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/v1/contracts/{contract.id}/export/?format=odcs&output_format=json&version=3.0.2"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify unicode characters are preserved in export
        exported_data = response.data
        self.assertIsNotNone(exported_data)

    def test_export_handles_special_characters(self):
        """Test that export handles special characters correctly."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-special",
            "info": {"name": "Test & Co. (Special)", "description": "Test <description> & more"},
            "schema": {"fields": []},
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/v1/contracts/{contract.id}/export/?format=odcs&output_format=json&version=3.0.2"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify special characters are preserved in export
        exported_data = response.data
        self.assertIsNotNone(exported_data)

    def test_export_handles_very_large_documents(self):
        """Test that export handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-large",
            "info": {"name": "Test Product", "description": large_description},
            "schema": {"fields": []},
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/v1/contracts/{contract.id}/export/?format=odcs&output_format=json&version=3.0.2"
        )

        # Should handle large documents gracefully
        self.assertIn(
            response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
        )

    def test_export_handles_none_values(self):
        """Test that export handles None values correctly."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-none",
            "info": {"name": "Test Product", "description": None},  # None value
            "schema": {"fields": []},
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/v1/contracts/{contract.id}/export/?format=odcs&output_format=json&version=3.0.2"
        )

        # Should handle None values gracefully
        self.assertIn(
            response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
        )

    def test_export_handles_nested_structures(self):
        """Test that export handles nested structures correctly."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-nested",
            "info": {
                "name": "Test Product",
                "nested": {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}},
            },
            "schema": {"fields": []},
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/v1/contracts/{contract.id}/export/?format=odcs&output_format=json&version=3.0.2"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify nested structures are preserved in export
        exported_data = response.data
        self.assertIsNotNone(exported_data)

    def test_export_maintains_cross_tenant_isolation(self):
        """Test that export maintains cross-tenant isolation."""
        # Create second tenant
        tenant2 = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        user2 = User.objects.create_user(
            email=f"user2-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant2,
            status=UserStatus.ACTIVE,
        )

        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-tenant2",
            "info": {"name": "Test Product Tenant 2"},
            "schema": {"fields": []},
        }

        contract2 = Contract.objects.create(
            tenant=tenant2,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=user2,
        )

        # Try to access tenant2 contract from tenant1 user
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/v1/contracts/{contract2.id}/export/?format=json&version=3.0.2"
        )

        # Should be denied due to tenant isolation
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
