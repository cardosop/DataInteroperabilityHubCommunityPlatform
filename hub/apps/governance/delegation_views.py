"""
Phase 272.6 — the ApprovalDelegation API surface.

The FE consumer is ``DelegationSettingsPage`` (frontend
``/settings/delegation``, guarded by TENANT_ADMIN|PLATFORM_ADMIN) — the
contract here is FE-frozen:

- GET    /api/v1/governance/delegations/       plain ARRAY (no pagination)
- POST   /api/v1/governance/delegations/       validation errors surface
  under ``{"detail": "..."}`` (the page reads ``body.detail``)
- DELETE /api/v1/governance/delegations/{id}/  the page's Revoke action

Permissions mirror the FE route guard: IsAuthenticated + HasRole
TENANT_ADMIN (HasRole passes platform admins automatically). Rows are
tenant-scoped (the RLS policy shipped with the 272.6 model migration);
platform admins see every tenant's rows (the access-request convention).
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from hub.apps.audit.utils import create_audit_event
from hub.apps.auth.permissions import HasRole
from hub.apps.governance.models import ApprovalDelegation
from hub.apps.users.models import User, UserStatus


class DelegationSerializer(serializers.ModelSerializer):
    """The FE record shape (DelegationSettingsPage's Delegation type)."""

    delegate_email = serializers.SerializerMethodField()
    delegate_name = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalDelegation
        fields = (
            "id",
            "delegate_email",
            "delegate_name",
            "start_at",
            "end_at",
            "reason",
            "is_active",
            "created_at",
        )

    def get_delegate_email(self, obj) -> str:
        return obj.delegate.email

    def get_delegate_name(self, obj) -> str:
        return obj.delegate.display_name or obj.delegate.email

    def get_is_active(self, obj) -> bool:
        return obj.is_active()


class DelegationInputSerializer(serializers.Serializer):
    """The create payload — validation errors carry ``{"detail": ...}``."""

    delegate_email = serializers.EmailField(required=True)
    start_at = serializers.DateTimeField(required=True)
    end_at = serializers.DateTimeField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs):
        if attrs["end_at"] <= attrs["start_at"]:
            raise serializers.ValidationError({"detail": "End date must be after start date."})
        return attrs


class DelegationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Delegation CRUD for the settings page — list / create / revoke."""

    serializer_class = DelegationSerializer
    lookup_field = "id"

    def get_permissions(self):
        # Pre-instantiated objects — the DRF 3.16 convention (HasRole
        # takes a required-role argument at construction).
        return [permissions.IsAuthenticated(), HasRole("TENANT_ADMIN")]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_platform_admin", False):
            return ApprovalDelegation.objects.all()
        tenant = getattr(self.request, "tenant", None) or getattr(user, "tenant", None)
        if tenant is None:
            return ApprovalDelegation.objects.none()
        return ApprovalDelegation.objects.filter(tenant=tenant)

    def create(self, request):
        input_serializer = DelegationInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        tenant = getattr(request, "tenant", None) or getattr(request.user, "tenant", None)
        if tenant is None:
            raise ValidationError({"detail": "No tenant context for this request."})

        delegate = User.objects.filter(
            email__iexact=data["delegate_email"].strip(),
            tenant=tenant,
            status=UserStatus.ACTIVE,
        ).first()
        if delegate is None:
            raise ValidationError(
                {"detail": "Delegate email does not match an active user in this tenant."}
            )
        if delegate.id == request.user.id:
            raise ValidationError({"detail": "You cannot delegate approval authority to yourself."})

        # `reason` is optional — DRF omits the key from validated_data
        # entirely when the client does not send it (the FE drops
        # undefined fields via JSON.stringify). A direct index raises
        # KeyError → 500 on the no-reason path.
        reason = (data.get("reason") or "").strip() or None
        delegation = ApprovalDelegation(
            tenant=tenant,
            delegator=request.user,
            delegate=delegate,
            start_at=data["start_at"],
            end_at=data["end_at"],
            reason=reason,
        )
        try:
            # The model's clean() rejects overlapping windows for the
            # same delegator-delegate pair (272.6) — surface it under
            # ``detail`` so the FE form shows the message.
            delegation.full_clean()
        except DjangoValidationError as exc:
            messages = [str(m) for m in exc.messages]
            raise ValidationError({"detail": "; ".join(messages)}) from exc
        delegation.save()

        create_audit_event(
            resource_type="APPROVAL_DELEGATION",
            action="DELEGATION_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(delegation.id),
            details={
                "delegate_email": delegate.email,
                "start_at": delegation.start_at.isoformat(),
                "end_at": delegation.end_at.isoformat(),
                "is_active": delegation.is_active(),
            },
            request=request,
        )
        return Response(
            DelegationSerializer(delegation).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance):
        """Audit BEFORE the delete (the row's data rides the event)."""
        delegation_id = str(instance.id)
        tenant = instance.tenant
        details = {
            "delegate_email": instance.delegate.email,
            "start_at": instance.start_at.isoformat(),
            "end_at": instance.end_at.isoformat(),
            "revoked_at": timezone.now().isoformat(),
        }
        instance.delete()
        create_audit_event(
            resource_type="APPROVAL_DELEGATION",
            action="DELEGATION_REVOKED",
            actor_user=self.request.user,
            tenant=tenant,
            resource_id=delegation_id,
            details=details,
            request=self.request,
        )
