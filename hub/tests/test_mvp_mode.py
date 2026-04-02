"""
Phase 200 — MVP_MODE: middleware blocks non-MVP /api/v1 prefixes; OpenAPI omits them.

URLconf keeps all routes mounted so Django settings reloads (e.g.
``@override_settings``) do not leave a stale, trimmed URLconf in sys.modules.
"""

from __future__ import annotations

import pytest
from django.test import Client, override_settings
from rest_framework import status


pytestmark = pytest.mark.mvp


@pytest.fixture
def api_client() -> Client:
    return Client()


@pytest.mark.django_db
class TestMvpModeMiddlewareAndOpenAPI:
    """Gated 404s via middleware; OpenAPI paths stripped when MVP_MODE is on."""

    @override_settings(MVP_MODE=True)
    def test_gated_paths_return_404(self, api_client: Client) -> None:
        for path in (
            "/api/v1/mesh/domains/",
            "/api/v1/virtualization/datasets/",
            "/api/v1/integrations/marketplace/connectors/",
            "/api/v1/baas/api-keys/",
            "/api/v1/ml/models/",
            "/api/v1/ai/natural-language-search/",
            "/api/v1/transformation/pipelines/",
            "/api/v1/social/communities/",
        ):
            r = api_client.get(path)
            assert r.status_code == status.HTTP_404_NOT_FOUND, path

    @override_settings(MVP_MODE=True)
    def test_mvp_core_paths_not_404(self, api_client: Client) -> None:
        for path in (
            "/api/v1/contracts/",
            "/api/v1/assets/",
            "/api/v1/marketplace/",
            "/api/v1/scheduled-ingestions/",
            "/api/v1/scheduled-exports/",
            "/api/v1/webhooks/",
        ):
            r = api_client.get(path)
            assert r.status_code != status.HTTP_404_NOT_FOUND, (
                path,
                r.status_code,
            )

    @override_settings(MVP_MODE=True)
    def test_openapi_json_omits_gated_prefixes(
        self, api_client: Client
    ) -> None:
        r = api_client.get("/api/v1/openapi.json")
        assert r.status_code == status.HTTP_200_OK
        data = r.json()
        paths = data.get("paths") or {}
        keys = " ".join(paths.keys())
        assert "mesh" not in keys.lower()
        assert "/api/v1/ai/" not in keys
        assert "social" not in keys.lower()

    @override_settings(MVP_MODE=False)
    def test_mesh_reachable_when_mvp_off(self, api_client: Client) -> None:
        r = api_client.get("/api/v1/mesh/domains/")
        assert r.status_code != status.HTTP_404_NOT_FOUND


class TestMvpModeHelpers:
    """Pure helpers (no DB)."""

    def test_openapi_path_detection(self) -> None:
        from hub.apps.api.mvp_mode import openapi_path_is_mvp_gated

        assert openapi_path_is_mvp_gated("/api/v1/mesh/domains/")
        assert openapi_path_is_mvp_gated("/mesh/domains/")
        assert openapi_path_is_mvp_gated("mesh/domains/")
        assert not openapi_path_is_mvp_gated("/api/v1/contracts/")
        assert not openapi_path_is_mvp_gated("/contracts/")
