"""
Data Mesh Views

Django REST Framework views for Data Mesh domain management.
"""

import uuid

import structlog
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, Throttled
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from hub.apps.audit.utils import create_audit_event
from hub.apps.auth.permissions import HasAnyRole, HasAnyScope, HasRole, HasScope
from hub.apps.core.responses import handle_service_exception
from hub.apps.core.services.base import ConflictError, NotFoundError, ValidationError
from hub.apps.rate_limiting.service import check_rate_limit, get_rate_limit_headers
from hub.apps.tenants.request_tenant import get_request_tenant_id

from .business_rules import DataMeshBusinessRules
from .models import (
    ComplianceReport,
    DataMeshDomain,
    DomainStatus,
    MeshComplianceStatus,
    PolicyApplication,
    PolicyApplicationStatus,
)
from .serializers import (
    ApplyPolicySerializer,
    CheckComplianceSerializer,
    ComplianceReportSerializer,
    DomainAnalyticsSerializer,
    DomainCreateSerializer,
    DomainRelationshipSerializer,
    DomainSerializer,
    DomainTopologySerializer,
    DomainUpdateSerializer,
    MeshHealthSerializer,
    PolicyApplicationSerializer,
    TopologySerializer,
    TransferOwnershipSerializer,
)
from .services import DataMeshService

logger = structlog.get_logger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List data mesh domains",
        description="List all data mesh domains for the authenticated user's tenant with filtering and pagination.",
        tags=["Data Mesh"],
    ),
    retrieve=extend_schema(
        summary="Get domain details",
        description="Get detailed information about a specific data mesh domain.",
        tags=["Data Mesh"],
    ),
    create=extend_schema(
        summary="Create data mesh domain",
        description="Create a new data mesh domain.",
        tags=["Data Mesh"],
    ),
    update=extend_schema(
        summary="Update data mesh domain",
        description="Update an existing data mesh domain.",
        tags=["Data Mesh"],
    ),
    destroy=extend_schema(
        summary="Delete data mesh domain",
        description="Delete a data mesh domain.",
        tags=["Data Mesh"],
    ),
)
class DomainViewSet(viewsets.ModelViewSet):
    """
    ViewSet for data mesh domain management.

    Tenant-scoped: users can only see/manage domains in their tenant.
    Requires TENANT_ADMIN role for write operations.
    Requires mesh:write scope for write operations.
    """

    queryset = DataMeshDomain.objects.all()
    serializer_class = DomainSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def initial(self, request, *args, **kwargs):
        from hub.apps.tenants.feature_flag_gates import check_data_mesh_enabled
        from rest_framework.exceptions import PermissionDenied
        result = check_data_mesh_enabled(request)
        if isinstance(result, Response):
            raise PermissionDenied(detail=result.data)
        super().initial(request, *args, **kwargs)

    filter_backends = [OrderingFilter, SearchFilter]
    ordering_fields = ["name", "status", "created_at", "updated_at"]
    ordering = ["-created_at"]  # Default ordering
    search_fields = ["name", "description"]

    def get_permissions(self):
        """Return appropriate permissions based on action"""
        write_actions = [
            "create",
            "update",
            "partial_update",
            "destroy",
            "transfer_ownership",
            "ownership",
            "boundaries",
            "assets",
            "apply_policy",
            "remove_policy",
            "check_compliance",
        ]
        if self.action in write_actions:
            # Write operations require TENANT_ADMIN role and mesh:write scope
            return [
                permissions.IsAuthenticated(),
                HasAnyRole(["TENANT_ADMIN"]),
                HasScope("mesh:write"),
            ]
        # Read operations only require authentication
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """Filter queryset based on user permissions and query parameters"""
        user = self.request.user

        # Platform admins can see all domains
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = DataMeshDomain.objects.select_related("tenant", "owner").all()
        else:
            # Phase 16: use central helper (docs/TENANT_ISOLATION.md)
            tenant_id_str = get_request_tenant_id(self.request)
            if not tenant_id_str:
                return DataMeshDomain.objects.none()
            import uuid

            try:
                tenant_id = uuid.UUID(tenant_id_str)
            except (ValueError, TypeError):
                return DataMeshDomain.objects.none()
            queryset = DataMeshDomain.objects.select_related("tenant", "owner").filter(tenant_id=tenant_id)

        # Apply status filter if provided (only for list action, not for get_object)
        # get_object() should work regardless of status filter
        if self.action == "list":
            status_filter = self.request.query_params.get("status")
            if status_filter:
                # Validate status value
                valid_statuses = [choice[0] for choice in DomainStatus.choices]
                if status_filter.upper() in valid_statuses:
                    queryset = queryset.filter(status=status_filter.upper())
                else:
                    # Invalid status - return empty queryset
                    return DataMeshDomain.objects.none()

        # Apply owner filter if provided (only for list action)
        if self.action == "list":
            owner_filter = self.request.query_params.get("owner_id")
            if owner_filter:
                import uuid

                try:
                    owner_uuid = uuid.UUID(owner_filter)
                    queryset = queryset.filter(owner_id=owner_uuid)
                except (ValueError, TypeError):
                    # Invalid UUID - return empty queryset
                    return DataMeshDomain.objects.none()

        return queryset

    def get_object(self):
        """
        Override get_object to ensure tenant context is properly set.
        This is critical for custom actions that use get_object().
        Returns 400 for invalid UUID format instead of 404.
        """
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        if lookup_value is not None:
            try:
                uuid.UUID(str(lookup_value))
            except (ValueError, TypeError, AttributeError):
                raise DRFValidationError(
                    {"id": [f'"{lookup_value}" is not a valid UUID.']}
                )
        # Ensure tenant_id is set on request if not already set
        # This is important for custom actions where middleware might not have run
        if not hasattr(self.request, "tenant_id") or not self.request.tenant_id:
            tenant_id = self.get_tenant_id_from_request()
            if tenant_id:
                self.request.tenant_id = tenant_id
                # Also set tenant object if available
                if not hasattr(self.request, "tenant") or not self.request.tenant:
                    from hub.apps.tenants.models import Tenant

                    try:
                        self.request.tenant = Tenant.objects.get(id=tenant_id)
                    except Tenant.DoesNotExist:
                        pass

        # Call parent get_object which uses get_queryset()
        return super().get_object()

    def get_tenant_id_from_request(self):
        """Get tenant_id from request with proper fallback logic"""
        # Try request.tenant_id first (set by authentication/middleware)
        if hasattr(self.request, "tenant_id") and self.request.tenant_id:
            tenant_id = self.request.tenant_id
            if isinstance(tenant_id, str):
                import uuid

                try:
                    tenant_id = uuid.UUID(tenant_id)
                except (ValueError, TypeError):
                    tenant_id = None
            if tenant_id:
                return str(tenant_id)

        # Fallback to request.tenant object
        if hasattr(self.request, "tenant") and self.request.tenant:
            return str(self.request.tenant.id)

        # Fallback to user.tenant_id
        user = self.request.user
        if hasattr(user, "id") and user.id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                db_user = User.objects.only("tenant_id").get(id=user.id)
                if db_user.tenant_id:
                    return str(db_user.tenant_id)
            except User.DoesNotExist:
                pass

        # Last resort: get from user.tenant relationship
        if hasattr(user, "tenant") and user.tenant:
            return str(user.tenant.id)

        return None

    def get_user_id_from_request(self):
        """Get user_id from request"""
        user = self.request.user
        if hasattr(user, "id") and user.id:
            return str(user.id)
        return None

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a new data mesh domain"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        # Get tenant_id first (needed for cross-tenant validation)
        tenant_id = self.get_tenant_id_from_request()
        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Reject cross-tenant creation: tenant_id in body must match request tenant
        requested_tenant_id = request.data.get("tenant_id")
        if requested_tenant_id and str(requested_tenant_id).strip():
            try:
                req_uuid = uuid.UUID(str(requested_tenant_id))
                if str(req_uuid) != str(tenant_id):
                    raise DRFValidationError(
                        "Cannot create domain in another tenant"
                    )
            except (ValueError, TypeError):
                raise DRFValidationError("Invalid tenant_id format")

        # Validate request data
        serializer = DomainCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = self.get_user_id_from_request()

        # Initialize service
        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)

        # Create domain
        try:
            domain = service.create_domain(
                tenant_id=tenant_id,
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description"),
                owner_id=(
                    str(serializer.validated_data["owner_id"])
                    if serializer.validated_data.get("owner_id")
                    else None
                ),
                boundaries=serializer.validated_data.get("boundaries"),
                capabilities=serializer.validated_data.get("capabilities"),
                resource_quota=serializer.validated_data.get("resource_quota"),
                status=serializer.validated_data.get("status", DomainStatus.ACTIVE),
            )
        except ValidationError as e:
            return handle_service_exception(e)
        except ConflictError as e:
            return handle_service_exception(e)
        except DjangoValidationError as e:
            raise DRFValidationError(str(e))

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        response_serializer = DomainSerializer(domain)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        """List domains with pagination"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        queryset = self.filter_queryset(self.get_queryset())

        # Pagination
        page_size = request.query_params.get("page_size", 20)
        try:
            page_size = int(page_size)
            if page_size < 1 or page_size > 100:
                page_size = 20
        except (ValueError, TypeError):
            page_size = 20

        paginator = Paginator(queryset, page_size)
        page_number = request.query_params.get("page", 1)
        try:
            page_number = int(page_number)
            if page_number < 1:
                page_number = 1
        except (ValueError, TypeError):
            page_number = 1

        try:
            page = paginator.page(page_number)
        except (EmptyPage, PageNotAnInteger, ValueError) as e:
            logger.debug(
                "Pagination error, defaulting to page 1",
                extra={"page_number": page_number, "error_type": type(e).__name__},
            )
            page = paginator.page(1)

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        serializer = DomainSerializer(page.object_list, many=True)
        return Response(
            {
                "count": paginator.count,
                "next": page.next_page_number() if page.has_next() else None,
                "previous": page.previous_page_number() if page.has_previous() else None,
                "results": serializer.data,
            },
            headers=headers,
        )

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific domain"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        return Response(serializer.data, headers=headers)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update a domain (full update)"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        instance = self.get_object()

        # Validate request data
        serializer = DomainUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Initialize service
        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)

        # Update domain
        try:
            domain = service.update_domain(
                domain_id=str(instance.id),
                tenant_id=tenant_id,
                name=serializer.validated_data.get("name"),
                description=serializer.validated_data.get("description"),
                owner_id=(
                    str(serializer.validated_data["owner_id"])
                    if serializer.validated_data.get("owner_id") is not None
                    else None
                ),
                boundaries=serializer.validated_data.get("boundaries"),
                capabilities=serializer.validated_data.get("capabilities"),
                resource_quota=serializer.validated_data.get("resource_quota"),
                status=serializer.validated_data.get("status"),
            )
        except NotFoundError as e:
            return handle_service_exception(e)
        except ValidationError as e:
            return handle_service_exception(e)
        except ConflictError as e:
            return handle_service_exception(e)
        except DjangoValidationError as e:
            raise DRFValidationError(str(e))

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        response_serializer = DomainSerializer(domain)
        return Response(response_serializer.data, headers=headers)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """Delete a domain"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        instance = self.get_object()

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Initialize service
        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)

        # Delete domain
        try:
            service.delete_domain(
                domain_id=str(instance.id),
                tenant_id=tenant_id,
            )
        except NotFoundError as e:
            return handle_service_exception(e)
        except ValidationError as e:
            return Response(
                {
                    "error": e.message,
                    "code": getattr(e, "code", "VALIDATION_ERROR"),
                    "details": getattr(e, "details", {}),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        return Response(status=status.HTTP_204_NO_CONTENT, headers=headers)

    @extend_schema(
        summary="Transfer domain ownership",
        description="Transfer ownership of a data mesh domain to another user.",
        request=TransferOwnershipSerializer,
        responses={
            200: DomainSerializer,
            400: OpenApiResponse(description="Bad request"),
            404: OpenApiResponse(description="Domain not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["post"], url_path="transfer-ownership")
    @transaction.atomic
    def transfer_ownership(self, request, id=None):
        """Transfer ownership of a domain"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        instance = self.get_object()

        # Validate request data
        serializer = TransferOwnershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Get new_owner_id from validated data (can be None)
        new_owner_id = serializer.validated_data.get("new_owner_id")
        new_owner_id_str = str(new_owner_id) if new_owner_id is not None else None

        # Validate ownership transfer using business rules with framework features
        business_rules = DataMeshBusinessRules(tenant_id=tenant_id, user_id=user_id)
        validation_result = business_rules.execute(
            domain=instance,
            validation_type="ownership",
            new_owner_id=new_owner_id_str,
        )

        # Return 400 when validation fails (e.g. nonexistent user, cross-tenant transfer)
        if not validation_result.is_valid:
            from hub.apps.core.services.base import ValidationError

            return handle_service_exception(
                ValidationError("; ".join(validation_result.errors))
            )

        # Initialize service
        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)

        # Update domain owner
        try:
            domain = service.update_domain(
                domain_id=str(instance.id),
                tenant_id=tenant_id,
                owner_id=new_owner_id_str,
                _owner_id_provided=True,  # Flag to indicate owner_id was explicitly provided
            )
        except NotFoundError as e:
            return handle_service_exception(e)
        except ValidationError as e:
            raise DRFValidationError(str(e))
        except ConflictError as e:
            raise DRFValidationError(str(e))
        except DjangoValidationError as e:
            raise DRFValidationError(str(e))

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        response_serializer = DomainSerializer(domain)
        return Response(response_serializer.data, headers=headers)

    @extend_schema(
        summary="Update domain boundaries",
        description="Update boundaries (data products, governance rules) for a domain.",
        request=inline_serializer(
            name="BoundariesRequest",
            fields={
                "data_products": serializers.ListField(
                    child=serializers.DictField(), required=False, default=list
                ),
                "governance_rules": serializers.ListField(
                    child=serializers.DictField(), required=False, default=list
                ),
            },
        ),
        responses={
            200: DomainSerializer,
            400: OpenApiResponse(description="Bad request"),
            404: OpenApiResponse(description="Domain not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["patch"], url_path="boundaries")
    def boundaries(self, request, id=None):
        """Update domain boundaries"""
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            raise Throttled(headers=get_rate_limit_headers(request, rate_limit_results))

        instance = self.get_object()
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()
        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        data = request.data or {}
        new_boundaries = dict(instance.boundaries or {})
        if "data_products" in data:
            new_boundaries["data_products"] = data["data_products"]
        if "governance_rules" in data:
            new_boundaries["governance_rules"] = data["governance_rules"]

        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)
        try:
            domain = service.update_domain(
                domain_id=str(instance.id),
                tenant_id=tenant_id,
                boundaries=new_boundaries,
            )
        except NotFoundError as e:
            return handle_service_exception(e)
        except ValidationError as e:
            return handle_service_exception(e)

        headers = get_rate_limit_headers(request, check_rate_limit(request)[1])
        return Response(
            DomainSerializer(domain).data, headers=headers, status=status.HTTP_200_OK
        )

    @extend_schema(
        summary="Assign domain ownership",
        description="Assign or update domain owner (PATCH alias for transfer-ownership).",
        request=inline_serializer(
            name="OwnershipRequest",
            fields={
                "owner_id": serializers.UUIDField(
                    required=True, help_text="Owner user ID"
                ),
            },
        ),
        responses={
            200: DomainSerializer,
            400: OpenApiResponse(description="Bad request"),
            404: OpenApiResponse(description="Domain not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["patch"], url_path="ownership")
    @transaction.atomic
    def ownership(self, request, id=None):
        """Assign domain ownership (PATCH with owner_id)"""
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            raise Throttled(headers=get_rate_limit_headers(request, rate_limit_results))

        instance = self.get_object()
        owner_id = request.data.get("owner_id")
        if owner_id is None:
            raise DRFValidationError("owner_id is required")

        # Reuse transfer_ownership logic via service
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()
        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        business_rules = DataMeshBusinessRules(tenant_id=tenant_id, user_id=user_id)
        validation_result = business_rules.execute(
            domain=instance,
            validation_type="ownership",
            new_owner_id=str(owner_id),
        )
        if not validation_result.is_valid:
            return handle_service_exception(
                ValidationError("; ".join(validation_result.errors))
            )

        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)
        try:
            domain = service.update_domain(
                domain_id=str(instance.id),
                tenant_id=tenant_id,
                owner_id=str(owner_id),
                _owner_id_provided=True,
            )
        except NotFoundError as e:
            return handle_service_exception(e)
        except ValidationError as e:
            raise DRFValidationError(str(e))
        except ConflictError as e:
            raise DRFValidationError(str(e))

        headers = get_rate_limit_headers(request, check_rate_limit(request)[1])
        return Response(
            DomainSerializer(domain).data, headers=headers, status=status.HTTP_200_OK
        )

    @extend_schema(
        summary="Get domain health",
        description="Get health metrics for a specific domain.",
        responses={
            200: MeshHealthSerializer,
            404: OpenApiResponse(description="Domain not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["get"], url_path="health")
    def health(self, request, id=None):
        """Get per-domain health metrics"""
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            raise Throttled(headers=get_rate_limit_headers(request, rate_limit_results))

        instance = self.get_object()
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()
        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)
        topology = service.get_topology(
            tenant_id=tenant_id,
            include_health_metrics=True,
        )
        nodes = topology.get("nodes", [])
        domain_node = next(
            (n for n in nodes if str(n.get("id")) == str(instance.id)), None
        )
        if not domain_node or not domain_node.get("health_metrics"):
            health_data = {
                "overall_health_score": 0,
                "total_domains": 1,
                "active_domains": 1 if instance.status == DomainStatus.ACTIVE else 0,
                "compliant_domains": 0,
                "non_compliant_domains": 0,
                "domains_with_violations": 0,
                "domain_health": [
                    {
                        "domain_id": str(instance.id),
                        "domain_name": instance.name,
                        "health_score": 0,
                        "compliance_status": None,
                        "violation_count": 0,
                        "is_active": instance.status == DomainStatus.ACTIVE,
                    }
                ],
            }
        else:
            hm = domain_node["health_metrics"]
            health_data = {
                "overall_health_score": hm.get("health_score", 0),
                "total_domains": 1,
                "active_domains": 1 if hm.get("is_active") else 0,
                "compliant_domains": 1 if hm.get("compliance_status") == MeshComplianceStatus.COMPLIANT else 0,
                "non_compliant_domains": 1 if hm.get("compliance_status") == MeshComplianceStatus.NON_COMPLIANT else 0,
                "domains_with_violations": 1 if (hm.get("violation_count") or 0) > 0 else 0,
                "domain_health": [
                    {
                        "domain_id": str(instance.id),
                        "domain_name": instance.name,
                        "health_score": hm.get("health_score", 0),
                        "compliance_status": hm.get("compliance_status"),
                        "violation_count": hm.get("violation_count", 0),
                        "is_active": hm.get("is_active", False),
                    }
                ],
            }

        headers = get_rate_limit_headers(request, check_rate_limit(request)[1])
        serializer = MeshHealthSerializer(health_data)
        return Response(serializer.data, headers=headers, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Add asset to domain",
        description="Associate an asset with a domain (set asset.domain).",
        request=inline_serializer(
            name="DomainAssetRequest",
            fields={"asset_id": serializers.UUIDField(required=True)},
        ),
        responses={
            201: OpenApiResponse(description="Asset associated"),
            400: OpenApiResponse(description="Bad request"),
            404: OpenApiResponse(description="Domain or asset not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["post"], url_path="assets")
    def assets(self, request, id=None):
        """Add asset to domain"""
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            raise Throttled(headers=get_rate_limit_headers(request, rate_limit_results))

        instance = self.get_object()
        asset_id = request.data.get("asset_id")
        if not asset_id:
            raise DRFValidationError("asset_id is required")

        tenant_id = self.get_tenant_id_from_request()
        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        from hub.apps.assets.models import Asset

        try:
            asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
        except Asset.DoesNotExist:
            return Response(
                {"error": "Asset not found"}, status=status.HTTP_404_NOT_FOUND
            )

        asset.domain = instance.name
        asset.save(update_fields=["domain", "updated_at"])

        headers = get_rate_limit_headers(request, check_rate_limit(request)[1])
        return Response(
            {"asset_id": str(asset_id), "domain_id": str(instance.id)},
            headers=headers,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Get domain infrastructure",
        description="Get infrastructure/capabilities for a domain.",
        responses={
            200: OpenApiResponse(description="Domain infrastructure"),
            404: OpenApiResponse(description="Domain not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["get", "post"], url_path="infrastructure")
    def infrastructure(self, request, id=None):
        """Get or configure domain infrastructure (capabilities)"""
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            raise Throttled(headers=get_rate_limit_headers(request, rate_limit_results))

        instance = self.get_object()
        if request.method == "POST":
            caps = instance.capabilities or {}
            caps.update(request.data or {})
            instance.capabilities = caps
            instance.save(update_fields=["capabilities", "updated_at"])
        infra = {
            "domain_id": str(instance.id),
            "domain_name": instance.name,
            "capabilities": instance.capabilities or {},
            "resource_quota": instance.resource_quota or {},
            "resource_usage": instance.resource_usage or {},
        }

        headers = get_rate_limit_headers(request, check_rate_limit(request)[1])
        return Response(infra, headers=headers, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get domain self-serve configuration",
        description="Get self-serve capabilities and configuration for a domain.",
        responses={
            200: OpenApiResponse(description="Self-serve config"),
            404: OpenApiResponse(description="Domain not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["get", "post"], url_path="self-serve")
    def self_serve(self, request, id=None):
        """Get or configure domain self-serve (capabilities, quotas)."""
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            raise Throttled(headers=get_rate_limit_headers(request, rate_limit_results))

        instance = self.get_object()
        if request.method == "POST":
            enabled = request.data.get("enabled", True)
            caps = instance.capabilities or {}
            caps["self_serve"] = enabled
            instance.capabilities = caps
            instance.save(update_fields=["capabilities", "updated_at"])
        data = {
            "domain_id": str(instance.id),
            "domain_name": instance.name,
            "self_serve_enabled": True,
            "capabilities": instance.capabilities or {},
            "resource_quota": instance.resource_quota or {},
        }

        headers = get_rate_limit_headers(request, check_rate_limit(request)[1])
        return Response(data, headers=headers, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get", "post"], url_path="quotas")
    def quotas(self, request, id=None):
        """Get or configure domain resource quotas."""
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            raise Throttled(headers=get_rate_limit_headers(request, rate_limit_results))
        instance = self.get_object()
        if request.method == "POST":
            quota = dict(instance.resource_quota or {})
            quota.update(request.data or {})
            instance.resource_quota = quota
            instance.save(update_fields=["resource_quota", "updated_at"])
        return Response({
            "domain_id": str(instance.id),
            "resource_quota": instance.resource_quota or {},
        }, headers=get_rate_limit_headers(request, check_rate_limit(request)[1]), status=200)

    @action(detail=True, methods=["get", "post"], url_path="governance")
    def governance(self, request, id=None):
        """Get or configure domain governance."""
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            raise Throttled(headers=get_rate_limit_headers(request, rate_limit_results))
        instance = self.get_object()
        if request.method == "POST":
            boundaries = dict(instance.boundaries or {})
            boundaries.setdefault("governance_rules", [])
            instance.boundaries = boundaries
            instance.save(update_fields=["boundaries", "updated_at"])
        return Response({
            "domain_id": str(instance.id),
            "boundaries": instance.boundaries or {},
        }, headers=get_rate_limit_headers(request, check_rate_limit(request)[1]), status=200)

    @action(detail=True, methods=["post"], url_path="deploy")
    def deploy(self, request, id=None):
        """Deploy domain (placeholder)."""
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            raise Throttled(headers=get_rate_limit_headers(request, rate_limit_results))
        instance = self.get_object()
        return Response({
            "domain_id": str(instance.id),
            "status": "deployed",
        }, headers=get_rate_limit_headers(request, check_rate_limit(request)[1]), status=200)

    @action(detail=True, methods=["get"], url_path="monitoring")
    def monitoring(self, request, id=None):
        """Get domain monitoring metrics."""
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            raise Throttled(headers=get_rate_limit_headers(request, rate_limit_results))
        instance = self.get_object()
        return Response({
            "domain_id": str(instance.id),
            "metrics": {},
            "health": "ok",
        }, headers=get_rate_limit_headers(request, check_rate_limit(request)[1]), status=200)

    @extend_schema(
        summary="Get domain analytics",
        description="Get analytics and statistics for a data mesh domain.",
        responses={
            200: DomainAnalyticsSerializer,
            404: OpenApiResponse(description="Domain not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["get"], url_path="analytics")
    def analytics(self, request, id=None):
        """Get analytics for a domain"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        instance = self.get_object()

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Initialize service
        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)

        # Get policy statistics
        policy_stats = PolicyApplication.objects.filter(domain=instance).aggregate(
            total_policies=Count("id"),
            applied_policies=Count("id", filter=Q(status=PolicyApplicationStatus.APPLIED)),
            pending_policies=Count("id", filter=Q(status=PolicyApplicationStatus.PENDING)),
        )

        # Get compliance statistics
        compliance_report = (
            ComplianceReport.objects.filter(domain=instance, asset=None)  # Domain-level report
            .order_by("-generated_at")
            .first()
        )

        # Calculate resource usage percentages
        resource_usage_percentages = {}
        for key, quota in instance.resource_quota.items():
            usage = instance.resource_usage.get(f"{key}_used", 0)
            if quota and quota > 0:
                percentage = (usage / quota) * 100
                resource_usage_percentages[key] = min(percentage, 100.0)
            else:
                resource_usage_percentages[key] = 0.0

        # Calculate boundary and capability counts
        boundaries_count = len(instance.boundaries) if instance.boundaries else 0
        capabilities_count = len(instance.capabilities) if instance.capabilities else 0

        # Build analytics response
        analytics_data = {
            "domain_id": instance.id,
            "domain_name": instance.name,
            "status": instance.status,
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
            "resource_usage": instance.resource_usage,
            "resource_quota": instance.resource_quota,
            "resource_usage_percentages": resource_usage_percentages,
            "total_policies": policy_stats["total_policies"] or 0,
            "applied_policies": policy_stats["applied_policies"] or 0,
            "pending_policies": policy_stats["pending_policies"] or 0,
            "compliance_status": compliance_report.compliance_status if compliance_report else None,
            "violation_count": compliance_report.get_violation_count() if compliance_report else 0,
            "last_compliance_check": compliance_report.generated_at if compliance_report else None,
            "boundaries_count": boundaries_count,
            "capabilities_count": capabilities_count,
            "health_score": None,  # TODO: Calculate health score from topology business rules
            "health_status": None,  # TODO: Calculate health status from topology business rules
        }

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        serializer = DomainAnalyticsSerializer(analytics_data)
        return Response(serializer.data, headers=headers)

    @extend_schema(
        summary="Apply policy to domain",
        description="Apply an access policy to a data mesh domain with optional overrides.",
        request=ApplyPolicySerializer,
        responses={
            201: PolicyApplicationSerializer,
            400: OpenApiResponse(description="Bad Request"),
            404: OpenApiResponse(description="Domain or Policy not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["post"], url_path="policies/apply")
    @transaction.atomic
    def apply_policy(self, request, id=None):
        """Apply a policy to a domain"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        instance = self.get_object()

        # Validate request data
        serializer = ApplyPolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Initialize service
        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)

        # Apply policy
        try:
            policy_application = service.apply_policy(
                domain_id=str(instance.id),
                policy_id=str(serializer.validated_data["policy_id"]),
                overrides=serializer.validated_data.get("overrides"),
                tenant_id=tenant_id,
            )
        except NotFoundError as e:
            return handle_service_exception(e)
        except ValidationError as e:
            raise DRFValidationError(str(e))
        except DjangoValidationError as e:
            raise DRFValidationError(str(e))

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        response_serializer = PolicyApplicationSerializer(policy_application)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @extend_schema(
        summary="List applied policies",
        description="List all policies applied to a data mesh domain with filtering and pagination.",
        responses={
            200: PolicyApplicationSerializer(many=True),
            404: OpenApiResponse(description="Domain not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["get"], url_path="policies")
    def list_policies(self, request, id=None):
        """List policies applied to a domain"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        instance = self.get_object()

        # Get queryset filtered by domain and tenant
        queryset = (
            PolicyApplication.objects.filter(
                domain=instance, domain__tenant_id=self.get_tenant_id_from_request()
            )
            .select_related("policy", "applied_by", "domain")
            .order_by("-applied_at", "-created_at")
        )

        # Apply status filter if provided
        status_filter = request.query_params.get("status")
        if status_filter:
            try:
                queryset = queryset.filter(status=status_filter)
            except (ValueError, TypeError):
                queryset = PolicyApplication.objects.none()

        # Pagination
        page_size = request.query_params.get("page_size", 20)
        try:
            page_size = int(page_size)
            if page_size < 1 or page_size > 100:
                page_size = 20
        except (ValueError, TypeError):
            page_size = 20

        paginator = Paginator(queryset, page_size)
        page_number = request.query_params.get("page", 1)
        try:
            page_number = int(page_number)
            if page_number < 1:
                page_number = 1
        except (ValueError, TypeError):
            page_number = 1

        try:
            page = paginator.page(page_number)
        except (EmptyPage, PageNotAnInteger, ValueError) as e:
            logger.debug(
                "Pagination error, defaulting to page 1",
                extra={"page_number": page_number, "error_type": type(e).__name__},
            )
            page = paginator.page(1)

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        serializer = PolicyApplicationSerializer(page.object_list, many=True)
        return Response(
            {
                "count": paginator.count,
                "page": page_number,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
                "results": serializer.data,
            },
            headers=headers,
        )

    @extend_schema(
        summary="Remove policy from domain",
        description="Remove (revoke) a policy application from a data mesh domain.",
        responses={
            200: PolicyApplicationSerializer,
            404: OpenApiResponse(description="Domain or Policy application not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["delete"], url_path="policies/(?P<policy_id>[^/.]+)")
    @transaction.atomic
    def remove_policy(self, request, id=None, policy_id=None):
        """Remove a policy from a domain"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        instance = self.get_object()

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Find policy application by policy_id and domain
        try:
            policy_application = PolicyApplication.objects.get(
                domain=instance, policy_id=policy_id, domain__tenant_id=tenant_id
            )
        except PolicyApplication.DoesNotExist:
            raise NotFound(
                f"Policy application for policy {policy_id} not found on domain {instance.id}"
            )

        # Initialize service
        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)

        # Revoke policy
        try:
            revoked_application = service.revoke_policy(
                policy_application_id=str(policy_application.id),
                reason=request.data.get("reason"),
                tenant_id=tenant_id,
            )
        except NotFoundError as e:
            return handle_service_exception(e)
        except ValidationError as e:
            raise DRFValidationError(str(e))
        except DjangoValidationError as e:
            raise DRFValidationError(str(e))

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        response_serializer = PolicyApplicationSerializer(revoked_application)
        return Response(response_serializer.data, headers=headers)

    @extend_schema(
        summary="Check domain compliance",
        description="Check compliance status for a data mesh domain and generate a compliance report.",
        request=CheckComplianceSerializer,
        responses={
            200: ComplianceReportSerializer,
            404: OpenApiResponse(description="Domain not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["post"], url_path="compliance/check")
    @transaction.atomic
    def check_compliance(self, request, id=None):
        """Check compliance for a domain"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        instance = self.get_object()

        # Validate request data
        serializer = CheckComplianceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Initialize service
        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)

        # Check compliance
        try:
            compliance_report = service.check_compliance(
                domain_id=str(instance.id),
                tenant_id=tenant_id,
                asset_id=(
                    str(serializer.validated_data["asset_id"])
                    if serializer.validated_data.get("asset_id")
                    else None
                ),
            )
        except NotFoundError as e:
            return handle_service_exception(e)
        except ValidationError as e:
            raise DRFValidationError(str(e))
        except DjangoValidationError as e:
            raise DRFValidationError(str(e))

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        response_serializer = ComplianceReportSerializer(compliance_report)
        return Response(response_serializer.data, headers=headers)

    @extend_schema(
        summary="List compliance reports",
        description="List all compliance reports for a data mesh domain with filtering and pagination.",
        responses={
            200: ComplianceReportSerializer(many=True),
            404: OpenApiResponse(description="Domain not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["get"], url_path="compliance/reports")
    def list_compliance_reports(self, request, id=None):
        """List compliance reports for a domain"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        instance = self.get_object()

        # Get queryset filtered by domain and tenant
        queryset = (
            ComplianceReport.objects.filter(
                domain=instance, domain__tenant_id=self.get_tenant_id_from_request()
            )
            .select_related("domain", "asset")
            .order_by("-generated_at")
        )

        # Apply status filter if provided
        status_filter = request.query_params.get("status")
        if status_filter:
            try:
                queryset = queryset.filter(compliance_status=status_filter)
            except (ValueError, TypeError):
                queryset = ComplianceReport.objects.none()

        # Apply asset filter if provided
        asset_filter = request.query_params.get("asset_id")
        if asset_filter:
            try:
                queryset = queryset.filter(asset_id=asset_filter)
            except (ValueError, TypeError):
                queryset = ComplianceReport.objects.none()

        # Pagination
        page_size = request.query_params.get("page_size", 20)
        try:
            page_size = int(page_size)
            if page_size < 1 or page_size > 100:
                page_size = 20
        except (ValueError, TypeError):
            page_size = 20

        paginator = Paginator(queryset, page_size)
        page_number = request.query_params.get("page", 1)
        try:
            page_number = int(page_number)
            if page_number < 1:
                page_number = 1
        except (ValueError, TypeError):
            page_number = 1

        try:
            page = paginator.page(page_number)
        except (EmptyPage, PageNotAnInteger, ValueError) as e:
            logger.debug(
                "Pagination error, defaulting to page 1",
                extra={"page_number": page_number, "error_type": type(e).__name__},
            )
            page = paginator.page(1)

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        serializer = ComplianceReportSerializer(page.object_list, many=True)
        return Response(
            {
                "count": paginator.count,
                "page": page_number,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
                "results": serializer.data,
            },
            headers=headers,
        )

    @extend_schema(
        summary="Get compliance report",
        description="Get detailed information about a specific compliance report for a data mesh domain.",
        responses={
            200: ComplianceReportSerializer,
            404: OpenApiResponse(description="Domain or Compliance report not found"),
        },
        tags=["Data Mesh"],
    )
    @action(detail=True, methods=["get"], url_path="compliance/reports/(?P<report_id>[^/.]+)")
    def get_compliance_report(self, request, id=None, report_id=None):
        """Get a specific compliance report for a domain"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        instance = self.get_object()

        # Get tenant_id
        tenant_id = self.get_tenant_id_from_request()
        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Get compliance report
        try:
            compliance_report = ComplianceReport.objects.select_related("domain", "asset").get(
                id=report_id, domain=instance, domain__tenant_id=tenant_id
            )
        except ComplianceReport.DoesNotExist:
            raise NotFound(f"Compliance report {report_id} not found for domain {instance.id}")

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        serializer = ComplianceReportSerializer(compliance_report)
        return Response(serializer.data, headers=headers)


@extend_schema_view(
    list=extend_schema(
        summary="Get mesh topology",
        description="Get complete data mesh topology including all domains, relationships, and health metrics.",
        responses={
            200: TopologySerializer,
        },
        tags=["Data Mesh Topology"],
    ),
)
class TopologyViewSet(viewsets.ViewSet):
    """
    ViewSet for data mesh topology endpoints.

    Provides endpoints for:
    - Full mesh topology (all domains and relationships)
    - Domain-specific topology
    - Mesh health metrics
    - Domain relationships
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        """Return appropriate permissions based on action"""
        # All topology endpoints are read-only, only require authentication
        return [permissions.IsAuthenticated()]

    def get_tenant_id_from_request(self):
        """Get tenant_id from request with proper fallback logic"""
        # Try request.tenant_id first (set by authentication/middleware)
        if hasattr(self.request, "tenant_id") and self.request.tenant_id:
            tenant_id = self.request.tenant_id
            if isinstance(tenant_id, str):
                import uuid

                try:
                    tenant_id = uuid.UUID(tenant_id)
                except (ValueError, TypeError):
                    tenant_id = None
            if tenant_id:
                return str(tenant_id)

        # Fallback to request.tenant object
        if hasattr(self.request, "tenant") and self.request.tenant:
            return str(self.request.tenant.id)

        # Fallback to user.tenant_id
        user = self.request.user
        if hasattr(user, "id") and user.id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                db_user = User.objects.only("tenant_id").get(id=user.id)
                if db_user.tenant_id:
                    return str(db_user.tenant_id)
            except User.DoesNotExist:
                pass

        # Last resort: get from user.tenant relationship
        if hasattr(user, "tenant") and user.tenant:
            return str(user.tenant.id)

        return None

    def get_user_id_from_request(self):
        """Get user_id from request"""
        user = self.request.user
        if hasattr(user, "id") and user.id:
            return str(user.id)
        return None

    @extend_schema(
        summary="Get mesh topology",
        description="Get complete data mesh topology for the authenticated user's tenant.",
        parameters=[
            {
                "name": "include_health_metrics",
                "in": "query",
                "description": "Include health metrics in response (default: true)",
                "required": False,
                "schema": {"type": "boolean", "default": True},
            },
        ],
        responses={
            200: TopologySerializer,
            400: OpenApiResponse(description="Bad request"),
        },
        tags=["Data Mesh Topology"],
    )
    def list(self, request):
        """Get complete mesh topology"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Get query parameters
        include_health_metrics = request.query_params.get("include_health_metrics", "true")
        include_health_metrics = include_health_metrics.lower() in ("true", "1", "yes")

        # Initialize service
        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)

        # Get topology
        try:
            topology = service.get_topology(
                tenant_id=tenant_id,
                include_health_metrics=include_health_metrics,
            )
        except ValidationError as e:
            raise DRFValidationError(str(e))

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        serializer = TopologySerializer(topology)
        return Response(serializer.data, headers=headers)

    @extend_schema(
        summary="Get domain topology",
        description="Get topology view for a specific domain including its relationships and health metrics.",
        responses={
            200: DomainTopologySerializer,
            404: OpenApiResponse(description="Domain not found"),
        },
        tags=["Data Mesh Topology"],
    )
    def retrieve(self, request, pk=None):
        """Get topology for a specific domain"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Get domain
        try:
            domain = DataMeshDomain.objects.get(id=pk, tenant_id=tenant_id)
        except DataMeshDomain.DoesNotExist:
            raise NotFound("Domain not found")

        # Initialize service and get full topology
        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)
        topology = service.get_topology(
            tenant_id=tenant_id,
            include_health_metrics=True,
        )

        # Find domain node
        domain_node = None
        for node in topology["nodes"]:
            if node["id"] == str(domain.id):
                domain_node = node
                break

        if not domain_node:
            raise NotFound("Domain not found in topology")

        # Find relationships for this domain
        domain_relationships = [
            edge
            for edge in topology["edges"]
            if edge["source"] == str(domain.id) or edge["target"] == str(domain.id)
        ]

        # Build response
        response_data = {
            "domain": domain_node,
            "relationships": domain_relationships,
            "health_metrics": domain_node.get("health_metrics"),
        }

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        serializer = DomainTopologySerializer(response_data)
        return Response(serializer.data, headers=headers)

    @extend_schema(
        summary="Get mesh health",
        description="Get overall mesh health metrics and per-domain health status.",
        responses={
            200: MeshHealthSerializer,
        },
        tags=["Data Mesh Topology"],
    )
    @action(detail=False, methods=["get"], url_path="health")
    def health(self, request):
        """Get mesh health metrics"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Initialize service and get topology with health metrics
        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)
        topology = service.get_topology(
            tenant_id=tenant_id,
            include_health_metrics=True,
        )

        # Calculate health metrics
        nodes = topology["nodes"]
        total_domains = len(nodes)
        active_domains = sum(1 for n in nodes if n.get("status") == DomainStatus.ACTIVE)

        compliant_domains = 0
        non_compliant_domains = 0
        domains_with_violations = 0
        domain_health = []
        total_health_score = 0

        for node in nodes:
            health_metrics = node.get("health_metrics", {})
            if health_metrics:
                compliance_status = health_metrics.get("compliance_status")
                if compliance_status == MeshComplianceStatus.COMPLIANT:
                    compliant_domains += 1
                elif compliance_status == MeshComplianceStatus.NON_COMPLIANT:
                    non_compliant_domains += 1

                violation_count = health_metrics.get("violation_count", 0)
                if violation_count > 0:
                    domains_with_violations += 1

                health_score = health_metrics.get("health_score", 0)
                total_health_score += health_score

                domain_health.append(
                    {
                        "domain_id": node["id"],
                        "domain_name": node["name"],
                        "health_score": health_score,
                        "compliance_status": compliance_status,
                        "violation_count": violation_count,
                        "is_active": health_metrics.get("is_active", False),
                    }
                )

        # Calculate overall health score
        overall_health_score = total_health_score / total_domains if total_domains > 0 else None

        # Build response
        health_data = {
            "overall_health_score": overall_health_score,
            "total_domains": total_domains,
            "active_domains": active_domains,
            "compliant_domains": compliant_domains,
            "non_compliant_domains": non_compliant_domains,
            "domains_with_violations": domains_with_violations,
            "domain_health": domain_health,
        }

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        serializer = MeshHealthSerializer(health_data)
        return Response(serializer.data, headers=headers)

    @extend_schema(
        summary="Get domain relationships",
        description="Get all domain relationships in the mesh.",
        responses={
            200: DomainRelationshipSerializer,
        },
        tags=["Data Mesh Topology"],
    )
    @action(detail=False, methods=["get"], url_path="relationships")
    def relationships(self, request):
        """Get all domain relationships"""
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            raise Throttled(headers=headers)

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Initialize service and get topology
        service = DataMeshService(tenant_id=tenant_id, user_id=user_id)
        topology = service.get_topology(
            tenant_id=tenant_id,
            include_health_metrics=False,  # Not needed for relationships
        )

        # Get relationships
        relationships = topology["edges"]

        # Count relationships by type
        relationship_types = {}
        for rel in relationships:
            rel_type = rel.get("type", "UNKNOWN")
            relationship_types[rel_type] = relationship_types.get(rel_type, 0) + 1

        # Build response
        response_data = {
            "relationships": relationships,
            "total_count": len(relationships),
            "relationship_types": relationship_types,
        }

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        serializer = DomainRelationshipSerializer(response_data)
        return Response(serializer.data, headers=headers)


class MeshGovernanceViewSet(viewsets.ViewSet):
    """ViewSet for mesh-level governance (tenant-scoped)."""

    permission_classes = [permissions.IsAuthenticated]

    def get_tenant_id_from_request(self):
        return get_request_tenant_id(self.request)

    def list(self, request):
        """
        Get mesh governance summary.

        GET /api/v1/mesh/governance/
        """
        tenant_id = self.get_tenant_id_from_request()
        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        domain_count = DataMeshDomain.objects.filter(tenant_id=tenant_id).count()
        policy_count = PolicyApplication.objects.filter(
            domain__tenant_id=tenant_id,
            status=PolicyApplicationStatus.APPLIED,
        ).count()

        return Response({
            "tenant_id": tenant_id,
            "domain_count": domain_count,
            "applied_policies_count": policy_count,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="policies")
    def policies(self, request):
        """
        List governance policies applied to mesh domains.

        GET /api/v1/mesh/governance/policies/
        """
        tenant_id = self.get_tenant_id_from_request()
        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        applications = PolicyApplication.objects.filter(
            domain__tenant_id=tenant_id,
        ).select_related("domain", "policy", "applied_by").order_by("-applied_at")[:100]

        data = [
            {
                "id": str(a.id),
                "domain_id": str(a.domain_id),
                "domain_name": a.domain.name,
                "policy_id": str(a.policy_id) if a.policy_id else None,
                "policy_name": a.policy.name if a.policy else None,
                "status": a.status,
                "applied_at": a.applied_at.isoformat() if a.applied_at else None,
            }
            for a in applications
        ]
        return Response({"results": data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="compliance")
    def compliance(self, request):
        """
        List mesh governance compliance status.

        GET /api/v1/mesh/governance/compliance/
        """
        tenant_id = self.get_tenant_id_from_request()
        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        domains = DataMeshDomain.objects.filter(tenant_id=tenant_id)
        reports = ComplianceReport.objects.filter(
            domain__tenant_id=tenant_id, asset=None
        ).select_related("domain").order_by("-generated_at")[:50]

        compliant_count = sum(
            1 for r in reports if r.compliance_status == MeshComplianceStatus.COMPLIANT
        )
        data = {
            "tenant_id": tenant_id,
            "domain_count": domains.count(),
            "compliant_count": compliant_count,
            "reports": [
                {
                    "id": str(r.id),
                    "domain_id": str(r.domain_id),
                    "compliance_status": r.compliance_status,
                    "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                }
                for r in reports
            ],
        }
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="reports")
    def reports(self, request):
        """
        List mesh governance reports.

        GET /api/v1/mesh/governance/reports/
        """
        tenant_id = self.get_tenant_id_from_request()
        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        reports = ComplianceReport.objects.filter(
            domain__tenant_id=tenant_id
        ).select_related("domain").order_by("-generated_at")[:50]

        data = {
            "tenant_id": tenant_id,
            "reports": [
                {
                    "id": str(r.id),
                    "domain_id": str(r.domain_id),
                    "compliance_status": r.compliance_status,
                    "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                }
                for r in reports
            ],
        }
        return Response(data, status=status.HTTP_200_OK)
