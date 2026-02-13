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

        # Create audit event
        log_user_operation(
            action="USER_CREATED",
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

    @transaction.atomic
    def delete_user(
        self,
        user_id: str,
        tenant_id: str,
        actor_user_id: str,
    ) -> None:
        """
        Delete a user with audit.

        Args:
            user_id: User ID to delete
            tenant_id: Tenant ID
            actor_user_id: User ID performing the deletion

        Raises:
            NotFoundError: If user not found
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

        # Create audit event before deletion
        log_user_operation(
            action="USER_DELETED",
            user=user,
            actor_user=actor_user,
            details={"email": user.email},
        )

        # Delete user
        user.delete()
