"""
Management command to archive audit events older than retention period (3 years).

This command should be run periodically (e.g., via cron) to archive old audit events.
For MVP, we'll mark events as archived rather than moving them to cold storage.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from hub.apps.audit.models import AuditEvent


class Command(BaseCommand):
    help = 'Archive audit events older than 3 years (retention period)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be archived without actually archiving',
        )
        parser.add_argument(
            '--retention-years',
            type=int,
            default=3,
            help='Number of years to retain audit events (default: 3)',
        )
    
    def handle(self, *args, **options):
        retention_years = options['retention_years']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=retention_years * 365)
        
        old_events = AuditEvent.objects.filter(timestamp__lt=cutoff_date)
        count = old_events.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No audit events to archive.'))
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would archive {count} audit events older than {cutoff_date.isoformat()}'
                )
            )
            # Show sample events
            sample = old_events[:5]
            for event in sample:
                self.stdout.write(f'  - {event.action} on {event.resource_type} at {event.timestamp}')
            if count > 5:
                self.stdout.write(f'  ... and {count - 5} more')
        else:
            # For MVP, we'll just log that these should be archived
            # In production, this would move events to cold storage or mark them
            self.stdout.write(
                self.style.SUCCESS(
                    f'Found {count} audit events older than {cutoff_date.isoformat()} to archive.'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'Note: In production, these events should be moved to cold storage. '
                    'For MVP, events are retained in the database.'
                )
            )
            # TODO: Implement actual archiving (move to cold storage, mark as archived, etc.)

