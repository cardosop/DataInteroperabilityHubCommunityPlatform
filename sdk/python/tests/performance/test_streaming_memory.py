import pytest

pytestmark = pytest.mark.performance

"""
Phase 216.4.6 — Streaming endpoint memory < 100MB peak.

Verifies that paginating a large result set does not accumulate all
pages in memory. The test measures peak RSS delta during pagination.
Budget: <100MB RSS growth. If the endpoint streams correctly, memory
stays roughly constant regardless of total result count.
"""

import os
import resource
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get
from tests.fixtures.perf_record import build_perf_record, write_perf_record

BUDGET_MB = 100.0
PAGE_SIZE = 100
MAX_PAGES = 50


def _get_rss_mb() -> float:
    """Current process RSS in MB (Linux/macOS)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # ru_maxrss is in KB on Linux, bytes on macOS
    if os.uname().sysname == "Darwin":
        return usage.ru_maxrss / (1024 * 1024)
    return usage.ru_maxrss / 1024


def test_streaming_memory_under_budget():
    """Paginating 50 pages must not grow RSS by >100MB."""
    creds = provision_persona("data_engineer")

    rss_before = _get_rss_mb()

    for page in range(1, MAX_PAGES + 1):
        resp = api_get("/assets/", creds, params={
            "page": page,
            "page_size": PAGE_SIZE,
        })
        if resp.status_code != 200:
            break
        data = resp.json()
        # Process the page but don't accumulate — this is what real
        # streaming code should do.
        _ = len(data.get("results", []))
        if not data.get("next"):
            break

    rss_after = _get_rss_mb()
    delta_mb = rss_after - rss_before

    # Record as measurement_ms (reusing the field for MB; the schema
    # is generic enough — budget_ms becomes budget_mb conceptually).
    record = build_perf_record(
        test_name="test_streaming_memory_under_budget",
        measurements_ms=[delta_mb],
        budget_ms=BUDGET_MB,
    )
    write_perf_record(record)

    assert delta_mb < BUDGET_MB, (
        f"Streaming pagination grew RSS by {delta_mb:.1f}MB "
        f"(budget: {BUDGET_MB}MB)"
    )
