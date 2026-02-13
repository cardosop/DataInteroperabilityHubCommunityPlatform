"""
Dead Letter Queue for Scheduled Ingestion

Manages permanently failed files with retry logic and manual intervention.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from django.db import models
from django.db.models import Count
import structlog

from .models import ScheduledIngestion, DeadLetterQueueItem
from .incremental_state import IncrementalStateManager

logger = structlog.get_logger(__name__)


def _parse_datetime_aware(value: Optional[str]) -> datetime:
    """Parse ISO datetime string to timezone-aware datetime. Idempotent for already-aware values."""
    if not value:
        return timezone.now()
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


class DeadLetterQueueManager:
    """
    Manager for Dead Letter Queue operations.
    """
    
    @staticmethod
    def sync_from_ingestion_state(scheduled_ingestion_id: str) -> int:
        """
        Sync DLQ items from ingestion state (permanently failed files).
        
        Args:
            scheduled_ingestion_id: Scheduled ingestion UUID
            
        Returns:
            Number of DLQ items created/updated
        """
        scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
        state_manager = IncrementalStateManager(scheduled_ingestion)
        
        failed_files = state_manager.get_failed_files()
        permanent_failures = [
            f for f in failed_files
            if f.get("permanent_failure", False)
        ]
        
        count = 0
        for failure in permanent_failures:
            file_path = failure["file_path"]
            
            # Get or create DLQ item
            dlq_item, created = DeadLetterQueueItem.objects.get_or_create(
                scheduled_ingestion=scheduled_ingestion,
                file_path=file_path,
                defaults={
                    'error_message': failure.get("last_error", "Unknown error"),
                    'error_code': failure.get("last_error_code"),
                    'retry_count': failure.get("retry_count", 0),
                    'first_failed_at': _parse_datetime_aware(failure.get("first_failed_at")),
                    'last_failed_at': _parse_datetime_aware(failure.get("last_failed_at")),
                    'permanently_failed_at': _parse_datetime_aware(failure.get("permanently_failed_at")),
                    'resolution_status': 'PENDING'
                }
            )
            
            if not created:
                # Update existing item
                dlq_item.error_message = failure.get("last_error", dlq_item.error_message)
                dlq_item.error_code = failure.get("last_error_code", dlq_item.error_code)
                dlq_item.retry_count = failure.get("retry_count", dlq_item.retry_count)
                dlq_item.last_failed_at = _parse_datetime_aware(failure.get("last_failed_at"))
                dlq_item.save()
            
            count += 1
        
        logger.info(
            "Synced DLQ items from ingestion state",
            scheduled_ingestion_id=scheduled_ingestion_id,
            items_synced=count
        )
        
        return count
    
    @staticmethod
    @transaction.atomic
    def retry_file(
        dlq_item_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Retry processing a failed file from DLQ.
        
        Args:
            dlq_item_id: DLQ item UUID
            user_id: Optional user UUID who initiated retry
            
        Returns:
            True if retry was initiated, False otherwise
        """
        from hub.apps.users.models import User
        from datetime import datetime
        
        dlq_item = DeadLetterQueueItem.objects.get(id=dlq_item_id)
        
        if dlq_item.resolution_status != 'PENDING':
            logger.warning(
                "Cannot retry DLQ item - not in PENDING status",
                dlq_item_id=dlq_item_id,
                status=dlq_item.resolution_status
            )
            return False
        
        # Clear from ingestion state
        state_manager = IncrementalStateManager(dlq_item.scheduled_ingestion)
        state_manager.clear_failed_file(dlq_item.file_path)
        
        # Update DLQ item
        dlq_item.resolution_status = 'RETRYING'
        dlq_item.retry_count += 1
        if user_id:
            dlq_item.resolved_by = User.objects.get(id=user_id)
        dlq_item.resolved_at = timezone.now()
        dlq_item.resolution_notes = f"Retry initiated (attempt {dlq_item.retry_count})"
        dlq_item.save()
        
        logger.info(
            "DLQ item retry initiated",
            dlq_item_id=dlq_item_id,
            file_path=dlq_item.file_path,
            retry_count=dlq_item.retry_count
        )
        
        return True
    
    @staticmethod
    @transaction.atomic
    def resolve_item(
        dlq_item_id: str,
        resolution_status: str,
        resolution_notes: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        Resolve a DLQ item (mark as resolved or ignored).
        
        Args:
            dlq_item_id: DLQ item UUID
            resolution_status: 'RESOLVED' or 'IGNORED'
            resolution_notes: Optional resolution notes
            user_id: Optional user UUID who resolved
        """
        from hub.apps.users.models import User
        
        if resolution_status not in ['RESOLVED', 'IGNORED']:
            raise ValueError(f"Invalid resolution status: {resolution_status}")
        
        dlq_item = DeadLetterQueueItem.objects.get(id=dlq_item_id)
        
        dlq_item.resolution_status = resolution_status
        dlq_item.resolution_notes = resolution_notes
        if user_id:
            dlq_item.resolved_by = User.objects.get(id=user_id)
        dlq_item.resolved_at = timezone.now()
        dlq_item.save()
        
        # If resolved, clear from ingestion state
        if resolution_status == 'RESOLVED':
            state_manager = IncrementalStateManager(dlq_item.scheduled_ingestion)
            state_manager.clear_failed_file(dlq_item.file_path)
        
        logger.info(
            "DLQ item resolved",
            dlq_item_id=dlq_item_id,
            resolution_status=resolution_status
        )
    
    @staticmethod
    def get_dlq_dashboard(
        tenant_id: str,
        scheduled_ingestion_id: Optional[str] = None,
        resolution_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get Dead Letter Queue dashboard data.
        
        Args:
            tenant_id: Tenant UUID
            scheduled_ingestion_id: Optional specific ingestion ID
            resolution_status: Optional filter by resolution status
            
        Returns:
            Dashboard data dictionary
        """
        from hub.apps.tenants.models import Tenant
        
        tenant = Tenant.objects.get(id=tenant_id)
        
        query = DeadLetterQueueItem.objects.filter(
            scheduled_ingestion__tenant=tenant
        )
        
        if scheduled_ingestion_id:
            query = query.filter(scheduled_ingestion_id=scheduled_ingestion_id)
        
        if resolution_status:
            query = query.filter(resolution_status=resolution_status)
        
        total_items = query.count()
        pending_items = query.filter(resolution_status='PENDING').count()
        retrying_items = query.filter(resolution_status='RETRYING').count()
        resolved_items = query.filter(resolution_status='RESOLVED').count()
        ignored_items = query.filter(resolution_status='IGNORED').count()
        
        # Get items by error code
        error_code_stats = query.values('error_code').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Get recent items
        recent_items = query.order_by('-permanently_failed_at')[:20]
        
        return {
            'summary': {
                'total_items': total_items,
                'pending_items': pending_items,
                'retrying_items': retrying_items,
                'resolved_items': resolved_items,
                'ignored_items': ignored_items
            },
            'error_codes': list(error_code_stats),
            'items': [
                {
                    'id': str(item.id),
                    'scheduled_ingestion_id': str(item.scheduled_ingestion.id),
                    'scheduled_ingestion_name': item.scheduled_ingestion.name,
                    'file_path': item.file_path,
                    'error_message': item.error_message,
                    'error_code': item.error_code,
                    'retry_count': item.retry_count,
                    'first_failed_at': item.first_failed_at.isoformat(),
                    'last_failed_at': item.last_failed_at.isoformat(),
                    'permanently_failed_at': item.permanently_failed_at.isoformat(),
                    'resolution_status': item.resolution_status,
                    'resolution_notes': item.resolution_notes,
                    'resolved_by_id': str(item.resolved_by.id) if item.resolved_by else None,
                    'resolved_at': item.resolved_at.isoformat() if item.resolved_at else None,
                    'created_at': item.created_at.isoformat()
                }
                for item in recent_items
            ]
        }

