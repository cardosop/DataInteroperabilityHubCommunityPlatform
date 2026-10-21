"""
Contract Views ODPS Linking Operations

ODPS linking actions for contract viewsets.

SAVING CHECKPOINT: This module contains ODPS linking-related actions.
"""

from django.db import transaction
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from hub.apps.core.services.base import NotFoundError, ValidationError

from .models import OriginalSpecType
from .serializers import ContractSerializer, ODPSLinkSerializer
from .services import ContractService


class ContractODPSMixin:
    """
    Mixin for Contract ODPS linking operations.

    Provides ODPS linking, unlinking, and listing endpoints.
    """

    @extend_schema(
        summary="Link ODPS contract to ODCS contract",
        description="""
        Link an ODPS contract to an ODCS contract.

        Can link an existing ODPS contract or create a new one from raw content.
        """,
        request=ODPSLinkSerializer,
        responses={
            200: ContractSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Linking"],
    )
    @action(detail=True, methods=["post"], url_path="link-odps")
    @transaction.atomic
    def link_odps(self, request, id=None):
        """
        Link ODPS contract to ODCS contract.

        POST /api/v1/contracts/{id}/link-odps/
        Body: {
            "odps_contract_id": "uuid" (optional, to link existing ODPS contract),
            OR
            "original_raw": "ODPS document content" (optional, to create new ODPS contract),
            "original_format": "JSON" or "YAML" (required if original_raw provided),
            "resolve_external_refs": true (optional, default: true, only used if original_raw provided)
        }
        """
        self.check_auditor_permissions(request, "update")
        contract = self.get_object()

        # Verify contract is ODCS
        if contract.original_spec_type != OriginalSpecType.ODCS:
            return Response(
                {
                    "error": "Contract must be ODCS type for ODPS linking",
                    "code": "INVALID_CONTRACT_TYPE",
                    "details": {"contract_type": contract.original_spec_type},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Phase 227 Wave 1 (227.L8.1) — 2 MB cap on the ODPS link
        # path. Without this, large ODPS bodies could bypass the
        # contract-create cap by routing through /link-odps/.
        from .serializers import payload_size_envelope

        envelope = payload_size_envelope(request.data)
        if envelope is not None:
            return Response(envelope, status=413)
        serializer = ODPSLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        odps_contract_id = serializer.validated_data.get("odps_contract_id")
        odps_raw = serializer.validated_data.get("original_raw")
        odps_format = serializer.validated_data.get("original_format")
        resolve_external_refs = serializer.validated_data.get("resolve_external_refs", True)

        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to link contracts"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer
        try:
            service = ContractService(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                request_id=getattr(request, "request_id", None),
            )
            odps_contract = service.link_odps_to_odcs(
                odcs_contract_id=str(contract.id),
                odps_contract_id=str(odps_contract_id) if odps_contract_id else None,
                odps_raw=odps_raw,
                odps_format=odps_format,
                resolve_external_refs=resolve_external_refs,
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
            )

            return Response(ContractSerializer(odps_contract).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except NotFoundError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            # Log the full exception for debugging
            import logging
            import traceback

            logger = logging.getLogger(__name__)
            logger.error(f"ODPS linking failed: {e!s}\n{traceback.format_exc()}", exc_info=True)
            return Response(
                {
                    "error": "ODPS linking failed",
                    "code": "INTERNAL_ERROR",
                    "details": {"error": str(e), "type": type(e).__name__},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Unlink ODPS from ODCS contract",
        description="Remove the bidirectional link between an ODCS contract and its linked ODPS contract.",
        request=None,
        responses={
            200: OpenApiResponse(description="Successfully unlinked"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Linking"],
    )
    @action(detail=True, methods=["post"], url_path="unlink-odps")
    @transaction.atomic
    def unlink_odps(self, request, id=None):
        """
        Unlink ODPS contract from ODCS contract.

        POST /api/v1/contracts/{id}/unlink-odps/
        """
        self.check_auditor_permissions(request, "update")
        contract = self.get_object()

        # Verify contract is ODCS
        if contract.original_spec_type != OriginalSpecType.ODCS:
            return Response(
                {
                    "error": "Contract must be ODCS type for ODPS unlinking",
                    "code": "INVALID_CONTRACT_TYPE",
                    "details": {"contract_type": contract.original_spec_type},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to unlink contracts"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer
        try:
            service = ContractService(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                request_id=getattr(request, "request_id", None),
            )
            service.unlink_odps_from_odcs(
                odcs_contract_id=str(contract.id),
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
            )

            return Response(
                {"message": "ODPS contract unlinked successfully"}, status=status.HTTP_200_OK
            )
        except ValidationError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except NotFoundError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            # Log the full exception for debugging
            import logging
            import traceback

            logger = logging.getLogger(__name__)
            logger.error(f"ODPS unlinking failed: {e!s}\n{traceback.format_exc()}", exc_info=True)
            return Response(
                {
                    "error": "ODPS unlinking failed",
                    "code": "INTERNAL_ERROR",
                    "details": {"error": str(e), "type": type(e).__name__},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="List contract links",
        description="""
        List all links for a contract (ODPS links for ODCS contracts).

        Returns linked contracts and their relationships.
        """,
        responses={
            200: OpenApiResponse(description="List of linked contracts"),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Linking"],
    )
    @action(detail=True, methods=["get"], url_path="links")
    def list_links(self, request, id=None):
        """
        List all links for a contract.

        GET /api/v1/contracts/{id}/links/

        Returns linked contracts.
        """
        contract = self.get_object()

        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to list links"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer
        try:
            service = ContractService(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                request_id=getattr(request, "request_id", None),
            )
            links = service.get_contract_links(contract_id=str(contract.id))

            return Response(links, status=status.HTTP_200_OK)
        except NotFoundError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to list links: {e!s}", exc_info=True)
            return Response(
                {
                    "error": "Failed to list links",
                    "code": "INTERNAL_ERROR",
                    "details": {"error": str(e)},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
