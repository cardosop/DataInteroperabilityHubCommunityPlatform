"""
Contract Views

REST API views for contract management.
"""

from django.db import models, transaction
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import filters, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.services.base import NotFoundError as ServiceNotFoundError, NotFoundError
from hub.apps.core.services.base import ValidationError
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.workflows.contract_creation import ContractCreationWorkflow
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow

from .caching import (
    cache_contract,
    cache_lineage,
    cache_query_result,
    get_cached_contract,
    get_cached_lineage,
    get_cached_query_result,
    invalidate_contract_cache,
    invalidate_lineage_cache,
)
from .cli_client import (
    SYNC_TIMEOUT,
    DataContractCLIClient,
    group_errors_by_category,
    interpret_validation_status,
)
from .impact_analysis import ImpactAnalyzer, ImpactScorer
from .impact_notifications import ImpactNotifier
from .impact_visualization import ImpactVisualizer
from .lineage import (
    LineageTraverser,
    generate_lineage_dot,
    generate_lineage_json,
    generate_lineage_mermaid,
)
from .lineage_service import LineageService
from .migration import MigrationStrategy, get_current_hubcontract_version
from .migration_manager import ContractMigrationManager
from .models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalSpecType,
    ValidationStatus,
)
from .normalization import normalize_contract, parse_contract, validate_hubcontract_schema
from .normalization_metrics import record_all_normalization_metrics
from .normalization_service import NormalizationService
from .optimization import (
    estimate_contract_json_size,
    optimize_large_contract_json,
    should_optimize_contract,
)
from .pagination import (
    ContractPageNumberPagination,
    get_pagination_params,
    optimize_queryset_for_pagination,
    paginate_queryset,
)
from .serializers import ContractCreateSerializer, ContractSerializer, ContractUpdateSerializer, ProductCreateSerializer, ODPSLinkSerializer
from .services import ContractService
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow
from hub.apps.observability.otel_metrics import (
    odps_export_duration_seconds,
    odps_export_size_bytes,
    odps_export_total,
)
import time


def _get_tenant_id_from_request(request) -> str:
    """
    Get tenant_id from request (Task 6.6.1).

    Priority:
    1. request.tenant_id (set by middleware/authentication)
    2. request.tenant.id (if tenant object is set)
    3. request.user.tenant_id (if user has tenant_id field)
    4. request.user.tenant.id (if user has tenant relationship)

    Returns:
        Tenant ID as string, or "unknown" if not found
    """
    tenant_id = None

    # Try request.tenant_id first (most reliable, set by middleware)
    if hasattr(request, "tenant_id") and request.tenant_id:
        tenant_id = str(request.tenant_id)

    # Fallback to request.tenant object
    if not tenant_id and hasattr(request, "tenant") and request.tenant:
        tenant_id = str(request.tenant.id)

    # Fallback to user.tenant_id (direct field access)
    if not tenant_id and hasattr(request, "user") and request.user:
        from django.contrib.auth.models import AnonymousUser
        if not isinstance(request.user, AnonymousUser):
            if hasattr(request.user, "tenant_id") and request.user.tenant_id:
                tenant_id = str(request.user.tenant_id)
            # Last resort: get from user.tenant relationship
            elif hasattr(request.user, "tenant") and request.user.tenant:
                tenant_id = str(request.user.tenant.id)

    return tenant_id or "unknown"


def _categorize_export_size(size_bytes: int) -> str:
    """
    Categorize export size into size categories (Task 6.6.1).

    Categories:
    - small: < 10 KB
    - medium: 10 KB - 100 KB
    - large: 100 KB - 1 MB
    - xlarge: >= 1 MB

    Args:
        size_bytes: Size in bytes

    Returns:
        Size category string
    """
    if size_bytes < 10 * 1024:  # < 10 KB
        return "small"
    elif size_bytes < 100 * 1024:  # 10 KB - 100 KB
        return "medium"
    elif size_bytes < 1024 * 1024:  # 100 KB - 1 MB
        return "large"
    else:  # >= 1 MB
        return "xlarge"


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
        Note: Only ODCS is supported. The Data Contract Specification (DCS) has been deprecated.
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
class ContractViewSet(viewsets.ModelViewSet):
    """
    Contract ViewSet with caching and pagination support.

    Features:

    Note: Overrides initialize_request to handle format suffix conflicts
    for the lineage visualization endpoint.
    - Caching for contract retrieval and lineage queries
    - Pagination for large result sets
    - Performance optimizations for large JSON
    """

    pagination_class = ContractPageNumberPagination
    """
    ViewSet for contract management.

    Tenant-scoped: users can only see/manage contracts in their tenant.
    """
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [permissions.IsAuthenticated]

    def check_auditor_permissions(self, request, view_action):
        """Check if AUDITOR role can perform the action (read-only)"""
        if not request.user or not request.user.is_authenticated:
            return True  # Let IsAuthenticated handle this

        # Check if user has AUDITOR role
        if hasattr(request.user, "user_roles"):
            role_names = [ur.role.name for ur in request.user.user_roles.all()]
            if "AUDITOR" in role_names:
                # AUDITOR can only read, not write
                if view_action in ["create", "update", "partial_update", "destroy"]:
                    raise PermissionDenied(
                        "AUDITOR role has read-only access. Cannot perform write operations."
                    )

        return True

    lookup_field = "id"

    def initialize_request(self, request, *args, **kwargs):
        """
        Override initialize_request to handle format suffix conflicts.

        When format is in query parameters (e.g., ?format=dot, ?format=hubcontract), DRF's format suffix
        patterns can interfere. For the lineage visualization and export endpoints, we need to
        ensure query parameters take precedence over format suffixes.
        """
        # Call parent to get the DRF request object
        drf_request = super().initialize_request(request, *args, **kwargs)

        # Check if this is the lineage visualization or export endpoint
        # The action name is determined by the URL path
        path = getattr(drf_request, "path", "")
        if not path and hasattr(request, "META"):
            path = request.META.get("PATH_INFO", "")
        is_lineage_visualization = "lineage/visualization" in path
        is_export = "export" in path

        if is_lineage_visualization or is_export:
            # If format is in query parameters, clear any format from kwargs
            # This prevents DRF from trying to match format suffix patterns
            if "format" in request.GET or "format" in drf_request.query_params:
                # Get format from query params to check if it's a valid format suffix
                format_in_query = request.GET.get("format") or drf_request.query_params.get("format")

                # Valid format suffixes for DRF (json, yaml, etc.)
                valid_format_suffixes = ["json", "yaml", "xml", "csv"]

                # Only clear format if it's NOT a valid format suffix
                # This allows format suffixes to work for other endpoints
                if format_in_query and format_in_query.lower() not in valid_format_suffixes:
                    # Clear format from kwargs if it was set by format suffix pattern
                    if "format" in kwargs:
                        # Store it temporarily but don't use it for routing
                        drf_request._format_from_suffix = kwargs.pop("format")
                    # Also clear format attribute if it was set
                    # CRITICAL: This must be done before content negotiation
                    if hasattr(drf_request, "format") and drf_request.format:
                        drf_request._original_format = drf_request.format
                        drf_request.format = None
                    # Disable format suffix handling for this request
                    # CRITICAL: Set format_kwarg to None to prevent DRF from trying to use format suffixes
                    # This must be set on the viewset instance, not just the request
                    self.format_kwarg = None
                    # Also set on the request object for consistency
                    if hasattr(drf_request, "format_kwarg"):
                        drf_request.format_kwarg = None

        return drf_request

    def perform_content_negotiation(self, request, force=False):
        """
        Override perform_content_negotiation to handle format parameter conflicts.

        For export endpoint, prevent DRF from treating ?format=hubcontract as a format suffix.
        """
        # Check if this is the export endpoint
        # Use action name if available, otherwise check path
        is_export = False
        if hasattr(self, "action") and self.action == "export_contract":
            is_export = True
        else:
            # Check path from request
            path = getattr(request, "path", "")
            if not path and hasattr(request, "META"):
                path = request.META.get("PATH_INFO", "")
            is_export = "export" in path

        if is_export:
            # Get format from query params
            format_in_query = None
            if hasattr(request, "query_params"):
                format_in_query = request.query_params.get("format")
            elif hasattr(request, "GET"):
                format_in_query = request.GET.get("format")

            # Valid format suffixes for DRF (json, yaml, etc.)
            valid_format_suffixes = ["json", "yaml", "xml", "csv"]

            # If format is in query params and it's NOT a valid format suffix,
            # disable format suffix handling for this request
            if format_in_query and format_in_query.lower() not in valid_format_suffixes:
                # Temporarily disable format_kwarg to prevent DRF from trying to use format suffixes
                original_format_kwarg = getattr(self, "format_kwarg", None)
                self.format_kwarg = None
                try:
                    # Perform content negotiation without format suffix
                    return super().perform_content_negotiation(request, force=force)
                finally:
                    # Restore original format_kwarg
                    if original_format_kwarg is not None:
                        self.format_kwarg = original_format_kwarg
                    elif hasattr(self, "format_kwarg"):
                        # If it was None, we might need to explicitly set it back
                        # But for now, just leave it as None since we disabled it
                        pass

        # For other endpoints, use default behavior
        return super().perform_content_negotiation(request, force=force)

    @transaction.atomic
    def create(self, request):
        """
        Create a new contract using workflow orchestration.

        POST /contracts
        Body: {
            "asset_id": "uuid" (optional),
            "original_raw": "contract content",
            "original_format": "JSON" or "YAML",
            "original_spec_type": "ODCS" (optional, auto-detected if not provided)
        }
        """
        self.check_auditor_permissions(request, "create")
        serializer = ContractCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        original_raw = serializer.validated_data["original_raw"]
        original_format = serializer.validated_data["original_format"]
        original_spec_type = serializer.validated_data.get("original_spec_type")
        asset_id = serializer.validated_data.get("asset_id")
        disable_external_refs = serializer.validated_data.get("disable_external_refs", False)
        remove_external_refs = serializer.validated_data.get("remove_external_refs", False)

        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to create contracts"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer
        try:
            service = ContractService(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                request_id=getattr(request, "request_id", None),
            )
            contract = service.create_contract(
                original_raw=original_raw,
                original_format=original_format,
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                asset_id=str(asset_id) if asset_id else None,
                original_spec_type=original_spec_type,
                disable_external_refs=disable_external_refs,
                remove_external_refs=remove_external_refs,
            )

            return Response(ContractSerializer(contract).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details}, status=e.http_status
            )
        except ServiceNotFoundError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details}, status=e.http_status
            )
        except Exception as e:
            return Response(
                {
                    "error": "Contract creation failed",
                    "code": "INTERNAL_ERROR",
                    "details": {"error": str(e)},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Create product (Product-First flow)",
        description="""
        Create ODPS product with linked ODCS contract (Product-First flow).

        This endpoint implements the Product-First creation flow where an ODPS document
        is ingested and automatically linked to an ODCS contract extracted from product.contract.

        **Workflow Steps:**
        1. Parse and validate ODPS document
        2. Resolve $ref references (internal, local, external)
        3. Extract ODCS contract from product.contract (required)
        4. Validate extracted ODCS contract
        5. Normalize ODCS → HubContract (technical)
        6. Normalize ODPS → HubContract (marketplace)
        7. Create ODCS contract record
        8. Create ODPS contract record
        9. Link contracts bidirectionally
        10. Index for search
        11. Generate semantic mapping (RDF)

        **Supported Formats:**
        - JSON (original_format: "JSON")
        - YAML (original_format: "YAML")

        **External References:**
        - `resolve_external_refs=True` (default): External $ref references will be resolved
        - `resolve_external_refs=False`: External $ref references will be disabled (raises error if found)

        **Response:**
        Returns both created contracts (ODPS + ODCS) with bidirectional links established.
        """,
        request=ProductCreateSerializer,
        responses={
            201: inline_serializer(
                name='ProductCreateResponse',
                fields={
                    'odps_contract': ContractSerializer(),
                    'odcs_contract': ContractSerializer(),
                    'workflow_instance_id': serializers.UUIDField(),
                }
            ),
            400: OpenApiResponse(description="Validation error or workflow execution failed"),
        },
        tags=["Contracts", "Products"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="products",
        url_name="create-product"
    )
    @transaction.atomic
    def create_product(self, request):
        """
        Create product using Product-First flow (ODPS).

        POST /api/v1/contracts/products/
        Body: {
            "original_raw": "ODPS document content",
            "original_format": "JSON" or "YAML",
            "resolve_external_refs": true (optional, default: true),
            "asset_id": "uuid" (optional)
        }
        """
        self.check_auditor_permissions(request, "create")
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        original_raw = serializer.validated_data["original_raw"]
        original_format = serializer.validated_data["original_format"]
        resolve_external_refs = serializer.validated_data.get("resolve_external_refs", True)
        asset_id = serializer.validated_data.get("asset_id")

        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to create products"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Execute ProductCreationWorkflow
        try:
            result = ProductCreationWorkflow.execute(
                original_raw=original_raw,
                original_format=original_format,
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                asset_id=str(asset_id) if asset_id else None,
                resolve_external_refs=resolve_external_refs
            )

            # Serialize contracts
            odps_contract_serializer = ContractSerializer(result["odps_contract"])
            odcs_contract_serializer = ContractSerializer(result["odcs_contract"])

            return Response(
                {
                    "odps_contract": odps_contract_serializer.data,
                    "odcs_contract": odcs_contract_serializer.data,
                    "workflow_instance_id": result["workflow_instance_id"]
                },
                status=status.HTTP_201_CREATED
            )
        except ValueError as e:
            return Response(
                {
                    "error": "Product creation failed",
                    "code": "WORKFLOW_EXECUTION_FAILED",
                    "details": {"error": str(e)},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {
                    "error": "Product creation failed",
                    "code": "INTERNAL_ERROR",
                    "details": {"error": str(e)},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
        self.check_auditor_permissions(request, "update")
        contract = self.get_object()
        serializer = ContractUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Store old values for audit
        old_status = contract.status
        old_hub_contract_json = contract.hub_contract_json

        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to update contracts"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer for updates
        try:
            service = ContractService(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                request_id=getattr(request, "request_id", None),
            )

            # Extract update parameters
            original_raw = serializer.validated_data.get("original_raw")
            original_format = serializer.validated_data.get("original_format")
            status_value = serializer.validated_data.get("status")
            remove_external_refs = serializer.validated_data.get("remove_external_refs", False)

            # Update contract using service layer
            contract = service.update_contract(
                contract_id=str(contract.id),
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                original_raw=original_raw,
                original_format=original_format,
                status=status_value,
                remove_external_refs=remove_external_refs,
            )

            return Response(ContractSerializer(contract).data, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details}, status=e.http_status
            )
        except NotFoundError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details}, status=e.http_status
            )
        except Exception as e:
            return Response(
                {
                    "error": "Contract update failed",
                    "code": "INTERNAL_ERROR",
                    "details": {"error": str(e)},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a contract (soft delete: set status to RETIRED).

        DELETE /contracts/{id}
        """
        self.check_auditor_permissions(request, "destroy")
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
                "original_spec_type": contract.original_spec_type,
                "original_spec_version": contract.original_spec_version,
            },
            request=request,
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
            import os
            import logging

            # Check multiple ways to detect test mode
            is_test = (
                os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("test") or
                "test" in os.environ.get("PYTEST_CURRENT_TEST", "") or
                "test" in str(os.environ.get("DJANGO_SETTINGS_MODULE", ""))
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
                    os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("test") or
                    "test" in os.environ.get("PYTEST_CURRENT_TEST", "") or
                    "pytest" in str(os.environ.get("_", "")) or
                    "test" in str(os.environ.get("DJANGO_SETTINGS_MODULE", ""))
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
                    os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("test") or
                    "test" in os.environ.get("PYTEST_CURRENT_TEST", "") or
                    "pytest" in str(os.environ.get("_", "")) or
                    "test" in str(os.environ.get("DJANGO_SETTINGS_MODULE", ""))
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
        queryset = self._apply_sorting(queryset)

        return queryset

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
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version=odps_version
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
                ).exclude(
                    hub_contract_json__extensions__x_odps__odps_link=""
                )
            else:
                # Filter ODCS contracts that do NOT have an ODPS link
                # Use Q objects to handle null checks properly (Q is already imported at top)
                # A contract doesn't have an ODPS link if:
                # - odps_link is null/empty, OR
                # - x_odps section doesn't exist, OR
                # - extensions section doesn't exist
                queryset = queryset.filter(
                    Q(hub_contract_json__extensions__x_odps__odps_link__isnull=True) |
                    Q(hub_contract_json__extensions__x_odps__odps_link="") |
                    Q(hub_contract_json__extensions__x_odps__isnull=True) |
                    Q(hub_contract_json__extensions__isnull=True) |
                    Q(hub_contract_json__isnull=True)
                )

        return queryset

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
        valid_db_fields = {'id', 'created_at', 'updated_at', 'status', 'version'}

        for field in order_fields:
            field_name = field.lstrip('-')  # Remove leading minus for comparison
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
            raise FieldError(f"Invalid ordering field(s): {', '.join(invalid_fields)}. Valid fields are: {', '.join(sorted(set(sort_mapping.keys()) | valid_db_fields))}")

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

    def list(self, request, *args, **kwargs):
        """
        List contracts (tenant-scoped) with enhanced filtering, sorting, caching, and pagination.

        Features:
        - Query result caching
        - Optimized pagination
        - Performance optimizations
        """
        # Handle invalid ordering fields gracefully
        from django.core.exceptions import FieldError
        try:
            # Get tenant ID for caching
            tenant_id = None
            if hasattr(request, "user") and request.user and hasattr(request.user, "tenant_id"):
                tenant_id = str(request.user.tenant_id)

            # Build query parameters dict for cache key
            query_params = dict(request.query_params.items())

            # Check cache for query results
            if tenant_id:
                cached_result = get_cached_query_result(query_params, tenant_id)
                if cached_result:
                    results, total_count = cached_result
                    # Return cached results with pagination metadata
                    pagination_params = get_pagination_params(request)
                    page = pagination_params["page"]
                    page_size = pagination_params["page_size"]

                    # Calculate pagination metadata
                    start_idx = (page - 1) * page_size
                    end_idx = start_idx + page_size
                    paginated_results = results[start_idx:end_idx]

                    return Response(
                        {
                            "count": total_count,
                            "page": page,
                            "page_size": page_size,
                            "total_pages": (total_count + page_size - 1) // page_size,
                            "results": paginated_results,
                            "_cached": True,
                        }
                    )

            # Optimize queryset for pagination
            queryset = self.filter_queryset(self.get_queryset())
            queryset = optimize_queryset_for_pagination(queryset)

            # Get pagination parameters
            pagination_params = get_pagination_params(request)

            # Paginate queryset
            results, pagination_meta = paginate_queryset(
                queryset,
                page=pagination_params["page"],
                page_size=pagination_params["page_size"],
                max_page_size=pagination_params["max_page_size"],
            )

            # Serialize results
            serializer = self.get_serializer(results, many=True)

            # Cache query results if tenant_id is available
            if tenant_id:
                cache_query_result(query_params, tenant_id, serializer.data, pagination_meta["count"])

            # Return paginated response
            return Response(
                {
                    "count": pagination_meta["count"],
                    "page": pagination_meta["page"],
                    "page_size": pagination_meta["page_size"],
                    "total_pages": pagination_meta["total_pages"],
                    "has_next": pagination_meta["has_next"],
                    "has_previous": pagination_meta["has_previous"],
                    "next_page": pagination_meta.get("next_page"),
                    "previous_page": pagination_meta.get("previous_page"),
                    "results": serializer.data,
                }
            )
        except FieldError as e:
            # Handle invalid ordering fields gracefully
            if 'ordering' in str(e).lower() or 'order' in str(e).lower():
                return Response(
                    {"error": f"Invalid ordering field: {str(e)}", "code": "INVALID_ORDERING"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Re-raise other FieldErrors
            raise

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve contract by ID with caching support.

        Applies ON_READ migration (lazy migration) if needed (GAP-10.2.2).
        Supports both v1 and v2 contracts (backward compatible).
        """
        contract = self.get_object()
        contract_id = str(contract.id)

        # Check cache first
        cached_data = get_cached_contract(contract_id)
        if cached_data:
            # Return cached data (but still apply migration if needed)
            serializer = self.get_serializer(contract)
            response_data = serializer.data
            response_data["hub_contract_json"] = cached_data.get(
                "hub_contract_json", contract.hub_contract_json
            )
            response_data["_cached"] = True
            return Response(response_data)

        # Apply ON_READ migration (lazy, in-memory) for backward compatibility (GAP-10.2.2)
        if contract.hub_contract_json and contract.hub_contract_version:
            migrated_hub_contract, migration_warnings = ContractMigrationManager.migrate_on_read(
                contract
            )

            # If migration was applied, return migrated version in response
            # (but don't update DB - that's the lazy part)
            if migrated_hub_contract != contract.hub_contract_json:
                # Create a temporary serializer with migrated contract
                serializer = self.get_serializer(contract)
                response_data = serializer.data
                # Override hub_contract_json with migrated version
                response_data["hub_contract_json"] = migrated_hub_contract
                if migration_warnings:
                    response_data["migration_warnings"] = migration_warnings

                # Cache the migrated contract
                cache_contract(
                    contract_id,
                    {
                        "hub_contract_json": migrated_hub_contract,
                        "status": contract.status,
                        "normalization_status": contract.normalization_status,
                    },
                )

                return Response(response_data)

        # Cache the contract for future requests
        if contract.hub_contract_json:
            # Optimize large JSON before caching
            if should_optimize_contract(contract.hub_contract_json):
                optimized_json = optimize_large_contract_json(contract.hub_contract_json)
                cache_contract(
                    contract_id,
                    {
                        "hub_contract_json": optimized_json,
                        "status": contract.status,
                        "normalization_status": contract.normalization_status,
                    },
                )
            else:
                cache_contract(
                    contract_id,
                    {
                        "hub_contract_json": contract.hub_contract_json,
                        "status": contract.status,
                        "normalization_status": contract.normalization_status,
                    },
                )

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
            name="ContractValidationRequest",
            fields={
                "async": serializers.BooleanField(
                    required=False, default=False, help_text="Use async validation (default: false)"
                )
            },
        ),
        responses={
            200: inline_serializer(
                name="ContractValidationResponse",
                fields={
                    "validation_status": serializers.CharField(),
                    "errors": serializers.ListField(child=serializers.DictField()),
                    "warnings": serializers.ListField(child=serializers.DictField()),
                    "grouped_errors": serializers.DictField(),
                    "cli_version": serializers.CharField(),
                    "validated_at": serializers.DateTimeField(),
                },
            ),
            202: inline_serializer(
                name="ContractValidationJobResponse",
                fields={
                    "job_id": serializers.UUIDField(),
                    "status": serializers.CharField(),
                    "message": serializers.CharField(),
                },
            ),
            500: OpenApiResponse(description="Validation failed"),
        },
        tags=["Contracts"],
    )
    @action(detail=True, methods=["post"], url_path="validate")
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

        use_async = request.data.get("async", False)
        contract_size = len(contract.original_raw.encode("utf-8"))

        # Determine if async is needed based on size
        from django.conf import settings

        sync_size_limit = getattr(settings, "DATACONTRACT_VALIDATION_SYNC_SIZE_LIMIT", 100 * 1024)

        if contract_size > sync_size_limit:
            use_async = True

        # Try async validation if requested
        if use_async:
            # Create async validation job
            try:
                job = create_job(
                    job_type=JobType.CONTRACT_VALIDATION,
                    resource_type="CONTRACT",
                    resource_id=str(contract.id),
                    tenant=contract.tenant,
                    created_by=request.user,
                    details_json={"contract_id": str(contract.id), "validation_type": "async"},
                    queue_name="default",
                )

                # Log audit event
                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_VALIDATION_STARTED",
                    actor_user=request.user,
                    tenant=contract.tenant,
                    resource_id=str(contract.id),
                    details={"job_id": str(job.id), "validation_type": "async"},
                    request=request,
                )

                return Response(
                    {
                        "job_id": str(job.id),
                        "status": "pending",
                        "message": "Validation job created. Poll /jobs/{job_id} for status.",
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
            except Exception as e:
                # If async job creation fails, fall back to sync validation
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to create async validation job: {e}. Falling back to sync validation.")
                # Fall through to sync validation below
                use_async = False

        # Synchronous validation (default or fallback from async failure)
        if not use_async:
            try:
                cli_client = DataContractCLIClient()

                # Validate contract
                validation_result = cli_client.validate(
                    raw_contract=contract.original_raw,
                    format=contract.original_format,
                    tenant_id=str(contract.tenant.id) if contract.tenant else None,
                    use_cache=True,
                    timeout=SYNC_TIMEOUT,
                )

                # Interpret validation status
                validation_status, errors, warnings = interpret_validation_status(validation_result)

                # Group errors by category
                grouped_errors = group_errors_by_category(errors)

                # Update contract with validation results
                contract.validation_status = validation_status
                contract.validation_errors = errors
                contract.validation_warnings = warnings
                contract.cli_version = validation_result.get("cli_version", "unknown")
                contract.last_validated_at = timezone.now()
                contract.save(
                    update_fields=[
                        "validation_status",
                        "validation_errors",
                        "validation_warnings",
                        "cli_version",
                        "last_validated_at",
                        "updated_at",
                    ]
                )

                # Log audit event
                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_VALIDATION_COMPLETED",
                    actor_user=request.user,
                    tenant=contract.tenant,
                    resource_id=str(contract.id),
                    details={
                        "validation_status": validation_status,
                        "error_count": len(errors),
                        "warning_count": len(warnings),
                        "cli_version": contract.cli_version,
                    },
                    request=request,
                )

                # Build enhanced response with field-level details
                response_data = {
                    "validation_status": validation_status,
                    "valid": validation_status in ["VALID", "WARNING_ONLY"],
                    "errors": errors,
                    "warnings": warnings,
                    "grouped_errors": grouped_errors,
                    "error_count": len(errors),
                    "warning_count": len(warnings),
                    "schema_compliance": {
                        "status": "COMPLIANT" if validation_status == "VALID" else "NON_COMPLIANT",
                        "details": "Schema validation passed" if validation_status == "VALID" else "Schema validation failed or has warnings"
                    },
                    "normalization_status": contract.normalization_status,
                    "normalization_compliant": contract.normalization_status in [
                        "NORMALIZED_OK",
                        "NORMALIZED_WITH_WARNINGS"
                    ],
                    "cli_version": contract.cli_version,
                    "validated_at": contract.last_validated_at.isoformat(),
                    "contract_id": str(contract.id),
                }

                # Add field-level error summary if errors exist
                if errors:
                    field_errors = {}
                    for error in errors:
                        field_path = error.get("path", "")
                        if field_path:
                            if field_path not in field_errors:
                                field_errors[field_path] = []
                            field_errors[field_path].append({
                                "message": error.get("message", ""),
                                "severity": error.get("severity", "ERROR"),
                                "rule_id": error.get("rule_id", ""),
                                "category": error.get("category", "unknown")
                            })
                    response_data["field_errors"] = field_errors

                return Response(
                    response_data,
                    status=status.HTTP_200_OK,
                )

            except Exception as e:
                # Check if error is from DataContract service (service unavailable)
                error_str = str(e).lower()
                is_service_error = (
                    "datacontract service" in error_str
                    or "service server error" in error_str
                    or "service timeout" in error_str
                    or "service error" in error_str
                    or "connection" in error_str
                )

                # Mark validation as ERROR
                contract.validation_status = ValidationStatus.ERROR
                contract.validation_errors = [{"message": str(e), "severity": "ERROR"}]
                contract.last_validated_at = timezone.now()
                contract.save(
                    update_fields=[
                        "validation_status",
                        "validation_errors",
                        "last_validated_at",
                        "updated_at",
                    ]
                )

                # Log audit event
                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_VALIDATION_FAILED",
                    actor_user=request.user,
                    tenant=contract.tenant,
                    resource_id=str(contract.id),
                    details={"error": str(e)},
                    request=request,
                )

                # Return 503 for service unavailable, 500 for other errors
                http_status = (
                    status.HTTP_503_SERVICE_UNAVAILABLE
                    if is_service_error
                    else status.HTTP_500_INTERNAL_SERVER_ERROR
                )

                return Response(
                    {"error": f"Validation failed: {str(e)}"},
                    status=http_status,
                )

    @extend_schema(
        summary="Lint contract",
        description="""
        Lint a contract using DataContract CLI.

        Returns linting issues and recommendations for improving the contract.
        """,
        responses={
            200: inline_serializer(
                name="ContractLintResponse",
                fields={
                    "issues": serializers.ListField(child=serializers.DictField()),
                    "cli_version": serializers.CharField(),
                },
            ),
            500: OpenApiResponse(description="Linting failed"),
        },
        tags=["Contracts"],
    )
    @action(detail=True, methods=["post"], url_path="lint")
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
                timeout=SYNC_TIMEOUT,
            )

            # Log audit event
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_LINTED",
                actor_user=request.user,
                tenant=contract.tenant,
                resource_id=str(contract.id),
                details={"issues_count": len(lint_result.get("issues", []))},
                request=request,
            )

            return Response(
                {
                    "issues": lint_result.get("issues", []),
                    "cli_version": lint_result.get("cli_version", "unknown"),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"Linting failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
            name="ContractConvertRequest",
            fields={
                "target_format": serializers.ChoiceField(
                    choices=["JSON", "YAML"],
                    required=True,
                    help_text="Target format for conversion",
                )
            },
        ),
        responses={
            200: inline_serializer(
                name="ContractConvertResponse",
                fields={
                    "converted_contract": serializers.CharField(),
                    "target_format": serializers.CharField(),
                    "format": serializers.CharField(),
                    "cli_version": serializers.CharField(),
                },
            ),
            400: OpenApiResponse(description="Invalid target format"),
            500: OpenApiResponse(description="Conversion failed"),
        },
        tags=["Contracts"],
    )
    @action(detail=True, methods=["post"], url_path="convert")
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
        target_format = request.data.get("target_format", "JSON")

        if target_format not in ["JSON", "YAML"]:
            return Response(
                {"error": "target_format must be JSON or YAML"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            cli_client = DataContractCLIClient()

            # Convert contract
            convert_result = cli_client.convert(
                raw_contract=contract.original_raw,
                source_format=contract.original_format,
                target_format=target_format,
                timeout=SYNC_TIMEOUT,
            )

            # Log audit event
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_CONVERTED",
                actor_user=request.user,
                tenant=contract.tenant,
                resource_id=str(contract.id),
                details={"source_format": contract.original_format, "target_format": target_format},
                request=request,
            )

            return Response(
                {
                    "converted_contract": convert_result.get("converted_contract", ""),
                    "target_format": convert_result.get("target_format", target_format),
                    "format": target_format,  # Keep for backward compatibility
                    "cli_version": convert_result.get("cli_version", "unknown"),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"Conversion failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
            name="ContractMigrationRequest",
            fields={
                "target_hub_contract_version": serializers.CharField(
                    required=False, help_text="Target HubContract version (defaults to current)"
                ),
                "migration_strategy": serializers.ChoiceField(
                    choices=["ON_WRITE", "ON_READ", "BACKGROUND"],
                    required=False,
                    default="ON_WRITE",
                    help_text="Migration strategy (default: ON_WRITE)",
                ),
            },
        ),
        responses={
            200: inline_serializer(
                name="ContractMigrationResponse",
                fields={
                    "contract": ContractSerializer,
                    "migration_applied": serializers.BooleanField(),
                    "migration_details": serializers.DictField(),
                },
            ),
            202: inline_serializer(
                name="ContractMigrationJobResponse",
                fields={
                    "job": serializers.DictField(),
                    "migration_details": serializers.DictField(),
                },
            ),
            400: OpenApiResponse(
                description="Invalid migration strategy or contract not normalized"
            ),
        },
        tags=["Contracts"],
    )
    @extend_schema(
        summary="Link ODPS contract to ODCS contract",
        description="""
        Link an ODPS contract to an existing ODCS contract (bidirectional linking).

        This endpoint implements Task 3.5.2: ODPS linking endpoint.
        It accepts either an existing ODPS contract ID or an ODPS document,
        validates compatibility, and creates bidirectional links.

        **Compatibility Validation:**
        - ODPS product.contract must match the ODCS contract (id, name, schema)
        - Both contracts must belong to the same tenant
        - Both contracts must be normalized

        **Linking:**
        - Creates bidirectional links: ODPS → ODCS and ODCS → ODPS
        - Links are stored in hub_contract_json.extensions.x_odps

        **Request Body Options:**
        1. Link to existing ODPS contract:
           ```json
           {
             "odps_contract_id": "uuid-of-existing-odps-contract"
           }
           ```

        2. Create and link new ODPS contract:
           ```json
           {
             "original_raw": "ODPS document content",
             "original_format": "JSON" or "YAML",
             "resolve_external_refs": true (optional, default: true)
           }
           ```

        **Response:**
        Returns the linked ODPS contract with bidirectional link established.
        """,
        request=ODPSLinkSerializer,
        responses={
            200: ContractSerializer,
            400: OpenApiResponse(description="Validation error or compatibility check failed"),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Linking"],
    )
    @action(detail=True, methods=["post"], url_path="link-odps")
    @transaction.atomic
    def link_odps(self, request, id=None):
        """
        Link ODPS contract to ODCS contract.

        POST /api/v1/contracts/{id}/link-odps/
        Body: {
            "odps_contract_id": "uuid" (optional, to link existing ODPS contract),
            OR
            "original_raw": "ODPS document content" (optional, to create new ODPS contract),
            "original_format": "JSON" or "YAML" (required if original_raw provided),
            "resolve_external_refs": true (optional, default: true, only used if original_raw provided)
        }
        """
        self.check_auditor_permissions(request, "update")
        contract = self.get_object()

        # Verify contract is ODCS
        if contract.original_spec_type != OriginalSpecType.ODCS:
            return Response(
                {
                    "error": "Contract must be ODCS type for ODPS linking",
                    "code": "INVALID_CONTRACT_TYPE",
                    "details": {"contract_type": contract.original_spec_type},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ODPSLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        odps_contract_id = serializer.validated_data.get("odps_contract_id")
        odps_raw = serializer.validated_data.get("original_raw")
        odps_format = serializer.validated_data.get("original_format")
        resolve_external_refs = serializer.validated_data.get("resolve_external_refs", True)

        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to link contracts"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer
        try:
            service = ContractService(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                request_id=getattr(request, "request_id", None),
            )
            odps_contract = service.link_odps_to_odcs(
                odcs_contract_id=str(contract.id),
                odps_contract_id=str(odps_contract_id) if odps_contract_id else None,
                odps_raw=odps_raw,
                odps_format=odps_format,
                resolve_external_refs=resolve_external_refs,
                tenant_id=str(tenant.id),
                user_id=str(request.user.id)
            )

            return Response(ContractSerializer(odps_contract).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details}, status=status.HTTP_400_BAD_REQUEST
            )
        except NotFoundError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            # Log the full exception for debugging
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(
                f"ODPS linking failed: {str(e)}\n{traceback.format_exc()}",
                exc_info=True
            )
            return Response(
                {
                    "error": "ODPS linking failed",
                    "code": "INTERNAL_ERROR",
                    "details": {"error": str(e), "type": type(e).__name__},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Unlink ODPS from ODCS contract",
        description="Remove the bidirectional link between an ODCS contract and its linked ODPS contract.",
        request=None,
        responses={
            200: OpenApiResponse(description="Successfully unlinked"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Linking"],
    )
    @action(detail=True, methods=["post"], url_path="unlink-odps")
    @transaction.atomic
    def unlink_odps(self, request, id=None):
        """
        Unlink ODPS contract from ODCS contract.

        POST /api/v1/contracts/{id}/unlink-odps/
        """
        self.check_auditor_permissions(request, "update")
        contract = self.get_object()

        # Verify contract is ODCS
        if contract.original_spec_type != OriginalSpecType.ODCS:
            return Response(
                {
                    "error": "Contract must be ODCS type for ODPS unlinking",
                    "code": "INVALID_CONTRACT_TYPE",
                    "details": {"contract_type": contract.original_spec_type},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to unlink contracts"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer
        try:
            service = ContractService(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                request_id=getattr(request, "request_id", None),
            )
            service.unlink_odps_from_odcs(
                odcs_contract_id=str(contract.id),
                tenant_id=str(tenant.id),
                user_id=str(request.user.id)
            )

            return Response(
                {"message": "ODPS contract unlinked successfully"},
                status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details}, status=status.HTTP_400_BAD_REQUEST
            )
        except NotFoundError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            # Log the full exception for debugging
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(
                f"ODPS unlinking failed: {str(e)}\n{traceback.format_exc()}",
                exc_info=True
            )
            return Response(
                {
                    "error": "ODPS unlinking failed",
                    "code": "INTERNAL_ERROR",
                    "details": {"error": str(e), "type": type(e).__name__},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="List contract links",
        description="Get all links for a contract (ODPS and ODCS links).",
        responses={
            200: inline_serializer(
                name="ContractLinksResponse",
                fields={
                    "odps_link": ContractSerializer(allow_null=True),
                    "odcs_link": ContractSerializer(allow_null=True),
                },
            ),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Linking"],
    )
    @action(detail=True, methods=["get"], url_path="links")
    def list_links(self, request, id=None):
        """
        List all links for a contract.

        GET /api/v1/contracts/{id}/links/
        Returns: {
            "odps_link": {...} or null,
            "odcs_link": {...} or null
        }
        """
        self.check_auditor_permissions(request, "view")
        contract = self.get_object()

        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to view contract links"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer
        try:
            service = ContractService(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                request_id=getattr(request, "request_id", None),
            )
            links = service.get_contract_links(
                contract_id=str(contract.id),
                tenant_id=str(tenant.id),
                user_id=str(request.user.id)
            )

            return Response(links, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details}, status=status.HTTP_400_BAD_REQUEST
            )
        except NotFoundError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            # Log the full exception for debugging
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to get contract links: {str(e)}\n{traceback.format_exc()}",
                exc_info=True
            )
            return Response(
                {
                    "error": "Failed to get contract links",
                    "code": "INTERNAL_ERROR",
                    "details": {"error": str(e), "type": type(e).__name__},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"], url_path="migrate")
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

        target_version = request.data.get("target_hub_contract_version")
        if not target_version:
            target_version = get_current_hubcontract_version()

        strategy = request.data.get("migration_strategy", MigrationStrategy.ON_WRITE)

        if strategy not in [
            MigrationStrategy.ON_WRITE,
            MigrationStrategy.ON_READ,
            MigrationStrategy.BACKGROUND,
        ]:
            return Response(
                {"error": f"Invalid migration_strategy: {strategy}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if migration is needed
        if not contract.hub_contract_json or not contract.hub_contract_version:
            return Response(
                {"error": "Contract is not normalized. Cannot migrate."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if contract.hub_contract_version == target_version:
            return Response(
                {
                    "contract": ContractSerializer(contract).data,
                    "migration_applied": False,
                    "migration_details": {
                        "source_version": contract.hub_contract_version,
                        "target_version": target_version,
                        "message": "Contract is already at target version",
                    },
                },
                status=status.HTTP_200_OK,
            )

        # Execute migration based on strategy
        if strategy == MigrationStrategy.ON_WRITE:
            migrated, migrated_hub_contract, warnings = ContractMigrationManager.migrate_on_write(
                contract
            )

            if not migrated:
                # Migration not needed (already at target version) or failed
                # Check if it's because migration isn't needed
                from .migration import needs_migration

                if not needs_migration(contract.hub_contract_version):
                    # Already at target version - return success
                    return Response(
                        {
                            "contract": ContractSerializer(contract).data,
                            "migration_applied": False,
                            "migration_details": {
                                "source_version": contract.hub_contract_version,
                                "target_version": target_version,
                                "message": "Contract is already at target version",
                            },
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    # Migration failed
                    return Response(
                        {"error": "Migration failed or not supported"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Refresh contract from DB
            contract.refresh_from_db()

            return Response(
                {
                    "contract": ContractSerializer(contract).data,
                    "migration_applied": True,
                    "migration_details": {
                        "source_version": contract.hub_contract_version,
                        "target_version": target_version,
                        "migration_strategy": strategy,
                        "warnings": warnings,
                    },
                },
                status=status.HTTP_200_OK,
            )

        elif strategy == MigrationStrategy.ON_READ:
            migrated_hub_contract, warnings = ContractMigrationManager.migrate_on_read(contract)

            # Return migrated version (in-memory, not persisted)
            serializer = ContractSerializer(contract)
            response_data = serializer.data
            response_data["hub_contract_json"] = migrated_hub_contract

            return Response(
                {
                    "contract": response_data,
                    "migration_applied": True,
                    "migration_details": {
                        "source_version": contract.hub_contract_version,
                        "target_version": target_version,
                        "migration_strategy": strategy,
                        "warnings": warnings,
                        "note": "Migration applied in-memory only (lazy migration)",
                    },
                },
                status=status.HTTP_200_OK,
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
                            "contract": ContractSerializer(contract).data,
                            "migration_applied": False,
                            "migration_details": {
                                "source_version": contract.hub_contract_version,
                                "target_version": target_version,
                                "message": "Contract is already at target version",
                            },
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    # Migration failed
                    return Response(
                        {"error": "Migration failed or not needed"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            return Response(
                {
                    "job": {
                        "id": str(job.id),
                        "type": job.type,
                        "status": job.status,
                        "resource_type": job.resource_type,
                        "resource_id": str(job.resource_id),
                    },
                    "migration_details": {
                        "source_version": contract.hub_contract_version,
                        "target_version": target_version,
                        "migration_strategy": strategy,
                    },
                },
                status=status.HTTP_202_ACCEPTED,
            )

    @extend_schema(
        summary="Get field-level lineage",
        description="""
        Get lineage for a specific field in a contract.

        Returns lineage information including input fields and transformations.
        """,
        parameters=[
            OpenApiParameter(
                name="field_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="Field name",
                required=True,
            ),
        ],
        responses={
            200: inline_serializer(
                name="FieldLineageResponse",
                fields={
                    "field_name": serializers.CharField(),
                    "lineage": serializers.DictField(),
                },
            ),
            404: OpenApiResponse(description="Contract or field not found"),
        },
        tags=["Contracts", "Lineage"],
    )
    @action(detail=True, methods=["get"], url_path="fields/(?P<field_name>[^/.]+)/lineage")
    def get_field_lineage(self, request, id=None, field_name=None):
        """
        Get field-level lineage with caching support.
        """
        contract = self.get_object()
        contract_id = str(contract.id)

        if not contract.hub_contract_json:
            return Response(
                {"error": "Contract has no hub_contract_json"}, status=status.HTTP_404_NOT_FOUND
            )

        hub_contract = contract.hub_contract_json
        models_list = hub_contract.get("models", [])

        for model in models_list:
            if not isinstance(model, dict):
                continue
            model_name = model.get("name")
            fields = model.get("fields", [])
            for field in fields:
                if isinstance(field, dict) and field.get("name") == field_name:
                    lineage = field.get("lineage", {})

                    # Check cache first
                    cached_lineage = get_cached_lineage(
                        contract_id, model_name=model_name, field_name=field_name
                    )
                    if cached_lineage:
                        # Cached data might be in different formats, normalize it
                        if isinstance(cached_lineage, dict) and "lineage" in cached_lineage:
                            return Response(cached_lineage)
                        return Response(
                            {
                                "field_name": field_name,
                                "model_name": model_name,
                                "lineage": (
                                    cached_lineage
                                    if isinstance(cached_lineage, dict)
                                    and "input_fields" in cached_lineage
                                    else {
                                        "input_fields": cached_lineage.get("input_fields", []),
                                        "transformations": cached_lineage.get(
                                            "transformations", []
                                        ),
                                    }
                                ),
                                "_cached": True,
                            }
                        )

                    # Format lineage response to match service layer format
                    field_lineage_result = {
                        "field_name": field_name,
                        "model_name": model_name,
                        "lineage": {
                            "input_fields": lineage.get("input_fields", []),
                            "transformations": lineage.get("transformations", []),
                        },
                    }

                    # Cache the lineage
                    cache_lineage(
                        contract_id,
                        field_lineage_result,
                        model_name=model_name,
                        field_name=field_name,
                    )

                    return Response(field_lineage_result)

        return Response(
            {"error": f"Field {field_name} not found"}, status=status.HTTP_404_NOT_FOUND
        )

    @extend_schema(
        summary="Get model-level lineage",
        description="""
        Get lineage for a specific model in a contract.

        Returns lineage information including model references and entries.
        """,
        parameters=[
            OpenApiParameter(
                name="model_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="Model name",
                required=True,
            ),
        ],
        responses={
            200: inline_serializer(
                name="ModelLineageResponse",
                fields={
                    "model_name": serializers.CharField(),
                    "lineage": serializers.DictField(),
                },
            ),
            404: OpenApiResponse(description="Contract or model not found"),
        },
        tags=["Contracts", "Lineage"],
    )
    @action(detail=True, methods=["get"], url_path="models/(?P<model_name>[^/.]+)/lineage")
    def get_model_lineage(self, request, id=None, model_name=None):
        """
        Get model-level lineage with caching support.
        """
        contract = self.get_object()
        contract_id = str(contract.id)

        # Check cache first
        cached_lineage = get_cached_lineage(contract_id, model_name=model_name)
        if cached_lineage:
            # Cached data might be in different formats, normalize it
            if isinstance(cached_lineage, dict) and "lineage" in cached_lineage:
                return Response(cached_lineage)
            return Response(
                {
                    "model_name": model_name,
                    "lineage": (
                        cached_lineage
                        if isinstance(cached_lineage, dict) and "models" in cached_lineage
                        else {
                            "models": cached_lineage.get("models", []),
                            "entries": cached_lineage.get("entries", []),
                        }
                    ),
                    "_cached": True,
                }
            )

        # Generate lineage
        if not contract.hub_contract_json:
            return Response(
                {"error": "Contract has no hub_contract_json"}, status=status.HTTP_404_NOT_FOUND
            )

        hub_contract = contract.hub_contract_json
        models_list = hub_contract.get("models", [])

        for model in models_list:
            if isinstance(model, dict) and model.get("name") == model_name:
                lineage_data = model.get("lineage", {})

                # Format response to match service layer format
                model_lineage_result = {
                    "model_name": model_name,
                    "lineage": {
                        "models": lineage_data.get("models", []),
                        "entries": lineage_data.get("entries", []),
                    },
                }

                # Cache the lineage
                cache_lineage(contract_id, model_lineage_result, model_name=model_name)

                return Response(model_lineage_result)

        return Response(
            {"error": f"Model {model_name} not found"}, status=status.HTTP_404_NOT_FOUND
        )

    @extend_schema(
        summary="Get contract-level lineage",
        description="""
        Get contract-level lineage including contract references.

        Returns contract references and lineage entries.
        """,
        responses={
            200: inline_serializer(
                name="ContractLineageResponse",
                fields={
                    "contracts": serializers.ListField(),
                    "entries": serializers.ListField(),
                },
            ),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Lineage"],
    )
    @action(detail=True, methods=["get"], url_path="lineage/contracts")
    def get_contract_lineage(self, request, id=None):
        """
        Get contract-level lineage with caching support.
        """
        contract = self.get_object()
        contract_id = str(contract.id)

        # Check cache first
        cached_lineage = get_cached_lineage(contract_id)
        if cached_lineage:
            # Cached lineage should already be in {contracts, entries} format
            if isinstance(cached_lineage, dict):
                return Response(
                    {
                        "contracts": cached_lineage.get("contracts", []),
                        "entries": cached_lineage.get("entries", []),
                        "_cached": True,
                    }
                )

        # Generate lineage (existing logic)
        from .lineage import extract_contract_level_lineage

        hub_contract = contract.hub_contract_json
        if not hub_contract:
            return Response(
                {"error": "Contract is not normalized"}, status=status.HTTP_400_BAD_REQUEST
            )

        lineage = hub_contract.get("lineage", {})
        if not lineage:
            return Response({"contracts": [], "entries": []})

        # Extract contracts and entries from lineage
        contracts = lineage.get("contracts", []) if isinstance(lineage, dict) else []
        entries = lineage.get("entries", []) if isinstance(lineage, dict) else []

        # Cache the lineage in expected format
        cache_lineage(contract_id, {"contracts": contracts, "entries": entries})

        return Response({"contracts": contracts, "entries": entries})

    @extend_schema(
        summary="Get hierarchical lineage",
        description="""
        Get complete hierarchical lineage (contract, model, and field levels).

        Returns full lineage traversal with all levels.
        """,
        parameters=[
            OpenApiParameter(
                name="max_contract_depth",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum contract depth for traversal (default: 10)",
                required=False,
            ),
            OpenApiParameter(
                name="max_model_depth",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum model depth for traversal (default: 10)",
                required=False,
            ),
            OpenApiParameter(
                name="max_field_depth",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum field depth for traversal (default: 10)",
                required=False,
            ),
        ],
        responses={
            200: inline_serializer(
                name="HierarchicalLineageResponse",
                fields={
                    "upstream": serializers.DictField(),
                    "downstream": serializers.DictField(),
                },
            ),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Lineage"],
    )
    @action(detail=True, methods=["get"], url_path="lineage/full")
    def get_hierarchical_lineage(self, request, id=None):
        """Get hierarchical lineage (bidirectional traversal)."""
        contract = self.get_object()

        max_contract_depth = int(request.query_params.get("max_contract_depth", 10))
        max_model_depth = int(request.query_params.get("max_model_depth", 10))
        max_field_depth = int(request.query_params.get("max_field_depth", 10))

        traverser = LineageTraverser(
            contract,
            max_contract_depth=max_contract_depth,
            max_model_depth=max_model_depth,
            max_field_depth=max_field_depth,
        )

        result = traverser.traverse_bidirectional()

        return Response(result)

    @extend_schema(
        summary="Get lineage visualization",
        description="""
        Get lineage graph in various visualization formats.

        Supports JSON (D3.js), DOT (Graphviz), and Mermaid formats.
        """,
        parameters=[
            OpenApiParameter(
                name="format",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Visualization format: json, dot, or mermaid (default: json)",
                required=False,
            ),
            OpenApiParameter(
                name="max_depth",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum traversal depth (default: 10)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Lineage graph in requested format"),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Lineage"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="lineage/visualization",
        url_name="lineage-visualization",
    )
    def get_lineage_visualization(self, request, id=None):
        """Get lineage visualization in various formats."""
        # Use pre-retrieved contract if available (from custom view), otherwise use get_object()
        # This allows the custom URL view to bypass DRF's get_object() which may have issues
        # with manually instantiated viewsets
        if hasattr(self, "_contract"):
            contract = self._contract
            # Clean up the temporary attribute
            delattr(self, "_contract")
        else:
            # Use get_object() for proper tenant scoping and object retrieval
            # This is the same approach used by get_hierarchical_lineage which works correctly
            # get_object() handles tenant scoping automatically via get_queryset()
            contract = self.get_object()

        # Get format from query params - prioritize query param over format suffix
        # DRF's DefaultRouter creates format suffix patterns that can interfere with query params
        # CRITICAL: Check query parameter FIRST before any format suffix handling
        # This ensures ?format=dot works even if DRF tries to interpret it as a suffix
        # Use request.query_params (DRF's version) - this works with both DRF Request and Django HttpRequest
        # If request is a DRF Request, use query_params; if it's a Django HttpRequest, use GET
        if hasattr(request, "query_params"):
            format_param = request.query_params.get("format", "json").lower().strip()
        elif hasattr(request, "GET"):
            format_param = request.GET.get("format", "json").lower().strip()
        else:
            format_param = "json"

        # Also check DRF's format attribute (set by format suffix pattern) as fallback
        # But only if query param wasn't found
        if not format_param and hasattr(request, "format") and request.format:
            format_param = request.format.lower()

        format_type = format_param if format_param in ["json", "dot", "mermaid"] else "json"
        max_depth = int(request.query_params.get("max_depth", 10))

        if format_type == "dot":
            dot_string = generate_lineage_dot(contract, max_depth=max_depth)
            return Response(dot_string, content_type="text/plain")
        elif format_type == "mermaid":
            mermaid_string = generate_lineage_mermaid(contract, max_depth=max_depth)
            return Response(mermaid_string, content_type="text/plain")
        else:  # Default to JSON
            graph_data = generate_lineage_json(contract, max_depth=max_depth)
            return Response(graph_data)

    @extend_schema(
        summary="Get impact analysis",
        description="""
        Analyze impact of changes to a contract, model, or field.

        Performs reverse lineage traversal to find all resources that depend on
        the specified contract/model/field.

        **Query Parameters:**
        - `depth`: Maximum traversal depth (default: 10)
        - `model_name`: Optional model name for model-level impact
        - `field_name`: Optional field name for field-level impact
        - `include_fields`: Include field-level dependencies (default: true)
        - `format`: Response format (json, csv, dot, mermaid, paths) (default: json)

        **Response includes:**
        - Source contract/model/field information
        - Impact graph with all affected resources
        - Impact scores and severity levels
        - Summary statistics
        """,
        parameters=[
            OpenApiParameter(
                name="depth",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum traversal depth (default: 10)",
                required=False,
            ),
            OpenApiParameter(
                name="model_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Model name for model-level impact analysis",
                required=False,
            ),
            OpenApiParameter(
                name="field_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Field name for field-level impact analysis",
                required=False,
            ),
            OpenApiParameter(
                name="include_fields",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Include field-level dependencies (default: true)",
                required=False,
            ),
            OpenApiParameter(
                name="format",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Response format: json, csv, dot, mermaid, paths (default: json)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Impact analysis result"),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Impact Analysis"],
    )
    @action(detail=True, methods=["get"], url_path="impact-analysis")
    def get_impact_analysis(self, request, id=None):
        """Get impact analysis for a contract, model, or field."""
        # Get contract ID from URL kwargs
        contract_id = self.kwargs.get("pk") or self.kwargs.get("id")
        if not contract_id:
            from rest_framework.exceptions import NotFound

            raise NotFound("Contract ID not found in URL")

        # Get contract directly and verify tenant access
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            from rest_framework.exceptions import NotFound

            raise NotFound("Contract not found")

        # Verify tenant access (same logic as get_queryset)
        user = request.user
        if not (hasattr(user, "is_platform_admin") and user.is_platform_admin):
            # Get tenant from request or user
            tenant_id = None
            if hasattr(request, "tenant_id") and request.tenant_id:
                tenant_id = request.tenant_id
                if isinstance(tenant_id, str):
                    import uuid

                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        tenant_id = None
            elif hasattr(request, "tenant") and request.tenant:
                tenant_id = request.tenant.id
            elif hasattr(user, "tenant_id") and user.tenant_id:
                tenant_id = user.tenant_id
            elif hasattr(user, "tenant") and user.tenant:
                tenant_id = user.tenant.id

            # Verify contract belongs to user's tenant
            if tenant_id and contract.tenant_id:
                # Convert both to UUID for comparison
                import uuid

                contract_tenant_id = contract.tenant_id
                if isinstance(contract_tenant_id, str):
                    try:
                        contract_tenant_id = uuid.UUID(contract_tenant_id)
                    except (ValueError, TypeError):
                        contract_tenant_id = None
                if isinstance(tenant_id, str):
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        tenant_id = None

                if contract_tenant_id != tenant_id:
                    from rest_framework.exceptions import NotFound

                    raise NotFound("Contract not found")

        # Get parameters
        depth = int(request.query_params.get("depth", 10))
        model_name = request.query_params.get("model_name")
        field_name = request.query_params.get("field_name")
        include_fields = request.query_params.get("include_fields", "true").lower() == "true"
        format_type = request.query_params.get("format", "json").lower()

        # Get tenant ID for scoping
        tenant_id = str(contract.tenant_id) if contract.tenant else None

        # Perform impact analysis
        analyzer = ImpactAnalyzer(
            max_contract_depth=depth,
            max_model_depth=depth,
            max_field_depth=depth if include_fields else 0,
            include_fields=include_fields,
        )

        impact_result = analyzer.analyze_impact(
            contract_id=str(contract.id),
            model_name=model_name,
            field_name=field_name,
            tenant_id=tenant_id,
        )

        # Check for errors
        if "error" in impact_result:
            return Response(
                impact_result,
                status=(
                    status.HTTP_404_NOT_FOUND
                    if "not found" in impact_result.get("error", "").lower()
                    else status.HTTP_400_BAD_REQUEST
                ),
            )

        # Format response based on format parameter
        if format_type == "csv":
            csv_string = ImpactVisualizer.generate_impact_csv(impact_result)
            return Response(
                csv_string,
                content_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="impact_analysis_{contract.id}.csv"'
                },
            )
        elif format_type == "dot":
            dot_string = ImpactVisualizer.generate_impact_dot(impact_result)
            return Response(dot_string, content_type="text/plain")
        elif format_type == "mermaid":
            mermaid_string = ImpactVisualizer.generate_impact_mermaid(impact_result)
            return Response(mermaid_string, content_type="text/plain")
        elif format_type == "paths":
            paths = ImpactVisualizer.generate_impact_paths(impact_result)
            return Response(
                {
                    "source": impact_result.get("source", {}),
                    "paths": paths,
                    "total_paths": len(paths),
                }
            )
        else:  # Default to JSON
            # Generate JSON visualization
            json_graph = ImpactVisualizer.generate_impact_json(impact_result)
            # Include impact_graph for backward compatibility and test expectations
            json_graph["impact_graph"] = impact_result.get("impact_graph", {})
            return Response(json_graph)

    @extend_schema(
        summary="Export contract",
        description="""
        Export a contract in various formats (ODPS, ODCS, HubContract).

        **Format Options:**
        - `odps`: Export as ODPS (Open Data Product Standard) format
        - `odcs`: Export as ODCS (Open Data Contract Standard) format (original or generated)
        - `hubcontract`: Export as HubContract format (normalized internal format)

        **Output Format Options:**
        - `json`: Export as JSON (default)
        - `yaml`: Export as YAML

        **Behavior:**
        - For `odcs` format: Returns original_raw if available, otherwise generates from HubContract
        - For `odps` format: Generates ODPS document from HubContract
        - For `hubcontract` format: Returns hub_contract_json directly

        **Response:**
        - Returns contract content in requested format
        - Content-Type header set based on output_format
        """,
        parameters=[
            OpenApiParameter(
                name="format",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Export format: odps, odcs, or hubcontract (default: hubcontract)",
                required=False,
            ),
            OpenApiParameter(
                name="output_format",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Output format: json or yaml (default: json)",
                required=False,
            ),
            OpenApiParameter(
                name="version",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="ODPS version for export (e.g., 4.1). Only used when format=odps (default: 4.1)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Contract exported successfully"),
            400: OpenApiResponse(description="Invalid format or contract not available"),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts"],
    )
    @action(detail=True, methods=["get"], url_path="export")
    def export_contract(self, request, id=None):
        """
        Export a contract in various formats.

        GET /contracts/{id}/export/
        Query params:
        - format: odps|odcs|hubcontract (default: hubcontract)
        - output_format: yaml|json (default: json)

        Returns contract content in requested format.
        """
        # CRITICAL: Disable format suffix handling for this endpoint
        # This prevents DRF from trying to interpret ?format=hubcontract as a format suffix
        # Store original format_kwarg and set to None
        original_format_kwarg = getattr(self, "format_kwarg", None)
        self.format_kwarg = None

        try:
            # get_object() may raise Http404 - let it propagate to be handled by DRF's exception handler
            from django.http import Http404
            import os
            import logging
            logger = logging.getLogger(__name__)


            contract = self.get_object()

            # Get format parameter (default: hubcontract)
            # CRITICAL: Check query parameter FIRST before any format suffix handling
            # This ensures ?format=hubcontract works even if DRF tries to interpret it as a suffix
            if hasattr(request, "query_params"):
                format_type = request.query_params.get("format", "hubcontract").lower().strip()
            elif hasattr(request, "GET"):
                format_type = request.GET.get("format", "hubcontract").lower().strip()
            else:
                format_type = "hubcontract"

            if format_type not in ["odps", "odcs", "hubcontract"]:
                return Response(
                    {
                        "error": f"Invalid format: {format_type}. Must be one of: odps, odcs, hubcontract"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get output_format parameter (default: json)
            if hasattr(request, "query_params"):
                output_format = request.query_params.get("output_format", "json").lower().strip()
            elif hasattr(request, "GET"):
                output_format = request.GET.get("output_format", "json").lower().strip()
            else:
                output_format = "json"

            if output_format not in ["yaml", "json"]:
                return Response(
                    {"error": f"Invalid output_format: {output_format}. Must be one of: yaml, json"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get version parameter (only used for ODPS format, default: 4.1)
            if hasattr(request, "query_params"):
                odps_version = request.query_params.get("version", "4.1").strip()
            elif hasattr(request, "GET"):
                odps_version = request.GET.get("version", "4.1").strip()
            else:
                odps_version = "4.1"

            # Handle different format types
            if format_type == "hubcontract":
                # Export as HubContract format
                if not contract.hub_contract_json:
                    return Response(
                        {
                            "error": "Contract has no hub_contract_json. Cannot export as HubContract format."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                contract_data = contract.hub_contract_json

                # Format output
                if output_format == "yaml":
                    from django.http import HttpResponse
                    from hub.apps.contracts.odps_generator import format_odps_as_yaml

                    try:
                        # Use ODPS formatter for YAML (works for any dict)
                        output = format_odps_as_yaml(contract_data)
                        # Use Django's HttpResponse directly to avoid DRF's JSON serialization
                        return HttpResponse(output, content_type="application/x-yaml")
                    except Exception as e:
                        return Response(
                            {"error": f"Failed to format as YAML: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
                else:  # json
                    # Return as JSON (DRF will serialize it automatically)
                    return Response(contract_data, content_type="application/json")

            elif format_type == "odcs":
                # Export as ODCS format
                # Prefer original_raw if available, otherwise generate from HubContract
                if contract.original_raw and contract.original_spec_type == OriginalSpecType.ODCS:
                    # Return original ODCS format
                    original_format = contract.original_format.lower()

                    # Convert to requested output format if needed
                    if output_format == original_format:
                        # Same format, return as-is
                        if output_format == "yaml":
                            from django.http import HttpResponse
                            return HttpResponse(contract.original_raw, content_type="application/x-yaml")
                        else:
                            # For JSON, parse the original_raw and return as dict
                            # DRF will serialize it properly
                            import json
                            contract_data = json.loads(contract.original_raw)
                            return Response(contract_data, content_type="application/json")
                    else:
                        # Need to convert format
                        # parse_contract is now imported at the top of the file
                        try:
                            # Parse original contract
                            contract_data = parse_contract(contract.original_raw, contract.original_format)

                            # Format in requested output format
                            if output_format == "yaml":
                                from django.http import HttpResponse
                                from hub.apps.contracts.odps_generator import format_odps_as_yaml

                                output = format_odps_as_yaml(contract_data)
                                return HttpResponse(output, content_type="application/x-yaml")
                            else:  # json
                                # Return as JSON (DRF will serialize it automatically)
                                return Response(contract_data, content_type="application/json")
                        except Exception as e:
                            return Response(
                                {"error": f"Failed to convert ODCS format: {str(e)}"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            )
                else:
                    # No original_raw or not ODCS, try to generate from HubContract
                    if not contract.hub_contract_json:
                        return Response(
                            {
                                "error": "Contract has no original_raw or hub_contract_json. Cannot export as ODCS format."
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    # TODO: Implement HubContract → ODCS generation if needed
                    # For now, return error if original_raw is not available
                    return Response(
                        {
                            "error": "ODCS export requires original_raw. HubContract → ODCS generation not yet implemented."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            elif format_type == "odps":
                # Export as ODPS format
                if not contract.hub_contract_json:
                    return Response(
                        {"error": "Contract has no hub_contract_json. Cannot export as ODPS format."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Generate ODPS from HubContract
                from hub.apps.contracts.odps_generator import (
                    generate_odps_from_hubcontract,
                    format_odps_as_json,
                    format_odps_as_yaml,
                )

                # Get tenant_id for metrics (Task 6.6.1)
                tenant_id = _get_tenant_id_from_request(request)

                try:
                    # Start timing for export duration metric (Task 6.6.1)
                    export_start_time = time.time()

                    # Get original ODCS contract if available (for embedding in ODPS)
                    original_odcs_contract = None
                    if contract.original_raw and contract.original_spec_type == OriginalSpecType.ODCS:
                        try:
                            # parse_contract is now imported at the top of the file
                            original_odcs_contract = parse_contract(
                                contract.original_raw, contract.original_format
                            )
                        except Exception:
                            # If parsing fails, continue without original ODCS
                            pass

                    # Generate ODPS document
                    odps_doc = generate_odps_from_hubcontract(
                        hub_contract=contract.hub_contract_json,
                        target_version=odps_version,
                        original_odcs_contract=original_odcs_contract,
                        original_odcs_url=None,
                    )

                    # Format output
                    if output_format == "yaml":
                        output = format_odps_as_yaml(odps_doc)
                        content_type = "application/x-yaml"
                    else:  # json
                        output = format_odps_as_json(odps_doc)
                        content_type = "application/json"

                    # Calculate export duration and size for metrics (Task 6.6.1)
                    export_duration = time.time() - export_start_time
                    export_size_bytes = len(output.encode('utf-8'))
                    size_category = _categorize_export_size(export_size_bytes)

                    # Record metrics (Task 6.6.1, 6.6.4)
                    odps_export_duration_seconds.labels(
                        format=output_format,
                        size_category=size_category,
                        tenant_id=tenant_id
                    ).observe(export_duration)

                    odps_export_size_bytes.labels(
                        format=output_format,
                        tenant_id=tenant_id
                    ).observe(export_size_bytes)

                    # Record export success (Task 6.6.4)
                    odps_export_total.labels(
                        status="success",
                        format=output_format,
                        tenant_id=tenant_id
                    ).inc()

                    return Response(output, content_type=content_type)

                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to generate ODPS export: {str(e)}", exc_info=True)

                    # Record export failure (Task 6.6.4)
                    try:
                        odps_export_total.labels(
                            status="failure",
                            format=output_format if 'output_format' in locals() else "unknown",
                            tenant_id=tenant_id
                        ).inc()
                    except Exception:
                        pass  # Don't fail on metrics recording

                    return Response(
                        {"error": f"Failed to generate ODPS export: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

        except Http404:
            # Re-raise Http404 so it can be handled by DRF's exception handler
            # This ensures proper 404 responses instead of 500 errors
            raise
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Export endpoint error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Export failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            # Restore original format_kwarg
            if "original_format_kwarg" in locals():
                if original_format_kwarg is not None:
                    self.format_kwarg = original_format_kwarg
                else:
                    # If it was None originally, we might need to restore it differently
                    # But for now, just leave it as None since we disabled it
                    pass

    @extend_schema(
        summary="Download contract",
        description="""
        Download a contract as a file in various formats (ODPS, ODCS, HubContract).

        **Format Options:**
        - `odps`: Download as ODPS (Open Data Product Standard) format
        - `odcs`: Download as ODCS (Open Data Contract Standard) format (original or generated)
        - `hubcontract`: Download as HubContract format (normalized internal format)

        **Output Format Options:**
        - `yaml`: Download in YAML format
        - `json`: Download in JSON format

        **Query Parameters:**
        - `format` (optional): Specify the desired output format. Defaults to `hubcontract`.
        - `output_format` (optional): Specify the desired serialization format (yaml or json). Defaults to `json`.

        Returns a file download with appropriate Content-Disposition header.
        """,
        parameters=[
            OpenApiParameter(
                name="format",
                type=OpenApiTypes.STR,
                enum=["odps", "odcs", "hubcontract"],
                description="Desired contract format for download.",
                default="hubcontract",
            ),
            OpenApiParameter(
                name="output_format",
                type=OpenApiTypes.STR,
                enum=["yaml", "json"],
                description="Desired output serialization format.",
                default="json",
            ),
            OpenApiParameter(
                name="version",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="ODPS version for download (e.g., 4.1). Only used when format=odps (default: 4.1)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description="Contract file downloaded successfully.",
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Invalid format or output_format specified.",
            ),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT, description="Contract not found."
            ),
            500: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Internal server error during download.",
            ),
        },
    )
    @action(detail=True, methods=["get"], url_path="download")
    def download_contract(self, request, id=None):
        """
        Download a contract as a file in various formats.

        GET /contracts/{id}/download/
        Query params:
        - format: odps|odcs|hubcontract (default: hubcontract)
        - output_format: yaml|json (default: json)

        Returns contract file with Content-Disposition header for download.
        """
        # CRITICAL: Disable format suffix handling for this endpoint
        # This prevents DRF from trying to interpret ?format=hubcontract as a format suffix
        # Store original format_kwarg and set to None
        original_format_kwarg = getattr(self, "format_kwarg", None)
        self.format_kwarg = None

        try:
            # get_object() may raise Http404 - let it propagate to be handled by DRF's exception handler
            from django.http import Http404, HttpResponse
            contract = self.get_object()

            # Get format parameter (default: hubcontract)
            # CRITICAL: Check query parameter FIRST before any format suffix handling
            # This ensures ?format=hubcontract works even if DRF tries to interpret it as a suffix
            if hasattr(request, "query_params"):
                format_type = request.query_params.get("format", "hubcontract").lower().strip()
            elif hasattr(request, "GET"):
                format_type = request.GET.get("format", "hubcontract").lower().strip()
            else:
                format_type = "hubcontract"

            if format_type not in ["odps", "odcs", "hubcontract"]:
                return Response(
                    {"error": f"Invalid format: {format_type}. Must be one of: odps, odcs, hubcontract"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get output_format parameter (default: json)
            if hasattr(request, "query_params"):
                output_format = request.query_params.get("output_format", "json").lower().strip()
            elif hasattr(request, "GET"):
                output_format = request.GET.get("output_format", "json").lower().strip()
            else:
                output_format = "json"

            if output_format not in ["yaml", "json"]:
                return Response(
                    {"error": f"Invalid output_format: {output_format}. Must be one of: yaml, json"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get version parameter (only used for ODPS format, default: 4.1)
            if hasattr(request, "query_params"):
                odps_version = request.query_params.get("version", "4.1").strip()
            elif hasattr(request, "GET"):
                odps_version = request.GET.get("version", "4.1").strip()
            else:
                odps_version = "4.1"

            # Generate filename based on contract and format
            # Try to get name from hub_contract_json, otherwise use contract ID
            contract_name = f"contract-{contract.id}"
            if contract.hub_contract_json:
                # Try to get name from hub_contract_json
                if isinstance(contract.hub_contract_json, dict):
                    info = contract.hub_contract_json.get("info", {})
                    if isinstance(info, dict):
                        name = info.get("name")
                        if name:
                            contract_name = name
            # Sanitize filename (remove invalid characters)
            import re
            contract_name = re.sub(r'[^\w\s-]', '', contract_name).strip()
            contract_name = re.sub(r'[-\s]+', '-', contract_name)

            # Determine file extension
            if output_format == "yaml":
                extension = "yaml"
                content_type = "application/x-yaml"
            else:
                extension = "json"
                content_type = "application/json"

            filename = f"{contract_name}.{format_type}.{extension}"

            # Handle different format types (reuse export logic)
            if format_type == "hubcontract":
                # Download as HubContract format
                if not contract.hub_contract_json:
                    return Response(
                        {
                            "error": "Contract has no hub_contract_json. Cannot download as HubContract format."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                contract_data = contract.hub_contract_json

                # Format output
                if output_format == "yaml":
                    from hub.apps.contracts.odps_generator import format_odps_as_yaml

                    try:
                        # Use ODPS formatter for YAML (works for any dict)
                        output = format_odps_as_yaml(contract_data)
                        response = HttpResponse(output, content_type=content_type)
                        response["Content-Disposition"] = f'attachment; filename="{filename}"'
                        return response
                    except Exception as e:
                        return Response(
                            {"error": f"Failed to format as YAML: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
                else:  # json
                    # Return as JSON
                    import json
                    output = json.dumps(contract_data, indent=2, ensure_ascii=False)
                    response = HttpResponse(output, content_type=content_type)
                    response["Content-Disposition"] = f'attachment; filename="{filename}"'
                    return response

            elif format_type == "odcs":
                # Download as ODCS format
                if not contract.original_raw:
                    # For now, return error if original_raw is not available
                    return Response(
                        {
                            "error": "ODCS download requires original_raw. HubContract → ODCS generation not yet implemented."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                original_format = contract.original_format.lower()

                # Convert to requested output format if needed
                if output_format == original_format:
                    # Same format, return as-is
                    if output_format == "yaml":
                        response = HttpResponse(contract.original_raw, content_type=content_type)
                        response["Content-Disposition"] = f'attachment; filename="{filename}"'
                        return response
                    else:
                        # For JSON, parse the original_raw and return as dict
                        # Then serialize back to JSON for download
                        import json
                        contract_data = json.loads(contract.original_raw)
                        output = json.dumps(contract_data, indent=2, ensure_ascii=False)
                        response = HttpResponse(output, content_type=content_type)
                        response["Content-Disposition"] = f'attachment; filename="{filename}"'
                        return response
                else:
                    # Need to convert format
                    # parse_contract is now imported at the top of the file
                    try:
                        # Parse original contract
                        contract_data = parse_contract(contract.original_raw, contract.original_format)

                        # Format in requested output format
                        if output_format == "yaml":
                            from hub.apps.contracts.odps_generator import format_odps_as_yaml

                            output = format_odps_as_yaml(contract_data)
                            response = HttpResponse(output, content_type=content_type)
                            response["Content-Disposition"] = f'attachment; filename="{filename}"'
                            return response
                        else:  # json
                            # Return as JSON
                            import json
                            output = json.dumps(contract_data, indent=2, ensure_ascii=False)
                            response = HttpResponse(output, content_type=content_type)
                            response["Content-Disposition"] = f'attachment; filename="{filename}"'
                            return response
                    except Exception as e:
                        return Response(
                            {"error": f"Failed to convert ODCS format: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

            elif format_type == "odps":
                # Download as ODPS format
                if not contract.hub_contract_json:
                    return Response(
                        {"error": "Contract has no hub_contract_json. Cannot download as ODPS format."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Generate ODPS from HubContract
                from hub.apps.contracts.odps_generator import (
                    generate_odps_from_hubcontract,
                )

                # Get original ODCS contract if available (for embedding in ODPS)
                original_odcs_contract = None
                if contract.original_raw and contract.original_spec_type == OriginalSpecType.ODCS:
                    try:
                        # parse_contract is now imported at the top of the file
                        original_odcs_contract = parse_contract(
                            contract.original_raw, contract.original_format
                        )
                    except Exception:
                        # If parsing fails, continue without original ODCS
                        pass

                try:
                    odps_doc = generate_odps_from_hubcontract(
                        hub_contract=contract.hub_contract_json,
                        target_version=odps_version,
                        original_odcs_contract=original_odcs_contract,
                        original_odcs_url=None,
                    )

                    # Format in requested output format
                    if output_format == "yaml":
                        from hub.apps.contracts.odps_generator import format_odps_as_yaml

                        output = format_odps_as_yaml(odps_doc)
                        response = HttpResponse(output, content_type=content_type)
                        response["Content-Disposition"] = f'attachment; filename="{filename}"'
                        return response
                    else:  # json
                        from hub.apps.contracts.odps_generator import format_odps_as_json

                        output = format_odps_as_json(odps_doc)
                        response = HttpResponse(output, content_type=content_type)
                        response["Content-Disposition"] = f'attachment; filename="{filename}"'
                        return response
                except Exception as e:
                    return Response(
                        {"error": f"Failed to generate ODPS format: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

        except Http404:
            # Re-raise Http404 so it can be handled by DRF's exception handler
            # This ensures proper 404 responses instead of 500 errors
            raise
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Download endpoint error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Download failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            # Restore original format_kwarg
            if "original_format_kwarg" in locals():
                if original_format_kwarg is not None:
                    self.format_kwarg = original_format_kwarg
                else:
                    # If it was None originally, we might need to restore it differently
                    # But for now, just leave it as None since we disabled it
                    pass

    @extend_schema(
        summary="Generate ODPS document",
        description="""
        Generate ODPS (Open Data Product Standard) document from HubContract.

        This endpoint generates an ODPS document from the contract's HubContract representation,
        focusing on marketplace metadata. The generated ODPS document can be used for
        marketplace listings and product catalogs.

        **Request Body (optional):**
        - `target_version` (string, optional): Target ODPS version (default: "4.1")
        - `output_format` (string, optional): Output format - "json" or "yaml" (default: "json")
        - `embed_odcs` (boolean, optional): If true and contract is ODCS, embed original ODCS
          contract inline in product.contract.spec (default: true)

        **Behavior:**
        - Generates ODPS from HubContract (marketplace metadata)
        - If contract is ODCS and has original_raw, optionally embeds ODCS in product.contract.spec
        - Returns generated ODPS document in requested format

        **Response:**
        - Returns generated ODPS document as JSON or YAML
        - Content-Type header set based on output_format
        """,
        request=inline_serializer(
            name='GenerateODPSRequest',
            fields={
                'target_version': serializers.CharField(
                    required=False,
                    default='4.1',
                    help_text='Target ODPS version (default: 4.1)'
                ),
                'output_format': serializers.ChoiceField(
                    choices=['json', 'yaml'],
                    required=False,
                    default='json',
                    help_text='Output format: json or yaml (default: json)'
                ),
                'embed_odcs': serializers.BooleanField(
                    required=False,
                    default=True,
                    help_text='If true and contract is ODCS, embed original ODCS contract inline'
                ),
            }
        ),
        responses={
            200: inline_serializer(
                name='GenerateODPSResponse',
                fields={
                    'odps_document': serializers.DictField(
                        help_text='Generated ODPS document'
                    ),
                    'target_version': serializers.CharField(
                        help_text='ODPS version used for generation'
                    ),
                    'output_format': serializers.CharField(
                        help_text='Output format (json or yaml)'
                    ),
                }
            ),
            400: OpenApiResponse(description="Contract has no hub_contract_json or invalid parameters"),
            404: OpenApiResponse(description="Contract not found"),
            500: OpenApiResponse(description="ODPS generation failed"),
        },
        tags=["Contracts", "ODPS"],
    )
    @action(detail=True, methods=["post"], url_path="generate-odps")
    def generate_odps(self, request, id=None):
        """
        Generate ODPS document from HubContract.

        POST /api/v1/contracts/{id}/generate-odps/
        Body (optional): {
            "target_version": "4.1" (optional, default: "4.1"),
            "output_format": "json" (optional, default: "json", options: "json", "yaml"),
            "embed_odcs": true (optional, default: true)
        }

        Returns generated ODPS document.
        """
        self.check_auditor_permissions(request, "generate_odps")

        try:
            # get_object() may raise Http404 - let it propagate to be handled by DRF's exception handler
            from django.http import Http404
            contract = self.get_object()

            # Validate contract has hub_contract_json
            if not contract.hub_contract_json:
                return Response(
                    {
                        "error": "Contract has no hub_contract_json. Cannot generate ODPS document."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get request parameters (with defaults)
            # Support both query params and body data
            target_version = request.query_params.get("target_version") or request.data.get("target_version", "4.1")
            output_format = request.query_params.get("output_format") or request.data.get("output_format", "json")
            embed_odcs_str = request.query_params.get("embed_odcs") or request.data.get("embed_odcs", True)
            # Convert embed_odcs to boolean if it's a string
            if isinstance(embed_odcs_str, str):
                embed_odcs = embed_odcs_str.lower() in ("true", "1", "yes")
            else:
                embed_odcs = embed_odcs_str

            # Validate target_version
            if not isinstance(target_version, str) or not target_version.strip():
                return Response(
                    {"error": "target_version must be a non-empty string"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            target_version = target_version.strip()

            # Validate output_format
            if output_format not in ["json", "yaml"]:
                return Response(
                    {"error": f"output_format must be 'json' or 'yaml', got '{output_format}'"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Import ODPS generator functions
            from hub.apps.contracts.odps_generator import (
                generate_odps_from_hubcontract,
                format_odps_as_json,
                format_odps_as_yaml,
            )
            from hub.apps.contracts.odps_errors import ODPSExportError

            # Get original ODCS contract if available and embed_odcs is True
            original_odcs_contract = None
            if embed_odcs and contract.original_raw and contract.original_spec_type == OriginalSpecType.ODCS:
                try:
                    original_odcs_contract = parse_contract(
                        contract.original_raw, contract.original_format
                    )
                except Exception as e:
                    # If parsing fails, log warning but continue without original ODCS
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Failed to parse original ODCS contract for embedding: {str(e)}",
                        exc_info=True
                    )

            # Generate ODPS document from HubContract
            try:
                odps_doc = generate_odps_from_hubcontract(
                    hub_contract=contract.hub_contract_json,
                    target_version=target_version,
                    original_odcs_contract=original_odcs_contract,
                    original_odcs_url=None,  # Not using URL reference for now
                )
            except ODPSExportError as e:
                # ODPS generation failed with structured error
                return Response(
                    {
                        "error": e.user_message or str(e),
                        "error_code": e.error_code,
                        "context": e.context,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                # Unexpected error during generation
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to generate ODPS document: {str(e)}", exc_info=True)
                return Response(
                    {"error": f"Failed to generate ODPS document: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Format output based on output_format
            if output_format == "yaml":
                try:
                    odps_content = format_odps_as_yaml(odps_doc)
                    # Return as JSON response with YAML content in a field
                    # This allows consistent response structure
                    return Response(
                        {
                            "odps_document": odps_doc,  # Include dict for programmatic access
                            "odps_content": odps_content,  # Include YAML string for direct use
                            "target_version": target_version,
                            "output_format": output_format,
                        },
                        content_type="application/json",
                    )
                except ODPSExportError as e:
                    return Response(
                        {
                            "error": f"Failed to format ODPS as YAML: {e.user_message or str(e)}",
                            "error_code": e.error_code,
                            "context": e.context,
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            else:  # json
                # Return ODPS document as JSON
                return Response(
                    {
                        "odps_document": odps_doc,
                        "target_version": target_version,
                        "output_format": output_format,
                    },
                    content_type="application/json",
                )

        except Http404:
            # Re-raise Http404 so it can be handled by DRF's exception handler
            raise
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Generate ODPS endpoint error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Generate ODPS failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
