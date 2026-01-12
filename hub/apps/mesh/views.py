"""
Data Mesh Views

Django REST Framework views for Data Mesh domain management.
"""

import structlog
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
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
from hub.apps.core.services.base import ConflictError, NotFoundError, ValidationError
from hub.apps.rate_limiting.service import check_rate_limit, get_rate_limit_headers

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
            queryset = DataMeshDomain.objects.all()
        else:
            # Get tenant from request (set by middleware/authentication) or user
            # Priority: request.tenant_id > request.tenant > user.tenant_id > user.tenant
            tenant_id = None

            # Try request.tenant_id first (set by authentication/middleware)
            if hasattr(self.request, "tenant_id") and self.request.tenant_id:
                tenant_id = self.request.tenant_id
                # Convert to UUID if it's a string
                if isinstance(tenant_id, str):
                    import uuid

                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        tenant_id = None

            # Fallback to request.tenant object
            if not tenant_id and hasattr(self.request, "tenant") and self.request.tenant:
                tenant_id = self.request.tenant.id

            # Fallback to user.tenant_id (direct field access, most reliable)
            # CRITICAL: Refresh user from DB to get fresh tenant_id (important for thread safety)
            if not tenant_id and hasattr(user, "id") and user.id:
                # Query user from database to get fresh tenant_id (works in LiveServerTestCase)
                from django.contrib.auth import get_user_model

                User = get_user_model()
                try:
                    db_user = User.objects.only("tenant_id").get(id=user.id)
                    if db_user.tenant_id:
                        tenant_id = db_user.tenant_id
                except User.DoesNotExist:
                    pass

            # Last resort: get from user.tenant relationship
            if not tenant_id and hasattr(user, "tenant") and user.tenant:
                tenant_id = user.tenant.id

            # Regular users can only see domains in their tenant
            if tenant_id:
                # Use tenant_id for filtering (more reliable than tenant object)
                # Ensure tenant_id is a UUID for proper filtering
                if isinstance(tenant_id, str):
                    import uuid

                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        return DataMeshDomain.objects.none()
                # Filter by tenant_id - this is the most reliable way
                queryset = DataMeshDomain.objects.filter(tenant_id=tenant_id)
            else:
                return DataMeshDomain.objects.none()

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
        """
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

        # Validate request data
        serializer = DomainCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

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
        except Exception:
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
            raise NotFound(str(e))
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
            raise NotFound(str(e))
        except ValidationError as e:
            raise DRFValidationError(str(e))

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
            validation_type='ownership',
            new_owner_id=new_owner_id_str,
        )

        # Raise error if validation failed (matching previous behavior)
        if not validation_result.is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError("; ".join(validation_result.errors))

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
            raise NotFound(str(e))
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
            raise NotFound(str(e))
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
        except Exception:
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
            raise NotFound(str(e))
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
            raise NotFound(str(e))
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
        except Exception:
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
