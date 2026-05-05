# Programmatic asset creation (DE-1)

**Phase**: 250.4.9
**Audience**: Data engineers using the Meshant Python SDK to drive
the full asset-creation lifecycle from a script (CI/CD pipelines,
scheduled ingestion runners, ad-hoc loaders).

This guide walks through the **DE-1 journey**: a single Python
function that takes an ODPS contract + a CSV file and produces an
ACTIVE asset, with all the intermediate async polls handled by
the SDK's `wait_for` helpers.

## Prerequisites

* A Meshant tenant with `kyc_status="VERIFIED"` (the workflow
  refuses to activate listings on unverified tenants — see
  [docs/sdk/](./)).
* An API token with `assets:write`, `contracts:write`,
  `dq:read`, `compliance:read` scopes. The token rotates on the
  90-day cadence documented at [./api-key-rotation.md](./api-key-rotation.md).
* Python 3.12+, the SDK (`pip install datahub-interoperability`).

## Environment variables

```bash
DATAHUB_BASE_URL=https://api.stagingmeshant-internal.example.com/api/v1
DATAHUB_API_TOKEN=<your token>
DATAHUB_TENANT_UUID=<your tenant uuid; for idempotency keys>
```

## Full DE-1 example

The example below is the **same code** that the Phase 250.4.5
nightly integration test exercises against staging. Copy-paste,
substitute your contract + CSV, and run.

```python
import asyncio
import json
import os
import uuid

import httpx

from datahub_interoperability.client import DataHubClient
from datahub_interoperability.config import DataHubClientConfig


async def create_asset(odps_payload: dict, csv_bytes: bytes) -> str:
    config = DataHubClientConfig(
        base_url=os.environ["DATAHUB_BASE_URL"],
        api_token=os.environ["DATAHUB_API_TOKEN"],
    )
    client = DataHubClient(config)
    tenant_uuid = os.environ["DATAHUB_TENANT_UUID"]
    unique = uuid.uuid4().hex[:8]

    # 1. Create ODPS contract via the canonical SDK method.
    #    Product-First flow extracts the embedded ODCS contract
    #    from the ODPS document automatically.
    contract_response = await client.contracts.create_odps(
        original_raw=json.dumps(odps_payload),
        extract_odcs=True,
        original_format="JSON",
    )

    # 2. (Optional) Poll any returned contract job_id.
    contract_job_id = contract_response.get("job_id")
    if contract_job_id:
        await client.jobs.wait_for(contract_job_id, timeout=300)

    # 3-5. File init → S3 upload → file complete (all SDK helpers).
    init = await client.files.init_upload(
        name=f"asset-{unique}.csv",
        content_type="text/csv",
        size=len(csv_bytes),
    )
    file_id = init["file_id"]
    async with httpx.AsyncClient(timeout=30.0) as http:
        put_response = await http.put(
            init["upload_url"],
            content=csv_bytes,
            headers={"Content-Type": "text/csv"},
        )
        put_response.raise_for_status()
    await client.files.complete_upload(file_id)

    # 6. Create the asset (data-first flow). The SDK auto-composes
    #    the Idempotency-Key per Phase 250.1.D.5 + sends canonical
    #    body bytes so a retried run within the 24h TTL returns
    #    the cached response.
    asset_response = await client.assets.create_data_first(
        tenant_uuid=tenant_uuid,
        file_id=file_id,
        key=f"my-asset-{unique}",
        name="My Programmatic Asset",
    )
    asset_id = asset_response["asset_id"]

    # 7-8. Poll DQ + compliance to terminal status.
    await client.dq.wait_for(asset_id, timeout=180)
    await client.compliance.wait_for(asset_id, timeout=180)

    # 9. Verify the asset reached ACTIVE.
    asset = await client.assets.get_asset(asset_id)
    assert asset["status"] == "ACTIVE", (
        f"Workflow completed but asset is in unexpected status: "
        f"{asset['status']!r}"
    )
    return asset_id


if __name__ == "__main__":
    odps = {...}  # your ODPS dict
    with open("data.csv", "rb") as f:
        csv_bytes = f.read()
    asset_id = asyncio.run(create_asset(odps, csv_bytes))
    print(f"Created asset: {asset_id}")
```

## SLO

The full DE-1 sequence has a **P95 ≤ 60 s SLO on a 1 MB CSV
payload** (Phase 250.4.10). Larger payloads scale roughly
linearly with DQ checks (Great Expectations) and compliance
scans (regex + ML PII detection). Per-step latency budget:

| Step | Budget | Notes |
| --- | --- | --- |
| 1 — POST contract | ≤ 2 s | Synchronous request |
| 2 — Poll contract job | ≤ 10 s | Normalisation pipeline |
| 3 — POST files/init | ≤ 1 s | Returns presigned URL |
| 4 — S3 PUT (1 MB) | ≤ 5 s | Network-bound; CDN-fronted |
| 5 — POST files/complete | ≤ 8 s | SHA-256 + ClamAV scan |
| 6 — POST assets/data-first | ≤ 3 s | Workflow kickoff |
| 7 — Poll DQ | ≤ 25 s | GE checks against 1 MB |
| 8 — Poll compliance | ≤ 15 s | Regex + ML PII detect |
| 9 — GET asset | ≤ 1 s | Read-only |
| **TOTAL** | **≤ 60 s** | P95 SLO |

## Idempotency

The SDK ships
[`compose_idempotency_key(tenant_uuid, body)`](../../sdk/python/datahub_interoperability/idempotency.py)
that produces the `<tenant_uuid>:<sha256(canonical_body)>` value
the server expects per [D250.8](../adr/asset-creation/ADR-AST-005-idempotency-key-format.md).
The canonical body is the JSON of the `dict` argument with
`sort_keys=True` and compact separators — equivalent payloads
with different whitespace produce the **same** key.

A retried request within the 24-hour TTL (the
``IDEMPOTENCY_KEY_TTL_HOURS`` server setting per Phase
250.0/250.1.D) returns the cached response without re-running
the workflow.

## Error handling

| Scenario | Exception | Recommended action |
| --- | --- | --- |
| Bad ODPS payload | `ApiError(code="VALIDATION_ERROR")` | Fix payload + retry |
| Contract job stuck | `asyncio.TimeoutError` | Inspect job state via `client.jobs.get_job(job_id)` |
| File too large | `ApiError(code="FILE_SIZE_EXCEEDED")` | Split + retry |
| ClamAV virus hit | `ApiError(code="FILE_QUARANTINED")` | Audit the file source |
| DQ FAIL | `wait_for` returns payload with `status="FAIL"` (non-exception) | Caller decides whether to mark asset DRAFT vs accept |
| Compliance fail-closed | `ApiError(code="ASSET_FAIL_CLOSED_REJECTED")` | See [docs/runbooks/asset-creation.md](../runbooks/asset-creation.md) |
| KYC not verified | `ApiError(code="TENANT_KYC_NOT_VERIFIED")` with `details.remediation_url` | Follow the remediation URL |

## Related documentation

* [./api-key-rotation.md](./api-key-rotation.md) — 90-day rotation cadence (Phase 250.4.7).
* [../adr/asset-creation/](../adr/asset-creation/) — design decisions D250.1–D250.16.
* [../runbooks/asset-creation.md](../runbooks/asset-creation.md) — operator playbook.
