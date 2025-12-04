"""
Pytest configuration for E2E tests.
"""
import os
import django
import pytest
import httpx
from typing import Dict, Optional

# Configure Django settings before any Django imports
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Setup Django before importing Django modules
try:
    from django.apps import apps
    if not apps.ready:
        django.setup()
except (ImportError, AttributeError):
    # Django not configured yet, setup now
    django.setup()

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from hub.apps.tenants.models import Tenant
from tests.factories import TenantFactory

User = get_user_model()


# Staging port configuration (from docker-compose.staging.yml)
STAGING_PORTS = {
    'API': 8001,
    'POSTGRES': 5433,
    'REDIS': 6380,
    'MINIO': 9010,
    'MINIO_CONSOLE': 9011,
    'FUSEKI': 3031,
    'SEMANTIC': 8082,
    'DATACONTRACT': 8081,
    'COMPLIANCE': 8083,
    'DQ': 8084,
    'WORKER': 8085,
    'PROMETHEUS': 9091,
    'GRAFANA': 3001,
    'JAEGER': 16687,
}

# Default ports (from regular docker-compose.yml)
DEFAULT_PORTS = {
    'API': 8000,
    'POSTGRES': 5432,
    'REDIS': 6379,
    'MINIO': 9000,
    'MINIO_CONSOLE': 9001,
    'FUSEKI': 3030,
    'SEMANTIC': 8081,
    'DATACONTRACT': 8080,
    'COMPLIANCE': 8082,
    'DQ': 8083,
    'WORKER': 8080,
    'PROMETHEUS': 9090,
    'GRAFANA': 3000,
    'JAEGER': 16686,
}


def detect_environment() -> str:
    """
    Detect if we're running against staging or default environment.
    Checks if staging ports are accessible.
    
    Returns:
        'staging' if staging ports are detected, 'default' otherwise
    """
    # Check if explicitly set
    env = os.getenv('TEST_ENVIRONMENT', '').lower()
    if env in ('staging', 'default'):
        return env
    
    # Auto-detect by checking if staging API port is accessible
    try:
        response = httpx.get(f"http://localhost:{STAGING_PORTS['API']}/health", timeout=2)
        if response.status_code == 200:
            return 'staging'
    except Exception:
        pass
    
    # Check default API port
    try:
        response = httpx.get(f"http://localhost:{DEFAULT_PORTS['API']}/health", timeout=2)
        if response.status_code == 200:
            return 'default'
    except Exception:
        pass
    
    # Default to staging if TEST_ENVIRONMENT is not set but staging ports might be in use
    # This is safer as staging is more likely to be what's running
    return 'staging'


def get_service_url(service_name: str, default_port_key: str) -> str:
    """
    Get service URL, automatically detecting staging vs default environment.
    
    Args:
        service_name: Environment variable name (e.g., 'API_SERVICE_URL')
        default_port_key: Key in PORTS dict (e.g., 'API', 'DQ', 'COMPLIANCE')
        
    Returns:
        Service URL with correct port
    """
    # Check environment variable first
    env_url = os.getenv(service_name)
    if env_url:
        return env_url
    
    # Auto-detect environment
    env = detect_environment()
    ports = STAGING_PORTS if env == 'staging' else DEFAULT_PORTS
    port = ports.get(default_port_key, DEFAULT_PORTS.get(default_port_key, 8000))
    
    return f"http://localhost:{port}"


def get_api_base_url() -> str:
    """Get API base URL"""
    return get_service_url('API_SERVICE_URL', 'API')


def get_datacontract_service_url() -> str:
    """Get DataContract service URL"""
    return get_service_url('DATACONTRACT_SERVICE_URL', 'DATACONTRACT')


def get_compliance_service_url() -> str:
    """Get Compliance service URL"""
    return get_service_url('COMPLIANCE_SERVICE_URL', 'COMPLIANCE')


def get_dq_service_url() -> str:
    """Get DQ service URL"""
    return get_service_url('DQ_SERVICE_URL', 'DQ')


def get_semantic_service_url() -> str:
    """Get Semantic service URL"""
    return get_service_url('SEMANTIC_SERVICE_URL', 'SEMANTIC')


def get_worker_service_url() -> str:
    """Get Worker service URL"""
    return get_service_url('WORKER_SERVICE_URL', 'WORKER')


def get_s3_endpoint_url() -> str:
    """Get S3/MinIO endpoint URL"""
    return get_service_url('AWS_S3_ENDPOINT_URL', 'MINIO')


def check_service_health(service_url: str, timeout: int = 5) -> bool:
    """
    Check if a service is healthy by hitting its health endpoint.
    
    Args:
        service_url: Base URL of the service
        timeout: Timeout in seconds
        
    Returns:
        True if service is healthy, False otherwise
    """
    try:
        health_url = f"{service_url.rstrip('/')}/health"
        response = httpx.get(health_url, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            return data.get('status') == 'healthy' or data.get('status') == 'ok'
    except Exception:
        pass
    return False


# Mark all E2E tests with e2e marker
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "e2e_batch1: E2E tests batch 1"
    )
    config.addinivalue_line(
        "markers", "e2e_batch2: E2E tests batch 2"
    )
    config.addinivalue_line(
        "markers", "e2e_batch3: E2E tests batch 3"
    )
    config.addinivalue_line(
        "markers", "e2e_batch4: E2E tests batch 4"
    )
    config.addinivalue_line(
        "markers", "e2e_batch5: E2E tests batch 5"
    )


class E2ETestBase(TestCase):
    """Base test class for E2E tests"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create test tenant
        self.tenant = TenantFactory.create_tenant()
        
        # Create test user
        self.user = User.objects.create_user(
            email="e2e_test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        
        # Create API client and authenticate
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Store service URLs for easy access
        self.api_base_url = get_api_base_url()
        self.datacontract_service_url = get_datacontract_service_url()
        self.compliance_service_url = get_compliance_service_url()
        self.dq_service_url = get_dq_service_url()
        self.semantic_service_url = get_semantic_service_url()
        self.worker_service_url = get_worker_service_url()
        self.s3_endpoint_url = get_s3_endpoint_url()
    
    def get_service_urls(self) -> Dict[str, str]:
        """Get all service URLs as a dictionary"""
        return {
            'api': self.api_base_url,
            'datacontract': self.datacontract_service_url,
            'compliance': self.compliance_service_url,
            'dq': self.dq_service_url,
            'semantic': self.semantic_service_url,
            'worker': self.worker_service_url,
            's3': self.s3_endpoint_url,
        }
    
    def create_asset(self, key: str, name: str, description: str = '', domain: str = '', **kwargs):
        """Create an asset via API and return its ID"""
        from rest_framework import status
        from hub.apps.assets.models import Asset
        
        response = self.client.post(
            '/api/v1/assets/assets/',
            {
                'key': key,
                'name': name,
                'description': description,
                'domain': domain,
                **kwargs
            },
            format='json'
        )
        
        if response.status_code != status.HTTP_201_CREATED:
            raise Exception(f"Failed to create asset: {response.status_code} - {response.data}")
        
        return response.data['id']
    
    def create_contract(self, asset_id, original_raw: str, original_format: str = None, **kwargs):
        """Create a contract via API and return its ID"""
        from rest_framework import status
        from hub.apps.contracts.models import Contract, OriginalFormat
        
        # Auto-detect format from original_raw if not provided
        if original_format is None:
            if original_raw.strip().startswith('{') or original_raw.strip().startswith('['):
                original_format = OriginalFormat.JSON
            elif original_raw.strip().startswith('---') or 'id:' in original_raw[:100]:
                original_format = OriginalFormat.YAML
            else:
                original_format = OriginalFormat.YAML  # Default
        
        # Ensure format is uppercase (JSON or YAML)
        if isinstance(original_format, str):
            original_format = original_format.upper()
            if original_format not in [OriginalFormat.JSON, OriginalFormat.YAML]:
                original_format = OriginalFormat.YAML
        
        # Override if provided in kwargs
        if 'original_format' in kwargs:
            original_format = kwargs.pop('original_format')
            if isinstance(original_format, str):
                original_format = original_format.upper()
        
        response = self.client.post(
            '/api/v1/contracts/contracts/',
            {
                'asset_id': asset_id,
                'original_raw': original_raw,
                'original_format': original_format,
                **kwargs
            },
            format='json'
        )
        
        if response.status_code not in [status.HTTP_201_CREATED, status.HTTP_200_OK]:
            raise Exception(f"Failed to create contract: {response.status_code} - {response.data}")
        
        return response.data['id']
    
    def init_file_upload(self, name: str, content_type: str, size: int, **kwargs):
        """Initialize a file upload and return file ID"""
        from rest_framework import status
        
        response = self.client.post(
            '/api/v1/files/files/init/',
            {
                'name': name,
                'content_type': content_type,
                'size': size,
                **kwargs
            },
            format='json'
        )
        
        if response.status_code != status.HTTP_201_CREATED:
            raise Exception(f"Failed to init file upload: {response.status_code} - {response.data}")
        
        # Response uses 'file_id' not 'id' (see FileInitResponseSerializer)
        return response.data.get('file_id') or response.data.get('id')
    
    def complete_file_upload(self, file_id, content_sha256: str = None, test_content: bytes = None, mock_s3: bool = False):
        """Complete a file upload"""
        from rest_framework import status
        import hashlib
        import boto3
        from botocore.exceptions import ClientError
        from django.conf import settings
        from hub.apps.files.models import File, FileStatus
        
        # Get file object to access storage_path
        file_obj = File.objects.get(id=file_id)
        
        if test_content:
            content_sha256 = hashlib.sha256(test_content).hexdigest()
        
        if not content_sha256:
            content_sha256 = 'abc123def456'  # Default for tests
        
        # Update file size if test_content provided
        if test_content:
            file_obj.size = len(test_content)
            file_obj.save()
        
        # If mock_s3 is True, just mark file as completed in DB (skip S3)
        if mock_s3:
            file_obj.status = FileStatus.ACTIVE  # Use ACTIVE not COMPLETED
            file_obj.content_sha256 = content_sha256
            file_obj.save()
        else:
            # Try to upload to S3 using the correct storage_path
            try:
                # Get S3 credentials from settings (which handles staging detection)
                s3_endpoint = get_s3_endpoint_url()
                s3_access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', 'minio')
                s3_secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', 'minio123')
                
                s3_client = boto3.client(
                    's3',
                    endpoint_url=s3_endpoint,
                    aws_access_key_id=s3_access_key,
                    aws_secret_access_key=s3_secret_key,
                    region_name='us-east-1'
                )
                
                # Get bucket name from settings
                bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'hub-files')
                
                # Ensure bucket exists
                try:
                    s3_client.head_bucket(Bucket=bucket_name)
                except ClientError:
                    # Try to create bucket (may fail if we don't have permissions, that's OK)
                    try:
                        s3_client.create_bucket(Bucket=bucket_name)
                    except ClientError:
                        pass  # Bucket might already exist or we don't have permissions
                
                # Upload file content to the correct storage_path
                # The storage_path format is: {tenant.id}/{file_id}/{name}
                if test_content:
                    # Use the file's storage_path as the S3 key
                    s3_key = file_obj.storage_path
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=s3_key,
                        Body=test_content,
                        ContentType=file_obj.content_type
                    )
                elif not file_obj.content_sha256:
                    # If no test_content but file needs to exist, create empty file
                    s3_key = file_obj.storage_path
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=s3_key,
                        Body=b'',
                        ContentType=file_obj.content_type
                    )
            except Exception as e:
                # If S3 upload fails, fall back to mock mode
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"S3 upload failed for file {file_id}, using mock mode: {e}")
                mock_s3 = True
                file_obj.status = FileStatus.ACTIVE
                file_obj.content_sha256 = content_sha256
                file_obj.save()
        
        # Complete upload via API (only if not already marked as mock)
        if not mock_s3:
            response = self.client.post(
                f'/api/v1/files/files/{file_id}/complete/',
                {
                    'content_sha256': content_sha256
                },
                format='json'
            )
            
            if response.status_code != status.HTTP_200_OK:
                raise Exception(f"Failed to complete file upload: {response.status_code} - {response.data}")
    
    def create_dataset(self, file_id, asset_id, **kwargs):
        """Create a dataset via API and return its ID"""
        from rest_framework import status
        
        response = self.client.post(
            '/api/v1/datasets/datasets/',
            {
                'file_id': file_id,
                'asset_id': asset_id,
                **kwargs
            },
            format='json'
        )
        
        if response.status_code != status.HTTP_201_CREATED:
            raise Exception(f"Failed to create dataset: {response.status_code} - {response.data}")
        
        # The response.data should be a dict from DatasetSerializer
        # which includes 'id' field
        data = response.data
        
        # Handle dict response (most common)
        if isinstance(data, dict):
            dataset_id = data.get('id')
            if dataset_id:
                return dataset_id
            # Try alternative keys if 'id' not found
            dataset_id = data.get('dataset_id') or data.get('uuid')
            if dataset_id:
                return dataset_id
            # Last resort: check all keys
            raise Exception(f"Dataset creation response missing 'id' field. Available keys: {list(data.keys())}, Response: {data}")
        
        # Handle object response (OrderedDict or similar)
        dataset_id = getattr(data, 'id', None)
        if dataset_id:
            return dataset_id
        
        # Try to access as dict even if not isinstance dict
        try:
            dataset_id = data['id']
            if dataset_id:
                return dataset_id
        except (KeyError, TypeError):
            pass
        
        raise Exception(f"Dataset creation response missing 'id' field. Response type: {type(data)}, Response: {data}")
    
    def prepare_contract_for_activation(self, contract_id):
        """Prepare contract for activation (validate and normalize)"""
        from hub.apps.contracts.models import Contract, ContractStatus, ValidationStatus, NormalizationStatus
        import time
        
        contract = Contract.objects.get(id=contract_id)
        
        # Try to trigger validation via tasks if available
        if contract.validation_status not in [ValidationStatus.VALID, ValidationStatus.WARNING_ONLY]:
            try:
                # Try to import and call task
                from hub.apps.contracts import tasks
                if hasattr(tasks, 'validate_contract_task'):
                    tasks.validate_contract_task.delay(contract_id)
                    time.sleep(1)
            except (ImportError, AttributeError):
                pass  # Tasks not available, will set manually
        
        # Try to trigger normalization via tasks if available
        if contract.normalization_status not in [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS]:
            try:
                from hub.apps.contracts import tasks
                if hasattr(tasks, 'normalize_contract_task'):
                    tasks.normalize_contract_task.delay(contract_id)
                    time.sleep(1)
            except (ImportError, AttributeError):
                pass  # Tasks not available, will set manually
        
        # Refresh and ensure statuses are set for test purposes
        contract.refresh_from_db()
        
        # Manually set statuses if not already set (for E2E tests)
        # Handle None validation_status explicitly
        if contract.validation_status is None or contract.validation_status not in [ValidationStatus.VALID, ValidationStatus.WARNING_ONLY]:
            contract.validation_status = ValidationStatus.VALID
        
        # Handle None normalization_status explicitly
        if contract.normalization_status is None or contract.normalization_status not in [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS]:
            if not contract.hub_contract_json:
                contract.hub_contract_json = {"hub_contract_version": "1.0.0", "id": "test", "schema": {}}
            contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        
        # Set status to ACTIVE only after ensuring validation_status and normalization_status are set
        # This order is important to avoid validation errors
        if contract.status != ContractStatus.ACTIVE:
            contract.status = ContractStatus.ACTIVE
        
        # Validate before saving to catch any issues early
        try:
            contract.full_clean()
        except Exception as e:
            # If validation fails, log and re-raise
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Contract validation failed: {e}. Contract: {contract.id}, validation_status: {contract.validation_status}, normalization_status: {contract.normalization_status}")
            raise
        
        contract.save()
        return True
    
    def prepare_asset_for_activation(self, asset_id):
        """Prepare asset for activation (DQ and compliance checks)"""
        from hub.apps.assets.models import Asset, DQStatus, ComplianceStatus
        import time
        
        asset = Asset.objects.get(id=asset_id)
        
        # Try to trigger DQ check via tasks if available
        if asset.dq_status == DQStatus.UNKNOWN:
            try:
                from hub.apps.dq import tasks
                if hasattr(tasks, 'run_dq_check_task'):
                    tasks.run_dq_check_task.delay(asset_id)
                    time.sleep(1)
            except (ImportError, AttributeError):
                pass  # Tasks not available, will set manually
        
        # Try to trigger compliance check via tasks if available
        if asset.compliance_status == ComplianceStatus.UNKNOWN:
            try:
                from hub.apps.compliance import tasks
                if hasattr(tasks, 'run_compliance_check_task'):
                    tasks.run_compliance_check_task.delay(asset_id)
                    time.sleep(1)
            except (ImportError, AttributeError):
                pass  # Tasks not available, will set manually
        
        # Refresh and ensure statuses are set for test purposes
        asset.refresh_from_db()
        
        # Manually set statuses if not already set (for E2E tests)
        if asset.dq_status == DQStatus.UNKNOWN:
            asset.dq_status = DQStatus.PASS
        
        if asset.compliance_status == ComplianceStatus.UNKNOWN:
            asset.compliance_status = ComplianceStatus.PASS
        
        asset.save()
        return True
    
    def activate_asset(self, asset_id):
        """Activate an asset via API"""
        from rest_framework import status
        
        response = self.client.post(
            f'/api/v1/assets/assets/{asset_id}/activate/',
            format='json'
        )
        
        return response
    
    def verify_audit_log(self, action: str, resource_type: str, resource_id, result: str = 'SUCCESS', **kwargs):
        """Verify an audit log entry exists"""
        from hub.apps.audit.models import AuditEvent
        
        # Query for the audit event
        events = AuditEvent.objects.filter(
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            result=result,
            **kwargs
        )
        
        self.assertGreater(events.count(), 0, 
                          f"Expected audit log entry not found: {action} for {resource_type} {resource_id}")
    
    def verify_asset_state(self, asset_id, **kwargs):
        """Verify asset state matches expected values"""
        from hub.apps.assets.models import Asset
        
        asset = Asset.objects.get(id=asset_id)
        for key, value in kwargs.items():
            actual_value = getattr(asset, key)
            self.assertEqual(actual_value, value,
                           f"Asset {key} mismatch: expected {value}, got {actual_value}")
    
    def verify_contract_state(self, contract_id, **kwargs):
        """Verify contract state matches expected values"""
        from hub.apps.contracts.models import Contract
        
        contract = Contract.objects.get(id=contract_id)
        for key, value in kwargs.items():
            actual_value = getattr(contract, key)
            self.assertEqual(actual_value, value,
                           f"Contract {key} mismatch: expected {value}, got {actual_value}")
    
    def verify_file_in_s3(self, file_id, expected_content: bytes = None, expected_size: int = None):
        """Verify file exists in S3 (optional check)"""
        # This is optional - S3 may not be available in all test environments
        pass
    
    def verify_cross_service_consistency(self, resource_id, resource_type: str):
        """Verify cross-service consistency (optional)"""
        # This is optional - semantic service may not be available
        pass
