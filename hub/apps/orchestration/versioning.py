"""
Workflow Versioning

Manages workflow definition versioning and version selection.
"""

import logging
import re
import time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import InternalError, OperationalError

from .models import WorkflowDefinition

logger = logging.getLogger(__name__)


class WorkflowVersionManager:
    """
    Workflow version manager.

    Manages workflow definition versioning using semantic versioning (major.minor.patch).
    """

    VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

    @classmethod
    def get_workflow_definition(
        cls, workflow_name: str, version: str | None = None
    ) -> WorkflowDefinition | None:
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
                return WorkflowDefinition.objects.get(name=workflow_name, version=version)
            except WorkflowDefinition.DoesNotExist:
                return None
        else:
            # Get active version
            return (
                WorkflowDefinition.objects.filter(name=workflow_name, is_active=True)
                .order_by("-created_at")
                .first()
            )

    @classmethod
    def get_all_versions(cls, workflow_name: str) -> list[WorkflowDefinition]:
        """
        Get all versions of a workflow definition.

        Args:
            workflow_name: Workflow name

        Returns:
            List of WorkflowDefinition instances ordered by version
        """
        return list(WorkflowDefinition.objects.filter(name=workflow_name).order_by("-version"))

    @classmethod
    def create_version(
        cls,
        workflow_name: str,
        dsl_json: dict,
        version: str | None = None,
        description: str | None = None,
        created_by_id: str | None = None,
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
        #
        # Even with ON CONFLICT DO NOTHING, PostgreSQL must still
        # probe the unique index, which can time out under extreme
        # bloat from --reuse-db test runs.  Retry on lock timeout
        # with exponential backoff as a safety net.
        #
        # Each retry attempt runs inside its own transaction.atomic
        # savepoint.  This is critical when the caller wraps us in
        # @transaction.atomic (e.g. WorkflowRegistry.register_workflow):
        # a lock timeout aborts the current PostgreSQL subtransaction,
        # and without a fresh savepoint every subsequent statement in
        # that subtransaction would fail with InFailedSqlTransaction
        # (25P02).  Isolation per attempt prevents the first timeout
        # from poisoning later attempts.
        wf_def = WorkflowDefinition(
            name=workflow_name,
            version=version,
            dsl_json=dsl_json,
            description=description or "",
            created_by=created_by,
            is_active=True,
        )

        max_retries = 3
        base_delay = 0.1  # seconds
        row_persisted = False
        for attempt in range(max_retries + 1):
            try:
                with transaction.atomic():
                    WorkflowDefinition.objects.bulk_create(
                        [wf_def],
                        ignore_conflicts=True,
                    )
                # Verify the row was actually inserted — ignore_conflicts
                # can silently skip the insert when the unique index has
                # bloat from rolled-back test transactions.  If the row
                # isn't there, retry without ignore_conflicts so the DB
                # raises a proper unique-violation error (which the caller
                # handles as "already exists") or succeeds.
                if WorkflowDefinition.objects.filter(
                    name=workflow_name, version=version,
                ).exists():
                    row_persisted = True
                    break
                # Row not found after insert — index bloat may have
                # caused a false conflict.  Retry with a regular INSERT
                # (ignore_conflicts=False) to force the issue.
                logger.warning(
                    "bulk_create with ignore_conflicts returned silently "
                    "but row not found for workflow %s v%s — retrying "
                    "without ignore_conflicts (attempt %d/%d)",
                    workflow_name, version, attempt + 1, max_retries + 1,
                )
                with transaction.atomic():
                    WorkflowDefinition.objects.bulk_create(
                        [wf_def],
                        ignore_conflicts=False,
                    )
                row_persisted = True
                break
            except (OperationalError, InternalError, IntegrityError) as e:
                error_msg = str(e).lower()
                is_lock_timeout = "lock timeout" in error_msg
                is_duplicate = (
                    "duplicate key" in error_msg
                    or "unique constraint" in error_msg
                    or "already exists" in error_msg
                )

                if is_duplicate:
                    # Another process inserted the row — fetch and return it.
                    existing = WorkflowDefinition.objects.filter(
                        name=workflow_name, version=version,
                    ).first()
                    if existing:
                        logger.info(
                            f"Workflow {workflow_name} version {version} "
                            f"created concurrently; using existing row."
                        )
                        return existing

                if (is_lock_timeout or is_duplicate) and attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"Lock timeout on workflow_definitions insert "
                        f"(attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)

                    # The lock holder may have committed by now —
                    # check whether the row already exists before
                    # attempting another insert (which would wait
                    # on the lock again).
                    existing = WorkflowDefinition.objects.filter(
                        name=workflow_name, version=version,
                    ).first()
                    if existing:
                        logger.info(
                            f"Workflow {workflow_name} version {version} "
                            f"found via SELECT after lock timeout; "
                            f"using existing row."
                        )
                        return existing
                    continue

                # Re-raise any non-timeout/non-duplicate error, or timeout
                # on the final attempt.
                raise

        if not row_persisted:
            raise OperationalError(
                f"Failed to persist workflow definition {workflow_name} "
                f"version {version} after {max_retries + 1} attempts."
            )

        # ── Fetch the winning row + deactivate other versions ──────────
        # The INSERT succeeded (or the row already existed).  Now fetch it
        # and deactivate all other versions so only this one is active.
        #
        # Both operations run inside their own transaction.atomic savepoint
        # so a lock timeout on the deactivation UPDATE cannot abort the
        # caller's savepoint (e.g. WorkflowRegistry.register_workflow's
        # @transaction.atomic), which would poison the caller's fallback
        # path (transaction aborted → TransactionManagementError on any
        # subsequent query).
        #
        # Deactivation is best-effort: if the UPDATE times out, we log a
        # warning and return the newly-active row — the next registration
        # will retry the deactivation.

        # First fetch the row we just inserted (or the concurrent row that
        # won the race).  Run inside the savepoint so the .get() is also
        # protected from aborted-transaction fallout.
        try:
            with transaction.atomic():
                wf_def = WorkflowDefinition.objects.get(
                    name=workflow_name, version=version
                )
                WorkflowDefinition.objects.filter(
                    name=workflow_name
                ).exclude(id=wf_def.id).update(is_active=False)
        except OperationalError as e:
            logger.warning(
                "Could not deactivate other versions for workflow %s v%s "
                "due to lock contention: %s.  The new version is active; "
                "deactivation will be retried on the next registration.",
                workflow_name, version, e,
            )
            # Fetch the row outside the aborted inner savepoint — the outer
            # transaction is still healthy.
            wf_def = WorkflowDefinition.objects.get(
                name=workflow_name, version=version
            )

        return wf_def

    @classmethod
    def get_latest_version(cls, workflow_name: str) -> WorkflowDefinition | None:
        """
        Get latest version of a workflow definition.

        Args:
            workflow_name: Workflow name

        Returns:
            Latest WorkflowDefinition or None if not found
        """
        return WorkflowDefinition.objects.filter(name=workflow_name).order_by("-created_at").first()

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
        workflow_def = WorkflowDefinition.objects.get(name=workflow_name, version=version)

        # Deactivate other versions
        WorkflowDefinition.objects.filter(name=workflow_name).exclude(id=workflow_def.id).update(
            is_active=False
        )

        # Activate this version
        workflow_def.is_active = True
        workflow_def.save(update_fields=["is_active"])

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
    ) -> list[WorkflowDefinition]:
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
