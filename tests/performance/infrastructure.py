"""
Performance Test Infrastructure

Infrastructure for performance testing including load generators,
baseline metrics collection, and performance regression detection.
"""

import json
import os
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PerformanceMetric:
    """Performance metric data structure"""

    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceBaseline:
    """Performance baseline data structure"""

    metric_name: str
    mean: float
    median: float
    min: float
    max: float
    stdev: float
    p95: float
    p99: float
    sample_count: int
    created_at: datetime = field(default_factory=datetime.now)


class PerformanceCollector:
    """Collects performance metrics during test execution"""

    def __init__(self):
        self.metrics: list[PerformanceMetric] = []

    def record_metric(
        self, name: str, value: float, unit: str = "seconds", metadata: dict[str, Any] | None = None
    ):
        """
        Record a performance metric.

        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            metadata: Additional metadata
        """
        self.metrics.append(
            PerformanceMetric(name=name, value=value, unit=unit, metadata=metadata or {})
        )

    def measure_time(self, func: Callable, metric_name: str | None = None, *args, **kwargs) -> Any:
        """
        Measure execution time of a function.

        Args:
            func: Function to measure
            metric_name: Name for the metric (default: function name)
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        if metric_name is None:
            metric_name = f"{func.__name__}_execution_time"

        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start

        self.record_metric(metric_name, elapsed, "seconds")
        return result

    def get_metrics_by_name(self, name: str) -> list[PerformanceMetric]:
        """
        Get all metrics with a specific name.

        Args:
            name: Metric name

        Returns:
            List of metrics
        """
        return [m for m in self.metrics if m.name == name]

    def calculate_baseline(self, metric_name: str) -> PerformanceBaseline | None:
        """
        Calculate baseline statistics for a metric.

        Args:
            metric_name: Metric name

        Returns:
            PerformanceBaseline or None if no metrics found
        """
        metrics = self.get_metrics_by_name(metric_name)
        if not metrics:
            return None

        values = [m.value for m in metrics]
        sorted_values = sorted(values)

        return PerformanceBaseline(
            metric_name=metric_name,
            mean=statistics.mean(values),
            median=statistics.median(values),
            min=min(values),
            max=max(values),
            stdev=statistics.stdev(values) if len(values) > 1 else 0.0,
            p95=sorted_values[int(len(sorted_values) * 0.95)] if sorted_values else 0.0,
            p99=sorted_values[int(len(sorted_values) * 0.99)] if sorted_values else 0.0,
            sample_count=len(values),
        )

    def export_metrics(self, filepath: str):
        """
        Export metrics to JSON file.

        Args:
            filepath: Path to output file
        """
        data = {
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "unit": m.unit,
                    "timestamp": m.timestamp.isoformat(),
                    "metadata": m.metadata,
                }
                for m in self.metrics
            ]
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def export_baselines(self, filepath: str):
        """
        Export baselines to JSON file.

        Args:
            filepath: Path to output file
        """
        metric_names = set(m.name for m in self.metrics)
        baselines = {}

        for name in metric_names:
            baseline = self.calculate_baseline(name)
            if baseline:
                baselines[name] = {
                    "mean": baseline.mean,
                    "median": baseline.median,
                    "min": baseline.min,
                    "max": baseline.max,
                    "stdev": baseline.stdev,
                    "p95": baseline.p95,
                    "p99": baseline.p99,
                    "sample_count": baseline.sample_count,
                    "created_at": baseline.created_at.isoformat(),
                }

        with open(filepath, "w") as f:
            json.dump(baselines, f, indent=2)


class LoadGenerator:
    """Generates load for performance testing"""

    def __init__(self, collector: PerformanceCollector):
        self.collector = collector

    def run_concurrent_requests(
        self, func: Callable, num_requests: int, metric_name: str | None = None, *args, **kwargs
    ) -> list[Any]:
        """
        Run concurrent requests and measure performance.

        Args:
            func: Function to execute
            num_requests: Number of concurrent requests
            metric_name: Name for the metric
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            List of function results
        """
        import concurrent.futures

        if metric_name is None:
            metric_name = f"{func.__name__}_concurrent_{num_requests}"

        start = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [executor.submit(func, *args, **kwargs) for _ in range(num_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        elapsed = time.time() - start

        self.collector.record_metric(
            metric_name,
            elapsed,
            "seconds",
            metadata={"num_requests": num_requests, "concurrent": True},
        )

        return results


class PerformanceRegressionDetector:
    """Detects performance regressions by comparing against baselines"""

    def __init__(self, baseline_file: str):
        """
        Initialize regression detector with baseline file.

        Args:
            baseline_file: Path to baseline JSON file
        """
        self.baseline_file = baseline_file
        self.baselines: dict[str, PerformanceBaseline] = {}
        self.load_baselines()

    def load_baselines(self):
        """Load baselines from file"""
        if not os.path.exists(self.baseline_file):
            return

        with open(self.baseline_file) as f:
            data = json.load(f)

        for name, baseline_data in data.items():
            self.baselines[name] = PerformanceBaseline(
                metric_name=name,
                mean=baseline_data["mean"],
                median=baseline_data["median"],
                min=baseline_data["min"],
                max=baseline_data["max"],
                stdev=baseline_data["stdev"],
                p95=baseline_data["p95"],
                p99=baseline_data["p99"],
                sample_count=baseline_data["sample_count"],
                created_at=datetime.fromisoformat(baseline_data["created_at"]),
            )

    def check_regression(
        self, metric_name: str, current_value: float, threshold_percent: float = 20.0
    ) -> tuple[bool, str | None]:
        """
        Check if a metric has regressed.

        Args:
            metric_name: Metric name
            current_value: Current metric value
            threshold_percent: Regression threshold percentage (default: 20%)

        Returns:
            Tuple of (is_regression: bool, message: Optional[str])
        """
        if metric_name not in self.baselines:
            return False, None

        baseline = self.baselines[metric_name]
        threshold = baseline.mean * (1 + threshold_percent / 100)

        if current_value > threshold:
            regression_percent = ((current_value - baseline.mean) / baseline.mean) * 100
            message = (
                f"Performance regression detected for {metric_name}: "
                f"{current_value:.3f}s (baseline: {baseline.mean:.3f}s, "
                f"{regression_percent:.1f}% slower)"
            )
            return True, message

        return False, None
