"""
Unit tests for File model.
"""

import pytest
from django.test import TestCase

from hub.apps.files.models import File, FileStatus
from hub.apps.files.tests.test_base import FilesTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class FileModelTest(FilesTestBase):
    """Test File model"""

    def test_create_file(self):
        """Test file creation"""
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.UPLOADING,
            created_by=self.user,
        )

        self.assertEqual(file_obj.tenant, self.tenant)
        self.assertEqual(file_obj.name, "test.csv")
        self.assertEqual(file_obj.size, 1024)
        self.assertEqual(file_obj.status, FileStatus.UPLOADING)

    def test_file_status_choices(self):
        """Test file status enum"""
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1024,
            content_type="text/csv",
        )

        file_obj.status = FileStatus.COMPLETED
        file_obj.save()
        self.assertEqual(file_obj.status, FileStatus.COMPLETED)
