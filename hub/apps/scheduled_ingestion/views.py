"""
Scheduled Ingestion Views

DRF viewsets for scheduled ingestion API endpoints.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from django_rq import get_queue

from .models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionStatus,
    ScheduledIngestionRunStatus
)
from .serializers import (
    ScheduledIngestionSerializer,
    ScheduledIngestionCreateSerializer,
    ScheduledIngestionRunSerializer,
    ScheduledIngestionTriggerSerializer
)
from hub.apps.audit.utils import create_audit_event
from hub.apps.jobs.models import Job, JobType
from hub.apps.jobs.utils import create_job

logger = logging.getLogger(__name__)


class ScheduledIngestionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for scheduled ingestion management.
    
    Provides CRUD operations and additional actions for scheduled ingestions.
    """
    serializer_class = ScheduledIngestionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        """Filter queryset by tenant and optional status"""
        if self.request.user.is_platform_admin:
            queryset = ScheduledIngestion.objects.all()
        else:
            # Get tenant from request (set by middleware) or from user
            tenant = getattr(self.request, 'tenant', None)
            if tenant is None and hasattr(self.request.user, 'tenant'):
                tenant = self.request.user.tenant
            
            if tenant is None:
                return ScheduledIngestion.objects.none()
            
            queryset = ScheduledIngestion.objects.filter(tenant=tenant)
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == 'create':
            return ScheduledIngestionCreateSerializer
        return ScheduledIngestionSerializer
    
    def perform_create(self, serializer):
        """Create scheduled ingestion and sync with Prefect"""
        with transaction.atomic():
            # Set tenant and created_by
            tenant = getattr(self.request, 'tenant', None)
            if tenant is None and hasattr(self.request.user, 'tenant'):
                tenant = self.request.user.tenant
            
            if not tenant:
                raise serializers.ValidationError("Tenant is required")
            
            scheduled_ingestion = serializer.save(
                tenant=tenant,
                created_by=self.request.user
            )
            
            # Sync with Prefect (create deployment)
            try:
                import os
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../services/prefect-integration'))
                try:
                    from deployment_sync import DeploymentSyncService
                except ImportError:
                    # Prefect not available - log warning but don't fail creation
                    logger.warning(
                        f"Prefect service not available for scheduled ingestion {scheduled_ingestion.id}. "
                        "Scheduled ingestion created but Prefect deployment will need to be synced later.",
                        exc_info=False
                    )
                    # Leave status as ACTIVE - Prefect sync can be retried later
                    return
                
                prefect_api_url = os.getenv("PREFECT_API_URL", "http://prefect-server:4200/api")
                prefect_api_key = os.getenv("PREFECT_API_KEY", "")
                work_pool_name = scheduled_ingestion.prefect_work_pool_name
                
                service = DeploymentSyncService(
                    prefect_api_url=prefect_api_url,
                    prefect_api_key=prefect_api_key,
                    work_pool_name=work_pool_name
                )
                
                deployment_name = f"{tenant.id}-{scheduled_ingestion.id}"
                import asyncio
                deployment = asyncio.run(service.create_or_update_deployment(
                    scheduled_ingestion_id=scheduled_ingestion.id,
                    tenant_id=tenant.id,
                    deployment_name=deployment_name
                ))
                
                if deployment:
                    scheduled_ingestion.prefect_deployment_id = deployment.id if hasattr(deployment, 'id') else str(deployment)
                    scheduled_ingestion.save()
            except ImportError:
                # Prefect module not available - log warning but don't fail creation
                logger.warning(
                    f"Prefect service not available for scheduled ingestion {scheduled_ingestion.id}. "
                    "Scheduled ingestion created but Prefect deployment will need to be synced later.",
                    exc_info=False
                )
                # Leave status as ACTIVE - Prefect sync can be retried later
            except Exception as e:
                logger.error(
                    f"Failed to sync with Prefect for scheduled ingestion {scheduled_ingestion.id}: {str(e)}",
                    exc_info=True
                )
                # Don't fail creation if Prefect sync fails - can be retried later
                # Only set to ERROR if it's a critical error, not just missing module
                if 'prefect' in str(e).lower() and 'module' in str(e).lower():
                    # Prefect module not available - leave as ACTIVE
                    logger.warning(
                        f"Prefect module not available. Scheduled ingestion {scheduled_ingestion.id} created but Prefect deployment will need to be synced later."
                    )
                else:
                    # Other errors - set to ERROR but don't fail creation
                    scheduled_ingestion.status = ScheduledIngestionStatus.ERROR
                    scheduled_ingestion.error_message = f"Prefect sync failed: {str(e)}"
                    scheduled_ingestion.save()
            
            # Log audit event
            create_audit_event(
                resource_type="SCHEDULED_INGESTION",
                action="CREATED",
                actor_user=self.request.user,
                tenant=tenant,
                resource_id=str(scheduled_ingestion.id),
                details={
                    'name': scheduled_ingestion.name,
                    'source_type': scheduled_ingestion.source_type,
                    'schedule_type': scheduled_ingestion.schedule_type
                }
            )
    
    def perform_update(self, serializer):
        """Update scheduled ingestion and sync with Prefect"""
        scheduled_ingestion = self.get_object()
        old_status = scheduled_ingestion.status
        
        with transaction.atomic():
            updated = serializer.save()
            
            # Sync with Prefect if deployment exists
            if updated.prefect_deployment_id:
                try:
                    import os
                    import sys
                    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../services/prefect-integration'))
                    from deployment_sync import DeploymentSyncService
                    
                    prefect_api_url = os.getenv("PREFECT_API_URL", "http://prefect-server:4200/api")
                    prefect_api_key = os.getenv("PREFECT_API_KEY", "")
                    work_pool_name = updated.prefect_work_pool_name
                    
                    service = DeploymentSyncService(
                        prefect_api_url=prefect_api_url,
                        prefect_api_key=prefect_api_key,
                        work_pool_name=work_pool_name
                    )
                    
                    deployment_name = f"{updated.tenant.id}-{updated.id}"
                    import asyncio
                    deployment = asyncio.run(service.create_or_update_deployment(
                        scheduled_ingestion_id=updated.id,
                        tenant_id=updated.tenant.id,
                        deployment_name=deployment_name
                    ))
                    
                    if deployment:
                        updated.prefect_deployment_id = deployment.id if hasattr(deployment, 'id') else str(deployment)
                        updated.save()
                except Exception as e:
                    logger.error(
                        f"Failed to sync with Prefect for scheduled ingestion {updated.id}: {str(e)}",
                        exc_info=True
                    )
            
            # Log audit event
            tenant = getattr(self.request, 'tenant', updated.tenant)
            create_audit_event(
                resource_type="SCHEDULED_INGESTION",
                action="UPDATED",
                actor_user=self.request.user,
                tenant=tenant,
                resource_id=str(updated.id),
                details={
                    'name': updated.name,
                    'status_changed': old_status != updated.status
                }
            )
    
    def perform_destroy(self, instance):
        """Delete scheduled ingestion and Prefect deployment"""
        tenant = getattr(self.request, 'tenant', instance.tenant)
        
        # Delete Prefect deployment
        if instance.prefect_deployment_id:
            try:
                import os
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../services/prefect-integration'))
                from deployment_sync import DeploymentSyncService
                
                prefect_api_url = os.getenv("PREFECT_API_URL", "http://prefect-server:4200/api")
                prefect_api_key = os.getenv("PREFECT_API_KEY", "")
                
                service = DeploymentSyncService(
                    prefect_api_url=prefect_api_url,
                    prefect_api_key=prefect_api_key
                )
                
                deployment_name = f"{tenant.id}-{instance.id}"
                import asyncio
                asyncio.run(service.delete_deployment(deployment_name))
            except Exception as e:
                logger.error(
                    f"Failed to delete Prefect deployment for scheduled ingestion {instance.id}: {str(e)}",
                    exc_info=True
                )
        
        # Log audit event
        create_audit_event(
            resource_type="SCHEDULED_INGESTION",
            action="DELETED",
            actor_user=self.request.user,
            tenant=tenant,
            resource_id=str(instance.id),
            details={
                'name': instance.name
            }
        )
        
        instance.delete()
    
    @extend_schema(
        operation_id='scheduled_ingestion_trigger',
        request=ScheduledIngestionTriggerSerializer,
        responses={
            200: inline_serializer(
                name='ScheduledIngestionTriggerResponse',
                fields={
                    'scheduled_ingestion_id': serializers.UUIDField(),
                    'flow_run_id': serializers.CharField(),
                    'status': serializers.CharField(),
                    'message': serializers.CharField()
                }
            )
        }
    )
    @action(detail=True, methods=['post'])
    def trigger(self, request, id=None):
        """
        Manually trigger a scheduled ingestion.
        
        Creates a Prefect flow run for the scheduled ingestion.
        """
        scheduled_ingestion = self.get_object()
        serializer = ScheduledIngestionTriggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        parameters = serializer.validated_data.get('parameters', {})
        
        try:
            import os
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../services/prefect-integration'))
            try:
                from prefect.deployments import run_deployment
            except ImportError:
                # Prefect not available - return appropriate error
                return Response(
                    {'error': 'Prefect service is not available. Cannot trigger ingestion.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            deployment_name = f"{scheduled_ingestion.tenant.id}-{scheduled_ingestion.id}"
            
            import asyncio
            flow_run = asyncio.run(run_deployment(
                name=deployment_name,
                parameters=parameters
            ))
            
            # Create run record
            run = ScheduledIngestionRun.objects.create(
                scheduled_ingestion=scheduled_ingestion,
                status=ScheduledIngestionRunStatus.PENDING,
                prefect_flow_run_id=str(flow_run.id)
            )
            
            # Log audit event
            create_audit_event(
                resource_type="SCHEDULED_INGESTION",
                action="TRIGGERED",
                actor_user=request.user,
                tenant=scheduled_ingestion.tenant,
                resource_id=str(scheduled_ingestion.id),
                details={
                    'run_id': str(run.id),
                    'flow_run_id': str(flow_run.id)
                }
            )
            
            return Response({
                'scheduled_ingestion_id': str(scheduled_ingestion.id),
                'run_id': str(run.id),
                'flow_run_id': str(flow_run.id),
                'status': 'success',
                'message': f'Scheduled ingestion {scheduled_ingestion.name} triggered successfully'
            })
        
        except Exception as e:
            logger.error(
                f"Failed to trigger scheduled ingestion {scheduled_ingestion.id}: {str(e)}",
                exc_info=True
            )
            # Return 503 if it's a service unavailability issue, otherwise 500
            if 'prefect' in str(e).lower() or 'module' in str(e).lower():
                return Response(
                    {'error': 'Prefect service is not available. Cannot trigger ingestion.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            return Response(
                {'error': f'Failed to trigger scheduled ingestion: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        operation_id='scheduled_ingestion_runs',
        responses={
            200: ScheduledIngestionRunSerializer(many=True)
        }
    )
    @action(detail=True, methods=['get'])
    def runs(self, request, id=None):
        """
        List runs for a scheduled ingestion.
        """
        scheduled_ingestion = self.get_object()
        runs = ScheduledIngestionRun.objects.filter(
            scheduled_ingestion=scheduled_ingestion
        ).order_by('-created_at')
        
        serializer = ScheduledIngestionRunSerializer(runs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """
        Get ingestion monitoring dashboard.
        
        GET /api/v1/scheduled-ingestions/dashboard/
        """
        from .monitoring import IngestionMonitoringDashboard
        
        tenant = getattr(request, 'tenant', None)
        if tenant is None and hasattr(request.user, 'tenant'):
            tenant = request.user.tenant
        
        if not tenant:
            return Response(
                {"error": "Tenant is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        scheduled_ingestion_id = request.query_params.get('scheduled_ingestion_id')
        days = int(request.query_params.get('days', 30))
        
        dashboard_data = IngestionMonitoringDashboard.get_dashboard(
            tenant_id=str(tenant.id),
            scheduled_ingestion_id=scheduled_ingestion_id,
            days=days
        )
        
        return Response(dashboard_data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='dead-letter-queue')
    def dead_letter_queue(self, request):
        """
        Get Dead Letter Queue dashboard.
        
        GET /api/v1/scheduled-ingestions/dead-letter-queue/
        """
        from .dead_letter_queue import DeadLetterQueueManager
        
        tenant = getattr(request, 'tenant', None)
        if tenant is None and hasattr(request.user, 'tenant'):
            tenant = request.user.tenant
        
        if not tenant:
            return Response(
                {"error": "Tenant is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        scheduled_ingestion_id = request.query_params.get('scheduled_ingestion_id')
        resolution_status = request.query_params.get('resolution_status')
        
        dlq_data = DeadLetterQueueManager.get_dlq_dashboard(
            tenant_id=str(tenant.id),
            scheduled_ingestion_id=scheduled_ingestion_id,
            resolution_status=resolution_status
        )
        
        return Response(dlq_data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='dlq/(?P<dlq_item_id>[^/.]+)/retry')
    def retry_dlq_item(self, request, pk=None, dlq_item_id=None):
        """
        Retry a failed file from Dead Letter Queue.
        
        POST /api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/retry/
        """
        from .dead_letter_queue import DeadLetterQueueManager
        
        success = DeadLetterQueueManager.retry_file(
            dlq_item_id=dlq_item_id,
            user_id=str(request.user.id) if request.user.is_authenticated else None
        )
        
        if success:
            return Response(
                {"message": "Retry initiated"},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Cannot retry - item not in PENDING status"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], url_path='dlq/(?P<dlq_item_id>[^/.]+)/resolve')
    def resolve_dlq_item(self, request, pk=None, dlq_item_id=None):
        """
        Resolve a Dead Letter Queue item.
        
        POST /api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/resolve/
        """
        from .dead_letter_queue import DeadLetterQueueManager
        
        resolution_status = request.data.get('resolution_status')
        resolution_notes = request.data.get('resolution_notes')
        
        if resolution_status not in ['RESOLVED', 'IGNORED']:
            return Response(
                {"error": "Invalid resolution_status. Must be 'RESOLVED' or 'IGNORED'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        DeadLetterQueueManager.resolve_item(
            dlq_item_id=dlq_item_id,
            resolution_status=resolution_status,
            resolution_notes=resolution_notes,
            user_id=str(request.user.id) if request.user.is_authenticated else None
        )
        
        return Response(
            {"message": f"DLQ item marked as {resolution_status}"},
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'], url_path='costs')
    def costs(self, request):
        """
        Get ingestion cost report.
        
        GET /api/v1/scheduled-ingestions/costs/
        """
        from .cost_tracking import CostTrackingManager
        from datetime import datetime
        
        tenant = getattr(request, 'tenant', None)
        if tenant is None and hasattr(request.user, 'tenant'):
            tenant = request.user.tenant
        
        if not tenant:
            return Response(
                {"error": "Tenant is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        scheduled_ingestion_id = request.query_params.get('scheduled_ingestion_id')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        start_date = None
        end_date = None
        
        if start_date_str:
            try:
                start_date = timezone.make_aware(datetime.fromisoformat(start_date_str))
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format. Use ISO format."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if end_date_str:
            try:
                end_date = timezone.make_aware(datetime.fromisoformat(end_date_str))
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format. Use ISO format."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        cost_report = CostTrackingManager.get_cost_report(
            tenant_id=str(tenant.id),
            scheduled_ingestion_id=scheduled_ingestion_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return Response(cost_report, status=status.HTTP_200_OK)
    
    @extend_schema(
        operation_id='get_scheduled_ingestion_credentials',
        responses={
            200: inline_serializer(
                name='CredentialsResponse',
                fields={
                    'scheduled_ingestion_id': serializers.UUIDField(),
                    'source_type': serializers.CharField(),
                    'credential_version': serializers.IntegerField(default=1),
                    'last_tested_at': serializers.DateTimeField(allow_null=True),
                    'last_test_result': serializers.CharField(allow_null=True),
                    'masked_credentials': serializers.DictField(),
                    'metadata': serializers.DictField(allow_null=True)
                }
            ),
            401: OpenApiResponse(description='Unauthorized'),
            403: OpenApiResponse(description='Forbidden'),
            404: OpenApiResponse(description='Scheduled ingestion not found')
        },
        tags=['Scheduled Ingestion']
    )
    @action(detail=True, methods=['get'], url_path='credentials')
    def credentials(self, request, id=None):
        """
        Get masked credentials for scheduled ingestion.
        
        GET /api/v1/scheduled-ingestions/{id}/credentials/
        
        Returns masked credentials (never exposes actual credentials).
        Performance target: < 200ms p95
        """
        scheduled_ingestion = self.get_object()
        
        # Check permissions: User must own the scheduled ingestion or be a TENANT_ADMIN
        if not (request.user.is_platform_admin or (scheduled_ingestion.tenant == request.user.tenant and request.user.has_role('DATA_PROVIDER', 'TENANT_ADMIN'))):
            raise PermissionDenied("You do not have permission to access credentials for this scheduled ingestion.")
        
        from hub.apps.scheduled_ingestion.credential_manager import CredentialManager
        
        try:
            # Get masked credentials
            masked_credentials_data = CredentialManager.get_masked_credentials(scheduled_ingestion)
            
            response_data = {
                'scheduled_ingestion_id': str(scheduled_ingestion.id),
                'source_type': scheduled_ingestion.source_type,
                'credential_version': getattr(scheduled_ingestion, 'credential_version', 1),
                'last_tested_at': scheduled_ingestion.last_credential_test_at.isoformat() if hasattr(scheduled_ingestion, 'last_credential_test_at') and scheduled_ingestion.last_credential_test_at else None,
                'last_test_result': getattr(scheduled_ingestion, 'last_credential_test_result', None),
                'masked_credentials': masked_credentials_data,
                'metadata': {k: v for k, v in (scheduled_ingestion.source_config or {}).items() if k not in CredentialManager.SENSITIVE_FIELDS}  # Include other non-sensitive metadata
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Failed to retrieve masked credentials for {scheduled_ingestion.id}: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to retrieve masked credentials', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    
    @extend_schema(
        operation_id='test_scheduled_ingestion_credentials',
        request=None,
        responses={
            200: inline_serializer(
                name='ConnectionTestResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'message': serializers.CharField(),
                    'tested_at': serializers.DateTimeField(),
                    'connection_details': serializers.DictField(allow_null=True)
                }
            ),
            400: OpenApiResponse(description='Bad Request'),
            401: OpenApiResponse(description='Unauthorized'),
            403: OpenApiResponse(description='Forbidden'),
            404: OpenApiResponse(description='Scheduled ingestion not found'),
            503: OpenApiResponse(description='Connector service unavailable')
        },
        tags=['Scheduled Ingestion']
    )
    @action(detail=True, methods=['post'], url_path='credentials/test')
    def test_credentials(self, request, id=None):
        """
        Test connection with stored credentials.
        
        POST /api/v1/scheduled-ingestions/{id}/credentials/test/
        
        Tests connection to the data source using stored credentials.
        Never exposes credentials in response.
        Performance target: < 5000ms p95 (connection testing can be slow)
        Timeout: 30 seconds
        """
        import time
        scheduled_ingestion = self.get_object()
        
        start_time = time.time()
        
        try:
            # Get source config with credentials
            source_config = scheduled_ingestion.source_config or {}
            
            if not source_config:
                return Response(
                    {'success': False, 'message': 'No source configuration found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Import connector factory
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../services/prefect-integration'))
            
            try:
                from connectors.factory import SourceConnectorFactory
            except ImportError:
                return Response(
                    {'success': False, 'message': 'Connector service is not available'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            # Get connector and test connection
            connector = SourceConnectorFactory.get_connector(scheduled_ingestion.source_type)
            
            # Test connection with timeout (30 seconds)
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Connection test timed out after 30 seconds")
            
            # Set timeout (Unix only)
            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)
            
            try:
                # test_connection returns a boolean
                test_result = connector.test_connection(source_config)
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Clear alarm
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)
                
                # Update last_tested_at and last_test_result (if tracked)
                # TODO: Add last_tested_at and last_test_result fields to ScheduledIngestion model
                
                # Log audit event
                create_audit_event(
                    resource_type="SCHEDULED_INGESTION",
                    action="CREDENTIALS_TESTED",
                    actor_user=request.user,
                    tenant=scheduled_ingestion.tenant,
                    resource_id=str(scheduled_ingestion.id),
                    details={
                        'source_type': scheduled_ingestion.source_type,
                        'test_result': 'success' if test_result else 'failure',
                        'response_time_ms': response_time_ms
                    },
                    request=request
                )
                
                if test_result:
                    return Response({
                        'success': True,
                        'message': 'Connection test successful',
                        'tested_at': timezone.now().isoformat(),
                        'connection_details': {
                            'response_time_ms': response_time_ms
                        }
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'success': False,
                        'message': 'Connection test failed - unable to connect to data source',
                        'tested_at': timezone.now().isoformat(),
                        'connection_details': {
                            'response_time_ms': response_time_ms
                        }
                    }, status=status.HTTP_200_OK)  # Return 200 with success=False for connection failures
            
            except TimeoutError:
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)
                return Response(
                    {'success': False, 'message': 'Connection test timed out after 30 seconds'},
                    status=status.HTTP_504_GATEWAY_TIMEOUT
                )
            except Exception as e:
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)
                logger.error(
                    f"Connection test failed for scheduled ingestion {scheduled_ingestion.id}: {str(e)}",
                    exc_info=True
                )
                return Response({
                    'success': False,
                    'message': f'Connection test failed: {str(e)}',
                    'tested_at': timezone.now().isoformat(),
                    'connection_details': {
                        'response_time_ms': int((time.time() - start_time) * 1000)
                    }
                }, status=status.HTTP_200_OK)  # Return 200 with success=False for connection failures
        
        except Exception as e:
            logger.error(
                f"Failed to test credentials for scheduled ingestion {scheduled_ingestion.id}: {str(e)}",
                exc_info=True
            )
            return Response(
                {'success': False, 'message': f'Failed to test credentials: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ScheduledIngestionRunViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for scheduled ingestion runs.
    """
    serializer_class = ScheduledIngestionRunSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        """Filter queryset by tenant"""
        if self.request.user.is_platform_admin:
            return ScheduledIngestionRun.objects.all()
        
        tenant = getattr(self.request, 'tenant', None)
        if tenant is None and hasattr(self.request.user, 'tenant'):
            tenant = self.request.user.tenant
        
        if tenant is None:
            return ScheduledIngestionRun.objects.none()
        
        return ScheduledIngestionRun.objects.filter(
            scheduled_ingestion__tenant=tenant
        )

