"""
Access Analytics

Tracking access patterns, anomaly detection, and security event tracking.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db.utils import ProgrammingError
from django.db import models
from django.utils import timezone
from django.db.models import Count, Q, Avg
from datetime import timedelta
import uuid
import structlog

logger = structlog.get_logger(__name__)


class AccessLog(models.Model):
    """
    Model for tracking access attempts and patterns.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="access_logs",
        help_text="Tenant this access log belongs to"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="access_logs",
        null=True,
        blank=True,
        help_text="User who made the access attempt"
    )
    resource_type = models.CharField(
        max_length=50,
        help_text="Resource type (ASSET, DATASET, FILE, etc.)"
    )
    resource_id = models.UUIDField(
        help_text="Resource UUID"
    )
    action = models.CharField(
        max_length=20,
        choices=[
            ("READ", "Read"),
            ("WRITE", "Write"),
            ("DELETE", "Delete"),
            ("DOWNLOAD", "Download"),
            ("UPLOAD", "Upload")
        ],
        help_text="Action attempted"
    )
    result = models.CharField(
        max_length=20,
        choices=[
            ("ALLOWED", "Allowed"),
            ("DENIED", "Denied"),
            ("MASKED", "Masked"),
            ("PARTIAL", "Partial")
        ],
        help_text="Access result"
    )
    policy_evaluation = models.JSONField(
        null=True,
        blank=True,
        help_text="Policy evaluation details (policy ID, conditions matched, etc.)"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request"
    )
    user_agent = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="User agent string"
    )
    is_anomaly = models.BooleanField(
        default=False,
        help_text="Whether this access was flagged as anomalous"
    )
    anomaly_reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for anomaly flag"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "access_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "user", "created_at"]),
            models.Index(fields=["tenant", "resource_type", "resource_id", "created_at"]),
            models.Index(fields=["tenant", "action", "result", "created_at"]),
            models.Index(fields=["tenant", "is_anomaly", "created_at"]),
            models.Index(fields=["created_at"]),
        ]
    
    def __str__(self):
        return f"{self.user.email if self.user else 'Unknown'} - {self.action} {self.resource_type} - {self.result}"


class AccessAnalyticsService:
    """
    Service for access analytics and anomaly detection.
    """
    
    @staticmethod
    def log_access(
        tenant_id: str,
        user_id: Optional[str],
        resource_type: str,
        resource_id: str,
        action: str,
        result: str,
        policy_evaluation: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        Log an access attempt.
        
        Args:
            tenant_id: Tenant UUID
            user_id: Optional user UUID
            resource_type: Resource type
            resource_id: Resource UUID
            action: Action attempted
            result: Access result
            policy_evaluation: Optional policy evaluation details
            ip_address: Optional IP address
            user_agent: Optional user agent
        """
        try:
            from django.contrib.auth import get_user_model
            from django.db import transaction

            from hub.apps.tenants.models import Tenant

            User = get_user_model()

            # Use nested atomic so INSERT failure rolls back savepoint without corrupting
            # the request transaction (e.g. when access_logs table does not exist)
            with transaction.atomic():
                tenant = Tenant.objects.get(id=tenant_id)
                user = User.objects.get(id=user_id) if user_id else None

                access_log = AccessLog.objects.create(
                    tenant=tenant,
                    user=user,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                    result=result,
                    policy_evaluation=policy_evaluation,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

                # Check for anomalies asynchronously (in production, use background job)
                AccessAnalyticsService._check_anomalies(access_log)

        except Exception as e:
            # Table may not exist in test DB before governance migrations
            if isinstance(e, ProgrammingError) and "does not exist" in str(e):
                logger.debug(
                    "access_logging_skipped_table_missing",
                    resource_type=resource_type,
                    resource_id=resource_id,
                )
            else:
                logger.warning(
                    "access_logging_failed",
                    error=str(e),
                    resource_type=resource_type,
                    resource_id=resource_id,
                )
    
    @staticmethod
    def _check_anomalies(access_log: AccessLog):
        """Check if access log indicates an anomaly"""
        # Check for unusual access patterns
        anomalies = []
        
        # Check for unusual time access
        hour = access_log.created_at.hour
        if hour < 6 or hour > 22:  # Outside business hours
            anomalies.append("Access outside business hours")
        
        # Check for unusual resource access
        recent_accesses = AccessLog.objects.filter(
            tenant=access_log.tenant,
            user=access_log.user,
            resource_type=access_log.resource_type,
            resource_id=access_log.resource_id,
            created_at__gte=access_log.created_at - timedelta(hours=1)
        ).count()
        
        if recent_accesses > 100:  # Threshold for unusual frequency
            anomalies.append(f"Unusual access frequency: {recent_accesses} accesses in 1 hour")
        
        # Check for denied access patterns
        if access_log.result == "DENIED":
            denied_count = AccessLog.objects.filter(
                tenant=access_log.tenant,
                user=access_log.user,
                result="DENIED",
                created_at__gte=access_log.created_at - timedelta(minutes=5)
            ).count()
            
            if denied_count > 10:  # Multiple denials in short time
                anomalies.append(f"Multiple access denials: {denied_count} in 5 minutes")
        
        # Flag as anomaly if any anomalies detected
        if anomalies:
            access_log.is_anomaly = True
            access_log.anomaly_reason = "; ".join(anomalies)
            access_log.save(update_fields=["is_anomaly", "anomaly_reason"])
    
    @staticmethod
    def get_access_patterns(
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[timezone.datetime] = None,
        end_date: Optional[timezone.datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get access patterns for analysis.
        
        Args:
            tenant_id: Optional tenant UUID filter
            user_id: Optional user UUID filter
            resource_type: Optional resource type filter
            start_date: Optional start date filter
            end_date: Optional end date filter
        
        Returns:
            List of access pattern data
        """
        query = AccessLog.objects.all()
        
        if tenant_id:
            query = query.filter(tenant_id=tenant_id)
        
        if user_id:
            query = query.filter(user_id=user_id)
        
        if resource_type:
            query = query.filter(resource_type=resource_type)
        
        if start_date:
            query = query.filter(created_at__gte=start_date)
        
        if end_date:
            query = query.filter(created_at__lte=end_date)
        
        # Default to last 7 days if no dates provided
        if not start_date and not end_date:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=7)
            query = query.filter(created_at__gte=start_date, created_at__lte=end_date)
        
        # Aggregate by user and resource
        patterns = query.values('user', 'resource_type', 'resource_id', 'action').annotate(
            access_count=Count('id'),
            allowed_count=Count('id', filter=Q(result='ALLOWED')),
            denied_count=Count('id', filter=Q(result='DENIED')),
            anomaly_count=Count('id', filter=Q(is_anomaly=True))
        ).order_by('-access_count')[:100]
        
        result = []
        for pattern in patterns:
            result.append({
                'user_id': str(pattern['user']) if pattern['user'] else None,
                'resource_type': pattern['resource_type'],
                'resource_id': str(pattern['resource_id']),
                'action': pattern['action'],
                'access_count': pattern['access_count'],
                'allowed_count': pattern['allowed_count'],
                'denied_count': pattern['denied_count'],
                'anomaly_count': pattern['anomaly_count']
            })
        
        return result
    
    @staticmethod
    def get_anomalies(
        tenant_id: Optional[str] = None,
        start_date: Optional[timezone.datetime] = None,
        end_date: Optional[timezone.datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get detected anomalies.
        
        Args:
            tenant_id: Optional tenant UUID filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of results
        
        Returns:
            List of anomaly data
        """
        query = AccessLog.objects.filter(is_anomaly=True)
        
        if tenant_id:
            query = query.filter(tenant_id=tenant_id)
        
        if start_date:
            query = query.filter(created_at__gte=start_date)
        
        if end_date:
            query = query.filter(created_at__lte=end_date)
        
        # Default to last 24 hours if no dates provided
        if not start_date and not end_date:
            end_date = timezone.now()
            start_date = end_date - timedelta(hours=24)
            query = query.filter(created_at__gte=start_date, created_at__lte=end_date)
        
        anomalies = query.order_by('-created_at')[:limit]
        
        result = []
        for anomaly in anomalies:
            result.append({
                'id': str(anomaly.id),
                'user_id': str(anomaly.user.id) if anomaly.user else None,
                'user_email': anomaly.user.email if anomaly.user else None,
                'resource_type': anomaly.resource_type,
                'resource_id': str(anomaly.resource_id),
                'action': anomaly.action,
                'result': anomaly.result,
                'anomaly_reason': anomaly.anomaly_reason,
                'ip_address': str(anomaly.ip_address) if anomaly.ip_address else None,
                'created_at': anomaly.created_at.isoformat()
            })
        
        return result
    
    @staticmethod
    def get_security_events(
        tenant_id: Optional[str] = None,
        start_date: Optional[timezone.datetime] = None,
        end_date: Optional[timezone.datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get security events (denied access, anomalies).
        
        Args:
            tenant_id: Optional tenant UUID filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of results
        
        Returns:
            List of security event data
        """
        query = AccessLog.objects.filter(
            Q(result='DENIED') | Q(is_anomaly=True)
        )
        
        if tenant_id:
            query = query.filter(tenant_id=tenant_id)
        
        if start_date:
            query = query.filter(created_at__gte=start_date)
        
        if end_date:
            query = query.filter(created_at__lte=end_date)
        
        # Default to last 24 hours if no dates provided
        if not start_date and not end_date:
            end_date = timezone.now()
            start_date = end_date - timedelta(hours=24)
            query = query.filter(created_at__gte=start_date, created_at__lte=end_date)
        
        events = query.order_by('-created_at')[:limit]
        
        result = []
        for event in events:
            result.append({
                'id': str(event.id),
                'user_id': str(event.user.id) if event.user else None,
                'user_email': event.user.email if event.user else None,
                'resource_type': event.resource_type,
                'resource_id': str(event.resource_id),
                'action': event.action,
                'result': event.result,
                'is_anomaly': event.is_anomaly,
                'anomaly_reason': event.anomaly_reason,
                'ip_address': str(event.ip_address) if event.ip_address else None,
                'created_at': event.created_at.isoformat()
            })
        
        return result
    
    @staticmethod
    def get_analytics_dashboard(
        tenant_id: Optional[str] = None,
        start_date: Optional[timezone.datetime] = None,
        end_date: Optional[timezone.datetime] = None
    ) -> Dict[str, Any]:
        """
        Get complete access analytics dashboard.
        
        Args:
            tenant_id: Optional tenant UUID filter
            start_date: Optional start date filter
            end_date: Optional end date filter
        
        Returns:
            Dictionary with complete dashboard data
        """
        query = AccessLog.objects.all()
        
        if tenant_id:
            query = query.filter(tenant_id=tenant_id)
        
        if start_date:
            query = query.filter(created_at__gte=start_date)
        
        if end_date:
            query = query.filter(created_at__lte=end_date)
        
        # Default to last 7 days if no dates provided
        if not start_date and not end_date:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=7)
            query = query.filter(created_at__gte=start_date, created_at__lte=end_date)
        
        total_accesses = query.count()
        allowed_accesses = query.filter(result='ALLOWED').count()
        denied_accesses = query.filter(result='DENIED').count()
        anomaly_count = query.filter(is_anomaly=True).count()
        
        # Top users by access count
        top_users = query.values('user', 'user__email').annotate(
            access_count=Count('id')
        ).order_by('-access_count')[:10]
        
        # Top resources by access count
        top_resources = query.values('resource_type', 'resource_id').annotate(
            access_count=Count('id')
        ).order_by('-access_count')[:10]
        
        return {
            'summary': {
                'total_accesses': total_accesses,
                'allowed_accesses': allowed_accesses,
                'denied_accesses': denied_accesses,
                'anomaly_count': anomaly_count,
                'denial_rate': round((denied_accesses / total_accesses * 100) if total_accesses > 0 else 0.0, 2),
                'anomaly_rate': round((anomaly_count / total_accesses * 100) if total_accesses > 0 else 0.0, 2)
            },
            'top_users': [
                {
                    'user_id': str(u['user']) if u['user'] else None,
                    'user_email': u.get('user__email'),
                    'access_count': u['access_count']
                }
                for u in top_users
            ],
            'top_resources': [
                {
                    'resource_type': r['resource_type'],
                    'resource_id': str(r['resource_id']),
                    'access_count': r['access_count']
                }
                for r in top_resources
            ],
            'anomalies': AccessAnalyticsService.get_anomalies(
                tenant_id=tenant_id,
                start_date=start_date,
                end_date=end_date,
                limit=20
            ),
            'security_events': AccessAnalyticsService.get_security_events(
                tenant_id=tenant_id,
                start_date=start_date,
                end_date=end_date,
                limit=20
            )
        }

