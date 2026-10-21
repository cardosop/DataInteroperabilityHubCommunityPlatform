"""
Authentication Middleware

Middleware for tenant scoping and request enrichment.

CRITICAL: This middleware runs BEFORE REST Framework authentication.
It extracts tenant_id from Authorization headers (API keys or JWT tokens)
so that rate limiting middleware can access it.

REST Framework authentication will run later and can override/validate.

RLS request-path arming (W1.20 / oss-release-remediation D2, W1.4b)
===================================================================

After tenant resolution, ``__call__`` wraps the rest of the request in
``transaction.atomic()`` and sets, transaction-locally (SET LOCAL):

* ``app.current_tenant_id`` — the resolved tenant (NULL for anonymous
  requests: the RLS policies then hide every tenant row — arming fails
  CLOSED, leaks become empty results, never cross-tenant rows);
* one ``app.rls_<table>_enabled`` GUC per RLS policy, mapped from the
  paired ``RLS_<TABLE>_ENABLED`` settings kill switch.

The whole path is gated behind the ``RLS_REQUEST_PATH_ENABLED`` master
kill switch (default True — armed; set it false to disable arming
without a deploy).  Transaction-local GUCs are mandatory: staging and
production run through PgBouncer transaction pooling, where a
session-level SET would leak onto the next client reusing the pooled
server connection.  SET LOCAL evaporates at COMMIT/ROLLBACK, so the
connection is clean for the next request (pinned by
``test_rls_middleware_guc`` / ``test_rls_request_path_arming``).

Pre-tenant identity resolution: the middleware's own lookups (API
keys, JWT users, memberships) run BEFORE the tenant GUC exists and
touch RLS-enabled tables — they route through ``user_lookup_alias()``
(the BYPASSRLS admin alias in the production role shape; the default
connection everywhere else).  See ``hub/apps/auth/db_aliases.py``.
"""

import hmac

import structlog
from django.apps.registry import AppRegistryNotReady
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, InterfaceError, OperationalError, transaction
from django.http import HttpResponse, JsonResponse

logger = structlog.get_logger(__name__)

# Phase 240.4.B.5 — guard get_user_model() against premature import
# (before the Django app registry is ready).  When the module is
# imported during an error-handling cascade (e.g. URL-conf-load
# failure), ``User`` can otherwise remain unbound, producing an
# ``UnboundLocalError`` in ``process_request`` that masks the real
# root cause.
try:
    User = get_user_model()
except (
    ImproperlyConfigured,
    AppRegistryNotReady,
):  # pragma: no cover — only hit during cascading import failures
    User = None


class TenantScopingMiddleware:
    """
    Middleware to extract and set tenant_id from JWT token or API key.

    This runs BEFORE REST Framework authentication, so it extracts tenant_id
    directly from Authorization headers to support rate limiting middleware.

    Sets request.tenant_id and request.tenant for use in views and rate limiting.
    """

    def __init__(self, get_response):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response

    def __call__(self, request):
        """Process request and return response."""
        # Handle DRF's force_authenticate in test environments
        # force_authenticate sets _force_auth_user before authentication classes run
        # We need to set request.user here so our middleware can access it
        if not hasattr(request, "user") or not request.user or not request.user.is_authenticated:
            forced_user = getattr(request, "_force_auth_user", None)
            if forced_user is not None:
                request.user = forced_user

        # Process request; short-circuit if middleware returns HttpResponse (e.g. 403)
        response = self.process_request(request)
        if response is not None:
            return response

        # W1.20 / D2 — RLS request-path arming.  Wrap the rest of the
        # request in ONE transaction and arm the RLS GUCs
        # transaction-locally inside it: SET LOCAL survives PgBouncer
        # transaction pooling and evaporates at commit, so a reused
        # pooled connection can never leak one tenant's scope into the
        # next request.  Fail-closed on arming failure: if the GUCs
        # cannot be set, the request must not run unscoped — 503.
        from django.conf import settings

        if getattr(settings, "RLS_REQUEST_PATH_ENABLED", True):
            armed = []

            def _arm():
                self._arm_rls_gucs(request)
                armed.append(True)

            try:
                with transaction.atomic():
                    _arm()
                    return self.get_response(request)
            except (DatabaseError, InterfaceError, OperationalError):
                if not armed:
                    # The GUCs could not be set — the request must not
                    # run unscoped.  Fail closed with 503.  A DB error
                    # AFTER arming (i.e. from the view itself) re-raises
                    # untouched.
                    logger.exception(
                        "rls_arming_failed", tenant_id=getattr(request, "tenant_id", None)
                    )
                    return JsonResponse(
                        {"error": "RLS_ARMING_FAILED", "code": "SERVICE_UNAVAILABLE"},
                        status=503,
                    )
                raise

        return self.get_response(request)

    def _arm_rls_gucs(self, request):
        """Set the tenant + per-table RLS GUCs transaction-locally.

        Must run INSIDE the request's ``transaction.atomic()`` block —
        the GUCs are SET LOCAL and die with the transaction.
        """
        from django.db import connection

        from hub.apps.auth.rls_gucs import build_arm_sql

        tenant_id = getattr(request, "tenant_id", None)
        sql, params = build_arm_sql(str(tenant_id) if tenant_id else None)
        with connection.cursor() as cursor:
            cursor.execute(sql, params)

    def _extract_tenant_id_from_api_key(self, request):
        """
        Extract tenant_id from API key in Authorization header.

        This is a lightweight lookup that doesn't perform full authentication
        (no expiration checks, no last_used updates). Full authentication
        will happen later in REST Framework authentication classes.

        Returns tenant_id (UUID string) or None.
        """
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        api_key = None

        if auth_header.startswith("ApiKey "):
            api_key = auth_header.split(" ", 1)[1] if " " in auth_header else None
        else:
            # Check X-API-Key header
            api_key = request.META.get("HTTP_X_API_KEY")

        if not api_key:
            return None

        try:
            from hub.apps.auth.db_aliases import user_lookup_alias
            from hub.apps.auth.models import APIKey

            # W1.20 — the api_keys table carries an RLS policy; this
            # lookup runs BEFORE the tenant GUC exists, so it must use
            # the pre-tenant alias (BYPASSRLS admin in production,
            # the default connection everywhere else).
            key_hash = APIKey.hash_key(api_key)
            api_key_obj = (
                APIKey.objects.using(user_lookup_alias())
                .select_related("tenant", "user")
                .prefetch_related("user__user_roles__role")
                .get(key_hash=key_hash)
            )
            if api_key_obj.is_expired() or api_key_obj.is_revoked():
                return None
            tenant_id_str = str(api_key_obj.tenant.id)
            request.tenant_id = tenant_id_str
            request.tenant = api_key_obj.tenant
            request.api_key_scopes = api_key_obj.scopes
            request.api_key_obj = api_key_obj
            # Set worker_authenticated flag if the API key has an internal scope,
            # so WorkerInternalAPIPermission passes even when DRF auth classes
            # are skipped (because middleware already set request.user).
            from hub.apps.auth.scopes import (
                SCOPE_SCHEDULED_EXPORT_INTERNAL,
                SCOPE_SCHEDULED_INGESTION_INTERNAL,
            )

            internal_scopes = {
                SCOPE_SCHEDULED_INGESTION_INTERNAL,
                SCOPE_SCHEDULED_EXPORT_INTERNAL,
            }
            if internal_scopes & set(api_key_obj.scopes or []):
                request.worker_authenticated = True
            if api_key_obj.user_id and api_key_obj.user:
                user = api_key_obj.user
                if user.is_active():
                    request.user = user
        except APIKey.DoesNotExist:
            # Invalid API key - will be caught by REST Framework authentication
            return None
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            # Log but don't fail - let REST Framework authentication handle errors
            logger.debug("failed_to_extract_tenant_from_api_key", error=str(e))
            return None
        else:
            return tenant_id_str

    def _extract_tenant_id_from_jwt(self, request):
        """
        Extract tenant_id from JWT token in Authorization header.

        This is a lightweight decode that doesn't perform full validation
        (no user lookup, no token version check). Full validation
        will happen later in REST Framework authentication classes.

        Returns tenant_id (UUID string) or None.
        """
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1] if " " in auth_header else None

        # Phase 220.4: fall back to httpOnly cookie
        if not token:
            token = request.COOKIES.get("access_token")

        if not token:
            return None

        try:
            from hub.apps.auth.jwt_utils import JWTTokenGenerator

            # Lightweight decode without version check (for tenant extraction only).
            # Full validation happens in REST Framework authentication.
            payload = JWTTokenGenerator.decode_access_token(token, verify_version=False)
            if payload and "tenant_id" in payload:
                return payload.get("tenant_id")
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            # Log but don't fail - let REST Framework authentication handle errors
            logger.debug("failed_to_extract_tenant_from_jwt", error=str(e))
            return None

        return None

    def process_request(self, request):
        """
        Extract tenant_id from Authorization header or request.user.

        Priority:
        1. X-Tenant-Id header (if present): validate membership; set tenant or 403
        2. If tenant_id already set, use it
        3. Extract from API key in Authorization header (for rate limiting)
        4. Extract from JWT token in Authorization header (for rate limiting)
        5. Get from request.user (set by Django's AuthenticationMiddleware)

        This ensures tenant_id is available for rate limiting middleware
        even though REST Framework authentication hasn't run yet.
        """
        # X-Tenant-Id: validate membership and set tenant or return 403
        x_tenant_id = request.META.get("HTTP_X_TENANT_ID", "").strip()
        if x_tenant_id:
            from django.conf import settings

            if not getattr(settings, "FEATURE_TENANT_SWITCH_ENABLED", True):
                return HttpResponse(status=403)

            # W1.6 / W10.3 (round-3 re-audit): the X-Tenant-Id scoping
            # branch must also refuse impersonation-linked bearers —
            # scope-widening beyond the impersonation's intent with the
            # same audit-severance class as switch_tenant. The claim is
            # checked directly: ImpersonationMiddleware runs AFTER this
            # middleware, so the request tag is not set yet. (An ENDED
            # session's bearer fails here 403 before JWTAuthentication
            # can answer 401 IMPERSONATION_SESSION_ENDED — both deny;
            # the auth-layer 401 is the primary contract.)
            _imp_auth = request.META.get("HTTP_AUTHORIZATION", "") or ""
            if _imp_auth.lower().startswith("bearer "):
                from hub.apps.auth.jwt_utils import JWTTokenGenerator

                # P0-1 battery finding (2026-10-19): the decode was
                # unprotected — a malformed bearer + X-Tenant-Id raised
                # ValueError out of process_request instead of falling
                # through to the 401 contract (the middleware pin
                # test_x_tenant_id_with_bearer_jwt_failure went RED with
                # it). A malformed bearer carries no impersonation
                # claim; the later user-resolution path answers it.
                try:
                    _imp_payload = JWTTokenGenerator.decode_access_token(
                        _imp_auth.split(" ", 1)[1].strip(), verify_version=False
                    )
                except (ValueError, TypeError, KeyError, AttributeError):
                    _imp_payload = None
                if _imp_payload and _imp_payload.get("impersonation_session_id"):
                    return HttpResponse(status=403)

            # Phase 250.5.C.1 — UUID format validation MUST run BEFORE
            # the auth-class checks (401) and membership-class checks
            # (403). A malformed value is a structurally-invalid
            # request — the right response is 400 regardless of
            # whether credentials are present.
            #
            # Rationale for "before auth": an attacker probing without
            # credentials could otherwise distinguish "401 = malformed
            # tenant" from "401 = bad creds" by header timing, leaking
            # signal about backend behaviour. Returning 400 first
            # makes both unauthenticated cases indistinguishable.
            #
            # Rationale for "before membership": the membership check
            # at ``UserTenantMembershipService.validate_membership``
            # already swallows malformed UUIDs (catches ValueError,
            # returns False), which would surface a misleading 403
            # ("not a member") instead of the correct 400 ("malformed
            # request"). Up-front validation keeps the response
            # contract honest.
            try:
                import uuid as _uuid_for_xtid

                _uuid_for_xtid.UUID(x_tenant_id)
            except (ValueError, TypeError, AttributeError):
                return HttpResponse(
                    b'{"error":"INVALID_TENANT_ID","code":"BAD_REQUEST"}',
                    status=400,
                    content_type="application/json",
                )
            user = getattr(request, "user", None) or getattr(request, "_force_auth_user", None)
            is_anon = user is None or isinstance(user, AnonymousUser)
            # When user not in request (e.g. JWT/ApiKey before DRF auth), try to resolve
            if is_anon:
                auth_header = request.META.get("HTTP_AUTHORIZATION", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header.split(" ", 1)[1] if " " in auth_header else None
                    if token:
                        try:
                            from hub.apps.auth.db_aliases import user_lookup_alias
                            from hub.apps.auth.jwt_utils import JWTTokenGenerator

                            payload = JWTTokenGenerator.decode_access_token(
                                token, verify_version=False
                            )
                            if payload:
                                # W1.20 — the users table is RLS-enabled
                                # and no tenant GUC exists yet; resolve
                                # through the pre-tenant alias.
                                user = JWTTokenGenerator.get_user_from_token(
                                    payload, using=user_lookup_alias()
                                )
                                if user and user.is_active():
                                    request.user = user
                                    is_anon = False
                        except (ValueError, TypeError, KeyError, AttributeError):
                            pass
                elif auth_header.startswith("ApiKey "):
                    # Lightweight API key lookup to resolve user before DRF auth
                    tenant_id_from_key = self._extract_tenant_id_from_api_key(request)
                    if tenant_id_from_key:
                        user = getattr(request, "user", None)
                        if user and not isinstance(user, AnonymousUser):
                            is_anon = False
                    else:
                        # The key was not found in the DB.  Check whether
                        # it matches the HUB_WORKER_API_KEY env var — the
                        # scheduled-export / scheduled-ingestion worker
                        # authenticates with a shared env-var key, not a
                        # DB-stored API key.  WorkerAPIKeyAuthentication
                        # in internal_auth.py handles this at the DRF
                        # level, but the middleware runs first and would
                        # otherwise short-circuit with an empty 401.
                        worker_key = getattr(settings, "HUB_WORKER_API_KEY", None)
                        if worker_key:
                            api_key = (
                                auth_header.split(" ", 1)[1].strip() if " " in auth_header else None
                            )
                            # W10.3 (round-3 re-audit): the worker env
                            # key is a shared secret — constant-time
                            # comparison (the internal_auth.py contract;
                            # plain ``==`` leaks prefix information over
                            # the network).
                            if api_key and hmac.compare_digest(api_key, worker_key):
                                # Resolve tenant from X-Tenant-ID header
                                # (same contract as WorkerAPIKeyAuthentication).
                                try:
                                    from hub.apps.tenants.models import Tenant

                                    tenant = Tenant.objects.get(id=x_tenant_id)
                                    request.tenant_id = str(tenant.id)
                                    request.tenant = tenant
                                    from hub.apps.auth.scopes import (
                                        SCOPE_SCHEDULED_EXPORT_INTERNAL,
                                        SCOPE_SCHEDULED_INGESTION_INTERNAL,
                                    )

                                    request.api_key_scopes = [
                                        SCOPE_SCHEDULED_INGESTION_INTERNAL,
                                        SCOPE_SCHEDULED_EXPORT_INTERNAL,
                                    ]
                                    request.worker_authenticated = True
                                    # Find a user in this tenant for the
                                    # middleware's is_authenticated check.
                                    # W1.20 — users is RLS-enabled; use
                                    # the pre-tenant alias.
                                    from hub.apps.auth.db_aliases import user_lookup_alias

                                    user = (
                                        User.objects.using(user_lookup_alias())
                                        .filter(
                                            tenant=tenant,
                                        )
                                        .first()
                                    )
                                    if user and user.is_active():
                                        request.user = user
                                        is_anon = False
                                except (ImportError, Tenant.DoesNotExist, ValueError):
                                    # Modules not available or tenant not
                                    # found — let DRF auth produce the
                                    # proper error response.
                                    pass
                # No Authorization header — try the httpOnly access_token cookie
                # (set by login when USE_HTTPONLY_AUTH_COOKIES=True).  This runs
                # before DRF authentication, which normally handles cookie fallback.
                if is_anon:
                    cookie_token = request.COOKIES.get("access_token", "")
                    if cookie_token:
                        try:
                            from hub.apps.auth.db_aliases import user_lookup_alias
                            from hub.apps.auth.jwt_utils import JWTTokenGenerator

                            payload = JWTTokenGenerator.decode_access_token(
                                cookie_token, verify_version=False
                            )
                            if payload:
                                # W1.20 — users is RLS-enabled; resolve
                                # through the pre-tenant alias.
                                user = JWTTokenGenerator.get_user_from_token(
                                    payload, using=user_lookup_alias()
                                )
                                if user and user.is_active():
                                    request.user = user
                                    is_anon = False
                        except (ValueError, TypeError, KeyError, AttributeError):
                            pass
            is_authenticated = not is_anon and (
                getattr(user, "is_authenticated", False)
                or (hasattr(user, "id") and user.id is not None)
            )
            if not is_authenticated:
                # Return 401 (not 403) when X-Tenant-Id is present but the bearer
                # token is missing/expired/invalid. Semantics: 401 = "your
                # credentials are invalid, refresh them"; 403 = "your credentials
                # are valid but you lack permission". Returning 403 here breaks
                # the frontend's automatic refresh-on-401 → retry path, which
                # would otherwise transparently re-auth on token expiry.
                return HttpResponse(status=401)
            # Allow if user's own tenant matches, or if explicit membership exists
            user_tenant_id = str(getattr(user, "tenant_id", None) or "")
            # Platform admins have cross-tenant access (the same
            # convention as the feature-flag gates and the
            # tenant-scoped querysets) — bypass the membership
            # check for them.
            if user_tenant_id != str(x_tenant_id) and not getattr(user, "is_platform_admin", False):
                from hub.apps.auth.db_aliases import user_lookup_alias
                from hub.apps.users.services import UserTenantMembershipService

                # W1.20 — user_tenant_memberships is RLS-enabled and no
                # tenant GUC exists yet; resolve through the pre-tenant
                # alias.
                if not UserTenantMembershipService().validate_membership(
                    user, x_tenant_id, using=user_lookup_alias()
                ):
                    return HttpResponse(status=403)
            from django.core.exceptions import ValidationError

            from hub.apps.tenants.models import Tenant

            try:
                tenant = Tenant.objects.get(id=x_tenant_id)
                request.tenant_id = str(tenant.id)
                request.tenant = tenant
            except Tenant.DoesNotExist:
                return HttpResponse(status=403)
            except (ValidationError, ValueError):
                # Phase 250.5.C.1 — malformed X-Tenant-Id header
                # (non-UUID value, e.g. ``"not-a-uuid"``) MUST surface
                # as 400, NOT 500. Without this guard, Django's
                # UUIDField.to_python raises ValidationError on the
                # ORM lookup, propagating as an unhandled middleware
                # exception → 500 with a stack-trace fragment in the
                # response body (an information-disclosure risk on
                # top of the wrong status code). 403 would also be
                # incorrect because the request is structurally
                # invalid, not permission-denied. The guard catches
                # ValueError too because some Django paths raise
                # ValueError instead of ValidationError on UUID
                # coercion.
                return HttpResponse(
                    b'{"error":"INVALID_TENANT_ID","code":"BAD_REQUEST"}',
                    status=400,
                    content_type="application/json",
                )
            return None

        # If tenant_id is already set, ensure it's a string and get tenant object
        if hasattr(request, "tenant_id") and request.tenant_id:
            # Ensure tenant_id is a string (authentication might set it as UUID)
            if not isinstance(request.tenant_id, str):
                request.tenant_id = str(request.tenant_id)
            try:
                from hub.apps.tenants.models import Tenant

                # Fetch tenant object fresh from database (important for thread safety)
                if not hasattr(request, "tenant") or not request.tenant:
                    request.tenant = Tenant.objects.get(id=request.tenant_id)
            except Tenant.DoesNotExist:
                return JsonResponse({"error": "TENANT_NOT_FOUND"}, status=403)
            except (InterfaceError, OperationalError, DatabaseError):
                return JsonResponse({"error": "SERVICE_UNAVAILABLE"}, status=503)
            return None

        # Try to extract tenant_id from Authorization header (for rate limiting)
        # This runs BEFORE REST Framework authentication
        tenant_id = None

        # Try API key first
        tenant_id = self._extract_tenant_id_from_api_key(request)

        # If not found, try JWT token
        if not tenant_id:
            tenant_id = self._extract_tenant_id_from_jwt(request)

        # If found from header, set it
        if tenant_id:
            request.tenant_id = str(tenant_id)
            try:
                from hub.apps.tenants.models import Tenant

                request.tenant = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                return JsonResponse({"error": "TENANT_NOT_FOUND"}, status=403)
            except (InterfaceError, OperationalError, DatabaseError):
                return JsonResponse({"error": "SERVICE_UNAVAILABLE"}, status=503)
            return None

        # Fallback: get tenant from request.user (set by Django's AuthenticationMiddleware)
        # This is for session-based authentication and test environments (force_authenticate)
        # Note: DRF's force_authenticate may set request._force_auth_user instead of request.user
        # Check both locations for test compatibility
        user = getattr(request, "user", None)
        if user is None:
            # DRF's force_authenticate might set _force_auth_user
            user = getattr(request, "_force_auth_user", None)

        # Debug logging for test environments (only in test mode to avoid production overhead)
        import os

        if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith(
            "test"
        ) or "test" in os.environ.get("PYTEST_CURRENT_TEST", ""):
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(
                f"TenantScopingMiddleware: user={user}, "
                f"has_user={hasattr(request, 'user')}, "
                f"has_force_auth={hasattr(request, '_force_auth_user')}, "
                f"user_id={getattr(user, 'id', None) if user else None}, "
                f"user_tenant_id={getattr(user, 'tenant_id', None) if user else None}"
            )

        if user:
            # Check if user is authenticated (works with both real auth and force_authenticate)
            is_anonymous = isinstance(user, AnonymousUser)
            # In test environments, force_authenticate sets user but is_authenticated might not be evaluated
            # So we check both is_authenticated and if user has an ID
            is_authenticated = not is_anonymous and (
                getattr(user, "is_authenticated", False)
                or (hasattr(user, "id") and user.id is not None)
            )
            if is_authenticated:
                # Ensure request.user is set for consistency
                if not hasattr(request, "user") or request.user != user:
                    request.user = user
                tenant_id_set = False
                if User is None:
                    # get_user_model() failed during module import
                    # (cascading import failure — see module docstring).
                    # Fall back to the user object's tenant_id directly.
                    return None
                try:
                    # Query user from database to get fresh tenant_id (avoid cached relationships)
                    # This is important for thread safety with LiveServerTestCase.
                    # W1.20 — users is RLS-enabled; use the pre-tenant
                    # alias so the lookup works under an enforcing role
                    # (the in-memory fallback below still covers the
                    # pathological cases).
                    from hub.apps.auth.db_aliases import user_lookup_alias

                    db_user = (
                        User.objects.using(user_lookup_alias()).only("tenant_id").get(id=user.id)
                    )
                    if db_user.tenant_id:
                        request.tenant_id = str(db_user.tenant_id)
                        tenant_id_set = True
                        # Also set tenant object if not already set
                        if not hasattr(request, "tenant") or not request.tenant:
                            from hub.apps.tenants.models import Tenant

                            try:
                                request.tenant = Tenant.objects.get(id=db_user.tenant_id)
                            except Tenant.DoesNotExist:
                                request.tenant = None
                except User.DoesNotExist:
                    # User doesn't exist in DB - try fallback
                    pass
                except (InterfaceError, OperationalError, DatabaseError):
                    # DB connectivity issue — try fallback from user object
                    pass

                # Fallback: if DB query didn't set tenant_id, try user object directly
                # This is important for test environments where transaction isolation might prevent DB queries
                if not tenant_id_set:
                    if hasattr(user, "tenant_id") and user.tenant_id:
                        request.tenant_id = str(user.tenant_id)
                        tenant_id_set = True
                        # Try to get tenant object
                        if not hasattr(request, "tenant") or not request.tenant:
                            from hub.apps.tenants.models import Tenant

                            try:
                                request.tenant = Tenant.objects.get(id=user.tenant_id)
                            except Tenant.DoesNotExist:
                                request.tenant = None
                    elif hasattr(user, "tenant") and user.tenant:
                        request.tenant_id = str(user.tenant.id)
                        tenant_id_set = True
                        request.tenant = user.tenant
            # User not authenticated - try legacy fallback for edge cases
            elif hasattr(user, "tenant") and user.tenant:
                request.tenant_id = str(user.tenant.id)
                request.tenant = user.tenant
            elif hasattr(user, "tenant_id") and user.tenant_id:
                request.tenant_id = str(user.tenant_id)
                # Try to get tenant object
                if not hasattr(request, "tenant") or not request.tenant:
                    from hub.apps.tenants.models import Tenant

                    try:
                        request.tenant = Tenant.objects.get(id=user.tenant_id)
                    except Tenant.DoesNotExist:
                        request.tenant = None

        return None
