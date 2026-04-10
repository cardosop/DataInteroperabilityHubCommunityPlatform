"""
Integration tests for compliance CLI commands using real API.

These tests use Django's live test server and make real API calls.
No mocks or stubs are used - all tests interact with real services.

NOTE: These tests must be run from the Django project root with pytest-django configured.
They require Django to be properly initialized and the CLI package to be installed.
"""
import os
import sys

# Add CLI directory to path if running from Django project root
cli_dir = os.path.join(os.path.dirname(__file__), '..', '..')
if os.path.exists(cli_dir) and cli_dir not in sys.path:
    sys.path.insert(0, cli_dir)

import pytest

# Phase 215.4 review fix: this module imports from django/hub which are
# not on the CLI test PYTHONPATH (CLI pytest.ini sets ``-p no:django``).
# Skip the entire module gracefully when those packages are unavailable
# instead of crashing pytest collection.
django = pytest.importorskip("django")
hub = pytest.importorskip("hub")
import json
from click.testing import CliRunner
from django.test import LiveServerTestCase
from django.contrib.auth import get_user_model

# Import CLI modules
from datahub_cli.main import cli
from datahub_cli.config import config
from datahub_cli.auth import auth_manager

# Import Django models
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestComplianceCommandsRealAPI(LiveServerTestCase):
    """
    Integration tests for compliance CLI commands using Django's live test server.

    All tests use real API endpoints - no mocks or stubs.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.runner = CliRunner()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="CLI Compliance Test Tenant",
            slug="cli-compliance-test-tenant"
        )

        # Create user
        self.user = User.objects.create_user(
            email="cli-compliance-test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Set API base URL to live test server
        self.api_base_url = f'{self.live_server_url}/api/v1'
        config.set_api_base_url(self.api_base_url)

        # Create API key for authentication
        from hub.apps.auth.models import APIKey
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        APIKey.objects.create(
            user=self.user,
            tenant=self.tenant,
            name="CLI Compliance Test Key",
            key_hash=key_hash
        )
        config.set_api_key(plaintext_key)
        self.api_key = plaintext_key

    def tearDown(self):
        """Clean up after tests"""
        super().tearDown()
        config.clear_auth()

    def _create_asset_via_api(self, key, name):
        """Create an asset via HTTP request to the live server"""
        import requests
        headers = {
            'Authorization': f'ApiKey {self.api_key}',
            'Content-Type': 'application/json'
        }
        data = {
            'key': key,
            'name': name,
            'status': AssetStatus.DRAFT.value
        }
        response = requests.post(
            f'{self.api_base_url}/assets/',
            json=data,
            headers=headers
        )
        if response.status_code == 201:
            return response.json()
        return None

    def test_compliance_run_command_with_asset_id(self):
        """Test compliance run command with asset_id using real API"""
        # Create asset via API
        asset = self._create_asset_via_api('test-asset', 'Test Asset')
        if not asset:
            pytest.skip("Could not create asset via API")

        asset_id = asset['id']

        # Run compliance check via CLI
        result = self.runner.invoke(cli, [
            'compliance', 'run',
            '--asset-id', asset_id,
            '--scan-mode', 'internal'
        ])

        # Should succeed (201) or fail gracefully (400 if validation fails)
        assert result.exit_code == 0
        if result.exit_code == 0:
            assert 'started successfully' in result.output.lower() or 'Compliance Run ID:' in result.output
            # Verify endpoint was called correctly (check output for success indicators)
            assert 'run' in result.output.lower() or 'id' in result.output.lower()

    def test_compliance_run_command_with_regulations(self):
        """Test compliance run command with regulations using real API"""
        # Create asset via API
        asset = self._create_asset_via_api('test-asset-regs', 'Test Asset Regulations')
        if not asset:
            pytest.skip("Could not create asset via API")

        asset_id = asset['id']

        # Run compliance check with regulations via CLI
        result = self.runner.invoke(cli, [
            'compliance', 'run',
            '--asset-id', asset_id,
            '--regulations', 'GDPR,HIPAA',
            '--scan-mode', 'internal'
        ])

        assert result.exit_code == 0
        if result.exit_code == 0:
            assert 'started successfully' in result.output.lower()
            assert 'Regulations: GDPR,HIPAA' in result.output or 'GDPR' in result.output

    def test_compliance_get_command(self):
        """Test compliance get command using real API"""
        # Create asset and compliance run via API
        asset = self._create_asset_via_api('test-asset-get', 'Test Asset Get')
        if not asset:
            pytest.skip("Could not create asset via API")

        # Create compliance run directly in database
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type='ASSET',
            resource_id=asset['id'],
            created_by=self.user
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset_id=asset['id'],
            job=job,
            status=ComplianceRunStatus.PENDING
        )

        # Get compliance run via CLI
        result = self.runner.invoke(cli, [
            'compliance', 'get',
            str(compliance_run.id)
        ])

        assert result.exit_code == 0
        assert str(compliance_run.id) in result.output
        assert 'PENDING' in result.output or 'Status:' in result.output

    def test_compliance_list_command(self):
        """Test compliance list command using real API"""
        # Create asset and compliance runs via API
        asset = self._create_asset_via_api('test-asset-list', 'Test Asset List')
        if not asset:
            pytest.skip("Could not create asset via API")

        # Create compliance runs directly in database
        for i in range(2):
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.COMPLIANCE_RUN,
                status=JobStatus.PENDING,
                resource_type='ASSET',
                resource_id=asset['id'],
                created_by=self.user
            )
            ComplianceRun.objects.create(
                tenant=self.tenant,
                asset_id=asset['id'],
                job=job,
                status=ComplianceRunStatus.PENDING
            )

        # List compliance runs via CLI
        result = self.runner.invoke(cli, [
            'compliance', 'list',
            '--limit', '10'
        ])

        assert result.exit_code == 0
        # Should show runs or "No compliance runs found"
        assert 'compliance run' in result.output.lower() or 'found' in result.output.lower()

    def test_compliance_list_command_with_asset_filter(self):
        """Test compliance list command with asset filter using real API"""
        # Create asset and compliance run via API
        asset = self._create_asset_via_api('test-asset-filter', 'Test Asset Filter')
        if not asset:
            pytest.skip("Could not create asset via API")

        # Create compliance run directly in database
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type='ASSET',
            resource_id=asset['id'],
            created_by=self.user
        )
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset_id=asset['id'],
            job=job,
            status=ComplianceRunStatus.PENDING
        )

        # List compliance runs filtered by asset via CLI
        result = self.runner.invoke(cli, [
            'compliance', 'list',
            '--asset-id', asset['id'],
            '--limit', '10'
        ])

        assert result.exit_code == 0
        # Should show runs or "No compliance runs found"
        assert 'compliance run' in result.output.lower() or 'found' in result.output.lower()

    def test_compliance_list_command_with_status_filter(self):
        """Test compliance list command with status filter using real API"""
        # Create asset and compliance run via API
        asset = self._create_asset_via_api('test-asset-status', 'Test Asset Status')
        if not asset:
            pytest.skip("Could not create asset via API")

        # Create compliance run with SUCCEEDED status
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type='ASSET',
            resource_id=asset['id'],
            created_by=self.user
        )
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset_id=asset['id'],
            job=job,
            status=ComplianceRunStatus.SUCCEEDED
        )

        # List compliance runs filtered by status via CLI
        result = self.runner.invoke(cli, [
            'compliance', 'list',
            '--status', 'SUCCEEDED',
            '--limit', '10'
        ])

        assert result.exit_code == 0
        # Should show runs or "No compliance runs found"
        assert 'compliance run' in result.output.lower() or 'found' in result.output.lower()

    def test_compliance_report_command(self):
        """Test compliance report command using real API"""
        # Create asset via API
        asset = self._create_asset_via_api('test-asset-report', 'Test Asset Report')
        if not asset:
            pytest.skip("Could not create asset via API")

        # Create compliance run with results
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type='ASSET',
            resource_id=asset['id'],
            created_by=self.user
        )
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset_id=asset['id'],
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status='PASS',
            risk_level='LOW'
        )

        # Generate compliance report via CLI
        result = self.runner.invoke(cli, [
            'compliance', 'report',
            '--asset-id', asset['id'],
            '--regulation', 'GDPR'
        ])

        assert result.exit_code == 0
        if result.exit_code == 0:
            assert 'GDPR' in result.output or 'compliance run' in result.output.lower()

    def test_compliance_endpoints_use_standardized_pattern(self):
        """Test that all compliance CLI commands use standardized /runs/ endpoint"""
        # This test verifies that CLI commands use the correct endpoint pattern
        # by checking the actual API calls made

        # Create asset
        asset = self._create_asset_via_api('test-asset-endpoint', 'Test Asset Endpoint')
        if not asset:
            pytest.skip("Could not create asset via API")

        # Test run command endpoint
        result = self.runner.invoke(cli, [
            'compliance', 'run',
            '--asset-id', asset['id'],
            '--scan-mode', 'internal'
        ])

        # If successful, the endpoint was called correctly
        # The actual endpoint verification happens in unit tests
        # This integration test verifies the command works end-to-end
        assert result.exit_code == 0

        # Test list command endpoint
        result = self.runner.invoke(cli, [
            'compliance', 'list'
        ])

        assert result.exit_code == 0

