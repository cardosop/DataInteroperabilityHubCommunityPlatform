"""
User Views

REST API views for user management.
"""

import uuid
from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.audit.utils import log_user_operation
from hub.apps.auth.utils import sha256_hex
from hub.apps.tenants.models import Tenant

from .models import Role, User, UserRole, UserStatus
from .serializers import (
    RoleSerializer,
    UserCreateSerializer,
    UserInviteSerializer,
    UserRoleAssignmentSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user management.

    Tenant-scoped: users can only see/manage users in their tenant.
    Platform admins can see all users.
    """

    queryset = User.objects.prefetch_related("user_roles__role").order_by("created_at")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    pagination_class = StandardPageNumberPagination

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
            queryset = User.objects.prefetch_related("user_roles__role").all()
        # Regular users can only see users in their tenant
        elif hasattr(user, "tenant") and user.tenant:
            queryset = User.objects.prefetch_related("user_roles__role").filter(tenant=user.tenant)
        else:
            return User.objects.none()

        # Filter by status if provided
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new user via service layer.

        Creates user with optional role assignment and invitation.
        """
        # Set tenant from request user if not provided
        data = request.data.copy()
        tenant_id = None
        if "tenant" not in data and hasattr(request.user, "tenant") and request.user.tenant:
            tenant_id = str(request.user.tenant.id)
            data["tenant"] = tenant_id
        elif "tenant" in data:
            tenant_id = str(data["tenant"])

        serializer = UserCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        # Use service layer for creation (Phase 24.7.2)
        from hub.apps.users.services import UserService

        if not tenant_id:
            return Response(
                {"error": "Tenant is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = UserService(tenant_id=tenant_id, user_id=str(request.user.id))
        try:
            user = service.create_user(
                tenant_id=tenant_id,
                actor_user_id=str(request.user.id),
                email=serializer.validated_data["email"],
                password=serializer.validated_data.get("password"),
                display_name=serializer.validated_data.get("display_name"),
                status=serializer.validated_data.get("status"),
                role_ids=serializer.validated_data.get("role_ids"),
                send_invitation=serializer.validated_data.get("send_invitation", True),
            )
        except Exception as e:
            from hub.apps.core.responses import handle_service_exception
            from hub.apps.core.services.base import NotFoundError
            from hub.apps.core.services.base import ValidationError as ServiceValidationError

            if isinstance(e, (ServiceValidationError, NotFoundError)):
                return handle_service_exception(e)
            raise

        # Set invitation token and send email if requested (11.3: store hash)
        if serializer.validated_data.get("send_invitation", True):
            _plaintext = str(uuid.uuid4())
            user.invitation_token = sha256_hex(_plaintext)
            user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
            user.save(update_fields=["invitation_token", "invitation_token_expires_at"])
            self._send_invitation_email(user, plaintext_token=_plaintext)

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        """List users (tenant-scoped)"""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve user by ID"""
        return super().retrieve(request, *args, **kwargs)

    def _check_admin_update_permission(self, request):
        """Require TENANT_ADMIN or PLATFORM_ADMIN for user update."""
        actor = request.user
        if not (
            (hasattr(actor, "is_platform_admin") and actor.is_platform_admin)
            or (hasattr(actor, "has_role") and actor.has_role("TENANT_ADMIN"))
        ):
            return Response(
                {"error": "Permission denied: TENANT_ADMIN or PLATFORM_ADMIN role required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update user via service layer (full update). Requires TENANT_ADMIN or PLATFORM_ADMIN."""
        perm = self._check_admin_update_permission(request)
        if perm is not None:
            return perm
        user = self.get_object()
        serializer = UserUpdateSerializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)

        # Use service layer for update (Phase 24.7.2)
        from hub.apps.core.responses import handle_service_exception
        from hub.apps.core.services.base import NotFoundError
        from hub.apps.core.services.base import ValidationError as ServiceValidationError
        from hub.apps.users.services import UserService

        tenant_id = str(user.tenant.id) if user.tenant else None
        if not tenant_id:
            return Response(
                {"error": "User must belong to a tenant"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = UserService(tenant_id=tenant_id, user_id=str(request.user.id))
        try:
            # Extract update data (exclude read-only fields)
            update_data = {
                k: v
                for k, v in serializer.validated_data.items()
                if k not in getattr(serializer.Meta, "read_only_fields", [])
            }
            user = service.update_user(
                user_id=str(user.id),
                tenant_id=tenant_id,
                actor_user_id=str(request.user.id),
                **update_data,
            )
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)

        return Response(UserSerializer(user).data)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Update user via service layer (partial update). Requires TENANT_ADMIN or PLATFORM_ADMIN."""
        perm = self._check_admin_update_permission(request)
        if perm is not None:
            return perm
        user = self.get_object()
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Use service layer for update (Phase 24.7.2)
        from hub.apps.core.responses import handle_service_exception
        from hub.apps.core.services.base import NotFoundError
        from hub.apps.core.services.base import ValidationError as ServiceValidationError
        from hub.apps.users.services import UserService

        tenant_id = str(user.tenant.id) if user.tenant else None
        if not tenant_id:
            return Response(
                {"error": "User must belong to a tenant"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = UserService(tenant_id=tenant_id, user_id=str(request.user.id))
        try:
            # Extract update data (exclude read-only fields)
            update_data = {
                k: v
                for k, v in serializer.validated_data.items()
                if k not in getattr(serializer.Meta, "read_only_fields", [])
            }
            user = service.update_user(
                user_id=str(user.id),
                tenant_id=tenant_id,
                actor_user_id=str(request.user.id),
                **update_data,
            )
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)

        return Response(UserSerializer(user).data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """Delete user via service layer. Requires TENANT_ADMIN or PLATFORM_ADMIN."""
        # Authorization: only admins can delete users
        perm = self._check_admin_update_permission(request)
        if perm is not None:
            return perm

        user = self.get_object()

        # Prevent self-deletion
        if user.id == request.user.id:
            return Response(
                {"error": "Users cannot delete themselves"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer for deletion (Phase 24.7.2)
        from hub.apps.core.responses import handle_service_exception
        from hub.apps.core.services.base import NotFoundError
        from hub.apps.users.services import UserService

        tenant_id = str(user.tenant.id) if user.tenant else None
        if not tenant_id:
            return Response(
                {"error": "User must belong to a tenant"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = UserService(tenant_id=tenant_id, user_id=str(request.user.id))
        try:
            soft_deleted = service.delete_user(
                user_id=str(user.id),
                tenant_id=tenant_id,
                actor_user_id=str(request.user.id),
            )
        except NotFoundError as e:
            return handle_service_exception(e)

        if soft_deleted:
            return Response(
                {"message": "User disabled (has resources)"},
                status=status.HTTP_200_OK,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @transaction.atomic
    def destroy_old(self, request, *args, **kwargs):
        """
        Delete a user.

        Performs soft delete if user has resources, hard delete otherwise.
        Prevents self-deletion.
        """
        user = self.get_object()

        # Prevent self-deletion
        if user.id == request.user.id:
            return Response(
                {"error": "Users cannot delete themselves"}, status=status.HTTP_400_BAD_REQUEST
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
                request=request,
            )

            return Response({"message": "User disabled (has resources)"}, status=status.HTTP_200_OK)
        else:
            # Hard delete: remove user completely
            user_id = user.id
            tenant = request.user.tenant if hasattr(request.user, "tenant") else None

            # Log audit event BEFORE deleting user (to avoid FK constraint violation)
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="USER",
                action="USER_DELETED",
                actor_user=request.user,
                tenant=tenant,
                resource_id=str(user_id),
                details={"user_id": str(user_id)},
                request=request,
            )

            # Now delete the user
            user.delete()

            return Response(status=status.HTTP_204_NO_CONTENT)

    @transaction.atomic
    @action(detail=False, methods=["post"], url_path="invite")
    def invite(self, request):
        """
        Invite a user to join the tenant via service layer.

        Creates user with INVITED status and sends invitation email.

        Requires TENANT_ADMIN or PLATFORM_ADMIN role (consistent with
        other mutation endpoints on this viewset: update, destroy, manage_roles).
        """
        perm = self._check_admin_update_permission(request)
        if perm is not None:
            return perm

        serializer = UserInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant from request (Phase 16 contract: get_request_tenant)
        from hub.apps.tenants.request_tenant import get_request_tenant

        tenant_id, tenant = get_request_tenant(request)
        if not tenant_id or not tenant:
            return Response(
                {"error": "User must belong to a tenant to invite others"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer for invitation (Phase 24.7.2, 29.65.4)
        from hub.apps.core.responses import handle_service_exception
        from hub.apps.core.services.base import NotFoundError
        from hub.apps.core.services.base import ValidationError as ServiceValidationError
        from hub.apps.users.services import UserService

        service = UserService(tenant_id=tenant_id, user_id=str(request.user.id))
        try:
            user, created_new = service.invite_user_to_tenant(
                tenant_id=tenant_id,
                actor_user_id=str(request.user.id),
                email=serializer.validated_data["email"],
                display_name=serializer.validated_data.get("display_name"),
                role_ids=serializer.validated_data.get("role_ids", []),
                send_invitation=True,
            )
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)

        if created_new:
            # Generate invitation token and send email only for new users (11.3: store hash)
            _plaintext = str(uuid.uuid4())
            user.invitation_token = sha256_hex(_plaintext)
            user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
            user.save(update_fields=["invitation_token", "invitation_token_expires_at"])
            self._send_invitation_email(user, plaintext_token=_plaintext)

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="roles")
    def manage_roles(self, request, id=None):
        """
        Assign or remove a role from a user.

        Requires TENANT_ADMIN or platform admin. Increments token_version to
        invalidate existing sessions.
        """
        user = self.get_object()
        actor = request.user
        if not (
            (hasattr(actor, "is_platform_admin") and actor.is_platform_admin)
            or (hasattr(actor, "has_role") and actor.has_role("TENANT_ADMIN"))
        ):
            return Response(
                {"error": "Permission denied: TENANT_ADMIN role required to manage roles"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = UserRoleAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role_id = serializer.validated_data["role_id"]
        action_type = serializer.validated_data["action"]

        try:
            role = Role.objects.get(id=role_id, tenant=user.tenant)
        except Role.DoesNotExist:
            return Response(
                {"error": "Role not found or not in same tenant"}, status=status.HTTP_404_NOT_FOUND
            )

        if action_type == "assign":
            UserRole.objects.get_or_create(user=user, tenant=role.tenant, role=role)
        elif action_type == "remove":
            UserRole.objects.filter(user=user, role=role).delete()

        # Increment token version to invalidate JWT sessions
        user.increment_token_version()

        # Invalidate the /auth/me response cache so the new role is visible
        # immediately. Without this, the cached response (TTL 300s) returns
        # stale roles for up to 5 minutes, causing spurious 403s on role-gated
        # routes like /audit after an AUDITOR role is assigned.
        from django.core.cache import cache
        cache.delete(f"user:me:{user.id}")

        # Log audit event
        log_user_operation(
            action="USER_ROLE_CHANGED",
            user=user,
            actor_user=request.user,
            details={"role_id": str(role_id), "action": action_type},
            request=request,
        )

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

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

    def _send_invitation_email(self, user, plaintext_token: str = None):
        """Send invitation email to user (11.3: plaintext_token for URL building).

        Deferred via transaction.on_commit so the task is only enqueued
        after the enclosing @transaction.atomic block commits — preventing
        orphaned emails on rollback.
        """
        import structlog

        from hub.apps.notifications.tasks import send_invitation_email

        logger = structlog.get_logger(__name__)

        _uid = str(user.id)
        _token = plaintext_token

        def _enqueue():
            try:
                send_invitation_email.delay(_uid, plaintext_token=_token)
            except Exception as e:
                # Handle Redis connection failures gracefully
                logger.warning(
                    "Failed to enqueue invitation email"
                    " (Redis may be unavailable)."
                    " User created but email not queued.",
                    user_id=_uid,
                    error=str(e),
                )

        transaction.on_commit(_enqueue)


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
