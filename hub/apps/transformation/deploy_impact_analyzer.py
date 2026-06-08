"""
285.9.6 — DeployImpactAnalyzer: pre-deploy validation of dependency resolution
and contract compatibility.

Before executing or deploying a transformation pipeline, this module traverses
the orchestration dependency graph to find all downstream pipelines that would
be affected, checks contract compatibility, and produces an impact report so
operators can assess risk before proceeding.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DownstreamImpact:
    """Impact assessment for a single downstream pipeline."""
    pipeline_id: str
    pipeline_name: str
    pipeline_status: str
    contract_compatible: bool = True
    contract_conflicts: List[Dict[str, str]] = field(default_factory=list)
    estimated_impact: str = "none"  # none, low, medium, high


@dataclass
class ImpactReport:
    """Complete pre-deploy impact analysis for a transformation pipeline."""
    pipeline_id: str
    pipeline_name: str
    downstream_pipelines: List[DownstreamImpact] = field(default_factory=list)
    total_downstream: int = 0
    breaking_count: int = 0
    estimated_downtime: Optional[str] = None  # human-readable, e.g. "~5 min"

    @property
    def is_safe_to_deploy(self) -> bool:
        """True when no downstream pipelines have contract conflicts."""
        return self.breaking_count == 0


class DeployImpactAnalyzer:
    """Analyze the impact of deploying or executing a transformation pipeline
    on all downstream pipelines in the dependency graph.

    Usage::

        analyzer = DeployImpactAnalyzer()
        report = analyzer.analyze(pipeline_id="...", tenant_id="...")
        if not report.is_safe_to_deploy:
            print(f"WARNING: {report.breaking_count} downstream pipelines affected")
    """

    @staticmethod
    def analyze(pipeline_id: str, tenant_id: str) -> ImpactReport:
        """Analyze deployment impact for *pipeline_id*.

        Args:
            pipeline_id: The transformation pipeline being deployed/executed.
            tenant_id: Tenant scope for the analysis.

        Returns:
            ImpactReport with downstream impact details.
        """
        from hub.apps.transformation.models import (
            PipelineStatus,
            TransformationPipeline,
        )

        try:
            pipeline = TransformationPipeline.objects.get(
                id=pipeline_id, tenant_id=tenant_id,
            )
        except TransformationPipeline.DoesNotExist:
            raise ValueError(f"Pipeline {pipeline_id} not found in tenant {tenant_id}")

        report = ImpactReport(
            pipeline_id=str(pipeline.id),
            pipeline_name=pipeline.name,
        )

        # Find downstream pipelines via the orchestration dependency graph.
        downstream = DeployImpactAnalyzer._find_downstream_pipelines(
            pipeline, tenant_id,
        )
        report.total_downstream = len(downstream)

        output_schema = DeployImpactAnalyzer._get_output_schema(pipeline)

        for ds_pipeline in downstream:
            impact = DeployImpactAnalyzer._assess_downstream_impact(
                ds_pipeline, output_schema,
            )
            report.downstream_pipelines.append(impact)
            if not impact.contract_compatible:
                report.breaking_count += 1

        if report.breaking_count > 0:
            report.estimated_downtime = (
                f"~{report.breaking_count * 5} min — "
                f"{report.breaking_count} downstream pipeline(s) may fail"
            )

        return report

    @staticmethod
    def _find_downstream_pipelines(
        pipeline: Any, tenant_id: str,
    ) -> List[Any]:
        """Find downstream transformation pipelines that depend on *pipeline*.

        Uses the orchestration trigger engine's dependency graph to find
        pipelines scheduled to run after this one.
        """
        from hub.apps.transformation.models import TransformationPipeline

        try:
            pdef = (
                pipeline.get_pipeline_definition()
                if hasattr(pipeline, "get_pipeline_definition")
                else pipeline.pipeline_definition
            )
        except Exception:
            pdef = pipeline.pipeline_definition

        # Find pipelines that consume this pipeline's output datasets.
        output_ids = (
            pdef.get("output_dataset_ids", [])
            if isinstance(pdef, dict) else []
        )

        if not output_ids:
            # Check metadata for result asset info from previous runs.
            metadata = pipeline.metadata or {}
            result_asset_id = metadata.get("result_asset_id")
            if result_asset_id:
                output_ids = [result_asset_id]

        downstream: List[TransformationPipeline] = []
        seen: set = set()

        for output_id in output_ids:
            # Find pipelines that have this output in their input_dataset_ids.
            candidates = TransformationPipeline.objects.filter(
                tenant_id=tenant_id,
            ).exclude(id=pipeline.id)
            for candidate in candidates:
                if candidate.id in seen:
                    continue
                try:
                    cdef = (
                        candidate.get_pipeline_definition()
                        if hasattr(candidate, "get_pipeline_definition")
                        else candidate.pipeline_definition
                    )
                except Exception:
                    cdef = candidate.pipeline_definition
                input_ids = (
                    cdef.get("input_dataset_ids", [])
                    if isinstance(cdef, dict) else []
                )
                if str(output_id) in [str(i) for i in input_ids]:
                    downstream.append(candidate)
                    seen.add(candidate.id)

        return downstream

    @staticmethod
    def _get_output_schema(pipeline: Any) -> Optional[Dict[str, Any]]:
        """Extract the expected output schema from the pipeline's metadata."""
        metadata = pipeline.metadata or {}
        return metadata.get("output_schema")

    @staticmethod
    def _assess_downstream_impact(
        downstream: Any,
        upstream_output_schema: Optional[Dict[str, Any]],
    ) -> DownstreamImpact:
        """Assess whether *downstream* can consume *upstream_output_schema*."""
        impact = DownstreamImpact(
            pipeline_id=str(downstream.id),
            pipeline_name=downstream.name,
            pipeline_status=downstream.status,
        )

        if not upstream_output_schema:
            return impact  # No schema to validate against — assume compatible

        # Compare upstream output schema to downstream's expected input.
        try:
            pdef = (
                downstream.get_pipeline_definition()
                if hasattr(downstream, "get_pipeline_definition")
                else downstream.pipeline_definition
            )
        except Exception:
            pdef = downstream.pipeline_definition

        expected_input = (
            pdef.get("expected_input_schema", {})
            if isinstance(pdef, dict) else {}
        )
        if not expected_input:
            return impact  # No explicit input expectations — assume compatible

        upstream_fields = {
            f["name"]: f for f in upstream_output_schema.get("fields", [])
        }
        expected_fields = {
            f["name"]: f for f in expected_input.get("fields", [])
        }

        conflicts: List[Dict[str, str]] = []

        # Check for removed required fields.
        for name, expected in expected_fields.items():
            if name not in upstream_fields:
                conflicts.append({
                    "field": name,
                    "issue": "missing",
                    "expected_type": expected.get("data_type", "unknown"),
                })
            else:
                u_type = upstream_fields[name].get("data_type", "").lower()
                e_type = expected.get("data_type", "").lower()
                if u_type != e_type:
                    conflicts.append({
                        "field": name,
                        "issue": "type_mismatch",
                        "expected_type": e_type,
                        "actual_type": u_type,
                    })

        if conflicts:
            impact.contract_compatible = False
            impact.contract_conflicts = conflicts
            impact.estimated_impact = (
                "high" if len(conflicts) > 2 else
                "medium" if len(conflicts) > 0 else "low"
            )

        return impact
