"""RoPA pipeline — S3 materialisation + ``ROPA_GENERATED`` audit (real boto3 client / MinIO)."""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.audit import event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.tasks_base import _execute_job_logic
from hub.apps.jobs.tasks_ropa import _execute_ropa_generate_job
from hub.apps.ropa.models import RopaGeneration, RopaGenerationStatus, RopaOutputFormat
from hub.apps.ropa.services.pipeline import materialize_generation, ropa_storage_client
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


def _ropa_s3_ready() -> bool:
    """MinIO/S3 reachable with the same credentials as RoPA uploads (no mocking)."""
    try:
        client = ropa_storage_client()
        client._ensure_bucket_exists()
        return True
    except Exception:
        return False


class RopaMaterializeTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"ropa-pipe-{uid}",
            slug=f"ropa-pipe-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_ropa_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"ropa-pipe-{uid}@example.com",
            password="test-pass!",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        role, _ = Role.objects.get_or_create(tenant=self.tenant, name="TENANT_ADMIN")
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)

    @pytest.mark.integration
    def test_materialize_uploads_writes_audit_completed(self):
        if not _ropa_s3_ready():
            self.skipTest("S3/MinIO storage not available for RoPA materialization")

        gen = RopaGeneration.objects.create(
            tenant=self.tenant,
            regulation="GDPR",
            output_format=RopaOutputFormat.JSON,
            status=RopaGenerationStatus.PENDING,
            gaps_json=[],
            summary_json={},
            created_by=self.user,
        )
        before = AuditEvent.objects.filter(
            tenant=self.tenant,
            resource_type="ROPA_GENERATION",
            resource_id=gen.id,
            action=event_types.ROPA_GENERATED,
        ).count()

        materialize_generation(generation=gen, actor_user=self.user)
        gen.refresh_from_db()

        self.assertEqual(gen.status, RopaGenerationStatus.COMPLETED)
        self.assertTrue(gen.object_key)
        client = ropa_storage_client()
        self.assertTrue(client.file_exists(gen.object_key))

        after = AuditEvent.objects.filter(
            tenant=self.tenant,
            resource_type="ROPA_GENERATION",
            resource_id=gen.id,
            action=event_types.ROPA_GENERATED,
        ).count()
        self.assertEqual(after, before + 1)

    @pytest.mark.integration
    def test_router_invokes_ropa_handler(self):
        """``_execute_job_logic`` dispatches ``ROPA_GENERATE`` to ``tasks_ropa``."""
        job = Job(
            tenant=self.tenant,
            type=JobType.ROPA_GENERATE,
            status=JobStatus.PENDING,
            resource_type="ROPA_GENERATION",
            resource_id=uuid.uuid4(),
            details_json={},
            created_by=self.user,
        )
        with self.assertRaises(ValueError):
            _execute_job_logic(job, JobType.ROPA_GENERATE)

    @pytest.mark.integration
    def test_execute_ropa_job_materializes_when_s3_ready(self):
        if not _ropa_s3_ready():
            self.skipTest("S3/MinIO storage not available")

        gen = RopaGeneration.objects.create(
            tenant=self.tenant,
            regulation="GDPR",
            output_format=RopaOutputFormat.CSV,
            status=RopaGenerationStatus.PENDING,
            gaps_json=[],
            summary_json={},
            created_by=self.user,
        )
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ROPA_GENERATE,
            status=JobStatus.PENDING,
            resource_type="ROPA_GENERATION",
            resource_id=gen.id,
            details_json={"ropa_generation_id": str(gen.id)},
            created_by=self.user,
        )
        out = _execute_ropa_generate_job(job)
        self.assertEqual(out["ropa_generation_id"], str(gen.id))
        gen.refresh_from_db()
        self.assertEqual(gen.status, RopaGenerationStatus.COMPLETED)
