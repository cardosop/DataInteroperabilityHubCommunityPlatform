"""
Management command to warm ODPS external $ref cache.

Pre-populates Redis cache with frequently accessed external references
to improve response times and reduce external API calls.

Usage:
    # Warm top 100 refs (default)
    python manage.py warm_odps_ref_cache

    # Warm top N refs
    python manage.py warm_odps_ref_cache --limit 500

    # Warm refs matching URL pattern
    python manage.py warm_odps_ref_cache --url-pattern "https://example.com/*"

    # Dry-run mode (no actual warming)
    python manage.py warm_odps_ref_cache --dry-run

    # Warm for specific tenant
    python manage.py warm_odps_ref_cache --tenant-id <uuid>

    # Minimum access count filter
    python manage.py warm_odps_ref_cache --min-access-count 5
"""
import re
from typing import List, Optional
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from hub.apps.contracts.ref_warming import (
    get_frequently_accessed_refs,
    warm_ref_cache
)

logger = None


class Command(BaseCommand):
    help = 'Warm ODPS external $ref cache with frequently accessed references'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of refs to warm (default: 100)',
        )
        parser.add_argument(
            '--url-pattern',
            type=str,
            default=None,
            help='URL pattern to filter refs (e.g., "https://example.com/*")',
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            default=None,
            help='Tenant ID to filter refs (reserved for future use)',
        )
        parser.add_argument(
            '--min-access-count',
            type=int,
            default=1,
            help='Minimum access count to include ref (default: 1)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode (no actual warming)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of refs to process per batch (default: 10)',
        )

    def handle(self, *args, **options):
        global logger
        import structlog
        logger = structlog.get_logger(__name__)

        limit = options['limit']
        url_pattern = options['url_pattern']
        tenant_id = options['tenant_id']
        min_access_count = options['min_access_count']
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        self.stdout.write(self.style.SUCCESS(
            f"Starting ODPS ref cache warming (limit: {limit}, dry-run: {dry_run})"
        ))

        # Get frequently accessed refs
        try:
            ref_urls = get_frequently_accessed_refs(
                limit=limit * 2,  # Get more to account for filtering
                min_access_count=min_access_count,
                tenant_id=tenant_id
            )
        except Exception as e:
            raise CommandError(f"Failed to get frequently accessed refs: {e}")

        if not ref_urls:
            self.stdout.write(self.style.WARNING(
                "No frequently accessed refs found. Cache warming skipped."
            ))
            return

        # Filter by URL pattern if specified
        if url_pattern:
            pattern_re = self._compile_pattern(url_pattern)
            ref_urls = [url for url in ref_urls if pattern_re.match(url)]
            self.stdout.write(self.style.SUCCESS(
                f"Filtered to {len(ref_urls)} refs matching pattern: {url_pattern}"
            ))

        # Limit to requested number
        ref_urls = ref_urls[:limit]

        if not ref_urls:
            self.stdout.write(self.style.WARNING(
                "No refs to warm after filtering."
            ))
            return

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"DRY-RUN: Would warm {len(ref_urls)} refs:"
            ))
            for i, ref_url in enumerate(ref_urls[:20], 1):  # Show first 20
                self.stdout.write(f"  {i}. {ref_url}")
            if len(ref_urls) > 20:
                self.stdout.write(f"  ... and {len(ref_urls) - 20} more")
            return

        # Warm cache
        try:
            result = warm_ref_cache(
                ref_urls=ref_urls,
                tenant_id=tenant_id,
                batch_size=batch_size
            )
        except Exception as e:
            raise CommandError(f"Failed to warm cache: {e}")

        # Report results
        self.stdout.write(self.style.SUCCESS(
            f"\nCache warming complete:"
        ))
        self.stdout.write(f"  Total refs: {result['total']}")
        self.stdout.write(self.style.SUCCESS(
            f"  Warmed: {result['warmed']}"
        ))
        self.stdout.write(self.style.WARNING(
            f"  Skipped (already cached): {result['skipped']}"
        ))
        if result['failed'] > 0:
            self.stdout.write(self.style.ERROR(
                f"  Failed: {result['failed']}"
            ))
        self.stdout.write(f"  Duration: {result['duration_seconds']:.2f}s")

        if result['failed'] > 0:
            self.stdout.write(self.style.WARNING(
                f"\nWarning: {result['failed']} refs failed to warm. "
                "Check logs for details."
            ))

    def _compile_pattern(self, pattern: str) -> re.Pattern:
        """
        Compile URL pattern to regex.

        Supports wildcards:
        - * matches any characters
        - ? matches single character

        Args:
            pattern: URL pattern (e.g., "https://example.com/*")

        Returns:
            Compiled regex pattern
        """
        # Escape special regex characters except * and ?
        escaped = re.escape(pattern)
        # Replace escaped \* with .* (match any)
        escaped = escaped.replace(r'\*', '.*')
        # Replace escaped \? with . (match single char)
        escaped = escaped.replace(r'\?', '.')
        # Anchor to start and end
        regex = f"^{escaped}$"
        return re.compile(regex)

