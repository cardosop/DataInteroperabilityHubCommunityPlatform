"""
DQ Service Client

Client for interacting with the dq-service microservice.
"""
import httpx
import logging
import time
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class DQServiceClient:
    """
    Client for interacting with the DQ service.
    """
    
    def __init__(self):
        self.base_url = getattr(settings, 'DQ_SERVICE_URL', 'http://dq-service:8083')
        self.timeout = getattr(settings, 'DQ_SERVICE_TIMEOUT', 1800)  # 30 minutes default
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
                        f"DQ service returned {e.response.status_code}. "
                        f"Retrying in {self.backoff_factor * (2 ** attempt)}s..."
                    )
                    time.sleep(self.backoff_factor * (2 ** attempt))
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"Network error connecting to DQ service: {e}. "
                        f"Retrying in {self.backoff_factor * (2 ** attempt)}s..."
                    )
                    time.sleep(self.backoff_factor * (2 ** attempt))
                    continue
                raise
        raise Exception("Max retries exceeded for DQ service.")
    
    def health_check(self) -> Tuple[bool, str]:
        """Checks the health of the DQ service"""
        try:
            response = self._request_with_retry("GET", "/health")
            data = response.json()
            return data.get("status") == "healthy", data.get("service", "dq-service")
        except Exception as e:
            logger.error(f"DQ service health check failed: {e}")
            return False, "unknown"
    
    def run_dq(
        self,
        file_content: bytes,
        file_format: str,
        profile_key: str = "intake_basic_gx",
        use_cache: bool = True,
        contract: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Run DQ checks on file content.
        
        Args:
            file_content: File content as bytes
            file_format: File format (csv, json, parquet)
            profile_key: DQ profile key (default: intake_basic_gx)
            use_cache: Whether to use cached results
            contract: Optional Contract instance to extract quality rules from
            
        Returns:
            DQ result dictionary
        """
        # Check cache if enabled
        if use_cache:
            import hashlib
            cache_key = f"dq:run:{hashlib.sha256(file_content).hexdigest()}:{profile_key}"
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"Using cached DQ result for profile {profile_key}")
                return cached_result
        
        try:
            # Extract quality rules from contract if provided (GAP-8.2.1)
            custom_checks = None
            effective_profile_key = profile_key
            if contract:
                from hub.apps.dq.contract_integration import (
                    ContractQualityRulesExtractor
                )
                # Get contract profile key if specified
                effective_profile_key = ContractQualityRulesExtractor.get_contract_profile_key(
                    contract, fallback=profile_key
                )
                # Get contract quality checks
                custom_checks = ContractQualityRulesExtractor.get_contract_quality_checks(contract)
            
            # Prepare file for upload
            files = {
                'file': (f'data.{file_format}', file_content, f'application/{file_format}')
            }
            data = {
                'profile_key': effective_profile_key
            }
            
            # Add custom checks if available (will be passed to DQ service as JSON string)
            if custom_checks:
                # Convert DQCheck objects to serializable format
                custom_checks_list = [
                    {
                        'check_id': check.check_id,
                        'name': check.name,
                        'category': check.category.value,
                        'severity': check.severity.value,
                        'expectation_type': check.expectation_type,
                        'params': check.params,
                        'target_level': check.target_level,
                        'target_column': check.target_column,
                        'target_pattern': check.target_pattern
                    }
                    for check in custom_checks
                ]
                import json
                data['custom_checks'] = json.dumps(custom_checks_list)
            
            response = self._request_with_retry(
                "POST",
                "/run",
                files=files,
                data=data
            )
            result = response.json()
            
            # Cache result if enabled
            if use_cache:
                cache.set(cache_key, result, timeout=getattr(settings, 'DQ_RESULT_CACHE_TTL', 3600))
            
            return result
        except Exception as e:
            logger.error(f"Error running DQ check with DQ service: {e}")
            return {
                "overall_status": "UNKNOWN",
                "quality_score": 0.0,
                "checks": [],
                "engine_type": "UNKNOWN",
                "engine_version": "unknown",
                "profile_key": profile_key,
                "metadata": {
                    "error": f"Failed to connect to DQ service: {e}"
                }
            }

