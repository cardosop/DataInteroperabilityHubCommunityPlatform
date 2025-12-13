"""
External Service Mock Fixtures

Fixtures for mocking external services (S3, GCS, Azure Blob, FTP/SFTP, HTTP/HTTPS).
These use real mocking libraries (moto, responses) to simulate external services.
"""
import pytest
import os
from typing import Dict, Any, Optional
from contextlib import contextmanager


@pytest.fixture
def s3_mock():
    """
    S3 mock fixture using moto.
    
    Provides a mocked S3 service for testing S3 interactions.
    """
    try:
        from moto import mock_s3
        from moto.core import DEFAULT_ACCOUNT_ID
        
        with mock_s3():
            import boto3
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                region_name='us-east-1',
                aws_access_key_id='testing',
                aws_secret_access_key='testing'
            )
            
            # Create test bucket
            bucket_name = 'test-bucket'
            s3_client.create_bucket(Bucket=bucket_name)
            
            yield {
                'client': s3_client,
                'bucket_name': bucket_name,
                'account_id': DEFAULT_ACCOUNT_ID
            }
    except ImportError:
        pytest.skip("moto not installed - required for S3 mocking")


@pytest.fixture
def gcs_mock():
    """
    GCS mock fixture.
    
    Provides a mocked Google Cloud Storage service for testing GCS interactions.
    Note: GCS mocking requires additional setup - this is a placeholder structure.
    """
    try:
        # GCS mocking typically requires google-cloud-storage testing utilities
        # or a local GCS emulator
        from google.cloud import storage
        
        # Placeholder for GCS mock setup
        # In practice, you might use:
        # - google-cloud-storage testing utilities
        # - Local GCS emulator
        # - Custom mock implementation
        
        yield {
            'client': None,  # Will be set when GCS mock is implemented
            'bucket_name': 'test-bucket'
        }
    except ImportError:
        pytest.skip("google-cloud-storage not installed - required for GCS mocking")


@pytest.fixture
def azure_blob_mock():
    """
    Azure Blob Storage mock fixture.
    
    Provides a mocked Azure Blob Storage service for testing Azure interactions.
    Note: Azure mocking requires additional setup - this is a placeholder structure.
    """
    try:
        from azure.storage.blob import BlobServiceClient
        
        # Placeholder for Azure Blob mock setup
        # In practice, you might use:
        # - azurite (local Azure Storage emulator)
        # - Custom mock implementation
        
        yield {
            'client': None,  # Will be set when Azure mock is implemented
            'container_name': 'test-container'
        }
    except ImportError:
        pytest.skip("azure-storage-blob not installed - required for Azure mocking")


@pytest.fixture
def ftp_sftp_mock():
    """
    FTP/SFTP mock fixture.
    
    Provides a mocked FTP/SFTP server for testing file transfer operations.
    """
    try:
        from unittest.mock import Mock, MagicMock
        
        # Create mock FTP/SFTP server
        ftp_mock = MagicMock()
        sftp_mock = MagicMock()
        
        # Configure mock behavior
        ftp_mock.connect.return_value = True
        ftp_mock.login.return_value = True
        ftp_mock.retrbinary.return_value = b"test data"
        ftp_mock.storbinary.return_value = True
        
        sftp_mock.connect.return_value = True
        sftp_mock.open.return_value = MagicMock()
        sftp_mock.put.return_value = True
        sftp_mock.get.return_value = b"test data"
        
        yield {
            'ftp': ftp_mock,
            'sftp': sftp_mock
        }
    except Exception as e:
        pytest.skip(f"Failed to create FTP/SFTP mock: {e}")


@pytest.fixture
def http_https_mock():
    """
    HTTP/HTTPS mock fixture using responses.
    
    Provides a mocked HTTP/HTTPS service for testing HTTP interactions.
    """
    try:
        import responses
        
        with responses.RequestsMock() as rsps:
            yield rsps
    except ImportError:
        pytest.skip("responses not installed - required for HTTP/HTTPS mocking")


@pytest.fixture
def httpx_mock():
    """
    HTTPX mock fixture.
    
    Provides a mocked HTTPX client for testing HTTPX-based HTTP interactions.
    """
    try:
        from unittest.mock import Mock, MagicMock
        import httpx
        
        # Create mock HTTPX client
        mock_client = MagicMock(spec=httpx.Client)
        
        # Configure default responses
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.text = "{}"
        mock_response.headers = {}
        
        mock_client.get.return_value = mock_response
        mock_client.post.return_value = mock_response
        mock_client.put.return_value = mock_response
        mock_client.delete.return_value = mock_response
        
        yield mock_client
    except ImportError:
        pytest.skip("httpx not installed - required for HTTPX mocking")


@contextmanager
def s3_bucket_fixture(bucket_name: str = "test-bucket", region: str = "us-east-1"):
    """
    Context manager for creating a temporary S3 bucket using moto.
    
    Args:
        bucket_name: Name of the bucket to create
        region: AWS region for the bucket
        
    Yields:
        Dictionary with S3 client and bucket name
    """
    try:
        from moto import mock_s3
        import boto3
        
        with mock_s3():
            s3_client = boto3.client(
                's3',
                region_name=region,
                aws_access_key_id='testing',
                aws_secret_access_key='testing'
            )
            
            s3_client.create_bucket(Bucket=bucket_name)
            
            yield {
                'client': s3_client,
                'bucket_name': bucket_name
            }
    except ImportError:
        raise ImportError("moto not installed - required for S3 mocking")


@contextmanager
def http_server_fixture(responses_config: Optional[Dict[str, Any]] = None):
    """
    Context manager for setting up HTTP server mocks using responses.
    
    Args:
        responses_config: Configuration for responses mock
        
    Yields:
        Responses mock object
    """
    try:
        import responses
        
        with responses.RequestsMock() as rsps:
            if responses_config:
                for url, method, response_data in responses_config.get('endpoints', []):
                    rsps.add(
                        method=method,
                        url=url,
                        json=response_data.get('json'),
                        status=response_data.get('status', 200)
                    )
            
            yield rsps
    except ImportError:
        raise ImportError("responses not installed - required for HTTP mocking")


