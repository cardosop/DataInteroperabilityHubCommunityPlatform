"""
Unit tests for LineageService.

Tests cover all service methods with 100% coverage target.
"""
import pytest
from django.test import TestCase
from unittest.mock import patch, Mock

from hub.apps.contracts.lineage_service import LineageService
from hub.apps.contracts.models import Contract
from hub.apps.core.services.base import NotFoundError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class LineageServiceTest(TestCase):
    """Test LineageService operations"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.service = LineageService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        
        # Create contract with lineage
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            hub_contract_json={
                "info": {"name": "test-contract"},
                "lineage": {
                    "contracts": [{"namespace": "ns1", "name": "source"}],
                    "entries": []
                },
                "models": [
                    {
                        "name": "test-model",
                        "lineage": {
                            "models": [],
                            "entries": []
                        },
                        "fields": [
                            {
                                "name": "test-field",
                                "lineage": {
                                    "input_fields": [],
                                    "transformations": []
                                }
                            }
                        ]
                    }
                ]
            }
        )
    
    def test_get_contract_lineage_success(self):
        """Test successful contract-level lineage retrieval"""
        lineage = self.service.get_contract_lineage(
            contract_id=str(self.contract.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertIn("contracts", lineage)
        self.assertIn("entries", lineage)
    
    def test_get_model_lineage_success(self):
        """Test successful model-level lineage retrieval"""
        lineage = self.service.get_model_lineage(
            contract_id=str(self.contract.id),
            model_name="test-model",
            tenant_id=str(self.tenant.id)
        )
        
        self.assertIn("model_name", lineage)
        self.assertIn("lineage", lineage)
    
    def test_get_model_lineage_not_found(self):
        """Test model lineage retrieval with non-existent model"""
        with self.assertRaises(NotFoundError):
            self.service.get_model_lineage(
                contract_id=str(self.contract.id),
                model_name="non-existent-model",
                tenant_id=str(self.tenant.id)
            )
    
    def test_get_field_lineage_success(self):
        """Test successful field-level lineage retrieval"""
        lineage = self.service.get_field_lineage(
            contract_id=str(self.contract.id),
            field_name="test-field",
            model_name="test-model",
            tenant_id=str(self.tenant.id)
        )
        
        self.assertIn("field_name", lineage)
        self.assertIn("lineage", lineage)
    
    def test_get_full_lineage_success(self):
        """Test successful full lineage retrieval"""
        with patch('hub.apps.contracts.lineage_service.LineageTraverser') as mock_traverser:
            mock_instance = Mock()
            mock_traverser.return_value = mock_instance
            mock_instance.traverse_upstream.return_value = {}
            mock_instance.traverse_downstream.return_value = {}
            
            lineage = self.service.get_full_lineage(
                contract_id=str(self.contract.id),
                tenant_id=str(self.tenant.id)
            )
            
            self.assertIn("upstream", lineage)
            self.assertIn("downstream", lineage)
    
    def test_get_lineage_visualization_success(self):
        """Test successful lineage visualization"""
        with patch('hub.apps.contracts.lineage_service.generate_lineage_json') as mock_gen:
            mock_gen.return_value = {"nodes": [], "edges": []}
            
            visualization = self.service.get_lineage_visualization(
                contract_id=str(self.contract.id),
                format="json",
                tenant_id=str(self.tenant.id)
            )
            
            self.assertIn("nodes", visualization)

