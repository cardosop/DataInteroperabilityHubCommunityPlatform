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
    
    This is called from within database_sync_to_async to ensure proper database connection handling.
    """
    try:
        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        payload = JWTTokenGenerator.decode_access_token(token)
        if payload:
            # Get user_id from payload
            user_id = payload.get('sub')
            if not user_id:
                return None
            
            # Query user directly - database_sync_to_async should handle connection management
            # If connection is closed, it will be reopened automatically
            try:
                user = User.objects.select_related("tenant").get(id=user_id)
                # Validate token version
                if JWTTokenGenerator.validate_token_version(payload, user):
                    return user
            except User.DoesNotExist:
                pass
            except Exception as db_error:
                # If database error occurs, log and return None
                # This handles cases where connection is closed
                logger.warning("websocket_token_auth_db_error", error=str(db_error))
                return None
    except Exception as e:
        # Only log non-database errors here (database errors are logged above)
        if "connection" not in str(e).lower():
            logger.warning("websocket_token_auth_failed", error=str(e))
    return None


@database_sync_to_async
def get_user_from_token(token: str) -> Optional[User]:
    """
    Get user from JWT token.

    Args:
        token: JWT token string

    Returns:
        User instance or None
    """
    # Close old connections to ensure fresh connection
    close_old_connections()
    return _get_user_from_token_sync(token)


def _get_user_from_api_key_sync(api_key: str) -> Optional[User]:
    """
    Synchronous helper to get user from API key.
    
    This is called from within database_sync_to_async to ensure proper database connection handling.
    """
    try:
        # Query API key directly - database_sync_to_async should handle connection management
        # If connection is closed, it will be reopened automatically
        api_key_obj = APIKey.objects.select_related("user__tenant").get(key=api_key)
        if api_key_obj.is_active:
            return api_key_obj.user
    except APIKey.DoesNotExist:
        logger.warning("websocket_api_key_not_found")
    except Exception as e:
        # Log database errors separately from other errors
        if "connection" in str(e).lower() or "closed" in str(e).lower():
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
    # Close old connections to ensure fresh connection
    close_old_connections()
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

