"""
Phase 250.4.2 / .4.3 / .4.4 — TDD tests for the SDK ``wait_for``
helpers on JobsAPI, ComplianceAPI, and DQAPI.

Contract under test
-------------------

The DE-1 "programmatic asset creation" workflow (Phase 250.0.8) is
a multi-step async sequence: POST contract → poll job → POST file
→ POST dataset → poll DQ → poll compliance → assert ACTIVE. Each
poll step is idiomatically awkward without a SDK-provided
``wait_for`` helper — every caller would otherwise re-implement
the same poll-until-terminal loop with the same edge cases.

This phase ships three helpers, each with the same contract:

1. **``client.jobs.wait_for(job_id, timeout=300)``** — polls
   ``GET /jobs/{id}/`` until ``status`` reaches one of
   ``{COMPLETED, FAILED, CANCELLED}``. Returns the final job
   payload. Raises :class:`asyncio.TimeoutError` on timeout.

2. **``client.compliance.wait_for(asset_id, timeout=180)``** —
   polls ``GET /compliance/runs/?asset_id=<id>&page_size=1`` for
   the latest run; returns when its ``status`` reaches a
   terminal state (``completed`` / ``failed`` / ``cancelled``).
   Asset may not have a run yet at first poll — the helper waits
   for the run to APPEAR first, then for it to terminate.

3. **``client.dq.wait_for(asset_id, timeout=180)``** — polls
   ``GET /dq/runs/?asset_id=<id>&limit=1`` for the latest run;
   returns when its ``status`` reaches a terminal state
   (``PASS`` / ``FAIL`` / ``WARN`` / ``completed`` / ``failed``).

All three share:
* configurable ``interval`` (default 2.0s) for the poll cadence.
* terminal-state set published as a class constant so callers
  can subclass / override for non-canonical hub deployments.
* fail-fast on ``ValueError`` or ``TypeError`` from the underlying
  client (auth / serialisation errors propagate; transient HTTP
  errors are NOT swallowed by the helper — the caller's retry
  policy is the right place for that).

TDD doctrine
------------
Real ``DataHubClient`` instance + real method dispatch; only the
HTTP boundary (``client.get`` / ``client.post``) is patched via
``unittest.mock.AsyncMock`` so we can pin the response shape per
call. The helper logic itself — the poll loop, terminal detection,
timeout — is exercised end-to-end. Real ``asyncio.sleep`` patched
to a no-op so the tests run in milliseconds without changing the
elapsed-time accounting (we still verify the timeout triggers
correctly).
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from datahub_interoperability.client import DataHubClient
from datahub_interoperability.compliance import ComplianceAPI
from datahub_interoperability.config import DataHubClientConfig
from datahub_interoperability.dq import DQAPI
from datahub_interoperability.jobs import JobsAPI


@pytest.fixture
def client():
    config = DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
    )
    return DataHubClient(config)


@pytest.fixture
def jobs_api(client):
    return JobsAPI(client)


@pytest.fixture
def compliance_api(client):
    return ComplianceAPI(client)


@pytest.fixture
def dq_api(client):
    return DQAPI(client)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Replace ``asyncio.sleep`` with a no-op so the poll loops
    don't actually wait. Time-elapsed accounting still uses the
    advertised ``interval`` parameter so the timeout assertion
    remains meaningful — we just don't waste real wall-clock."""
    import asyncio as _asyncio

    async def _instant(_seconds):
        return None

    monkeypatch.setattr(_asyncio, "sleep", _instant)


# ---------------------------------------------------------------------------
# 250.4.2 — JobsAPI.wait_for
# ---------------------------------------------------------------------------


class TestJobsWaitFor:
    """``client.jobs.wait_for(job_id, timeout=300)`` polls
    ``GET /jobs/{id}/`` until terminal status."""

    @pytest.mark.asyncio
    async def test_returns_completed_job_immediately(self, jobs_api, client):
        """If the first poll already shows a terminal status,
        return after one round-trip — no extra polls."""
        terminal_payload = {"id": "job-1", "status": "COMPLETED"}
        client.get = AsyncMock(return_value=terminal_payload)

        result = await jobs_api.wait_for("job-1", timeout=10.0)

        assert result == terminal_payload
        client.get.assert_called_once_with("jobs/job-1/")

    @pytest.mark.asyncio
    async def test_polls_until_completed(self, jobs_api, client):
        """Two non-terminal polls then one terminal — verify the
        helper persists across multiple round-trips."""
        client.get = AsyncMock(side_effect=[
            {"id": "job-1", "status": "PENDING"},
            {"id": "job-1", "status": "RUNNING"},
            {"id": "job-1", "status": "COMPLETED", "result": "ok"},
        ])

        result = await jobs_api.wait_for("job-1", timeout=10.0, interval=0.1)
        assert result["status"] == "COMPLETED"
        assert client.get.await_count == 3

    @pytest.mark.asyncio
    async def test_returns_failed_terminal(self, jobs_api, client):
        """FAILED is terminal — return the failure payload
        rather than raise; the caller decides whether failure is
        an exception."""
        client.get = AsyncMock(return_value={
            "id": "job-1", "status": "FAILED", "error": "boom",
        })

        result = await jobs_api.wait_for("job-1", timeout=10.0)
        assert result["status"] == "FAILED"
        assert result["error"] == "boom"

    @pytest.mark.asyncio
    async def test_returns_cancelled_terminal(self, jobs_api, client):
        client.get = AsyncMock(return_value={
            "id": "job-1", "status": "CANCELLED",
        })

        result = await jobs_api.wait_for("job-1", timeout=10.0)
        assert result["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_raises_timeout_when_status_never_terminal(
        self, jobs_api, client,
    ):
        client.get = AsyncMock(return_value={
            "id": "job-1", "status": "RUNNING",
        })

        with pytest.raises(TimeoutError) as exc_info:
            await jobs_api.wait_for(
                "job-1", timeout=1.0, interval=0.5,
            )
        assert "job-1" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 250.4.3 — ComplianceAPI.wait_for
# ---------------------------------------------------------------------------


class TestComplianceWaitFor:
    """``client.compliance.wait_for(asset_id, timeout=180)``
    polls ``GET /compliance/runs/?asset_id=<id>`` for the
    latest run; returns when terminal."""

    @pytest.mark.asyncio
    async def test_returns_when_latest_run_completed(
        self, compliance_api, client,
    ):
        client.get = AsyncMock(return_value={
            "results": [{
                "id": "run-1",
                "asset_id": "asset-1",  # noqa: PHASE216-STATIC-ID
                "status": "completed",
            }],
        })

        result = await compliance_api.wait_for(
            "asset-1", timeout=10.0,  # noqa: PHASE216-STATIC-ID
        )
        assert result["status"] == "completed"
        assert result["asset_id"] == "asset-1"  # noqa: PHASE216-STATIC-ID

    @pytest.mark.asyncio
    async def test_waits_for_run_to_appear(
        self, compliance_api, client,
    ):
        """First poll returns no runs (the workflow hasn't yet
        created one); second poll returns a running one; third
        returns terminal."""
        client.get = AsyncMock(side_effect=[
            {"results": []},  # not yet
            {"results": [{
                "id": "run-1", "asset_id": "asset-1",  # noqa: PHASE216-STATIC-ID
                "status": "running",
            }]},
            {"results": [{
                "id": "run-1", "asset_id": "asset-1",  # noqa: PHASE216-STATIC-ID
                "status": "completed",
            }]},
        ])

        result = await compliance_api.wait_for(
            "asset-1", timeout=10.0, interval=0.1,  # noqa: PHASE216-STATIC-ID
        )
        assert result["status"] == "completed"
        assert client.get.await_count == 3

    @pytest.mark.asyncio
    async def test_returns_failed_terminal(self, compliance_api, client):
        client.get = AsyncMock(return_value={
            "results": [{
                "id": "run-1", "asset_id": "asset-1",  # noqa: PHASE216-STATIC-ID
                "status": "failed", "reason": "policy_violation",
            }],
        })

        result = await compliance_api.wait_for("asset-1", timeout=10.0)  # noqa: PHASE216-STATIC-ID
        assert result["status"] == "failed"
        assert result["reason"] == "policy_violation"

    @pytest.mark.asyncio
    async def test_raises_timeout_when_no_run_appears(
        self, compliance_api, client,
    ):
        client.get = AsyncMock(return_value={"results": []})

        with pytest.raises(TimeoutError) as exc_info:
            await compliance_api.wait_for(
                "asset-1", timeout=1.0, interval=0.5,  # noqa: PHASE216-STATIC-ID
            )
        assert "asset-1" in str(exc_info.value)  # noqa: PHASE216-STATIC-ID


# ---------------------------------------------------------------------------
# 250.4.4 — DQAPI.wait_for
# ---------------------------------------------------------------------------


class TestDQWaitFor:
    """``client.dq.wait_for(asset_id, timeout=180)`` polls
    ``GET /dq/runs/?asset_id=<id>`` for the latest run; returns
    when terminal."""

    @pytest.mark.asyncio
    async def test_returns_when_latest_run_passes(self, dq_api, client):
        client.get = AsyncMock(return_value={
            "results": [{
                "id": "run-1", "asset_id": "asset-1",  # noqa: PHASE216-STATIC-ID
                "status": "PASS", "score": 0.97,
            }],
        })

        result = await dq_api.wait_for("asset-1", timeout=10.0)  # noqa: PHASE216-STATIC-ID
        assert result["status"] == "PASS"
        assert result["score"] == 0.97

    @pytest.mark.asyncio
    async def test_returns_when_latest_run_fails(self, dq_api, client):
        client.get = AsyncMock(return_value={
            "results": [{
                "id": "run-1", "asset_id": "asset-1",  # noqa: PHASE216-STATIC-ID
                "status": "FAIL",
            }],
        })

        result = await dq_api.wait_for("asset-1", timeout=10.0)  # noqa: PHASE216-STATIC-ID
        assert result["status"] == "FAIL"

    @pytest.mark.asyncio
    async def test_returns_warn_terminal(self, dq_api, client):
        """WARN is a non-success terminal — returned, not
        raised. The caller's policy decides what to do with WARN."""
        client.get = AsyncMock(return_value={
            "results": [{
                "id": "run-1", "asset_id": "asset-1",  # noqa: PHASE216-STATIC-ID
                "status": "WARN",
            }],
        })

        result = await dq_api.wait_for("asset-1", timeout=10.0)  # noqa: PHASE216-STATIC-ID
        assert result["status"] == "WARN"

    @pytest.mark.asyncio
    async def test_polls_through_running(self, dq_api, client):
        """RUNNING is non-terminal; helper continues polling."""
        client.get = AsyncMock(side_effect=[
            {"results": [{"id": "run-1", "status": "RUNNING"}]},
            {"results": [{"id": "run-1", "status": "RUNNING"}]},
            {"results": [{"id": "run-1", "status": "PASS"}]},
        ])

        result = await dq_api.wait_for(
            "asset-1", timeout=10.0, interval=0.1,  # noqa: PHASE216-STATIC-ID
        )
        assert result["status"] == "PASS"
        assert client.get.await_count == 3

    @pytest.mark.asyncio
    async def test_raises_timeout(self, dq_api, client):
        client.get = AsyncMock(return_value={
            "results": [{"id": "run-1", "status": "RUNNING"}],
        })
        with pytest.raises(TimeoutError):
            await dq_api.wait_for(
                "asset-1", timeout=1.0, interval=0.5,  # noqa: PHASE216-STATIC-ID
            )


# ---------------------------------------------------------------------------
# Cross-cutting: terminal-state-set surface + override
# ---------------------------------------------------------------------------


class TestTerminalStatesAreOverridable:
    """The terminal-state sets are published as class constants
    so a non-canonical deployment with custom statuses can
    subclass + override without re-implementing the poll loop."""

    def test_jobs_terminal_states_published(self):
        assert {"COMPLETED", "FAILED", "CANCELLED"} <= JobsAPI.TERMINAL_STATUSES

    def test_compliance_terminal_states_published(self):
        assert {"completed", "failed", "cancelled"} <= ComplianceAPI.TERMINAL_STATUSES

    def test_dq_terminal_states_published(self):
        # Both case variants — DQ run status historically used
        # uppercase (PASS/FAIL/WARN) but newer endpoints emit
        # lowercase. The helper accepts both so the contract
        # works against any hub version.
        assert {"PASS", "FAIL", "WARN"} <= DQAPI.TERMINAL_STATUSES
        assert {"completed", "failed"} <= DQAPI.TERMINAL_STATUSES
