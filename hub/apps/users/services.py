"""
User Service

Service layer for user operations.
All create/update/delete paths apply validation and audit.
"""

import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant

    User = get_user_model()
from django.db import IntegrityError, transaction

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

        # Plan limit enforcement
        from hub.apps.tenants.services import PlanLimitService
        plan_limit_service = PlanLimitService(tenant_id=tenant_id)
        plan_limit_service.check_limit(
            tenant_id=tenant_id,
            limit_key="max_users",
            delta=1,
        )

        # Get actor user
        try:
            actor_user = User.objects.get(id=actor_user_id)
        except User.DoesNotExist:
            raise NotFoundError(f"Actor user {actor_user_id} not found")

        # Set status based on invitation, but respect explicit status if provided
        if status is None:
            if send_invitation:
                status = UserStatus.INVITED
            else:
                status = UserStatus.ACTIVE

        # Create user (nested atomic block acts as savepoint for IntegrityError)
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    tenant=tenant,
                    display_name=display_name or "",
                    status=status,
                    **kwargs,
                )
        except IntegrityError:
            raise ValidationError(
                "Email address is already registered",
                code="EMAIL_EXISTS",
            )

        # Assign roles if provided — bulk_create is O(1) queries vs O(n)
        if role_ids:
            roles = Role.objects.filter(id__in=role_ids, tenant=tenant)
            UserRole.objects.bulk_create(
                [UserRole(user=user, tenant=role.tenant, role=role) for role in roles],
                ignore_conflicts=True,
            )

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

        # Handle role_ids (replace user roles)
        role_ids = update_data.pop("role_ids", None)
        if role_ids is not None:
            from .models import Role, UserRole

            tenant = user.tenant
            roles = list(Role.objects.filter(id__in=role_ids, tenant=tenant))
            UserRole.objects.filter(user=user).delete()
            # bulk_create is O(1) queries vs O(n) get_or_create round-trips (13.9)
            UserRole.objects.bulk_create(
                [UserRole(user=user, tenant=role.tenant, role=role) for role in roles],
                ignore_conflicts=True,
            )
            user.increment_token_version()

        # Update fields
        for field, value in update_data.items():
            if hasattr(user, field) and field != "id":
                setattr(user, field, value)

        try:
            with transaction.atomic():
                user.save()
        except IntegrityError:
            raise ValidationError(
                "Email address is already registered",
                code="EMAIL_EXISTS",
            )

        # Create audit event (include role_ids if changed)
        audit_details = dict(update_data)
        if role_ids is not None:
            audit_details["role_ids"] = [str(r) for r in role_ids]
        log_user_operation(
            action="USER_UPDATED",
            user=user,
            actor_user=actor_user,
            details=audit_details,
        )

        return user

    @transaction.atomic
    def invite_user_to_tenant(
        self,
        tenant_id: str,
        actor_user_id: str,
        email: str,
        display_name: Optional[str] = None,
        role_ids: Optional[list] = None,
        send_invitation: bool = True,
    ) -> tuple[User, bool]:
        """
        Invite a user to join a tenant.

        When User exists (same email): add UserTenantMembership instead of failing.
        When User does not exist: create User + membership.

        Args:
            tenant_id: Tenant to invite user to
            actor_user_id: User ID performing the invitation
            email: Invitee email
            display_name: Optional display name (used only when creating new user)
            role_ids: Optional list of role IDs to assign (from inviting tenant)
            send_invitation: Whether to send invitation email (for new users only)

        Returns:
            Tuple of (User instance, created_new: bool)
            created_new is True when a new user was created, False when existing user was added.
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import Role, UserRole, UserStatus

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(f"Tenant {tenant_id} not found")

        try:
            actor_user = User.objects.get(id=actor_user_id)
        except User.DoesNotExist:
            raise NotFoundError(f"Actor user {actor_user_id} not found")

        membership_service = UserTenantMembershipService()

        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            from hub.apps.users.models import UserTenantMembership

            already_member = (
                (existing_user.tenant_id is not None and str(existing_user.tenant_id) == str(tenant_id))
                or UserTenantMembership.objects.filter(user=existing_user, tenant=tenant).exists()
            )
            if already_member:
                # Idempotent: user already a member → return existing user with
                # created=False, matching the non-member existing-user branch below.
                return existing_user, False
            membership_service.add_membership(existing_user, tenant)

            if role_ids:
                roles = Role.objects.filter(id__in=role_ids, tenant=tenant)
                # bulk_create is O(1) queries vs O(n) get_or_create round-trips (13.9)
                UserRole.objects.bulk_create(
                    [UserRole(user=existing_user, tenant=role.tenant, role=role) for role in roles],
                    ignore_conflicts=True,
                )

            # Audit in inviting tenant's context (action performed there)
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="USER",
                action="USER_TENANT_INVITED",
                actor_user=actor_user,
                tenant=tenant,
                resource_id=str(existing_user.id),
                result="SUCCESS",
                details={
                    "email": email,
                    "tenant_id": tenant_id,
                    "role_ids": role_ids,
                },
            )
            return existing_user, False

        user = self.create_user(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            email=email,
            display_name=display_name,
            status=UserStatus.INVITED,
            role_ids=role_ids or [],
            send_invitation=send_invitation,
        )
        membership_service.add_membership(user, tenant)
        return user, True

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
            # Soft delete: set status to DISABLED + bump token_version so
            # existing JWTs are rejected immediately (B3 fix —
            # glittery-dreaming-micali.md). Without the version bump, the
            # disabled user's sessions remain valid until the access_token
            # naturally expires (up to 2 h on staging, 15 min on prod).
            #
            # Single save with both fields — avoids the non-atomic
            # two-save pattern that increment_token_version() + save()
            # would produce (review fix from 225.5.review).
            user.status = UserStatus.DISABLED
            user.token_version += 1
            user.save(update_fields=[
                "status", "token_version", "updated_at",
            ])
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


class UserTenantMembershipService:
    """
    Service for user–tenant membership operations (tenant switch).

    Provides add_membership, list_tenants_for_user, validate_membership.
    Per design D16 and specs/tenants/spec.md User Tenant Membership.
    """

    def add_membership(self, user, tenant) -> None:
        """
        Add user to tenant (idempotent). Creates UserTenantMembership if not exists.

        Args:
            user: User instance
            tenant: Tenant instance
        """
        from .models import UserTenantMembership

        UserTenantMembership.objects.get_or_create(
            user=user,
            tenant=tenant,
            defaults={},
        )

    def list_tenants_for_user(self, user) -> list:
        """
        Return list of Tenant objects the user has membership in.

        Args:
            user: User instance

        Returns:
            List of Tenant instances, ordered by created_at
        """
        from .models import UserTenantMembership

        memberships = (
            UserTenantMembership.objects.filter(user=user)
            .select_related("tenant")
            .order_by("created_at")
        )
        return [m.tenant for m in memberships]

    def validate_membership(self, user, tenant_id) -> bool:
        """
        Check if user has membership in the given tenant.

        Args:
            user: User instance
            tenant_id: Tenant ID (str or UUID)

        Returns:
            True if membership exists, False otherwise.
            Returns False for None or invalid tenant_id (defensive; avoids 500 on malformed input).
        """
        if tenant_id is None:
            return False
        if isinstance(tenant_id, str) and not tenant_id.strip():
            return False
        try:
            uuid.UUID(str(tenant_id))
        except (ValueError, TypeError, AttributeError):
            return False

        from .models import UserTenantMembership

        return UserTenantMembership.objects.filter(
            user=user, tenant_id=tenant_id
        ).exists()


# ---------------------------------------------------------------------------
# Phase 227 Wave 0 — tenant-admin lookup
# ---------------------------------------------------------------------------

def get_tenant_admin_users(tenant) -> "Any":
    """Return the active TENANT_ADMIN users for a tenant.

    Returns a queryset of `User` rows that hold the `TENANT_ADMIN` role
    in the given tenant. Results are de-duplicated (a user with multiple
    overlapping role rows appears once). Returns an empty queryset if no
    TENANT_ADMIN role exists for the tenant.

    Used by the structureless-contract notification path
    (Phase 227.0.3) and by any future code that needs to broadcast a
    governance-tier message to tenant admins.

    Args:
        tenant: ``Tenant`` instance.

    Returns:
        QuerySet[User] — distinct active TENANT_ADMIN users for the
        tenant. Always usable as an iterable; never raises on empty.
    """
    from hub.apps.users.models import Role, UserRole

    role = Role.objects.filter(tenant=tenant, name="TENANT_ADMIN").first()
    if role is None:
        return User.objects.none()

    user_ids = (
        UserRole.objects.filter(role=role, tenant=tenant)
        .values_list("user_id", flat=True)
        .distinct()
    )
    return User.objects.filter(id__in=user_ids).distinct()
