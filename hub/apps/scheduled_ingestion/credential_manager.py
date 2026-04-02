"""
Credential Manager for Scheduled Ingestion

Provides secure credential masking and connection testing functionality.
"""
import logging
from typing import Dict, Any, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class CredentialManager:
    """
    Manager for handling credentials for scheduled ingestions.
    
    Provides:
    - Credential masking (never expose actual credentials)
    - Connection testing
    - Credential versioning
    """
    
    # Fields that should be masked in credentials
    SENSITIVE_FIELDS = [
        'password',
        'secret',
        'secret_key',
        'secret_access_key',
        'access_key_secret',
        'api_key',
        'api_secret',
        'token',
        'auth_token',
        'private_key',
        'private_key_data',
        'passphrase',
        'credential',
        'credentials'
    ]
    
    @staticmethod
    def get_masked_credentials(scheduled_ingestion) -> Dict[str, Any]:
        """
        Get masked credentials for a scheduled ingestion.
        
        Args:
            scheduled_ingestion: ScheduledIngestion instance
            
        Returns:
            Dictionary with masked credentials (sensitive fields masked)
        """
        source_config = scheduled_ingestion.get_source_config()
        masked_config = {}
        
        # Define sensitive fields to mask based on source type
        sensitive_fields_map = {
            'S3': ['secret_access_key', 'access_key_id'],
            'GCS': ['credentials_json', 'private_key'],
            'AZURE_BLOB': ['account_key', 'sas_token'],
            'HTTP': ['password', 'api_key', 'token'],
            'HTTPS': ['password', 'api_key', 'token'],
            'FTP': ['password'],
            'SFTP': ['password', 'private_key'],
            'DATABASE': ['password', 'connection_string']
        }
        
        # Get sensitive fields for this source type
        source_type = scheduled_ingestion.source_type
        fields_to_mask = sensitive_fields_map.get(source_type, CredentialManager.SENSITIVE_FIELDS)
        
        for key, value in source_config.items():
            key_lower = key.lower()
            
            # Check if this is a sensitive field
            is_sensitive = any(sensitive_field in key_lower for sensitive_field in fields_to_mask) or \
                          any(sensitive_field in key_lower for sensitive_field in CredentialManager.SENSITIVE_FIELDS)
            
            if is_sensitive and value:
                # Mask the value
                if isinstance(value, str):
                    if len(value) <= 4:
                        masked_config[key] = "****"
                    else:
                        # Show first 4 chars and mask the rest (e.g., AKIA***)
                        masked_config[key] = f"{value[:4]}***"
                else:
                    masked_config[key] = "****"
            else:
                # Non-sensitive field - include as-is
                masked_config[key] = value
        
        return masked_config
    
    @staticmethod
    def test_connection(scheduled_ingestion) -> Dict[str, Any]:
        """
        Test connection with credentials for a scheduled ingestion.
        
        Args:
            scheduled_ingestion: ScheduledIngestion instance
            
        Returns:
            Dictionary with test result:
            {
                'success': bool,
                'message': str,
                'tested_at': str (ISO format),
                'connection_details': dict
            }
        """
        from django.utils import timezone
        import time
        
        start_time = time.time()
        source_config = scheduled_ingestion.get_source_config()
        source_type = scheduled_ingestion.source_type
        
        if not source_config:
            return {
                'success': False,
                'message': 'No source configuration found',
                'tested_at': timezone.now().isoformat(),
                'connection_details': {}
            }
        
        try:
            # Import connector factory
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../services/prefect-integration'))
            
            try:
                from connectors.factory import SourceConnectorFactory
            except ImportError:
                return {
                    'success': False,
                    'message': 'Connector service is not available',
                    'tested_at': timezone.now().isoformat(),
                    'connection_details': {}
                }
            
            # Get connector and test connection
            connector = SourceConnectorFactory.get_connector(source_type)
            
            # Test connection with timeout (30 seconds)
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Connection test timed out after 30 seconds")
            
            # Set timeout (Unix only)
            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)
            
            try:
                # test_connection returns a boolean
                test_result = connector.test_connection(source_config)
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Clear alarm
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)
                
                if test_result:
                    return {
                        'success': True,
                        'message': 'Connection test successful',
                        'tested_at': timezone.now().isoformat(),
                        'connection_details': {
                            'response_time_ms': response_time_ms
                        }
                    }
                else:
                    return {
                        'success': False,
                        'message': 'Connection test failed - unable to connect to data source',
                        'tested_at': timezone.now().isoformat(),
                        'connection_details': {
                            'response_time_ms': response_time_ms
                        }
                    }
            
            except TimeoutError:
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)
                return {
                    'success': False,
                    'message': 'Connection test timed out after 30 seconds',
                    'tested_at': timezone.now().isoformat(),
                    'connection_details': {
                        'response_time_ms': 30000
                    }
                }
            
            except Exception as e:
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)
                logger.error(
                    f"Connection test failed for scheduled ingestion {scheduled_ingestion.id}: {str(e)}",
                    exc_info=True
                )
                return {
                    'success': False,
                    'message': f'Connection test failed: {str(e)}',
                    'tested_at': timezone.now().isoformat(),
                    'connection_details': {
                        'response_time_ms': int((time.time() - start_time) * 1000)
                    }
                }
        
        except Exception as e:
            logger.error(
                f"Failed to test credentials for scheduled ingestion {scheduled_ingestion.id}: {str(e)}",
                exc_info=True
            )
            return {
                'success': False,
                'message': f'Failed to test credentials: {str(e)}',
                'tested_at': timezone.now().isoformat(),
                'connection_details': {}
            }

