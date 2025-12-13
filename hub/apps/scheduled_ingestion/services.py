"""
Ingestion Service

Service layer for scheduled ingestion operations.
Extracts ingestion logic from ingestion.py module.
"""
from typing import Dict, Any, Optional

from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError
from hub.apps.core.events.service_publishers import IngestionEventPublisher
from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.apps.orchestration.workflows.scheduled_ingestion import ScheduledIngestionWorkflow


class IngestionService(BaseService, IngestionEventPublisher):
    """
    Service for scheduled ingestion operations.
    
    Provides business logic for:
    - Scheduled ingestion execution
    - Ingestion status monitoring
    - Ingestion configuration management
    """
    
    service_name = "ingestion_service"
    
    def execute_ingestion(
        self,
        scheduled_ingestion_id: str,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a scheduled ingestion using workflow orchestration.
        
        Args:
            scheduled_ingestion_id: Scheduled ingestion ID
            tenant_id: Optional tenant ID for filtering
            
        Returns:
            Execution result dictionary
            
        Raises:
            NotFoundError: If scheduled ingestion not found
        """
        scheduled_ingestion = self.get_resource_or_raise(
            ScheduledIngestion,
            scheduled_ingestion_id,
            tenant_id=tenant_id or self.tenant_id
        )
        
        return self.execute_with_metrics(
            operation="execute_ingestion",
            func=lambda: self._execute_ingestion_impl(scheduled_ingestion),
            tenant_id=str(scheduled_ingestion.tenant_id)
        )
    
    def _execute_ingestion_impl(
        self,
        scheduled_ingestion: ScheduledIngestion
    ) -> Dict[str, Any]:
        """Internal implementation of ingestion execution."""
        # Execute workflow
        workflow_result = ScheduledIngestionWorkflow.execute(
            scheduled_ingestion_id=str(scheduled_ingestion.id)
        )
        
        # Extract results from workflow output
        output_data = workflow_result.get("output_data", {})
        state_summary = output_data.get("state_summary", {})
        
        return {
            "files_found": output_data.get("files_found", 0),
            "files_processed": state_summary.get("total_processed", 0),
            "files_failed": state_summary.get("total_failed", 0),
            "datasets_created": state_summary.get("total_processed", 0),
            "ingestion_state": {
                "processed_files": state_summary.get("total_processed", 0),
                "failed_files": state_summary.get("total_failed", 0),
                "permanent_failures": state_summary.get("permanent_failures", 0),
                "retryable_failures": state_summary.get("retryable_failures", 0),
                "last_processed_at": state_summary.get("last_processed_timestamp")
            },
            "workflow_instance_id": workflow_result.get("workflow_instance_id")
        }
    
    def get_ingestion_status(
        self,
        scheduled_ingestion_id: str,
        tenant_id: Optional[str] = None
    ) -> ScheduledIngestion:
        """
        Get scheduled ingestion status.
        
        Args:
            scheduled_ingestion_id: Scheduled ingestion ID
            tenant_id: Optional tenant ID for filtering
            
        Returns:
            ScheduledIngestion instance
            
        Raises:
            NotFoundError: If scheduled ingestion not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")
        
        return self.execute_with_metrics(
            operation="get_ingestion_status",
            tenant_id=effective_tenant_id,
            func=lambda: self.get_resource_or_raise(
                ScheduledIngestion,
                scheduled_ingestion_id,
                tenant_id=effective_tenant_id
            )
        )

