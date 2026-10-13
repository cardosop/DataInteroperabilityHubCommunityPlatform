"""
SSO Integration

OIDC single sign-on authentication (D4 — the SAML stub is DELETED, see
oss-release-remediation W1.5: no signature verification existed, so the
stub was an unauthenticated identity assertion surface).

The OIDC flow verifies every ID token via JWKS before ANY user lookup:
signature (RS256/ES256 against the tenant IdP's JWKS), the pinned
issuer, the tenant's OIDC client_id as audience, and expiry — see
``hub.apps.auth.oidc_verifier``. Roles NEVER come from ID-token claims
(role forgery): the user's roles are the DB-assigned ``UserRole`` rows
only.
"""

from __future__ import annotations

from typing import Any

import structlog
from django.contrib.auth import get_user_model

from .oidc_verifier import OIDCTokenVerificationError, verify_oidc_id_token

logger = structlog.get_logger(__name__)

User = get_user_model()


class SSOProvider:
    """Base class for SSO providers"""

    def __init__(self, tenant_id: str, config: dict[str, Any]):
        self.tenant_id = tenant_id
        self.config = config

    def authenticate(self, request_data: dict[str, Any]) -> tuple[User | None, dict[str, Any]]:
        """
        Authenticate user via SSO.

        Returns:
            Tuple of (user, attributes)
        """
        raise NotImplementedError


class OIDCProvider(SSOProvider):
    """
    OpenID Connect (OIDC) SSO provider.

    D4/W1.5: the ID token is verified via JWKS (signature + iss + aud +
    exp) BEFORE the user is found or created — forged, expired, or
    wrong-audience tokens are rejected and never touch the user table.
    """

    def authenticate(self, request_data: dict[str, Any]) -> tuple[User | None, dict[str, Any]]:
        """
        Authenticate user via OIDC.

        Args:
            request_data: OIDC token/claims data (``id_token`` required)

        Returns:
            Tuple of (user, attributes). On verification failure the user
            is None and ``attributes["verification_error"]`` carries the
            classified reason code (never token material).
        """
        id_token = request_data.get("id_token")
        if not id_token:
            return None, {}

        try:
            claims = self._verify_id_token(id_token)
            user_identifier = claims.get("email") or claims["sub"]
            if not user_identifier:
                logger.warning("oidc_auth_no_identifier", tenant_id=self.tenant_id)
                return None, {}
            user = self._get_or_create_user(user_identifier, claims)
        except OIDCTokenVerificationError as exc:
            logger.warning(
                "oidc_token_verification_failed",
                code=exc.code,
                tenant_id=self.tenant_id,
            )
            return None, {"verification_error": exc.code}
        else:
            return user, claims

    def _verify_id_token(self, id_token: str) -> dict[str, Any]:
        """Verify the ID token against the tenant's OIDC configuration.

        The tenant config (``TenantConfig.get_sso_config()["oidc"]``)
        must carry ``issuer`` + ``client_id`` (audience) and either
        ``jwks_uri`` or ``discovery_url``. Missing configuration fails
        CLOSED — the token is rejected, never verified-less.
        """
        oidc_config = self.config or {}
        return verify_oidc_id_token(
            id_token,
            issuer=oidc_config.get("issuer") or "",
            audience=oidc_config.get("client_id") or "",
            jwks_uri=oidc_config.get("jwks_uri"),
            discovery_url=oidc_config.get("discovery_url"),
        )

    def _get_or_create_user(self, identifier: str, claims: dict[str, Any]) -> User | None:
        """Get or create user from VERIFIED OIDC claims."""
        from hub.apps.tenants.models import Tenant

        try:
            tenant = Tenant.objects.get(id=self.tenant_id)
        except Tenant.DoesNotExist:
            return None

        # Try to find existing user by email
        try:
            user = User.objects.get(email=identifier, tenant=tenant)
            # Update user attributes from OIDC
            self._update_user_from_claims(user, claims)
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create_user(
                email=identifier,
                tenant=tenant,
                password=None,  # SSO users don't have passwords
                status="ACTIVE",
            )
            self._update_user_from_claims(user, claims)
            return user
        else:
            return user

    def _update_user_from_claims(self, user: User, claims: dict[str, Any]):
        """Update profile fields from VERIFIED claims.

        D4/W1.5 role forgery: ``roles``/``groups`` claims are DELIBERATELY
        IGNORED — role assignment happens through the DB (UserRole rows),
        never through IdP-asserted strings.
        """
        # Update user fields from OIDC claims (cosmetic profile data only)
        if "given_name" in claims:
            user.first_name = claims["given_name"]
        if "family_name" in claims:
            user.last_name = claims["family_name"]

        user.save()


class SSOService:
    """
    Service for SSO integration and authentication.

    D4/W1.5: OIDC only — the SAML stub (provider, service methods, and
    the unverified claim extractors) is deleted; the SSO endpoints
    resolve tenants ONLY through the signed one-time ``state`` payload
    (``hub.apps.auth.sso_state``), never through unverified identity
    claims.
    """

    @staticmethod
    def get_provider(tenant_id: str, provider_type: str) -> SSOProvider | None:
        """
        Get SSO provider for tenant.

        Args:
            tenant_id: Tenant UUID
            provider_type: "OIDC" (SAML is retired)

        Returns:
            SSOProvider instance or None
        """
        from hub.apps.tenants.models import Tenant, TenantConfig

        if provider_type.upper() != "OIDC":
            return None
        try:
            tenant = Tenant.objects.get(id=tenant_id)
            config = TenantConfig.objects.filter(tenant=tenant).first()

            if not config or not config.sso_config:
                return None

            sso_config = config.get_sso_config().get("oidc")
            if not sso_config:
                return None
        except Tenant.DoesNotExist:
            # Expected: the tenant record does not exist.  The view will return
            # 400 — no need to log at ERROR level.
            return None
        except Exception as e:
            logger.exception("sso_provider_error", error=str(e), tenant_id=tenant_id)
            return None
        else:
            return OIDCProvider(tenant_id, sso_config)

    @staticmethod
    def authenticate_oidc(
        tenant_id: str, id_token: str, access_token: str | None = None
    ) -> tuple[User | None, dict[str, Any]]:
        """
        Authenticate user via OIDC (JWKS-verified ID token).

        Args:
            tenant_id: Tenant UUID
            id_token: OIDC ID token
            access_token: Optional access token

        Returns:
            Tuple of (user, attributes)
        """
        provider = SSOService.get_provider(tenant_id, "OIDC")
        if not provider:
            return None, {}

        return provider.authenticate({"id_token": id_token, "access_token": access_token})

    @staticmethod
    def get_sso_login_url(
        tenant_id: str,
        provider_type: str,
        redirect_uri: str,
        state: str | None = None,
    ) -> str | None:
        """
        Get SSO login URL for redirect (OIDC only — SAML is retired).

        Args:
            tenant_id: Tenant UUID
            provider_type: Provider type ("OIDC")
            redirect_uri: Redirect URI after authentication

        Returns:
            SSO login URL or None
        """
        provider = SSOService.get_provider(tenant_id, provider_type)
        if not provider:
            return None

        config = provider.config

        if provider_type.upper() == "OIDC":
            # Generate OIDC authorization URL
            auth_url = config.get("authorization_endpoint")
            client_id = config.get("client_id")
            if auth_url and client_id:
                from urllib.parse import urlencode

                params = {
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "scope": "openid email profile",
                    "state": state or "...",
                }
                return f"{auth_url}?{urlencode(params)}"

        return None
