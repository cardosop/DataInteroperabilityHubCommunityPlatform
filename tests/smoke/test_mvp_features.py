"""
Smoke checks for MVP API surface (real HTTP — no mocks).

MVP feature entry paths must not return 404 (401/403/405 are acceptable).

When the deployment runs with MVP_MODE=true, non-MVP areas must return 404.
Enable those assertions by setting SMOKE_EXPECT_MVP_MODE=1 (or true/yes), or rely on
deploy workflow for staging (see .github/workflows/deploy.yml smoke job env).
"""

from __future__ import annotations

import os

import pytest
import requests

# Shallowest list-style paths that should exist for each MVP area (aligned with hub.apps.api.urls).
MVP_FEATURE_PATHS: dict[str, str] = {
    "auth": "/api/v1/auth/login/",
    "contracts": "/api/v1/contracts/",
    "assets": "/api/v1/assets/",
    "dq": "/api/v1/dq/runs/",
    "compliance": "/api/v1/compliance/runs/",
    "governance": "/api/v1/governance/certifications/",
    "files": "/api/v1/files/",
    "semantic": "/api/v1/semantic/semantic-resources/",
    "marketplace": "/api/v1/marketplace/",
}

# Blocked by MvpModeApiGateMiddleware when MVP_MODE=true (hub.tests.test_mvp_mode).
GATED_MVP_OFF_PATHS: tuple[str, ...] = (
    "/api/v1/mesh/domains/",
    "/api/v1/virtualization/datasets/",
    "/api/v1/integrations/marketplace/connectors/",
    "/api/v1/baas/api-keys/",
    "/api/v1/ml/models/",
    "/api/v1/ai/natural-language-search/",
    "/api/v1/transformation/pipelines/",
    "/api/v1/social/communities/",
    "/api/v1/scheduled-ingestions/",
    "/api/v1/scheduled-exports/",
)


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


class TestMvpFeatureSmoke:
    def test_mvp_feature_roots_not_404(
        self,
        base_url: str,
        api_session: requests.Session,
        timeout: int,
    ) -> None:
        """Each MVP feature exposes at least one route that is not a framework 404."""
        for name, path in MVP_FEATURE_PATHS.items():
            url = f"{base_url}{path}"
            response = api_session.get(url, timeout=timeout)
            assert response.status_code not in (404, 500, 502, 503), (
                f"{name} smoke path {path} returned {response.status_code} — "
                f"body snippet: {response.text[:200]!r}"
            )

    @pytest.mark.e2e
    @pytest.mark.skipif(
        not _truthy_env("SMOKE_EXPECT_MVP_MODE"),
        reason="Set SMOKE_EXPECT_MVP_MODE=1 when the target API runs with MVP_MODE=true",
    )
    def test_gated_areas_return_404_when_mvp_mode(
        self,
        base_url: str,
        api_session: requests.Session,
        timeout: int,
    ) -> None:
        """Non-MVP prefixes must be hidden (404) on MVP deployments."""
        for path in GATED_MVP_OFF_PATHS:
            url = f"{base_url}{path}"
            response = api_session.get(url, timeout=timeout)
            assert response.status_code == 404, (
                f"Expected 404 for gated path {path} on MVP deployment, got {response.status_code}"
            )
