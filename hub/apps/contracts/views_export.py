"""
Contract Views Export Operations

Export, download, and ODPS generation actions for contract viewsets.

SAVING CHECKPOINT: This module contains export-related actions.
This file is large (>2000 lines) and contains three major methods:
1. export_contract (lines ~50-700): Export contract in various formats
2. download_contract (lines ~700-1400): Download contract as file
3. generate_odps (lines ~1400-2000): Generate ODPS document from HubContract
"""

import time

from django.http import Http404, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from hub.apps.observability.otel_metrics import (
    odcs_export_duration_seconds,
    odcs_export_size_bytes,
    odcs_export_total,
    odps_export_duration_seconds,
    odps_export_size_bytes,
    odps_export_total,
)

from .models import Contract, OriginalSpecType
from .normalization import parse_contract
from .views_helpers import _categorize_export_size, _get_tenant_id_from_request


class ContractExportMixin:
    """
    Mixin for Contract export, download, and ODPS generation operations.

    Provides export, download, and ODPS generation endpoints.
    """

    @action(detail=True, methods=["get"], url_path="export")
    def export_contract(self, request, id=None):
        # ROOT CAUSE FIX: Ensure self.request and self.kwargs are set correctly
        # This is critical for custom URL handlers where these might not be set properly
        # DRF normally sets these in initial(), but custom handlers might not call it
        self.request = request
        # Ensure kwargs contains 'id' if passed as parameter
        # CRITICAL: get_object() uses self.kwargs[lookup_url_kwarg] to get the ID
        # So we must ensure 'id' is in self.kwargs
        if not hasattr(self, "kwargs") or not self.kwargs:
            self.kwargs = {}
        # If 'id' is passed as parameter but not in kwargs, add it
        if id and "id" not in self.kwargs:
            self.kwargs["id"] = id
        # Also ensure lookup_url_kwarg is set (get_object() uses it)
        if not hasattr(self, "lookup_url_kwarg") or not self.lookup_url_kwarg:
            self.lookup_url_kwarg = "id"
        if not hasattr(self, "lookup_field") or not self.lookup_field:
            self.lookup_field = "id"
        """
        Export a contract in various formats.

        GET /contracts/{id}/export/
        Query params:
        - format: odps|odcs|hubcontract (default: hubcontract)
        - output_format: yaml|json (default: json)

        Returns contract content in requested format.
        """
        # CRITICAL: Disable format suffix handling for this endpoint
        # This prevents DRF from trying to interpret ?format=hubcontract as a format suffix
        # Store original format_kwarg and set to None
        original_format_kwarg = getattr(self, "format_kwarg", None)
        self.format_kwarg = None

        try:
            # get_object() may raise Http404 - let it propagate to be handled by DRF's exception handler
            import logging
            import os

            from django.http import Http404

            logger = logging.getLogger(__name__)

            # ROOT CAUSE FIX: Ensure tenant_id is set on request before calling get_object()
            # This is critical for custom URL handlers where middleware might not have run
            # The get_object() override also does this, but doing it here ensures it's set before get_queryset() is called
            if not hasattr(self.request, "tenant_id") or not self.request.tenant_id:
                if (
                    hasattr(self.request, "user")
                    and self.request.user
                    and not self.request.user.is_anonymous
                ):
                    from django.contrib.auth import get_user_model

                    User = get_user_model()
                    try:
                        db_user = User.objects.only("tenant_id").get(id=self.request.user.id)
                        if db_user.tenant_id:
                            self.request.tenant_id = db_user.tenant_id  # UUID from database
                    except User.DoesNotExist:
                        pass

            # Ensure tenant_id is UUID (not string) for proper filtering in get_queryset()
            if hasattr(self.request, "tenant_id") and self.request.tenant_id:
                import uuid

                if isinstance(self.request.tenant_id, str):
                    try:
                        self.request.tenant_id = uuid.UUID(self.request.tenant_id)
                    except (ValueError, TypeError):
                        pass

            # ROOT CAUSE FIX: Try get_object() first (proper tenant filtering)
            # If it fails, use manual retrieval as fallback for robustness
            contract = None
            contract_id = self.kwargs.get("id") or self.kwargs.get("pk")

            try:
                contract = self.get_object()
            except Http404:
                # ROOT CAUSE FIX: If get_object() fails, try manual retrieval as fallback
                # This provides robustness for custom URL handlers where viewset initialization might differ
                if contract_id:
                    # Get tenant_id from request or user
                    tenant_id = None
                    if hasattr(self.request, "tenant_id") and self.request.tenant_id:
                        tenant_id = self.request.tenant_id
                    elif (
                        hasattr(self.request, "user")
                        and self.request.user
                        and not self.request.user.is_anonymous
                    ):
                        from django.contrib.auth import get_user_model

                        User = get_user_model()
                        try:
                            db_user = User.objects.only("tenant_id").get(id=self.request.user.id)
                            if db_user.tenant_id:
                                tenant_id = db_user.tenant_id
                        except User.DoesNotExist:
                            pass

                    if tenant_id:
                        try:
                            # Try to get contract directly with tenant_id filter
                            import uuid

                            if isinstance(tenant_id, str):
                                tenant_id = uuid.UUID(tenant_id)
                            if isinstance(contract_id, str):
                                try:
                                    contract_id = uuid.UUID(contract_id)
                                except (ValueError, TypeError):
                                    pass

                            contract = Contract.objects.get(id=contract_id, tenant_id=tenant_id)
                        except (Contract.DoesNotExist, ValueError, TypeError):
                            # Re-raise Http404 if contract not found
                            raise Http404("Contract not found")
                    else:
                        raise Http404("Contract not found: No tenant_id available")
                else:
                    raise Http404("Contract ID is required")

            # Ensure contract was retrieved
            if contract is None:
                raise Http404("Contract not found")

            # Get format parameter (default: hubcontract)
            # CRITICAL: Check query parameter FIRST before any format suffix handling
            # This ensures ?format=hubcontract works even if DRF tries to interpret it as a suffix
            if hasattr(request, "query_params"):
                format_type = request.query_params.get("format", "hubcontract").lower().strip()
            elif hasattr(request, "GET"):
                format_type = request.GET.get("format", "hubcontract").lower().strip()
            else:
                format_type = "hubcontract"

            if format_type not in ["odps", "odcs", "hubcontract"]:
                return Response(
                    {
                        "error": f"Invalid format: {format_type}. Must be one of: odps, odcs, hubcontract"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get output_format parameter (default: json)
            if hasattr(request, "query_params"):
                output_format = request.query_params.get("output_format", "json").lower().strip()
            elif hasattr(request, "GET"):
                output_format = request.GET.get("output_format", "json").lower().strip()
            else:
                output_format = "json"

            if output_format not in ["yaml", "json"]:
                return Response(
                    {
                        "error": f"Invalid output_format: {output_format}. Must be one of: yaml, json"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get version parameter (used for ODPS and ODCS formats)
            # For ODPS: default is "4.1"
            # For ODCS: default is detected from contract or "3.0.2"
            version_param = None
            if hasattr(request, "query_params"):
                version_param = request.query_params.get("version", "").strip()
            elif hasattr(request, "GET"):
                version_param = request.GET.get("version", "").strip()

            # Set defaults based on format type
            if format_type == "odps":
                odps_version = version_param if version_param else "4.1"
                odcs_version = None
            elif format_type == "odcs":
                odcs_version = version_param if version_param else None
                odps_version = None
            else:
                odps_version = None
                odcs_version = None

            # Handle different format types
            if format_type == "hubcontract":
                # Export as HubContract format
                if not contract.hub_contract_json:
                    return Response(
                        {
                            "error": "Contract has no hub_contract_json. Cannot export as HubContract format."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                contract_data = contract.hub_contract_json

                # Format output
                if output_format == "yaml":
                    from django.http import HttpResponse

                    from hub.apps.contracts.odps_generator import format_odps_as_yaml

                    try:
                        # Use ODPS formatter for YAML (works for any dict)
                        output = format_odps_as_yaml(contract_data)
                        # Use Django's HttpResponse directly to avoid DRF's JSON serialization
                        return HttpResponse(output, content_type="application/x-yaml")
                    except Exception as e:
                        return Response(
                            {"error": f"Failed to format as YAML: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
                else:  # json
                    # Return as JSON (DRF will serialize it automatically)
                    return Response(contract_data, content_type="application/json")

            elif format_type == "odcs":
                # Export as ODCS format (Task 9.5.4.1.4.1)
                # Prefer original_raw if available and matches requested version, otherwise generate

                # Get tenant_id for metrics
                tenant_id = _get_tenant_id_from_request(request)

                # Validate ODCS version if provided
                if odcs_version:
                    try:
                        from hub.apps.contracts.odcs_validation import validate_odcs_version

                        validate_odcs_version(odcs_version)
                    except Exception as e:
                        # Record failure metric
                        try:
                            odcs_export_total.labels(
                                status="failure",
                                format=output_format,
                                version=odcs_version or "unknown",
                                tenant_id=tenant_id,
                            ).inc()
                        except Exception:
                            pass  # Don't fail on metrics recording
                        return Response(
                            {"error": f"Invalid ODCS version: {str(e)}"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                # Start timing for export duration metric
                export_start_time = time.time()

                try:
                    from hub.apps.contracts.odcs_errors import (
                        ODCSExportError,
                        ODCSGenerationError,
                    )
                    from hub.apps.contracts.odcs_format_converter import (
                        format_odcs_as_json,
                        format_odcs_as_yaml,
                    )
                    from hub.apps.contracts.odcs_generator import (
                        generate_odcs_from_hubcontract,
                    )
                    from hub.apps.contracts.odcs_version_detection import detect_odcs_version

                    odcs_doc = None
                    final_version = None
                    use_original = False

                    # Check if original_raw is available and matches requested version
                    # original_raw can be empty string, so check for truthiness and non-empty
                    if (
                        contract.original_raw
                        and contract.original_raw.strip()
                        and contract.original_spec_type == OriginalSpecType.ODCS
                    ):
                        try:
                            # Parse original contract to detect version
                            original_contract_data = parse_contract(
                                contract.original_raw, contract.original_format
                            )
                            original_version = detect_odcs_version(original_contract_data)

                            # Use original if:
                            # 1. No version requested (use original version)
                            # 2. Requested version matches original version
                            if not odcs_version or original_version == odcs_version:
                                odcs_doc = original_contract_data
                                final_version = (
                                    original_version
                                    if original_version != "unknown"
                                    else (odcs_version or "3.0.2")
                                )
                                use_original = True
                            else:
                                # Version mismatch - need to generate
                                final_version = odcs_version
                        except Exception as e:
                            # If parsing fails, fall through to generation
                            logger.warning(
                                f"Failed to parse original ODCS contract: {str(e)}, will generate instead"
                            )

                    # Generate from HubContract if original not used
                    if not use_original:
                        # ROOT CAUSE FIX: Check if hub_contract_json exists and is not empty
                        # Empty dict {} is falsy but we want to attempt generation to get proper error
                        if contract.hub_contract_json is None:
                            # Record failure metric
                            try:
                                odcs_export_total.labels(
                                    status="failure",
                                    format=output_format,
                                    version=odcs_version or "unknown",
                                    tenant_id=tenant_id,
                                ).inc()
                            except Exception:
                                pass
                            return Response(
                                {
                                    "error": "Contract has no original_raw or hub_contract_json. Cannot export as ODCS format."
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                        # Generate ODCS from HubContract
                        # ROOT CAUSE FIX: Attempt generation even if hub_contract_json is empty/invalid
                        # This allows proper error handling (500) for generation failures vs missing data (400)
                        try:
                            odcs_doc = generate_odcs_from_hubcontract(
                                hub_contract=contract.hub_contract_json,
                                target_version=odcs_version,
                                tenant_id=tenant_id,
                            )
                            # Detect final version from generated document
                            final_version = detect_odcs_version(odcs_doc)
                            if final_version == "unknown":
                                final_version = odcs_version or "3.0.2"
                        except ODCSGenerationError as e:
                            # Record failure metric
                            try:
                                odcs_export_total.labels(
                                    status="failure",
                                    format=output_format,
                                    version=odcs_version or "unknown",
                                    tenant_id=tenant_id,
                                ).inc()
                            except Exception:
                                pass
                            return Response(
                                {
                                    "error": f"Failed to generate ODCS document: {str(e)}",
                                    "details": getattr(e, "context", {}),
                                },
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            )
                        except Exception as e:
                            # Record failure metric
                            try:
                                odcs_export_total.labels(
                                    status="failure",
                                    format=output_format,
                                    version=odcs_version or "unknown",
                                    tenant_id=tenant_id,
                                ).inc()
                            except Exception:
                                pass
                            logger.error(f"Failed to generate ODCS export: {str(e)}", exc_info=True)
                            return Response(
                                {"error": f"Failed to generate ODCS export: {str(e)}"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            )

                    # Format output
                    # Ensure odcs_doc is not None (should never happen, but safety check)
                    if odcs_doc is None:
                        # Record failure metric
                        try:
                            odcs_export_total.labels(
                                status="failure",
                                format=output_format,
                                version=final_version or "unknown",
                                tenant_id=tenant_id,
                            ).inc()
                        except Exception:
                            pass
                        return Response(
                            {"error": "Failed to generate ODCS document: document is None"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

                    try:
                        if output_format == "yaml":
                            output = format_odcs_as_yaml(odcs_doc)
                            content_type = "application/x-yaml"
                        else:  # json
                            output = format_odcs_as_json(odcs_doc)
                            content_type = "application/json"
                    except ODCSExportError as e:
                        # Record failure metric
                        try:
                            odcs_export_total.labels(
                                status="failure",
                                format=output_format,
                                version=final_version or "unknown",
                                tenant_id=tenant_id,
                            ).inc()
                        except Exception:
                            pass
                        return Response(
                            {
                                "error": f"Failed to format ODCS document: {str(e)}",
                                "details": getattr(e, "context", {}),
                            },
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
                    except Exception as e:
                        # Record failure metric
                        try:
                            odcs_export_total.labels(
                                status="failure",
                                format=output_format,
                                version=final_version or "unknown",
                                tenant_id=tenant_id,
                            ).inc()
                        except Exception:
                            pass
                        logger.error(f"Failed to format ODCS export: {str(e)}", exc_info=True)
                        return Response(
                            {"error": f"Failed to format ODCS export: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

                    # Calculate export duration and size for metrics
                    export_duration = time.time() - export_start_time
                    export_size_bytes = len(output.encode("utf-8"))
                    size_category = _categorize_export_size(export_size_bytes)

                    # Record metrics (Task 9.5.4.1.4.1)
                    try:
                        odcs_export_duration_seconds.labels(
                            format=output_format,
                            size_category=size_category,
                            version=final_version or "unknown",
                            tenant_id=tenant_id,
                        ).observe(export_duration)

                        odcs_export_size_bytes.labels(
                            format=output_format,
                            version=final_version or "unknown",
                            tenant_id=tenant_id,
                        ).observe(export_size_bytes)

                        # Record export success
                        odcs_export_total.labels(
                            status="success",
                            format=output_format,
                            version=final_version or "unknown",
                            tenant_id=tenant_id,
                        ).inc()
                    except Exception:
                        pass  # Don't fail on metrics recording

                    # Return response
                    if output_format == "yaml":
                        from django.http import HttpResponse

                        return HttpResponse(output, content_type=content_type)
                    else:
                        # For JSON, parse back to dict for DRF serialization
                        import json

                        contract_data = json.loads(output)
                        return Response(contract_data, content_type=content_type)

                except Exception as e:
                    # Record failure metric
                    try:
                        odcs_export_total.labels(
                            status="failure",
                            format=output_format if "output_format" in locals() else "unknown",
                            version=odcs_version or "unknown",
                            tenant_id=tenant_id,
                        ).inc()
                    except Exception:
                        pass
                    logger.error(f"ODCS export endpoint error: {str(e)}", exc_info=True)
                    return Response(
                        {"error": f"ODCS export failed: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            elif format_type == "odps":
                # Export as ODPS format
                if not contract.hub_contract_json:
                    return Response(
                        {
                            "error": "Contract has no hub_contract_json. Cannot export as ODPS format."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Generate ODPS from HubContract
                from hub.apps.contracts.odps_generator import (
                    format_odps_as_json,
                    format_odps_as_yaml,
                    generate_odps_from_hubcontract,
                )

                # Get tenant_id for metrics (Task 6.6.1)
                tenant_id = _get_tenant_id_from_request(request)

                try:
                    # Start timing for export duration metric (Task 6.6.1)
                    export_start_time = time.time()

                    # Get original ODCS contract if available (for embedding in ODPS)
                    original_odcs_contract = None
                    if (
                        contract.original_raw
                        and contract.original_spec_type == OriginalSpecType.ODCS
                    ):
                        try:
                            # parse_contract is now imported at the top of the file
                            original_odcs_contract = parse_contract(
                                contract.original_raw, contract.original_format
                            )
                        except Exception:
                            # If parsing fails, continue without original ODCS
                            pass

                    # Generate ODPS document
                    # ROOT CAUSE FIX: Ensure target_version is a string (not None)
                    # generate_odps_from_hubcontract expects str, not Optional[str]
                    odps_target_version = odps_version if odps_version else "4.1"
                    odps_doc = generate_odps_from_hubcontract(
                        hub_contract=contract.hub_contract_json,
                        target_version=odps_target_version,
                        original_odcs_contract=original_odcs_contract,
                        original_odcs_url=None,
                    )

                    # Format output
                    if output_format == "yaml":
                        output = format_odps_as_yaml(odps_doc)
                        content_type = "application/x-yaml"
                    else:  # json
                        output = format_odps_as_json(odps_doc)
                        content_type = "application/json"

                    # Calculate export duration and size for metrics (Task 6.6.1)
                    export_duration = time.time() - export_start_time
                    export_size_bytes = len(output.encode("utf-8"))
                    size_category = _categorize_export_size(export_size_bytes)

                    # Record metrics (Task 6.6.1, 6.6.4)
                    odps_export_duration_seconds.labels(
                        format=output_format, size_category=size_category, tenant_id=tenant_id
                    ).observe(export_duration)

                    odps_export_size_bytes.labels(
                        format=output_format, tenant_id=tenant_id
                    ).observe(export_size_bytes)

                    # Record export success (Task 6.6.4)
                    odps_export_total.labels(
                        status="success", format=output_format, tenant_id=tenant_id
                    ).inc()

                    return Response(output, content_type=content_type)

                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to generate ODPS export: {str(e)}", exc_info=True)

                    # Record export failure (Task 6.6.4)
                    try:
                        odps_export_total.labels(
                            status="failure",
                            format=output_format if "output_format" in locals() else "unknown",
                            tenant_id=tenant_id,
                        ).inc()
                    except Exception:
                        pass  # Don't fail on metrics recording

                    return Response(
                        {"error": f"Failed to generate ODPS export: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

        except Http404:
            # Re-raise Http404 so it can be handled by DRF's exception handler
            # This ensures proper 404 responses instead of 500 errors
            raise
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Export endpoint error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Export failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            # Restore original format_kwarg
            if "original_format_kwarg" in locals():
                if original_format_kwarg is not None:
                    self.format_kwarg = original_format_kwarg
                else:
                    # If it was None originally, we might need to restore it differently
                    # But for now, just leave it as None since we disabled it
                    pass

    @extend_schema(
        summary="Download contract",
        description="""
        Download a contract as a file in various formats (ODPS, ODCS, HubContract).

        **Format Options:**
        - `odps`: Download as ODPS (Open Data Product Standard) format
        - `odcs`: Download as ODCS (Open Data Contract Standard) format (original or generated)
        - `hubcontract`: Download as HubContract format (normalized internal format)

        **Output Format Options:**
        - `yaml`: Download in YAML format
        - `json`: Download in JSON format

        **Query Parameters:**
        - `format` (optional): Specify the desired output format. Defaults to `hubcontract`.
        - `output_format` (optional): Specify the desired serialization format (yaml or json). Defaults to `json`.
        - `version` (optional): Specify the version for ODPS or ODCS format. For ODPS, defaults to `4.1`. For ODCS, defaults to detected version or `3.0.2`.

        **Behavior:**
        - For `odcs` format: Returns original_raw if available and matches requested version, otherwise generates from HubContract
        - For `odps` format: Generates ODPS document from HubContract
        - For `hubcontract` format: Returns hub_contract_json directly

        Returns a file download with appropriate Content-Disposition header (filename includes version for ODCS format).
        """,
        parameters=[
            OpenApiParameter(
                name="format",
                type=OpenApiTypes.STR,
                enum=["odps", "odcs", "hubcontract"],
                description="Desired contract format for download.",
                default="hubcontract",
            ),
            OpenApiParameter(
                name="output_format",
                type=OpenApiTypes.STR,
                enum=["yaml", "json"],
                description="Desired output serialization format.",
                default="json",
            ),
            OpenApiParameter(
                name="version",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Version for download (e.g., ODPS 4.1, ODCS 3.0.2). Only used when format=odps or format=odcs (default: latest for format)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description="Contract file downloaded successfully.",
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Invalid format or output_format specified.",
            ),
            404: OpenApiResponse(response=OpenApiTypes.OBJECT, description="Contract not found."),
            500: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Internal server error during download.",
            ),
        },
    )

    # SAVING CHECKPOINT: End of export_contract method (~680 lines).
    # Starting download_contract method (~680-1200 lines).

    @action(detail=True, methods=["get"], url_path="download")
    def download_contract(self, request, id=None):
        """
        Download a contract as a file in various formats.

        GET /contracts/{id}/download/
        Query params:
        - format: odps|odcs|hubcontract (default: hubcontract)
        - output_format: yaml|json (default: json)

        Returns contract file with Content-Disposition header for download.
        """
        # CRITICAL: Disable format suffix handling for this endpoint
        # This prevents DRF from trying to interpret ?format=hubcontract as a format suffix
        # Store original format_kwarg and set to None
        original_format_kwarg = getattr(self, "format_kwarg", None)
        self.format_kwarg = None

        try:
            # get_object() may raise Http404 - let it propagate to be handled by DRF's exception handler
            from django.http import Http404, HttpResponse

            contract = self.get_object()

            # Get format parameter (default: hubcontract)
            # CRITICAL: Check query parameter FIRST before any format suffix handling
            # This ensures ?format=hubcontract works even if DRF tries to interpret it as a suffix
            if hasattr(request, "query_params"):
                format_type = request.query_params.get("format", "hubcontract").lower().strip()
            elif hasattr(request, "GET"):
                format_type = request.GET.get("format", "hubcontract").lower().strip()
            else:
                format_type = "hubcontract"

            if format_type not in ["odps", "odcs", "hubcontract"]:
                return Response(
                    {
                        "error": f"Invalid format: {format_type}. Must be one of: odps, odcs, hubcontract"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get output_format parameter (default: json)
            if hasattr(request, "query_params"):
                output_format = request.query_params.get("output_format", "json").lower().strip()
            elif hasattr(request, "GET"):
                output_format = request.GET.get("output_format", "json").lower().strip()
            else:
                output_format = "json"

            if output_format not in ["yaml", "json"]:
                return Response(
                    {
                        "error": f"Invalid output_format: {output_format}. Must be one of: yaml, json"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get version parameter (for ODPS and ODCS formats)
            # For ODPS: default is "4.1"
            # For ODCS: default is detected from contract or "3.0.2"
            version_param = None
            if hasattr(request, "query_params"):
                version_param = request.query_params.get("version", "").strip()
            elif hasattr(request, "GET"):
                version_param = request.GET.get("version", "").strip()

            # Set defaults based on format type
            if format_type == "odps":
                odps_version = version_param if version_param else "4.1"
                odcs_version = None
            elif format_type == "odcs":
                odcs_version = version_param if version_param else None
                odps_version = None
            else:
                odps_version = None
                odcs_version = None

            # Generate filename based on contract and format
            # Try to get name from hub_contract_json, otherwise use contract ID
            contract_name = f"contract-{contract.id}"
            if contract.hub_contract_json:
                # Try to get name from hub_contract_json
                if isinstance(contract.hub_contract_json, dict):
                    info = contract.hub_contract_json.get("info", {})
                    if isinstance(info, dict):
                        name = info.get("name")
                        if name:
                            contract_name = name
            # Sanitize filename (remove invalid characters)
            import re

            contract_name = re.sub(r"[^\w\s-]", "", contract_name).strip()
            contract_name = re.sub(r"[-\s]+", "-", contract_name)

            # Determine file extension
            if output_format == "yaml":
                extension = "yaml"
                content_type = "application/x-yaml"
            else:
                extension = "json"
                content_type = "application/json"

            # Build filename with version for ODCS format
            if format_type == "odcs" and odcs_version:
                # Include version in filename: {name}-v{version}.odcs.{ext}
                filename = f"{contract_name}-v{odcs_version}.{format_type}.{extension}"
            else:
                filename = f"{contract_name}.{format_type}.{extension}"

            # Handle different format types (reuse export logic)
            if format_type == "hubcontract":
                # Download as HubContract format
                if not contract.hub_contract_json:
                    return Response(
                        {
                            "error": "Contract has no hub_contract_json. Cannot download as HubContract format."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                contract_data = contract.hub_contract_json

                # Format output
                if output_format == "yaml":
                    from hub.apps.contracts.odps_generator import format_odps_as_yaml

                    try:
                        # Use ODPS formatter for YAML (works for any dict)
                        output = format_odps_as_yaml(contract_data)
                        response = HttpResponse(output, content_type=content_type)
                        response["Content-Disposition"] = f'attachment; filename="{filename}"'
                        return response
                    except Exception as e:
                        return Response(
                            {"error": f"Failed to format as YAML: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
                else:  # json
                    # Return as JSON
                    import json

                    output = json.dumps(contract_data, indent=2, ensure_ascii=False)
                    response = HttpResponse(output, content_type=content_type)
                    response["Content-Disposition"] = f'attachment; filename="{filename}"'
                    return response

            elif format_type == "odcs":
                # Download as ODCS format (Task 9.5.4.1.5.1)
                # Prefer original_raw if available and matches requested version, otherwise generate

                # Get tenant_id for metrics
                tenant_id = _get_tenant_id_from_request(request)

                # Validate ODCS version if provided
                if odcs_version:
                    try:
                        from hub.apps.contracts.odcs_validation import validate_odcs_version

                        validate_odcs_version(odcs_version)
                    except Exception as e:
                        return Response(
                            {"error": f"Invalid ODCS version: {str(e)}"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                # Start timing for export duration metric
                export_start_time = time.time()

                try:
                    from hub.apps.contracts.odcs_errors import (
                        ODCSExportError,
                        ODCSGenerationError,
                    )
                    from hub.apps.contracts.odcs_format_converter import (
                        format_odcs_as_json,
                        format_odcs_as_yaml,
                    )
                    from hub.apps.contracts.odcs_generator import (
                        generate_odcs_from_hubcontract,
                    )
                    from hub.apps.contracts.odcs_version_detection import detect_odcs_version

                    odcs_doc = None
                    final_version = None
                    use_original = False

                    # Check if original_raw is available and matches requested version
                    if (
                        contract.original_raw
                        and contract.original_raw.strip()
                        and contract.original_spec_type == OriginalSpecType.ODCS
                    ):
                        try:
                            # Parse original contract to detect version
                            original_contract_data = parse_contract(
                                contract.original_raw, contract.original_format
                            )
                            original_version = detect_odcs_version(original_contract_data)

                            # Use original if:
                            # 1. No version requested (use original version)
                            # 2. Requested version matches original version
                            if not odcs_version or original_version == odcs_version:
                                odcs_doc = original_contract_data
                                final_version = (
                                    original_version
                                    if original_version != "unknown"
                                    else (odcs_version or "3.0.2")
                                )
                                use_original = True
                            else:
                                # Version mismatch - need to generate
                                final_version = odcs_version
                        except Exception as e:
                            # If parsing fails, fall through to generation
                            import logging

                            logger = logging.getLogger(__name__)
                            logger.warning(
                                f"Failed to parse original ODCS contract: {str(e)}, will generate instead"
                            )

                    # Generate from HubContract if original not used
                    if not use_original:
                        # Check if hub_contract_json exists
                        if contract.hub_contract_json is None:
                            return Response(
                                {
                                    "error": "Contract has no original_raw or hub_contract_json. Cannot download as ODCS format."
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                        # Generate ODCS from HubContract
                        # Attempt generation even if hub_contract_json is empty/invalid to get proper error handling
                        try:
                            odcs_doc = generate_odcs_from_hubcontract(
                                hub_contract=contract.hub_contract_json,
                                target_version=odcs_version,
                                tenant_id=tenant_id,
                            )
                            # Detect final version from generated document
                            final_version = detect_odcs_version(odcs_doc)
                            if final_version == "unknown":
                                final_version = odcs_version or "3.0.2"
                        except ODCSGenerationError as e:
                            return Response(
                                {
                                    "error": f"Failed to generate ODCS document: {str(e)}",
                                    "details": getattr(e, "context", {}),
                                },
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            )
                        except Exception as e:
                            import logging

                            logger = logging.getLogger(__name__)
                            logger.error(
                                f"Failed to generate ODCS download: {str(e)}", exc_info=True
                            )
                            return Response(
                                {"error": f"Failed to generate ODCS download: {str(e)}"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            )

                    # Ensure odcs_doc is not None
                    if odcs_doc is None:
                        return Response(
                            {"error": "Failed to retrieve or generate ODCS document."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

                    # Update filename with final version if not already set
                    if final_version and not filename.endswith(
                        f"-v{final_version}.{format_type}.{extension}"
                    ):
                        # Rebuild filename with detected/generated version
                        filename = f"{contract_name}-v{final_version}.{format_type}.{extension}"

                    # Format output
                    try:
                        if output_format == "yaml":
                            output = format_odcs_as_yaml(odcs_doc)
                        else:  # json
                            output = format_odcs_as_json(odcs_doc)
                    except ODCSExportError as e:
                        return Response(
                            {
                                "error": f"Failed to format ODCS document: {str(e)}",
                                "details": getattr(e, "context", {}),
                            },
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
                    except Exception as e:
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.error(f"Failed to format ODCS download: {str(e)}", exc_info=True)
                        return Response(
                            {"error": f"Failed to format ODCS download: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

                    # Calculate export duration and size for metrics
                    export_duration = time.time() - export_start_time
                    export_size_bytes = len(output.encode("utf-8"))
                    size_category = _categorize_export_size(export_size_bytes)

                    # Record metrics (Task 9.5.4.1.5.1)
                    try:
                        odcs_export_duration_seconds.labels(
                            format=output_format,
                            size_category=size_category,
                            version=final_version or "unknown",
                            tenant_id=tenant_id,
                        ).observe(export_duration)

                        odcs_export_size_bytes.labels(
                            format=output_format,
                            version=final_version or "unknown",
                            tenant_id=tenant_id,
                        ).observe(export_size_bytes)

                        # Record export success
                        odcs_export_total.labels(
                            status="success",
                            format=output_format,
                            version=final_version or "unknown",
                            tenant_id=tenant_id,
                        ).inc()
                    except Exception:
                        pass  # Don't fail on metrics recording

                    # Return response with Content-Disposition header
                    response = HttpResponse(output, content_type=content_type)
                    response["Content-Disposition"] = f'attachment; filename="{filename}"'
                    return response

                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"ODCS download endpoint error: {str(e)}", exc_info=True)
                    return Response(
                        {"error": f"ODCS download failed: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            elif format_type == "odps":
                # Download as ODPS format
                if not contract.hub_contract_json:
                    return Response(
                        {
                            "error": "Contract has no hub_contract_json. Cannot download as ODPS format."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Generate ODPS from HubContract
                from hub.apps.contracts.odps_generator import (
                    generate_odps_from_hubcontract,
                )

                # Get original ODCS contract if available (for embedding in ODPS)
                original_odcs_contract = None
                if contract.original_raw and contract.original_spec_type == OriginalSpecType.ODCS:
                    try:
                        # parse_contract is now imported at the top of the file
                        original_odcs_contract = parse_contract(
                            contract.original_raw, contract.original_format
                        )
                    except Exception:
                        # If parsing fails, continue without original ODCS
                        pass

                try:
                    # ROOT CAUSE FIX: Ensure target_version is a string (not None)
                    # generate_odps_from_hubcontract expects str, not Optional[str]
                    odps_target_version = odps_version if odps_version else "4.1"
                    odps_doc = generate_odps_from_hubcontract(
                        hub_contract=contract.hub_contract_json,
                        target_version=odps_target_version,
                        original_odcs_contract=original_odcs_contract,
                        original_odcs_url=None,
                    )

                    # Format in requested output format
                    if output_format == "yaml":
                        from hub.apps.contracts.odps_generator import format_odps_as_yaml

                        output = format_odps_as_yaml(odps_doc)
                        response = HttpResponse(output, content_type=content_type)
                        response["Content-Disposition"] = f'attachment; filename="{filename}"'
                        return response
                    else:  # json
                        from hub.apps.contracts.odps_generator import format_odps_as_json

                        output = format_odps_as_json(odps_doc)
                        response = HttpResponse(output, content_type=content_type)
                        response["Content-Disposition"] = f'attachment; filename="{filename}"'
                        return response
                except Exception as e:
                    return Response(
                        {"error": f"Failed to generate ODPS format: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

        except Http404:
            # Re-raise Http404 so it can be handled by DRF's exception handler
            # This ensures proper 404 responses instead of 500 errors
            raise
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Download endpoint error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Download failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            # Restore original format_kwarg
            if "original_format_kwarg" in locals():
                if original_format_kwarg is not None:
                    self.format_kwarg = original_format_kwarg
                else:
                    # If it was None originally, we might need to restore it differently
                    # But for now, just leave it as None since we disabled it
                    pass

    @extend_schema(
        summary="Generate ODPS document",
        description="""
        Generate ODPS (Open Data Product Standard) document from HubContract.

        This endpoint generates an ODPS document from the contract's HubContract representation,
        focusing on marketplace metadata. The generated ODPS document can be used for
        marketplace listings and product catalogs.

        **Request Body (optional):**
        - `target_version` (string, optional): Target ODPS version (default: "4.1")
        - `output_format` (string, optional): Output format - "json" or "yaml" (default: "json")
        - `embed_odcs` (boolean, optional): If true and contract is ODCS, embed original ODCS
          contract inline in product.contract.spec (default: true)

        **Behavior:**
        - Generates ODPS from HubContract (marketplace metadata)
        - If contract is ODCS and has original_raw, optionally embeds ODCS in product.contract.spec
        - Returns generated ODPS document in requested format

        **Response:**
        - Returns generated ODPS document as JSON or YAML
        - Content-Type header set based on output_format
        """,
        request=inline_serializer(
            name="GenerateODPSRequest",
            fields={
                "target_version": serializers.CharField(
                    required=False, default="4.1", help_text="Target ODPS version (default: 4.1)"
                ),
                "output_format": serializers.ChoiceField(
                    choices=["json", "yaml"],
                    required=False,
                    default="json",
                    help_text="Output format: json or yaml (default: json)",
                ),
                "embed_odcs": serializers.BooleanField(
                    required=False,
                    default=True,
                    help_text="If true and contract is ODCS, embed original ODCS contract inline",
                ),
            },
        ),
        responses={
            200: inline_serializer(
                name="GenerateODPSResponse",
                fields={
                    "odps_document": serializers.DictField(help_text="Generated ODPS document"),
                    "target_version": serializers.CharField(
                        help_text="ODPS version used for generation"
                    ),
                    "output_format": serializers.CharField(
                        help_text="Output format (json or yaml)"
                    ),
                },
            ),
            400: OpenApiResponse(
                description="Contract has no hub_contract_json or invalid parameters"
            ),
            404: OpenApiResponse(description="Contract not found"),
            500: OpenApiResponse(description="ODPS generation failed"),
        },
        tags=["Contracts", "ODPS"],
    )

    # SAVING CHECKPOINT: End of download_contract method (~1200 lines).
    # Starting generate_odps method (~1200-1426 lines).

    @action(detail=True, methods=["post"], url_path="generate-odps")
    def generate_odps(self, request, id=None):
        """
        Generate ODPS document from HubContract.

        POST /api/v1/contracts/{id}/generate-odps/
        Body (optional): {
            "target_version": "4.1" (optional, default: "4.1"),
            "output_format": "json" (optional, default: "json", options: "json", "yaml"),
            "embed_odcs": true (optional, default: true)
        }

        Returns generated ODPS document.
        """
        self.check_auditor_permissions(request, "generate_odps")

        try:
            # get_object() may raise Http404 - let it propagate to be handled by DRF's exception handler
            from django.http import Http404

            contract = self.get_object()

            # Validate contract has hub_contract_json
            if not contract.hub_contract_json:
                return Response(
                    {"error": "Contract has no hub_contract_json. Cannot generate ODPS document."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get request parameters (with defaults)
            # Support both query params and body data
            target_version = request.query_params.get("target_version") or request.data.get(
                "target_version", "4.1"
            )
            output_format = request.query_params.get("output_format") or request.data.get(
                "output_format", "json"
            )
            embed_odcs_str = request.query_params.get("embed_odcs") or request.data.get(
                "embed_odcs", True
            )
            # Convert embed_odcs to boolean if it's a string
            if isinstance(embed_odcs_str, str):
                embed_odcs = embed_odcs_str.lower() in ("true", "1", "yes")
            else:
                embed_odcs = embed_odcs_str

            # Validate target_version
            if not isinstance(target_version, str) or not target_version.strip():
                return Response(
                    {"error": "target_version must be a non-empty string"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            target_version = target_version.strip()

            # Validate output_format
            if output_format not in ["json", "yaml"]:
                return Response(
                    {"error": f"output_format must be 'json' or 'yaml', got '{output_format}'"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Import ODPS generator functions
            from hub.apps.contracts.odps_errors import ODPSExportError
            from hub.apps.contracts.odps_generator import (
                format_odps_as_json,
                format_odps_as_yaml,
                generate_odps_from_hubcontract,
            )

            # Get original ODCS contract if available and embed_odcs is True
            original_odcs_contract = None
            if (
                embed_odcs
                and contract.original_raw
                and contract.original_spec_type == OriginalSpecType.ODCS
            ):
                try:
                    original_odcs_contract = parse_contract(
                        contract.original_raw, contract.original_format
                    )
                except Exception as e:
                    # If parsing fails, log warning but continue without original ODCS
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Failed to parse original ODCS contract for embedding: {str(e)}",
                        exc_info=True,
                    )

            # Generate ODPS document from HubContract
            try:
                odps_doc = generate_odps_from_hubcontract(
                    hub_contract=contract.hub_contract_json,
                    target_version=target_version,
                    original_odcs_contract=original_odcs_contract,
                    original_odcs_url=None,  # Not using URL reference for now
                )
            except ODPSExportError as e:
                # ODPS generation failed with structured error
                return Response(
                    {
                        "error": e.user_message or str(e),
                        "error_code": e.error_code,
                        "context": e.context,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                # Unexpected error during generation
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to generate ODPS document: {str(e)}", exc_info=True)
                return Response(
                    {"error": f"Failed to generate ODPS document: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Format output based on output_format
            if output_format == "yaml":
                try:
                    odps_content = format_odps_as_yaml(odps_doc)
                    # Return as JSON response with YAML content in a field
                    # This allows consistent response structure
                    return Response(
                        {
                            "odps_document": odps_doc,  # Include dict for programmatic access
                            "odps_content": odps_content,  # Include YAML string for direct use
                            "target_version": target_version,
                            "output_format": output_format,
                        },
                        content_type="application/json",
                    )
                except ODPSExportError as e:
                    return Response(
                        {
                            "error": f"Failed to format ODPS as YAML: {e.user_message or str(e)}",
                            "error_code": e.error_code,
                            "context": e.context,
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            else:  # json
                # Return ODPS document as JSON
                return Response(
                    {
                        "odps_document": odps_doc,
                        "target_version": target_version,
                        "output_format": output_format,
                    },
                    content_type="application/json",
                )

        except Http404:
            # Re-raise Http404 so it can be handled by DRF's exception handler
            raise
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Generate ODPS endpoint error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Generate ODPS failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
