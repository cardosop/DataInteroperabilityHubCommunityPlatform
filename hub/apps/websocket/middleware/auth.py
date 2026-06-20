"""
WebSocket Authentication Middleware

Authenticates WebSocket connections using JWT tokens or API keys.
"""

import structlog
from asgiref.sync import sync_to_async

# Optional channels imports
try:
    from channels.db import database_sync_to_async
    from channels.middleware import BaseMiddleware

    CHANNELS_AVAILABLE = True
except ImportError:
    # Fallback if channels not available
    database_sync_to_async = sync_to_async

    # Create a stub BaseMiddleware
    class BaseMiddleware:
        """Stub for BaseMiddleware when channels is not available."""

    CHANNELS_AVAILABLE = False

from django.contrib.auth import get_user_model

from hub.apps.auth.models import APIKey

User = get_user_model()
logger = structlog.get_logger(__name__)


def _get_user_from_token_sync(token: str) -> User | None:
    """
    Synchronous helper to get user from JWT token.

    This is called from within database_sync_to_async which handles
    database connection management automatically. However, in pytest-django
    async tests, the connection might be closed in the thread that
    database_sync_to_async uses, so we need to ensure it's opened.
    """
    try:
        from django.db import connections

        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        payload = JWTTokenGenerator.decode_access_token(token)
        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        # Query user with retry on connection errors (pytest-django async: connection may be stale)
        max_retries = 2
        for attempt in range(max_retries):
            try:
                from django.db import close_old_connections

                if attempt > 0:
                    close_old_connections()

                connection = connections["default"]
                try:
                    connection.ensure_connection()
                except Exception as conn_err:
                    close_old_connections()
                    try:
                        connection.ensure_connection()
                    except Exception as retry_err:
                        logger.debug(
                            "websocket_auth_ensure_connection_failed",
                            extra={
                                "error_type": type(retry_err).__name__,
                                "error": str(retry_err),
                                "attempt": attempt,
                            },
                        )
                    else:
                        logger.debug(
                            "websocket_auth_ensure_connection_retry_ok",
                            extra={"error_type": type(conn_err).__name__, "error": str(conn_err)},
                        )
                    # Django will open connection on query if needed

                user = User.objects.select_related("tenant").get(id=user_id)
                token_valid = JWTTokenGenerator.validate_token_version(payload, user)
                if token_valid:
                    return user
                return None
            except User.DoesNotExist:
                return None
            except Exception as db_error:
                error_str = str(db_error).lower()
                is_connection_error = (
                    "connection" in error_str
                    or "closed" in error_str
                    or "operationalerror" in error_str
                )
                if is_connection_error and attempt < max_retries - 1:
                    close_old_connections()
                    continue
                if is_connection_error:
                    logger.warning("websocket_token_auth_db_error", error=str(db_error))
                return None
    except Exception as e:
        if "connection" not in str(e).lower():
            logger.warning(
                "websocket_token_auth_failed",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
    return None


# database_sync_to_async is already imported at the top of the file with optional handling


@database_sync_to_async
def get_user_from_token(token: str) -> User | None:
    """
    Get user from JWT token.

    Args:
        token: JWT token string

    Returns:
        User instance or None
    """
    return _get_user_from_token_sync(token)


def _get_user_from_api_key_sync(api_key: str) -> User | None:
    """
    Synchronous helper to get user from API key.

    This is called from within database_sync_to_async which handles
    database connection management automatically.
    """
    try:
        from django.db import close_old_connections

        # Close old connections to ensure we get a fresh connection
        # This is important for pytest-django async tests
        close_old_connections()

        # Hash the provided API key before lookup (API keys are stored hashed)
        key_hash = APIKey.hash_key(api_key)

        # Query API key - Django will open a fresh connection automatically
        api_key_obj = APIKey.objects.select_related("user__tenant").get(key_hash=key_hash)

        # Check if API key is expired
        if api_key_obj.is_expired():
            logger.warning("websocket_api_key_expired", api_key_id=str(api_key_obj.id))
            return None

        # Update last used timestamp
        api_key_obj.update_last_used()

        # Return user if API key has a user (user-scoped key)
        if api_key_obj.user:
            return api_key_obj.user

        # If no user, return None (tenant-scoped keys don't have users)
        logger.debug("websocket_api_key_no_user", api_key_id=str(api_key_obj.id))
        return None
    except APIKey.DoesNotExist:
        logger.warning("websocket_api_key_not_found")
    except Exception as e:
        # Log database errors separately from other errors
        error_str = str(e).lower()
        if "connection" in error_str or "closed" in error_str:
            logger.warning("websocket_api_key_auth_db_error", error=str(e))
        else:
            logger.warning("websocket_api_key_auth_failed", error=str(e))
    return None


@database_sync_to_async
def get_user_from_api_key(api_key: str) -> User | None:
    """
    Get user from API key.

    Args:
        api_key: API key string

    Returns:
        User instance or None
    """
    return _get_user_from_api_key_sync(api_key)


class WebSocketAuthMiddleware(BaseMiddleware):
    """
    WebSocket authentication middleware.

    Supports:
    - JWT token authentication (via query parameter, Authorization header, or subprotocol)
    - API key authentication (via query parameter or X-API-Key header)

    Rejects connections if authentication fails (sends close message with code 4001).
    """

    def _extract_token_from_headers(self, headers: list) -> str | None:
        """
        Extract JWT token from Authorization header.

        Args:
            headers: List of (header_name, header_value) tuples

        Returns:
            Token string or None
        """
        for header_name, header_value in headers:
            if header_name.lower() == b"authorization":
                # Handle both bytes and string headers
                if isinstance(header_value, bytes):
                    header_value = header_value.decode("utf-8")

                # Extract Bearer token
                if header_value.startswith("Bearer "):
                    return header_value[7:]  # Remove "Bearer " prefix
                elif header_value.startswith("bearer "):
                    return header_value[7:]  # Case-insensitive
        return None

    def _extract_api_key_from_headers(self, headers: list) -> str | None:
        """
        Extract API key from X-API-Key header.

        Args:
            headers: List of (header_name, header_value) tuples

        Returns:
            API key string or None
        """
        for header_name, header_value in headers:
            if header_name.lower() == b"x-api-key":
                # Handle both bytes and string headers
                if isinstance(header_value, bytes):
                    return header_value.decode("utf-8")
                return header_value
        return None

    def _parse_query_string(self, query_string: bytes) -> dict:
        """
        Parse query string into dictionary.

        Args:
            query_string: Query string bytes

        Returns:
            Dictionary of query parameters
        """
        query_params = {}
        if query_string:
            query_str = query_string.decode("utf-8")
            for param in query_str.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    # URL decode the value
                    import urllib.parse

                    query_params[key] = urllib.parse.unquote(value)
        return query_params

    async def __call__(self, scope, receive, send):
        """
        Process WebSocket connection and authenticate user.

        Supports three authentication paths:
        1. Message-based auth (preferred): No credentials at connect time; the
           consumer handles an ``authenticate`` message after the connection opens.
        2. Header-based auth: JWT via ``Authorization: Bearer`` or API key via
           ``X-API-Key`` header — authenticated at handshake.
        3. Query-param auth (deprecated): ``?token=`` / ``?access_token=`` / ``?api_key=``
           — still works but logs a deprecation warning. Will be removed in a
           future release. Can be force-disabled with the Django setting
           ``WEBSOCKET_QUERY_PARAM_AUTH_DISABLED = True``.
        """
        # Only process WebSocket connections
        if scope.get("type") != "websocket":
            return await super().__call__(scope, receive, send)

        # Extract authentication from query string and headers
        query_string = scope.get("query_string", b"")
        headers = scope.get("headers", [])

        query_params = self._parse_query_string(query_string)

        user = None
        auth_method = None

        # Check if query-param auth has been disabled (post-deprecation)
        from django.conf import settings

        query_param_auth_disabled = getattr(settings, "WEBSOCKET_QUERY_PARAM_AUTH_DISABLED", False)

        # --- Header-based auth (not deprecated) ---
        header_token = self._extract_token_from_headers(headers)
        if header_token:
            user = await get_user_from_token(header_token)
            if user:
                auth_method = "jwt_token"

        header_api_key = self._extract_api_key_from_headers(headers)
        if not user and header_api_key:
            user = await get_user_from_api_key(header_api_key)
            if user:
                auth_method = "api_key"

        # --- Query-param auth (deprecated fallback) ---
        if not user:
            query_token = query_params.get("token") or query_params.get("access_token")
            query_api_key = query_params.get("api_key") or query_params.get("X-API-Key")

            if query_token or query_api_key:
                if query_param_auth_disabled:
                    # Post-deprecation: reject query-param auth entirely
                    logger.warning(
                        "websocket_auth_query_param_rejected",
                        path=scope.get("path"),
                        message="Query-parameter authentication has been disabled. "
                        "Use message-based authentication.",
                    )
                    await send(
                        {
                            "type": "websocket.close",
                            "code": 4001,
                            "reason": "Query-parameter authentication is no longer supported",
                        }
                    )
                    return

                # Deprecated but still allowed — authenticate and warn
                if query_token:
                    user = await get_user_from_token(query_token)
                    if user:
                        auth_method = "jwt_token_query_param_deprecated"
                if not user and query_api_key:
                    user = await get_user_from_api_key(query_api_key)
                    if user:
                        auth_method = "api_key_query_param_deprecated"

                if user:
                    logger.warning(
                        "websocket_auth_query_param_deprecated",
                        path=scope.get("path"),
                        message="Token authentication via query parameter is deprecated. "
                        "Use message-based authentication instead.",
                    )

        # Set user and tenant in scope if authenticated
        if user:
            scope["user"] = user
            scope["tenant"] = user.tenant if hasattr(user, "tenant") else None
            scope["auth_method"] = auth_method

            logger.debug(
                "websocket_authenticated",
                user_id=str(user.id),
                tenant_id=str(scope["tenant"].id) if scope["tenant"] else None,
                auth_method=auth_method,
            )

            return await super().__call__(scope, receive, send)

        # --- No credentials provided: pass through for message-based auth ---
        # The consumer will handle the ``authenticate`` message and enforce
        # a 10-second timeout for unauthenticated connections.
        scope["user"] = None
        scope["tenant"] = None
        scope["auth_method"] = "pending_message_auth"

        logger.debug(
            "websocket_pending_message_auth",
            path=scope.get("path"),
            message="No credentials at handshake; awaiting message-based auth",
        )

        return await super().__call__(scope, receive, send)
