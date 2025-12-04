"""
Authentication Views

REST API views for authentication (login, logout, password reset, etc.).
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import uuid

from .models import APIKey, RefreshToken
from .serializers import (
    LoginSerializer,
    TokenResponseSerializer,
    RefreshTokenSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    InvitationAcceptanceSerializer,
    APIKeyCreateSerializer,
    APIKeySerializer,
    APIKeyResponseSerializer
)
from .jwt_utils import JWTTokenGenerator
from hub.apps.users.models import User, UserStatus
from hub.apps.audit.utils import log_auth_operation
from django.conf import settings


@extend_schema(
    request=LoginSerializer,
    responses={200: TokenResponseSerializer, 400: OpenApiResponse(description='Invalid credentials')},
    tags=['Authentication']
)
@api_view(['POST'])
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
    
    email = serializer.validated_data['email']
    password = serializer.validated_data['password']
    
    # Authenticate user
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        raise ValidationError({'email': 'Invalid email or password'})
    
    # Check password
    if not user.check_password(password):
        raise ValidationError({'email': 'Invalid email or password'})
    
    # Check if user is active
    if not user.is_active():
        raise ValidationError({'email': 'User account is not active'})
    
    # Generate access token
    access_token = JWTTokenGenerator.generate_access_token(user)
    
    # Generate refresh token
    refresh_token_str = RefreshToken.generate_token()
    refresh_token_hash = RefreshToken.hash_token(refresh_token_str)
    
    expires_at = timezone.now() + timedelta(seconds=settings.JWT_REFRESH_TOKEN_EXPIRY)
    
    refresh_token_obj = RefreshToken.objects.create(
        user=user,
        token_hash=refresh_token_hash,
        expires_at=expires_at
    )
    
    # Log audit event
    log_auth_operation(
        action="LOGIN",
        user=user,
        details={"method": "password"},
        request=request
    )
    
    return Response({
        'access_token': access_token,
        'refresh_token': refresh_token_str,
        'token_type': 'Bearer',
        'expires_in': settings.JWT_ACCESS_TOKEN_EXPIRY
    }, status=status.HTTP_200_OK)


@extend_schema(
    request=RefreshTokenSerializer,
    responses={200: TokenResponseSerializer, 400: OpenApiResponse(description='Invalid refresh token')},
    tags=['Authentication']
)
@api_view(['POST'])
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
    
    refresh_token_str = serializer.validated_data['refresh_token']
    refresh_token_hash = RefreshToken.hash_token(refresh_token_str)
    
    # Look up refresh token
    try:
        refresh_token_obj = RefreshToken.objects.get(token_hash=refresh_token_hash)
    except RefreshToken.DoesNotExist:
        raise ValidationError({'refresh_token': 'Invalid refresh token'})
    
    # Check if valid
    if not refresh_token_obj.is_valid():
        raise ValidationError({'refresh_token': 'Refresh token is expired or revoked'})
    
    user = refresh_token_obj.user
    
    # Check if user is active
    if not user.is_active():
        raise ValidationError({'refresh_token': 'User account is not active'})
    
    # Generate new access token
    access_token = JWTTokenGenerator.generate_access_token(user)
    
    # Log audit event
    log_auth_operation(
        action="TOKEN_REFRESHED",
        user=user,
        details={},
        request=request
    )
    
    return Response({
        'access_token': access_token,
        'token_type': 'Bearer',
        'expires_in': settings.JWT_ACCESS_TOKEN_EXPIRY
    }, status=status.HTTP_200_OK)


@extend_schema(
    request=inline_serializer(
        name='TokenRefreshRequest',
        fields={
            'refresh_token': serializers.CharField(required=True)
        }
    ),
    responses={200: OpenApiResponse(description='Logged out successfully')},
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    """
    User logout endpoint.
    
    POST /auth/logout
    Body: {"refresh_token": "token_string"} (optional)
    
    Revokes refresh token(s).
    """
    revoked_count = 0
    
    # If refresh token provided, revoke it
    if 'refresh_token' in request.data:
        refresh_token_str = request.data['refresh_token']
        refresh_token_hash = RefreshToken.hash_token(refresh_token_str)
        
        # Try to find and revoke the token
        # Use user_id instead of user to handle object instance differences
        refresh_token_obj = RefreshToken.objects.filter(
            token_hash=refresh_token_hash,
            user_id=request.user.id
        ).first()
        
        if refresh_token_obj:
            # Token found - revoke it
            if not refresh_token_obj.revoked_at:
                refresh_token_obj.revoked_at = timezone.now()
                refresh_token_obj.save(update_fields=["revoked_at", "updated_at"])
                revoked_count = 1
        else:
            # If not found with user match, try without user match (fallback)
            # This handles edge cases but should not normally be needed
            refresh_token_obj = RefreshToken.objects.filter(
                token_hash=refresh_token_hash
            ).first()
            
            if refresh_token_obj and refresh_token_obj.user_id == request.user.id:
                # Only revoke if the token's user ID matches request.user ID
                if not refresh_token_obj.revoked_at:
                    refresh_token_obj.revoked_at = timezone.now()
                    refresh_token_obj.save(update_fields=["revoked_at", "updated_at"])
                    revoked_count = 1
    else:
        # Revoke all refresh tokens for this user
        revoked_count = RefreshToken.objects.filter(
            user=request.user,
            revoked_at__isnull=True
        ).update(revoked_at=timezone.now())
    
    # Log audit event
    log_auth_operation(
        action="LOGOUT",
        user=request.user,
        details={"revoked_tokens": revoked_count},
        request=request
    )
    
    return Response({
        'message': 'Logged out successfully',
        'revoked_sessions': revoked_count
    }, status=status.HTTP_200_OK)


@extend_schema(
    request=PasswordResetRequestSerializer,
    responses={200: OpenApiResponse(description='Password reset email sent')},
    tags=['Authentication']
)
@api_view(['POST'])
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
    
    email = serializer.validated_data['email']
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Don't reveal if user exists
        return Response({'message': 'If the email exists, a password reset link has been sent.'}, status=status.HTTP_200_OK)
    
    # Generate password reset token
    user.password_reset_token = uuid.uuid4()
    user.password_reset_token_expires_at = timezone.now() + timedelta(hours=1)
    user.save(update_fields=['password_reset_token', 'password_reset_token_expires_at'])
    
    # Send password reset email
    from hub.apps.notifications.tasks import send_password_reset_email
    send_password_reset_email.delay(str(user.id))
    
    # Log audit event
    log_auth_operation(
        action="PASSWORD_RESET_REQUESTED",
        user=user,
        details={},
        request=request
    )
    
    return Response({'message': 'If the email exists, a password reset link has been sent.'}, status=status.HTTP_200_OK)


@extend_schema(
    request=PasswordResetConfirmSerializer,
    responses={200: OpenApiResponse(description='Password reset successful')},
    tags=['Authentication']
)
@api_view(['POST'])
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
    
    token = serializer.validated_data['token']
    new_password = serializer.validated_data['new_password']
    
    # Find user with this token
    try:
        user = User.objects.get(
            password_reset_token=token,
            password_reset_token_expires_at__gt=timezone.now(),
            password_reset_token_used_at__isnull=True
        )
    except User.DoesNotExist:
        raise ValidationError({'token': 'Invalid or expired password reset token'})
    
    # Update password
    user.set_password(new_password)
    user.password_reset_token = None
    user.password_reset_token_expires_at = None
    user.password_reset_token_used_at = timezone.now()
    
    # Increment token version to invalidate existing tokens
    user.increment_token_version()
    
    # Revoke all refresh tokens
    RefreshToken.objects.filter(
        user=user,
        revoked_at__isnull=True
    ).update(revoked_at=timezone.now())
    
    user.save()
    
    # Log audit event
    log_auth_operation(
        action="PASSWORD_RESET_COMPLETED",
        user=user,
        details={},
        request=request
    )
    
    return Response({'message': 'Password reset successfully'}, status=status.HTTP_200_OK)


@extend_schema(
    request=InvitationAcceptanceSerializer,
    responses={200: TokenResponseSerializer, 400: OpenApiResponse(description='Invalid invitation token')},
    tags=['Authentication']
)
@api_view(['POST'])
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
    
    token = serializer.validated_data['token']
    password = serializer.validated_data['password']
    
    # Find user with this invitation token
    try:
        user = User.objects.get(
            invitation_token=token,
            invitation_token_expires_at__gt=timezone.now(),
            invitation_token_used_at__isnull=True
        )
    except User.DoesNotExist:
        raise ValidationError({'token': 'Invalid or expired invitation token'})
    
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
        user=user,
        token_hash=refresh_token_hash,
        expires_at=expires_at
    )
    
    # Log audit event (placeholder)
    # TODO: Implement audit logging
    
    return Response({
        'access_token': access_token,
        'refresh_token': refresh_token_str,
        'token_type': 'Bearer',
        'expires_in': settings.JWT_ACCESS_TOKEN_EXPIRY
    }, status=status.HTTP_200_OK)


class APIKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for API key management.
    
    Tenant-scoped: users can only manage API keys in their tenant.
    """
    serializer_class = APIKeySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    
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
                'tenant': request.user.tenant if hasattr(request.user, 'tenant') and request.user.tenant else None,
                'user': request.user
            }
        )
        serializer.is_valid(raise_exception=True)
        
        # Ensure tenant is set
        tenant = serializer.context['tenant']
        if not tenant:
            return Response(
                {'error': 'User must belong to a tenant to create API keys'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        api_key = serializer.save()
        
        # Return response with plaintext key
        response_serializer = APIKeyResponseSerializer({
            'id': api_key.id,
            'name': api_key.name,
            'api_key': api_key._plaintext_key,
            'scopes': api_key.scopes,
            'expires_at': api_key.expires_at,
            'created_at': api_key.created_at
        })
        
        # Log audit event
        from hub.apps.audit.utils import create_audit_event
        create_audit_event(
            resource_type="API_KEY",
            action="API_KEY_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(api_key.id),
            details={"name": api_key.name, "scopes": api_key.scopes},
            request=request
        )
        
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
        Revoke an API key (soft delete by setting expires_at to past).
        
        For now, we'll actually delete it. In production, you might want to soft delete.
        """
        api_key = self.get_object()
        api_key_id = api_key.id
        api_key.delete()
        
        # Log audit event
        from hub.apps.audit.utils import create_audit_event
        create_audit_event(
            resource_type="API_KEY",
            action="API_KEY_REVOKED",
            actor_user=request.user,
            tenant=api_key.tenant,
            resource_id=str(api_key_id),
            details={"name": api_key.name},
            request=request
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)

