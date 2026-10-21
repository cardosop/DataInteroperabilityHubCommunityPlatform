"""
DQ Anomaly Detection

Automatic detection of anomalies in data quality metrics.
"""

from __future__ import annotations

import statistics
from typing import Any

import structlog
from django.db.models import Q
from django.utils import timezone

from .models import DQAnomaly, DQAnomalySeverity, DQRun, DQRunStatus

logger = structlog.get_logger(__name__)


class AnomalyDetector:
    """
    Detects anomalies in data quality metrics using statistical methods.
    """

    Z_SCORE_THRESHOLD = 3.0  # Standard deviations for z-score detection
    IQR_MULTIPLIER = 1.5  # IQR multiplier for outlier detection

    @staticmethod
    def detect_anomalies(
        dq_run: DQRun, metric_type: str = "quality_score", lookback_periods: int = 30
    ) -> list[DQAnomaly]:
        """
        Detect anomalies in a DQ run.

        Args:
            dq_run: DQ run to analyze
            metric_type: Type of metric to analyze
            lookback_periods: Number of historical periods to use for baseline

        Returns:
            List of detected anomalies
        """
        anomalies = []

        # Get metric value
        metric_value = AnomalyDetector._get_metric_value(dq_run, metric_type)
        if metric_value is None:
            return anomalies

        # Get historical baseline
        baseline = AnomalyDetector._get_baseline(dq_run, metric_type, lookback_periods)

        if not baseline:
            # Not enough data for anomaly detection
            return anomalies

        # Check for z-score outlier
        z_score_anomaly = AnomalyDetector._check_z_score(
            dq_run, metric_type, metric_value, baseline
        )
        if z_score_anomaly:
            anomalies.append(z_score_anomaly)

        # Check for IQR outlier
        iqr_anomaly = AnomalyDetector._check_iqr(dq_run, metric_type, metric_value, baseline)
        if iqr_anomaly:
            anomalies.append(iqr_anomaly)

        # Check for sudden drop
        sudden_drop_anomaly = AnomalyDetector._check_sudden_drop(
            dq_run, metric_type, metric_value, baseline
        )
        if sudden_drop_anomaly:
            anomalies.append(sudden_drop_anomaly)

        return anomalies

    @staticmethod
    def _get_metric_value(dq_run: DQRun, metric_type: str) -> float | None:
        """Get metric value from DQ run"""
        if metric_type == "quality_score":
            return dq_run.quality_score

        # Extract from details_json
        if dq_run.details_json and isinstance(dq_run.details_json, dict):
            return dq_run.details_json.get(metric_type)

        return None

    @staticmethod
    def _get_baseline(
        dq_run: DQRun, metric_type: str, lookback_periods: int
    ) -> dict[str, Any] | None:
        """Get historical baseline for anomaly detection"""
        # Get historical DQ runs
        historical_filter = Q(tenant=dq_run.tenant, status=DQRunStatus.SUCCEEDED)

        if dq_run.asset:
            historical_filter &= Q(asset=dq_run.asset)
        elif dq_run.dataset:
            historical_filter &= Q(dataset=dq_run.dataset)
        else:
            return None

        # Get last N successful runs
        historical_runs = DQRun.objects.filter(
            historical_filter, completed_at__lt=dq_run.completed_at or timezone.now()
        ).order_by("-completed_at")[:lookback_periods]

        if len(historical_runs) < 5:
            # Not enough data
            return None

        # Extract metric values
        values = []
        for run in historical_runs:
            value = AnomalyDetector._get_metric_value(run, metric_type)
            if value is not None:
                values.append(value)

        if len(values) < 5:
            return None

        # Calculate statistics
        mean = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0.0

        # Calculate quartiles for IQR
        sorted_values = sorted(values)
        q1_index = len(sorted_values) // 4
        q3_index = (3 * len(sorted_values)) // 4
        q1 = sorted_values[q1_index] if q1_index < len(sorted_values) else sorted_values[0]
        q3 = sorted_values[q3_index] if q3_index < len(sorted_values) else sorted_values[-1]
        iqr = q3 - q1

        return {
            "mean": mean,
            "std_dev": std_dev,
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "values": values,
            "count": len(values),
        }

    @staticmethod
    def _check_z_score(
        dq_run: DQRun, metric_type: str, metric_value: float, baseline: dict[str, Any]
    ) -> DQAnomaly | None:
        """Check for z-score outlier"""
        mean = baseline["mean"]
        std_dev = baseline["std_dev"]

        if std_dev == 0:
            return None

        z_score = abs((metric_value - mean) / std_dev)

        if z_score > AnomalyDetector.Z_SCORE_THRESHOLD:
            deviation = metric_value - mean
            severity = AnomalyDetector._calculate_severity(z_score)

            return DQAnomaly(
                tenant=dq_run.tenant,
                asset=dq_run.asset,
                dataset=dq_run.dataset,
                dq_run=dq_run,
                metric_type=metric_type,
                expected_value=mean,
                actual_value=metric_value,
                deviation=deviation,
                severity=severity,
                anomaly_type="z_score_outlier",
                description=f"Z-score {z_score:.2f} exceeds threshold {AnomalyDetector.Z_SCORE_THRESHOLD}",
                metadata={"z_score": z_score, "mean": mean, "std_dev": std_dev},
            )

        return None

    @staticmethod
    def _check_iqr(
        dq_run: DQRun, metric_type: str, metric_value: float, baseline: dict[str, Any]
    ) -> DQAnomaly | None:
        """Check for IQR-based outlier"""
        q1 = baseline["q1"]
        q3 = baseline["q3"]
        iqr = baseline["iqr"]

        if iqr == 0:
            return None

        lower_bound = q1 - (AnomalyDetector.IQR_MULTIPLIER * iqr)
        upper_bound = q3 + (AnomalyDetector.IQR_MULTIPLIER * iqr)

        is_outlier = metric_value < lower_bound or metric_value > upper_bound

        if is_outlier:
            deviation = metric_value - baseline["mean"]
            severity = AnomalyDetector._calculate_severity(
                abs(deviation) / baseline["std_dev"] if baseline["std_dev"] > 0 else abs(deviation)
            )

            return DQAnomaly(
                tenant=dq_run.tenant,
                asset=dq_run.asset,
                dataset=dq_run.dataset,
                dq_run=dq_run,
                metric_type=metric_type,
                expected_value=baseline["mean"],
                actual_value=metric_value,
                deviation=deviation,
                severity=severity,
                anomaly_type="iqr_outlier",
                description=f"Value {metric_value} is outside IQR bounds [{lower_bound:.2f}, {upper_bound:.2f}]",
                metadata={
                    "q1": q1,
                    "q3": q3,
                    "iqr": iqr,
                    "lower_bound": lower_bound,
                    "upper_bound": upper_bound,
                },
            )

        return None

    @staticmethod
    def _check_sudden_drop(
        dq_run: DQRun, metric_type: str, metric_value: float, baseline: dict[str, Any]
    ) -> DQAnomaly | None:
        """Check for sudden drop in metric value"""
        mean = baseline["mean"]
        std_dev = baseline["std_dev"]

        # Check if value dropped significantly (more than 2 std devs)
        drop_threshold = mean - (2 * std_dev)

        if metric_value < drop_threshold:
            deviation = metric_value - mean
            drop_percent = ((mean - metric_value) / mean * 100) if mean > 0 else 0

            severity = DQAnomalySeverity.HIGH if drop_percent > 20 else DQAnomalySeverity.MEDIUM

            return DQAnomaly(
                tenant=dq_run.tenant,
                asset=dq_run.asset,
                dataset=dq_run.dataset,
                dq_run=dq_run,
                metric_type=metric_type,
                expected_value=mean,
                actual_value=metric_value,
                deviation=deviation,
                severity=severity,
                anomaly_type="sudden_drop",
                description=f"Sudden drop of {drop_percent:.1f}% from baseline mean {mean:.2f}",
                metadata={"drop_percent": drop_percent, "mean": mean, "std_dev": std_dev},
            )

        return None

    @staticmethod
    def _calculate_severity(z_score: float) -> str:
        """Calculate anomaly severity based on z-score"""
        if z_score >= 4.0:
            return DQAnomalySeverity.CRITICAL
        elif z_score >= 3.5:
            return DQAnomalySeverity.HIGH
        elif z_score >= 3.0:
            return DQAnomalySeverity.MEDIUM
        else:
            return DQAnomalySeverity.LOW

    @staticmethod
    def detect_anomalies_for_asset(
        asset_id: str,
        tenant_id: str,
        metric_type: str = "quality_score",
        lookback_periods: int = 30,
    ) -> list[DQAnomaly]:
        """
        Detect anomalies for all DQ runs of an asset.

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
            metric_type: Type of metric to analyze
            lookback_periods: Number of historical periods

        Returns:
            List of detected anomalies
        """
        # Get latest DQ run
        latest_run = (
            DQRun.objects.filter(
                tenant_id=tenant_id, asset_id=asset_id, status=DQRunStatus.SUCCEEDED
            )
            .order_by("-completed_at")
            .first()
        )

        if not latest_run:
            return []

        return AnomalyDetector.detect_anomalies(
            latest_run, metric_type=metric_type, lookback_periods=lookback_periods
        )

    @staticmethod
    def detect_anomalies_for_dataset(
        dataset_id: str,
        tenant_id: str,
        metric_type: str = "quality_score",
        lookback_periods: int = 30,
    ) -> list[DQAnomaly]:
        """
        Detect anomalies for all DQ runs of a dataset.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant UUID
            metric_type: Type of metric to analyze
            lookback_periods: Number of historical periods

        Returns:
            List of detected anomalies
        """
        # Get latest DQ run
        latest_run = (
            DQRun.objects.filter(
                tenant_id=tenant_id, dataset_id=dataset_id, status=DQRunStatus.SUCCEEDED
            )
            .order_by("-completed_at")
            .first()
        )

        if not latest_run:
            return []

        return AnomalyDetector.detect_anomalies(
            latest_run, metric_type=metric_type, lookback_periods=lookback_periods
        )
