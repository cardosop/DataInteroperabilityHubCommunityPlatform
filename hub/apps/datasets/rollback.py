"""
Version Rollback Automation

Automated rollback functionality for dataset versions based on quality and compliance failures.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import structlog
from django.db import transaction

from hub.apps.dq.models import DQRun, DQRunStatus

from .models import Dataset
from .versioning import VersionHistoryManager

logger = structlog.get_logger(__name__)


class RollbackTrigger(str, Enum):
    """Rollback trigger types"""

    QUALITY_FAILURE = "QUALITY_FAILURE"
    COMPLIANCE_FAILURE = "COMPLIANCE_FAILURE"
    MANUAL = "MANUAL"


class RollbackStatus(str, Enum):
    """Rollback status"""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RollbackConfig:
    """Configuration for automated rollback"""

    def __init__(
        self,
        enable_auto_rollback: bool = False,
        require_approval: bool = True,
        quality_threshold: float = 0.8,  # Quality score threshold
        compliance_required: bool = True,
        rollback_on_quality_failure: bool = True,
        rollback_on_compliance_failure: bool = True,
    ):
        self.enable_auto_rollback = enable_auto_rollback
        self.require_approval = require_approval
        self.quality_threshold = quality_threshold
        self.compliance_required = compliance_required
        self.rollback_on_quality_failure = rollback_on_quality_failure
        self.rollback_on_compliance_failure = rollback_on_compliance_failure


class VersionRollbackManager:
    """
    Manages automated rollback of dataset versions.
    """

    @staticmethod
    def check_rollback_conditions(
        dataset: Dataset, config: RollbackConfig | None = None
    ) -> dict[str, Any]:
        """
        Check if rollback conditions are met for a dataset version.

        Args:
            dataset: Dataset version to check
            config: Rollback configuration (default: require approval, rollback on failures)

        Returns:
            Dictionary with rollback recommendation and reasons
        """
        if config is None:
            config = RollbackConfig()

        if not config.enable_auto_rollback:
            return {"should_rollback": False, "reason": "Auto-rollback is disabled", "triggers": []}

        triggers = []
        should_rollback = False

        # Check quality failures
        if config.rollback_on_quality_failure:
            quality_failure = VersionRollbackManager._check_quality_failure(
                dataset, config.quality_threshold
            )
            if quality_failure:
                triggers.append(
                    {
                        "type": RollbackTrigger.QUALITY_FAILURE.value,
                        "reason": quality_failure["reason"],
                        "details": quality_failure["details"],
                    }
                )
                should_rollback = True

        # Check compliance failures
        if config.rollback_on_compliance_failure:
            compliance_failure = VersionRollbackManager._check_compliance_failure(dataset)
            if compliance_failure:
                triggers.append(
                    {
                        "type": RollbackTrigger.COMPLIANCE_FAILURE.value,
                        "reason": compliance_failure["reason"],
                        "details": compliance_failure["details"],
                    }
                )
                should_rollback = True

        return {
            "should_rollback": should_rollback,
            "reason": "Quality or compliance failure detected"
            if should_rollback
            else "No failures detected",
            "triggers": triggers,
            "requires_approval": config.require_approval,
        }

    @staticmethod
    def _check_quality_failure(dataset: Dataset, quality_threshold: float) -> dict[str, Any] | None:
        """Check if quality failure occurred"""
        # Get latest DQ run for this dataset
        latest_dq_run = (
            DQRun.objects.filter(
                tenant=dataset.tenant, dataset=dataset, status=DQRunStatus.SUCCEEDED
            )
            .order_by("-completed_at")
            .first()
        )

        if not latest_dq_run:
            return None

        # Check quality score
        if latest_dq_run.quality_score is not None:
            quality_score_normalized = latest_dq_run.quality_score / 100.0
            if quality_score_normalized < quality_threshold:
                return {
                    "reason": f"Quality score {latest_dq_run.quality_score} below threshold {quality_threshold * 100}",
                    "details": {
                        "quality_score": latest_dq_run.quality_score,
                        "threshold": quality_threshold * 100,
                        "dq_run_id": str(latest_dq_run.id),
                    },
                }

        # Check overall status
        if latest_dq_run.overall_status == "FAIL":
            return {
                "reason": "DQ run overall status is FAIL",
                "details": {
                    "overall_status": latest_dq_run.overall_status,
                    "dq_run_id": str(latest_dq_run.id),
                },
            }

        return None

    @staticmethod
    def _check_compliance_failure(dataset: Dataset) -> dict[str, Any] | None:
        """Check if compliance failure occurred"""
        # Get latest compliance run for this dataset
        try:
            from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus

            latest_compliance_run = (
                ComplianceRun.objects.filter(
                    tenant=dataset.tenant, dataset=dataset, status=ComplianceRunStatus.SUCCEEDED
                )
                .order_by("-completed_at")
                .first()
            )

            if not latest_compliance_run:
                return None

            # Check compliance status (check overall_status or risk_level)
            overall_status = getattr(latest_compliance_run, "overall_status", None)
            risk_level = getattr(latest_compliance_run, "risk_level", None)

            if overall_status == "FAIL" or (risk_level and risk_level in ["HIGH", "CRITICAL"]):
                return {
                    "reason": f"Compliance run failure: overall_status={overall_status}, risk_level={risk_level}",
                    "details": {
                        "overall_status": overall_status,
                        "risk_level": risk_level,
                        "compliance_run_id": str(latest_compliance_run.id),
                    },
                }
        except (ImportError, AttributeError):
            # Compliance models not available or field doesn't exist
            pass

        return None

    @staticmethod
    @transaction.atomic
    def execute_rollback(
        dataset: Dataset,
        approved_by: Any | None = None,  # User object
        reason: str | None = None,
        config: RollbackConfig | None = None,
    ) -> dict[str, Any]:
        """
        Execute rollback to previous version.

        Args:
            dataset: Current dataset version to rollback
            approved_by: User who approved the rollback (if approval required)
            reason: Reason for rollback
            config: Rollback configuration

        Returns:
            Dictionary with rollback result
        """
        if config is None:
            config = RollbackConfig()

        # Check if rollback is needed
        rollback_check = VersionRollbackManager.check_rollback_conditions(dataset, config)

        if not rollback_check["should_rollback"] and not reason:
            return {
                "success": False,
                "error": "No rollback conditions met",
                "rollback_check": rollback_check,
            }

        # Check approval requirement
        if config.require_approval and not approved_by:
            return {
                "success": False,
                "error": "Approval required but no approver provided",
                "requires_approval": True,
            }

        # Get parent version
        if not dataset.parent_version:
            return {"success": False, "error": "No parent version to rollback to"}

        parent_version = dataset.parent_version

        # Restore parent version
        try:
            restored = VersionHistoryManager.restore_version(parent_version)

            # Log rollback event
            logger.info(
                "Dataset version rolled back",
                dataset_id=str(dataset.id),
                parent_version_id=str(parent_version.id),
                reason=reason,
                approved_by=str(approved_by.id) if approved_by else None,
                triggers=rollback_check.get("triggers", []),
            )

            return {
                "success": True,
                "rolled_back_from": {
                    "dataset_id": str(dataset.id),
                    "version": dataset.version,
                    "semantic_version": dataset.semantic_version,
                },
                "rolled_back_to": {
                    "dataset_id": str(restored.id),
                    "version": restored.version,
                    "semantic_version": restored.semantic_version,
                },
                "reason": reason,
                "approved_by": str(approved_by.id) if approved_by else None,
                "triggers": rollback_check.get("triggers", []),
            }
        except Exception as e:
            logger.error("Rollback failed", dataset_id=str(dataset.id), error=str(e), exc_info=True)
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_rollback_history(
        asset_id: str, tenant_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get rollback history for an asset.

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
            limit: Maximum number of history entries

        Returns:
            List of rollback history entries
        """
        # This would typically be stored in a separate rollback history table
        # For now, we'll return empty list as this is a placeholder
        # In production, you'd query a RollbackHistory model
        return []
