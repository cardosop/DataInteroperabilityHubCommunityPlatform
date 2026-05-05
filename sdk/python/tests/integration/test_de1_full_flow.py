"""
Phase 250.4.5 — full DE-1 ("programmatic asset creation") flow
against staging. Runs in nightly CI per
``.github/workflows/sdk-integration.yml``.

The test is **gated on the presence of staging credentials**
(env vars ``DATAHUB_SDK_STAGING_BASE_URL`` and
``DATAHUB_SDK_STAGING_API_TOKEN``); it is silently skipped in
local / unit-test runs that lack those env vars. This makes the
test portable without breaking CI when staging is down for
maintenance — the skip is observable but non-blocking.

What the test covers
--------------------
1. Create ODPS contract via ``client.contracts.create_odps(...)``
2. Poll the workflow / job to terminal status if the response
   carries one (Product-First flow returns ``workflow_instance_id``)
3. Init file upload via ``client.files.init_upload(...)``
4. PUT bytes to S3 (out of SDK scope)
5. Complete file upload via ``client.files.complete_upload(...)``
6. Create asset via ``client.assets.create_data_first(...)`` —
   the SDK auto-composes the ``Idempotency-Key`` per Phase
   250.1.D.5 + sends the canonical body bytes
7. Poll DQ via ``client.dq.wait_for(asset_id, ...)``
8. Poll compliance via ``client.compliance.wait_for(asset_id, ...)``
9. ``client.assets.get_asset(asset_id)``; assert ``status == "ACTIVE"``

The test asserts the **DE-1 SLO** (Phase 250.4.10): P95 ≤ 60 s
for the full sequence on a 1 MB payload.

Why no mocks
------------
The test runs against a **real staging deployment**. The
``wait_for`` helpers are real polls; the contract / file / asset
endpoints are real DB writes; the DQ + compliance pipelines run
real worker processes. The only synthetic surface is the test
fixture's deterministic 1MB CSV payload — generated in-process
to avoid checking a binary fixture into git.

Audit-pass GAP fix: original implementation hand-rolled raw
``client.post("contracts/from-odps/", ...)`` etc. against
**fictional** endpoints. The fix routes through the actual SDK
helpers (``client.contracts.create_odps``, ``client.files.init_upload``,
``client.files.complete_upload``, ``client.assets.create_data_first``)
so the test exercises the SAME wire shapes a real SDK consumer
would use, AND a future endpoint-rename refactor doesn't have
to update both the test and the SDK.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid

import httpx
import pytest

from datahub_interoperability.client import DataHubClient
from datahub_interoperability.config import DataHubClientConfig


_STAGING_BASE_URL = os.environ.get("DATAHUB_SDK_STAGING_BASE_URL")
_STAGING_API_TOKEN = os.environ.get("DATAHUB_SDK_STAGING_API_TOKEN")
_STAGING_TENANT_UUID = os.environ.get("DATAHUB_SDK_STAGING_TENANT_UUID")


# Phase 250.4.10 — SLO target: P95 ≤ 60s for the full DE-1 sequence
# on 1 MB payload. We assert P95 in CI by aggregating multiple runs
# (this single test asserts the per-invocation budget and the
# nightly CI surfaces P95 across the rolling window).
_DE1_SLO_BUDGET_SECONDS: float = 60.0

# Bounded payload size so the test is deterministic across runs.
_DE1_PAYLOAD_BYTES: int = 1024 * 1024  # 1 MB


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skipif(
        not (
            _STAGING_BASE_URL
            and _STAGING_API_TOKEN
            and _STAGING_TENANT_UUID
        ),
        reason=(
            "Staging credentials missing — set "
            "DATAHUB_SDK_STAGING_BASE_URL, "
            "DATAHUB_SDK_STAGING_API_TOKEN, AND "
            "DATAHUB_SDK_STAGING_TENANT_UUID to run."
        ),
    ),
]


def _generate_csv_payload(size_bytes: int) -> bytes:
    """Generate a deterministic CSV body of approximately
    ``size_bytes`` bytes. Each row is a fixed-shape record so
    schema inference + DQ checks succeed without surprises."""
    header = b"id,email,score\n"
    record = b"00000000-0000-0000-0000-000000000000,user@example.com,0.95\n"
    rows_needed = max(1, (size_bytes - len(header)) // len(record))
    return header + (record * rows_needed)


def _minimal_odps_payload(unique: str) -> dict:
    """Generate a minimal valid ODPS document. ``unique`` keeps
    concurrent CI runs from colliding on the contract name."""
    return {
        "schema_version": "v1.0",
        "kind": "DataProduct",
        "metadata": {
            "name": f"de1-it-{unique}",
            "version": "1.0.0",
        },
        "spec": {
            "models": [
                {
                    "name": "users",
                    "fields": [
                        {"name": "id", "type": "string"},
                        {"name": "email", "type": "string"},
                        {"name": "score", "type": "number"},
                    ],
                }
            ],
        },
    }


async def test_de1_full_flow_completes_within_slo():
    """End-to-end: create ODPS contract → optional job poll →
    init/upload/complete file → create asset (data-first) →
    poll DQ → poll compliance → assert ACTIVE.

    The test asserts:
    1. Every step succeeds (no exceptions, no non-terminal
       responses post-poll).
    2. Total elapsed ≤ ``_DE1_SLO_BUDGET_SECONDS`` (60s) for
       the 1 MB payload.

    Failures are collected with a per-step latency breakdown so
    the CI report identifies WHICH step regressed when the SLO
    is busted.
    """
    config = DataHubClientConfig(
        base_url=_STAGING_BASE_URL,
        api_token=_STAGING_API_TOKEN,
    )
    client = DataHubClient(config)

    timings: dict[str, float] = {}
    overall_start = time.monotonic()
    unique = uuid.uuid4().hex[:8]

    # ---- Step 1: create ODPS contract via canonical SDK method ----
    step_start = time.monotonic()
    odps_payload = _minimal_odps_payload(unique)
    contract_response = await client.contracts.create_odps(
        original_raw=json.dumps(odps_payload),
        extract_odcs=True,  # Product-First flow
        original_format="JSON",
    )
    # Product-First flow returns dict with both ODPS + ODCS
    # contracts AND a workflow_instance_id; Link flow returns the
    # ODPS contract directly. Try both response shapes.
    workflow_instance_id = contract_response.get(
        "workflow_instance_id"
    )
    timings["contract_create_odps"] = time.monotonic() - step_start

    # ---- Step 2: poll the contract workflow to completion (if async) ----
    # The Product-First flow's workflow_instance_id maps to a
    # WorkflowInstance, NOT a Job — but for the DE-1 SLO contract
    # we pin the wait_for helper at the JOB layer (the SDK consumer
    # may receive either depending on the contract endpoint). When
    # only a workflow id is returned, we don't poll here; the
    # asset's data-first call below is the durable signal.
    if workflow_instance_id:
        # Best-effort: if the response also carries a job_id (the
        # contract endpoint emits one for non-product-first flows),
        # poll it. Otherwise skip — the asset workflow's wait_for
        # below covers the contract-not-yet-ready case.
        contract_job_id = contract_response.get("job_id")
        if contract_job_id:
            step_start = time.monotonic()
            await client.jobs.wait_for(contract_job_id, timeout=120.0)
            timings["contract_job_wait"] = (
                time.monotonic() - step_start
            )

    # ---- Step 3: POST files/init via SDK helper ----
    step_start = time.monotonic()
    file_init = await client.files.init_upload(
        name=f"de1-{unique}.csv",
        content_type="text/csv",
        size=_DE1_PAYLOAD_BYTES,
    )
    file_id = file_init["file_id"]
    upload_url = file_init["upload_url"]
    timings["file_init"] = time.monotonic() - step_start

    # ---- Step 4: PUT file content to S3 (out of SDK scope) ----
    step_start = time.monotonic()
    payload = _generate_csv_payload(_DE1_PAYLOAD_BYTES)
    async with httpx.AsyncClient(timeout=30.0) as http:
        put_response = await http.put(
            upload_url, content=payload,
            headers={"Content-Type": "text/csv"},
        )
        put_response.raise_for_status()
    timings["s3_put"] = time.monotonic() - step_start

    # ---- Step 5: complete file upload via SDK helper ----
    step_start = time.monotonic()
    await client.files.complete_upload(file_id)
    timings["file_complete"] = time.monotonic() - step_start

    # ---- Step 6: create asset via SDK helper ----
    # ``create_data_first`` auto-composes the Idempotency-Key per
    # Phase 250.1.D.5 + sends canonical body bytes — a regression
    # in the canonical-body contract surfaces here as a 409
    # IDEMPOTENCY_KEY_MISMATCH.
    step_start = time.monotonic()
    asset_response = await client.assets.create_data_first(
        tenant_uuid=_STAGING_TENANT_UUID,
        file_id=file_id,
        key=f"de1-it-{unique}",
        name=f"DE-1 Integration Test {unique}",
    )
    asset_id = asset_response["asset_id"]
    timings["asset_create_data_first"] = time.monotonic() - step_start

    # ---- Step 7: poll DQ to completion ----
    step_start = time.monotonic()
    dq_run = await client.dq.wait_for(asset_id, timeout=120.0)
    assert dq_run.get("status") in client.dq.TERMINAL_STATUSES, (
        f"DQ run reached unexpected status: {dq_run!r}"
    )
    timings["dq_wait"] = time.monotonic() - step_start

    # ---- Step 8: poll compliance to completion ----
    step_start = time.monotonic()
    compliance_run = await client.compliance.wait_for(
        asset_id, timeout=120.0,
    )
    assert (
        compliance_run.get("status")
        in client.compliance.TERMINAL_STATUSES
    ), (
        f"Compliance run reached unexpected status: {compliance_run!r}"
    )
    timings["compliance_wait"] = time.monotonic() - step_start

    # ---- Step 9: GET asset; assert ACTIVE ----
    step_start = time.monotonic()
    asset = await client.assets.get_asset(asset_id)
    assert asset.get("status") == "ACTIVE", (
        f"Asset did not reach ACTIVE: {asset!r}; "
        f"timings={json.dumps(timings, indent=2)}"
    )
    timings["asset_get"] = time.monotonic() - step_start

    # ---- SLO assertion: total ≤ 60s for 1 MB payload ----
    total_elapsed = time.monotonic() - overall_start
    timings["__total__"] = total_elapsed
    assert total_elapsed <= _DE1_SLO_BUDGET_SECONDS, (
        f"DE-1 SLO violation: full sequence took "
        f"{total_elapsed:.2f}s (budget: "
        f"{_DE1_SLO_BUDGET_SECONDS}s on {_DE1_PAYLOAD_BYTES} "
        f"byte payload). Per-step timings: "
        f"{json.dumps(timings, indent=2)}"
    )

    # On success, surface the timings in pytest's captured
    # output so the CI dashboard can chart per-step trends.
    print(  # noqa: T201 — intentional for CI surface
        f"DE-1 full-flow timings: {json.dumps(timings, indent=2)}"
    )
