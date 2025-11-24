"""
Compliance Service Client

Client for interacting with the compliance-service microservice.
"""
import httpx
import logging
import time
from typing import Dict, Any, Optional, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


class ComplianceServiceClient:
    """
    Client for interacting with the Compliance service.
    """
    
    def __init__(self):
        self.base_url = getattr(settings, 'COMPLIANCE_SERVICE_URL', 'http://compliance-service:8082')
        self.timeout = getattr(settings, 'COMPLIANCE_SERVICE_TIMEOUT', 1800)  # 30 minutes default
        if not self.base_url.endswith('/'):
            self.base_url = self.base_url.rstrip('/')
        self.client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        self.max_retries = 2
        self.backoff_factor = 1
    
    def _request_with_retry(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Helper to make HTTP requests with retry logic"""
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    logger.warning(
                        f"Compliance service returned {e.response.status_code}. "
                        f"Retrying in {self.backoff_factor * (2 ** attempt)}s..."
                    )
                    time.sleep(self.backoff_factor * (2 ** attempt))
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"Network error connecting to Compliance service: {e}. "
                        f"Retrying in {self.backoff_factor * (2 ** attempt)}s..."
                    )
                    time.sleep(self.backoff_factor * (2 ** attempt))
                    continue
                raise
        raise Exception("Max retries exceeded for Compliance service.")
    
    def health_check(self) -> Tuple[bool, str]:
        """Checks the health of the Compliance service"""
        try:
            response = self._request_with_retry("GET", "/health")
            data = response.json()
            return data.get("status") == "healthy", data.get("service", "compliance-service")
        except Exception as e:
            logger.error(f"Compliance service health check failed: {e}")
            return False, "unknown"
    
    def scan_file(
        self,
        file_content: bytes,
        file_format: str,
        scan_mode: str = "internal",
        applicable_regulations: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Scan file for PII and compliance issues.
        
        Args:
            file_content: File content as bytes
            file_format: File format (csv, json, parquet)
            scan_mode: Scan mode ('internal' or 'external' for scan-only)
            applicable_regulations: Optional list of regulations to check (e.g., ['GDPR', 'HIPAA'])
            
        Returns:
            Compliance scan result dictionary
        """
        try:
            # Prepare file for upload
            files = {
                'file': (f'data.{file_format}', file_content, f'application/{file_format}')
            }
            data = {
                'scan_mode': scan_mode
            }
            if applicable_regulations:
                data['applicable_regulations'] = applicable_regulations
            
            response = self._request_with_retry(
                "POST",
                "/scan-file",
                files=files,
                data=data
            )
            return response.json()
        except Exception as e:
            logger.error(f"Error scanning file with Compliance service: {e}")
            return {
                "overall_status": "UNKNOWN",
                "risk_level": "UNKNOWN",
                "allowed_to_store": None,
                "detected_categories": {},
                "column_findings": [],
                "regulation_mapping": {},
                "error": f"Failed to connect to Compliance service: {e}"
            }

