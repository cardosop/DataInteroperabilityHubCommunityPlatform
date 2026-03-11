"""
User Serializers

DRF serializers for User and Role API.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import User, Role, UserRole, UserStatus

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model"""
    
    class Meta:
        model = Role
        fields = ["id", "tenant", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserRoleSerializer(serializers.ModelSerializer):
    """Serializer for UserRole join table"""
    role = RoleSerializer(read_only=True)
    role_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = UserRole
        fields = ["id", "user", "role", "role_id", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    status = serializers.ChoiceField(choices=UserStatus.choices, read_only=True)
    roles = serializers.SerializerMethodField()
    tenant_name = serializers.CharField(source="tenant.name", read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "email",
            "display_name",
            "status",
            "is_platform_admin",
            "roles",
            "created_at",
            "updated_at"
        ]
        read_only_fields = [
            "id",
            "status",
            "is_platform_admin",
            "created_at",
            "updated_at"
        ]
    
    def get_roles(self, obj):
        """Get user's role names (strings) for display in admin/list views."""
        user_roles = UserRole.objects.filter(user=obj).select_related("role")
        return [role.role.name for role in user_roles]


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for user creation"""
    role_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="List of role IDs to assign to the user"
    )
    send_invitation = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether to send an invitation email to the user"
    )
    
    class Meta:
        model = User
        fields = [
            "email",
            "display_name",
            "tenant",
            "password",
            "role_ids",
            "send_invitation",
            "status"
        ]
        extra_kwargs = {
            "password": {"write_only": True, "required": False}
        }
    
    def create(self, validated_data):
        """Create user with optional role assignment"""
        role_ids = validated_data.pop("role_ids", [])
        send_invitation = validated_data.pop("send_invitation", True)
        password = validated_data.pop("password", None)
        
        # Set status based on invitation, but respect explicit status if provided
        if "status" not in validated_data:
            if send_invitation:
                validated_data["status"] = UserStatus.INVITED
            else:
                validated_data["status"] = UserStatus.ACTIVE
        
        # Create user
        user = User.objects.create_user(
            email=validated_data["email"],
            password=password,
            tenant=validated_data.get("tenant"),
            display_name=validated_data.get("display_name")
        )
        user.status = validated_data["status"]
        user.save()
        
        # Assign roles
        if role_ids:
            roles = Role.objects.filter(id__in=role_ids, tenant=user.tenant)
            for role in roles:
                UserRole.objects.get_or_create(user=user, role=role)
        
        # Generate invitation token if needed
        if send_invitation:
            from django.utils import timezone
            from datetime import timedelta
            import uuid
            
            user.invitation_token = uuid.uuid4()
            user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
            user.save(update_fields=["invitation_token", "invitation_token_expires_at"])
        
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for user update (roles, status, display_name). Admin only."""

    role_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="List of role IDs to assign (replaces existing roles)",
    )

    class Meta:
        model = User
        fields = ["display_name", "status", "role_ids"]

    def validate_status(self, value):
        """Validate status transitions"""
        user = self.instance
        if user.status == UserStatus.DISABLED and value != UserStatus.ACTIVE:
            raise serializers.ValidationError("Cannot change status from DISABLED")
        return value

    def validate_role_ids(self, value):
        """Validate role IDs belong to user's tenant"""
        if not value:
            return value
        user = self.instance
        if not user or not user.tenant_id:
            raise serializers.ValidationError("User must belong to a tenant")
        from .models import Role

        valid_ids = set(
            Role.objects.filter(id__in=value, tenant_id=user.tenant_id).values_list("id", flat=True)
        )
        invalid = set(value) - valid_ids
        if invalid:
            raise serializers.ValidationError(
                f"Role(s) not found or not in same tenant: {list(invalid)}"
            )
        return value


class UserInviteSerializer(serializers.Serializer):
    """Serializer for user invitation"""
    email = serializers.EmailField()
    display_name = serializers.CharField(required=False, allow_blank=True)
    role_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="List of role IDs to assign to the user"
    )


class UserRoleAssignmentSerializer(serializers.Serializer):
    """Serializer for role assignment/removal"""
    role_id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=["assign", "remove"])

