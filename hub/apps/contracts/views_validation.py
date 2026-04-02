"""
Contract Views Validation Operations

Validation, linting, and conversion actions for contract viewsets.

SAVING CHECKPOINT: This module contains validation-related actions.
"""

import time

from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from hub.apps.audit.utils import create_audit_event
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job

from .cli_client import (
    SYNC_TIMEOUT,
    DataContractCLIClient,
    group_errors_by_category,
    interpret_validation_status,
)
from .models import ValidationStatus


class ContractValidationMixin:
    """
    Mixin for Contract validation, linting, and conversion operations.

    Provides validation, linting, and format conversion endpoints.
    """

    @extend_schema(
        summary="Validate contract",
        description="""
        Validate a contract using DataContract CLI.

        Supports both synchronous and asynchronous validation.
        """,
        request=inline_serializer(
            name="ContractValidateRequest",
            fields={
                "async": serializers.BooleanField(
                    required=False, default=False, help_text="Use async validation"
                )
            },
        ),
        responses={
            200: inline_serializer(
                name="ContractValidateResponse",
                fields={
                    "validation_status": serializers.CharField(),
                    "valid": serializers.BooleanField(),
                    "errors": serializers.ListField(),
                    "warnings": serializers.ListField(),
                },
            ),
            202: inline_serializer(
                name="ContractValidateAsyncResponse",
                fields={
                    "job_id": serializers.CharField(),
                    "status": serializers.CharField(),
                    "message": serializers.CharField(),
                },
            ),
            500: OpenApiResponse(description="Validation failed"),
        },
        tags=["Contracts"],
    )
    @action(detail=True, methods=["post"], url_path="validate")
    def validate_contract(self, request, id=None):
        """
        Validate a contract using DataContract CLI.

        POST /contracts/{id}/validate
        Body: {
            "async": false (optional, default false for sync validation)
        }

        Returns validation result with status, errors, warnings.
        """
        contract = self.get_object()

        use_async = request.data.get("async", False)
        contract_size = len(contract.original_raw.encode("utf-8"))

        # Determine if async is needed based on size
        from django.conf import settings

        sync_size_limit = getattr(settings, "DATACONTRACT_VALIDATION_SYNC_SIZE_LIMIT", 100 * 1024)

        if contract_size > sync_size_limit:
            use_async = True

        # Try async validation if requested
        if use_async:
            # Create async validation job
            try:
                job = create_job(
                    job_type=JobType.CONTRACT_VALIDATION,
                    resource_type="CONTRACT",
                    resource_id=str(contract.id),
                    tenant=contract.tenant,
                    created_by=request.user,
                    details_json={"contract_id": str(contract.id), "validation_type": "async"},
                    queue_name="default",
                )

                # Log audit event
                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_VALIDATION_STARTED",
                    actor_user=request.user,
                    tenant=contract.tenant,
                    resource_id=str(contract.id),
                    details={"job_id": str(job.id), "validation_type": "async"},
                    request=request,
                )

                return Response(
                    {
                        "job_id": str(job.id),
                        "status": "pending",
                        "message": "Validation job created. Poll /jobs/{job_id} for status.",
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
            except Exception as e:
                # If async job creation fails, fall back to sync validation
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to create async validation job: {e}. Falling back to sync validation."
                )
                # Fall through to sync validation below
                use_async = False

        # Synchronous validation (default or fallback from async failure)
        if not use_async:
            try:
                cli_client = DataContractCLIClient()

                # Validate contract
                validation_result = cli_client.validate(
                    raw_contract=contract.original_raw,
                    format=contract.original_format,
                    tenant_id=str(contract.tenant.id) if contract.tenant else None,
                    use_cache=True,
                    timeout=SYNC_TIMEOUT,
                )

                # Interpret validation status
                validation_status, errors, warnings = interpret_validation_status(validation_result)

                # Group errors by category
                grouped_errors = group_errors_by_category(errors)

                # Update contract with validation results
                contract.validation_status = validation_status
                contract.validation_errors = errors
                contract.validation_warnings = warnings
                contract.cli_version = validation_result.get("cli_version", "unknown")
                contract.last_validated_at = timezone.now()
                contract.save(
                    update_fields=[
                        "validation_status",
                        "validation_errors",
                        "validation_warnings",
                        "cli_version",
                        "last_validated_at",
                        "updated_at",
                    ]
                )

                from hub.apps.contracts.invalidation_cascade import (
                    maybe_apply_invalidation_after_validation,
                )

                maybe_apply_invalidation_after_validation(
                    contract, actor_user=request.user, request=request
                )

                # Log audit event
                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_VALIDATION_COMPLETED",
                    actor_user=request.user,
                    tenant=contract.tenant,
                    resource_id=str(contract.id),
                    details={
                        "validation_status": validation_status,
                        "error_count": len(errors),
                        "warning_count": len(warnings),
                        "cli_version": contract.cli_version,
                    },
                    request=request,
                )

                # Build enhanced response with field-level details
                response_data = {
                    "validation_status": validation_status,
                    "valid": validation_status in ["VALID", "WARNING_ONLY"],
                    "errors": errors,
                    "warnings": warnings,
                    "grouped_errors": grouped_errors,
                    "error_count": len(errors),
                    "warning_count": len(warnings),
                    "schema_compliance": {
                        "status": "COMPLIANT" if validation_status == "VALID" else "NON_COMPLIANT",
                        "details": (
                            "Schema validation passed"
                            if validation_status == "VALID"
                            else "Schema validation failed or has warnings"
                        ),
                    },
                    "normalization_status": contract.normalization_status,
                    "normalization_compliant": contract.normalization_status
                    in ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"],
                    "cli_version": contract.cli_version,
                    "validated_at": contract.last_validated_at.isoformat(),
                    "contract_id": str(contract.id),
                }

                # Add field-level error summary if errors exist
                if errors:
                    field_errors = {}
                    for error in errors:
                        field_path = error.get("path", "")
                        if field_path:
                            if field_path not in field_errors:
                                field_errors[field_path] = []
                            field_errors[field_path].append(
                                {
                                    "message": error.get("message", ""),
                                    "severity": error.get("severity", "ERROR"),
                                    "rule_id": error.get("rule_id", ""),
                                    "category": error.get("category", "unknown"),
                                }
                            )
                    response_data["field_errors"] = field_errors

                return Response(
                    response_data,
                    status=status.HTTP_200_OK,
                )

            except Exception as e:
                # Check if error is from DataContract service (service unavailable)
                error_str = str(e).lower()
                is_service_error = (
                    "datacontract service" in error_str
                    or "service server error" in error_str
                    or "service timeout" in error_str
                    or "service error" in error_str
                    or "connection" in error_str
                )

                # Mark validation as ERROR
                contract.validation_status = ValidationStatus.ERROR
                contract.validation_errors = [{"message": str(e), "severity": "ERROR"}]
                contract.last_validated_at = timezone.now()
                contract.save(
                    update_fields=[
                        "validation_status",
                        "validation_errors",
                        "last_validated_at",
                        "updated_at",
                    ]
                )

                # Log audit event
                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_VALIDATION_FAILED",
                    actor_user=request.user,
                    tenant=contract.tenant,
                    resource_id=str(contract.id),
                    details={"error": str(e)},
                    request=request,
                )

                # Return 503 for service unavailable, 500 for other errors
                http_status = (
                    status.HTTP_503_SERVICE_UNAVAILABLE
                    if is_service_error
                    else status.HTTP_500_INTERNAL_SERVER_ERROR
                )

                return Response(
                    {"error": f"Validation failed: {str(e)}"},
                    status=http_status,
                )

    @extend_schema(
        summary="Lint contract",
        description="""
        Lint a contract using DataContract CLI.

        Returns linting issues and recommendations for improving the contract.
        """,
        responses={
            200: inline_serializer(
                name="ContractLintResponse",
                fields={
                    "issues": serializers.ListField(child=serializers.DictField()),
                    "cli_version": serializers.CharField(),
                },
            ),
            500: OpenApiResponse(description="Linting failed"),
        },
        tags=["Contracts"],
    )
    @action(detail=True, methods=["post"], url_path="lint")
    def lint_contract(self, request, id=None):
        """
        Lint a contract using DataContract CLI.

        POST /contracts/{id}/lint

        Returns linting result with issues.
        """
        contract = self.get_object()

        try:
            cli_client = DataContractCLIClient()

            # Lint contract
            lint_result = cli_client.lint(
                raw_contract=contract.original_raw,
                format=contract.original_format,
                timeout=SYNC_TIMEOUT,
            )

            # Log audit event
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_LINTED",
                actor_user=request.user,
                tenant=contract.tenant,
                resource_id=str(contract.id),
                details={"issues_count": len(lint_result.get("issues", []))},
                request=request,
            )

            return Response(
                {
                    "issues": lint_result.get("issues", []),
                    "cli_version": lint_result.get("cli_version", "unknown"),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"Linting failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Convert contract format",
        description="""
        Convert a contract between JSON and YAML formats.

        **Supported Formats:**
        - `JSON`: Convert to JSON format
        - `YAML`: Convert to YAML format
        """,
        request=inline_serializer(
            name="ContractConvertRequest",
            fields={
                "target_format": serializers.ChoiceField(
                    choices=["JSON", "YAML"],
                    required=True,
                    help_text="Target format for conversion",
                )
            },
        ),
        responses={
            200: inline_serializer(
                name="ContractConvertResponse",
                fields={
                    "converted_contract": serializers.CharField(),
                    "target_format": serializers.CharField(),
                    "format": serializers.CharField(),
                    "cli_version": serializers.CharField(),
                },
            ),
            400: OpenApiResponse(description="Invalid target format"),
            500: OpenApiResponse(description="Conversion failed"),
        },
        tags=["Contracts"],
    )
    @action(detail=True, methods=["post"], url_path="convert")
    def convert_contract(self, request, id=None):
        """
        Convert a contract between formats.

        POST /contracts/{id}/convert
        Body: {
            "target_format": "JSON" or "YAML"
        }

        Returns converted contract.
        """
        contract = self.get_object()
        target_format = request.data.get("target_format", "JSON")

        if target_format not in ["JSON", "YAML"]:
            return Response(
                {"error": "target_format must be JSON or YAML"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            cli_client = DataContractCLIClient()

            # Convert contract
            convert_result = cli_client.convert(
                raw_contract=contract.original_raw,
                source_format=contract.original_format,
                target_format=target_format,
                timeout=SYNC_TIMEOUT,
            )

            # Log audit event
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_CONVERTED",
                actor_user=request.user,
                tenant=contract.tenant,
                resource_id=str(contract.id),
                details={"source_format": contract.original_format, "target_format": target_format},
                request=request,
            )

            return Response(
                {
                    "converted_contract": convert_result.get("converted_contract", ""),
                    "target_format": convert_result.get("target_format", target_format),
                    "format": target_format,  # Keep for backward compatibility
                    "cli_version": convert_result.get("cli_version", "unknown"),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"Conversion failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
