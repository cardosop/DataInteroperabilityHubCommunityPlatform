"""
E2E tests for Asset Recommendations, Popularity Metrics, and Health Score

End-to-end tests for complete workflows.
"""

from datetime import timedelta

import pytest

pytestmark = pytest.mark.slow
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.assets.health_score import AssetHealthScoreService
from hub.apps.assets.models import Asset, AssetStatus, ComplianceStatus, DQStatus
from hub.apps.assets.popularity import AssetPopularityService
from hub.apps.assets.recommendations import AssetRecommendationService
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.datasets.models import Dataset
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.search.models import SearchAnalytics
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

from tests.e2e.conftest import get_response_data
import uuid

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class AssetRecommendationsE2ETest(TestCase):
    """E2E tests for asset recommendations"""

    def setUp(self):
        """Set up test fixtures"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.semantic.signals import asset_saved, contract_saved
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        self.user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create assets
        self.asset1 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-1",
            name="Asset 1",
            status=AssetStatus.PUBLIC,
            popularity_score=95.0,
            view_count=500,
            download_count=200,
            created_by=self.user,
        )

        self.asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="asset-2",
            name="Asset 2",
            status=AssetStatus.ACTIVE,
            popularity_score=80.0,
            view_count=300,
            download_count=150,
            domain="finance",
            created_by=self.user,
        )

    def test_complete_recommendations_workflow(self):
        """
        Test complete recommendations workflow:
        1. Create user search history
        2. Get recommendations via API
        3. Verify recommendations
        """
        # Step 1: Create user search history
        SearchAnalytics.objects.create(
            tenant=self.tenant,
            user=self.user,
            query="finance",
            clicked_result_id=self.asset2.id,
            clicked_result_type="ASSET",
            clicked_at=timezone.now(),
        )

        # Step 2: Get recommendations via API
        response = self.client.get(
            "/api/v1/assets/recommendations/", {"user_id": str(self.user.id), "limit": 10}
        )

        # Step 3: Verify recommendations
        self.assertEqual(response.status_code, 200)
        recommendations = (get_response_data(response) or {})

        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)

        # Verify recommendation structure
        for rec in recommendations:
            self.assertIn("asset_id", rec)
            self.assertIn("asset_name", rec)
            self.assertIn("score", rec)
            self.assertIn("reasons", rec)


class AssetPopularityE2ETest(TestCase):
    """E2E tests for asset popularity"""

    def setUp(self):
        """Set up test fixtures"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.semantic.signals import asset_saved, contract_saved
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            view_count=0,
            download_count=0,
            created_by=self.user,
        )

    def test_complete_popularity_tracking_workflow(self):
        """
        Test complete popularity tracking workflow:
        1. Track view via API
        2. Track download via API
        3. Verify counts and popularity score
        """
        # Step 1: Track view
        response = self.client.post(f"/api/v1/assets/{self.asset.id}/track-view/")

        self.assertEqual(response.status_code, 200)

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.view_count, 1)
        self.assertIsNotNone(self.asset.popularity_score)

        # Step 2: Track download
        response = self.client.post(f"/api/v1/assets/{self.asset.id}/track-download/")

        self.assertEqual(response.status_code, 200)

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.download_count, 1)

        # Step 3: Verify popularity score was recalculated
        self.assertIsNotNone(self.asset.popularity_score)
        self.assertGreater(self.asset.popularity_score, 0.0)


class AssetHealthScoreE2ETest(TestCase):
    """E2E tests for asset health score"""

    def setUp(self):
        """Set up test fixtures"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts (root cause fix)
        # Semantic service signals trigger on every Asset/Contract save, causing 60s timeouts
        # This provides 10-100x speedup by preventing semantic service calls during tests
        from django.db.models.signals import post_save

        try:
            from hub.apps.semantic.signals import asset_saved, contract_saved
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract

            # Disconnect signals to prevent semantic service calls during tests
            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            # Signals may not be available - continue without disconnecting
            pass

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        self.user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            view_count=100,
            download_count=50,
            popularity_score=80.0,
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_at=timezone.now() - timedelta(hours=12),
            created_by=self.user,
        )

    def test_complete_health_score_workflow(self):
        """
        Test complete health score workflow:
        1. Create DQ run
        2. Get health score via API
        3. Get health score with breakdown
        4. Recalculate health score
        """
        # Step 1: Create DQ run
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=self.dataset.id,
            created_by=self.user,
        )

        DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.0,
            completed_at=timezone.now(),
        )

        # Step 2: Get health score (recalculate to ensure it's computed)
        response = self.client.get(
            f"/api/v1/assets/{self.asset.id}/health-score/", {"recalculate": "true"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("health_score", (get_response_data(response) or {}))
        self.assertIsNotNone((get_response_data(response) or {})["health_score"])

        # Step 3: Get health score with breakdown
        response = self.client.get(
            f"/api/v1/assets/{self.asset.id}/health-score/",
            {"breakdown": "true", "recalculate": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("breakdown", (get_response_data(response) or {}))
        self.assertIn("components", (get_response_data(response) or {})["breakdown"])

        # Step 4: Recalculate health score
        response = self.client.get(
            f"/api/v1/assets/{self.asset.id}/health-score/", {"recalculate": "true"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("health_score", (get_response_data(response) or {}))
