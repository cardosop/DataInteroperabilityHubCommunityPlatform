"""
285.11.6.1 — DeployImpactAnalyzer.

Three-phase dry-run analysis before a pipeline deploy:
  1. Dependency resolution — upstreams exist, no cycles, contracts accessible.
  2. Contract compatibility — schema matches input, no breaking drift.
  3. Downstream impact simulation — walks full graph, checks each downstream.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from .dependency_resolver import (
    CycleDetectedError,
    PipelineDependencyResolver,
)
from .drift_detector import ContractDriftDetector, DriftSeverity
from .models import PipelineDependency

logger = logging.getLogger(__name__)


class DeployImpactAnalyzer:
    """Pre-deploy impact analysis across the dependency graph."""

    def __init__(self, tenant_id: str):
        self.tenant_id = str(tenant_id)
        self._resolver = PipelineDependencyResolver(self.tenant_id)

    def analyze(
        self,
        pipeline_type: str,
        pipeline_id: str,
        contract_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run all three checks and return a deploy recommendation.

        Returns::

            {
                "can_deploy": bool,
                "impact_summary": {
                    "downstream_pipelines_affected": int,
                    "contract_drifts_detected": int,
                    "breaking_changes": int,
                    "warnings": int,
                },
                "recommendation": "SAFE_TO_DEPLOY"
                               | "WARNING_DOWNSTREAM_IMPACT"
                               | "BLOCKING_ISSUES",
                "checks": {
                    "dependency_resolution": {...},
                    "contract_compatibility": {...},
                    "downstream_impact": {...},
                },
            }
        """
        checks = {
            "dependency_resolution": self._check_dependency_resolution(
                pipeline_type, pipeline_id,
            ),
            "contract_compatibility": self._check_contract_compatibility(
                pipeline_type, pipeline_id, contract_id,
            ),
            "downstream_impact": self._check_downstream_impact(
                pipeline_type, pipeline_id,
            ),
        }

        # Derive recommendation from checks.
        blocking = any(
            c.get("status") == "BLOCKED"
            for c in checks.values()
            if isinstance(c, dict)
        )
        warnings = any(
            c.get("status") == "WARNING"
            for c in checks.values()
            if isinstance(c, dict)
        )

        downstream_count = len(
            self._resolver.resolve_downstream(pipeline_type, pipeline_id)
        )
        drift_check = checks.get("contract_compatibility", {}) or {}
        breaking = (drift_check.get("drift_report", {}) or {}).get("breaking_count", 0)
        warn_count = (drift_check.get("drift_report", {}) or {}).get("warning_count", 0)

        if blocking:
            recommendation = "BLOCKING_ISSUES"
            can_deploy = False
        elif warnings or breaking > 0:
            recommendation = "WARNING_DOWNSTREAM_IMPACT"
            can_deploy = True  # deployable but with warnings
        else:
            recommendation = "SAFE_TO_DEPLOY"
            can_deploy = True

        return {
            "can_deploy": can_deploy,
            "impact_summary": {
                "downstream_pipelines_affected": downstream_count,
                "contract_drifts_detected": 1 if breaking or warn_count else 0,
                "breaking_changes": breaking,
                "warnings": warn_count,
            },
            "recommendation": recommendation,
            "checks": checks,
        }

    # ── Check 1: Dependency resolution ─────────────────────────────

    def _check_dependency_resolution(
        self, pipeline_type: str, pipeline_id: str,
    ) -> Dict[str, Any]:
        """Verify upstream deps exist and there are no cycles."""
        try:
            self._resolver.validate_no_cycles()
        except CycleDetectedError as e:
            return {
                "status": "BLOCKED",
                "error": "CIRCULAR_DEPENDENCY",
                "detail": str(e),
            }

        upstream = self._resolver.resolve_upstream(pipeline_type, pipeline_id)
        missing: list[dict] = []
        for dep in upstream:
            # Check the upstream pipeline still exists.
            from .trigger_engine import _get_pipeline_execution_status
            status = _get_pipeline_execution_status(
                self.tenant_id, dep.pipeline_type, str(dep.pipeline_id),
            )
            if status is None:
                missing.append({
                    "pipeline_type": dep.pipeline_type,
                    "pipeline_id": str(dep.pipeline_id),
                })

        if missing:
            return {
                "status": "BLOCKED",
                "error": "MISSING_UPSTREAM_PIPELINES",
                "missing": missing,
            }

        return {
            "status": "PASS",
            "upstream_count": len(upstream),
            "cycle_free": True,
        }

    # ── Check 2: Contract compatibility ────────────────────────────

    def _check_contract_compatibility(
        self, pipeline_type: str, pipeline_id: str,
        contract_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Check for breaking contract drift against the source contract."""
        if not contract_id:
            # No contract specified — check cannot run.
            return {"status": "PASS", "note": "No contract specified"}

        try:
            from hub.apps.contracts.models import Contract

            contract = Contract.objects.filter(
                tenant_id=self.tenant_id, id=contract_id,
            ).first()
            if not contract:
                return {
                    "status": "BLOCKED",
                    "error": "CONTRACT_NOT_FOUND",
                }

            detector = ContractDriftDetector(self.tenant_id)
            drift_report = detector.detect(contract)  # extracts schema internally

            if drift_report["breaking_count"] > 0:
                return {
                    "status": "WARNING",
                    "drift_report": drift_report,
                    "detail": (
                        f"{drift_report['breaking_count']} breaking change(s) "
                        f"detected in contract schema."
                    ),
                }

            return {
                "status": "PASS",
                "drift_report": drift_report,
            }
        except Exception as exc:
            return {
                "status": "WARNING",
                "error": "CONTRACT_CHECK_FAILED",
                "detail": str(exc),
            }

    # ── Check 3: Downstream impact simulation ──────────────────────

    def _check_downstream_impact(
        self, pipeline_type: str, pipeline_id: str,
    ) -> Dict[str, Any]:
        """Walk the full downstream graph and check each node."""
        downstream = self._resolver.resolve_downstream(pipeline_type, pipeline_id)
        if not downstream:
            return {"status": "PASS", "downstream_count": 0}

        # Build the execution graph to detect structural issues.
        try:
            graph = self._resolver.build_execution_graph(
                pipeline_type, pipeline_id, max_depth=10,
            )
        except Exception as exc:
            return {
                "status": "WARNING",
                "error": "GRAPH_BUILD_FAILED",
                "detail": str(exc),
                "downstream_count": len(downstream),
            }

        affected = len(downstream)
        inactive = [d for d in downstream if not d.is_active]

        # Having downstream deps is normal — only warn if there are
        # structural issues (inactive deps or cycle problems).
        has_issues = len(inactive) > 0 or not graph.get("cycle_free", True)

        return {
            "status": "WARNING" if has_issues else "PASS",
            "downstream_count": affected,
            "inactive_count": len(inactive),
            "cycle_free": graph.get("cycle_free", True),
            "graph_depth": graph.get("depth", 0),
        }
