"""
Tests for Enhanced Contract Views with Filtering and Sorting (GAP-9.2.2).

Tests:
- Filtering works (by owners, tags, quality profile, compliance regime)
- Sorting works (by quality score, compliance risk, creation date, update date)
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from hub.apps.contracts.models import Contract, OriginalSpecType, OriginalFormat, ContractStatus, NormalizationStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ContractViewFilteringTest(TestCase):
    """Test contract view filtering (GAP-9.2.2)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        # CRITICAL: Refresh user from DB to ensure tenant_id is loaded
        # This is important for test isolation and ensures tenant_id is available in get_queryset
        self.user.refresh_from_db()
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create contracts with different owners
        self.contract1 = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="2.2.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "2.2.2", "name": "test1"}',
            status=ContractStatus.DRAFT,
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {
                    "name": "Contract 1",
                    "owners": [
                        {"name": "John Doe", "email": "john@example.com"}
                    ],
                    "tags": ["analytics", "sales"]
                },
                "schema": {"fields": []},
                "quality": {
                    "default_profile_key": "profile1"
                },
                "privacy_compliance": {
                    "jurisdictions": ["GDPR"]
                }
            }
        )
        
        self.contract2 = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="2.2.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "2.2.2", "name": "test2"}',
            status=ContractStatus.DRAFT,
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {
                    "name": "Contract 2",
                    "owners": [
                        {"name": "Jane Smith", "email": "jane@example.com"}
                    ],
                    "tags": ["marketing", "analytics"]
                },
                "schema": {"fields": []},
                "quality": {
                    "default_profile_key": "profile2"
                },
                "privacy_compliance": {
                    "jurisdictions": ["CCPA"]
                }
            }
        )
    
    def test_list_contracts_without_filter(self):
        """Test listing contracts without filter (should return all tenant contracts)"""
        # First, verify contracts exist in the database
        from hub.apps.contracts.models import Contract
        all_contracts = Contract.objects.filter(tenant_id=self.tenant.id)
        self.assertEqual(all_contracts.count(), 2, f"Expected 2 contracts in DB, got {all_contracts.count()}")
        
        # Verify user has tenant_id
        self.assertIsNotNone(self.user.tenant_id, "User should have tenant_id")
        self.assertEqual(self.user.tenant_id, self.tenant.id, "User tenant_id should match tenant id")
        
        # Now test the API
        response = self.client.get('/api/v1/contracts/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should return both contracts (both belong to the tenant)
        self.assertEqual(len(results), 2, f"Expected 2 contracts, got {len(results)}. Results: {[r.get('id') for r in results]}")
    
    def test_filter_by_owner_email(self):
        """Test filtering contracts by owner email (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/', {'owner_email': 'john@example.com'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should return contract1
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], str(self.contract1.id))
    
    def test_filter_by_owner_name(self):
        """Test filtering contracts by owner name (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/', {'owner_name': 'John Doe'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should return contract1
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], str(self.contract1.id))
    
    def test_filter_by_tag(self):
        """Test filtering contracts by tag (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/', {'tag': 'analytics'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should return both contracts (both have 'analytics' tag)
        self.assertEqual(len(results), 2)
    
    def test_filter_by_multiple_tags(self):
        """Test filtering contracts by multiple tags (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/', {'tag': ['analytics', 'sales']})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should return contract1 (has both tags)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], str(self.contract1.id))
    
    def test_filter_by_quality_profile(self):
        """Test filtering contracts by quality profile (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/', {'quality_profile': 'profile1'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should return contract1
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], str(self.contract1.id))
    
    def test_filter_by_compliance_regime(self):
        """Test filtering contracts by compliance regime (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/', {'compliance_regime': 'GDPR'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should return contract1
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], str(self.contract1.id))
    
    def test_filter_combination(self):
        """Test filtering with multiple criteria (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/', {
            'tag': 'analytics',
            'compliance_regime': 'GDPR'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should return contract1 (has both analytics tag and GDPR)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], str(self.contract1.id))


class ContractViewSortingTest(TestCase):
    """Test contract view sorting (GAP-9.2.2)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        # CRITICAL: Refresh user from DB to ensure tenant_id is loaded
        # This is important for test isolation and ensures tenant_id is available in get_queryset
        self.user.refresh_from_db()
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create contracts with different normalization statuses (affects quality_score)
        from django.utils import timezone
        import datetime
        
        self.contract1 = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="2.2.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "2.2.2", "name": "test1"}',
            status=ContractStatus.DRAFT,
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={
                "info": {"name": "Contract 1"},
                "schema": {"fields": []},
                "privacy_compliance": {
                    "contains_personal_data": False
                }
            },
            created_at=timezone.now() - datetime.timedelta(days=2)
        )
        
        self.contract2 = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="2.2.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "2.2.2", "name": "test2"}',
            status=ContractStatus.DRAFT,
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            hub_contract_json={
                "info": {"name": "Contract 2"},
                "schema": {"fields": []},
                "privacy_compliance": {
                    "contains_personal_data": True
                }
            },
            created_at=timezone.now() - datetime.timedelta(days=1)
        )
        
        self.contract3 = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="2.2.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "2.2.2", "name": "test3"}',
            status=ContractStatus.DRAFT,
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZATION_FAILED,
            hub_contract_json={
                "info": {"name": "Contract 3"},
                "schema": {"fields": []},
                "privacy_compliance": {
                    "contains_personal_data": True
                }
            },
            created_at=timezone.now()
        )
    
    def test_sort_by_created_at_ascending(self):
        """Test sorting contracts by creation date ascending (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/', {'ordering': 'created_at'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should be sorted by created_at ascending (oldest first)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['id'], str(self.contract1.id))
        self.assertEqual(results[1]['id'], str(self.contract2.id))
        self.assertEqual(results[2]['id'], str(self.contract3.id))
    
    def test_sort_by_created_at_descending(self):
        """Test sorting contracts by creation date descending (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/', {'ordering': '-created_at'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should be sorted by created_at descending (newest first)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['id'], str(self.contract3.id))
        self.assertEqual(results[1]['id'], str(self.contract2.id))
        self.assertEqual(results[2]['id'], str(self.contract1.id))
    
    def test_sort_by_quality_score(self):
        """Test sorting contracts by quality score (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/', {'ordering': '-quality_score'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should be sorted by quality score descending (highest first)
        # contract1: NORMALIZED_OK = 100
        # contract2: NORMALIZED_WITH_WARNINGS = 75
        # contract3: NORMALIZATION_FAILED = 0
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['id'], str(self.contract1.id))
        self.assertEqual(results[1]['id'], str(self.contract2.id))
        self.assertEqual(results[2]['id'], str(self.contract3.id))
    
    def test_sort_by_compliance_risk(self):
        """Test sorting contracts by compliance risk (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/', {'ordering': '-compliance_risk'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should be sorted by compliance risk descending (highest first)
        # contract2 and contract3: contains_personal_data = True = 100
        # contract1: contains_personal_data = False = 0
        self.assertEqual(len(results), 3)
        # contract2 and contract3 should come first (both have personal data)
        self.assertIn(results[0]['id'], [str(self.contract2.id), str(self.contract3.id)])
        self.assertIn(results[1]['id'], [str(self.contract2.id), str(self.contract3.id)])
        self.assertEqual(results[2]['id'], str(self.contract1.id))
    
    def test_sort_by_multiple_fields(self):
        """Test sorting contracts by multiple fields (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/', {'ordering': '-compliance_risk,-created_at'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Should be sorted by compliance_risk first, then created_at
        self.assertEqual(len(results), 3)
        # contract2 and contract3 should come first (both have personal data)
        # Then sorted by created_at descending (newest first)
        self.assertIn(results[0]['id'], [str(self.contract2.id), str(self.contract3.id)])
        self.assertIn(results[1]['id'], [str(self.contract2.id), str(self.contract3.id)])
        self.assertEqual(results[2]['id'], str(self.contract1.id))
    
    def test_default_sorting(self):
        """Test default sorting (newest first) (GAP-9.2.2)"""
        response = self.client.get('/api/v1/contracts/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        
        # Default should be -created_at (newest first)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['id'], str(self.contract3.id))
        self.assertEqual(results[1]['id'], str(self.contract2.id))
        self.assertEqual(results[2]['id'], str(self.contract1.id))

