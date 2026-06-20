"""
Phase 16: Tenant isolation integration tests.

Asserts that user A (tenant 1) cannot see tenant 2's resources by ID (404)
and that list endpoints return only tenant 1's resources. Uses real DB and
auth; no mocks. See docs/TENANT_ISOLATION.md and tasks.md Phase 16.

Tenant2 resources are created via ORM (not API) to avoid slow contract
normalization and API/signal overhead; we only assert list/detail isolation.

For faster reruns (skip DB create/migrate): run with --reuse-db.
First run: session-scoped DB create+migrate runs during first test's setup
(~5 min in this project). Test bodies finish in seconds. Per-test timeout 600s
accommodates that one-time setup; use --reuse-db so reruns complete in under a minute.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = [
    pytest.mark.django_db(transaction=True),
    # 600s per test: django_db_setup (create+migrate) runs in first test's setup (~5 min);
    # test bodies are fast; timeout is ceiling for real hangs
    pytest.mark.timeout(600),
]
User = get_user_model()


class TenantIsolationTest(TestCase):
    """Integration tests: no cross-tenant read (Phase 16.2.2)."""

    def setUp(self):
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        self.client = APIClient()
        self.tenant1 = Tenant.objects.create(
            name="Tenant One",
            slug="tenant-one",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.tenant2 = Tenant.objects.create(
            name="Tenant Two",
            slug="tenant-two",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user1 = User.objects.create_user(
            email="user1@tenant1.example.com",
            password="testpass123",
            tenant=self.tenant1,
            status=UserStatus.ACTIVE,
        )
        self.user2 = User.objects.create_user(
            email="user2@tenant2.example.com",
            password="testpass123",
            tenant=self.tenant2,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user1)

    def tearDown(self):
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass
        super().tearDown()

    def test_assets_list_returns_only_tenant1_resources(self):
        """List assets as user1 returns only tenant1 assets."""
        from hub.apps.assets.models import Asset

        # Create asset in tenant2 via ORM (avoids API/signals; we only assert list isolation)
        asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key="tenant2-asset",
            name="Tenant Two Asset",
            domain="test",
        )
        asset2_id = str(asset2.id)

        # user1 lists assets: should not see tenant2's asset
        list_resp = self.client.get("/api/v1/assets/")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        ids = [a["id"] for a in list_resp.data.get("results", list_resp.data)]
        self.assertNotIn(asset2_id, ids, "User1 must not see tenant2 asset in list")

    def test_assets_detail_tenant2_resource_returns_404_for_user1(self):
        """User1 cannot retrieve tenant2's asset by ID (404)."""
        from hub.apps.assets.models import Asset

        asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key="tenant2-only",
            name="Tenant Two Only",
            domain="test",
        )

        resp = self.client.get(f"/api/v1/assets/{asset2.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_contracts_list_returns_only_tenant1_resources(self):
        """List contracts as user1 returns only tenant1 contracts."""
        from hub.apps.assets.models import Asset
        from hub.apps.contracts.models import Contract, OriginalFormat, OriginalSpecType

        # Create asset and contract in tenant2 via ORM to avoid slow normalization in tests
        asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key="t2-asset",
            name="T2 Asset",
            domain="test",
        )
        contract2 = Contract.objects.create(
            tenant=self.tenant2,
            asset=asset2,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id":"c2","info":{"name":"C2"}}',
        )
        contract2_id = str(contract2.id)

        list_resp = self.client.get("/api/v1/contracts/")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        ids = [str(c["id"]) for c in list_resp.data.get("results", list_resp.data)]
        self.assertNotIn(contract2_id, ids)

    def test_contracts_detail_tenant2_resource_returns_404_for_user1(self):
        """User1 cannot retrieve tenant2's contract by ID (404)."""
        from hub.apps.assets.models import Asset
        from hub.apps.contracts.models import Contract, OriginalFormat, OriginalSpecType

        asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key="t2-a",
            name="T2 A",
            domain="test",
        )
        contract2 = Contract.objects.create(
            tenant=self.tenant2,
            asset=asset2,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id":"x","info":{"name":"X"}}',
        )

        resp = self.client.get(f"/api/v1/contracts/{contract2.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_datasets_list_returns_only_tenant1_resources(self):
        """List datasets as user1 returns only tenant1 datasets."""
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus

        f2 = File.objects.create(
            tenant=self.tenant2,
            name="t2.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            storage_path="tenant2/t2.csv",
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key="t2-ds-asset",
            name="T2 DS Asset",
            domain="test",
        )
        ds2 = Dataset.objects.create(
            tenant=self.tenant2,
            file=f2,
            asset=asset2,
            format="CSV",
        )
        ds2_id = str(ds2.id)

        list_resp = self.client.get("/api/v1/datasets/")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        ids = [d["id"] for d in list_resp.data.get("results", list_resp.data)]
        self.assertNotIn(ds2_id, ids)

    def test_datasets_detail_tenant2_resource_returns_404_for_user1(self):
        """User1 cannot retrieve tenant2's dataset by ID (404)."""
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus

        f2 = File.objects.create(
            tenant=self.tenant2,
            name="t2f.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            storage_path="tenant2/t2f.csv",
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key="t2-ds-a",
            name="T2 DS A",
            domain="test",
        )
        ds2 = Dataset.objects.create(tenant=self.tenant2, file=f2, asset=asset2, format="CSV")

        resp = self.client.get(f"/api/v1/datasets/{ds2.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_files_list_returns_only_tenant1_resources(self):
        """List files as user1 returns only tenant1 files."""
        from hub.apps.files.models import File, FileStatus

        f2 = File.objects.create(
            tenant=self.tenant2,
            name="t2file.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            storage_path="tenant2/t2file.csv",
        )
        f2_id = str(f2.id)

        list_resp = self.client.get("/api/v1/files/")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        ids = [f["id"] for f in list_resp.data.get("results", list_resp.data)]
        self.assertNotIn(f2_id, ids)

    def test_files_detail_tenant2_resource_returns_404_for_user1(self):
        """User1 cannot retrieve tenant2's file by ID (404)."""
        from hub.apps.files.models import File, FileStatus

        f2 = File.objects.create(
            tenant=self.tenant2,
            name="t2only.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            storage_path="tenant2/t2only.csv",
        )

        resp = self.client.get(f"/api/v1/files/{f2.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_jobs_list_returns_only_tenant1_resources(self):
        """List jobs as user1 returns only tenant1 jobs."""
        import uuid

        from hub.apps.jobs.models import Job, JobStatus, JobType

        j2 = Job.objects.create(
            tenant=self.tenant2,
            type=JobType.SCHEDULED_INGESTION,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
        )
        j2_id = str(j2.id)

        list_resp = self.client.get("/api/v1/jobs/")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        ids = [j["id"] for j in list_resp.data.get("results", list_resp.data)]
        self.assertNotIn(j2_id, ids)

    def test_jobs_detail_tenant2_resource_returns_404_for_user1(self):
        """User1 cannot retrieve tenant2's job by ID (404)."""
        import uuid

        from hub.apps.jobs.models import Job, JobStatus, JobType

        j2 = Job.objects.create(
            tenant=self.tenant2,
            type=JobType.SCHEDULED_INGESTION,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
        )

        resp = self.client.get(f"/api/v1/jobs/{j2.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # Phase 10.3: Tests for ViewSets using central helper (get_request_tenant_id)
    # These tests verify that tenant resolution follows request.tenant_id when it differs from user.tenant

    def test_dq_runs_list_follows_request_tenant_id(self):
        """DQRunViewSet.get_queryset follows request.tenant_id when set (Phase 10.1.1)."""
        import uuid

        from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
        from hub.apps.jobs.models import Job, JobStatus, JobType

        # Create job for DQ run
        job1 = Job.objects.create(
            tenant=self.tenant1,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
        )
        job2 = Job.objects.create(
            tenant=self.tenant2,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
        )

        # Create assets for DQ runs (required by model validation)
        from hub.apps.assets.models import Asset

        asset1 = Asset.objects.create(
            tenant=self.tenant1,
            key="t1-dq-asset",
            name="T1 DQ Asset",
            domain="test",
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key="t2-dq-asset",
            name="T2 DQ Asset",
            domain="test",
        )

        # Create DQ runs in both tenants
        dq_run1 = DQRun.objects.create(
            tenant=self.tenant1,
            job=job1,
            asset=asset1,
            profile_key="test_profile",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )
        dq_run2 = DQRun.objects.create(
            tenant=self.tenant2,
            job=job2,
            asset=asset2,
            profile_key="test_profile",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        # Test get_queryset with request.tenant_id set to tenant2 (different from user.tenant)
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from hub.apps.dq.views import DQRunViewSet

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/dq/runs/")
        # Wrap in DRF Request to get query_params
        request = Request(drf_request)
        request.tenant_id = str(self.tenant2.id)
        request.tenant = None  # Clear to force resolution from tenant_id
        request.user = self.user1  # user1 belongs to tenant1

        viewset = DQRunViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        # Should return tenant2's DQ runs (follows request.tenant_id, not user.tenant)
        self.assertIn(
            dq_run2, queryset, "Should see tenant2 DQ runs when request.tenant_id=tenant2"
        )
        self.assertNotIn(
            dq_run1, queryset, "Should not see tenant1 DQ runs when request.tenant_id=tenant2"
        )

    def test_compliance_runs_list_follows_request_tenant_id(self):
        """ComplianceRunViewSet.get_queryset follows request.tenant_id when set (Phase 10.1.2)."""

        from hub.apps.assets.models import Asset
        from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
        from hub.apps.jobs.models import Job, JobStatus, JobType

        asset1 = Asset.objects.create(
            tenant=self.tenant1,
            key="t1-asset",
            name="T1 Asset",
            domain="test",
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key="t2-asset",
            name="T2 Asset",
            domain="test",
        )

        job1 = Job.objects.create(
            tenant=self.tenant1,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=asset1.id,
        )
        job2 = Job.objects.create(
            tenant=self.tenant2,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=asset2.id,
        )

        comp_run1 = ComplianceRun.objects.create(
            tenant=self.tenant1,
            job=job1,
            asset=asset1,
            status=ComplianceRunStatus.PENDING,
        )
        comp_run2 = ComplianceRun.objects.create(
            tenant=self.tenant2,
            job=job2,
            asset=asset2,
            status=ComplianceRunStatus.PENDING,
        )

        # Test get_queryset with request.tenant_id set to tenant2 (different from user.tenant)
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from hub.apps.compliance.views import ComplianceRunViewSet

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/compliance/runs/")
        # Wrap in DRF Request to get query_params
        request = Request(drf_request)
        request.tenant_id = str(self.tenant2.id)
        request.tenant = None
        request.user = self.user1

        viewset = ComplianceRunViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        # Should return tenant2's compliance runs (follows request.tenant_id, not user.tenant)
        self.assertIn(
            comp_run2, queryset, "Should see tenant2 compliance runs when request.tenant_id=tenant2"
        )
        self.assertNotIn(
            comp_run1,
            queryset,
            "Should not see tenant1 compliance runs when request.tenant_id=tenant2",
        )

    def test_audit_events_list_follows_request_tenant_id(self):
        """AuditEventViewSet.get_queryset follows request.tenant_id when set (Phase 10.1.3)."""
        from hub.apps.audit.models import AuditEvent

        audit1 = AuditEvent.objects.create(
            tenant=self.tenant1,
            resource_type="ASSET",
            action="CREATED",
            actor_user_id=str(self.user1.id),
        )
        audit2 = AuditEvent.objects.create(
            tenant=self.tenant2,
            resource_type="ASSET",
            action="CREATED",
            actor_user_id=str(self.user2.id),
        )

        # Test get_queryset with request.tenant_id set to tenant2 (different from user.tenant)
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from hub.apps.audit.views import AuditEventViewSet

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/audit/audit-events/")
        # Wrap in DRF Request to get query_params
        request = Request(drf_request)
        request.tenant_id = str(self.tenant2.id)
        request.tenant = None
        request.user = self.user1

        viewset = AuditEventViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        # Should return tenant2's audit events (follows request.tenant_id, not user.tenant)
        self.assertIn(
            audit2, queryset, "Should see tenant2 audit events when request.tenant_id=tenant2"
        )
        self.assertNotIn(
            audit1, queryset, "Should not see tenant1 audit events when request.tenant_id=tenant2"
        )

    def test_semantic_resources_list_follows_request_tenant_id(self):
        """SemanticResourceViewSet.get_queryset follows request.tenant_id when set (Phase 10.1.4)."""
        import uuid

        from hub.apps.semantic.models import ResourceType, SemanticResource

        resource1 = SemanticResource.objects.create(
            tenant=self.tenant1,
            uri="http://example.com/t1/resource",
            resource_type=ResourceType.ASSET,
            resource_id=uuid.uuid4(),
        )
        resource2 = SemanticResource.objects.create(
            tenant=self.tenant2,
            uri="http://example.com/t2/resource",
            resource_type=ResourceType.ASSET,
            resource_id=uuid.uuid4(),
        )

        # Test get_queryset with request.tenant_id set to tenant2 (different from user.tenant)
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from hub.apps.semantic.views import SemanticResourceViewSet

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/semantic/resources/")
        # Wrap in DRF Request to get query_params
        request = Request(drf_request)
        request.tenant_id = str(self.tenant2.id)
        request.tenant = None
        request.user = self.user1

        viewset = SemanticResourceViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        # Should return tenant2's semantic resources (follows request.tenant_id, not user.tenant)
        self.assertIn(
            resource2,
            queryset,
            "Should see tenant2 semantic resources when request.tenant_id=tenant2",
        )
        self.assertNotIn(
            resource1,
            queryset,
            "Should not see tenant1 semantic resources when request.tenant_id=tenant2",
        )

    def test_scheduled_ingestions_list_follows_request_tenant_id(self):
        """ScheduledIngestionViewSet.get_queryset follows request.tenant_id when set (Phase 10.1.5)."""
        from hub.apps.scheduled_ingestion.models import (
            ScheduledIngestion,
            ScheduledIngestionStatus,
            ScheduleType,
        )

        si1 = ScheduledIngestion.objects.create(
            tenant=self.tenant1,
            name="T1 Ingestion",
            source_type="S3",
            source_config={"bucket": "t1-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00", "timezone": "UTC"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user1,
        )
        si2 = ScheduledIngestion.objects.create(
            tenant=self.tenant2,
            name="T2 Ingestion",
            source_type="S3",
            source_config={"bucket": "t2-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00", "timezone": "UTC"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user2,
        )

        # Test get_queryset with request.tenant_id set to tenant2 (different from user.tenant)
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from hub.apps.scheduled_ingestion.views import ScheduledIngestionViewSet

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/scheduled-ingestions/")
        # Wrap in DRF Request to get query_params
        request = Request(drf_request)
        request.tenant_id = str(self.tenant2.id)
        request.tenant = None
        request.user = self.user1

        viewset = ScheduledIngestionViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        # Should return tenant2's scheduled ingestions (follows request.tenant_id, not user.tenant)
        self.assertIn(
            si2, queryset, "Should see tenant2 scheduled ingestions when request.tenant_id=tenant2"
        )
        self.assertNotIn(
            si1,
            queryset,
            "Should not see tenant1 scheduled ingestions when request.tenant_id=tenant2",
        )

    def test_ml_models_list_follows_request_tenant_id(self):
        """MLModelViewSet.get_queryset follows request.tenant_id when set (Phase 10.1.7)."""
        from hub.apps.ml.models import MLModel, ModelStatus

        model1 = MLModel.objects.create(
            tenant=self.tenant1,
            odh_model_id="t1-model-id",
            odh_model_name="t1-model",
            odh_model_version="1.0",
            model_type="CLASSIFICATION",
            status=ModelStatus.TRAINED,
        )
        model2 = MLModel.objects.create(
            tenant=self.tenant2,
            odh_model_id="t2-model-id",
            odh_model_name="t2-model",
            odh_model_version="1.0",
            model_type="CLASSIFICATION",
            status=ModelStatus.TRAINED,
        )

        # Test get_queryset with request.tenant_id set to tenant2 (different from user.tenant)
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from hub.apps.ml.views import MLModelViewSet

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/ml/models/")
        # Wrap in DRF Request to get query_params
        request = Request(drf_request)
        request.tenant_id = str(self.tenant2.id)
        request.tenant = None
        request.user = self.user1

        viewset = MLModelViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        # Should return tenant2's ML models (follows request.tenant_id, not user.tenant)
        self.assertIn(
            model2, queryset, "Should see tenant2 ML models when request.tenant_id=tenant2"
        )
        self.assertNotIn(
            model1, queryset, "Should not see tenant1 ML models when request.tenant_id=tenant2"
        )

    def test_governance_access_certifications_list_follows_request_tenant_id(self):
        """AccessCertificationViewSet.get_queryset follows request.tenant_id when set (Phase 10.1.6)."""
        from datetime import timedelta

        from django.utils import timezone

        from hub.apps.governance.access_certification import AccessCertification

        cert1 = AccessCertification.objects.create(
            tenant=self.tenant1,
            user=self.user1,
            certification_type="USER_LEVEL",
            status="PENDING",
            expires_at=timezone.now() + timedelta(days=30),
        )
        cert2 = AccessCertification.objects.create(
            tenant=self.tenant2,
            user=self.user2,
            certification_type="USER_LEVEL",
            status="PENDING",
            expires_at=timezone.now() + timedelta(days=30),
        )

        # Test get_queryset with request.tenant_id set to tenant2 (different from user.tenant)
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from hub.apps.governance.views import AccessCertificationViewSet

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/governance/access/certifications/")
        # Wrap in DRF Request to get query_params
        request = Request(drf_request)
        request.tenant_id = str(self.tenant2.id)
        request.tenant = None
        request.user = self.user1

        viewset = AccessCertificationViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        # Should return tenant2's certifications (follows request.tenant_id, not user.tenant)
        self.assertIn(
            cert2, queryset, "Should see tenant2 certifications when request.tenant_id=tenant2"
        )
        self.assertNotIn(
            cert1, queryset, "Should not see tenant1 certifications when request.tenant_id=tenant2"
        )

    def test_governance_retention_policies_list_follows_request_tenant_id(self):
        """RetentionPolicyViewSet.get_queryset follows request.tenant_id when set (Phase 10.1.11)."""
        from hub.apps.assets.models import Asset
        from hub.apps.governance.models import RetentionPolicy, RetentionPolicyType

        # Create assets for retention policies (required by model validation)
        asset1 = Asset.objects.create(
            tenant=self.tenant1,
            key="t1-retention-asset",
            name="T1 Retention Asset",
            domain="test",
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key="t2-retention-asset",
            name="T2 Retention Asset",
            domain="test",
        )

        policy1 = RetentionPolicy.objects.create(
            tenant=self.tenant1,
            name="T1 Policy",
            policy_type=RetentionPolicyType.TIME_BASED,
            retention_period_days=30,
            asset=asset1,
        )
        policy2 = RetentionPolicy.objects.create(
            tenant=self.tenant2,
            name="T2 Policy",
            policy_type=RetentionPolicyType.TIME_BASED,
            retention_period_days=30,
            asset=asset2,
        )

        # Test get_queryset with request.tenant_id set to tenant2 (different from user.tenant)
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from hub.apps.governance.retention_views import RetentionPolicyViewSet

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/governance/retention-policies/")
        # Wrap in DRF Request to get query_params
        request = Request(drf_request)
        request.tenant_id = str(self.tenant2.id)
        request.tenant = None
        request.user = self.user1

        viewset = RetentionPolicyViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        # Should return tenant2's retention policies (follows request.tenant_id, not user.tenant)
        self.assertIn(
            policy2,
            queryset,
            "Should see tenant2 retention policies when request.tenant_id=tenant2",
        )
        self.assertNotIn(
            policy1,
            queryset,
            "Should not see tenant1 retention policies when request.tenant_id=tenant2",
        )

    def test_virtualization_query_executions_list_follows_request_tenant_id(self):
        """QueryExecutionViewSet.get_queryset follows request.tenant_id when set (Phase 10.1.8)."""
        from hub.apps.virtualization.models import (
            QueryExecution,
            QueryExecutionStatus,
            QueryType,
            VirtualDataset,
            VirtualDatasetStatus,
        )

        vd1 = VirtualDataset.objects.create(
            tenant=self.tenant1,
            name="T1 Dataset",
            query_type=QueryType.SQL,
            query="SELECT * FROM t1",
            status=VirtualDatasetStatus.ACTIVE,
            created_by=self.user1,
        )
        vd2 = VirtualDataset.objects.create(
            tenant=self.tenant2,
            name="T2 Dataset",
            query_type=QueryType.SQL,
            query="SELECT * FROM t2",
            status=VirtualDatasetStatus.ACTIVE,
            created_by=self.user2,
        )

        exec1 = QueryExecution.objects.create(
            virtual_dataset=vd1,
            query="SELECT * FROM t1",
            status=QueryExecutionStatus.COMPLETED,
        )
        exec2 = QueryExecution.objects.create(
            virtual_dataset=vd2,
            query="SELECT * FROM t2",
            status=QueryExecutionStatus.COMPLETED,
        )

        # Test get_queryset with request.tenant_id set to tenant2 (different from user.tenant)
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from hub.apps.virtualization.views import QueryExecutionViewSet

        factory = APIRequestFactory()
        drf_request = factory.get("/api/v1/virtualization/query-executions/")
        # Wrap in DRF Request to get query_params
        request = Request(drf_request)
        request.tenant_id = str(self.tenant2.id)
        request.tenant = None
        request.user = self.user1

        viewset = QueryExecutionViewSet()
        viewset.request = request
        viewset.action = "list"
        queryset = viewset.get_queryset()

        # Should return tenant2's query executions (follows request.tenant_id via virtual_dataset, not user.tenant)
        self.assertIn(
            exec2, queryset, "Should see tenant2 query executions when request.tenant_id=tenant2"
        )
        self.assertNotIn(
            exec1,
            queryset,
            "Should not see tenant1 query executions when request.tenant_id=tenant2",
        )


class PersonalTenantIsolationTest(TestCase):
    """User with personal tenant cannot access another tenant's resources (useronboardfix 2.1.2)."""

    def setUp(self):
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        from django.core.management import call_command

        call_command("seed_default_plans")

        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uid}",
            slug=f"other-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

    def tearDown(self):
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass
        super().tearDown()

    def test_personal_tenant_user_cannot_access_other_tenant_resources(self):
        """User created via registration (personal tenant) cannot access another tenant's asset."""
        from hub.apps.assets.models import Asset

        email = f"personal-{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePass123"
        name = "Personal User"

        reg = self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "password": password, "name": name},
            format="json",
        )
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(reg.data.get("tenant_id"))

        login = self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")

        other_asset = Asset.objects.create(
            tenant=self.other_tenant,
            key="other-tenant-asset",
            name="Other Tenant Asset",
            domain="test",
        )

        resp = self.client.get(f"/api/v1/assets/{other_asset.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
