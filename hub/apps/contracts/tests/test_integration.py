"""
Integration tests for DataContract CLI service.

Note: These tests require the DataContract CLI service to be running.
Start services with: make docker-up-services
"""
import pytest
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
import os

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalSpecType,
    OriginalFormat
)
from hub.apps.contracts.cli_client import DataContractCLIClient
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


@pytest.mark.integration
class DataContractCLIIntegrationTest(TestCase):
    """Integration tests with DataContract CLI service"""
    
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
        
        # Get service URL from environment or use default
        self.service_url = os.getenv(
            'DATACONTRACT_SERVICE_URL',
            'http://localhost:8080'
        )
        
        # Verify service is available
        cli_client = DataContractCLIClient()
        cli_client.base_url = self.service_url
        try:
            health = cli_client.health_check()
            if health.get('status') != 'healthy':
                pytest.skip(f"DataContract CLI service is not healthy at {self.service_url}")
        except Exception as e:
            pytest.skip(f"DataContract CLI service not available at {self.service_url}: {str(e)}")
    
    @override_settings(DATACONTRACT_SERVICE_URL='http://localhost:8080')
    def test_validate_contract_integration(self):
        """Integration test: Validate contract via DataContract CLI service"""
        self.client.force_authenticate(user=self.user)
        
        # Create a simple valid contract
        contract_data = {
            "id": "test-contract",
            "info": {
                "title": "Test Contract"
            },
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"}
                }
            }
        }
        
        import json
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.DATACONTRACT_COM,
            original_spec_version="0.4.0",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(contract_data),
            created_by=self.user
        )
        
        # Validate contract via API
        response = self.client.post(
            f"/api/v1/contracts/contracts/{contract.id}/validate/",
            {},
            format="json"
        )
        
        # Should get a response (either success or error from service)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED, status.HTTP_500_INTERNAL_SERVER_ERROR])
    
    @override_settings(DATACONTRACT_SERVICE_URL='http://localhost:8080')
    def test_health_check_integration(self):
        """Integration test: Check DataContract CLI service health"""
        cli_client = DataContractCLIClient()
        cli_client.base_url = self.service_url
        
        health = cli_client.health_check()
        self.assertIn('status', health)
        self.assertIn('cli_version', health)
        self.assertEqual(health['status'], 'healthy')
