"""
Data Incident Management Service

Manages data incidents through lifecycle: DETECTED → TRIAGED → IN_PROGRESS → RESOLVED
"""
from typing import Optional, Dict, Any, List
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.db import transaction

from .models import DataIncident


class IncidentManager:
    """
    Data incident management service.
    """
    
    @staticmethod
    def create_incident(
        tenant_id: str,
        title: str,
        description: str,
        incident_type: str,
        severity: str = "MEDIUM",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        detected_by_id: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None
    ) -> DataIncident:
        """
        Create a new data incident.
        
        Args:
            tenant_id: Tenant UUID
            title: Incident title
            description: Incident description
            incident_type: Type of incident
            severity: Incident severity (CRITICAL, HIGH, MEDIUM, LOW)
            resource_type: Resource type (DATASET, ASSET, etc.)
            resource_id: Resource UUID
            detected_by_id: User UUID who detected the incident
            metadata_json: Additional metadata
            
        Returns:
            DataIncident instance
        """
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        tenant = Tenant.objects.get(id=tenant_id)
        
        detected_by = None
        if detected_by_id:
            detected_by = User.objects.get(id=detected_by_id)
        
        incident = DataIncident.objects.create(
            tenant=tenant,
            title=title,
            description=description,
            incident_type=incident_type,
            severity=severity,
            status="DETECTED",
            resource_type=resource_type,
            resource_id=resource_id,
            detected_by=detected_by,
            metadata_json=metadata_json or {}
        )
        
        return incident
    
    @staticmethod
    def update_incident_status(
        incident_id: str,
        status: str,
        assigned_to_id: Optional[str] = None,
        root_cause: Optional[str] = None,
        resolution_notes: Optional[str] = None,
        resolved_by_id: Optional[str] = None
    ) -> DataIncident:
        """
        Update incident status and lifecycle.
        
        Args:
            incident_id: Incident UUID
            status: New status (TRIAGED, IN_PROGRESS, RESOLVED)
            assigned_to_id: User UUID to assign incident to
            root_cause: Root cause analysis
            resolution_notes: Resolution notes
            resolved_by_id: User UUID who resolved the incident
            
        Returns:
            Updated DataIncident instance
        """
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        incident = DataIncident.objects.get(id=incident_id)
        
        update_fields = ['status', 'updated_at']
        
        # Update status
        incident.status = status
        
        # Update lifecycle timestamps
        now = timezone.now()
        
        if status == "TRIAGED" and not incident.triaged_at:
            incident.triaged_at = now
            update_fields.append('triaged_at')
        
        if status == "IN_PROGRESS" and not incident.in_progress_at:
            incident.in_progress_at = now
            update_fields.append('in_progress_at')
        
        if status == "RESOLVED" and not incident.resolved_at:
            incident.resolved_at = now
            update_fields.append('resolved_at')
            
            # Calculate resolution time
            if incident.detected_at:
                incident.resolution_time_seconds = int(
                    (now - incident.detected_at).total_seconds()
                )
                update_fields.append('resolution_time_seconds')
        
        # Update assignment
        if assigned_to_id:
            assigned_to = User.objects.get(id=assigned_to_id)
            incident.assigned_to = assigned_to
            update_fields.append('assigned_to')
        
        # Update root cause
        if root_cause is not None:
            incident.root_cause = root_cause
            update_fields.append('root_cause')
        
        # Update resolution notes
        if resolution_notes is not None:
            incident.resolution_notes = resolution_notes
            update_fields.append('resolution_notes')
        
        # Update resolved by
        if resolved_by_id:
            resolved_by = User.objects.get(id=resolved_by_id)
            incident.resolved_by = resolved_by
            update_fields.append('resolved_by')
        
        incident.save(update_fields=update_fields)
        
        return incident
    
    @staticmethod
    def assign_incident(
        incident_id: str,
        assigned_to_id: str
    ) -> DataIncident:
        """
        Assign incident to a user.
        
        Args:
            incident_id: Incident UUID
            assigned_to_id: User UUID to assign to
            
        Returns:
            Updated DataIncident instance
        """
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        incident = DataIncident.objects.get(id=incident_id)
        assigned_to = User.objects.get(id=assigned_to_id)
        
        incident.assigned_to = assigned_to
        
        # Auto-transition to IN_PROGRESS if still in DETECTED or TRIAGED
        if incident.status in ["DETECTED", "TRIAGED"]:
            incident.status = "IN_PROGRESS"
            if not incident.in_progress_at:
                incident.in_progress_at = timezone.now()
                incident.save(update_fields=['assigned_to', 'status', 'in_progress_at', 'updated_at'])
            else:
                incident.save(update_fields=['assigned_to', 'status', 'updated_at'])
        else:
            incident.save(update_fields=['assigned_to', 'updated_at'])
        
        return incident
    
    @staticmethod
    def resolve_incident(
        incident_id: str,
        resolution_notes: str,
        root_cause: Optional[str] = None,
        resolved_by_id: Optional[str] = None
    ) -> DataIncident:
        """
        Resolve an incident.
        
        Args:
            incident_id: Incident UUID
            resolution_notes: Resolution notes
            root_cause: Root cause analysis
            resolved_by_id: User UUID who resolved the incident
            
        Returns:
            Updated DataIncident instance
        """
        return IncidentManager.update_incident_status(
            incident_id=incident_id,
            status="RESOLVED",
            root_cause=root_cause,
            resolution_notes=resolution_notes,
            resolved_by_id=resolved_by_id
        )
    
    @staticmethod
    def get_incidents_dashboard(
        tenant_id: str,
        status: Optional[str] = None,
        incident_type: Optional[str] = None,
        severity: Optional[str] = None,
        assigned_to_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get incidents dashboard.
        
        Args:
            tenant_id: Tenant UUID
            status: Optional status filter
            incident_type: Optional incident type filter
            severity: Optional severity filter
            assigned_to_id: Optional assigned user filter
            resource_type: Optional resource type filter
            resource_id: Optional resource ID filter
            limit: Maximum number of incidents to return
            
        Returns:
            Dashboard data dictionary
        """
        from hub.apps.tenants.models import Tenant
        
        tenant = Tenant.objects.get(id=tenant_id)
        
        # Build query
        query = Q(tenant=tenant)
        
        if status:
            query &= Q(status=status)
        
        if incident_type:
            query &= Q(incident_type=incident_type)
        
        if severity:
            query &= Q(severity=severity)
        
        if assigned_to_id:
            query &= Q(assigned_to_id=assigned_to_id)
        
        if resource_type:
            query &= Q(resource_type=resource_type)
        
        if resource_id:
            query &= Q(resource_id=resource_id)
        
        # Get incidents
        incidents = DataIncident.objects.filter(query).order_by('-detected_at')[:limit]
        
        # Calculate statistics
        stats_query = DataIncident.objects.filter(tenant=tenant)
        
        total_incidents = stats_query.count()
        detected_incidents = stats_query.filter(status="DETECTED").count()
        triaged_incidents = stats_query.filter(status="TRIAGED").count()
        in_progress_incidents = stats_query.filter(status="IN_PROGRESS").count()
        resolved_incidents = stats_query.filter(status="RESOLVED").count()
        
        # Get incident type distribution
        incident_types = stats_query.values('incident_type').annotate(
            count=Count('id'),
            resolved_count=Count('id', filter=Q(status="RESOLVED"))
        ).order_by('-count')
        
        # Get severity distribution
        severities = stats_query.values('severity').annotate(
            count=Count('id'),
            resolved_count=Count('id', filter=Q(status="RESOLVED"))
        ).order_by('-count')
        
        # Calculate average resolution time
        avg_resolution_time = stats_query.filter(
            status="RESOLVED",
            resolution_time_seconds__isnull=False
        ).aggregate(avg=Avg('resolution_time_seconds'))['avg']
        
        # Get unassigned incidents
        unassigned_incidents = stats_query.filter(
            assigned_to__isnull=True,
            status__in=["DETECTED", "TRIAGED", "IN_PROGRESS"]
        ).count()
        
        return {
            'results': [
                {
                    'id': str(incident.id),
                    'title': incident.title,
                    'description': incident.description,
                    'incident_type': incident.incident_type,
                    'severity': incident.severity,
                    'status': incident.status,
                    'detected_at': incident.detected_at.isoformat(),
                    'triaged_at': incident.triaged_at.isoformat() if incident.triaged_at else None,
                    'in_progress_at': incident.in_progress_at.isoformat() if incident.in_progress_at else None,
                    'resolved_at': incident.resolved_at.isoformat() if incident.resolved_at else None,
                    'resolution_time_seconds': incident.resolution_time_seconds,
                    'assigned_to_id': str(incident.assigned_to.id) if incident.assigned_to else None,
                    'detected_by_id': str(incident.detected_by.id) if incident.detected_by else None,
                    'resolved_by_id': str(incident.resolved_by.id) if incident.resolved_by else None,
                    'resource_type': incident.resource_type,
                    'resource_id': str(incident.resource_id) if incident.resource_id else None,
                    'root_cause': incident.root_cause,
                    'resolution_notes': incident.resolution_notes,
                    'created_at': incident.created_at.isoformat(),
                    'updated_at': incident.updated_at.isoformat(),
                }
                for incident in incidents
            ],
            'summary': {
                'total_incidents': total_incidents,
                'detected_incidents': detected_incidents,
                'triaged_incidents': triaged_incidents,
                'in_progress_incidents': in_progress_incidents,
                'resolved_incidents': resolved_incidents,
                'unassigned_incidents': unassigned_incidents,
                'avg_resolution_time_seconds': round(avg_resolution_time, 2) if avg_resolution_time else None,
                'incident_types': list(incident_types),
                'severities': list(severities),
            }
        }
    
    @staticmethod
    def auto_detect_incidents(tenant_id: str) -> Dict[str, Any]:
        """
        Automatically detect incidents from SLA violations and other sources.
        
        Args:
            tenant_id: Tenant UUID
            
        Returns:
            Detection results
        """
        from hub.apps.tenants.models import Tenant
        from .data_slas import DataSLAMonitor
        from .models import DataSLA
        
        tenant = Tenant.objects.get(id=tenant_id)
        
        detected_count = 0
        
        # Check for SLA violations
        violated_slas = DataSLA.objects.filter(
            tenant=tenant,
            is_active=True,
            is_violated=True
        )
        
        for sla in violated_slas:
            # Check if incident already exists for this SLA violation
            existing_incident = DataIncident.objects.filter(
                tenant=tenant,
                incident_type="FRESHNESS_VIOLATION" if sla.sla_type == "FRESHNESS"
                else "QUALITY_VIOLATION" if sla.sla_type == "QUALITY"
                else "AVAILABILITY_VIOLATION" if sla.sla_type == "AVAILABILITY"
                else "OTHER",
                resource_type="DATASET" if sla.dataset else "ASSET",
                resource_id=str(sla.dataset.id) if sla.dataset else str(sla.asset.id),
                status__in=["DETECTED", "TRIAGED", "IN_PROGRESS"]
            ).first()
            
            if not existing_incident:
                # Create new incident
                incident_type = (
                    "FRESHNESS_VIOLATION" if sla.sla_type == "FRESHNESS"
                    else "QUALITY_VIOLATION" if sla.sla_type == "QUALITY"
                    else "AVAILABILITY_VIOLATION" if sla.sla_type == "AVAILABILITY"
                    else "OTHER"
                )
                
                severity = "HIGH" if sla.violation_count > 3 else "MEDIUM"
                
                IncidentManager.create_incident(
                    tenant_id=str(tenant.id),
                    title=f"SLA Violation: {sla.name}",
                    description=f"SLA '{sla.name}' is currently violated. Compliance: {sla.current_compliance_percent}%",
                    incident_type=incident_type,
                    severity=severity,
                    resource_type="DATASET" if sla.dataset else "ASSET",
                    resource_id=str(sla.dataset.id) if sla.dataset else str(sla.asset.id),
                    metadata_json={
                        'sla_id': str(sla.id),
                        'sla_type': sla.sla_type,
                        'compliance_percent': sla.current_compliance_percent,
                        'violation_count': sla.violation_count
                    }
                )
                
                detected_count += 1
        
        return {
            'detected_count': detected_count,
            'message': f'Detected {detected_count} new incidents'
        }

