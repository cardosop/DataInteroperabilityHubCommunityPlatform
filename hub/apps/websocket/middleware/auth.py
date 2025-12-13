"""
WebSocket Authentication Middleware

Authenticates WebSocket connections using JWT tokens or API keys.
"""

import json
from typing import Optional

import structlog
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections

from hub.apps.auth.models import APIKey

User = get_user_model()
logger = structlog.get_logger(__name__)


def _get_user_from_token_sync(token: str) -> Optional[User]:
    """
    Synchronous helper to get user from JWT token.

    This is called from within database_sync_to_async which handles
    database connection management automatically. However, in pytest-django
    async tests, the connection might be closed in the thread that
    database_sync_to_async uses, so we need to ensure it's opened.
    """
    # #region agent log
    import json
    import threading
    import time

    try:
        with open("/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A",
                        "location": "auth.py:_get_user_from_token_sync:entry",
                        "message": "Function entry",
                        "data": {
                            "thread_id": threading.get_ident(),
                            "thread_name": threading.current_thread().name,
                            "token_length": len(token) if token else 0,
                        },
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion
    try:
        from django.db import connections

        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        # #region agent log
        try:
            conn = connections["default"]
            conn_state = {
                "has_connection": conn.connection is not None,
                "connection_closed": (
                    hasattr(conn.connection, "closed") and conn.connection.closed
                    if conn.connection
                    else None
                ),
                "thread_id": threading.get_ident(),
            }
            with open("/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A",
                            "location": "auth.py:_get_user_from_token_sync:before_decode",
                            "message": "Connection state before decode",
                            "data": conn_state,
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

        payload = JWTTokenGenerator.decode_access_token(token)
        if not payload:
            return None

        # Get user_id from payload
        user_id = payload.get("sub")
        if not user_id:
            return None

        # #region agent log
        try:
            with open("/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "auth.py:_get_user_from_token_sync:before_query",
                            "message": "Before query attempt",
                            "data": {"user_id": user_id, "thread_id": threading.get_ident()},
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

        # Query user with retry on connection errors
        # The root cause: In pytest-django async tests, the database connection
        # created in setUp (sync context) may be closed when database_sync_to_async
        # executes. However, database_sync_to_async properly handles test database
        # transactions, so the user created in setUp should be visible.
        # Solution: Use close_old_connections() before querying to ensure we get
        # a fresh connection, and retry on connection errors.
        max_retries = 2
        for attempt in range(max_retries):
            # #region agent log
            try:
                with open("/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a") as f:
                    f.write(
                        json.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "C",
                                "location": "auth.py:_get_user_from_token_sync:before_query_attempt",
                                "message": "Before query attempt",
                                "data": {
                                    "attempt": attempt,
                                    "thread_id": threading.get_ident(),
                                },
                                "timestamp": int(time.time() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
            try:
                # Close old connections before querying to ensure we get a fresh connection
                # This is critical for pytest-django async tests where connections may be stale
                from django.db import close_old_connections

                if attempt > 0:
                    close_old_connections()

                # Ensure connection is open by accessing it directly
                # database_sync_to_async ensures proper test database transaction handling,
                # so the user created in setUp should be visible here
                connection = connections["default"]
                try:
                    # Try to ensure connection is open
                    # This may fail, but that's OK - Django will open it on query
                    connection.ensure_connection()
                except Exception:
                    # If ensure_connection fails, close old connections and try again
                    close_old_connections()
                    try:
                        connection.ensure_connection()
                    except Exception:
                        # If it still fails, that's OK - Django will open it on query
                        pass

                # #region agent log
                try:
                    with open(
                        "/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a"
                    ) as f:
                        f.write(
                            json.dumps(
                                {
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "C",
                                    "location": "auth.py:_get_user_from_token_sync:before_actual_query",
                                    "message": "About to execute query",
                                    "data": {
                                        "user_id": user_id,
                                        "attempt": attempt,
                                        "thread_id": threading.get_ident(),
                                    },
                                    "timestamp": int(time.time() * 1000),
                                }
                            )
                            + "\n"
                        )
                except Exception:
                    pass
                # #endregion
                # Query user - Django will automatically open a connection if needed
                # Even if ensure_connection() failed, Django's ORM will open a connection
                # when we perform the query
                user = User.objects.select_related("tenant").get(id=user_id)
                # #region agent log
                try:
                    with open(
                        "/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a"
                    ) as f:
                        f.write(
                            json.dumps(
                                {
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "D",
                                    "location": "auth.py:_get_user_from_token_sync:query_success",
                                    "message": "Query succeeded",
                                    "data": {
                                        "user_id": str(user.id) if user else None,
                                        "attempt": attempt,
                                        "thread_id": threading.get_ident(),
                                    },
                                    "timestamp": int(time.time() * 1000),
                                }
                            )
                            + "\n"
                        )
                except Exception:
                    pass
                # #endregion
                # Validate token version
                token_valid = JWTTokenGenerator.validate_token_version(payload, user)
                # #region agent log
                try:
                    with open(
                        "/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a"
                    ) as f:
                        f.write(
                            json.dumps(
                                {
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "D",
                                    "location": "auth.py:_get_user_from_token_sync:token_validation",
                                    "message": "Token validation result",
                                    "data": {
                                        "token_valid": token_valid,
                                        "user_id": str(user.id) if user else None,
                                        "attempt": attempt,
                                        "thread_id": threading.get_ident(),
                                    },
                                    "timestamp": int(time.time() * 1000),
                                }
                            )
                            + "\n"
                        )
                except Exception:
                    pass
                # #endregion
                if token_valid:
                    return user
                # If token version validation fails, return None
                return None
            except User.DoesNotExist:
                return None  # User doesn't exist, no point retrying
            except Exception as db_error:
                # #region agent log
                try:
                    error_str = str(db_error).lower()
                    is_connection_error = (
                        "connection" in error_str
                        or "closed" in error_str
                        or "operationalerror" in error_str
                    )
                    with open(
                        "/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a"
                    ) as f:
                        f.write(
                            json.dumps(
                                {
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "E",
                                    "location": "auth.py:_get_user_from_token_sync:query_error",
                                    "message": "Query error",
                                    "data": {
                                        "error_type": type(db_error).__name__,
                                        "error_message": str(db_error),
                                        "is_connection_error": is_connection_error,
                                        "attempt": attempt,
                                        "thread_id": threading.get_ident(),
                                        "max_retries": max_retries,
                                    },
                                    "timestamp": int(time.time() * 1000),
                                }
                            )
                            + "\n"
                        )
                except Exception:
                    pass
                # #endregion
                error_str = str(db_error).lower()
                is_connection_error = (
                    "connection" in error_str
                    or "closed" in error_str
                    or "operationalerror" in error_str
                )
                if is_connection_error and attempt < max_retries - 1:
                    # Connection error, close old connections and retry
                    # This gives Django a chance to open a fresh connection on retry
                    from django.db import close_old_connections

                    close_old_connections()
                    continue
                else:
                    # Other error or last attempt, log and return None
                    if is_connection_error:
                        logger.warning("websocket_token_auth_db_error", error=str(db_error))
                    return None
    except Exception as e:
        # #region agent log
        try:
            with open("/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A",
                            "location": "auth.py:_get_user_from_token_sync:outer_exception",
                            "message": "Outer exception",
                            "data": {
                                "error_type": type(e).__name__,
                                "error_message": str(e),
                                "thread_id": threading.get_ident(),
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        # Only log non-database errors here (database errors are logged above)
        if "connection" not in str(e).lower():
            logger.warning("websocket_token_auth_failed", error=str(e))
    return None


from channels.db import database_sync_to_async


@database_sync_to_async
def get_user_from_token(token: str) -> Optional[User]:
    """
    Get user from JWT token.

    Args:
        token: JWT token string

    Returns:
        User instance or None
    """
    return _get_user_from_token_sync(token)


def _get_user_from_api_key_sync(api_key: str) -> Optional[User]:
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

        # Query API key - Django will open a fresh connection automatically
        api_key_obj = APIKey.objects.select_related("user__tenant").get(key=api_key)
        if api_key_obj.is_active:
            return api_key_obj.user
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
def get_user_from_api_key(api_key: str) -> Optional[User]:
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
    - JWT token authentication (via query parameter or subprotocol)
    - API key authentication (via query parameter)
    """

    async def __call__(self, scope, receive, send):
        """Process WebSocket connection and authenticate user."""
        # Extract authentication from query string or subprotocol
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = {}
        for param in query_string.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                query_params[key] = value

        # Try JWT token authentication
        token = query_params.get("token") or query_params.get("access_token")
        user = None

        if token:
            user = await get_user_from_token(token)

        # Try API key authentication if JWT failed
        if not user:
            api_key = query_params.get("api_key") or query_params.get("X-API-Key")
            if api_key:
                user = await get_user_from_api_key(api_key)

        # Set user in scope
        if user:
            scope["user"] = user
            scope["tenant"] = user.tenant if hasattr(user, "tenant") else None
        else:
            scope["user"] = AnonymousUser()
            scope["tenant"] = None

        return await super().__call__(scope, receive, send)
