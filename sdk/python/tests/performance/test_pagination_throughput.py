import pytest

pytestmark = pytest.mark.performance

"""
Phase 216.4.4 — SDK paginate 10k assets < 30s.

Measures the time to paginate through all assets. If the staging
backend has fewer than 10k assets, this validates what's available
and records the throughput. The 30s budget is generous for CI.
"""

import time
import requests
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get
from tests.fixtures.perf_record import build_perf_record, write_perf_record

BUDGET_MS = 30_000.0
PAGE_SIZE = 100
MAX_PAGES = 100  # 100 pages × 100 items = 10k


def test_pagination_throughput_under_budget():
    """Paginating through up to 10k assets must complete in <30s."""
    try:
        creds = provision_persona("data_engineer")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        pytest.skip("Backend not available")

    start = time.perf_counter()
    total_items = 0
    page = 1

    for _ in range(MAX_PAGES):
        resp = api_get("/assets/", creds, params={
            "page": page,
            "page_size": PAGE_SIZE,
        })
        if resp.status_code != 200:
            break

        data = resp.json()
        results = data.get("results", [])
        total_items += len(results)

        if not data.get("next") or not results:
            break
        page += 1

    elapsed_ms = (time.perf_counter() - start) * 1000

    record = build_perf_record(
        test_name="test_pagination_throughput_under_budget",
        measurements_ms=[elapsed_ms],
        budget_ms=BUDGET_MS,
    )
    write_perf_record(record)

    assert record.passed, (
        f"Pagination of {total_items} items took {elapsed_ms:.0f}ms "
        f"(budget: {BUDGET_MS:.0f}ms)"
    )
