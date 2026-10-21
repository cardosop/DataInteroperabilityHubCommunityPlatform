"""
Smoke test — Phase 250 Definition of Done #7 (250.DoD.7).

Validates the four post-deploy criteria called out in `openspec/changes/preprod01/tasks.md`
section 250.DoD.7 against a deployed staging or production environment, using real HTTP
calls (no mocks, no stubs):

    1. Data-first creation P95 latency ≤ 8 s.
    2. Fail-closed run produces zero orphan DRAFT assets.
    3. Federated-import flag flipped → CKAN PULL sync creates the federated asset
       (marketplace_sync workflow, D250.3 tenant gate + dual-contract validation).
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
CKAN_TEST_URL / CKAN_TEST_API_KEY
    Federated source for the import sub-test: the test CKAN instance plus its
    write-capable JWT (raw ``Authorization`` header). The sub-test seeds its
    own source package and skips loudly when these are absent.

References
----------
- ``openspec/changes/preprod01/tasks.md`` § 250.DoD.7
- ``hub/apps/assets/views.py::AssetViewSet.data_first``
- ``hub/apps/assets/views.py::AssetViewSet.partial_update``
- ``hub/apps/integrations/services/discovery_service.py``
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import time
import uuid
from typing import TYPE_CHECKING, Any

import pytest
import requests

if TYPE_CHECKING:
    from collections.abc import Iterator

# ---------------------------------------------------------------------------
# Config knobs
# ---------------------------------------------------------------------------

LATENCY_ITERATIONS = int(os.getenv("SMOKE_PHASE250_LATENCY_ITERATIONS", "5"))
LATENCY_BUDGET_MS = int(os.getenv("SMOKE_PHASE250_LATENCY_BUDGET_MS", "8000"))
FEDERATED_IMPORT_ENABLED = os.getenv(
    "SMOKE_PHASE250_FEDERATED_IMPORT_ENABLED", ""
).strip().lower() in ("1", "true", "yes", "on")
CKAN_TEST_URL = os.getenv("CKAN_TEST_URL", "")
CKAN_TEST_API_KEY = os.getenv("CKAN_TEST_API_KEY", "")

ASSETS_PATH = "/api/v1/assets/"
ASSETS_DATA_FIRST_PATH = "/api/v1/assets/data-first/"
FILES_INIT_PATH = "/api/v1/files/init/"
FILES_COMPLETE_PATH_TEMPLATE = "/api/v1/files/{file_id}/complete/"

# Federated import (250.DoD.7) now rides the marketplace sync API: a PULL
# sync from a CKAN connection creates the federated asset via
# marketplace_sync.create_federated_assets (D250.3 gates apply).
MARKETPLACE_CONNECTIONS_PATH = "/api/v1/integrations/marketplace/connections/"
MARKETPLACE_SYNC_PATH = "/api/v1/integrations/marketplace/sync/"


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
    if init_response.status_code not in (200, 201):
        pytest.skip(f"/files/init returned {init_response.status_code}: {init_response.text[:300]}")
    init_body = init_response.json()
    file_id = str(init_body["file_id"])
    upload_url = str(init_body["upload_url"])
    fields = init_body.get("fields") or {}

    # The API issues a presigned POST (policy fields) — upload as a
    # multipart form POST, NOT a raw PUT (raw PUTs make S3/minio reject
    # with MalformedXML). Do NOT forward the bearer token — the URL itself
    # carries the auth.
    upload_resp = requests.post(
        upload_url,
        data=fields,
        files={"file": (f"{name_prefix}-{uuid.uuid4().hex[:8]}.csv", payload, content_type)},
        timeout=timeout,
    )
    if upload_resp.status_code not in (200, 204):
        pytest.skip(
            f"Presigned upload returned {upload_resp.status_code}: {upload_resp.text[:300]}"
        )

    complete_resp = session.post(
        f"{base_url}{FILES_COMPLETE_PATH_TEMPLATE.format(file_id=file_id)}",
        json={"content_sha256": hashlib.sha256(payload).hexdigest()},
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

        # The P95 budget is a production SLO. On dev hardware with degraded
        # dependencies (clamd self-check latency on slow disks) the
        # pipeline's scan step alone blows the budget — skip the measurement
        # there instead of failing the suite.
        health = authenticated_session.get(f"{base_url}/health/", timeout=timeout)
        if health.status_code == 200:
            try:
                health_data = health.json()
            except ValueError:
                health_data = {}
            if health_data.get("status") == "degraded":
                pytest.skip(  # noqa: skip-in-body — runtime service dependency
                    "latency SLO not measurable while dependencies are degraded "
                    "(e.g. slow ClamAV on dev hardware) — production must be healthy."
                )

        # data-first requires an Idempotency-Key of the form
        # <tenant_uuid>:<sha256(wire-body)> (Phase 250.1.D).
        me = authenticated_session.get(f"{base_url}/api/v1/auth/me/", timeout=timeout)
        tenant_id = str(me.json()["tenant_id"])

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
            # We pass the JSON via requests so it computes Content-Length itself,
            # which the data-first view requires (rejects chunked transfer).
            wire_body = json.dumps(payload).encode("utf-8")
            idem_key = f"{tenant_id}:{hashlib.sha256(wire_body).hexdigest()}"
            started = time.perf_counter()
            response = authenticated_session.post(
                f"{base_url}{ASSETS_DATA_FIRST_PATH}",
                json=payload,
                headers={"Idempotency-Key": idem_key},
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
        if not CKAN_TEST_URL or not CKAN_TEST_API_KEY:
            pytest.skip(  # noqa: skip-in-body — runtime service dependency
                "CKAN_TEST_URL/CKAN_TEST_API_KEY not set — no federated "
                "source marketplace to import from."
            )

        # 250.DoD.7 federated import rides the marketplace sync API: a PULL
        # sync from a CKAN connection runs the marketplace_sync workflow,
        # whose create_federated_assets step enforces the D250.3 tenant gate
        # (federated_import_enabled) and the dual-contract validation.
        package_name = f"smoke-federated-src-{smoke_run_id}"
        ckan_headers = {"Authorization": CKAN_TEST_API_KEY, "Content-Type": "application/json"}
        connection_id: str | None = None
        try:
            # 1. Seed a CKAN source package carrying ODPS metadata in the
            #    ``x_odps`` extra — the dual-contract validation requires it.
            seed = requests.post(
                f"{CKAN_TEST_URL}/api/3/action/package_create",
                json={
                    "name": package_name,
                    "title": f"Smoke Federated Source {smoke_run_id}",
                    "owner_org": "meshant-test-org",
                    "notes": "Smoke-suite federated import source package.",
                    "extras": [
                        {
                            "key": "x_odps",
                            "value": json.dumps(
                                {
                                    "pricing_plans": [
                                        {
                                            "plan_name": "smoke-free",
                                            "price": "0.00",
                                            "currency": "USD",
                                            "billing_frequency": "one-time",
                                        }
                                    ],
                                    "access_methods": {
                                        "download": {
                                            "type": "direct",
                                            "url": f"{CKAN_TEST_URL}/dataset/{package_name}",
                                        }
                                    },
                                }
                            ),
                        }
                    ],
                },
                headers=ckan_headers,
                timeout=timeout,
            )
            if seed.status_code != 200 or not seed.json().get("success"):
                pytest.skip(  # noqa: skip-in-body — runtime service dependency
                    f"CKAN package seed failed ({seed.status_code}) — "
                    "source instance is not writable."
                )

            # 2. Marketplace connection to the CKAN instance.
            conn = authenticated_session.post(
                f"{base_url}{MARKETPLACE_CONNECTIONS_PATH}",
                json={
                    "marketplace_type": "CKAN_INSTANCE",
                    "name": f"smoke-fed-conn-{smoke_run_id}",
                    "config": {"base_url": CKAN_TEST_URL, "api_key": CKAN_TEST_API_KEY},
                },
                timeout=timeout,
            )
            if conn.status_code not in (200, 201):
                pytest.skip(  # noqa: skip-in-body — runtime service dependency
                    f"Marketplace connection create failed ({conn.status_code}): {conn.text[:300]}"
                )
            connection_id = conn.json()["id"]

            # 3. PULL sync = federated import.
            job = authenticated_session.post(
                f"{base_url}{MARKETPLACE_SYNC_PATH}",
                json={
                    "connection_id": connection_id,
                    "direction": "PULL",
                    "listing_ids": [package_name],
                },
                timeout=timeout,
            )
            assert job.status_code in (200, 201, 202), (
                f"Federated import sync failed ({job.status_code}): {job.text[:500]}"
            )
            job_id = job.json()["id"]

            # 4. Poll to a terminal state (the test stack runs the workflow
            #    synchronously, but the poll keeps this valid on async deploys).
            deadline = time.monotonic() + 120
            sync_body: dict[str, Any] = {}
            while time.monotonic() < deadline:
                st = authenticated_session.get(
                    f"{base_url}{MARKETPLACE_SYNC_PATH}{job_id}/", timeout=timeout
                )
                assert st.status_code == 200, (
                    f"Sync poll failed ({st.status_code}): {st.text[:300]}"
                )
                sync_body = st.json()
                if sync_body.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
                    break
                time.sleep(5)  # noqa: sleep-needed  # INTENTIONAL: poll interval inside the 120s deadline-bounded status loop (HTTP polling — Event.wait cannot replace it)

            assert sync_body.get("status") == "COMPLETED", (
                f"Federated import ended {sync_body.get('status')!r}: {sync_body}"
            )

            # 5. The federated asset landed under the connector's key scheme.
            assets = authenticated_session.get(
                f"{base_url}{ASSETS_PATH}",
                params={"key": f"ckan-{package_name}"},
                timeout=timeout,
            )
            assert assets.status_code == 200, (
                f"Asset list failed ({assets.status_code}): {assets.text[:300]}"
            )
            listed = assets.json().get("results", [])
            assert listed, (
                f"Federated asset ckan-{package_name} missing after COMPLETED sync — "
                "dual-contract validation or the D250.3 tenant gate may have "
                f"rejected it. Sync body: {sync_body}"
            )
            created_assets.append(listed[0]["id"])
        finally:
            if connection_id:
                with contextlib.suppress(Exception):
                    authenticated_session.delete(
                        f"{base_url}{MARKETPLACE_CONNECTIONS_PATH}{connection_id}/",
                        timeout=timeout,
                    )
            with contextlib.suppress(Exception):
                requests.post(
                    f"{CKAN_TEST_URL}/api/3/action/package_delete",
                    json={"id": package_name},
                    headers=ckan_headers,
                    timeout=timeout,
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
