"""
User Views

REST API views for user management.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import uuid

from .models import User, Role, UserRole, UserStatus
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    UserInviteSerializer,
    UserRoleAssignmentSerializer,
    RoleSerializer
)
from hub.apps.tenants.models import Tenant
from hub.apps.audit.utils import log_user_operation


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user management.
    
    Tenant-scoped: users can only see/manage users in their tenant.
    Platform admins can see all users.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return UserCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return UserUpdateSerializer
        return UserSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user
        
        # Platform admins can see all users
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = User.objects.all()
        # Regular users can only see users in their tenant
        elif hasattr(user, "tenant") and user.tenant:
            queryset = User.objects.filter(tenant=user.tenant)
        else:
            return User.objects.none()
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new user.
        
        Creates user with optional role assignment and invitation.
        """
        # Set tenant from request user if not provided
        data = request.data.copy()
        if 'tenant' not in data and hasattr(request.user, 'tenant') and request.user.tenant:
            data['tenant'] = str(request.user.tenant.id)
        
        serializer = UserCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Send invitation email if requested
        if serializer.validated_data.get("send_invitation", True):
            self._send_invitation_email(user)
        
        # Log audit event
        log_user_operation(
            action="USER_CREATED",
            user=user,
            actor_user=request.user,
            details={"email": user.email, "status": user.status},
            request=request
        )
        
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED
        )
    
    def list(self, request, *args, **kwargs):
        """List users (tenant-scoped)"""
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve user by ID"""
        return super().retrieve(request, *args, **kwargs)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update user (full update)"""
        user = self.get_object()
        serializer = UserUpdateSerializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Log audit event
        log_user_operation(
            action="USER_UPDATED",
            user=user,
            actor_user=request.user,
            details=serializer.validated_data,
            request=request
        )
        
        return Response(UserSerializer(user).data)
    
    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Update user (partial update)"""
        user = self.get_object()
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Log audit event
        log_user_operation(
            action="USER_UPDATED",
            user=user,
            actor_user=request.user,
            details=serializer.validated_data,
            request=request
        )
        
        return Response(UserSerializer(user).data)
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a user.
        
        Performs soft delete if user has resources, hard delete otherwise.
        Prevents self-deletion.
        """
        user = self.get_object()
        
        # Prevent self-deletion
        if user.id == request.user.id:
            return Response(
                {"error": "Users cannot delete themselves"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has resources
        has_resources = self._user_has_resources(user)
        
        if has_resources:
            # Soft delete: set status to DISABLED
            user.status = UserStatus.DISABLED
            user.save(update_fields=["status", "updated_at"])
            
            # Log audit event
            log_user_operation(
                action="USER_DISABLED",
                user=user,
                actor_user=request.user,
                details={"reason": "User has resources"},
                request=request
            )
            
            return Response(
                {"message": "User disabled (has resources)"},
                status=status.HTTP_200_OK
            )
        else:
            # Hard delete: remove user completely
            user_id = user.id
            tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
            
            # Log audit event BEFORE deleting user (to avoid FK constraint violation)
            from hub.apps.audit.utils import create_audit_event
            create_audit_event(
                resource_type="USER",
                action="USER_DELETED",
                actor_user=request.user,
                tenant=tenant,
                resource_id=str(user_id),
                details={"user_id": str(user_id)},
                request=request
            )
            
            # Now delete the user
            user.delete()
            
            return Response(status=status.HTTP_204_NO_CONTENT)
    
    @transaction.atomic
    @action(detail=False, methods=["post"], url_path="invite")
    def invite(self, request):
        """
        Invite a user to join the tenant.
        
        Creates user with INVITED status and sends invitation email.
        """
        serializer = UserInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get tenant from request user
        tenant = request.user.tenant if hasattr(request.user, "tenant") else None
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to invite others"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user already exists
        email = serializer.validated_data["email"]
        existing_user = User.objects.filter(email=email, tenant=tenant).first()
        if existing_user:
            return Response(
                {"error": "User with this email already exists in tenant"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create invited user
        user = User.objects.create_user(
            email=email,
            tenant=tenant,
            display_name=serializer.validated_data.get("display_name"),
            status=UserStatus.INVITED
        )
        
        # Generate invitation token
        user.invitation_token = uuid.uuid4()
        user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        user.save(update_fields=["invitation_token", "invitation_token_expires_at"])
        
        # Assign roles if provided
        role_ids = serializer.validated_data.get("role_ids", [])
        if role_ids:
            roles = Role.objects.filter(id__in=role_ids, tenant=tenant)
            for role in roles:
                UserRole.objects.get_or_create(user=user, role=role)
        
        # Send invitation email
        self._send_invitation_email(user)
        
        # Log audit event
        log_user_operation(
            action="USER_INVITED",
            user=user,
            actor_user=request.user,
            details={"email": email},
            request=request
        )
        
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED
        )
    
    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="roles")
    def manage_roles(self, request, id=None):
        """
        Assign or remove a role from a user.
        
        Increments token_version to invalidate existing sessions.
        """
        user = self.get_object()
        serializer = UserRoleAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        role_id = serializer.validated_data["role_id"]
        action_type = serializer.validated_data["action"]
        
        try:
            role = Role.objects.get(id=role_id, tenant=user.tenant)
        except Role.DoesNotExist:
            return Response(
                {"error": "Role not found or not in same tenant"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if action_type == "assign":
            UserRole.objects.get_or_create(user=user, role=role)
        elif action_type == "remove":
            UserRole.objects.filter(user=user, role=role).delete()
        
        # Increment token version to invalidate sessions
        user.increment_token_version()
        
        # Log audit event
        log_user_operation(
            action="USER_ROLE_CHANGED",
            user=user,
            actor_user=request.user,
            details={"role_id": str(role_id), "action": action_type},
            request=request
        )
        
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_200_OK
        )
    
    def _user_has_resources(self, user) -> bool:
        """
        Check if user has associated resources (assets, datasets, etc.).
        
        Returns True if user has any resources that prevent hard deletion.
        """
        # Check for assets created by this user
        from hub.apps.assets.models import Asset
        if Asset.objects.filter(created_by=user).exists():
            return True
        
        # Check for datasets created by this user
        from hub.apps.datasets.models import Dataset
        if Dataset.objects.filter(created_by=user).exists():
            return True
        
        # Check for contracts created by this user
        from hub.apps.contracts.models import Contract
        if Contract.objects.filter(created_by=user).exists():
            return True
        
        # Check for files created by this user
        from hub.apps.files.models import File
        if File.objects.filter(created_by=user).exists():
            return True
        
        return False
    
    def _send_invitation_email(self, user):
        """Send invitation email to user"""
        from hub.apps.notifications.tasks import send_invitation_email
        send_invitation_email.delay(str(user.id))
        pass
    


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for role management (read-only for MVP).
    
    Roles are created automatically when tenants are created.
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user
        
        # Platform admins can see all roles
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return Role.objects.all()
        
        # Regular users can only see roles in their tenant
        if hasattr(user, "tenant") and user.tenant:
            return Role.objects.filter(tenant=user.tenant)
        
        return Role.objects.none()

