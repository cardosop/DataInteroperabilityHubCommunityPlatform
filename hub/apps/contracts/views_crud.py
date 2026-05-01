"""
Contract Views CRUD Operations

Core CRUD operations (create, update, destroy, list, retrieve) with caching
and pagination support.

SAVING CHECKPOINT: This module contains the core CRUD operations.
"""

from typing import Optional

from django.core.exceptions import FieldError
from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response


# Phase 227 Wave 1 (227.L4.3) — ETag / If-Match optimistic concurrency.
#
# Delegates to the shared ``CacheHeadersMiddleware`` helper
# ``generate_etag_from_model`` so the validator emitted by the middleware
# on GET responses is byte-identical to the one we check against on PATCH.
# Pre-fix, this view used a different SHA-256-based ETag, but the
# middleware overwrote it on the way out — clients received an MD5 ETag
# from the middleware and our PATCH validator computed a different
# SHA-256 ETag, producing spurious 412s.
def _contract_etag(contract) -> str:
    """Return the weak ETag for a Contract row, matching the middleware."""
    from hub.apps.api.middleware.cache_headers import generate_etag_from_model
    return generate_etag_from_model(contract)

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.services.base import (
    NotFoundError,
    PermissionError,
    ValidationError,
)
from hub.apps.core.services.base import (
    NotFoundError as ServiceNotFoundError,
)
from hub.apps.core.services.base import (
    PermissionError as ServicePermissionError,
)

from .caching import (
    cache_contract,
    cache_query_result,
    get_cached_contract,
    get_cached_query_result,
)
from .migration_manager import ContractMigrationManager
from .optimization import (
    optimize_large_contract_json,
    should_optimize_contract,
)
from .pagination import (
    get_pagination_params,
    optimize_queryset_for_pagination,
    paginate_queryset,
)
from .serializers import (
    ContractCreateSerializer,
    ContractSerializer,
    ContractUpdateSerializer,
)
from .serializers import payload_size_envelope
from .services import ContractService


# Phase 227 Wave 1 (227.L8.1) — payload-size 413 routing.
#
# Centralised at the view boundary: ``payload_size_envelope`` (in
# ``serializers.py``) returns a ready-to-respond envelope dict when the
# request body's ``original_raw`` exceeds the 2 MB cap. We check
# BEFORE serializer instantiation so:
#   * No DRF error-shape vagaries to navigate.
#   * No serializer object built for bodies we will reject.
#   * The same helper is reusable from every other write surface
#     (`/contracts/validate-draft/`, `/contracts/products/`, ODPS link).
def _check_payload_too_large(request) -> Optional[Response]:
    envelope = payload_size_envelope(request.data)
    if envelope is None:
        return None
    return Response(envelope, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)


class ContractCRUDMixin:
    """
    Mixin for Contract CRUD operations.

    Provides create, update, destroy, list, and retrieve methods with caching
    and pagination support.
    """

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new contract using workflow orchestration.

        POST /contracts
        Body: {
            "asset_id": "uuid" (optional),
            "original_raw": "contract content",
            "original_format": "JSON" or "YAML",
            "original_spec_type": "ODCS" (optional, auto-detected if not provided)
        }
        """
        self.check_auditor_permissions(request, "create")
        # Phase 227 Wave 1 (227.L8.1) — 413 fires BEFORE the serializer
        # is constructed. Cheap rejection + deterministic envelope.
        too_large = _check_payload_too_large(request)
        if too_large is not None:
            return too_large
        serializer = ContractCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        original_raw = serializer.validated_data["original_raw"]
        original_format = serializer.validated_data["original_format"]
        original_spec_type = serializer.validated_data.get("original_spec_type")
        asset_id = serializer.validated_data.get("asset_id")
        disable_external_refs = serializer.validated_data.get("disable_external_refs", False)
        remove_external_refs = serializer.validated_data.get("remove_external_refs", False)

        # Get tenant from user (relation or tenant_id so tests/API always have tenant)
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant and getattr(request.user, "tenant_id", None):
            from hub.apps.tenants.models import Tenant as TenantModel

            try:
                tenant = TenantModel.objects.get(id=request.user.tenant_id)
            except (TenantModel.DoesNotExist, ValueError, TypeError):
                tenant = None
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to create contracts"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure tenant_id is valid UUID string
        tenant_id_str = str(tenant.id) if tenant and tenant.id else None
        if not tenant_id_str:
            return Response(
                {"error": "Invalid tenant ID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer
        try:
            service = ContractService(
                tenant_id=tenant_id_str,
                user_id=str(request.user.id),
                request_id=getattr(request, "request_id", None),
            )
            contract = service.create_contract(
                original_raw=original_raw,
                original_format=original_format,
                tenant_id=tenant_id_str,
                user_id=str(request.user.id),
                asset_id=str(asset_id) if asset_id else None,
                original_spec_type=original_spec_type,
                disable_external_refs=disable_external_refs,
                remove_external_refs=remove_external_refs,
            )

            # Refresh contract from DB to ensure all fields are loaded
            contract.refresh_from_db()

            # Serialize contract with error handling
            try:
                serializer = ContractSerializer(contract)
                serializer_data = serializer.data
            except Exception as serialization_error:
                # Log the error but return the contract with minimal data
                import logging

                logger = logging.getLogger(__name__)
                logger.error(
                    f"Failed to serialize contract {contract.id}: " f"{serialization_error}",
                    exc_info=True,
                )
                # Return minimal contract data if serialization fails
                serializer_data = {
                    "id": str(contract.id),
                    "status": contract.status,
                    "original_spec_type": contract.original_spec_type,
                    "error": "Serialization failed",
                    "details": str(serialization_error),
                }

            return Response(serializer_data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details},
                status=e.http_status,
            )
        except ServiceNotFoundError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details},
                status=e.http_status,
            )
        except PermissionDenied:
            # Re-raise PermissionDenied so DRF can handle it properly (returns 403)
            raise
        except Exception as e:
            return Response(
                {
                    "error": "Contract creation failed",
                    "code": "INTERNAL_ERROR",
                    "details": {"error": str(e)},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update a contract.

        PATCH /contracts/{id}
        Body: {
            "original_raw": "updated contract content" (optional),
            "original_format": "JSON" or "YAML" (optional),
            "status": "DRAFT" | "ACTIVE" | "RETIRED" (optional)
        }
        """
        self.check_auditor_permissions(request, "update")
        contract = self.get_object()

        # Phase 227 Wave 1 (227.L4.3) — ETag / If-Match optimistic
        # concurrency. When the client supplies an ``If-Match`` header,
        # we compare against the contract's current weak ETag and return
        # HTTP 412 on mismatch. Clients that omit the header keep
        # last-write-wins semantics for backward compatibility.
        if_match = request.headers.get("If-Match") or request.META.get("HTTP_IF_MATCH")
        if if_match:
            current_etag = _contract_etag(contract)
            # Tolerate the optional weak-prefix difference (`W/"x"` vs `"x"`).
            client_tags = {t.strip() for t in if_match.split(",")}
            if current_etag not in client_tags and current_etag.lstrip("W/") not in client_tags:
                response = Response(
                    {
                        "error": "Contract has been modified since you read it",
                        "code": "PRECONDITION_FAILED",
                        "details": {
                            "current_etag": current_etag,
                            "client_etag": if_match,
                            "hint": (
                                "Re-fetch the contract to obtain the "
                                "current ETag, merge your changes, and "
                                "retry the PATCH with the fresh value."
                            ),
                        },
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
                response["ETag"] = current_etag
                return response

        # Phase 227 Wave 1 (227.L8.1) — 413 fires BEFORE the serializer
        # is constructed (same pattern as create).
        too_large = _check_payload_too_large(request)
        if too_large is not None:
            return too_large
        serializer = ContractUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to update contracts"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer for updates
        try:
            service = ContractService(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                request_id=getattr(request, "request_id", None),
            )

            # Extract update parameters
            original_raw = serializer.validated_data.get("original_raw")
            original_format = serializer.validated_data.get("original_format")
            original_spec_type = serializer.validated_data.get("original_spec_type")
            original_spec_version = serializer.validated_data.get("original_spec_version") or None
            status_value = serializer.validated_data.get("status")
            remove_external_refs = serializer.validated_data.get("remove_external_refs", False)

            # Update contract using service layer
            contract = service.update_contract(
                contract_id=str(contract.id),
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                original_raw=original_raw,
                original_format=original_format,
                original_spec_type=original_spec_type,
                original_spec_version=original_spec_version,
                status=status_value,
                remove_external_refs=remove_external_refs,
            )

            response = Response(ContractSerializer(contract).data, status=status.HTTP_200_OK)
            # Phase 227 Wave 1 (227.L4.3) — emit fresh ETag so the
            # client can chain subsequent PATCHes without a re-read.
            response["ETag"] = _contract_etag(contract)
            return response

        except ValidationError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details},
                status=e.http_status,
            )
        except NotFoundError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details},
                status=e.http_status,
            )
        except PermissionDenied:
            # Re-raise PermissionDenied so DRF can handle it properly (returns 403)
            raise
        except Exception as e:
            return Response(
                {
                    "error": "Contract update failed",
                    "code": "INTERNAL_ERROR",
                    "details": {"error": str(e)},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a contract (soft delete: set status to RETIRED).

        DELETE /contracts/{id}
        Uses ContractService.delete_contract so business rules
        (validate_contract_deletion) are invoked.
        """
        self.check_auditor_permissions(request, "destroy")
        contract = self.get_object()

        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to delete contracts"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Store contract info before deletion for audit logging
        contract_id = str(contract.id)
        contract_tenant = contract.tenant
        original_spec_type = contract.original_spec_type
        original_spec_version = contract.original_spec_version

        try:
            service = ContractService(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                request_id=getattr(request, "request_id", None),
            )
            service.delete_contract(
                contract_id=contract_id,
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
            )
        except ValidationError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details},
                status=e.http_status,
            )
        except ServiceNotFoundError as e:
            return Response(
                {"error": e.message, "code": e.code, "details": e.details},
                status=e.http_status,
            )
        except (ServicePermissionError, PermissionError) as e:
            # Handle both ServicePermissionError (from service layer) and
            # built-in PermissionError
            # The service layer raises PermissionError from
            # hub.apps.core.services.base
            return Response(
                {"error": str(e), "code": "PERMISSION_DENIED", "details": {}},
                status=status.HTTP_403_FORBIDDEN,
            )
        except PermissionDenied:
            # Re-raise PermissionDenied so DRF can handle it properly (returns 403)
            raise
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception(f"Contract deletion failed: {e}")
            return Response(
                {
                    "error": "Contract deletion failed",
                    "code": "INTERNAL_ERROR",
                    "details": {"error": str(e)},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Create audit event (non-critical - don't fail if this fails)
        try:
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_DELETED",
                actor_user=request.user,
                tenant=contract_tenant,
                resource_id=contract_id,
                details={
                    "original_spec_type": original_spec_type,
                    "original_spec_version": original_spec_version,
                },
                request=request,
            )
        except Exception as e:
            # Log audit event creation failure but don't fail the request
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to create audit event for contract deletion: {e}")

        return Response(status=status.HTTP_204_NO_CONTENT)

    def list(self, request, *args, **kwargs):
        """
        List contracts (tenant-scoped) with enhanced filtering, sorting,
        caching, and pagination.

        Features:
        - Query result caching
        - Optimized pagination
        - Performance optimizations
        """
        # Handle invalid ordering fields gracefully
        try:
            # Get tenant ID for caching
            tenant_id = None
            if hasattr(request, "user") and request.user and hasattr(request.user, "tenant_id"):
                tenant_id = str(request.user.tenant_id)

            # Build query parameters dict for cache key
            query_params = dict(request.query_params.items())

            # Check cache for query results
            if tenant_id:
                cached_result = get_cached_query_result(query_params, tenant_id)
                if cached_result:
                    results, total_count = cached_result
                    # Return cached results with pagination metadata
                    pagination_params = get_pagination_params(request)
                    page = pagination_params["page"]
                    page_size = pagination_params["page_size"]

                    # Calculate pagination metadata
                    start_idx = (page - 1) * page_size
                    end_idx = start_idx + page_size
                    paginated_results = results[start_idx:end_idx]

                    return Response(
                        {
                            "count": total_count,
                            "page": page,
                            "page_size": page_size,
                            "total_pages": (total_count + page_size - 1) // page_size,
                            "results": paginated_results,
                            "_cached": True,
                        }
                    )

            # Optimize queryset for pagination
            queryset = self.filter_queryset(self.get_queryset())

            # Phase 227 Wave 1 (227.L5.8 + 227.L9.3) —
            # ``?filter=structureless`` support, gated to TENANT_ADMIN.
            # The frontend ``ContractHealthPage`` (admin triage view)
            # calls this endpoint with ``filter=structureless`` to list
            # contracts whose normalised payload carries no resolvable
            # models or schema fields. Spec language (227.L9.3): "GET
            # /api/v1/contracts/?filter=structureless (TENANT_ADMIN-only)".
            #
            # Permission rationale: structureless contracts are an
            # operational/compliance concern (Wave 0 audit cohort).
            # Exposing the list to non-admins would leak information
            # about other users' incomplete contracts and clutter the
            # ``DATA_VIEWER`` role's normal browse view. Platform
            # admins bypass the gate via the standard ``is_platform_admin``
            # short-circuit baked into ``user.has_role``.
            #
            # Same coarse + Python-refined approach the Wave 0
            # diagnosis command uses — ``is_structureless`` refines
            # per-row to catch the ``models=[{"fields":[]}]`` corner-
            # case that the ORM cannot express directly.
            filter_kind = (request.query_params.get("filter") or "").strip().lower()
            if filter_kind == "structureless":
                user = getattr(request, "user", None)
                if user is None or not getattr(user, "is_authenticated", False):
                    return Response(
                        {
                            "error": (
                                "Authentication required to access "
                                "?filter=structureless"
                            ),
                            "code": "AUTHENTICATION_REQUIRED",
                        },
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                if not user.has_role("TENANT_ADMIN"):
                    return Response(
                        {
                            "error": (
                                "?filter=structureless requires "
                                "TENANT_ADMIN role"
                            ),
                            "code": "PERMISSION_DENIED",
                            "details": {
                                "required_roles": ["TENANT_ADMIN"],
                            },
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

                from hub.apps.contracts.structureless import (
                    is_structureless,
                )

                # Iterate the (already tenant-scoped) queryset and
                # drop rows that pass the floor predicate. Wave 0's
                # empirical staging finding: 0 structureless of 218,
                # so the linear scan is fine at MVP scale. If we ever
                # see >1k contracts/tenant we can revisit with a
                # generated column.
                offending_ids = [
                    c.id for c in queryset.iterator(chunk_size=200)
                    if is_structureless(c)
                ]
                queryset = queryset.filter(id__in=offending_ids).order_by("-updated_at")

            queryset = optimize_queryset_for_pagination(queryset)

            # Get pagination parameters
            pagination_params = get_pagination_params(request)

            # Paginate queryset
            results, pagination_meta = paginate_queryset(
                queryset,
                page=pagination_params["page"],
                page_size=pagination_params["page_size"],
                max_page_size=pagination_params["max_page_size"],
            )

            # Serialize results
            serializer = self.get_serializer(results, many=True)

            # Cache query results if tenant_id is available
            if tenant_id:
                cache_query_result(
                    query_params,
                    tenant_id,
                    serializer.data,
                    pagination_meta["count"],
                )

            # Return paginated response
            return Response(
                {
                    "count": pagination_meta["count"],
                    "page": pagination_meta["page"],
                    "page_size": pagination_meta["page_size"],
                    "total_pages": pagination_meta["total_pages"],
                    "has_next": pagination_meta["has_next"],
                    "has_previous": pagination_meta["has_previous"],
                    "next_page": pagination_meta.get("next_page"),
                    "previous_page": pagination_meta.get("previous_page"),
                    "results": serializer.data,
                }
            )
        except FieldError as e:
            # Handle invalid ordering fields gracefully
            if "ordering" in str(e).lower() or "order" in str(e).lower():
                return Response(
                    {
                        "error": f"Invalid ordering field: {str(e)}",
                        "code": "INVALID_ORDERING",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Re-raise other FieldErrors
            raise

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve contract by ID with caching support.

        Applies ON_READ migration (lazy migration) if needed.
        Supports both v1 and v2 contracts (backward compatible).

        Phase 227 Wave 1 (227.L4.3) — emits an ``ETag`` header derived
        from ``Contract.updated_at`` so clients can use ``If-Match`` on
        subsequent PATCHes for optimistic concurrency.
        """
        contract = self.get_object()
        contract_id = str(contract.id)
        # Phase 227 L4.3 — pin the resource instance on the request so
        # ``CacheHeadersMiddleware`` uses ``generate_etag_from_model``
        # (id + updated_at) instead of falling back to the response-body
        # hash. This keeps the GET ETag byte-identical to the PATCH
        # ``If-Match`` validator we compute below in ``update()``.
        # DRF wraps the WSGI request — set both so the middleware
        # (which sees the underlying ``HttpRequest``) reads it too.
        request._resource_instance = contract
        if hasattr(request, "_request"):
            request._request._resource_instance = contract
        etag = _contract_etag(contract)

        # Check cache first
        cached_data = get_cached_contract(contract_id)
        if cached_data:
            # Return cached data (but still apply migration if needed)
            serializer = self.get_serializer(contract)
            response_data = serializer.data
            response_data["hub_contract_json"] = cached_data.get(
                "hub_contract_json", contract.hub_contract_json
            )
            response_data["_cached"] = True
            response = Response(response_data)
            response["ETag"] = etag
            return response

        # Apply ON_READ migration (lazy, in-memory) for backward compatibility
        if contract.hub_contract_json and contract.hub_contract_version:
            migrated_hub_contract, migration_warnings = ContractMigrationManager.migrate_on_read(
                contract
            )

            # If migration was applied, return migrated version in response
            # (but don't update DB - that's the lazy part)
            if migrated_hub_contract != contract.hub_contract_json:
                # Create a temporary serializer with migrated contract
                serializer = self.get_serializer(contract)
                response_data = serializer.data
                # Override hub_contract_json with migrated version
                response_data["hub_contract_json"] = migrated_hub_contract
                if migration_warnings:
                    response_data["migration_warnings"] = migration_warnings

                # Cache the migrated contract
                cache_contract(
                    contract_id,
                    {
                        "hub_contract_json": migrated_hub_contract,
                        "status": contract.status,
                        "normalization_status": contract.normalization_status,
                    },
                )

                response = Response(response_data)
                response["ETag"] = etag
                return response

        # Cache the contract for future requests
        if contract.hub_contract_json:
            # Optimize large JSON before caching
            if should_optimize_contract(contract.hub_contract_json):
                optimized_json = optimize_large_contract_json(contract.hub_contract_json)
                cache_contract(
                    contract_id,
                    {
                        "hub_contract_json": optimized_json,
                        "status": contract.status,
                        "normalization_status": contract.normalization_status,
                    },
                )
            else:
                cache_contract(
                    contract_id,
                    {
                        "hub_contract_json": contract.hub_contract_json,
                        "status": contract.status,
                        "normalization_status": contract.normalization_status,
                    },
                )

        # Support both v1 and v2 contracts
        # API handles both versions transparently
        response = super().retrieve(request, *args, **kwargs)
        # Phase 227 Wave 1 (227.L4.3) — attach the ETag last so the
        # super() default response carries the optimistic-concurrency
        # validator regardless of which branch produced it.
        try:
            response["ETag"] = etag
        except Exception:
            # Defensive: if super() returned something unexpected
            # (StreamingHttpResponse subclass, etc.), don't break the
            # endpoint — just skip the header.
            pass
        return response

    # ------------------------------------------------------------------
    # Phase 227 Wave 1 (227.L5.4) — JSON Schema endpoint
    # ------------------------------------------------------------------

    @action(
        detail=False,
        methods=["get"],
        url_path="schema/json-schema",
        url_name="schema-json-schema",
        # Phase 227 Wave 1 (227.L9.2) — IANA-registered media type for
        # JSON Schema documents. Setting this on the action's
        # ``renderer_classes`` is the canonical DRF pattern; setting
        # ``response["Content-Type"]`` directly is overwritten when
        # ``Response.render()`` finalises the response from
        # ``self.accepted_renderer.media_type``. See:
        # https://www.django-rest-framework.org/api-guide/renderers/#custom-renderers
        renderer_classes=[
            __import__(
                "hub.apps.contracts.renderers_schema_json",
                fromlist=["JSONSchemaRenderer"],
            ).JSONSchemaRenderer,
        ],
        # Phase 227 Wave 1 (227.L9.2 audit follow-up) — RFC 6839
        # +json suffix-aware negotiation so clients sending
        # ``Accept: application/json`` (the most common default for
        # JS fetch / curl) match ``application/schema+json`` instead
        # of getting HTTP 406 Not Acceptable. The server upgrades
        # the response type per RFC 7231 §3.1.1.5; the
        # ``Content-Type`` header still carries the IANA-typed
        # ``application/schema+json`` for clients that branch on it.
        content_negotiation_class=__import__(
            "hub.apps.contracts.renderers_schema_json",
            fromlist=["StructuredSuffixContentNegotiation"],
        ).StructuredSuffixContentNegotiation,
    )
    @extend_schema(
        # Phase 227 Wave 1 (227.L9.4 audit follow-up) — drf-spectacular
        # does NOT auto-discover error codes from runtime
        # ``ValidationError`` raises. Annotate explicitly so the
        # OpenAPI snapshot carries the contract a typed client
        # (frontend, ajv, ops scripts) needs.
        tags=["Contracts"],
        summary="Get HubContract JSON Schema",
        description=(
            "Returns the canonical JSON Schema describing a valid "
            "HubContract payload. The frontend Schema editor "
            "(227.L5.5) fetches this at load to drive client-side "
            "validation. Response media type: "
            "``application/schema+json`` (IANA-registered)."
        ),
        responses={
            200: OpenApiResponse(
                description=(
                    "JSON Schema document with ``{spec, schema}`` "
                    "wrapper. Content-Type: application/schema+json."
                ),
            ),
            400: OpenApiResponse(
                description=(
                    "Invalid ``spec`` query parameter. ``code`` will "
                    "be ``INVALID_SPEC``."
                ),
            ),
        },
    )
    def schema_json_schema(self, request):
        """Return the JSON Schema describing valid HubContract payloads.

        ``GET /api/v1/contracts/schema/json-schema/?spec=<odcs|odps>``

        The frontend Schema editor (Phase 227 L5.5) fetches this at load
        and uses it to drive client-side field-level validation —
        rejecting empty model names, duplicate fields within a model,
        and ``object``-typed fields with no nested ``fields[]`` BEFORE
        the user clicks Save. The schema returned is derived from the
        canonical ``HubContractModel.model_json_schema()`` so server +
        client speak the same Pydantic-defined contract.

        Query params
        ------------
        * ``spec`` — optional, ``odcs`` or ``odps``. Reserved for future
          spec-specific narrowing; currently both values return the
          same canonical HubContract schema (the editor compiles to
          either ODCS or ODPS source via the client-side compiler).

        Response
        --------
        ::

            {
              "spec": "odcs" | "odps" | null,
              "schema": <JSON-Schema dict>
            }
        """
        spec = (request.query_params.get("spec") or "").strip().lower() or None
        if spec is not None and spec not in ("odcs", "odps"):
            return Response(
                {
                    "error": "Invalid 'spec' query parameter",
                    "code": "INVALID_SPEC",
                    "details": {
                        "spec": spec,
                        "allowed": ["odcs", "odps"],
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        from hub.apps.contracts.typed_models import HubContractModel
        try:
            json_schema = HubContractModel.model_json_schema(by_alias=True)
        except Exception as exc:  # pragma: no cover — defensive
            return Response(
                {
                    "error": "Failed to build HubContract JSON Schema",
                    "code": "SCHEMA_BUILD_FAILED",
                    "details": {"error": str(exc)},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        # Phase 227 Wave 1 (227.L9.2) — content-type is
        # ``application/schema+json`` per IANA, set via the
        # ``JSONSchemaRenderer`` configured in ``renderer_classes`` on
        # the @action decorator above. The body shape stays
        # ``{spec, schema}`` so the existing 227.L5.5 frontend reader
        # doesn't change.
        return Response({"spec": spec, "schema": json_schema})

    # ------------------------------------------------------------------
    # Phase 228.F2 — Field-level lineage editor
    # REQ-LIN-F2-001 / F2-002 — PATCH /api/v1/contracts/{id}/lineage/
    # ------------------------------------------------------------------

    @action(
        detail=True,
        methods=["patch"],
        url_path="lineage",
        url_name="contract-lineage-edit",
    )
    def lineage_edit(self, request, *args, **kwargs):
        """``PATCH /api/v1/contracts/{id}/lineage/`` — full-state lineage edit.

        Request body shape (validated by :class:`LineageEditPatchSerializer`)::

            {
              "edges": [
                {
                  "source_contract": "<uuid>",
                  "source_model": "orders",
                  "source_field": "customer_id",
                  "target_contract": "<uuid>",
                  "target_model": "customer_aggregates",
                  "target_field": "customer_id",
                  "edge_type": "transformation",
                  "transformation_ref": "dbt_orders_v1",
                  "job_ref": "airflow_run_42"
                },
                ...
              ]
            }

        The full edge list is the desired post-patch state.  The view
        diffs against the current open edges, closes removed ones,
        opens new ones, and re-serialises ``hub_contract_json.lineage``.

        Concurrency: ``If-Match`` (REQ-LIN-F2-002).  Idempotency:
        ``Idempotency-Key`` cached 24h via the existing bug-prevention
        idempotency layer.  Cap: 1000 edges per patch (413 over).

        RBAC (F2.10): platform admin OR same-tenant tenant admin OR
        same-tenant user with ``EDIT_LINEAGE`` permission OR contract
        owner.  Returns 403 ``EDIT_LINEAGE_FORBIDDEN`` otherwise.
        """
        from hub.apps.contracts.lineage_edit_service import (
            apply_lineage_patch,
        )
        from hub.apps.contracts.lineage_edit_serializers import (
            LineageEditPatchSerializer,
        )
        from hub.apps.contracts.permissions_lineage import (
            require_edit_lineage,
        )

        # Resolve contract + RBAC.
        try:
            contract = self.get_queryset().get(id=kwargs["id"])
        except self.queryset.model.DoesNotExist:
            return Response(
                {"detail": "Not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            require_edit_lineage(request.user, contract)
        except Exception as exc:
            from rest_framework.exceptions import PermissionDenied
            if isinstance(exc, PermissionDenied):
                return Response(
                    exc.detail
                    if isinstance(exc.detail, dict)
                    else {"error": str(exc.detail), "code": "EDIT_LINEAGE_FORBIDDEN"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            raise

        # ETag concurrency check (F2.4 / REQ-LIN-F2-002).  We reuse
        # the existing _contract_etag helper that's load-bearing for
        # the Phase 227 L4.3 contract-update path.
        if_match = request.headers.get("If-Match") or request.META.get(
            "HTTP_IF_MATCH",
        )
        current_etag = _contract_etag(contract)
        if if_match and if_match.strip() != current_etag:
            return Response(
                {
                    "error": "Precondition failed: If-Match ETag mismatch",
                    "code": "PRECONDITION_FAILED",
                    "details": {
                        "expected_etag": current_etag,
                        "received_etag": if_match,
                    },
                },
                status=status.HTTP_412_PRECONDITION_FAILED,
                headers={"ETag": current_etag},
            )

        # Serializer (cap 1000 edges, structural validation).
        serializer = LineageEditPatchSerializer(data=request.data)
        if not serializer.is_valid():
            errs = serializer.errors
            # Surface the typed PAYLOAD_TOO_LARGE code as 413 instead
            # of the default 400 — the REQ-LIN-F2-002 contract.
            edges_err = errs.get("edges")
            if (
                isinstance(edges_err, list)
                and edges_err
                and isinstance(edges_err[0], dict)
                and edges_err[0].get("code") == "PAYLOAD_TOO_LARGE"
            ):
                return Response(
                    edges_err[0],
                    status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )
            return Response(errs, status=status.HTTP_400_BAD_REQUEST)

        # Idempotency-Key (24h cached response per the existing
        # bug-prevention service, F2.4).  When the same
        # (tenant, key, method, path) tuple replays we return the
        # cached response without re-applying the patch.  Optional
        # header — caller-driven.  Uses the existing
        # ``IdempotencyService.check_idempotency`` /
        # ``store_idempotency`` API from
        # ``hub/apps/core/bug_prevention/services.py``.
        idempotency_key = request.headers.get(
            "Idempotency-Key"
        ) or request.META.get("HTTP_IDEMPOTENCY_KEY")
        cached_response = None
        if idempotency_key:
            try:
                from hub.apps.core.bug_prevention.services import (
                    IdempotencyService,
                )
                _, cached_response = IdempotencyService.check_idempotency(
                    tenant_id=str(getattr(request.user, "tenant_id", "")),
                    idempotency_key=idempotency_key,
                    method="PATCH",
                    path=request.path,
                    body=request.data,
                )
            except Exception:  # pragma: no cover — best-effort
                cached_response = None
            if cached_response is not None:
                return Response(
                    cached_response.get("data") if isinstance(cached_response, dict) else cached_response,
                    status=status.HTTP_200_OK,
                    headers={"X-Idempotent-Replay": "true"},
                )

        # Apply the patch (single tx; SERIALIZABLE; audit per edge).
        try:
            result = apply_lineage_patch(
                contract=contract,
                desired_edges=serializer.validated_data["edges"],
                user=request.user,
            )
        except Exception as exc:
            from rest_framework.exceptions import ValidationError as _Validate
            from hub.apps.core.services.base import (
                ConflictError,
                ValidationError as ServiceValidate,
            )

            if isinstance(exc, ConflictError):
                return Response(
                    {
                        "error": str(exc),
                        "code": getattr(exc, "code", "CONFLICT"),
                        "details": getattr(exc, "details", {}),
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if isinstance(exc, (ServiceValidate, _Validate)):
                # Validator findings (cycle, field-not-found, type-mismatch).
                details = getattr(exc, "details", None) or getattr(
                    exc, "detail", None
                ) or {"error": str(exc)}
                return Response(
                    details,
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise

        # Cache the response under the idempotency key.
        if idempotency_key:
            try:
                from hub.apps.core.bug_prevention.services import (
                    IdempotencyService,
                )
                IdempotencyService.store_idempotency(
                    tenant_id=str(getattr(request.user, "tenant_id", "")),
                    idempotency_key=idempotency_key,
                    method="PATCH",
                    path=request.path,
                    body=request.data,
                    response_status=200,
                    response_body=result,
                )
            except Exception:  # pragma: no cover — best-effort
                pass

        # ETag of the post-patch contract — the client uses this on
        # the next round-trip's If-Match.
        contract.refresh_from_db()
        new_etag = _contract_etag(contract)
        return Response(
            result,
            status=status.HTTP_200_OK,
            headers={"ETag": new_etag},
        )
