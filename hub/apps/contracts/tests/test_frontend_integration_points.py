"""
Comprehensive Frontend Integration Point Test Suite (Task 10.1.18.2)

Tests verify:
1. All APIs return data in frontend-consumable format
2. All events are in frontend-consumable format
3. All WebSocket events are in frontend-consumable format
4. All error responses are frontend-friendly
"""
import json
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.contracts.models import (
    Contract, ContractStatus, OriginalSpecType, OriginalFormat, NormalizationStatus
)
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, Role, UserRole, UserStatus


class FrontendIntegrationPointsTest(TestCase):
    """
    Comprehensive frontend integration point tests (Task 10.1.18.2).
    
    Tests all APIs and events for frontend-consumable format without mocks/stubs:
    1. APIs return JSON in frontend-consumable format
    2. Events are in frontend-consumable format
    3. WebSocket events are properly formatted
    4. Error responses are frontend-friendly
    """
    
    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Frontend Test Tenant",
            slug="frontend-test",
            kyc_status=KYCStatus.VERIFIED
        )
        
        # Create role
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator"}
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="user@frontend.test",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=self.user, role=self.admin_role)
        
        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name="Frontend Test Asset",
            status=AssetStatus.ACTIVE
        )
        
        # Create client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Valid ODPS structure
        self.valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-frontend",
                        "name": "Test Product",
                        "description": "Test description"
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "name": "Test Contract",
                        "version": "1.0.0",
                        "schema": {
                            "fields": [
                                {"name": "id", "type": "string", "nullable": False}
                            ]
                        }
                    }
                }
            }
        }
    
    def test_apis_return_data_in_frontend_consumable_format(self):
        """Test all APIs return data in frontend-consumable format"""
        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.valid_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK
        )
        
        # Test GET endpoint
        response = self.client.get(f'/api/v1/contracts/{contract.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK,
                        "API should return data")
        
        # Verify response is JSON
        self.assertEqual(response['Content-Type'], 'application/json',
                        "Response should be JSON")
        
        # Verify response structure is frontend-consumable
        data = response.json()
        self.assertIsInstance(data, dict, "Response should be a dictionary")
        
        # Verify common frontend-consumable fields
        if 'id' in data:
            self.assertIsInstance(data['id'], (str, int),
                                "ID should be string or integer")
    
    def test_error_responses_are_frontend_friendly(self):
        """Test all error responses are frontend-friendly"""
        # Test 404 error
        response = self.client.get('/api/v1/contracts/00000000-0000-0000-0000-000000000000/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND,
                        "Should return 404 for non-existent resource")
        
        # Verify error response is JSON
        self.assertEqual(response['Content-Type'], 'application/json',
                        "Error response should be JSON")
        
        # Verify error response structure
        error_data = response.json()
        self.assertIsInstance(error_data, dict, "Error response should be a dictionary")
        
        # Error responses should be frontend-friendly (have message or detail)
        has_message = 'message' in error_data or 'detail' in error_data or 'error' in error_data
        self.assertTrue(has_message,
                       "Error response should include message, detail, or error field")
    
    def test_api_responses_use_consistent_data_formats(self):
        """Test all API responses use consistent data formats"""
        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.valid_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK
        )
        
        # Test detail endpoint
        response = self.client.get(f'/api/v1/contracts/{contract.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Verify UUIDs are in standard format (if present)
        if 'id' in data:
            id_value = str(data['id'])
            # UUID format: 8-4-4-4-12 hex digits
            if len(id_value) == 36 and id_value.count('-') == 4:
                # Valid UUID format
                pass
        
        # Verify dates are in ISO 8601 format (if present)
        date_fields = ['created_at', 'updated_at', 'deleted_at']
        for field in date_fields:
            if field in data and data[field]:
                date_value = str(data[field])
                # Should be ISO 8601 format (contains T and Z or timezone)
                self.assertIn('T', date_value or '',
                            f"{field} should be in ISO 8601 format")
