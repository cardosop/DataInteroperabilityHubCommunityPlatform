"""
Unit tests for contract CRUD operations.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
import uuid

from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat, NormalizationStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ContractCRUDTest(TestCase):
    """Test contract CRUD operations"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_create_contract_json(self):
        """Test creating a contract with JSON format"""
        self.client.force_authenticate(user=self.user)
        
        contract_data = {
            "id": "test-contract",
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            }
        }
        
        import json
        data = {
            "original_raw": json.dumps(contract_data),
            "original_format": OriginalFormat.JSON
        }
        
        response = self.client.post("/api/v1/contracts/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], ContractStatus.DRAFT)
        self.assertEqual(response.data["original_format"], OriginalFormat.JSON)
        
        # Verify contract was created
        contract_id = response.data["id"]
        contract = Contract.objects.get(id=contract_id)
        self.assertEqual(contract.tenant, self.tenant)
        self.assertEqual(contract.created_by, self.user)
    
    def test_create_contract_yaml(self):
        """Test creating a contract with YAML format"""
        self.client.force_authenticate(user=self.user)
        
        yaml_content = """
id: test-contract
name: Test Contract
schema:
  fields:
    - name: id
      type: string
    - name: name
      type: string
"""
        
        data = {
            "original_raw": yaml_content,
            "original_format": OriginalFormat.YAML
        }
        
        response = self.client.post("/api/v1/contracts/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["original_format"], OriginalFormat.YAML)
    
    def test_retrieve_contract(self):
        """Test retrieving a contract"""
        self.client.force_authenticate(user=self.user)
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user
        )
        
        response = self.client.get(f"/api/v1/contracts/{contract.id}/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(contract.id))
        self.assertEqual(response.data["original_raw"], contract.original_raw)
    
    def test_update_contract(self):
        """Test updating a contract"""
        self.client.force_authenticate(user=self.user)
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user
        )
        
        updated_data = {
            "original_raw": '{"id": "test", "name": "Updated Test"}',
            "original_format": OriginalFormat.JSON
        }
        
        response = self.client.patch(f"/api/v1/contracts/{contract.id}/", updated_data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        contract.refresh_from_db()
        self.assertEqual(contract.original_raw, updated_data["original_raw"])
        # Validation status should be reset
        self.assertIsNone(contract.validation_status)
    
    def test_delete_contract(self):
        """Test deleting a contract (soft delete)"""
        self.client.force_authenticate(user=self.user)
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user
        )
        
        response = self.client.delete(f"/api/v1/contracts/{contract.id}/")
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        contract.refresh_from_db()
        self.assertEqual(contract.status, ContractStatus.RETIRED)
    
    def test_list_contracts_tenant_scoped(self):
        """Test that users can only see contracts in their tenant"""
        self.client.force_authenticate(user=self.user)
        
        # Create another tenant and contract
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "other", "name": "Other"}'
        )
        
        # Create contract in user's tenant
        my_contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "mine", "name": "Mine"}',
            created_by=self.user
        )
        
        response = self.client.get("/api/v1/contracts/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        contract_ids = [c["id"] for c in response.data["results"]]
        
        # Should only see contracts in own tenant
        self.assertIn(str(my_contract.id), contract_ids)
        self.assertNotIn(str(other_contract.id), contract_ids)

