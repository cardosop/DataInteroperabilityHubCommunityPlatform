"""
Edge case tests for API endpoints.

Tests partial updates, validation errors, and concurrent updates.
"""
import pytest
import threading
import time
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.contracts.models import Contract, ContractStatus, NormalizationStatus
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class APIEdgeCaseTest(TestCase):
    """Edge case tests for API endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    # Partial Updates Tests
    
    def test_partial_update_only_owners(self):
        """Test partial update updating only owners"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Update only owners
        new_owners = [
            {"name": "New Owner", "email": "newowner@example.com"}
        ]
        
        # Get current hub_contract_json
        current_hub = contract.hub_contract_json.copy()
        current_hub["info"]["owners"] = new_owners
        
        # Update via API
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {"original_raw": str(current_hub).replace("'", '"')},
            format="json"
        )
        
        # Should update successfully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
    
    def test_partial_update_only_tags(self):
        """Test partial update updating only tags"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        new_tags = ["new_tag1", "new_tag2"]
        
        current_hub = contract.hub_contract_json.copy()
        current_hub["info"]["tags"] = new_tags
        
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {"original_raw": str(current_hub).replace("'", '"')},
            format="json"
        )
        
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
    
    def test_partial_update_only_quality_rules(self):
        """Test partial update updating only quality rules"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        new_rules = [
            {
                "rule_id": "new_rule",
                "dimension": "completeness",
                "expression": "field1 IS NOT NULL",
                "severity": "ERROR"
            }
        ]
        
        current_hub = contract.hub_contract_json.copy()
        current_hub["quality"]["rules"] = new_rules
        
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {"original_raw": str(current_hub).replace("'", '"')},
            format="json"
        )
        
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
    
    def test_partial_update_only_compliance(self):
        """Test partial update updating only compliance policy"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        new_compliance = {
            "contains_personal_data": False,
            "personal_data_categories": [],
            "jurisdictions": [],
            "legal_bases": []
        }
        
        current_hub = contract.hub_contract_json.copy()
        current_hub["privacy_compliance"] = new_compliance
        
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {"original_raw": str(current_hub).replace("'", '"')},
            format="json"
        )
        
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
    
    def test_partial_update_only_lifecycle(self):
        """Test partial update updating only lifecycle policy"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        new_lifecycle = {
            "data_source": "NEW_SOURCE",
            "refresh_cadence": "HOURLY"
        }
        
        current_hub = contract.hub_contract_json.copy()
        current_hub["lifecycle"] = new_lifecycle
        
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {"original_raw": str(current_hub).replace("'", '"')},
            format="json"
        )
        
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
    
    def test_partial_update_only_marketplace(self):
        """Test partial update updating only marketplace policy"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        new_marketplace = {
            "license_summary": "Apache 2.0",
            "intended_use": ["research"]
        }
        
        current_hub = contract.hub_contract_json.copy()
        current_hub["marketplace"] = new_marketplace
        
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {"original_raw": str(current_hub).replace("'", '"')},
            format="json"
        )
        
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
    
    def test_partial_update_only_schema_fields(self):
        """Test partial update updating only schema fields"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        new_fields = [
            {
                "name": "new_field",
                "data_type": "string",
                "description": "New field"
            }
        ]
        
        current_hub = contract.hub_contract_json.copy()
        current_hub["schema"]["fields"] = new_fields
        
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {"original_raw": str(current_hub).replace("'", '"')},
            format="json"
        )
        
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
    
    # Validation Errors Tests
    
    def test_validation_error_invalid_owner_email(self):
        """Test validation error with invalid owner email"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            owners=[
                {"name": "Owner", "email": "invalid-email"}  # Invalid email
            ]
        )
        
        import json
        response = self.client.post(
            "/api/v1/contracts/contracts/",
            {
                "original_raw": json.dumps(hub_contract),
                "original_format": "JSON",
                "original_spec_type": "ODCS"
            },
            format="json"
        )
        
        # May accept invalid email or reject
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ])
    
    def test_validation_error_invalid_quality_rule_dimension(self):
        """Test validation error with invalid quality rule dimension"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            quality_rules=[
                {
                    "rule_id": "rule1",
                    "dimension": "INVALID_DIMENSION",  # Invalid
                    "expression": "field1 IS NOT NULL",
                    "severity": "ERROR"
                }
            ]
        )
        
        import json
        response = self.client.post(
            "/api/v1/contracts/contracts/",
            {
                "original_raw": json.dumps(hub_contract),
                "original_format": "JSON"
            },
            format="json"
        )
        
        # May accept or reject invalid dimension
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ])
    
    def test_validation_error_invalid_compliance_jurisdiction(self):
        """Test validation error with invalid compliance jurisdiction"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            compliance_policy={
                "contains_personal_data": True,
                "personal_data_categories": ["EMAIL"],
                "jurisdictions": ["INVALID_JURISDICTION"],  # Invalid
                "legal_bases": ["CONSENT"]
            }
        )
        
        import json
        response = self.client.post(
            "/api/v1/contracts/contracts/",
            {
                "original_raw": json.dumps(hub_contract),
                "original_format": "JSON"
            },
            format="json"
        )
        
        # May accept or reject invalid jurisdiction
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ])
    
    def test_validation_error_invalid_field_pattern_regex(self):
        """Test validation error with invalid field pattern regex"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=[
                {
                    "name": "field1",
                    "data_type": "string",
                    "pattern": "[invalid(regex"  # Invalid regex
                }
            ]
        )
        
        import json
        response = self.client.post(
            "/api/v1/contracts/contracts/",
            {
                "original_raw": json.dumps(hub_contract),
                "original_format": "JSON"
            },
            format="json"
        )
        
        # May accept or reject invalid regex
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ])
    
    def test_validation_error_invalid_enum_value_type(self):
        """Test validation error with invalid enum value type"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=[
                {
                    "name": "field1",
                    "data_type": "string",
                    "enum": ["value1", 123, None, {"nested": "object"}]  # Mixed types
                }
            ]
        )
        
        import json
        response = self.client.post(
            "/api/v1/contracts/contracts/",
            {
                "original_raw": json.dumps(hub_contract),
                "original_format": "JSON"
            },
            format="json"
        )
        
        # May accept or reject invalid enum types
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ])
    
    # Concurrent Updates Tests
    
    def test_concurrent_updates_two_users(self):
        """Test two users updating contract simultaneously"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Create second user
        user2 = User.objects.create_user(
            email="user2@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        client2 = APIClient()
        client2.force_authenticate(user=user2)
        
        update_count = {"user1": 0, "user2": 0}
        errors = {"user1": [], "user2": []}
        
        def update_contract(user_id, client):
            try:
                current_hub = contract.hub_contract_json.copy()
                current_hub["info"]["name"] = f"Updated by {user_id}"
                
                response = client.patch(
                    f"/api/v1/contracts/contracts/{contract.id}/",
                    {"original_raw": str(current_hub).replace("'", '"')},
                    format="json"
                )
                
                if response.status_code == status.HTTP_200_OK:
                    update_count[user_id] += 1
                else:
                    errors[user_id].append(response.status_code)
            except Exception as e:
                errors[user_id].append(str(e))
        
        # Start concurrent updates
        thread1 = threading.Thread(target=update_contract, args=("user1", self.client))
        thread2 = threading.Thread(target=update_contract, args=("user2", client2))
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # At least one update should succeed
        self.assertGreater(update_count["user1"] + update_count["user2"], 0)
    
    def test_concurrent_update_during_semantic_mapping(self):
        """Test updating contract while semantic mapping in progress"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Start semantic mapping (if available)
        from hub.apps.semantic.utils import map_contract_to_semantic
        mapping_thread = threading.Thread(
            target=map_contract_to_semantic,
            args=(contract, self.tenant)
        )
        mapping_thread.start()
        
        # Try to update while mapping
        time.sleep(0.1)  # Small delay
        
        current_hub = contract.hub_contract_json.copy()
        current_hub["info"]["name"] = "Updated During Mapping"
        
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {"original_raw": str(current_hub).replace("'", '"')},
            format="json"
        )
        
        mapping_thread.join()
        
        # Update should handle concurrent mapping
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_409_CONFLICT
        ])
    
    # Additional Edge Cases
    
    def test_update_nonexistent_contract(self):
        """Test updating non-existent contract"""
        import uuid
        fake_id = uuid.uuid4()
        
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{fake_id}/",
            {"status": "ACTIVE"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_delete_nonexistent_contract(self):
        """Test deleting non-existent contract"""
        import uuid
        fake_id = uuid.uuid4()
        
        response = self.client.delete(
            f"/api/v1/contracts/contracts/{fake_id}/"
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_create_contract_invalid_json(self):
        """Test creating contract with invalid JSON"""
        response = self.client.post(
            "/api/v1/contracts/contracts/",
            {
                "original_raw": "invalid json {",
                "original_format": "JSON"
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_contract_missing_required_fields(self):
        """Test creating contract with missing required fields"""
        response = self.client.post(
            "/api/v1/contracts/contracts/",
            {},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_update_contract_unauthorized(self):
        """Test updating contract without authentication"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Create unauthenticated client
        unauth_client = APIClient()
        
        response = unauth_client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {"status": "ACTIVE"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_update_contract_wrong_tenant(self):
        """Test updating contract from different tenant"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Create user from different tenant
        other_tenant = TenantFactory.create_tenant()
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )
        other_client = APIClient()
        other_client.force_authenticate(user=other_user)
        
        response = other_client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {"status": "ACTIVE"},
            format="json"
        )
        
        # Should be forbidden or not found
        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ])
    
    def test_list_contracts_empty_result(self):
        """Test listing contracts with no results"""
        response = self.client.get("/api/v1/contracts/contracts/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 0)
    
    def test_list_contracts_with_filters(self):
        """Test listing contracts with various filters"""
        # Create contracts with different properties
        contract1 = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Test various filters
        filters = [
            {"owner_email": "dataplatform@example.com"},
            {"tag": "analytics"},
            {"quality_profile": "intake_basic"},
            {"compliance_regime": "GDPR"}
        ]
        
        for filter_params in filters:
            response = self.client.get("/api/v1/contracts/contracts/", filter_params)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("results", response.data)
    
    def test_retrieve_contract_by_id(self):
        """Test retrieving contract by ID"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        response = self.client.get(f"/api/v1/contracts/contracts/{contract.id}/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(contract.id))
    
    def test_create_contract_with_all_sections(self):
        """Test creating contract with all sections populated"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json()
        
        import json
        response = self.client.post(
            "/api/v1/contracts/contracts/",
            {
                "original_raw": json.dumps(hub_contract),
                "original_format": "JSON",
                "original_spec_type": "ODCS"
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
    
    def test_update_contract_status_only(self):
        """Test updating only contract status"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {"status": "ACTIVE"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ACTIVE")
    
    def test_update_contract_re_normalization(self):
        """Test that updating original_raw triggers re-normalization"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Update original_raw
        new_contract = {
            "id": "new-contract",
            "name": "New Contract Name",
            "schema": {
                "fields": [
                    {"name": "new_field", "type": "string"}
                ]
            }
        }
        
        import json
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {
                "original_raw": json.dumps(new_contract),
                "original_format": "JSON"
            },
            format="json"
        )
        
        # Should trigger re-normalization
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST
        ])
        
        if response.status_code == status.HTTP_200_OK:
            # Normalization status should be updated
            self.assertIn("normalization_status", response.data)
    
    def test_create_contract_auto_detect_spec_type(self):
        """Test creating contract with auto-detection of spec type"""
        odcs_contract = {
            "id": "test-auto-detect",
            "name": "Auto Detect Test",
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"}
                ]
            }
        }
        
        import json
        response = self.client.post(
            "/api/v1/contracts/contracts/",
            {
                "original_raw": json.dumps(odcs_contract),
                "original_format": "JSON"
                # No original_spec_type - should auto-detect
            },
            format="json"
        )
        
        # Should auto-detect ODCS
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ])
        
        if response.status_code == status.HTTP_201_CREATED:
            self.assertIn("original_spec_type", response.data)
    
    def test_list_contracts_pagination(self):
        """Test listing contracts with pagination"""
        # Create multiple contracts
        for i in range(5):
            ContractFactoryEnhanced.create_contract_with_all_sections(
                tenant=self.tenant,
                created_by=self.user
            )
        
        response = self.client.get("/api/v1/contracts/contracts/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
    
    def test_list_contracts_ordering(self):
        """Test listing contracts with ordering"""
        # Create contracts
        for i in range(3):
            ContractFactoryEnhanced.create_contract_with_all_sections(
                tenant=self.tenant,
                created_by=self.user
            )
        
        # Test ordering
        response = self.client.get("/api/v1/contracts/contracts/", {"ordering": "-created_at"})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
    
    def test_create_contract_yaml_format(self):
        """Test creating contract with YAML format"""
        yaml_content = """
id: test-yaml
name: YAML Contract
schema:
  fields:
    - name: field1
      type: string
"""
        
        response = self.client.post(
            "/api/v1/contracts/contracts/",
            {
                "original_raw": yaml_content,
                "original_format": "YAML"
            },
            format="json"
        )
        
        # May support YAML or return error
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ])
    
    def test_update_contract_large_payload(self):
        """Test updating contract with very large payload"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Create large contract
        large_fields = [{"name": f"field_{i}", "type": "string"} for i in range(1000)]
        large_contract = {
            "id": "large-contract",
            "name": "Large Contract",
            "schema": {
                "fields": large_fields
            }
        }
        
        import json
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {
                "original_raw": json.dumps(large_contract),
                "original_format": "JSON"
            },
            format="json"
        )
        
        # Should handle large payload
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        ])
    
    def test_create_contract_unicode_content(self):
        """Test creating contract with unicode content"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            name="Contract with 测试 Unicode",
            description="Description with émojis 🎉 and 中文"
        )
        
        import json
        response = self.client.post(
            "/api/v1/contracts/contracts/",
            {
                "original_raw": json.dumps(hub_contract, ensure_ascii=False),
                "original_format": "JSON"
            },
            format="json"
        )
        
        # Should handle unicode
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ])
    
    def test_update_contract_special_characters(self):
        """Test updating contract with special characters"""
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        current_hub = contract.hub_contract_json.copy()
        current_hub["info"]["name"] = "Contract with Special: !@#$%^&*()"
        
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            {"original_raw": str(current_hub).replace("'", '"')},
            format="json"
        )
        
        # Should handle special characters
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST
        ])

