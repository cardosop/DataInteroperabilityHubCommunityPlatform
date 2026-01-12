"""
Compliance Views

REST API views for compliance run management.
"""
from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse
from django.db import transaction
from django.utils import timezone
from datetime import datetime

from .models import ComplianceRun, ComplianceRunStatus, RiskLevel
from .serializers import ComplianceRunSerializer, ComplianceRunCreateSerializer
from .service_client import ComplianceServiceClient
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.utils import create_job, get_job_timeout
from hub.apps.audit.utils import create_audit_event
from hub.apps.assets.models import Asset, ComplianceStatus as AssetComplianceStatus
from hub.apps.tenants.services import get_tenant_compliance_regimes, get_tenant_config
from hub.apps.tenants.validators import VALID_COMPLIANCE_REGIMES
import structlog

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
    ordering_fields = ['created_at', 'updated_at', 'status', 'completed_at']
    ordering = ['-created_at']  # Default ordering

    def check_auditor_permissions(self, request, view_action):
        """Check if AUDITOR role can perform the action (read-only)"""
        if not request.user or not request.user.is_authenticated:
            return True  # Let IsAuthenticated handle this

        # Check if user has AUDITOR role
        if hasattr(request.user, 'user_roles'):
            role_names = [ur.role.name for ur in request.user.user_roles.all()]
            if 'AUDITOR' in role_names:
                # AUDITOR can only read, not write
                if view_action in ['create', 'update', 'partial_update', 'destroy']:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied("AUDITOR role has read-only access. Cannot perform write operations.")

        return True

    def get_queryset(self):
        """Filter queryset based on user permissions and query parameters"""
        user = self.request.user

        # Platform admins can see all compliance runs
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = ComplianceRun.objects.all()
        else:
            # Regular users can only see compliance runs in their tenant
            if hasattr(user, "tenant") and user.tenant:
                queryset = ComplianceRun.objects.filter(tenant=user.tenant)
            else:
                return ComplianceRun.objects.none()

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            valid_statuses = [choice[0] for choice in ComplianceRunStatus.choices]
            if status_filter.upper() in valid_statuses:
                queryset = queryset.filter(status=status_filter.upper())
            else:
                # Invalid status - return empty queryset
                return ComplianceRun.objects.none()

        # Filter by asset_id
        asset_id = self.request.query_params.get('asset')
        if asset_id:
            try:
                import uuid
                asset_uuid = uuid.UUID(asset_id)
                queryset = queryset.filter(asset_id=asset_uuid)
            except (ValueError, TypeError):
                # Invalid UUID format - return empty queryset
                return ComplianceRun.objects.none()

        return queryset.order_by('-created_at')

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
        self.check_auditor_permissions(request, 'create')
        serializer = ComplianceRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant from user
        tenant = request.user.tenant if hasattr(request.user, 'tenant') and request.user.tenant else None
        if not tenant:
            return Response(
                {'error': 'User must belong to a tenant to create compliance runs'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get resource references
        asset_id = serializer.validated_data.get('asset_id')
        dataset_id = serializer.validated_data.get('dataset_id')
        file_id = serializer.validated_data.get('file_id')
        scan_mode = serializer.validated_data.get('scan_mode', 'internal')
        applicable_regulations = serializer.validated_data.get('applicable_regulations')

        # Determine applicable regulations (explicit request > tenant default > platform default)
        regimes_source = None
        if not applicable_regulations:
            # Get tenant default from TenantConfig (with platform default fallback)
            applicable_regulations = get_tenant_compliance_regimes(str(tenant.id))
            regimes_source = "tenant_config" if applicable_regulations != ["GDPR", "LGPD"] else "platform_default"
            logger.info(
                "compliance_regimes_selected",
                tenant_id=str(tenant.id),
                regimes=applicable_regulations,
                source=regimes_source,
                message=f"Using {regimes_source} regimes: {applicable_regulations}"
            )
        else:
            # Explicit regimes in request (user override)
            regimes_source = "request_override"

            # Validate that provided regimes are subset of allowed_compliance_regimes
            tenant_config = get_tenant_config(tenant)
            allowed_regimes = tenant_config.get("allowed_compliance_regimes", VALID_COMPLIANCE_REGIMES)

            invalid_regimes = [r for r in applicable_regulations if r not in allowed_regimes]
            if invalid_regimes:
                return Response(
                    {
                        'error': f'Invalid compliance regimes: {invalid_regimes}. '
                                f'Allowed regimes for this tenant: {allowed_regimes}'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(
                "compliance_regimes_selected",
                tenant_id=str(tenant.id),
                regimes=applicable_regulations,
                source=regimes_source,
                message=f"Using explicit regimes from request: {applicable_regulations}"
            )

        # Resolve resources
        asset = None
        dataset = None
        file_obj = None

        if asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Asset.DoesNotExist:
                return Response(
                    {'error': 'Asset not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        if dataset_id:
            try:
                from hub.apps.datasets.models import Dataset
                dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)
                if asset and dataset.asset != asset:
                    return Response(
                        {'error': 'Dataset does not belong to the specified asset'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if not asset and dataset.asset:
                    asset = dataset.asset
            except Dataset.DoesNotExist:
                return Response(
                    {'error': 'Dataset not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        if file_id:
            try:
                from hub.apps.files.models import File
                file_obj = File.objects.get(id=file_id, tenant=tenant)
            except File.DoesNotExist:
                return Response(
                    {'error': 'File not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Create a temporary UUID for resource_id (will be updated after compliance_run is created)
        import uuid
        temp_resource_id = str(uuid.uuid4())

        # Create job first (needed for ComplianceRun creation)
        job = create_job(
            tenant=tenant,
            user=request.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=temp_resource_id,  # Temporary, will be updated
            details_json={
                'scan_mode': scan_mode,
                'applicable_regulations': applicable_regulations or []
            },
            timeout_seconds=get_job_timeout(JobType.COMPLIANCE_RUN)
        )

        # Create compliance run record with job
        compliance_run = ComplianceRun.objects.create(
            tenant=tenant,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            job=job,
            status=ComplianceRunStatus.PENDING
        )

        # Update job with compliance_run_id
        job.resource_id = str(compliance_run.id)
        job.details_json['compliance_run_id'] = str(compliance_run.id)
        job.save(update_fields=['resource_id', 'details_json'])

        # Enqueue job for processing
        from hub.apps.jobs.tasks import process_job
        from django_rq import get_queue

        queue = get_queue('default')
        queue.enqueue(
            process_job,
            str(job.id),
            job_type=JobType.COMPLIANCE_RUN,
            timeout=get_job_timeout(JobType.COMPLIANCE_RUN)
        )

        # Log audit event
        create_audit_event(
            resource_type="COMPLIANCE_RUN",
            action="COMPLIANCE_RUN_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(compliance_run.id),
            details={
                'scan_mode': scan_mode,
                'applicable_regulations': applicable_regulations,
                'asset_id': str(asset.id) if asset else None,
                'dataset_id': str(dataset.id) if dataset else None,
                'file_id': str(file_obj.id) if file_obj else None
            },
            request=request
        )

        return Response(
            ComplianceRunSerializer(compliance_run).data,
            status=status.HTTP_201_CREATED
        )

    def list(self, request, *args, **kwargs):
        """List compliance runs (tenant-scoped)"""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve compliance run by ID"""
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update compliance run (full update)"""
        self.check_auditor_permissions(request, 'update')
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Update compliance run (partial update)"""
        self.check_auditor_permissions(request, 'partial_update')
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete compliance run"""
        self.check_auditor_permissions(request, 'destroy')
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        operation_id='get_compliance_run_results',
        responses={
            200: inline_serializer(
                name='ComplianceRunResultsResponse',
                fields={
                    'compliance_run_id': serializers.UUIDField(),
                    'overall_status': serializers.CharField(),
                    'risk_level': serializers.CharField(),
                    'allowed_to_store': serializers.BooleanField(),
                    'compliance_score': serializers.FloatField(allow_null=True),
                    'score_breakdown': serializers.DictField(),
                    'violations': serializers.ListField(),
                    'violation_details': serializers.ListField(),
                    'remediation_suggestions': serializers.ListField(),
                    'risk_assessment': serializers.DictField(),
                    'violation_timeline': serializers.ListField(),
                    'regulations': serializers.ListField(),
                    'detected_categories': serializers.DictField(),
                    'column_findings': serializers.ListField(),
                    'started_at': serializers.DateTimeField(allow_null=True),
                    'completed_at': serializers.DateTimeField(allow_null=True)
                }
            ),
            404: OpenApiResponse(description='Compliance run not found')
        },
        tags=['Compliance']
    )
    @action(detail=True, methods=['get'], url_path='results')
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
        from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse
        from rest_framework import serializers

        compliance_run = self.get_object()

        # Extract data from compliance run
        column_findings = compliance_run.column_findings_json or []
        regulation_mapping = compliance_run.regulation_mapping_json or {}
        detected_categories = compliance_run.detected_categories_json or {}

        # Build violation details from column findings
        violations = []
        violation_details = []
        remediation_suggestions = []

        for finding in column_findings:
            column_name = finding.get('column_name', 'Unknown')
            pii_types = finding.get('pii_types', [])
            risk_score = finding.get('risk_score', 0.0)

            for pii_type in pii_types:
                violation = {
                    'column': column_name,
                    'pii_type': pii_type,
                    'risk_score': risk_score,
                    'severity': 'HIGH' if risk_score > 0.7 else 'MEDIUM' if risk_score > 0.4 else 'LOW'
                }
                violations.append(violation)

                # Add detailed violation information
                violation_detail = {
                    'column': column_name,
                    'pii_type': pii_type,
                    'risk_score': risk_score,
                    'severity': violation['severity'],
                    'regulations_affected': finding.get('regulations_affected', []),
                    'detection_confidence': finding.get('confidence', 0.0),
                    'sample_values': finding.get('sample_values', [])[:3]  # Limit to 3 samples
                }
                violation_details.append(violation_detail)

                # Generate remediation suggestions
                if pii_type in ['EMAIL', 'PHONE', 'SSN', 'CREDIT_CARD']:
                    remediation_suggestions.append({
                        'column': column_name,
                        'pii_type': pii_type,
                        'suggestion': f'Consider masking or redacting {pii_type} data in column {column_name}',
                        'priority': 'HIGH' if risk_score > 0.7 else 'MEDIUM'
                    })

        # Calculate compliance score breakdown
        total_columns = len(column_findings) if column_findings else 1
        columns_with_pii = len([f for f in column_findings if f.get('pii_types')])
        columns_without_pii = total_columns - columns_with_pii

        compliance_score = 100.0
        if total_columns > 0:
            # Reduce score based on PII detection
            pii_penalty = (columns_with_pii / total_columns) * 50  # Max 50 point penalty
            compliance_score = max(0, 100 - pii_penalty)

        score_breakdown = {
            'total_columns': total_columns,
            'columns_with_pii': columns_with_pii,
            'columns_without_pii': columns_without_pii,
            'pii_detection_rate': columns_with_pii / total_columns if total_columns > 0 else 0,
            'base_score': 100,
            'pii_penalty': pii_penalty if total_columns > 0 else 0,
            'final_score': compliance_score
        }

        # Build risk assessment
        risk_assessment = {
            'overall_risk_level': compliance_run.risk_level or 'UNKNOWN',
            'risk_score': regulation_mapping.get('metering', {}).get('risk_score', 0.0),
            'allowed_to_store': compliance_run.allowed_to_store,
            'total_violations': len(violations),
            'high_severity_violations': len([v for v in violations if v['severity'] == 'HIGH']),
            'medium_severity_violations': len([v for v in violations if v['severity'] == 'MEDIUM']),
            'low_severity_violations': len([v for v in violations if v['severity'] == 'LOW']),
            'regulations_checked': compliance_run.regulations or [],
            'recommendations': []
        }

        # Add recommendations based on risk level
        if compliance_run.risk_level == 'CRITICAL':
            risk_assessment['recommendations'].append('Immediate action required: Data contains high-risk PII')
        elif compliance_run.risk_level == 'HIGH':
            risk_assessment['recommendations'].append('Review and remediate high-risk PII detections')
        elif compliance_run.risk_level == 'MEDIUM':
            risk_assessment['recommendations'].append('Consider implementing data masking for detected PII')

        # Build violation timeline (simplified - just use created_at for now)
        violation_timeline = []
        if compliance_run.completed_at:
            violation_timeline.append({
                'timestamp': compliance_run.completed_at.isoformat(),
                'event': 'Compliance scan completed',
                'violations_detected': len(violations),
                'risk_level': compliance_run.risk_level
            })

        # Log audit event
        create_audit_event(
            resource_type="COMPLIANCE_RUN",
            action="RESULTS_ACCESSED",
            actor_user=request.user,
            tenant=compliance_run.tenant,
            resource_id=str(compliance_run.id),
            details={},
            request=request
        )

        return Response({
            'compliance_run_id': str(compliance_run.id),
            'overall_status': compliance_run.overall_status,
            'risk_level': compliance_run.risk_level,
            'allowed_to_store': compliance_run.allowed_to_store,
            'compliance_score': compliance_score,
            'score_breakdown': score_breakdown,
            'violations': violations,
            'violation_details': violation_details,
            'remediation_suggestions': remediation_suggestions,
            'risk_assessment': risk_assessment,
            'violation_timeline': violation_timeline,
            'regulations': compliance_run.regulations or [],
            'detected_categories': detected_categories,
            'column_findings': column_findings,
            'started_at': compliance_run.started_at.isoformat() if compliance_run.started_at else None,
            'completed_at': compliance_run.completed_at.isoformat() if compliance_run.completed_at else None
        }, status=status.HTTP_200_OK)


def execute_compliance_run(compliance_run_id: str) -> None:
    """
    Execute a compliance run.

    This function is called by the job worker to process a compliance run.

    Args:
        compliance_run_id: Compliance run ID
    """
    from hub.apps.files.storage import S3StorageClient
    from hub.apps.files.models import File as FileModel

    compliance_run = ComplianceRun.objects.get(id=compliance_run_id)
    compliance_run.status = ComplianceRunStatus.RUNNING
    compliance_run.started_at = timezone.now()
    compliance_run.save(update_fields=['status', 'started_at'])

    try:
        # Get scan mode and regulations from job details
        scan_mode = compliance_run.job.details_json.get('scan_mode', 'internal')
        applicable_regulations = compliance_run.job.details_json.get('applicable_regulations', [])

        # Get file content
        file_obj = None
        file_format = None

        if compliance_run.file:
            file_obj = compliance_run.file
            file_format = file_obj.name.split('.')[-1].lower() if '.' in file_obj.name else 'csv'
        elif compliance_run.dataset and compliance_run.dataset.file:
            file_obj = compliance_run.dataset.file
            file_format = compliance_run.dataset.format.lower() if compliance_run.dataset.format else 'csv'
        elif compliance_run.asset:
            # Get latest dataset for asset
            dataset = compliance_run.asset.datasets.order_by('-version').first()
            if dataset and dataset.file:
                file_obj = dataset.file
                file_format = dataset.format.lower() if dataset.format else 'csv'

        if not file_obj:
            raise ValueError("No file found for compliance run")

        # Download file from storage (for internal mode)
        # For external/scan-only mode, file should already be available
        storage_client = S3StorageClient()
        file_content = storage_client.download_file(file_obj.storage_path)

        # Call compliance service
        compliance_client = ComplianceServiceClient()
        result = compliance_client.scan_file(
            file_content=file_content,
            file_format=file_format,
            scan_mode=scan_mode,
            applicable_regulations=applicable_regulations if applicable_regulations else None
        )

        # Update compliance run with results
        compliance_run.status = ComplianceRunStatus.SUCCEEDED
        compliance_run.overall_status = result.get('overall_status')
        compliance_run.risk_level = result.get('risk_level')
        compliance_run.allowed_to_store = result.get('allowed_to_store')
        compliance_run.detected_categories_json = result.get('detected_categories', [])
        compliance_run.column_findings_json = result.get('column_findings', [])
        # Initialize regulation_mapping_json with result data, metering will be added below
        compliance_run.regulation_mapping_json = result.get('regulation_mapping', {})
        compliance_run.regulations = result.get('applicable_regulations', [])

        # Calculate execution time for metering
        execution_time = (timezone.now() - compliance_run.started_at).total_seconds()

        # Store metering information in regulation_mapping_json
        metadata = result.get('metadata', {})
        if not compliance_run.regulation_mapping_json:
            compliance_run.regulation_mapping_json = {}
        compliance_run.regulation_mapping_json['metering'] = {
            'operation_type': 'COMPLIANCE_RUN',
            'rows_scanned': metadata.get('total_rows', 0),
            'columns_scanned': metadata.get('total_columns', 0),
            'execution_time_seconds': round(execution_time, 2),
            'scan_mode': scan_mode,
            'risk_score': result.get('risk_score', 0.0),
            'risk_level': result.get('risk_level'),
            'allowed_to_store': result.get('allowed_to_store'),
            'regulations_checked': result.get('applicable_regulations', [])
        }

        compliance_run.completed_at = timezone.now()
        compliance_run.save(update_fields=[
            'status', 'overall_status', 'risk_level', 'allowed_to_store',
            'detected_categories_json', 'column_findings_json', 'regulation_mapping_json',
            'regulations', 'completed_at'
        ])

        # Update asset compliance status if applicable
        if compliance_run.asset:
            # Map overall_status to Asset compliance status
            if compliance_run.overall_status == 'PASS':
                comp_status = AssetComplianceStatus.PASS
            elif compliance_run.overall_status == 'WARN':
                comp_status = AssetComplianceStatus.WARN
            elif compliance_run.overall_status == 'FAIL':
                comp_status = AssetComplianceStatus.FAIL
            else:
                comp_status = AssetComplianceStatus.UNKNOWN

            compliance_run.asset.compliance_status = comp_status
            compliance_run.asset.save(update_fields=['compliance_status'])

        # Fail-closed enforcement: if allowed_to_store is False, block storage
        if not compliance_run.allowed_to_store:
            # This will be enforced at the ingestion/asset activation level
            # Log warning for now
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Compliance run {compliance_run_id} determined allowed_to_store=False. "
                f"Storage should be blocked for asset {compliance_run.asset.id if compliance_run.asset else 'N/A'}"
            )

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Compliance run {compliance_run_id} failed: {e}", exc_info=True)

        compliance_run.status = ComplianceRunStatus.FAILED
        # For fail-closed, if service fails, we should block storage
        compliance_run.allowed_to_store = False
        compliance_run.regulation_mapping_json = {
            'error': str(e),
            'error_type': type(e).__name__,
            'fail_closed': True
        }
        compliance_run.completed_at = timezone.now()
        compliance_run.save(update_fields=['status', 'allowed_to_store', 'regulation_mapping_json', 'completed_at'])

