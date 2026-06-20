"""
Marketplace Integration Views

REST API views for marketplace connection management.
"""

import time

import structlog
from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.auth.permissions import HasAnyRole, HasScope
from hub.apps.core.services.base import ConflictError, NotFoundError, ValidationError
from hub.apps.rate_limiting.service import check_rate_limit, get_rate_limit_headers

from .base import MarketplaceType, SyncDirection
from .factory import MarketplaceConnectorFactory
from .models import MarketplaceConnection, MarketplaceMapping, MarketplaceSyncJob
from .serializers import (
    MarketplaceConnectionCreateSerializer,
    MarketplaceConnectionSerializer,
    MarketplaceConnectionTestResponseSerializer,
    MarketplaceConnectionUpdateSerializer,
    MarketplaceMappingSerializer,
    MarketplaceSyncJobCancelSerializer,
    MarketplaceSyncJobSerializer,
    MarketplaceSyncRequestSerializer,
)
from .services import MarketplaceIntegrationService

logger = structlog.get_logger(__name__)


class MarketplaceIntegrationMixin:
    """
    Shared helper methods for marketplace integration ViewSets.

    Provides tenant/user ID resolution common across MarketplaceConnectionViewSet,
    MarketplaceSyncJobViewSet, and MarketplaceMappingViewSet.
    """

    def _get_tenant_id(self, request):
        """Get tenant ID from request user"""
        user = request.user

        # Try request.tenant_id first
        if hasattr(request, "tenant_id") and request.tenant_id:
            tenant_id = request.tenant_id
            if isinstance(tenant_id, str):
                import uuid

                try:
                    return uuid.UUID(tenant_id)
                except (ValueError, TypeError):
                    pass

        # Fallback to request.tenant object
        if hasattr(request, "tenant") and request.tenant:
            return request.tenant.id

        # Fallback to user.tenant_id
        if hasattr(user, "tenant_id") and user.tenant_id:
            return user.tenant_id

        # Last resort: get from user.tenant relationship
        if hasattr(user, "tenant") and user.tenant:
            return user.tenant.id

        return None

    def _get_user_id(self, request):
        """Get user ID from request"""
        if request.user and hasattr(request.user, "id"):
            return str(request.user.id)
        return None

    def _resolve_queryset_tenant(self, request, model_class):
        """
        Resolve tenant-scoped queryset for the given model.

        Returns a queryset filtered by tenant (or empty queryset if no tenant
        can be determined).  Platform admins bypass tenant scoping.
        """
        user = request.user

        # Platform admins can see all records
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return model_class.objects.all()

        # Get tenant from request (set by middleware/authentication) or user
        tenant_id = None

        # Try request.tenant_id first (set by authentication/middleware)
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

        # Fallback to user.tenant_id (direct field access)
        if not tenant_id and hasattr(user, "id") and user.id:
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

        # Regular users can only see records in their tenant
        if tenant_id:
            if isinstance(tenant_id, str):
                import uuid

                try:
                    tenant_id = uuid.UUID(tenant_id)
                except (ValueError, TypeError):
                    return model_class.objects.none()
            return model_class.objects.filter(tenant_id=tenant_id)

        return model_class.objects.none()


@extend_schema_view(
    list=extend_schema(
        summary="List marketplace connections",
        description="List all marketplace connections for the authenticated user's tenant with filtering, pagination, and search.",
        parameters=[
            OpenApiParameter(
                name="marketplace_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by marketplace type (e.g., SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE)",
                required=False,
            ),
            OpenApiParameter(
                name="is_active",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Filter by active status (true/false)",
                required=False,
            ),
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Search in connection name",
                required=False,
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Order by field (e.g., name, -created_at). Prefix with - for descending.",
                required=False,
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Page number (default: 1)",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Items per page (default: 50, max: 100)",
                required=False,
            ),
        ],
        tags=["Integrations"],
    ),
    retrieve=extend_schema(
        summary="Get marketplace connection details",
        description="Get detailed information about a specific marketplace connection.",
        tags=["Integrations"],
    ),
    create=extend_schema(
        summary="Create marketplace connection",
        description="Create a new marketplace connection. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.",
        tags=["Integrations"],
    ),
    update=extend_schema(
        summary="Update marketplace connection",
        description="Update an existing marketplace connection. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.",
        tags=["Integrations"],
    ),
    partial_update=extend_schema(
        summary="Partially update marketplace connection",
        description="Partially update an existing marketplace connection. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.",
        tags=["Integrations"],
    ),
    destroy=extend_schema(
        summary="Delete marketplace connection",
        description="Delete a marketplace connection. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.",
        tags=["Integrations"],
    ),
)
class MarketplaceConnectionViewSet(MarketplaceIntegrationMixin, viewsets.ModelViewSet):
    """
    ViewSet for marketplace connection management.

    Tenant-scoped: users can only see/manage connections in their tenant.
    Supports RBAC (role-based) and ABAC (attribute-based) authorization.
    Includes rate limiting, comprehensive filtering, pagination, and audit logging.
    """

    queryset = MarketplaceConnection.objects.all()
    serializer_class = MarketplaceConnectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def initial(self, request, *args, **kwargs):
        # Run DRF auth/permission/throttle checks FIRST so unauthenticated
        # requests receive 401 (NotAuthenticated) instead of 403 from the
        # feature-flag gate below. The feature flag is only meaningful for
        # authenticated tenants.
        super().initial(request, *args, **kwargs)

        from rest_framework.exceptions import PermissionDenied

        from hub.apps.tenants.feature_flag_gates import check_marketplace_integrations_enabled

        result = check_marketplace_integrations_enabled(request)
        if isinstance(result, Response):
            raise PermissionDenied(detail=result.data)

    filter_backends = [OrderingFilter, SearchFilter]
    ordering_fields = ["name", "marketplace_type", "is_active", "created_at", "updated_at"]
    ordering = ["-created_at"]  # Default ordering
    search_fields = ["name"]
    pagination_class = StandardPageNumberPagination

    def get_permissions(self):
        """Return appropriate permissions based on action"""
        write_actions = ["create", "update", "partial_update", "destroy", "test"]
        if self.action in write_actions:
            # Write operations require DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope
            return [
                permissions.IsAuthenticated(),
                HasAnyRole(["DATA_PROVIDER", "TENANT_ADMIN"]),
                HasScope("integrations:write"),
            ]
        # Read operations only require authentication
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return MarketplaceConnectionCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return MarketplaceConnectionUpdateSerializer
        elif self.action == "test":
            return MarketplaceConnectionTestResponseSerializer
        return MarketplaceConnectionSerializer

    def get_queryset(self):
        """Filter queryset based on user permissions and tenant isolation"""
        queryset = self._resolve_queryset_tenant(self.request, MarketplaceConnection)

        # Apply filters
        marketplace_type_filter = self.request.query_params.get("marketplace_type")
        if marketplace_type_filter:
            queryset = queryset.filter(marketplace_type=marketplace_type_filter)

        is_active_filter = self.request.query_params.get("is_active")
        if is_active_filter is not None:
            is_active_bool = is_active_filter.lower() in ("true", "1", "yes")
            queryset = queryset.filter(is_active=is_active_bool)

        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new marketplace connection.

        POST /api/v1/integrations/marketplace/connections/
        """
        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id) if request.user else None,
                    "tenant_id": str(self._get_tenant_id(request))
                    if self._get_tenant_id(request)
                    else None,
                    "endpoint": "marketplace_connection_create",
                },
            )
            from rest_framework.exceptions import Throttled

            limiting_result = next(
                (r for r in rate_limit_results if not r.allowed),
                rate_limit_results[0] if rate_limit_results else None,
            )
            reset_time = limiting_result.reset_time if limiting_result else None
            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            exception.headers = headers
            raise exception

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant_id = self._get_tenant_id(request)
        user_id = self._get_user_id(request)

        if not tenant_id:
            return Response(
                {"error": "User must belong to a tenant"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not user_id:
            return Response(
                {"error": "User authentication required"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            # Create service instance
            service = MarketplaceIntegrationService(
                tenant_id=str(tenant_id), user_id=user_id, request_id=getattr(request, "id", None)
            )

            # Create connection
            connection = service.create_connection(
                tenant_id=str(tenant_id),
                user_id=user_id,
                marketplace_type=serializer.validated_data["marketplace_type"],
                name=serializer.validated_data["name"],
                config=serializer.validated_data["config"],
                is_active=serializer.validated_data.get("is_active", True),
                request=request,
            )

            # Return serialized connection
            response_serializer = MarketplaceConnectionSerializer(connection)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            logger.warning(
                "marketplace_connection_validation_error",
                error=str(e),
                details=getattr(e, "details", {}),
                extra={
                    "user_id": user_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return Response(
                {
                    "error": str(e),
                    "code": getattr(e, "code", "VALIDATION_ERROR"),
                    "details": getattr(e, "details", {}),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ConflictError as e:
            logger.warning(
                "marketplace_connection_conflict",
                error=str(e),
                details=getattr(e, "details", {}),
                extra={
                    "user_id": user_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return Response(
                {"error": str(e), "details": getattr(e, "details", {})},
                status=status.HTTP_409_CONFLICT,
            )
        except NotFoundError as e:
            logger.warning(
                "marketplace_connection_not_found",
                error=str(e),
                extra={
                    "user_id": user_id,
                    "tenant_id": str(tenant_id),
                },
            )
            raise NotFound(str(e))
        except Exception as e:
            logger.error(
                "marketplace_connection_create_error",
                error=str(e),
                exc_info=True,
                extra={
                    "user_id": user_id,
                    "tenant_id": str(tenant_id),
                },
            )
            raise DRFValidationError(f"Failed to create marketplace connection: {e!s}")

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a marketplace connection.

        GET /api/v1/integrations/marketplace/connections/{id}/
        """
        instance = self.get_object()

        # Verify tenant isolation
        tenant_id = self._get_tenant_id(request)
        if tenant_id and str(instance.tenant_id) != str(tenant_id):
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                raise PermissionDenied("Cannot access connection from different tenant")

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update a marketplace connection.

        PUT /api/v1/integrations/marketplace/connections/{id}/
        """
        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id) if request.user else None,
                    "tenant_id": str(self._get_tenant_id(request))
                    if self._get_tenant_id(request)
                    else None,
                    "endpoint": "marketplace_connection_update",
                },
            )
            from rest_framework.exceptions import Throttled

            limiting_result = next(
                (r for r in rate_limit_results if not r.allowed),
                rate_limit_results[0] if rate_limit_results else None,
            )
            reset_time = limiting_result.reset_time if limiting_result else None
            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            exception.headers = headers
            raise exception

        instance = self.get_object()

        # Verify tenant isolation
        tenant_id = self._get_tenant_id(request)
        if tenant_id and str(instance.tenant_id) != str(tenant_id):
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                raise PermissionDenied("Cannot update connection from different tenant")

        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = self._get_user_id(request)
        if not user_id:
            return Response(
                {"error": "User authentication required"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            # Create service instance
            service = MarketplaceIntegrationService(
                tenant_id=str(instance.tenant_id),
                user_id=user_id,
                request_id=getattr(request, "id", None),
            )

            # Prepare update data
            update_data = {}
            if "name" in serializer.validated_data:
                update_data["name"] = serializer.validated_data["name"]
            if "config" in serializer.validated_data:
                update_data["config"] = serializer.validated_data["config"]
            if "is_active" in serializer.validated_data:
                update_data["is_active"] = serializer.validated_data["is_active"]

            # Update connection
            connection = service.update_connection(
                connection_id=str(instance.id),
                tenant_id=str(instance.tenant_id),
                user_id=user_id,
                **update_data,
                request=request,
            )

            # Return serialized connection
            response_serializer = MarketplaceConnectionSerializer(connection)
            return Response(response_serializer.data)

        except ValidationError as e:
            logger.warning(
                "marketplace_connection_update_validation_error",
                error=str(e),
                details=getattr(e, "details", {}),
                extra={
                    "connection_id": str(instance.id),
                    "user_id": user_id,
                },
            )
            raise DRFValidationError({"error": str(e), "details": getattr(e, "details", {})})
        except NotFoundError as e:
            logger.warning(
                "marketplace_connection_update_not_found",
                error=str(e),
                extra={
                    "connection_id": str(instance.id),
                    "user_id": user_id,
                },
            )
            raise NotFound(str(e))
        except ConflictError as e:
            logger.warning(
                "marketplace_connection_update_conflict",
                error=str(e),
                details=getattr(e, "details", {}),
                extra={
                    "connection_id": str(instance.id),
                    "user_id": user_id,
                },
            )
            return Response(
                {"error": str(e), "details": getattr(e, "details", {})},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            logger.error(
                "marketplace_connection_update_error",
                error=str(e),
                exc_info=True,
                extra={
                    "connection_id": str(instance.id),
                    "user_id": user_id,
                },
            )
            raise DRFValidationError(f"Failed to update marketplace connection: {e!s}")

    def partial_update(self, request, *args, **kwargs):
        """
        Partially update a marketplace connection.

        PATCH /api/v1/integrations/marketplace/connections/{id}/
        """
        # Same as update, but serializer handles partial=True
        return self.update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a marketplace connection.

        DELETE /api/v1/integrations/marketplace/connections/{id}/
        """
        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id) if request.user else None,
                    "tenant_id": str(self._get_tenant_id(request))
                    if self._get_tenant_id(request)
                    else None,
                    "endpoint": "marketplace_connection_delete",
                },
            )
            from rest_framework.exceptions import Throttled

            limiting_result = next(
                (r for r in rate_limit_results if not r.allowed),
                rate_limit_results[0] if rate_limit_results else None,
            )
            reset_time = limiting_result.reset_time if limiting_result else None
            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            exception.headers = headers
            raise exception

        instance = self.get_object()

        # Verify tenant isolation
        tenant_id = self._get_tenant_id(request)
        if tenant_id and str(instance.tenant_id) != str(tenant_id):
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                raise PermissionDenied("Cannot delete connection from different tenant")

        user_id = self._get_user_id(request)
        if not user_id:
            return Response(
                {"error": "User authentication required"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            # Create service instance
            service = MarketplaceIntegrationService(
                tenant_id=str(instance.tenant_id),
                user_id=user_id,
                request_id=getattr(request, "id", None),
            )

            # Delete connection
            service.delete_connection(
                connection_id=str(instance.id),
                tenant_id=str(instance.tenant_id),
                user_id=user_id,
                request=request,
            )

            return Response(status=status.HTTP_204_NO_CONTENT)

        except NotFoundError as e:
            logger.warning(
                "marketplace_connection_delete_not_found",
                error=str(e),
                extra={
                    "connection_id": str(instance.id),
                    "user_id": user_id,
                },
            )
            raise NotFound(str(e))
        except Exception as e:
            logger.error(
                "marketplace_connection_delete_error",
                error=str(e),
                exc_info=True,
                extra={
                    "connection_id": str(instance.id),
                    "user_id": user_id,
                },
            )
            raise DRFValidationError(f"Failed to delete marketplace connection: {e!s}")

    @extend_schema(
        summary="Test marketplace connection",
        description="Test a marketplace connection by verifying credentials and connectivity. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.",
        request=None,
        responses={
            200: MarketplaceConnectionTestResponseSerializer,
            400: OpenApiResponse(description="Bad request"),
            404: OpenApiResponse(description="Connection not found"),
            429: OpenApiResponse(description="Rate limit exceeded"),
        },
        tags=["Integrations"],
    )
    @action(detail=True, methods=["post"], url_path="test")
    @transaction.atomic
    def test(self, request, id=None):
        """
        Test a marketplace connection.

        POST /api/v1/integrations/marketplace/connections/{id}/test/
        """
        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id) if request.user else None,
                    "tenant_id": str(self._get_tenant_id(request))
                    if self._get_tenant_id(request)
                    else None,
                    "endpoint": "marketplace_connection_test",
                },
            )
            from rest_framework.exceptions import Throttled

            limiting_result = next(
                (r for r in rate_limit_results if not r.allowed),
                rate_limit_results[0] if rate_limit_results else None,
            )
            reset_time = limiting_result.reset_time if limiting_result else None
            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            exception.headers = headers
            raise exception

        instance = self.get_object()

        # Verify tenant isolation
        tenant_id = self._get_tenant_id(request)
        if tenant_id and str(instance.tenant_id) != str(tenant_id):
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                raise PermissionDenied("Cannot test connection from different tenant")

        user_id = self._get_user_id(request)
        if not user_id:
            return Response(
                {"error": "User authentication required"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            # Create service instance
            service = MarketplaceIntegrationService(
                tenant_id=str(instance.tenant_id),
                user_id=user_id,
                request_id=getattr(request, "id", None),
            )

            # Test connection
            test_result = service.test_connection(
                connection_id=str(instance.id),
                tenant_id=str(instance.tenant_id),
                user_id=user_id,
                request=request,
            )

            # Return serialized test result
            serializer = MarketplaceConnectionTestResponseSerializer(
                {
                    "success": test_result.get("success", False),
                    "message": test_result.get("message", ""),
                    "error": test_result.get("error"),
                    "tested_at": test_result.get("tested_at"),
                    "connection_id": instance.id,
                }
            )
            return Response(serializer.data, status=status.HTTP_200_OK)

        except NotFoundError as e:
            logger.warning(
                "marketplace_connection_test_not_found",
                error=str(e),
                extra={
                    "connection_id": str(instance.id),
                    "user_id": user_id,
                },
            )
            raise NotFound(str(e))
        except ValidationError as e:
            logger.warning(
                "marketplace_connection_test_validation_error",
                error=str(e),
                details=getattr(e, "details", {}),
                extra={
                    "connection_id": str(instance.id),
                    "user_id": user_id,
                },
            )
            return Response(
                {"error": str(e), "details": getattr(e, "details", {})},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(
                "marketplace_connection_test_error",
                error=str(e),
                exc_info=True,
                extra={
                    "connection_id": str(instance.id),
                    "user_id": user_id,
                },
            )
            return Response(
                {"error": f"Failed to test marketplace connection: {e!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    list=extend_schema(
        summary="List marketplace sync jobs",
        description="List all marketplace sync jobs for the authenticated user's tenant with filtering, pagination, and search.",
        parameters=[
            OpenApiParameter(
                name="connection_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Filter by connection ID",
                required=False,
            ),
            OpenApiParameter(
                name="direction",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by sync direction (PUSH, PULL, BIDIRECTIONAL)",
                required=False,
            ),
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by sync status (PENDING, RUNNING, COMPLETED, FAILED, PARTIAL)",
                required=False,
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Order by field (e.g., created_at, -created_at). Prefix with - for descending.",
                required=False,
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Page number (default: 1)",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Items per page (default: 50, max: 100)",
                required=False,
            ),
        ],
        tags=["Integrations"],
    ),
    retrieve=extend_schema(
        summary="Get marketplace sync job details",
        description="Get detailed information about a specific marketplace sync job.",
        tags=["Integrations"],
    ),
    create=extend_schema(
        summary="Create marketplace sync job",
        description="Create a new marketplace sync job. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.",
        tags=["Integrations"],
    ),
)
class MarketplaceSyncJobViewSet(MarketplaceIntegrationMixin, viewsets.ModelViewSet):
    """
    ViewSet for marketplace sync job management.

    Tenant-scoped: users can only see/manage sync jobs in their tenant.
    Supports RBAC (role-based) and ABAC (attribute-based) authorization.
    Includes rate limiting, comprehensive filtering, pagination, and audit logging.
    """

    queryset = MarketplaceSyncJob.objects.all()
    serializer_class = MarketplaceSyncJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at", "updated_at", "completed_at", "status", "direction"]
    ordering = ["-created_at"]  # Default ordering
    pagination_class = StandardPageNumberPagination

    def get_permissions(self):
        """Return appropriate permissions based on action"""
        write_actions = ["create", "cancel"]
        if self.action in write_actions:
            # Write operations require DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope
            return [
                permissions.IsAuthenticated(),
                HasAnyRole(["DATA_PROVIDER", "TENANT_ADMIN"]),
                HasScope("integrations:write"),
            ]
        # Read operations only require authentication
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return MarketplaceSyncRequestSerializer
        elif self.action == "cancel":
            return MarketplaceSyncJobCancelSerializer
        return MarketplaceSyncJobSerializer

    def get_queryset(self):
        """Filter queryset based on user permissions and tenant isolation"""
        queryset = self._resolve_queryset_tenant(self.request, MarketplaceSyncJob)

        # Apply filters
        connection_id_filter = self.request.query_params.get("connection_id")
        if connection_id_filter:
            try:
                import uuid

                connection_uuid = uuid.UUID(connection_id_filter)
                queryset = queryset.filter(connection_id=connection_uuid)
            except (ValueError, TypeError):
                return MarketplaceSyncJob.objects.none()

        direction_filter = self.request.query_params.get("direction")
        if direction_filter:
            valid_directions = [sd.value for sd in SyncDirection]
            if direction_filter in valid_directions:
                queryset = queryset.filter(direction=direction_filter)
            else:
                return MarketplaceSyncJob.objects.none()

        status_filter = self.request.query_params.get("status")
        if status_filter:
            from .base import SyncStatus

            valid_statuses = [ss.value for ss in SyncStatus]
            if status_filter in valid_statuses:
                queryset = queryset.filter(status=status_filter)
            else:
                return MarketplaceSyncJob.objects.none()

        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new marketplace sync job.

        POST /api/v1/integrations/marketplace/sync/
        """
        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id) if request.user else None,
                    "tenant_id": str(self._get_tenant_id(request))
                    if self._get_tenant_id(request)
                    else None,
                    "endpoint": "marketplace_sync_create",
                },
            )
            from rest_framework.exceptions import Throttled

            limiting_result = next(
                (r for r in rate_limit_results if not r.allowed),
                rate_limit_results[0] if rate_limit_results else None,
            )
            reset_time = limiting_result.reset_time if limiting_result else None
            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            exception.headers = headers
            raise exception

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant_id = self._get_tenant_id(request)
        user_id = self._get_user_id(request)

        if not tenant_id:
            return Response(
                {"error": "User must belong to a tenant"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not user_id:
            return Response(
                {"error": "User authentication required"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            # Create service instance
            service = MarketplaceIntegrationService(
                tenant_id=str(tenant_id), user_id=user_id, request_id=getattr(request, "id", None)
            )

            connection_id = str(serializer.validated_data["connection_id"])
            direction = serializer.validated_data["direction"]
            asset_ids = serializer.validated_data.get("asset_ids")
            listing_ids = serializer.validated_data.get("listing_ids")
            filters = serializer.validated_data.get("filters")
            options = serializer.validated_data.get("options")

            # Create sync job based on direction
            if direction == SyncDirection.PUSH.value:
                # PUSH: sync assets to marketplace
                if not asset_ids:
                    return Response(
                        {"error": "asset_ids is required for PUSH direction"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                sync_job = service.sync_assets_to_marketplace(
                    connection_id=connection_id,
                    tenant_id=str(tenant_id),
                    user_id=user_id,
                    asset_ids=[str(aid) for aid in asset_ids],
                    options=options,
                    request=request,
                )
            elif direction == SyncDirection.PULL.value:
                # PULL: sync from marketplace
                sync_job = service.sync_from_marketplace(
                    connection_id=connection_id,
                    tenant_id=str(tenant_id),
                    user_id=user_id,
                    listing_ids=[str(lid) for lid in listing_ids] if listing_ids else None,
                    filters=filters,
                    options=options,
                    request=request,
                )
            else:
                # BIDIRECTIONAL: not yet supported via API
                return Response(
                    {"error": "BIDIRECTIONAL sync is not yet supported via API"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Return serialized sync job
            response_serializer = MarketplaceSyncJobSerializer(sync_job)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            logger.warning(
                "marketplace_sync_validation_error",
                error=str(e),
                details=getattr(e, "details", {}),
                extra={
                    "user_id": user_id,
                    "tenant_id": str(tenant_id),
                },
            )
            raise DRFValidationError({"error": str(e), "details": getattr(e, "details", {})})
        except NotFoundError as e:
            logger.warning(
                "marketplace_sync_not_found",
                error=str(e),
                extra={
                    "user_id": user_id,
                    "tenant_id": str(tenant_id),
                },
            )
            raise NotFound(str(e))
        except Exception as e:
            logger.error(
                "marketplace_sync_create_error",
                error=str(e),
                exc_info=True,
                extra={
                    "user_id": user_id,
                    "tenant_id": str(tenant_id),
                },
            )
            raise DRFValidationError(f"Failed to create marketplace sync job: {e!s}")

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a marketplace sync job.

        GET /api/v1/integrations/marketplace/sync/{id}/
        """
        instance = self.get_object()

        # Verify tenant isolation
        tenant_id = self._get_tenant_id(request)
        if tenant_id and str(instance.tenant_id) != str(tenant_id):
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                raise PermissionDenied("Cannot access sync job from different tenant")

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @extend_schema(
        summary="Cancel marketplace sync job",
        description="Cancel a running marketplace sync job. Only jobs in PENDING or RUNNING status can be cancelled. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.",
        request=MarketplaceSyncJobCancelSerializer,
        responses={
            200: MarketplaceSyncJobSerializer,
            400: OpenApiResponse(description="Bad request - job cannot be cancelled"),
            404: OpenApiResponse(description="Sync job not found"),
            429: OpenApiResponse(description="Rate limit exceeded"),
        },
        tags=["Integrations"],
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    @transaction.atomic
    def cancel(self, request, id=None):
        """
        Cancel a marketplace sync job.

        POST /api/v1/integrations/marketplace/sync/{id}/cancel/
        """
        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id) if request.user else None,
                    "tenant_id": str(self._get_tenant_id(request))
                    if self._get_tenant_id(request)
                    else None,
                    "endpoint": "marketplace_sync_cancel",
                },
            )
            from rest_framework.exceptions import Throttled

            limiting_result = next(
                (r for r in rate_limit_results if not r.allowed),
                rate_limit_results[0] if rate_limit_results else None,
            )
            reset_time = limiting_result.reset_time if limiting_result else None
            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            exception.headers = headers
            raise exception

        instance = self.get_object()

        # Verify tenant isolation
        tenant_id = self._get_tenant_id(request)
        if tenant_id and str(instance.tenant_id) != str(tenant_id):
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                raise PermissionDenied("Cannot cancel sync job from different tenant")

        serializer = MarketplaceSyncJobCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = self._get_user_id(request)
        if not user_id:
            return Response(
                {"error": "User authentication required"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            # Create service instance
            service = MarketplaceIntegrationService(
                tenant_id=str(instance.tenant_id),
                user_id=user_id,
                request_id=getattr(request, "id", None),
            )

            # Cancel sync job
            sync_job = service.cancel_sync_job(
                sync_job_id=str(instance.id),
                tenant_id=str(instance.tenant_id),
                user_id=user_id,
                reason=serializer.validated_data.get("reason"),
                request=request,
            )

            # Return serialized sync job
            response_serializer = MarketplaceSyncJobSerializer(sync_job)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except NotFoundError as e:
            logger.warning(
                "marketplace_sync_cancel_not_found",
                error=str(e),
                extra={
                    "sync_job_id": str(instance.id),
                    "user_id": user_id,
                },
            )
            raise NotFound(str(e))
        except ValidationError as e:
            logger.warning(
                "marketplace_sync_cancel_validation_error",
                error=str(e),
                details=getattr(e, "details", {}),
                extra={
                    "sync_job_id": str(instance.id),
                    "user_id": user_id,
                },
            )
            return Response(
                {"error": str(e), "details": getattr(e, "details", {})},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(
                "marketplace_sync_cancel_error",
                error=str(e),
                exc_info=True,
                extra={
                    "sync_job_id": str(instance.id),
                    "user_id": user_id,
                },
            )
            return Response(
                {"error": f"Failed to cancel marketplace sync job: {e!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    list=extend_schema(
        summary="List marketplace mappings",
        description="List all marketplace mappings for the authenticated user's tenant with filtering, pagination, and search.",
        parameters=[
            OpenApiParameter(
                name="connection_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Filter by connection ID",
                required=False,
            ),
            OpenApiParameter(
                name="hub_asset_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Filter by hub asset ID",
                required=False,
            ),
            OpenApiParameter(
                name="external_listing_id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by external listing ID",
                required=False,
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Order by field (e.g., created_at, -created_at, external_listing_id). Prefix with - for descending.",
                required=False,
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Page number (default: 1)",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Items per page (default: 50, max: 100)",
                required=False,
            ),
        ],
        tags=["Integrations"],
    ),
    retrieve=extend_schema(
        summary="Get marketplace mapping details",
        description="Get detailed information about a specific marketplace mapping.",
        tags=["Integrations"],
    ),
    destroy=extend_schema(
        summary="Delete marketplace mapping",
        description="Delete a marketplace mapping. Requires DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope.",
        tags=["Integrations"],
    ),
)
class MarketplaceMappingViewSet(MarketplaceIntegrationMixin, viewsets.ModelViewSet):
    """
    ViewSet for marketplace mapping management.

    Tenant-scoped: users can only see/manage mappings in their tenant.
    Supports RBAC (role-based) and ABAC (attribute-based) authorization.
    Includes rate limiting, comprehensive filtering, pagination, and audit logging.

    Only GET (list/retrieve) and DELETE operations are supported.
    Mappings are created automatically during sync operations.
    """

    queryset = MarketplaceMapping.objects.all()
    serializer_class = MarketplaceMappingSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at", "updated_at", "last_synced_at", "external_listing_id"]
    ordering = ["-created_at"]  # Default ordering
    pagination_class = StandardPageNumberPagination
    http_method_names = ["get", "delete", "head", "options"]  # Only GET and DELETE

    def get_permissions(self):
        """Return appropriate permissions based on action"""
        if self.action == "destroy":
            # Delete operations require DATA_PROVIDER or TENANT_ADMIN role and integrations:write scope
            return [
                permissions.IsAuthenticated(),
                HasAnyRole(["DATA_PROVIDER", "TENANT_ADMIN"]),
                HasScope("integrations:write"),
            ]
        # Read operations only require authentication
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """Filter queryset based on user permissions and tenant isolation"""
        queryset = self._resolve_queryset_tenant(self.request, MarketplaceMapping)

        # Apply filters
        connection_id_filter = self.request.query_params.get("connection_id")
        if connection_id_filter:
            try:
                import uuid

                connection_uuid = uuid.UUID(connection_id_filter)
                queryset = queryset.filter(connection_id=connection_uuid)
            except (ValueError, TypeError):
                return MarketplaceMapping.objects.none()

        hub_asset_id_filter = self.request.query_params.get("hub_asset_id")
        if hub_asset_id_filter:
            try:
                import uuid

                asset_uuid = uuid.UUID(hub_asset_id_filter)
                queryset = queryset.filter(hub_asset_id=asset_uuid)
            except (ValueError, TypeError):
                return MarketplaceMapping.objects.none()

        external_listing_id_filter = self.request.query_params.get("external_listing_id")
        if external_listing_id_filter:
            queryset = queryset.filter(external_listing_id=external_listing_id_filter)

        return queryset

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a marketplace mapping.

        DELETE /api/v1/integrations/marketplace/mappings/{id}/
        """
        # Rate limiting check
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            headers = get_rate_limit_headers(request, rate_limit_results)
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "user_id": str(request.user.id) if request.user else None,
                    "tenant_id": str(self._get_tenant_id(request))
                    if self._get_tenant_id(request)
                    else None,
                    "endpoint": "marketplace_mapping_delete",
                },
            )
            from rest_framework.exceptions import Throttled

            limiting_result = next(
                (r for r in rate_limit_results if not r.allowed),
                rate_limit_results[0] if rate_limit_results else None,
            )
            reset_time = limiting_result.reset_time if limiting_result else None
            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            exception.headers = headers
            raise exception

        instance = self.get_object()
        user_id = self._get_user_id(request)
        tenant_id = self._get_tenant_id(request)

        # Verify tenant isolation
        if tenant_id and str(instance.tenant_id) != str(tenant_id):
            if not (hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin):
                raise PermissionDenied("Cannot delete mapping from different tenant")

        if not user_id:
            return Response(
                {"error": "User authentication required"}, status=status.HTTP_401_UNAUTHORIZED
            )

        # Log deletion attempt
        logger.info(
            "marketplace_mapping_delete_attempt",
            extra={
                "mapping_id": str(instance.id),
                "connection_id": str(instance.connection_id),
                "hub_asset_id": str(instance.hub_asset_id),
                "external_listing_id": instance.external_listing_id,
                "user_id": user_id,
                "tenant_id": str(tenant_id) if tenant_id else None,
            },
        )

        try:
            service = MarketplaceIntegrationService(
                tenant_id=str(instance.tenant_id),
                user_id=user_id,
                request_id=getattr(request, "id", None),
            )

            service.delete_mapping(
                mapping_id=str(instance.id),
                tenant_id=str(instance.tenant_id),
                user_id=user_id,
                request=request,
            )

            return Response(status=status.HTTP_204_NO_CONTENT)

        except NotFoundError as e:
            logger.warning(
                "marketplace_mapping_not_found",
                error=str(e),
                extra={
                    "mapping_id": str(instance.id),
                    "user_id": user_id,
                    "tenant_id": str(tenant_id) if tenant_id else None,
                },
            )
            raise NotFound(str(e))

        except Exception as e:
            logger.error(
                "marketplace_mapping_delete_error",
                error=str(e),
                exc_info=True,
                extra={
                    "mapping_id": str(instance.id),
                    "user_id": user_id,
                    "tenant_id": str(tenant_id) if tenant_id else None,
                },
            )
            raise DRFValidationError(f"Failed to delete marketplace mapping: {e!s}")


@extend_schema(
    summary="List marketplace connectors",
    description="List all available marketplace connector types with their supported sync directions and status.",
    responses={
        200: {
            "description": "List of available connectors",
            "content": {
                "application/json": {
                    "example": {
                        "connectors": [
                            {
                                "type": "SNOWFLAKE_DATA_MARKETPLACE",
                                "display_name": "Snowflake Data Marketplace",
                                "supported_sync_directions": ["PULL"],
                                "status": "available",
                                "description": "Connector for Snowflake Data Marketplace",
                            }
                        ]
                    }
                }
            },
        }
    },
    tags=["Integrations"],
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def list_connectors(request):
    """
    List all available marketplace connector types.

    Returns information about all registered marketplace connectors including:
    - Connector type (marketplace type)
    - Display name
    - Supported sync directions (PUSH, PULL, BIDIRECTIONAL)
    - Status (available/not available)
    - Description

    GET /api/v1/integrations/marketplace/connectors/
    """
    try:
        # Get all supported connector types from factory
        supported_types = MarketplaceConnectorFactory.get_supported_types()

        connectors = []
        for marketplace_type in supported_types:
            try:
                # Try to create a connector instance to get its properties
                connector = MarketplaceConnectorFactory.get_connector(marketplace_type)

                # Get supported sync directions
                sync_directions = [
                    direction.value for direction in connector.supported_sync_directions
                ]

                # Get connector class for additional info
                connector_class = MarketplaceConnectorFactory._connectors[marketplace_type.value]

                # Extract description from docstring if available
                description = connector_class.__doc__ or ""
                if description:
                    # Get first line of docstring
                    description = description.strip().split("\n")[0]

                connectors.append(
                    {
                        "type": marketplace_type.value,
                        "display_name": marketplace_type.value.replace("_", " ").title(),
                        "supported_sync_directions": sync_directions,
                        "status": "available",
                        "description": description,
                    }
                )
            except Exception as e:
                # If we can't create connector, still include it but mark as unavailable
                logger.warning(
                    "connector_info_error", marketplace_type=marketplace_type.value, error=str(e)
                )
                connectors.append(
                    {
                        "type": marketplace_type.value,
                        "display_name": marketplace_type.value.replace("_", " ").title(),
                        "supported_sync_directions": [],
                        "status": "unavailable",
                        "description": f"Connector unavailable: {e!s}",
                    }
                )

        return Response({"connectors": connectors}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("list_connectors_error", error=str(e), exc_info=True)
        return Response(
            {"error": f"Failed to list connectors: {e!s}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Get marketplace connector information",
    description="Get detailed information about a specific marketplace connector type including capabilities and configuration requirements.",
    parameters=[
        OpenApiParameter(
            name="type",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            description="Marketplace connector type (e.g., SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE)",
            required=True,
        ),
    ],
    responses={
        200: {
            "description": "Connector information",
            "content": {
                "application/json": {
                    "example": {
                        "type": "SNOWFLAKE_DATA_MARKETPLACE",
                        "display_name": "Snowflake Data Marketplace",
                        "supported_sync_directions": ["PULL"],
                        "status": "available",
                        "description": "Connector for Snowflake Data Marketplace",
                        "capabilities": {
                            "discovery": True,
                            "harvest": True,
                            "push": False,
                            "pull": True,
                        },
                        "configuration_requirements": {
                            "required": ["account", "user", "token"],
                            "optional": ["warehouse", "role", "database"],
                        },
                    }
                }
            },
        },
        404: OpenApiResponse(description="Connector type not found"),
    },
    tags=["Integrations"],
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def get_connector_info(request, connector_type: str):
    """
    Get detailed information about a specific marketplace connector type.

    Returns comprehensive information about the connector including:
    - Connector type and display name
    - Supported sync directions
    - Status (available/not available)
    - Description
    - Capabilities (discovery, harvest, push, pull)
    - Configuration requirements (required and optional fields)

    GET /api/v1/integrations/marketplace/connectors/{type}/
    """
    try:
        # Validate connector type
        try:
            marketplace_type = MarketplaceType(connector_type.upper())
        except ValueError:
            return Response(
                {"error": f"Invalid connector type: {connector_type}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if connector is supported
        if not MarketplaceConnectorFactory.is_supported(marketplace_type):
            return Response(
                {"error": f"Connector type not available: {connector_type}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            # Create connector instance to get properties
            connector = MarketplaceConnectorFactory.get_connector(marketplace_type)

            # Get supported sync directions
            sync_directions = [direction.value for direction in connector.supported_sync_directions]

            # Get connector class for additional info
            connector_class = MarketplaceConnectorFactory._connectors[marketplace_type.value]

            # Extract description from docstring
            description = connector_class.__doc__ or ""
            if description:
                # Get first paragraph of docstring
                description = description.strip().split("\n\n")[0]

            # Determine capabilities based on supported sync directions
            capabilities = {
                "discovery": True,  # All connectors support discovery
                "harvest": SyncDirection.PULL in connector.supported_sync_directions,
                "push": SyncDirection.PUSH in connector.supported_sync_directions,
                "pull": SyncDirection.PULL in connector.supported_sync_directions,
                "bidirectional": SyncDirection.BIDIRECTIONAL in connector.supported_sync_directions,
            }

            # Extract configuration requirements from __init__ signature
            import inspect

            config_requirements = {"required": [], "optional": []}

            try:
                sig = inspect.signature(connector_class.__init__)
                for param_name, param in sig.parameters.items():
                    if param_name == "self":
                        continue
                    if param.default == inspect.Parameter.empty:
                        config_requirements["required"].append(param_name)
                    else:
                        config_requirements["optional"].append(param_name)
            except Exception:
                # If we can't inspect signature, leave empty
                pass

            return Response(
                {
                    "type": marketplace_type.value,
                    "display_name": marketplace_type.value.replace("_", " ").title(),
                    "supported_sync_directions": sync_directions,
                    "status": "available",
                    "description": description,
                    "capabilities": capabilities,
                    "configuration_requirements": config_requirements,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.warning("connector_info_error", connector_type=connector_type, error=str(e))
            return Response(
                {
                    "type": marketplace_type.value,
                    "display_name": marketplace_type.value.replace("_", " ").title(),
                    "supported_sync_directions": [],
                    "status": "unavailable",
                    "description": f"Connector unavailable: {e!s}",
                    "capabilities": {},
                    "configuration_requirements": {},
                },
                status=status.HTTP_200_OK,
            )

    except Exception as e:
        logger.error(
            "get_connector_info_error", connector_type=connector_type, error=str(e), exc_info=True
        )
        return Response(
            {"error": f"Failed to get connector information: {e!s}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
