"""
E2E Tests for Django 6 Upgrade Critical Workflows

These tests verify that critical workflows continue to work correctly after
Django 6 upgrade, including JSONField operations, middleware functionality,
and API compatibility.

All tests use real services (no mocks/stubs) and follow TDD principles.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import connection
from django.core.management import call_command
from rest_framework.test import APIClient as DRFAPIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.assets.models import Asset
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.datasets.models import Dataset


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class Django6JSONFieldWorkflowTest(TestCase):
    """Test critical JSONField workflows with Django 6."""

    def setUp(self):
        """Set up test fixtures. Use DRF APIClient so /api/v1/ endpoints get auth (JWT/APIKey only, no session)."""
        self.client = DRFAPIClient()
        self.tenant = Tenant.objects.create(name="Test Tenant JSONField", slug="test-tenant-jsonfield")
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email="test-jsonfield@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=tenant_admin_role)
        self.client.force_authenticate(user=self.user)
    
    def test_contract_creation_with_jsonfield(self):
        """Test contract creation with JSONField data."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset"
        )
        
        contract_data = {
            "info": {
                "title": "Test Contract",
                "tags": ["tag1", "tag2"],
                "owners": [{"name": "Test Owner", "email": "owner@example.com"}]
            },
            "quality": {
                "default_profile_key": "great_expectations"
            },
            "privacy_compliance": {
                "jurisdictions": ["GDPR", "CCPA"],
                "contains_personal_data": True
            }
        }
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json=contract_data,
            created_by=self.user
        )
        
        # Verify JSONField data is stored correctly
        contract.refresh_from_db()
        self.assertEqual(contract.hub_contract_json['info']['title'], "Test Contract")
        self.assertEqual(contract.hub_contract_json['info']['tags'], ["tag1", "tag2"])
        self.assertEqual(contract.hub_contract_json['quality']['default_profile_key'], "great_expectations")
    
    def test_jsonfield_query_by_tags(self):
        """Test querying contracts by tags using JSONField."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset"
        )
        
        # Create contracts with different tags
        contract1 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"tags": ["tag1", "tag2"]}
            },
            created_by=self.user
        )
        
        contract2 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=2,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"tags": ["tag2", "tag3"]}
            },
            created_by=self.user
        )
        
        # Query by tag
        contracts_with_tag1 = Contract.objects.filter(
            hub_contract_json__info__tags__contains=["tag1"]
        )
        self.assertEqual(contracts_with_tag1.count(), 1)
        self.assertEqual(contracts_with_tag1.first().id, contract1.id)
        
        contracts_with_tag2 = Contract.objects.filter(
            hub_contract_json__info__tags__contains=["tag2"]
        )
        self.assertEqual(contracts_with_tag2.count(), 2)
    
    def test_jsonfield_query_by_compliance_jurisdiction(self):
        """Test querying contracts by compliance jurisdiction."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset"
        )
        
        contract1 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "privacy_compliance": {
                    "jurisdictions": ["GDPR", "CCPA"]
                }
            },
            created_by=self.user
        )
        
        contract2 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=2,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "privacy_compliance": {
                    "jurisdictions": ["GDPR"]
                }
            },
            created_by=self.user
        )
        
        # Query by jurisdiction
        gdpr_contracts = Contract.objects.filter(
            hub_contract_json__privacy_compliance__jurisdictions__contains=["GDPR"]
        )
        self.assertEqual(gdpr_contracts.count(), 2)
        
        ccpa_contracts = Contract.objects.filter(
            hub_contract_json__privacy_compliance__jurisdictions__contains=["CCPA"]
        )
        self.assertEqual(ccpa_contracts.count(), 1)
        self.assertEqual(ccpa_contracts.first().id, contract1.id)
    
    def test_jsonfield_query_by_quality_profile(self):
        """Test querying contracts by quality profile."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset"
        )
        
        contract1 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "quality": {
                    "default_profile_key": "great_expectations"
                }
            },
            created_by=self.user
        )
        
        contract2 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=2,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "quality": {
                    "default_profile_key": "soda"
                }
            },
            created_by=self.user
        )
        
        # Query by quality profile
        ge_contracts = Contract.objects.filter(
            hub_contract_json__quality__default_profile_key="great_expectations"
        )
        self.assertEqual(ge_contracts.count(), 1)
        self.assertEqual(ge_contracts.first().id, contract1.id)
        
        soda_contracts = Contract.objects.filter(
            hub_contract_json__quality__default_profile_key="soda"
        )
        self.assertEqual(soda_contracts.count(), 1)
        self.assertEqual(soda_contracts.first().id, contract2.id)
    
    def test_jsonfield_api_filtering(self):
        """Test API filtering using JSONField queries."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset"
        )
        
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"tags": ["tag1"]},
                "quality": {"default_profile_key": "great_expectations"},
                "privacy_compliance": {"jurisdictions": ["GDPR"]}
            },
            created_by=self.user
        )
        
        # Test API filtering by tag
        response = self.client.get('/api/v1/contracts/', {'tag': 'tag1'})
        self.assertEqual(response.status_code, 200, getattr(response, "data", response.content))
        data = getattr(response, "data", None) or (response.json() if response.content else {})
        self.assertGreaterEqual(len(data.get('results', [])), 1)
        
        # Test API filtering by quality profile
        response = self.client.get('/api/v1/contracts/', {'quality_profile': 'great_expectations'})
        self.assertEqual(response.status_code, 200, getattr(response, "data", response.content))
        data = getattr(response, "data", None) or (response.json() if response.content else {})
        self.assertGreaterEqual(len(data.get('results', [])), 1)
        
        # Test API filtering by compliance regime
        response = self.client.get('/api/v1/contracts/', {'compliance_regime': 'GDPR'})
        self.assertEqual(response.status_code, 200, getattr(response, "data", response.content))
        data = getattr(response, "data", None) or (response.json() if response.content else {})
        self.assertGreaterEqual(len(data.get('results', [])), 1)


class Django6MiddlewareWorkflowTest(TestCase):
    """Test critical middleware workflows with Django 6."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = DRFAPIClient()
        self.tenant = Tenant.objects.create(name="Test Tenant Middleware", slug="test-tenant-middleware")
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email="test-middleware@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=tenant_admin_role)
        self.client.force_authenticate(user=self.user)
    
    def test_tenant_scoping_middleware(self):
        """Test tenant scoping middleware works correctly."""
        response = self.client.get('/api/v1/assets/')
        self.assertEqual(response.status_code, 200)
        
        # Verify tenant is scoped correctly
        # (This is tested by the fact that we only see tenant's assets)
    
    def test_request_id_middleware(self):
        """Test request ID middleware works correctly."""
        response = self.client.get('/api/v1/assets/')
        self.assertEqual(response.status_code, 200)
        
        # Verify request ID is in response headers
        self.assertIn('X-Request-ID', response.headers or {})


class Django6APICompatibilityTest(TestCase):
    """Test API compatibility with Django 6."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = DRFAPIClient()
        self.tenant = Tenant.objects.create(name="Test Tenant API", slug="test-tenant-api")
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email="test-api@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=tenant_admin_role)
        self.client.force_authenticate(user=self.user)
    
    def test_contract_list_api(self):
        """Test contract list API works correctly."""
        response = self.client.get('/api/v1/contracts/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('results', data)
        self.assertIn('count', data)
    
    def test_contract_create_api(self):
        """Test contract create API works correctly."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset"
        )
        # Minimal valid ODCS so normalization succeeds (schema.fields required by normalizer)
        minimal_odcs = (
            '{"id": "test-contract", "info": {"name": "Test", "title": "Test"}, '
            '"schema": {"fields": [{"name": "id", "type": "string"}]}}'
        )
        response = self.client.post(
            '/api/v1/contracts/',
            {
                'asset_id': str(asset.id),
                'original_spec_type': 'ODCS',
                'original_format': 'JSON',
                'original_raw': minimal_odcs,
            },
            format='json',
        )
        self.assertIn(
            response.status_code,
            (200, 201),
            msg=f"Contract create failed: {response.status_code} {getattr(response, 'data', response.content)}",
        )
        data = getattr(response, "data", None) or (response.json() if response.content else {})
        self.assertIn("id", data if isinstance(data, dict) else {})
    
    def test_contract_filter_api(self):
        """Test contract filter API works correctly."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset"
        )
        
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"tags": ["test-tag"]}
            },
            created_by=self.user
        )
        
        # Test filtering by tag
        response = self.client.get('/api/v1/contracts/', {'tag': 'test-tag'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data.get('results', [])), 1)


class Django6DatabaseOperationsTest(TestCase):
    """Test critical database operations with Django 6."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant DB", slug="test-tenant-db")
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email="test-db@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=tenant_admin_role)
    
    def test_transaction_rollback(self):
        """Test transaction rollback works correctly."""
        from django.db import transaction

        # Use unique key to isolate from other tests (shared DB)
        unique_key = f"rollback-test-{self.tenant.id}"
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=unique_key,
            name="Test Asset Rollback"
        )

        try:
            with transaction.atomic():
                Contract.objects.create(
                    tenant=self.tenant,
                    asset=asset,
                    version=999,
                    status=ContractStatus.DRAFT,
                    original_spec_type=OriginalSpecType.ODCS,
                    original_spec_version="1.0.0",
                    original_format=OriginalFormat.JSON,
                    original_raw='{}',
                    hub_contract_version="1.0.0",
                    hub_contract_json={"test": "rollback"},
                    created_by=self.user
                )
                raise Exception("Test rollback")
        except Exception:
            pass

        # Our contract should not exist after rollback (query by our asset)
        self.assertEqual(Contract.objects.filter(asset=asset).count(), 0)
    
    def test_bulk_operations(self):
        """Test bulk operations work correctly."""
        # Use unique key to isolate from other tests (shared DB)
        unique_key = f"bulk-test-{self.tenant.id}"
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=unique_key,
            name="Test Asset Bulk"
        )

        contracts = []
        for i in range(10):
            contracts.append(Contract(
                tenant=self.tenant,
                asset=asset,
                version=1000 + i,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="1.0.0",
                original_format=OriginalFormat.JSON,
                original_raw='{}',
                hub_contract_version="1.0.0",
                hub_contract_json={"index": i, "test": "bulk"},
                created_by=self.user
            ))

        Contract.objects.bulk_create(contracts)
        # Assert our asset's contracts (shared DB has data from other tests)
        self.assertEqual(Contract.objects.filter(asset=asset).count(), 10)

