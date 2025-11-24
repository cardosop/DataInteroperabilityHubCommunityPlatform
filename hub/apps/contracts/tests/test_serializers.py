"""
Unit tests for contract serializers.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.contracts.serializers import (
    ContractSerializer,
    ContractCreateSerializer,
    ContractUpdateSerializer,
)

User = get_user_model()


class ContractSerializerTest(TestCase):
    """Test contract serializers"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test Contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1, "id": "test"},
            created_by=self.user
        )
    
    def test_contract_serializer(self):
        """Test ContractSerializer serialization"""
        serializer = ContractSerializer(self.contract)
        data = serializer.data
        
        self.assertEqual(data['id'], str(self.contract.id))
        self.assertEqual(data['status'], ContractStatus.DRAFT)
        self.assertEqual(data['original_spec_type'], OriginalSpecType.ODCS)
        self.assertIn('original_raw', data)
        self.assertIn('hub_contract_json', data)
    
    def test_contract_create_serializer(self):
        """Test ContractCreateSerializer validation"""
        serializer = ContractCreateSerializer(data={
            'original_raw': '{"id": "new", "name": "New Contract"}',
            'original_format': 'JSON',
            'original_spec_type': 'ODCS'
        })
        
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['original_format'], 'JSON')
        self.assertEqual(serializer.validated_data['original_spec_type'], 'ODCS')
    
    def test_contract_create_serializer_invalid_format(self):
        """Test ContractCreateSerializer with invalid format"""
        serializer = ContractCreateSerializer(data={
            'original_raw': '{"id": "test"}',
            'original_format': 'INVALID',
            'original_spec_type': 'ODCS'
        })
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('original_format', serializer.errors)
    
    def test_contract_update_serializer(self):
        """Test ContractUpdateSerializer"""
        # Note: ContractUpdateSerializer is a plain Serializer, not ModelSerializer
        # So we test validation only, not save
        serializer = ContractUpdateSerializer(
            data={
                'status': ContractStatus.ACTIVE
            }
        )
        
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['status'], ContractStatus.ACTIVE)

