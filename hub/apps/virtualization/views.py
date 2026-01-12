"""
Virtualization Views

REST API views for virtual dataset management.
"""
import logging
import time
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError as DRFValidationError, NotFound, PermissionDenied, Throttled
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer, OpenApiResponse, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers as drf_serializers
from django.utils import timezone

from .models import (
    VirtualDataset,
    QueryExecution,
    QueryType,
    VirtualDatasetStatus,
    QueryExecutionStatus,
    QueryExecutionMode
)
from .serializers import (
    VirtualDatasetSerializer,
    VirtualDatasetCreateSerializer,
    VirtualDatasetUpdateSerializer,
    VirtualDatasetValidationResponseSerializer,
    VirtualDatasetVersionSerializer,
    QueryExecutionSerializer,
    QueryExecutionCreateSerializer,
    QueryExecutionResultSerializer,
    QueryExecutionProgressSerializer,
    QueryExecutionCancelResponseSerializer,
    VirtualizationTopologySerializer,
    DatasetTopologySerializer
)
from .services import VirtualizationService
from .business_rules import VirtualizationBusinessRules, VirtualizationRuleExecutionContext
from hub.apps.core.services.base import ValidationError, NotFoundError, PermissionError
from hub.apps.audit.utils import create_audit_event
from hub.apps.auth.permissions import HasRole, HasAnyRole, HasScope
from hub.apps.rate_limiting.service import check_rate_limit, get_rate_limit_headers
from hub.apps.governance.abac import ABACEngine, PolicyEvaluationResult
from hub.apps.api.standards.pagination import StandardPageNumberPagination

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List virtual datasets",
        description="List all virtual datasets for the authenticated user's tenant with filtering, pagination, and search.",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by status (DRAFT, ACTIVE, INACTIVE, ARCHIVED)',
                required=False
            ),
            OpenApiParameter(
                name='query_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by query type (SQL, SPARQL, FEDERATED, GRAPHQL, REST)',
                required=False
            ),
            OpenApiParameter(
                name='owner',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Filter by owner/created_by user ID',
                required=False
            ),
            OpenApiParameter(
                name='created_by',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Filter by created_by user ID (alias for owner)',
                required=False
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search in name, description, and query fields',
                required=False
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Order by field (e.g., name, -created_at). Prefix with - for descending.',
                required=False
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Page number (default: 1)',
                required=False
            ),
            OpenApiParameter(
                name='page_size',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Items per page (default: 50, max: 100)',
                required=False
            ),
        ],
        tags=["Virtualization"],
    ),
    retrieve=extend_schema(
        summary="Get virtual dataset details",
        description="Get detailed information about a specific virtual dataset.",
        tags=["Virtualization"],
    ),
    create=extend_schema(
        summary="Create virtual dataset",
        description="Create a new virtual dataset. Requires DATA_PROVIDER or TENANT_ADMIN role and virtualization:write scope.",
        tags=["Virtualization"],
    ),
    update=extend_schema(
        summary="Update virtual dataset",
        description="Update an existing virtual dataset. Requires DATA_PROVIDER or TENANT_ADMIN role and virtualization:write scope.",
        tags=["Virtualization"],
    ),
    destroy=extend_schema(
        summary="Delete virtual dataset",
        description="Delete a virtual dataset. Requires DATA_PROVIDER or TENANT_ADMIN role and virtualization:write scope.",
        tags=["Virtualization"],
    ),
)
class VirtualDatasetViewSet(viewsets.ModelViewSet):
    """
    ViewSet for virtual dataset management.

    Tenant-scoped: users can only see/manage virtual datasets in their tenant.
    Supports RBAC (role-based) and ABAC (attribute-based) authorization.
    Includes rate limiting, comprehensive filtering, pagination, and audit logging.
    """
    queryset = VirtualDataset.objects.all()
    serializer_class = VirtualDatasetSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    filter_backends = [OrderingFilter, SearchFilter]
    ordering_fields = ['name', 'query_type', 'status', 'version', 'created_at', 'updated_at']
    ordering = ['-created_at']  # Default ordering
    search_fields = ['name', 'description', 'query']
    pagination_class = StandardPageNumberPagination

    def get_permissions(self):
        """Return appropriate permissions based on action"""
        write_actions = ['create', 'update', 'partial_update', 'destroy']
        if self.action in write_actions:
            # Write operations require DATA_PROVIDER or TENANT_ADMIN role and virtualization:write scope
            return [
                permissions.IsAuthenticated(),
                HasAnyRole(['DATA_PROVIDER', 'TENANT_ADMIN']),
                HasScope('virtualization:write'),
            ]
        # Read operations only require authentication
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return VirtualDatasetCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return VirtualDatasetUpdateSerializer
        return VirtualDatasetSerializer

    def get_queryset(self):
        """Filter queryset based on user permissions and tenant isolation"""
        user = self.request.user

        # Platform admins can see all virtual datasets
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = VirtualDataset.objects.all()
        else:
            # Get tenant from request (set by middleware/authentication) or user
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

            # Fallback to user.tenant_id (direct field access)
            if not tenant_id and hasattr(user, "id") and user.id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    db_user = User.objects.only('tenant_id').get(id=user.id)
                    if db_user.tenant_id:
                        tenant_id = db_user.tenant_id
                except User.DoesNotExist:
                    pass

            # Last resort: get from user.tenant relationship
            if not tenant_id and hasattr(user, "tenant") and user.tenant:
                tenant_id = user.tenant.id

            # Regular users can only see virtual datasets in their tenant
            if tenant_id:
                if isinstance(tenant_id, str):
                    import uuid
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        return VirtualDataset.objects.none()
                queryset = VirtualDataset.objects.filter(tenant_id=tenant_id)
            else:
                return VirtualDataset.objects.none()

        # Apply status filter if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            valid_statuses = [choice[0] for choice in VirtualDatasetStatus.choices]
            if status_filter.upper() in valid_statuses:
                queryset = queryset.filter(status=status_filter.upper())
            else:
                return VirtualDataset.objects.none()

        # Apply query_type filter if provided
        query_type_filter = self.request.query_params.get('query_type')
        if query_type_filter:
            valid_query_types = [choice[0] for choice in QueryType.choices]
            if query_type_filter.upper() in valid_query_types:
                queryset = queryset.filter(query_type=query_type_filter.upper())
            else:
                return VirtualDataset.objects.none()

        # Apply owner/created_by filter if provided
        owner_filter = self.request.query_params.get('owner') or self.request.query_params.get('created_by')
        if owner_filter:
            try:
                import uuid
                owner_uuid = uuid.UUID(owner_filter)
                queryset = queryset.filter(created_by_id=owner_uuid)
            except (ValueError, TypeError):
                # Invalid UUID, return empty queryset
                return VirtualDataset.objects.none()

        return queryset

    def get_tenant_from_request(self):
        """Get tenant from request"""
        user = self.request.user

        # Try request.tenant_id first
        if hasattr(self.request, "tenant_id") and self.request.tenant_id:
            from hub.apps.tenants.models import Tenant
            try:
                return Tenant.objects.get(id=self.request.tenant_id)
            except Tenant.DoesNotExist:
                pass

        # Fallback to request.tenant object
        if hasattr(self.request, "tenant") and self.request.tenant:
            return self.request.tenant

        # Fallback to user.tenant
        if hasattr(user, "tenant") and user.tenant:
            return user.tenant

        return None

    def _check_abac_policy(
        self,
        user_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        access_type: str = "WRITE"
    ) -> None:
        """
        Check ABAC policy for resource access.

        Args:
            user_id: User UUID
            tenant_id: Tenant UUID
            resource_type: Resource type (VIRTUAL_DATASET)
            resource_id: Resource UUID
            access_type: Access type (READ, WRITE, DELETE)

        Raises:
            PermissionDenied: If ABAC policy denies access
        """
        try:
            result = ABACEngine.evaluate_access(
                user_id=user_id,
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                access_type=access_type
            )

            if not result.allowed:
                # If a policy explicitly denied access, raise PermissionDenied
                if result.policy:
                    policy_name = result.policy.name if result.policy else "Unknown Policy"
                    raise PermissionDenied(
                        f"ABAC policy '{policy_name}' denies {access_type} access to {resource_type} {resource_id}"
                    )
                # If no policy matched (default deny), we allow access for new resource creation
                # This is a "fail open" approach for new resources when no policies are configured
                # For existing resources, we should still check ownership/tenant isolation
                logger.debug(
                    "abac_no_policy_matched: No ABAC policy matched, allowing access (fail open)",
                    extra={
                        "user_id": user_id,
                        "tenant_id": tenant_id,
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                        "access_type": access_type
                    }
                )
                # Allow access when no policy matches (fail open)
                return
        except PermissionDenied:
            raise
        except Exception as e:
            logger.warning(
                f"ABAC policy check failed: {str(e)}",
                extra={
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "access_type": access_type,
                    "error": str(e)
                },
                exc_info=True
            )
            # Fail open: if ABAC check fails, allow access (but log the warning)
            # In production, you might want to fail closed instead

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new virtual dataset.

        POST /api/v1/virtualization/datasets/
        """
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        serializer = VirtualDatasetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant
        tenant = self.get_tenant_from_request()
        if not tenant:
            return Response(
                {'error': 'Tenant context required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ensure user_id is provided
        if not request.user or not request.user.id:
            return Response(
                {'error': 'User authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user_id = str(request.user.id)
        tenant_id = str(tenant.id)

        # Check ABAC policy for creating new virtual dataset
        # Use placeholder resource ID for new resources
        placeholder_resource_id = f"tenant:{tenant_id}:virtual_dataset:new"
        try:
            self._check_abac_policy(
                user_id=user_id,
                tenant_id=tenant_id,
                resource_type="VIRTUAL_DATASET",
                resource_id=placeholder_resource_id,
                access_type="WRITE"
            )
        except PermissionDenied as e:
            logger.warning(
                "ABAC policy denied virtual dataset creation",
                extra={
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "error": str(e)
                }
            )
            return Response(
                {'error': str(e), 'code': 'PERMISSION_DENIED'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Initialize service
        service = VirtualizationService(
            tenant_id=tenant_id,
            user_id=user_id
        )

        try:
            # Ensure user_id is provided
            if not request.user or not request.user.id:
                return Response(
                    {'error': 'User authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Create virtual dataset using service
            virtual_dataset = service.create_virtual_dataset(
                name=serializer.validated_data['name'],
                query=serializer.validated_data['query'],
                query_type=serializer.validated_data['query_type'],
                tenant_id=tenant_id,
                user_id=user_id,
                description=serializer.validated_data.get('description'),
                schema=serializer.validated_data.get('schema'),
                sources=serializer.validated_data.get('sources'),
                version=serializer.validated_data.get('version', '1.0.0'),
                status=serializer.validated_data.get('status', VirtualDatasetStatus.DRAFT)
            )

            # Log audit event
            create_audit_event(
                resource_type="VIRTUAL_DATASET",
                action="VIRTUAL_DATASET_CREATED",
                actor_user=request.user,
                tenant=tenant,
                resource_id=str(virtual_dataset.id),
                details={
                    'name': virtual_dataset.name,
                    'query_type': virtual_dataset.query_type,
                    'status': virtual_dataset.status,
                    'version': virtual_dataset.version
                },
                request=request
            )

            # Get rate limit headers for response
            _, rate_limit_results = check_rate_limit(request)
            headers = get_rate_limit_headers(request, rate_limit_results)

            return Response(
                VirtualDatasetSerializer(virtual_dataset).data,
                status=status.HTTP_201_CREATED,
                headers=headers
            )

        except ValidationError as e:
            logger.error(
                "Virtual dataset creation failed",
                extra={
                    "tenant_id": str(tenant.id),
                    "user_id": str(request.user.id) if request.user else None,
                    "error": str(e),
                    "error_code": getattr(e, 'code', None)
                },
                exc_info=True
            )
            return Response(
                {'error': str(e), 'code': getattr(e, 'code', 'VALIDATION_ERROR')},
                status=status.HTTP_400_BAD_REQUEST
            )
        except PermissionError as e:
            logger.warning(
                "Permission denied for virtual dataset creation",
                extra={
                    "tenant_id": str(tenant.id),
                    "user_id": str(request.user.id) if request.user else None,
                    "error": str(e)
                }
            )
            return Response(
                {'error': str(e), 'code': 'PERMISSION_DENIED'},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.error(
                "Unexpected error during virtual dataset creation",
                extra={
                    "tenant_id": str(tenant.id),
                    "user_id": str(request.user.id) if request.user else None,
                    "error": str(e)
                },
                exc_info=True
            )
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def list(self, request, *args, **kwargs):
        """
        List virtual datasets (tenant-scoped).

        GET /api/v1/virtualization/datasets/
        Query params: status, query_type, owner/created_by, search, ordering, page, page_size
        """
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        response = super().list(request, *args, **kwargs)

        # Get rate limit headers for response
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Add rate limit headers to response
        for key, value in headers.items():
            response[key] = value

        return response

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve virtual dataset by ID.

        GET /api/v1/virtualization/datasets/{id}/
        """
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        dataset_id = kwargs.get('id')
        tenant = self.get_tenant_from_request()

        # Check if dataset exists in another tenant first (for proper 403 vs 404)
        if dataset_id and tenant:
            try:
                # Try to get dataset without tenant filtering
                other_tenant_dataset = VirtualDataset.objects.get(id=dataset_id)
                if str(other_tenant_dataset.tenant_id) != str(tenant.id):
                    if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                        raise PermissionDenied("Cannot access virtual dataset from different tenant")
            except VirtualDataset.DoesNotExist:
                pass  # Dataset doesn't exist at all, will return 404 below

        # Try to get from tenant-scoped queryset
        try:
            virtual_dataset = self.get_object()
        except NotFound:
            raise NotFound("Virtual dataset not found")

        # Check ABAC policy for READ access
        if request.user and request.user.id and tenant:
            try:
                self._check_abac_policy(
                    user_id=str(request.user.id),
                    tenant_id=str(tenant.id),
                    resource_type="VIRTUAL_DATASET",
                    resource_id=str(virtual_dataset.id),
                    access_type="READ"
                )
            except PermissionDenied as e:
                logger.warning(
                    "ABAC policy denied virtual dataset read access",
                    extra={
                        "user_id": str(request.user.id),
                        "tenant_id": str(tenant.id),
                        "virtual_dataset_id": str(virtual_dataset.id),
                        "error": str(e)
                    }
                )
                raise

        # Get rate limit headers for response
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        return Response(
            VirtualDatasetSerializer(virtual_dataset).data,
            headers=headers
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update virtual dataset (full update).

        PUT /api/v1/virtualization/datasets/{id}/
        """
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        dataset_id = kwargs.get('id')
        tenant = self.get_tenant_from_request()

        # Check if dataset exists in another tenant first (for proper 403 vs 404)
        if dataset_id and tenant:
            try:
                # Try to get dataset without tenant filtering
                other_tenant_dataset = VirtualDataset.objects.get(id=dataset_id)
                if str(other_tenant_dataset.tenant_id) != str(tenant.id):
                    if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                        raise PermissionDenied("Cannot update virtual dataset from different tenant")
            except VirtualDataset.DoesNotExist:
                pass  # Dataset doesn't exist at all, will return 404 below

        # Try to get from tenant-scoped queryset
        try:
            virtual_dataset = self.get_object()
        except NotFound:
            raise NotFound("Virtual dataset not found")

        serializer = VirtualDatasetUpdateSerializer(virtual_dataset, data=request.data)
        serializer.is_valid(raise_exception=True)

        # Ensure user_id is provided
        if not request.user or not request.user.id:
            return Response(
                {'error': 'User authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user_id = str(request.user.id)
        tenant_id = str(virtual_dataset.tenant_id)

        # Check ABAC policy for WRITE access
        try:
            self._check_abac_policy(
                user_id=user_id,
                tenant_id=tenant_id,
                resource_type="VIRTUAL_DATASET",
                resource_id=str(virtual_dataset.id),
                access_type="WRITE"
            )
        except PermissionDenied as e:
            logger.warning(
                "ABAC policy denied virtual dataset update",
                extra={
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "error": str(e)
                }
            )
            return Response(
                {'error': str(e), 'code': 'PERMISSION_DENIED'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Initialize service
        service = VirtualizationService(
            tenant_id=tenant_id,
            user_id=user_id
        )

        try:
            # Update virtual dataset using service
            update_data = serializer.validated_data.copy()
            virtual_dataset = service.update_virtual_dataset(
                virtual_dataset_id=str(virtual_dataset.id),
                tenant_id=str(virtual_dataset.tenant_id),
                **update_data
            )

            # Log audit event
            create_audit_event(
                resource_type="VIRTUAL_DATASET",
                action="VIRTUAL_DATASET_UPDATED",
                actor_user=request.user,
                tenant=virtual_dataset.tenant,
                resource_id=str(virtual_dataset.id),
                details=update_data,
                request=request
            )

            # Get rate limit headers for response
            _, rate_limit_results = check_rate_limit(request)
            headers = get_rate_limit_headers(request, rate_limit_results)

            return Response(
                VirtualDatasetSerializer(virtual_dataset).data,
                headers=headers
            )

        except ValidationError as e:
            logger.error(
                "Virtual dataset update failed",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": str(virtual_dataset.tenant_id),
                    "error": str(e),
                    "error_code": getattr(e, 'code', None)
                },
                exc_info=True
            )
            return Response(
                {'error': str(e), 'code': getattr(e, 'code', 'VALIDATION_ERROR')},
                status=status.HTTP_400_BAD_REQUEST
            )
        except PermissionError as e:
            logger.warning(
                "Permission denied for virtual dataset update",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": str(virtual_dataset.tenant_id),
                    "user_id": str(request.user.id) if request.user else None,
                    "error": str(e)
                }
            )
            return Response(
                {'error': str(e), 'code': 'PERMISSION_DENIED'},
                status=status.HTTP_403_FORBIDDEN
            )
        except NotFoundError as e:
            raise NotFound(str(e))
        except Exception as e:
            logger.error(
                "Unexpected error during virtual dataset update",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": str(virtual_dataset.tenant_id),
                    "error": str(e)
                },
                exc_info=True
            )
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """
        Partially update virtual dataset.

        PATCH /api/v1/virtualization/datasets/{id}/
        """
        return self.update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete virtual dataset.

        DELETE /api/v1/virtualization/datasets/{id}/
        """
        # Check rate limiting
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        dataset_id = kwargs.get('id')
        tenant = self.get_tenant_from_request()

        # Check if dataset exists in another tenant first (for proper 403 vs 404)
        if dataset_id and tenant:
            try:
                # Try to get dataset without tenant filtering
                other_tenant_dataset = VirtualDataset.objects.get(id=dataset_id)
                if str(other_tenant_dataset.tenant_id) != str(tenant.id):
                    if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                        raise PermissionDenied("Cannot delete virtual dataset from different tenant")
            except VirtualDataset.DoesNotExist:
                pass  # Dataset doesn't exist at all, will return 404 below

        # Try to get from tenant-scoped queryset
        try:
            virtual_dataset = self.get_object()
        except NotFound:
            raise NotFound("Virtual dataset not found")

        # Store details for audit log
        dataset_id = str(virtual_dataset.id)
        dataset_name = virtual_dataset.name

        # Ensure user_id is provided
        if not request.user or not request.user.id:
            return Response(
                {'error': 'User authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user_id = str(request.user.id)
        tenant_id = str(virtual_dataset.tenant_id)

        # Check ABAC policy for DELETE access
        try:
            self._check_abac_policy(
                user_id=user_id,
                tenant_id=tenant_id,
                resource_type="VIRTUAL_DATASET",
                resource_id=dataset_id,
                access_type="DELETE"
            )
        except PermissionDenied as e:
            logger.warning(
                "ABAC policy denied virtual dataset deletion",
                extra={
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "virtual_dataset_id": dataset_id,
                    "error": str(e)
                }
            )
            return Response(
                {'error': str(e), 'code': 'PERMISSION_DENIED'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Initialize service
        service = VirtualizationService(
            tenant_id=tenant_id,
            user_id=user_id
        )

        try:
            # Delete virtual dataset using service
            service.delete_virtual_dataset(
                virtual_dataset_id=dataset_id,
                tenant_id=str(virtual_dataset.tenant_id)
            )

            # Log audit event
            create_audit_event(
                resource_type="VIRTUAL_DATASET",
                action="VIRTUAL_DATASET_DELETED",
                actor_user=request.user,
                tenant=virtual_dataset.tenant,
                resource_id=dataset_id,
                details={
                    'name': dataset_name
                },
                request=request
            )

            # Get rate limit headers for response
            _, rate_limit_results = check_rate_limit(request)
            headers = get_rate_limit_headers(request, rate_limit_results)

            return Response(
                status=status.HTTP_204_NO_CONTENT,
                headers=headers
            )

        except PermissionError as e:
            logger.warning(
                "Permission denied for virtual dataset deletion",
                extra={
                    "virtual_dataset_id": dataset_id,
                    "tenant_id": str(virtual_dataset.tenant_id),
                    "user_id": str(request.user.id) if request.user else None,
                    "error": str(e)
                }
            )
            return Response(
                {'error': str(e), 'code': 'PERMISSION_DENIED'},
                status=status.HTTP_403_FORBIDDEN
            )
        except NotFoundError as e:
            raise NotFound(str(e))
        except Exception as e:
            logger.error(
                "Unexpected error during virtual dataset deletion",
                extra={
                    "virtual_dataset_id": dataset_id,
                    "tenant_id": str(virtual_dataset.tenant_id),
                    "error": str(e)
                },
                exc_info=True
            )
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Validate virtual dataset",
        description="Validate a virtual dataset structure, query syntax, schema alignment, and source compatibility.",
        request=None,
        responses={
            200: VirtualDatasetValidationResponseSerializer,
        },
        tags=["Virtualization"],
    )
    @action(detail=True, methods=['post'], url_path='validate')
    def validate_dataset(self, request, id=None):
        """
        Validate virtual dataset.

        POST /api/v1/virtualization/datasets/{id}/validate/
        """
        # Get dataset ID from URL kwargs
        dataset_id = id or request.parser_context.get('kwargs', {}).get('id')
        tenant = self.get_tenant_from_request()

        # Check if dataset exists in another tenant first (for proper 403 vs 404)
        if dataset_id and tenant:
            try:
                # Try to get dataset without tenant filtering
                other_tenant_dataset = VirtualDataset.objects.get(id=dataset_id)
                if str(other_tenant_dataset.tenant_id) != str(tenant.id):
                    if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                        raise PermissionDenied("Cannot validate virtual dataset from different tenant")
            except VirtualDataset.DoesNotExist:
                pass  # Dataset doesn't exist at all, will return 404 below

        # Try to get from tenant-scoped queryset
        try:
            virtual_dataset = self.get_object()
        except NotFound:
            raise NotFound("Virtual dataset not found")

        # Initialize business rules
        business_rules = VirtualizationBusinessRules(
            tenant_id=str(virtual_dataset.tenant_id),
            user_id=str(request.user.id) if request.user and request.user.id else None
        )

        # Create execution context for better integration with base class features
        # (caching, metrics, tracing, logging)
        context = VirtualizationRuleExecutionContext(
            tenant_id=str(virtual_dataset.tenant_id),
            user_id=str(request.user.id) if request.user and request.user.id else None,
            virtual_dataset=virtual_dataset,
            query=virtual_dataset.query
        )

        # Use execute() method for comprehensive validation with caching, metrics, and tracing
        # This enables better observability and performance through caching
        validation_result = business_rules.execute(
            context=context,
            validation_type='all',
            use_cache=True  # Enable caching for validation results
        )

        # Convert ValidationResult to the expected format
        validation_results = {
            'is_valid': validation_result.is_valid,
            'errors': validation_result.errors,
            'warnings': validation_result.warnings,
            'details': validation_result.details
        }

        # Log audit event
        create_audit_event(
            resource_type="VIRTUAL_DATASET",
            action="VIRTUAL_DATASET_VALIDATED",
            actor_user=request.user,
            tenant=virtual_dataset.tenant,
            resource_id=str(virtual_dataset.id),
            details={
                'validation_result': validation_results['is_valid'],
                'error_count': len(validation_results['errors']),
                'warning_count': len(validation_results['warnings'])
            },
            request=request
        )

        return Response(
            VirtualDatasetValidationResponseSerializer(validation_results).data,
            status=status.HTTP_200_OK
        )

    @extend_schema(
        summary="Get virtual dataset versions",
        description="Get all versions of a virtual dataset (by name) for the current tenant.",
        responses={
            200: inline_serializer(
                name='VirtualDatasetVersionsResponse',
                fields={
                    'versions': drf_serializers.ListField(
                        child=VirtualDatasetVersionSerializer()
                    ),
                    'count': drf_serializers.IntegerField()
                }
            ),
        },
        tags=["Virtualization"],
    )
    @action(detail=True, methods=['get'], url_path='versions')
    def versions(self, request, id=None):
        """
        Get all versions of a virtual dataset.

        GET /api/v1/virtualization/datasets/{id}/versions/
        """
        # Get dataset ID from URL kwargs
        dataset_id = id or request.parser_context.get('kwargs', {}).get('id')
        tenant = self.get_tenant_from_request()

        # Check if dataset exists in another tenant first (for proper 403 vs 404)
        if dataset_id and tenant:
            try:
                # Try to get dataset without tenant filtering
                other_tenant_dataset = VirtualDataset.objects.get(id=dataset_id)
                if str(other_tenant_dataset.tenant_id) != str(tenant.id):
                    if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                        raise PermissionDenied("Cannot access virtual dataset from different tenant")
            except VirtualDataset.DoesNotExist:
                pass  # Dataset doesn't exist at all, will return 404 below

        # Try to get from tenant-scoped queryset
        try:
            virtual_dataset = self.get_object()
        except NotFound:
            raise NotFound("Virtual dataset not found")

        # Get all versions of this dataset (same name, same tenant)
        versions = VirtualDataset.objects.filter(
            tenant_id=virtual_dataset.tenant_id,
            name=virtual_dataset.name
        ).order_by('-created_at')

        # Serialize versions
        version_data = []
        for version in versions:
            version_data.append({
                'version': version.version,
                'status': version.status,
                'created_at': version.created_at,
                'updated_at': version.updated_at,
                'query_type': version.query_type,
                'source_count': version.get_source_count()
            })

        return Response({
            'versions': VirtualDatasetVersionSerializer(version_data, many=True).data,
            'count': len(version_data)
        })

    @extend_schema(
        summary="Execute query on virtual dataset",
        description="Execute a query on a virtual dataset. Supports synchronous and asynchronous execution modes.",
        request=QueryExecutionCreateSerializer,
        responses={
            201: QueryExecutionSerializer,
            400: OpenApiResponse(description='Bad request'),
        },
        tags=["Virtualization"],
    )
    @action(detail=True, methods=['post'], url_path='queries')
    @transaction.atomic
    def execute_query(self, request, id=None):
        """
        Execute a query on a virtual dataset.

        POST /api/v1/virtualization/datasets/{id}/queries/
        """
        # Get dataset ID from URL kwargs
        dataset_id = id or request.parser_context.get('kwargs', {}).get('id')
        tenant = self.get_tenant_from_request()

        # Try to get from tenant-scoped queryset
        try:
            virtual_dataset = self.get_object()
        except NotFound:
            # Check if dataset exists in another tenant (for proper 403 vs 404)
            if dataset_id and tenant:
                try:
                    other_tenant_dataset = VirtualDataset.objects.get(id=dataset_id)
                    if str(other_tenant_dataset.tenant_id) != str(tenant.id):
                        if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                            raise PermissionDenied("Cannot execute query on virtual dataset from different tenant")
                except VirtualDataset.DoesNotExist:
                    pass
            raise NotFound("Virtual dataset not found")

        # Check tenant isolation
        if tenant and str(virtual_dataset.tenant_id) != str(tenant.id):
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                raise PermissionDenied("Cannot execute query on virtual dataset from different tenant")

        # Ensure user_id is provided
        if not request.user or not request.user.id:
            return Response(
                {'error': 'User authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id),
                    "tenant_id": str(tenant.id) if tenant else None,
                    "virtual_dataset_id": dataset_id
                }
            )
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        # ABAC check for write access to virtual dataset
        if virtual_dataset.tenant:
            # Skip ABAC for platform admins
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                try:
                    self._check_abac_policy(
                        user_id=str(request.user.id),
                        tenant_id=str(virtual_dataset.tenant_id),
                        resource_type="VIRTUAL_DATASET",
                        resource_id=str(virtual_dataset.id),
                        access_type="WRITE"
                    )
                except PermissionDenied:
                    logger.warning(
                        "abac_denied_query_execution_create",
                        extra={
                            "user_id": str(request.user.id),
                            "tenant_id": str(virtual_dataset.tenant_id),
                            "virtual_dataset_id": str(virtual_dataset.id)
                        }
                    )
                    raise

        # Validate request data
        serializer = QueryExecutionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Initialize service
        service = VirtualizationService(
            tenant_id=str(virtual_dataset.tenant_id),
            user_id=str(request.user.id)
        )

        try:
            # Execute query using service
            execution = service.execute_query(
                virtual_dataset_id=str(virtual_dataset.id),
                tenant_id=str(virtual_dataset.tenant_id),
                user_id=str(request.user.id),
                execution_mode=serializer.validated_data.get('execution_mode'),
                parameters=serializer.validated_data.get('parameters'),
                force_async=serializer.validated_data.get('force_async', False),
                timeout_seconds=serializer.validated_data.get('timeout_seconds')
            )

            # Log audit event
            create_audit_event(
                resource_type="QUERY_EXECUTION",
                action="QUERY_EXECUTION_CREATED",
                actor_user=request.user,
                tenant=virtual_dataset.tenant,
                resource_id=str(execution.id),
                details={
                    'virtual_dataset_id': str(virtual_dataset.id),
                    'virtual_dataset_name': virtual_dataset.name,
                    'execution_mode': execution.execution_mode,
                    'status': execution.status
                },
                request=request
            )

            response = Response(
                QueryExecutionSerializer(execution).data,
                status=status.HTTP_201_CREATED
            )

            # Add rate limit headers
            _, rate_limit_results = check_rate_limit(request)
            headers = get_rate_limit_headers(request, rate_limit_results)
            for header, value in headers.items():
                response[header] = value

            return response

        except ValidationError as e:
            logger.error(
                "Query execution failed",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": str(virtual_dataset.tenant_id),
                    "user_id": str(request.user.id),
                    "error": str(e),
                    "error_code": getattr(e, 'code', None)
                },
                exc_info=True
            )
            return Response(
                {'error': str(e), 'code': getattr(e, 'code', 'VALIDATION_ERROR')},
                status=status.HTTP_400_BAD_REQUEST
            )
        except NotFoundError as e:
            raise NotFound(str(e))
        except PermissionError as e:
            logger.warning(
                "Permission denied for query execution",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": str(virtual_dataset.tenant_id),
                    "user_id": str(request.user.id),
                    "error": str(e)
                }
            )
            return Response(
                {'error': str(e), 'code': 'PERMISSION_DENIED'},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.error(
                "Unexpected error during query execution",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": str(virtual_dataset.tenant_id),
                    "user_id": str(request.user.id),
                    "error": str(e)
                },
                exc_info=True
            )
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema_view(
    retrieve=extend_schema(
        summary="Get query execution details",
        description="Get detailed information about a specific query execution.",
        tags=["Virtualization"],
    ),
)
class QueryExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for query execution management.

    Tenant-scoped: users can only see query executions for virtual datasets in their tenant.
    Supports RBAC (role-based) and ABAC (attribute-based) authorization.
    Includes rate limiting, comprehensive audit logging, and result retrieval in multiple formats.
    """
    queryset = QueryExecution.objects.all()
    serializer_class = QueryExecutionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    pagination_class = StandardPageNumberPagination

    def get_permissions(self):
        """Return appropriate permissions based on action"""
        write_actions = ['cancel_execution']
        if self.action in write_actions:
            # Write operations require DATA_PROVIDER or TENANT_ADMIN role and virtualization:write scope
            return [
                permissions.IsAuthenticated(),
                HasAnyRole(['DATA_PROVIDER', 'TENANT_ADMIN']),
                HasScope('virtualization:write'),
            ]
        # Read operations only require authentication
        return [permissions.IsAuthenticated()]

    def _check_abac_policy(
        self,
        user_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        access_type: str = "WRITE"
    ) -> None:
        """
        Check ABAC policy for resource access.

        Args:
            user_id: User UUID
            tenant_id: Tenant UUID
            resource_type: Resource type (QUERY_EXECUTION)
            resource_id: Resource UUID
            access_type: Access type (READ, WRITE, DELETE)

        Raises:
            PermissionDenied: If ABAC policy denies access
        """
        try:
            result = ABACEngine.evaluate_access(
                user_id=user_id,
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                access_type=access_type
            )

            if not result.allowed:
                # If a policy explicitly denied access, raise PermissionDenied
                if result.policy:
                    policy_name = result.policy.name if result.policy else "Unknown Policy"
                    raise PermissionDenied(
                        f"ABAC policy '{policy_name}' denies {access_type} access to {resource_type} {resource_id}"
                    )
                # If no policy matched (default deny), we allow access for read operations
                # This is a "fail open" approach for read operations when no policies are configured
                logger.debug(
                    "abac_no_policy_matched: No ABAC policy matched, allowing access (fail open for reads)",
                    extra={
                        "user_id": user_id,
                        "tenant_id": tenant_id,
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                        "access_type": access_type
                    }
                )
                # Allow access when no policy matches (fail open for reads)
                return
        except PermissionDenied:
            raise
        except Exception as e:
            logger.warning(
                "abac_check_failed",
                extra={
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "access_type": access_type,
                    "error": str(e)
                },
                exc_info=True
            )
            # On ABAC engine failure, allow access (fail open) but log the error
            return

    def get_queryset(self):
        """Filter queryset based on user permissions and tenant isolation"""
        user = self.request.user

        # Platform admins can see all query executions
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = QueryExecution.objects.select_related('virtual_dataset', 'job').all()
        else:
            # Get tenant from request
            tenant_id = None

            # Try request.tenant_id first
            if hasattr(self.request, "tenant_id") and self.request.tenant_id:
                tenant_id = self.request.tenant_id
                if isinstance(tenant_id, str):
                    import uuid
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        tenant_id = None

            # Fallback to request.tenant object
            if not tenant_id and hasattr(self.request, "tenant") and self.request.tenant:
                tenant_id = self.request.tenant.id

            # Fallback to user.tenant_id
            if not tenant_id and hasattr(user, "id") and user.id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    db_user = User.objects.only('tenant_id').get(id=user.id)
                    if db_user.tenant_id:
                        tenant_id = db_user.tenant_id
                except User.DoesNotExist:
                    pass

            # Last resort: get from user.tenant relationship
            if not tenant_id and hasattr(user, "tenant") and user.tenant:
                tenant_id = user.tenant.id

            # Filter by tenant via virtual_dataset relationship
            if tenant_id:
                if isinstance(tenant_id, str):
                    import uuid
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        return QueryExecution.objects.none()
                queryset = QueryExecution.objects.select_related('virtual_dataset', 'job').filter(
                    virtual_dataset__tenant_id=tenant_id
                )
            else:
                return QueryExecution.objects.none()

        # Apply status filter if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            valid_statuses = [choice[0] for choice in QueryExecutionStatus.choices]
            if status_filter.upper() in valid_statuses:
                queryset = queryset.filter(status=status_filter.upper())
            else:
                return QueryExecution.objects.none()

        # Apply virtual_dataset filter if provided
        dataset_filter = self.request.query_params.get('virtual_dataset_id')
        if dataset_filter:
            try:
                import uuid
                dataset_uuid = uuid.UUID(dataset_filter)
                queryset = queryset.filter(virtual_dataset_id=dataset_uuid)
            except (ValueError, TypeError):
                return QueryExecution.objects.none()

        return queryset

    def get_tenant_from_request(self):
        """Get tenant from request"""
        user = self.request.user

        # Try request.tenant_id first
        if hasattr(self.request, "tenant_id") and self.request.tenant_id:
            from hub.apps.tenants.models import Tenant
            try:
                return Tenant.objects.get(id=self.request.tenant_id)
            except Tenant.DoesNotExist:
                pass

        # Fallback to request.tenant object
        if hasattr(self.request, "tenant") and self.request.tenant:
            return self.request.tenant

        # Fallback to user.tenant
        if hasattr(user, "tenant") and user.tenant:
            return user.tenant

        return None

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve query execution by ID.

        GET /api/v1/virtualization/queries/{id}/
        """
        execution_id = kwargs.get('id')
        tenant = self.get_tenant_from_request()

        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id) if request.user else None,
                    "tenant_id": str(tenant.id) if tenant else None,
                    "execution_id": execution_id
                }
            )
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        # Check if execution exists in another tenant first (for proper 403 vs 404)
        if execution_id and tenant:
            try:
                # Try to get execution without tenant filtering
                other_tenant_execution = QueryExecution.objects.select_related('virtual_dataset').get(id=execution_id)
                if str(other_tenant_execution.virtual_dataset.tenant_id) != str(tenant.id):
                    if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                        raise PermissionDenied("Cannot access query execution from different tenant")
            except QueryExecution.DoesNotExist:
                pass  # Execution doesn't exist at all, will return 404 below

        # Try to get from tenant-scoped queryset
        try:
            execution = self.get_object()
        except NotFound:
            raise NotFound("Query execution not found")

        # ABAC check for read access
        if request.user and request.user.id and execution.virtual_dataset.tenant:
            # Skip ABAC for platform admins
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                try:
                    self._check_abac_policy(
                        user_id=str(request.user.id),
                        tenant_id=str(execution.virtual_dataset.tenant_id),
                        resource_type="QUERY_EXECUTION",
                        resource_id=str(execution.id),
                        access_type="READ"
                    )
                except PermissionDenied:
                    logger.warning(
                        "abac_denied_query_execution_read",
                        extra={
                            "user_id": str(request.user.id),
                            "tenant_id": str(execution.virtual_dataset.tenant_id),
                            "execution_id": str(execution.id)
                        }
                    )
                    raise

        # Log audit event
        try:
            create_audit_event(
                resource_type="QUERY_EXECUTION",
                action="QUERY_EXECUTION_READ",
                actor_user=request.user,
                tenant=execution.virtual_dataset.tenant,
                resource_id=str(execution.id),
                details={
                    "virtual_dataset_id": str(execution.virtual_dataset.id),
                    "virtual_dataset_name": execution.virtual_dataset.name,
                    "status": execution.status
                },
                request=request
            )
        except Exception as e:
            logger.warning(
                f"Failed to create audit event for query execution read: {e}",
                extra={
                    "execution_id": str(execution.id),
                    "tenant_id": str(execution.virtual_dataset.tenant_id),
                    "error": str(e)
                },
                exc_info=True
            )

        response = Response(QueryExecutionSerializer(execution).data)

        # Add rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)
        for header, value in headers.items():
            response[header] = value

        return response

    @extend_schema(
        summary="Cancel query execution",
        description="Cancel a running or pending query execution.",
        request=None,
        responses={
            200: QueryExecutionCancelResponseSerializer,
            400: OpenApiResponse(description='Execution cannot be cancelled'),
        },
        tags=["Virtualization"],
    )
    @action(detail=True, methods=['post'], url_path='cancel')
    @transaction.atomic
    def cancel_execution(self, request, id=None):
        """
        Cancel a query execution.

        POST /api/v1/virtualization/queries/{id}/cancel/
        """
        execution_id = id or request.parser_context.get('kwargs', {}).get('id')
        tenant = self.get_tenant_from_request()

        # Ensure user_id is provided
        if not request.user or not request.user.id:
            return Response(
                {'error': 'User authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id),
                    "tenant_id": str(tenant.id) if tenant else None,
                    "execution_id": execution_id
                }
            )
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        # Check if execution exists in another tenant first (for proper 403 vs 404)
        if execution_id and tenant:
            try:
                # Try to get execution without tenant filtering
                other_tenant_execution = QueryExecution.objects.select_related('virtual_dataset').get(id=execution_id)
                if str(other_tenant_execution.virtual_dataset.tenant_id) != str(tenant.id):
                    if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                        raise PermissionDenied("Cannot cancel query execution from different tenant")
            except QueryExecution.DoesNotExist:
                pass  # Execution doesn't exist at all, will return 404 below

        # Try to get from tenant-scoped queryset
        try:
            execution = self.get_object()
        except NotFound:
            raise NotFound("Query execution not found")

        # ABAC check for write access
        if execution.virtual_dataset.tenant:
            # Skip ABAC for platform admins
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                try:
                    self._check_abac_policy(
                        user_id=str(request.user.id),
                        tenant_id=str(execution.virtual_dataset.tenant_id),
                        resource_type="QUERY_EXECUTION",
                        resource_id=str(execution.id),
                        access_type="WRITE"
                    )
                except PermissionDenied:
                    logger.warning(
                        "abac_denied_query_execution_cancel",
                        extra={
                            "user_id": str(request.user.id),
                            "tenant_id": str(execution.virtual_dataset.tenant_id),
                            "execution_id": str(execution.id)
                        }
                    )
                    raise

        # Check if execution can be cancelled
        if not execution.can_cancel():
            return Response(
                {
                    'error': f'Query execution cannot be cancelled (current status: {execution.status})',
                    'execution_id': str(execution.id),
                    'status': execution.status
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Initialize service
        service = VirtualizationService(
            tenant_id=str(execution.virtual_dataset.tenant_id),
            user_id=str(request.user.id)
        )

        try:
            # Cancel execution - use the execution object we already have
            # The service method will handle job cancellation and event publishing
            from hub.apps.jobs.models import JobStatus
            from hub.apps.jobs.utils import decrement_tenant_job_counter

            # Store previous status
            previous_status = execution.status

            # Cancel the execution
            execution.mark_cancelled(reason="User requested cancellation via API")

            # If execution has a job, cancel the job as well
            if execution.job and execution.job.can_cancel():
                job_previous_status = execution.job.status
                execution.job.mark_cancelled()

                # If job was running, release tenant concurrency slot
                if job_previous_status == JobStatus.RUNNING and execution.virtual_dataset.tenant:
                    decrement_tenant_job_counter(
                        str(execution.virtual_dataset.tenant.id),
                        "running"
                    )

            # Publish cancellation event
            try:
                service.publish_query_execution_cancelled(
                    query_execution_id=str(execution.id),
                    virtual_dataset_id=str(execution.virtual_dataset.id),
                    tenant_id=str(execution.virtual_dataset.tenant_id),
                    user_id=str(request.user.id),
                    reason="User requested cancellation via API"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to publish query execution cancelled event: {e}",
                    extra={
                        "execution_id": str(execution.id),
                        "tenant_id": str(execution.virtual_dataset.tenant_id),
                        "error": str(e)
                    },
                    exc_info=True
                )

            # Log audit event
            try:
                create_audit_event(
                    resource_type="QUERY_EXECUTION",
                    action="QUERY_EXECUTION_CANCELLED",
                    actor_user=request.user,
                    tenant=execution.virtual_dataset.tenant,
                    resource_id=str(execution.id),
                    details={
                        "virtual_dataset_id": str(execution.virtual_dataset.id),
                        "virtual_dataset_name": execution.virtual_dataset.name,
                        "previous_status": previous_status,
                        "reason": "User requested cancellation via API"
                    },
                    request=request
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create audit event for query execution cancellation: {e}",
                    extra={
                        "execution_id": str(execution.id),
                        "tenant_id": str(execution.virtual_dataset.tenant_id),
                        "error": str(e)
                    },
                    exc_info=True
                )

            cancelled_execution = execution

            response = Response(
                QueryExecutionCancelResponseSerializer({
                    'execution_id': str(cancelled_execution.id),
                    'status': cancelled_execution.status,
                    'message': 'Query execution cancelled successfully'
                }).data,
                status=status.HTTP_200_OK
            )

            # Add rate limit headers
            _, rate_limit_results = check_rate_limit(request)
            headers = get_rate_limit_headers(request, rate_limit_results)
            for header, value in headers.items():
                response[header] = value

            return response

        except ValidationError as e:
            logger.warning(
                "Query execution cancellation failed",
                extra={
                    "execution_id": str(execution.id),
                    "tenant_id": str(execution.virtual_dataset.tenant_id),
                    "user_id": str(request.user.id),
                    "error": str(e),
                    "error_code": getattr(e, 'code', None)
                }
            )
            return Response(
                {'error': str(e), 'code': getattr(e, 'code', 'VALIDATION_ERROR')},
                status=status.HTTP_400_BAD_REQUEST
            )
        except NotFoundError as e:
            raise NotFound(str(e))
        except PermissionError as e:
            logger.warning(
                "Permission denied for query execution cancellation",
                extra={
                    "execution_id": str(execution.id),
                    "tenant_id": str(execution.virtual_dataset.tenant_id),
                    "user_id": str(request.user.id),
                    "error": str(e)
                }
            )
            return Response(
                {'error': str(e), 'code': 'PERMISSION_DENIED'},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.error(
                "Unexpected error during query execution cancellation",
                extra={
                    "execution_id": str(execution.id),
                    "tenant_id": str(execution.virtual_dataset.tenant_id),
                    "user_id": str(request.user.id),
                    "error": str(e)
                },
                exc_info=True
            )
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Get query execution result",
        description="Get the result of a completed query execution, with support for pagination and multiple formats.",
        responses={
            200: QueryExecutionResultSerializer,
            400: OpenApiResponse(description='Execution not completed'),
            404: OpenApiResponse(description='Execution not found'),
        },
        tags=["Virtualization"],
    )
    @action(detail=True, methods=['get'], url_path='result')
    def get_result(self, request, id=None):
        """
        Get query execution result.

        GET /api/v1/virtualization/queries/{id}/result/
        Query params: output_format (json|csv|parquet), page, page_size, offset, limit
        Note: Using 'output_format' instead of 'format' to avoid DRF content negotiation conflict
        """
        execution_id = id or request.parser_context.get('kwargs', {}).get('id')
        tenant = self.get_tenant_from_request()

        # Ensure user_id is provided
        if not request.user or not request.user.id:
            return Response(
                {'error': 'User authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id),
                    "tenant_id": str(tenant.id) if tenant else None,
                    "execution_id": execution_id
                }
            )
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        # Check if execution exists in another tenant first (for proper 403 vs 404)
        if execution_id and tenant:
            try:
                # Try to get execution without tenant filtering
                other_tenant_execution = QueryExecution.objects.select_related('virtual_dataset').get(id=execution_id)
                if str(other_tenant_execution.virtual_dataset.tenant_id) != str(tenant.id):
                    if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                        raise PermissionDenied("Cannot access query execution result from different tenant")
            except QueryExecution.DoesNotExist:
                pass  # Execution doesn't exist at all, will return 404 below

        # Try to get from tenant-scoped queryset
        try:
            execution = self.get_object()
        except NotFound:
            raise NotFound("Query execution not found")

        # ABAC check for read access
        if execution.virtual_dataset.tenant:
            # Skip ABAC for platform admins
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                try:
                    self._check_abac_policy(
                        user_id=str(request.user.id),
                        tenant_id=str(execution.virtual_dataset.tenant_id),
                        resource_type="QUERY_EXECUTION",
                        resource_id=str(execution.id),
                        access_type="READ"
                    )
                except PermissionDenied:
                    logger.warning(
                        "abac_denied_query_execution_result",
                        extra={
                            "user_id": str(request.user.id),
                            "tenant_id": str(execution.virtual_dataset.tenant_id),
                            "execution_id": str(execution.id)
                        }
                    )
                    raise

        # Initialize service
        service = VirtualizationService(
            tenant_id=str(execution.virtual_dataset.tenant_id),
            user_id=str(request.user.id)
        )

        try:
            # Get query parameters
            # Use 'output_format' to avoid conflict with DRF's 'format' parameter for content negotiation
            result_format = request.query_params.get('output_format') or request.query_params.get('format', 'json')
            result_format = result_format.lower()
            page = request.query_params.get('page')
            page_size = request.query_params.get('page_size')
            offset = request.query_params.get('offset')
            limit = request.query_params.get('limit')
            stream = request.query_params.get('stream', 'false').lower() == 'true'

            # Parse pagination parameters
            page_int = int(page) if page else None
            page_size_int = int(page_size) if page_size else None
            offset_int = int(offset) if offset else None
            limit_int = int(limit) if limit else None

            # Get result using service - pass execution object to avoid re-fetching
            result = service.get_query_result(
                execution_id=str(execution.id),
                tenant_id=str(execution.virtual_dataset.tenant_id),
                format=result_format,
                page=page_int,
                page_size=page_size_int,
                offset=offset_int,
                limit=limit_int,
                stream=stream,
                execution=execution  # Pass execution object to avoid re-fetching
            )

            # Log audit event
            try:
                create_audit_event(
                    resource_type="QUERY_EXECUTION",
                    action="QUERY_EXECUTION_RESULT_ACCESSED",
                    actor_user=request.user,
                    tenant=execution.virtual_dataset.tenant,
                    resource_id=str(execution.id),
                    details={
                        "virtual_dataset_id": str(execution.virtual_dataset.id),
                        "virtual_dataset_name": execution.virtual_dataset.name,
                        "format": result_format,
                        "status": execution.status
                    },
                    request=request
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create audit event for query execution result access: {e}",
                    extra={
                        "execution_id": str(execution.id),
                        "tenant_id": str(execution.virtual_dataset.tenant_id),
                        "error": str(e)
                    },
                    exc_info=True
                )

            # Create response with appropriate content type
            # For CSV and Parquet, return the data directly as string/bytes
            if result_format == 'csv':
                response = Response(
                    result.get('data', ''),
                    status=status.HTTP_200_OK,
                    content_type='text/csv'
                )
            elif result_format == 'parquet':
                # Parquet is base64 encoded in the result
                import base64
                parquet_data = result.get('data', '')
                if parquet_data:
                    response = Response(
                        base64.b64decode(parquet_data),
                        status=status.HTTP_200_OK,
                        content_type='application/parquet'
                    )
                else:
                    response = Response(
                        b'',
                        status=status.HTTP_200_OK,
                        content_type='application/parquet'
                    )
            else:
                # JSON format - use serializer
                response = Response(
                    QueryExecutionResultSerializer(result).data,
                    status=status.HTTP_200_OK,
                    content_type='application/json'
                )

            # Add rate limit headers
            _, rate_limit_results = check_rate_limit(request)
            headers = get_rate_limit_headers(request, rate_limit_results)
            for header, value in headers.items():
                response[header] = value

            return response

        except ValidationError as e:
            logger.warning(
                "Query result retrieval failed",
                extra={
                    "execution_id": str(execution.id),
                    "tenant_id": str(execution.virtual_dataset.tenant_id),
                    "user_id": str(request.user.id),
                    "error": str(e),
                    "error_code": getattr(e, 'code', None)
                }
            )
            # Include execution details in error response
            error_response = {
                'error': str(e),
                'code': getattr(e, 'code', 'VALIDATION_ERROR'),
                'execution_id': str(execution.id),
                'status': execution.status
            }
            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)
        except NotFoundError as e:
            raise NotFound(str(e))
        except PermissionError as e:
            logger.warning(
                "Permission denied for query result retrieval",
                extra={
                    "execution_id": str(execution.id),
                    "tenant_id": str(execution.virtual_dataset.tenant_id),
                    "user_id": str(request.user.id),
                    "error": str(e)
                }
            )
            return Response(
                {'error': str(e), 'code': 'PERMISSION_DENIED'},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.error(
                "Unexpected error during query result retrieval",
                extra={
                    "execution_id": str(execution.id),
                    "tenant_id": str(execution.virtual_dataset.tenant_id),
                    "user_id": str(request.user.id),
                    "error": str(e)
                },
                exc_info=True
            )
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Get query execution progress",
        description="Get real-time progress information for a query execution.",
        responses={
            200: QueryExecutionProgressSerializer,
            404: OpenApiResponse(description='Execution not found'),
        },
        tags=["Virtualization"],
    )
    @action(detail=True, methods=['get'], url_path='progress')
    def get_progress(self, request, id=None):
        """
        Get query execution progress.

        GET /api/v1/virtualization/queries/{id}/progress/
        """
        execution_id = id or request.parser_context.get('kwargs', {}).get('id')
        tenant = self.get_tenant_from_request()

        # Ensure user_id is provided
        if not request.user or not request.user.id:
            return Response(
                {'error': 'User authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id),
                    "tenant_id": str(tenant.id) if tenant else None,
                    "execution_id": execution_id
                }
            )
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        # Check if execution exists in another tenant first (for proper 403 vs 404)
        if execution_id and tenant:
            try:
                # Try to get execution without tenant filtering
                other_tenant_execution = QueryExecution.objects.select_related('virtual_dataset').get(id=execution_id)
                if str(other_tenant_execution.virtual_dataset.tenant_id) != str(tenant.id):
                    if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                        raise PermissionDenied("Cannot access query execution progress from different tenant")
            except QueryExecution.DoesNotExist:
                pass  # Execution doesn't exist at all, will return 404 below

        # Try to get from tenant-scoped queryset
        try:
            execution = self.get_object()
        except NotFound:
            raise NotFound("Query execution not found")

        # ABAC check for read access
        if execution.virtual_dataset.tenant:
            # Skip ABAC for platform admins
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                try:
                    self._check_abac_policy(
                        user_id=str(request.user.id),
                        tenant_id=str(execution.virtual_dataset.tenant_id),
                        resource_type="QUERY_EXECUTION",
                        resource_id=str(execution.id),
                        access_type="READ"
                    )
                except PermissionDenied:
                    logger.warning(
                        "abac_denied_query_execution_progress",
                        extra={
                            "user_id": str(request.user.id),
                            "tenant_id": str(execution.virtual_dataset.tenant_id),
                            "execution_id": str(execution.id)
                        }
                    )
                    raise

        # Calculate progress
        progress_percentage = None
        if execution.status == QueryExecutionStatus.COMPLETED:
            progress_percentage = 100.0
        elif execution.status == QueryExecutionStatus.FAILED:
            progress_percentage = 0.0
        elif execution.status == QueryExecutionStatus.RUNNING:
            # Estimate progress based on metrics if available
            if execution.metrics and 'progress_percentage' in execution.metrics:
                progress_percentage = execution.metrics['progress_percentage']
            elif execution.started_at:
                # Estimate based on elapsed time (rough estimate)
                elapsed = (timezone.now() - execution.started_at).total_seconds()
                # Assume average query takes 60 seconds (this is a rough estimate)
                estimated_total = 60.0
                progress_percentage = min(95.0, (elapsed / estimated_total) * 100.0)

        # Get latest logs (last 10 entries)
        latest_logs = None
        if execution.execution_log and isinstance(execution.execution_log, list):
            latest_logs = execution.execution_log[-10:]

        progress_data = {
            'execution_id': str(execution.id),
            'status': execution.status,
            'progress_percentage': progress_percentage,
            'started_at': execution.started_at,
            'completed_at': execution.completed_at,
            'duration_seconds': execution.get_duration_seconds(),
            'metrics': execution.metrics if execution.metrics else {},
            'latest_logs': latest_logs
        }

        # Log audit event
        try:
            create_audit_event(
                resource_type="QUERY_EXECUTION",
                action="QUERY_EXECUTION_PROGRESS_ACCESSED",
                actor_user=request.user,
                tenant=execution.virtual_dataset.tenant,
                resource_id=str(execution.id),
                details={
                    "virtual_dataset_id": str(execution.virtual_dataset.id),
                    "virtual_dataset_name": execution.virtual_dataset.name,
                    "status": execution.status,
                    "progress_percentage": progress_percentage
                },
                request=request
            )
        except Exception as e:
            logger.warning(
                f"Failed to create audit event for query execution progress access: {e}",
                extra={
                    "execution_id": str(execution.id),
                    "tenant_id": str(execution.virtual_dataset.tenant_id),
                    "error": str(e)
                },
                exc_info=True
            )

        response = Response(
            QueryExecutionProgressSerializer(progress_data).data,
            status=status.HTTP_200_OK
        )

        # Add rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)
        for header, value in headers.items():
            response[header] = value

        return response

    @extend_schema(
        summary="Stream query execution result",
        description="Stream query execution result using Server-Sent Events (SSE) for large datasets.",
        responses={
            200: OpenApiResponse(description='SSE stream'),
            400: OpenApiResponse(description='Execution not completed'),
            404: OpenApiResponse(description='Execution not found'),
        },
        tags=["Virtualization"],
    )
    @action(detail=True, methods=['get'], url_path='stream')
    def stream_result(self, request, id=None):
        """
        Stream query execution result using Server-Sent Events (SSE).

        GET /api/v1/virtualization/queries/{id}/stream/
        Query params: format (json|csv)
        """
        from django.http import StreamingHttpResponse
        import json
        import time

        execution_id = id or request.parser_context.get('kwargs', {}).get('id')
        tenant = self.get_tenant_from_request()

        # Ensure user_id is provided
        if not request.user or not request.user.id:
            return Response(
                {'error': 'User authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id),
                    "tenant_id": str(tenant.id) if tenant else None,
                    "execution_id": execution_id
                }
            )
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        # Check if execution exists in another tenant first (for proper 403 vs 404)
        if execution_id and tenant:
            try:
                # Try to get execution without tenant filtering
                other_tenant_execution = QueryExecution.objects.select_related('virtual_dataset').get(id=execution_id)
                if str(other_tenant_execution.virtual_dataset.tenant_id) != str(tenant.id):
                    if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                        raise PermissionDenied("Cannot stream query execution result from different tenant")
            except QueryExecution.DoesNotExist:
                pass  # Execution doesn't exist at all, will return 404 below

        # Try to get from tenant-scoped queryset
        try:
            execution = self.get_object()
        except NotFound:
            raise NotFound("Query execution not found")

        # ABAC check for read access
        if execution.virtual_dataset.tenant:
            # Skip ABAC for platform admins
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                try:
                    self._check_abac_policy(
                        user_id=str(request.user.id),
                        tenant_id=str(execution.virtual_dataset.tenant_id),
                        resource_type="QUERY_EXECUTION",
                        resource_id=str(execution.id),
                        access_type="READ"
                    )
                except PermissionDenied:
                    logger.warning(
                        "abac_denied_query_execution_stream",
                        extra={
                            "user_id": str(request.user.id),
                            "tenant_id": str(execution.virtual_dataset.tenant_id),
                            "execution_id": str(execution.id)
                        }
                    )
                    raise

        # Check execution status
        if execution.status != QueryExecutionStatus.COMPLETED:
            return Response(
                {
                    'error': f'Query execution is not completed (status: {execution.status})',
                    'execution_id': str(execution.id),
                    'status': execution.status
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get format parameter
        # Use 'output_format' to avoid conflict with DRF's 'format' parameter for content negotiation
        result_format = request.query_params.get('output_format') or request.query_params.get('format', 'json')
        result_format = result_format.lower()
        if result_format not in ['json', 'csv']:
            return Response(
                {'error': f'Unsupported format for streaming: {result_format}. Supported formats: json, csv'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Log audit event
        try:
            create_audit_event(
                resource_type="QUERY_EXECUTION",
                action="QUERY_EXECUTION_STREAM_STARTED",
                actor_user=request.user,
                tenant=execution.virtual_dataset.tenant,
                resource_id=str(execution.id),
                details={
                    "virtual_dataset_id": str(execution.virtual_dataset.id),
                    "virtual_dataset_name": execution.virtual_dataset.name,
                    "format": result_format,
                    "status": execution.status
                },
                request=request
            )
        except Exception as e:
            logger.warning(
                f"Failed to create audit event for query execution stream start: {e}",
                extra={
                    "execution_id": str(execution.id),
                    "tenant_id": str(execution.virtual_dataset.tenant_id),
                    "error": str(e)
                },
                exc_info=True
            )

        # Initialize service
        service = VirtualizationService(
            tenant_id=str(execution.virtual_dataset.tenant_id),
            user_id=str(request.user.id)
        )

        try:
            # Get full result (we'll stream it in chunks)
            result = service.get_query_result(
                execution_id=str(execution.id),
                tenant_id=str(execution.virtual_dataset.tenant_id),
                format=result_format,
                stream=False  # Get full result, we'll stream it ourselves
            )

            def generate_sse_stream():
                """Generate SSE stream for query results"""
                # Send initial metadata
                yield f"data: {json.dumps({'type': 'metadata', 'total_count': result['total_count'], 'format': result_format})}\n\n"

                # Stream data in chunks
                data = result.get('data', [])
                if isinstance(data, list):
                    # Stream JSON array
                    chunk_size = 100  # Stream 100 rows at a time
                    for i in range(0, len(data), chunk_size):
                        chunk = data[i:i + chunk_size]
                        yield f"data: {json.dumps({'type': 'data', 'chunk': chunk, 'offset': i, 'count': len(chunk)})}\n\n"
                        time.sleep(0.01)  # Small delay to prevent overwhelming the client
                elif isinstance(data, str):
                    # Stream CSV or other string format in chunks
                    chunk_size = 8192  # 8KB chunks
                    for i in range(0, len(data), chunk_size):
                        chunk = data[i:i + chunk_size]
                        yield f"data: {json.dumps({'type': 'data', 'chunk': chunk})}\n\n"
                        time.sleep(0.01)

                # Send completion signal
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"

            response = StreamingHttpResponse(
                generate_sse_stream(),
                content_type='text/event-stream'
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx
            return response

        except ValidationError as e:
            logger.warning(
                "Query result streaming failed",
                extra={
                    "execution_id": str(execution.id),
                    "tenant_id": str(execution.virtual_dataset.tenant_id),
                    "user_id": str(request.user.id),
                    "error": str(e),
                    "error_code": getattr(e, 'code', None)
                }
            )
            return Response(
                {'error': str(e), 'code': getattr(e, 'code', 'VALIDATION_ERROR')},
                status=status.HTTP_400_BAD_REQUEST
            )
        except NotFoundError as e:
            raise NotFound(str(e))
        except PermissionError as e:
            logger.warning(
                "Permission denied for query result streaming",
                extra={
                    "execution_id": str(execution.id),
                    "tenant_id": str(execution.virtual_dataset.tenant_id),
                    "user_id": str(request.user.id),
                    "error": str(e)
                }
            )
            return Response(
                {'error': str(e), 'code': 'PERMISSION_DENIED'},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.error(
                "Unexpected error during query result streaming",
                extra={
                    "execution_id": str(execution.id),
                    "tenant_id": str(execution.virtual_dataset.tenant_id),
                    "user_id": str(request.user.id),
                    "error": str(e)
                },
                exc_info=True
            )
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema_view(
    list=extend_schema(
        summary="Get virtualization topology",
        description="Get complete virtualization topology including all virtual datasets, relationships, and health metrics.",
        parameters=[
            OpenApiParameter(
                name='include_health_metrics',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Include health metrics in response (default: true)',
                required=False
            ),
        ],
        responses={
            200: VirtualizationTopologySerializer,
            400: OpenApiResponse(description='Bad request'),
        },
        tags=["Virtualization"],
    ),
    retrieve=extend_schema(
        summary="Get dataset topology",
        description="Get topology view for a specific virtual dataset including its relationships and health metrics.",
        responses={
            200: DatasetTopologySerializer,
            404: OpenApiResponse(description='Dataset not found'),
        },
        tags=["Virtualization"],
    ),
)
class VirtualizationTopologyViewSet(viewsets.ViewSet):
    """
    ViewSet for virtualization topology endpoints.

    Provides endpoints for:
    - Full virtualization topology (all datasets and relationships)
    - Dataset-specific topology
    - Health metrics

    Tenant-scoped: users can only see topology for virtual datasets in their tenant.
    Supports RBAC (role-based) and ABAC (attribute-based) authorization.
    Includes rate limiting and comprehensive audit logging.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        """Return appropriate permissions based on action"""
        # All topology endpoints are read-only, only require authentication
        return [permissions.IsAuthenticated()]

    def get_tenant_from_request(self):
        """Get tenant from request"""
        user = self.request.user

        # Try request.tenant_id first
        if hasattr(self.request, "tenant_id") and self.request.tenant_id:
            from hub.apps.tenants.models import Tenant
            try:
                return Tenant.objects.get(id=self.request.tenant_id)
            except Tenant.DoesNotExist:
                pass

        # Fallback to request.tenant object
        if hasattr(self.request, "tenant") and self.request.tenant:
            return self.request.tenant

        # Fallback to user.tenant
        if hasattr(user, "tenant") and user.tenant:
            return user.tenant

        return None

    def get_tenant_id_from_request(self):
        """Get tenant_id from request with proper fallback logic"""
        tenant = self.get_tenant_from_request()
        if tenant:
            return str(tenant.id)

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

        # Fallback to user.tenant_id
        user = self.request.user
        if hasattr(user, "id") and user.id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                db_user = User.objects.only('tenant_id').get(id=user.id)
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

    def list(self, request):
        """
        Get complete virtualization topology.

        GET /api/v1/virtualization/topology/
        Query params: include_health_metrics (default: true)
        """
        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": self.get_user_id_from_request(),
                    "tenant_id": self.get_tenant_id_from_request(),
                    "action": "topology.list"
                }
            )
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Get query parameters
        include_health_metrics = request.query_params.get("include_health_metrics", "true")
        include_health_metrics = include_health_metrics.lower() in ("true", "1", "yes")

        # Initialize service
        service = VirtualizationService(tenant_id=tenant_id, user_id=user_id)

        # Get topology
        try:
            topology = service.get_topology(
                tenant_id=tenant_id,
                include_health_metrics=include_health_metrics,
            )
        except ValidationError as e:
            raise DRFValidationError(str(e))

        # Log audit event
        try:
            tenant = self.get_tenant_from_request()
            create_audit_event(
                resource_type="VIRTUALIZATION_TOPOLOGY",
                action="TOPOLOGY_ACCESSED",
                actor_user=request.user,
                tenant=tenant,
                resource_id=None,
                details={
                    "dataset_count": topology["metadata"]["dataset_count"],
                    "relationship_count": topology["metadata"]["relationship_count"],
                    "include_health_metrics": include_health_metrics
                },
                request=request
            )
        except Exception as e:
            logger.warning(
                f"Failed to create audit event for topology access: {e}",
                extra={
                    "tenant_id": tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        serializer = VirtualizationTopologySerializer(topology)
        response = Response(serializer.data, headers=headers)

        return response

    def retrieve(self, request, pk=None):
        """
        Get topology for a specific virtual dataset.

        GET /api/v1/virtualization/topology/{dataset_id}/
        """
        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": self.get_user_id_from_request(),
                    "tenant_id": self.get_tenant_id_from_request(),
                    "action": "topology.retrieve",
                    "dataset_id": pk
                }
            )
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        # Get tenant_id and user_id
        tenant_id = self.get_tenant_id_from_request()
        user_id = self.get_user_id_from_request()

        if not tenant_id:
            raise DRFValidationError("Unable to determine tenant from request")

        # Get dataset
        dataset = None
        try:
            dataset = VirtualDataset.objects.get(id=pk, tenant_id=tenant_id)
        except VirtualDataset.DoesNotExist:
            # Check if dataset exists in another tenant (for proper 403 vs 404)
            try:
                other_tenant_dataset = VirtualDataset.objects.get(id=pk)
                if str(other_tenant_dataset.tenant_id) != str(tenant_id):
                    # Allow platform admin to access datasets from other tenants
                    if hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin:
                        dataset = other_tenant_dataset
                        # Update tenant_id to the dataset's tenant for topology generation
                        tenant_id = str(other_tenant_dataset.tenant_id)
                    else:
                        raise PermissionDenied("Cannot access virtual dataset topology from different tenant")
            except VirtualDataset.DoesNotExist:
                raise NotFound("Virtual dataset not found")

        if not dataset:
            raise NotFound("Virtual dataset not found")

        # Check tenant isolation
        tenant = self.get_tenant_from_request()
        if tenant and str(dataset.tenant_id) != str(tenant.id):
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                raise PermissionDenied("Cannot access virtual dataset topology from different tenant")

        # ABAC check for read access
        if dataset.tenant:
            # Skip ABAC for platform admins
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                try:
                    result = ABACEngine.evaluate_access(
                        user_id=str(request.user.id),
                        tenant_id=str(dataset.tenant_id),
                        resource_type="VIRTUAL_DATASET",
                        resource_id=str(dataset.id),
                        access_type="READ"
                    )

                    if not result.allowed:
                        # If a policy explicitly denied access, raise PermissionDenied
                        if result.policy:
                            policy_name = result.policy.name if result.policy else "Unknown Policy"
                            raise PermissionDenied(
                                f"ABAC policy '{policy_name}' denies READ access to VIRTUAL_DATASET {dataset.id}"
                            )
                except PermissionDenied:
                    raise
                except Exception as e:
                    logger.warning(
                        "abac_check_failed",
                        extra={
                            "user_id": str(request.user.id),
                            "tenant_id": str(dataset.tenant_id),
                            "resource_type": "VIRTUAL_DATASET",
                            "resource_id": str(dataset.id),
                            "access_type": "READ",
                            "error": str(e)
                        },
                        exc_info=True
                    )
                    # On ABAC engine failure, allow access (fail open) but log the error

        # Initialize service and get full topology
        service = VirtualizationService(tenant_id=tenant_id, user_id=user_id)
        topology = service.get_topology(
            tenant_id=tenant_id,
            include_health_metrics=True,
        )

        # Find dataset node
        dataset_node = None
        for node in topology["nodes"]:
            if node["id"] == str(dataset.id):
                dataset_node = node
                break

        if not dataset_node:
            raise NotFound("Virtual dataset not found in topology")

        # Find relationships for this dataset
        dataset_relationships = [
            edge
            for edge in topology["edges"]
            if edge["source"] == str(dataset.id) or edge["target"] == str(dataset.id)
        ]

        # Build response
        response_data = {
            "dataset": dataset_node,
            "relationships": dataset_relationships,
            "health_metrics": dataset_node.get("health_metrics"),
        }

        # Log audit event
        try:
            create_audit_event(
                resource_type="VIRTUALIZATION_TOPOLOGY",
                action="DATASET_TOPOLOGY_ACCESSED",
                actor_user=request.user,
                tenant=dataset.tenant,
                resource_id=str(dataset.id),
                details={
                    "dataset_id": str(dataset.id),
                    "dataset_name": dataset.name,
                    "relationship_count": len(dataset_relationships)
                },
                request=request
            )
        except Exception as e:
            logger.warning(
                f"Failed to create audit event for dataset topology access: {e}",
                extra={
                    "dataset_id": str(dataset.id),
                    "tenant_id": str(dataset.tenant_id),
                    "error": str(e)
                },
                exc_info=True
            )

        # Get rate limit headers
        _, rate_limit_results = check_rate_limit(request)
        headers = get_rate_limit_headers(request, rate_limit_results)

        # Serialize response
        serializer = DatasetTopologySerializer(response_data)
        response = Response(serializer.data, headers=headers)

        return response

