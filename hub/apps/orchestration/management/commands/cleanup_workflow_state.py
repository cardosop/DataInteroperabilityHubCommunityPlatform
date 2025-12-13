"""
Management command for workflow state cleanup and archival.

This command handles:
- Archiving completed workflows older than retention period
- Deleting archived workflows older than archival retention period
- Cleaning up orphaned workflow states
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from typing import Optional
from collections import defaultdict
import logging

from hub.apps.orchestration.models import (
    WorkflowInstance,
    WorkflowStep,
    WorkflowState,
    WorkflowStatus
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Cleanup and archive workflow state data based on retention policies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--archive-days',
            type=int,
            default=90,
            help='Archive completed workflows older than this many days (default: 90)'
        )
        parser.add_argument(
            '--delete-days',
            type=int,
            default=365,
            help='Delete archived workflows older than this many days (default: 365)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be archived/deleted without actually doing it'
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Process workflows for a specific tenant only'
        )
        parser.add_argument(
            '--cleanup-orphaned',
            action='store_true',
            help='Clean up orphaned workflow states (states without instances)'
        )

    def handle(self, *args, **options):
        archive_days = options['archive_days']
        delete_days = options['delete_days']
        dry_run = options['dry_run']
        tenant_id = options.get('tenant_id')
        cleanup_orphaned = options['cleanup_orphaned']

        self.stdout.write(
            self.style.SUCCESS(
                f'Starting workflow state cleanup (archive_days={archive_days}, '
                f'delete_days={delete_days}, dry_run={dry_run})'
            )
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Archive completed workflows
        archived_count = self._archive_completed_workflows(
            archive_days, tenant_id, dry_run
        )

        # Delete old archived workflows
        deleted_count = self._delete_archived_workflows(
            delete_days, tenant_id, dry_run
        )

        # Cleanup orphaned states
        orphaned_count = 0
        if cleanup_orphaned:
            orphaned_count = self._cleanup_orphaned_states(tenant_id, dry_run)

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCleanup Summary:\n'
                f'  Archived workflows: {archived_count}\n'
                f'  Deleted workflows: {deleted_count}\n'
                f'  Cleaned orphaned states: {orphaned_count}'
            )
        )

    def _archive_completed_workflows(
        self,
        archive_days: int,
        tenant_id: Optional[str],
        dry_run: bool
    ) -> int:
        """Archive completed workflows older than archive_days."""
        cutoff_date = timezone.now() - timedelta(days=archive_days)

        queryset = WorkflowInstance.objects.filter(
            status__in=[WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED],
            completed_at__lt=cutoff_date
        )

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        # Exclude already archived workflows
        queryset = queryset.exclude(state_data__has_key='archived')

        count = queryset.count()

        if count == 0:
            self.stdout.write(f'No workflows to archive (older than {archive_days} days)')
            return 0

        self.stdout.write(f'Found {count} workflows to archive')

        if not dry_run:
            archived_at = timezone.now().isoformat()
            with transaction.atomic():
                for workflow in queryset:
                    # Mark as archived in state_data
                    state_data = workflow.state_data or {}
                    state_data['archived'] = True
                    state_data['archived_at'] = archived_at
                    workflow.state_data = state_data
                    workflow.save(update_fields=['state_data', 'updated_at'])

                    logger.info(
                        f'Archived workflow {workflow.id} '
                        f'(completed_at={workflow.completed_at})'
                    )

        return count

    def _delete_archived_workflows(
        self,
        delete_days: int,
        tenant_id: Optional[str],
        dry_run: bool
    ) -> int:
        """Delete archived workflows older than delete_days."""
        cutoff_date = timezone.now() - timedelta(days=delete_days)

        queryset = WorkflowInstance.objects.filter(
            state_data__archived=True,
            completed_at__lt=cutoff_date
        )

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        count = queryset.count()

        if count == 0:
            self.stdout.write(f'No archived workflows to delete (older than {delete_days} days)')
            return 0

        self.stdout.write(f'Found {count} archived workflows to delete')

        if not dry_run:
            with transaction.atomic():
                # Delete workflow states (CASCADE will handle steps)
                workflow_ids = list(queryset.values_list('id', flat=True))
                
                # Delete workflow states
                WorkflowState.objects.filter(workflow_instance_id__in=workflow_ids).delete()
                
                # Delete workflow steps
                WorkflowStep.objects.filter(workflow_instance_id__in=workflow_ids).delete()
                
                # Delete workflow instances
                deleted_count = queryset.delete()[0]

                logger.info(f'Deleted {deleted_count} archived workflows')

                return deleted_count

        return count

    def _cleanup_orphaned_states(
        self,
        tenant_id: Optional[str],
        dry_run: bool
    ) -> int:
        """Clean up workflow states that reference non-existent workflow instances."""
        # Find all workflow state workflow_instance_ids
        state_instance_ids = set(
            WorkflowState.objects.values_list('workflow_instance_id', flat=True).distinct()
        )

        # Find existing workflow instance IDs
        queryset = WorkflowInstance.objects.all()
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        existing_instance_ids = set(queryset.values_list('id', flat=True))

        # Find orphaned states
        orphaned_ids = state_instance_ids - existing_instance_ids

        if not orphaned_ids:
            self.stdout.write('No orphaned workflow states found')
            return 0

        count = len(orphaned_ids)
        self.stdout.write(f'Found {count} orphaned workflow states')

        if not dry_run:
            # Delete orphaned states
            deleted_count = WorkflowState.objects.filter(
                workflow_instance_id__in=orphaned_ids
            ).count()
            
            WorkflowState.objects.filter(
                workflow_instance_id__in=orphaned_ids
            ).delete()

            logger.info(f'Deleted {deleted_count} orphaned workflow states')
            return deleted_count

        return count

