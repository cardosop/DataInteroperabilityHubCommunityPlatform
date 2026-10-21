"""
Internal Worker API Authentication

Authentication and permission for scheduled ingestion internal endpoints
used only by the Prefect worker. Supports:
- HUB_WORKER_API_KEY (env): worker sends Authorization: ApiKey <key> and X-Tenant-ID
- API key from DB with scope scheduled_ingestion:internal
"""

import hmac
import logging

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import authentication, permissions
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)

# Scope required for internal scheduled-ingestion endpoints when using DB API key.
# W6.5 (S1) — canonical definition lives in hub/apps/auth/scopes.py (the
# Django-free vocabulary the SDK/CLI contract test imports); re-exported
# here so existing importers keep working.
from hub.apps.auth.scopes import SCOPE_SCHEDULED_INGESTION_INTERNAL


class WorkerAPIKeyAuthentication(authentication.BaseAuthentication):
    """
    Authenticate internal worker requests:
    1. If HUB_WORKER_API_KEY is set and request has that key, accept and set tenant from X-Tenant-ID.
    2. Otherwise delegate to APIKeyAuthentication; scope is checked by permission class.
    """

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        api_key = None
        if auth_header.startswith("ApiKey "):
            api_key = auth_header.split(" ", 1)[1].strip()
        if not api_key:
            api_key = request.META.get("HTTP_X_API_KEY")

        if not api_key:
            return None

        worker_key = getattr(settings, "HUB_WORKER_API_KEY", None)
        # Phase P.8 — timing-safe comparison: the env key is a shared
        # secret; a plain `==` leaks prefix information over the network.
        if worker_key and hmac.compare_digest(api_key, worker_key):
            tenant_id = request.META.get("HTTP_X_TENANT_ID") or request.headers.get("X-Tenant-ID")
            if not tenant_id:
                raise AuthenticationFailed("X-Tenant-ID header required for worker API key")
            from hub.apps.tenants.models import Tenant

            try:
                tenant = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                raise AuthenticationFailed("Invalid X-Tenant-ID for worker") from None
            from hub.apps.users.models import User

            user = User.objects.filter(tenant=tenant).first()
            if not user:
                raise AuthenticationFailed("No user found for worker tenant")
            request.tenant_id = str(tenant.id)
            request.tenant = tenant
            request.api_key_scopes = [SCOPE_SCHEDULED_INGESTION_INTERNAL]
            request.worker_authenticated = True
            return (user, api_key)

        from hub.apps.auth.authentication import APIKeyAuthentication

        auth = APIKeyAuthentication()
        result = auth.authenticate(request)
        if result is not None and hasattr(request, "api_key_scopes"):
            request.worker_authenticated = SCOPE_SCHEDULED_INGESTION_INTERNAL in (
                request.api_key_scopes or []
            )
        return result

    def authenticate_header(self, _request):
        return "ApiKey"


class WorkerInternalAPIPermission(permissions.BasePermission):
    """
    Allow only worker-authenticated requests (env key or API key with scope scheduled_ingestion:internal).
    Reject unauthenticated and tokens without the internal scope.
    """

    def has_permission(self, request, _view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request, "worker_authenticated", False):
            return True
        if hasattr(request, "api_key_scopes") and request.api_key_scopes:
            return SCOPE_SCHEDULED_INGESTION_INTERNAL in request.api_key_scopes
        return False


class WorkerAPIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    OpenAPI security-scheme extension for the worker's API-key auth.

    The worker sends ``Authorization: ApiKey <key>`` (env key) or a
    DB-scoped API key, plus ``X-Tenant-ID`` for tenant context.
    """

    target_class = "hub.apps.scheduled_ingestion.internal_auth.WorkerAPIKeyAuthentication"
    name = "WorkerApiKeyIngestion"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": (
                "Internal worker API key. Send the key in the Authorization "
                "header as: ApiKey <key> (plus X-Tenant-ID for tenant context)."
            ),
        }
