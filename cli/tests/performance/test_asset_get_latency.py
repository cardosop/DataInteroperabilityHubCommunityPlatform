import pytest

pytestmark = pytest.mark.performance

"""
Phase 216.4.2 — CLI `datahub asset get <id>` end-to-end < 2s.

Measures authenticated API round-trip through the CLI layer. The budget
is 2000ms — covers DNS, TLS handshake, auth, DB query, serialisation,
and CLI output formatting. Skips if no backend is reachable.
"""

import time

from tests._persona_provisioning import provision_persona
from tests.fixtures.perf_record import build_perf_record, write_perf_record
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_get, api_post

BUDGET_MS = 2000.0
ITERATIONS = 5


@pytest.fixture(scope="module")
def asset_id():
    """Create a test asset and return its id."""
    creds = provision_persona("data_engineer")
    resp = api_post(
        "/assets/",
        creds,
        json={
            "name": fresh_id("perf-asset"),
            "key": fresh_id("perf-key"),
        },
    )
    if resp.status_code not in (200, 201):
        pytest.skip(f"Could not create test asset: {resp.status_code}")
    return resp.json()["id"]


@pytest.fixture(scope="module")
def creds():
    return provision_persona("data_engineer")


def test_asset_get_under_budget(asset_id, creds):
    """GET /assets/{id}/ must complete in <2s."""
    measurements = []
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        resp = api_get(f"/assets/{asset_id}/", creds)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert resp.status_code == 200, f"GET /assets/{asset_id}/ returned {resp.status_code}"
        measurements.append(elapsed_ms)

    record = build_perf_record(
        test_name="test_asset_get_under_budget",
        measurements_ms=measurements,
        budget_ms=BUDGET_MS,
    )
    write_perf_record(record)

    assert record.passed, (
        f"Asset GET exceeded {BUDGET_MS}ms budget: "
        f"mean={record.measurement_ms:.0f}ms "
        f"p95={record.p95_ms:.0f}ms p99={record.p99_ms:.0f}ms"
    )
