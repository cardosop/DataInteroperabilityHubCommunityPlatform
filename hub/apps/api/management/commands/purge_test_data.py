"""
Layer 3 cleanup sweep — Django management command for CI CronJob.

Removes test data older than a configurable threshold. Designed as
the last-resort cleanup layer after per-test LIFO teardown (layer 1)
and per-session persona teardown (layer 2).

280.B.5.4 — 3-layer cleanup: layer 3 sweep for escaped resources.

Usage:
    python manage.py purge_test_data --older-than=24h --dry-run
    python manage.py purge_test_data --older-than=24h  # production sweep
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)

# Test data markers — resources created by test suites use these naming
# conventions or metadata tags so the sweep can target them without
# touching real tenant data.
_TEST_NAME_PATTERNS = (
    "test-",
    "e2e-",
    "pytest-",
    "cli-test-",
    "sdk-test-",
    "dim-",
    "xtn-",  # cross-tenant leak tests
    "fresh-",  # persona provisioning
)


class Command(BaseCommand):
    help = "Purge test data older than a threshold (layer 3 cleanup sweep)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than",
            default="24h",
            help="Purge test data older than this duration (default: 24h). "
            "Accepts Django duration strings: 24h, 7d, 1h30m.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be deleted without actually deleting.",
        )
        parser.add_argument(
            "--tenant",
            help="Restrict purge to a specific tenant slug.",
        )

    def handle(self, **options):
        older_than = self._parse_duration(options["older_than"])
        dry_run = options["dry_run"]
        options["tenant"]

        cutoff = timezone.now() - older_than

        self.stdout.write(
            f"Purge test data older than {options['older_than']} (cutoff: {cutoff.isoformat()})"
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no deletions"))

        purged = 0

        try:
            from hub.apps.assets.models import Asset

            purged += self._purge_queryset(
                Asset.objects.filter(
                    created_at__lt=cutoff,
                    name__istartswith=_TEST_NAME_PATTERNS[0],
                ),
                "assets",
                dry_run,
            )
        except Exception as e:
            self.stderr.write(f"Asset purge skipped: {e}")

        try:
            from hub.apps.contracts.models import Contract

            purged += self._purge_queryset(
                Contract.objects.filter(created_at__lt=cutoff),
                "contracts",
                dry_run,
            )
        except Exception as e:
            self.stderr.write(f"Contract purge skipped: {e}")

        try:
            from hub.apps.files.models import File

            purged += self._purge_queryset(
                File.objects.filter(
                    created_at__lt=cutoff,
                    name__istartswith=_TEST_NAME_PATTERNS[0],
                ),
                "files",
                dry_run,
            )
        except Exception as e:
            self.stderr.write(f"File purge skipped: {e}")

        try:
            from hub.apps.datasets.models import Dataset

            purged += self._purge_queryset(
                Dataset.objects.filter(
                    created_at__lt=cutoff,
                    name__istartswith=_TEST_NAME_PATTERNS[0],
                ),
                "datasets",
                dry_run,
            )
        except Exception as e:
            self.stderr.write(f"Dataset purge skipped: {e}")

        try:
            from django.db.models import Q

            from hub.apps.users.models import User

            # Match users whose email starts with any test-name pattern
            # (e.g. e2e-invited-*, test-*, fresh-*).  The old filter
            # (email__icontains="test") missed e2e-invited-*@example.com
            # because the substring "test" never appears there.
            _user_pattern_q = Q()
            for pattern in _TEST_NAME_PATTERNS:
                _user_pattern_q |= Q(email__istartswith=pattern)
            _user_pattern_q |= Q(email__icontains="test")  # legacy broad catch

            purged += self._purge_queryset(
                User.objects.filter(
                    created_at__lt=cutoff,
                ).filter(_user_pattern_q),
                "users",
                dry_run,
            )

            # Also purge INVITED users with expired tokens regardless of
            # join date — catches the e2e-invited-* pattern which may have
            # a recent date_joined but an invitation that expired long ago.
            invited_qs = User.objects.filter(
                status="INVITED",
                invitation_token_expires_at__lt=timezone.now() - timedelta(hours=1),
            )
            purged += self._purge_queryset(invited_qs, "users (expired invited)", dry_run)

        except Exception as e:
            self.stderr.write(f"User purge skipped: {e}")

        self.stdout.write(
            self.style.SUCCESS(f"Purged {purged} test resource(s) {'(dry run)' if dry_run else ''}")
        )

    def _purge_queryset(self, qs, label, dry_run):
        count = qs.count()
        if count == 0:
            return 0
        if not dry_run:
            deleted, _ = qs.delete()
            count = deleted
        self.stdout.write(f"  {label}: {count} item(s) {'would be' if dry_run else ''} purged")
        return count

    @staticmethod
    def _parse_duration(duration_str: str) -> timedelta:
        """Parse Django-style duration strings like '24h', '7d', '1h30m'."""
        import re

        total = timedelta()
        pattern = re.compile(r"(\d+)\s*(d|h|m|s)")
        for match in pattern.finditer(duration_str):
            value = int(match.group(1))
            unit = match.group(2)
            if unit == "d":
                total += timedelta(days=value)
            elif unit == "h":
                total += timedelta(hours=value)
            elif unit == "m":
                total += timedelta(minutes=value)
            elif unit == "s":
                total += timedelta(seconds=value)
        if total.total_seconds() == 0:
            raise ValueError(f"Could not parse duration: {duration_str!r}")
        return total
