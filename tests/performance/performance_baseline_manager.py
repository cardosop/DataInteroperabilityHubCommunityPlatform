"""
Performance Baseline Manager

Comprehensive system for establishing, storing, comparing, and tracking
performance baselines across different test types and scenarios.

Features:
- Baseline establishment from test results
- Baseline comparison and regression detection
- Baseline versioning and history
- Export/import for CI/CD integration
- Statistical analysis and reporting
"""

import json
import os
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class BaselineMetric:
    """Individual metric in a performance baseline."""

    name: str
    mean: float
    median: float
    min: float
    max: float
    stdev: float
    p50: float
    p95: float
    p99: float
    sample_count: int
    unit: str = "ms"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceBaseline:
    """Complete performance baseline for a test scenario."""

    test_name: str
    test_type: str  # load, stress, endurance, spike
    version: str
    created_at: datetime
    environment: str
    metrics: List[BaselineMetric]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerformanceBaseline":
        """Create from dictionary."""
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        metrics = [BaselineMetric(**m) for m in data["metrics"]]
        data["metrics"] = metrics
        return cls(**data)


class PerformanceBaselineManager:
    """Manages performance baselines."""

    def __init__(self, baseline_dir: Optional[Path] = None):
        """
        Initialize baseline manager.

        Args:
            baseline_dir: Directory to store baselines (default: tests/performance/baselines)
        """
        if baseline_dir is None:
            baseline_dir = Path(__file__).parent / "baselines"
        self.baseline_dir = Path(baseline_dir)
        self.baseline_dir.mkdir(parents=True, exist_ok=True)

    def calculate_metrics(self, values: List[float]) -> BaselineMetric:
        """
        Calculate statistical metrics from a list of values.

        Args:
            values: List of measured values

        Returns:
            BaselineMetric with calculated statistics
        """
        if not values:
            raise ValueError("Cannot calculate metrics from empty list")

        sorted_values = sorted(values)
        n = len(sorted_values)

        return BaselineMetric(
            name="",  # Will be set by caller
            mean=statistics.mean(values),
            median=statistics.median(values),
            min=min(values),
            max=max(values),
            stdev=statistics.stdev(values) if n > 1 else 0.0,
            p50=sorted_values[int(n * 0.50)] if n > 0 else 0.0,
            p95=sorted_values[int(n * 0.95)] if n > 1 else sorted_values[-1],
            p99=sorted_values[int(n * 0.99)] if n > 1 else sorted_values[-1],
            sample_count=n,
        )

    def create_baseline(
        self,
        test_name: str,
        test_type: str,
        metrics_data: Dict[str, List[float]],
        version: Optional[str] = None,
        environment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PerformanceBaseline:
        """
        Create a performance baseline from test results.

        Args:
            test_name: Name of the test
            test_type: Type of test (load, stress, endurance, spike)
            metrics_data: Dictionary mapping metric names to lists of values
            version: Version identifier (default: timestamp)
            environment: Environment name (default: from env var or 'default')
            metadata: Additional metadata

        Returns:
            PerformanceBaseline object
        """
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")

        if environment is None:
            environment = os.getenv("PERF_TEST_ENV", "default")

        metrics = []
        for metric_name, values in metrics_data.items():
            metric = self.calculate_metrics(values)
            metric.name = metric_name
            metrics.append(metric)

        baseline = PerformanceBaseline(
            test_name=test_name,
            test_type=test_type,
            version=version,
            created_at=datetime.now(),
            environment=environment,
            metrics=metrics,
            metadata=metadata or {},
        )

        return baseline

    def save_baseline(self, baseline: PerformanceBaseline) -> Path:
        """
        Save baseline to file.

        Args:
            baseline: Baseline to save

        Returns:
            Path to saved file
        """
        filename = f"{baseline.test_name}_{baseline.test_type}_{baseline.version}.json"
        filepath = self.baseline_dir / filename

        with open(filepath, "w") as f:
            json.dump(baseline.to_dict(), f, indent=2)

        return filepath

    def load_baseline(self, filepath: Path) -> PerformanceBaseline:
        """
        Load baseline from file.

        Args:
            filepath: Path to baseline file

        Returns:
            PerformanceBaseline object
        """
        with open(filepath, "r") as f:
            data = json.load(f)

        return PerformanceBaseline.from_dict(data)

    def find_baseline(
        self,
        test_name: str,
        test_type: Optional[str] = None,
        version: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> Optional[PerformanceBaseline]:
        """
        Find baseline matching criteria.

        Args:
            test_name: Test name
            test_type: Test type (optional)
            version: Version (optional, defaults to latest)
            environment: Environment (optional)

        Returns:
            Baseline if found, None otherwise
        """
        pattern = f"{test_name}_*.json"
        if test_type:
            pattern = f"{test_name}_{test_type}_*.json"

        matches = list(self.baseline_dir.glob(pattern))

        if not matches:
            return None

        # Load all matching baselines
        baselines = []
        for match in matches:
            try:
                baseline = self.load_baseline(match)
                if environment and baseline.environment != environment:
                    continue
                baselines.append(baseline)
            except Exception:
                continue

        if not baselines:
            return None

        # Sort by created_at (newest first)
        baselines.sort(key=lambda b: b.created_at, reverse=True)

        # Return specified version or latest
        if version:
            for baseline in baselines:
                if baseline.version == version:
                    return baseline
            return None

        return baselines[0]  # Latest

    def compare_baselines(
        self,
        baseline1: PerformanceBaseline,
        baseline2: PerformanceBaseline,
        regression_threshold: float = 0.10,  # 10% regression threshold
    ) -> Dict[str, Any]:
        """
        Compare two baselines and detect regressions.

        Args:
            baseline1: Reference baseline (typically older)
            baseline2: Current baseline (typically newer)
            regression_threshold: Percentage threshold for regression detection

        Returns:
            Comparison report dictionary
        """
        comparison = {
            "baseline1": {
                "test_name": baseline1.test_name,
                "version": baseline1.version,
                "created_at": baseline1.created_at.isoformat(),
            },
            "baseline2": {
                "test_name": baseline2.test_name,
                "version": baseline2.version,
                "created_at": baseline2.created_at.isoformat(),
            },
            "metrics": [],
            "summary": {
                "total_metrics": 0,
                "improved": 0,
                "regressed": 0,
                "unchanged": 0,
            },
        }

        # Create metric lookup
        metrics1 = {m.name: m for m in baseline1.metrics}
        metrics2 = {m.name: m for m in baseline2.metrics}

        # Compare common metrics
        common_metrics = set(metrics1.keys()) & set(metrics2.keys())

        for metric_name in common_metrics:
            m1 = metrics1[metric_name]
            m2 = metrics2[metric_name]

            # Compare p95 (most important metric)
            p95_change = ((m2.p95 - m1.p95) / m1.p95) * 100 if m1.p95 > 0 else 0
            mean_change = ((m2.mean - m1.mean) / m1.mean) * 100 if m1.mean > 0 else 0

            status = "unchanged"
            if abs(p95_change) < 5:  # Less than 5% change
                status = "unchanged"
            elif p95_change > regression_threshold * 100:  # Regression
                status = "regressed"
            elif p95_change < -5:  # Improvement
                status = "improved"

            metric_comparison = {
                "name": metric_name,
                "baseline1_p95": m1.p95,
                "baseline2_p95": m2.p95,
                "p95_change_percent": p95_change,
                "baseline1_mean": m1.mean,
                "baseline2_mean": m2.mean,
                "mean_change_percent": mean_change,
                "status": status,
            }

            comparison["metrics"].append(metric_comparison)

            # Update summary
            comparison["summary"]["total_metrics"] += 1
            if status == "improved":
                comparison["summary"]["improved"] += 1
            elif status == "regressed":
                comparison["summary"]["regressed"] += 1
            else:
                comparison["summary"]["unchanged"] += 1

        return comparison

    def export_comparison_report(self, comparison: Dict[str, Any], output_path: Path) -> Path:
        """
        Export comparison report to JSON file.

        Args:
            comparison: Comparison dictionary
            output_path: Output file path

        Returns:
            Path to exported file
        """
        with open(output_path, "w") as f:
            json.dump(comparison, f, indent=2)

        return output_path
