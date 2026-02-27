"""
E2E tests for Version Impact Analysis and Rollback Automation

End-to-end tests for complete workflows including impact analysis and rollback.
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.datasets.models import Dataset
from hub.apps.datasets.version_impact import VersionImpactAnalyzer
from hub.apps.datasets.rollback import VersionRollbackManager, RollbackConfig
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.files.models import File, FileStatus

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class VersionImpactE2ETest(TestCase):
    """E2E tests for version impact analysis"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.tenant = Tenant.objects.create(
            name="Test Tenant Impact",
            slug="test-tenant-impact",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email="user-impact@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client = APIClient()
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
    
    def test_complete_impact_analysis_workflow(self):
        """
        Test complete version impact analysis workflow:
        1. Create dataset version
        2. Create contract for asset
        3. Analyze impact
        4. Verify impact on assets and contracts
        """
        # Step 1: Create contract
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
        
        # Step 2: Create dataset version
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
        
        # Step 3: Analyze impact
        analyzer = VersionImpactAnalyzer()
        result = analyzer.analyze_impact(str(dataset.id))
        
        # Step 4: Verify impact
        self.assertIn("source", result)
        self.assertIn("impact_graph", result)
        self.assertIn("summary", result)
        self.assertGreater(result["summary"]["total_assets"], 0)
        self.assertGreater(result["summary"]["total_contracts"], 0)
        self.assertGreater(result["total_affected"], 0)


class VersionRollbackE2ETest(TestCase):
    """E2E tests for version rollback automation"""
    
    def setUp(self):
        """Set up test fixtures"""
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
        self.client = APIClient()
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
    
    def test_complete_rollback_workflow(self):
        """
        Test complete rollback workflow:
        1. Create parent version
        2. Create child version
        3. Create failed DQ run
        4. Check rollback conditions
        5. Execute rollback
        6. Verify rollback success
        """
        # Step 1: Create parent version
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(parent, semantic_version="1.0.0", is_current=False)
        
        # Step 2: Create child version
        file2 = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            content_sha256="def456",
            created_by=self.user
        )
        
        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user
        )
        VersionHistoryManager.create_version(child, parent_version=parent, semantic_version="1.1.0", is_current=True)
        
        # Step 3: Create failed DQ run
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=child.id,
            status=JobStatus.COMPLETED,
            created_by=self.user
        )
        
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=child,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="FAIL",
            quality_score=50.0
        )
        
        # Step 4: Check rollback conditions
        config = RollbackConfig(
            enable_auto_rollback=True,
            quality_threshold=0.8,
            rollback_on_quality_failure=True,
            require_approval=False
        )
        rollback_check = VersionRollbackManager.check_rollback_conditions(child, config)
        
        self.assertTrue(rollback_check["should_rollback"])
        self.assertGreater(len(rollback_check["triggers"]), 0)
        
        # Step 5: Execute rollback
        result = VersionRollbackManager.execute_rollback(
            child,
            approved_by=self.user,
            reason="Quality failure detected",
            config=config
        )
        
        # Step 6: Verify rollback success
        self.assertTrue(result["success"])
        self.assertEqual(result["rolled_back_to"]["semantic_version"], "1.0.0")
        
        # Verify parent is now current
        parent.refresh_from_db()
        child.refresh_from_db()
        self.assertTrue(parent.is_current)
        self.assertFalse(child.is_current)

