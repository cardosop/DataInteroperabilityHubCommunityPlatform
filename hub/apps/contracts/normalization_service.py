"""
Normalization Service

Service layer for contract normalization operations.
Extracts normalization logic from normalization.py module.
"""
from typing import Dict, Any, Optional, Tuple, List

from hub.apps.core.services.base import BaseService, ValidationError
from hub.apps.contracts.normalization import (
    normalize_contract,
    validate_hubcontract_schema
)
from hub.apps.contracts.models import NormalizationStatus
from hub.apps.contracts.normalization_metrics import record_all_normalization_metrics


class NormalizationService(BaseService):
    """
    Service for contract normalization operations.

    Provides business logic for:
    - Contract normalization (ODCS → HubContract)
    - Schema validation
    - Normalization metrics recording
    """

    service_name = "normalization_service"

    def normalize_contract(
        self,
        raw_contract: str,
        format: str,
        spec_type: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], str, str, NormalizationStatus, List[str], List[str]]:
        """
        Normalize a contract from ODCS to HubContract format.

        Args:
            raw_contract: Raw contract content
            format: Contract format (JSON or YAML)
            spec_type: Optional spec type (auto-detected if not provided)
            tenant_id: Optional tenant ID for metrics

        Returns:
            Tuple of (hub_contract, detected_spec_type, detected_spec_version,
                     normalization_status, errors, warnings)
        """
        return self.execute_with_metrics(
            operation="normalize_contract",
            func=lambda: self._normalize_contract_impl(
                raw_contract=raw_contract,
                format=format,
                spec_type=spec_type,
                tenant_id=tenant_id
            ),
            tenant_id=tenant_id
        )

    def _normalize_contract_impl(
        self,
        raw_contract: str,
        format: str,
        spec_type: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], str, str, NormalizationStatus, List[str], List[str]]:
        """Internal implementation of contract normalization."""
        import time
        start_time = time.time()

        # Normalize contract
        hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = normalize_contract(
            raw_contract=raw_contract,
            format=format,
            spec_type=spec_type
        )

        # Check for normalization failures
        if norm_status == NormalizationStatus.NORMALIZATION_FAILED and norm_errors:
            raise ValidationError(
                message='Contract normalization failed',
                details={'code': 'NORMALIZATION_FAILED', 'errors': norm_errors}
            )

        # Validate HubContract schema if normalization succeeded
        if hub_contract:
            is_valid, validation_errors = validate_hubcontract_schema(hub_contract)
            if not is_valid:
                norm_status = NormalizationStatus.NORMALIZATION_FAILED
                norm_errors.extend(validation_errors)
                hub_contract = None

        # Record normalization metrics
        duration_ms = (time.time() - start_time) * 1000
        if tenant_id and hub_contract:
            record_all_normalization_metrics(
                hub_contract=hub_contract,
                broken_links=None,
                tenant_id=tenant_id
            )

        return hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings

    def validate_hubcontract(
        self,
        hub_contract: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate HubContract schema.

        Args:
            hub_contract: HubContract dictionary

        Returns:
            Tuple of (is_valid, validation_errors)
        """
        return validate_hubcontract_schema(hub_contract)

