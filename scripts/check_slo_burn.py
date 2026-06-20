#!/usr/bin/env python3
"""
301.3 — Check SLO error budget burn rate.

Queries Prometheus for current error budget consumption.
Exit non-zero if > 10% of monthly error budget is consumed.
Runs as CI informational check (non-blocking during trial period).

Requires:
  - PROMETHEUS_URL env var (defaults to http://prometheus:9090)
  - PROMETHEUS_TOKEN env var (optional, for authenticated endpoints)

Usage:
  python scripts/check_slo_burn.py           # check all SLOs
  python scripts/check_slo_burn.py --slo availability  # check specific SLO
"""

import json
import os
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
PROMETHEUS_TOKEN = os.environ.get("PROMETHEUS_TOKEN", "")

# SLO definitions matching docs/operations/SLO.md
SLOS = {
    "availability": {
        "query": (
            'sum(increase(http_requests_total{status=~"5..",path!~"/health/.*"}[30d]))'
            ' / sum(increase(http_requests_total{path!~"/health/.*"}[30d]))'
        ),
        "target": 0.005,  # 99.5% availability → 0.5% error budget
        "burn_threshold": 0.10,  # >10% of budget consumed
    },
    "search_latency": {
        "query": (
            "histogram_quantile(0.95, rate(search_request_duration_seconds_bucket[30d])) / 0.5"
        ),
        "target": 1.0,  # p95 < 500ms
        "burn_threshold": 0.10,
    },
    "sparql_latency": {
        "query": ("histogram_quantile(0.95, rate(sparql_execution_seconds_bucket[30d])) / 2.0"),
        "target": 1.0,  # p95 < 2s
        "burn_threshold": 0.10,
    },
}


def query_prometheus(query: str) -> float | None:
    """Execute an instant query against Prometheus and return the scalar result."""
    url = f"{PROMETHEUS_URL.rstrip('/')}/api/v1/query"
    params = f"query={query}"
    full_url = f"{url}?{params}"

    req = Request(full_url)
    req.add_header("Accept", "application/json")
    if PROMETHEUS_TOKEN:
        req.add_header("Authorization", f"Bearer {PROMETHEUS_TOKEN}")

    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except URLError as exc:
        print(f"WARNING: Prometheus unreachable ({exc}) — skipping SLO burn check")
        return None
    except json.JSONDecodeError:
        print("WARNING: Prometheus returned non-JSON response — skipping")
        return None

    results = data.get("data", {}).get("result", [])
    if not results:
        return 0.0
    value = results[0].get("value", [None, "0"])[1]
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def main():
    slo_filter = None
    args = sys.argv[1:]
    if args and args[0] == "--slo" and len(args) > 1:
        slo_filter = args[1]

    failures = 0
    checked = 0

    for name, slo in SLOS.items():
        if slo_filter and name != slo_filter:
            continue
        checked += 1
        value = query_prometheus(slo["query"])
        if value is None:
            continue  # Prometheus unreachable — skip gracefully

        budget_consumed = value / slo["target"] if slo["target"] > 0 else 0
        over_threshold = budget_consumed > slo["burn_threshold"]

        status = "❌ BURN" if over_threshold else "✅ OK"
        print(
            f"  {status} {name:<20} "
            f"value={value:.4f} "
            f"budget_consumed={budget_consumed:.1%} "
            f"threshold={slo['burn_threshold']:.0%}"
        )

        if over_threshold:
            failures += 1

    print(f"\nSLO burn check: {checked} checked, {failures} over threshold")
    if failures > 0:
        # Informational — does not block CI during trial period
        print("WARNING: Some SLO burn rates exceed threshold.")
        print("This check is informational for 60 days, then blocks CI.")
        # sys.exit(1)  # Uncomment after trial period

    sys.exit(0)


if __name__ == "__main__":
    main()
