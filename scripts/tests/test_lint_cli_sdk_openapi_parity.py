"""Tests for CLI/SDK ↔ OpenAPI parity lint script (277.B.083)."""

import tempfile
from pathlib import Path

from scripts.lint_cli_sdk_openapi_parity import (
    _RE_CLI_FSTRING,
    _RE_CLI_PATH,
    _RE_JS_SDK_PATH,
    _RE_JS_TEMPLATE,
    _RE_PY_FSTRING,
    _RE_PY_SDK_PATH,
    _extract_js_paths,
    _extract_paths_from_source,
    _is_excluded,
    _is_mvp_gated,
    _normalize_sdk_path,
    _should_report_missing,
)


class TestPathExtractionCLI:
    """Extract endpoint paths from CLI source code."""

    def test_extracts_get_path(self):
        code = 'api_client.get("assets/", params=params)'
        matches = _RE_CLI_PATH.findall(code)
        assert "assets/" in matches, f"Got: {matches}"

    def test_extracts_post_path(self):
        code = 'api_client.post("compliance/runs/", json=payload)'
        matches = _RE_CLI_PATH.findall(code)
        assert "compliance/runs/" in matches

    def test_extracts_patch_path(self):
        code = 'api_client.patch(f"assets/{asset_id}/", data=body)'
        matches = _RE_CLI_PATH.findall(code)
        assert "assets/" in matches

    def test_extracts_delete_path(self):
        code = 'api_client.delete("webhooks/webhooks/some-id/")'
        matches = _RE_CLI_PATH.findall(code)
        assert "webhooks/webhooks/some-id/" in matches

    def test_extracts_fstring_with_interpolation(self):
        code = 'api_client.get(f"assets/{asset_id}/activate/")'
        matches = _RE_CLI_FSTRING.findall(code)
        assert "assets/" in matches

    def test_extracts_single_quoted_path(self):
        code = "api_client.get('contracts/', params=p)"
        matches = _RE_CLI_PATH.findall(code)
        assert "contracts/" in matches

    def test_ignores_non_api_strings(self):
        code = 'click.echo("assets/")'
        matches = _RE_CLI_PATH.findall(code)
        assert len(matches) == 0

    def test_multiple_paths_in_one_file(self):
        code = """
        api_client.get("assets/")
        api_client.post("contracts/", json=body)
        api_client.delete("files/some-file/")
        """
        matches = _RE_CLI_PATH.findall(code)
        assert len(matches) == 3

    def test_full_extraction_from_source_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "commands"
            src.mkdir()
            (src / "test_cmd.py").write_text("""
import click
from ..api_client import api_client

@click.command()
def list_things():
    api_client.get("assets/", params={})
    api_client.post("contracts/", json={})
    api_client.patch(f"assets/{asset_id}/", data={})
    api_client.delete(f"contracts/{contract_id}/")
""")
            paths = _extract_paths_from_source(src, _RE_CLI_PATH, _RE_CLI_FSTRING)
            assert "assets/" in paths
            assert "contracts/" in paths
            assert any("assets/" in p for p in paths)
            assert any("contracts/" in p for p in paths)


class TestPathExtractionPySDK:
    """Extract endpoint paths from Python SDK source code."""

    def test_extracts_self_client_get(self):
        code = 'return self.client.get("assets/", {params})'
        matches = _RE_PY_SDK_PATH.findall(code)
        assert "assets/" in matches

    def test_extracts_self_client_post(self):
        code = 'return self.client.post("baas/api-keys/", data)'
        matches = _RE_PY_SDK_PATH.findall(code)
        assert "baas/api-keys/" in matches

    def test_extracts_fstring(self):
        code = 'return self.client.get(f"assets/{id}/")'
        matches = _RE_PY_FSTRING.findall(code)
        assert "assets/" in matches

    def test_ignores_non_client_calls(self):
        code = 'print("assets/")'
        matches = _RE_PY_SDK_PATH.findall(code)
        assert len(matches) == 0


class TestPathExtractionJSSDK:
    """Extract endpoint paths from JS SDK source code."""

    def test_extracts_this_client_get(self):
        code = "return this.client.get('assets/', { params });"
        matches = _RE_JS_SDK_PATH.findall(code)
        assert "assets/" in matches

    def test_extracts_this_client_post(self):
        code = 'return this.client.post("compliance/runs/", data);'
        matches = _RE_JS_SDK_PATH.findall(code)
        assert "compliance/runs/" in matches

    def test_extracts_template_literal(self):
        code = "return this.client.get(`assets/${id}/`);"
        matches = _RE_JS_TEMPLATE.findall(code)
        assert "assets/" in matches

    def test_full_extraction_from_source_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            (src / "test_api.ts").write_text(r"""
import { DataHubClient } from './client';

export class TestAPI {
  private client: DataHubClient;
  constructor(client: DataHubClient) { this.client = client; }

  async list(): Promise<any> {
    return this.client.get('assets/', { params });
  }
  async get(id: string): Promise<any> {
    return this.client.get(`assets/\${id}/`);
  }
  async create(data: any): Promise<any> {
    return this.client.post('contracts/', data);
  }
  async remove(id: string): Promise<any> {
    return this.client.delete(`webhooks/webhooks/\${id}/`);
  }
}
""")
            paths = _extract_js_paths(src)
            assert "assets/" in paths
            assert "contracts/" in paths
            assert "webhooks/webhooks/" in paths


class TestPathNormalization:
    """Path normalization for OpenAPI comparison."""

    def test_replaces_asset_id(self):
        assert _normalize_sdk_path("assets/{asset_id}/") == "assets/{id}/"

    def test_replaces_contract_id(self):
        assert _normalize_sdk_path("contracts/{contract_id}/") == "contracts/{id}/"

    def test_preserves_trailing_slash(self):
        assert _normalize_sdk_path("assets") == "assets/"

    def test_no_double_slash(self):
        assert _normalize_sdk_path("assets/") == "assets/"

    def test_multiple_variables(self):
        result = _normalize_sdk_path("contracts/{contract_id}/fields/{field_id}/")
        assert "{id}" in result


class TestGatingAndExclusion:
    """MVP gating and path exclusion logic."""

    def test_mvp_gated_prefixes_are_recognized(self):
        assert _is_mvp_gated("mesh/clusters/")
        assert _is_mvp_gated("baas/api-keys/")
        assert _is_mvp_gated("ml/models/")
        assert not _is_mvp_gated("assets/")
        assert not _is_mvp_gated("contracts/")

    def test_excluded_prefixes_are_recognized(self):
        assert _is_excluded("admin/tenants/")
        assert _is_excluded("internal/runs/")
        assert _is_excluded("health/")
        assert _is_excluded("auth/login/")
        assert not _is_excluded("assets/")

    def test_should_report_missing_excludes_gated_and_excluded(self):
        assert not _should_report_missing("mesh/clusters/")  # MVP-gated
        assert not _should_report_missing("admin/tenants/")  # excluded
        assert _should_report_missing("assets/")  # reportable
        assert _should_report_missing("contracts/")  # reportable
