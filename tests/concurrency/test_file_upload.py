"""Phase 103: File record creation consistency."""
import uuid
from django.test import TestCase
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant


class FileUploadConsistencyTest(TestCase):
    """Multiple file records for same tenant all succeed."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"File {uid}", slug=f"file-{uid}",
        )

    def test_multiple_files_all_succeed(self):
        for i in range(5):
            File.objects.create(
                tenant=self.tenant,
                name=f"test-file-{i}.csv",
                content_type="text/csv",
                size=1024,
                storage_path=f"test/{uuid.uuid4().hex}.csv",
                status=FileStatus.PENDING,
            )
        self.assertEqual(
            File.objects.filter(tenant=self.tenant).count(), 5
        )

    def test_file_count_matches_creates(self):
        ids = []
        for i in range(3):
            f = File.objects.create(
                tenant=self.tenant,
                name=f"counted-{i}.csv",
                content_type="text/csv",
                size=512,
                storage_path=f"test/{uuid.uuid4().hex}.csv",
                status=FileStatus.PENDING,
            )
            ids.append(f.id)
        self.assertEqual(File.objects.filter(id__in=ids).count(), 3)
