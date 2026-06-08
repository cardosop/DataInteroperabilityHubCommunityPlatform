"""
Phase 260.1.E — identify File rows eligible for orphan cleanup.

Orphan = within a tenant, no Dataset / ComplianceRun / DQRun /
RetentionPolicy / AccessRequest row references ``file_id``, and the file is
not already in DELETING/DELETED. Scoped to ``created_at`` before the cutoff
so recent uploads are not swept.

Used by ``cleanup_orphan_files`` management command (query-building only).
"""
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from django.db.models import Exists, OuterRef
from django.utils import timezone

from hub.apps.files.models import File, FileStatus


def _tenant_pk(tenant_id: Any) -> UUID:
    if hasattr(tenant_id, "pk"):
        return tenant_id.pk
    return UUID(str(tenant_id))


def orphan_cleanup_candidate_qs(
    *,
    tenant_id: Any,
    min_age_cutoff: datetime | None = None,
    using: str = "default",
):
    """Filter set of files that may be orphaned ( refcount gap ) for one tenant.

    ``min_age_cutoff`` defaults to now; callers should pass
    ``timezone.now() - timedelta(days=min_age_days)``.
    """
    from hub.apps.compliance.models import ComplianceRun
    from hub.apps.datasets.models import Dataset
    from hub.apps.dq.models import DQRun
    from hub.apps.governance.models import AccessRequest, RetentionPolicy

    tid = _tenant_pk(tenant_id)
    cutoff = min_age_cutoff if min_age_cutoff is not None else timezone.now()

    ref_dataset = Exists(
        Dataset.objects.using(using).filter(
            tenant_id=tid,
            file_id=OuterRef("pk"),
        ),
    )
    ref_compliance = Exists(
        ComplianceRun.objects.using(using).filter(
            tenant_id=tid,
            file_id=OuterRef("pk"),
        ),
    )
    ref_dq = Exists(
        DQRun.objects.using(using).filter(
            tenant_id=tid,
            file_id=OuterRef("pk"),
        ),
    )
    ref_retention = Exists(
        RetentionPolicy.objects.using(using).filter(
            tenant_id=tid,
            file_id=OuterRef("pk"),
        ),
    )
    ref_access = Exists(
        AccessRequest.objects.using(using).filter(
            tenant_id=tid,
            file_id=OuterRef("pk"),
        ),
    )

    return (
        File.objects.using(using)
        .filter(
            tenant_id=tid,
            created_at__lte=cutoff,
        )
        .exclude(status__in=(FileStatus.DELETING, FileStatus.DELETED))
        .filter(
            ~ref_dataset,
            ~ref_compliance,
            ~ref_dq,
            ~ref_retention,
            ~ref_access,
        )
        .order_by("pk")
    )
