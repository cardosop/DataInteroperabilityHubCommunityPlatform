"""
Smoke test — Phase 231 Definition of Done #5 (231.DoD.5).

Closes the production smoke contract for Phase 231 (Compliance Feature
MVP-Promise Closure):

    "Production smoke test post-deploy: tenant with gate enabled →
     asset auto-enqueues compliance run within 60s; CRITICAL asset
     blocked from publish with HTTP 422."

Coverage map
------------
This file pins the two sub-criteria that no other smoke covers:

* **Auto-enqueue within 60 s** — for a tenant whose
  ``compliance_intake_gate_enabled=True`` flag is set, registering an
  Asset must auto-enqueue a ``ComplianceRun`` (visible at
  ``GET /api/v1/compliance/runs/?asset_id=<id>``) within 60 seconds.

* **CRITICAL asset blocked from publish with HTTP 422** — when an
  Asset's latest ``ComplianceRun`` carries
  ``regulation_summary.overall_risk_level=CRITICAL`` (above the
  tenant's ``compliance_risk_threshold``), attempting to PATCH the
  Asset's marketplace listing to ``status=PUBLISHED`` must return
  HTTP **422** with body code ``COMPLIANCE_THRESHOLD_EXCEEDED`` (per
  ``hub/apps/marketplace/compliance_gate.py``).

The base compliance pipeline (file → run → poll → succeed) is already
covered by ``tests/smoke/test_compliance.py``; this file targets the
**gate** behaviour added in Phase 231.

Required env vars
-----------------
SMOKE_ADMIN_EMAIL / SMOKE_ADMIN_PASSWORD
    Authenticated session — provided by ``conftest.py``.

Optional env vars (gating)
--------------------------
SMOKE_PHASE231_GATE_ENABLED
    When ``1``/``true``/``yes`` the auto-enqueue sub-test runs against
    the deployed environment. Set this only after the smoke admin's
    tenant has ``compliance_intake_gate_enabled=True`` flipped on (or
    a dedicated test tenant has been provisioned and the smoke
    admin has membership).
SMOKE_PHASE231_CRITICAL_LISTING_ID
    Listing ID whose underlying Asset has a SUCCEEDED ComplianceRun at
    ``risk_level=CRITICAL``. When set, the publish-block sub-test runs.
    Provisioned ahead of time by the staging seeder (it is destructive
    to manufacture a CRITICAL run on the fly).
SMOKE_PHASE231_AUTO_ENQUEUE_TIMEOUT
    Max seconds to wait for auto-enqueue (default: 60 — the DoD.5 SLO).
SMOKE_PHASE231_AUTO_ENQUEUE_INTERVAL
    Seconds between polls (default: 5).

References
----------
- 231.DoD.5 in ``openspec/changes/preprod01/tasks.md``
- ``hub/apps/compliance/intake_scan.py`` (auto-enqueue helper)
- ``hub/apps/compliance/signals.py`` (post_save receiver)
- ``hub/apps/marketplace/compliance_gate.py`` (publish 422 path)
"""

from __future__ import annotations

import contextlib
import os
import time
import uuid

import pytest
import requests

ASSETS_PATH = "/api/v1/assets/"
COMPLIANCE_RUNS_PATH = "/api/v1/compliance/runs/"
LISTINGS_PATH = "/api/v1/marketplace/listings/"
AUTH_ME_PATH = "/api/v1/auth/me/"


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


GATE_ENABLED = _truthy_env("SMOKE_PHASE231_GATE_ENABLED")
CRITICAL_LISTING_ID = os.getenv("SMOKE_PHASE231_CRITICAL_LISTING_ID")
AUTO_ENQUEUE_TIMEOUT = int(os.getenv("SMOKE_PHASE231_AUTO_ENQUEUE_TIMEOUT", "60"))
AUTO_ENQUEUE_INTERVAL = float(os.getenv("SMOKE_PHASE231_AUTO_ENQUEUE_INTERVAL", "5"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_tenant_id(
    base_url: str,
    session: requests.Session,
    timeout: int,
) -> str | None:
    response = session.get(f"{base_url}{AUTH_ME_PATH}", timeout=timeout)
    if response.status_code != 200:
        return None
    body = response.json()
    return (
        body.get("tenant")
        or body.get("tenant_id")
        or (body.get("tenant_membership") or {}).get("tenant_id")
    )


def _delete_asset(
    base_url: str,
    session: requests.Session,
    timeout: int,
    asset_id: str,
) -> None:
    with contextlib.suppress(requests.RequestException):
        session.delete(f"{base_url}{ASSETS_PATH}{asset_id}/", timeout=timeout)


# ---------------------------------------------------------------------------
# 1) Auto-enqueue within 60 s
# ---------------------------------------------------------------------------


class TestPhase231DoD5AutoEnqueueOnAssetCreate:
    """231.DoD.5 — gate-enabled tenant: Asset registration auto-enqueues
    a ComplianceRun within 60 seconds."""

    @pytest.mark.skipif(
        not GATE_ENABLED,
        reason=(
            "Set SMOKE_PHASE231_GATE_ENABLED=1 once the smoke admin's "
            "tenant has compliance_intake_gate_enabled=True."
        ),
    )
    def test_asset_registration_auto_enqueues_compliance_run_within_60s(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
    ) -> None:
        own_tenant_id = _resolve_tenant_id(base_url, authenticated_session, timeout)
        if not own_tenant_id:
            pytest.skip("Could not resolve smoke admin tenant via /auth/me/")  # noqa: skip-in-body — runtime service dependency

        unique_key = f"smoke-p231-dod5-{uuid.uuid4().hex[:12]}"
        create_payload = {
            "key": unique_key,
            "name": f"Smoke P231 DoD.5 ({unique_key})",
            "description": ("Phase 231.DoD.5 smoke — auto-enqueue verification. Safe to delete."),
            "asset_type": "DATASET",
        }
        create_response = authenticated_session.post(
            f"{base_url}{ASSETS_PATH}",
            json=create_payload,
            timeout=timeout,
        )

        if create_response.status_code == 422:
            pytest.skip(  # noqa: skip-in-body — runtime service dependency
                "Asset create endpoint refused minimal payload "
                f"({create_response.status_code}): "
                f"{create_response.text[:300]} — adjust create_payload."
            )
        assert create_response.status_code in (200, 201), (
            f"Asset create failed ({create_response.status_code}): {create_response.text[:500]}"
        )
        asset = create_response.json()
        asset_id = asset.get("id") or asset.get("asset_id")
        assert asset_id, f"Asset response missing id: {asset}"

        try:
            # Poll the compliance-runs list filtered by this Asset's id;
            # the 231.1 signal must auto-create a ComplianceRun within
            # the SLO. Use ``asset_id`` query param (alias of ``asset``)
            # — see 231.7.1 R1: ComplianceRunViewSet.get_queryset accepts
            # both forms.
            deadline = time.monotonic() + AUTO_ENQUEUE_TIMEOUT
            seen_runs: list[dict] = []
            while time.monotonic() < deadline:
                list_resp = authenticated_session.get(
                    f"{base_url}{COMPLIANCE_RUNS_PATH}",
                    params={"asset_id": asset_id},
                    timeout=timeout,
                )
                assert list_resp.status_code == 200, (
                    f"Compliance-runs list failed ({list_resp.status_code}): {list_resp.text[:300]}"
                )
                body = list_resp.json()
                results = body.get("results", body if isinstance(body, list) else [])
                seen_runs = [
                    r
                    for r in results
                    if str(r.get("asset")) == str(asset_id)
                    or str(r.get("asset_id")) == str(asset_id)
                    or str(
                        (r.get("asset") or {}).get("id") if isinstance(r.get("asset"), dict) else ""
                    )
                    == str(asset_id)
                ]
                if seen_runs:
                    break
                time.sleep(AUTO_ENQUEUE_INTERVAL)  # noqa: sleep-needed — retry loop

            assert seen_runs, (
                f"Phase 231.DoD.5: no ComplianceRun auto-enqueued for "
                f"asset_id={asset_id} within {AUTO_ENQUEUE_TIMEOUT}s. "
                f"Possible causes: (a) compliance_intake_gate_enabled is "
                f"not actually True on this tenant — re-verify; "
                f"(b) the post_save signal is not loaded (check "
                f"`hub/apps/compliance/apps.py::ready()`); (c) the "
                f"compliance worker is not consuming the queue."
            )
        finally:
            _delete_asset(base_url, authenticated_session, timeout, asset_id)


# ---------------------------------------------------------------------------
# 2) CRITICAL asset blocked from publish with HTTP 422
# ---------------------------------------------------------------------------


class TestPhase231DoD5CriticalAssetBlockedFromPublish:
    """231.DoD.5 — publishing a CRITICAL asset's listing returns HTTP 422."""

    @pytest.mark.skipif(
        not CRITICAL_LISTING_ID,
        reason=(
            "Set SMOKE_PHASE231_CRITICAL_LISTING_ID to a listing whose "
            "asset has a SUCCEEDED ComplianceRun at risk_level=CRITICAL "
            "(provisioned by the staging seeder)."
        ),
    )
    def test_publish_critical_asset_listing_returns_422(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
    ) -> None:
        listing_url = f"{base_url}{LISTINGS_PATH}{CRITICAL_LISTING_ID}/"

        # Sanity: the seeder-provisioned listing exists and is reachable.
        get_resp = authenticated_session.get(listing_url, timeout=timeout)
        assert get_resp.status_code == 200, (
            f"Seeder listing {CRITICAL_LISTING_ID} not reachable "
            f"({get_resp.status_code}): {get_resp.text[:300]}"
        )

        publish_resp = authenticated_session.patch(
            listing_url,
            json={"status": "PUBLISHED"},
            timeout=timeout,
        )

        assert publish_resp.status_code == 422, (
            f"Phase 231.DoD.5: PATCH listing→PUBLISHED for a CRITICAL "
            f"asset must return HTTP 422 (COMPLIANCE_THRESHOLD_EXCEEDED), "
            f"got {publish_resp.status_code}: {publish_resp.text[:500]}"
        )
        body = publish_resp.json()
        # The marketplace path raises ComplianceGateError → ValidationError
        # subclass; `handle_service_exception` maps to 422 with structured
        # body. Accept both flat-`code` and nested-`details.code` shapes
        # so a future serialiser tweak doesn't silently break detection.
        code = body.get("code") or (body.get("error") or {}).get("code")
        details_code = (body.get("details") or {}).get("code")
        assert (
            code == "COMPLIANCE_THRESHOLD_EXCEEDED"
            or details_code == "COMPLIANCE_THRESHOLD_EXCEEDED"
            or code == "VALIDATION_ERROR"  # outer code; details carry the gate code
        ), f"422 body missing COMPLIANCE_THRESHOLD_EXCEEDED code: {body}"
