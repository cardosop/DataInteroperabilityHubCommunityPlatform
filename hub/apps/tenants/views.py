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

from .models import Tenant, TenantStatus
from .permissions import IsPlatformAdmin
from .serializers import (
    TenantSerializer,
    TenantCreateSerializer,
    TenantUpdateSerializer,
    TenantSuspendSerializer,
    TenantReactivateSerializer
)
from hub.apps.audit.utils import log_tenant_operation


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

