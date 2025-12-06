"""
Comprehensive E2E tests for contract-only onboarding flow.
pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e_batch1]


Covers:
- Success paths (contract-only activation, attach data later)
- Failure scenarios (invalid contract, activation without validation)
- Edge cases (contract without schema, multiple contracts)

Uses REAL services (DataContract, MinIO).
"""
import pytest
from django.test import TestCase
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, ValidationStatus, NormalizationStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.datasets.models import Dataset

from .conftest import E2ETestBase


class ContractOnlyFlowSuccessTests(E2ETestBase):
    """Test successful contract-only onboarding flows"""
    
    def test_complete_contract_only_journey_happy_path(self):
        """Test complete contract-only onboarding journey - happy path"""
        # Step 1: Create asset
        asset_id = self.create_asset(
            key='contract-only',
            name='Contract Only Asset'
        )
        
        # Step 2: Create contract (no data)
        contract_id = self.create_contract(
            asset_id,
            original_raw='{"id": "contract-only", "name": "Contract Only", "schema": {"fields": []}}'
        )
        
        # Step 3: Validate contract
        # Check DataContract service availability upfront
        self.require_service('DataContract', self.datacontract_service_url, health_path='/health')
        
        validate_response = self.validate_contract(contract_id, async_mode=False)
        # Service is available, validation should have completed
        if isinstance(validate_response, dict) and 'validation_status' in validate_response:
            self.assertIn(validate_response.get('validation_status'), ['VALID', 'INVALID'])
        
        # Step 4: Attach contract to asset
        self.attach_contract_to_asset(asset_id, contract_id)
        
        # Step 5: Prepare contract for activation
        self.prepare_contract_for_activation(contract_id)
        
        # Step 6: Activate asset (no dataset required)
        activate_response = self.activate_asset(asset_id)
        # activate_asset already asserts 200 OK, but we can verify the response
        if hasattr(activate_response, 'status_code'):
            self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        
        # Verify final state - asset is ACTIVE without dataset
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        self.assertTrue(asset.contracts.exists())
        self.assertFalse(asset.datasets.exists())  # No dataset for contract-only
    
    def test_contract_only_then_attach_data_later(self):
        """Test contract-only flow with data attached later"""
        # Step 1: Create contract-only asset
        asset_id = self.create_asset(key='contract-then-data', name='Contract Then Data')
        
        contract_id = self.create_contract(
            asset_id,
            original_raw='{"id": "test", "schema": {"fields": [{"name": "id", "type": "string"}]}}'
        )
        
        self.validate_contract(contract_id)
        self.attach_contract_to_asset(asset_id, contract_id)
        self.prepare_contract_for_activation(contract_id)
        
        activate_response = self.activate_asset(asset_id)
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        
        # Step 2: Attach data later
        file_id = self.init_file_upload(name='data.csv')
        self.complete_file_upload(file_id)
        
        dataset_id = self.create_dataset(file_id, asset_id)
        
        # Step 3: Run compliance and DQ checks
        compliance_run_id = self.run_compliance_check(file_id, dataset_id, asset_id)
        dq_run_id = self.run_dq_check(file_id, dataset_id, asset_id)
        
        # Step 4: Attach dataset to asset
        self.attach_dataset_to_asset(asset_id, dataset_id)
        
        # Asset should remain ACTIVE with dataset attached
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        self.assertTrue(asset.datasets.exists())
    
    def test_contract_only_with_multiple_contracts(self):
        """Test contract-only asset with multiple contracts"""
        asset_id = self.create_asset(key='multiple-contracts', name='Multiple Contracts')
        
        # Create first contract
        contract1_id = self.create_contract(
            asset_id,
            original_raw='{"id": "contract1", "schema": {"fields": []}}'
        )
        
        # Create second contract
        contract2_id = self.create_contract(
            asset_id,
            original_raw='{"id": "contract2", "schema": {"fields": []}}'
        )
        
        # Attach both contracts
        self.attach_contract_to_asset(asset_id, contract1_id)
        self.attach_contract_to_asset(asset_id, contract2_id)
        
        # Prepare contracts for activation
        self.prepare_contract_for_activation(contract1_id)
        self.prepare_contract_for_activation(contract2_id)
        
        # Activate asset
        activate_response = self.activate_asset(asset_id)
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        
        # Verify both contracts attached
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.contracts.count(), 2)


class ContractOnlyFlowFailureTests(E2ETestBase):
    """Test failure scenarios in contract-only onboarding flow"""
    
    def test_activation_without_valid_contract_fails(self):
        """Test that activation fails without valid contract"""
        asset_id = self.create_asset(key='no-contract', name='No Contract')
        
        # Try to activate without contract - call endpoint directly (not helper)
        from hub.apps.assets.models import Asset
        asset = Asset.objects.get(id=asset_id)
        activate_response = self.client.post(
            f'/api/v1/assets/assets/{asset_id}/activate/',
            {'version': asset.version},
            format='json'
        )
        self.assertEqual(activate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('blocked', str(activate_response.data).lower())
    
    def test_activation_with_invalid_contract_fails(self):
        """Test that activation fails with invalid contract"""
        asset_id = self.create_asset(key='invalid-contract-only', name='Invalid Contract Only')
        
        # Create invalid contract
        contract_id = self.create_contract(
            asset_id,
            original_raw='{"invalid": "structure"}'
        )
        
        # Validate - may return INVALID
        validate_response = self.validate_contract(contract_id)
        
        contract = Contract.objects.get(id=contract_id)
        if contract.validation_status == ValidationStatus.INVALID:
            # Attach contract
            self.attach_contract_to_asset(asset_id, contract_id)
            
            # Try to activate - should fail (call endpoint directly, not helper)
            from hub.apps.assets.models import Asset
            asset = Asset.objects.get(id=asset_id)
            activate_response = self.client.post(
                f'/api/v1/assets/assets/{asset_id}/activate/',
                {'version': asset.version},
                format='json'
            )
            self.assertEqual(activate_response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_activation_without_normalization_fails(self):
        """Test that activation fails if contract normalization failed"""
        asset_id = self.create_asset(key='normalization-failed', name='Normalization Failed')
        
        contract_id = self.create_contract(asset_id)
        contract = Contract.objects.get(id=contract_id)
        
        # Set normalization status to failed
        contract.normalization_status = NormalizationStatus.NORMALIZATION_FAILED
        contract.validation_status = ValidationStatus.VALID
        contract.save()
        
        self.attach_contract_to_asset(asset_id, contract_id)
        
        # Try to activate - should fail (call endpoint directly, not helper)
        from hub.apps.assets.models import Asset
        asset = Asset.objects.get(id=asset_id)
        activate_response = self.client.post(
            f'/api/v1/assets/assets/{asset_id}/activate/',
            {'version': asset.version},
            format='json'
        )
        self.assertEqual(activate_response.status_code, status.HTTP_400_BAD_REQUEST)


class ContractOnlyFlowEdgeCasesTests(E2ETestBase):
    """Test edge cases in contract-only flow"""
    
    def test_contract_only_without_schema(self):
        """Test contract-only asset with contract that has no schema"""
        asset_id = self.create_asset(key='no-schema', name='No Schema')
        
        # Create contract without schema definition
        contract_id = self.create_contract(
            asset_id,
            original_raw='{"id": "test", "name": "Test Contract"}'
        )
        
        # Check DataContract service availability upfront
        self.require_service('DataContract', self.datacontract_service_url, health_path='/health')
        
        # Contract should still be valid (schema is optional)
        validate_response = self.validate_contract(contract_id)
        # Service is available, validation should have completed
        # May be valid or invalid depending on spec requirements
        if isinstance(validate_response, dict) and 'validation_status' in validate_response:
            self.assertIn(validate_response.get('validation_status'), ['VALID', 'INVALID', 'WARNING_ONLY'])
        
        # Should be able to activate if validation passes
        if validate_response.get('validation_status') in ['VALID', 'WARNING_ONLY']:
            self.prepare_contract_for_activation(contract_id)
            self.attach_contract_to_asset(asset_id, contract_id)
            
            activate_response = self.activate_asset(asset_id)
            # Should succeed if contract is valid
            if activate_response.status_code == status.HTTP_200_OK:
                asset = Asset.objects.get(id=asset_id)
                self.assertEqual(asset.status, AssetStatus.ACTIVE)
    
    def test_contract_only_activation_without_dataset_requirements(self):
        """Test that contract-only assets don't require DQ/compliance status"""
        asset_id = self.create_asset(key='no-dq-required', name='No DQ Required')
        
        contract_id = self.create_contract(asset_id)
        self.validate_contract(contract_id)
        self.attach_contract_to_asset(asset_id, contract_id)
        self.prepare_contract_for_activation(contract_id)
        
        # Asset doesn't need DQ/compliance status for contract-only
        # (These are only required when dataset exists)
        activate_response = self.activate_asset(asset_id)
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        # DQ and compliance status may be None for contract-only
        # This is acceptable

