"""
Phase TR.B — API integration test for file virus scan status.

Tests the GET /api/v1/files/{id}/scan-status/ endpoint which returns
the scan_status of a File without requiring ClamAV or any external
infrastructure (pure DB lookup).
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.files.models import File, FileScanStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User


class TestScanStatusEndpoint(TestCase):
    """Integration tests for GET /api/v1/files/{id}/scan-status/."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Virus Scan Test", slug="virus-scan-test", status="ACTIVE"
        )
        self.user = User.objects.create_user(
            email="vscan@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        self.client.force_authenticate(user=self.user)

    def test_scan_status_returns_clean_file(self):
        """GET scan-status returns scan_status=CLEAN and correct file_id."""
        f = File.objects.create(
            tenant=self.tenant,
            storage_path="clean-file",
            scan_status=FileScanStatus.CLEAN,
            size=0,
        )
        response = self.client.get(f"/api/v1/files/{f.id}/scan-status/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.data["scan_status"] == FileScanStatus.CLEAN
        assert response.data["file_id"] == str(f.id)

    def test_scan_status_returns_infected_file(self):
        """GET scan-status returns scan_status=INFECTED for an infected file."""
        f = File.objects.create(
            tenant=self.tenant,
            storage_path="infected-file",
            scan_status=FileScanStatus.INFECTED,
            size=0,
        )
        response = self.client.get(f"/api/v1/files/{f.id}/scan-status/")
        assert response.status_code == 200
        assert response.data["scan_status"] == FileScanStatus.INFECTED

    def test_scan_status_requires_auth(self):
        """Unauthenticated GET returns 401."""
        unauth_client = APIClient()
        f = File.objects.create(
            tenant=self.tenant, storage_path="noauth", scan_status=FileScanStatus.CLEAN, size=0
        )
        response = unauth_client.get(f"/api/v1/files/{f.id}/scan-status/")
        assert response.status_code in (401, 403), (
            f"Expected 401/403 for unauthenticated, got {response.status_code}"
        )
