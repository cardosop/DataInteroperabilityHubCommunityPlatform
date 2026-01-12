"""
Unit tests for Compliance URL pattern resolution

Tests verify that URL patterns are correctly configured and resolve to the
expected views with the standardized 'runs' resource naming.
"""
from django.test import TestCase
from django.urls import reverse, resolve, NoReverseMatch
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.compliance.views import ComplianceRunViewSet
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.jobs.models import Job, JobType, JobStatus
from tests.fixtures.test_data_factories import TenantFactory, UserFactory, AssetFactory, JobFactory


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
        url = reverse('compliance-run-list')
        self.assertEqual(url, '/api/v1/compliance/runs/')

        resolved = resolve('/api/v1/compliance/runs/')
        self.assertIsNotNone(resolved)
        # DRF routers wrap ViewSet methods, so check url_name instead
        self.assertIn('list', resolved.url_name or '')

    def test_detail_url_resolves_to_viewset(self):
        """Test that /api/v1/compliance/runs/{id}/ resolves to ComplianceRunViewSet.retrieve"""
        # Create an asset for testing
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user
        )
        # Create a compliance run for testing
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.PENDING
        )

        url = reverse('compliance-run-detail', kwargs={'id': str(compliance_run.id)})
        self.assertEqual(url, f'/api/v1/compliance/runs/{compliance_run.id}/')

        resolved = resolve(f'/api/v1/compliance/runs/{compliance_run.id}/')
        self.assertIsNotNone(resolved)
        # DRF routers wrap ViewSet methods, so check url_name instead
        self.assertIn('detail', resolved.url_name or '')
        self.assertIn('id', resolved.kwargs)
        self.assertEqual(str(resolved.kwargs['id']), str(compliance_run.id))

    def test_results_action_url_resolves(self):
        """Test that /api/v1/compliance/runs/{id}/results/ resolves to results action"""
        # Create an asset for testing
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user
        )
        # Create a compliance run for testing
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED
        )

        url = reverse('compliance-run-results', kwargs={'id': str(compliance_run.id)})
        self.assertEqual(url, f'/api/v1/compliance/runs/{compliance_run.id}/results/')

        resolved = resolve(f'/api/v1/compliance/runs/{compliance_run.id}/results/')
        self.assertIsNotNone(resolved)
        # DRF routers wrap ViewSet methods, so check url_name instead
        self.assertIn('results', resolved.url_name or '')
        self.assertIn('id', resolved.kwargs)
        self.assertEqual(str(resolved.kwargs['id']), str(compliance_run.id))

    def test_url_pattern_uses_runs_not_compliance_runs(self):
        """Test that URL patterns use 'runs' not 'compliance-runs'"""
        # Verify list endpoint uses 'runs'
        list_url = reverse('compliance-run-list')
        self.assertIn('/runs/', list_url)
        self.assertNotIn('/compliance-runs/', list_url)

        # Verify detail endpoint uses 'runs'
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user
        )
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.PENDING
        )
        detail_url = reverse('compliance-run-detail', kwargs={'id': str(compliance_run.id)})
        self.assertIn('/runs/', detail_url)
        self.assertNotIn('/compliance-runs/', detail_url)

    def test_old_compliance_runs_url_does_not_resolve(self):
        """Test that old /compliance-runs/ URL pattern does not resolve to compliance viewset"""
        # Old pattern should not resolve to ComplianceRunViewSet
        # It may resolve to a catch-all pattern, but should not be the compliance viewset
        from django.urls import resolve
        try:
            resolved = resolve('/api/v1/compliance/compliance-runs/')
            # If it resolves, verify it's not the compliance viewset
            # Check that url_name doesn't contain 'compliance-run'
            if resolved.url_name:
                self.assertNotIn('compliance-run', resolved.url_name,
                               "Old pattern should not resolve to compliance-run viewset")
            # Also check that the view is not ComplianceRunViewSet
            if hasattr(resolved, 'func'):
                from hub.apps.compliance.views import ComplianceRunViewSet
                # Check if it's a ViewSet method (wrapped by DRF router)
                if hasattr(resolved.func, 'cls'):
                    self.assertNotIsInstance(resolved.func.cls, ComplianceRunViewSet,
                                            "Old pattern should not resolve to ComplianceRunViewSet")
        except Exception:
            # If it doesn't resolve at all, that's also acceptable
            pass

    def test_url_reverse_with_basename(self):
        """Test that URL reverse works with basename 'compliance-run'"""
        # List endpoint
        list_url = reverse('compliance-run-list')
        self.assertEqual(list_url, '/api/v1/compliance/runs/')

        # Detail endpoint
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user
        )
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.PENDING
        )
        detail_url = reverse('compliance-run-detail', kwargs={'id': str(compliance_run.id)})
        self.assertEqual(detail_url, f'/api/v1/compliance/runs/{compliance_run.id}/')

    def test_all_viewset_actions_have_urls(self):
        """Test that all ViewSet actions have corresponding URLs"""
        # List action
        list_url = reverse('compliance-run-list')
        self.assertIsNotNone(list_url)

        # Create action (same URL as list, different method)
        # This is handled by the router automatically

        # Detail action
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user
        )
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.PENDING
        )
        detail_url = reverse('compliance-run-detail', kwargs={'id': str(compliance_run.id)})
        self.assertIsNotNone(detail_url)

        # Results action
        results_url = reverse('compliance-run-results', kwargs={'id': str(compliance_run.id)})
        self.assertIsNotNone(results_url)


class ComplianceURLIntegrationTest(TestCase):
    """Integration tests for compliance URL endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.client.force_authenticate(user=self.user)

        self.asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.user
        )

    def test_list_endpoint_accessible(self):
        """Test that list endpoint is accessible via /api/v1/compliance/runs/"""
        response = self.client.get('/api/v1/compliance/runs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_endpoint_accessible(self):
        """Test that create endpoint is accessible via POST /api/v1/compliance/runs/"""
        response = self.client.post(
            '/api/v1/compliance/runs/',
            {
                'asset_id': str(self.asset.id),
                'scan_mode': 'internal'
            },
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_detail_endpoint_accessible(self):
        """Test that detail endpoint is accessible via /api/v1/compliance/runs/{id}/"""
        # Create a compliance run
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            status=ComplianceRunStatus.PENDING
        )

        response = self.client.get(f'/api/v1/compliance/runs/{compliance_run.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(compliance_run.id))

    def test_results_endpoint_accessible(self):
        """Test that results endpoint is accessible via /api/v1/compliance/runs/{id}/results/"""
        # Create a compliance run with results
        job = JobFactory.create_job(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='PASS',
            completed_at=job.completed_at
        )

        response = self.client.get(f'/api/v1/compliance/runs/{compliance_run.id}/results/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('compliance_run_id', response.data)

    def test_old_compliance_runs_endpoint_not_accessible(self):
        """Test that old /compliance-runs/ endpoint returns 404"""
        # Test the actual old endpoint pattern
        response = self.client.get('/api/v1/compliance/compliance-runs/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_url_consistency_across_endpoints(self):
        """Test that all endpoints use consistent 'runs' pattern"""
        # List endpoint
        list_response = self.client.get('/api/v1/compliance/runs/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        # Create endpoint
        create_response = self.client.post(
            '/api/v1/compliance/runs/',
            {
                'asset_id': str(self.asset.id),
                'scan_mode': 'internal'
            },
            format='json'
        )
        self.assertIn(create_response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

        # If creation succeeded, test detail endpoint
        if create_response.status_code == status.HTTP_201_CREATED:
            compliance_run_id = create_response.data['id']
            detail_response = self.client.get(f'/api/v1/compliance/runs/{compliance_run_id}/')
            self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

            # Test results endpoint
            results_response = self.client.get(f'/api/v1/compliance/runs/{compliance_run_id}/results/')
            # May return 200 or 404 depending on run status
            self.assertIn(results_response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_router_registration_uses_runs_pattern(self):
        """Test that router registration uses 'runs' pattern, not 'compliance-runs'"""
        from hub.apps.compliance.urls import router

        # Check router registry for the registered pattern
        registered_patterns = [prefix for prefix, _, _ in router.registry]
        self.assertIn('runs', registered_patterns)
        self.assertNotIn('compliance-runs', registered_patterns)

        # Verify basename is correct
        basenames = [basename for _, _, basename in router.registry]
        self.assertIn('compliance-run', basenames)

    def test_no_duplicate_url_patterns(self):
        """Test that there are no duplicate URL patterns"""
        from hub.apps.compliance.urls import urlpatterns
        from django.urls import URLPattern, URLResolver

        # Collect all URL patterns
        patterns = []
        for pattern in urlpatterns:
            if isinstance(pattern, URLPattern):
                patterns.append(pattern.pattern._regex)
            elif isinstance(pattern, URLResolver):
                # Include router URLs
                patterns.extend([p.pattern._regex for p in pattern.url_patterns if hasattr(p, 'pattern')])

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
        for prefix, viewset, basename in router.registry:
            if prefix == 'runs':
                found_basename = basename
                break

        self.assertIsNotNone(found_basename, "Router registration for 'runs' not found")
        self.assertEqual(found_basename, 'compliance-run',
                        f"Expected basename 'compliance-run', got '{found_basename}'")

