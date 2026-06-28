"""
Tenant Views

REST API views for tenant management.
"""

import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hub.apps.api.e2e_gating import is_e2e_environment, verify_e2e_token
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.utils import create_audit_event, log_tenant_operation
from hub.apps.billing.serializers import TenantPlanAdminSerializer
from hub.apps.compliance.models import RiskLevel
from hub.apps.core.responses import handle_service_exception
from hub.apps.core.services.base import ServiceError

from .models import PlanCategory, Tenant, TenantConfig, TenantPlan, TenantStatus
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

logger = logging.getLogger(__name__)


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
            tenant_id=None,
            user_id=str(request.user.id),  # Platform admin operations
        )
        try:
            tenant = service.create_tenant(
                name=serializer.validated_data["name"],
                slug=serializer.validated_data["slug"],
                region=serializer.validated_data.get("region"),
            )
        except ServiceError as e:
            return handle_service_exception(e)

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
        # Use all_objects to also find soft-deleted tenants so we can
        # return a meaningful 400 instead of a misleading 404.
        tenant = get_object_or_404(Tenant.all_objects, pk=id)
        self.check_object_permissions(request, tenant)

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

        Query ``?cascade=true`` — **test/staging gated**: platform-admin hard-delete with
        E2E token; removes User rows (RESTRICT), then Tenant row → DB CASCADE removes
        File rows; ``pre_delete`` schedules S3 purges ``on_commit`` (Phase 260.1.F).
        """
        tenant = self.get_object()
        cascade_raw = request.query_params.get("cascade")
        cascade_hard = str(cascade_raw or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if cascade_hard:
            if not is_e2e_environment():
                return Response(
                    {"detail": "Tenant hard-delete cascade is not enabled in this environment."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if not verify_e2e_token(request):
                return Response(
                    {"detail": "X-E2E-Token header required for cascade delete."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return self._hard_delete_tenant_cascade(request, tenant)

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

    def _hard_delete_tenant_cascade(self, request, tenant: Tenant):
        """E2E / operator hard-delete — DB CASCADE + storage purge callbacks (Phase 260.1.F).

        Audit placement: per-file ``FILE_TENANT_OFFBOARD_PURGE_SCHEDULED`` audit
        events are emitted BEFORE ``tenant.delete()`` so the Tenant FK is still valid;
        the operator summary row is appended after the row hard-delete completes.
        """
        from hub.apps.files.models import File
        from hub.apps.users.models import User

        tid = tenant.pk
        slug = getattr(tenant, "slug", None)
        tenant_id_str = str(tid)

        # Emit per-file audit events before cascade delete
        files = File.objects.filter(tenant_id=tid)
        for f in files:
            create_audit_event(
                resource_type="FILE",
                action=audit_event_types.FILE_TENANT_OFFBOARD_PURGE_SCHEDULED,
                actor_user=request.user,
                tenant=tenant,
                resource_id=str(f.id),
                details={
                    "tenant_id": tenant_id_str,
                    "file_id": str(f.id),
                    "name": f.name,
                    "size": f.size if f.size else 0,
                    "content_sha256": getattr(f, "content_sha256", "") or "",
                    "storage_path": getattr(f, "storage_path", "") or "",
                    "reason": "tenant_hard_delete",
                },
                request=request,
            )

        User.objects.filter(tenant_id=tid).delete()
        tenant.delete()
        create_audit_event(
            resource_type="TENANT",
            action=audit_event_types.TENANT_HARD_DELETE_CASCADE,
            actor_user=request.user,
            tenant=None,
            resource_id=tenant_id_str,
            details={"tenant_id": tenant_id_str, "slug": slug},
            request=request,
            infer_tenant_from_actor=False,
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
        config, _created = TenantConfig.objects.get_or_create(tenant=tenant)

        prev_compliance_thr = str(
            getattr(config, "compliance_risk_threshold", RiskLevel.HIGH.value)
        )

        serializer = TenantConfigUpdateSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Use TenantService to update config (publishes quota change events automatically).
        # For explicit None values (field clearing), update directly on the config model
        # since the service treats None as "not provided" (sentinel).
        service = TenantService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        vd = serializer.validated_data

        # Handle explicit None values: set directly on config before service call
        null_fields = []
        for field_name in list(vd.keys()):
            if vd[field_name] is None and field_name in request.data:
                setattr(config, field_name, None)
                null_fields.append(field_name)
        if null_fields:
            config.save(update_fields=null_fields + ["updated_at"])

        # Pass non-None values through the service for event publishing
        service_kwargs = {k: v for k, v in vd.items() if v is not None}
        if service_kwargs:
            service.update_tenant_config(tenant_id=str(tenant.id), **service_kwargs)

        # Log audit event
        log_tenant_operation(
            action="TENANT_CONFIG_UPDATED",
            tenant=tenant,
            actor_user=request.user,
            details=serializer.validated_data,
            request=request,
        )

        if "compliance_risk_threshold" in vd:
            cfg_fresh = TenantConfig.objects.get(pk=config.pk)
            new_thr = str(getattr(cfg_fresh, "compliance_risk_threshold", RiskLevel.HIGH.value))
            if new_thr != prev_compliance_thr:
                try:
                    create_audit_event(
                        resource_type="TENANT",
                        action=audit_event_types.TENANT_COMPLIANCE_THRESHOLD_CHANGED,
                        actor_user=request.user,
                        tenant=tenant,
                        resource_id=str(tenant.id),
                        details={
                            "tenant_id": str(tenant.id),
                            "previous_threshold": prev_compliance_thr,
                            "new_threshold": new_thr,
                        },
                        request=request,
                    )
                except Exception as exc:
                    logger.warning(
                        "tenant_compliance_threshold_audit_failed",
                        extra={
                            "error": str(exc),
                            "tenant_id": str(tenant.id),
                        },
                        exc_info=True,
                    )

        # Return complete config with defaults
        config_dict = get_tenant_config(tenant)
        return Response(config_dict, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path="onboarding",
        permission_classes=[permissions.IsAuthenticated],
    )
    @transaction.atomic
    def onboarding(self, request):
        """
        Tenant creation with first user (Platform Admin only).

        POST /api/v1/tenants/onboarding/
        Requires: IsAuthenticated + PLATFORM_ADMIN role.
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
        # Only Platform Admins can create organizations.
        # Checks is_platform_admin (project-specific field), is_superuser
        # (Django PermissionsMixin), and PLATFORM_ADMIN role assignment.
        if not (
            getattr(request.user, "is_platform_admin", False)
            or request.user.is_superuser
            or (
                hasattr(request.user, "user_roles")
                and request.user.user_roles.filter(role__name="PLATFORM_ADMIN").exists()
            )
        ):
            return Response(
                {"error": "Organization creation requires PLATFORM_ADMIN role."},
                status=status.HTTP_403_FORBIDDEN,
            )

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

        log_tenant_operation(
            action="TENANT_CONFIG_UPDATED",
            tenant=tenant,
            actor_user=request.user,
            details=serializer.validated_data,
            request=request,
        )

        config_dict = get_tenant_config(tenant)
        return Response(config_dict, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # Phase 250.6.E — per-tenant feature-flags admin surface
    # ------------------------------------------------------------------

    #: Per-tenant capability flags surfaced by the admin settings
    #: page. Each entry is ``(field_name, description)``. Adding a new
    #: per-tenant boolean flag to ``Tenant`` should ALSO add an entry
    #: here so the admin UI surfaces it without code changes elsewhere.
    #: The list is the single source of truth — the GET endpoint
    #: reflects it as the response shape, the PATCH endpoint
    #: validates incoming flag names against it, and the audit-log
    #: query relies on it to filter the resource_type='TENANT' rows.
    _TENANT_FEATURE_FLAGS: tuple = (
        (
            "asset_creation_enabled",
            "When True (default), this tenant may create assets via "
            "POST /assets/ and POST /assets/data-first/. Flip to False "
            "to FREEZE creation under investigation (compliance breach, "
            "billing dispute, etc.). Phase 250.6.A / D250.17.",
        ),
        (
            "datasets_enabled",
            "When True (default), Dataset REST API (/api/v1/datasets/*) is "
            "enabled. When False, returns 403 DATASETS_DISABLED. Phase 260.3.B.",
        ),
        (
            "files_enabled",
            "When True (default), File REST API (/api/v1/files/*) is "
            "enabled. When False, returns 403 FILES_DISABLED. Phase 260.3.B.",
        ),
        (
            "federated_import_enabled",
            "When True, this tenant may import federated assets from "
            "configured marketplace connections. Default False — opt-in "
            "per D250.3 to prevent accidental activation. Phase 250.5.A.2.",
        ),
        (
            "asset_auto_activate_on_gate_pass",
            "When True (default), the asset-creation workflow auto-"
            "activates an Asset (DRAFT → ACTIVE) once all gates pass. "
            "Flip to False for a per-tenant DRAFT-first review queue. "
            "Phase 250.2.A.1 / D250.6.",
        ),
        (
            "compliance_fail_closed_enabled",
            "When True (default), a FAIL on the pre-persistence "
            "compliance gate refuses asset intake (HTTP 422). When "
            "False, the asset still lands as DRAFT but with a "
            "compliance_status=FAIL marker. Phase 250.1.A.8.",
        ),
        (
            "data_quality_enabled",
            "When True (default), the tenant has access to the Data "
            "Quality feature suite (DQ runs, alerts, profiles). When "
            "False, DQ endpoints return 403 + the SPA hides the DQ "
            "menu. Phase 240.4.B.4 / D240.18.",
        ),
        (
            "data_quality_advanced_enabled",
            "When True (and ``data_quality_enabled`` is also True), "
            "the tenant has access to advanced DQ features (anomaly "
            "detection, trend analysis, scorecards, RCA). Conjunctive "
            "with the base flag — disabling the base also disables "
            "this. Phase 240.3.B.",
        ),
        (
            "compliance_consent_enabled",
            "When True, the Phase 232.1 consent subsystem is active: purposes, "
            "HMAC-bound consent records, signup/marketplace/webhook gates, "
            "and consent webhooks. Default False — explicit opt-in.",
        ),
        (
            "compliance_ropa_enabled",
            "When True, RoPA generation endpoints and history are enabled for handlers "
            "(Phase 232.4). Default False — explicit opt-in.",
        ),
        (
            "compliance_dpia_enabled",
            "When True, DPIA register, wizard, DPO review queue, and asset DPIA badges "
            "are enabled (Phase 232.5). Default False — explicit opt-in.",
        ),
        (
            "compliance_dsar_enabled",
            "When True, public DSAR ingress and tenant DSAR handler queue are enabled "
            "(Phase 232.2). Default False — explicit opt-in; requires appropriate DPA tier.",
        ),
        (
            "compliance_breach_enabled",
            "When True, breach incident register, templates, and statutory notification flows "
            "are enabled (Phase 232.3). Default False — explicit opt-in.",
        ),
        (
            "compliance_processor_agreements_enabled",
            "When True, Article 28 processor register, agreements, and asset–processor links "
            "are enabled (Phase 232.6). Default False — explicit opt-in.",
        ),
        (
            "compliance_retention_enforcer_enabled",
            "When True, Phase 232.7 retention auto-sweep may tombstone datasets/assets after "
            "expiry and hard-delete following a 90-day grace. Default False — explicit opt-in.",
        ),
        (
            "compliance_audit_full_sampling",
            "When True, every successful GET /api/v1/files/{id}/ emits a FILE_METADATA_VIEWED "
            "audit row (Phase 260.2.F). When False (default), ~10% deterministic sampling applies.",
        ),
    )

    def _enforce_tenant_admin(self, request):
        """Phase 250.6.E.2 — TENANT_ADMIN-only gate. Returns ``None``
        when the user is allowed, OR a ``Response(403)`` object
        otherwise. Mirrors the gate-helper pattern from
        ``hub/apps/assets/views.py::_check_asset_creation_kill_switch``."""
        user = request.user
        is_tenant_admin = user.has_role("TENANT_ADMIN") if hasattr(user, "has_role") else False
        is_platform_admin = hasattr(user, "is_platform_admin") and user.is_platform_admin
        if is_tenant_admin or is_platform_admin:
            return None
        return Response(
            {
                "error": (
                    "Permission denied: TENANT_ADMIN role required to manage tenant feature flags."
                ),
                "code": "PERMISSION_DENIED",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    @action(
        detail=False,
        methods=["get", "patch"],
        url_path="me/feature-flags",
        url_name="me-feature-flags",
    )
    def me_feature_flags(self, request):
        """Phase 250.6.E.1 — per-tenant capability-flags admin surface.

        ``GET`` returns the current flag values + descriptions, so the
        SPA can render a self-describing settings page without a
        separate "schema" round-trip:

            {
              "flags": [
                {"name": "asset_creation_enabled", "value": true,
                 "description": "When True (default), ..."},
                ...
              ]
            }

        ``PATCH`` accepts a partial dict of ``{flag_name: bool}`` and
        flips the matching ``Tenant`` columns. Each flipped flag
        emits a ``TENANT_FEATURE_FLAG_UPDATED`` audit row carrying
        the before/after values for the audit-log panel below the
        form. Unknown flag names return HTTP 400 + ``code="UNKNOWN_FLAG"``
        rather than silently ignoring them — admin actions need
        loud rejection on typos so the operator knows their change
        DIDN'T land.

        Both methods require TENANT_ADMIN role (per 250.6.E.2).
        """
        gate = self._enforce_tenant_admin(request)
        if gate is not None:
            return gate

        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant context required", "code": "NO_TENANT"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from hub.apps.tenants.models import Tenant as _Tenant

        tenant = _Tenant.all_objects.get(id=tenant_id)

        if request.method == "GET":
            flags = [
                {
                    "name": name,
                    "value": bool(getattr(tenant, name, False)),
                    "description": description,
                }
                for name, description in self._TENANT_FEATURE_FLAGS
            ]
            return Response({"flags": flags}, status=status.HTTP_200_OK)

        # PATCH
        body = request.data or {}
        if not isinstance(body, dict):
            return Response(
                {"error": "Request body must be a JSON object", "code": "INVALID_REQUEST"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        known_flag_names = {n for n, _ in self._TENANT_FEATURE_FLAGS}
        unknown = [k for k in body.keys() if k not in known_flag_names]
        if unknown:
            return Response(
                {
                    "error": (
                        f"Unknown feature flag(s): {sorted(unknown)}. "
                        f"Known flags: {sorted(known_flag_names)}."
                    ),
                    "code": "UNKNOWN_FLAG",
                    "details": {
                        "unknown": sorted(unknown),
                        "known": sorted(known_flag_names),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Capture before-values for audit before mutating.
        before_values = {name: bool(getattr(tenant, name, False)) for name in body.keys()}
        # Apply each flag.
        update_fields = []
        for name, value in body.items():
            setattr(tenant, name, bool(value))
            update_fields.append(name)
        tenant.save(update_fields=update_fields + ["updated_at"])

        # Audit one row per flipped flag for forensic granularity.
        from hub.apps.audit import event_types as _audit_event_types
        from hub.apps.audit.utils import create_audit_event

        for name, new_value_raw in body.items():
            new_value = bool(new_value_raw)
            try:
                create_audit_event(
                    resource_type="TENANT",
                    action=_audit_event_types.TENANT_FEATURE_FLAG_UPDATED,
                    actor_user=request.user,
                    tenant=tenant,
                    resource_id=str(tenant.id),
                    result="SUCCESS",
                    details={
                        "flag_name": name,
                        "previous_value": before_values[name],
                        "new_value": new_value,
                        "actor_user_id": str(request.user.id),
                        "tenant_id": str(tenant.id),
                    },
                    request=request,
                )
            except Exception as exc:
                # Best-effort: audit emission failure logs a warning
                # but doesn't roll back the flag write (the operator
                # already committed the intent; losing the audit row
                # is recoverable via DB diff).
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "tenant_feature_flag_audit_emit_failed",
                    extra={
                        "flag_name": name,
                        "tenant_id": str(tenant.id),
                        "error": str(exc),
                    },
                )

        # Return the fresh flag map so the SPA can re-render without
        # a follow-up GET.
        flags = [
            {
                "name": name,
                "value": bool(getattr(tenant, name, False)),
                "description": description,
            }
            for name, description in self._TENANT_FEATURE_FLAGS
        ]
        return Response({"flags": flags}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["get"],
        url_path="me/feature-flag-history",
        url_name="me-feature-flag-history",
    )
    def me_feature_flag_history(self, request):
        """Phase 250.6.E.1 — audit-log query for the settings page.

        ``GET /api/v1/tenants/me/feature-flag-history/`` — returns
        ``TENANT_FEATURE_FLAG_UPDATED`` rows scoped to the calling
        tenant. The SPA renders these as "User X changed flag Y
        from <previous> to <new> at <timestamp>" beneath the flag
        form so the audit history is co-located with the action.

        TENANT_ADMIN-only (250.6.E.2). Cross-tenant rows are excluded
        by the ``tenant=tenant`` filter (existence-leak protection).
        """
        gate = self._enforce_tenant_admin(request)
        if gate is not None:
            return gate

        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant context required", "code": "NO_TENANT"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from hub.apps.audit import event_types as _audit_event_types
        from hub.apps.audit.models import AuditEvent

        events_qs = AuditEvent.objects.filter(
            tenant_id=tenant_id,
            action=_audit_event_types.TENANT_FEATURE_FLAG_UPDATED,
        ).order_by("-timestamp")[:100]
        # Hard-cap at 100 rows so a chatty admin's history doesn't
        # blow the response payload size; the SPA can paginate if
        # the limit is hit (follow-up). 100 covers ~3 months of
        # daily flag flips at expected volumes.

        events = [
            {
                "id": str(ev.id),
                "action": ev.action,
                "actor_user_id": (str(ev.actor_user_id) if ev.actor_user_id else None),
                "result": ev.result,
                "created_at": ev.timestamp.isoformat(),
                "details_json": ev.details_json,
            }
            for ev in events_qs
        ]
        return Response({"events": events}, status=status.HTTP_200_OK)

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
                    # Phase 277.B.106 — dynamic usage key: max_assets → asset_usage
                    usage_key = limit_key.replace("max_", "") + "_usage"
                    current = current_usage.get(usage_key, 0)
                    percentage = (current / max_limit * 100) if max_limit > 0 else 0
                    usage_percentages[limit_key] = round(min(percentage, 100.0), 1)

        # Phase 277.B.106 — quota_warnings for limits at >=80%
        quota_warnings: dict[str, dict[str, Any]] = {}
        for limit_key, pct in usage_percentages.items():
            if pct is not None and pct >= 80.0:
                usage_key = limit_key.replace("max_", "") + "_usage"
                quota_warnings[limit_key] = {
                    "usage": current_usage.get(usage_key, 0),
                    "limit": plan_limits[limit_key],
                    "percentage": pct,
                }

        # Build response
        response_data = {
            **current_usage,
            "plan_limits": plan_limits,
            "usage_percentages": usage_percentages,
            "quota_warnings": quota_warnings,
            "plan_slug": plan.slug if plan else None,
            "plan_tier": plan.tier if plan else None,
        }

        # D232.16 — commercial Compliance Pro packaging on the subscription plan.
        response_data["plan_compliance_pro_pack"] = (
            bool(plan.compliance_pro_pack) if plan else False
        )

        # Phase 285.13.8 — threshold / overall status
        if quota_warnings:
            response_data["threshold_status"] = "warning"
            response_data["overall_status"] = "warning"
        else:
            response_data["threshold_status"] = "ok"
            response_data["overall_status"] = "ok"

        # Phase 285.13.8 — upgrade recommendations
        if plan:
            current_order = getattr(plan, "order", 0) or 0
            current_cat = getattr(plan, "category", "") or ""
            from hub.apps.tenants.models import TenantPlan as _TP

            upgrades = (
                _TP.objects.filter(
                    is_active=True,
                    category=current_cat,
                    order__gt=current_order,
                )
                .order_by("order")
                .values_list("slug", flat=True)
            )
            response_data["upgrade_recommendation"] = list(upgrades)
        else:
            response_data["upgrade_recommendation"] = []

        serializer = TenantUsageSerializer(response_data)
        data = serializer.data

        # Phase 285.13.8 — response-level caching
        from django.core.cache import cache as _dj_cache

        _dj_cache.set(f"tenant_usage_response:{tenant_id}", data, timeout=60)

        return Response(data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # Phase 278.B.2 — Seed sample data for empty-list activation
    # ------------------------------------------------------------------

    @extend_schema(
        operation_id="tenant_seed_sample_data",
        summary="Seed sample data for activation",
        description=(
            "Creates one sample asset, contract, and listing in the "
            "caller's tenant scope. Idempotent: subsequent calls with "
            "the same tenant are no-ops (``get_or_create`` by key). "
            "Emits ``TENANT_SAMPLE_DATA_SEEDED`` audit event."
        ),
        request=None,
        responses={
            201: OpenApiResponse(description="Sample data seeded."),
            200: OpenApiResponse(description="Sample data already exists (idempotent)."),
            401: OpenApiResponse(description="Unauthorized."),
        },
        tags=["Tenants"],
    )
    @action(detail=False, methods=["post"], url_path="me/seed-sample")
    def seed_sample(self, request):
        """Idempotently seed one sample asset, contract, and listing."""
        from hub.apps.assets.models import Asset
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.marketplace.models import Listing, ListingStatus, PricingModel

        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant context required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)

        created_any = False
        asset, asset_created = Asset.objects.get_or_create(
            tenant_id=tenant_id,
            key="sample-customer-db",
            defaults={
                "name": "Sample Customer Database",
                "description": "Auto-generated sample asset to explore the platform.",
                "data_strategy": "METADATA_ONLY",
            },
        )
        created_any = created_any or asset_created

        listing, listing_created = Listing.objects.get_or_create(
            tenant_id=tenant_id,
            asset=asset,
            defaults={
                "pricing_model": PricingModel.FREE,
                "status": ListingStatus.DRAFT,
            },
        )
        created_any = created_any or listing_created

        create_audit_event(
            resource_type="TENANT",
            action="TENANT_SAMPLE_DATA_SEEDED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(tenant.id),
            result="SUCCESS",
            details={
                "asset_created": asset_created,
                "listing_created": listing_created,
                "asset_key": asset.key,
            },
            request=request,
        )

        return Response(
            {
                "message": "Sample data ready — explore your assets!"
                if created_any
                else "Sample data already exists.",
                "asset_id": str(asset.id),
                "asset_key": asset.key,
                "listing_id": str(listing.id),
            },
            status=status.HTTP_201_CREATED if created_any else status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # Phase 285.13.8 — Self-serve plan management endpoints
    # ------------------------------------------------------------------

    def me_plan(self, request):
        """GET /api/v1/tenants/me/plan/ — current plan info."""
        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return Response({"error": "Tenant context required"}, status=400)
        tenant = Tenant.objects.get(id=tenant_id)
        plan = tenant.plan
        if not plan:
            plan = TenantPlan.objects.filter(slug="free", is_active=True).first()
        if not plan:
            return Response({"error": "No plan assigned"}, status=404)
        serializer = TenantPlanAdminSerializer(plan)
        data = serializer.data
        # Attach tier profile if present
        if hasattr(plan, "tier_profile") and plan.tier_profile is not None:
            tp = plan.tier_profile
            data["tier_profile"] = {
                "headline": tp.headline,
                "is_public": tp.is_public,
                "self_serve": tp.self_serve,
                "sort_order": tp.sort_order,
            }
        # Nest under "plan" key per test expectations
        return Response({"plan": data})

    def me_plan_available_upgrades(self, request):
        """GET /api/v1/tenants/me/plan/available-upgrades/ — upgradable plans."""
        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return Response({"error": "Tenant context required"}, status=400)
        tenant = Tenant.objects.get(id=tenant_id)
        current = tenant.plan
        current_order = getattr(current, "order", 0) or 0
        # Respect ?category= query param; default to current plan's category
        requested_cat = request.query_params.get("category", "")
        current_cat = requested_cat or getattr(current, "category", "") or ""

        # Available: active plans in the chosen category with order > current
        candidates = (
            TenantPlan.objects.filter(
                is_active=True,
                category=current_cat,
                order__gt=current_order,
            )
            .select_related("tier_profile")
            .order_by("order")
        )

        def _serialize(p):
            d = TenantPlanAdminSerializer(p).data
            d.pop("flsc_estimate_cents", None)
            d.pop("markup_bps", None)
            d.pop("stripe_product_id", None)
            d.pop("stripe_price_id", None)
            if hasattr(p, "tier_profile") and p.tier_profile is not None:
                d["tier_profile"] = {
                    "headline": p.tier_profile.headline,
                    "is_public": p.tier_profile.is_public,
                    "self_serve": p.tier_profile.self_serve,
                    "sort_order": p.tier_profile.sort_order,
                }
            return d

        return Response([_serialize(p) for p in candidates])

    def me_plan_upgrade(self, request):
        """POST /api/v1/tenants/me/plan/upgrade/ — upgrade to a plan."""
        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return Response({"error": "Tenant context required"}, status=400)
        target_slug = request.data.get("plan_slug", "")
        if not target_slug:
            return Response({"error": "plan_slug required"}, status=400)
        target = TenantPlan.objects.filter(slug=target_slug, is_active=True).first()
        if not target:
            return Response({"error": f"Plan '{target_slug}' not found"}, status=404)

        tenant = Tenant.objects.get(id=tenant_id)
        current = tenant.plan
        if current and getattr(current, "order", 0) >= getattr(target, "order", 0):
            return Response(
                {"error": "Target plan must have higher order than current"},
                status=400,
            )

        tenant.plan = target
        tenant.save(update_fields=["plan"])
        from hub.apps.audit.event_types import TENANT_PLAN_UPGRADED
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="TENANT",
            action=TENANT_PLAN_UPGRADED,
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(tenant.id),
            details={"from_slug": getattr(current, "slug", None), "to_slug": target.slug},
            request=request,
        )
        return Response({"plan_slug": target.slug, "message": "Plan upgraded"})

    def me_plan_downgrade(self, request):
        """POST /api/v1/tenants/me/plan/downgrade/ — downgrade with validation."""
        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return Response({"error": "Tenant context required"}, status=400)
        target_slug = request.data.get("plan_slug", "")
        if not target_slug:
            return Response({"error": "plan_slug required"}, status=400)
        target = TenantPlan.objects.filter(slug=target_slug, is_active=True).first()
        if not target:
            return Response({"error": f"Plan '{target_slug}' not found"}, status=404)

        tenant = Tenant.objects.get(id=tenant_id)
        # Validate downgrade
        from hub.apps.billing.services import PlanLimitService as BillingPlanLimitService

        result = BillingPlanLimitService.validate_downgrade(str(tenant.id), target)
        if not result.is_valid:
            return Response(
                {"error": "Downgrade validation failed", "details": result.errors},
                status=400,
            )
        if result.details:
            # Include warnings in response
            pass  # warnings are advisory

        old_slug = getattr(tenant.plan, "slug", None)
        tenant.plan = target
        tenant.save(update_fields=["plan"])
        from hub.apps.audit.event_types import TENANT_PLAN_DOWNGRADED
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="TENANT",
            action=TENANT_PLAN_DOWNGRADED,
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(tenant.id),
            details={"from_slug": old_slug, "to_slug": target.slug},
            request=request,
        )
        return Response(
            {
                "plan_slug": target.slug,
                "message": "Plan downgraded",
                "warnings": list(result.details.keys()) if result.details else [],
            }
        )

    def me_plan_available_ml_addons(self, request):
        """GET /api/v1/tenants/me/plan/available-ml-addons/ — ML add-on plans."""
        from hub.apps.billing.models import Subscription, SubscriptionStatus

        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return Response({"error": "Tenant context required"}, status=400)
        tenant = Tenant.objects.get(id=tenant_id)

        # Check for existing ML subscription — return 409 Conflict
        has_ml = Subscription.objects.filter(
            tenant=tenant,
            plan__category=PlanCategory.ML_AI,
            status__in=[
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIAL,
                SubscriptionStatus.PAST_DUE,
            ],
        ).exists()
        if has_ml:
            return Response(
                {"error": "Tenant already has an active ML add-on plan."},
                status=409,
            )

        # Check if tenant has a qualifying base plan via subscription
        base_sub = (
            Subscription.objects.filter(
                tenant=tenant,
                plan__category=PlanCategory.BASE,
                status__in=[
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIAL,
                    SubscriptionStatus.PAST_DUE,
                ],
            )
            .select_related("plan")
            .first()
        )
        base_order = getattr(base_sub.plan if base_sub else None, "order", 0) or 0
        if base_order < 1:
            return Response(
                {"error": "ML/AI plans require at least a Starter plan."},
                status=400,
            )

        ml_plans = (
            TenantPlan.objects.filter(
                is_active=True,
                category=PlanCategory.ML_AI,
            )
            .select_related("tier_profile")
            .order_by("order")
        )

        def _serialize(p):
            d = TenantPlanAdminSerializer(p).data
            d.pop("flsc_estimate_cents", None)
            d.pop("markup_bps", None)
            d.pop("stripe_product_id", None)
            d.pop("stripe_price_id", None)
            if hasattr(p, "tier_profile") and p.tier_profile is not None:
                d["tier_profile"] = {
                    "headline": p.tier_profile.headline,
                    "is_public": p.tier_profile.is_public,
                    "self_serve": p.tier_profile.self_serve,
                    "sort_order": p.tier_profile.sort_order,
                }
            return d

        return Response([_serialize(p) for p in ml_plans])

    # ------------------------------------------------------------------
    # Phase 270.D.3 — Tax & Billing Identity surface
    # ------------------------------------------------------------------

    @action(detail=False, methods=["get", "post"], url_path="me/tax-id")
    def me_tax_id(self, request):
        """Phase 270.D.3 — tenant tax-identity submission.

        ``GET  /api/v1/tenants/me/tax-id/`` returns the current
        ``{tax_id, tax_id_type, tax_id_verified, tax_address}``
        (tax_address is decrypted). ``POST`` submits a new
        registration: validates input, calls
        ``stripe.Customer.create_tax_id`` to register the value
        Stripe-side, persists the four fields locally (tax_id
        flips back to unverified pending the verified webhook).

        Audit: emits ``TENANT_TAX_ID_SUBMITTED`` with the
        masked tax_id + country so the audit log carries the
        submission record without leaking the plaintext ID.
        """
        from hub.apps.audit import event_types as _ev
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.tax_id_service import (
            TaxIdSubmissionError,
            submit_tax_id_to_stripe,
        )

        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return Response(
                {"error": "Tenant context required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant = self.get_tenant(tenant_id)

        if request.method == "GET":
            return Response(
                {
                    "tax_id": tenant.tax_id or "",
                    "tax_id_type": tenant.tax_id_type or "",
                    "tax_id_verified": bool(tenant.tax_id_verified),
                    "tax_address": tenant.get_tax_address(),
                },
                status=status.HTTP_200_OK,
            )

        # POST — submit + persist.
        tax_id_value = (request.data.get("tax_id") or "").strip()
        tax_id_type = (request.data.get("tax_id_type") or "").strip()
        tax_address = request.data.get("tax_address") or None

        if not tax_id_value or not tax_id_type:
            return Response(
                {
                    "error": "tax_id and tax_id_type are required",
                    "code": "TAX_ID_INPUT_INVALID",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if tax_address is not None and not isinstance(tax_address, dict):
            return Response(
                {
                    "error": "tax_address must be a JSON object",
                    "code": "TAX_ID_INPUT_INVALID",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Submit to Stripe + persist locally. The service-layer
        # call is the boundary that talks to Stripe; the view is
        # a thin wrapper that wires HTTP semantics.
        try:
            result = submit_tax_id_to_stripe(
                tenant=tenant,
                tax_id_value=tax_id_value,
                tax_id_type=tax_id_type,
                tax_address=tax_address,
            )
        except TaxIdSubmissionError as exc:
            return Response(
                {"error": str(exc), "code": "TAX_ID_SUBMISSION_FAILED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Audit row carries the MASKED tax_id only — the
        # encrypted Tenant.tax_id column is the system-of-record
        # for the unmasked value.
        from hub.apps.billing.views import _mask_tax_id  # local import

        create_audit_event(
            resource_type="TENANT",
            action=_ev.TENANT_TAX_ID_SUBMITTED,
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(tenant.id),
            details={
                "tax_id_type": tax_id_type,
                "tax_id_masked": _mask_tax_id(tax_id_value),
                "country": (tax_address or {}).get("country") if tax_address else "",
                "stripe_tax_id_id": result.get("stripe_tax_id_id"),
            },
            request=request,
        )

        return Response(
            {
                "tax_id": tenant.tax_id,
                "tax_id_type": tenant.tax_id_type,
                "tax_id_verified": bool(tenant.tax_id_verified),
                "tax_address": tenant.get_tax_address(),
                "stripe_tax_id_id": result.get("stripe_tax_id_id"),
            },
            status=status.HTTP_200_OK,
        )


# ── Phase 277.B.070 — Per-Tenant Rate Limit Admin ────────────────


class RateLimitConfigView(viewsets.ViewSet):
    """
    Platform-admin endpoint for viewing and updating per-tenant rate limits.

    GET  /api/v1/admin/tenants/{id}/rate-limits/
    PATCH /api/v1/admin/tenants/{id}/rate-limits/

    Validates overrides against PLATFORM_MAXIMUM_LIMITS so a tenant
    can never exceed the global ceiling.  Emits ``TENANT_RATE_LIMITS_UPDATED``
    audit event on every mutation.
    """

    def get_permissions(self):
        from hub.apps.tenants.permissions import IsPlatformAdmin

        return [IsPlatformAdmin()]

    # Phase 277.B.092 — ABAC enforcement before admin mutations
    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            from hub.apps.governance.admin_abac import _evaluate_admin_action

            _evaluate_admin_action(request, "TENANT_CONFIG", "ADMIN_WRITE")

    def _get_tenant_or_404(self, tenant_id: str) -> Tenant:
        try:
            return Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            from rest_framework.exceptions import NotFound

            raise NotFound("Tenant not found")

    def _get_config_or_create(self, tenant: Tenant) -> TenantConfig:
        config, _created = TenantConfig.objects.get_or_create(
            tenant=tenant,
            defaults={"rate_limits": {}},
        )
        return config

    @extend_schema(
        operation_id="get_tenant_rate_limits",
        summary="Get tenant rate limits",
        description=(
            "Returns the current per-tenant rate limit overrides for the "
            "specified tenant.  Categories not overridden fall back to "
            "platform defaults at enforcement time."
        ),
        responses={
            200: OpenApiResponse(description="Rate limits for the tenant."),
            401: OpenApiResponse(description="Unauthorized."),
            403: OpenApiResponse(description="Forbidden — PLATFORM_ADMIN required."),
            404: OpenApiResponse(description="Tenant not found."),
        },
        tags=["Tenants"],
    )
    def retrieve(self, request, tenant_id=None):
        tenant = self._get_tenant_or_404(tenant_id)
        config = self._get_config_or_create(tenant)

        effective_limits = {}
        for category in [
            "auth",
            "asset",
            "contract",
            "search",
            "file_upload",
            "dq_runs",
            "compliance_runs",
            "file_download",
            "contract_validation",
            "catalog_reads",
            "sparql_queries",
            "general",
        ]:
            from hub.apps.rate_limiting.config import (
                get_tenant_rate_limit,
            )
            from hub.apps.rate_limiting.utils import TimeWindow

            effective_limits[category] = {
                "burst_per_10s": get_tenant_rate_limit(tenant_id, category, TimeWindow.BURST),
                "sustained_per_min": get_tenant_rate_limit(
                    tenant_id, category, TimeWindow.SUSTAINED
                ),
                "daily_cap": get_tenant_rate_limit(tenant_id, category, TimeWindow.DAILY),
            }

        return Response(
            {
                "tenant_id": str(tenant.id),
                "overrides": config.rate_limits or {},
                "effective": effective_limits,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        operation_id="update_tenant_rate_limits",
        summary="Update tenant rate limits",
        description=(
            "Update per-tenant rate limit overrides.  Only the categories "
            "present in the request body are modified; other overrides are "
            "left unchanged.  Values are validated against platform maximums."
        ),
        request=TenantConfigSerializer,
        responses={
            200: OpenApiResponse(description="Rate limits updated."),
            400: OpenApiResponse(description="Validation error."),
            401: OpenApiResponse(description="Unauthorized."),
            403: OpenApiResponse(description="Forbidden — PLATFORM_ADMIN required."),
            404: OpenApiResponse(description="Tenant not found."),
        },
        tags=["Tenants"],
    )
    def partial_update(self, request, tenant_id=None):
        from hub.apps.tenants.validators import validate_rate_limits

        tenant = self._get_tenant_or_404(tenant_id)
        config = self._get_config_or_create(tenant)

        rate_limits_payload = request.data.get("rate_limits")
        if rate_limits_payload is None:
            return Response(
                {"error": "rate_limits field is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validate_rate_limits(rate_limits_payload)

        # Merge with existing overrides
        current = config.rate_limits or {}
        current.update(rate_limits_payload)
        config.rate_limits = current
        config.save(update_fields=["rate_limits", "updated_at"])

        create_audit_event(
            resource_type="TENANT_CONFIG",
            action="TENANT_RATE_LIMITS_UPDATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(tenant.id),
            result="SUCCESS",
            details={
                "updated_categories": list(rate_limits_payload.keys()),
                "rate_limits": rate_limits_payload,
            },
            request=request,
        )

        return Response(
            {
                "tenant_id": str(tenant.id),
                "rate_limits": config.rate_limits,
                "message": "Rate limits updated successfully",
            },
            status=status.HTTP_200_OK,
        )
