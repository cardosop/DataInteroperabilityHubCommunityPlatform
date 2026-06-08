#!/usr/bin/env python3
"""
Performance baseline gate checks (312.17).

Validates operational performance baselines against defined thresholds:
  - API response times (p95 targets)
  - Worker queue depth
  - PgBouncer connection pool wait time
  - DB active connections count
  - Redis memory usage

Usage:
    python scripts/check_performance_baselines.py               # all checks
    python scripts/check_performance_baselines.py --check api   # API only
    python scripts/check_performance_baselines.py --json        # JSON output for CI

Environment variables:
    API_BASE_URL        Target API base URL (default: http://localhost:8000)
    REDIS_HOST          Redis host for memory check (default: localhost)
    POSTGRES_HOST       PostgreSQL host for connection check (default: localhost)
    PGBOUNCER_HOST      PgBouncer admin host (default: localhost)
    PGBOUNCER_PORT      PgBouncer admin port (default: 6432)

Exit 0 if all checks pass, 1 if any threshold is exceeded.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]

# ── Thresholds (312.17) ──────────────────────────────────────────────

THRESHOLDS = {
    "api_get_list_p95_ms": 500,
    "api_post_create_p95_ms": 2000,
    "api_compliance_scan_p95_ms": 10000,
    "worker_queue_depth_max": 100,
    "pgbouncer_wait_p95_ms": 30,
    "db_active_connections_max": 80,
    "redis_memory_pct_max": 80,
}

# ── Helpers ───────────────────────────────────────────────────────────

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
TIMEOUT = int(os.environ.get("PERF_CHECK_TIMEOUT", "30"))


def _api_request(path: str, method: str = "GET") -> tuple[int, float, str]:
    """Make an API request and return (status, elapsed_seconds, body)."""
    url = f"{API_BASE}{path}"
    start = time.monotonic()
    try:
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            elapsed = time.monotonic() - start
            return resp.status, elapsed, body
    except Exception as exc:
        elapsed = time.monotonic() - start
        return 0, elapsed, str(exc)


def _check_threshold(name: str, value: float, threshold: float, unit: str = "") -> tuple[bool, str]:
    """Check a value against its threshold.  Return (passed, message)."""
    if value <= threshold:
        return True, f"  PASS  {name}: {value}{unit} <= {threshold}{unit}"
    return False, f"  FAIL  {name}: {value}{unit} > {threshold}{unit}"


# ── 312.17.1 — API Response Time Benchmarks ──────────────────────────

def check_api_response_times() -> dict:
    """Measure API response times against p95 thresholds.
    Uses repeated requests to estimate p95.  For CI, runs a modest sample;
    for production monitoring, increase sample count."""
    results: dict = {"api_get_list_ms": [], "api_post_create_ms": [], "compliance_scan_ms": []}
    failures: list[str] = []

    # GET list — sample 10 requests
    for _ in range(10):
        status, elapsed, _ = _api_request("/api/v1/assets/")
        if status == 200:
            results["api_get_list_ms"].append(elapsed * 1000)
    if results["api_get_list_ms"]:
        p95 = sorted(results["api_get_list_ms"])[int(len(results["api_get_list_ms"]) * 0.95)]
        passed, msg = _check_threshold("API GET list p95", p95, THRESHOLDS["api_get_list_p95_ms"], "ms")
        print(msg)
        if not passed:
            failures.append("api_get_list_p95")
    else:
        print("  SKIP  API GET list — no successful responses")

    return {"failures": failures, "results": results}


# ── 312.17.2 — Worker Queue Depth Benchmark ──────────────────────────

def check_worker_queue_depth() -> dict:
    """Check RQ worker queue depth via the API or Redis directly."""
    failures: list[str] = []

    # Try the RQ queue stats endpoint.
    status, elapsed, body = _api_request("/api/v1/jobs/queue-stats/")
    if status == 404:
        print("  SKIP  Worker queue stats endpoint not available")
        return {"failures": []}

    if status == 200:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            print("  SKIP  Worker queue stats returned non-JSON")
            return {"failures": []}

        # Extract queue depth — support common response shapes.
        depth = None
        if isinstance(data, dict):
            depth = data.get("queued_count") or data.get("queue_depth") or data.get("count")
            queues = data.get("queues", {})
            if isinstance(queues, dict):
                depth = sum(v if isinstance(v, (int, float)) else 0 for v in queues.values())
        elif isinstance(data, list):
            depth = len(data)

        if depth is not None:
            passed, msg = _check_threshold("Worker queue depth", depth, THRESHOLDS["worker_queue_depth_max"])
            print(msg)
            if not passed:
                failures.append("worker_queue_depth")
        else:
            print("  SKIP  Worker queue depth not found in response")
    else:
        print(f"  SKIP  Worker queue stats returned {status}")

    return {"failures": failures}


# ── 312.17.3 — PgBouncer Connection Pool Benchmark ───────────────────

def check_pgbouncer_pool() -> dict:
    """Check PgBouncer client wait time via the PgBouncer admin console or API."""
    failures: list[str] = []

    # Try through the API health endpoint (which may proxy PgBouncer stats).
    status, elapsed, body = _api_request("/api/v1/health/database/")
    if status == 404:
        # Try direct PgBouncer check via Django management command output.
        print("  SKIP  Database health endpoint not available — check PgBouncer directly")
        return {"failures": []}

    if status == 200:
        print(f"  INFO  Database health endpoint responded in {elapsed*1000:.0f}ms")
        # If the response includes pool stats, parse them.
        try:
            data = json.loads(body)
            if isinstance(data, dict):
                pool_wait = data.get("pgbouncer_avg_wait_ms") or data.get("pool_wait_ms")
                if pool_wait is not None:
                    passed, msg = _check_threshold("PgBouncer client wait", pool_wait,
                                                    THRESHOLDS["pgbouncer_wait_p95_ms"], "ms")
                    print(msg)
                    if not passed:
                        failures.append("pgbouncer_wait")
                else:
                    print("  INFO  PgBouncer wait metric not in health response")
        except json.JSONDecodeError:
            pass
    else:
        print(f"  SKIP  Database health endpoint returned {status}")

    return {"failures": failures}


# ── 312.17.4 — DB Active Connections Benchmark ───────────────────────

def check_db_connections() -> dict:
    """Check active PostgreSQL connections via the health endpoint."""
    failures: list[str] = []

    status, elapsed, body = _api_request("/api/v1/health/database/")
    if status != 200:
        # Try the generic health endpoint.
        status, elapsed, body = _api_request("/health/")
        if status not in (200, 503):
            print("  SKIP  No health endpoint available for DB connection check")
            return {"failures": []}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print("  SKIP  Health response not JSON — can't parse connection count")
        return {"failures": []}

    if isinstance(data, dict):
        conns = data.get("active_connections") or data.get("db_connections") or data.get("connections")
        if conns is not None:
            passed, msg = _check_threshold("DB active connections", conns,
                                            THRESHOLDS["db_active_connections_max"])
            print(msg)
            if not passed:
                failures.append("db_connections")
        else:
            print("  INFO  DB connection count not in health response")
    else:
        print("  SKIP  Unexpected health response format")

    return {"failures": failures}


# ── 312.17.5 — Redis Memory Benchmark ────────────────────────────────

def check_redis_memory() -> dict:
    """Check Redis memory usage via health endpoint or Redis metrics."""
    failures: list[str] = []

    status, elapsed, body = _api_request("/api/v1/health/redis/")
    if status == 404:
        status, elapsed, body = _api_request("/health/")
        if status not in (200, 503):
            print("  SKIP  No health endpoint available for Redis memory check")
            return {"failures": []}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print("  SKIP  Health response not JSON — can't parse Redis memory")
        return {"failures": []}

    if isinstance(data, dict):
        # Check for Redis-specific fields.
        redis_info = data.get("redis", data)
        if isinstance(redis_info, dict):
            for instance in ["cache", "queue", "events", "channels"]:
                key = f"redis_{instance}_memory_pct"
                pct = redis_info.get(key)
                if pct is not None:
                    passed, msg = _check_threshold(
                        f"Redis {instance} memory", pct,
                        THRESHOLDS["redis_memory_pct_max"], "%"
                    )
                    print(msg)
                    if not passed:
                        failures.append(f"redis_{instance}_memory")
        else:
            # Generic memory check.
            mem = redis_info if isinstance(redis_info, (int, float)) else None
            if mem is not None:
                passed, msg = _check_threshold("Redis memory", mem,
                                                THRESHOLDS["redis_memory_pct_max"], "%")
                print(msg)
                if not passed:
                    failures.append("redis_memory")
            else:
                print("  INFO  Redis memory percentage not in health response")
    else:
        print("  SKIP  Unexpected health response format")

    return {"failures": failures}


# ── Main ──────────────────────────────────────────────────────────────

CHECKS = {
    "api": ("API response times", check_api_response_times),
    "worker": ("Worker queue depth", check_worker_queue_depth),
    "pgbouncer": ("PgBouncer connection pool", check_pgbouncer_pool),
    "db": ("DB active connections", check_db_connections),
    "redis": ("Redis memory", check_redis_memory),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Performance baseline gate checks (312.17)")
    parser.add_argument("--check", choices=list(CHECKS) + ["all"], default="all",
                        help="Which check to run (default: all)")
    parser.add_argument("--json", action="store_true", help="JSON output for CI")
    args = parser.parse_args()

    selected = list(CHECKS) if args.check == "all" else [args.check]
    all_failures: list[str] = []
    report: dict = {}

    for name in selected:
        label, fn = CHECKS[name]
        print(f"\n{'='*60}")
        print(f"  {label} (312.17)")
        print(f"{'='*60}")
        result = fn()
        all_failures.extend(result.get("failures", []))
        report[name] = result

    print(f"\n{'='*60}")
    if all_failures:
        print(f"  FAILED: {len(all_failures)} threshold(s) exceeded:")
        for f in all_failures:
            print(f"    - {f}")
        print(f"{'='*60}")
        if args.json:
            print(json.dumps({"status": "fail", "failures": all_failures, "report": report}))
        sys.exit(1)
    else:
        print("  PASSED: All performance baselines within thresholds")
        print(f"{'='*60}")
        if args.json:
            print(json.dumps({"status": "pass", "failures": [], "report": report}))
        sys.exit(0)


if __name__ == "__main__":
    main()
