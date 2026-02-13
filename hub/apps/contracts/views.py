"""
Contract Views

REST API views for contract management.

This module imports ContractViewSet which uses mixins for different responsibilities.
"""

from django.db.models import Case, IntegerField, Q, Value, When
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import permissions

from .models import Contract, NormalizationStatus, OriginalSpecType
from .pagination import ContractPageNumberPagination
from .serializers import (
    ContractCreateSerializer,
    ContractSerializer,
    ContractUpdateSerializer,
)
from .views_base import ContractViewSetBase
from .views_crud import ContractCRUDMixin
from .views_export import ContractExportMixin
from .views_format_handling import ContractFormatHandlingMixin
from .views_impact import ContractImpactMixin
from .views_lineage import ContractLineageMixin
from .views_migration import ContractMigrationMixin
from .views_odps import ContractODPSMixin
from .views_product import ContractProductMixin
from .views_validation import ContractValidationMixin


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
                name="owner_email",
                type=OpenApiTypes.EMAIL,
                location=OpenApiParameter.QUERY,
                description="Filter by owner email (case-insensitive)",
                required=False,
            ),
            OpenApiParameter(
                name="owner_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by owner name (case-insensitive partial match)",
                required=False,
            ),
            OpenApiParameter(
                name="tag",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by tag (can specify multiple times)",
                required=False,
            ),
            OpenApiParameter(
                name="quality_profile",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by quality profile key (e.g., intake_basic)",
                required=False,
            ),
            OpenApiParameter(
                name="compliance_regime",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by compliance jurisdiction (e.g., GDPR, LGPD, CCPA)",
                required=False,
            ),
            OpenApiParameter(
                name="contact_email",
                type=OpenApiTypes.EMAIL,
                location=OpenApiParameter.QUERY,
                description="Filter by contact email (case-insensitive)",
                required=False,
            ),
            OpenApiParameter(
                name="contact_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by contact name (case-insensitive partial match)",
                required=False,
            ),
            OpenApiParameter(
                name="server_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by server type (e.g., S3, PostgreSQL, API)",
                required=False,
            ),
            OpenApiParameter(
                name="server_url",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by server URL (case-insensitive partial match)",
                required=False,
            ),
            OpenApiParameter(
                name="min_availability",
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                description="Filter by minimum availability (from servicelevels)",
                required=False,
            ),
            OpenApiParameter(
                name="max_latency_ms",
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                description="Filter by maximum latency in milliseconds (from servicelevels)",
                required=False,
            ),
            OpenApiParameter(
                name="model_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by model name",
                required=False,
            ),
            OpenApiParameter(
                name="spec_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by original spec type (e.g., 'ODPS', 'ODCS')",
                required=False,
            ),
            OpenApiParameter(
                name="odps_version",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by ODPS version (e.g., '4.1', '4.0'). Only applies to ODPS contracts",
                required=False,
            ),
            OpenApiParameter(
                name="has_odps_link",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Filter by whether contract has an ODPS link (true/false). Only applies to ODCS contracts",
                required=False,
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Comma-separated list of fields to sort by (e.g., -created_at,quality_score)",
                required=False,
            ),
        ],
        tags=["Contracts"],
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
        tags=["Contracts"],
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
        - ODCS (original_spec_type: "ODCS") - Open Data Contract Standard v3.0.2+

        If `original_spec_type` is not provided, it will be auto-detected.
        Supported spec types: ODCS (Open Data Contract Standard) and ODPS (Open Data Product Standard).
        """,
        request=ContractCreateSerializer,
        responses={
            201: ContractSerializer,
            400: OpenApiResponse(description="Validation error or normalization failed"),
        },
        tags=["Contracts"],
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
        tags=["Contracts"],
    ),
    destroy=extend_schema(
        summary="Delete contract",
        description="""
        Delete a contract (soft delete: sets status to RETIRED).
        """,
        responses={
            204: OpenApiResponse(description="Contract deleted successfully"),
        },
        tags=["Contracts"],
    ),
)
class ContractViewSet(
    ContractCRUDMixin,
    ContractViewSetBase,
    ContractFormatHandlingMixin,
    ContractLineageMixin,
    ContractValidationMixin,
    ContractODPSMixin,
    ContractMigrationMixin,
    ContractImpactMixin,
    ContractExportMixin,
    ContractProductMixin,
):
    """
    Contract ViewSet with caching and pagination support.

    Features:
    - Caching for contract retrieval and lineage queries
    - Pagination for large result sets
    - Performance optimizations for large JSON
    - Enhanced filtering and sorting
    - All CRUD operations via ContractCRUDMixin
    - Lineage operations via ContractLineageMixin
    - Validation operations via ContractValidationMixin
    - ODPS operations via ContractODPSMixin
    - Migration operations via ContractMigrationMixin
    - Impact analysis via ContractImpactMixin
    - Export operations via ContractExportMixin
    - Product operations via ContractProductMixin

    Note: Overrides initialize_request to handle format suffix conflicts
    for the lineage visualization endpoint.
    """

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
                # CRITICAL: Convert string tenant_id to UUID for filtering
                # Middleware sets tenant_id as string, but Contract.tenant_id is UUIDField
                if isinstance(tenant_id, str):
                    import uuid

                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        # Invalid UUID string - log and set to None
                        import logging
                        import os

                        if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("test"):
                            logger = logging.getLogger(__name__)
                            logger.warning(
                                f"ContractViewSet.get_queryset: Failed to convert tenant_id string '{tenant_id}' to UUID"
                            )
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
                        db_user = User.objects.only("tenant_id").get(id=user.id)
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

            # DEBUG: Log tenant_id retrieval for troubleshooting (always log in test environments)
            import logging
            import os

            # Check multiple ways to detect test mode
            is_test = (
                os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("test")
                or "test" in os.environ.get("PYTEST_CURRENT_TEST", "")
                or "test" in str(os.environ.get("DJANGO_SETTINGS_MODULE", ""))
            )

            if is_test:
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"ContractViewSet.get_queryset: tenant_id={tenant_id} (type: {type(tenant_id)}), "
                    f"user.tenant_id={getattr(user, 'tenant_id', None)}, "
                    f"user.tenant={getattr(user, 'tenant', None)}, "
                    f"request.tenant_id={getattr(self.request, 'tenant_id', None)} (type: {type(getattr(self.request, 'tenant_id', None))}), "
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

                # Check multiple ways to detect test mode
                is_test = (
                    os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("test")
                    or "test" in os.environ.get("PYTEST_CURRENT_TEST", "")
                    or "pytest" in str(os.environ.get("_", ""))
                    or "test" in str(os.environ.get("DJANGO_SETTINGS_MODULE", ""))
                )

                if is_test:
                    count_before_filtering = queryset.count()
                    total_for_tenant = Contract.objects.filter(tenant_id=tenant_id).count()
                    # Always log in test mode to debug the issue
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"ContractViewSet.get_queryset: tenant_id={tenant_id} (type: {type(tenant_id)}), "
                        f"queryset.count()={count_before_filtering}, "
                        f"Total contracts for tenant: {total_for_tenant}, "
                        f"request.tenant_id={getattr(self.request, 'tenant_id', None)} (type: {type(getattr(self.request, 'tenant_id', None))}), "
                        f"user.id={getattr(user, 'id', None) if user else None}, "
                        f"user.tenant_id={getattr(user, 'tenant_id', None) if user else None}"
                    )
                    if count_before_filtering == 0 and total_for_tenant > 0:
                        # Queryset is empty but contracts exist - this indicates a filtering issue
                        logger.error(
                            f"ContractViewSet.get_queryset: CRITICAL - queryset is empty but {total_for_tenant} contracts exist for tenant {tenant_id}. "
                            f"This suggests a UUID type mismatch or filtering issue."
                        )
            else:
                queryset = Contract.objects.none()
                # Log when tenant_id is None
                import os

                is_test = (
                    os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("test")
                    or "test" in os.environ.get("PYTEST_CURRENT_TEST", "")
                    or "pytest" in str(os.environ.get("_", ""))
                    or "test" in str(os.environ.get("DJANGO_SETTINGS_MODULE", ""))
                )
                if is_test:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"ContractViewSet.get_queryset: CRITICAL - tenant_id is None! "
                        f"request.tenant_id={getattr(self.request, 'tenant_id', None)}, "
                        f"request.tenant={getattr(self.request, 'tenant', None)}, "
                        f"user.id={getattr(user, 'id', None) if user else None}, "
                        f"user.tenant_id={getattr(user, 'tenant_id', None) if user else None}"
                    )

        # Apply enhanced filtering (GAP-9.2.2)
        # NOTE: Filtering must happen BEFORE sorting annotations are applied
        # because filtering may need to evaluate the queryset, and annotations can interfere
        queryset = self._apply_filtering(queryset)

        # Apply enhanced sorting (GAP-9.2.2)
        # Sorting annotations are applied after filtering to avoid interfering with queryset evaluation
        try:
            queryset = self._apply_sorting(queryset)
        except Exception as sort_err:
            from django.core.exceptions import FieldError
            from rest_framework.exceptions import ValidationError as DRFValidationError
            if isinstance(sort_err, FieldError):
                raise DRFValidationError(
                    detail={"ordering": str(sort_err)},
                    code="invalid_ordering",
                ) from sort_err
            raise

        return queryset

    # SAVING CHECKPOINT: End of get_queryset method (~450 lines).
    # Starting _apply_filtering method (~450-770 lines).

    def _apply_filtering(self, queryset):
        """Apply filtering by owners, tags, quality profile, compliance regime, and new filters (GAP-9.2.2)"""
        request = self.request
        # Handle both DRF Request objects (with query_params) and Django WSGIRequest (with GET)
        if hasattr(request, "query_params"):
            query_params = request.query_params
        else:
            # Fallback for Django WSGIRequest (e.g., in tests with APIRequestFactory)
            query_params = request.GET

        # Filter by owners (email or name)
        owner_email = query_params.get("owner_email")
        owner_name = query_params.get("owner_name")
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
                    info = contract.hub_contract_json.get("info", {})
                    if not info:
                        continue
                    owners = info.get("owners", [])
                    if not owners:
                        continue

                    email_match = True
                    name_match = True

                    if owner_email:
                        # Check if any owner has this email (case-insensitive)
                        email_match = False
                        for owner in owners:
                            if isinstance(owner, dict):
                                owner_email_val = owner.get("email", "")
                                if (
                                    owner_email_val
                                    and owner_email_val.lower() == owner_email.lower()
                                ):
                                    email_match = True
                                    break

                    if owner_name:
                        # Check if any owner has this name (case-insensitive contains)
                        name_match = False
                        for owner in owners:
                            if isinstance(owner, dict):
                                owner_name_val = owner.get("name", "")
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
        tags = query_params.getlist("tag")  # Support multiple tags
        if tags:
            # Filter contracts where hub_contract_json.info.tags contains any of the specified tags
            # Use contains lookup for array elements (works better for simple arrays)
            tag_filter = Q()
            for tag in tags:
                tag_filter |= Q(hub_contract_json__info__tags__contains=[tag])
            queryset = queryset.filter(tag_filter)

        # Filter by quality profile
        quality_profile = query_params.get("quality_profile")
        if quality_profile:
            queryset = queryset.filter(
                hub_contract_json__quality__default_profile_key=quality_profile
            )

        # Filter by compliance regime (jurisdiction)
        compliance_regime = query_params.get("compliance_regime")
        if compliance_regime:
            # Filter contracts where hub_contract_json.privacy_compliance.jurisdictions contains the regime
            queryset = queryset.filter(
                hub_contract_json__privacy_compliance__jurisdictions__contains=[compliance_regime]
            )

        # Filter by contact_email (from contact[] array)
        contact_email = query_params.get("contact_email")
        if contact_email:
            contract_ids = []
            try:
                contracts_list = list(queryset)
                for contract in contracts_list:
                    if not contract.hub_contract_json:
                        continue
                    contacts = contract.hub_contract_json.get("contact", [])
                    if contacts:
                        for contact in contacts:
                            if isinstance(contact, dict):
                                email = contact.get("email", "")
                                if email and email.lower() == contact_email.lower():
                                    contract_ids.append(contract.id)
                                    break
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Error filtering contracts by contact_email: {e}", exc_info=True)
                return queryset.none()

            if contract_ids:
                queryset = queryset.filter(id__in=contract_ids)
            else:
                queryset = queryset.none()

        # Filter by contact_name (from contact[] array)
        contact_name = query_params.get("contact_name")
        if contact_name:
            contract_ids = []
            try:
                contracts_list = list(queryset)
                for contract in contracts_list:
                    if not contract.hub_contract_json:
                        continue
                    contacts = contract.hub_contract_json.get("contact", [])
                    if contacts:
                        for contact in contacts:
                            if isinstance(contact, dict):
                                name = contact.get("name", "")
                                if name and contact_name.lower() in name.lower():
                                    contract_ids.append(contract.id)
                                    break
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Error filtering contracts by contact_name: {e}", exc_info=True)
                return queryset.none()

            if contract_ids:
                queryset = queryset.filter(id__in=contract_ids)
            else:
                queryset = queryset.none()

        # Filter by server_type
        server_type = query_params.get("server_type")
        if server_type:
            queryset = queryset.filter(hub_contract_json__servers__type=server_type)

        # Filter by server_url
        server_url = query_params.get("server_url")
        if server_url:
            queryset = queryset.filter(hub_contract_json__servers__url__icontains=server_url)

        # Filter by min_availability (from servicelevels[])
        min_availability = query_params.get("min_availability")
        if min_availability:
            try:
                min_avail_float = float(min_availability)
                # Filter contracts where any servicelevel has target >= min_availability
                # This requires evaluating the queryset
                contract_ids = []
                contracts_list = list(queryset)
                for contract in contracts_list:
                    if not contract.hub_contract_json:
                        continue
                    servicelevels = contract.hub_contract_json.get("servicelevels", [])
                    if servicelevels:
                        for sl in servicelevels:
                            if isinstance(sl, dict):
                                target = sl.get("target")
                                if target is not None:
                                    try:
                                        target_float = float(target)
                                        if target_float >= min_avail_float:
                                            contract_ids.append(contract.id)
                                            break
                                    except (ValueError, TypeError):
                                        continue
            except (ValueError, TypeError):
                # Invalid min_availability value, return empty queryset
                queryset = queryset.none()
            else:
                if contract_ids:
                    queryset = queryset.filter(id__in=contract_ids)
                else:
                    queryset = queryset.none()

        # Filter by max_latency_ms (from servicelevels[])
        max_latency_ms = query_params.get("max_latency_ms")
        if max_latency_ms:
            try:
                max_latency_float = float(max_latency_ms)
                # Filter contracts where any servicelevel has target <= max_latency_ms
                contract_ids = []
                contracts_list = list(queryset)
                for contract in contracts_list:
                    if not contract.hub_contract_json:
                        continue
                    servicelevels = contract.hub_contract_json.get("servicelevels", [])
                    if servicelevels:
                        for sl in servicelevels:
                            if isinstance(sl, dict):
                                target = sl.get("target")
                                metric = sl.get("metric", "").lower()
                                if target is not None and "latency" in metric:
                                    try:
                                        target_float = float(target)
                                        if target_float <= max_latency_float:
                                            contract_ids.append(contract.id)
                                            break
                                    except (ValueError, TypeError):
                                        continue
            except (ValueError, TypeError):
                queryset = queryset.none()
            else:
                if contract_ids:
                    queryset = queryset.filter(id__in=contract_ids)
                else:
                    queryset = queryset.none()

        # Filter by model_name
        model_name = query_params.get("model_name")
        if model_name:
            queryset = queryset.filter(hub_contract_json__models__name=model_name)

        # Filter by spec_type (ODPS-specific filtering)
        spec_type = query_params.get("spec_type")
        if spec_type:
            queryset = queryset.filter(original_spec_type=spec_type)

        # Filter by odps_version (ODPS-specific filtering)
        odps_version = query_params.get("odps_version")
        if odps_version:
            # Only apply to ODPS contracts
            queryset = queryset.filter(
                original_spec_type=OriginalSpecType.ODPS, original_spec_version=odps_version
            )

        # Filter by has_odps_link (ODPS-specific filtering)
        has_odps_link = query_params.get("has_odps_link")
        if has_odps_link is not None:
            # Convert string to boolean if needed
            if isinstance(has_odps_link, str):
                has_odps_link = has_odps_link.lower() in ("true", "1", "yes")

            # Only apply to ODCS contracts (they can have ODPS links)
            queryset = queryset.filter(original_spec_type=OriginalSpecType.ODCS)

            if has_odps_link:
                # Filter ODCS contracts that have an ODPS link
                # Check for extensions.x_odps.odps_link in hub_contract_json
                # The link must exist and not be null/empty
                queryset = queryset.filter(
                    hub_contract_json__extensions__x_odps__odps_link__isnull=False
                ).exclude(hub_contract_json__extensions__x_odps__odps_link="")
            else:
                # Filter ODCS contracts that do NOT have an ODPS link
                # Use Q objects to handle null checks properly (Q is already imported at top)
                # A contract doesn't have an ODPS link if:
                # - odps_link is null/empty, OR
                # - x_odps section doesn't exist, OR
                # - extensions section doesn't exist
                queryset = queryset.filter(
                    Q(hub_contract_json__extensions__x_odps__odps_link__isnull=True)
                    | Q(hub_contract_json__extensions__x_odps__odps_link="")
                    | Q(hub_contract_json__extensions__x_odps__isnull=True)
                    | Q(hub_contract_json__extensions__isnull=True)
                    | Q(hub_contract_json__isnull=True)
                )

        # Filter by status (Contract lifecycle status: DRAFT, ACTIVE, RETIRED)
        status_filter = query_params.get("status")
        if status_filter:
            # Status is a direct field on Contract model, so we can filter directly
            queryset = queryset.filter(status=status_filter.upper())

        return queryset

    # SAVING CHECKPOINT: End of _apply_filtering method (~770 lines).
    # Starting _apply_sorting method (~770-862 lines).

    def _apply_sorting(self, queryset):
        """Apply sorting by quality score, compliance risk level, creation date, update date (GAP-9.2.2)"""
        request = self.request
        # Handle both DRF Request objects (with query_params) and Django WSGIRequest (with GET)
        if hasattr(request, "query_params"):
            query_params = request.query_params
        else:
            # Fallback for Django WSGIRequest (e.g., in tests with APIRequestFactory)
            query_params = request.GET
        ordering = query_params.get("ordering", "-created_at")  # Default to newest first

        # Parse ordering parameter (can be comma-separated)
        order_fields = [field.strip() for field in ordering.split(",")]

        # Map sort fields to database fields or annotations
        sort_mapping = {
            "created_at": "created_at",
            "-created_at": "-created_at",
            "updated_at": "updated_at",
            "-updated_at": "-updated_at",
            "quality_score": "quality_score",
            "-quality_score": "-quality_score",
            "compliance_risk": "compliance_risk",
            "-compliance_risk": "-compliance_risk",
        }

        # Build ordering list
        ordering_list = []
        invalid_fields = []
        # Valid database fields (in addition to computed fields in sort_mapping)
        valid_db_fields = {"id", "created_at", "updated_at", "status", "version"}

        for field in order_fields:
            field_name = field.lstrip("-")  # Remove leading minus for comparison
            if field in sort_mapping:
                ordering_list.append(sort_mapping[field])
            elif field.startswith("-") and field[1:] in sort_mapping:
                ordering_list.append(sort_mapping[field])
            elif field_name in valid_db_fields:
                # Allow valid database fields
                ordering_list.append(field)
            else:
                # Track invalid fields
                invalid_fields.append(field)

        # If invalid fields were provided, raise FieldError to be caught by error handler
        if invalid_fields:
            from django.core.exceptions import FieldError

            raise FieldError(
                f"Invalid ordering field(s): {', '.join(invalid_fields)}. Valid fields are: {', '.join(sorted(set(sort_mapping.keys()) | valid_db_fields))}"
            )

        # Annotate queryset with computed fields for sorting (GAP-9.2.2)
        # Quality score: extract from hub_contract_json if available
        # For now, we'll use a simple annotation based on normalization status
        # In a real implementation, this would extract from quality metrics
        queryset = queryset.annotate(
            quality_score=Case(
                When(normalization_status=NormalizationStatus.NORMALIZED_OK, then=Value(100)),
                When(
                    normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
                    then=Value(75),
                ),
                When(normalization_status=NormalizationStatus.NORMALIZATION_FAILED, then=Value(0)),
                default=Value(50),
                output_field=IntegerField(),
            )
        )

        # Compliance risk: extract from hub_contract_json.privacy_compliance if available
        # For now, use a simple annotation based on whether personal data is present
        queryset = queryset.annotate(
            compliance_risk=Case(
                When(
                    hub_contract_json__privacy_compliance__contains_personal_data=True,
                    then=Value(100),
                ),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

        # Apply ordering
        if ordering_list:
            queryset = queryset.order_by(*ordering_list)
        else:
            queryset = queryset.order_by("-created_at")  # Default ordering

        return queryset
