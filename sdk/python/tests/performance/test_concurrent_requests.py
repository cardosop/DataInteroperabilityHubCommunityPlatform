import pytest

pytestmark = pytest.mark.performance

"""
Phase 216.4.5 — 50 concurrent SDK requests: no deadlock, < 10s.

Fires 50 parallel GET /auth/me/ and verifies all complete within 10s
with no server errors or thread hangs.
"""

import concurrent.futures
import time
import requests
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url
from tests.fixtures.perf_record import build_perf_record, write_perf_record

BUDGET_MS = 10_000.0
CONCURRENCY = 50


def _single_request(token: str) -> tuple[int, float]:
    """Execute one authenticated GET and return (status, latency_ms)."""
    start = time.perf_counter()
    try:
        resp = requests.get(
            f"{api_base_url()}/auth/me/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        return resp.status_code, elapsed_ms
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return -1, elapsed_ms


def test_concurrent_requests_under_budget():
    """50 parallel requests must all complete in <10s total."""
    creds = provision_persona("data_engineer")

    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(_single_request, creds.api_key) for _ in range(CONCURRENCY)]
        results = [f.result(timeout=30) for f in futures]
    total_ms = (time.perf_counter() - start) * 1000

    statuses = [r[0] for r in results]
    latencies = [r[1] for r in results]

    # No thread should have hung
    errors = [s for s in statuses if s == -1]
    assert not errors, f"{len(errors)}/{CONCURRENCY} requests failed (network error)"

    # No server errors
    server_errors = [s for s in statuses if s >= 500]
    assert not server_errors, f"{len(server_errors)} server errors in concurrent batch"

    record = build_perf_record(
        test_name="test_concurrent_requests_under_budget",
        measurements_ms=[total_ms],
        budget_ms=BUDGET_MS,
    )
    write_perf_record(record)

    from collections import Counter
    assert record.passed, (
        f"50 concurrent requests took {total_ms:.0f}ms (budget: {BUDGET_MS:.0f}ms). "
        f"Statuses: {dict(Counter(statuses))}"
    )
