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

        # Check if version already exists - if so, return it (idempotent)
        existing = WorkflowDefinition.objects.filter(name=workflow_name, version=version).first()
        if existing:
            # Workflow already exists - return it instead of raising error (idempotent behavior)
            return existing

        # Validate created_by_id if provided
        created_by = None
        if created_by_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                created_by = User.objects.get(id=created_by_id)
            except User.DoesNotExist:
                # User doesn't exist - log warning and continue without created_by
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"User {created_by_id} not found for workflow {workflow_name}, "
                    "creating workflow without created_by"
                )

        # Create new version
        workflow_def = WorkflowDefinition.objects.create(
            name=workflow_name,
            version=version,
            dsl_json=dsl_json,
            description=description,
            created_by=created_by,
            is_active=True  # New version becomes active by default
        )

        # Deactivate other versions (only one active version per workflow)
        WorkflowDefinition.objects.filter(
            name=workflow_name
        ).exclude(id=workflow_def.id).update(is_active=False)

        return workflow_def

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

