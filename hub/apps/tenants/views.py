"""
Tenant Views

REST API views for tenant management.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer
from rest_framework import serializers

from .models import Tenant, TenantStatus, TenantConfig
from .permissions import IsPlatformAdmin
from .serializers import (
    TenantSerializer,
    TenantCreateSerializer,
    TenantUpdateSerializer,
    TenantSuspendSerializer,
    TenantReactivateSerializer,
    TenantConfigSerializer,
    TenantConfigUpdateSerializer,
)
from .services import get_tenant_config
from hub.apps.audit.utils import log_tenant_operation
from hub.apps.auth.permissions import HasRole


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
        """
        serializer = TenantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        
        # Log audit event
        log_tenant_operation(
            action="TENANT_CREATED",
            tenant=tenant,
            actor_user=request.user,
            details={"name": tenant.name, "slug": tenant.slug},
            request=request
        )
        
        return Response(
            TenantSerializer(tenant).data,
            status=status.HTTP_201_CREATED
        )
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve tenant by ID"""
        tenant = self.get_object()
        return Response(TenantSerializer(tenant).data)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update tenant (full update)"""
        tenant = self.get_object()
        serializer = TenantUpdateSerializer(tenant, data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        
        # Log audit event
        log_tenant_operation(
            action="TENANT_UPDATED",
            tenant=tenant,
            actor_user=request.user,
            details=serializer.validated_data,
            request=request
        )
        
        return Response(TenantSerializer(tenant).data)
    
    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Update tenant (partial update)"""
        tenant = self.get_object()
        serializer = TenantUpdateSerializer(tenant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        
        # Log audit event
        log_tenant_operation(
            action="TENANT_UPDATED",
            tenant=tenant,
            actor_user=request.user,
            details=serializer.validated_data,
            request=request
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
                {"error": "Cannot suspend a deleted tenant"},
                status=status.HTTP_400_BAD_REQUEST
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
            request=request
        )
        
        return Response(
            TenantSerializer(tenant).data,
            status=status.HTTP_200_OK
        )
    
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
                status=status.HTTP_400_BAD_REQUEST
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
            request=request
        )
        
        return Response(
            TenantSerializer(tenant).data,
            status=status.HTTP_200_OK
        )
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a tenant (soft delete).
        
        Sets status to DELETED and blocks all access.
        Data retention period begins (default: 30 days).
        """
        tenant = self.get_object()
        
        if tenant.status == TenantStatus.DELETED:
            return Response(
                {"error": "Tenant is already deleted"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Soft delete tenant
        tenant.soft_delete()
        
        # Log audit event
        log_tenant_operation(
            action="TENANT_DELETED",
            tenant=tenant,
            actor_user=request.user,
            details={},
            request=request
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
            403: OpenApiResponse(description="Forbidden - user lacks TENANT_ADMIN role or Platform Admin privileges"),
            404: OpenApiResponse(description="Tenant not found"),
        },
        tags=["Tenants"]
    )
    def retrieve(self, request, tenant_id=None, **kwargs):
        """
        Get tenant configuration.
        
        Returns tenant configuration with platform defaults for any unset values.
        """
        # Extract tenant_id from kwargs if not provided directly
        if tenant_id is None:
            tenant_id = kwargs.get('tenant_id')
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
            403: OpenApiResponse(description="Forbidden - user lacks TENANT_ADMIN role or Platform Admin privileges"),
            404: OpenApiResponse(description="Tenant not found"),
        },
        tags=["Tenants"]
    )
    @transaction.atomic
    def partial_update(self, request, tenant_id=None, **kwargs):
        """
        Update tenant configuration (partial update).
        
        Updates only the provided fields, leaving others unchanged.
        """
        # Extract tenant_id from kwargs if not provided directly
        if tenant_id is None:
            tenant_id = kwargs.get('tenant_id')
        tenant = self.get_tenant(tenant_id)
        
        # Get or create tenant config
        config, created = TenantConfig.objects.get_or_create(tenant=tenant)
        
        serializer = TenantConfigUpdateSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        
        # Log audit event
        log_tenant_operation(
            action="TENANT_CONFIG_UPDATED",
            tenant=tenant,
            actor_user=request.user,
            details=serializer.validated_data,
            request=request
        )
        
        # Return complete config with defaults
        config_dict = get_tenant_config(tenant)
        return Response(config_dict, status=status.HTTP_200_OK)

