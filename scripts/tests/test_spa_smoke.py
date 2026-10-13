"""
Contract tests for scripts/spa_smoke.py (pilot-readiness 1.6).

The SPA smoke verifies a PRODUCTION frontend build the way a browser's
first load would: a real stdlib HTTP server serves the real dist output,
the smoke fetches index.html, asserts the SPA shell, fetches every
referenced asset (a missing chunk must fail), and checks that the
VITE_API_BASE_URL literal is baked into the JS bundle (the U.8 trap —
a build made without the right API base silently points the pilot SPA at
the wrong API). No mocks: real files, real HTTP.
"""

import importlib.util
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "spa_smoke.py"
spec = importlib.util.spec_from_file_location("spa_smoke", script_path)
spa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spa)


def _make_dist(tmp_path, *, index="default", assets=None, baked_base="/api/v1"):
    """A real minimal vite-style dist output on disk.

    Uses the repo's REAL layout (assetsDir=static — frontend/dist/static)
    so the smoke cannot regress into assuming vite's default /assets/.
    """
    dist = tmp_path / "dist"
    (dist / "static").mkdir(parents=True)
    if index == "default":
        index_html = (
            '<!doctype html><html><head>'
            '<script type="module" crossorigin src="/static/app-abc.js"></script>'
            '<link rel="stylesheet" href="/static/app-abc.css">'
            "</head><body><div id=\"root\"></div></body></html>"
        )
    elif index == "no-root":
        index_html = "<!doctype html><html><body>nothing</body></html>"
    else:
        raise ValueError(index)
    (dist / "index.html").write_text(index_html)
    assets = assets or {}
    # vite bakes import.meta.env values as JSON-quoted literals — the
    # fixture mirrors that form so the exact-quoted check sees the real
    # shape (an unquoted bake is not what vite emits).
    js = assets.get("app-abc.js", f'const B="{baked_base}";export default B;')
    css = assets.get("app-abc.css", "body{margin:0}")
    if js is not None:
        (dist / "static" / "app-abc.js").write_text(js)
    if css is not None:
        (dist / "static" / "app-abc.css").write_text(css)
    return dist


class TestDistInspection:
    def test_shell_assertion_passes_with_root_div(self, tmp_path):
        dist = _make_dist(tmp_path)
        index_text = (dist / "index.html").read_text()
        assert spa.assert_shell(index_text) == []

    def test_shell_assertion_fails_without_root_div(self, tmp_path):
        dist = _make_dist(tmp_path, index="no-root")
        index_text = (dist / "index.html").read_text()
        violations = spa.assert_shell(index_text)
        assert violations
        assert "root" in violations[0].lower()

    def test_asset_extraction_finds_js_and_css(self, tmp_path):
        dist = _make_dist(tmp_path)
        assets = spa.extract_assets((dist / "index.html").read_text())
        assert "/static/app-abc.js" in assets
        assert "/static/app-abc.css" in assets

    def test_api_base_literal_is_baked_in_js(self, tmp_path):
        dist = _make_dist(tmp_path, baked_base="/api/v1")
        assert spa.api_base_baked((dist / "index.html").read_text(), dist, "/api/v1")

    def test_wrong_api_base_is_detected(self, tmp_path):
        dist = _make_dist(tmp_path, baked_base="/api/v1")
        assert not spa.api_base_baked((dist / "index.html").read_text(), dist, "https://api.example.com/api/v1")

    def test_a_wrong_absolute_base_is_not_a_substring_pass(self, tmp_path):
        # Q1 (W0.10): a bundle baked with the WRONG absolute base
        # ("https://staging.example.com/api/v1") contains "/api/v1" as a
        # substring — the vacuous check passes it. Only the EXACT quoted
        # literal may count.
        dist = _make_dist(tmp_path, baked_base="https://staging.example.com/api/v1")
        assert not spa.api_base_baked((dist / "index.html").read_text(), dist, "/api/v1"), (
            "the baked check passed on a substring of a WRONG absolute "
            "base — the exact quoted literal is the only valid signal"
        )

    def test_an_unreferenced_js_file_is_not_a_pass(self, tmp_path):
        # Q1 (W0.10): a leftover file anywhere in dist must not satisfy
        # the check — only the assets index.html actually references can.
        dist = _make_dist(tmp_path, baked_base="https://wrong.example/api/v1")
        (dist / "static" / "stale-old-build.js").write_text(
            'const B="/api/v1";export default B;'
        )
        assert not spa.api_base_baked((dist / "index.html").read_text(), dist, "/api/v1"), (
            "the baked check passed via a file index.html never loads — "
            "stale build litter masks a wrong entry bundle"
        )


class TestRealHttpSmoke:
    def test_well_formed_dist_passes_end_to_end(self, tmp_path):
        dist = _make_dist(tmp_path)
        violations = spa.smoke_dist(dist, api_base="/api/v1")
        assert violations == []

    def test_missing_asset_fails(self, tmp_path):
        dist = _make_dist(tmp_path, assets={"app-abc.js": None})
        violations = spa.smoke_dist(dist, api_base="/api/v1")
        assert any("app-abc.js" in v for v in violations)

    def test_missing_index_fails(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        violations = spa.smoke_dist(dist, api_base=None)
        assert any("index.html" in v for v in violations)

    def test_wrong_api_base_fails_via_http(self, tmp_path):
        dist = _make_dist(tmp_path, baked_base="/api/v1")
        violations = spa.smoke_dist(dist, api_base="https://wrong.example/api/v1")
        assert any("VITE_API_BASE_URL" in v for v in violations)

    def test_served_response_reports_content_type(self, tmp_path):
        dist = _make_dist(tmp_path)
        with spa.serve(dist) as base:
            import urllib.request

            with urllib.request.urlopen(f"{base}/") as resp:
                assert resp.status == 200
                assert resp.headers["Content-Type"].startswith("text/html")
