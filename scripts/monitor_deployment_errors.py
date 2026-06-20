#!/usr/bin/env python3
"""
Deployment Error Monitoring Script

This script monitors for errors after deployment, checking:
- Application logs for errors
- Metrics endpoint for errors
- Service health
- Performance degradation

Usage:
    python scripts/monitor_deployment_errors.py [--url URL] [--duration SECONDS] [--log-file PATH]

Example:
    python scripts/monitor_deployment_errors.py --url http://localhost:8000 --duration 300
    python scripts/monitor_deployment_errors.py --url http://staging.example.com --log-file /var/log/app.log
"""

import argparse
import json
import sys
import time
from datetime import datetime

import requests


def check_health_endpoint(api_url: str, timeout: int = 10) -> tuple[bool, str]:
    """Check API health endpoint."""
    try:
        response = requests.get(f"{api_url}/health/", timeout=timeout)
        if response.status_code == 200:
            return True, "Health endpoint healthy"
        else:
            return False, f"Health endpoint returned HTTP {response.status_code}"
    except Exception as e:
        return False, f"Health endpoint error: {e!s}"


def check_metrics_endpoint(api_url: str, timeout: int = 10) -> tuple[bool, str, dict | None]:
    """Check metrics endpoint and extract error metrics."""
    try:
        response = requests.get(f"{api_url}/metrics/", timeout=timeout)
        if response.status_code == 200:
            content = response.text

            # Check for error metrics
            error_count = 0
            error_details = {}

            # Look for http_errors_total metric
            for line in content.split("\n"):
                if "http_errors_total" in line and not line.startswith("#"):
                    # Parse metric line: metric_name{labels} value
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            value = float(parts[-1])
                            if value > 0:
                                error_count += int(value)
                                error_details["http_errors"] = value
                        except ValueError:
                            pass

            if error_count > 0:
                return False, f"Found {error_count} HTTP errors in metrics", error_details
            else:
                return True, "No errors in metrics", None
        else:
            return False, f"Metrics endpoint returned HTTP {response.status_code}", None
    except Exception as e:
        return False, f"Metrics endpoint error: {e!s}", None


def check_performance_metrics(api_url: str, timeout: int = 10) -> tuple[bool, str, dict | None]:
    """Check performance metrics for degradation."""
    try:
        response = requests.get(f"{api_url}/metrics/", timeout=timeout)
        if response.status_code == 200:
            content = response.text

            performance_issues = []
            performance_data = {}

            # Check for high latency in http_request_duration_seconds
            for line in content.split("\n"):
                if "http_request_duration_seconds_bucket" in line and 'le="1.0"' in line:
                    # Check P95 bucket (le="1.0" is roughly P95 for most requests)
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            value = float(parts[-1])
                            if value > 100:  # More than 100 requests > 1s
                                performance_issues.append(
                                    f"High latency detected: {value} requests > 1s"
                                )
                                performance_data["high_latency_count"] = value
                        except ValueError:
                            pass

            if performance_issues:
                return False, "; ".join(performance_issues), performance_data
            else:
                return True, "Performance metrics normal", None
        else:
            return (
                False,
                f"Cannot check performance (metrics endpoint HTTP {response.status_code})",
                None,
            )
    except Exception as e:
        return False, f"Performance check error: {e!s}", None


def monitor_logs(log_file: str | None, duration: int) -> tuple[bool, list[str]]:
    """Monitor application logs for errors."""
    if not log_file:
        return True, []  # Skip if no log file provided

    errors = []
    try:
        # Read last N lines of log file
        # This is a simplified version - in production, use proper log tailing
        with open(log_file) as f:
            lines = f.readlines()
            # Check last 100 lines for errors
            for line in lines[-100:]:
                if any(
                    keyword in line.lower()
                    for keyword in ["error", "exception", "traceback", "failed"]
                ):
                    # Check if it's a recent error (within monitoring duration)
                    # Simplified - in production, parse timestamps properly
                    errors.append(line.strip())
    except FileNotFoundError:
        return False, [f"Log file not found: {log_file}"]
    except Exception as e:
        return False, [f"Error reading log file: {e!s}"]

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description="Monitor deployment for errors")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="API service URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--duration", type=int, default=300, help="Monitoring duration in seconds (default: 300)"
    )
    parser.add_argument(
        "--interval", type=int, default=30, help="Check interval in seconds (default: 30)"
    )
    parser.add_argument("--log-file", default=None, help="Path to application log file (optional)")
    parser.add_argument(
        "--prometheus-url", default=None, help="Prometheus URL for advanced monitoring (optional)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Deployment Error Monitoring")
    print("=" * 60)
    print(f"API URL: {args.url}")
    print(f"Duration: {args.duration} seconds")
    print(f"Check Interval: {args.interval} seconds")
    if args.log_file:
        print(f"Log File: {args.log_file}")
    print()

    start_time = time.time()
    end_time = start_time + args.duration
    check_count = 0
    error_count = 0

    all_errors = []

    try:
        while time.time() < end_time:
            check_count += 1
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] Check #{check_count}")

            # 1. Check health
            success, message = check_health_endpoint(args.url)
            if success:
                print(f"  ✓ Health: {message}")
            else:
                print(f"  ✗ Health: {message}")
                error_count += 1
                all_errors.append(f"Health check failed: {message}")

            # 2. Check metrics for errors
            success, message, details = check_metrics_endpoint(args.url)
            if success:
                print(f"  ✓ Metrics: {message}")
            else:
                print(f"  ✗ Metrics: {message}")
                if details:
                    print(f"    Details: {json.dumps(details, indent=2)}")
                error_count += 1
                all_errors.append(f"Metrics check failed: {message}")

            # 3. Check performance
            success, message, details = check_performance_metrics(args.url)
            if success:
                print(f"  ✓ Performance: {message}")
            else:
                print(f"  ✗ Performance: {message}")
                if details:
                    print(f"    Details: {json.dumps(details, indent=2)}")
                error_count += 1
                all_errors.append(f"Performance check failed: {message}")

            # 4. Check logs (if log file provided)
            if args.log_file:
                success, log_errors = monitor_logs(args.log_file, args.duration)
                if success:
                    print("  ✓ Logs: No errors found")
                else:
                    print(f"  ✗ Logs: Found {len(log_errors)} errors")
                    for error in log_errors[:3]:  # Show first 3
                        print(f"    - {error}")
                    error_count += 1
                    all_errors.extend(log_errors)

            print()

            # Wait for next check
            if time.time() < end_time:
                time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nMonitoring interrupted by user")

    print("=" * 60)
    print("Monitoring Summary")
    print(f"  Total Checks: {check_count}")
    print(f"  Errors Found: {error_count}")
    print(f"  Duration: {time.time() - start_time:.1f} seconds")
    print()

    if error_count > 0:
        print("Errors Detected:")
        for i, error in enumerate(all_errors[:10], 1):  # Show first 10
            print(f"  {i}. {error}")
        if len(all_errors) > 10:
            print(f"  ... and {len(all_errors) - 10} more errors")
        return 1
    else:
        print("✓ No errors detected during monitoring period")
        return 0


if __name__ == "__main__":
    sys.exit(main())
