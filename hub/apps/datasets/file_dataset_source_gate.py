"""
Phase 260.2.D — single choke-point for “may this File back a new Dataset?”.

Mirrors ``FileViewSet.download`` / ``DatasetService`` semantics: block ``INFECTED``
and ``PENDING_SCAN`` only (``SCAN_UNAVAILABLE`` / ``SCAN_ERROR`` / ``CLEAN`` may proceed).
"""

from __future__ import annotations
from hub.apps.core.services.base import ValidationError
from hub.apps.files.models import File, FileScanStatus


def validate_file_allows_dataset_creation(file_obj: File) -> None:
    """
    Raise ``ValidationError`` with API-stable codes when dataset creation must fail.

    Called from ``DatasetService`` and any other ingestion path that creates datasets.
    """
    if file_obj.scan_status == FileScanStatus.INFECTED:
        raise ValidationError(
            "Cannot create a dataset from a file that failed malware scanning.",
            code="FILE_INFECTED",
            details={
                "file_id": str(file_obj.id),
                "scan_status": file_obj.scan_status,
            },
            http_status=403,
        )
    if file_obj.scan_status == FileScanStatus.PENDING_SCAN:
        raise ValidationError(
            "File is pending malware scan; dataset creation is not allowed until "
            "the scan completes.",
            code="FILE_SCAN_PENDING",
            details={
                "file_id": str(file_obj.id),
                "scan_status": file_obj.scan_status,
            },
            http_status=403,
        )
