"""P8 (openspec add-databricks-account-plane task 8.3) — the provisioning
surface: metastore ops + workspace provisioning through the account API.

PLATFORM_ADMIN-only (a non-platform caller gets 403 PERMISSION_DENIED —
the prose error table). The account row resolves through the forced admin
alias (the ``AdminDatabaseManager``); the target tenant resolves over the
admin alias too (the sanctioned cross-tenant read path — a
platform-admin request carries no target-tenant GUC). Every provisioning
request is refused with 403 and ZERO network unless BOTH the target
tenant's flag is ON and a COMPLETE DPO/Legal signoff is recorded (the D3
triple — ``account_ops.check_provisioning_allowed``). Request-shape
discipline fires FIRST: a missing tenant_id / name / region /
workspace_name / aws_region is a 400 before any provisioning logic.
"""

from __future__ import annotations

from typing import ClassVar

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from hub.apps.auth.permissions import HasRole
from hub.apps.databricks_admin import account_ops
from hub.apps.databricks_admin.models import DatabricksAccount


class _AccountPermissionDenied(PermissionDenied):
    """The prose error table's contract: a non-platform-admin caller gets
    403 with the CANONICAL ``PERMISSION_DENIED`` code. The code is a CLASS
    attribute (the repo's envelope handler reads class attributes — DRF
    3.16 dropped the instance ``code`` attribute, so a constructor
    ``code=`` kwarg would collapse to ``AUTH_FORBIDDEN``)."""

    status_code = 403
    code = "PERMISSION_DENIED"
    default_detail = "You do not have permission to perform this action."


class AccountAlreadyLinked(APIException):
    """409 — the Databricks account id is already linked (the model's
    unique constraint; the class-attribute code convention)."""

    status_code = status.HTTP_409_CONFLICT
    code = "DATABRICKS_ACCOUNT_ALREADY_LINKED"
    default_detail = "This Databricks account is already linked to the platform."


class AccountProvisioningViewSet(viewsets.ViewSet):
    """POST /api/v1/databricks/accounts/ (the link, 8.5) +
    POST /api/v1/databricks/accounts/{id}/metastores/ and
    POST /api/v1/databricks/accounts/{id}/workspaces/."""

    permission_classes: ClassVar[list] = [permissions.IsAuthenticated]

    # NOTE: no further ``permission_classes`` entries — get_permissions()
    # is the single source of truth (pre-instantiated HasRole entries
    # break DRF's re-invocation; see the HasRole docstring).
    def get_permissions(self):
        return [permissions.IsAuthenticated(), HasRole("PLATFORM_ADMIN")]

    def permission_denied(
        self,
        request,
        message=None,
        code=None,  # DRF override — framework keyword-dispatches
    ):
        # DRF's default semantics FIRST: an unauthenticated caller (no
        # successful authenticator) gets 401 NotAuthenticated — never a
        # 403 (the DRF permission_denied contract the house surfaces
        # rely on; the override below only pins the code for the
        # AUTHENTICATED non-platform caller). 8.4 review fix — the
        # unconditional raise sent anonymous callers 403.
        if request.authenticators and not request.successful_authenticator:
            from rest_framework import exceptions as drf_exceptions

            raise drf_exceptions.NotAuthenticated()
        raise _AccountPermissionDenied(detail=message)

    def create(self, request):
        """POST /api/v1/databricks/accounts/ — link the platform's
        Databricks account (design D1; the ``DATABRICKS_ACCOUNT_LINKED``
        emission rides ``account_ops.link_account``)."""
        data = request.data or {}
        account_id = (data.get("account_id") or "").strip()
        display_name = (data.get("display_name") or "").strip()
        credential = data.get("credential")
        if not account_id:
            raise ValidationError({"account_id": "Required."})
        if not display_name:
            raise ValidationError({"display_name": "Required."})
        if not isinstance(credential, dict) or not (credential.get("token") or "").strip():
            raise ValidationError({"credential": {"token": "Required."}})
        try:
            account = account_ops.link_account(
                account_id=account_id,
                display_name=display_name,
                credential_config=credential,
            )
        except DjangoValidationError as exc:
            raise ValidationError(str(exc)) from None
        except IntegrityError:
            raise AccountAlreadyLinked() from None
        return Response(
            {
                "id": str(account.id),
                "account_id": str(account.account_id),
                "display_name": account.display_name,
                "created_at": account.created_at,
            },
            status=status.HTTP_201_CREATED,
        )

    def _account(self, pk) -> DatabricksAccount:
        # The forced admin alias rides the model's manager — every read
        # and write of the platform table routes through DATABASES["admin"].
        try:
            return DatabricksAccount.objects.get(id=pk)
        except (DatabricksAccount.DoesNotExist, ValueError):
            raise NotFound("Account not found.") from None

    def _target_tenant(self, request):
        from hub.apps.tenants.models import Tenant

        tenant_id = (request.data or {}).get("tenant_id")
        if not tenant_id:
            raise ValidationError({"tenant_id": "Required."})
        try:
            return Tenant.objects.using("admin").get(id=tenant_id)
        except (Tenant.DoesNotExist, ValueError):
            raise NotFound("Tenant not found.") from None

    @extend_schema(
        parameters=[OpenApiParameter("id", OpenApiTypes.UUID, OpenApiParameter.PATH)],
    )
    @action(detail=True, methods=["post"], url_path="metastores")
    def create_metastore(self, request, pk=None):
        account = self._account(pk)
        tenant = self._target_tenant(request)
        data = request.data or {}
        name = (data.get("name") or "").strip()
        region = (data.get("region") or "").strip()
        if not name:
            raise ValidationError({"name": "Required."})
        if not region:
            raise ValidationError({"region": "Required."})

        envelope = account_ops.provision_metastore(
            account,
            tenant,
            name=name,
            region=region,
            storage_root=data.get("storage_root"),
        )
        return Response(envelope, status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[OpenApiParameter("id", OpenApiTypes.UUID, OpenApiParameter.PATH)],
    )
    @action(detail=True, methods=["post"], url_path="workspaces")
    def provision_workspace(self, request, pk=None):
        account = self._account(pk)
        tenant = self._target_tenant(request)
        data = request.data or {}
        workspace_name = (data.get("workspace_name") or "").strip()
        aws_region = (data.get("aws_region") or "").strip()
        if not workspace_name:
            raise ValidationError({"workspace_name": "Required."})
        if not aws_region:
            raise ValidationError({"aws_region": "Required."})

        try:
            workspace = account_ops.provision_workspace(
                account,
                tenant,
                workspace_name=workspace_name,
                aws_region=aws_region,
                deployment_name=data.get("deployment_name"),
                pricing_tier=data.get("pricing_tier"),
            )
        except DjangoValidationError as exc:
            # The EXISTING registry validation (host SSRF / region
            # residency) refusing the envelope — surface it as a 400,
            # never a 500.
            raise ValidationError(str(exc)) from None
        return Response(
            {
                "id": str(workspace.id),
                "tenant_id": str(workspace.tenant_id),
                "name": workspace.name,
                "host": workspace.host,
                "cloud": workspace.cloud,
                "region": workspace.region,
                "status": workspace.status,
            },
            status=status.HTTP_201_CREATED,
        )
