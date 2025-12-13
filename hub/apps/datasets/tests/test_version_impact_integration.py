"""
Integration tests for Version Impact Analysis

Tests for impact analysis in the context of complete workflows.
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.datasets.models import Dataset
from hub.apps.datasets.version_impact import VersionImpactAnalyzer
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class VersionImpactIntegrationTest(TestCase):
    """Integration tests for version impact analysis"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user
        )
    
    def test_version_impact_analysis_workflow(self):
        """Test complete version impact analysis workflow"""
        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"apiVersion": "v3", "kind": "DataContract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"info": {"name": "Test Contract"}},
            created_by=self.user
        )
        
        # Create dataset version
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(dataset, is_current=True)
        
        # Analyze impact
        analyzer = VersionImpactAnalyzer()
        result = analyzer.analyze_impact(str(dataset.id))
        
        # Verify impact analysis
        self.assertIn("source", result)
        self.assertIn("impact_graph", result)
        self.assertIn("summary", result)
        self.assertGreater(result["summary"]["total_assets"], 0)
        self.assertGreater(result["summary"]["total_contracts"], 0)

