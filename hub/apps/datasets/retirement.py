"""
Dataset retirement helpers (Phase 260.1.C).

Keeps migration RunPython and tests on one code path without importing live
model classes inside historical migrations.
"""

from __future__ import annotations


def backfill_orphan_active_datasets_qs(queryset):
    """Retire ACTIVE datasets whose backing file FK is NULL (invalid lineage).

    Used after adding ``status``/``retired_at``: legacy rows could be ACTIVE
    with ``file_id`` already cleared. Accepts any Dataset QuerySet (including
    historical migration models).
    """
    from django.utils import timezone

    now = timezone.now()
    return queryset.filter(file_id__isnull=True, status="ACTIVE").update(
        status="RETIRED",
        retired_at=now,
        updated_at=now,
    )
