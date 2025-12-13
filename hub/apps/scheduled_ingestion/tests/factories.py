"""
Test Factories for Scheduled Ingestion

Real factories (not mocks) for creating test data for ScheduledIngestion models.

NOTE: These factories are placeholders for future scheduled ingestion models.
They will be updated when the scheduled ingestion models are created in Phase 5.
"""
import uuid
from typing import Optional, Dict, Any
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset

User = get_user_model()


class ScheduledIngestionFactory:
    """
    Factory for creating ScheduledIngestion instances.
    
    NOTE: This is a placeholder factory. The actual ScheduledIngestion model
    will be created in Phase 5. This factory will be updated at that time.
    
    Expected model structure (from design.md):
    - id: UUID
    - tenant: ForeignKey to Tenant
    - name: str
    - source_type: str (S3, GCS, Azure, HTTP, FTP, SFTP, DATABASE)
    - source_config: JSONField
    - schedule: str (cron expression)
    - file_pattern: str
    - asset_id: ForeignKey to Asset
    - contract_id: ForeignKey to Contract (optional)
    - status: str (ACTIVE, PAUSED, ERROR)
    - prefect_deployment_id: str (optional)
    - prefect_work_pool_name: str (optional)
    - created_by: ForeignKey to User
    - created_at: DateTime
    - updated_at: DateTime
    """
    
    @staticmethod
    def create_scheduled_ingestion(
        tenant: Tenant,
        asset: Optional[Asset] = None,
        name: Optional[str] = None,
        source_type: str = "S3",
        source_config: Optional[Dict[str, Any]] = None,
        schedule: str = "0 0 * * *",  # Daily at midnight
        file_pattern: str = "*.csv",
        status: str = "ACTIVE",
        created_by: Optional[User] = None,
        **kwargs
    ):
        """
        Create a ScheduledIngestion instance.
        
        NOTE: This is a placeholder. Will be implemented when ScheduledIngestion model exists.
        
        Args:
            tenant: Tenant instance
            asset: Asset instance (optional)
            name: Scheduled ingestion name
            source_type: Source type (S3, GCS, Azure, HTTP, FTP, SFTP, DATABASE)
            source_config: Source configuration JSON
            schedule: Cron expression
            file_pattern: File pattern to match
            status: Status (ACTIVE, PAUSED, ERROR)
            created_by: User who created the scheduled ingestion
            **kwargs: Additional fields
            
        Returns:
            ScheduledIngestion instance (when model exists)
        """
        # Placeholder - will be implemented when model exists
        raise NotImplementedError(
            "ScheduledIngestion model not yet created. "
            "This factory will be implemented in Phase 5."
        )


class ScheduledIngestionRunFactory:
    """
    Factory for creating ScheduledIngestionRun instances.
    
    NOTE: This is a placeholder factory. The actual ScheduledIngestionRun model
    will be created in Phase 5. This factory will be updated at that time.
    
    Expected model structure (from design.md):
    - id: UUID
    - scheduled_ingestion: ForeignKey to ScheduledIngestion
    - status: str (RUNNING, COMPLETED, FAILED, CANCELLED)
    - started_at: DateTime
    - finished_at: DateTime (optional)
    - files_found: int
    - files_processed: int
    - files_failed: int
    - prefect_flow_run_id: str (optional)
    - details_json: JSONField
    - error_message: TextField (optional)
    """
    
    @staticmethod
    def create_scheduled_ingestion_run(
        scheduled_ingestion=None,
        status: str = "COMPLETED",
        started_at: Optional[timezone.datetime] = None,
        finished_at: Optional[timezone.datetime] = None,
        files_found: int = 10,
        files_processed: int = 10,
        files_failed: int = 0,
        prefect_flow_run_id: Optional[str] = None,
        details_json: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        **kwargs
    ):
        """
        Create a ScheduledIngestionRun instance.
        
        NOTE: This is a placeholder. Will be implemented when ScheduledIngestionRun model exists.
        
        Args:
            scheduled_ingestion: ScheduledIngestion instance
            status: Run status
            started_at: When run started
            finished_at: When run finished
            files_found: Number of files found
            files_processed: Number of files processed
            files_failed: Number of files failed
            prefect_flow_run_id: Prefect flow run ID
            details_json: Run details JSON
            error_message: Error message if failed
            **kwargs: Additional fields
            
        Returns:
            ScheduledIngestionRun instance (when model exists)
        """
        # Placeholder - will be implemented when model exists
        raise NotImplementedError(
            "ScheduledIngestionRun model not yet created. "
            "This factory will be implemented in Phase 5."
        )

