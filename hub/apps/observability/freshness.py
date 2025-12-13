"""
Data Freshness Monitoring

Tracks last update time, calculates freshness age, defines SLAs, and detects stale data.
"""
from typing import Dict, List, Any, Optional
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Max, Min, Avg
import structlog
import hashlib
import json

from .models import DataObservabilityMetric, FreshnessSLA
from hub.apps.datasets.models import Dataset
from hub.apps.assets.models import Asset

logger = structlog.get_logger(__name__)


class FreshnessMonitor:
    """
    Monitors data freshness for datasets and assets.
    """
    
    # SLA definitions in seconds
    SLA_SECONDS = {
        FreshnessSLA.REAL_TIME: 60,  # 1 minute
        FreshnessSLA.NEAR_REAL_TIME: 300,  # 5 minutes
        FreshnessSLA.HOURLY: 3600,  # 1 hour
        FreshnessSLA.DAILY: 86400,  # 24 hours
        FreshnessSLA.WEEKLY: 604800,  # 7 days
        FreshnessSLA.MONTHLY: 2592000,  # 30 days
        FreshnessSLA.ON_DEMAND: None,  # No SLA
    }
    
    @staticmethod
    def get_sla_seconds(sla: str) -> Optional[int]:
        """Get SLA threshold in seconds"""
        return FreshnessMonitor.SLA_SECONDS.get(sla)
    
    @staticmethod
    def calculate_freshness_age(last_update_time: Optional[timezone.datetime]) -> Optional[int]:
        """
        Calculate freshness age in seconds.
        
        Args:
            last_update_time: Last update timestamp
        
        Returns:
            Age in seconds, or None if last_update_time is None
        """
        if last_update_time is None:
            return None
        
        now = timezone.now()
        delta = now - last_update_time
        return int(delta.total_seconds())
    
    @staticmethod
    def is_stale(freshness_age_seconds: Optional[int], sla_seconds: Optional[int]) -> bool:
        """
        Check if data is stale (exceeds SLA).
        
        Args:
            freshness_age_seconds: Age of data in seconds
            sla_seconds: SLA threshold in seconds
        
        Returns:
            True if stale, False otherwise
        """
        if freshness_age_seconds is None:
            return False  # Unknown freshness, not considered stale
        
        if sla_seconds is None:
            return False  # No SLA, never stale
        
        return freshness_age_seconds > sla_seconds
    
    @classmethod
    @transaction.atomic
    def record_metric(
        cls,
        tenant_id: str,
        dataset: Optional[Dataset] = None,
        asset: Optional[Asset] = None,
        last_update_time: Optional[timezone.datetime] = None,
        freshness_sla: Optional[str] = None,
        row_count: Optional[int] = None,
        size_bytes: Optional[int] = None,
        schema_json: Optional[Dict[str, Any]] = None
    ) -> DataObservabilityMetric:
        """
        Record a data observability metric.
        
        Args:
            tenant_id: Tenant UUID
            dataset: Dataset instance (optional)
            asset: Asset instance (optional)
            last_update_time: Last update timestamp
            freshness_sla: Freshness SLA level
            row_count: Number of rows
            size_bytes: Size in bytes
            schema_json: Schema JSON for drift detection
        
        Returns:
            Created DataObservabilityMetric instance
        """
        if not dataset and not asset:
            raise ValueError("Either dataset or asset must be provided")
        
        # Calculate freshness age
        freshness_age_seconds = cls.calculate_freshness_age(last_update_time)
        
        # Get SLA threshold
        sla_seconds = cls.get_sla_seconds(freshness_sla) if freshness_sla else None
        
        # Check if stale
        is_stale_flag = cls.is_stale(freshness_age_seconds, sla_seconds)
        
        # Calculate schema hash
        schema_hash = None
        if schema_json:
            schema_str = json.dumps(schema_json, sort_keys=True)
            schema_hash = hashlib.sha256(schema_str.encode('utf-8')).hexdigest()
        
        # Create metric
        metric = DataObservabilityMetric.objects.create(
            tenant_id=tenant_id,
            dataset=dataset,
            asset=asset,
            last_update_time=last_update_time,
            freshness_age_seconds=freshness_age_seconds,
            freshness_sla=freshness_sla,
            freshness_sla_seconds=sla_seconds,
            is_stale=is_stale_flag,
            row_count=row_count,
            size_bytes=size_bytes,
            schema_hash=schema_hash,
            schema_json=schema_json
        )
        
        logger.info(
            "Data observability metric recorded",
            metric_id=str(metric.id),
            dataset_id=str(dataset.id) if dataset else None,
            asset_id=str(asset.id) if asset else None,
            freshness_age_seconds=freshness_age_seconds,
            is_stale=is_stale_flag
        )
        
        return metric
    
    @classmethod
    def get_freshness_dashboard(
        cls,
        tenant_id: str,
        dataset_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get freshness dashboard data.
        
        Args:
            tenant_id: Tenant UUID
            dataset_id: Optional dataset UUID filter
            asset_id: Optional asset UUID filter
            limit: Maximum number of records to return
        
        Returns:
            Dashboard data dictionary
        """
        queryset = DataObservabilityMetric.objects.filter(tenant_id=tenant_id)
        
        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)
        
        # Get latest metrics
        latest_metrics = queryset.order_by('-recorded_at')[:limit]
        
        # Calculate statistics
        total_metrics = queryset.count()
        stale_count = queryset.filter(is_stale=True).count()
        fresh_count = total_metrics - stale_count
        
        # Get SLA distribution
        sla_distribution = {}
        for sla in FreshnessSLA.values:
            sla_count = queryset.filter(freshness_sla=sla).count()
            if sla_count > 0:
                sla_distribution[sla] = sla_count
        
        # Get average freshness age
        avg_freshness = queryset.exclude(freshness_age_seconds__isnull=True).aggregate(
            avg_age=Avg('freshness_age_seconds')
        )
        
        # Format results
        results = []
        for metric in latest_metrics:
            results.append({
                "id": str(metric.id),
                "dataset_id": str(metric.dataset_id) if metric.dataset else None,
                "asset_id": str(metric.asset_id) if metric.asset else None,
                "last_update_time": metric.last_update_time.isoformat() if metric.last_update_time else None,
                "freshness_age_seconds": metric.freshness_age_seconds,
                "freshness_sla": metric.freshness_sla,
                "is_stale": metric.is_stale,
                "recorded_at": metric.recorded_at.isoformat()
            })
        
        return {
            "results": results,
            "summary": {
                "total_metrics": total_metrics,
                "stale_count": stale_count,
                "fresh_count": fresh_count,
                "stale_percentage": round((stale_count / total_metrics * 100) if total_metrics > 0 else 0, 2),
                "avg_freshness_age_seconds": int(avg_freshness["avg_age"]) if avg_freshness["avg_age"] else None,
                "sla_distribution": sla_distribution
            }
        }
    
    @classmethod
    def detect_stale_data(
        cls,
        tenant_id: str,
        dataset_id: Optional[str] = None,
        asset_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect all stale data (exceeds SLA).
        
        Args:
            tenant_id: Tenant UUID
            dataset_id: Optional dataset UUID filter
            asset_id: Optional asset UUID filter
        
        Returns:
            List of stale data records
        """
        queryset = DataObservabilityMetric.objects.filter(
            tenant_id=tenant_id,
            is_stale=True
        )
        
        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)
        
        # Get latest stale record per resource
        stale_records = []
        
        if dataset_id:
            # Get latest stale record for this dataset
            latest = queryset.filter(dataset_id=dataset_id).order_by('-recorded_at').first()
            if latest:
                stale_records.append({
                    "dataset_id": str(latest.dataset_id),
                    "asset_id": str(latest.asset_id) if latest.asset else None,
                    "last_update_time": latest.last_update_time.isoformat() if latest.last_update_time else None,
                    "freshness_age_seconds": latest.freshness_age_seconds,
                    "freshness_sla": latest.freshness_sla,
                    "recorded_at": latest.recorded_at.isoformat()
                })
        elif asset_id:
            # Get latest stale record for this asset
            latest = queryset.filter(asset_id=asset_id).order_by('-recorded_at').first()
            if latest:
                stale_records.append({
                    "dataset_id": str(latest.dataset_id) if latest.dataset else None,
                    "asset_id": str(latest.asset_id),
                    "last_update_time": latest.last_update_time.isoformat() if latest.last_update_time else None,
                    "freshness_age_seconds": latest.freshness_age_seconds,
                    "freshness_sla": latest.freshness_sla,
                    "recorded_at": latest.recorded_at.isoformat()
                })
        else:
            # Get latest stale record per dataset/asset
            from django.db.models import OuterRef, Subquery
            
            # For datasets
            dataset_latest = queryset.filter(
                dataset__isnull=False
            ).values('dataset_id').annotate(
                latest_recorded=Max('recorded_at')
            )
            
            for item in dataset_latest:
                latest = queryset.filter(
                    dataset_id=item['dataset_id'],
                    recorded_at=item['latest_recorded']
                ).first()
                if latest:
                    stale_records.append({
                        "dataset_id": str(latest.dataset_id),
                        "asset_id": str(latest.asset_id) if latest.asset else None,
                        "last_update_time": latest.last_update_time.isoformat() if latest.last_update_time else None,
                        "freshness_age_seconds": latest.freshness_age_seconds,
                        "freshness_sla": latest.freshness_sla,
                        "recorded_at": latest.recorded_at.isoformat()
                    })
            
            # For assets
            asset_latest = queryset.filter(
                asset__isnull=False,
                dataset__isnull=True
            ).values('asset_id').annotate(
                latest_recorded=Max('recorded_at')
            )
            
            for item in asset_latest:
                latest = queryset.filter(
                    asset_id=item['asset_id'],
                    recorded_at=item['latest_recorded']
                ).first()
                if latest:
                    stale_records.append({
                        "dataset_id": None,
                        "asset_id": str(latest.asset_id),
                        "last_update_time": latest.last_update_time.isoformat() if latest.last_update_time else None,
                        "freshness_age_seconds": latest.freshness_age_seconds,
                        "freshness_sla": latest.freshness_sla,
                        "recorded_at": latest.recorded_at.isoformat()
                    })
        
        return stale_records

