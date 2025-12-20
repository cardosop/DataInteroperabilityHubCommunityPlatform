"""
Contract Service

Business logic for contract operations.
"""
from typing import Dict, Any, Optional, List, Tuple
from django.db import transaction
from django.core.paginator import Paginator
from django.utils import timezone

from hub.apps.core.services.base import BaseService, ValidationError, NotFoundError
from hub.apps.core.events.service_publishers import ContractEventPublisher
from hub.apps.contracts.models import Contract, ContractStatus, NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import normalize_contract, validate_hubcontract_schema
from hub.apps.contracts.cli_client import DataContractCLIClient
from hub.apps.assets.models import Asset
from hub.apps.jobs.utils import create_job
from hub.apps.jobs.models import JobType


class ContractService(BaseService, ContractEventPublisher):
    """
    Service for contract operations.

    Provides business logic for retrieving and validating contracts.
    """
    service_name = "contract_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None, request_id: Optional[str] = None):
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
        # Initialize event publisher (ContractEventPublisher.__init__ will handle super())
        ContractEventPublisher.__init__(self)

    def get_contract(
        self,
        contract_id: str,
        tenant_id: Optional[str] = None
    ) -> Contract:
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
                Contract,
                contract_id,
                tenant_id=effective_tenant_id
            )
        )

    def get_active_contract_for_asset(
        self,
        asset_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[Contract]:
        """
        Get active contract for an asset.

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
            try:
                return Contract.objects.get(
                    asset_id=asset_id,
                    tenant_id=effective_tenant_id,
                    status=ContractStatus.ACTIVE
                )
            except Contract.DoesNotExist:
                return None

        return self.execute_with_metrics(
            operation="get_active_contract_for_asset",
            tenant_id=effective_tenant_id,
            func=_get_contract
        )

    def validate_contract_active(
        self,
        contract_id: str,
        tenant_id: Optional[str] = None
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
                Contract,
                contract_id,
                tenant_id=effective_tenant_id
            )

            if contract.status != ContractStatus.ACTIVE:
                raise ValidationError(
                    f"Contract is not active (status: {contract.status})",
                    details={"contract_id": contract_id, "status": contract.status}
                )

            return contract

        return self.execute_with_metrics(
            operation="validate_contract_active",
            tenant_id=effective_tenant_id,
            func=_validate
        )

    @transaction.atomic
    def create_contract(
        self,
        original_raw: str,
        original_format: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        original_spec_type: Optional[str] = None
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

        Returns:
            Created contract instance

        Raises:
            ValidationError: If validation fails
            NotFoundError: If asset not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        # Detect spec type if not provided (capture before nested function)
        effective_spec_type = original_spec_type or OriginalSpecType.ODCS

        def _create():
            # Validate asset exists if provided
            asset = None
            if asset_id:
                try:
                    asset = Asset.objects.get(id=asset_id, tenant_id=effective_tenant_id)
                except Asset.DoesNotExist:
                    raise NotFoundError("Asset", asset_id)

            # Normalize contract
            hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = normalize_contract(
                raw_contract=original_raw,
                format=original_format,
                spec_type=effective_spec_type
            )

            # Check for DCS rejection
            if norm_status == NormalizationStatus.NORMALIZATION_FAILED and norm_errors:
                dcs_rejection_errors = [
                    e for e in norm_errors
                    if 'data contract specification' in e.lower() or 'dcs' in e.lower() or 'no longer supported' in e.lower()
                ]
                if dcs_rejection_errors:
                    raise ValidationError(
                        message='DCS contracts are no longer supported',
                        details={'code': 'DCS_NOT_SUPPORTED', 'errors': norm_errors}
                    )

            # Validate HubContract schema if normalization succeeded
            if hub_contract:
                is_valid, validation_errors = validate_hubcontract_schema(hub_contract)
                if not is_valid:
                    norm_status = NormalizationStatus.NORMALIZATION_FAILED
                    norm_errors.extend(validation_errors)
                    hub_contract = None

            # Get user if user_id provided
            user = None
            if effective_user_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(id=effective_user_id)
                except User.DoesNotExist:
                    pass  # User not found, created_by will be None

            # Create contract
            contract = Contract.objects.create(
                tenant_id=effective_tenant_id,
                asset=asset,
                original_raw=original_raw,
                original_format=original_format,
                original_spec_type=detected_spec_type or effective_spec_type,
                original_spec_version=detected_spec_version or "3.0.2",
                hub_contract_json=hub_contract,
                hub_contract_version="1.0.0" if hub_contract else None,
                normalization_status=norm_status,
                normalization_errors=norm_errors,
                normalization_warnings=norm_warnings,
                status=ContractStatus.DRAFT,
                created_by=user
            )

            # Index for search
            try:
                from hub.apps.search.indexing import SearchIndexer
                indexer = SearchIndexer()
                indexer.index_contract(contract)
            except Exception as e:
                # Log but don't fail contract creation if indexing fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to index contract {contract.id} for search: {e}")

            # Create audit log
            try:
                from hub.apps.audit.utils import create_audit_event
                from hub.apps.tenants.models import Tenant
                tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_CREATED",
                    actor_user=user,
                    tenant=tenant_obj,
                    resource_id=str(contract.id),
                    details={
                        "contract_id": str(contract.id),
                        "original_spec_type": contract.original_spec_type,
                        "normalization_status": contract.normalization_status
                    }
                )
            except Exception as e:
                # Log but don't fail contract creation if audit logging fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to create audit log for contract {contract.id}: {e}")

            return contract

        return self.execute_with_metrics(
            operation="create_contract",
            tenant_id=effective_tenant_id,
            func=_create
        )

    @transaction.atomic
    def update_contract(
        self,
        contract_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        original_raw: Optional[str] = None,
        original_format: Optional[str] = None,
        status: Optional[str] = None
    ) -> Contract:
        """
        Update a contract.

        Args:
            contract_id: Contract ID
            tenant_id: Tenant ID
            user_id: User ID
            original_raw: Updated contract content (optional)
            original_format: Updated format (optional)
            status: Updated status (optional)

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
                Contract,
                contract_id,
                tenant_id=effective_tenant_id
            )

            # Update original_raw if provided
            if original_raw is not None:
                contract.original_raw = original_raw
                if original_format:
                    contract.original_format = original_format

                # Re-normalize contract
                hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = normalize_contract(
                    raw_contract=contract.original_raw,
                    format=contract.original_format,
                    spec_type=contract.original_spec_type
                )

                # Validate HubContract schema if normalization succeeded
                if hub_contract:
                    is_valid, validation_errors = validate_hubcontract_schema(hub_contract)
                    if not is_valid:
                        norm_status = NormalizationStatus.NORMALIZATION_FAILED
                        norm_errors.extend(validation_errors)
                        hub_contract = None

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
                        f"Invalid status: {status}",
                        details={"valid_statuses": valid_statuses}
                    )
                contract.status = status

            contract.save()
            return contract

        return self.execute_with_metrics(
            operation="update_contract",
            tenant_id=effective_tenant_id,
            func=_update
        )

    @transaction.atomic
    def delete_contract(
        self,
        contract_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        Delete a contract (soft delete: set status to RETIRED).

        Args:
            contract_id: Contract ID
            tenant_id: Tenant ID
            user_id: User ID

        Raises:
            NotFoundError: If contract not found
        """
        effective_tenant_id = tenant_id or self.tenant_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _delete():
            contract = self.get_resource_or_raise(
                Contract,
                contract_id,
                tenant_id=effective_tenant_id
            )

            contract.status = ContractStatus.RETIRED
            contract.save()

        return self.execute_with_metrics(
            operation="delete_contract",
            tenant_id=effective_tenant_id,
            func=_delete
        )

    def list_contracts(
        self,
        tenant_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20
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
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'asset_id' in filters:
                    queryset = queryset.filter(asset_id=filters['asset_id'])

            # Order by created_at descending
            queryset = queryset.order_by('-created_at')

            # Paginate
            paginator = Paginator(queryset, page_size)
            page_obj = paginator.get_page(page)

            pagination_meta = {
                'count': paginator.count,
                'page': page,
                'page_size': page_size,
                'num_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }

            return list(page_obj), pagination_meta

        return self.execute_with_metrics(
            operation="list_contracts",
            tenant_id=effective_tenant_id,
            func=_list
        )

    def validate_contract(
        self,
        contract_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        use_async: bool = False
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
                Contract,
                contract_id,
                tenant_id=effective_tenant_id
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
                    details_json={
                        'contract_id': str(contract.id)
                    }
                )

                return {
                    'async': True,
                    'job_id': str(job.id)
                }
            else:
                # Synchronous validation
                cli_client = DataContractCLIClient()
                result = cli_client.validate(contract)

                # Update contract validation status
                contract.validation_status = result.get('validation_status')
                contract.validation_errors = result.get('errors', [])
                contract.validation_warnings = result.get('warnings', [])
                contract.last_validated_at = timezone.now()
                contract.save()

                return {
                    'async': False,
                    'validation_status': result.get('validation_status'),
                    'valid': result.get('valid', False),
                    'errors': result.get('errors', []),
                    'warnings': result.get('warnings', []),
                    'cli_version': result.get('cli_version')
                }

        return self.execute_with_metrics(
            operation="validate_contract",
            tenant_id=effective_tenant_id,
            func=_validate
        )
