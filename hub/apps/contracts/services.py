"""
Contract Service

Business logic for contract operations.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

import structlog
from django.core.paginator import Paginator
from django.db import models, transaction
from django.utils import timezone

from hub.apps.assets.models import Asset
from hub.apps.contracts.business_rules import ContractsBusinessRules, ODPSBusinessRules
from hub.apps.contracts.cli_client import DataContractCLIClient
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.contracts.normalization import normalize_contract, validate_hubcontract_schema
from hub.apps.contracts.structural_floor import enforce_structural_floor
from hub.apps.contracts.normalization_service import NormalizationService
from hub.apps.contracts.odps_parser import ODPSParser
from hub.apps.contracts.ref_resolver import resolve_odps_refs
from hub.apps.core.events.service_publishers import ContractEventPublisher, ODPSEventPublisher
from hub.apps.core.transaction_safe import run_side_effect
from hub.apps.core.services.base import BaseService, NotFoundError, PermissionError, ValidationError
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job

logger = structlog.get_logger(__name__)


class ContractService(BaseService, ContractEventPublisher, ODPSEventPublisher):
    """
    Service for contract operations.

    Provides business logic for retrieving and validating contracts.
    """

    service_name = "contract_service"

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """
        Initialize ContractService.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
            request_id: Request ID for tracing
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.request_id = request_id
        # Initialize event publishers (both will handle super() appropriately)
        ContractEventPublisher.__init__(self)
        ODPSEventPublisher.__init__(self)

    def _emit_validation_failed_observability(
        self,
        *,
        validation_errors: list,
        spec_type: Optional[str],
        spec_version: Optional[str],
        contract_id: Optional[str],
        tenant_id: Optional[str],
        source: str,
    ) -> None:
        """Phase 227 Wave 1 (227.L7.1, L7.3, L7.4) — emit metric + log
        + audit event for a CONTRACT_VALIDATION_FAILED Layer-3 raise.

        Distinct from the structural-floor path
        (``_emit_floor_violation_observability`` in ``structural_floor.py``)
        because this fires for non-structural validation failures
        (missing ``info.name``, malformed JSON, etc.) — those have
        ``code="VALIDATION_ERROR"`` rather than
        ``code="STRUCTURELESS_CONTRACT"``. Both contribute to the
        ``contract_validation_failed_total`` counter so the dashboard
        shows the union.
        """
        # L7.1 — metric.
        try:
            from hub.apps.contracts.normalization_metrics import (
                record_validation_failed,
            )
            record_validation_failed(
                code="VALIDATION_ERROR",
                subcode=None,
                spec_type=spec_type,
            )
        except Exception:
            pass
        # L7.4 — structured log.
        try:
            logger.warning(
                "contract_validation_failed",
                contract_id=str(contract_id) if contract_id else None,
                spec_type=spec_type,
                spec_version=spec_version,
                tenant_id=str(tenant_id) if tenant_id else None,
                error_count=len(validation_errors or []),
                source=source,
            )
        except Exception:
            pass
        # L7.3 — audit event.
        try:
            from hub.apps.audit.utils import create_audit_event
            from hub.apps.tenants.models import Tenant

            tenant_obj = None
            if tenant_id:
                tenant_obj = Tenant.objects.filter(id=tenant_id).first()
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_VALIDATION_FAILED",
                actor_user=None,
                tenant=tenant_obj,
                resource_id=str(contract_id) if contract_id else None,
                result="FAILURE",
                details={
                    "code": "VALIDATION_ERROR",
                    "spec_type": spec_type,
                    "spec_version": spec_version,
                    "error_count": len(validation_errors or []),
                    "errors_truncated": (validation_errors or [])[:10],
                    "source": source,
                },
            )
        except Exception:
            pass

    def get_contract(self, contract_id: str, tenant_id: Optional[str] = None) -> Contract:
        """
        Get contract by ID.

        Args:
            contract_id: Contract ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            Contract instance

        Raises:
            NotFoundError: If contract not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        return self.execute_with_metrics(
            operation="get_contract",
            tenant_id=effective_tenant_id,
            func=lambda: self.get_resource_or_raise(
                Contract, contract_id, tenant_id=effective_tenant_id
            ),
        )

    def get_active_contract_for_asset(
        self, asset_id: str, tenant_id: Optional[str] = None
    ) -> Optional[Contract]:
        """
        Get active contract for an asset.

        When multiple active contracts exist (e.g., both ODCS and ODPS),
        prefers ODCS contract for backward compatibility.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID

        Returns:
            Contract instance or None if not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _get_contract():
            from hub.apps.contracts.models import OriginalSpecType

            # Get all active contracts for the asset
            contracts = Contract.objects.filter(
                asset_id=asset_id, tenant_id=effective_tenant_id, status=ContractStatus.ACTIVE
            )

            # If no contracts, return None
            if not contracts.exists():
                return None

            # If only one contract, return it
            if contracts.count() == 1:
                return contracts.first()

            # Multiple contracts: prefer ODCS over ODPS for backward compatibility
            # This handles the case where both ODCS and ODPS contracts are attached
            odcs_contract = (
                contracts.filter(original_spec_type=OriginalSpecType.ODCS)
                .order_by("-version")
                .first()
            )

            if odcs_contract:
                return odcs_contract

            # If no ODCS, return the first ODPS contract (or any other type)
            return contracts.order_by("-version").first()

        return self.execute_with_metrics(
            operation="get_active_contract_for_asset",
            tenant_id=effective_tenant_id,
            func=_get_contract,
        )

    def validate_contract_active(
        self, contract_id: str, tenant_id: Optional[str] = None
    ) -> Contract:
        """
        Validate that contract exists and is active.

        Args:
            contract_id: Contract ID
            tenant_id: Tenant ID

        Returns:
            Contract instance

        Raises:
            NotFoundError: If contract not found
            ValidationError: If contract is not active
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _validate():
            contract = self.get_resource_or_raise(
                Contract, contract_id, tenant_id=effective_tenant_id
            )

            if contract.status != ContractStatus.ACTIVE:
                raise ValidationError(
                    f"Contract is not active (status: {contract.status})",
                    details={"contract_id": contract_id, "status": contract.status},
                )

            return contract

        return self.execute_with_metrics(
            operation="validate_contract_active", tenant_id=effective_tenant_id, func=_validate
        )

    @transaction.atomic
    def create_contract(
        self,
        original_raw: str,
        original_format: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        original_spec_type: Optional[str] = None,
        disable_external_refs: bool = False,
        remove_external_refs: bool = False,
    ) -> Contract:
        """
        Create a new contract.

        Args:
            original_raw: Original contract content
            original_format: Format (JSON or YAML)
            tenant_id: Tenant ID
            user_id: User ID
            asset_id: Optional asset ID
            original_spec_type: Optional spec type (defaults to ODCS)
            disable_external_refs: If True, external $ref references are disabled (raises error)
            remove_external_refs: If True, external $ref references are removed from the document

        Returns:
            Created contract instance

        Raises:
            ValidationError: If validation fails (including invalid/cross-tenant asset reference)
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        # Normalize original_format to canonical uppercase (JSON, YAML) so "json"/"yaml" are accepted
        if original_format and isinstance(original_format, str):
            original_format = original_format.strip().upper()

        # Detect spec type if not provided (capture before nested function)
        effective_spec_type = original_spec_type or OriginalSpecType.ODCS
        spec_type_str = getattr(effective_spec_type, "value", None) or str(effective_spec_type)

        # Plan limit enforcement
        from hub.apps.tenants.services import PlanLimitService
        plan_limit_service = PlanLimitService(tenant_id=effective_tenant_id)
        plan_limit_service.check_limit(
            tenant_id=effective_tenant_id,
            limit_key="max_contracts",
            delta=1,
        )

        # Phase 18.2.1: validate contract creation via business rules before mutating
        # Business rules run first so invalid asset references (cross-tenant, non-existent)
        # return 400 BUSINESS_RULES_VALIDATION instead of 404 NOT_FOUND
        contract_data = {
            "tenant_id": effective_tenant_id,
            "original_raw": original_raw,
            "original_format": original_format,
            "original_spec_type": spec_type_str,
            "asset_id": asset_id,
        }
        rules = ContractsBusinessRules(tenant_id=effective_tenant_id, user_id=effective_user_id)
        creation_result = rules.validate_contract_creation(contract_data)
        if not creation_result.is_valid:
            raise ValidationError(
                message="; ".join(creation_result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details={
                    "errors": creation_result.errors,
                    "validation_details": creation_result.details,
                },
                http_status=400,
            )

        def _create():
            # Validate asset exists if provided
            asset = None
            if asset_id:
                try:
                    asset = Asset.objects.get(id=asset_id, tenant_id=effective_tenant_id)
                except Asset.DoesNotExist:
                    raise NotFoundError(
                        f"Asset with ID '{asset_id}' not found for tenant",
                        code="NOT_FOUND",
                    )

            # Handle $ref resolution for ODPS contracts
            original_raw_resolved = None
            contract_content_for_normalization = original_raw

            # Check if this is an ODPS contract and resolve $refs if needed
            if effective_spec_type == OriginalSpecType.ODPS or (
                not original_spec_type
                and (
                    OriginalSpecType.ODPS in original_raw or "opendataproducts.org" in original_raw
                )
            ):
                try:
                    # Parse the document
                    parser = ODPSParser()
                    document = parser.parse(original_raw, original_format)

                    # Resolve $refs with external ref handling
                    _, resolved_document = resolve_odps_refs(
                        document=document,
                        disable_external_refs=disable_external_refs,
                        remove_external_refs=remove_external_refs,
                        tenant_id=effective_tenant_id,
                        user_id=effective_user_id,
                    )

                    # Serialize resolved document back to string
                    if original_format == "JSON":
                        original_raw_resolved = json.dumps(
                            resolved_document, indent=2, ensure_ascii=False
                        )
                    else:  # YAML
                        import yaml

                        original_raw_resolved = yaml.dump(
                            resolved_document, default_flow_style=False, allow_unicode=True
                        )

                    # Use resolved document for normalization
                    contract_content_for_normalization = original_raw_resolved

                except Exception as e:
                    # If ref resolution fails, log but continue with original
                    # This allows contracts with invalid refs to still be created (they'll fail validation)
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to resolve $refs for ODPS contract: {e}")
                    # Continue with original_raw for normalization

            # Normalize contract using NormalizationService (event publishing integrated)
            # Note: contract_id is not available yet, so events won't be published during creation
            normalization_service = NormalizationService(
                tenant_id=effective_tenant_id, user_id=effective_user_id
            )
            (
                hub_contract,
                detected_spec_type,
                detected_spec_version,
                norm_status,
                norm_errors,
                norm_warnings,
            ) = normalization_service.normalize_contract(
                raw_contract=contract_content_for_normalization,
                format=original_format,
                spec_type=effective_spec_type,
                tenant_id=effective_tenant_id,
                user_id=effective_user_id,
                # contract_id not available yet - events will be published after contract creation if needed
            )

            # Phase 227 Wave 1 (227.L3.2) — enforce the structural floor
            # FIRST. Many normalization failures upstream are themselves
            # caused by a structureless input (no schema/models/fields).
            # Surfacing the typed ``STRUCTURELESS_CONTRACT`` code here —
            # before the generic ``NORMALIZATION_FAILED`` short-circuit —
            # gives API consumers a parseable code and a remediation_url.
            # ALWAYS-ON per the 2026-04-30 ungate directive.
            enforce_structural_floor(
                hub_contract,
                spec_type=detected_spec_type or effective_spec_type,
                spec_version=detected_spec_version,
                warnings=norm_warnings,
                contract_id=None,  # Not yet persisted on create.
                tenant_id=effective_tenant_id,
                source="creation",
            )

            # Check for non-structural normalization failures (missing
            # required `info.name`, malformed JSON, etc.). The structural
            # floor above has already filtered out the structureless
            # cases; anything that reaches here failed for a different
            # reason and is reported as generic VALIDATION_ERROR.
            if norm_status == NormalizationStatus.NORMALIZATION_FAILED and norm_errors:
                raise ValidationError(
                    message="Contract normalization failed",
                    details={"code": "NORMALIZATION_FAILED", "errors": norm_errors},
                )

            # Phase 227 Wave 1 (227.L3.1) — explicit ValidationError on
            # validation failure, never silent-nullify. Pre-Wave-1 we used
            # to set ``hub_contract = None`` here, persist a row with
            # ``hub_contract_json=NULL``, and let the caller wonder why
            # downstream lineage/search were broken. The new contract
            # surfaces the exact validation failures and refuses to
            # persist a structureless or invalid row.
            if hub_contract:
                is_valid, validation_errors = validate_hubcontract_schema(hub_contract)
                if not is_valid:
                    self._emit_validation_failed_observability(
                        validation_errors=validation_errors,
                        spec_type=detected_spec_type or effective_spec_type,
                        spec_version=detected_spec_version,
                        contract_id=None,
                        tenant_id=effective_tenant_id,
                        source="creation",
                    )
                    raise ValidationError(
                        message="Contract validation failed",
                        code="VALIDATION_ERROR",
                        details={
                            "errors": validation_errors,
                            "spec_type": detected_spec_type or effective_spec_type,
                            "spec_version": detected_spec_version,
                        },
                        http_status=400,
                    )

            # Get user if user_id provided
            user = None
            if effective_user_id:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                try:
                    user = User.objects.get(id=effective_user_id)
                except User.DoesNotExist:
                    pass  # User not found, created_by will be None

            # Find next available version for this asset to avoid unique constraint violation
            # The constraint unique_contract_version_per_asset requires unique (tenant, asset, version)
            version = 1
            if asset:
                # Find the maximum version for this asset
                max_version = (
                    Contract.objects.filter(tenant_id=effective_tenant_id, asset=asset).aggregate(
                        max_version=models.Max("version")
                    )["max_version"]
                    or 0
                )
                version = max_version + 1

            # Create contract
            contract = Contract.objects.create(
                tenant_id=effective_tenant_id,
                asset=asset,
                version=version,
                original_raw=original_raw,
                original_raw_resolved=original_raw_resolved,
                original_format=original_format,
                original_spec_type=detected_spec_type or effective_spec_type,
                original_spec_version=detected_spec_version or "3.0.2",
                hub_contract_json=hub_contract,
                hub_contract_version="1.0.0" if hub_contract else None,
                normalization_status=norm_status,
                normalization_errors=norm_errors,
                normalization_warnings=norm_warnings,
                status=ContractStatus.DRAFT,
                created_by=user,
            )

            # Index for search
            from hub.apps.search.indexing import SearchIndexer

            indexer = SearchIndexer()
            run_side_effect(indexer.index_contract, contract)

            # Create audit log
            from hub.apps.audit.utils import create_audit_event
            from hub.apps.tenants.models import Tenant

            tenant_obj = Tenant.objects.get(id=effective_tenant_id)
            run_side_effect(
                create_audit_event,
                resource_type="CONTRACT",
                action="CONTRACT_CREATED",
                actor_user=user,
                tenant=tenant_obj,
                resource_id=str(contract.id),
                details={
                    "contract_id": str(contract.id),
                    "original_spec_type": contract.original_spec_type,
                    "normalization_status": contract.normalization_status,
                },
            )

            # Send notification email for ODPS creation completion or normalization failure
            if user and contract.original_spec_type == OriginalSpecType.ODPS:
                try:
                    from hub.apps.notifications.tasks import (
                        send_odps_creation_completion_email,
                        send_odps_normalization_failure_email,
                    )

                    if contract.normalization_status == NormalizationStatus.NORMALIZATION_FAILED:
                        # Send normalization failure notification
                        error_message = (
                            "; ".join(contract.normalization_errors)
                            if contract.normalization_errors
                            else "ODPS normalization failed"
                        )
                        _cid = str(contract.id)
                        _err = error_message
                        _errs = contract.normalization_errors
                        transaction.on_commit(
                            lambda: send_odps_normalization_failure_email.delay(
                                contract_id=_cid,
                                error_message=_err,
                                error_code="ODPS_NORMALIZATION_ERROR",
                                errors=_errs,
                                field_path=None,
                            )
                        )
                    else:
                        # Send creation completion notification
                        _cid = str(contract.id)
                        transaction.on_commit(
                            lambda: send_odps_creation_completion_email.delay(_cid)
                        )
                except Exception as e:
                    # Log but don't fail contract creation if notification fails
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Failed to send ODPS notification for contract {contract.id}: {e}"
                    )

            return contract

        return self.execute_with_metrics(
            operation="create_contract", tenant_id=effective_tenant_id, func=_create
        )

    @transaction.atomic
    def update_contract(
        self,
        contract_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        original_raw: Optional[str] = None,
        original_format: Optional[str] = None,
        original_spec_type: Optional[str] = None,
        original_spec_version: Optional[str] = None,
        status: Optional[str] = None,
        remove_external_refs: bool = False,
    ) -> Contract:
        """
        Update a contract.

        Args:
            contract_id: Contract ID
            tenant_id: Tenant ID
            user_id: User ID
            original_raw: Updated contract content (optional)
            original_format: Updated format (optional)
            original_spec_type: Spec type of the new content, e.g. ODCS or ODPS (optional; used when updating original_raw so normalization uses the correct normalizer)
            original_spec_version: Spec version, e.g. 3.0.2 or 4.1 (optional; used with original_spec_type)
            status: Updated status (optional)
            remove_external_refs: If True, external $ref references will be removed from the document

        Returns:
            Updated contract instance

        Raises:
            NotFoundError: If contract not found
            ValidationError: If validation fails
        """
        effective_tenant_id = tenant_id or self.tenant_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _update():
            contract = self.get_resource_or_raise(
                Contract, contract_id, tenant_id=effective_tenant_id
            )

            # Phase 18.2.2: validate contract update via business rules before mutating
            update_data = {}
            if original_raw is not None:
                update_data["original_raw"] = original_raw
                update_data["original_format"] = original_format or contract.original_format
            if status is not None:
                update_data["status"] = status
            if update_data:
                rules = ContractsBusinessRules(
                    tenant_id=effective_tenant_id, user_id=user_id or self.user_id
                )
                update_result = rules.validate_contract_update(contract, contract_data=update_data)
                if not update_result.is_valid:
                    raise ValidationError(
                        message="; ".join(update_result.errors),
                        code="BUSINESS_RULES_VALIDATION",
                        details={
                            "errors": update_result.errors,
                            "validation_details": update_result.details,
                        },
                        http_status=400,
                    )

            # Update original_raw if provided
            if original_raw is not None:
                contract.original_raw = original_raw
                if original_format:
                    contract.original_format = original_format
                # When client sends spec type/version with the new content, use them for normalization
                if original_spec_type is not None:
                    contract.original_spec_type = original_spec_type
                if original_spec_version is not None:
                    contract.original_spec_version = original_spec_version

                # Handle $ref resolution for ODPS contracts
                original_raw_resolved = None
                contract_content_for_normalization = contract.original_raw

                # Check if this is an ODPS contract and resolve $refs if needed
                if contract.original_spec_type == OriginalSpecType.ODPS:
                    try:
                        # Parse the document
                        parser = ODPSParser()
                        document = parser.parse(contract.original_raw, contract.original_format)

                        # Resolve $refs with external ref handling (remove_external_refs only for updates)
                        _, resolved_document = resolve_odps_refs(
                            document=document,
                            disable_external_refs=False,  # Updates don't disable, only remove
                            remove_external_refs=remove_external_refs,
                            tenant_id=effective_tenant_id,
                            user_id=user_id or self.user_id,
                        )

                        # Serialize resolved document back to string
                        if contract.original_format == "JSON":
                            original_raw_resolved = json.dumps(
                                resolved_document, indent=2, ensure_ascii=False
                            )
                        else:  # YAML
                            import yaml

                            original_raw_resolved = yaml.dump(
                                resolved_document, default_flow_style=False, allow_unicode=True
                            )

                        # Use resolved document for normalization
                        contract_content_for_normalization = original_raw_resolved
                        contract.original_raw_resolved = original_raw_resolved

                    except Exception as e:
                        # If ref resolution fails, log but continue with original
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to resolve $refs for ODPS contract update: {e}")
                        # Continue with original_raw for normalization
                        contract.original_raw_resolved = None

                # Re-normalize contract using NormalizationService (event publishing integrated)
                normalization_service = NormalizationService(
                    tenant_id=effective_tenant_id, user_id=user_id or self.user_id
                )
                (
                    hub_contract,
                    detected_spec_type,
                    detected_spec_version,
                    norm_status,
                    norm_errors,
                    norm_warnings,
                ) = normalization_service.normalize_contract(
                    raw_contract=contract_content_for_normalization,
                    format=contract.original_format,
                    spec_type=contract.original_spec_type,
                    tenant_id=effective_tenant_id,
                    user_id=user_id or self.user_id,
                    contract_id=str(contract.id),  # Contract exists, so events will be published
                )

                # Phase 227 Wave 1 (227.L3.4) — mirror the create-path
                # invariant: structural-floor check FIRST, then explicit
                # ``ValidationError`` on validation failure. The pre-Wave-1
                # behaviour ("save raw content and fix later" by setting
                # ``hub_contract=None``) silently dropped the parsed
                # structure and left a NULL ``hub_contract_json`` —
                # exactly the structureless population Wave 0 catalogued.
                enforce_structural_floor(
                    hub_contract,
                    spec_type=detected_spec_type or contract.original_spec_type,
                    spec_version=detected_spec_version
                    or contract.original_spec_version,
                    warnings=norm_warnings,
                    contract_id=str(contract.id),
                    tenant_id=effective_tenant_id,
                    source="update",
                )

                # Non-structural validation failures (missing required
                # `info.name`, malformed JSON, etc.) — generic 400.
                if hub_contract:
                    is_valid, validation_errors = validate_hubcontract_schema(hub_contract)
                    if not is_valid:
                        self._emit_validation_failed_observability(
                            validation_errors=validation_errors,
                            spec_type=detected_spec_type or contract.original_spec_type,
                            spec_version=detected_spec_version,
                            contract_id=str(contract.id),
                            tenant_id=effective_tenant_id,
                            source="update",
                        )
                        raise ValidationError(
                            message="Contract validation failed",
                            code="VALIDATION_ERROR",
                            details={
                                "errors": validation_errors,
                                "spec_type": detected_spec_type or contract.original_spec_type,
                                "spec_version": detected_spec_version,
                            },
                            http_status=400,
                        )

                # Preserve existing extensions (especially x_odps links) when normalizing
                # This ensures ODPS/ODCS bidirectional linking is maintained during normalization
                if hub_contract and contract.hub_contract_json:
                    existing_extensions = contract.hub_contract_json.get("extensions", {})
                    if existing_extensions:
                        # Preserve x_odps links specifically (critical for ODPS/ODCS linking)
                        existing_x_odps = existing_extensions.get("x_odps", {})
                        if existing_x_odps:
                            import structlog

                            logger = structlog.get_logger(__name__)
                            logger.debug(
                                "Preserving x_odps links during normalization",
                                contract_id=str(contract.id),
                                existing_x_odps=existing_x_odps,
                            )
                            if "extensions" not in hub_contract:
                                hub_contract["extensions"] = {}
                            if "x_odps" not in hub_contract["extensions"]:
                                hub_contract["extensions"]["x_odps"] = {}
                            # Merge existing x_odps links with new extensions (preserve existing links)
                            hub_contract["extensions"]["x_odps"].update(existing_x_odps)
                            # Preserve any other extensions that might have been added
                            for key, value in existing_extensions.items():
                                if key != "x_odps" and key not in hub_contract["extensions"]:
                                    hub_contract["extensions"][key] = value
                            logger.debug(
                                "Preserved x_odps links in normalized hub_contract",
                                contract_id=str(contract.id),
                                preserved_x_odps=hub_contract["extensions"]["x_odps"],
                            )

                # Update normalization fields
                contract.hub_contract_version = "1.0.0" if hub_contract else None
                contract.hub_contract_json = hub_contract
                contract.normalization_status = norm_status
                contract.normalization_errors = norm_errors
                contract.normalization_warnings = norm_warnings

                # Reset validation status
                contract.validation_status = None
                contract.validation_errors = []
                contract.validation_warnings = []
                contract.last_validated_at = None

                # If contract was ACTIVE, set to DRAFT since it needs re-validation
                if contract.status == ContractStatus.ACTIVE:
                    contract.status = ContractStatus.DRAFT

            # Update status if provided
            if status is not None:
                # Validate status
                valid_statuses = [s[0] for s in ContractStatus.choices]
                if status not in valid_statuses:
                    raise ValidationError(
                        f"Invalid status: {status}", details={"valid_statuses": valid_statuses}
                    )
                contract.status = status

            contract.save()

            # Phase 227 Wave 1 (227.L8.5) — post-save cache-invalidation
            # cascade. Order: save (above) → contract cache → lineage
            # cache (this contract) → dependents' lineage caches →
            # search re-index → semantic/AI re-ingest (gated) →
            # rate-limited contract.normalized event. Failures are
            # logged but never raised — the user's PATCH already
            # succeeded; we shouldn't 500 them on cache-flush hiccups.
            from hub.apps.contracts.cache_invalidation import run_post_save_cascade
            run_side_effect(
                lambda: run_post_save_cascade(
                    contract,
                    tenant_id=effective_tenant_id,
                    user_id=user_id,
                )
            )

            # Log audit event for contract update
            from hub.apps.audit.utils import create_audit_event
            from hub.apps.tenants.models import Tenant
            from hub.apps.users.models import User

            def _audit_update():
                actor_user = User.objects.get(id=user_id) if user_id else None
                tenant_obj = (
                    Tenant.objects.get(id=effective_tenant_id) if effective_tenant_id else None
                )
                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_UPDATED",
                    actor_user=actor_user,
                    tenant=tenant_obj,
                    resource_id=str(contract.id),
                    details={
                        "status": contract.status,
                        "normalization_status": contract.normalization_status,
                        "updated_fields": ["original_raw"] if original_raw else [],
                    },
                )

            run_side_effect(_audit_update)
            return contract

        return self.execute_with_metrics(
            operation="update_contract", tenant_id=effective_tenant_id, func=_update
        )

    @transaction.atomic
    def delete_contract(
        self, contract_id: str, tenant_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> None:
        """
        Delete a contract (soft delete: set status to RETIRED).

        Args:
            contract_id: Contract ID
            tenant_id: Tenant ID
            user_id: User ID

        Raises:
            NotFoundError: If contract not found
            PermissionError: If user lacks deletion permission
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        # Check deletion permission if user_id is provided
        if effective_user_id:
            from hub.apps.users.models import User

            try:
                user = User.objects.get(id=effective_user_id)
                # Platform admins have all permissions
                if not user.is_platform_admin:
                    # Check if user has required role (TENANT_ADMIN)
                    has_permission = user.has_role("TENANT_ADMIN")
                    if not has_permission:
                        raise PermissionError(
                            f"User {effective_user_id} does not have required role (TENANT_ADMIN) for contract deletion"
                        )
            except User.DoesNotExist:
                raise ValidationError(f"User {effective_user_id} not found")

        def _delete():
            contract = self.get_resource_or_raise(
                Contract, contract_id, tenant_id=effective_tenant_id
            )

            # Phase 18.2.3: validate contract deletion via business rules before mutating
            rules = ContractsBusinessRules(tenant_id=effective_tenant_id, user_id=effective_user_id)
            deletion_result = rules.validate_contract_deletion(contract)
            if not deletion_result.is_valid:
                raise ValidationError(
                    message="; ".join(deletion_result.errors),
                    code="BUSINESS_RULES_VALIDATION",
                    details={
                        "errors": deletion_result.errors,
                        "validation_details": deletion_result.details,
                    },
                    http_status=400,
                )

            contract.status = ContractStatus.RETIRED
            contract.save()

        return self.execute_with_metrics(
            operation="delete_contract", tenant_id=effective_tenant_id, func=_delete
        )

    def list_contracts(
        self,
        tenant_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Contract], Dict[str, Any]]:
        """
        List contracts with filtering and pagination.

        Args:
            tenant_id: Tenant ID
            filters: Optional filters dict
            page: Page number (1-indexed)
            page_size: Page size

        Returns:
            Tuple of (contracts list, pagination metadata)
        """
        effective_tenant_id = tenant_id or self.tenant_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _list():
            queryset = Contract.objects.filter(tenant_id=effective_tenant_id)

            # Apply filters
            if filters:
                if "status" in filters:
                    queryset = queryset.filter(status=filters["status"])
                if "asset_id" in filters:
                    queryset = queryset.filter(asset_id=filters["asset_id"])

            # Order by created_at descending
            queryset = queryset.order_by("-created_at")

            # Paginate
            paginator = Paginator(queryset, page_size)
            if page > paginator.num_pages and paginator.num_pages > 0:
                pagination_meta = {
                    "count": paginator.count,
                    "page": page,
                    "page_size": page_size,
                    "num_pages": paginator.num_pages,
                    "has_next": False,
                    "has_previous": True,
                }
                return [], pagination_meta
            page_obj = paginator.get_page(page)
            pagination_meta = {
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": page_size,
                "num_pages": paginator.num_pages,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            }
            return list(page_obj), pagination_meta

        return self.execute_with_metrics(
            operation="list_contracts", tenant_id=effective_tenant_id, func=_list
        )

    def validate_contract(
        self,
        contract_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        use_async: bool = False,
    ) -> Dict[str, Any]:
        """
        Validate contract using DataContract CLI.

        Args:
            contract_id: Contract ID
            tenant_id: Tenant ID
            user_id: User ID
            use_async: Whether to use async validation (for large contracts)

        Returns:
            Validation result dict

        Raises:
            NotFoundError: If contract not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _validate():
            contract = self.get_resource_or_raise(
                Contract, contract_id, tenant_id=effective_tenant_id
            )

            # Determine if async validation is needed
            contract_size = len(contract.original_raw) if contract.original_raw else 0
            should_use_async = use_async or contract_size > 100000  # 100KB threshold

            if should_use_async:
                # Create async validation job
                from hub.apps.tenants.models import Tenant
                from hub.apps.users.models import User

                tenant = Tenant.objects.get(id=effective_tenant_id)
                user = User.objects.get(id=effective_user_id) if effective_user_id else None
                job = create_job(
                    tenant=tenant,
                    user=user,
                    job_type=JobType.CONTRACT_VALIDATION,
                    resource_type="CONTRACT",
                    resource_id=str(contract.id),
                    details_json={"contract_id": str(contract.id)},
                )

                return {"async": True, "job_id": str(job.id)}
            else:
                # Synchronous validation
                cli_client = DataContractCLIClient()
                # Get raw contract and format
                raw_contract = contract.original_raw or ""
                format_str = (
                    contract.original_format.lower() if contract.original_format else "json"
                )
                result = cli_client.validate(
                    raw_contract=raw_contract, format=format_str, tenant_id=effective_tenant_id
                )

                # Log the raw result for debugging
                logger_instance = structlog.get_logger(__name__)
                logger_instance.debug(
                    "contract_validation_result",
                    contract_id=str(contract.id),
                    result_keys=list(result.keys()) if isinstance(result, dict) else "not_a_dict",
                    validation_status=(
                        result.get("validation_status") if isinstance(result, dict) else None
                    ),
                    valid=result.get("valid") if isinstance(result, dict) else None,
                )

                # Update contract validation status
                # Handle both 'validation_status' and 'valid' fields for compatibility
                validation_status = (
                    result.get("validation_status") if isinstance(result, dict) else None
                )
                if validation_status is None:
                    # Fallback: derive from 'valid' field if validation_status is missing
                    if isinstance(result, dict) and result.get("valid", False):
                        validation_status = ValidationStatus.VALID
                    else:
                        validation_status = ValidationStatus.ERROR

                # Ensure validation_status is a string (handle enum values)
                if hasattr(validation_status, "value"):
                    validation_status = validation_status.value
                elif not isinstance(validation_status, str):
                    validation_status = str(validation_status)

                # Log if validation_status is still None (shouldn't happen with fallback)
                if validation_status is None:
                    logger_instance.warning(
                        "contract_validation_status_missing",
                        contract_id=str(contract.id),
                        result_keys=(
                            list(result.keys()) if isinstance(result, dict) else "not_a_dict"
                        ),
                        result_type=type(result).__name__,
                        message="validation_status is None after processing result",
                    )
                    validation_status = ValidationStatus.ERROR

                contract.validation_status = validation_status
                contract.validation_errors = result.get("errors", [])
                contract.validation_warnings = result.get("warnings", [])
                contract.last_validated_at = timezone.now()
                contract.save()

                from hub.apps.contracts.invalidation_cascade import (
                    maybe_apply_invalidation_after_validation,
                )
                from hub.apps.users.models import User

                actor = None
                if effective_user_id:
                    try:
                        actor = User.objects.get(id=effective_user_id)
                    except User.DoesNotExist:
                        actor = None
                maybe_apply_invalidation_after_validation(
                    contract, actor_user=actor
                )

                return {
                    "async": False,
                    "validation_status": result.get("validation_status"),
                    "valid": result.get("valid", False),
                    "errors": result.get("errors", []),
                    "warnings": result.get("warnings", []),
                    "cli_version": result.get("cli_version"),
                }

        return self.execute_with_metrics(
            operation="validate_contract", tenant_id=effective_tenant_id, func=_validate
        )

    @transaction.atomic
    def auto_generate_odps_for_odcs(
        self,
        odcs_contract_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        target_odps_version: str = "4.1",
    ) -> Contract:
        """
        Auto-generate ODPS contract from ODCS contract when link is missing (marketplace focus).

        Auto-generates ODPS contracts from ODCS contracts with marketplace focus.
        It checks if an ODCS contract has a linked ODPS contract, and if not,
        automatically generates ODPS from HubContract focusing on marketplace aspects.

        The generated ODPS will:
        - Populate product.details from HubContract.info
        - Map HubContract.marketplace.x_odps.* → ODPS pricing/license/access/payment (if present)
        - Note: Technical quality/SLA from ODCS remains in HubContract; ODPS generation focuses on marketplace

        Args:
            odcs_contract_id: ODCS contract UUID
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID (uses service user_id if not provided)
            target_odps_version: Target ODPS version (default: "4.1")

        Returns:
            Created or existing ODPS contract instance

        Raises:
            ValidationError: If contract is not ODCS or missing HubContract
            NotFoundError: If contract not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _auto_generate():
            # Get ODCS contract
            odcs_contract = self.get_resource_or_raise(
                Contract, odcs_contract_id, tenant_id=effective_tenant_id
            )

            # Validate it's an ODCS contract
            if odcs_contract.original_spec_type != OriginalSpecType.ODCS:
                raise ValidationError(
                    f"Contract {odcs_contract_id} is not an ODCS contract (spec_type: {odcs_contract.original_spec_type})"
                )

            # Check if ODCS contract already has a linked ODPS contract
            if odcs_contract.hub_contract_json:
                extensions = odcs_contract.hub_contract_json.get("extensions", {})
                x_odps = extensions.get("x_odps", {})
                odps_link = x_odps.get("odps_link")

                if odps_link:
                    # ODPS contract already linked, return it
                    try:
                        odps_contract = Contract.objects.get(
                            id=odps_link, tenant_id=effective_tenant_id
                        )
                        import structlog

                        logger = structlog.get_logger(__name__)
                        logger.info(
                            "ODPS contract already linked to ODCS contract",
                            odcs_contract_id=str(odcs_contract.id),
                            odps_contract_id=str(odps_contract.id),
                        )
                        return odps_contract
                    except Contract.DoesNotExist:
                        # Link exists but contract not found, remove invalid link
                        import structlog

                        logger = structlog.get_logger(__name__)
                        logger.warning(
                            "Invalid ODPS link found, removing and regenerating",
                            odcs_contract_id=str(odcs_contract.id),
                            odps_link=odps_link,
                        )
                        # Remove invalid link
                        del x_odps["odps_link"]
                        if not x_odps:
                            del extensions["x_odps"]
                        if not extensions:
                            del odcs_contract.hub_contract_json["extensions"]
                        odcs_contract.save(update_fields=["hub_contract_json"])

            # Validate HubContract exists
            if not odcs_contract.hub_contract_json:
                raise ValidationError(
                    f"ODCS contract {odcs_contract_id} has no hub_contract_json. Cannot generate ODPS."
                )

            # Generate ODPS from HubContract (marketplace focus)
            from hub.apps.contracts.normalization import parse_contract
            from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract

            # Get original ODCS contract if available (for embedding in ODPS)
            original_odcs_contract = None
            if (
                odcs_contract.original_raw
                and odcs_contract.original_spec_type == OriginalSpecType.ODCS
            ):
                try:
                    original_odcs_contract = parse_contract(
                        odcs_contract.original_raw, odcs_contract.original_format
                    )
                except Exception as parse_err:
                    logger.debug(
                        "contract_parse_original_odcs_failed",
                        extra={"error_type": type(parse_err).__name__, "error": str(parse_err)},
                    )

            # Generate ODPS document (focuses on marketplace aspects)
            odps_doc = generate_odps_from_hubcontract(
                hub_contract=odcs_contract.hub_contract_json,
                target_version=target_odps_version,
                original_odcs_contract=original_odcs_contract,
                original_odcs_url=None,
            )

            # Format as JSON for storage
            import json

            odps_raw = json.dumps(odps_doc, indent=2)

            # Get user if user_id provided
            user = None
            if effective_user_id:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                try:
                    user = User.objects.get(id=effective_user_id)
                except User.DoesNotExist:
                    pass  # User not found, created_by will be None

            # Detect ODPS version from generated document
            from hub.apps.contracts.odps_version_detection import detect_odps_version

            detected_version = detect_odps_version(odps_doc)

            # Normalize ODPS to HubContract using NormalizationService (for consistency)
            # Note: contract_id not available yet (contract will be created below), so events won't be published
            normalization_service = NormalizationService(
                tenant_id=effective_tenant_id, user_id=effective_user_id
            )
            hub_contract_odps, _, _, norm_status, norm_errors, norm_warnings = (
                normalization_service.normalize_contract(
                    raw_contract=odps_raw,
                    format=OriginalFormat.JSON,
                    spec_type=OriginalSpecType.ODPS,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    # contract_id not available yet - events won't be published
                )
            )

            # Find next available version for this asset to avoid unique constraint violation
            # The constraint unique_contract_version_per_asset requires unique (tenant, asset, version)
            # Since ODPS and ODCS contracts can be linked to the same asset, we need different versions
            if odcs_contract.asset:
                # Find the maximum version for this asset
                max_version = (
                    Contract.objects.filter(
                        tenant_id=effective_tenant_id, asset=odcs_contract.asset
                    ).aggregate(max_version=models.Max("version"))["max_version"]
                    or 0
                )
                next_version = max_version + 1
            else:
                # No asset, use version 1
                next_version = 1

            # Create ODPS contract record
            odps_contract = Contract.objects.create(
                tenant_id=effective_tenant_id,
                asset=odcs_contract.asset,
                version=next_version,  # Use next available version to avoid constraint violation
                original_raw=odps_raw,
                original_format=OriginalFormat.JSON,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version=detected_version or target_odps_version,
                hub_contract_json=hub_contract_odps,
                hub_contract_version="1.0.0" if hub_contract_odps else None,
                normalization_status=norm_status,
                normalization_errors=norm_errors,
                normalization_warnings=norm_warnings,
                status=odcs_contract.status,  # Inherit status from ODCS
                created_by=user,
            )

            # Establish bidirectional link
            # ODPS → ODCS: Store in ODPS contract's hub_contract_json.extensions.x_odps.odcs_link
            if odps_contract.hub_contract_json:
                if "extensions" not in odps_contract.hub_contract_json:
                    odps_contract.hub_contract_json["extensions"] = {}
                if "x_odps" not in odps_contract.hub_contract_json["extensions"]:
                    odps_contract.hub_contract_json["extensions"]["x_odps"] = {}
                odps_contract.hub_contract_json["extensions"]["x_odps"]["odcs_link"] = str(
                    odcs_contract.id
                )
                odps_contract.save(update_fields=["hub_contract_json"])

            # ODCS → ODPS: Store in ODCS contract's hub_contract_json.extensions.x_odps.odps_link
            if odcs_contract.hub_contract_json:
                if "extensions" not in odcs_contract.hub_contract_json:
                    odcs_contract.hub_contract_json["extensions"] = {}
                if "x_odps" not in odcs_contract.hub_contract_json["extensions"]:
                    odcs_contract.hub_contract_json["extensions"]["x_odps"] = {}
                odcs_contract.hub_contract_json["extensions"]["x_odps"]["odps_link"] = str(
                    odps_contract.id
                )
                odcs_contract.save(update_fields=["hub_contract_json"])

            import structlog

            logger = structlog.get_logger(__name__)
            logger.info(
                "ODPS contract auto-generated from ODCS contract",
                odcs_contract_id=str(odcs_contract.id),
                odps_contract_id=str(odps_contract.id),
                target_version=target_odps_version,
            )

            # Publish contract event
            self.publish_contract_created(
                contract_id=str(odps_contract.id),
                asset_id=str(odps_contract.asset.id) if odps_contract.asset else None,
                status=odps_contract.status,
                original_format=odps_contract.original_format,
                original_spec_version=odps_contract.original_spec_version,
            )

            # Publish ODPS-specific event
            self.publish_odps_created(
                contract_id=str(odps_contract.id),
                asset_id=str(odps_contract.asset.id) if odps_contract.asset else None,
                status=odps_contract.status,
                odps_version=target_odps_version,
                original_format=odps_contract.original_format,
            )

            return odps_contract

        return self.execute_with_metrics(
            operation="auto_generate_odps_for_odcs",
            tenant_id=effective_tenant_id,
            func=_auto_generate,
        )

    def link_odps_to_odcs(
        self,
        odcs_contract_id: str,
        odps_contract_id: Optional[str] = None,
        odps_raw: Optional[str] = None,
        odps_format: Optional[str] = None,
        resolve_external_refs: bool = True,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Contract:
        """
        Link ODPS contract to ODCS contract (bidirectional).

        Links ODPS contracts to ODCS contracts bidirectionally.
        It accepts either an existing ODPS contract ID or an ODPS document,
        validates compatibility, and creates bidirectional links.

        If any step fails after links are established, compensation logic will:
        - Remove established links
        - Restore previous state
        - Cleanup resources

        Args:
            odcs_contract_id: ODCS contract ID to link to
            odps_contract_id: Optional existing ODPS contract ID to link
            odps_raw: Optional ODPS document content (if creating new ODPS contract)
            odps_format: Optional ODPS document format (JSON or YAML, required if odps_raw provided)
            resolve_external_refs: If True, resolve external $ref references (default: True)
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)
            user_id: Optional user ID (uses service user_id if not provided)

        Returns:
            Linked ODPS contract instance

        Raises:
            ValidationError: If validation fails
            NotFoundError: If contract not found
        """
        import structlog

        from hub.apps.contracts.odps_linking_compensation import (
            ODPSLinkingCompensation,
            ODPSLinkingState,
        )

        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError(message="tenant_id is required", code="TENANT_ID_REQUIRED")

        # Initialize compensation handler
        compensation = ODPSLinkingCompensation(
            tenant_id=effective_tenant_id, user_id=effective_user_id
        )

        # Initialize state tracking
        state = ODPSLinkingState(
            odcs_contract_id=odcs_contract_id, odps_contract_id=odps_contract_id
        )

        # Initialize logger for outer scope
        logger = structlog.get_logger(__name__)

        # Import metrics at function level
        import time

        from hub.apps.observability.otel_metrics import (
            odps_linking_duration_seconds,
            odps_linking_failures_total,
            odps_linking_success_total,
            odps_linking_total,
        )

        # Track linking direction: ODCS → ODPS (linking ODPS to ODCS)
        linking_direction = "odcs_to_odps"
        start_time = time.time()

        # Increment total linking attempts
        odps_linking_total.labels(
            direction=linking_direction, tenant_id=effective_tenant_id or "unknown"
        ).inc()

        def _link_odps():
            import structlog
            from django.contrib.auth import get_user_model

            from hub.apps.contracts.linking_validation import (
                LinkingValidationError,
                validate_linking,
            )
            from hub.apps.contracts.models import (
                Contract,
                NormalizationStatus,
                OriginalFormat,
                OriginalSpecType,
            )
            from hub.apps.contracts.normalization import normalize_contract
            from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
            from hub.apps.contracts.odps_errors import ODPSRefResolutionError, ODPSValidationError
            from hub.apps.contracts.odps_parser import ODPSParser
            from hub.apps.contracts.odps_version_detection import detect_odps_version
            from hub.apps.contracts.ref_resolver import ExternalRefHandling, RefResolver

            User = get_user_model()
            logger = structlog.get_logger(__name__)

            # Get ODCS contract
            try:
                odcs_contract = Contract.objects.get(id=odcs_contract_id)

                # Store previous ODPS link if it exists (for restoration)
                if odcs_contract.hub_contract_json:
                    extensions = odcs_contract.hub_contract_json.get("extensions", {})
                    x_odps = extensions.get("x_odps", {})
                    if "odps_link" in x_odps:
                        state.previous_odps_link = x_odps.get("odps_link")

            except Contract.DoesNotExist:
                raise NotFoundError(
                    message=f"ODCS contract not found: {odcs_contract_id}",
                    code="ODCS_CONTRACT_NOT_FOUND",
                )

            # Validate ODCS contract
            if odcs_contract.original_spec_type != OriginalSpecType.ODCS:
                raise ValidationError(
                    message=f"Contract {odcs_contract_id} is not an ODCS contract (type: {odcs_contract.original_spec_type})",
                    code="INVALID_CONTRACT_TYPE",
                )

            if str(odcs_contract.tenant_id) != str(effective_tenant_id):
                raise ValidationError(
                    message=f"ODCS contract {odcs_contract_id} does not belong to tenant {effective_tenant_id}",
                    code="TENANT_MISMATCH",
                )

            # Get user for audit logging (needed in all code paths)
            user = None
            if effective_user_id:
                try:
                    user = User.objects.get(id=effective_user_id)
                except User.DoesNotExist:
                    pass

            # Get or create ODPS contract
            odps_contract = None

            if odps_contract_id:
                # Link to existing ODPS contract
                try:
                    odps_contract = Contract.objects.get(id=odps_contract_id)

                    # Store previous ODCS link if it exists (for restoration)
                    if odps_contract.hub_contract_json:
                        extensions = odps_contract.hub_contract_json.get("extensions", {})
                        x_odps = extensions.get("x_odps", {})
                        if "odcs_link" in x_odps:
                            state.previous_odcs_link = x_odps.get("odcs_link")

                except Contract.DoesNotExist:
                    raise NotFoundError(
                        message=f"ODPS contract not found: {odps_contract_id}",
                        code="ODPS_CONTRACT_NOT_FOUND",
                    )

                # Validate existing ODPS contract
                if odps_contract.original_spec_type != OriginalSpecType.ODPS:
                    raise ValidationError(
                        message=f"Contract {odps_contract_id} is not an ODPS contract (type: {odps_contract.original_spec_type})",
                        code="INVALID_CONTRACT_TYPE",
                    )

                if str(odps_contract.tenant_id) != str(effective_tenant_id):
                    raise ValidationError(
                        message=f"ODPS contract {odps_contract_id} does not belong to tenant {effective_tenant_id}",
                        code="TENANT_MISMATCH",
                    )

                # Extract ODCS contract from ODPS product.contract and validate compatibility
                if not odps_contract.hub_contract_json:
                    raise ValidationError(
                        message=f"ODPS contract {odps_contract_id} must be normalized (missing hub_contract_json)",
                        code="ODPS_NOT_NORMALIZED",
                    )

                # Extract ODCS contract from ODPS original_raw
                if not odps_contract.original_raw:
                    raise ValidationError(
                        message=f"ODPS contract {odps_contract_id} missing original_raw",
                        code="ODPS_MISSING_ORIGINAL_RAW",
                    )

                # Parse ODPS document
                # Handle both enum and string formats
                format_str = odps_contract.original_format
                if hasattr(format_str, "value"):
                    format_str = format_str.value
                if hasattr(format_str, "lower"):
                    format_str = format_str.lower()
                else:
                    format_str = str(format_str).lower()

                odps_doc = ODPSParser.parse(content=odps_contract.original_raw, format=format_str)

                # Debug: log the parsed document structure
                import logging

                logger = logging.getLogger(__name__)
                logger.debug(f"Parsed ODPS doc keys: {list(odps_doc.keys())}")
                logger.debug(f"Parsed ODPS doc has product: {'product' in odps_doc}")
                if "product" in odps_doc:
                    logger.debug(f"Parsed ODPS product type: {type(odps_doc['product'])}")
                    logger.debug(f"Parsed ODPS product value: {odps_doc['product']}")
                logger.debug(
                    f"Original raw (first 500 chars): {odps_contract.original_raw[:500] if odps_contract.original_raw else 'None'}"
                )

                # Extract ODCS contract from product.contract
                product = odps_doc.get("product", {})
                if not isinstance(product, dict):
                    # Debug: log what we actually got
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.debug(f"ODPS document structure: {list(odps_doc.keys())}")
                    logger.debug(f"ODPS document has product: {'product' in odps_doc}")
                    raise ValidationError(
                        message="ODPS document must have a 'product' field",
                        code="ODPS_MISSING_PRODUCT",
                    )

                contract_section = product.get("contract")
                if not isinstance(contract_section, dict):
                    # Debug: log what we actually got
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.debug(f"ODPS product structure: {list(product.keys())}")
                    logger.debug(f"ODPS product has contract: {'contract' in product}")
                    logger.debug(f"ODPS product.contract value: {product.get('contract')}")
                    raise ValidationError(
                        message="ODPS product.contract is required for linking",
                        code="ODPS_MISSING_CONTRACT",
                    )

                # Extract ODCS contract from spec
                odcs_from_odps = contract_section.get("spec")
                if not isinstance(odcs_from_odps, dict):
                    raise ValidationError(
                        message="ODPS product.contract.spec must be a dictionary",
                        code="ODPS_INVALID_CONTRACT_SPEC",
                    )

                # Validate that extracted ODCS matches the existing ODCS contract
                # Compare key fields: id, name
                import json

                try:
                    odcs_original = (
                        json.loads(odcs_contract.original_raw) if odcs_contract.original_raw else {}
                    )
                    odcs_id = odcs_from_odps.get("id")
                    odcs_name = odcs_from_odps.get("name")

                    if odcs_id and odcs_original.get("id") != odcs_id:
                        raise ValidationError(
                            message=f"ODPS product.contract.id ({odcs_id}) does not match ODCS contract.id ({odcs_original.get('id')})",
                            code="CONTRACT_ID_MISMATCH",
                        )
                    if odcs_name and odcs_original.get("name") != odcs_name:
                        raise ValidationError(
                            message=f"ODPS product.contract.name ({odcs_name}) does not match ODCS contract.name ({odcs_original.get('name')})",
                            code="CONTRACT_NAME_MISMATCH",
                        )
                except (json.JSONDecodeError, AttributeError) as e:
                    # If we can't parse, log warning but continue with linking validation
                    # The linking validation will catch other incompatibilities
                    pass

            elif odps_raw:
                # Create new ODPS contract from document
                if not odps_format:
                    raise ValidationError(
                        message="odps_format is required when odps_raw is provided",
                        code="ODPS_FORMAT_REQUIRED",
                    )

                # Parse ODPS document
                # Handle both enum and string formats
                format_str = odps_format
                if hasattr(format_str, "value"):
                    format_str = format_str.value
                if hasattr(format_str, "lower"):
                    format_str = format_str.lower()
                else:
                    format_str = str(format_str).lower()

                odps_doc = ODPSParser.parse(content=odps_raw, format=format_str)

                # Detect version
                odps_version = detect_odps_version(odps_doc) or "4.1"

                # Validate ODPS
                is_valid, validation_errors = ODPSParser.validate(odps_doc, version=odps_version)
                if not is_valid:
                    raise ValidationError(
                        message=f"ODPS validation failed: {validation_errors}",
                        code="ODPS_VALIDATION_FAILED",
                    )

                # Resolve $ref references if needed
                if resolve_external_refs:
                    external_ref_handling = ExternalRefHandling.RESOLVE.value
                else:
                    external_ref_handling = ExternalRefHandling.DISABLE.value

                resolver = RefResolver()
                _, resolved_doc = resolver.resolve_all_refs(
                    document=odps_doc,
                    preserve_original=True,
                    external_ref_handling=ExternalRefHandling(external_ref_handling),
                )
                odps_doc = resolved_doc

                # Extract ODCS contract from product.contract and validate compatibility
                product = odps_doc.get("product", {})
                if not isinstance(product, dict):
                    raise ValidationError(
                        message="ODPS document must have a 'product' field",
                        code="ODPS_MISSING_PRODUCT",
                    )

                contract_section = product.get("contract")
                if not isinstance(contract_section, dict):
                    raise ValidationError(
                        message="ODPS product.contract is required for linking",
                        code="ODPS_MISSING_CONTRACT",
                    )

                # Extract ODCS contract from spec
                odcs_from_odps = contract_section.get("spec")
                if not isinstance(odcs_from_odps, dict):
                    raise ValidationError(
                        message="ODPS product.contract.spec must be a dictionary",
                        code="ODPS_INVALID_CONTRACT_SPEC",
                    )

                # Validate that extracted ODCS matches the existing ODCS contract
                import json

                try:
                    odcs_original = (
                        json.loads(odcs_contract.original_raw) if odcs_contract.original_raw else {}
                    )
                    odcs_id = odcs_from_odps.get("id")
                    odcs_name = odcs_from_odps.get("name")
                    if odcs_id and odcs_original.get("id") != odcs_id:
                        raise ValidationError(
                            message=f"ODPS product.contract.id ({odcs_id}) does not match ODCS contract.id ({odcs_original.get('id')})",
                            code="CONTRACT_ID_MISMATCH",
                        )
                    if odcs_name and odcs_original.get("name") != odcs_name:
                        raise ValidationError(
                            message=f"ODPS product.contract.name ({odcs_name}) does not match ODCS contract.name ({odcs_original.get('name')})",
                            code="CONTRACT_NAME_MISMATCH",
                        )
                except (json.JSONDecodeError, AttributeError):
                    # If we can't parse, just continue with normalization
                    pass

                # Normalize ODPS to HubContract
                normalizer = ODPSNormalizer()
                normalization_result = normalizer.normalize(odps_doc, spec_version=odps_version)
                hub_contract_from_odps = normalization_result.hub_contract

                # Phase 227 Wave 1 (227.L3.2 / L3.4 parity) — enforce the
                # structural floor before persisting the linked ODPS row.
                # ``link_odps_to_odcs`` is a public service entry-point
                # (REST: ``views_odps.py:101``, GraphQL: ``schema.py:1568``)
                # that bypasses ``ContractService.create_contract``; without
                # this guard a structureless ODPS doc could land linked.
                # ALWAYS-ON per the 2026-04-30 ungate directive.
                from hub.apps.contracts.structural_floor import (
                    enforce_structural_floor as _enforce_floor,
                )
                _enforce_floor(
                    hub_contract_from_odps,
                    spec_type=OriginalSpecType.ODPS,
                    spec_version=odps_version,
                    warnings=normalization_result.warnings or [],
                    contract_id=None,  # ODPS row not persisted yet.
                )

                # Find next available version for this asset to avoid unique constraint violation
                # The constraint unique_contract_version_per_asset requires unique (tenant, asset, version)
                # Since ODPS and ODCS contracts can be linked to the same asset, we need different versions
                if odcs_contract.asset:
                    # Find the maximum version for this asset
                    max_version = (
                        Contract.objects.filter(
                            tenant_id=effective_tenant_id, asset=odcs_contract.asset
                        ).aggregate(max_version=models.Max("version"))["max_version"]
                        or 0
                    )
                    next_version = max_version + 1
                else:
                    # No asset, use version 1
                    next_version = 1

                # Create ODPS contract record
                # Normalize format to uppercase for enum
                format_upper = odps_format.upper() if isinstance(odps_format, str) else odps_format
                odps_contract = Contract.objects.create(
                    tenant_id=effective_tenant_id,
                    asset=odcs_contract.asset,
                    version=next_version,
                    original_raw=odps_raw,
                    original_format=OriginalFormat(format_upper),
                    original_spec_type=OriginalSpecType.ODPS,
                    original_spec_version=odps_version,
                    hub_contract_json=hub_contract_from_odps,
                    hub_contract_version="1.0.0" if hub_contract_from_odps else None,
                    normalization_status=NormalizationStatus.NORMALIZED_OK,
                    normalization_errors=[],
                    normalization_warnings=normalization_result.warnings or [],
                    status=odcs_contract.status,
                    created_by=user,
                )

                # Track that ODPS contract was created (for compensation)
                state.odps_contract_id = str(odps_contract.id)
                state.odps_contract_created = True

                logger = structlog.get_logger(__name__)
                logger.info(
                    "ODPS contract created for linking",
                    odcs_contract_id=str(odcs_contract.id),
                    odps_contract_id=str(odps_contract.id),
                )
            else:
                raise ValidationError(
                    message="Either odps_contract_id or odps_raw must be provided",
                    code="ODPS_SOURCE_REQUIRED",
                )

            # Check if already linked
            logger = structlog.get_logger(__name__)
            if odps_contract.hub_contract_json:
                extensions = odps_contract.hub_contract_json.get("extensions", {})
                x_odps = extensions.get("x_odps", {})
                existing_odcs_link = x_odps.get("odcs_link")
                if existing_odcs_link and str(existing_odcs_link) == str(odcs_contract.id):
                    # Already linked to this ODCS contract, return existing ODPS contract
                    logger.info(
                        "ODPS contract already linked to ODCS contract",
                        odps_contract_id=str(odps_contract.id),
                        odcs_contract_id=str(odcs_contract.id),
                    )
                    return odps_contract

            # Validate linking compatibility
            try:
                validate_linking(
                    odps_contract_id=str(odps_contract.id),
                    odcs_contract_id=str(odcs_contract.id),
                    tenant_id=effective_tenant_id,
                )
            except LinkingValidationError as e:
                raise ValidationError(
                    message=f"Linking validation failed: {e.message}",
                    code=e.error_code,
                    details=e.context,
                )

            # Track ODPS contract ID if not already set
            if not state.odps_contract_id:
                state.odps_contract_id = str(odps_contract.id)

            # Establish bidirectional link
            # ODPS → ODCS: Store in ODPS contract's hub_contract_json.extensions.x_odps.odcs_link
            # Ensure hub_contract_json exists (create minimal structure if needed to store links)
            if not odps_contract.hub_contract_json:
                odps_contract.hub_contract_json = {
                    "id": str(odps_contract.id),
                    "hub_contract_version": odps_contract.hub_contract_version or "1.0.0",
                    "schema": {},
                }
            if "extensions" not in odps_contract.hub_contract_json:
                odps_contract.hub_contract_json["extensions"] = {}
            if "x_odps" not in odps_contract.hub_contract_json["extensions"]:
                odps_contract.hub_contract_json["extensions"]["x_odps"] = {}
            odps_contract.hub_contract_json["extensions"]["x_odps"]["odcs_link"] = str(
                odcs_contract.id
            )
            odps_contract.save(update_fields=["hub_contract_json"])

            # ODCS → ODPS: Store in ODCS contract's hub_contract_json.extensions.x_odps.odps_link
            # Ensure hub_contract_json exists (create minimal structure if needed to store links)
            if not odcs_contract.hub_contract_json:
                odcs_contract.hub_contract_json = {
                    "id": str(odcs_contract.id),
                    "hub_contract_version": odcs_contract.hub_contract_version or "1.0.0",
                    "schema": {},
                }
            if "extensions" not in odcs_contract.hub_contract_json:
                odcs_contract.hub_contract_json["extensions"] = {}
            if "x_odps" not in odcs_contract.hub_contract_json["extensions"]:
                odcs_contract.hub_contract_json["extensions"]["x_odps"] = {}
            odcs_contract.hub_contract_json["extensions"]["x_odps"]["odps_link"] = str(
                odps_contract.id
            )
            odcs_contract.save(update_fields=["hub_contract_json"])

            logger.info(
                "ODPS-ODCS contracts linked bidirectionally",
                odcs_contract_id=str(odcs_contract.id),
                odps_contract_id=str(odps_contract.id),
            )

            # Create audit log for ODPS linking
            from hub.apps.audit.utils import create_audit_event
            from hub.apps.tenants.models import Tenant

            def _audit_linking():
                tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                create_audit_event(
                    resource_type="ODPS",
                    action="ODPS_LINKED",
                    actor_user=user,
                    tenant=tenant_obj,
                    resource_id=str(odps_contract.id),
                    result="SUCCESS",
                    details={
                        "odps_contract_id": str(odps_contract.id),
                        "odcs_contract_id": str(odcs_contract.id),
                        "link_type": "bidirectional",
                        "odps_contract_created": (
                            state.odps_contract_created
                            if hasattr(state, "odps_contract_created")
                            else False
                        ),
                        "request_id": self.request_id,
                    },
                )

            run_side_effect(_audit_linking)

            # Publish contract event
            try:
                event_id = self.publish_contract_created(
                    contract_id=str(odps_contract.id),
                    asset_id=str(odps_contract.asset.id) if odps_contract.asset else None,
                    status=odps_contract.status,
                    original_format=odps_contract.original_format,
                    original_spec_version=odps_contract.original_spec_version,
                )
                if event_id and state.events_published is not None:
                    state.events_published.append(str(event_id))
            except Exception as e:
                logger.exception(
                    "contract_created_event_publish_failed",
                    contract_id=str(odps_contract.id),
                    error=str(e),
                    message="Failed to publish contract created event, triggering compensation",
                )
                # Compensate for the failure
                try:
                    compensation.compensate(
                        state=state,
                        remove_links=True,
                        restore_state=True,
                        cleanup_resources=True,
                        publish_compensation_events=True,
                    )
                except Exception as comp_error:
                    logger.exception(
                        "compensation_failed_after_event_publish_failure",
                        contract_id=str(odps_contract.id),
                        error=str(comp_error),
                        message="Compensation failed after event publish failure",
                    )
                raise ValidationError(
                    message=f"Failed to publish contract created event: {str(e)}",
                    code="CONTRACT_EVENT_PUBLISH_FAILED",
                    details={"contract_id": str(odps_contract.id), "error": str(e)},
                ) from e

            # Publish ODPS-specific events
            # Publish ODPS created event (if this is a new contract)
            if state.odps_contract_created:
                event_id = run_side_effect(
                    self.publish_odps_created,
                    contract_id=str(odps_contract.id),
                    asset_id=str(odps_contract.asset.id) if odps_contract.asset else None,
                    status=odps_contract.status,
                    odps_version=odps_contract.original_spec_version,
                    original_format=odps_contract.original_format,
                )
                if event_id and state.events_published is not None:
                    state.events_published.append(str(event_id))

            # Publish ODPS linked event
            try:
                event_id = self.publish_odps_linked(
                    odps_contract_id=str(odps_contract.id),
                    odcs_contract_id=str(odcs_contract.id),
                    link_type="bidirectional",
                )
                if event_id and state.events_published is not None:
                    state.events_published.append(str(event_id))
            except Exception as e:
                logger.exception(
                    "odps_linked_event_publish_failed",
                    odps_contract_id=str(odps_contract.id),
                    odcs_contract_id=str(odcs_contract.id),
                    error=str(e),
                    message="Failed to publish ODPS linked event, triggering compensation",
                )
                # Compensate for the failure
                try:
                    compensation.compensate(
                        state=state,
                        remove_links=True,
                        restore_state=True,
                        cleanup_resources=True,
                        publish_compensation_events=True,
                    )
                except Exception as comp_error:
                    logger.exception(
                        "compensation_failed_after_linked_event_publish_failure",
                        odps_contract_id=str(odps_contract.id),
                        error=str(comp_error),
                        message="Compensation failed after linked event publish failure",
                    )
                raise ValidationError(
                    message=f"Failed to publish ODPS linked event: {str(e)}",
                    code="ODPS_LINKED_EVENT_PUBLISH_FAILED",
                    details={
                        "odps_contract_id": str(odps_contract.id),
                        "odcs_contract_id": str(odcs_contract.id),
                        "error": str(e),
                    },
                ) from e

            # Send notification email for ODPS linking status
            try:
                from hub.apps.notifications.tasks import (
                    send_odps_linking_status_email,
                )

                _odps_id = str(odps_contract.id)
                _odcs_id = str(odcs_contract.id)
                _uid = effective_user_id
                _tid = effective_tenant_id
                transaction.on_commit(
                    lambda: send_odps_linking_status_email.delay(
                        odps_contract_id=_odps_id,
                        status="completed",
                        status_message=(
                            "ODPS contract linked to ODCS"
                            " contract successfully"
                        ),
                        odcs_contract_id=_odcs_id,
                        progress_percentage=100.0,
                        current_phase="completed",
                        validation_passed=True,
                        user_id=_uid,
                        tenant_id=_tid,
                    )
                )
            except Exception as notify_error:
                # Log but don't fail linking if notification fails
                logger.warning(
                    "odps_linking_notification_failed",
                    odps_contract_id=str(odps_contract.id),
                    odcs_contract_id=str(odcs_contract.id),
                    error=str(notify_error),
                    message="Failed to send ODPS linking status notification (non-critical)",
                )

            return odps_contract

        # Wrap with error handling for metrics. Failure audit runs outside this atomic
        # block so FAILURE rows are not rolled back with the aborted ODPS linking txn.
        try:
            with transaction.atomic():
                result = _link_odps()
            # Record success metrics
            duration = time.time() - start_time
            odps_linking_success_total.labels(
                direction=linking_direction, tenant_id=effective_tenant_id or "unknown"
            ).inc()
            odps_linking_duration_seconds.labels(
                direction=linking_direction, tenant_id=effective_tenant_id or "unknown"
            ).observe(duration)
            return result
        except Exception as e:
            # Record failure metrics
            duration = time.time() - start_time
            error_code = getattr(e, "code", type(e).__name__)
            odps_linking_failures_total.labels(
                direction=linking_direction,
                error_code=str(error_code),
                tenant_id=effective_tenant_id or "unknown",
            ).inc()
            odps_linking_duration_seconds.labels(
                direction=linking_direction, tenant_id=effective_tenant_id or "unknown"
            ).observe(duration)

            # Create audit log for ODPS linking failure
            try:
                from django.contrib.auth import get_user_model

                from hub.apps.audit.utils import create_audit_event
                from hub.apps.tenants.models import Tenant

                User = get_user_model()
                tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                user_obj = User.objects.get(id=effective_user_id) if effective_user_id else None
                create_audit_event(
                    resource_type="ODPS",
                    action="ODPS_LINKED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=(
                        state.odps_contract_id
                        if hasattr(state, "odps_contract_id") and state.odps_contract_id
                        else None
                    ),
                    result="FAILURE",
                    details={
                        "odcs_contract_id": odcs_contract_id,
                        "odps_contract_id": (
                            state.odps_contract_id if hasattr(state, "odps_contract_id") else None
                        ),
                        "error": str(e),
                        "error_code": str(error_code),
                        "request_id": self.request_id,
                    },
                )
            except Exception as audit_error:
                # Don't fail on audit logging failure
                logger.warning(
                    "odps_linking_audit_logging_failed_on_error",
                    error=str(audit_error),
                    message="Failed to create audit log for ODPS linking failure (non-critical)",
                )

            # If linking fails after links were established, compensate
            # Note: If the failure occurs before links are established, transaction rollback
            # will handle it automatically. We only need to compensate if links
            # were established but subsequent operations failed.
            if state.odps_contract_id and state.odcs_contract_id:
                logger.exception(
                    "odps_linking_failed_after_links_established",
                    odps_contract_id=state.odps_contract_id,
                    odcs_contract_id=state.odcs_contract_id,
                    error=str(e),
                    message="ODPS linking failed after links established, triggering compensation",
                )
                try:
                    # Compensate outside the transaction to ensure it happens
                    # even if the transaction is rolled back
                    compensation.compensate(
                        state=state,
                        remove_links=True,
                        restore_state=True,
                        cleanup_resources=True,
                        publish_compensation_events=True,
                    )
                except Exception as comp_error:
                    logger.exception(
                        "compensation_failed_after_odps_linking_failure",
                        odps_contract_id=state.odps_contract_id,
                        error=str(comp_error),
                        message="Compensation failed after ODPS linking failure",
                    )
            raise

    @transaction.atomic
    def unlink_odps_from_odcs(
        self, odcs_contract_id: str, tenant_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> None:
        """
        Unlink ODPS contract from ODCS contract (removes bidirectional links).

        This method removes the bidirectional links between an ODCS contract
        and its linked ODPS contract.

        Args:
            odcs_contract_id: ODCS contract ID to unlink from
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)
            user_id: Optional user ID (uses service user_id if not provided)

        Raises:
            ValidationError: If validation fails
            NotFoundError: If contract not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError(message="tenant_id is required", code="TENANT_ID_REQUIRED")

        def _unlink_odps():
            import structlog

            from hub.apps.contracts.models import Contract, OriginalSpecType

            logger = structlog.get_logger(__name__)

            # Get ODCS contract
            try:
                odcs_contract = Contract.objects.get(id=odcs_contract_id)
            except Contract.DoesNotExist:
                raise NotFoundError(
                    message=f"ODCS contract not found: {odcs_contract_id}",
                    code="ODCS_CONTRACT_NOT_FOUND",
                )

            # Validate ODCS contract
            if odcs_contract.original_spec_type != OriginalSpecType.ODCS:
                raise ValidationError(
                    message=f"Contract {odcs_contract_id} is not an ODCS contract (type: {odcs_contract.original_spec_type})",
                    code="INVALID_CONTRACT_TYPE",
                )

            if str(odcs_contract.tenant_id) != str(effective_tenant_id):
                raise ValidationError(
                    message=f"ODCS contract {odcs_contract_id} does not belong to tenant {effective_tenant_id}",
                    code="TENANT_MISMATCH",
                )

            # Get linked ODPS contract ID from ODCS contract
            odps_contract_id = None
            if odcs_contract.hub_contract_json:
                extensions = odcs_contract.hub_contract_json.get("extensions", {})
                x_odps = extensions.get("x_odps", {})
                odps_contract_id = x_odps.get("odps_link")

            if not odps_contract_id:
                # No link exists, nothing to unlink
                logger.info(
                    "No ODPS link found on ODCS contract", odcs_contract_id=str(odcs_contract.id)
                )
                return

            # Get ODPS contract
            try:
                odps_contract = Contract.objects.get(id=odps_contract_id)
            except Contract.DoesNotExist:
                # ODPS contract doesn't exist, but link exists - clean up the link
                logger.warning(
                    "ODPS contract not found but link exists, cleaning up link",
                    odcs_contract_id=str(odcs_contract.id),
                    odps_contract_id=str(odps_contract_id),
                )
                # Remove link from ODCS contract
                if odcs_contract.hub_contract_json:
                    extensions = odcs_contract.hub_contract_json.get("extensions", {})
                    x_odps = extensions.get("x_odps", {})
                    if "odps_link" in x_odps:
                        del x_odps["odps_link"]
                        odcs_contract.save(update_fields=["hub_contract_json"])
                return

            # Validate ODPS contract belongs to same tenant
            if str(odps_contract.tenant_id) != str(effective_tenant_id):
                raise ValidationError(
                    message=f"ODPS contract {odps_contract_id} does not belong to tenant {effective_tenant_id}",
                    code="TENANT_MISMATCH",
                )

            # Remove bidirectional links
            # Remove ODCS link from ODPS contract
            if odps_contract.hub_contract_json:
                extensions = odps_contract.hub_contract_json.get("extensions", {})
                x_odps = extensions.get("x_odps", {})
                if "odcs_link" in x_odps:
                    del x_odps["odcs_link"]
                    odps_contract.save(update_fields=["hub_contract_json"])

            # Remove ODPS link from ODCS contract
            if odcs_contract.hub_contract_json:
                extensions = odcs_contract.hub_contract_json.get("extensions", {})
                x_odps = extensions.get("x_odps", {})
                if "odps_link" in x_odps:
                    del x_odps["odps_link"]
                    odcs_contract.save(update_fields=["hub_contract_json"])

            logger.info(
                "ODPS-ODCS contracts unlinked successfully",
                odcs_contract_id=str(odcs_contract.id),
                odps_contract_id=str(odps_contract.id),
            )

        return self.execute_with_metrics(
            operation="unlink_odps_from_odcs", tenant_id=effective_tenant_id, func=_unlink_odps
        )

    def get_contract_links(
        self, contract_id: str, tenant_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all links for a contract (ODPS and ODCS links).

        Args:
            contract_id: Contract ID to get links for
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)
            user_id: Optional user ID (uses service user_id if not provided)

        Returns:
            Dictionary with linked contract information:
            {
                "odps_link": {"id": "...", "status": "...", ...} or None,
                "odcs_link": {"id": "...", "status": "...", ...} or None
            }

        Raises:
            NotFoundError: If contract not found
        """
        effective_tenant_id = tenant_id or self.tenant_id

        if not effective_tenant_id:
            raise ValidationError(message="tenant_id is required", code="TENANT_ID_REQUIRED")

        from hub.apps.contracts.models import Contract
        from hub.apps.contracts.serializers import ContractSerializer

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise NotFoundError(
                message=f"Contract not found: {contract_id}", code="CONTRACT_NOT_FOUND"
            )

        # Validate tenant
        if str(contract.tenant_id) != str(effective_tenant_id):
            raise ValidationError(
                message=f"Contract {contract_id} does not belong to tenant {effective_tenant_id}",
                code="TENANT_MISMATCH",
            )

        result = {"odps_link": None, "odcs_link": None}

        if not contract.hub_contract_json:
            return result

        extensions = contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})

        # Get ODPS link (if this is an ODCS contract)
        odps_link_id = x_odps.get("odps_link")
        if odps_link_id:
            try:
                odps_contract = Contract.objects.get(id=odps_link_id)
                if str(odps_contract.tenant_id) == str(effective_tenant_id):
                    # Return basic contract info to avoid serializer issues with ODPS schema structure
                    result["odps_link"] = {
                        "id": str(odps_contract.id),
                        "original_spec_type": odps_contract.original_spec_type,
                        "original_spec_version": odps_contract.original_spec_version,
                        "status": odps_contract.status,
                        "created_at": (
                            odps_contract.created_at.isoformat()
                            if odps_contract.created_at
                            else None
                        ),
                        "updated_at": (
                            odps_contract.updated_at.isoformat()
                            if odps_contract.updated_at
                            else None
                        ),
                    }
            except Contract.DoesNotExist:
                pass

        # Get ODCS link (if this is an ODPS contract)
        odcs_link_id = x_odps.get("odcs_link")
        if odcs_link_id:
            try:
                odcs_contract = Contract.objects.get(id=odcs_link_id)
                if str(odcs_contract.tenant_id) == str(effective_tenant_id):
                    # Return basic contract info to avoid serializer issues
                    result["odcs_link"] = {
                        "id": str(odcs_contract.id),
                        "original_spec_type": odcs_contract.original_spec_type,
                        "original_spec_version": odcs_contract.original_spec_version,
                        "status": odcs_contract.status,
                        "created_at": (
                            odcs_contract.created_at.isoformat()
                            if odcs_contract.created_at
                            else None
                        ),
                        "updated_at": (
                            odcs_contract.updated_at.isoformat()
                            if odcs_contract.updated_at
                            else None
                        ),
                    }
            except Contract.DoesNotExist:
                pass

        return result

    def coordinate_odcs_odps_operations(
        self,
        odcs_contract_id: str,
        odps_operation: str,
        odps_contract_id: Optional[str] = None,
        odps_raw: Optional[str] = None,
        odps_format: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Coordinate ODCS and ODPS operations for unified contract management.

        This method provides a unified interface for coordinating operations between
        ODCS and ODPS contracts using ODPSService. It handles:
        - Linking ODPS to ODCS contracts
        - Creating ODPS contracts from ODCS
        - Exporting ODPS contracts
        - Normalizing ODPS contracts

        Args:
            odcs_contract_id: ODCS contract ID
            odps_operation: Operation to perform ('link', 'create', 'export', 'normalize')
            odps_contract_id: Optional existing ODPS contract ID (for 'link' operation)
            odps_raw: Optional ODPS document content (for 'create' operation)
            odps_format: Optional ODPS document format (required if odps_raw provided)
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID (uses service user_id if not provided)

        Returns:
            Dictionary with operation results

        Raises:
            ValidationError: If operation is invalid or validation fails
            NotFoundError: If contract not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError(message="tenant_id is required", code="TENANT_ID_REQUIRED")

        def _coordinate():
            from hub.apps.contracts.services import ODPSService

            # Initialize ODPSService
            odps_service = ODPSService(
                tenant_id=effective_tenant_id, user_id=effective_user_id, request_id=self.request_id
            )

            result = {
                "operation": odps_operation,
                "odcs_contract_id": odcs_contract_id,
                "success": False,
            }

            if odps_operation == "link":
                # Link ODPS to ODCS
                if not odps_contract_id and not odps_raw:
                    raise ValidationError(
                        message="Either odps_contract_id or odps_raw must be provided for 'link' operation",
                        code="ODPS_SOURCE_REQUIRED",
                    )

                linked_contract = odps_service.link_odps_to_odcs(
                    odcs_contract_id=odcs_contract_id,
                    odps_contract_id=odps_contract_id,
                    odps_raw=odps_raw,
                    odps_format=odps_format,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                )

                result.update(
                    {"success": True, "odps_contract_id": str(linked_contract.id), "linked": True}
                )

            elif odps_operation == "create":
                # Create ODPS from ODCS
                if not odps_raw:
                    raise ValidationError(
                        message="odps_raw is required for 'create' operation",
                        code="ODPS_RAW_REQUIRED",
                    )

                created_contract = odps_service.create_odps(
                    odps_raw=odps_raw,
                    odps_format=odps_format or "json",
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                )

                result.update(
                    {"success": True, "odps_contract_id": str(created_contract.id), "created": True}
                )

            elif odps_operation == "export":
                # Export ODPS contract
                if not odps_contract_id:
                    raise ValidationError(
                        message="odps_contract_id is required for 'export' operation",
                        code="ODPS_CONTRACT_ID_REQUIRED",
                    )

                exported = odps_service.export_odps(
                    contract_id=odps_contract_id,
                    output_format=odps_format or "json",
                    tenant_id=effective_tenant_id,
                )

                result.update(
                    {"success": True, "exported_content": exported, "format": odps_format or "json"}
                )

            elif odps_operation == "normalize":
                # Normalize ODPS document
                if not odps_raw:
                    raise ValidationError(
                        message="odps_raw is required for 'normalize' operation",
                        code="ODPS_RAW_REQUIRED",
                    )

                import json

                odps_doc = json.loads(odps_raw) if isinstance(odps_raw, str) else odps_raw

                hub_contract = odps_service.normalize_odps(
                    odps_doc=odps_doc, tenant_id=effective_tenant_id
                )

                result.update({"success": True, "hub_contract": hub_contract, "normalized": True})

            else:
                raise ValidationError(
                    message=f"Invalid odps_operation: {odps_operation}. Must be 'link', 'create', 'export', or 'normalize'",
                    code="INVALID_OPERATION",
                )

            return result

        return self.execute_with_metrics(
            operation="coordinate_odcs_odps_operations",
            tenant_id=effective_tenant_id,
            func=_coordinate,
        )


class ODPSService(BaseService, ODPSEventPublisher):
    """
    Service for ODPS (Open Data Product Standard) operations.

    Provides business logic for:
    - ODPS contract creation
    - ODPS normalization
    - ODPS linking to ODCS
    - ODPS export
    - ODPS generation from HubContract

    This service encapsulates all ODPS-specific operations with proper
    transaction management, event publishing, and error handling.
    """

    service_name = "odps_service"

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """
        Initialize ODPSService.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
            request_id: Request ID for tracing
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.request_id = request_id
        # Initialize event publisher
        ODPSEventPublisher.__init__(self)

    def create_odps(
        self,
        odps_raw: str,
        odps_format: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        resolve_external_refs: bool = True,
        target_version: Optional[str] = None,
    ) -> Contract:
        """
        Create ODPS contract from raw ODPS document.

        This method creates a new ODPS contract by:
        1. Parsing and validating the ODPS document
        2. Resolving $ref references (if enabled)
        3. Normalizing to HubContract format
        4. Creating the contract record
        5. Publishing events

        If any step fails after contract creation, compensation logic will:
        - Rollback created contracts
        - Cleanup resources
        - Restore previous state

        Args:
            odps_raw: Raw ODPS document content (JSON or YAML string)
            odps_format: Format of ODPS document ("json" or "yaml")
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID (uses service user_id if not provided)
            asset_id: Optional asset ID to associate with contract
            resolve_external_refs: If True, resolve external $ref references (default: True)
            target_version: Optional target ODPS version (auto-detected if not provided)

        Returns:
            Created Contract instance

        Raises:
            ValidationError: If validation fails
            NotFoundError: If asset not found
        """
        import structlog

        from hub.apps.contracts.odps_compensation import ODPSCreationCompensation, ODPSCreationState

        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError(message="tenant_id is required", code="TENANT_ID_REQUIRED")

        # Validate tenant_id format and existence before any DB write
        import uuid as uuid_module

        try:
            uuid_module.UUID(effective_tenant_id)
        except (ValueError, TypeError, AttributeError):
            raise ValidationError(
                message="tenant_id must be a valid UUID",
                code="INVALID_TENANT_ID",
                details={"tenant_id": effective_tenant_id},
            )
        from hub.apps.tenants.models import Tenant

        if not Tenant.objects.filter(id=effective_tenant_id).exists():
            raise NotFoundError(
                message=f"Tenant not found: {effective_tenant_id}", code="TENANT_NOT_FOUND"
            )

        # Validate user_id format and existence when provided
        if effective_user_id:
            try:
                uuid_module.UUID(effective_user_id)
            except (ValueError, TypeError, AttributeError):
                raise ValidationError(
                    message="user_id must be a valid UUID",
                    code="INVALID_USER_ID",
                    details={"user_id": effective_user_id},
                )
            from django.contrib.auth import get_user_model

            UserModel = get_user_model()
            if not UserModel.objects.filter(id=effective_user_id).exists():
                raise NotFoundError(
                    message=f"User not found: {effective_user_id}", code="USER_NOT_FOUND"
                )

        # Initialize compensation handler
        compensation = ODPSCreationCompensation(
            tenant_id=effective_tenant_id, user_id=effective_user_id
        )

        # Initialize state tracking
        state = ODPSCreationState(asset_id=asset_id)

        # Initialize logger for outer scope
        logger = structlog.get_logger(__name__)

        def _create():
            import json as json_module

            import structlog
            import yaml
            from django.contrib.auth import get_user_model

            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import (
                Contract,
                ContractStatus,
                NormalizationStatus,
                OriginalFormat,
                OriginalSpecType,
            )
            from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
            from hub.apps.contracts.odps_errors import (
                ODPSNormalizationError,
                ODPSRefResolutionError,
                ODPSValidationError,
            )
            from hub.apps.contracts.odps_parser import ODPSParser
            from hub.apps.contracts.odps_version_detection import detect_odps_version
            from hub.apps.contracts.ref_resolver import ExternalRefHandling, RefResolver

            User = get_user_model()
            logger = structlog.get_logger(__name__)

            # Validate asset exists if provided
            asset = None
            if asset_id:
                try:
                    asset = Asset.objects.get(id=asset_id, tenant_id=effective_tenant_id)
                    # Store previous asset version for state restoration
                    if hasattr(asset, "version"):
                        state.asset_previous_version = asset.version
                except Asset.DoesNotExist:
                    raise NotFoundError(
                        message=f"Asset not found: {asset_id}", code="ASSET_NOT_FOUND"
                    )

            # Get user (existence already validated above)
            user = None
            if effective_user_id:
                try:
                    user = User.objects.get(id=effective_user_id)
                except User.DoesNotExist:
                    raise NotFoundError(
                        message=f"User not found: {effective_user_id}", code="USER_NOT_FOUND"
                    )

            # Parse ODPS document
            format_str = odps_format.lower()
            if format_str not in ["json", "yaml"]:
                raise ValidationError(
                    message=f"Invalid format: {odps_format}. Must be 'json' or 'yaml'",
                    code="INVALID_FORMAT",
                )

            try:
                odps_doc = ODPSParser.parse(content=odps_raw, format=format_str)
            except Exception as e:
                raise ValidationError(
                    message=f"Failed to parse ODPS document: {str(e)}",
                    code="ODPS_PARSE_FAILED",
                    details={"error": str(e), "format": format_str},
                ) from e

            # Detect version
            if target_version:
                odps_version = target_version
            else:
                try:
                    odps_version = detect_odps_version(odps_doc) or "4.1"
                except Exception as e:
                    logger.warning(
                        "odps_version_detection_failed",
                        error=str(e),
                        message="Failed to detect ODPS version, using default 4.1",
                    )
                    odps_version = "4.1"

            # Phase 18.2.4: Validate ODPS via business rules before create (run first so
            # structure/version failures return BUSINESS_RULES_VALIDATION)
            odps_rules = ODPSBusinessRules()
            structure_result = odps_rules.validate_odps_structure(odps_doc, strict=False)
            if not structure_result.is_valid:
                raise ValidationError(
                    message="; ".join(structure_result.errors)
                    or "ODPS structure validation failed",
                    code="BUSINESS_RULES_VALIDATION",
                    details={
                        "validation_errors": structure_result.errors,
                        "warnings": structure_result.warnings,
                        "version": odps_version,
                    },
                )
            version_result = odps_rules.validate_odps_version(
                odps_doc, required_version=odps_version
            )
            if not version_result.is_valid:
                raise ValidationError(
                    message="; ".join(version_result.errors) or "ODPS version validation failed",
                    code="BUSINESS_RULES_VALIDATION",
                    details={
                        "validation_errors": version_result.errors,
                        "warnings": version_result.warnings,
                        "version": odps_version,
                    },
                )

            # Schema validation (ODPSParser)
            is_valid, validation_errors = ODPSParser.validate(odps_doc, version=odps_version)
            if not is_valid:
                raise ValidationError(
                    message=f"ODPS validation failed: {validation_errors}",
                    code="ODPS_VALIDATION_FAILED",
                    details={"validation_errors": validation_errors, "version": odps_version},
                )

            # Resolve $ref references if needed
            # Preserve original_raw on failure - always use original input for original_raw
            odps_raw_resolved = None
            if resolve_external_refs:
                try:
                    resolver = RefResolver()
                    _, resolved_doc = resolver.resolve_all_refs(
                        document=odps_doc,
                        preserve_original=True,
                        external_ref_handling=ExternalRefHandling.RESOLVE,
                    )
                    odps_doc = resolved_doc

                    # Serialize resolved document back to string
                    if format_str == "json":
                        odps_raw_resolved = json_module.dumps(
                            odps_doc, indent=2, ensure_ascii=False
                        )
                    else:
                        odps_raw_resolved = yaml.dump(
                            odps_doc, default_flow_style=False, allow_unicode=True
                        )
                except Exception as e:
                    logger.warning(
                        "odps_ref_resolution_failed",
                        error=str(e),
                        message="Failed to resolve $ref references, continuing with original document",
                    )
                    # If resolution fails, odps_raw_resolved remains None, we'll use original odps_raw
                    odps_raw_resolved = None

            # Normalize ODPS to HubContract.
            #
            # Phase 227 Wave 1 (227.L3.1) — eliminate the silent-nullify
            # path. The legacy behaviour caught ``ODPSNormalizationError``,
            # set ``hub_contract = None``, and persisted a row with
            # ``hub_contract_json=NULL`` and ``normalization_status=
            # NORMALIZATION_FAILED``. That is *exactly* the structureless
            # population Wave 0 catalogued. ``ContractService.create_contract``
            # was hardened in L3.1; this alternate ODPS-create entry-point
            # MUST mirror the invariant or callers can sidestep the floor by
            # routing through ``create_odps`` (reachable from the GraphQL
            # mutation, ``coordinate_odcs_odps_operations``, and the
            # ``views_odps`` REST surface).
            normalizer = ODPSNormalizer()
            try:
                normalization_result = normalizer.normalize(odps_doc, spec_version=odps_version)
            except ODPSNormalizationError as e:
                logger.warning(
                    "odps_normalization_failed",
                    error=str(e),
                    error_code=getattr(e, "error_code", "NORMALIZATION_FAILED"),
                    message="ODPS normalization failed — refusing to persist structureless row",
                )
                raise ValidationError(
                    message=f"ODPS normalization failed: {str(e)}",
                    code=getattr(e, "error_code", "NORMALIZATION_FAILED"),
                    details={
                        "errors": [str(e)],
                        "field_path": getattr(e, "field_path", None),
                        "context": getattr(e, "context", {}),
                        "spec_type": OriginalSpecType.ODPS,
                        "spec_version": odps_version,
                    },
                    http_status=400,
                ) from e

            hub_contract = normalization_result.hub_contract
            normalization_status = normalization_result.status
            normalization_errors = normalization_result.errors or []
            normalization_warnings = normalization_result.warnings or []

            # Phase 227 Wave 1 (227.L3.2 / L3.4 parity) — enforce the
            # structural floor on this alternate write path too. Without
            # this guard a successful-but-structureless normalization
            # (e.g. ODPS doc with empty ``outputPorts[]``) would land in
            # the DB. ALWAYS-ON per the 2026-04-30 ungate directive.
            from hub.apps.contracts.structural_floor import enforce_structural_floor as _enforce_floor
            _enforce_floor(
                hub_contract,
                spec_type=OriginalSpecType.ODPS,
                spec_version=odps_version,
                warnings=normalization_warnings,
                contract_id=None,  # Not persisted yet.
            )

            # Calculate version
            version = 1
            if asset:
                latest_contract = (
                    Contract.objects.filter(tenant_id=effective_tenant_id, asset=asset)
                    .order_by("-version")
                    .first()
                )
                if latest_contract:
                    version = latest_contract.version + 1

            # Create contract record - preserve original_raw on failure
            # original_raw should always contain the original input (odps_raw), not the resolved version
            # original_raw_resolved should contain the resolved version if resolution succeeded
            contract = Contract.objects.create(
                tenant_id=effective_tenant_id,
                asset=asset,
                version=version,
                original_raw=odps_raw,  # Always preserve original input
                original_raw_resolved=(
                    odps_raw_resolved if odps_raw_resolved else None
                ),  # Resolved version if available
                original_format=(
                    OriginalFormat.JSON if format_str == "json" else OriginalFormat.YAML
                ),
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version=odps_version,
                hub_contract_json=hub_contract,
                hub_contract_version="1.0.0" if hub_contract else None,
                normalization_status=normalization_status,
                normalization_errors=normalization_errors,
                normalization_warnings=normalization_warnings,
                status=ContractStatus.DRAFT,
                created_by=user,
            )

            # Track contract in state for compensation
            state.contract_id = str(contract.id)

            logger.info(
                "odps_contract_created",
                contract_id=str(contract.id),
                tenant_id=effective_tenant_id,
                odps_version=odps_version,
                normalization_status=normalization_status,
                message="ODPS contract created successfully",
            )

            # Create audit log for ODPS creation
            from hub.apps.audit.utils import create_audit_event
            from hub.apps.tenants.models import Tenant

            def _audit_odps_creation():
                tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                create_audit_event(
                    resource_type="ODPS",
                    action="ODPS_CREATED",
                    actor_user=user,
                    tenant=tenant_obj,
                    resource_id=str(contract.id),
                    result="SUCCESS",
                    details={
                        "contract_id": str(contract.id),
                        "odps_version": odps_version,
                        "original_format": (
                            contract.original_format.value
                            if hasattr(contract.original_format, "value")
                            else str(contract.original_format)
                        ),
                        "normalization_status": (
                            normalization_status.value
                            if hasattr(normalization_status, "value")
                            else str(normalization_status)
                        ),
                        "asset_id": str(asset.id) if asset else None,
                        "resolve_external_refs": resolve_external_refs,
                        "request_id": self.request_id,
                    },
                )

            run_side_effect(_audit_odps_creation)

            # Send notification email for ODPS creation completion or normalization failure
            if user:
                try:
                    from hub.apps.notifications.tasks import (
                        send_odps_creation_completion_email,
                        send_odps_normalization_failure_email,
                    )

                    if normalization_status == NormalizationStatus.NORMALIZATION_FAILED:
                        # Send normalization failure notification
                        error_message = (
                            "; ".join(normalization_errors)
                            if normalization_errors
                            else "ODPS normalization failed"
                        )
                        _cid = str(contract.id)
                        _err = error_message
                        _errs = normalization_errors
                        transaction.on_commit(
                            lambda: send_odps_normalization_failure_email.delay(
                                contract_id=_cid,
                                error_message=_err,
                                error_code="ODPS_NORMALIZATION_ERROR",
                                errors=_errs,
                                field_path=None,
                            )
                        )
                    else:
                        # Send creation completion notification
                        _cid = str(contract.id)
                        transaction.on_commit(
                            lambda: send_odps_creation_completion_email.delay(_cid)
                        )
                except Exception as e:
                    # Log but don't fail ODPS creation if notification fails
                    logger.warning(
                        "odps_creation_notification_failed",
                        contract_id=str(contract.id),
                        error=str(e),
                        message="Failed to send ODPS notification (non-critical)",
                    )

            # Publish events (track event IDs for compensation if needed)
            try:
                event_id = self.publish_odps_created(
                    contract_id=str(contract.id),
                    asset_id=str(asset.id) if asset else None,
                    status=contract.status,
                    odps_version=odps_version,
                    original_format=contract.original_format,
                )
                if event_id and state.events_published is not None:
                    state.events_published.append(str(event_id))
            except Exception as e:
                # If event publishing fails after contract creation, we need to compensate
                logger.exception(
                    "odps_created_event_publish_failed",
                    contract_id=str(contract.id),
                    error=str(e),
                    message="Failed to publish ODPS created event, triggering compensation",
                )
                # Compensate for the failure
                try:
                    compensation.compensate(
                        state=state,
                        rollback_contract=True,
                        cleanup_resources=True,
                        restore_state=True,
                        publish_compensation_events=True,
                    )
                except Exception as comp_error:
                    logger.exception(
                        "compensation_failed_after_event_publish_failure",
                        contract_id=str(contract.id),
                        error=str(comp_error),
                        message="Compensation failed after event publish failure",
                    )
                raise ValidationError(
                    message=f"Failed to publish ODPS created event: {str(e)}",
                    code="ODPS_EVENT_PUBLISH_FAILED",
                    details={"contract_id": str(contract.id), "error": str(e)},
                ) from e

            if hub_contract:
                event_id = run_side_effect(
                    self.publish_odps_normalized,
                    contract_id=str(contract.id),
                    odps_version=odps_version,
                    normalization_status=(
                        normalization_status.value
                        if hasattr(normalization_status, "value")
                        else str(normalization_status)
                    ),
                )
                if event_id and state.events_published is not None:
                    state.events_published.append(str(event_id))

            return contract

        try:
            with transaction.atomic():
                return self.execute_with_metrics(
                    operation="create_odps", tenant_id=effective_tenant_id, func=_create
                )
        except Exception as e:
            # Create audit log for ODPS creation failure
            try:
                from django.contrib.auth import get_user_model

                from hub.apps.audit.utils import create_audit_event
                from hub.apps.tenants.models import Tenant

                User = get_user_model()
                tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                user_obj = User.objects.get(id=effective_user_id) if effective_user_id else None
                create_audit_event(
                    resource_type="ODPS",
                    action="ODPS_CREATED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=(
                        state.contract_id
                        if hasattr(state, "contract_id") and state.contract_id
                        else None
                    ),
                    result="FAILURE",
                    details={
                        "error": str(e),
                        "error_code": getattr(e, "code", "UNKNOWN_ERROR"),
                        "asset_id": asset_id,
                        "resolve_external_refs": resolve_external_refs,
                        "request_id": self.request_id,
                    },
                )
            except Exception as audit_error:
                # Don't fail on audit logging failure
                logger.warning(
                    "odps_audit_logging_failed_on_error",
                    error=str(audit_error),
                    message="Failed to create audit log for ODPS creation failure (non-critical)",
                )

            # If creation fails after contract was created, compensate
            # Note: If the failure occurs before contract creation, transaction rollback
            # will handle it automatically. We only need to compensate if contract
            # was created but subsequent operations failed.
            if state.contract_id:
                logger.exception(
                    "odps_creation_failed_after_contract_creation",
                    contract_id=state.contract_id,
                    error=str(e),
                    message="ODPS creation failed after contract creation, triggering compensation",
                )
                try:
                    # Compensate outside the transaction to ensure it happens
                    # even if the transaction is rolled back
                    compensation.compensate(
                        state=state,
                        rollback_contract=True,
                        cleanup_resources=True,
                        restore_state=True,
                        publish_compensation_events=True,
                    )
                except Exception as comp_error:
                    logger.exception(
                        "compensation_failed_after_odps_creation_failure",
                        contract_id=state.contract_id,
                        error=str(comp_error),
                        message="Compensation failed after ODPS creation failure",
                    )
            raise

    def normalize_odps(
        self,
        odps_doc: Dict[str, Any],
        odps_version: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Normalize ODPS document to HubContract format.

        This method normalizes an ODPS document (dict) to HubContract format
        without creating a contract record. Useful for validation and transformation.

        Args:
            odps_doc: ODPS document dictionary
            odps_version: Optional ODPS version (auto-detected if not provided)
            tenant_id: Optional tenant ID for metrics

        Returns:
            HubContract dictionary

        Raises:
            ValidationError: If normalization fails
        """
        effective_tenant_id = tenant_id or self.tenant_id

        def _normalize():
            import structlog

            from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
            from hub.apps.contracts.odps_errors import ODPSNormalizationError
            from hub.apps.contracts.odps_version_detection import detect_odps_version

            logger = structlog.get_logger(__name__)

            # Detect version if not provided
            if not odps_version:
                try:
                    detected_version = detect_odps_version(odps_doc) or "4.1"
                except Exception as e:
                    logger.warning(
                        "odps_version_detection_failed",
                        error=str(e),
                        message="Failed to detect ODPS version, using default 4.1",
                    )
                    detected_version = "4.1"
            else:
                detected_version = odps_version

            # Normalize
            normalizer = ODPSNormalizer()
            try:
                normalization_result = normalizer.normalize(odps_doc, spec_version=detected_version)
                hub_contract = normalization_result.hub_contract

                if not hub_contract:
                    # Create audit log for normalization failure
                    try:
                        from django.contrib.auth import get_user_model

                        from hub.apps.audit.utils import create_audit_event
                        from hub.apps.tenants.models import Tenant

                        User = get_user_model()
                        tenant_obj = (
                            Tenant.objects.get(id=effective_tenant_id)
                            if effective_tenant_id
                            else None
                        )
                        user_obj = User.objects.get(id=self.user_id) if self.user_id else None
                        if tenant_obj:
                            create_audit_event(
                                resource_type="ODPS",
                                action="ODPS_NORMALIZED",
                                actor_user=user_obj,
                                tenant=tenant_obj,
                                resource_id=None,
                                result="FAILURE",
                                details={
                                    "error": "ODPS normalization failed: no HubContract generated",
                                    "odps_version": detected_version,
                                    "errors": normalization_result.errors or [],
                                    "warnings": normalization_result.warnings or [],
                                    "request_id": self.request_id,
                                },
                            )
                    except Exception as audit_error:
                        logger.warning(
                            "odps_normalize_audit_logging_failed",
                            error=str(audit_error),
                            message="Failed to create audit log for ODPS normalization failure (non-critical)",
                        )

                    raise ValidationError(
                        message="ODPS normalization failed: no HubContract generated",
                        code="NORMALIZATION_FAILED",
                        details={
                            "errors": normalization_result.errors or [],
                            "warnings": normalization_result.warnings or [],
                        },
                    )

                # Phase 227 Wave 1 (227.L3.2 / L3.4 parity) — enforce the
                # structural floor on this preview/normalize path. Even
                # though ``normalize_odps`` does not itself persist, its
                # output is consumed by ``coordinate_odcs_odps_operations``
                # (services.py:2420) and the ``views_odps`` REST surface;
                # surfacing ``STRUCTURELESS_CONTRACT`` here gives the
                # caller a typed code to act on instead of returning a
                # silently-empty hub_contract dict.
                from hub.apps.contracts.structural_floor import (
                    enforce_structural_floor as _enforce_floor,
                )
                _enforce_floor(
                    hub_contract,
                    spec_type=OriginalSpecType.ODPS,
                    spec_version=detected_version,
                    warnings=normalization_result.warnings or [],
                    contract_id=None,
                )

                # Create audit log for successful normalization
                try:
                    from django.contrib.auth import get_user_model

                    from hub.apps.audit.utils import create_audit_event
                    from hub.apps.tenants.models import Tenant

                    User = get_user_model()
                    tenant_obj = (
                        Tenant.objects.get(id=effective_tenant_id) if effective_tenant_id else None
                    )
                    user_obj = User.objects.get(id=self.user_id) if self.user_id else None
                    if tenant_obj:
                        create_audit_event(
                            resource_type="ODPS",
                            action="ODPS_NORMALIZED",
                            actor_user=user_obj,
                            tenant=tenant_obj,
                            resource_id=None,
                            result="SUCCESS",
                            details={
                                "odps_version": detected_version,
                                "warnings": normalization_result.warnings or [],
                                "request_id": self.request_id,
                            },
                        )
                except Exception as audit_error:
                    logger.warning(
                        "odps_normalize_audit_logging_failed",
                        error=str(audit_error),
                        message="Failed to create audit log for ODPS normalization (non-critical)",
                    )

                return hub_contract

            except ODPSNormalizationError as e:
                # Create audit log for normalization error
                try:
                    from django.contrib.auth import get_user_model

                    from hub.apps.audit.utils import create_audit_event
                    from hub.apps.tenants.models import Tenant

                    User = get_user_model()
                    tenant_obj = (
                        Tenant.objects.get(id=effective_tenant_id) if effective_tenant_id else None
                    )
                    user_obj = User.objects.get(id=self.user_id) if self.user_id else None
                    if tenant_obj:
                        create_audit_event(
                            resource_type="ODPS",
                            action="ODPS_NORMALIZED",
                            actor_user=user_obj,
                            tenant=tenant_obj,
                            resource_id=None,
                            result="FAILURE",
                            details={
                                "error": str(e),
                                "error_code": getattr(e, "error_code", "NORMALIZATION_FAILED"),
                                "field_path": getattr(e, "field_path", None),
                                "odps_version": detected_version,
                                "request_id": self.request_id,
                            },
                        )
                except Exception as audit_error:
                    logger.warning(
                        "odps_normalize_audit_logging_failed",
                        error=str(audit_error),
                        message="Failed to create audit log for ODPS normalization error (non-critical)",
                    )

                raise ValidationError(
                    message=f"ODPS normalization failed: {str(e)}",
                    code=getattr(e, "error_code", "NORMALIZATION_FAILED"),
                    details={
                        "field_path": getattr(e, "field_path", None),
                        "context": getattr(e, "context", {}),
                    },
                ) from e

        return self.execute_with_metrics(
            operation="normalize_odps", tenant_id=effective_tenant_id, func=_normalize
        )

    def link_odps_to_odcs(
        self,
        odcs_contract_id: str,
        odps_contract_id: Optional[str] = None,
        odps_raw: Optional[str] = None,
        odps_format: Optional[str] = None,
        resolve_external_refs: bool = True,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Contract:
        """
        Link ODPS contract to ODCS contract (bidirectional).

        This method delegates to ContractService.link_odps_to_odcs() to maintain
        consistency and avoid code duplication. No method-level transaction: the
        service implementation uses an inner atomic block and records FAILURE
        audit events outside that block so audits are not rolled back.

        Args:
            odcs_contract_id: ODCS contract ID to link to
            odps_contract_id: Optional existing ODPS contract ID to link
            odps_raw: Optional ODPS document content (if creating new ODPS contract)
            odps_format: Optional ODPS document format (required if odps_raw provided)
            resolve_external_refs: If True, resolve external $ref references (default: True)
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)
            user_id: Optional user ID (uses service user_id if not provided)

        Returns:
            Linked ODPS contract instance

        Raises:
            ValidationError: If validation fails
            NotFoundError: If contract not found
        """
        # Delegate to ContractService to maintain consistency
        contract_service = ContractService(
            tenant_id=tenant_id or self.tenant_id,
            user_id=user_id or self.user_id,
            request_id=self.request_id,
        )
        return contract_service.link_odps_to_odcs(
            odcs_contract_id=odcs_contract_id,
            odps_contract_id=odps_contract_id,
            odps_raw=odps_raw,
            odps_format=odps_format,
            resolve_external_refs=resolve_external_refs,
            tenant_id=tenant_id or self.tenant_id,
            user_id=user_id or self.user_id,
        )

    def export_odps(
        self,
        contract_id: str,
        output_format: str = "json",
        odps_version: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> str:
        """
        Export ODPS contract to JSON or YAML format.

        This method exports an existing ODPS contract (or generates ODPS from HubContract)
        to the specified format.

        Args:
            contract_id: Contract ID
            output_format: Output format ("json" or "yaml", default: "json")
            odps_version: Optional target ODPS version (default: contract's version or 4.1)
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)

        Returns:
            ODPS document as string (JSON or YAML)

        Raises:
            NotFoundError: If contract not found
            ValidationError: If export fails
        """
        effective_tenant_id = tenant_id or self.tenant_id

        if not effective_tenant_id:
            raise ValidationError(message="tenant_id is required", code="TENANT_ID_REQUIRED")

        # Record export metrics
        import time

        from hub.apps.observability.otel_metrics import (
            odps_export_duration_seconds,
            odps_export_size_bytes,
            odps_export_total,
        )

        export_start_time = time.time()
        output_format_lower = output_format.lower()

        if output_format_lower not in ["json", "yaml"]:
            # Record failure metric
            odps_export_total.labels(
                status="failure", format=output_format_lower, tenant_id=effective_tenant_id
            ).inc()
            raise ValidationError(
                message=f"Invalid output format: {output_format}. Must be 'json' or 'yaml'",
                code="INVALID_FORMAT",
            )

        def _export():
            import structlog

            from hub.apps.contracts.models import Contract, OriginalSpecType
            from hub.apps.contracts.normalization import parse_contract
            from hub.apps.contracts.odps_errors import ODPSExportError
            from hub.apps.contracts.odps_generator import (
                format_odps_as_json,
                format_odps_as_yaml,
                generate_odps_from_hubcontract,
            )

            logger = structlog.get_logger(__name__)

            # Get contract
            contract = self.get_resource_or_raise(
                Contract, contract_id, tenant_id=effective_tenant_id
            )

            # Check if contract has hub_contract_json (required for export)
            if not contract.hub_contract_json:
                # Record failure metric
                odps_export_total.labels(
                    status="failure", format=output_format_lower, tenant_id=effective_tenant_id
                ).inc()
                raise ValidationError(
                    message="Contract has no hub_contract_json. Cannot export as ODPS format.",
                    code="MISSING_HUB_CONTRACT",
                )

            # Determine ODPS version
            target_odps_version = odps_version or contract.original_spec_version or "4.1"

            # Validate requested ODPS version is supported (reject e.g. "99.99")
            from hub.apps.contracts.business_rules import SUPPORTED_ODPS_VERSIONS

            if target_odps_version not in SUPPORTED_ODPS_VERSIONS:
                major = target_odps_version.split(".")[0] if "." in target_odps_version else None
                is_supported = bool(
                    major
                    and any(
                        s == f"{major}.x" or s.startswith(f"{major}.")
                        for s in SUPPORTED_ODPS_VERSIONS
                    )
                )
                if not is_supported:
                    odps_export_total.labels(
                        status="failure",
                        format=output_format_lower,
                        tenant_id=effective_tenant_id,
                    ).inc()
                    raise ValidationError(
                        message=(
                            f"Unsupported ODPS version '{target_odps_version}'. "
                            f"Supported: {', '.join(SUPPORTED_ODPS_VERSIONS)}"
                        ),
                        code="UNSUPPORTED_ODPS_VERSION",
                        details={"supported_versions": list(SUPPORTED_ODPS_VERSIONS)},
                    )

            # Get original ODCS contract if available (for embedding in ODPS)
            original_odcs_contract = None
            if contract.original_raw and contract.original_spec_type == OriginalSpecType.ODCS:
                try:
                    original_odcs_contract = parse_contract(
                        contract.original_raw, contract.original_format
                    )
                except Exception as parse_err:
                    logger.debug(
                        "contract_parse_original_odcs_failed",
                        extra={"error_type": type(parse_err).__name__, "error": str(parse_err)},
                    )

            # Generate ODPS document
            try:
                odps_doc = generate_odps_from_hubcontract(
                    hub_contract=contract.hub_contract_json,
                    target_version=target_odps_version,
                    original_odcs_contract=original_odcs_contract,
                    original_odcs_url=None,
                )
            except ODPSExportError as e:
                # Record failure metric
                odps_export_total.labels(
                    status="failure", format=output_format_lower, tenant_id=effective_tenant_id
                ).inc()
                raise ValidationError(
                    message=f"Failed to generate ODPS document: {str(e)}",
                    code=getattr(e, "error_code", "EXPORT_FAILED"),
                    details=getattr(e, "context", {}),
                ) from e

            # Format output
            try:
                if output_format_lower == "yaml":
                    output = format_odps_as_yaml(odps_doc)
                else:
                    output = format_odps_as_json(odps_doc)
            except ODPSExportError as e:
                # Record failure metric
                odps_export_total.labels(
                    status="failure", format=output_format_lower, tenant_id=effective_tenant_id
                ).inc()
                raise ValidationError(
                    message=f"Failed to format ODPS document: {str(e)}",
                    code=getattr(e, "error_code", "EXPORT_FAILED"),
                    details=getattr(e, "context", {}),
                ) from e

            # Calculate metrics
            export_duration = time.time() - export_start_time
            export_size_bytes = len(output.encode("utf-8"))

            # Categorize size
            if export_size_bytes < 10240:
                size_category = "small"
            elif export_size_bytes < 102400:
                size_category = "medium"
            elif export_size_bytes < 1048576:
                size_category = "large"
            else:
                size_category = "xlarge"

            # Record success metrics
            odps_export_total.labels(
                status="success", format=output_format_lower, tenant_id=effective_tenant_id
            ).inc()

            odps_export_duration_seconds.labels(
                format=output_format_lower,
                size_category=size_category,
                tenant_id=effective_tenant_id,
            ).observe(export_duration)

            odps_export_size_bytes.labels(
                format=output_format_lower, tenant_id=effective_tenant_id
            ).observe(export_size_bytes)

            logger.info(
                "odps_export_completed",
                contract_id=str(contract_id),
                tenant_id=effective_tenant_id,
                output_format=output_format_lower,
                odps_version=target_odps_version,
                size_bytes=export_size_bytes,
                duration_seconds=export_duration,
                message="ODPS export completed successfully",
            )

            # Create audit log for ODPS export
            try:
                from django.contrib.auth import get_user_model

                from hub.apps.audit.utils import create_audit_event
                from hub.apps.tenants.models import Tenant

                User = get_user_model()
                tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                user_obj = User.objects.get(id=self.user_id) if self.user_id else None
                create_audit_event(
                    resource_type="ODPS",
                    action="ODPS_EXPORTED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=str(contract.id),
                    result="SUCCESS",
                    details={
                        "contract_id": str(contract.id),
                        "output_format": output_format_lower,
                        "odps_version": target_odps_version,
                        "size_bytes": export_size_bytes,
                        "duration_seconds": export_duration,
                        "request_id": self.request_id,
                    },
                )
            except Exception as e:
                # Log but don't fail export if audit logging fails
                logger.warning(
                    "odps_export_audit_logging_failed",
                    contract_id=str(contract_id),
                    error=str(e),
                    message="Failed to create audit log for ODPS export (non-critical)",
                )

            # Publish export event
            self.publish_odps_export_completed(
                contract_id=str(contract_id),
                export_format=output_format_lower,
                output_format=output_format_lower,
                file_size=export_size_bytes,
                duration_ms=int(export_duration * 1000),
            )

            return output

        try:
            return self.execute_with_metrics(
                operation="export_odps", tenant_id=effective_tenant_id, func=_export
            )
        except Exception as e:
            # Record failure metric if not already recorded
            try:
                odps_export_total.labels(
                    status="failure", format=output_format_lower, tenant_id=effective_tenant_id
                ).inc()
            except Exception as metrics_err:
                logger.debug(
                    "contract_odps_export_metrics_failed",
                    extra={"error_type": type(metrics_err).__name__, "error": str(metrics_err)},
                )

            # Create audit log for ODPS export failure
            try:
                from django.contrib.auth import get_user_model

                from hub.apps.audit.utils import create_audit_event
                from hub.apps.tenants.models import Tenant

                User = get_user_model()
                tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                user_obj = User.objects.get(id=self.user_id) if self.user_id else None
                create_audit_event(
                    resource_type="ODPS",
                    action="ODPS_EXPORTED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=str(contract_id),
                    result="FAILURE",
                    details={
                        "contract_id": str(contract_id),
                        "output_format": output_format_lower,
                        "error": str(e),
                        "error_code": getattr(e, "code", type(e).__name__),
                        "request_id": self.request_id,
                    },
                )
            except Exception as audit_error:
                logger.warning(
                    "odps_export_audit_logging_failed_on_error",
                    contract_id=str(contract_id),
                    error=str(audit_error),
                    message="Failed to create audit log for ODPS export failure (non-critical)",
                )

            # Publish export failed event
            try:
                self.publish_odps_export_failed(
                    contract_id=str(contract_id),
                    export_format=output_format_lower,
                    error_message=str(e),
                )
            except Exception as event_err:
                logger.warning(
                    "odps_export_event_publish_failed",
                    extra={"error_type": type(event_err).__name__, "error": str(event_err), "contract_id": str(contract_id)},
                )

            raise

    def generate_odps_from_hubcontract(
        self,
        hub_contract: Dict[str, Any],
        target_version: str = "4.1",
        original_odcs_contract: Optional[Dict[str, Any]] = None,
        original_odcs_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate ODPS document from HubContract format.

        This method is a service wrapper around the generate_odps_from_hubcontract()
        function, providing service-level error handling and metrics.

        Args:
            hub_contract: HubContract dictionary
            target_version: Target ODPS version (default: "4.1")
            original_odcs_contract: Optional original ODCS contract dictionary to embed inline
            original_odcs_url: Optional URL to original ODCS contract to reference

        Returns:
            ODPS document as dictionary

        Raises:
            ValidationError: If generation fails
        """

        def _generate():
            from hub.apps.contracts.odps_errors import ODPSExportError
            from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract

            try:
                return generate_odps_from_hubcontract(
                    hub_contract=hub_contract,
                    target_version=target_version,
                    original_odcs_contract=original_odcs_contract,
                    original_odcs_url=original_odcs_url,
                )
            except ODPSExportError as e:
                raise ValidationError(
                    message=f"Failed to generate ODPS document: {str(e)}",
                    code=getattr(e, "error_code", "EXPORT_FAILED"),
                    details=getattr(e, "context", {}),
                ) from e

        return self.execute_with_metrics(
            operation="generate_odps_from_hubcontract", tenant_id=self.tenant_id, func=_generate
        )
