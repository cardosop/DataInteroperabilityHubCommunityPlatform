"""
Audit Logging Views

REST API views for querying and exporting audit events.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse
import csv
import json

from .models import AuditEvent
from .serializers import AuditEventSerializer
from hub.apps.auth.permissions import HasRole


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for audit event querying and export.
    
    Tenant-scoped: users can only see audit events for their tenant.
    Platform admins can see all audit events.
    """
    queryset = AuditEvent.objects.all()
    serializer_class = AuditEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    
    def get_queryset(self):
        """Filter queryset based on user permissions and filters"""
        user = self.request.user
        
        # Platform admins can see all audit events
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = AuditEvent.objects.all()
        else:
            # Regular users can only see audit events for their tenant
            if hasattr(user, "tenant") and user.tenant:
                queryset = AuditEvent.objects.filter(tenant=user.tenant)
            else:
                queryset = AuditEvent.objects.none()
        
        # Apply filters
        resource_type = self.request.query_params.get('resource_type')
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        
        action_filter = self.request.query_params.get('action')
        if action_filter:
            queryset = queryset.filter(action=action_filter)
        
        actor_user_id = self.request.query_params.get('actor_user_id')
        if actor_user_id:
            queryset = queryset.filter(actor_user_id=actor_user_id)
        
        # Time range filters
        start_date = self.request.query_params.get('start_date')
        if start_date:
            try:
                start_dt = timezone.datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                queryset = queryset.filter(timestamp__gte=start_dt)
            except ValueError:
                pass  # Invalid date format, ignore
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            try:
                end_dt = timezone.datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                queryset = queryset.filter(timestamp__lte=end_dt)
            except ValueError:
                pass  # Invalid date format, ignore
        
        return queryset.order_by('-timestamp')
    
    def list(self, request, *args, **kwargs):
        """List audit events with filtering"""
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve audit event by ID"""
        return super().retrieve(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'], url_path='export', url_name='export')
    def export(self, request):
        """
        Export audit events to CSV or JSON.
        
        Query params:
        - format: 'csv' or 'json' (default: 'json')
        - All other filters from list endpoint apply
        """
        # Get format from query params or format suffix (DRF format suffix handling)
        format_type = request.query_params.get('format', 'json').lower()
        # Also check format suffix if available (from DRF format suffix pattern)
        if hasattr(request, 'format') and request.format:
            format_type = request.format.lower()
        
        # Get filtered queryset
        queryset = self.get_queryset()
        
        # Limit export size (safety measure)
        max_export_size = 10000
        if queryset.count() > max_export_size:
            return Response(
                {'error': f'Export size exceeds maximum of {max_export_size} events. Please use filters to reduce the result set.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        events = list(queryset[:max_export_size])
        
        if format_type == 'csv':
            return self._export_csv(events)
        else:
            return self._export_json(events)
    
    def _export_csv(self, events):
        """Export events as CSV"""
        from rest_framework.response import Response
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_events.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Timestamp', 'Tenant', 'Actor User', 'Resource Type', 'Resource ID',
            'Action', 'Result', 'Details'
        ])
        
        for event in events:
            writer.writerow([
                str(event.id),
                event.timestamp.isoformat(),
                event.tenant.name if event.tenant else '',
                event.actor_user.email if event.actor_user else '',
                event.resource_type,
                str(event.resource_id) if event.resource_id else '',
                event.action,
                event.result,
                json.dumps(event.details_json)
            ])
        
        return response
    
    def _export_json(self, events):
        """Export events as JSON"""
        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data)

