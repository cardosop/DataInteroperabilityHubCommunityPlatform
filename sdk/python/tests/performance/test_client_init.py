import pytest

pytestmark = pytest.mark.performance

"""
Phase 216.4.3 — SDK DataHubClient init < 100ms.

Measures the time to construct a DataHubClient instance (import +
construction, no network call). The budget is 100ms — client init
must be fast so CLI commands feel instant.
"""

import time
from tests.fixtures.perf_record import build_perf_record, write_perf_record

BUDGET_MS = 100.0
ITERATIONS = 10


def _measure_init_ms() -> float:
    start = time.perf_counter()
    try:
        from datahub_sdk import DataHubClient
        _ = DataHubClient(base_url="http://localhost:8000/api/v1", api_key="perf-test-key")
    except ImportError:
        pytest.skip("datahub_sdk not installed")
    except Exception:
        pass  # Init may fail (no backend) — we only care about speed
    return (time.perf_counter() - start) * 1000


def test_client_init_under_budget():
    """DataHubClient(...) init must complete in <100ms."""
    measurements = [_measure_init_ms() for _ in range(ITERATIONS)]

    record = build_perf_record(
        test_name="test_client_init_under_budget",
        measurements_ms=measurements,
        budget_ms=BUDGET_MS,
    )
    write_perf_record(record)

    assert record.passed, (
        f"SDK client init exceeded {BUDGET_MS}ms budget: "
        f"mean={record.measurement_ms:.0f}ms "
        f"p95={record.p95_ms:.0f}ms"
    )
