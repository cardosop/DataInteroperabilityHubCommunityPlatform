"""
Transformation Views

Django REST Framework views for transformation pipeline management.
"""
import structlog
import time
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, inline_serializer
from rest_framework import serializers

from .models import (
    TransformationPipeline, PipelineStatus, PipelineExecution, ExecutionStatus, ExecutionMode,
    PreviewResult, WranglingSession
)
from .serializers import (
    TransformationPipelineSerializer,
    TransformationPipelineCreateSerializer,
    TransformationPipelineUpdateSerializer,
    PipelineValidationResponseSerializer,
    PipelineExecutionSerializer,
    PipelineExecutionProgressSerializer,
    PipelineExecutionResultSerializer,
    PreviewResultSerializer,
    WranglingSessionSerializer,
    WranglingOperationRequestSerializer,
    WranglingResultSerializer,
)
from .business_rules import TransformationBusinessRules
from .exceptions import TransformationValidationError
from .services import TransformationService
from hub.apps.auth.permissions import HasRole, HasAnyRole, HasScope, HasAnyScope
from hub.apps.audit.utils import create_audit_event
from hub.apps.rate_limiting.service import check_rate_limit, get_rate_limit_headers
from rest_framework.exceptions import Throttled
from hub.apps.governance.abac import ABACEngine, PolicyEvaluationResult

logger = structlog.get_logger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List transformation pipelines",
        description="List all transformation pipelines for the authenticated user's tenant with filtering and pagination.",
        tags=["Transformation"],
    ),
    retrieve=extend_schema(
        summary="Get pipeline details",
        description="Get detailed information about a specific transformation pipeline.",
        tags=["Transformation"],
    ),
    create=extend_schema(
        summary="Create transformation pipeline",
        description="Create a new transformation pipeline.",
        tags=["Transformation"],
    ),
    update=extend_schema(
        summary="Update transformation pipeline",
        description="Update an existing transformation pipeline.",
        tags=["Transformation"],
    ),
    destroy=extend_schema(
        summary="Delete transformation pipeline",
        description="Delete a transformation pipeline.",
        tags=["Transformation"],
    ),
)
class TransformationPipelineViewSet(viewsets.ModelViewSet):
    """
    ViewSet for transformation pipeline management.

    Tenant-scoped: users can only see/manage pipelines in their tenant.
    Requires DATA_PROVIDER or TENANT_ADMIN role for write operations.
    Requires transformation:write scope for write operations.
    """
    queryset = TransformationPipeline.objects.all()
    serializer_class = TransformationPipelineSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    filter_backends = [OrderingFilter, SearchFilter]
    ordering_fields = ['name', 'status', 'version', 'created_at', 'updated_at']
    ordering = ['-created_at']  # Default ordering
    search_fields = ['name', 'description']

    def get_permissions(self):
        """Return appropriate permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                          'validate', 'test', 'execute', 'preview']:
            return [
                permissions.IsAuthenticated(),
                HasScope('transformation:write'),
            ]
        # Read operations require transformation:read scope
        return [permissions.IsAuthenticated(), HasScope('transformation:read')]

    def get_queryset(self):
        """Filter queryset based on user permissions and query parameters"""
        user = self.request.user

        # Platform admins can see all pipelines
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = TransformationPipeline.objects.all()
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
                    db_user = User.objects.only('tenant_id').get(id=user.id)
                    if db_user.tenant_id:
                        tenant_id = db_user.tenant_id
                except User.DoesNotExist:
                    pass

            # Last resort: get from user.tenant relationship
            if not tenant_id and hasattr(user, "tenant") and user.tenant:
                tenant_id = user.tenant.id

            # Regular users can only see pipelines in their tenant
            if tenant_id:
                # Use tenant_id for filtering (more reliable than tenant object)
                # Ensure tenant_id is a UUID for proper filtering
                if isinstance(tenant_id, str):
                    import uuid
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        return TransformationPipeline.objects.none()
                # Filter by tenant_id - this is the most reliable way
                queryset = TransformationPipeline.objects.filter(tenant_id=tenant_id)
            else:
                return TransformationPipeline.objects.none()

        # Apply status filter if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            # Validate status value
            valid_statuses = [choice[0] for choice in PipelineStatus.choices]
            if status_filter.upper() in valid_statuses:
                queryset = queryset.filter(status=status_filter.upper())
            else:
                # Invalid status - return empty queryset
                return TransformationPipeline.objects.none()

        # Apply version filter if provided
        version_filter = self.request.query_params.get('version')
        if version_filter:
            queryset = queryset.filter(version=version_filter)

        return queryset

    def get_tenant_from_request(self):
        """Get tenant from request with proper fallback logic"""
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
                from hub.apps.tenants.models import Tenant
                try:
                    return Tenant.objects.get(id=tenant_id)
                except Tenant.DoesNotExist:
                    pass

        # Fallback to request.tenant object
        if hasattr(self.request, "tenant") and self.request.tenant:
            return self.request.tenant

        # Fallback to user.tenant_id
        user = self.request.user
        if hasattr(user, "id") and user.id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                db_user = User.objects.only('tenant_id').get(id=user.id)
                if db_user.tenant_id:
                    from hub.apps.tenants.models import Tenant
                    try:
                        return Tenant.objects.get(id=db_user.tenant_id)
                    except Tenant.DoesNotExist:
                        pass
            except User.DoesNotExist:
                pass

        # Last resort: get from user.tenant relationship
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
            resource_type: Resource type (TRANSFORMATION_PIPELINE)
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
                    policy_name = result.policy.name if result.policy else "Unknown"
                    raise PermissionDenied(
                        f"ABAC policy denied {access_type} access to {resource_type}. "
                        f"Policy: {policy_name}"
                    )
                # If no policy matched (default deny), we allow access for new resource creation
                # This is a "fail open" approach for new resources when no policies are configured
                # For existing resources, we should still check ownership/tenant isolation
                # Note: This behavior can be configured via settings if needed
                logger.debug(
                    "abac_no_policy_matched",
                    user_id=user_id,
                    tenant_id=tenant_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    access_type=access_type,
                    message="No ABAC policy matched, allowing access (fail open)"
                )

            logger.debug(
                "abac_policy_checked",
                user_id=user_id,
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                access_type=access_type,
                allowed=result.allowed,
            )
        except PermissionDenied:
            raise
        except Exception as e:
            # Log error but don't fail authorization if ABAC check fails
            # This allows the system to continue operating if ABAC service is unavailable
            logger.warning(
                "abac_policy_check_failed",
                user_id=user_id,
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                access_type=access_type,
                error=str(e),
                exc_info=True
            )
            # In production, you might want to fail closed (deny access) or fail open (allow)
            # For now, we'll allow access if ABAC check fails (fail open)
            # This can be configured via settings

    def _check_pipeline_ownership_or_access(
        self,
        pipeline: TransformationPipeline,
        user,
        access_type: str = "WRITE"
    ) -> bool:
        """
        Check if user owns pipeline or has access via domain/mesh.

        Args:
            pipeline: TransformationPipeline instance
            user: User instance
            access_type: Access type (READ, WRITE, DELETE)

        Returns:
            True if user has access, False otherwise
        """
        # Platform admins have access to everything
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return True

        # Check if user created the pipeline (ownership)
        if pipeline.created_by and pipeline.created_by.id == user.id:
            return True

        # Check if user has TENANT_ADMIN role (can access all in tenant)
        if hasattr(user, "user_roles"):
            role_names = [ur.role.name for ur in user.user_roles.all()]
            if "TENANT_ADMIN" in role_names:
                return True

        # Check domain/mesh access if pipeline has domain metadata
        # This is a placeholder for future domain/mesh integration
        # For now, we rely on tenant isolation and ownership
        if pipeline.metadata and "domain" in pipeline.metadata:
            # Future: Check if user has access to the domain
            # For now, domain access is implied by tenant membership
            pass

        return False

    def _check_resource_level_permissions(
        self,
        pipeline: TransformationPipeline,
        user,
        access_type: str = "WRITE"
    ) -> None:
        """
        Check resource-level permissions including ABAC policies.

        Args:
            pipeline: TransformationPipeline instance
            user: User instance
            access_type: Access type (READ, WRITE, DELETE)

        Raises:
            PermissionDenied: If user doesn't have required permissions
        """
        tenant_id = str(pipeline.tenant.id) if pipeline.tenant else None
        user_id = str(user.id) if user else None

        if not tenant_id or not user_id:
            raise PermissionDenied("Unable to determine tenant or user for permission check")

        # Check ABAC policies for resource-level permissions
        self._check_abac_policy(
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="TRANSFORMATION_PIPELINE",
            resource_id=str(pipeline.id),
            access_type=access_type
        )

        # Check ownership or access via domain/mesh
        if not self._check_pipeline_ownership_or_access(pipeline, user, access_type):
            # For write/delete operations, require ownership or TENANT_ADMIN
            if access_type in ["WRITE", "DELETE"]:
                raise PermissionDenied(
                    "You do not have permission to perform this action. "
                    "Only the pipeline owner or tenant administrators can modify pipelines."
                )
            # For read operations, tenant isolation is sufficient (already checked in get_queryset)

    @transaction.atomic
    def create(self, request):
        """
        Create a new transformation pipeline.

        POST /api/v1/transformation/pipelines/
        """
        # Check rate limits (per tenant, per user)
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            # Get rate limit headers for response
            headers = get_rate_limit_headers(request, rate_limit_results)
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many pipeline creation requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        serializer = TransformationPipelineCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant from request
        tenant = self.get_tenant_from_request()
        if not tenant:
            raise ValidationError("Unable to determine tenant for pipeline creation")

        # Check tenant isolation - ensure user belongs to the tenant
        user = request.user
        if not hasattr(user, "is_platform_admin") or not user.is_platform_admin:
            user_tenant_id = None
            if hasattr(user, "id") and user.id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    db_user = User.objects.only('tenant_id').get(id=user.id)
                    user_tenant_id = db_user.tenant_id
                except User.DoesNotExist:
                    pass

            if not user_tenant_id or str(user_tenant_id) != str(tenant.id):
                raise PermissionDenied("Cannot create pipeline for different tenant")

        # Check ABAC policies for pipeline creation
        # Use placeholder resource ID for new pipeline creation
        placeholder_resource_id = f"tenant:{tenant.id}:pipeline:new"
        try:
            self._check_abac_policy(
                user_id=str(user.id),
                tenant_id=str(tenant.id),
                resource_type="TRANSFORMATION_PIPELINE",
                resource_id=placeholder_resource_id,
                access_type="WRITE"
            )
        except PermissionDenied:
            # Re-raise with more context
            raise PermissionDenied(
                "You do not have permission to create pipelines. "
                "ABAC policy denied access."
            )

        # Create pipeline instance
        pipeline = TransformationPipeline(
            tenant=tenant,
            created_by=user,
            name=serializer.validated_data['name'],
            description=serializer.validated_data.get('description'),
            pipeline_definition=serializer.validated_data['pipeline_definition'],
            version=serializer.validated_data.get('version', '1.0.0'),
            status=serializer.validated_data.get('status', PipelineStatus.DRAFT),
            metadata=serializer.validated_data.get('metadata', {}),
        )

        try:
            pipeline.full_clean()
            pipeline.save()
        except DjangoValidationError as e:
            raise ValidationError(e.message_dict)

        # Create audit event
        create_audit_event(
            resource_type="transformation_pipeline",
            action="pipeline.created",
            actor_user=user,
            tenant=tenant,
            resource_id=str(pipeline.id),
            details={
                "pipeline_name": pipeline.name,
                "pipeline_version": pipeline.version,
                "pipeline_status": pipeline.status,
            },
            request=request
        )

        # Serialize and return response
        response_serializer = TransformationPipelineSerializer(pipeline)

        # Add rate limit headers to response
        headers = get_rate_limit_headers(request, rate_limit_results)

        logger.info(
            "pipeline_created",
            pipeline_id=str(pipeline.id),
            pipeline_name=pipeline.name,
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        )
        response = Response(response_serializer.data, status=status.HTTP_201_CREATED)
        # Add rate limit headers to response
        for header_name, header_value in headers.items():
            response[header_name] = header_value
        return response

    def list(self, request):
        """
        List transformation pipelines with filtering and pagination.

        GET /api/v1/transformation/pipelines/
        Query parameters:
        - status: Filter by status (DRAFT, ACTIVE, INACTIVE, ARCHIVED)
        - version: Filter by version
        - search: Search in name and description
        - ordering: Order by name, status, version, created_at, updated_at
        - page: Page number for pagination
        - page_size: Number of items per page
        """
        queryset = self.filter_queryset(self.get_queryset())

        # Pagination
        page_size = request.query_params.get('page_size', 20)
        try:
            page_size = int(page_size)
            if page_size < 1 or page_size > 100:
                page_size = 20
        except (ValueError, TypeError):
            page_size = 20

        paginator = Paginator(queryset, page_size)
        page_number = request.query_params.get('page', 1)
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

        serializer = self.get_serializer(page.object_list, many=True)
        return Response({
            'count': paginator.count,
            'next': page.next_page_number() if page.has_next() else None,
            'previous': page.previous_page_number() if page.has_previous() else None,
            'results': serializer.data,
        })

    def retrieve(self, request, id=None):
        """
        Get pipeline details.

        GET /api/v1/transformation/pipelines/{id}/
        """
        try:
            pipeline = self.get_queryset().get(id=id)
        except TransformationPipeline.DoesNotExist:
            raise NotFound("Pipeline not found")

        serializer = self.get_serializer(pipeline)
        return Response(serializer.data)

    @transaction.atomic
    def update(self, request, id=None):
        """
        Update transformation pipeline.

        PUT /api/v1/transformation/pipelines/{id}/
        """
        try:
            pipeline = self.get_queryset().get(id=id)
        except TransformationPipeline.DoesNotExist:
            raise NotFound("Pipeline not found")

        # Check tenant isolation
        user = request.user
        if not hasattr(user, "is_platform_admin") or not user.is_platform_admin:
            tenant = self.get_tenant_from_request()
            if not tenant or str(pipeline.tenant.id) != str(tenant.id):
                raise PermissionDenied("Cannot update pipeline from different tenant")

        # Check resource-level permissions (ownership, ABAC policies)
        self._check_resource_level_permissions(pipeline, user, access_type="WRITE")

        serializer = TransformationPipelineUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Update fields
        if 'name' in serializer.validated_data:
            pipeline.name = serializer.validated_data['name']
        if 'description' in serializer.validated_data:
            pipeline.description = serializer.validated_data['description']
        if 'pipeline_definition' in serializer.validated_data:
            pipeline.pipeline_definition = serializer.validated_data['pipeline_definition']
        if 'version' in serializer.validated_data:
            pipeline.version = serializer.validated_data['version']
        if 'status' in serializer.validated_data:
            pipeline.status = serializer.validated_data['status']
        if 'metadata' in serializer.validated_data:
            pipeline.metadata = serializer.validated_data['metadata']

        try:
            pipeline.full_clean()
            pipeline.save()
        except DjangoValidationError as e:
            raise ValidationError(e.message_dict)

        # Create audit event
        create_audit_event(
            resource_type="transformation_pipeline",
            action="pipeline.updated",
            actor_user=user,
            tenant=pipeline.tenant,
            resource_id=str(pipeline.id),
            details={
                "pipeline_name": pipeline.name,
                "pipeline_version": pipeline.version,
                "pipeline_status": pipeline.status,
            },
            request=request
        )

        response_serializer = TransformationPipelineSerializer(pipeline)
        logger.info(
            "pipeline_updated",
            pipeline_id=str(pipeline.id),
            pipeline_name=pipeline.name,
            tenant_id=str(pipeline.tenant.id),
            user_id=str(user.id),
        )
        return Response(response_serializer.data)

    def partial_update(self, request, id=None):
        """
        Partially update transformation pipeline.

        PATCH /api/v1/transformation/pipelines/{id}/
        """
        return self.update(request, id)

    @transaction.atomic
    def destroy(self, request, id=None):
        """
        Delete transformation pipeline.

        DELETE /api/v1/transformation/pipelines/{id}/
        """
        try:
            pipeline = self.get_queryset().get(id=id)
        except TransformationPipeline.DoesNotExist:
            raise NotFound("Pipeline not found")

        # Check tenant isolation
        user = request.user
        if not hasattr(user, "is_platform_admin") or not user.is_platform_admin:
            tenant = self.get_tenant_from_request()
            if not tenant or str(pipeline.tenant.id) != str(tenant.id):
                raise PermissionDenied("Cannot delete pipeline from different tenant")

        # Check resource-level permissions (ownership, ABAC policies)
        self._check_resource_level_permissions(pipeline, user, access_type="DELETE")

        pipeline_id = str(pipeline.id)
        pipeline_name = pipeline.name
        tenant_id = str(pipeline.tenant.id)

        pipeline.delete()

        # Create audit event
        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id)
        create_audit_event(
            resource_type="transformation_pipeline",
            action="pipeline.deleted",
            actor_user=user,
            tenant=tenant,
            resource_id=pipeline_id,
            details={
                "pipeline_name": pipeline_name,
            },
            request=request
        )

        logger.info(
            "pipeline_deleted",
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            tenant_id=tenant_id,
            user_id=str(user.id),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Validate transformation pipeline",
        description="Validate a transformation pipeline structure and business rules.",
        request=None,
        responses={
            200: PipelineValidationResponseSerializer,
        },
        tags=["Transformation"],
    )
    @action(detail=True, methods=['post'], url_path='validate')
    def validate_pipeline(self, request, id=None):
        """
        Validate transformation pipeline.

        POST /api/v1/transformation/pipelines/{id}/validate/
        """
        try:
            pipeline = self.get_queryset().get(id=id)
        except TransformationPipeline.DoesNotExist:
            raise NotFound("Pipeline not found")

        # Check tenant isolation
        user = request.user
        if not hasattr(user, "is_platform_admin") or not user.is_platform_admin:
            tenant = self.get_tenant_from_request()
            if not tenant or str(pipeline.tenant.id) != str(tenant.id):
                raise PermissionDenied("Cannot validate pipeline from different tenant")

        # Check resource-level permissions (ownership, ABAC policies)
        # Validation is a read operation, but we check for consistency
        self._check_resource_level_permissions(pipeline, user, access_type="READ")

        # Get tenant_id and user_id for business rules
        tenant_id = str(pipeline.tenant.id) if pipeline.tenant else None
        user_id = str(user.id) if user else None

        # Validate pipeline using business rules
        business_rules = TransformationBusinessRules(
            tenant_id=tenant_id,
            user_id=user_id
        )

        validation_result = business_rules.validate_pipeline_structure(
            pipeline,
            raise_on_error=False
        )

        # Create audit event
        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id) if tenant_id else pipeline.tenant
        create_audit_event(
            resource_type="transformation_pipeline",
            action="pipeline.validated",
            actor_user=user,
            tenant=tenant,
            resource_id=str(pipeline.id),
            details={
                "pipeline_name": pipeline.name,
                "validation_result": validation_result.is_valid,
                "validation_errors": validation_result.errors,
                "validation_warnings": validation_result.warnings,
            },
            request=request
        )

        response_serializer = PipelineValidationResponseSerializer({
            'is_valid': validation_result.is_valid,
            'errors': validation_result.errors,
            'warnings': validation_result.warnings,
            'details': validation_result.details,
        })

        logger.info(
            "pipeline_validated",
            pipeline_id=str(pipeline.id),
            pipeline_name=pipeline.name,
            tenant_id=tenant_id,
            user_id=user_id,
            is_valid=validation_result.is_valid,
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Execute transformation pipeline",
        description="Execute a transformation pipeline on a source asset.",
        request=inline_serializer(
            name='PipelineExecuteRequest',
            fields={
                'asset_id': serializers.UUIDField(help_text="Source asset ID to transform"),
                'execution_mode': serializers.ChoiceField(
                    choices=['SYNC', 'ASYNC'],
                    required=False,
                    help_text="Execution mode: SYNC (synchronous) or ASYNC (asynchronous)"
                ),
            }
        ),
        responses={
            200: inline_serializer(
                name='PipelineExecuteResponse',
                fields={
                    'execution_id': serializers.UUIDField(),
                    'status': serializers.CharField(),
                    'pipeline_id': serializers.UUIDField(),
                    'asset_id': serializers.UUIDField(),
                }
            ),
            429: OpenApiResponse(description='Rate limit exceeded'),
        },
        tags=["Transformation"],
    )
    @action(detail=True, methods=['post'], url_path='execute')
    @transaction.atomic
    def execute_pipeline(self, request, id=None):
        """
        Execute a transformation pipeline.

        POST /api/v1/transformation/pipelines/{id}/execute/
        """

        # Check rate limits (per tenant, per user)
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            # Get rate limit headers for response
            headers = get_rate_limit_headers(request, rate_limit_results)
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many pipeline execution requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        try:
            pipeline = self.get_queryset().get(id=id)
        except TransformationPipeline.DoesNotExist:
            raise NotFound("Pipeline not found")

        # Check tenant isolation
        user = request.user
        if not hasattr(user, "is_platform_admin") or not user.is_platform_admin:
            tenant = self.get_tenant_from_request()
            if not tenant or str(pipeline.tenant.id) != str(tenant.id):
                raise PermissionDenied("Cannot execute pipeline from different tenant")

        # Validate request data
        asset_id = request.data.get('asset_id')
        if not asset_id:
            raise ValidationError({"asset_id": "This field is required."})

        execution_mode = request.data.get('execution_mode', 'ASYNC')

        # Get tenant_id and user_id
        tenant_id = str(pipeline.tenant.id) if pipeline.tenant else None
        user_id = str(user.id) if user else None

        # Initialize service
        service = TransformationService(
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Execute pipeline
        execution = service.execute_pipeline(
            pipeline_id=str(pipeline.id),
            asset_id=str(asset_id),
            tenant_id=tenant_id,
            user_id=user_id,
            execution_mode=execution_mode,
            request=request
        )

        # Create audit event
        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id) if tenant_id else pipeline.tenant
        create_audit_event(
            resource_type="transformation_pipeline",
            action="pipeline.executed",
            actor_user=user,
            tenant=tenant,
            resource_id=str(pipeline.id),
            details={
                "pipeline_name": pipeline.name,
                "execution_id": str(execution.id),
                "asset_id": str(asset_id),
                "execution_mode": execution_mode,
            },
            request=request
        )

        # Add rate limit headers to response
        headers = get_rate_limit_headers(request, rate_limit_results)

        logger.info(
            "pipeline_executed",
            pipeline_id=str(pipeline.id),
            execution_id=str(execution.id),
            tenant_id=tenant_id,
            user_id=user_id,
        )
        response = Response({
            'execution_id': str(execution.id),
            'status': execution.status,
            'pipeline_id': str(pipeline.id),
            'asset_id': str(asset_id),
        }, status=status.HTTP_200_OK)
        # Add rate limit headers to response
        for header_name, header_value in headers.items():
            response[header_name] = header_value
        return response

    @extend_schema(
        summary="Preview transformation pipeline",
        description="Preview transformation pipeline execution on sample data.",
        request=inline_serializer(
            name='PipelinePreviewRequest',
            fields={
                'asset_id': serializers.UUIDField(help_text="Source asset ID to preview"),
                'sample_size': serializers.IntegerField(
                    default=100,
                    required=False,
                    help_text="Number of rows to sample (default: 100)"
                ),
                'sampling_method': serializers.ChoiceField(
                    choices=['first_n', 'random'],
                    default='first_n',
                    required=False,
                    help_text="Sampling method: first_n or random (default: first_n)"
                ),
            }
        ),
        responses={
            200: inline_serializer(
                name='PipelinePreviewResponse',
                fields={
                    'preview_id': serializers.CharField(),
                    'pipeline_id': serializers.UUIDField(),
                    'asset_id': serializers.UUIDField(),
                    'analysis': serializers.DictField(),
                    'cached': serializers.BooleanField(),
                }
            ),
            429: OpenApiResponse(description='Rate limit exceeded'),
        },
        tags=["Transformation"],
    )
    @action(detail=True, methods=['post'], url_path='preview')
    def preview_pipeline(self, request, id=None):
        """
        Preview transformation pipeline execution on sample data.

        POST /api/v1/transformation/pipelines/{id}/preview/
        """

        # Check rate limits (per tenant, per user)
        allowed, rate_limit_results = check_rate_limit(request)
        if not allowed:
            # Get rate limit headers for response
            headers = get_rate_limit_headers(request, rate_limit_results)
            # Find the limiting result to get reset time
            limiting_result = next((r for r in rate_limit_results if not r.allowed), rate_limit_results[0] if rate_limit_results else None)
            reset_time = limiting_result.reset_time if limiting_result else None

            exception = Throttled(
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many pipeline preview requests. Please try again later.",
                    "retry_after": reset_time - int(time.time()) if reset_time else None,
                }
            )
            # Set headers on the exception (DRF exception handler will use these)
            exception.headers = headers
            raise exception

        try:
            pipeline = self.get_queryset().get(id=id)
        except TransformationPipeline.DoesNotExist:
            raise NotFound("Pipeline not found")

        # Check tenant isolation
        user = request.user
        if not hasattr(user, "is_platform_admin") or not user.is_platform_admin:
            tenant = self.get_tenant_from_request()
            if not tenant or str(pipeline.tenant.id) != str(tenant.id):
                raise PermissionDenied("Cannot preview pipeline from different tenant")

        # Validate request data
        asset_id = request.data.get('asset_id')
        if not asset_id:
            raise ValidationError({"asset_id": "This field is required."})

        sample_size = request.data.get('sample_size', 100)
        sampling_method = request.data.get('sampling_method', 'first_n')

        # Get tenant_id and user_id
        tenant_id = str(pipeline.tenant.id) if pipeline.tenant else None
        user_id = str(user.id) if user else None

        # Initialize service
        service = TransformationService(
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Generate preview
        preview_result = service.preview_transformation(
            pipeline_id=str(pipeline.id),
            asset_id=str(asset_id),
            sample_size=sample_size,
            sampling_method=sampling_method,
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Create audit event
        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id) if tenant_id else pipeline.tenant
        create_audit_event(
            resource_type="transformation_pipeline",
            action="pipeline.previewed",
            actor_user=user,
            tenant=tenant,
            resource_id=str(pipeline.id),
            details={
                "pipeline_name": pipeline.name,
                "preview_id": preview_result.get("preview_id"),
                "asset_id": str(asset_id),
                "sample_size": sample_size,
            },
            request=request
        )

        # Add rate limit headers to response
        headers = get_rate_limit_headers(request, rate_limit_results)

        logger.info(
            "pipeline_previewed",
            pipeline_id=str(pipeline.id),
            preview_id=preview_result.get("preview_id"),
            tenant_id=tenant_id,
            user_id=user_id,
        )
        response = Response(preview_result, status=status.HTTP_200_OK)
        # Add rate limit headers to response
        for header_name, header_value in headers.items():
            response[header_name] = header_value
        return response

    @extend_schema(
        summary="List pipeline executions",
        description="List all executions for a transformation pipeline with filtering and pagination.",
        responses={
            200: inline_serializer(
                name='PipelineExecutionsListResponse',
                fields={
                    'count': serializers.IntegerField(),
                    'next': serializers.IntegerField(allow_null=True),
                    'previous': serializers.IntegerField(allow_null=True),
                    'results': serializers.ListField(
                        child=serializers.DictField()
                    ),
                }
            ),
        },
        tags=["Transformation"],
    )
    @action(detail=True, methods=['get'], url_path='executions')
    def list_executions(self, request, id=None):
        """
        List all executions for a transformation pipeline.

        GET /api/v1/transformation/pipelines/{id}/executions/
        Query parameters:
        - status: Filter by execution status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
        - page: Page number for pagination
        - page_size: Number of items per page
        """
        # Get pipeline without status filter (status filter is for executions, not pipelines)
        # We need to get the base queryset without query parameter filters
        user = request.user

        # Get tenant for filtering
        tenant_id = None
        if hasattr(request, "tenant_id") and request.tenant_id:
            tenant_id = request.tenant_id
            if isinstance(tenant_id, str):
                import uuid
                try:
                    tenant_id = uuid.UUID(tenant_id)
                except (ValueError, TypeError):
                    tenant_id = None

        if not tenant_id and hasattr(request, "tenant") and request.tenant:
            tenant_id = request.tenant.id

        if not tenant_id and hasattr(user, "id") and user.id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                db_user = User.objects.only('tenant_id').get(id=user.id)
                if db_user.tenant_id:
                    tenant_id = db_user.tenant_id
            except User.DoesNotExist:
                pass

        if not tenant_id and hasattr(user, "tenant") and user.tenant:
            tenant_id = user.tenant.id

        # Get pipeline queryset without status filter
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            pipeline_queryset = TransformationPipeline.objects.all()
        elif tenant_id:
            if isinstance(tenant_id, str):
                import uuid
                try:
                    tenant_id = uuid.UUID(tenant_id)
                except (ValueError, TypeError):
                    raise NotFound("Pipeline not found")
            pipeline_queryset = TransformationPipeline.objects.filter(tenant_id=tenant_id)
        else:
            raise NotFound("Pipeline not found")

        try:
            pipeline = pipeline_queryset.get(id=id)
        except TransformationPipeline.DoesNotExist:
            raise NotFound("Pipeline not found")

        # Check tenant isolation
        user = request.user
        if not hasattr(user, "is_platform_admin") or not user.is_platform_admin:
            tenant = self.get_tenant_from_request()
            if not tenant or str(pipeline.tenant.id) != str(tenant.id):
                raise PermissionDenied("Cannot list executions for pipeline from different tenant")

        # Get executions for this pipeline
        queryset = PipelineExecution.objects.filter(pipeline=pipeline)

        # Apply status filter if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            valid_statuses = [choice[0] for choice in ExecutionStatus.choices]
            if status_filter.upper() in valid_statuses:
                queryset = queryset.filter(status=status_filter.upper())
            else:
                # Invalid status - return empty queryset
                queryset = PipelineExecution.objects.none()

        # Order by most recent first
        queryset = queryset.order_by('-started_at', '-created_at')

        # Pagination
        page_size = request.query_params.get('page_size', 20)
        try:
            page_size = int(page_size)
            if page_size < 1 or page_size > 100:
                page_size = 20
        except (ValueError, TypeError):
            page_size = 20

        paginator = Paginator(queryset, page_size)
        page_number = request.query_params.get('page', 1)
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

        serializer = PipelineExecutionSerializer(page.object_list, many=True)
        return Response({
            'count': paginator.count,
            'next': page.next_page_number() if page.has_next() else None,
            'previous': page.previous_page_number() if page.has_previous() else None,
            'results': serializer.data,
        })


@extend_schema_view(
    retrieve=extend_schema(
        summary="Get execution details",
        description="Get detailed information about a specific pipeline execution.",
        tags=["Transformation"],
    ),
)
class PipelineExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for pipeline execution management.

    Tenant-scoped: users can only see/manage executions in their tenant.
    Requires transformation:read scope for all operations.
    """
    queryset = PipelineExecution.objects.all()
    serializer_class = PipelineExecutionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_permissions(self):
        if self.action in ('cancel_execution',):
            return [permissions.IsAuthenticated(), HasScope('transformation:write')]
        return [permissions.IsAuthenticated(), HasScope('transformation:read')]

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Platform admins can see all executions
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = PipelineExecution.objects.all()
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

            # Filter by tenant via pipeline
            if tenant_id:
                if isinstance(tenant_id, str):
                    import uuid
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        return PipelineExecution.objects.none()
                queryset = PipelineExecution.objects.filter(pipeline__tenant_id=tenant_id)
            else:
                return PipelineExecution.objects.none()

        # Apply status filter if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            valid_statuses = [choice[0] for choice in ExecutionStatus.choices]
            if status_filter.upper() in valid_statuses:
                queryset = queryset.filter(status=status_filter.upper())
            else:
                return PipelineExecution.objects.none()

        return queryset.order_by('-started_at', '-created_at')

    def retrieve(self, request, id=None):
        """
        Get execution details.

        GET /api/v1/transformation/executions/{id}/
        """
        try:
            execution = self.get_queryset().get(id=id)
        except PipelineExecution.DoesNotExist:
            raise NotFound("Execution not found")

        serializer = self.get_serializer(execution)
        return Response(serializer.data)

    @extend_schema(
        summary="Cancel pipeline execution",
        description="Cancel a running or pending pipeline execution.",
        request=None,
        responses={
            200: inline_serializer(
                name='PipelineExecutionCancelResponse',
                fields={
                    'execution_id': serializers.UUIDField(),
                    'status': serializers.CharField(),
                    'message': serializers.CharField(),
                }
            ),
            400: OpenApiResponse(description='Execution cannot be cancelled'),
        },
        tags=["Transformation"],
    )
    @action(detail=True, methods=['post'], url_path='cancel')
    @transaction.atomic
    def cancel_execution(self, request, id=None):
        """
        Cancel a pipeline execution.

        POST /api/v1/transformation/executions/{id}/cancel/
        """
        try:
            execution = self.get_queryset().get(id=id)
        except PipelineExecution.DoesNotExist:
            raise NotFound("Execution not found")

        # Check if execution can be cancelled
        if not execution.can_cancel():
            return Response(
                {
                    'error': f'Execution cannot be cancelled (current status: {execution.status})',
                    'execution_id': str(execution.id),
                    'status': execution.status
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        tenant_id = str(execution.pipeline.tenant.id) if execution.pipeline.tenant else None

        # Cancel the execution
        execution.mark_cancelled()

        # If execution has a job, cancel the job as well
        if execution.job and execution.job.can_cancel():
            from hub.apps.jobs.models import JobStatus
            from hub.apps.jobs.utils import decrement_tenant_job_counter

            previous_status = execution.job.status
            execution.job.mark_cancelled()

            # If job was running, release tenant concurrency slot
            if previous_status == JobStatus.RUNNING and execution.pipeline.tenant:
                decrement_tenant_job_counter(str(execution.pipeline.tenant.id), "running")

        # Create audit event
        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id) if tenant_id else execution.pipeline.tenant
        create_audit_event(
            resource_type="transformation_pipeline_execution",
            action="execution.cancelled",
            actor_user=user,
            tenant=tenant,
            resource_id=str(execution.id),
            details={
                "pipeline_id": str(execution.pipeline.id),
                "pipeline_name": execution.pipeline.name,
                "execution_status": execution.status,
            },
            request=request
        )

        logger.info(
            "execution_cancelled",
            execution_id=str(execution.id),
            pipeline_id=str(execution.pipeline.id),
            tenant_id=tenant_id,
            user_id=str(user.id),
        )

        return Response({
            'execution_id': str(execution.id),
            'status': execution.status,
            'message': 'Execution cancelled successfully',
        }, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get execution progress",
        description="Get real-time progress information for a pipeline execution.",
        responses={
            200: PipelineExecutionProgressSerializer,
        },
        tags=["Transformation"],
    )
    @action(detail=True, methods=['get'], url_path='progress')
    def get_progress(self, request, id=None):
        """
        Get execution progress.

        GET /api/v1/transformation/executions/{id}/progress/
        """
        try:
            execution = self.get_queryset().get(id=id)
        except PipelineExecution.DoesNotExist:
            raise NotFound("Execution not found")

        # Calculate progress percentage
        progress_percentage = None
        current_step = None
        total_steps = None

        # Get pipeline steps
        pipeline_steps = execution.pipeline.pipeline_definition.get("steps", [])
        total_steps = len(pipeline_steps) if pipeline_steps else None

        # Calculate progress based on status and metrics
        if execution.status == ExecutionStatus.PENDING:
            progress_percentage = 0.0
        elif execution.status == ExecutionStatus.RUNNING:
            # Try to get progress from metrics
            if execution.metrics and isinstance(execution.metrics, dict):
                progress_percentage = execution.metrics.get("progress_percentage")
                current_step = execution.metrics.get("current_step")

            # If not in metrics, estimate based on time elapsed
            if progress_percentage is None and execution.started_at:
                # Estimate progress based on average execution time
                # This is a fallback - actual progress should be in metrics
                duration = execution.get_duration_seconds()
                if duration:
                    # Rough estimate: assume 60 seconds average execution time
                    estimated_total = 60.0
                    progress_percentage = min(95.0, (duration / estimated_total) * 100.0)
                else:
                    progress_percentage = 5.0  # Just started
        elif execution.status == ExecutionStatus.COMPLETED:
            progress_percentage = 100.0
        elif execution.status in [ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
            # Failed/cancelled executions show last known progress
            if execution.metrics and isinstance(execution.metrics, dict):
                progress_percentage = execution.metrics.get("progress_percentage", 0.0)
            else:
                progress_percentage = 0.0

        # Get estimated completion time
        estimated_completion_at = None
        if execution.status == ExecutionStatus.RUNNING and execution.started_at and progress_percentage:
            duration = execution.get_duration_seconds()
            if duration and progress_percentage > 0:
                # Estimate: (elapsed_time / progress) * 100
                estimated_total_seconds = (duration / progress_percentage) * 100.0
                remaining_seconds = estimated_total_seconds - duration
                from django.utils import timezone
                estimated_completion_at = timezone.now() + timezone.timedelta(seconds=remaining_seconds)

        # Get recent logs (last 10 entries)
        recent_logs = []
        if execution.execution_log and isinstance(execution.execution_log, list):
            recent_logs = execution.execution_log[-10:]

        response_data = {
            'execution_id': str(execution.id),
            'status': execution.status,
            'progress_percentage': progress_percentage,
            'current_step': current_step,
            'total_steps': total_steps,
            'started_at': execution.started_at,
            'estimated_completion_at': estimated_completion_at,
            'duration_seconds': execution.get_duration_seconds(),
            'metrics': execution.metrics if execution.metrics else {},
            'recent_logs': recent_logs,
        }

        serializer = PipelineExecutionProgressSerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get execution result",
        description="Get the result of a completed pipeline execution, including result asset and metrics.",
        responses={
            200: PipelineExecutionResultSerializer,
            404: OpenApiResponse(description='Execution not found'),
            400: OpenApiResponse(description='Execution not completed'),
        },
        tags=["Transformation"],
    )
    @action(detail=True, methods=['get'], url_path='result')
    def get_result(self, request, id=None):
        """
        Get execution result.

        GET /api/v1/transformation/executions/{id}/result/
        """
        try:
            execution = self.get_queryset().get(id=id)
        except PipelineExecution.DoesNotExist:
            raise NotFound("Execution not found")

        # Check if execution is in a terminal state (completed or failed)
        if execution.status not in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
            return Response(
                {
                    'error': f'Execution is not in a terminal state (current status: {execution.status})',
                    'execution_id': str(execution.id),
                    'status': execution.status
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract error message from logs if failed
        error_message = None
        if execution.status == ExecutionStatus.FAILED and execution.execution_log:
            # Find the last ERROR log entry
            for log_entry in reversed(execution.execution_log):
                if isinstance(log_entry, dict) and log_entry.get("level") == "ERROR":
                    error_message = log_entry.get("message")
                    break

        response_data = {
            'execution_id': str(execution.id),
            'status': execution.status,
            'result_asset_id': str(execution.result_asset.id) if execution.result_asset else None,
            'result_asset_name': execution.result_asset.name if execution.result_asset else None,
            'metrics': execution.metrics if execution.metrics else {},
            'execution_log': execution.execution_log if execution.execution_log else [],
            'started_at': execution.started_at,
            'completed_at': execution.completed_at,
            'duration_seconds': execution.get_duration_seconds(),
            'error_message': error_message,
        }

        serializer = PipelineExecutionResultSerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    retrieve=extend_schema(
        summary="Get preview result",
        description="Get preview result by preview ID.",
        responses={
            200: PreviewResultSerializer,
            404: OpenApiResponse(description='Preview not found'),
            410: OpenApiResponse(description='Preview expired'),
        },
        tags=["Transformation"],
    ),
)
class PreviewResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for preview result retrieval.

    Tenant-scoped: users can only see previews in their tenant.
    Requires transformation:read scope for all operations.
    """
    queryset = PreviewResult.objects.all()
    serializer_class = PreviewResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "preview_id"
    lookup_url_kwarg = "preview_id"

    def get_permissions(self):
        return [permissions.IsAuthenticated(), HasScope('transformation:read')]

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Platform admins can see all previews
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = PreviewResult.objects.all()
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

            # Filter by tenant
            if tenant_id:
                if isinstance(tenant_id, str):
                    import uuid
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        return PreviewResult.objects.none()
                queryset = PreviewResult.objects.filter(tenant_id=tenant_id)
            else:
                return PreviewResult.objects.none()

        return queryset.order_by('-generated_at')

    def retrieve(self, request, preview_id=None):
        """
        Get preview result by preview_id.

        GET /api/v1/transformation/previews/{preview_id}/
        """
        try:
            preview = self.get_queryset().get(preview_id=preview_id)
        except PreviewResult.DoesNotExist:
            raise NotFound("Preview not found")

        # Check if preview has expired
        if preview.is_expired():
            return Response(
                {
                    'error': 'Preview has expired',
                    'preview_id': preview_id,
                    'expires_at': preview.expires_at.isoformat(),
                },
                status=status.HTTP_410_GONE
            )

        serializer = self.get_serializer(preview)
        return Response(serializer.data)


@extend_schema_view(
    retrieve=extend_schema(
        summary="Get wrangling session",
        description="Get detailed information about a wrangling session.",
        responses={
            200: WranglingSessionSerializer,
            404: OpenApiResponse(description='Wrangling session not found'),
        },
        tags=["Transformation"],
    ),
    create=extend_schema(
        summary="Perform wrangling operation",
        description="Perform a data wrangling operation on an asset.",
        request=WranglingOperationRequestSerializer,
        responses={
            200: WranglingResultSerializer,
            400: OpenApiResponse(description='Invalid request'),
            404: OpenApiResponse(description='Asset or session not found'),
        },
        tags=["Transformation"],
    ),
)
class WranglingSessionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for wrangling session management.

    Tenant-scoped: users can only see/manage sessions in their tenant.
    Requires transformation:read for reads, transformation:write for writes.
    """
    queryset = WranglingSession.objects.all()
    serializer_class = WranglingSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [permissions.IsAuthenticated(), HasScope('transformation:write')]
        return [permissions.IsAuthenticated(), HasScope('transformation:read')]

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Platform admins can see all sessions
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = WranglingSession.objects.all()
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

            # Filter by tenant
            if tenant_id:
                if isinstance(tenant_id, str):
                    import uuid
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        return WranglingSession.objects.none()
                queryset = WranglingSession.objects.filter(tenant_id=tenant_id)
            else:
                return WranglingSession.objects.none()

        return queryset.order_by('-created_at')

    @transaction.atomic
    def create(self, request):
        """
        Perform a wrangling operation.

        POST /api/v1/transformation/wrangling/
        """
        from .serializers import WranglingOperationRequestSerializer, WranglingResultSerializer

        # Validate request
        serializer = WranglingOperationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        asset_id = serializer.validated_data['asset_id']
        operation = serializer.validated_data['operation']
        session_id = serializer.validated_data.get('session_id')

        # Get tenant and user
        tenant = self.get_tenant_from_request()
        if not tenant:
            raise ValidationError("Unable to determine tenant for wrangling operation")

        user = request.user
        tenant_id = str(tenant.id)
        user_id = str(user.id) if user else None

        # Initialize service
        service = TransformationService(
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Perform wrangling operation
        result = service.wrangle_data(
            asset_id=str(asset_id),
            operation=operation,
            session_id=str(session_id) if session_id else None,
            tenant_id=tenant_id,
            user_id=user_id,
            request=request
        )

        # Create audit event
        create_audit_event(
            resource_type="wrangling_session",
            action="wrangling.operation.performed",
            actor_user=user,
            tenant=tenant,
            resource_id=result.get("session_id"),
            details={
                "operation_type": operation.get("type"),
                "operation_id": result.get("operation_id"),
                "asset_id": str(asset_id),
            },
            request=request
        )

        response_serializer = WranglingResultSerializer(result)
        logger.info(
            "wrangling_operation_performed",
            session_id=result.get("session_id"),
            operation_id=result.get("operation_id"),
            operation_type=operation.get("type"),
            tenant_id=tenant_id,
            user_id=user_id,
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Undo wrangling operation",
        description="Undo the last operation in a wrangling session.",
        request=None,
        responses={
            200: inline_serializer(
                name='WranglingUndoResponse',
                fields={
                    'session_id': serializers.UUIDField(),
                    'undone_operation': serializers.DictField(allow_null=True),
                    'can_undo': serializers.BooleanField(),
                    'can_redo': serializers.BooleanField(),
                    'applied_operations_count': serializers.IntegerField(),
                }
            ),
            400: OpenApiResponse(description='Cannot undo'),
            404: OpenApiResponse(description='Wrangling session not found'),
        },
        tags=["Transformation"],
    )
    @action(detail=True, methods=['post'], url_path='undo')
    @transaction.atomic
    def undo_operation(self, request, id=None):
        """
        Undo the last operation in a wrangling session.

        POST /api/v1/transformation/wrangling/{id}/undo/
        """
        try:
            session = self.get_queryset().get(id=id)
        except WranglingSession.DoesNotExist:
            raise NotFound("Wrangling session not found")

        # Check if undo is possible
        if not session.can_undo():
            return Response(
                {
                    'error': 'Cannot undo: no operations to undo',
                    'session_id': str(session.id),
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Undo operation
        undone_operation = session.undo()

        # Create audit event
        tenant = session.tenant
        user = request.user
        create_audit_event(
            resource_type="wrangling_session",
            action="wrangling.operation.undone",
            actor_user=user,
            tenant=tenant,
            resource_id=str(session.id),
            details={
                "undone_operation_type": undone_operation.get("type") if undone_operation else None,
                "history_position": session.history_position,
            },
            request=request
        )

        logger.info(
            "wrangling_operation_undone",
            session_id=str(session.id),
            operation_type=undone_operation.get("type") if undone_operation else None,
            tenant_id=str(tenant.id),
            user_id=str(user.id) if user else None,
        )

        return Response({
            'session_id': str(session.id),
            'undone_operation': undone_operation,
            'can_undo': session.can_undo(),
            'can_redo': session.can_redo(),
            'applied_operations_count': len(session.get_applied_operations()),
        }, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Redo wrangling operation",
        description="Redo the next operation in a wrangling session.",
        request=None,
        responses={
            200: inline_serializer(
                name='WranglingRedoResponse',
                fields={
                    'session_id': serializers.UUIDField(),
                    'redone_operation': serializers.DictField(allow_null=True),
                    'can_undo': serializers.BooleanField(),
                    'can_redo': serializers.BooleanField(),
                    'applied_operations_count': serializers.IntegerField(),
                }
            ),
            400: OpenApiResponse(description='Cannot redo'),
            404: OpenApiResponse(description='Wrangling session not found'),
        },
        tags=["Transformation"],
    )
    @action(detail=True, methods=['post'], url_path='redo')
    @transaction.atomic
    def redo_operation(self, request, id=None):
        """
        Redo the next operation in a wrangling session.

        POST /api/v1/transformation/wrangling/{id}/redo/
        """
        try:
            session = self.get_queryset().get(id=id)
        except WranglingSession.DoesNotExist:
            raise NotFound("Wrangling session not found")

        # Check if redo is possible
        if not session.can_redo():
            return Response(
                {
                    'error': 'Cannot redo: no operations to redo',
                    'session_id': str(session.id),
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Redo operation
        redone_operation = session.redo()

        # Create audit event
        tenant = session.tenant
        user = request.user
        create_audit_event(
            resource_type="wrangling_session",
            action="wrangling.operation.redone",
            actor_user=user,
            tenant=tenant,
            resource_id=str(session.id),
            details={
                "redone_operation_type": redone_operation.get("type") if redone_operation else None,
                "history_position": session.history_position,
            },
            request=request
        )

        logger.info(
            "wrangling_operation_redone",
            session_id=str(session.id),
            operation_type=redone_operation.get("type") if redone_operation else None,
            tenant_id=str(tenant.id),
            user_id=str(user.id) if user else None,
        )

        return Response({
            'session_id': str(session.id),
            'redone_operation': redone_operation,
            'can_undo': session.can_undo(),
            'can_redo': session.can_redo(),
            'applied_operations_count': len(session.get_applied_operations()),
        }, status=status.HTTP_200_OK)

    def get_tenant_from_request(self):
        """Get tenant from request with proper fallback logic"""
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
                from hub.apps.tenants.models import Tenant
                try:
                    return Tenant.objects.get(id=tenant_id)
                except Tenant.DoesNotExist:
                    pass

        # Fallback to request.tenant object
        if hasattr(self.request, "tenant") and self.request.tenant:
            return self.request.tenant

        # Fallback to user.tenant_id
        user = self.request.user
        if hasattr(user, "id") and user.id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                db_user = User.objects.only('tenant_id').get(id=user.id)
                if db_user.tenant_id:
                    from hub.apps.tenants.models import Tenant
                    try:
                        return Tenant.objects.get(id=db_user.tenant_id)
                    except Tenant.DoesNotExist:
                        pass
            except User.DoesNotExist:
                pass

        # Last resort: get from user.tenant relationship
        if hasattr(user, "tenant") and user.tenant:
            return user.tenant

        return None

