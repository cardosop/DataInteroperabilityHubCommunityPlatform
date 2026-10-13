"""
W1.6 (R2-S12) — DRF authentication on plain-Django GraphQL views.

Both GraphQL surfaces (strawberry ``/graphql`` + graphene
``/graphql-graphene``) are plain Django views, not DRF ``APIView``s —
so ``APIView.initial()`` never runs, no DRF authenticator ever fires,
and ``request.user`` comes from ``TenantScopingMiddleware``'s
LIGHTWEIGHT JWT decode (signature + expiry, ``verify_version=False``).
A token_version-revoked JWT therefore kept authenticating on GraphQL
after it 401'd on every REST surface, and an invalid token silently
fell back to anonymous (a resolver error instead of a 401).

``GraphQLDRFAuthMixin`` closes that seam: the view calls
``authenticate_graphql_request()`` at the top of ``dispatch``, which
runs the DRF authentication stack (JWTAuthentication +
APIKeyAuthentication — the REST defaults, overridable per view):

* an authenticator returning ``(user, auth)`` sets ``request.user`` /
  ``request.auth`` and the request proceeds;
* ``AuthenticationFailed`` (bad signature, expired, token-version
  mismatch, ended impersonation session, ...) → HTTP 401 with a
  GraphQL-shaped ``errors`` envelope + ``WWW-Authenticate`` header —
  the response code is the DRF exception's ``code`` (uppercased), so
  the same ``TOKEN_INVALIDATED`` the REST envelope carries;
* ``NotAuthenticated`` → the next authenticator runs;
* no authenticator claims the request → anonymous passthrough (the
  pre-existing contract: resolvers raise their own
  "Authentication required" errors with HTTP 200, per the GraphQL
  spec);
* DRF's ``force_authenticate`` test hook (``_force_auth_user``) skips
  the stack entirely, exactly like ``APIView``.

The 401 is emitted BEFORE the query executes — a rejected token never
reaches a resolver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import JsonResponse
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
from rest_framework.settings import api_settings

if TYPE_CHECKING:  # pragma: no cover — typing only
    from django.http import HttpRequest, HttpResponse


class GraphQLDRFAuthMixin:
    """Run the DRF authentication stack in a plain-Django GraphQL view.

    Subclasses call ``authenticate_graphql_request`` at the top of
    ``dispatch``. Returns a 401 ``JsonResponse`` when authentication
    fails, ``None`` otherwise.
    """

    #: Per-view override; defaults to settings.REST_FRAMEWORK
    #: DEFAULT_AUTHENTICATION_CLASSES (JWTAuthentication +
    #: APIKeyAuthentication — the same classes the REST paths run).
    authentication_classes: tuple | None = None

    @classmethod
    def _graphql_authenticators(cls):
        # ``api_settings`` resolves the dotted-path strings in
        # REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] into classes
        # (the same import DRF's APIView performs).
        classes = cls.authentication_classes or api_settings.DEFAULT_AUTHENTICATION_CLASSES
        return [auth_class() for auth_class in classes]

    @staticmethod
    def _graphql_auth_error_response(
        exc: AuthenticationFailed, request
    ) -> JsonResponse:
        """The 401 envelope: GraphQL ``errors`` shape, never token
        material — the classified DRF code only."""
        code = str(getattr(exc, "code", "") or "UNAUTHENTICATED").upper()
        detail = getattr(exc, "detail", None)
        message = str(detail) if detail else "Authentication failed"
        body = {
            "errors": [
                {
                    "message": message,
                    "extensions": {"code": code},
                }
            ]
        }
        response = JsonResponse(body, status=401)
        response["WWW-Authenticate"] = "Bearer"
        return response

    def authenticate_graphql_request(
        self, request: "HttpRequest"
    ) -> "HttpResponse | None":
        """Run DRF authentication on the request; 401 on failure.

        Mirrors ``APIView.perform_authentication`` for a plain view:
        the first authenticator that claims the request wins;
        ``AuthenticationFailed`` short-circuits to the 401 response;
        nothing claiming it leaves the request anonymous.
        """
        # DRF's force_authenticate contract: when a test (or caller)
        # forces a user, the authentication stack is skipped — the
        # existing GraphQL views rely on this hook heavily.
        if getattr(request, "_force_auth_user", None) is not None:
            return None

        for authenticator in self._graphql_authenticators():
            try:
                user_auth_tuple = authenticator.authenticate(request)
            except AuthenticationFailed as exc:
                return self._graphql_auth_error_response(exc, request)
            except NotAuthenticated:
                continue
            if user_auth_tuple is None:
                continue
            user, auth = user_auth_tuple
            request.user = user
            request.auth = auth
            return None
        return None
