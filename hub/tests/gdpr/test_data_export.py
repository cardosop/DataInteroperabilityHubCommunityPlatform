"""Phase 110: GDPR data export."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.gdpr.models import DataExportJob, DataExportStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


class DataExportTest(TestCase):
    """Verify GDPR data export model and workflow."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Export {uid}",
            slug=f"export-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"export-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_data_export_job_created(self):
        """Data export job can be created for user."""
        job = DataExportJob.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=DataExportStatus.PENDING,
        )
        self.assertEqual(job.status, DataExportStatus.PENDING)
        self.assertEqual(job.user, self.user)

    def test_data_export_status_lifecycle(self):
        """Export job transitions through statuses."""
        job = DataExportJob.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=DataExportStatus.PENDING,
        )
        job.status = DataExportStatus.PROCESSING
        job.save()
        job.refresh_from_db()
        self.assertEqual(job.status, DataExportStatus.PROCESSING)

    def test_user_pii_fields_exist(self):
        """User model has required PII fields for export."""
        user = User.objects.get(pk=self.user.pk)
        # PII fields that must be included in export
        self.assertTrue(hasattr(user, "email"))
        self.assertTrue(hasattr(user, "display_name"))
        self.assertTrue(hasattr(user, "created_at"))
