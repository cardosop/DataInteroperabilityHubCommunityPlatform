#!/usr/bin/env python3
"""
Performance Baseline Establishment Script

This script runs performance tests and establishes baselines for comparison.
It supports establishing baselines for load, stress, endurance, and spike tests.

Usage:
    python tests/performance/establish_baseline.py --test-type load
    python tests/performance/establish_baseline.py --test-type stress --users 200
    python tests/performance/establish_baseline.py --test-type endurance --duration 2h
    python tests/performance/establish_baseline.py --test-type spike --spike-users 500
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.performance.performance_baseline_manager import (
    PerformanceBaselineManager,
)


def run_locust_test(test_type: str, **kwargs) -> Path:
    """
    Run Locust test and return path to results.

    Args:
        test_type: Type of test (load, stress, endurance, spike)
        **kwargs: Additional test parameters

    Returns:
        Path to results directory
    """
    api_host = kwargs.get("api_host", "http://localhost:8000")
    users = kwargs.get("users", 50)
    spawn_rate = kwargs.get("spawn_rate", 5)
    duration = kwargs.get("duration", "5m")
    output_dir = kwargs.get("output_dir", "tests/performance/results")

    # Create results directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(output_dir) / f"{test_type}_baseline_{timestamp}"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Determine user class based on test type
    user_class_map = {
        "load": "APIEndpointsAvailabilityUser",
        "stress": "StressTestUser",
        "endurance": "EnduranceTestUser",
        "spike": "SpikeTestUser",
    }

    user_class = user_class_map.get(test_type)
    if not user_class:
        raise ValueError(f"Unknown test type: {test_type}")

    # Run Locust test
    cmd = [
        "locust",
        "-f",
        "tests/performance/locustfile.py",
        user_class,
        "--host",
        api_host,
        "-u",
        str(users),
        "-r",
        str(spawn_rate),
        "-t",
        duration,
        "--headless",
        "--html",
        str(results_dir / f"{test_type}_test.html"),
        "--csv",
        str(results_dir / f"{test_type}_test"),
        "--loglevel",
        "INFO",
    ]

    print(f"Running {test_type} test...")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, check=False, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error running test: {result.stderr}")
        sys.exit(1)

    return results_dir


def parse_locust_results(results_dir: Path) -> dict:
    """
    Parse Locust CSV results and extract metrics.

    Args:
        results_dir: Directory containing Locust results

    Returns:
        Dictionary of metrics
    """
    stats_file = results_dir / "*.csv"
    stats_files = list(results_dir.glob("*_stats.csv"))

    if not stats_files:
        raise FileNotFoundError(f"No stats CSV files found in {results_dir}")

    # Use the main stats file
    stats_file = stats_files[0]

    metrics = {}

    # Parse CSV (simple parsing, could be enhanced)
    with open(stats_file) as f:
        lines = f.readlines()

        # Skip header
        for line in lines[1:]:
            parts = line.strip().split(",")
            if len(parts) >= 8:
                name = parts[0].strip('"')
                if name and name != "Aggregated":
                    try:
                        # Extract key metrics
                        requests = int(float(parts[1]))
                        failures = int(float(parts[2]))
                        median_response_time = float(parts[3])
                        avg_response_time = float(parts[4])
                        min_response_time = float(parts[5])
                        max_response_time = float(parts[6])
                        rps = float(parts[7])

                        # Calculate percentiles (simplified, would need full data)
                        metrics[name] = {
                            "response_times": [
                                min_response_time,
                                median_response_time,
                                avg_response_time,
                                max_response_time,
                            ],
                            "requests": requests,
                            "failures": failures,
                            "rps": rps,
                        }
                    except (ValueError, IndexError):
                        continue

    return metrics


def establish_baseline(test_type: str, **kwargs):
    """
    Establish performance baseline for a test type.

    Args:
        test_type: Type of test (load, stress, endurance, spike)
        **kwargs: Test parameters
    """
    print(f"Establishing {test_type} test baseline...")

    # Run test
    results_dir = run_locust_test(test_type, **kwargs)

    # Parse results
    print("Parsing test results...")
    metrics_data = parse_locust_results(results_dir)

    # Convert to baseline format
    baseline_metrics = {}
    for metric_name, metric_data in metrics_data.items():
        baseline_metrics[f"{metric_name}_response_time"] = metric_data["response_times"]
        baseline_metrics[f"{metric_name}_rps"] = [metric_data["rps"]]

    # Create baseline
    manager = PerformanceBaselineManager()
    baseline = manager.create_baseline(
        test_name=f"{test_type}_test",
        test_type=test_type,
        metrics_data=baseline_metrics,
        environment=kwargs.get("environment", "default"),
        metadata={
            "users": kwargs.get("users", 50),
            "spawn_rate": kwargs.get("spawn_rate", 5),
            "duration": kwargs.get("duration", "5m"),
            "results_dir": str(results_dir),
        },
    )

    # Save baseline
    baseline_path = manager.save_baseline(baseline)
    print(f"Baseline saved to: {baseline_path}")

    return baseline, baseline_path


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Establish performance baseline")
    parser.add_argument(
        "--test-type",
        required=True,
        choices=["load", "stress", "endurance", "spike"],
        help="Type of test to establish baseline for",
    )
    parser.add_argument("--api-host", default="http://localhost:8000", help="API host")
    parser.add_argument("--users", type=int, default=50, help="Number of concurrent users")
    parser.add_argument("--spawn-rate", type=int, default=5, help="Users spawned per second")
    parser.add_argument("--duration", default="5m", help="Test duration")
    parser.add_argument("--environment", default="default", help="Environment name")
    parser.add_argument("--spike-users", type=int, default=500, help="Spike users (for spike test)")

    args = parser.parse_args()

    kwargs = {
        "api_host": args.api_host,
        "users": args.users,
        "spawn_rate": args.spawn_rate,
        "duration": args.duration,
        "environment": args.environment,
    }

    if args.test_type == "spike":
        kwargs["spike_users"] = args.spike_users

    try:
        baseline, baseline_path = establish_baseline(args.test_type, **kwargs)
        print("\n✅ Baseline established successfully!")
        print(f"   Test Type: {args.test_type}")
        print(f"   Baseline File: {baseline_path}")
        print(f"   Metrics: {len(baseline.metrics)}")
        return 0
    except Exception as e:
        print(f"\n❌ Error establishing baseline: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
