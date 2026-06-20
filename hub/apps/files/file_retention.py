"""
Phase 260.1.A — file soft-delete grace and hard-purge eligibility helpers.

Pure functions keep property-based tests focused and fast.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Union

from django.utils import timezone

from hub.apps.files.models import FileStatus

FileStatusLike = Union[str, FileStatus]


def normalized_file_status(status: FileStatusLike) -> str:
    """Return DB string for a File status value or enum member."""
    if isinstance(status, FileStatus):
        return status.value
    return str(status)


def file_is_purge_eligible(
    *,
    status: FileStatusLike,
    deleted_at: datetime | None,
    grace_days: int,
    now: datetime | None = None,
) -> bool:
    """
    True when a row is ready for hard-delete (S3 + DB) by purge_deleted_files.

    Eligible: status in {DELETING, DELETED}, deleted_at set, and deleted_at is
    at least ``grace_days`` before ``now`` (UTC).
    """
    if deleted_at is None:
        return False
    ns = normalized_file_status(status)
    if ns not in (FileStatus.DELETING.value, FileStatus.DELETED.value):
        return False
    effective_now = now if now is not None else timezone.now()
    if timezone.is_naive(deleted_at):
        deleted_at_aware = timezone.make_aware(deleted_at, UTC)
    else:
        deleted_at_aware = deleted_at
    if timezone.is_naive(effective_now):
        effective_now = timezone.make_aware(effective_now, UTC)
    cutoff = effective_now - timedelta(days=int(grace_days))
    return deleted_at_aware <= cutoff
