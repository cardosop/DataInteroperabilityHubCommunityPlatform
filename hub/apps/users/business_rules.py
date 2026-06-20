"""
Phase 277.2.5 — UserBusinessRules.

Consolidates user-creation validation that was previously scattered
across serializers and services into a single registered rule class.

``validate_user_creation(data, tenant, actor)`` performs:
  - duplicate email detection
  - missing tenant check
  - invalid status transitions (via UserCreateSerializer validation)
  - password minimum length enforcement
  - role assignment validation (roles must belong to the same tenant)
  - invitation token expiry check
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from django.utils.translation import gettext_lazy as _

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.users.models import User, UserStatus

logger = logging.getLogger(__name__)


@dataclass
class UserCreationValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@register_rule(
    rule_name="user_creation_validation",
    description="Validates user creation including duplicate email, tenant, status, password, roles, and invitation expiry",
    tags=["users", "validation", "security"],
    priority=10,
    openspec_ref="openspec/changes/preprod01/specs/business-rules-hardening/spec.md",
)
class UserBusinessRules(BusinessRules):
    """Business rules for user lifecycle validation."""

    def validate_user_creation(
        self,
        email: str,
        tenant_id: str | None = None,
        password: str | None = None,
        status: str | None = None,
        role_ids: list[str] | None = None,
        invitation_token: str | None = None,
    ) -> UserCreationValidationResult:
        """
        Validate user-creation inputs.

        Returns ``UserCreationValidationResult(is_valid=True)`` when all
        checks pass, or ``is_valid=False`` with a list of error messages.
        """
        errors: list[str] = []
        details: dict[str, Any] = {}

        # 1. Duplicate email
        email_lower = email.lower().strip() if email else ""
        if User.objects.filter(email__iexact=email_lower).exists():
            errors.append(str(_("Email address is already registered")))
            details["code"] = "EMAIL_EXISTS"

        # 2. Missing tenant
        if tenant_id is not None and not tenant_id.strip():
            errors.append(str(_("Tenant is required")))
            details.setdefault("code", "TENANT_REQUIRED")

        # 3. Invalid status
        valid_statuses = {s.value for s in UserStatus}
        if status is not None and status not in valid_statuses:
            errors.append(f"{_('Invalid user status:')} {status}. Valid: {sorted(valid_statuses)}")
            details.setdefault("code", "INVALID_STATUS")

        # 4. Password minimum length (10 chars — Phase 277.B.065)
        if password is not None and len(password) < 10:
            errors.append(str(_("Password must be at least 10 characters")))
            details.setdefault("code", "WEAK_PASSWORD")

        # 5. Role assignment validation — roles must belong to the
        #    same tenant.  Actual DB-side enforcement happens in
        #    UserService.create_user / UserCreateSerializer; this is
        #    the business-rule contract layer.
        if role_ids is not None and tenant_id is not None:
            from hub.apps.users.models import Role

            mismatched = (
                Role.objects.filter(
                    id__in=role_ids,
                )
                .exclude(tenant_id=tenant_id)
                .count()
            )
            if mismatched > 0:
                errors.append(f"{mismatched} role(s) do not belong to tenant {tenant_id}")
                details.setdefault("code", "ROLE_TENANT_MISMATCH")

        # 6. Invitation token expiry
        if invitation_token is not None:
            user = User.objects.filter(invitation_token=invitation_token).first()
            if user is not None and hasattr(user, "invitation_token_expires_at"):
                from django.utils import timezone

                expires = user.invitation_token_expires_at
                if expires is not None and timezone.now() > expires:
                    errors.append(str(_("Invitation token has expired")))
                    details.setdefault("code", "INVITATION_EXPIRED")

        if errors:
            return UserCreationValidationResult(
                is_valid=False,
                errors=errors,
                details=details,
            )

        return UserCreationValidationResult(is_valid=True)

    def validate(
        self, context: RuleExecutionContext | None = None, *args, **kwargs  # noqa: ARG002
    ) -> ValidationResult:
        """Abstract method required by :class:`BusinessRules`.

        Delegates to :meth:`validate_user_creation` with parameters
        extracted from *context* or *kwargs*.

        Returns a standard :class:`ValidationResult`.
        """
        if context is not None:
            kwargs.setdefault("tenant_id", context.tenant_id)
            if context.metadata:
                kwargs.setdefault("email", context.metadata.get("email"))
                kwargs.setdefault("password", context.metadata.get("password"))
                kwargs.setdefault("status", context.metadata.get("status"))
                kwargs.setdefault("role_ids", context.metadata.get("role_ids"))
                kwargs.setdefault("invitation_token", context.metadata.get("invitation_token"))

        result = self.validate_user_creation(
            email=kwargs.get("email", ""),
            tenant_id=kwargs.get("tenant_id"),
            password=kwargs.get("password"),
            status=kwargs.get("status"),
            role_ids=kwargs.get("role_ids"),
            invitation_token=kwargs.get("invitation_token"),
        )
        return ValidationResult(
            is_valid=result.is_valid,
            errors=result.errors,
            details=result.details,
        )
