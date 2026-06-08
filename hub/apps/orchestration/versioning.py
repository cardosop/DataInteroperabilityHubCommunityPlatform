"""
Workflow Versioning

Manages workflow definition versioning and version selection.
"""
import re
from typing import Optional, List
from django.db import models
from django.core.exceptions import ValidationError

from .models import WorkflowDefinition


class WorkflowVersionManager:
    """
    Workflow version manager.

    Manages workflow definition versioning using semantic versioning (major.minor.patch).
    """

    VERSION_PATTERN = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')

    @classmethod
    def get_workflow_definition(
        cls,
        workflow_name: str,
        version: Optional[str] = None
    ) -> Optional[WorkflowDefinition]:
        """
        Get workflow definition by name and version.

        Args:
            workflow_name: Workflow name
            version: Optional version (uses active version if not specified)

        Returns:
            WorkflowDefinition or None if not found
        """
        if version:
            try:
                return WorkflowDefinition.objects.get(
                    name=workflow_name,
                    version=version
                )
            except WorkflowDefinition.DoesNotExist:
                return None
        else:
            # Get active version
            return WorkflowDefinition.objects.filter(
                name=workflow_name,
                is_active=True
            ).order_by('-created_at').first()

    @classmethod
    def get_all_versions(cls, workflow_name: str) -> List[WorkflowDefinition]:
        """
        Get all versions of a workflow definition.

        Args:
            workflow_name: Workflow name

        Returns:
            List of WorkflowDefinition instances ordered by version
        """
        return list(
            WorkflowDefinition.objects.filter(name=workflow_name)
            .order_by('-version')
        )

    @classmethod
    def create_version(
        cls,
        workflow_name: str,
        dsl_json: dict,
        version: Optional[str] = None,
        description: Optional[str] = None,
        created_by_id: Optional[str] = None
    ) -> WorkflowDefinition:
        """
        Create a new workflow definition version.

        Args:
            workflow_name: Workflow name
            dsl_json: Workflow DSL JSON
            version: Optional version (auto-increments patch version if not specified)
            description: Optional description
            created_by_id: Optional user ID

        Returns:
            Created WorkflowDefinition
        """
        if version:
            cls._validate_version(version)
        else:
            # Auto-increment patch version
            latest = cls.get_latest_version(workflow_name)
            if latest:
                version = cls._increment_patch_version(latest.version)
            else:
                version = "1.0.0"

        # Resolve created_by user if provided (best-effort).
        created_by = None
        if created_by_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                created_by = User.objects.get(id=created_by_id)
            except User.DoesNotExist:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"User {created_by_id} not found for workflow {workflow_name}, "
                    "creating workflow without created_by"
                )

        # Use bulk_create with ignore_conflicts to avoid the
        # unique-index lock stall that can occur under MVCC when
        # the ``unique_workflow_def_name_version`` index is bloated
        # from many rolled-back test inserts (--keepdb).  This
        # translates to ``ON CONFLICT DO NOTHING`` in PostgreSQL
        # and does NOT wait on index locks held by concurrent or
        # recently-aborted transactions.
        wf_def = WorkflowDefinition(
            name=workflow_name,
            version=version,
            dsl_json=dsl_json,
            description=description or "",
            created_by=created_by,
            is_active=True,
        )
        WorkflowDefinition.objects.bulk_create(
            [wf_def],
            ignore_conflicts=True,
        )
        # Fetch whichever row ended up in the table (ours or a
        # concurrent insert) so the caller always gets an instance.
        wf_def = WorkflowDefinition.objects.get(
            name=workflow_name, version=version
        )

        # Deactivate other versions (only one active version per workflow)
        WorkflowDefinition.objects.filter(
            name=workflow_name
        ).exclude(id=wf_def.id).update(is_active=False)

        return wf_def

    @classmethod
    def get_latest_version(cls, workflow_name: str) -> Optional[WorkflowDefinition]:
        """
        Get latest version of a workflow definition.

        Args:
            workflow_name: Workflow name

        Returns:
            Latest WorkflowDefinition or None if not found
        """
        return WorkflowDefinition.objects.filter(
            name=workflow_name
        ).order_by('-created_at').first()

    @classmethod
    def activate_version(cls, workflow_name: str, version: str) -> WorkflowDefinition:
        """
        Activate a specific workflow version.

        Args:
            workflow_name: Workflow name
            version: Version to activate

        Returns:
            Activated WorkflowDefinition
        """
        workflow_def = WorkflowDefinition.objects.get(
            name=workflow_name,
            version=version
        )

        # Deactivate other versions
        WorkflowDefinition.objects.filter(
            name=workflow_name
        ).exclude(id=workflow_def.id).update(is_active=False)

        # Activate this version
        workflow_def.is_active = True
        workflow_def.save(update_fields=['is_active'])

        return workflow_def

    @classmethod
    def _validate_version(cls, version: str) -> None:
        """
        Validate version format (semantic versioning).

        Args:
            version: Version string

        Raises:
            ValidationError: If version format is invalid
        """
        if not cls.VERSION_PATTERN.match(version):
            raise ValidationError(
                f"Invalid version format: {version}. Expected format: major.minor.patch (e.g., 1.0.0)"
            )

    @classmethod
    def _increment_patch_version(cls, version: str) -> str:
        """
        Increment patch version.

        Args:
            version: Current version (e.g., "1.0.0")

        Returns:
            Incremented version (e.g., "1.0.1")
        """
        match = cls.VERSION_PATTERN.match(version)
        if not match:
            raise ValidationError(f"Invalid version format: {version}")

        major, minor, patch = map(int, match.groups())
        return f"{major}.{minor}.{patch + 1}"

    @classmethod
    def get_versions_eligible_for_inflight_runs(
        cls,
        workflow_name: str,
        soak_days: int = 14,
    ) -> List[WorkflowDefinition]:
        """Return versions still eligible to handle in-flight runs.

        Phase 250.0.12 / D250.7 — when a new workflow version is activated,
        the previous version is NOT immediately rejected. Existing in-flight
        runs (e.g. long-running async asset-creation workflows) MUST be able
        to complete on the version they started on. A 14-day soak window
        keeps prior versions eligible for new step-progressions of in-flight
        runs even after a newer version becomes the default for fresh runs.

        Eligibility rules:

        * The currently-active version is ALWAYS eligible.
        * A version that became inactive within the last ``soak_days`` is
          eligible.
        * A version that became inactive more than ``soak_days`` ago is NOT
          eligible — in-flight runs against it MUST be marked
          ``REQUIRES_VERSION_MIGRATION`` and either migrated or aborted.

        Args:
            workflow_name: Workflow name (e.g. ``asset_creation``).
            soak_days: Soak window length. Default 14 days per D250.7
                (covers P99 long-running workflow durations); per-tenant or
                per-workflow override allowed via call-site configuration.

        Returns:
            List of ``WorkflowDefinition`` instances ordered by version,
            newest first. The first element is the active version.
        """
        from datetime import timedelta
        from django.utils import timezone

        soak_cutoff = timezone.now() - timedelta(days=soak_days)
        active = WorkflowDefinition.objects.filter(
            name=workflow_name,
            is_active=True,
        )
        recently_deactivated = WorkflowDefinition.objects.filter(
            name=workflow_name,
            is_active=False,
            updated_at__gte=soak_cutoff,
        )
        eligible_qs = (active | recently_deactivated).distinct()
        # Order: active first, then recently-deactivated by newest first.
        return sorted(
            eligible_qs,
            key=lambda d: (not d.is_active, -d.created_at.timestamp()),
        )

    @classmethod
    def is_version_eligible_for_inflight(
        cls,
        workflow_name: str,
        version: str,
        soak_days: int = 14,
    ) -> bool:
        """True iff ``version`` is currently eligible to handle in-flight runs.

        Phase 250.0.12 / D250.7 — convenience wrapper around
        :meth:`get_versions_eligible_for_inflight_runs` for the common
        per-run dispatch check: given a ``WorkflowInstance.workflow_version``,
        can the engine still progress this run?
        """
        eligible = cls.get_versions_eligible_for_inflight_runs(
            workflow_name=workflow_name,
            soak_days=soak_days,
        )
        return any(d.version == version for d in eligible)

    @classmethod
    def compare_versions(cls, version1: str, version2: str) -> int:
        """
        Compare two versions.

        Args:
            version1: First version
            version2: Second version

        Returns:
            -1 if version1 < version2, 0 if equal, 1 if version1 > version2
        """
        match1 = cls.VERSION_PATTERN.match(version1)
        match2 = cls.VERSION_PATTERN.match(version2)

        if not match1 or not match2:
            raise ValidationError(f"Invalid version format: {version1} or {version2}")

        v1_parts = tuple(map(int, match1.groups()))
        v2_parts = tuple(map(int, match2.groups()))

        if v1_parts < v2_parts:
            return -1
        elif v1_parts > v2_parts:
            return 1
        else:
            return 0

