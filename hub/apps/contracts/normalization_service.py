"""
Normalization Service

Service layer for contract normalization operations.
Extracts normalization logic from normalization.py module.
"""
from typing import Dict, Any, Optional, Tuple, List

from hub.apps.core.services.base import BaseService, ValidationError
from hub.apps.core.events.service_publishers import NormalizationEventPublisher
from hub.apps.contracts.normalization import (
    normalize_contract,
    validate_hubcontract_schema
)
from hub.apps.contracts.models import NormalizationStatus
from hub.apps.contracts.normalization_metrics import record_all_normalization_metrics


class NormalizationService(BaseService, NormalizationEventPublisher):
    """
    Service for contract normalization operations.

    Provides business logic for:
    - Contract normalization (ODCS → HubContract)
    - Schema validation
    - Normalization metrics recording
    """

    service_name = "normalization_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None, **kwargs):
        """Initialize NormalizationService with tenant and user context."""
        self.tenant_id = tenant_id
        self.user_id = user_id
        super().__init__(tenant_id=tenant_id, user_id=user_id, **kwargs)
        # Initialize event publisher (BaseService.__init__ does not call
        # super().__init__(), so the mixin __init__ must be invoked explicitly).
        NormalizationEventPublisher.__init__(self)

    def normalize_contract(
        self,
        raw_contract: str,
        format: str,
        spec_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], str, str, NormalizationStatus, List[str], List[str]]:
        """
        Normalize a contract from ODCS to HubContract format.

        Args:
            raw_contract: Raw contract content
            format: Contract format (JSON or YAML)
            spec_type: Optional spec type (auto-detected if not provided)
            tenant_id: Optional tenant ID for metrics and events
            contract_id: Optional contract ID for event publishing (required for events)
            user_id: Optional user ID for event context

        Returns:
            Tuple of (hub_contract, detected_spec_type, detected_spec_version,
                     normalization_status, errors, warnings)
        """
        # Use provided tenant_id/user_id or fall back to instance attributes
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        return self.execute_with_metrics(
            operation="normalize_contract",
            func=lambda: self._normalize_contract_impl(
                raw_contract=raw_contract,
                format=format,
                spec_type=spec_type,
                tenant_id=effective_tenant_id,
                contract_id=contract_id,
                user_id=effective_user_id
            ),
            tenant_id=effective_tenant_id
        )

    def _normalize_contract_impl(
        self,
        raw_contract: str,
        format: str,
        spec_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], str, str, NormalizationStatus, List[str], List[str]]:
        """Internal implementation of contract normalization."""
        import time
        start_time = time.time()

        # Determine normalization type from spec_type
        normalization_type = spec_type or "AUTO_DETECT"
        if normalization_type == "AUTO_DETECT":
            normalization_type = "ODCS"  # Default assumption

        # Publish normalization.started event if contract_id is provided
        if contract_id:
            try:
                self.publish_normalization_started(
                    contract_id=contract_id,
                    normalization_type=normalization_type,
                    spec_version=None,  # Will be detected during normalization
                    source_format=format,
                    tenant_id=tenant_id,
                    user_id=user_id
                )
            except Exception as e:
                # Event publishing failure should not block normalization
                import structlog
                logger = structlog.get_logger(__name__)
                logger.warning(
                    "normalization_event_publish_failed",
                    event_type="normalization.started",
                    contract_id=contract_id,
                    error=str(e),
                    message="Failed to publish normalization.started event (non-critical)"
                )

        try:
            # Normalize contract
            hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = normalize_contract(
                raw_contract=raw_contract,
                format=format,
                spec_type=spec_type
            )

            # Phase 227 Wave 1 (227.L3.2) — structural-floor check FIRST.
            # Many "normalization failed" errors are actually structureless
            # inputs in disguise. Surfacing the typed STRUCTURELESS_CONTRACT
            # code here gives the API consumer a parseable code + a
            # remediation_url instead of a generic NORMALIZATION_FAILED.
            # ALWAYS-ON per the 2026-04-30 ungate directive.
            from hub.apps.contracts.structural_floor import (
                enforce_structural_floor,
            )
            try:
                enforce_structural_floor(
                    hub_contract,
                    spec_type=detected_spec_type or spec_type,
                    spec_version=detected_spec_version,
                    warnings=norm_warnings,
                    contract_id=contract_id,
                )
            except ValidationError:
                # Structural floor violation — emit the failed event for
                # observability, then re-raise the typed STRUCTURELESS_CONTRACT.
                if contract_id:
                    try:
                        self.publish_normalization_failed(
                            contract_id=contract_id,
                            error_message="Contract failed structural-floor invariant",
                            error_details={
                                "code": "STRUCTURELESS_CONTRACT",
                                "errors": norm_errors,
                            },
                            normalization_errors=norm_errors,
                            spec_version=detected_spec_version,
                            tenant_id=tenant_id,
                            user_id=user_id,
                        )
                    except Exception as exc:
                        import structlog
                        logger = structlog.get_logger(__name__)
                        logger.warning(
                            "normalization_event_publish_failed",
                            event_type="normalization.failed",
                            contract_id=contract_id,
                            error=str(exc),
                            message="Failed to publish event (non-critical)",
                        )
                raise

            # Check for non-structural normalization failures (missing
            # required `info.name`, malformed JSON, etc.).
            if norm_status == NormalizationStatus.NORMALIZATION_FAILED and norm_errors:
                # Publish normalization.failed event if contract_id is provided
                if contract_id:
                    try:
                        self.publish_normalization_failed(
                            contract_id=contract_id,
                            error_message="Contract normalization failed",
                            error_details={"code": "NORMALIZATION_FAILED", "errors": norm_errors},
                            normalization_errors=norm_errors,
                            spec_version=detected_spec_version,
                            tenant_id=tenant_id,
                            user_id=user_id
                        )
                    except Exception as e:
                        import structlog
                        logger = structlog.get_logger(__name__)
                        logger.warning(
                            "normalization_event_publish_failed",
                            event_type="normalization.failed",
                            contract_id=contract_id,
                            error=str(e),
                            message="Failed to publish normalization.failed event (non-critical)"
                        )

                raise ValidationError(
                    message='Contract normalization failed',
                    details={'code': 'NORMALIZATION_FAILED', 'errors': norm_errors}
                )

            # Validate HubContract schema if normalization succeeded.
            # Phase 227 L3.1 — explicit raise on validation failure
            # (no more silent-nullify). The pre-raise event publish
            # gives ops the same observability the old block produced.
            if hub_contract:
                is_valid, validation_errors = validate_hubcontract_schema(hub_contract)
                if not is_valid:
                    if contract_id:
                        try:
                            self.publish_normalization_failed(
                                contract_id=contract_id,
                                error_message="HubContract schema validation failed",
                                error_details={
                                    "code": "SCHEMA_VALIDATION_FAILED",
                                    "errors": validation_errors,
                                },
                                normalization_errors=norm_errors + validation_errors,
                                spec_version=detected_spec_version,
                                tenant_id=tenant_id,
                                user_id=user_id,
                            )
                        except Exception as exc:
                            import structlog
                            logger = structlog.get_logger(__name__)
                            logger.warning(
                                "normalization_event_publish_failed",
                                event_type="normalization.failed",
                                contract_id=contract_id,
                                error=str(exc),
                                message="Failed to publish normalization.failed event (non-critical)",
                            )
                    raise ValidationError(
                        message="Contract validation failed",
                        code="VALIDATION_ERROR",
                        details={
                            "errors": validation_errors,
                            "spec_type": detected_spec_type or spec_type,
                            "spec_version": detected_spec_version,
                        },
                        http_status=400,
                    )

            # Record normalization metrics
            duration_ms = (time.time() - start_time) * 1000
            if tenant_id and hub_contract:
                record_all_normalization_metrics(
                    hub_contract=hub_contract,
                    broken_links=None,
                    tenant_id=tenant_id
                )

            # Publish normalization.completed event if contract_id is provided
            if contract_id:
                try:
                    # Convert NormalizationStatus enum to string value
                    if hasattr(norm_status, 'value'):
                        status_str = norm_status.value
                    elif hasattr(norm_status, '__str__'):
                        status_str = str(norm_status)
                    else:
                        status_str = norm_status

                    self.publish_normalization_completed(
                        contract_id=contract_id,
                        normalization_status=status_str,
                        normalization_errors=norm_errors if norm_errors else None,
                        normalization_warnings=norm_warnings if norm_warnings else None,
                        duration_ms=int(duration_ms),
                        spec_version=detected_spec_version,
                        tenant_id=tenant_id,
                        user_id=user_id
                    )
                except Exception as e:
                    import structlog
                    logger = structlog.get_logger(__name__)
                    logger.warning(
                        "normalization_event_publish_failed",
                        event_type="normalization.completed",
                        contract_id=contract_id,
                        error=str(e),
                        message="Failed to publish normalization.completed event (non-critical)"
                    )

            return hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings

        except ValidationError:
            # Re-raise validation errors (events already published above)
            raise
        except Exception as e:
            # Publish normalization.failed event for unexpected errors
            if contract_id:
                try:
                    self.publish_normalization_failed(
                        contract_id=contract_id,
                        error_message=str(e),
                        error_details={"code": "UNEXPECTED_ERROR", "error_type": type(e).__name__},
                        normalization_errors=None,
                        spec_version=None,
                        tenant_id=tenant_id,
                        user_id=user_id
                    )
                except Exception as event_error:
                    import structlog
                    logger = structlog.get_logger(__name__)
                    logger.warning(
                        "normalization_event_publish_failed",
                        event_type="normalization.failed",
                        contract_id=contract_id,
                        error=str(event_error),
                        message="Failed to publish normalization.failed event (non-critical)"
                    )
            raise

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

