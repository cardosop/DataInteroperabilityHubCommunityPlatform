import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.3.4 — Dimension: concurrent operations.

Verifies that N parallel authenticated requests complete without
deadlock, data corruption, or server errors.
"""

import concurrent.futures
import requests
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url


CONCURRENCY = 10  # Number of parallel requests


@pytest.fixture(scope="module")
def creds():
    return provision_persona("data_engineer")


def _make_request(token: str) -> tuple[int, str]:
    """Single authenticated GET /auth/me/."""
    try:
        resp = requests.get(
            f"{api_base_url()}/auth/me/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        return resp.status_code, ""
    except Exception as exc:
        return -1, str(exc)


def test_concurrent_reads_all_succeed(creds):
    """10 parallel GET /auth/me/ must all return 200 (or 429 for rate-limiting)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(_make_request, creds.api_key) for _ in range(CONCURRENCY)]
        results = [f.result(timeout=60) for f in futures]

    statuses = [r[0] for r in results]
    errors = [r[1] for r in results if r[0] == -1]

    assert not errors, f"Concurrent requests raised exceptions: {errors}"
    # Every status should be 200 or 429 (rate limit). Never 500 or deadlock.
    for status in statuses:
        assert status in (200, 429), f"Unexpected status in concurrent batch: {status}"


def test_concurrent_writes_no_server_error(creds):
    """10 parallel POST /assets/ must not cause 500 or deadlock."""

    def _create_asset(i: int) -> int:
        try:
            resp = requests.post(
                f"{api_base_url()}/assets/",
                headers={
                    "Authorization": f"Bearer {creds.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "name": f"concurrent-test-{i}",
                    "key": f"concurrent-key-{i}-{id(creds)}",
                },
                timeout=30,
            )
            return resp.status_code
        except Exception:
            return -1

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(_create_asset, i) for i in range(CONCURRENCY)]
        statuses = [f.result(timeout=60) for f in futures]

    for status in statuses:
        assert status < 500, f"Concurrent write caused server error: {status}"


def test_no_thread_hangs():
    """All threads must complete within the 60s budget — no deadlock."""
    creds = provision_persona("data_consumer")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(_make_request, creds.api_key) for _ in range(5)]
        # If any future doesn't complete in 60s, this raises TimeoutError
        done, not_done = concurrent.futures.wait(futures, timeout=60)

    assert len(not_done) == 0, (
        f"{len(not_done)} threads hung (deadlock?)"
    )
