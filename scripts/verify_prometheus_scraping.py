#!/usr/bin/env python3
"""
Prometheus Scraping Verification Script

This script verifies that Prometheus can successfully scrape metrics from
the API service after OpenTelemetry metrics migration.

Usage:
    python scripts/verify_prometheus_scraping.py [--url URL] [--prometheus-url URL]

Example:
    python scripts/verify_prometheus_scraping.py --url http://localhost:8000
    python scripts/verify_prometheus_scraping.py --url http://staging.example.com --prometheus-url http://prometheus:9090
"""

import argparse
import sys
import time

import requests


def check_metrics_endpoint(api_url: str, timeout: int = 30) -> tuple[bool, str, str | None]:
    """
    Check if metrics endpoint is accessible and returns valid Prometheus format.

    Returns:
        (success, message, metrics_content)
    """
    try:
        response = requests.get(f"{api_url}/metrics/", timeout=timeout)

        if response.status_code == 200:
            content = response.text
            content_type = response.headers.get("Content-Type", "")

            # Verify Content-Type
            if "text/plain" not in content_type:
                return False, f"Invalid Content-Type: {content_type}", None

            # Verify Prometheus format indicators
            if "# HELP" not in content:
                return False, "Missing # HELP comments", None

            if "# TYPE" not in content:
                return False, "Missing # TYPE comments", None

            # Verify metric lines exist
            metric_lines = [
                line for line in content.split("\n") if line and not line.startswith("#")
            ]
            if len(metric_lines) == 0:
                return False, "No metric lines found", None

            return True, "Metrics endpoint accessible and valid", content

        elif response.status_code == 503:
            return False, "Metrics endpoint returned 503 (service unavailable)", None
        else:
            return False, f"Metrics endpoint returned HTTP {response.status_code}", None

    except requests.exceptions.Timeout:
        return False, f"Metrics endpoint timeout after {timeout}s", None
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to metrics endpoint", None
    except Exception as e:
        return False, f"Error checking metrics endpoint: {e!s}", None


def verify_metric_names(
    metrics_content: str, required_metrics: list[str]
) -> tuple[bool, list[str]]:
    """
    Verify that required metric names are present in the metrics output.

    Returns:
        (all_present, missing_metrics)
    """
    missing = []
    for metric in required_metrics:
        if metric not in metrics_content:
            missing.append(metric)

    return len(missing) == 0, missing


def verify_prometheus_scraping(
    prometheus_url: str, api_url: str, timeout: int = 60
) -> tuple[bool, str]:
    """
    Verify that Prometheus can scrape metrics from the API service.

    This checks if Prometheus has successfully scraped the metrics endpoint.
    """
    try:
        # Check if Prometheus is accessible
        health_response = requests.get(f"{prometheus_url}/-/healthy", timeout=10)
        if health_response.status_code != 200:
            return False, f"Prometheus health check failed: HTTP {health_response.status_code}"

        # Query Prometheus for a metric we know should exist
        # Wait a bit for Prometheus to scrape
        time.sleep(5)

        # Query for http_requests_total metric
        query_url = f"{prometheus_url}/api/v1/query"
        params = {"query": "http_requests_total"}

        response = requests.get(query_url, params=params, timeout=timeout)

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                result = data.get("data", {}).get("result", [])
                if len(result) > 0:
                    return (
                        True,
                        f"Prometheus successfully scraped metrics ({len(result)} series found)",
                    )
                else:
                    return False, "Prometheus scraped but no metrics found (may need more time)"
            else:
                return False, f"Prometheus query failed: {data.get('error', 'Unknown error')}"
        else:
            return False, f"Prometheus API returned HTTP {response.status_code}"

    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Prometheus"
    except Exception as e:
        return False, f"Error checking Prometheus: {e!s}"


def verify_metric_format(metrics_content: str) -> tuple[bool, list[str]]:
    """
    Verify that metrics follow Prometheus format rules.

    Returns:
        (valid, errors)
    """
    errors = []
    lines = metrics_content.split("\n")

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Check for valid metric format: name{labels} value
        # More lenient check - just verify it has a name and value
        parts = line.split()
        if len(parts) < 2:
            errors.append(f"Line {i}: Invalid format (missing value): {line}")
            continue

        metric_part = parts[0]
        # Check metric name format
        if not metric_part[0].isalpha() and metric_part[0] != "_":
            errors.append(f"Line {i}: Invalid metric name format: {metric_part}")

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(
        description="Verify Prometheus scraping of OpenTelemetry metrics"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="API service URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--prometheus-url",
        default=None,
        help="Prometheus URL (optional, for scraping verification)",
    )
    parser.add_argument(
        "--timeout", type=int, default=30, help="Request timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--required-metrics",
        nargs="+",
        default=["http_requests_total", "http_request_duration_seconds", "jobs_started_total"],
        help="Required metric names to check",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Prometheus Scraping Verification")
    print("=" * 60)
    print(f"API URL: {args.url}")
    if args.prometheus_url:
        print(f"Prometheus URL: {args.prometheus_url}")
    print()

    all_checks_passed = True

    # 1. Check metrics endpoint
    print("1. Checking metrics endpoint...")
    success, message, metrics_content = check_metrics_endpoint(args.url, args.timeout)
    if success:
        print(f"   ✓ {message}")
    else:
        print(f"   ✗ {message}")
        all_checks_passed = False
    print()

    if metrics_content:
        # 2. Verify metric names
        print("2. Verifying required metric names...")
        all_present, missing = verify_metric_names(metrics_content, args.required_metrics)
        if all_present:
            print("   ✓ All required metrics present")
        else:
            print(f"   ✗ Missing metrics: {', '.join(missing)}")
            all_checks_passed = False
        print()

        # 3. Verify metric format
        print("3. Verifying metric format...")
        valid, errors = verify_metric_format(metrics_content)
        if valid:
            print("   ✓ Metric format valid")
        else:
            print("   ✗ Format errors found:")
            for error in errors[:5]:  # Show first 5 errors
                print(f"     - {error}")
            if len(errors) > 5:
                print(f"     ... and {len(errors) - 5} more errors")
            all_checks_passed = False
        print()

        # 4. Verify Prometheus scraping (if Prometheus URL provided)
        if args.prometheus_url:
            print("4. Verifying Prometheus scraping...")
            success, message = verify_prometheus_scraping(
                args.prometheus_url, args.url, args.timeout
            )
            if success:
                print(f"   ✓ {message}")
            else:
                print(f"   ✗ {message}")
                all_checks_passed = False
            print()

    print("=" * 60)
    if all_checks_passed:
        print("✓ All verification checks passed")
        return 0
    else:
        print("✗ Some verification checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
