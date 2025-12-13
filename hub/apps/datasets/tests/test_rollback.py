"""
Unit tests for Version Rollback Automation

Tests for automated rollback functionality.
"""
import pytest
from django.test import TestCase
from django.db import transaction

from hub.apps.datasets.models import Dataset
from hub.apps.datasets.rollback import (
    VersionRollbackManager,
    RollbackConfig,
    RollbackTrigger
)
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class VersionRollbackManagerTest(TestCase):
    """Test VersionRollbackManager"""
    
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
    
    def test_check_rollback_conditions_no_failures(self):
        """Test rollback check with no failures"""
        # Create dataset
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
        
        # Create successful DQ run
        job = Job.objects.create(
            tenant=self.tenant,
            job_type=JobType.DQ_CHECK,
            status=JobStatus.COMPLETED,
            created_by=self.user
        )
        
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.0
        )
        
        # Check rollback conditions
        config = RollbackConfig(
            enable_auto_rollback=True,
            quality_threshold=0.8
        )
        result = VersionRollbackManager.check_rollback_conditions(dataset, config)
        
        self.assertFalse(result["should_rollback"])
        self.assertEqual(len(result["triggers"]), 0)
    
    def test_check_rollback_conditions_quality_failure(self):
        """Test rollback check with quality failure"""
        # Create parent version
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(parent, is_current=False)
        
        # Create child version
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
        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)
        
        # Create failed DQ run
        job = Job.objects.create(
            tenant=self.tenant,
            job_type=JobType.DQ_CHECK,
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
            quality_score=50.0  # Below threshold
        )
        
        # Check rollback conditions
        config = RollbackConfig(
            enable_auto_rollback=True,
            quality_threshold=0.8,
            rollback_on_quality_failure=True
        )
        result = VersionRollbackManager.check_rollback_conditions(child, config)
        
        self.assertTrue(result["should_rollback"])
        self.assertGreater(len(result["triggers"]), 0)
        self.assertEqual(result["triggers"][0]["type"], RollbackTrigger.QUALITY_FAILURE.value)
    
    def test_execute_rollback(self):
        """Test executing rollback"""
        # Create parent version
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
        
        # Create child version
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
        
        # Execute rollback
        config = RollbackConfig(require_approval=False)
        result = VersionRollbackManager.execute_rollback(
            child,
            approved_by=self.user,
            reason="Quality failure",
            config=config
        )
        
        self.assertTrue(result["success"])
        self.assertEqual(result["rolled_back_to"]["semantic_version"], "1.0.0")
        
        # Verify parent is now current
        parent.refresh_from_db()
        child.refresh_from_db()
        self.assertTrue(parent.is_current)
        self.assertFalse(child.is_current)
    
    def test_execute_rollback_requires_approval(self):
        """Test rollback with approval requirement"""
        # Create versions
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(parent, is_current=False)
        
        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user
        )
        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)
        
        # Try rollback without approval
        config = RollbackConfig(require_approval=True)
        result = VersionRollbackManager.execute_rollback(
            child,
            approved_by=None,  # No approver
            reason="Test",
            config=config
        )
        
        self.assertFalse(result["success"])
        self.assertIn("Approval required", result["error"])

