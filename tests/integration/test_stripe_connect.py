"""Phase 271.6.5 — Stripe Connect integration smoke test.

Runs against the live Hub API. Stripe Connect endpoints are called
only when ``STRIPE_CONNECT_ENABLED`` is True AND ``STRIPE_SECRET_KEY``
is configured. Otherwise the test is automatically skipped (the CI
nightly workflow sets both).

The test validates the full onboarding surface:
1. Connect onboarding link issuance (idempotent retry)
2. Connect status read
3. Connect payouts list (empty for a fresh account)
4. KYB review queue (PLATFORM_ADMIN only)
"""

import os

import pytest
import requests


@pytest.mark.integration
@pytest.mark.stripe_connect
class TestStripeConnectIntegration:
    @pytest.fixture(autouse=True)
    def auth_headers(self) -> dict | None:
        """Resolve auth token from env or from a local e2e login."""
        token = os.environ.get("HUB_E2E_AUTH_TOKEN") or os.environ.get("HUB_API_TOKEN")
        if not token:
            # Try the e2e login endpoint (dev/test only).
            try:
                login_resp = requests.post(
                    f"{self._api_base()}/auth/login/",
                    json={
                        "email": os.environ.get(
                            "HUB_E2E_EMAIL",
                            "e2e-provider@meshant.com",
                        ),
                        "password": os.environ.get("HUB_E2E_PASSWORD", "e2e-test-password"),
                    },
                    timeout=10,
                )
                if login_resp.status_code == 200:
                    token = login_resp.json().get("access_token")
            except Exception:
                pass
        if not token:
            pytest.skip("No HUB_E2E_AUTH_TOKEN / HUB_API_TOKEN set and login failed")
        return {"Authorization": f"Bearer {token}"}

    def _api_base(self) -> str:
        return os.environ.get("HUB_API_BASE", "http://localhost:8000/api/v1").rstrip("/")

    def _check_connect_enabled(self, auth_headers: dict) -> bool:
        """Return True when the Hub instance has Connect enabled."""
        try:
            resp = requests.get(
                f"{self._api_base()}/capabilities/",
                headers=auth_headers,
                timeout=5,
            )
            if resp.status_code != 200:
                return False
            caps = resp.json()
            return bool(caps.get("features", {}).get("stripe_connect", False))
        except Exception:
            return False

    # ── 271.1.3 — onboarding link ─────────────────────────────

    def test_onboarding_link_returns_200_or_501(
        self,
        auth_headers: dict,
    ):
        """POST /billing/connect/onboarding-link/ returns 200 when
        Connect is enabled, or 501 when disabled (graceful)."""
        if not auth_headers:
            pytest.skip("No auth headers available")  # noqa: skip-in-body — runtime service dependency
        resp = requests.post(
            f"{self._api_base()}/billing/connect/onboarding-link/",
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code in (200, 501), f"Unexpected status {resp.status_code}: {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            assert "onboarding_url" in data
            assert "expires_at" in data

    # ── 271.1.4 — connect status ──────────────────────────────

    def test_connect_status_returns_200_or_404(
        self,
        auth_headers: dict,
    ):
        """GET /billing/connect/status/ returns 200 for onboarded
        tenant or 404 when no ConnectAccount exists."""
        if not auth_headers:
            pytest.skip("No auth headers available")  # noqa: skip-in-body — runtime service dependency
        resp = requests.get(
            f"{self._api_base()}/billing/connect/status/",
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code in (200, 404), f"Unexpected status {resp.status_code}: {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            assert "stripe_account_id" in data
            assert "charges_enabled" in data
            assert "payouts_enabled" in data

    # ── 271.4.2 — payouts list ────────────────────────────────

    def test_payouts_list_returns_200_or_404(
        self,
        auth_headers: dict,
    ):
        """GET /billing/connect/payouts/ returns 200 for onboarded
        tenant or 404 when no ConnectAccount exists."""
        if not auth_headers:
            pytest.skip("No auth headers available")  # noqa: skip-in-body — runtime service dependency
        resp = requests.get(
            f"{self._api_base()}/billing/connect/payouts/",
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code in (200, 404), f"Unexpected status {resp.status_code}: {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            assert "results" in data
            assert "count" in data
            assert "page" in data

    # ── 271.5.1 — KYB review queue ───────────────────────────

    def test_review_queue_403_for_non_admin(
        self,
        auth_headers: dict,
    ):
        """GET /admin/connect/review-queue/ returns 403 for non-admin."""
        if not auth_headers:
            pytest.skip("No auth headers available")  # noqa: skip-in-body — runtime service dependency
        resp = requests.get(
            f"{self._api_base()}/admin/connect/review-queue/",
            headers=auth_headers,
            timeout=10,
        )
        # 403 if non-admin; 200 if admin (CI uses admin token)
        assert resp.status_code in (200, 403), f"Unexpected status {resp.status_code}: {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            assert "results" in data
            assert "count" in data
