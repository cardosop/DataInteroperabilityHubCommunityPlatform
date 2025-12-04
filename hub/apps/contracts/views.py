"""
Contract Views

REST API views for contract management.
"""
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction, models
from django.db.models import Q, F, Case, When, Value, IntegerField
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse, inline_serializer
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers

from .models import Contract, ContractStatus, NormalizationStatus, ValidationStatus
from .serializers import ContractSerializer, ContractCreateSerializer, ContractUpdateSerializer
from .normalization import (
    normalize_contract,
    validate_hubcontract_schema
)
from .cli_client import (
    DataContractCLIClient,
    interpret_validation_status,
    group_errors_by_category,
    SYNC_TIMEOUT
)
from .migration_manager import ContractMigrationManager
from .migration import MigrationStrategy, get_current_hubcontract_version
from hub.apps.audit.utils import create_audit_event
from hub.apps.jobs.utils import create_job
from hub.apps.jobs.models import JobType


@extend_schema_view(
    list=extend_schema(
        summary="List contracts",
        description="""
        List contracts with enhanced filtering and sorting.
        
        **Filtering:**
        - `owner_email`: Filter by owner email (case-insensitive)
        - `owner_name`: Filter by owner name (case-insensitive partial match)
        - `tag`: Filter by tags (can specify multiple tags)
        - `quality_profile`: Filter by quality profile key
        - `compliance_regime`: Filter by compliance jurisdiction (e.g., GDPR, LGPD)
        
        **Sorting:**
        - `ordering`: Comma-separated list of fields to sort by
        - Supported fields: `created_at`, `updated_at`, `quality_score`, `compliance_risk`
        - Prefix with `-` for descending order (e.g., `-created_at`)
        - Default: `-created_at` (newest first)
        
        **Response includes computed fields:**
        - `owners`: Array of owner objects (name, email) from `info.owners`
        - `tags`: Array of tags from `info.tags`
        - `quality_rules`: Array of quality rules from `quality.rules`
        - `compliance_policy`: Compliance policy from `privacy_compliance`
        - `lifecycle_policy`: Lifecycle policy from `lifecycle`
        - `marketplace_policy`: Marketplace policy from `marketplace`
        - `schema_fields`: Array of schema fields with all properties (format, pattern, enum, semantic_type, etc.)
        """,
        parameters=[
            OpenApiParameter(
                name='owner_email',
                type=OpenApiTypes.EMAIL,
                location=OpenApiParameter.QUERY,
                description='Filter by owner email (case-insensitive)',
                required=False
            ),
            OpenApiParameter(
                name='owner_name',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by owner name (case-insensitive partial match)',
                required=False
            ),
            OpenApiParameter(
                name='tag',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by tag (can specify multiple times)',
                required=False
            ),
            OpenApiParameter(
                name='quality_profile',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by quality profile key (e.g., intake_basic)',
                required=False
            ),
            OpenApiParameter(
                name='compliance_regime',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by compliance jurisdiction (e.g., GDPR, LGPD, CCPA)',
                required=False
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Comma-separated list of fields to sort by (e.g., -created_at,quality_score)',
                required=False
            ),
        ],
        tags=['Contracts']
    ),
    retrieve=extend_schema(
        summary="Retrieve contract",
        description="""
        Retrieve a contract by ID.
        
        **Response includes all HubContract sections:**
        - `hub_contract_json`: Complete normalized HubContract with all sections
        - `owners`: Computed array of owners from `info.owners`
        - `tags`: Computed array of tags from `info.tags`
        - `quality_rules`: Computed array of quality rules from `quality.rules`
        - `compliance_policy`: Computed compliance policy from `privacy_compliance`
        - `lifecycle_policy`: Computed lifecycle policy from `lifecycle`
        - `marketplace_policy`: Computed marketplace policy from `marketplace`
        - `schema_fields`: Computed array of schema fields with all properties
        
        **Normalization Status:**
        - `NORMALIZED_OK`: Contract normalized successfully
        - `NORMALIZED_WITH_WARNINGS`: Normalized with warnings
        - `NORMALIZATION_FAILED`: Normalization failed
        - `NOT_NORMALIZED`: Not yet normalized
        
        **Validation Status:**
        - `VALID`: Contract is valid
        - `INVALID`: Contract has errors
        - `WARNING_ONLY`: Contract has warnings but no errors
        - `ERROR`: Validation error occurred
        """,
        tags=['Contracts']
    ),
    create=extend_schema(
        summary="Create contract",
        description="""
        Create a new contract from original contract content.
        
        The contract will be automatically normalized to HubContract format.
        All sections (owners, tags, quality, compliance, lifecycle, marketplace) will be extracted
        from the original contract and stored in `hub_contract_json`.
        
        **Supported Formats:**
        - JSON (original_format: "JSON")
        - YAML (original_format: "YAML")
        
        **Supported Spec Types:**
        - ODCS (original_spec_type: "ODCS")
        - DataContract.com (original_spec_type: "DATACONTRACT_COM")
        
        If `original_spec_type` is not provided, it will be auto-detected.
        """,
        request=ContractCreateSerializer,
        responses={
            201: ContractSerializer,
            400: OpenApiResponse(description="Validation error or normalization failed"),
        },
        tags=['Contracts']
    ),
    update=extend_schema(
        summary="Update contract",
        description="""
        Update a contract (partial update supported).
        
        If `original_raw` is updated, the contract will be re-normalized.
        All sections will be re-extracted and stored in `hub_contract_json`.
        """,
        request=ContractUpdateSerializer,
        responses={
            200: ContractSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
        tags=['Contracts']
    ),
    destroy=extend_schema(
        summary="Delete contract",
        description="""
        Delete a contract (soft delete: sets status to RETIRED).
        """,
        responses={
            204: OpenApiResponse(description="Contract deleted successfully"),
        },
        tags=['Contracts']
    ),
)
class ContractViewSet(viewsets.ModelViewSet):
    """
    ViewSet for contract management.
    
    Tenant-scoped: users can only see/manage contracts in their tenant.
    """
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    
    @transaction.atomic
    def create(self, request):
        """
        Create a new contract.
        
        POST /contracts
        Body: {
            "asset_id": "uuid" (optional),
            "original_raw": "contract content",
            "original_format": "JSON" or "YAML",
            "original_spec_type": "ODCS" or "DATACONTRACT_COM" (optional)
        }
        """
        serializer = ContractCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        original_raw = serializer.validated_data['original_raw']
        original_format = serializer.validated_data['original_format']
        original_spec_type = serializer.validated_data.get('original_spec_type')
        asset_id = serializer.validated_data.get('asset_id')
        
        # Get tenant from user
        tenant = request.user.tenant if hasattr(request.user, 'tenant') and request.user.tenant else None
        if not tenant:
            return Response(
                {'error': 'User must belong to a tenant to create contracts'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get asset if provided
        asset = None
        if asset_id:
            try:
                from hub.apps.assets.models import Asset
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Exception:
                return Response(
                    {'error': 'Asset not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Get next version for asset (if asset provided)
        version = 1
        if asset:
            latest_contract = Contract.objects.filter(
                tenant=tenant,
                asset=asset
            ).order_by('-version').first()
            if latest_contract:
                version = latest_contract.version + 1
        
        # Normalize contract
        hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = normalize_contract(
            raw_contract=original_raw,
            format=original_format,
            spec_type=original_spec_type
        )
        
        # Use provided spec_type or detected
        final_spec_type = original_spec_type or detected_spec_type
        final_spec_version = detected_spec_version
        
        # Validate HubContract schema if normalization succeeded
        if hub_contract:
            is_valid, validation_errors = validate_hubcontract_schema(hub_contract)
            if not is_valid:
                norm_status = NormalizationStatus.NORMALIZATION_FAILED
                norm_errors.extend(validation_errors)
                hub_contract = None
        
        # Create contract
        contract = Contract.objects.create(
            tenant=tenant,
            asset=asset,
            version=version,
            status=ContractStatus.DRAFT,
            original_spec_type=final_spec_type,
            original_spec_version=final_spec_version,
            original_format=original_format,
            original_raw=original_raw,
            hub_contract_version="1.0.0" if hub_contract else None,
            hub_contract_json=hub_contract,
            normalization_status=norm_status,
            normalization_errors=norm_errors,
            normalization_warnings=norm_warnings,
            created_by=request.user
        )
        
        # Log audit event
        create_audit_event(
            resource_type="CONTRACT",
            action="CONTRACT_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(contract.id),
            details={
                'original_spec_type': final_spec_type,
                'original_spec_version': final_spec_version,
                'normalization_status': norm_status,
                'asset_id': str(asset_id) if asset_id else None
            },
            request=request
        )
        
        return Response(
            ContractSerializer(contract).data,
            status=status.HTTP_201_CREATED
        )
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update a contract.
        
        PATCH /contracts/{id}
        Body: {
            "original_raw": "updated contract content" (optional),
            "original_format": "JSON" or "YAML" (optional),
            "status": "DRAFT" | "ACTIVE" | "RETIRED" (optional)
        }
        """
        contract = self.get_object()
        serializer = ContractUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Store old values for audit
        old_status = contract.status
        old_hub_contract_json = contract.hub_contract_json
        
        # Update original_raw if provided
        if 'original_raw' in serializer.validated_data:
            contract.original_raw = serializer.validated_data['original_raw']
            
            # Update format if provided
            if 'original_format' in serializer.validated_data:
                contract.original_format = serializer.validated_data['original_format']
            
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
            
            # Reset validation status (requires re-validation)
            contract.validation_status = None
            contract.validation_errors = []
            contract.validation_warnings = []
            contract.last_validated_at = None
        
        # Update status if provided
        if 'status' in serializer.validated_data:
            new_status = serializer.validated_data['status']
            
            # Enforce ACTIVE status requirements
            if new_status == ContractStatus.ACTIVE:
                can_activate, reason = contract.can_activate()
                if not can_activate:
                    return Response(
                        {'error': f'Cannot activate contract: {reason}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            contract.status = new_status
        
        # Apply ON_WRITE migration if needed
        if contract.hub_contract_json and contract.hub_contract_version:
            migrated, migrated_hub_contract, migration_warnings = ContractMigrationManager.migrate_on_write(contract)
            if migrated:
                # Contract was migrated, refresh from DB
                contract.refresh_from_db()
        
        # Validate contract before saving
        try:
            contract.full_clean()
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        contract.save()
        
        # Log audit event
        create_audit_event(
            resource_type="CONTRACT",
            action="CONTRACT_UPDATED",
            actor_user=request.user,
            tenant=contract.tenant,
            resource_id=str(contract.id),
            details={
                'old_status': old_status,
                'new_status': contract.status,
                'normalization_status': contract.normalization_status,
                'old_hub_contract_json': old_hub_contract_json,
                'new_hub_contract_json': contract.hub_contract_json
            },
            request=request
        )
        
        return Response(
            ContractSerializer(contract).data,
            status=status.HTTP_200_OK
        )
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a contract (soft delete: set status to RETIRED).
        
        DELETE /contracts/{id}
        """
        contract = self.get_object()
        
        # Soft delete: set status to RETIRED
        contract.status = ContractStatus.RETIRED
        contract.save()
        
        # Log audit event
        create_audit_event(
            resource_type="CONTRACT",
            action="CONTRACT_DELETED",
            actor_user=request.user,
            tenant=contract.tenant,
            resource_id=str(contract.id),
            details={
                'original_spec_type': contract.original_spec_type,
                'original_spec_version': contract.original_spec_version
            },
            request=request
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def get_queryset(self):
        """Filter queryset based on user permissions and query parameters (GAP-9.2.2)"""
        user = self.request.user
        
        # Platform admins can see all contracts
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = Contract.objects.all()
        else:
            # Get tenant from request (set by middleware/authentication) or user
            # Priority: request.tenant_id > request.tenant > user.tenant_id > user.tenant
            # CRITICAL: Always refresh user from DB to ensure tenant_id is available (works in all environments)
            # This matches how TenantScopingMiddleware handles it for consistency
            tenant_id = None
            if hasattr(self.request, "tenant_id") and self.request.tenant_id:
                tenant_id = self.request.tenant_id
                if isinstance(tenant_id, str):
                    import uuid
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        tenant_id = None
            if not tenant_id and hasattr(self.request, "tenant") and self.request.tenant:
                tenant_id = self.request.tenant.id
            # Always query user from DB to get fresh tenant_id (most reliable, works in all environments)
            # This ensures we have the latest tenant_id from the database, not from a cached object
            if not tenant_id and hasattr(user, "id") and user.id:
                from django.contrib.auth import get_user_model
                from django.contrib.auth.models import AnonymousUser
                User = get_user_model()
                if not isinstance(user, AnonymousUser):
                    try:
                        db_user = User.objects.only('tenant_id').get(id=user.id)
                        if db_user.tenant_id:
                            tenant_id = db_user.tenant_id
                    except User.DoesNotExist:
                        pass
            # Fallback: try user.tenant_id directly (works if user object is properly loaded)
            if not tenant_id and hasattr(user, "tenant_id") and user.tenant_id:
                tenant_id = user.tenant_id
            # Last resort: get from user.tenant relationship
            if not tenant_id and hasattr(user, "tenant") and user.tenant:
                tenant_id = user.tenant.id
            
            # DEBUG: Log tenant_id retrieval for troubleshooting (only in test environments)
            import os
            if os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('test') or 'test' in os.environ.get('PYTEST_CURRENT_TEST', ''):
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(
                    f"ContractViewSet.get_queryset: tenant_id={tenant_id}, "
                    f"user.tenant_id={getattr(user, 'tenant_id', None)}, "
                    f"user.tenant={getattr(user, 'tenant', None)}, "
                    f"request.tenant_id={getattr(self.request, 'tenant_id', None)}, "
                    f"request.tenant={getattr(self.request, 'tenant', None)}"
                )
            
            # Regular users can only see contracts in their tenant
            if tenant_id:
                if isinstance(tenant_id, str):
                    import uuid
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        queryset = Contract.objects.none()
                    else:
                        queryset = Contract.objects.filter(tenant_id=tenant_id)
                else:
                    queryset = Contract.objects.filter(tenant_id=tenant_id)
                
                # DEBUG: Verify queryset has contracts (only in test environments)
                import os
                if 'test' in os.environ.get('PYTEST_CURRENT_TEST', '') or 'pytest' in str(os.environ.get('_', '')):
                    count_before_filtering = queryset.count()
                    if count_before_filtering == 0:
                        # Log for debugging
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"ContractViewSet.get_queryset: tenant_id={tenant_id}, "
                            f"but queryset is empty. Total contracts for tenant: {Contract.objects.filter(tenant_id=tenant_id).count()}"
                        )
            else:
                queryset = Contract.objects.none()
        
        # Apply enhanced filtering (GAP-9.2.2)
        # NOTE: Filtering must happen BEFORE sorting annotations are applied
        # because filtering may need to evaluate the queryset, and annotations can interfere
        queryset = self._apply_filtering(queryset)
        
        # Apply enhanced sorting (GAP-9.2.2)
        # Sorting annotations are applied after filtering to avoid interfering with queryset evaluation
        queryset = self._apply_sorting(queryset)
        
        return queryset
    
    def _apply_filtering(self, queryset):
        """Apply filtering by owners, tags, quality profile, compliance regime (GAP-9.2.2)"""
        request = self.request
        # Handle both DRF Request objects (with query_params) and Django WSGIRequest (with GET)
        if hasattr(request, 'query_params'):
            query_params = request.query_params
        else:
            # Fallback for Django WSGIRequest (e.g., in tests with APIRequestFactory)
            query_params = request.GET
        
        # Filter by owners (email or name)
        owner_email = query_params.get('owner_email')
        owner_name = query_params.get('owner_name')
        if owner_email or owner_name:
            # Filter contracts where hub_contract_json.info.owners contains matching owner
            # Use a Python-based filter for JSON arrays (more reliable than JSONField lookups)
            contract_ids = []
            
            # Evaluate queryset to check JSON fields (needed for complex JSON filtering)
            # This is acceptable for owner filtering as it's typically a small dataset per tenant
            # We need to load hub_contract_json to check the owners array
            try:
                # Convert queryset to list to evaluate it once
                # This ensures we're working with the actual filtered queryset
                # Note: For large datasets, this could be optimized with iterator(), but for
                # tenant-scoped queries, the dataset is typically small
                # IMPORTANT: Evaluate queryset BEFORE any annotations from sorting are applied
                # The sorting annotations might interfere with queryset evaluation
                # So we evaluate the base queryset first, then filter, then apply sorting
                contracts_list = list(queryset)
                
                # If queryset is empty, there's nothing to filter - return early
                if not contracts_list:
                    return queryset.none()
                
                for contract in contracts_list:
                    if not contract.hub_contract_json:
                        continue
                    info = contract.hub_contract_json.get('info', {})
                    if not info:
                        continue
                    owners = info.get('owners', [])
                    if not owners:
                        continue
                    
                    email_match = True
                    name_match = True
                    
                    if owner_email:
                        # Check if any owner has this email (case-insensitive)
                        email_match = False
                        for owner in owners:
                            if isinstance(owner, dict):
                                owner_email_val = owner.get('email', '')
                                if owner_email_val and owner_email_val.lower() == owner_email.lower():
                                    email_match = True
                                    break
                    
                    if owner_name:
                        # Check if any owner has this name (case-insensitive contains)
                        name_match = False
                        for owner in owners:
                            if isinstance(owner, dict):
                                owner_name_val = owner.get('name', '')
                                if owner_name_val and owner_name.lower() in owner_name_val.lower():
                                    name_match = True
                                    break
                    
                    # Both conditions must be met if both are specified, otherwise either one
                    if owner_email and owner_name:
                        if email_match and name_match:
                            contract_ids.append(contract.id)
                    elif owner_email:
                        if email_match:
                            contract_ids.append(contract.id)
                    elif owner_name:
                        if name_match:
                            contract_ids.append(contract.id)
            except Exception as e:
                # Log the error for debugging but don't fail silently
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error filtering contracts by owner: {e}", exc_info=True)
                # If queryset evaluation fails, return empty queryset
                return queryset.none()
            
            if contract_ids:
                # Filter the queryset by the matching contract IDs
                # Since the contracts_list came from a tenant-filtered queryset, all IDs are already tenant-scoped
                # We can safely filter by ID without losing tenant security
                queryset = queryset.filter(id__in=contract_ids)
            else:
                # No contracts matched the owner filter
                queryset = queryset.none()
        
        # Filter by tags
        tags = query_params.getlist('tag')  # Support multiple tags
        if tags:
            # Filter contracts where hub_contract_json.info.tags contains any of the specified tags
            # Use contains lookup for array elements (works better for simple arrays)
            tag_filter = Q()
            for tag in tags:
                tag_filter |= Q(hub_contract_json__info__tags__contains=[tag])
            queryset = queryset.filter(tag_filter)
        
        # Filter by quality profile
        quality_profile = query_params.get('quality_profile')
        if quality_profile:
            queryset = queryset.filter(
                hub_contract_json__quality__default_profile_key=quality_profile
            )
        
        # Filter by compliance regime (jurisdiction)
        compliance_regime = query_params.get('compliance_regime')
        if compliance_regime:
            # Filter contracts where hub_contract_json.privacy_compliance.jurisdictions contains the regime
            queryset = queryset.filter(
                hub_contract_json__privacy_compliance__jurisdictions__contains=[compliance_regime]
            )
        
        return queryset
    
    def _apply_sorting(self, queryset):
        """Apply sorting by quality score, compliance risk level, creation date, update date (GAP-9.2.2)"""
        request = self.request
        # Handle both DRF Request objects (with query_params) and Django WSGIRequest (with GET)
        if hasattr(request, 'query_params'):
            query_params = request.query_params
        else:
            # Fallback for Django WSGIRequest (e.g., in tests with APIRequestFactory)
            query_params = request.GET
        ordering = query_params.get('ordering', '-created_at')  # Default to newest first
        
        # Parse ordering parameter (can be comma-separated)
        order_fields = [field.strip() for field in ordering.split(',')]
        
        # Map sort fields to database fields or annotations
        sort_mapping = {
            'created_at': 'created_at',
            '-created_at': '-created_at',
            'updated_at': 'updated_at',
            '-updated_at': '-updated_at',
            'quality_score': 'quality_score',
            '-quality_score': '-quality_score',
            'compliance_risk': 'compliance_risk',
            '-compliance_risk': '-compliance_risk',
        }
        
        # Build ordering list
        ordering_list = []
        for field in order_fields:
            if field in sort_mapping:
                ordering_list.append(sort_mapping[field])
            elif field.startswith('-') and field[1:] in sort_mapping:
                ordering_list.append(sort_mapping[field])
            else:
                # Default fallback
                ordering_list.append(field)
        
        # Annotate queryset with computed fields for sorting (GAP-9.2.2)
        # Quality score: extract from hub_contract_json if available
        # For now, we'll use a simple annotation based on normalization status
        # In a real implementation, this would extract from quality metrics
        queryset = queryset.annotate(
            quality_score=Case(
                When(normalization_status=NormalizationStatus.NORMALIZED_OK, then=Value(100)),
                When(normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS, then=Value(75)),
                When(normalization_status=NormalizationStatus.NORMALIZATION_FAILED, then=Value(0)),
                default=Value(50),
                output_field=IntegerField()
            )
        )
        
        # Compliance risk: extract from hub_contract_json.privacy_compliance if available
        # For now, use a simple annotation based on whether personal data is present
        queryset = queryset.annotate(
            compliance_risk=Case(
                When(hub_contract_json__privacy_compliance__contains_personal_data=True, then=Value(100)),
                default=Value(0),
                output_field=IntegerField()
            )
        )
        
        # Apply ordering
        if ordering_list:
            queryset = queryset.order_by(*ordering_list)
        else:
            queryset = queryset.order_by('-created_at')  # Default ordering
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """List contracts (tenant-scoped) with enhanced filtering and sorting (GAP-9.2.2)"""
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve contract by ID.
        
        Applies ON_READ migration (lazy migration) if needed (GAP-10.2.2).
        Supports both v1 and v2 contracts (backward compatible).
        """
        contract = self.get_object()
        
        # Apply ON_READ migration (lazy, in-memory) for backward compatibility (GAP-10.2.2)
        if contract.hub_contract_json and contract.hub_contract_version:
            migrated_hub_contract, migration_warnings = ContractMigrationManager.migrate_on_read(contract)
            
            # If migration was applied, return migrated version in response
            # (but don't update DB - that's the lazy part)
            if migrated_hub_contract != contract.hub_contract_json:
                # Create a temporary serializer with migrated contract
                serializer = self.get_serializer(contract)
                response_data = serializer.data
                # Override hub_contract_json with migrated version
                response_data['hub_contract_json'] = migrated_hub_contract
                if migration_warnings:
                    response_data['migration_warnings'] = migration_warnings
                return Response(response_data)
        
        # Support both v1 and v2 contracts (GAP-10.2.2)
        # API handles both versions transparently
        return super().retrieve(request, *args, **kwargs)
    
    @transaction.atomic
    @extend_schema(
        summary="Validate contract",
        description="""
        Validate a contract using DataContract CLI.
        
        **Validation Modes:**
        - **Synchronous** (default): Returns validation result immediately
        - **Asynchronous**: Creates a job and returns job ID (for large contracts)
        
        **Validation Status:**
        - `VALID`: Contract is valid
        - `INVALID`: Contract has errors
        - `WARNING_ONLY`: Contract has warnings but no errors
        - `ERROR`: Validation error occurred
        
        **Response includes:**
        - `validation_status`: Overall validation status
        - `errors`: Array of validation errors
        - `warnings`: Array of validation warnings
        - `grouped_errors`: Errors grouped by category
        - `cli_version`: DataContract CLI version used
        - `validated_at`: Timestamp of validation
        """,
        request=inline_serializer(
            name='ContractValidationRequest',
            fields={
                'async': serializers.BooleanField(required=False, default=False, help_text='Use async validation (default: false)')
            }
        ),
        responses={
            200: inline_serializer(
                name='ContractValidationResponse',
                fields={
                    'validation_status': serializers.CharField(),
                    'errors': serializers.ListField(child=serializers.DictField()),
                    'warnings': serializers.ListField(child=serializers.DictField()),
                    'grouped_errors': serializers.DictField(),
                    'cli_version': serializers.CharField(),
                    'validated_at': serializers.DateTimeField()
                }
            ),
            202: inline_serializer(
                name='ContractValidationJobResponse',
                fields={
                    'job_id': serializers.UUIDField(),
                    'status': serializers.CharField(),
                    'message': serializers.CharField()
                }
            ),
            500: OpenApiResponse(description="Validation failed")
        },
        tags=['Contracts']
    )
    @action(detail=True, methods=['post'], url_path='validate')
    def validate_contract(self, request, id=None):
        """
        Validate a contract using DataContract CLI.
        
        POST /contracts/{id}/validate
        Body: {
            "async": false (optional, default false for sync validation)
        }
        
        Returns validation result with status, errors, warnings.
        """
        contract = self.get_object()
        
        use_async = request.data.get('async', False)
        contract_size = len(contract.original_raw.encode('utf-8'))
        
        # Determine if async is needed based on size
        from django.conf import settings
        sync_size_limit = getattr(settings, 'DATACONTRACT_VALIDATION_SYNC_SIZE_LIMIT', 100 * 1024)
        
        if contract_size > sync_size_limit:
            use_async = True
        
        if use_async:
            # Create async validation job
            job = create_job(
                job_type=JobType.CONTRACT_VALIDATION,
                resource_type="CONTRACT",
                resource_id=str(contract.id),
                tenant=contract.tenant,
                created_by=request.user,
                details_json={
                    'contract_id': str(contract.id),
                    'validation_type': 'async'
                },
                queue_name='default'
            )
            
            # Log audit event
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_VALIDATION_STARTED",
                actor_user=request.user,
                tenant=contract.tenant,
                resource_id=str(contract.id),
                details={
                    'job_id': str(job.id),
                    'validation_type': 'async'
                },
                request=request
            )
            
            return Response(
                {
                    'job_id': str(job.id),
                    'status': 'pending',
                    'message': 'Validation job created. Poll /jobs/{job_id} for status.'
                },
                status=status.HTTP_202_ACCEPTED
            )
        else:
            # Synchronous validation
            try:
                cli_client = DataContractCLIClient()
                
                # Validate contract
                validation_result = cli_client.validate(
                    raw_contract=contract.original_raw,
                    format=contract.original_format,
                    tenant_id=str(contract.tenant.id) if contract.tenant else None,
                    use_cache=True,
                    timeout=SYNC_TIMEOUT
                )
                
                # Interpret validation status
                validation_status, errors, warnings = interpret_validation_status(validation_result)
                
                # Group errors by category
                grouped_errors = group_errors_by_category(errors)
                
                # Update contract with validation results
                contract.validation_status = validation_status
                contract.validation_errors = errors
                contract.validation_warnings = warnings
                contract.cli_version = validation_result.get('cli_version', 'unknown')
                contract.last_validated_at = timezone.now()
                contract.save(update_fields=[
                    'validation_status',
                    'validation_errors',
                    'validation_warnings',
                    'cli_version',
                    'last_validated_at',
                    'updated_at'
                ])
                
                # Log audit event
                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_VALIDATION_COMPLETED",
                    actor_user=request.user,
                    tenant=contract.tenant,
                    resource_id=str(contract.id),
                    details={
                        'validation_status': validation_status,
                        'error_count': len(errors),
                        'warning_count': len(warnings),
                        'cli_version': contract.cli_version
                    },
                    request=request
                )
                
                return Response(
                    {
                        'validation_status': validation_status,
                        'errors': errors,
                        'warnings': warnings,
                        'grouped_errors': grouped_errors,
                        'cli_version': contract.cli_version,
                        'validated_at': contract.last_validated_at.isoformat()
                    },
                    status=status.HTTP_200_OK
                )
            
            except Exception as e:
                # Mark validation as ERROR
                contract.validation_status = ValidationStatus.ERROR
                contract.validation_errors = [{'message': str(e), 'severity': 'ERROR'}]
                contract.last_validated_at = timezone.now()
                contract.save(update_fields=[
                    'validation_status',
                    'validation_errors',
                    'last_validated_at',
                    'updated_at'
                ])
                
                # Log audit event
                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_VALIDATION_FAILED",
                    actor_user=request.user,
                    tenant=contract.tenant,
                    resource_id=str(contract.id),
                    details={'error': str(e)},
                    request=request
                )
                
                return Response(
                    {'error': f'Validation failed: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
    
    @extend_schema(
        summary="Lint contract",
        description="""
        Lint a contract using DataContract CLI.
        
        Returns linting issues and recommendations for improving the contract.
        """,
        responses={
            200: inline_serializer(
                name='ContractLintResponse',
                fields={
                    'issues': serializers.ListField(child=serializers.DictField()),
                    'cli_version': serializers.CharField()
                }
            ),
            500: OpenApiResponse(description="Linting failed")
        },
        tags=['Contracts']
    )
    @action(detail=True, methods=['post'], url_path='lint')
    def lint_contract(self, request, id=None):
        """
        Lint a contract using DataContract CLI.
        
        POST /contracts/{id}/lint
        
        Returns linting result with issues.
        """
        contract = self.get_object()
        
        try:
            cli_client = DataContractCLIClient()
            
            # Lint contract
            lint_result = cli_client.lint(
                raw_contract=contract.original_raw,
                format=contract.original_format,
                timeout=SYNC_TIMEOUT
            )
            
            # Log audit event
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_LINTED",
                actor_user=request.user,
                tenant=contract.tenant,
                resource_id=str(contract.id),
                details={'issues_count': len(lint_result.get('issues', []))},
                request=request
            )
            
            return Response(
                {
                    'issues': lint_result.get('issues', []),
                    'cli_version': lint_result.get('cli_version', 'unknown')
                },
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            return Response(
                {'error': f'Linting failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Convert contract format",
        description="""
        Convert a contract between JSON and YAML formats.
        
        **Supported Formats:**
        - `JSON`: Convert to JSON format
        - `YAML`: Convert to YAML format
        """,
        request=inline_serializer(
            name='ContractConvertRequest',
            fields={
                'target_format': serializers.ChoiceField(
                    choices=['JSON', 'YAML'],
                    required=True,
                    help_text='Target format for conversion'
                )
            }
        ),
        responses={
            200: inline_serializer(
                name='ContractConvertResponse',
                fields={
                    'converted_contract': serializers.CharField(),
                    'target_format': serializers.CharField(),
                    'format': serializers.CharField(),
                    'cli_version': serializers.CharField()
                }
            ),
            400: OpenApiResponse(description="Invalid target format"),
            500: OpenApiResponse(description="Conversion failed")
        },
        tags=['Contracts']
    )
    @action(detail=True, methods=['post'], url_path='convert')
    def convert_contract(self, request, id=None):
        """
        Convert a contract between formats.
        
        POST /contracts/{id}/convert
        Body: {
            "target_format": "JSON" or "YAML"
        }
        
        Returns converted contract.
        """
        contract = self.get_object()
        target_format = request.data.get('target_format', 'JSON')
        
        if target_format not in ['JSON', 'YAML']:
            return Response(
                {'error': 'target_format must be JSON or YAML'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cli_client = DataContractCLIClient()
            
            # Convert contract
            convert_result = cli_client.convert(
                raw_contract=contract.original_raw,
                source_format=contract.original_format,
                target_format=target_format,
                timeout=SYNC_TIMEOUT
            )
            
            # Log audit event
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_CONVERTED",
                actor_user=request.user,
                tenant=contract.tenant,
                resource_id=str(contract.id),
                details={
                    'source_format': contract.original_format,
                    'target_format': target_format
                },
                request=request
            )
            
            return Response(
                {
                    'converted_contract': convert_result.get('converted_contract', ''),
                    'target_format': convert_result.get('target_format', target_format),
                    'format': target_format,  # Keep for backward compatibility
                    'cli_version': convert_result.get('cli_version', 'unknown')
                },
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            return Response(
                {'error': f'Conversion failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @transaction.atomic
    @extend_schema(
        summary="Migrate contract",
        description="""
        Migrate contract to a new HubContract version.
        
        **Migration Strategies:**
        - `ON_WRITE`: Migrate immediately and persist to database
        - `ON_READ`: Migrate in-memory only (lazy migration, not persisted)
        - `BACKGROUND`: Queue background job for migration
        
        **Response:**
        - For `ON_WRITE` and `ON_READ`: Returns migrated contract
        - For `BACKGROUND`: Returns job ID to poll for status
        """,
        request=inline_serializer(
            name='ContractMigrationRequest',
            fields={
                'target_hub_contract_version': serializers.CharField(
                    required=False,
                    help_text='Target HubContract version (defaults to current)'
                ),
                'migration_strategy': serializers.ChoiceField(
                    choices=['ON_WRITE', 'ON_READ', 'BACKGROUND'],
                    required=False,
                    default='ON_WRITE',
                    help_text='Migration strategy (default: ON_WRITE)'
                )
            }
        ),
        responses={
            200: inline_serializer(
                name='ContractMigrationResponse',
                fields={
                    'contract': ContractSerializer,
                    'migration_applied': serializers.BooleanField(),
                    'migration_details': serializers.DictField()
                }
            ),
            202: inline_serializer(
                name='ContractMigrationJobResponse',
                fields={
                    'job': serializers.DictField(),
                    'migration_details': serializers.DictField()
                }
            ),
            400: OpenApiResponse(description="Invalid migration strategy or contract not normalized")
        },
        tags=['Contracts']
    )
    @action(detail=True, methods=['post'], url_path='migrate')
    def migrate_contract(self, request, id=None):
        """
        Migrate contract to a new HubContract version.
        
        POST /contracts/{id}/migrate
        Body: {
            "target_hub_contract_version": "2.0.0" (optional, defaults to current),
            "migration_strategy": "ON_WRITE" | "ON_READ" | "BACKGROUND" (optional, default: "ON_WRITE")
        }
        
        Returns migration result or job ID for BACKGROUND strategy.
        """
        contract = self.get_object()
        
        target_version = request.data.get('target_hub_contract_version')
        if not target_version:
            target_version = get_current_hubcontract_version()
        
        strategy = request.data.get('migration_strategy', MigrationStrategy.ON_WRITE)
        
        if strategy not in [MigrationStrategy.ON_WRITE, MigrationStrategy.ON_READ, MigrationStrategy.BACKGROUND]:
            return Response(
                {'error': f'Invalid migration_strategy: {strategy}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if migration is needed
        if not contract.hub_contract_json or not contract.hub_contract_version:
            return Response(
                {'error': 'Contract is not normalized. Cannot migrate.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if contract.hub_contract_version == target_version:
            return Response(
                {
                    'contract': ContractSerializer(contract).data,
                    'migration_applied': False,
                    'migration_details': {
                        'source_version': contract.hub_contract_version,
                        'target_version': target_version,
                        'message': 'Contract is already at target version'
                    }
                },
                status=status.HTTP_200_OK
            )
        
        # Execute migration based on strategy
        if strategy == MigrationStrategy.ON_WRITE:
            migrated, migrated_hub_contract, warnings = ContractMigrationManager.migrate_on_write(contract)
            
            if not migrated:
                # Migration not needed (already at target version) or failed
                # Check if it's because migration isn't needed
                from .migration import needs_migration
                if not needs_migration(contract.hub_contract_version):
                    # Already at target version - return success
                    return Response(
                        {
                            'contract': ContractSerializer(contract).data,
                            'migration_applied': False,
                            'migration_details': {
                                'source_version': contract.hub_contract_version,
                                'target_version': target_version,
                                'message': 'Contract is already at target version'
                            }
                        },
                        status=status.HTTP_200_OK
                    )
                else:
                    # Migration failed
                    return Response(
                        {'error': 'Migration failed or not supported'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Refresh contract from DB
            contract.refresh_from_db()
            
            return Response(
                {
                    'contract': ContractSerializer(contract).data,
                    'migration_applied': True,
                    'migration_details': {
                        'source_version': contract.hub_contract_version,
                        'target_version': target_version,
                        'migration_strategy': strategy,
                        'warnings': warnings
                    }
                },
                status=status.HTTP_200_OK
            )
        
        elif strategy == MigrationStrategy.ON_READ:
            migrated_hub_contract, warnings = ContractMigrationManager.migrate_on_read(contract)
            
            # Return migrated version (in-memory, not persisted)
            serializer = ContractSerializer(contract)
            response_data = serializer.data
            response_data['hub_contract_json'] = migrated_hub_contract
            
            return Response(
                {
                    'contract': response_data,
                    'migration_applied': True,
                    'migration_details': {
                        'source_version': contract.hub_contract_version,
                        'target_version': target_version,
                        'migration_strategy': strategy,
                        'warnings': warnings,
                        'note': 'Migration applied in-memory only (lazy migration)'
                    }
                },
                status=status.HTTP_200_OK
            )
        
        elif strategy == MigrationStrategy.BACKGROUND:
            job = ContractMigrationManager.migrate_background(contract, user=request.user)
            
            if not job:
                # Check if migration isn't needed (already at target version)
                from .migration import needs_migration
                if not needs_migration(contract.hub_contract_version):
                    # Already at target version - return success
                    return Response(
                        {
                            'contract': ContractSerializer(contract).data,
                            'migration_applied': False,
                            'migration_details': {
                                'source_version': contract.hub_contract_version,
                                'target_version': target_version,
                                'message': 'Contract is already at target version'
                            }
                        },
                        status=status.HTTP_200_OK
                    )
                else:
                    # Migration failed
                    return Response(
                        {'error': 'Migration failed or not needed'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            return Response(
                {
                    'job': {
                        'id': str(job.id),
                        'type': job.type,
                        'status': job.status,
                        'resource_type': job.resource_type,
                        'resource_id': str(job.resource_id)
                    },
                    'migration_details': {
                        'source_version': contract.hub_contract_version,
                        'target_version': target_version,
                        'migration_strategy': strategy
                    }
                },
                status=status.HTTP_202_ACCEPTED
            )
