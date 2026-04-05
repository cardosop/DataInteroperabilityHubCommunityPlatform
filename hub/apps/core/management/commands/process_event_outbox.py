"""
Management command to process event outbox.

This command should be run periodically (e.g., via cron or celery beat) to process
pending events from the outbox and publish them to the event bus.

Usage:
    python manage.py process_event_outbox [--batch-size 100] [--once]
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import structlog

from hub.apps.core.events.outbox import get_outbox_publisher

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = 'Process pending events from event outbox'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of events to process per batch (default: 100)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Process one batch and exit (default: run continuously)'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=10,
            help='Interval between batches in seconds (default: 10, only used if not --once)'
        )
        parser.add_argument(
            '--cleanup-days',
            type=int,
            default=7,
            help='Number of days to keep published events (default: 7)'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        run_once = options['once']
        interval = options['interval']
        cleanup_days = options['cleanup_days']
        
        outbox_publisher = get_outbox_publisher()
        
        self.stdout.write(f"Processing event outbox (batch_size={batch_size})...")
        
        if run_once:
            # Process one batch and exit
            processed = outbox_publisher.process_outbox(batch_size=batch_size)
            self.stdout.write(
                self.style.SUCCESS(f'Processed {processed} events')
            )
            
            # Cleanup old events
            deleted = outbox_publisher.cleanup_old_events(days=cleanup_days)
            if deleted > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'Cleaned up {deleted} old events')
                )
        else:
            # Run continuously
            import time
            total_processed = 0
            
            try:
                while True:
                    processed = outbox_publisher.process_outbox(batch_size=batch_size)
                    total_processed += processed
                    
                    if processed > 0:
                        self.stdout.write(
                            self.style.SUCCESS(f'Processed {processed} events (total: {total_processed})')
                        )
                    
                    # Cleanup old events periodically (every 10 batches)
                    if total_processed % (batch_size * 10) == 0:
                        deleted = outbox_publisher.cleanup_old_events(days=cleanup_days)
                        if deleted > 0:
                            self.stdout.write(
                                self.style.SUCCESS(f'Cleaned up {deleted} old events')
                            )
                    
                    time.sleep(interval)
                    
            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.SUCCESS(f'\nStopped. Total processed: {total_processed}')
                )

