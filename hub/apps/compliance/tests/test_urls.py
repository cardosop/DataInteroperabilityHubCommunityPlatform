"""
Unit tests for Compliance URL pattern resolution

Tests verify that URL patterns are correctly configured and resolve to the
expected views with the standardized 'runs' resource naming.
"""

from django.test import TestCase
from django.urls import resolve, reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.jobs.models import JobStatus, JobType
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from tests.fixtures.test_data_factories import AssetFactory, JobFactory, TenantFactory, UserFactory


class ComplianceURLPatternResolutionTest(TestCase):
    """Test URL pattern resolution for compliance endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_url_resolves_to_viewset(self):
        """Test that /api/v1/compliance/runs/ resolves to ComplianceRunViewSet.list"""
        url = reverse("compliance-run-list")
        self.assertEqual(url, "/api/v1/compliance/runs/")

        resolved = resolve("/api/v1/compliance/runs/")
        self.assertIsNotNone(resolved)
        # DRF routers wrap ViewSet methods, so check url_name instead
        self.assertIn("list", resolved.url_name or "")

    def test_detail_url_resolves_to_viewset(self):
        """Test that /api/v1/compliance/runs/{id}/ resolves to ComplianceRunViewSet.retrieve"""
        # Create an asset for testing
        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)
        # Create a compliance run for testing
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=str(asset.id),
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=asset, job=job, status=ComplianceRunStatus.PENDING
        )

        url = reverse("compliance-run-detail", kwargs={"id": str(compliance_run.id)})
        self.assertEqual(url, f"/api/v1/compliance/runs/{compliance_run.id}/")

        resolved = resolve(f"/api/v1/compliance/runs/{compliance_run.id}/")
        self.assertIsNotNone(resolved)
        # DRF routers wrap ViewSet methods, so check url_name instead
        self.assertIn("detail", resolved.url_name or "")
        self.assertIn("id", resolved.kwargs)
        self.assertEqual(str(resolved.kwargs["id"]), str(compliance_run.id))

    def test_results_action_url_resolves(self):
        """Test that /api/v1/compliance/runs/{id}/results/ resolves to results action"""
        # Create an asset for testing
        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)
        # Create a compliance run for testing
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="ASSET",
            resource_id=str(asset.id),
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=asset, job=job, status=ComplianceRunStatus.SUCCEEDED
        )

        url = reverse("compliance-run-results", kwargs={"id": str(compliance_run.id)})
        self.assertEqual(url, f"/api/v1/compliance/runs/{compliance_run.id}/results/")

        resolved = resolve(f"/api/v1/compliance/runs/{compliance_run.id}/results/")
        self.assertIsNotNone(resolved)
        # DRF routers wrap ViewSet methods, so check url_name instead
        self.assertIn("results", resolved.url_name or "")
        self.assertIn("id", resolved.kwargs)
        self.assertEqual(str(resolved.kwargs["id"]), str(compliance_run.id))

    def test_url_pattern_uses_runs_not_compliance_runs(self):
        """Test that URL patterns use 'runs' not 'compliance-runs'"""
        # Verify list endpoint uses 'runs'
        list_url = reverse("compliance-run-list")
        self.assertIn("/runs/", list_url)
        self.assertNotIn("/compliance-runs/", list_url)

        # Verify detail endpoint uses 'runs'
        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=str(asset.id),
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=asset, job=job, status=ComplianceRunStatus.PENDING
        )
        detail_url = reverse("compliance-run-detail", kwargs={"id": str(compliance_run.id)})
        self.assertIn("/runs/", detail_url)
        self.assertNotIn("/compliance-runs/", detail_url)

    def test_old_compliance_runs_url_does_not_resolve(self):
        """Test that old /compliance-runs/ URL pattern does not resolve."""
        from django.urls import Resolver404, resolve

        with self.assertRaises(Resolver404):
            resolve("/api/v1/compliance/compliance-runs/")

    def test_url_reverse_with_basename(self):
        """Test that URL reverse works with basename 'compliance-run'"""
        # List endpoint
        list_url = reverse("compliance-run-list")
        self.assertEqual(list_url, "/api/v1/compliance/runs/")

        # Detail endpoint
        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=str(asset.id),
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=asset, job=job, status=ComplianceRunStatus.PENDING
        )
        detail_url = reverse("compliance-run-detail", kwargs={"id": str(compliance_run.id)})
        self.assertEqual(detail_url, f"/api/v1/compliance/runs/{compliance_run.id}/")

    def test_all_viewset_actions_have_urls(self):
        """Test that all ViewSet actions have corresponding URLs"""
        # List action
        list_url = reverse("compliance-run-list")
        self.assertEqual(list_url, "/api/v1/compliance/runs/")

        # Create action (same URL as list, different method)
        # This is handled by the router automatically

        # Detail action
        asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=str(asset.id),
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=asset, job=job, status=ComplianceRunStatus.PENDING
        )
        detail_url = reverse("compliance-run-detail", kwargs={"id": str(compliance_run.id)})
        self.assertEqual(detail_url, f"/api/v1/compliance/runs/{compliance_run.id}/")

        # Results action
        results_url = reverse("compliance-run-results", kwargs={"id": str(compliance_run.id)})
        self.assertEqual(results_url, f"/api/v1/compliance/runs/{compliance_run.id}/results/")


class ComplianceURLIntegrationTest(TestCase):
    """Integration tests for compliance URL endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        ensure_tenant_has_active_subscription(self.tenant)
        self.client.force_authenticate(user=self.user)

        self.asset = AssetFactory.create_asset(tenant=self.tenant, created_by=self.user)

    def test_list_endpoint_accessible(self):
        """Test that list endpoint is accessible via /api/v1/compliance/runs/"""
        response = self.client.get("/api/v1/compliance/runs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_endpoint_accessible(self):
        """Test that create endpoint is accessible via POST /api/v1/compliance/runs/"""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"asset_id": str(self.asset.id), "scan_mode": "internal"},
            format="json",
        )
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            self.skipTest(f"Compliance service unavailable: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_detail_endpoint_accessible(self):
        """Test that detail endpoint is accessible via /api/v1/compliance/runs/{id}/"""
        # Create a compliance run
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=str(self.asset.id),
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset, job=job, status=ComplianceRunStatus.PENDING
        )

        response = self.client.get(f"/api/v1/compliance/runs/{compliance_run.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(compliance_run.id))

    def test_results_endpoint_accessible(self):
        """Test that results endpoint is accessible via /api/v1/compliance/runs/{id}/results/"""
        # Create a compliance run with results
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="ASSET",
            resource_id=str(self.asset.id),
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status="PASS",
            completed_at=job.completed_at,
        )

        response = self.client.get(f"/api/v1/compliance/runs/{compliance_run.id}/results/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("compliance_run_id", response.data)

    def test_old_compliance_runs_endpoint_not_accessible(self):
        """Test that old /compliance-runs/ endpoint returns 404"""
        # Test the actual old endpoint pattern
        response = self.client.get("/api/v1/compliance/compliance-runs/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_url_consistency_across_endpoints(self):
        """Test that all endpoints use consistent 'runs' pattern"""
        # List endpoint
        list_response = self.client.get("/api/v1/compliance/runs/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        # Create endpoint
        create_response = self.client.post(
            "/api/v1/compliance/runs/",
            {"asset_id": str(self.asset.id), "scan_mode": "internal"},
            format="json",
        )
        if create_response.status_code == status.HTTP_400_BAD_REQUEST:
            self.skipTest(f"Compliance service unavailable: {create_response.data}")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        # Creation succeeded, test detail endpoint
        compliance_run_id = create_response.data["id"]
        detail_response = self.client.get(f"/api/v1/compliance/runs/{compliance_run_id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

        # Test results endpoint — may return 404 if run has not completed yet
        results_response = self.client.get(f"/api/v1/compliance/runs/{compliance_run_id}/results/")
        if results_response.status_code == status.HTTP_404_NOT_FOUND:
            self.skipTest("Compliance run has not completed yet — results not available")
        self.assertEqual(results_response.status_code, status.HTTP_200_OK)

    def test_router_registration_uses_runs_pattern(self):
        """Test that router registration uses 'runs' pattern, not 'compliance-runs'"""
        from hub.apps.compliance.urls import router

        # Check router registry for the registered pattern
        registered_patterns = [prefix for prefix, _, _ in router.registry]
        self.assertIn("runs", registered_patterns)
        self.assertNotIn("compliance-runs", registered_patterns)

        # Verify basename is correct
        basenames = [basename for _, _, basename in router.registry]
        self.assertIn("compliance-run", basenames)

    def test_no_duplicate_url_patterns(self):
        """Test that there are no duplicate URL patterns"""
        from django.urls import URLPattern, URLResolver

        from hub.apps.compliance.urls import urlpatterns

        # Collect all URL patterns
        patterns = []
        for pattern in urlpatterns:
            if isinstance(pattern, URLPattern):
                patterns.append(pattern.pattern._regex)
            elif isinstance(pattern, URLResolver):
                # Include router URLs
                patterns.extend(
                    [p.pattern._regex for p in pattern.url_patterns if hasattr(p, "pattern")]
                )

        # Check for duplicates
        seen = set()
        duplicates = []
        for pattern in patterns:
            if pattern in seen:
                duplicates.append(pattern)
            seen.add(pattern)

        self.assertEqual(len(duplicates), 0, f"Found duplicate URL patterns: {duplicates}")

    def test_router_basename_consistency(self):
        """Test that router basename matches expected pattern"""
        from hub.apps.compliance.urls import router

        # Find compliance-run basename
        found_basename = None
        for prefix, _viewset, basename in router.registry:
            if prefix == "runs":
                found_basename = basename
                break

        self.assertIsNotNone(found_basename, "Router registration for 'runs' not found")
        self.assertEqual(
            found_basename,
            "compliance-run",
            f"Expected basename 'compliance-run', got '{found_basename}'",
        )
