"""
Management command for processing workflow instances.

This command continuously polls for workflow instances in DRAFT or RUNNING status
and executes them using the workflow engine.

Usage:
    python manage.py process_workflows [--poll-interval SECONDS] [--batch-size N]
"""
import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from typing import Optional

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process workflow instances continuously (polls for DRAFT and RUNNING workflows)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--poll-interval',
            type=int,
            default=5,
            help='Polling interval in seconds (default: 5)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of workflows to process per batch (default: 10)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Process one batch and exit (for testing)'
        )

    def handle(self, *args, **options):
        poll_interval = options['poll_interval']
        batch_size = options['batch_size']
        run_once = options['once']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting workflow processor '
                f'(poll_interval={poll_interval}s, batch_size={batch_size})'
            )
        )
        
        # Initialize workflow engine and registry
        workflow_engine = WorkflowEngine()
        workflow_registry = WorkflowRegistry()
        
        # Register all workflow tasks from workflow classes
        try:
            from hub.apps.orchestration.workflows import (
                ContractCreationWorkflow,
                ScheduledIngestionWorkflow,
                AccessRequestWorkflow,
                DataQualityCheckWorkflow,
                ComplianceReportingWorkflow,
                AssetCreationWorkflow,
                DatasetCreationWorkflow,
                VersionCreationWorkflow,
                MarketplacePublicationWorkflow,
            )
            
            workflow_classes = [
                ContractCreationWorkflow,
                ScheduledIngestionWorkflow,
                AccessRequestWorkflow,
                DataQualityCheckWorkflow,
                ComplianceReportingWorkflow,
                AssetCreationWorkflow,
                DatasetCreationWorkflow,
                VersionCreationWorkflow,
                MarketplacePublicationWorkflow,
            ]
            
            # Register tasks from each workflow class
            for workflow_class in workflow_classes:
                if hasattr(workflow_class, 'register_tasks'):
                    workflow_class.register_tasks(workflow_engine)
            
            self.stdout.write(
                self.style.SUCCESS(f'Registered tasks from {len(workflow_classes)} workflow classes')
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Warning: Could not register workflow tasks: {e}')
            )
            logger.warning(f"Could not register workflow tasks: {e}", exc_info=True)
        
        total_processed = 0
        
        try:
            while True:
                processed = self._process_batch(workflow_engine, batch_size)
                total_processed += processed
                
                if processed > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Processed {processed} workflow(s) (total: {total_processed})'
                        )
                    )
                
                if run_once:
                    break
                
                # Sleep before next poll
                time.sleep(poll_interval)
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.SUCCESS(f'\nStopped. Total processed: {total_processed}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error processing workflows: {e}')
            )
            logger.error(f"Workflow processing error: {e}", exc_info=True)
            raise CommandError(f"Workflow processing failed: {e}")

    def _process_batch(self, workflow_engine: WorkflowEngine, batch_size: int) -> int:
        """
        Process a batch of workflow instances.
        
        Args:
            workflow_engine: WorkflowEngine instance
            batch_size: Maximum number of workflows to process
            
        Returns:
            Number of workflows processed
        """
        processed = 0
        
        # Get workflows that need processing:
        # 1. DRAFT workflows that need to be started
        # 2. RUNNING workflows that need to be continued
        
        # Process DRAFT workflows first (start them)
        # select_for_update requires a transaction, so we need to evaluate the queryset inside a transaction
        with transaction.atomic():
            draft_workflows = list(WorkflowInstance.objects.filter(
                status=WorkflowStatus.DRAFT
            ).select_for_update(skip_locked=True)[:batch_size])
        
        for instance in draft_workflows:
            try:
                with transaction.atomic():
                    # Refresh to ensure we have the latest state
                    instance.refresh_from_db()
                    
                    # Double-check status (may have changed)
                    if instance.status != WorkflowStatus.DRAFT:
                        continue
                    
                    # Start the workflow
                    workflow_engine.start_instance(str(instance.id))
                    
                    # Execute the workflow
                    workflow_engine.execute_instance(str(instance.id))
                    
                    processed += 1
                    logger.info(
                        f"Processed DRAFT workflow instance: {instance.id} "
                        f"({instance.workflow_name})"
                    )
            except Exception as e:
                logger.error(
                    f"Error processing DRAFT workflow instance {instance.id}: {e}",
                    exc_info=True
                )
                # Mark as failed if retries exhausted
                try:
                    instance.refresh_from_db()
                    if instance.retry_count >= instance.max_retries:
                        instance.mark_failed(
                            error_message=str(e),
                            error_details={'exception_type': type(e).__name__}
                        )
                except Exception:
                    pass  # Ignore errors during failure marking
        
        # Process RUNNING workflows (continue execution)
        remaining_slots = batch_size - processed
        if remaining_slots > 0:
            # select_for_update requires a transaction, so we need to evaluate the queryset inside a transaction
            with transaction.atomic():
                running_workflows = list(WorkflowInstance.objects.filter(
                    status=WorkflowStatus.RUNNING
                ).select_for_update(skip_locked=True)[:remaining_slots])
            
            for instance in running_workflows:
                try:
                    with transaction.atomic():
                        # Refresh to ensure we have the latest state
                        instance.refresh_from_db()
                        
                        # Double-check status (may have changed)
                        if instance.status != WorkflowStatus.RUNNING:
                            continue
                        
                        # Continue execution
                        workflow_engine.execute_instance(str(instance.id))
                        
                        processed += 1
                        logger.info(
                            f"Continued RUNNING workflow instance: {instance.id} "
                            f"({instance.workflow_name})"
                        )
                except Exception as e:
                    logger.error(
                        f"Error continuing RUNNING workflow instance {instance.id}: {e}",
                        exc_info=True
                    )
                    # Mark as failed if retries exhausted
                    try:
                        instance.refresh_from_db()
                        if instance.retry_count >= instance.max_retries:
                            instance.mark_failed(
                                error_message=str(e),
                                error_details={'exception_type': type(e).__name__}
                            )
                    except Exception:
                        pass  # Ignore errors during failure marking
        
        return processed

