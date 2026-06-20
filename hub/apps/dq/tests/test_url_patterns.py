"""
Tests for DQ service URL patterns.

Task: 9.6.3.1.2 - Standardize DQ service resource naming
Tests URL pattern resolution, consistency, and backward compatibility.
"""

import uuid

import pytest
from django.test import TestCase
from django.urls import Resolver404, resolve, reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class DQURLPatternTest(TestCase):
    """Test URL pattern resolution and reverse lookup for DQ endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create file
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        # Create job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        # Create DQ run
        self.dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.5,
        )

        # Authenticate
        self.client.force_authenticate(user=self.user)

    def test_runs_list_url_resolution(self):
        """Test that runs list URL resolves correctly."""
        # Standardized pattern: /api/v1/dq/runs/
        url = "/api/v1/dq/runs/"

        try:
            resolved = resolve(url)
            self.assertIsNotNone(resolved)
            # Should resolve to DQRunViewSet list action
            self.assertIn("list", resolved.url_name or "")
        except Resolver404 as e:
            self.fail(f"URL pattern did not resolve: {e}")

    def test_runs_detail_url_resolution(self):
        """Test that runs detail URL resolves correctly."""
        # Standardized pattern: /api/v1/dq/runs/{id}/
        url = f"/api/v1/dq/runs/{self.dq_run.id}/"

        try:
            resolved = resolve(url)
            self.assertIsNotNone(resolved)
            # Should resolve to DQRunViewSet detail action
            self.assertIn("detail", resolved.url_name or "")
            self.assertIn("id", resolved.kwargs)
            self.assertEqual(str(resolved.kwargs["id"]), str(self.dq_run.id))
        except Resolver404 as e:
            self.fail(f"URL pattern did not resolve: {e}")

    def test_runs_results_url_resolution(self):
        """Test that runs results URL resolves correctly."""
        # Standardized pattern: /api/v1/dq/runs/{id}/results/
        url = f"/api/v1/dq/runs/{self.dq_run.id}/results/"

        try:
            resolved = resolve(url)
            self.assertIsNotNone(resolved)
            # Should resolve to DQRunViewSet results action
            self.assertIn("results", resolved.url_name or "")
            self.assertIn("id", resolved.kwargs)
            self.assertEqual(str(resolved.kwargs["id"]), str(self.dq_run.id))
        except Resolver404 as e:
            self.fail(f"URL pattern did not resolve: {e}")

    def test_runs_list_reverse_lookup(self):
        """Test reverse lookup for runs list endpoint."""
        try:
            # Try to reverse using the standardized basename
            url = reverse("dq-run-list")
            self.assertEqual(url, "/api/v1/dq/runs/")
        except Exception as e:
            self.fail(f"Reverse lookup failed: {e}")

    def test_runs_detail_reverse_lookup(self):
        """Test reverse lookup for runs detail endpoint."""
        try:
            # Try to reverse using the standardized basename
            url = reverse("dq-run-detail", kwargs={"id": self.dq_run.id})
            self.assertEqual(url, f"/api/v1/dq/runs/{self.dq_run.id}/")
        except Exception as e:
            self.fail(f"Reverse lookup failed: {e}")

    def test_runs_results_reverse_lookup(self):
        """Test reverse lookup for runs results endpoint."""
        try:
            # Try to reverse using the standardized basename
            url = reverse("dq-run-results", kwargs={"id": self.dq_run.id})
            self.assertEqual(url, f"/api/v1/dq/runs/{self.dq_run.id}/results/")
        except Exception as e:
            self.fail(f"Reverse lookup failed: {e}")

    def test_no_duplicate_router_registration(self):
        """Test that there is no duplicate router registration."""
        from hub.apps.dq.urls import router

        # Check that router only has one registration for runs
        registrations = [reg for reg in router.registry if "run" in reg[0].lower()]

        # Should have exactly one registration
        self.assertEqual(
            len(registrations),
            1,
            f"Expected exactly one router registration, found {len(registrations)}",
        )

        # Should be registered as 'runs'
        prefix, _viewset, basename = registrations[0]
        self.assertEqual(prefix, "runs", f"Expected prefix 'runs', found '{prefix}'")
        self.assertEqual(basename, "dq-run", f"Expected basename 'dq-run', found '{basename}'")

    def test_no_duplicate_quality_router_registration(self):
        """Test that quality_router has exactly one registration."""
        from hub.apps.dq.urls import quality_router

        registrations = list(quality_router.registry)
        self.assertEqual(
            len(registrations),
            1,
            f"Expected exactly one quality router registration, "
            f"found {len(registrations)}",
        )
        prefix, _viewset, basename = registrations[0]
        self.assertEqual(prefix, "quality")
        self.assertEqual(basename, "dq-quality")

    def test_url_paths_follow_naming_standards(self):
        """Test that URL paths follow API naming standards by inspecting
        actual router registrations (not hardcoded strings)."""
        from hub.apps.dq.urls import router

        for prefix, _viewset, basename in router.registry:
            generated_url = reverse(f"{basename}-list")
            parts = [p for p in generated_url.split("/") if p]
            # Should contain 'dq' exactly once
            dq_count = parts.count("dq")
            self.assertEqual(
                dq_count,
                1,
                f"URL {generated_url} should contain 'dq' exactly once, "
                f"found {dq_count} times",
            )
            # Registered prefix should appear in the generated URL
            self.assertIn(
                prefix,
                parts,
                f"Registered prefix '{prefix}' should appear in "
                f"generated URL {generated_url}",
            )

    def test_runs_list_endpoint_accessible(self):
        """Test that runs list endpoint is accessible."""
        response = self.client.get("/api/v1/dq/runs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_runs_detail_endpoint_accessible(self):
        """Test that runs detail endpoint is accessible."""
        response = self.client.get(f"/api/v1/dq/runs/{self.dq_run.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_runs_results_endpoint_accessible(self):
        """Test that runs results endpoint is accessible."""
        response = self.client.get(f"/api/v1/dq/runs/{self.dq_run.id}/results/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class DQIntegrationTest(TestCase):
    """Integration tests for DQ endpoints using standardized URL patterns."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create file
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        # Authenticate
        self.client.force_authenticate(user=self.user)

    def test_create_dq_run_via_runs_endpoint(self):
        """Test creating DQ run via standardized runs endpoint."""
        # Use standardized URL pattern
        url = "/api/v1/dq/runs/"

        data = {
            "file_id": str(self.file.id),
            "profile_key": "intake_basic_gx",
            "engine": "GREAT_EXPECTATIONS",
        }

        response = self.client.post(url, data, format="json")

        # Must succeed with 201 — test data has all required fields
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Expected 201 CREATED, got {response.status_code}: {response.data}",
        )
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], "PENDING")

    def test_list_dq_runs_via_runs_endpoint(self):
        """Test listing DQ runs via standardized runs endpoint."""
        # Create some DQ runs
        for i in range(3):
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                resource_type="DQ_RUN",
                resource_id=uuid.uuid4(),
                created_by=self.user,
            )
            DQRun.objects.create(
                tenant=self.tenant,
                file=self.file,
                job=job,
                profile_key="intake_basic_gx",
                engine=DQEngine.GREAT_EXPECTATIONS,
                status=DQRunStatus.SUCCEEDED,
                overall_status="PASS",
                quality_score=95.0 + i,
            )

        # Use standardized URL pattern
        url = "/api/v1/dq/runs/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertGreaterEqual(len(response.data["results"]), 3)

    def test_retrieve_dq_run_via_runs_endpoint(self):
        """Test retrieving DQ run via standardized runs endpoint."""
        # Create DQ run
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.5,
        )

        # Use standardized URL pattern
        url = f"/api/v1/dq/runs/{dq_run.id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data["id"]), str(dq_run.id))
        self.assertEqual(response.data["overall_status"], "PASS")
        self.assertEqual(response.data["quality_score"], 95.5)

    def test_retrieve_dq_run_results_via_runs_endpoint(self):
        """Test retrieving DQ run results via standardized runs endpoint."""
        # Create DQ run with results
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.5,
            checks_json=[
                {"check_id": "test_check", "status": "PASS", "message": "Test check passed"}
            ],
        )

        # Use standardized URL pattern
        url = f"/api/v1/dq/runs/{dq_run.id}/results/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("dq_run_id", response.data)
        self.assertIn("overall_status", response.data)
        self.assertIn("quality_score", response.data)
        self.assertIn("checks", response.data)
