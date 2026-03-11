"""
Tenant Views

REST API views for tenant management.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hub.apps.audit.utils import log_tenant_operation
from hub.apps.auth.permissions import HasRole
from hub.apps.billing.services import SubscriptionService

from .models import Tenant, TenantConfig, TenantStatus
from .permissions import IsPlatformAdmin
from .request_tenant import get_request_tenant_id
from .serializers import (
    TenantConfigSerializer,
    TenantConfigUpdateSerializer,
    TenantCreateSerializer,
    TenantOnboardingSerializer,
    TenantReactivateSerializer,
    TenantSerializer,
    TenantSuspendSerializer,
    TenantUpdateSerializer,
    TenantUsageSerializer,
)
from .services import TenantOnboardingService, TenantService, TenantUsageService, get_tenant_config


class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for tenant management.

    Only platform admins can manage tenants.
    """

    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    lookup_field = "id"

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return TenantCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return TenantUpdateSerializer
        return TenantSerializer

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        # Platform admins can see all tenants
        # Regular users can only see their own tenant
        user = self.request.user

        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return Tenant.objects.all()

        # For now, return all (will be filtered by tenant_id in middleware)
        return Tenant.objects.all()

    # Permission check is handled by IsPlatformAdmin permission class

    def list(self, request, *args, **kwargs):
        """List tenants (paginated)"""
        return super().list(request, *args, **kwargs)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new tenant.

        Creates tenant with ACTIVE status and UNVERIFIED KYC status.
        Default roles are created via signal.
        Events are published automatically via TenantService.
        """
        serializer = TenantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Use TenantService to create tenant (publishes events automatically)
        service = TenantService(
            tenant_id=None, user_id=str(request.user.id)  # Platform admin operations
        )
        tenant = service.create_tenant(
            name=serializer.validated_data["name"],
            slug=serializer.validated_data["slug"],
            region=serializer.validated_data.get("region"),
        )

        # Log audit event
        log_tenant_operation(
            action="TENANT_CREATED",
            tenant=tenant,
            actor_user=request.user,
            details={"name": tenant.name, "slug": tenant.slug},
            request=request,
        )

        return Response(TenantSerializer(tenant).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve tenant by ID"""
        tenant = self.get_object()
        return Response(TenantSerializer(tenant).data)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update tenant (full update).

        Events are published automatically via TenantService.
        """
        tenant = self.get_object()
        serializer = TenantUpdateSerializer(tenant, data=request.data)
        serializer.is_valid(raise_exception=True)

        # Use TenantService to update tenant (publishes events automatically)
        service = TenantService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        tenant = service.update_tenant(
            tenant_id=str(tenant.id),
            name=serializer.validated_data.get("name"),
            slug=serializer.validated_data.get("slug"),
            kyc_status=serializer.validated_data.get("kyc_status"),
            region=serializer.validated_data.get("region"),
        )

        # Log audit event
        log_tenant_operation(
            action="TENANT_UPDATED",
            tenant=tenant,
            actor_user=request.user,
            details=serializer.validated_data,
            request=request,
        )

        return Response(TenantSerializer(tenant).data)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """
        Update tenant (partial update).

        Events are published automatically via TenantService.
        """
        tenant = self.get_object()
        serializer = TenantUpdateSerializer(tenant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Use TenantService to update tenant (publishes events automatically)
        service = TenantService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        tenant = service.update_tenant(
            tenant_id=str(tenant.id),
            name=serializer.validated_data.get("name"),
            slug=serializer.validated_data.get("slug"),
            kyc_status=serializer.validated_data.get("kyc_status"),
            region=serializer.validated_data.get("region"),
        )

        # Log audit event
        log_tenant_operation(
            action="TENANT_UPDATED",
            tenant=tenant,
            actor_user=request.user,
            details=serializer.validated_data,
            request=request,
        )

        return Response(TenantSerializer(tenant).data)

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, id=None):
        """
        Suspend a tenant.

        Sets status to SUSPENDED and blocks write operations.
        Sends notification to tenant admins.
        """
        tenant = self.get_object()

        if tenant.status == TenantStatus.DELETED:
            return Response(
                {"error": "Cannot suspend a deleted tenant"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = TenantSuspendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Suspend tenant
        tenant.suspend()

        # Send notification to tenant admins
        self._send_suspension_notification(tenant, serializer.validated_data.get("reason"))

        # Log audit event
        log_tenant_operation(
            action="TENANT_SUSPENDED",
            tenant=tenant,
            actor_user=request.user,
            details={"reason": serializer.validated_data.get("reason")},
            request=request,
        )

        return Response(TenantSerializer(tenant).data, status=status.HTTP_200_OK)

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, id=None):
        """
        Reactivate a suspended tenant.

        Sets status to ACTIVE and restores write operations.
        Sends notification to tenant admins.
        """
        tenant = self.get_object()

        if tenant.status != TenantStatus.SUSPENDED:
            return Response(
                {"error": "Can only reactivate suspended tenants"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TenantReactivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Reactivate tenant
        tenant.reactivate()

        # Send notification to tenant admins
        self._send_reactivation_notification(tenant)

        # Log audit event
        log_tenant_operation(
            action="TENANT_REACTIVATED",
            tenant=tenant,
            actor_user=request.user,
            details={},
            request=request,
        )

        return Response(TenantSerializer(tenant).data, status=status.HTTP_200_OK)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a tenant (soft delete).

        Sets status to DELETED and blocks all access.
        Data retention period begins (default: 30 days).
        Events are published automatically via TenantService.
        """
        tenant = self.get_object()

        # Use TenantService to delete tenant (publishes events automatically)
        service = TenantService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        tenant = service.delete_tenant(
            tenant_id=str(tenant.id),
            reason=request.data.get("reason") if hasattr(request, "data") else None,
        )

        # Log audit event
        log_tenant_operation(
            action="TENANT_DELETED",
            tenant=tenant,
            actor_user=request.user,
            details={},
            request=request,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _send_suspension_notification(self, tenant, reason=None):
        """Send suspension notification to tenant admins (placeholder)"""
        # TODO: Implement email notification when notification service is ready
        # from hub.apps.users.models import User
        # admins = User.objects.filter(
        #     tenant=tenant,
        #     roles__name="TENANT_ADMIN",
        #     status="ACTIVE"
        # )
        # for admin in admins:
        #     send_email(admin.email, "tenant_suspended", {"tenant": tenant, "reason": reason})
        pass

    def _send_reactivation_notification(self, tenant):
        """Send reactivation notification to tenant admins (placeholder)"""
        # TODO: Implement email notification when notification service is ready
        # from hub.apps.users.models import User
        # admins = User.objects.filter(
        #     tenant=tenant,
        #     roles__name="TENANT_ADMIN",
        #     status="ACTIVE"
        # )
        # for admin in admins:
        #     send_email(admin.email, "tenant_reactivated", {"tenant": tenant})
        pass


class TenantConfigViewSet(viewsets.ViewSet):
    """
    ViewSet for tenant configuration management.

    Allows TENANT_ADMIN (for own tenant) or Platform Admin (for any tenant)
    to get and update tenant configuration.
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "tenant_id"

    def get_permissions(self):
        """Return appropriate permissions based on action"""
        if self.action == "onboarding":
            # Onboarding endpoint allows unauthenticated access
            return [permissions.AllowAny()]
        # Other actions require authentication
        return [IsAuthenticated()]

    def get_tenant(self, tenant_id: str) -> Tenant:
        """Get tenant by ID with permission check"""
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            from rest_framework.exceptions import NotFound

            not_found = NotFound("Tenant not found")
            not_found.code = "TENANT_NOT_FOUND"  # Set specific error code per API spec
            raise not_found

        # Check permissions: Platform Admin can access any tenant,
        # TENANT_ADMIN can only access own tenant
        user = self.request.user

        # Platform admins have access to all tenants
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return tenant

        # TENANT_ADMIN can only access own tenant
        if hasattr(user, "tenant") and user.tenant.id == tenant.id:
            # Check if user has TENANT_ADMIN role
            if hasattr(user, "user_roles"):
                role_names = [ur.role.name for ur in user.user_roles.all()]
                if "TENANT_ADMIN" in role_names:
                    return tenant

        # No permission
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied("You do not have permission to access this tenant configuration.")

    @extend_schema(
        operation_id="get_tenant_config",
        summary="Get tenant configuration",
        description="Get tenant configuration with platform defaults for any unset values. Returns configuration matching API spec §13.1.",
        responses={
            200: TenantConfigSerializer,
            401: OpenApiResponse(description="Unauthorized - missing or invalid bearer token"),
            403: OpenApiResponse(
                description="Forbidden - user lacks TENANT_ADMIN role or Platform Admin privileges"
            ),
            404: OpenApiResponse(description="Tenant not found"),
        },
        tags=["Tenants"],
    )
    def retrieve(self, request, tenant_id=None, **kwargs):
        """
        Get tenant configuration.

        Returns tenant configuration with platform defaults for any unset values.
        """
        # Extract tenant_id from kwargs if not provided directly
        if tenant_id is None:
            tenant_id = kwargs.get("tenant_id")
        tenant = self.get_tenant(tenant_id)
        config_dict = get_tenant_config(tenant)

        return Response(config_dict, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="update_tenant_config",
        summary="Update tenant configuration",
        description="Update tenant configuration (partial update). Updates only the provided fields, leaving others unchanged. Returns updated configuration matching API spec §13.2.",
        request=TenantConfigUpdateSerializer,
        responses={
            200: TenantConfigSerializer,
            400: OpenApiResponse(description="Validation error - invalid configuration values"),
            401: OpenApiResponse(description="Unauthorized - missing or invalid bearer token"),
            403: OpenApiResponse(
                description="Forbidden - user lacks TENANT_ADMIN role or Platform Admin privileges"
            ),
            404: OpenApiResponse(description="Tenant not found"),
        },
        tags=["Tenants"],
    )
    @transaction.atomic
    def partial_update(self, request, tenant_id=None, **kwargs):
        """
        Update tenant configuration (partial update).

        Updates only the provided fields, leaving others unchanged.
        Events are published automatically via TenantService for quota changes.
        """
        # Extract tenant_id from kwargs if not provided directly
        if tenant_id is None:
            tenant_id = kwargs.get("tenant_id")
        tenant = self.get_tenant(tenant_id)

        # Get or create tenant config for validation
        config, created = TenantConfig.objects.get_or_create(tenant=tenant)

        serializer = TenantConfigUpdateSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Use TenantService to update config (publishes quota change events automatically)
        service = TenantService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        service.update_tenant_config(
            tenant_id=str(tenant.id),
            default_dq_profile=serializer.validated_data.get("default_dq_profile"),
            allowed_compliance_regimes=serializer.validated_data.get("allowed_compliance_regimes"),
            default_compliance_regimes=serializer.validated_data.get("default_compliance_regimes"),
            data_retention_days=serializer.validated_data.get("data_retention_days"),
            rate_limits=serializer.validated_data.get("rate_limits"),
            max_file_size_bytes=serializer.validated_data.get("max_file_size_bytes"),
            max_job_concurrency=serializer.validated_data.get("max_job_concurrency"),
            max_queued_jobs=serializer.validated_data.get("max_queued_jobs"),
            trust_signals_enabled=serializer.validated_data.get("trust_signals_enabled"),
            versioning_enabled=serializer.validated_data.get("versioning_enabled"),
            workflows_enabled=serializer.validated_data.get("workflows_enabled"),
        )

        # Log audit event
        log_tenant_operation(
            action="TENANT_CONFIG_UPDATED",
            tenant=tenant,
            actor_user=request.user,
            details=serializer.validated_data,
            request=request,
        )

        # Return complete config with defaults
        config_dict = get_tenant_config(tenant)
        return Response(config_dict, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path="onboarding",
        permission_classes=[permissions.AllowAny],
    )
    @transaction.atomic
    def onboarding(self, request):
        """
        Self-service tenant creation with first user.

        POST /api/v1/tenants/onboarding/
        Body: {
            "name": "My Company",
            "slug": "my-company",
            "plan_slug": "free",  # Optional, defaults to "free"
            "first_user": {
                "email": "admin@example.com",
                "password": "securepassword123",
                "display_name": "Admin User"  # Optional
            },
            "region": "us-east-1"  # Optional
        }

        Creates:
        - Tenant with specified plan
        - First user (tenant admin)
        - TenantConfig with platform defaults
        - Stripe customer and subscription (if not FREE plan)
        """
        serializer = TenantOnboardingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        first_user_data = serializer.validated_data["first_user"]

        service = TenantOnboardingService()
        try:
            result = service.create_tenant_with_first_user(
                name=serializer.validated_data["name"],
                slug=serializer.validated_data["slug"],
                plan_slug=serializer.validated_data.get("plan_slug", "free"),
                first_user_email=first_user_data["email"],
                first_user_password=first_user_data["password"],
                first_user_display_name=first_user_data.get("display_name"),
                region=serializer.validated_data.get("region"),
            )

            # Return tenant and user info (don't return password)
            from hub.apps.users.serializers import UserSerializer

            return Response(
                {
                    "tenant": TenantSerializer(result["tenant"]).data,
                    "user": UserSerializer(result["user"]).data,
                    "subscription_id": (
                        str(result["subscription"].id) if result["subscription"] else None
                    ),
                    "plan": {
                        "slug": result["plan"].slug,
                        "name": result["plan"].name,
                        "tier": result["plan"].tier,
                    },
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            from hub.apps.core.responses import handle_service_exception
            from hub.apps.core.services.base import NotFoundError
            from hub.apps.core.services.base import ValidationError as ServiceValidationError

            if isinstance(e, (ServiceValidationError, NotFoundError)):
                return handle_service_exception(e)
            raise

    @extend_schema(
        operation_id="get_me_config",
        summary="Get current tenant configuration",
        description="Get tenant configuration for the authenticated user's tenant. Returns config with platform defaults for unset values.",
        responses={
            200: TenantConfigSerializer,
            400: OpenApiResponse(description="Tenant context required"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden - TENANT_ADMIN or Platform Admin required"),
        },
        tags=["Tenants"],
    )
    @extend_schema(
        operation_id="patch_me_config",
        summary="Update current tenant configuration",
        description="Update tenant configuration (partial) for the authenticated user's tenant.",
        request=TenantConfigUpdateSerializer,
        responses={
            200: TenantConfigSerializer,
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden - TENANT_ADMIN or Platform Admin required"),
        },
        tags=["Tenants"],
        methods=["PATCH"],
    )
    @action(detail=False, methods=["get", "patch"], url_path="me/config")
    def me_config(self, request):
        """
        Get or update tenant configuration for current user's tenant.

        GET /api/v1/tenants/me/config/
        PATCH /api/v1/tenants/me/config/
        """
        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant context required"}, status=status.HTTP_400_BAD_REQUEST
            )

        tenant = self.get_tenant(tenant_id)

        if request.method == "GET":
            config_dict = get_tenant_config(tenant)
            return Response(config_dict, status=status.HTTP_200_OK)

        # PATCH
        config, _ = TenantConfig.objects.get_or_create(tenant=tenant)
        serializer = TenantConfigUpdateSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        service = TenantService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        service.update_tenant_config(
            tenant_id=str(tenant.id),
            default_dq_profile=serializer.validated_data.get("default_dq_profile"),
            allowed_compliance_regimes=serializer.validated_data.get(
                "allowed_compliance_regimes"
            ),
            default_compliance_regimes=serializer.validated_data.get(
                "default_compliance_regimes"
            ),
            data_retention_days=serializer.validated_data.get("data_retention_days"),
            rate_limits=serializer.validated_data.get("rate_limits"),
            max_file_size_bytes=serializer.validated_data.get("max_file_size_bytes"),
            max_job_concurrency=serializer.validated_data.get("max_job_concurrency"),
            max_queued_jobs=serializer.validated_data.get("max_queued_jobs"),
            trust_signals_enabled=serializer.validated_data.get("trust_signals_enabled"),
            versioning_enabled=serializer.validated_data.get("versioning_enabled"),
            workflows_enabled=serializer.validated_data.get("workflows_enabled"),
        )

        log_tenant_operation(
            action="TENANT_CONFIG_UPDATED",
            tenant=tenant,
            actor_user=request.user,
            details=serializer.validated_data,
            request=request,
        )

        config_dict = get_tenant_config(tenant)
        return Response(config_dict, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="get_me_usage",
        summary="Get current tenant usage",
        description="Get usage metrics (storage, API calls, limits) for the authenticated user's tenant.",
        responses={
            200: TenantUsageSerializer,
            400: OpenApiResponse(description="Tenant context required"),
            401: OpenApiResponse(description="Unauthorized"),
        },
        tags=["Tenants"],
    )
    @action(detail=False, methods=["get"], url_path="me/usage")
    def usage(self, request):
        """
        Get current usage for tenant.

        GET /api/v1/tenants/me/usage/

        Returns current usage metrics and plan limits.
        """
        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant context required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get current usage
        usage_service = TenantUsageService(tenant_id=tenant_id)
        current_usage = usage_service.get_current_usage(tenant_id=tenant_id)

        # Get tenant and plan limits
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)
        plan = tenant.plan
        if not plan:
            # Default to FREE plan
            from hub.apps.tenants.models import TenantPlan

            plan = TenantPlan.objects.filter(slug="free", is_active=True).first()

        plan_limits = {}
        usage_percentages = {}

        if plan:
            plan_limits = plan.limits_json.copy()

            # Calculate usage percentages
            for limit_key, max_limit in plan_limits.items():
                if max_limit is None:
                    usage_percentages[limit_key] = None  # Unlimited
                else:
                    current = current_usage.get(f"{limit_key.replace('max_', '')}_count", 0)
                    if limit_key == "max_storage_gb":
                        current = current_usage.get("storage_gb", 0)
                    elif limit_key == "max_api_calls_per_month":
                        current = current_usage.get("api_calls_this_month", 0)
                    else:
                        # Map limit keys to usage keys
                        usage_key_map = {
                            "max_assets": "asset_count",
                            "max_datasets": "dataset_count",
                            "max_scheduled_ingestions": "scheduled_ingestion_count",
                            "max_scheduled_exports": "scheduled_export_count",
                        }
                        usage_key = usage_key_map.get(limit_key)
                        if usage_key:
                            current = current_usage.get(usage_key, 0)

                    percentage = (current / max_limit * 100) if max_limit > 0 else 0
                    usage_percentages[limit_key] = min(percentage, 100.0)

        # Build response
        response_data = {
            **current_usage,
            "plan_limits": plan_limits,
            "usage_percentages": usage_percentages,
            "plan_slug": plan.slug if plan else None,
            "plan_tier": plan.tier if plan else None,
        }

        serializer = TenantUsageSerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)
