"""
Schema Evolution Tracking

Tracks schema changes between dataset versions, calculates compatibility levels,
and generates change logs.
"""
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from django.db import models
from django.utils import timezone

from .models import Dataset


class CompatibilityLevel(str, Enum):
    """Schema compatibility levels"""
    FULLY_COMPATIBLE = "FULLY_COMPATIBLE"  # No schema changes
    BACKWARD_COMPATIBLE = "BACKWARD_COMPATIBLE"  # New fields added (non-breaking)
    FORWARD_COMPATIBLE = "FORWARD_COMPATIBLE"  # Fields removed (breaking for consumers)
    INCOMPATIBLE = "INCOMPATIBLE"  # Type changes or both added/removed


class ChangeType(str, Enum):
    """Types of schema changes"""
    FIELD_ADDED = "FIELD_ADDED"
    FIELD_REMOVED = "FIELD_REMOVED"
    FIELD_TYPE_CHANGED = "FIELD_TYPE_CHANGED"
    FIELD_NULLABLE_CHANGED = "FIELD_NULLABLE_CHANGED"
    FIELD_PROPERTY_CHANGED = "FIELD_PROPERTY_CHANGED"
    PRIMARY_KEY_CHANGED = "PRIMARY_KEY_CHANGED"
    UNIQUE_CONSTRAINT_CHANGED = "UNIQUE_CONSTRAINT_CHANGED"
    INDEX_RECOMMENDATION_CHANGED = "INDEX_RECOMMENDATION_CHANGED"


@dataclass
class SchemaChange:
    """Represents a single schema change"""
    change_type: ChangeType
    field_name: Optional[str] = None
    old_value: Any = None
    new_value: Any = None
    description: str = ""
    breaking: bool = False


@dataclass
class SchemaDiff:
    """Complete schema difference between two versions"""
    old_schema: Dict[str, Any]
    new_schema: Dict[str, Any]
    changes: List[SchemaChange]
    compatibility_level: CompatibilityLevel
    summary: Dict[str, int]  # Count of each change type


class SchemaEvolutionTracker:
    """
    Tracks schema evolution between dataset versions.
    """

    @staticmethod
    def calculate_schema_diff(
        old_schema: Dict[str, Any],
        new_schema: Dict[str, Any]
    ) -> SchemaDiff:
        """
        Calculate complete schema difference between two schemas.

        Args:
            old_schema: Old schema JSON
            new_schema: New schema JSON

        Returns:
            SchemaDiff object with all changes
        """
        old_schema = old_schema or {}
        new_schema = new_schema or {}

        old_fields = {f.get('name'): f for f in old_schema.get('fields', [])}
        new_fields = {f.get('name'): f for f in new_schema.get('fields', [])}

        changes = []

        # Find added fields
        added_fields = set(new_fields.keys()) - set(old_fields.keys())
        for field_name in added_fields:
            changes.append(SchemaChange(
                change_type=ChangeType.FIELD_ADDED,
                field_name=field_name,
                new_value=new_fields[field_name],
                description=f"Field '{field_name}' added",
                breaking=False
            ))

        # Find removed fields
        removed_fields = set(old_fields.keys()) - set(new_fields.keys())
        for field_name in removed_fields:
            changes.append(SchemaChange(
                change_type=ChangeType.FIELD_REMOVED,
                field_name=field_name,
                old_value=old_fields[field_name],
                description=f"Field '{field_name}' removed",
                breaking=True
            ))

        # Find modified fields
        common_fields = set(old_fields.keys()) & set(new_fields.keys())
        for field_name in common_fields:
            old_field = old_fields[field_name]
            new_field = new_fields[field_name]

            # Check type changes
            old_type = old_field.get('data_type')
            new_type = new_field.get('data_type')
            if old_type != new_type:
                changes.append(SchemaChange(
                    change_type=ChangeType.FIELD_TYPE_CHANGED,
                    field_name=field_name,
                    old_value=old_type,
                    new_value=new_type,
                    description=f"Field '{field_name}' type changed from {old_type} to {new_type}",
                    breaking=True
                ))

            # Check nullable changes
            old_nullable = old_field.get('nullable', True)
            new_nullable = new_field.get('nullable', True)
            if old_nullable != new_nullable:
                changes.append(SchemaChange(
                    change_type=ChangeType.FIELD_NULLABLE_CHANGED,
                    field_name=field_name,
                    old_value=old_nullable,
                    new_value=new_nullable,
                    description=f"Field '{field_name}' nullable changed from {old_nullable} to {new_nullable}",
                    breaking=not new_nullable  # Breaking if changed from nullable to non-nullable
                ))

            # Check other property changes
            old_props = {k: v for k, v in old_field.items() if k not in ['name', 'data_type', 'nullable', 'sample_values']}
            new_props = {k: v for k, v in new_field.items() if k not in ['name', 'data_type', 'nullable', 'sample_values']}

            for prop_name in set(old_props.keys()) | set(new_props.keys()):
                old_val = old_props.get(prop_name)
                new_val = new_props.get(prop_name)
                if old_val != new_val:
                    changes.append(SchemaChange(
                        change_type=ChangeType.FIELD_PROPERTY_CHANGED,
                        field_name=field_name,
                        old_value=old_val,
                        new_value=new_val,
                        description=f"Field '{field_name}' property '{prop_name}' changed",
                        breaking=False  # Property changes are usually non-breaking
                    ))

        # Check primary key changes
        old_pk = old_schema.get('primary_key_candidates', [])
        new_pk = new_schema.get('primary_key_candidates', [])
        if old_pk != new_pk:
            changes.append(SchemaChange(
                change_type=ChangeType.PRIMARY_KEY_CHANGED,
                old_value=old_pk,
                new_value=new_pk,
                description=f"Primary key candidates changed from {old_pk} to {new_pk}",
                breaking=True
            ))

        # Check unique constraint changes
        old_unique = old_schema.get('unique_constraint_candidates', [])
        new_unique = new_schema.get('unique_constraint_candidates', [])
        if old_unique != new_unique:
            changes.append(SchemaChange(
                change_type=ChangeType.UNIQUE_CONSTRAINT_CHANGED,
                old_value=old_unique,
                new_value=new_unique,
                description=f"Unique constraint candidates changed from {old_unique} to {new_unique}",
                breaking=False
            ))

        # Check index recommendation changes
        old_indexes = old_schema.get('index_recommendations', [])
        new_indexes = new_schema.get('index_recommendations', [])
        if old_indexes != new_indexes:
            changes.append(SchemaChange(
                change_type=ChangeType.INDEX_RECOMMENDATION_CHANGED,
                old_value=old_indexes,
                new_value=new_indexes,
                description=f"Index recommendations changed",
                breaking=False
            ))

        # Calculate compatibility level
        compatibility_level = SchemaEvolutionTracker._calculate_compatibility_level(changes)

        # Generate summary
        summary = {}
        for change_type in ChangeType:
            summary[change_type.value] = sum(1 for c in changes if c.change_type == change_type)

        return SchemaDiff(
            old_schema=old_schema,
            new_schema=new_schema,
            changes=changes,
            compatibility_level=compatibility_level,
            summary=summary
        )

    @staticmethod
    def _calculate_compatibility_level(changes: List[SchemaChange]) -> CompatibilityLevel:
        """
        Calculate compatibility level from list of changes.

        Args:
            changes: List of schema changes

        Returns:
            CompatibilityLevel enum value
        """
        if not changes:
            return CompatibilityLevel.FULLY_COMPATIBLE

        # Check for breaking changes
        breaking_changes = [c for c in changes if c.breaking]
        if breaking_changes:
            # Check if only fields removed (forward compatible)
            only_removed = all(
                c.change_type == ChangeType.FIELD_REMOVED
                for c in breaking_changes
            )
            if only_removed:
                return CompatibilityLevel.FORWARD_COMPATIBLE

            # Otherwise incompatible
            return CompatibilityLevel.INCOMPATIBLE

        # Check if only fields added (backward compatible)
        only_added = all(
            c.change_type == ChangeType.FIELD_ADDED
            for c in changes
        )
        if only_added:
            return CompatibilityLevel.BACKWARD_COMPATIBLE

        # Non-breaking changes only
        return CompatibilityLevel.FULLY_COMPATIBLE

    @staticmethod
    def generate_change_log(
        old_dataset: Dataset,
        new_dataset: Dataset
    ) -> Dict[str, Any]:
        """
        Generate change log between two dataset versions.

        Args:
            old_dataset: Old dataset version
            new_dataset: New dataset version

        Returns:
            Change log dictionary
        """
        schema_diff = SchemaEvolutionTracker.calculate_schema_diff(
            old_dataset.schema_json or {},
            new_dataset.schema_json or {}
        )

        change_log = {
            'from_version': {
                'id': str(old_dataset.id),
                'semantic_version': old_dataset.semantic_version,
                'version': old_dataset.version,
                'created_at': old_dataset.created_at.isoformat()
            },
            'to_version': {
                'id': str(new_dataset.id),
                'semantic_version': new_dataset.semantic_version,
                'version': new_dataset.version,
                'created_at': new_dataset.created_at.isoformat()
            },
            'compatibility_level': schema_diff.compatibility_level.value,
            'summary': schema_diff.summary,
            'changes': [
                {
                    'type': change.change_type.value,
                    'field_name': change.field_name,
                    'description': change.description,
                    'breaking': change.breaking,
                    'old_value': change.old_value,
                    'new_value': change.new_value
                }
                for change in schema_diff.changes
            ],
            'generated_at': timezone.now().isoformat()
        }

        return change_log

    @staticmethod
    def track_schema_version(
        dataset: Dataset,
        parent_dataset: Optional[Dataset] = None
    ) -> 'SchemaVersion':
        """
        Track schema version for a dataset.

        Args:
            dataset: Dataset to track
            parent_dataset: Parent dataset version (optional)

        Returns:
            SchemaVersion instance
        """
        from .models import SchemaVersion

        schema_diff = None
        compatibility_level = CompatibilityLevel.FULLY_COMPATIBLE

        if parent_dataset:
            schema_diff = SchemaEvolutionTracker.calculate_schema_diff(
                parent_dataset.schema_json or {},
                dataset.schema_json or {}
            )
            compatibility_level = schema_diff.compatibility_level

        # Use get_or_create to handle duplicate calls (OneToOneField constraint)
        schema_version, created = SchemaVersion.objects.get_or_create(
            dataset=dataset,
            defaults={
                'parent_schema_version': SchemaVersion.objects.filter(
                    dataset=parent_dataset
                ).first() if parent_dataset else None,
                'schema_json': dataset.schema_json or {},
                'compatibility_level': compatibility_level.value,
                'change_summary': schema_diff.summary if schema_diff else {},
                'change_log': SchemaEvolutionTracker.generate_change_log(
                    parent_dataset, dataset
                ) if parent_dataset else {}
            }
        )

        # If already exists, update it with latest data
        if not created:
            schema_version.parent_schema_version = SchemaVersion.objects.filter(
                dataset=parent_dataset
            ).first() if parent_dataset else None
            schema_version.schema_json = dataset.schema_json or {}
            schema_version.compatibility_level = compatibility_level.value
            schema_version.change_summary = schema_diff.summary if schema_diff else {}
            schema_version.change_log = SchemaEvolutionTracker.generate_change_log(
                parent_dataset, dataset
            ) if parent_dataset else {}
            schema_version.save()

        return schema_version

