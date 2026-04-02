"""Phase 103: DQ job creation consistency."""
import uuid
from django.test import TestCase
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.jobs.models import Job, JobStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from django.contrib.auth import get_user_model

User = get_user_model()


class DQTriggerConsistencyTest(TestCase):
    """Multiple DQ jobs for same resource all created."""

    def test_multiple_jobs_same_resource_all_created(self):
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"DQ {uid}", slug=f"dq-{uid}",
        )
        user = User.objects.create_user(
            email=f"dq-{uid}@example.com", password="test123",
            tenant=tenant, status=UserStatus.ACTIVE,
        )
        asset = Asset.objects.create(
            tenant=tenant, key=f"dq-asset-{uid}",
            name="DQ Test Asset", status=AssetStatus.DRAFT,
        )
        for _ in range(5):
            Job.objects.create(
                tenant=tenant,
                type="DATA_QUALITY",
                resource_type="ASSET",
                resource_id=str(asset.id),
                status=JobStatus.PENDING,
                created_by=user,
            )
        self.assertEqual(
            Job.objects.filter(
                tenant=tenant, resource_id=str(asset.id)
            ).count(), 5,
        )
