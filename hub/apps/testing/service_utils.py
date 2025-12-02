"""
Testing Utilities for Service Detection

Utilities to detect if external services are available and conditionally
use real services or mocks in tests.
"""
import os
import logging
from typing import Optional, Dict, Any
from django.conf import settings
from unittest.mock import MagicMock, patch

logger = logging.getLogger(__name__)


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
        import httpx
        health_url = f"{service_url.rstrip('/')}/health"
        response = httpx.get(health_url, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            return data.get('status') == 'healthy'
    except Exception as e:
        logger.debug(f"Service health check failed for {service_url}: {e}")
    return False


def get_service_url(service_name: str, default_url: str) -> str:
    """
    Get service URL from environment variable or settings.
    
    Args:
        service_name: Name of the service (e.g., 'DQ_SERVICE_URL')
        default_url: Default URL if not found
        
    Returns:
        Service URL
    """
    env_var = os.getenv(service_name)
    if env_var:
        return env_var
    
    # Try to get from settings
    setting_name = service_name.replace('_URL', '').replace('_', '')
    return getattr(settings, service_name, default_url)


def is_service_available(service_name: str, default_url: str) -> bool:
    """
    Check if a service is available and healthy.
    
    Args:
        service_name: Environment variable name (e.g., 'DQ_SERVICE_URL')
        default_url: Default URL if not found
        
    Returns:
        True if service is available and healthy
    """
    service_url = get_service_url(service_name, default_url)
    
    # For localhost testing, ensure we use localhost
    # Don't replace if already localhost
    if 'localhost' not in service_url and '127.0.0.1' not in service_url:
        # Replace service names with localhost for local testing
        service_url = service_url.replace('dq-service', 'localhost')
        service_url = service_url.replace('compliance-service', 'localhost')
        service_url = service_url.replace('datacontract-service', 'localhost')
        service_url = service_url.replace('semantic-service', 'localhost')
    
    return check_service_health(service_url)


class ServiceMockManager:
    """
    Context manager that conditionally uses real services or mocks.
    
    Usage:
        with ServiceMockManager('DQ_SERVICE_URL', 'http://localhost:8083') as mock_manager:
            if mock_manager.use_real_service:
                # Use real service
                dq_client = DQServiceClient()
            else:
                # Use mock
                dq_client = mock_manager.mock_client
    """
    
    def __init__(self, service_name: str, default_url: str, mock_class=None):
        """
        Initialize service mock manager.
        
        Args:
            service_name: Environment variable name (e.g., 'DQ_SERVICE_URL')
            default_url: Default URL if not found
            mock_class: Class to mock if service not available
        """
        self.service_name = service_name
        self.default_url = default_url
        self.mock_class = mock_class
        self.use_real_service = False
        self.mock_patcher = None
        self.mock_client = None
    
    def __enter__(self):
        # Check if service is available
        self.use_real_service = is_service_available(self.service_name, self.default_url)
        
        if not self.use_real_service and self.mock_class:
            # Service not available, use mock
            logger.info(f"Service {self.service_name} not available, using mock")
            # Get the module path for the service client
            if 'DQ' in self.service_name:
                patch_path = 'hub.apps.dq.service_client.DQServiceClient'
            elif 'COMPLIANCE' in self.service_name:
                patch_path = 'hub.apps.compliance.service_client.ComplianceServiceClient'
            elif 'DATACONTRACT' in self.service_name:
                patch_path = 'hub.apps.contracts.cli_client.DataContractCLIClient'
            elif 'SEMANTIC' in self.service_name:
                patch_path = 'hub.apps.semantic.service_client.SemanticServiceClient'
            else:
                patch_path = None
            
            if patch_path:
                self.mock_patcher = patch(patch_path)
                self.mock_client = self.mock_patcher.start()
                self.mock_client.return_value = MagicMock()
        else:
            logger.info(f"Using real service {self.service_name}")
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.mock_patcher:
            self.mock_patcher.stop()


def should_use_real_services() -> bool:
    """
    Check if tests should use real services.
    
    This checks the USE_REAL_SERVICES environment variable.
    If set to 'true' or '1', tests will attempt to use real services.
    Otherwise, tests will use mocks.
    
    Returns:
        True if real services should be used
    """
    use_real = os.getenv('USE_REAL_SERVICES', '').lower() in ('true', '1', 'yes')
    return use_real


def get_service_mock_or_real(service_name: str, default_url: str, mock_class=None):
    """
    Get either a real service client or a mock, depending on availability.
    
    Args:
        service_name: Environment variable name (e.g., 'DQ_SERVICE_URL')
        default_url: Default URL if not found
        mock_class: Class to mock if service not available
        
    Returns:
        Tuple of (use_real: bool, client_or_mock: Any)
    """
    use_real = should_use_real_services() and is_service_available(service_name, default_url)
    
    if use_real:
        # Return real service client
        if 'DQ' in service_name:
            from hub.apps.dq.service_client import DQServiceClient
            return True, DQServiceClient()
        elif 'COMPLIANCE' in service_name:
            from hub.apps.compliance.service_client import ComplianceServiceClient
            return True, ComplianceServiceClient()
        elif 'DATACONTRACT' in service_name:
            from hub.apps.contracts.cli_client import DataContractCLIClient
            return True, DataContractCLIClient()
        elif 'SEMANTIC' in service_name:
            from hub.apps.semantic.service_client import SemanticServiceClient
            return True, SemanticServiceClient()
    
    # Return mock
    mock = MagicMock()
    return False, mock

