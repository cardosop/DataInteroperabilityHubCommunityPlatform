"""
E2E tests for ODPS GraphQL mutations.

Tests complete workflows:
- Create ODPS contract
- Link ODPS to ODCS
- Unlink ODPS from ODCS
- Export ODPS contract

Uses REAL services (no mocks).
"""

import json

import graphql_relay
import pytest
from rest_framework import status

from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType

from .conftest import E2ETestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


def _decode_relay_id(relay_id: str) -> str:
    """Decode GraphQL Relay global ID to plain UUID."""
    if not relay_id:
        return relay_id
    try:
        _type_name, decoded = graphql_relay.from_global_id(str(relay_id))
        return decoded
    except (ValueError, TypeError):
        return relay_id


class GraphQLODPSMutationsE2ETest(E2ETestBase):
    """E2E tests for ODPS GraphQL mutations"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Sample ODPS document (dataSchema required by ODPS business rules)
        self.sample_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test product description",
                    }
                },
                "dataSchema": {
                    "fields": [
                        {"name": "id", "type": "string"},
                        {"name": "field1", "type": "string"},
                    ]
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs/v3",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "name": "Test Contract",
                        "schema": {
                            "fields": [{"name": "field1", "type": "string", "required": True}]
                        },
                    }
                },
            },
        }

        # Sample ODCS document (schema.primaryKey required by ODCS normalizer)
        self.sample_odcs = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "schema": {
                "fields": [{"name": "field1", "type": "string", "required": True}],
                "primaryKey": "field1",
            },
        }

    def _graphql_mutation(self, mutation, variables=None):
        """Helper to execute GraphQL mutation"""
        data = {"query": mutation}
        if variables:
            data["variables"] = variables

        response = self.client.post(
            "/graphql-graphene/",
            data=json.dumps(data),
            content_type="application/json",
        )
        return response

    def test_create_odps_workflow(self):
        """Test complete workflow: Create ODPS contract via GraphQL"""
        mutation = """
        mutation CreateODPS($input: CreateODPSInput!) {
            createODPS(input: $input) {
                contract {
                    id
                    originalSpecType
                    originalSpecVersion
                    odpsVersion
                }
                errors
            }
        }
        """

        variables = {
            "input": {
                "originalRaw": json.dumps(self.sample_odps),
                "originalFormat": "JSON",
                "assetId": str(self.asset.id) if hasattr(self, "asset") else None,
                "resolveExternalRefs": True,
            }
        }

        response = self._graphql_mutation(mutation, variables)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = json.loads(response.content)
        self.assertIn("data", data)
        result = data["data"].get("createODPS")
        self.assertIsNotNone(result, "createODPS mutation returned no result")
        errors = result.get("errors") if result else []
        self.assertEqual(len(errors), 0, f"createODPS errors: {errors}")
        self.assertIsNotNone(result["contract"])
        self.assertEqual(result["contract"]["originalSpecType"], "ODPS")

        # Verify contract exists in database (GraphQL returns Relay ID; decode to UUID)
        contract_relay_id = result["contract"]["id"]
        contract_id = _decode_relay_id(contract_relay_id)
        contract = Contract.objects.get(id=contract_id)
        self.assertEqual(contract.original_spec_type, OriginalSpecType.ODPS)

    def test_link_odps_workflow(self):
        """Test complete workflow: Link ODPS to ODCS via GraphQL"""
        from hub.apps.contracts.services import ContractService

        contract_service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        # Create ODCS and ODPS via service so they get normalized (hub_contract_json required for linking)
        odcs_contract = contract_service.create_contract(
            original_raw=json.dumps(self.sample_odcs),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            asset_id=str(self.asset.id) if hasattr(self, "asset") and self.asset else None,
        )
        odps_contract = contract_service.create_contract(
            original_raw=json.dumps(self.sample_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            asset_id=str(self.asset.id) if hasattr(self, "asset") and self.asset else None,
        )

        mutation = """
        mutation LinkODPS($odcsId: ID!, $odpsId: ID!) {
            linkODPS(odcsId: $odcsId, odpsId: $odpsId) {
                odpsContract {
                    id
                    odcsLink
                }
                odcsContract {
                    id
                    odpsLink
                }
                errors
            }
        }
        """

        variables = {
            "odcsId": str(odcs_contract.id),
            "odpsId": str(odps_contract.id),
        }

        response = self._graphql_mutation(mutation, variables)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = json.loads(response.content)
        self.assertIn("data", data)
        result = data["data"].get("linkODPS")
        self.assertIsNotNone(result, "linkODPS mutation returned no result")
        errors = result.get("errors") if result else []
        self.assertEqual(len(errors), 0, f"linkODPS errors: {errors}")
        self.assertIsNotNone(result.get("odpsContract"), "linkODPS should return odpsContract")
        self.assertIsNotNone(result.get("odcsContract"), "linkODPS should return odcsContract")

    def test_unlink_odps_workflow(self):
        """Test complete workflow: Unlink ODPS from ODCS via GraphQL"""
        # Create ODCS contract
        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset if hasattr(self, "asset") else None,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.sample_odcs),
            created_by=self.user,
        )

        mutation = """
        mutation UnlinkODPS($odcsId: ID!) {
            unlinkODPS(odcsId: $odcsId) {
                success
                errors
            }
        }
        """

        variables = {"odcsId": str(odcs_contract.id)}

        response = self._graphql_mutation(mutation, variables)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = json.loads(response.content)
        self.assertIn("data", data)
        result = data["data"].get("unlinkODPS")
        self.assertIsNotNone(result, "unlinkODPS mutation returned no result")
        # Should succeed even if no link exists
        self.assertTrue(result.get("success"), "unlinkODPS should return success=True")

    def test_export_odps_workflow(self):
        """Test complete workflow: Export ODPS contract via GraphQL"""
        # Create ODPS contract with hub_contract_json
        hub_contract = {
            "id": "test-contract",
            "info": {
                "name": "Test Contract",
                "description": "Test contract description",
            },
            "schema": {"fields": [{"name": "field1", "type": "string", "required": True}]},
        }

        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset if hasattr(self, "asset") else None,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.sample_odps),
            hub_contract_json=hub_contract,
            created_by=self.user,
        )

        mutation = """
        mutation ExportODPS($contractId: ID!, $options: ExportODPSOptions) {
            exportODPS(contractId: $contractId, options: $options) {
                content
                format
                errors
            }
        }
        """

        variables = {
            "contractId": str(odps_contract.id),
            "options": {"version": "4.1", "format": "json"},
        }

        response = self._graphql_mutation(mutation, variables)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = json.loads(response.content)
        self.assertIn("data", data)
        result = data["data"].get("exportODPS")
        self.assertIsNotNone(result, "exportODPS mutation returned no result")
        errors = result.get("errors") if result else []
        self.assertEqual(len(errors), 0, f"exportODPS errors: {errors}")
        self.assertIsNotNone(result["content"])
        self.assertEqual(result["format"], "json")

        # Verify exported content is valid JSON
        exported_data = json.loads(result["content"])
        self.assertIn("schema", exported_data)
        self.assertIn("version", exported_data)
        self.assertIn("product", exported_data)

    def test_export_odps_yaml_workflow(self):
        """Test complete workflow: Export ODPS contract as YAML via GraphQL"""
        # Create ODPS contract with hub_contract_json
        hub_contract = {
            "id": "test-contract",
            "info": {
                "name": "Test Contract",
                "description": "Test contract description",
            },
            "schema": {"fields": [{"name": "field1", "type": "string", "required": True}]},
        }

        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset if hasattr(self, "asset") else None,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.sample_odps),
            hub_contract_json=hub_contract,
            created_by=self.user,
        )

        mutation = """
        mutation ExportODPS($contractId: ID!, $options: ExportODPSOptions) {
            exportODPS(contractId: $contractId, options: $options) {
                content
                format
                errors
            }
        }
        """

        variables = {
            "contractId": str(odps_contract.id),
            "options": {"version": "4.1", "format": "yaml"},
        }

        response = self._graphql_mutation(mutation, variables)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = json.loads(response.content)
        self.assertIn("data", data)
        result = data["data"].get("exportODPS")
        self.assertIsNotNone(result, "exportODPS mutation returned no result")
        errors = result.get("errors") if result else []
        self.assertEqual(len(errors), 0, f"exportODPS errors: {errors}")
        self.assertIsNotNone(result["content"])
        self.assertEqual(result["format"], "yaml")

        # Verify exported content is valid YAML.
        # If PyYAML is not installed, skip the YAML-specific assertions.
        yaml = pytest.importorskip("yaml", reason="PyYAML not installed")
        exported_data = yaml.safe_load(result["content"])
        self.assertIn("schema", exported_data)
        self.assertIn("version", exported_data)
        self.assertIn("product", exported_data)

    def test_complete_odps_workflow(self):
        """Test complete workflow: Create, Link, Export ODPS via GraphQL"""
        # Step 1: Create ODPS contract
        create_mutation = """
        mutation CreateODPS($input: CreateODPSInput!) {
            createODPS(input: $input) {
                contract {
                    id
                    originalSpecType
                }
                errors
            }
        }
        """

        create_variables = {
            "input": {
                "originalRaw": json.dumps(self.sample_odps),
                "originalFormat": "JSON",
                "resolveExternalRefs": True,
            }
        }

        response = self._graphql_mutation(create_mutation, create_variables)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = json.loads(response.content)
        create_result = data.get("data", {}).get("createODPS")
        self.assertIsNotNone(create_result, "createODPS mutation returned no result")
        self.assertIsNotNone(create_result.get("contract"), "createODPS returned no contract")
        odps_contract_id = create_result["contract"]["id"]

        # Step 2: Create ODCS contract via service (so it gets
        # normalized -- hub_contract_json is required for linking)
        from hub.apps.contracts.services import ContractService

        contract_service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        odcs_contract = contract_service.create_contract(
            original_raw=json.dumps(self.sample_odcs),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
        )

        # Step 3: Link ODPS to ODCS
        link_mutation = """
        mutation LinkODPS($odcsId: ID!, $odpsId: ID!) {
            linkODPS(odcsId: $odcsId, odpsId: $odpsId) {
                odpsContract {
                    id
                }
                odcsContract {
                    id
                }
                errors
            }
        }
        """

        link_variables = {
            "odcsId": str(odcs_contract.id),
            "odpsId": odps_contract_id,
        }

        response = self._graphql_mutation(link_mutation, link_variables)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        link_data = json.loads(response.content)
        link_result = link_data.get("data", {}).get("linkODPS")
        self.assertIsNotNone(link_result, "linkODPS mutation returned no result")
        link_errors = link_result.get("errors") if link_result else []
        self.assertEqual(len(link_errors), 0, f"linkODPS errors: {link_errors}")
        self.assertIsNotNone(
            link_result.get("odpsContract"), "linkODPS should return odpsContract with id"
        )
        self.assertIsNotNone(
            link_result.get("odcsContract"), "linkODPS should return odcsContract with id"
        )

        # Step 4: Export ODPS
        export_mutation = """
        mutation ExportODPS($contractId: ID!, $options: ExportODPSOptions) {
            exportODPS(contractId: $contractId, options: $options) {
                content
                format
                errors
            }
        }
        """

        export_variables = {
            "contractId": odps_contract_id,
            "options": {"version": "4.1", "format": "json"},
        }

        response = self._graphql_mutation(export_mutation, export_variables)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = json.loads(response.content)
        result = data["data"].get("exportODPS")
        self.assertIsNotNone(result, "exportODPS mutation returned no result")
        errors = result.get("errors") if result else []
        self.assertEqual(len(errors), 0, f"exportODPS errors: {errors}")
        self.assertIsNotNone(result["content"])
