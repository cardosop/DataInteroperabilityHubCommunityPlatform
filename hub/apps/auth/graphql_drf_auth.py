"""DRF authentication on the GraphQL views — the shared seam.

W1.6 (R2-S12) + W10.3 F1b: the GraphQL views are plain Django views, so
NO DRF authentication class ever ran on them.  The strawberry view got
the fix in the round-3 re-audit; the graphene view kept the gap (found
RED by the P0-1 compat battery, 2026-10-18: revoked/expired/deleted-user
tokens returned 200-with-errors instead of the pinned 401 shape).

This module is the ONE implementation for both GraphQL stacks — a
consumer calls :func:`authenticate_graphql_request` at the top of its
``dispatch`` and returns the 401 response when one is produced:

* the DRF default authentication classes
  (``JWTAuthentication`` + ``APIKeyAuthentication``) run first;
* ``AuthenticationFailed`` maps to the pinned GraphQL error shape
  (``errors[0].extensions.code`` from the authenticator's code — e.g.
  ``TOKEN_INVALIDATED`` — plus the authenticator's
  ``WWW-Authenticate`` header);
* returns ``None`` when the request is anonymous — the resolver-level
  anonymous contract (200 + errors) is unchanged;
* the resolved user is copied onto the plain Django request
  (``request.user``), which is what the resolvers read.
"""

from __future__ import annotations

from django.http import JsonResponse
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request as DRFRequest
from rest_framework.settings import api_settings


def authenticate_graphql_request(request):
    """Run the DRF default authenticators on a GraphQL request.

    Returns ``None`` when the request is anonymous (resolver-level
    UNAUTHENTICATED contract unchanged) or authenticated, or the 401
    ``JsonResponse`` when an authenticator failed.
    """
    authenticators = [auth_class() for auth_class in api_settings.DEFAULT_AUTHENTICATION_CLASSES]
    drf_request = DRFRequest(request)
    failed_authenticator = None
    auth_error = None
    for authenticator in authenticators:
        try:
            user_auth_tuple = authenticator.authenticate(drf_request)
        except AuthenticationFailed as exc:
            failed_authenticator = authenticator
            auth_error = exc
            break
        if user_auth_tuple is not None:
            drf_request.user, drf_request.auth = user_auth_tuple
            # Copy the resolved user onto the plain Django request —
            # the resolvers read request.user.
            request.user = drf_request.user
            break

    if auth_error is None:
        return None

    code = getattr(auth_error, "code", None) or "UNAUTHENTICATED"
    message = str(auth_error.detail) if hasattr(auth_error, "detail") else "Authentication failed"
    request_id = getattr(request, "id", None)
    response = JsonResponse(
        {
            "errors": [
                {
                    "message": message,
                    "extensions": {
                        "code": code,
                        "request_id": request_id,
                        "category": "authentication",
                    },
                }
            ]
        },
        status=401,
    )
    if failed_authenticator is not None:
        response["WWW-Authenticate"] = failed_authenticator.authenticate_header(request)
    return response
