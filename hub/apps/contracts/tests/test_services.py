"""
Unit tests for ContractService.

Tests cover all service methods with 100% coverage target.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from unittest.mock import Mock, patch, MagicMock

from hub.apps.contracts.services import ContractService
from hub.apps.contracts.models import Contract, ContractStatus, NormalizationStatus
from hub.apps.core.services.base import ValidationError, NotFoundError, ConflictError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus


pytestmark = pytest.mark.django_db(transaction=True)


class ContractServiceTest(TestCase):
    """Test ContractService operations"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
    
    def test_create_contract_success(self):
        """Test successful contract creation"""
        original_raw = '{"info": {"name": "test-contract"}}'
        original_format = "JSON"
        
        contract = self.service.create_contract(
            original_raw=original_raw,
            original_format=original_format,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        
        self.assertIsNotNone(contract)
        self.assertEqual(contract.original_raw, original_raw)
        self.assertEqual(contract.original_format, original_format)
        self.assertEqual(str(contract.tenant_id), str(self.tenant.id))
    
    def test_create_contract_with_asset(self):
        """Test contract creation with asset"""
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT
        )
        
        original_raw = '{"info": {"name": "test-contract"}}'
        original_format = "JSON"
        
        contract = self.service.create_contract(
            original_raw=original_raw,
            original_format=original_format,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset.id)
        )
        
        self.assertIsNotNone(contract)
        self.assertEqual(contract.asset_id, asset.id)
    
    def test_create_contract_asset_not_found(self):
        """Test contract creation with non-existent asset"""
        original_raw = '{"info": {"name": "test-contract"}}'
        original_format = "JSON"
        
        with self.assertRaises(NotFoundError) as cm:
            self.service.create_contract(
                original_raw=original_raw,
                original_format=original_format,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                asset_id="00000000-0000-0000-0000-000000000000"
            )
        
        self.assertEqual(cm.exception.code, "NOT_FOUND")
    
    def test_update_contract_success(self):
        """Test successful contract update"""
        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "old-contract"}}',
            original_format="JSON",
            status=ContractStatus.DRAFT
        )
        
        updated_raw = '{"info": {"name": "updated-contract"}}'
        
        updated_contract = self.service.update_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_raw=updated_raw
        )
        
        updated_contract.refresh_from_db()
        self.assertEqual(updated_contract.original_raw, updated_raw)
    
    def test_update_contract_not_found(self):
        """Test contract update with non-existent contract"""
        with self.assertRaises(NotFoundError):
            self.service.update_contract(
                contract_id="00000000-0000-0000-0000-000000000000",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                original_raw='{"info": {"name": "test"}}'
            )
    
    def test_update_contract_status(self):
        """Test contract status update"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.DRAFT
        )
        
        updated_contract = self.service.update_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            status=ContractStatus.ACTIVE
        )
        
        updated_contract.refresh_from_db()
        self.assertEqual(updated_contract.status, ContractStatus.ACTIVE)
    
    def test_update_contract_invalid_status(self):
        """Test contract update with invalid status"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.DRAFT
        )
        
        with self.assertRaises(ValidationError) as cm:
            self.service.update_contract(
                contract_id=str(contract.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                status="INVALID_STATUS"
            )
        
        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
    
    def test_delete_contract_success(self):
        """Test successful contract deletion"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE
        )
        
        self.service.delete_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        
        contract.refresh_from_db()
        self.assertEqual(contract.status, ContractStatus.RETIRED)
    
    def test_delete_contract_not_found(self):
        """Test contract deletion with non-existent contract"""
        with self.assertRaises(NotFoundError):
            self.service.delete_contract(
                contract_id="00000000-0000-0000-0000-000000000000",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )
    
    def test_get_contract_success(self):
        """Test successful contract retrieval"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE
        )
        
        retrieved = self.service.get_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(retrieved.id, contract.id)
        self.assertEqual(retrieved.original_raw, contract.original_raw)
    
    def test_get_contract_not_found(self):
        """Test contract retrieval with non-existent contract"""
        with self.assertRaises(NotFoundError):
            self.service.get_contract(
                contract_id="00000000-0000-0000-0000-000000000000",
                tenant_id=str(self.tenant.id)
            )
    
    def test_list_contracts_success(self):
        """Test successful contract listing"""
        # Create multiple contracts
        for i in range(5):
            Contract.objects.create(
                tenant=self.tenant,
                original_raw=f'{{"info": {{"name": "contract-{i}"}}}}',
                original_format="JSON",
                status=ContractStatus.ACTIVE
            )
        
        contracts, pagination_meta = self.service.list_contracts(
            tenant_id=str(self.tenant.id),
            page=1,
            page_size=20
        )
        
        self.assertEqual(len(contracts), 5)
        self.assertEqual(pagination_meta['count'], 5)
    
    def test_list_contracts_with_filters(self):
        """Test contract listing with filters"""
        # Create contracts with different statuses
        Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "active-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE
        )
        Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "draft-contract"}}',
            original_format="JSON",
            status=ContractStatus.DRAFT
        )
        
        contracts, _ = self.service.list_contracts(
            tenant_id=str(self.tenant.id),
            filters={'status': ContractStatus.ACTIVE}
        )
        
        self.assertEqual(len(contracts), 1)
        self.assertEqual(contracts[0].status, ContractStatus.ACTIVE)
    
    def test_validate_contract_sync(self):
        """Test synchronous contract validation"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE
        )
        
        with patch('hub.apps.contracts.services.DataContractCLIClient') as mock_cli:
            mock_client_instance = Mock()
            mock_cli.return_value = mock_client_instance
            mock_client_instance.validate.return_value = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'cli_version': '1.0.0'
            }
            
            result = self.service.validate_contract(
                contract_id=str(contract.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                use_async=False
            )
            
            self.assertFalse(result['async'])
            self.assertIn('validation_status', result)
    
    def test_validate_contract_async(self):
        """Test asynchronous contract validation"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}' * 1000,  # Large contract
            original_format="JSON",
            status=ContractStatus.ACTIVE
        )
        
        result = self.service.validate_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            use_async=True
        )
        
        self.assertTrue(result['async'])
        self.assertIn('job_id', result)

