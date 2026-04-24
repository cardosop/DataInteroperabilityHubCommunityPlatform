"""
Compliance Views

REST API views for compliance run management.
"""

from datetime import datetime

import structlog
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from hub.apps.assets.models import Asset
from hub.apps.assets.models import ComplianceStatus as AssetComplianceStatus
from hub.apps.audit.utils import create_audit_event
from hub.apps.core.responses import api_error_response, handle_service_exception
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.utils import create_job, get_job_timeout
from hub.apps.tenants.request_tenant import get_request_tenant, get_request_tenant_id
from hub.apps.tenants.services import get_tenant_compliance_regimes, get_tenant_config
from hub.apps.tenants.validators import VALID_COMPLIANCE_REGIMES

from .models import ComplianceRun, ComplianceRunStatus, RiskLevel
from .serializers import ComplianceRunCreateSerializer, ComplianceRunSerializer
from .service_client import ComplianceServiceClient
from .services import ComplianceService

logger = structlog.get_logger(__name__)


class ComplianceRunViewSet(viewsets.ModelViewSet):
    """
    ViewSet for compliance run management.

    Tenant-scoped: users can only see/manage compliance runs in their tenant.
    """

    queryset = ComplianceRun.objects.all()
    serializer_class = ComplianceRunSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at", "updated_at", "status", "completed_at"]
    ordering = ["-created_at"]  # Default ordering

    def check_auditor_permissions(self, request, view_action):
        """Check if AUDITOR role can perform the action (read-only)"""
        if not request.user or not request.user.is_authenticated:
            return True  # Let IsAuthenticated handle this

        # Check if user has AUDITOR role
        if hasattr(request.user, "user_roles"):
            role_names = [ur.role.name for ur in request.user.user_roles.all()]
            if "AUDITOR" in role_names:
                # AUDITOR can only read, not write
                if view_action in ["create", "update", "partial_update", "destroy", "cancel"]:
                    from rest_framework.exceptions import PermissionDenied

                    raise PermissionDenied(
                        "AUDITOR role has read-only access. Cannot perform write operations."
                    )

        return True

    def get_queryset(self):
        """Filter queryset based on user permissions and query parameters"""
        user = self.request.user

        # Platform admins can see all compliance runs
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = ComplianceRun.objects.select_related("tenant", "asset", "dataset", "file", "job").all()
        else:
            # Regular users can only see compliance runs in their tenant
            # Use central helper for tenant resolution (Phase 10.1.2)
            tenant_id = get_request_tenant_id(self.request)
            if tenant_id:
                queryset = ComplianceRun.objects.select_related("tenant", "asset", "dataset", "file", "job").filter(tenant_id=tenant_id)
            else:
                return ComplianceRun.objects.none()

        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            valid_statuses = [choice[0] for choice in ComplianceRunStatus.choices]
            if status_filter.upper() in valid_statuses:
                queryset = queryset.filter(status=status_filter.upper())
            else:
                # Invalid status - return empty queryset
                return ComplianceRun.objects.none()

        # Filter by asset_id
        asset_id = self.request.query_params.get("asset")
        if asset_id:
            try:
                import uuid

                asset_uuid = uuid.UUID(asset_id)
                queryset = queryset.filter(asset_id=asset_uuid)
            except (ValueError, TypeError):
                # Invalid UUID format - return empty queryset
                return ComplianceRun.objects.none()

        return queryset.order_by("-created_at")

    @transaction.atomic
    def create(self, request):
        """
        Create a new compliance run.

        POST /runs
        Body: {
            "asset_id": "uuid" (optional),
            "dataset_id": "uuid" (optional),
            "file_id": "uuid" (optional, scan-only),
            "scan_mode": "internal" | "external",
            "applicable_regulations": ["GDPR", "HIPAA"] (optional)
        }
        """
        self.check_auditor_permissions(request, "create")
        serializer = ComplianceRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant from user
        # Get tenant using central helper (Phase 10.1.2)
        tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to create compliance runs"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get resource references
        asset_id = serializer.validated_data.get("asset_id")
        dataset_id = serializer.validated_data.get("dataset_id")
        file_id = serializer.validated_data.get("file_id")
        scan_mode = serializer.validated_data.get("scan_mode", "internal")
        applicable_regulations = serializer.validated_data.get(
            "applicable_regulations"
        )
        legal_basis = serializer.validated_data.get("legal_basis")
        destination_jurisdiction = serializer.validated_data.get(
            "destination_jurisdiction"
        )

        # Determine applicable regulations (explicit request > tenant default > platform default)
        regimes_source = None
        if not applicable_regulations:
            # Get tenant default from TenantConfig (with platform default fallback)
            applicable_regulations = get_tenant_compliance_regimes(str(tenant.id))
            regimes_source = (
                "tenant_config"
                if applicable_regulations != ["GDPR", "LGPD"]
                else "platform_default"
            )
            logger.info(
                "compliance_regimes_selected",
                tenant_id=str(tenant.id),
                regimes=applicable_regulations,
                source=regimes_source,
                message=f"Using {regimes_source} regimes: {applicable_regulations}",
            )
        else:
            # Explicit regimes in request (user override)
            regimes_source = "request_override"

            # Validate that provided regimes are subset of allowed_compliance_regimes
            tenant_config = get_tenant_config(tenant)
            allowed_regimes = tenant_config.get(
                "allowed_compliance_regimes", VALID_COMPLIANCE_REGIMES
            )

            invalid_regimes = [r for r in applicable_regulations if r not in allowed_regimes]
            if invalid_regimes:
                return Response(
                    {
                        "error": f"Invalid compliance regimes: {invalid_regimes}. "
                        f"Allowed regimes for this tenant: {allowed_regimes}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            logger.info(
                "compliance_regimes_selected",
                tenant_id=str(tenant.id),
                regimes=applicable_regulations,
                source=regimes_source,
                message=f"Using explicit regimes from request: {applicable_regulations}",
            )

        # Resolve resources
        asset = None
        dataset = None
        file_obj = None

        if asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Asset.DoesNotExist:
                return api_error_response(
                    message="Asset not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOT_FOUND",
                )

        if dataset_id:
            try:
                from hub.apps.datasets.models import Dataset

                dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)
                if asset and dataset.asset != asset:
                    return Response(
                        {"error": "Dataset does not belong to the specified asset"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not asset and dataset.asset:
                    asset = dataset.asset
            except Dataset.DoesNotExist:
                return api_error_response(
                    message="Dataset not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOT_FOUND",
                )

        if file_id:
            try:
                from hub.apps.files.models import File

                file_obj = File.objects.get(id=file_id, tenant=tenant)
            except File.DoesNotExist:
                return api_error_response(
                    message="File not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOT_FOUND",
                )

        # Validate contract compliance schema when run will use contract terms (5.4.2)
        if asset or dataset:
            from hub.apps.contracts.models import Contract, ContractStatus
            from hub.apps.compliance.contract_integration import (
                validate_contract_compliance_payload,
                ContractComplianceSchemaError,
            )
            contract_to_validate = None
            if asset:
                contract_to_validate = asset.contracts.filter(status=ContractStatus.ACTIVE).first()
            if not contract_to_validate and dataset and getattr(dataset, "asset", None):
                contract_to_validate = dataset.asset.contracts.filter(status=ContractStatus.ACTIVE).first()
            if contract_to_validate and contract_to_validate.hub_contract_json:
                try:
                    validate_contract_compliance_payload(contract_to_validate.hub_contract_json)
                except ContractComplianceSchemaError as e:
                    return Response(
                        {
                            "error": "Contract compliance terms are invalid",
                            "code": "contract_compliance_schema_invalid",
                            "details": e.details,
                            "message": e.message,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        # Create compliance run via service (validates via ComplianceBusinessRules, then creates)
        service = ComplianceService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        try:
            compliance_run = service.create_compliance_run(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                asset_id=asset_id,
                dataset_id=dataset_id,
                file_id=file_id,
                scan_mode=scan_mode,
                applicable_regulations=applicable_regulations,
                legal_basis=legal_basis,
                destination_jurisdiction=destination_jurisdiction,
                tenant=tenant,
                user=request.user,
                asset=asset,
                dataset=dataset,
                file_obj=file_obj,
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)

        # Log audit event
        create_audit_event(
            resource_type="COMPLIANCE_RUN",
            action="COMPLIANCE_RUN_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(compliance_run.id),
            details={
                "scan_mode": scan_mode,
                "applicable_regulations": applicable_regulations,
                "asset_id": str(asset.id) if asset else None,
                "dataset_id": str(dataset.id) if dataset else None,
                "file_id": str(file_obj.id) if file_obj else None,
            },
            request=request,
        )

        return Response(
            ComplianceRunSerializer(compliance_run).data, status=status.HTTP_201_CREATED
        )

    def list(self, request, *args, **kwargs):
        """List compliance runs (tenant-scoped)"""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve compliance run by ID"""
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update compliance run (full update)"""
        self.check_auditor_permissions(request, "update")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Update compliance run (partial update)"""
        self.check_auditor_permissions(request, "partial_update")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete compliance run"""
        self.check_auditor_permissions(request, "destroy")
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, id=None):
        """
        Cancel a compliance run by cancelling its underlying job.

        POST /compliance/runs/{id}/cancel/

        Only PENDING or RUNNING runs can be cancelled.
        """
        self.check_auditor_permissions(request, "cancel")
        compliance_run = self.get_object()

        cancellable = (
            ComplianceRunStatus.PENDING,
            ComplianceRunStatus.QUEUED,   # async job queued at service
            ComplianceRunStatus.RUNNING,
        )
        if compliance_run.status not in cancellable:
            return api_error_response(
                f"Cannot cancel compliance run "
                f"(current status: {compliance_run.status})",
                code="INVALID_STATUS",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        job = compliance_run.job
        if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
            return api_error_response(
                f"Cannot cancel: underlying job status is {job.status}",
                code="JOB_NOT_CANCELLABLE",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        previous_job_status = job.status
        job.mark_cancelled()
        if previous_job_status == JobStatus.RUNNING and job.tenant:
            from hub.apps.jobs.utils import decrement_tenant_job_counter
            decrement_tenant_job_counter(str(job.tenant.id), "running")

        compliance_run.status = ComplianceRunStatus.FAILED
        compliance_run.allowed_to_store = False
        compliance_run.regulation_mapping_json = {
            **(compliance_run.regulation_mapping_json or {}),
            "error": "Cancelled by user",
            "cancelled": True,
        }
        compliance_run.completed_at = timezone.now()
        compliance_run.save(
            update_fields=["status", "allowed_to_store", "regulation_mapping_json", "completed_at"]
        )

        create_audit_event(
            resource_type="COMPLIANCE_RUN",
            action="COMPLIANCE_RUN_CANCELLED",
            actor_user=request.user,
            tenant=compliance_run.tenant,
            resource_id=str(compliance_run.id),
            details={"job_id": str(job.id)},
            request=request,
        )

        return Response(
            ComplianceRunSerializer(compliance_run).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        operation_id="get_compliance_run_results",
        responses={
            200: inline_serializer(
                name="ComplianceRunResultsResponse",
                fields={
                    "compliance_run_id": serializers.UUIDField(),
                    "overall_status": serializers.CharField(),
                    "risk_level": serializers.CharField(),
                    "allowed_to_store": serializers.BooleanField(),
                    "compliance_score": serializers.FloatField(allow_null=True),
                    "score_breakdown": serializers.DictField(),
                    "violations": serializers.ListField(),
                    "violation_details": serializers.ListField(),
                    "remediation_suggestions": serializers.ListField(),
                    "risk_assessment": serializers.DictField(),
                    "violation_timeline": serializers.ListField(),
                    "regulations": serializers.ListField(),
                    "detected_categories": serializers.DictField(),
                    "column_findings": serializers.ListField(),
                    "started_at": serializers.DateTimeField(allow_null=True),
                    "completed_at": serializers.DateTimeField(allow_null=True),
                },
            ),
            404: OpenApiResponse(description="Compliance run not found"),
        },
        tags=["Compliance"],
    )
    @action(detail=True, methods=["get"], url_path="results")
    def results(self, request, id=None):
        """
        Get enhanced compliance run results with detailed violation information.

        GET /api/v1/compliance/runs/{id}/results/

        Returns detailed compliance results including:
        - Violation details with remediation suggestions
        - Compliance score breakdown
        - Risk assessment
        - Timeline of violations
        """
        from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
        from rest_framework import serializers

        compliance_run = self.get_object()

        # Extract data from compliance run
        column_findings = compliance_run.column_findings_json or []
        regulation_mapping = compliance_run.regulation_mapping_json or {}
        detected_categories = compliance_run.detected_categories_json or {}

        # Build a PII-type → [regulation_name, ...] index from regulation_mapping_json.
        # The raw regulation_mapping_json shape is
        #   {"GDPR": {"applies": true, "applicable_categories": ["PII_DIRECT_EMAIL", ...], ...},
        #    "LGPD": {...}, "metadata": {...}}
        # — regulations are keyed at the top level and list their applicable PII
        # categories. The earlier implementation read `finding.get("regulations_affected")`
        # which does not exist on column_findings entries (the CLI emits only
        # `confidence`, `match_ratio`, `categories`, etc.). That left every
        # violation with `regulations_affected: []`, which in turn made the
        # Regulation filter dropdown in the frontend viewer render with
        # exactly one option ("All Regulations") — the filter looked broken.
        regulations_by_pii_type: dict[str, list[str]] = {}
        for reg_name, reg_info in regulation_mapping.items():
            # Skip the non-regulation metadata key emitted at the same level.
            if reg_name == "metadata":
                continue
            if not isinstance(reg_info, dict):
                continue
            # Respect the CLI's own `applies` flag — a regulation listed but
            # marked applies=False should not surface as affecting the violation.
            if reg_info.get("applies") is False:
                continue
            for pii in reg_info.get("applicable_categories", []) or []:
                regulations_by_pii_type.setdefault(pii, []).append(reg_name)

        # Build violation details from column findings
        violations = []
        violation_details = []
        remediation_suggestions = []

        for finding in column_findings:
            column_name = finding.get("column") or finding.get("column_name", "Unknown")
            pii_types = finding.get("categories") or finding.get("pii_types", [])
            risk_score = finding.get("match_ratio") or finding.get("risk_score", 0.0)

            for pii_type in pii_types:
                violation = {
                    "column": column_name,
                    "pii_type": pii_type,
                    "risk_score": risk_score,
                    "severity": (
                        "HIGH" if risk_score > 0.7 else "MEDIUM" if risk_score > 0.4 else "LOW"
                    ),
                }
                violations.append(violation)

                # Add detailed violation information.
                #
                # `detection_confidence` is a qualitative label (HIGH/MEDIUM/LOW)
                # produced by the DataContract CLI — not a numeric score. The
                # earlier default `0.0` pretended the field was numeric and
                # broke the frontend renderer which did `Math.round(x * 100)%`
                # and produced "Confidence: NaN%" whenever the actual string
                # value landed. Using `None` when the label is missing keeps
                # the type honest (string-or-null, never a surprise number).
                violation_detail = {
                    "column": column_name,
                    "pii_type": pii_type,
                    "risk_score": risk_score,
                    "severity": violation["severity"],
                    "regulations_affected": sorted(
                        regulations_by_pii_type.get(pii_type, [])
                    ),
                    "detection_confidence": finding.get("confidence"),
                    "sample_values": finding.get("sample_values", [])[:3],  # Limit to 3 samples
                }
                violation_details.append(violation_detail)

                # Generate remediation suggestions
                if pii_type in [
                    "PII_DIRECT_EMAIL",
                    "PII_DIRECT_PHONE",
                    "PII_DIRECT_SSN",
                    "PAYMENT_CARD",
                ]:
                    remediation_suggestions.append(
                        {
                            "column": column_name,
                            "pii_type": pii_type,
                            "suggestion": f"Consider masking or redacting {pii_type} data in column {column_name}",
                            "priority": "HIGH" if risk_score > 0.7 else "MEDIUM",
                        }
                    )

        # Calculate compliance score breakdown
        total_columns = len(column_findings) if column_findings else 1
        columns_with_pii = len([
            f for f in column_findings
            if f.get("categories") or f.get("pii_types")
        ])
        columns_without_pii = total_columns - columns_with_pii

        compliance_score = 100.0
        if total_columns > 0:
            # Reduce score based on PII detection
            pii_penalty = (columns_with_pii / total_columns) * 50  # Max 50 point penalty
            compliance_score = max(0, 100 - pii_penalty)

        score_breakdown = {
            "total_columns": total_columns,
            "columns_with_pii": columns_with_pii,
            "columns_without_pii": columns_without_pii,
            "pii_detection_rate": columns_with_pii / total_columns if total_columns > 0 else 0,
            "base_score": 100,
            "pii_penalty": pii_penalty if total_columns > 0 else 0,
            "final_score": compliance_score,
        }

        # Build risk assessment
        risk_assessment = {
            "overall_risk_level": compliance_run.risk_level or "UNKNOWN",
            "risk_score": regulation_mapping.get("metering", {}).get("risk_score", 0.0),
            "allowed_to_store": compliance_run.allowed_to_store,
            "total_violations": len(violations),
            "high_severity_violations": len([v for v in violations if v["severity"] == "HIGH"]),
            "medium_severity_violations": len([v for v in violations if v["severity"] == "MEDIUM"]),
            "low_severity_violations": len([v for v in violations if v["severity"] == "LOW"]),
            "regulations_checked": compliance_run.regulations or [],
            "recommendations": [],
        }

        # Add recommendations based on risk level and actual findings
        has_violations = len(violations) > 0
        if has_violations:
            if compliance_run.risk_level == "CRITICAL":
                risk_assessment["recommendations"].append(
                    "Immediate action required: Data contains "
                    "high-risk PII"
                )
            elif compliance_run.risk_level == "HIGH":
                risk_assessment["recommendations"].append(
                    "Review and remediate high-risk PII "
                    "detections"
                )
            elif compliance_run.risk_level == "MEDIUM":
                risk_assessment["recommendations"].append(
                    "Consider implementing data masking for "
                    "detected PII"
                )
        elif compliance_run.overall_status == "FAIL":
            risk_assessment["recommendations"].append(
                "Compliance check failed due to policy "
                "violations (e.g. missing legal basis). "
                "Review the issues section for details."
            )

        # Build violation timeline (simplified - just use created_at for now)
        violation_timeline = []
        if compliance_run.completed_at:
            violation_timeline.append(
                {
                    "timestamp": compliance_run.completed_at.isoformat(),
                    "event": "Compliance scan completed",
                    "violations_detected": len(violations),
                    "risk_level": compliance_run.risk_level,
                }
            )

        # Log audit event
        create_audit_event(
            resource_type="COMPLIANCE_RUN",
            action="RESULTS_ACCESSED",
            actor_user=request.user,
            tenant=compliance_run.tenant,
            resource_id=str(compliance_run.id),
            details={},
            request=request,
        )

        return Response(
            {
                "compliance_run_id": str(compliance_run.id),
                "overall_status": compliance_run.overall_status,
                "risk_level": compliance_run.risk_level,
                "allowed_to_store": compliance_run.allowed_to_store,
                "compliance_score": compliance_score,
                "score_breakdown": score_breakdown,
                "violations": violations,
                "violation_details": violation_details,
                "remediation_suggestions": remediation_suggestions,
                "risk_assessment": risk_assessment,
                "violation_timeline": violation_timeline,
                "regulations": compliance_run.regulations or [],
                "detected_categories": detected_categories,
                "column_findings": column_findings,
                "started_at": (
                    compliance_run.started_at.isoformat() if compliance_run.started_at else None
                ),
                "completed_at": (
                    compliance_run.completed_at.isoformat() if compliance_run.completed_at else None
                ),
            },
            status=status.HTTP_200_OK,
        )


def execute_compliance_run(compliance_run_id: str) -> None:
    """
    Execute a compliance run (called by the job worker).

    Resolves file content, then delegates to
    ComplianceService._call_compliance_service which handles both the
    async (202 / QUEUED) and synchronous (200) response paths.

    Args:
        compliance_run_id: Compliance run UUID string
    """
    import logging

    from hub.apps.compliance.services import ComplianceService
    from hub.apps.files.storage import S3StorageClient

    _logger = logging.getLogger(__name__)

    compliance_run = ComplianceRun.objects.get(id=compliance_run_id)
    compliance_run.status = ComplianceRunStatus.RUNNING
    compliance_run.started_at = timezone.now()
    compliance_run.save(update_fields=["status", "started_at"])

    try:
        details = compliance_run.job.details_json
        scan_mode = details.get("scan_mode", "internal")
        applicable_regulations = details.get("applicable_regulations", [])
        legal_basis = details.get("legal_basis")
        destination_jurisdiction = details.get("destination_jurisdiction")

        # Resolve the file to scan
        file_obj = None
        file_format = None

        if compliance_run.file:
            file_obj = compliance_run.file
            file_format = (
                file_obj.name.split(".")[-1].lower()
                if "." in file_obj.name
                else "csv"
            )
        elif compliance_run.dataset and compliance_run.dataset.file:
            file_obj = compliance_run.dataset.file
            file_format = (
                compliance_run.dataset.format.lower()
                if compliance_run.dataset.format
                else "csv"
            )
        elif compliance_run.asset:
            dataset = (
                compliance_run.asset.datasets.order_by("-version").first()
            )
            if dataset and dataset.file:
                file_obj = dataset.file
                file_format = (
                    dataset.format.lower() if dataset.format else "csv"
                )

        if not file_obj:
            # Phase 213.G — raise FileNotFoundError so the except handler
            # below maps it to the canonical STORAGE_MISSING error_type.
            # This is the original "No file found" path called out in the
            # phase context: the asset/dataset has no attached file row.
            raise FileNotFoundError(
                "No file found for compliance run "
                f"(run_id={compliance_run.id}) — the asset/dataset has no "
                "attached File row. Typically caused by dataset creation "
                "failing or being skipped during test setup."
            )

        storage_client = S3StorageClient()
        file_content = storage_client.get_file_content(
            file_obj.storage_path
        )

        # Phase 213.G.3 — empty-bytes guard. Catches both the
        # NoSuchKey-returns-empty case and the legitimately-empty file
        # case with one clear, actionable message instead of letting
        # pandas raise EmptyDataError downstream.
        if not file_content:
            raise FileNotFoundError(
                f"file is empty (storage_path={file_obj.storage_path}) — "
                f"typically means the File row is orphaned (presigned PUT "
                f"silently failed)"
            )

        tenant_id = (
            str(compliance_run.tenant_id)
            if compliance_run.tenant_id
            else "unknown"
        )

        # Dispatch through service layer (handles 202 async + 200 sync)
        ComplianceService._call_compliance_service(
            compliance_run=compliance_run,
            file_content=file_content,
            file_format=file_format or "csv",
            scan_mode=scan_mode,
            applicable_regulations=(
                applicable_regulations or None
            ),
            legal_basis=legal_basis,
            destination_jurisdiction=destination_jurisdiction,
            tenant_id=tenant_id,
            correlation_id=str(compliance_run.id),
        )

        # Fail-closed log when storage is blocked
        if (
            compliance_run.allowed_to_store is False
            and compliance_run.status == ComplianceRunStatus.SUCCEEDED
        ):
            asset_id = (
                str(compliance_run.asset.id)
                if compliance_run.asset
                else "N/A"
            )
            _logger.warning(
                "Compliance run %s: allowed_to_store=False. "
                "Storage should be blocked for asset %s.",
                compliance_run_id,
                asset_id,
            )

    except Exception as e:
        _logger.error(
            "Compliance run %s failed: %s",
            compliance_run_id,
            e,
            exc_info=True,
        )
        # Phase 213.G — map exception to canonical error_type taxonomy
        # {REMOTE_FAILURE, POLL_TIMEOUT, STORAGE_MISSING, EXECUTION_ERROR}
        # so the FAILED-row invariant holds for every code path.
        if isinstance(e, FileNotFoundError):
            _error_type = "STORAGE_MISSING"
        else:
            _error_type = "EXECUTION_ERROR"
        compliance_run.status = ComplianceRunStatus.FAILED
        compliance_run.allowed_to_store = False
        compliance_run.regulation_mapping_json = {
            "error": str(e),
            "error_type": _error_type,
            "fail_closed": True,
        }
        compliance_run.completed_at = timezone.now()
        compliance_run.save(
            update_fields=[
                "status",
                "allowed_to_store",
                "regulation_mapping_json",
                "completed_at",
            ]
        )
