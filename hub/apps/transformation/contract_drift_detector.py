"""
285.9.5 — ContractDriftDetector: detect schema drift between upstream datasets
and downstream transformation pipelines.

When a source dataset gets a new version, this module checks whether the schema
has changed in a way that could break downstream transformation pipelines, and
classifies the change severity so pipeline owners can be alerted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DriftSeverity(Enum):
    BREAKING = "BREAKING"  # Column removed or type changed
    WARNING = "WARNING"  # Column added or nullable changed
    INFO = "INFO"  # Column reordered or comment changed


@dataclass
class DriftResult:
    """A single schema change detected between two versions."""

    field_name: str
    severity: DriftSeverity
    description: str
    previous_value: str | None = None
    current_value: str | None = None


@dataclass
class DriftReport:
    """Complete drift analysis result for a downstream pipeline."""

    pipeline_id: str
    pipeline_name: str
    upstream_dataset_id: str
    has_breaking_changes: bool = False
    changes: list[DriftResult] = field(default_factory=list)

    @property
    def breaking(self) -> list[DriftResult]:
        return [c for c in self.changes if c.severity == DriftSeverity.BREAKING]

    @property
    def warnings(self) -> list[DriftResult]:
        return [c for c in self.changes if c.severity == DriftSeverity.WARNING]

    @property
    def info(self) -> list[DriftResult]:
        return [c for c in self.changes if c.severity == DriftSeverity.INFO]


class ContractDriftDetector:
    """Detect schema drift between a dataset's current and previous schema
    versions, and identify which downstream transformation pipelines are
    affected.

    Usage::

        detector = ContractDriftDetector()
        reports = detector.detect(
            upstream_dataset=dataset,
            previous_schema=old_schema,
            current_schema=new_schema,
        )
        for report in reports:
            if report.has_breaking_changes:
                # Alert pipeline owner
                ...
    """

    @staticmethod
    def detect(
        upstream_dataset: Any,  # Dataset instance
        previous_schema: dict[str, Any] | None = None,
        current_schema: dict[str, Any] | None = None,
    ) -> list[DriftReport]:
        """Detect schema drift and return impact reports for all affected
        downstream transformation pipelines.

        Args:
            upstream_dataset: The Dataset that received a new version.
            previous_schema: Schema dict with ``fields`` list from the
                previous dataset version.
            current_schema: Schema dict with ``fields`` list from the
                new dataset version.

        Returns:
            List of DriftReport, one per affected downstream pipeline.
        """
        # If no schemas to compare, nothing to detect.
        if not previous_schema or not current_schema:
            return []

        changes = ContractDriftDetector._compare_schemas(
            previous_schema,
            current_schema,
        )
        if not changes:
            return []

        # Find downstream transformation pipelines that consume this dataset.
        downstream = ContractDriftDetector._find_downstream_pipelines(
            upstream_dataset,
        )
        if not downstream:
            return []

        reports: list[DriftReport] = []
        for pipeline in downstream:
            report = DriftReport(
                pipeline_id=str(pipeline.id),
                pipeline_name=pipeline.name,
                upstream_dataset_id=str(upstream_dataset.id),
                has_breaking_changes=any(c.severity == DriftSeverity.BREAKING for c in changes),
                changes=list(changes),
            )
            reports.append(report)

        return reports

    @staticmethod
    def _compare_schemas(
        previous: dict[str, Any],
        current: dict[str, Any],
    ) -> list[DriftResult]:
        """Compare two schema dicts and return a list of changes."""
        prev_fields: dict[str, dict[str, Any]] = {f["name"]: f for f in previous.get("fields", [])}
        curr_fields: dict[str, dict[str, Any]] = {f["name"]: f for f in current.get("fields", [])}

        changes: list[DriftResult] = []

        # Removed columns (BREAKING)
        for name in sorted(set(prev_fields) - set(curr_fields)):
            prev_type = prev_fields[name].get("data_type", "unknown")
            changes.append(
                DriftResult(
                    field_name=name,
                    severity=DriftSeverity.BREAKING,
                    description=f"Column '{name}' was removed",
                    previous_value=prev_type,
                )
            )

        # Added columns (WARNING)
        for name in sorted(set(curr_fields) - set(prev_fields)):
            curr_type = curr_fields[name].get("data_type", "unknown")
            changes.append(
                DriftResult(
                    field_name=name,
                    severity=DriftSeverity.WARNING,
                    description=f"Column '{name}' was added",
                    current_value=curr_type,
                )
            )

        # Changed columns
        for name in sorted(set(prev_fields) & set(curr_fields)):
            p = prev_fields[name]
            c = curr_fields[name]
            p_type = p.get("data_type", "").lower()
            c_type = c.get("data_type", "").lower()
            p_nullable = p.get("nullable")
            c_nullable = c.get("nullable")

            if p_type != c_type:
                changes.append(
                    DriftResult(
                        field_name=name,
                        severity=DriftSeverity.BREAKING,
                        description=f"Column '{name}' type changed from {p_type} to {c_type}",
                        previous_value=p_type,
                        current_value=c_type,
                    )
                )
            elif p_nullable is not None and c_nullable is not None and p_nullable != c_nullable:
                changes.append(
                    DriftResult(
                        field_name=name,
                        severity=DriftSeverity.WARNING,
                        description=f"Column '{name}' nullability changed",
                        previous_value=str(p_nullable),
                        current_value=str(c_nullable),
                    )
                )

        return changes

    @staticmethod
    def _find_downstream_pipelines(dataset: Any) -> list[Any]:
        """Find active transformation pipelines that consume *dataset*."""
        from hub.apps.transformation.models import (
            PipelineStatus,
            TransformationPipeline,
        )

        pipelines = TransformationPipeline.objects.filter(
            tenant_id=dataset.tenant_id,
            status__in=[PipelineStatus.ACTIVE, PipelineStatus.DRAFT],
        )

        downstream: list[TransformationPipeline] = []
        for pipeline in pipelines:
            try:
                pdef = (
                    pipeline.get_pipeline_definition()
                    if hasattr(pipeline, "get_pipeline_definition")
                    else pipeline.pipeline_definition
                )
            except Exception:
                pdef = pipeline.pipeline_definition

            # Check if this dataset is in the pipeline's declared inputs.
            input_ids = pdef.get("input_dataset_ids", []) if isinstance(pdef, dict) else []
            if str(dataset.id) in [str(i) for i in input_ids]:
                downstream.append(pipeline)
                continue

            # Also check metadata.source_asset_id (legacy trigger field).
            metadata = pipeline.metadata or {}
            source_id = metadata.get("source_asset_id")
            if source_id and str(dataset.asset_id) == str(source_id):
                downstream.append(pipeline)

        return downstream
