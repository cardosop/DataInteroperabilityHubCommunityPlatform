"""
Unit tests for Version Rollback Automation

Tests for automated rollback functionality.
"""

import pytest

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.rollback import RollbackConfig, RollbackTrigger, VersionRollbackManager
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType

pytestmark = pytest.mark.django_db(transaction=True)


class VersionRollbackManagerTest(DatasetsTestBase):
    """Test VersionRollbackManager"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
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
            created_by=self.user,
        )
        VersionHistoryManager.create_version(dataset, is_current=True)

        # Create successful DQ run
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=dataset.id,
            created_by=self.user,
        )

        DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.0,
        )

        # Check rollback conditions
        config = RollbackConfig(enable_auto_rollback=True, quality_threshold=0.8)
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
            created_by=self.user,
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
            created_by=self.user,
        )

        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)

        # Create failed DQ run (Job uses type, resource_type, resource_id)
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=child.id,
            created_by=self.user,
        )

        DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=child,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="FAIL",
            quality_score=50.0,  # Below threshold
        )

        # Check rollback conditions
        config = RollbackConfig(
            enable_auto_rollback=True, quality_threshold=0.8, rollback_on_quality_failure=True
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
            created_by=self.user,
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
            created_by=self.user,
        )

        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            child, parent_version=parent, semantic_version="1.1.0", is_current=True
        )

        # Execute rollback
        config = RollbackConfig(require_approval=False)
        result = VersionRollbackManager.execute_rollback(
            child, approved_by=self.user, reason="Quality failure", config=config
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
            created_by=self.user,
        )
        VersionHistoryManager.create_version(parent, is_current=False)

        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(child, parent_version=parent, is_current=True)

        # Try rollback without approval
        config = RollbackConfig(require_approval=True)
        result = VersionRollbackManager.execute_rollback(
            child,
            approved_by=None,
            reason="Test",
            config=config,  # No approver
        )

        self.assertFalse(result["success"])
        self.assertIn("Approval required", result["error"])

    # ========== SUCCESS SCENARIOS ==========

    def test_rollback_success(self):
        """Test successful rollback to previous version"""
        # Create v1
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            is_current=False,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v1, is_current=False)

        # Create v2 (current)
        file2 = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            created_by=self.user,
        )
        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={"fields": [{"name": "col2", "type": "integer"}]},
            format="CSV",
            version=2,
            is_current=True,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=True)

        # Rollback to v1 using execute_rollback (API: dataset, approved_by, reason, config)
        config = RollbackConfig(require_approval=False, enable_auto_rollback=True)
        result = VersionRollbackManager.execute_rollback(
            v2, approved_by=self.user, reason="Rollback test", config=config
        )
        self.assertTrue(result.get("success"), result.get("error"))
        self.assertIsNotNone(result.get("rolled_back_to"))

    # ========== EDGE CASES ==========

    def test_rollback_no_parent_version_returns_failure(self):
        """Rollback fails when the dataset has no parent version."""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            is_current=True,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(dataset, is_current=True)

        # Rollback to same version: no parent_version, so execute_rollback returns success=False
        config = RollbackConfig(require_approval=False)
        result = VersionRollbackManager.execute_rollback(
            dataset, approved_by=self.user, reason="Same version", config=config
        )
        self.assertFalse(result.get("success"))
        error_msg = result.get("error", "")
        self.assertTrue(
            "No rollback conditions met" in error_msg or "No parent version" in error_msg,
            f"Expected rollback error message, got: {error_msg!r}",
        )

    def test_rollback_to_nonexistent_version(self):
        """Test rollback to non-existent version (edge case)"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            is_current=True,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(dataset, is_current=True)

        # Only one version exists (no parent); execute_rollback returns success=False
        config = RollbackConfig(require_approval=False)
        result = VersionRollbackManager.execute_rollback(
            dataset, approved_by=self.user, reason="Test", config=config
        )
        self.assertFalse(result.get("success"))
        self.assertIn("No parent version", result.get("error", ""))

    # ========== ERROR HANDLING ==========

    def test_execute_rollback_no_parent_version_returns_failure(self):
        """execute_rollback with no parent version returns success=False without raising."""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            is_current=True,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(dataset, is_current=True)

        # execute_rollback with single version (no parent) returns success=False, no exception
        config = RollbackConfig(require_approval=False)
        result = VersionRollbackManager.execute_rollback(
            dataset, approved_by=self.user, reason="Test", config=config
        )
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("success"))

    def test_check_rollback_conditions_error_handling(self):
        """Test error handling when checking rollback conditions fails"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(dataset, is_current=True)

        # Should handle errors gracefully
        try:
            config = RollbackConfig(enable_auto_rollback=True)
            result = VersionRollbackManager.check_rollback_conditions(dataset, config=config)
            self.assertIsNotNone(result)
            self.assertIn("should_rollback", result)
            self.assertIn("triggers", result)
        except Exception:
            self.fail("check_rollback_conditions should handle errors gracefully")

    # ── Rollback history (gap: previously untested) ──────────────────

    def test_get_rollback_history_returns_list(self):
        """get_rollback_history must return a list for an asset with versions."""
        history = VersionRollbackManager.get_rollback_history(
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
        )
        self.assertIsInstance(history, list, "get_rollback_history must return a list")

    def test_get_rollback_history_with_limit(self):
        """get_rollback_history respects the limit parameter."""
        history = VersionRollbackManager.get_rollback_history(
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            limit=5,
        )
        self.assertIsInstance(history, list)
        self.assertLessEqual(
            len(history), 5, "get_rollback_history must not exceed the requested limit"
        )
