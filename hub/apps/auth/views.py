"""
Authentication Views

REST API views for authentication (login, logout, password reset, etc.).
"""

import uuid
from datetime import timedelta

import structlog
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.audit.utils import log_auth_operation
from hub.apps.core.events.publisher import publish_event
from hub.apps.notifications.models import EmailType
from hub.apps.notifications.tasks import send_email_async
from hub.apps.users.models import User, UserStatus

from .jwt_utils import JWTTokenGenerator
from .models import APIKey, RefreshToken
from .serializers import (
    APIKeyCreateSerializer,
    APIKeyResponseSerializer,
    APIKeySerializer,
    CurrentUserSerializer,
    InvitationAcceptanceSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshTokenResponseSerializer,
    RefreshTokenSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    TokenResponseSerializer,
)


@extend_schema(
    request=LoginSerializer,
    responses={
        200: TokenResponseSerializer,
        400: OpenApiResponse(description="Invalid credentials"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def login(request):
    """
    User login endpoint.

    POST /auth/login
    Body: {"email": "user@example.com", "password": "password"}

    Returns access token and refresh token.
    """
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]

    # Authenticate user
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        raise ValidationError({"email": "Invalid email or password"})

    # Check password
    if not user.check_password(password):
        raise ValidationError({"email": "Invalid email or password"})

    # Check if user is active
    if not user.is_active():
        raise ValidationError({"email": "User account is not active"})

    # Generate access token
    access_token = JWTTokenGenerator.generate_access_token(user)

    # Generate refresh token
    refresh_token_str = RefreshToken.generate_token()
    refresh_token_hash = RefreshToken.hash_token(refresh_token_str)

    expires_at = timezone.now() + timedelta(seconds=settings.JWT_REFRESH_TOKEN_EXPIRY)

    refresh_token_obj = RefreshToken.objects.create(
        user=user, token_hash=refresh_token_hash, expires_at=expires_at
    )

    # Log audit event
    log_auth_operation(action="LOGIN", user=user, details={"method": "password"}, request=request)

    # Warm cache for tenant on login (async to avoid blocking login response)
    if user.tenant_id:
        try:
            import threading

            from hub.apps.core.caching.warming import warm_tenant_cache

            # Warm cache in background thread to avoid blocking login
            def warm_cache_async():
                try:
                    tenant_id = str(user.tenant_id)
                    warm_tenant_cache(tenant_id)
                except Exception as e:
                    # Log error but don't fail login
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to warm cache on login: {e}", exc_info=True)

            # Start background thread for cache warming
            thread = threading.Thread(target=warm_cache_async, daemon=True)
            thread.start()
        except Exception as e:
            # Log error but don't fail login
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to start cache warming on login: {e}", exc_info=True)

    return Response(
        {
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "token_type": "Bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRY,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=RefreshTokenSerializer,
    responses={
        200: TokenResponseSerializer,
        400: OpenApiResponse(description="Invalid refresh token"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def refresh_token(request):
    """
    Token refresh endpoint.

    POST /auth/refresh
    Body: {"refresh_token": "token_string"}

    Returns new access token.
    """
    serializer = RefreshTokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    refresh_token_str = serializer.validated_data["refresh_token"]
    refresh_token_hash = RefreshToken.hash_token(refresh_token_str)

    # Look up refresh token
    try:
        refresh_token_obj = RefreshToken.objects.get(token_hash=refresh_token_hash)
    except RefreshToken.DoesNotExist:
        raise ValidationError({"refresh_token": "Invalid refresh token"})

    # Check if valid
    if not refresh_token_obj.is_valid():
        raise ValidationError({"refresh_token": "Refresh token is expired or revoked"})

    user = refresh_token_obj.user

    # Check if user is active
    if not user.is_active():
        raise ValidationError({"refresh_token": "User account is not active"})

    # Generate new access token
    access_token = JWTTokenGenerator.generate_access_token(user)

    # Log audit event
    log_auth_operation(action="TOKEN_REFRESHED", user=user, details={}, request=request)

    return Response(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRY,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=inline_serializer(
        name="TokenRefreshRequest", fields={"refresh_token": serializers.CharField(required=True)}
    ),
    responses={200: OpenApiResponse(description="Logged out successfully")},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    """
    User logout endpoint.

    POST /auth/logout
    Body: {"refresh_token": "token_string"} (required)

    Revokes the given refresh token. Invalid/missing token returns 400; unknown token returns 200 (idempotent).
    """
    # Require refresh_token in body
    refresh_token_str = request.data.get("refresh_token") if request.data else None
    if not refresh_token_str or not str(refresh_token_str).strip():
        return Response(
            {"error": "Refresh token is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    revoked_count = 0
    refresh_token_hash = RefreshToken.hash_token(refresh_token_str)
    refresh_token_obj = RefreshToken.objects.filter(
        token_hash=refresh_token_hash, user_id=request.user.id
    ).first()

    if refresh_token_obj:
        if not refresh_token_obj.revoked_at:
            refresh_token_obj.revoked_at = timezone.now()
            refresh_token_obj.save(update_fields=["revoked_at", "updated_at"])
        revoked_count = 1
    # else: invalid/unknown token → 200 with revoked_count=0 (idempotent)

    # Log audit event
    log_auth_operation(
        action="LOGOUT",
        user=request.user,
        details={"revoked_tokens": revoked_count},
        request=request,
    )

    return Response(
        {"message": "Logged out successfully", "revoked_sessions": revoked_count},
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=PasswordResetRequestSerializer,
    responses={200: OpenApiResponse(description="Password reset email sent")},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def password_reset_request(request):
    """
    Password reset request endpoint.

    POST /auth/password-reset
    Body: {"email": "user@example.com"}

    Generates password reset token and sends email.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Don't reveal if user exists
        return Response(
            {"message": "If the email exists, a password reset link has been sent."},
            status=status.HTTP_200_OK,
        )

    # Generate password reset token
    user.password_reset_token = uuid.uuid4()
    user.password_reset_token_expires_at = timezone.now() + timedelta(hours=1)
    user.save(update_fields=["password_reset_token", "password_reset_token_expires_at"])

    # Send password reset email
    from hub.apps.notifications.tasks import send_password_reset_email

    send_password_reset_email.delay(str(user.id))

    # Log audit event
    log_auth_operation(action="PASSWORD_RESET_REQUESTED", user=user, details={}, request=request)

    return Response(
        {"message": "If the email exists, a password reset link has been sent."},
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=PasswordResetConfirmSerializer,
    responses={200: OpenApiResponse(description="Password reset successful")},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def password_reset_confirm(request):
    """
    Password reset confirmation endpoint.

    POST /auth/password-reset/confirm
    Body: {"token": "uuid", "new_password": "password"}

    Resets password and invalidates existing tokens.
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    token = serializer.validated_data["token"]
    new_password = serializer.validated_data["new_password"]

    # Find user with this token
    try:
        user = User.objects.get(
            password_reset_token=token,
            password_reset_token_expires_at__gt=timezone.now(),
            password_reset_token_used_at__isnull=True,
        )
    except User.DoesNotExist:
        raise ValidationError({"token": "Invalid or expired password reset token"})

    # Update password
    user.set_password(new_password)
    user.password_reset_token = None
    user.password_reset_token_expires_at = None
    user.password_reset_token_used_at = timezone.now()

    # Increment token version to invalidate existing tokens
    user.increment_token_version()

    # Revoke all refresh tokens
    RefreshToken.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )

    user.save()

    # Log audit event
    log_auth_operation(action="PASSWORD_RESET_COMPLETED", user=user, details={}, request=request)

    return Response({"message": "Password reset successfully"}, status=status.HTTP_200_OK)


@extend_schema(
    request=InvitationAcceptanceSerializer,
    responses={
        200: TokenResponseSerializer,
        400: OpenApiResponse(description="Invalid invitation token"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def accept_invitation(request):
    """
    Invitation acceptance endpoint.

    POST /auth/accept-invitation
    Body: {"token": "uuid", "password": "password"}

    Accepts invitation and activates user account.
    """
    serializer = InvitationAcceptanceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    token = serializer.validated_data["token"]
    password = serializer.validated_data["password"]

    # Find user with this invitation token
    try:
        user = User.objects.get(
            invitation_token=token,
            invitation_token_expires_at__gt=timezone.now(),
            invitation_token_used_at__isnull=True,
        )
    except User.DoesNotExist:
        raise ValidationError({"token": "Invalid or expired invitation token"})

    # Activate user and set password
    user.status = UserStatus.ACTIVE
    user.set_password(password)
    user.invitation_token = None
    user.invitation_token_expires_at = None
    user.invitation_token_used_at = timezone.now()
    user.save()

    # Generate tokens
    access_token = JWTTokenGenerator.generate_access_token(user)

    refresh_token_str = RefreshToken.generate_token()
    refresh_token_hash = RefreshToken.hash_token(refresh_token_str)
    expires_at = timezone.now() + timedelta(seconds=settings.JWT_REFRESH_TOKEN_EXPIRY)

    refresh_token_obj = RefreshToken.objects.create(
        user=user, token_hash=refresh_token_hash, expires_at=expires_at
    )

    # Audit logging is handled by the authentication middleware and signal handlers

    return Response(
        {
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "token_type": "Bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRY,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=RegisterSerializer,
    responses={
        201: RegisterResponseSerializer,
        400: OpenApiResponse(description="Validation error or email already exists"),
        429: OpenApiResponse(description="Rate limit exceeded"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@transaction.atomic
def register(request):
    """
    User registration endpoint.

    POST /auth/register
    Body: {"email": "user@example.com", "password": "SecurePass123", "name": "John Doe", "tenant_id": "uuid (optional)"}

    Creates a new user account with email, password, and name.
    Optionally associates user with a tenant.
    Publishes user.created event and sends welcome email (async).
    """
    logger = structlog.get_logger(__name__)
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]
    name = serializer.validated_data["name"]
    tenant_id = serializer.validated_data.get("tenant_id")

    # Get tenant if provided; otherwise use default tenant so tenant-scoped features (e.g. webhooks) work
    tenant = None
    if tenant_id:
        from hub.apps.tenants.models import Tenant

        try:
            tenant = Tenant.objects.get(id=tenant_id)
            if not tenant.is_active():
                raise ValidationError({"tenant_id": "Tenant is not active"})
        except Tenant.DoesNotExist:
            raise ValidationError({"tenant_id": "Tenant not found"})
    else:
        from hub.apps.tenants.models import Tenant, TenantStatus

        tenant, _ = Tenant.objects.get_or_create(
            slug="default",
            defaults={"name": "Default Tenant", "status": TenantStatus.ACTIVE},
        )
        if not tenant.is_active():
            tenant = None

    # Create user
    user = User.objects.create_user(
        email=email,
        password=password,
        tenant=tenant,
        display_name=name,
        status=UserStatus.ACTIVE,  # Users register as active (not invited)
    )

    # Publish user.created event
    try:
        event_id = publish_event(
            event_type="user.created",
            data={
                "user_id": str(user.id),
                "email": user.email,
                "tenant_id": str(tenant.id) if tenant else None,
                "created_at": user.created_at.isoformat(),
            },
            tenant_id=str(tenant.id) if tenant else None,
            user_id=str(user.id),
            request_id=getattr(request, "id", None),
        )
    except Exception as e:
        # Log error but don't fail registration
        logger.error(
            "user_created_event_publish_failed", user_id=str(user.id), error=str(e), exc_info=True
        )

    # Send welcome email asynchronously (optional, don't fail if it fails)
    try:
        from django_rq import get_queue

        from hub.apps.notifications.models import EmailType
        from hub.apps.notifications.tasks import send_email_async

        # Build welcome email context
        context = {
            "user": user,
            "tenant": tenant,
            "login_url": f"{getattr(settings, 'EMAIL_BASE_URL', 'http://localhost:8000')}/login",
        }

        # Use USER_INVITATION email type (or create USER_WELCOME if it exists)
        email_type = EmailType.USER_INVITATION  # Use existing email type

        # Queue email task (non-blocking) - send_email_async is a regular function, not a task
        # We'll call it directly in a background job
        queue = get_queue("job_low")
        queue.enqueue(
            send_email_async,
            email_type=email_type,
            to_email=user.email,
            subject=f"Welcome to {tenant.name if tenant else 'Data Interoperability Hub'}",
            template_name="notifications/emails/user_welcome.html",
            context=context,
            tenant_id=str(tenant.id) if tenant else None,
            user_id=str(user.id),
        )
    except Exception as e:
        # Log error but don't fail registration
        logger.warning("welcome_email_queue_failed", user_id=str(user.id), error=str(e))

    # Log audit event
    log_auth_operation(
        action="REGISTER",
        user=user,
        details={"method": "email", "tenant_id": str(tenant.id) if tenant else None},
        request=request,
    )

    # Return response
    response_serializer = RegisterResponseSerializer(
        {
            "id": user.id,
            "email": user.email,
            "name": user.display_name,
            "tenant_id": tenant.id if tenant else None,
            "created_at": user.created_at,
        }
    )

    return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    responses={
        200: CurrentUserSerializer,
        401: OpenApiResponse(description="Unauthorized - Invalid or missing token"),
    },
    tags=["Authentication"],
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    """
    Get current authenticated user information.

    GET /auth/me

    Returns information about the currently authenticated user including:
    - Basic user info (id, email, name, tenant_id)
    - Roles
    - Permissions
    - Account metadata (created_at, last_login_at)

    Performance target: < 200ms p95
    Caching: Response may be cached for up to 5 minutes
    """
    user = request.user

    # Check cache first (5 minute TTL)
    cache_key = f"user:me:{user.id}"
    cached_response = cache.get(cache_key)
    if cached_response:
        return Response(cached_response, status=status.HTTP_200_OK)

    # Get roles
    roles = []
    if hasattr(user, "user_roles"):
        roles = [ur.role.name for ur in user.user_roles.all()]

    # Get permissions
    from .serializers import get_user_permissions

    permissions = get_user_permissions(user)

    # Get last login (if available - this would need to be tracked separately)
    # For now, we'll use updated_at as a proxy
    last_login_at = None
    # TODO: Track last_login_at in User model or separate LoginHistory model

    # Build response
    # Handle deleted tenant gracefully
    tenant_id = None
    try:
        if user.tenant:
            tenant_id = user.tenant.id
    except Exception:
        # Tenant was deleted or doesn't exist
        tenant_id = None

    response_data = {
        "id": str(user.id),  # Ensure UUID is serialized as string
        "email": user.email,
        "name": user.display_name,
        "tenant_id": str(tenant_id) if tenant_id else None,  # Ensure UUID is serialized as string
        "roles": roles,
        "permissions": permissions,
        "created_at": user.created_at,
        "last_login_at": last_login_at,
    }

    # Cache response for 5 minutes
    cache.set(cache_key, response_data, 300)

    return Response(response_data, status=status.HTTP_200_OK)


class APIKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for API key management.

    Tenant-scoped: users can only manage API keys in their tenant.
    Supports pagination via query parameters: page (default: 1) and page_size (default: 50, max: 100).
    """

    serializer_class = APIKeySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    pagination_class = StandardPageNumberPagination

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Platform admins can see all API keys
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return APIKey.objects.all()

        # Regular users can only see API keys in their tenant
        if hasattr(user, "tenant") and user.tenant:
            return APIKey.objects.filter(tenant=user.tenant)

        return APIKey.objects.none()

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return APIKeyCreateSerializer
        return APIKeySerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new API key.

        Returns the plaintext key (shown only once).
        """
        serializer = APIKeyCreateSerializer(
            data=request.data,
            context={
                "tenant": (
                    request.user.tenant
                    if hasattr(request.user, "tenant") and request.user.tenant
                    else None
                ),
                "user": request.user,
            },
        )
        serializer.is_valid(raise_exception=True)

        # Ensure tenant is set
        tenant = serializer.context["tenant"]
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to create API keys"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer for creation (Phase 24.7.2)
        from hub.apps.auth.services import APIKeyService
        from hub.apps.core.responses import handle_service_exception
        from hub.apps.core.services.base import NotFoundError
        from hub.apps.core.services.base import ValidationError as ServiceValidationError

        service = APIKeyService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        try:
            api_key, plaintext_key = service.create_api_key(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id) if request.user else None,
                name=serializer.validated_data["name"],
                scopes=serializer.validated_data.get("scopes", []),
                expires_in_days=serializer.validated_data.get("expires_in_days"),
                rate_limit_per_hour=serializer.validated_data.get("rate_limit_per_hour"),
            )
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)

        # Return response with plaintext key
        response_serializer = APIKeyResponseSerializer(
            {
                "id": api_key.id,
                "name": api_key.name,
                "api_key": plaintext_key,
                "scopes": api_key.scopes,
                "expires_at": api_key.expires_at,
                "created_at": api_key.created_at,
            }
        )

        # Audit event is already created in service layer

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        """List API keys (tenant-scoped)"""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve API key by ID"""
        return super().retrieve(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Revoke an API key via service layer (soft delete by setting expires_at to past).

        For now, we'll actually delete it. In production, you might want to soft delete.
        """
        api_key = self.get_object()
        tenant_id = str(api_key.tenant.id) if api_key.tenant else None
        if not tenant_id:
            return Response(
                {"error": "API key must belong to a tenant"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer for deletion (Phase 24.7.2)
        from hub.apps.auth.services import APIKeyService
        from hub.apps.core.responses import handle_service_exception
        from hub.apps.core.services.base import NotFoundError

        service = APIKeyService(tenant_id=tenant_id, user_id=str(request.user.id))
        try:
            service.delete_api_key(
                api_key_id=str(api_key.id),
                tenant_id=tenant_id,
                actor_user_id=str(request.user.id),
            )
        except NotFoundError as e:
            return handle_service_exception(e)

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(responses={200: RefreshTokenResponseSerializer(many=True)}, tags=["Authentication"])
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def list_active_sessions(request):
    """
    List active sessions (refresh tokens) for the current user.

    GET /auth/sessions/

    Returns list of active refresh tokens (sessions) for the authenticated user.
    """
    user = request.user

    # Get all refresh tokens for this user (including revoked ones for history)
    refresh_tokens = RefreshToken.objects.filter(user=user).order_by("-created_at")

    # Get current session's refresh token hash from request if available
    current_token_hash = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        # We can't get the refresh token from the access token, so we'll
        # check if we can identify the current session another way
        # For now, we'll mark the most recent non-revoked token as current
        pass

    # Serialize refresh tokens
    sessions = []
    most_recent_active = None
    for token in refresh_tokens:
        if not token.is_revoked() and not token.is_expired():
            if most_recent_active is None:
                most_recent_active = token.id

        session_data = {
            "id": str(token.id),
            "created_at": token.created_at,
            "expires_at": token.expires_at,
            "revoked_at": token.revoked_at,
            "is_current": token.id == most_recent_active
            and not token.is_revoked()
            and not token.is_expired(),
        }
        sessions.append(session_data)

    return Response(sessions, status=status.HTTP_200_OK)


@extend_schema(
    responses={200: OpenApiResponse(description="Session revoked successfully")},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def revoke_session(request, session_id):
    """
    Revoke a specific session (refresh token).

    POST /auth/sessions/{session_id}/revoke/

    Revokes the specified refresh token (session).
    """
    try:
        refresh_token = RefreshToken.objects.get(id=session_id, user=request.user)
    except RefreshToken.DoesNotExist:
        raise NotFound("Session not found")

    # Revoke the token
    if not refresh_token.revoked_at:
        refresh_token.revoked_at = timezone.now()
        refresh_token.save(update_fields=["revoked_at", "updated_at"])

        # Log audit event
        log_auth_operation(
            action="SESSION_REVOKED",
            user=request.user,
            details={"session_id": str(session_id)},
            request=request,
        )

    return Response({"message": "Session revoked successfully"}, status=status.HTTP_200_OK)
