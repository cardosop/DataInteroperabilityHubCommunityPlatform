"""
Integration tests for Product-First creation endpoint (Task 3.5.1)

Tests verify:
1. POST /api/v1/contracts/products/ endpoint
2. Accept ODPS document (YAML/JSON)
3. Support resolve_external_refs parameter
4. Return created contracts (ODPS + ODCS, linked)
5. Error handling for invalid inputs
"""
import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.contracts.models import Contract, OriginalSpecType, OriginalFormat, ContractStatus, NormalizationStatus
from hub.apps.tenants.models import Tenant
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine


User = get_user_model()


class ProductFirstEndpointIntegrationTest(TestCase):
    """Integration tests for Product-First creation endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.client.force_authenticate(user=self.user)

        # Register workflow
        self.registry = WorkflowRegistry()
        ProductCreationWorkflow.register_workflow(self.registry)
        self.engine = WorkflowEngine()
        ProductCreationWorkflow.register_tasks(self.engine)

        # Valid ODPS document with embedded ODCS contract
        self.valid_odps_json = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-001",
                        "name": "Test Product",
                        "description": "A test product for integration testing",
                        "productVersion": "1.0.0"
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": "test-odcs-contract",
                        "name": "Test ODCS Contract",
                        "version": "1.0.0",
                        "description": "Test ODCS contract for integration testing",
                        "schema": {
                            "fields": [
                                {
                                    "name": "id",
                                    "type": "string",
                                    "nullable": False,
                                    "description": "Unique identifier"
                                }
                            ]
                        }
                    }
                }
            }
        }, indent=2)

    def test_create_product_json_success(self):
        """Test successful product creation with JSON format"""
        from django.urls import reverse
        url = reverse("contract-create-product")
        response = self.client.post(
            url,
            {
                "original_raw": self.valid_odps_json,
                "original_format": "JSON",
                "resolve_external_refs": True
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("odps_contract", response.data)
        self.assertIn("odcs_contract", response.data)
        self.assertIn("workflow_instance_id", response.data)

        # Verify ODPS contract
        odps_contract_data = response.data["odps_contract"]
        self.assertEqual(odps_contract_data["original_spec_type"], OriginalSpecType.ODPS)
        self.assertEqual(odps_contract_data["original_format"], OriginalFormat.JSON)

        # Verify ODCS contract
        odcs_contract_data = response.data["odcs_contract"]
        self.assertEqual(odcs_contract_data["original_spec_type"], OriginalSpecType.ODCS)
        self.assertEqual(odcs_contract_data["original_format"], OriginalFormat.JSON)

        # Verify contracts are linked
        odps_contract = Contract.objects.get(id=odps_contract_data["id"])
        odcs_contract = Contract.objects.get(id=odcs_contract_data["id"])

        self.assertIsNotNone(odps_contract.hub_contract_json)
        self.assertIsNotNone(odcs_contract.hub_contract_json)

        odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
        odcs_extensions = odcs_contract.hub_contract_json.get("extensions", {})

        if "x_odps" in odps_extensions:
            self.assertEqual(
                odps_extensions["x_odps"].get("odcs_link"),
                str(odcs_contract.id)
            )

        if "x_odps" in odcs_extensions:
            self.assertEqual(
                odcs_extensions["x_odps"].get("odps_link"),
                str(odps_contract.id)
            )

    def test_create_product_yaml_success(self):
        """Test successful product creation with YAML format"""
        valid_odps_yaml = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: test-product-002
      name: Test Product YAML
      description: A test product in YAML format
      productVersion: "1.0.0"
  contract:
    spec:
      apiVersion: odcs.io/v3.0.2
      kind: DataContract
      id: test-odcs-contract-yaml
      name: Test ODCS Contract YAML
      version: "1.0.0"
      description: Test ODCS contract in YAML format
      schema:
        fields:
          - name: id
            type: string
            nullable: false
            description: Unique identifier
"""

        from django.urls import reverse
        url = reverse("contract-create-product")
        response = self.client.post(
            url,
            {
                "original_raw": valid_odps_yaml,
                "original_format": "YAML",
                "resolve_external_refs": True
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("odps_contract", response.data)
        self.assertIn("odcs_contract", response.data)

        odps_contract_data = response.data["odps_contract"]
        self.assertEqual(odps_contract_data["original_format"], OriginalFormat.YAML)

    def test_create_product_with_asset_id(self):
        """Test product creation with asset_id parameter"""
        from hub.apps.assets.models import Asset

        # Create an asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset for product linking"
        )

        from django.urls import reverse
        url = reverse("contract-create-product")
        response = self.client.post(
            url,
            {
                "original_raw": self.valid_odps_json,
                "original_format": "JSON",
                "resolve_external_refs": True,
                "asset_id": str(asset.id)
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify contracts are linked to asset
        odps_contract = Contract.objects.get(id=response.data["odps_contract"]["id"])
        odcs_contract = Contract.objects.get(id=response.data["odcs_contract"]["id"])

        self.assertEqual(odps_contract.asset, asset)
        self.assertEqual(odcs_contract.asset, asset)

    def test_create_product_resolve_external_refs_false(self):
        """Test product creation with resolve_external_refs=False"""
        # ODPS with external reference (will fail if resolve_external_refs=False)
        odps_with_external_ref = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-003",
                        "name": "Test Product with External Ref"
                    }
                },
                "contract": {
                    "spec": {
                        "$ref": "https://external.example.com/contract.json"
                    }
                }
            }
        }, indent=2)

        from django.urls import reverse
        url = reverse("contract-create-product")
        response = self.client.post(
            url,
            {
                "original_raw": odps_with_external_ref,
                "original_format": "JSON",
                "resolve_external_refs": False
            },
            format="json"
        )

        # Should fail because external refs are disabled
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_create_product_invalid_odps(self):
        """Test product creation with invalid ODPS document"""
        invalid_odps = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            # Missing required "product" field
        }, indent=2)

        from django.urls import reverse
        url = reverse("contract-create-product")
        response = self.client.post(
            url,
            {
                "original_raw": invalid_odps,
                "original_format": "JSON",
                "resolve_external_refs": True
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_create_product_missing_required_fields(self):
        """Test product creation with missing required fields"""
        from django.urls import reverse
        url = reverse("contract-create-product")
        response = self.client.post(
            url,
            {
                # Missing original_raw
                "original_format": "JSON"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_product_invalid_format(self):
        """Test product creation with invalid format"""
        from django.urls import reverse
        url = reverse("contract-create-product")
        response = self.client.post(
            url,
            {
                "original_raw": self.valid_odps_json,
                "original_format": "INVALID_FORMAT",
                "resolve_external_refs": True
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_product_unauthenticated(self):
        """Test product creation without authentication"""
        self.client.force_authenticate(user=None)

        from django.urls import reverse
        url = reverse("contract-create-product")
        response = self.client.post(
            url,
            {
                "original_raw": self.valid_odps_json,
                "original_format": "JSON",
                "resolve_external_refs": True
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_product_default_resolve_external_refs(self):
        """Test that resolve_external_refs defaults to True"""
        from django.urls import reverse
        url = reverse("contract-create-product")
        response = self.client.post(
            url,
            {
                "original_raw": self.valid_odps_json,
                "original_format": "JSON"
                # resolve_external_refs not specified, should default to True
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("odps_contract", response.data)
        self.assertIn("odcs_contract", response.data)

    def test_create_product_workflow_instance_id_returned(self):
        """Test that workflow_instance_id is returned in response"""
        from django.urls import reverse
        url = reverse("contract-create-product")
        response = self.client.post(
            url,
            {
                "original_raw": self.valid_odps_json,
                "original_format": "JSON",
                "resolve_external_refs": True
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("workflow_instance_id", response.data)
        self.assertIsNotNone(response.data["workflow_instance_id"])

        # Verify workflow instance exists
        from hub.apps.orchestration.models import WorkflowInstance
        workflow_instance = WorkflowInstance.objects.get(id=response.data["workflow_instance_id"])
        self.assertIsNotNone(workflow_instance)
        self.assertEqual(workflow_instance.workflow_name, ProductCreationWorkflow.WORKFLOW_NAME)

