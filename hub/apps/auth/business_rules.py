"""
Auth Business Rules — Phase 74 (74.1)

Centralizes auth validation logic that was previously inline in views.py.
"""

import re
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from hub.apps.core.business_rules.base import BusinessRules, ValidationResult

User = get_user_model()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthBusinessRules(BusinessRules):
    """Business rules for authentication operations."""

    def validate(self, context=None, *args, **kwargs):
        return ValidationResult(is_valid=True)

    def get_rule_name(self) -> str:
        return "auth_validation"

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def validate_registration(
        self, email: str, tenant_id: Optional[str] = None
    ) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if not email or not _EMAIL_RE.match(email):
            result.is_valid = False
            result.errors.append("Invalid email format")
            return result

        if User.objects.filter(email=email).exists():
            result.is_valid = False
            result.errors.append("Email already registered")
            return result

        if tenant_id:
            from hub.apps.tenants.models import Tenant
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                if hasattr(tenant, "status") and tenant.status == "SUSPENDED":
                    result.is_valid = False
                    result.errors.append("Tenant is suspended")
                    return result
            except Tenant.DoesNotExist:
                result.is_valid = False
                result.errors.append("Tenant not found")
                return result

        return result

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def validate_login_attempt(
        self, email: str, tenant_id: Optional[str] = None
    ) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if not email or not _EMAIL_RE.match(email):
            result.is_valid = False
            result.errors.append("Invalid email format")
            return result

        # Lockout check
        max_attempts = getattr(settings, "LOGIN_MAX_ATTEMPTS", 10)
        window_minutes = getattr(settings, "LOGIN_LOCKOUT_WINDOW_MINUTES", 15)
        since = timezone.now() - timedelta(minutes=window_minutes)
        from hub.apps.auth.models import LoginAttempt
        failures = LoginAttempt.objects.filter(
            email=email, success=False, created_at__gte=since
        ).count()
        if failures >= max_attempts:
            result.is_valid = False
            result.errors.append("Account locked due to too many failed attempts")
            return result

        if tenant_id:
            from hub.apps.tenants.models import Tenant
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                if hasattr(tenant, "status") and tenant.status == "SUSPENDED":
                    result.is_valid = False
                    result.errors.append("Tenant is suspended")
            except Tenant.DoesNotExist:
                result.is_valid = False
                result.errors.append("Tenant not found")

        return result

    # ------------------------------------------------------------------
    # Invitation acceptance
    # ------------------------------------------------------------------

    def validate_invitation_acceptance(
        self, token: str, email: str
    ) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if not token:
            result.is_valid = False
            result.errors.append("Token is required")
            return result

        from hub.apps.auth.utils import sha256_hex
        token_hash = sha256_hex(token)
        try:
            user = User.objects.get(invitation_token=token_hash)
        except User.DoesNotExist:
            result.is_valid = False
            result.errors.append("Invalid invitation token")
            return result

        if user.status != "INVITED":
            result.is_valid = False
            result.errors.append("Invitation already accepted or expired")
            return result

        if email and user.email.lower() != email.lower():
            result.is_valid = False
            result.errors.append("Email does not match invitation")

        return result

    # ------------------------------------------------------------------
    # Token refresh
    # ------------------------------------------------------------------

    def validate_token_refresh(self, refresh_token_str: str) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if not refresh_token_str:
            result.is_valid = False
            result.errors.append("Refresh token is required")
            return result

        from hub.apps.auth.models import RefreshToken
        token_hash = RefreshToken.hash_token(refresh_token_str)
        try:
            token_obj = RefreshToken.objects.select_related("user").get(
                token_hash=token_hash
            )
        except RefreshToken.DoesNotExist:
            result.is_valid = False
            result.errors.append("Invalid refresh token")
            return result

        if token_obj.is_revoked():
            result.is_valid = False
            result.errors.append("Token has been revoked")
            result.details["family_compromised"] = True
            return result

        if token_obj.is_expired():
            result.is_valid = False
            result.errors.append("Token has expired")

        return result
