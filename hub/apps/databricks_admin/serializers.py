"""P0 (openspec add-databricks-control-plane) — workspace + credential serializers."""

from typing import ClassVar

from rest_framework import serializers

from hub.apps.databricks_admin.models import (
    DatabricksCredential,
    DatabricksCredentialAuthMode,
    DatabricksWorkspace,
)
from hub.apps.governance.models import AccessRequest, AccessRequestStatus


class WorkspaceSerializer(serializers.ModelSerializer):
    """Workspace read/write serializer.

    ``status`` is read-only: lifecycle changes happen only through the
    state machine (``transition_to``) driven by the test/delete actions —
    never through arbitrary client writes.
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = DatabricksWorkspace
        fields = (
            "id",
            "tenant",
            "name",
            "host",
            "cloud",
            "region",
            "metastore_id",
            "status",
            "status_display",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "tenant",
            "status",
            "created_at",
            "updated_at",
        )


class CredentialSerializer(serializers.ModelSerializer):
    """Credential metadata; ``config`` is write-only — never returned."""

    auth_mode_display = serializers.CharField(source="get_auth_mode_display", read_only=True)
    # Phase 1 (add-databricks-uc-read 1.5) — the Phase 272 access request
    # whose approver chain authorized this service credential. Background
    # execution (the UC metadata sync job) resolves its D12 identity
    # through it; validated in create() against the workspace's tenant.
    approval_request = serializers.PrimaryKeyRelatedField(
        queryset=AccessRequest.objects.all(),
        write_only=True,
        required=False,
        allow_null=False,
    )

    class Meta:
        model = DatabricksCredential
        fields = (
            "id",
            "workspace",
            "auth_mode",
            "auth_mode_display",
            "config",
            "expires_at",
            "last_rotated_at",
            "approval_request",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "workspace", "created_at", "updated_at")
        extra_kwargs: ClassVar[dict[str, dict[str, bool]]] = {"config": {"write_only": True}}

    def validate_config(self, value):
        # The model's encryption guard only wraps dicts — a bare JSON
        # string/array would be stored in PLAINTEXT. Reject it here so
        # encryption-at-rest cannot be bypassed through the API.
        if not isinstance(value, dict):
            raise serializers.ValidationError("config must be a JSON object")
        return value

    def validate(self, attrs):
        # API-boundary credential shape: a malformed credential must fail at
        # registration time, not later at probe/execution time.
        auth_mode = attrs.get("auth_mode")
        config = attrs.get("config") or {}
        if auth_mode == DatabricksCredentialAuthMode.PAT:
            if not str(config.get("token") or "").strip():
                raise serializers.ValidationError(
                    {"config": "PAT credentials require a non-empty 'token'"}
                )
        elif auth_mode == DatabricksCredentialAuthMode.OAUTH_M2M:
            missing = [
                key
                for key in ("client_id", "client_secret")
                if not str(config.get(key) or "").strip()
            ]
            if missing:
                raise serializers.ValidationError(
                    {"config": f"M2M credentials require non-empty {', '.join(missing)}"}
                )
        return attrs

    def create(self, validated_data):
        # 1.5 — the approver-chain linkage is validated at CREATE time:
        # a background execution identity is only as strong as the chain
        # that authorized it. Same tenant, APPROVED status, non-empty
        # workflow snapshot — anything less can never authorize a sync.
        workspace = validated_data.pop("workspace")
        approval_request = validated_data.pop("approval_request", None)
        if approval_request is not None:
            if str(approval_request.tenant_id) != str(workspace.tenant_id):
                raise serializers.ValidationError(
                    {"approval_request": "the access request belongs to a different tenant"}
                )
            if approval_request.status != AccessRequestStatus.APPROVED:
                raise serializers.ValidationError(
                    {"approval_request": "only APPROVED access requests can authorize a credential"}
                )
            if not approval_request.approval_workflow:
                raise serializers.ValidationError(
                    {"approval_request": "the access request carries no approver chain"}
                )
        return DatabricksCredential.objects.create(
            workspace=workspace, approval_request=approval_request, **validated_data
        )


class RotateCredentialSerializer(serializers.Serializer):
    """Rotation payload — M2M re-issue requires the new secret."""

    client_secret = serializers.CharField(required=False, write_only=True, allow_blank=False)
