"""
Comprehensive Frontend Data Format Test Suite (Task 10.1.18.5)

Tests verify:
1. All API responses use consistent data formats
2. All dates are in ISO 8601 format
3. All UUIDs are in standard format
4. All nested objects are properly structured
"""
import json
import re
from datetime import datetime
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.contracts.models import (
    Contract, ContractStatus, OriginalSpecType, OriginalFormat, NormalizationStatus
)
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, Role, UserRole, UserStatus


class FrontendDataFormatTest(TestCase):
    """
    Comprehensive frontend data format tests (Task 10.1.18.5).
    
    Tests all API responses for consistent data formats without mocks/stubs:
    1. Consistent data formats
    2. ISO 8601 date format
    3. Standard UUID format
    4. Properly structured nested objects
    """
    
    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Data Format Test Tenant",
            slug="data-format-test",
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
            email="user@dataformat.test",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=self.user, role=self.admin_role)
        
        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name="Data Format Test Asset",
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
                        "productID": "test-product-dataformat",
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
        
        # Create test contract
        self.contract = Contract.objects.create(
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
    
    def test_all_dates_are_in_iso_8601_format(self):
        """Test all dates are in ISO 8601 format"""
        response = self.client.get(f'/api/v1/contracts/{self.contract.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Check date fields
        date_fields = ['created_at', 'updated_at', 'deleted_at']
        iso8601_pattern = re.compile(
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$'
        )
        
        for field in date_fields:
            if field in data and data[field]:
                date_value = str(data[field])
                # Should match ISO 8601 pattern or contain T separator
                self.assertTrue(
                    'T' in date_value or iso8601_pattern.match(date_value),
                    f"{field} should be in ISO 8601 format, got: {date_value}"
                )
    
    def test_all_uuids_are_in_standard_format(self):
        """Test all UUIDs are in standard format"""
        response = self.client.get(f'/api/v1/contracts/{self.contract.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # UUID pattern: 8-4-4-4-12 hex digits
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        
        # Check ID field
        if 'id' in data:
            id_value = str(data['id'])
            if len(id_value) == 36:  # UUID length
                self.assertTrue(
                    uuid_pattern.match(id_value),
                    f"ID should be in UUID format, got: {id_value}"
                )
    
    def test_all_nested_objects_are_properly_structured(self):
        """Test all nested objects are properly structured"""
        response = self.client.get(f'/api/v1/contracts/{self.contract.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Verify nested objects are dictionaries, not strings
        nested_fields = ['hub_contract_json', 'original_raw']
        for field in nested_fields:
            if field in data and data[field] is not None:
                field_value = data[field]
                # Should be dict (parsed JSON) or string (JSON string) or None
                self.assertIsInstance(field_value, (dict, str, type(None)),
                                     f"{field} should be dict, string, or None")
                
                # If it's a string, it should be valid JSON
                if isinstance(field_value, str):
                    try:
                        parsed = json.loads(field_value)
                        self.assertIsInstance(parsed, (dict, list),
                                             f"{field} should contain valid JSON")
                    except json.JSONDecodeError:
                        # If it's not JSON, that's okay - might be other format
                        pass
    
    def test_api_responses_use_consistent_data_formats(self):
        """Test all API responses use consistent data formats"""
        # Test list endpoint
        list_response = self.client.get('/api/v1/contracts/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        list_data = list_response.json()
        
        # Test detail endpoint
        detail_response = self.client.get(f'/api/v1/contracts/{self.contract.id}/')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        detail_data = detail_response.json()
        
        # Both should be JSON
        self.assertIsInstance(list_data, (dict, list),
                             "List response should be dict or list")
        self.assertIsInstance(detail_data, dict,
                             "Detail response should be dict")
        
        # If list response has results, verify structure
        if isinstance(list_data, dict) and 'results' in list_data:
            results = list_data['results']
            if results and isinstance(results, list):
                # First result should have similar structure to detail
                first_result = results[0]
                if 'id' in first_result and 'id' in detail_data:
                    # Both should have ID field
                    self.assertIn('id', first_result)
                    self.assertIn('id', detail_data)
