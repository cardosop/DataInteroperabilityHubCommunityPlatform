"""Databricks U2M OIDC provider (openspec add-databricks-control-plane task 0b.1).

Implements the repo's ``SSOProvider`` framework (``hub/apps/auth/sso.py``)
for the Databricks user-to-machine auth-code flow:

1. ``build_authorize_url`` — ``GET {host}/oidc/v1/authorize`` with
   ``response_type=code``, PKCE ``code_challenge`` (S256), and the signed
   ``state`` issued by ``hub.apps.auth.sso_state``. The PKCE VERIFIER is
   persisted server-side in the real cache (keyed by the state hash, same
   300s TTL as the state) — the client only ever sees the challenge.
2. ``exchange_auth_code`` — the callback path. The signed state is
   CONSUMED (single-use, TTL, ip-class, tenant binding) BEFORE any network
   call: a replayed / expired / ip-mismatched / tenant-mismatched /
   verifier-less state produces ZERO requests against the token endpoint.
   Only then does the provider ``POST {host}/oidc/v1/token`` with
   ``grant_type=authorization_code`` + ``code`` + ``code_verifier``.

Provider boundary: this module lives in ``databricks_admin`` (Databricks
endpoints are provider-specific); the generic framework it implements
stays in ``hub/apps/auth`` (provider-agnostic).
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from django.core.cache import cache

from hub.apps.auth.sso import SSOProvider
from hub.apps.auth.sso_state import SSOStateError, consume_state

_VERIFIER_CACHE_PREFIX = "sso:pkce:verifier:"
# Mirrors the signed-state TTL — the verifier must never outlive its state.
_PKCE_TTL_SECONDS = 300
_AUTHORIZE_PATH = "/oidc/v1/authorize"
_TOKEN_PATH = "/oidc/v1/token"
# 0b.2 scope contract: the U2M flow requests the Databricks API scopes
# (``sql`` + ``all-apis``) and ``offline_access`` so the token endpoint
# returns a REFRESH token for OBO persistence (UC-DB-003: without
# offline_access, no refresh token is persisted). The identity scopes
# (``openid email profile``) are OPTIONAL — appended only when the tenant
# config enables them, per the 0b.2 contract.
_DEFAULT_SCOPES = "sql all-apis offline_access"
_IDENTITY_SCOPES = "openid email profile"

SSO_CONSENT_EXPLAINER: dict[str, Any] = {
    "title": "Allow the Hub to access your Databricks workspace",
    "scopes": {
        "sql": (
            "Run SQL statements in your Databricks workspace on your behalf, "
            "with the same permissions your own Databricks account has."
        ),
        "all-apis": (
            "Call Databricks REST APIs on your behalf for actions you initiate "
            "in the Hub — always under your own Databricks permissions."
        ),
        "offline_access": (
            "Keep a refresh token so the Hub can keep acting on your behalf "
            "during your Hub session without asking you again."
        ),
    },
    "statements": [
        (
            "The Hub acts on your behalf only for operations you start "
            "(queries, catalog browsing, jobs) — background system jobs use "
            "separate service credentials, never your token."
        ),
        (
            "Your tokens are stored encrypted at rest and are bound to this "
            "workspace only — they are never shared with other workspaces."
        ),
        (
            "You can revoke access at any time: logging out of the Hub revokes "
            "the tokens, and you can also revoke the Hub app in your "
            "Databricks workspace settings."
        ),
    ],
}


class DatabricksSSOUnavailableError(ValueError):
    """U2M SSO is not supported for this workspace (GCP — task 0b.8).

    Carries the catalogue code ``DATABRICKS_SSO_UNAVAILABLE`` (UC-DB-003
    error table: GCP workspace → 400 with this code).
    """

    def __init__(self, workspace_name: str):
        super().__init__(
            f"Sign-in with Databricks is unavailable for workspace "
            f"'{workspace_name}' (GCP does not support user-to-machine SSO)."
        )
        self.code = "DATABRICKS_SSO_UNAVAILABLE"


def ensure_sso_supported(workspace) -> None:
    """Raise ``DatabricksSSOUnavailableError`` for GCP workspaces — the
    guard every SSO entry point (authorize/build URL, callback) must run
    BEFORE any redirect or token exchange."""
    from hub.apps.databricks_admin.models import DatabricksCloud

    if getattr(workspace, "cloud", None) == DatabricksCloud.GCP:
        raise DatabricksSSOUnavailableError(workspace.name)


class DatabricksOIDCTokenError(ValueError):
    """Token-endpoint rejection — the OAuth error code is preserved."""

    def __init__(self, code: str, description: str = ""):
        super().__init__(description or code)
        self.code = code


def _verifier_cache_key(state: str) -> str:
    """Cache key for the PKCE verifier — keyed by the STATE's hash so the
    verifier is only retrievable by the exact state that minted it."""
    digest = hashlib.sha256(state.encode()).hexdigest()
    return f"{_VERIFIER_CACHE_PREFIX}{digest}"


def _s256_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def classify_sso_state_error(_exc: SSOStateError) -> str:
    """Map any signed-state validation failure to the API-surface code
    (``DATABRICKS_SSO_STATE_MISMATCH``, UC-DB-003 error table). The
    internal diagnostic codes (REUSED / EXPIRED / ...) stay on the
    exception; the callback surface exposes only the catalogue code."""
    return "DATABRICKS_SSO_STATE_MISMATCH"


class DatabricksOIDCProvider(SSOProvider):
    """U2M auth-code flow provider with PKCE (S256) + signed-state validation.

    Config keys (from the tenant's SSO config, ``sso_config.databricks``):
        ``host``           — workspace host (``dbc-….cloud.databricks.com``)
        ``client_id``      — OIDC client id registered in the Databricks
                             account console (BYO runbook, task 0b.9)
        ``redirect_uri``   — the registered callback URI
        ``scopes``         — optional; defaults to
                             ``sql all-apis offline_access`` (task 0b.2)
        ``oidc_base_url``  — optional override of the scheme+authority
                             (defaults to ``https://{host}``); the seam the
                             tests point at a real local HTTP server.
    """

    def __init__(self, tenant_id: str, config: dict[str, Any]):
        super().__init__(tenant_id, config)
        self.host = str(config.get("host") or "").strip().rstrip("/")
        self.client_id = str(config.get("client_id") or "")
        self.redirect_uri = str(config.get("redirect_uri") or "")
        # Fail loud at construction: a missing host/client_id/redirect_uri
        # would otherwise surface later as a silently broken login URL.
        missing = [key for key in ("host", "client_id", "redirect_uri") if not getattr(self, key)]
        if missing:
            raise ValueError(
                f"DatabricksOIDCProvider requires non-empty config keys: {', '.join(missing)}"
            )
        explicit_scopes = str(config.get("scopes") or "").strip()
        if explicit_scopes:
            # An explicit override wins as-is (never auto-appended).
            self.scopes = explicit_scopes
        else:
            # 0b.2: default `sql all-apis offline_access`; the identity
            # scopes are OPTIONAL and appended only when enabled.
            self.scopes = _DEFAULT_SCOPES
            if config.get("include_openid_scopes"):
                self.scopes = f"{self.scopes} {_IDENTITY_SCOPES}"
        self.oidc_base_url = str(config.get("oidc_base_url") or f"https://{self.host}").rstrip("/")

    def build_authorize_url(self, *, state: str) -> dict[str, str]:
        """Build the authorize URL; persist the PKCE verifier for the state."""
        verifier = secrets.token_urlsafe(48)
        cache.set(
            _verifier_cache_key(state),
            verifier,
            timeout=_PKCE_TTL_SECONDS,
        )
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scopes,
            "state": state,
            "code_challenge": _s256_challenge(verifier),
            "code_challenge_method": "S256",
        }
        return {"login_url": f"{self.oidc_base_url}{_AUTHORIZE_PATH}?{urlencode(params)}"}

    def exchange_auth_code(
        self,
        *,
        code: str,
        state: str,
        ip_class: str,
    ) -> dict[str, Any]:
        """Callback exchange — state is consumed BEFORE any network call."""
        if not code:
            raise DatabricksOIDCTokenError(
                "invalid_request",
                "authorization code is missing",
            )

        # 1. Validate + consume the signed state (single-use, TTL, ip-class,
        #    signature) — the security gate the task requires upstream of
        #    the token POST.
        consumed_tenant = consume_state(state, ip_class)

        # 2. The state must belong to THIS provider's tenant.
        if str(consumed_tenant) != str(self.tenant_id):
            raise SSOStateError("SSO_STATE_TENANT_MISMATCH")

        # 3. The verifier minted for this exact state must still exist.
        verifier = cache.get(_verifier_cache_key(state))
        if not verifier:
            raise SSOStateError("SSO_STATE_INVALID")
        cache.delete(_verifier_cache_key(state))

        # 4. Token exchange.
        try:
            response = httpx.post(
                f"{self.oidc_base_url}{_TOKEN_PATH}",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "code_verifier": verifier,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                },
                timeout=15,
            )
        except httpx.HTTPError as exc:
            # A failed LOGIN is a failed login regardless of the failure
            # mode — transport failures are audited like rejections
            # (abuse/brute-force detection needs every failure).
            self._emit_login_audit("FAILURE", {"error": "transport_error"})
            raise DatabricksOIDCTokenError(
                "transport_error",
                f"Databricks token endpoint unreachable: {type(exc).__name__}",
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            self._emit_login_audit("FAILURE", {"error": "invalid_response"})
            raise DatabricksOIDCTokenError(
                "invalid_response",
                f"Databricks token endpoint returned a non-JSON body: {exc}",
            ) from exc
        if not isinstance(payload, dict):
            self._emit_login_audit("FAILURE", {"error": "invalid_response"})
            raise DatabricksOIDCTokenError(
                "invalid_response",
                "Databricks token endpoint returned a non-object JSON body",
            )
        if not response.is_success:
            self._emit_login_audit(
                "FAILURE",
                {"error": str(payload.get("error") or f"HTTP_{response.status_code}")},
            )
            raise DatabricksOIDCTokenError(
                str(payload.get("error") or f"HTTP_{response.status_code}"),
                str(payload.get("error_description") or payload.get("error") or ""),
            )
        self._emit_login_audit("SUCCESS")
        return payload

    def _emit_login_audit(self, result: str, details: dict | None = None) -> None:
        """Best-effort SSO login audit (0b.11 — an audit-DB outage never
        blocks the exchange)."""
        import logging

        logger = logging.getLogger(__name__)
        try:
            from hub.apps.audit.utils import create_audit_event
            from hub.apps.tenants.models import Tenant as _Tenant

            tenant_obj = _Tenant.all_objects.filter(id=self.tenant_id).first()
            create_audit_event(
                resource_type="DATABRICKS_SSO",
                action="LOGIN_SUCCESS" if result == "SUCCESS" else "LOGIN_FAILED",
                tenant=tenant_obj,  # FK needs the object; None → system row
                resource_id=None,
                result=result,
                details=details or {},
            )
        except Exception:
            logger.warning("databricks_sso_login_audit_failed", extra={"result": result})
