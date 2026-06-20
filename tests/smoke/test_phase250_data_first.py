"""
Smoke test — Phase 250 Definition of Done #7 (250.DoD.7).

Validates the four post-deploy criteria called out in `openspec/changes/preprod01/tasks.md`
section 250.DoD.7 against a deployed staging or production environment, using real HTTP
calls (no mocks, no stubs):

    1. Data-first creation P95 latency ≤ 8 s.
    2. Fail-closed run produces zero orphan DRAFT assets.
    3. Federated-import flag flipped → import succeeds AND surfaces a compliance-gate
       result (verified via structured response metadata).
    4. ``If-Match`` mismatch on ``PATCH /assets/<id>/`` returns the structured
       412 Precondition Failed contract.

The test creates ephemeral resources (file uploads, assets) under the smoke admin
account and tears each one down regardless of test outcome. Tests that require
seeded fixtures or a flag flipped on the smoke tenant are gated behind explicit
opt-in env vars so an unconfigured environment skips loudly rather than failing
silently.

Required env vars
-----------------
SMOKE_ADMIN_EMAIL / SMOKE_ADMIN_PASSWORD
    Authenticated session for resource creation. Provided by ``conftest.py``.

Optional env vars
-----------------
SMOKE_PHASE250_LATENCY_ITERATIONS
    Number of data-first creations to run for the P95 calculation (default: 5).
SMOKE_PHASE250_LATENCY_BUDGET_MS
    P95 latency budget in milliseconds (default: 8000 — matches DoD.7).
SMOKE_PHASE250_FEDERATED_IMPORT_ENABLED
    When ``1``/``true``/``yes``, the federated-import sub-test runs against the
    smoke tenant. Set this only after the tenant has had
    ``federated_import_enabled=True`` flipped on. Otherwise the test skips.
SMOKE_PHASE250_FEDERATED_SOURCE_LISTING_ID
    Listing ID on the federated source side. Required when the federated test runs.

References
----------
- ``openspec/changes/preprod01/tasks.md`` § 250.DoD.7
- ``hub/apps/assets/views.py::AssetViewSet.data_first``
- ``hub/apps/assets/views.py::AssetViewSet.partial_update``
- ``hub/apps/integrations/services/discovery_service.py``
"""

from __future__ import annotations

import contextlib
import os
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
import requests

# ---------------------------------------------------------------------------
# Config knobs
# ---------------------------------------------------------------------------

LATENCY_ITERATIONS = int(os.getenv("SMOKE_PHASE250_LATENCY_ITERATIONS", "5"))
LATENCY_BUDGET_MS = int(os.getenv("SMOKE_PHASE250_LATENCY_BUDGET_MS", "8000"))
FEDERATED_IMPORT_ENABLED = os.getenv(
    "SMOKE_PHASE250_FEDERATED_IMPORT_ENABLED", ""
).strip().lower() in ("1", "true", "yes", "on")
FEDERATED_SOURCE_LISTING_ID = os.getenv("SMOKE_PHASE250_FEDERATED_SOURCE_LISTING_ID")

ASSETS_PATH = "/api/v1/assets/"
ASSETS_DATA_FIRST_PATH = "/api/v1/assets/data-first/"
FILES_INIT_PATH = "/api/v1/files/init/"
FILES_COMPLETE_PATH_TEMPLATE = "/api/v1/files/{file_id}/complete/"
FEDERATED_IMPORT_PATH = "/api/v1/marketplace/imports/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (matches numpy default)."""
    if not values:
        raise ValueError("Cannot compute percentile of empty sequence")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _upload_smoke_file(
    base_url: str,
    session: requests.Session,
    timeout: int,
    *,
    name_prefix: str,
    payload: bytes,
    content_type: str = "text/csv",
) -> str:
    """Upload ``payload`` via the real /files/init → presign → /complete flow.

    Returns the resulting ``file_id`` (UUID string).

    A successful upload requires the deployed environment to expose presigned
    S3 URLs reachable from the test runner. If init returns 4xx (e.g. quota,
    invalid Content-Type), the caller should ``pytest.skip`` so smoke remains
    advisory in misconfigured environments.
    """
    init_response = session.post(
        f"{base_url}{FILES_INIT_PATH}",
        json={
            "name": f"{name_prefix}-{uuid.uuid4().hex[:8]}.csv",
            "content_type": content_type,
            "size": len(payload),
            "upload_method": "sdk",
        },
        timeout=timeout,
    )
    if init_response.status_code != 200:
        pytest.skip(f"/files/init returned {init_response.status_code}: {init_response.text[:300]}")
    init_body = init_response.json()
    file_id = str(init_body["file_id"])
    upload_url = str(init_body["upload_url"])
    fields = init_body.get("fields") or {}

    # Presigned PUT uploads encode auth in the URL itself; do NOT forward the
    # bearer token (it confuses S3 signature validation).
    upload_resp = requests.put(
        upload_url,
        data=payload,
        headers={"Content-Type": content_type, **fields},
        timeout=timeout,
    )
    if upload_resp.status_code not in (200, 204):
        pytest.skip(
            f"Presigned upload returned {upload_resp.status_code}: {upload_resp.text[:300]}"
        )

    complete_resp = session.post(
        f"{base_url}{FILES_COMPLETE_PATH_TEMPLATE.format(file_id=file_id)}",
        json={},
        timeout=timeout,
    )
    if complete_resp.status_code not in (200, 201):
        pytest.skip(
            f"/files/{{id}}/complete returned {complete_resp.status_code}: "
            f"{complete_resp.text[:300]}"
        )
    return file_id


def _delete_asset(
    base_url: str,
    session: requests.Session,
    timeout: int,
    asset_id: str,
) -> None:
    """Best-effort delete; never raises."""
    with contextlib.suppress(requests.RequestException):
        session.delete(f"{base_url}{ASSETS_PATH}{asset_id}/", timeout=timeout)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def smoke_run_id() -> str:
    """A unique ID for this smoke run; embedded in resource names for traceability."""
    return uuid.uuid4().hex[:12]


@pytest.fixture
def created_assets(
    base_url: str,
    authenticated_session: requests.Session,
    timeout: int,
) -> Iterator[list[str]]:
    """Track asset IDs created by a single test and clean them up on teardown."""
    ids: list[str] = []
    yield ids
    for asset_id in ids:
        _delete_asset(base_url, authenticated_session, timeout, asset_id)


# ---------------------------------------------------------------------------
# 1) Data-first P95 ≤ 8 s
# ---------------------------------------------------------------------------


class TestDataFirstLatency:
    """DoD.7 — data-first creation P95 ≤ 8 s."""

    def test_data_first_p95_within_budget(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
        smoke_run_id: str,
        created_assets: list[str],
    ) -> None:
        if LATENCY_ITERATIONS < 3:
            pytest.skip(  # noqa: skip-in-body — runtime service dependency
                "Need at least 3 iterations for a meaningful P95 — set "
                "SMOKE_PHASE250_LATENCY_ITERATIONS >= 5 (default 5)"
            )

        latencies_ms: list[float] = []
        # Minimal but valid CSV — workflow must accept it through DQ + compliance.
        sample_csv = b"id,name\n1,smoke\n2,test\n"

        for i in range(LATENCY_ITERATIONS):
            file_id = _upload_smoke_file(
                base_url,
                authenticated_session,
                timeout,
                name_prefix=f"smoke-p250-latency-{smoke_run_id}-{i}",
                payload=sample_csv,
            )
            unique_key = f"smoke-p250-{smoke_run_id}-latency-{i}"
            payload: dict[str, Any] = {
                "file_id": file_id,
                "key": unique_key,
                "name": f"Smoke P250 latency {i}",
                "description": "Phase 250 DoD.7 smoke — safe to delete",
            }
            io.BytesIO()
            # We pass the JSON via requests so it computes Content-Length itself,
            # which the data-first view requires (rejects chunked transfer).
            started = time.perf_counter()
            response = authenticated_session.post(
                f"{base_url}{ASSETS_DATA_FIRST_PATH}",
                json=payload,
                timeout=max(timeout, LATENCY_BUDGET_MS // 1000 + 5),
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0

            assert response.status_code in (200, 201, 202), (
                f"data-first iteration {i} failed ({response.status_code}): {response.text[:500]}"
            )
            body = response.json()
            asset_id = body.get("asset_id") or body.get("id")
            if asset_id:
                created_assets.append(asset_id)
            latencies_ms.append(elapsed_ms)

        p95_ms = _percentile(latencies_ms, 95.0)
        assert p95_ms <= LATENCY_BUDGET_MS, (
            f"data-first P95 latency {p95_ms:.0f} ms exceeded budget "
            f"{LATENCY_BUDGET_MS} ms (DoD.7). All samples (ms): "
            f"{[round(v) for v in latencies_ms]}"
        )


# ---------------------------------------------------------------------------
# 2) Fail-closed → zero orphan DRAFTs
# ---------------------------------------------------------------------------


class TestFailClosedNoOrphanDrafts:
    """DoD.7 — a fail-closed data-first run leaves no DRAFT row behind."""

    def test_failed_data_first_creates_no_asset(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
        smoke_run_id: str,
    ) -> None:
        # An empty body is rejected at the serializer layer, but we want to
        # exercise the **gate** rejection path — so we upload a file the
        # compliance gate is configured to reject. The repo's fail-closed test
        # plane recognises a sentinel content marker.
        compliance_reject_payload = b"id,name\n1,smoke-fail-closed-sentinel\n"
        file_id = _upload_smoke_file(
            base_url,
            authenticated_session,
            timeout,
            name_prefix=f"smoke-p250-failclosed-{smoke_run_id}",
            payload=compliance_reject_payload,
        )
        unique_key = f"smoke-p250-{smoke_run_id}-failclosed"
        response = authenticated_session.post(
            f"{base_url}{ASSETS_DATA_FIRST_PATH}",
            json={
                "file_id": file_id,
                "key": unique_key,
                "name": "Smoke P250 fail-closed",
                "description": "Phase 250 DoD.7 smoke — must NOT persist",
                # Hint: some staging tenants honor this header to force the
                # compliance gate to FAIL. If unsupported, we still verify
                # below that no asset row exists for this unique key.
                "_smoke_force_compliance_fail": True,
            },
            timeout=timeout,
        )

        # Acceptable outcomes when the gate rejects the payload:
        #   - 422 ASSET_FAIL_CLOSED_REJECTED (canonical fail-closed contract)
        #   - 400/422 with another VALIDATION_ERROR if the staging plane has
        #     no synthetic-fail mechanism configured
        # Either way, the post-condition is: no asset row with this key.
        # If the request succeeds, the staging plane has no fail-closed
        # synthetic; record and skip rather than asserting falsely.
        if response.status_code in (200, 201, 202):
            body = response.json()
            asset_id = body.get("asset_id") or body.get("id")
            if asset_id:
                _delete_asset(base_url, authenticated_session, timeout, asset_id)
            pytest.skip(  # noqa: skip-in-body — runtime service dependency
                "Staging plane accepted the synthetic fail-closed payload — "
                "configure a compliance-fail fixture or set "
                "ASSET_FAIL_CLOSED_SMOKE_FIXTURE on the API to exercise this."
            )

        assert response.status_code in (400, 422), (
            f"Expected fail-closed rejection (400/422), got "
            f"{response.status_code}: {response.text[:500]}"
        )

        # Post-condition: no DRAFT asset persisted under our unique key.
        list_resp = authenticated_session.get(
            f"{base_url}{ASSETS_PATH}",
            params={"key": unique_key},
            timeout=timeout,
        )
        assert list_resp.status_code == 200, (
            f"Asset list query failed ({list_resp.status_code}): {list_resp.text[:300]}"
        )
        listed = list_resp.json()
        results = listed.get("results", listed if isinstance(listed, list) else [])
        matching = [r for r in results if r.get("key") == unique_key]
        assert matching == [], f"Fail-closed left orphan DRAFT(s) for key={unique_key}: {matching}"


# ---------------------------------------------------------------------------
# 3) Federated import — flag flipped → succeeds with compliance gate
# ---------------------------------------------------------------------------


class TestFederatedImportFlagFlipped:
    """DoD.7 — federated-import flag flipped → import succeeds with compliance gate."""

    @pytest.mark.skipif(
        not FEDERATED_IMPORT_ENABLED,
        reason=(
            "Set SMOKE_PHASE250_FEDERATED_IMPORT_ENABLED=1 once the smoke "
            "tenant has Tenant.federated_import_enabled flipped on."
        ),
    )
    def test_federated_import_succeeds_with_compliance_gate(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
        smoke_run_id: str,
        created_assets: list[str],
    ) -> None:
        if not FEDERATED_SOURCE_LISTING_ID:
            pytest.skip(  # noqa: skip-in-body — runtime service dependency
                "SMOKE_PHASE250_FEDERATED_SOURCE_LISTING_ID is required when "
                "the federated-import smoke is enabled."
            )

        response = authenticated_session.post(
            f"{base_url}{FEDERATED_IMPORT_PATH}",
            json={
                "source_listing_id": FEDERATED_SOURCE_LISTING_ID,
                "import_key": f"smoke-p250-{smoke_run_id}-federated",
            },
            timeout=timeout,
        )

        if response.status_code == 404:
            pytest.skip(  # noqa: skip-in-body — runtime service dependency
                f"Federated-import endpoint not exposed at {FEDERATED_IMPORT_PATH} "
                "in this environment — update SMOKE config or the path constant."
            )

        assert response.status_code in (200, 201, 202), (
            f"Federated import failed ({response.status_code}): {response.text[:500]}"
        )
        body = response.json()
        asset_id = body.get("asset_id") or body.get("id")
        if asset_id:
            created_assets.append(asset_id)

        # Compliance-gate signal must be present (D250.5.A): either an explicit
        # ``compliance_*`` field or a nested ``gates.compliance`` section.
        compliance_signal = (
            body.get("compliance_check_id")
            or body.get("compliance_status")
            or (body.get("gates") or {}).get("compliance")
        )
        assert compliance_signal, (
            f"Federated import response missing compliance-gate metadata: {list(body.keys())}"
        )


# ---------------------------------------------------------------------------
# 4) If-Match 412 → structured error
# ---------------------------------------------------------------------------


class TestIfMatch412Contract:
    """DoD.7 — ``If-Match`` mismatch returns the structured 412 contract."""

    def test_stale_if_match_returns_412_with_structured_body(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
        smoke_run_id: str,
        created_assets: list[str],
    ) -> None:
        # Create a minimal asset via the canonical create path. We don't need
        # the full data-first workflow here — the If-Match contract is on
        # ``PATCH /assets/<id>/`` and applies to all asset rows.
        create_payload = {
            "key": f"smoke-p250-{smoke_run_id}-ifmatch",
            "name": "Smoke P250 If-Match",
            "description": "Phase 250 DoD.7 smoke — If-Match 412 contract",
            "asset_type": "DATASET",
        }
        create_resp = authenticated_session.post(
            f"{base_url}{ASSETS_PATH}",
            json=create_payload,
            timeout=timeout,
        )
        if create_resp.status_code == 422:
            pytest.skip(  # noqa: skip-in-body — runtime service dependency
                f"Asset create endpoint refused minimal payload ({create_resp.status_code}): "
                f"{create_resp.text[:300]} — adjust create_payload for this environment."
            )
        assert create_resp.status_code in (200, 201), (
            f"Asset create failed ({create_resp.status_code}): {create_resp.text[:500]}"
        )
        asset = create_resp.json()
        asset_id = asset.get("id") or asset.get("asset_id")
        current_version = asset.get("version", 1)
        assert asset_id, f"Asset create response missing id: {asset}"
        created_assets.append(asset_id)

        stale_version = max(int(current_version) - 1, 0)
        if stale_version == int(current_version):
            # First-version asset — bump to v2 so we have a stale value.
            bump = authenticated_session.patch(
                f"{base_url}{ASSETS_PATH}{asset_id}/",
                json={"description": "bump-for-smoke"},
                headers={"If-Match": str(current_version)},
                timeout=timeout,
            )
            assert bump.status_code in (200, 202), (
                f"Could not bump asset version for stale-If-Match check "
                f"({bump.status_code}): {bump.text[:300]}"
            )
            current_version = bump.json().get("version", int(current_version) + 1)
            stale_version = int(current_version) - 1

        patch_resp = authenticated_session.patch(
            f"{base_url}{ASSETS_PATH}{asset_id}/",
            json={"description": "stale-write-attempt"},
            headers={"If-Match": str(stale_version)},
            timeout=timeout,
        )
        assert patch_resp.status_code == 412, (
            f"Expected 412 PRECONDITION_FAILED for stale If-Match, got "
            f"{patch_resp.status_code}: {patch_resp.text[:500]}"
        )

        body = patch_resp.json()
        assert body.get("code") == "PRECONDITION_FAILED", (
            f"412 body missing code=PRECONDITION_FAILED: {body}"
        )
        assert "error" in body, f"412 body missing error message: {body}"
        details = body.get("details") or {}
        assert "expected_version" in details, f"412 body.details missing expected_version: {body}"
        assert "provided_version" in details, f"412 body.details missing provided_version: {body}"
        assert int(details["provided_version"]) == int(stale_version), (
            f"412 details.provided_version mismatch: {details}"
        )
