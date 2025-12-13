"""
Ingestion Monitoring Dashboard

Provides real-time dashboard data for ingestion health, success rates, and performance metrics.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from django.db.models import Q, Count, Avg, Sum, Max, Min
from django.utils import timezone
from django.db import models
import structlog

from .models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus
)

logger = structlog.get_logger(__name__)


class IngestionMonitoringDashboard:
    """
    Service for generating ingestion monitoring dashboard data.
    """
    
    @staticmethod
    def get_dashboard(
        tenant_id: str,
        scheduled_ingestion_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get ingestion monitoring dashboard data.
        
        Args:
            tenant_id: Tenant UUID
            scheduled_ingestion_id: Optional specific ingestion ID
            days: Number of days to look back
            
        Returns:
            Dashboard data dictionary
        """
        from hub.apps.tenants.models import Tenant
        
        tenant = Tenant.objects.get(id=tenant_id)
        start_date = timezone.now() - timedelta(days=days)
        
        # Base query
        if scheduled_ingestion_id:
            ingestions = ScheduledIngestion.objects.filter(
                tenant=tenant,
                id=scheduled_ingestion_id
            )
        else:
            ingestions = ScheduledIngestion.objects.filter(tenant=tenant)
        
        # Get runs in time period
        runs_query = ScheduledIngestionRun.objects.filter(
            scheduled_ingestion__tenant=tenant,
            created_at__gte=start_date
        )
        
        if scheduled_ingestion_id:
            runs_query = runs_query.filter(scheduled_ingestion_id=scheduled_ingestion_id)
        
        # Overall statistics
        total_runs = runs_query.count()
        completed_runs = runs_query.filter(status=ScheduledIngestionRunStatus.COMPLETED).count()
        failed_runs = runs_query.filter(status=ScheduledIngestionRunStatus.FAILED).count()
        running_runs = runs_query.filter(status=ScheduledIngestionRunStatus.RUNNING).count()
        pending_runs = runs_query.filter(status=ScheduledIngestionRunStatus.PENDING).count()
        
        # Calculate success rate
        success_rate = (completed_runs / total_runs * 100) if total_runs > 0 else 0.0
        
        # Performance metrics
        completed_runs_with_times = runs_query.filter(
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at__isnull=False,
            completed_at__isnull=False
        )
        
        avg_execution_time = None
        if completed_runs_with_times.exists():
            execution_times = []
            for run in completed_runs_with_times:
                if run.started_at and run.completed_at:
                    execution_times.append(
                        (run.completed_at - run.started_at).total_seconds()
                    )
            if execution_times:
                avg_execution_time = sum(execution_times) / len(execution_times)
        
        # File processing metrics
        total_files_found = runs_query.aggregate(
            total=Sum('files_found')
        )['total'] or 0
        
        total_files_processed = runs_query.aggregate(
            total=Sum('files_processed')
        )['total'] or 0
        
        total_files_failed = runs_query.aggregate(
            total=Sum('files_failed')
        )['total'] or 0
        
        total_datasets_created = runs_query.aggregate(
            total=Sum('datasets_created')
        )['total'] or 0
        
        # Calculate file processing success rate
        file_success_rate = (
            (total_files_processed / total_files_found * 100)
            if total_files_found > 0 else 0.0
        )
        
        # Ingestion health status
        health_status = IngestionMonitoringDashboard._calculate_health_status(
            success_rate=success_rate,
            file_success_rate=file_success_rate,
            failed_runs=failed_runs,
            total_runs=total_runs
        )
        
        # Recent runs
        recent_runs = runs_query.order_by('-created_at')[:10]
        
        # Per-ingestion statistics
        ingestion_stats = []
        for ingestion in ingestions:
            ingestion_runs = runs_query.filter(scheduled_ingestion=ingestion)
            ingestion_completed = ingestion_runs.filter(
                status=ScheduledIngestionRunStatus.COMPLETED
            ).count()
            ingestion_failed = ingestion_runs.filter(
                status=ScheduledIngestionRunStatus.FAILED
            ).count()
            ingestion_total = ingestion_runs.count()
            ingestion_success_rate = (
                (ingestion_completed / ingestion_total * 100)
                if ingestion_total > 0 else 0.0
            )
            
            # Get last run
            last_run = ingestion_runs.order_by('-created_at').first()
            
            ingestion_stats.append({
                'id': str(ingestion.id),
                'name': ingestion.name,
                'status': ingestion.status,
                'total_runs': ingestion_total,
                'completed_runs': ingestion_completed,
                'failed_runs': ingestion_failed,
                'success_rate': round(ingestion_success_rate, 2),
                'last_run_at': last_run.created_at.isoformat() if last_run else None,
                'last_run_status': last_run.status if last_run else None,
                'next_run_at': ingestion.next_run_at.isoformat() if ingestion.next_run_at else None
            })
        
        # Trend data (daily aggregates)
        trend_data = IngestionMonitoringDashboard._get_trend_data(
            runs_query, start_date, days
        )
        
        return {
            'summary': {
                'total_ingestions': ingestions.count(),
                'active_ingestions': ingestions.filter(status='ACTIVE').count(),
                'paused_ingestions': ingestions.filter(status='PAUSED').count(),
                'error_ingestions': ingestions.filter(status='ERROR').count(),
                'total_runs': total_runs,
                'completed_runs': completed_runs,
                'failed_runs': failed_runs,
                'running_runs': running_runs,
                'pending_runs': pending_runs,
                'success_rate_percent': round(success_rate, 2),
                'avg_execution_time_seconds': round(avg_execution_time, 2) if avg_execution_time else None,
                'total_files_found': total_files_found,
                'total_files_processed': total_files_processed,
                'total_files_failed': total_files_failed,
                'file_success_rate_percent': round(file_success_rate, 2),
                'total_datasets_created': total_datasets_created,
                'health_status': health_status
            },
            'ingestions': ingestion_stats,
            'recent_runs': [
                {
                    'id': str(run.id),
                    'scheduled_ingestion_id': str(run.scheduled_ingestion.id),
                    'scheduled_ingestion_name': run.scheduled_ingestion.name,
                    'status': run.status,
                    'started_at': run.started_at.isoformat() if run.started_at else None,
                    'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                    'files_found': run.files_found,
                    'files_processed': run.files_processed,
                    'files_failed': run.files_failed,
                    'datasets_created': run.datasets_created,
                    'error_message': run.error_message,
                    'created_at': run.created_at.isoformat()
                }
                for run in recent_runs
            ],
            'trends': trend_data
        }
    
    @staticmethod
    def _calculate_health_status(
        success_rate: float,
        file_success_rate: float,
        failed_runs: int,
        total_runs: int
    ) -> str:
        """
        Calculate overall health status.
        
        Args:
            success_rate: Run success rate percentage
            file_success_rate: File processing success rate percentage
            failed_runs: Number of failed runs
            total_runs: Total number of runs
            
        Returns:
            Health status: 'HEALTHY', 'DEGRADED', or 'UNHEALTHY'
        """
        failure_rate = (failed_runs / total_runs * 100) if total_runs > 0 else 0.0
        
        # Unhealthy if success rate < 80% or failure rate > 20%
        if success_rate < 80.0 or failure_rate > 20.0:
            return 'UNHEALTHY'
        
        # Degraded if success rate < 95% or file success rate < 90%
        if success_rate < 95.0 or file_success_rate < 90.0:
            return 'DEGRADED'
        
        return 'HEALTHY'
    
    @staticmethod
    def _get_trend_data(
        runs_query: models.QuerySet,
        start_date: datetime,
        days: int
    ) -> List[Dict[str, Any]]:
        """
        Get trend data (daily aggregates).
        
        Args:
            runs_query: QuerySet of runs
            start_date: Start date for trend
            days: Number of days
            
        Returns:
            List of daily trend data
        """
        trend_data = []
        
        for i in range(days):
            day_start = start_date + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            day_runs = runs_query.filter(
                created_at__gte=day_start,
                created_at__lt=day_end
            )
            
            day_completed = day_runs.filter(
                status=ScheduledIngestionRunStatus.COMPLETED
            ).count()
            
            day_failed = day_runs.filter(
                status=ScheduledIngestionRunStatus.FAILED
            ).count()
            
            day_files_processed = day_runs.aggregate(
                total=Sum('files_processed')
            )['total'] or 0
            
            day_datasets_created = day_runs.aggregate(
                total=Sum('datasets_created')
            )['total'] or 0
            
            trend_data.append({
                'date': day_start.date().isoformat(),
                'total_runs': day_runs.count(),
                'completed_runs': day_completed,
                'failed_runs': day_failed,
                'files_processed': day_files_processed,
                'datasets_created': day_datasets_created
            })
        
        return trend_data

