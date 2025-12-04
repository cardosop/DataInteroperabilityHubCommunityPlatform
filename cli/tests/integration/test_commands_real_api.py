"""
Integration tests for CLI commands using Django LiveServerTestCase.

These tests use Django's live test server, which starts automatically,
so they work without requiring a pre-running API service.

CRITICAL: To avoid transaction isolation issues with LiveServerTestCase,
all test data is created via HTTP requests to the live server. This ensures
the data is created through the server thread's database connection and is
immediately visible to subsequent CLI commands.
"""
import pytest
import requests
from click.testing import CliRunner
from django.test import LiveServerTestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from datahub_cli.main import cli
from datahub_cli.config import config
from datahub_cli.auth import auth_manager

from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestCLIIntegrationRealAPI(LiveServerTestCase):
    """
    Integration tests for CLI commands using Django's live test server.
    
    CRITICAL: All test data is created via HTTP requests to the live server
    to avoid transaction isolation issues. This ensures data is created
    through the server thread's database connection and is immediately visible.
    """
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.runner = CliRunner()
        
        # Create tenant (this is OK to create directly as it's needed for user creation)
        self.tenant = Tenant.objects.create(
            name="CLI Test Tenant",
            slug="cli-test-tenant"
        )
        
        # Create user with ACTIVE status (required for authentication)
        self.user = User.objects.create_user(
            email="cli-test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Set API base URL to live test server
        # LiveServerTestCase provides self.live_server_url automatically
        # Note: live_server_url is available after setUp() completes
        self.api_base_url = f'{self.live_server_url}/api/v1'
        config.set_api_base_url(self.api_base_url)
        
        # Create API key for testing (more reliable than login for tests)
        from hub.apps.auth.models import APIKey
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        api_key_obj = APIKey.objects.create(
            user=self.user,
            tenant=self.tenant,
            name="CLI Test Key",
            key_hash=key_hash
        )
        config.set_api_key(plaintext_key)
        self.api_key = plaintext_key
        self.authenticated = True
    
    def tearDown(self):
        """Clean up after tests"""
        super().tearDown()
        config.clear_auth()
    
    def _get_auth_headers(self):
        """Get authentication headers for HTTP requests"""
        return {
            'Authorization': f'ApiKey {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def _create_asset_via_api(self, key, name, description=None, domain=None, visibility='INTERNAL'):
        """
        Create an asset via HTTP request to the live server.
        
        This ensures the asset is created through the server thread's
        database connection and is immediately visible to CLI commands.
        
        Returns the created asset data as a dict.
        """
        # URL structure: /api/v1/assets/assets/ (assets/ from api/urls.py + assets from router)
        url = f'{self.api_base_url}/assets/assets/'
        data = {
            'key': key,
            'name': name,
            'visibility': visibility
        }
        if description:
            data['description'] = description
        if domain:
            data['domain'] = domain
        
        response = requests.post(url, json=data, headers=self._get_auth_headers())
        response.raise_for_status()
        return response.json()
    
    def _create_contract_via_api(self, asset_id, original_raw, original_format='JSON', original_spec_type='ODCS'):
        """
        Create a contract via HTTP request to the live server.
        
        Returns the created contract data as a dict.
        """
        # URL structure: /api/v1/contracts/contracts/ (contracts/ from api/urls.py + contracts from router)
        url = f'{self.api_base_url}/contracts/contracts/'
        data = {
            'asset_id': asset_id,
            'original_raw': original_raw,
            'original_format': original_format,
            'original_spec_type': original_spec_type
        }
        
        response = requests.post(url, json=data, headers=self._get_auth_headers())
        response.raise_for_status()
        return response.json()
    
    def _create_file_via_api(self, name, content_type='text/csv', size=None):
        """
        Initialize a file upload via HTTP request to the live server.
        
        Returns the file initialization data as a dict.
        """
        # URL structure: /api/v1/files/files/init/ (files/ from api/urls.py + files from router + init action)
        url = f'{self.api_base_url}/files/files/init/'
        data = {
            'name': name,
            'content_type': content_type
        }
        if size is not None:
            data['size'] = size
        
        response = requests.post(url, json=data, headers=self._get_auth_headers())
        response.raise_for_status()
        return response.json()
    
    def _create_job_via_api(self, job_type, resource_type='ASSET', resource_id=None):
        """
        Create a job via HTTP request to the live server.
        
        Args:
            job_type: Job type (e.g., 'DQ_RUN', 'COMPLIANCE_RUN')
            resource_type: Resource type (e.g., 'ASSET', 'CONTRACT', 'FILE', 'DATASET')
            resource_id: UUID of the resource (required)
        
        Returns the created job data as a dict.
        """
        # URL structure: /api/v1/jobs/jobs/ (jobs/ from api/urls.py + jobs from router)
        url = f'{self.api_base_url}/jobs/jobs/'
        
        if not resource_id:
            raise ValueError("resource_id must be provided")
        
        # JobCreateSerializer requires: type, resource_type, resource_id
        data = {
            'type': job_type,  # Note: API expects 'type', not 'job_type'
            'resource_type': resource_type,
            'resource_id': str(resource_id)  # Must be UUID string
        }
        
        response = requests.post(url, json=data, headers=self._get_auth_headers())
        response.raise_for_status()
        return response.json()
    
    def test_assets_list_real_api(self):
        """Test assets list command with real API"""
        # Ensure config is set correctly for this test
        config.set_api_base_url(self.api_base_url)
        
        # Create asset via HTTP request to live server
        # This ensures the asset is created through the server thread's connection
        asset_data = self._create_asset_via_api(
            key='cli-test-asset',
            name='CLI Test Asset',
            description='Test asset created via API'
        )
        
        # Verify asset was created
        assert asset_data['key'] == 'cli-test-asset'
        assert asset_data['name'] == 'CLI Test Asset'
        
        # Now list assets via CLI - they should be visible since they were created via the API
        result = self.runner.invoke(cli, ['assets', 'list'])
        if result.exit_code != 0:
            print(f"CLI Error: {result.output}")
            print(f"Exception: {result.exception}")
        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        assert 'CLI Test Asset' in result.output or 'cli-test-asset' in result.output, \
            f"Asset not found in output: {result.output}"
    
    def test_assets_get_real_api(self):
        """Test assets get command with real API"""
        # Create test asset via HTTP request to live server
        asset_data = self._create_asset_via_api(
            key='cli-test-asset-2',
            name='CLI Test Asset 2',
            description='Test asset for get command'
        )
        
        result = self.runner.invoke(cli, ['assets', 'get', asset_data['id']])
        assert result.exit_code == 0
        assert 'CLI Test Asset 2' in result.output or 'cli-test-asset-2' in result.output
    
    def test_assets_create_real_api(self):
        """Test assets create command with real API"""
        result = self.runner.invoke(cli, [
            'assets', 'create',
            '--name', 'CLI Created Asset',
            '--key', 'cli-created-asset',
            '--description', 'Created via CLI'
        ])
        assert result.exit_code == 0
        assert 'created successfully' in result.output.lower()
        
        # Verify asset was created
        assert Asset.objects.filter(key='cli-created-asset', tenant=self.tenant).exists()
    
    def test_contracts_list_real_api(self):
        """Test contracts list command with real API"""
        # Create test contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_format='YAML',
            original_raw='test: contract',
            created_by=self.user
        )
        
        result = self.runner.invoke(cli, ['contracts', 'list'])
        assert result.exit_code == 0
    
    def test_contracts_get_real_api(self):
        """Test contracts get command with real API"""
        # First create an asset (required for contract)
        asset_data = self._create_asset_via_api(
            key='cli-test-asset-for-contract-2',
            name='CLI Test Asset for Contract 2'
        )
        
        # Create test contract via HTTP request to live server
        contract_data = self._create_contract_via_api(
            asset_id=asset_data['id'],
            original_raw='test: contract for get',
            original_format='YAML',
            original_spec_type='ODCS'
        )
        
        result = self.runner.invoke(cli, ['contracts', 'get', contract_data['id']])
        assert result.exit_code == 0
    
    def test_files_list_real_api(self):
        """Test files list command with real API"""
        # Create test file via HTTP request to live server
        file_data = self._create_file_via_api(
            name='cli-test.csv',
            content_type='text/csv',
            size=1024
        )
        
        result = self.runner.invoke(cli, ['files', 'list'])
        assert result.exit_code == 0
    
    def test_jobs_list_real_api(self):
        """Test jobs list command with real API"""
        # Create test job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type='DATASET',
            resource_id='123e4567-e89b-12d3-a456-426614174000',
            created_by=self.user
        )
        
        result = self.runner.invoke(cli, ['jobs', 'list'])
        assert result.exit_code == 0
    
    def test_jobs_get_real_api(self):
        """Test jobs get command with real API"""
        # First create an asset (required for job)
        asset_data = self._create_asset_via_api(
            key='cli-test-asset-for-job-2',
            name='CLI Test Asset for Job 2'
        )
        
        # Create test job via HTTP request to live server
        # Job requires: type, resource_type, resource_id
        job_data = self._create_job_via_api(
            job_type='DQ_RUN',
            resource_type='ASSET',
            resource_id=asset_data['id']
        )
        
        result = self.runner.invoke(cli, ['jobs', 'get', job_data['id']])
        assert result.exit_code == 0
    
    def test_config_commands(self):
        """Test config commands (no API needed)"""
        # Test config get
        result = self.runner.invoke(cli, ['config', 'get', 'api_base_url'])
        assert result.exit_code == 0
        
        # Test config set
        result = self.runner.invoke(cli, ['config', 'set', 'test_key', 'test_value'])
        assert result.exit_code == 0
        assert config.get('test_key') == 'test_value'

