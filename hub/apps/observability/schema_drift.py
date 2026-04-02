"""
Schema Drift Detection

Compares schemas over time to detect new fields, removed fields, type changes, and nullable changes.
"""
from typing import Dict, List, Any, Optional, Tuple
from django.db import transaction
from django.utils import timezone
import structlog
import hashlib
import json

from .models import SchemaDrift, DataObservabilityMetric
from hub.apps.datasets.models import Dataset
from hub.apps.assets.models import Asset

logger = structlog.get_logger(__name__)


class SchemaDriftDetector:
    """
    Detects schema drift by comparing current schema with previous schema.
    """
    
    DEFAULT_TOLERANCE = {
        "allow_new_fields": True,
        "allow_removed_fields": False,  # Breaking change
        "allow_type_changes": False,  # Breaking change
        "allow_nullable_changes": True,  # Non-breaking (nullable -> non-nullable is breaking, but we allow it with warning)
        "allow_field_reorder": True,  # Non-breaking
    }
    
    @staticmethod
    def calculate_schema_hash(schema_json: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Calculate SHA-256 hash of schema JSON.
        
        Args:
            schema_json: Schema JSON dictionary
        
        Returns:
            SHA-256 hash string, or None if schema_json is None
        """
        if schema_json is None:
            return None
        
        schema_str = json.dumps(schema_json, sort_keys=True)
        return hashlib.sha256(schema_str.encode('utf-8')).hexdigest()
    
    @staticmethod
    def _extract_field_map(
        schema: Optional[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Build ``{field_name: field_info}`` from a schema.

        Supports two formats:
        1. List-of-dicts: ``{"fields": [{"name": "id", "type": "int"}, …]}``
        2. JSON Schema:   ``{"properties": {"id": {"type": "integer"}, …}}``
        """
        if not isinstance(schema, dict):
            return {}

        # Format 1: explicit fields list
        fields = schema.get("fields", [])
        if fields:
            return {
                str(f["name"]): f
                for f in fields
                if isinstance(f, dict) and f.get("name")
            }

        # Format 2: JSON Schema properties
        props = schema.get("properties", {})
        if isinstance(props, dict) and props:
            return {
                name: {**info, "name": name}
                for name, info in props.items()
                if isinstance(info, dict)
            }

        return {}

    @classmethod
    def compare_schemas(
        cls,
        previous_schema: Optional[Dict[str, Any]],
        current_schema: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare two schemas and detect changes.
        
        Args:
            previous_schema: Previous schema JSON
            current_schema: Current schema JSON
        
        Returns:
            Dictionary with detected changes
        """
        if previous_schema is None and current_schema is None:
            return {
                "new_fields": [],
                "removed_fields": [],
                "type_changes": [],
                "nullable_changes": [],
                "has_changes": False
            }
        
        if previous_schema is None:
            # New schema
            current_field_map = cls._extract_field_map(current_schema)
            return {
                "new_fields": list(current_field_map.keys()),
                "removed_fields": [],
                "type_changes": [],
                "nullable_changes": [],
                "has_changes": bool(current_field_map),
            }

        if current_schema is None:
            # Schema removed
            previous_field_map = cls._extract_field_map(previous_schema)
            return {
                "new_fields": [],
                "removed_fields": list(previous_field_map.keys()),
                "type_changes": [],
                "nullable_changes": [],
                "has_changes": bool(previous_field_map),
            }
        
        # Extract fields — supports both list-of-dicts format
        # ({"fields": [{"name": "id", "type": "int"}, ...]})
        # and JSON Schema format
        # ({"properties": {"id": {"type": "integer"}, ...}}).
        previous_field_map = cls._extract_field_map(
            previous_schema,
        )
        current_field_map = cls._extract_field_map(
            current_schema,
        )
        
        # Detect changes
        new_fields = []
        removed_fields = []
        type_changes = []
        nullable_changes = []
        
        # New fields
        for field_name in current_field_map:
            if field_name not in previous_field_map:
                new_fields.append(field_name)
        
        # Removed fields
        for field_name in previous_field_map:
            if field_name not in current_field_map:
                removed_fields.append(field_name)
        
        # Type and nullable changes
        for field_name in previous_field_map:
            if field_name in current_field_map:
                prev_field = previous_field_map[field_name]
                curr_field = current_field_map[field_name]
                
                # Type change
                prev_type = prev_field.get("type") or prev_field.get("data_type")
                curr_type = curr_field.get("type") or curr_field.get("data_type")
                
                if prev_type != curr_type:
                    type_changes.append({
                        "field_name": field_name,
                        "old_type": prev_type,
                        "new_type": curr_type
                    })
                
                # Nullable change
                prev_nullable = prev_field.get("nullable", True)
                curr_nullable = curr_field.get("nullable", True)
                
                if prev_nullable != curr_nullable:
                    nullable_changes.append({
                        "field_name": field_name,
                        "old_nullable": prev_nullable,
                        "new_nullable": curr_nullable
                    })
        
        has_changes = len(new_fields) > 0 or len(removed_fields) > 0 or len(type_changes) > 0 or len(nullable_changes) > 0
        
        return {
            "new_fields": new_fields,
            "removed_fields": removed_fields,
            "type_changes": type_changes,
            "nullable_changes": nullable_changes,
            "has_changes": has_changes
        }
    
    @staticmethod
    def calculate_drift_severity(
        new_fields: List[str],
        removed_fields: List[str],
        type_changes: List[Dict[str, Any]],
        nullable_changes: List[Dict[str, Any]],
        tolerance_config: Dict[str, bool]
    ) -> Tuple[str, bool]:
        """
        Calculate drift severity based on changes and tolerance.
        
        Args:
            new_fields: List of new field names
            removed_fields: List of removed field names
            type_changes: List of type changes
            nullable_changes: List of nullable changes
            tolerance_config: Tolerance configuration
        
        Returns:
            Tuple of (severity, is_within_tolerance)
        """
        is_within_tolerance = True
        severity = "MINOR"
        
        # Check removed fields (breaking change)
        if len(removed_fields) > 0:
            if not tolerance_config.get("allow_removed_fields", False):
                severity = "BREAKING"
                is_within_tolerance = False
            else:
                severity = "NON_BREAKING"
        
        # Check type changes (breaking change)
        if len(type_changes) > 0:
            if not tolerance_config.get("allow_type_changes", False):
                if severity != "BREAKING":
                    severity = "BREAKING"
                is_within_tolerance = False
            else:
                if severity == "MINOR":
                    severity = "NON_BREAKING"
        
        # Check nullable changes (potentially breaking)
        for change in nullable_changes:
            # nullable -> non-nullable is breaking
            if change["old_nullable"] and not change["new_nullable"]:
                if not tolerance_config.get("allow_nullable_changes", True):
                    if severity != "BREAKING":
                        severity = "BREAKING"
                    is_within_tolerance = False
                else:
                    if severity == "MINOR":
                        severity = "NON_BREAKING"
        
        # New fields are non-breaking (unless tolerance says otherwise)
        if len(new_fields) > 0 and not tolerance_config.get("allow_new_fields", True):
            if severity == "MINOR":
                severity = "NON_BREAKING"
            is_within_tolerance = False
        
        return severity, is_within_tolerance
    
    @classmethod
    @transaction.atomic
    def detect_drift(
        cls,
        tenant_id: str,
        dataset: Optional[Dataset] = None,
        asset: Optional[Asset] = None,
        current_schema_json: Optional[Dict[str, Any]] = None,
        tolerance_config: Optional[Dict[str, bool]] = None
    ) -> Optional[SchemaDrift]:
        """
        Detect schema drift by comparing current schema with previous.
        
        Args:
            tenant_id: Tenant UUID
            dataset: Dataset instance (optional)
            asset: Asset instance (optional)
            current_schema_json: Current schema JSON
            tolerance_config: Tolerance configuration (defaults to DEFAULT_TOLERANCE)
        
        Returns:
            SchemaDrift instance if drift detected, None otherwise
        """
        if not dataset and not asset:
            raise ValueError("Either dataset or asset must be provided")
        
        if current_schema_json is None:
            # Try to get schema from dataset
            if dataset and dataset.schema_json:
                current_schema_json = dataset.schema_json
            else:
                return None
        
        # Calculate current schema hash
        current_hash = cls.calculate_schema_hash(current_schema_json)
        if current_hash is None:
            return None
        
        # Get previous schema
        previous_metric = DataObservabilityMetric.objects.filter(
            tenant_id=tenant_id
        )
        
        if dataset:
            previous_metric = previous_metric.filter(dataset=dataset)
        if asset:
            previous_metric = previous_metric.filter(asset=asset)
        
        previous_metric = previous_metric.exclude(
            schema_hash__isnull=True
        ).exclude(
            schema_hash=current_hash  # Exclude metrics with current schema
        ).order_by('-recorded_at').first()
        
        if previous_metric is None:
            # No previous schema, this is the first
            return None
        
        previous_hash = previous_metric.schema_hash
        previous_schema = previous_metric.schema_json
        
        # Check if schema changed
        if current_hash == previous_hash:
            # No change
            return None
        
        # Compare schemas
        comparison = cls.compare_schemas(previous_schema, current_schema_json)
        
        if not comparison["has_changes"]:
            return None
        
        # Use tolerance config
        tolerance = tolerance_config or cls.DEFAULT_TOLERANCE
        
        # Calculate severity
        severity, is_within_tolerance = cls.calculate_drift_severity(
            comparison["new_fields"],
            comparison["removed_fields"],
            comparison["type_changes"],
            comparison["nullable_changes"],
            tolerance
        )
        
        # Create drift record
        drift = SchemaDrift.objects.create(
            tenant_id=tenant_id,
            dataset=dataset,
            asset=asset,
            previous_schema_hash=previous_hash,
            current_schema_hash=current_hash,
            previous_schema_json=previous_schema,
            current_schema_json=current_schema_json,
            new_fields=comparison["new_fields"],
            removed_fields=comparison["removed_fields"],
            type_changes=comparison["type_changes"],
            nullable_changes=comparison["nullable_changes"],
            drift_severity=severity,
            tolerance_config=tolerance,
            is_within_tolerance=is_within_tolerance
        )
        
        logger.info(
            "Schema drift detected",
            drift_id=str(drift.id),
            dataset_id=str(dataset.id) if dataset else None,
            asset_id=str(asset.id) if asset else None,
            severity=severity,
            is_within_tolerance=is_within_tolerance
        )
        
        return drift
    
    @classmethod
    def get_drift_dashboard(
        cls,
        tenant_id: str,
        dataset_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get schema drift dashboard data.
        
        Args:
            tenant_id: Tenant UUID
            dataset_id: Optional dataset UUID filter
            asset_id: Optional asset UUID filter
            limit: Maximum number of records to return
        
        Returns:
            Dashboard data dictionary
        """
        queryset = SchemaDrift.objects.filter(tenant_id=tenant_id)
        
        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)
        
        # Get latest drifts
        drifts = queryset.order_by('-detected_at')[:limit]
        
        # Calculate statistics
        total_drifts = queryset.count()
        breaking_count = queryset.filter(drift_severity="BREAKING").count()
        non_breaking_count = queryset.filter(drift_severity="NON_BREAKING").count()
        minor_count = queryset.filter(drift_severity="MINOR").count()
        within_tolerance_count = queryset.filter(is_within_tolerance=True).count()
        
        # Format results (include all fields expected by SchemaDriftSerializer)
        results = []
        for drift in drifts:
            results.append({
                "id": str(drift.id),
                "dataset_id": str(drift.dataset_id) if drift.dataset_id else None,
                "asset_id": str(drift.asset_id) if drift.asset_id else None,
                "previous_schema_hash": drift.previous_schema_hash,
                "current_schema_hash": drift.current_schema_hash,
                "new_fields": drift.new_fields,
                "removed_fields": drift.removed_fields,
                "type_changes": drift.type_changes,
                "nullable_changes": drift.nullable_changes,
                "drift_severity": drift.drift_severity,
                "tolerance_config": drift.tolerance_config,
                "is_within_tolerance": drift.is_within_tolerance,
                "detected_at": drift.detected_at.isoformat()
            })
        
        return {
            "results": results,
            "summary": {
                "total_drifts": total_drifts,
                "breaking_count": breaking_count,
                "non_breaking_count": non_breaking_count,
                "minor_count": minor_count,
                "within_tolerance_count": within_tolerance_count,
                "breaking_percentage": round((breaking_count / total_drifts * 100) if total_drifts > 0 else 0, 2)
            }
        }

