"""
User Service

Service layer for user operations.
All create/update/delete paths apply validation and audit.
"""

from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.db import transaction

from hub.apps.audit.utils import log_user_operation
from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError

User = get_user_model()


class UserService(BaseService):
    """
    Service for user operations.

    Provides business logic for:
    - User creation with validation
    - User update with validation
    - User deletion
    """

    service_name = "user_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.user_id = user_id

    @transaction.atomic
    def create_user(
        self,
        tenant_id: str,
        actor_user_id: str,
        email: str,
        password: Optional[str] = None,
        display_name: Optional[str] = None,
        status: Optional[str] = None,
        role_ids: Optional[list] = None,
        send_invitation: bool = True,
        **kwargs,
    ) -> User:
        """
        Create a user with validation and audit.

        Args:
            tenant_id: Tenant ID
            actor_user_id: User ID performing the creation
            email: User email
            password: Optional password
            display_name: Optional display name
            status: Optional user status
            role_ids: Optional list of role IDs to assign
            send_invitation: Whether to send invitation email
            **kwargs: Additional user fields

        Returns:
            Created User instance

        Raises:
            ValidationError: If validation fails
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import Role, UserRole, UserStatus

        # Get tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(f"Tenant {tenant_id} not found")

        # Get actor user
        try:
            actor_user = User.objects.get(id=actor_user_id)
        except User.DoesNotExist:
            raise NotFoundError(f"Actor user {actor_user_id} not found")

        # Validate email uniqueness
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email address is already registered", code="EMAIL_EXISTS")

        # Set status based on invitation, but respect explicit status if provided
        if status is None:
            if send_invitation:
                status = UserStatus.INVITED
            else:
                status = UserStatus.ACTIVE

        # Create user
        user = User.objects.create_user(
            email=email,
            password=password,
            tenant=tenant,
            display_name=display_name,
            status=status,
            **kwargs,
        )

        # Assign roles if provided
        if role_ids:
            roles = Role.objects.filter(id__in=role_ids, tenant=tenant)
            for role in roles:
                UserRole.objects.get_or_create(user=user, role=role)

        # Create audit event (USER_INVITED when inviting, USER_CREATED otherwise)
        audit_action = "USER_INVITED" if status == UserStatus.INVITED else "USER_CREATED"
        log_user_operation(
            action=audit_action,
            user=user,
            actor_user=actor_user,
            details={"email": email, "status": status, "role_ids": role_ids},
        )

        return user

    @transaction.atomic
    def update_user(
        self,
        user_id: str,
        tenant_id: str,
        actor_user_id: str,
        **update_data,
    ) -> User:
        """
        Update a user with validation and audit.

        Args:
            user_id: User ID to update
            tenant_id: Tenant ID
            actor_user_id: User ID performing the update
            **update_data: Fields to update

        Returns:
            Updated User instance

        Raises:
            NotFoundError: If user not found
            ValidationError: If validation fails
        """
        # Get user
        user = self.get_resource_or_raise(
            User,
            user_id,
            tenant_id=tenant_id,
        )

        # Get actor user
        try:
            actor_user = User.objects.get(id=actor_user_id)
        except User.DoesNotExist:
            raise NotFoundError(f"Actor user {actor_user_id} not found")

        # Validate email uniqueness if email is being updated
        if "email" in update_data:
            new_email = update_data["email"]
            if User.objects.filter(email=new_email).exclude(id=user_id).exists():
                raise ValidationError("Email address is already registered", code="EMAIL_EXISTS")

        # Update fields
        for field, value in update_data.items():
            if hasattr(user, field) and field != "id":
                setattr(user, field, value)

        user.save()

        # Create audit event
        log_user_operation(
            action="USER_UPDATED",
            user=user,
            actor_user=actor_user,
            details=update_data,
        )

        return user

    def _user_has_resources(self, user: User) -> bool:
        """Check if user has associated resources (assets, datasets, etc.)."""
        from hub.apps.assets.models import Asset
        from hub.apps.contracts.models import Contract
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        if Asset.objects.filter(created_by=user).exists():
            return True
        if Dataset.objects.filter(created_by=user).exists():
            return True
        if Contract.objects.filter(created_by=user).exists():
            return True
        if File.objects.filter(created_by=user).exists():
            return True
        return False

    @transaction.atomic
    def delete_user(
        self,
        user_id: str,
        tenant_id: str,
        actor_user_id: str,
    ) -> bool:
        """
        Delete a user with audit.

        Performs soft delete (status=DISABLED) if user has resources,
        hard delete otherwise.

        Args:
            user_id: User ID to delete
            tenant_id: Tenant ID
            actor_user_id: User ID performing the deletion

        Returns:
            True if soft delete was performed, False if hard delete.

        Raises:
            NotFoundError: If user not found
        """
        from .models import UserStatus

        # Get user
        user = self.get_resource_or_raise(
            User,
            user_id,
            tenant_id=tenant_id,
        )

        # Get actor user
        try:
            actor_user = User.objects.get(id=actor_user_id)
        except User.DoesNotExist:
            raise NotFoundError(f"Actor user {actor_user_id} not found")

        if self._user_has_resources(user):
            # Soft delete: set status to DISABLED
            user.status = UserStatus.DISABLED
            user.save(update_fields=["status", "updated_at"])
            log_user_operation(
                action="USER_DISABLED",
                user=user,
                actor_user=actor_user,
                details={"reason": "User has resources"},
            )
            return True

        # Hard delete
        log_user_operation(
            action="USER_DELETED",
            user=user,
            actor_user=actor_user,
            details={"email": user.email},
        )
        user.delete()
        return False
