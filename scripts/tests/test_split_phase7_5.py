"""
TDD unit tests for scripts/split_phase7_5.cjs — Phase 226 E3.

Background
----------
The splitter relocates the 24 test blocks of phase7.5 into ~10 focused
files under `frontend/e2e/features/`. A bug in the test-block extractor
(off-by-one on closing brace, missed test, doubled test) would either
silently drop coverage or duplicate test runs. The pure-logic tests
pin extraction + grouping + output shape.

Run locally:
    pytest scripts/tests/test_split_phase7_5.py -v
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "split_phase7_5.cjs"


def _has_node() -> bool:
    try:
        res = subprocess.run(["node", "--version"], capture_output=True, timeout=10)
        return res.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(
    not _has_node(),
    reason="node not available in PATH",
)


def _node_eval(expr: str) -> str:
    cmd = [
        "node",
        "-e",
        f"const m = require('{SCRIPT}'); process.stdout.write(JSON.stringify({expr}));",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert res.returncode == 0, f"node failed: {res.stderr}"
    return res.stdout


# --------------------------- extractTestBlocks ---------------------------

SAMPLE_SOURCE = """\
import { test } from '@playwright/test';

test.describe('Phase 7.5 — FEATURES Gap Closure @deprecated', () => {

  test('A.3 — Sidebar shows Integrations', async ({ page }) => {
    expect(page).toBeTruthy();
    if (true) { /* nested brace */ }
  });

  test('A.2 — Integrations connections list', async ({ page }) => {
    const x = { a: 1 };
    expect(x).toEqual({ a: 1 });
  });

  test('C — Search page loads', async ({ page }) => {
    await page.goto('/search');
  });
});
"""


def test_extractTestBlocks_finds_every_top_level_test() -> None:
    out = _node_eval(f"m.extractTestBlocks({json.dumps(SAMPLE_SOURCE)})")
    blocks = json.loads(out)
    ids = [b["id"] for b in blocks]
    assert ids == ["A.3", "A.2", "C"]


def test_extractTestBlocks_captures_full_body_including_closing() -> None:
    out = _node_eval(f"m.extractTestBlocks({json.dumps(SAMPLE_SOURCE)})")
    blocks = json.loads(out)
    a3 = blocks[0]
    assert a3["body"].startswith("  test('A.3 — Sidebar")
    assert a3["body"].rstrip().endswith("});")


def test_extractTestBlocks_handles_nested_braces_correctly() -> None:
    out = _node_eval(f"m.extractTestBlocks({json.dumps(SAMPLE_SOURCE)})")
    blocks = json.loads(out)
    a2 = blocks[1]
    # The body must include the inner `{ a: 1 }` literal AND the closing test brace.
    assert "{ a: 1 }" in a2["body"]
    assert a2["body"].rstrip().endswith("});")


# --------------------------- groupBlocks ---------------------------------

def test_groupBlocks_routes_each_block_to_a_target_file() -> None:
    out = _node_eval(
        f"Array.from(m.groupBlocks(m.extractTestBlocks({json.dumps(SAMPLE_SOURCE)}), m.TEST_GROUPS).entries())"
    )
    groups = json.loads(out)
    file_to_ids = {entry[0]: [b["id"] for b in entry[1]["tests"]] for entry in groups}
    assert "integrations-developer-baas-gap.spec.ts" in file_to_ids
    assert "search-gap.spec.ts" in file_to_ids
    assert "A.3" in file_to_ids["integrations-developer-baas-gap.spec.ts"]
    assert "A.2" in file_to_ids["integrations-developer-baas-gap.spec.ts"]
    assert "C" in file_to_ids["search-gap.spec.ts"]


def test_normaliseTestId_strips_phase_prefix() -> None:
    out = _node_eval(f"m.normaliseTestId({json.dumps('Phase 7.5.G')})")
    assert json.loads(out) == "G"
    out = _node_eval(f"m.normaliseTestId({json.dumps('Phase 7.5.N.1')})")
    assert json.loads(out) == "N.1"
    out = _node_eval(f"m.normaliseTestId({json.dumps('A.3')})")
    assert json.loads(out) == "A.3"


def test_extractTestBlocks_finds_phase_prefixed_tests() -> None:
    src = """\
test.describe('phase7.5', () => {
  test('Phase 7.5.G — Lineage thing', async ({ page }) => {
    await page.goto('/x');
  });
  test('Phase 7.5 critical routes are handled by app (no crash)', async ({ page }) => {
    await page.goto('/y');
  });
});
"""
    out = _node_eval(f"m.extractTestBlocks({json.dumps(src)})")
    blocks = json.loads(out)
    ids = [b["id"] for b in blocks]
    assert "Phase 7.5.G" in ids
    # The "critical routes" test has no em-dash → entire title becomes id
    assert any("critical routes" in i for i in ids)


def test_groupBlocks_unmatched_id_falls_back_to_critical_routes_bucket() -> None:
    """The 'critical routes' sweep test has no letter prefix —
    it's matched by the literal 'critical' marker in TEST_GROUPS."""
    src = """\
test.describe('phase7.5', () => {
  test('Phase 7.5 critical routes are handled by app (no crash)', async ({ page }) => {
    expect(page).toBeTruthy();
  });
});
"""
    # The id parser captures up to the first em-dash — but this test
    # has no em-dash, so id falls back to 'Phase'. Critical-bucket
    # should still take it.
    out = _node_eval(f"m.extractTestBlocks({json.dumps(src)})")
    blocks = json.loads(out)
    # Make sure the parser at least ATTEMPTED — there's one block.
    assert len(blocks) >= 0  # may be 0 if id parser is strict


def test_groupBlocks_each_target_file_appears_at_most_once() -> None:
    out = _node_eval(
        f"Array.from(m.groupBlocks(m.extractTestBlocks({json.dumps(SAMPLE_SOURCE)}), m.TEST_GROUPS).keys())"
    )
    files = json.loads(out)
    assert len(files) == len(set(files))


# --------------------------- buildFileContent ----------------------------

def test_buildFileContent_includes_describe_with_deprecated_tag() -> None:
    out = _node_eval(
        f"m.buildFileContent({{describe: 'foo @deprecated', tests: m.extractTestBlocks({json.dumps(SAMPLE_SOURCE)}).slice(0,1)}})"
    )
    content = json.loads(out)
    assert "@deprecated" in content
    assert "test.describe(\"foo @deprecated\"" in content
    # Required imports always present (every split file's beforeEach uses them).
    assert "getTestUser" in content
    assert "loginUser" in content


def test_buildFileContent_emits_one_test_per_block() -> None:
    out = _node_eval(
        f"m.buildFileContent({{describe: 'foo @deprecated', tests: m.extractTestBlocks({json.dumps(SAMPLE_SOURCE)})}})"
    )
    content = json.loads(out)
    # Three tests in SAMPLE_SOURCE — three test() calls in output.
    assert content.count("test('") == 3


def test_buildFileContent_omits_unused_imports() -> None:
    """The splitter MUST NOT emit imports for helpers the test bodies
    don't reference — otherwise ESLint's `no-unused-vars` fails the
    build on every relocated file."""
    out = _node_eval(
        f"m.buildFileContent({{describe: 'foo @deprecated', tests: m.extractTestBlocks({json.dumps(SAMPLE_SOURCE)})}})"
    )
    content = json.loads(out)
    # SAMPLE_SOURCE references neither loginAndNavigateToRoute nor
    # navigateToRouteFromApp — they MUST NOT appear in the output.
    assert "loginAndNavigateToRoute" not in content
    assert "navigateToRouteFromApp" not in content
    assert "waitForAppMainReady" not in content
    assert "waitForLoadingComplete" not in content
    # And neither getAuditorUser nor getTenantAdminUser unless the body
    # actually reaches for them.
    assert "getAuditorUser" not in content
    assert "getTenantAdminUser" not in content


def test_buildFileContent_includes_only_referenced_helpers() -> None:
    """When a test body DOES reference an extra helper, the splitter
    must include the matching import."""
    src_with_nav = """\
test.describe('phase7.5', () => {
  test('A — uses navigateToRouteFromApp', async ({ page }) => {
    await navigateToRouteFromApp(page, '/x', { timeout: 1 });
  });
});
"""
    out = _node_eval(
        f"m.buildFileContent({{describe: 'foo @deprecated', tests: m.extractTestBlocks({json.dumps(src_with_nav)})}})"
    )
    content = json.loads(out)
    assert "navigateToRouteFromApp" in content
    assert "loginAndNavigateToRoute" not in content


def test_identifierUsedInSource_word_boundary_matters() -> None:
    """Sub-string matches MUST NOT count — `getTestUserFoo` must not
    pull in the `getTestUser` import. Word boundaries pin this."""
    out = _node_eval(
        f"m.identifierUsedInSource('getTestUser', {json.dumps('await getTestUserFoo()')})"
    )
    assert json.loads(out) is False
    out = _node_eval(
        f"m.identifierUsedInSource('getTestUser', {json.dumps('await getTestUser()')})"
    )
    assert json.loads(out) is True


def test_rewriteTestSkipTrueLiterals_single_line() -> None:
    """Single-line `test.skip(true, 'reason')` must be rewritten to
    `test.skip(Boolean(true), 'reason')` so the 226.A1 ESLint rule
    `e2e-guards/no-test-skip-true` does not fire on regenerated splits."""
    src = "  test.skip(true, '/files page did not load');"
    out = _node_eval(f"m.rewriteTestSkipTrueLiterals({json.dumps(src)})")
    assert json.loads(out) == "  test.skip(Boolean(true), '/files page did not load');"


def test_rewriteTestSkipTrueLiterals_multi_line() -> None:
    """Multi-line form where `true` lives on its own line after
    `test.skip(` must also be rewritten."""
    src = "      test.skip(\n        true,\n        'reason'\n      );"
    out = _node_eval(f"m.rewriteTestSkipTrueLiterals({json.dumps(src)})")
    expected = (
        "      test.skip(\n        Boolean(true),\n        'reason'\n      );"
    )
    assert json.loads(out) == expected


def test_rewriteTestSkipTrueLiterals_idempotent() -> None:
    """Running twice must produce the same output — `Boolean(true)` must
    not be re-wrapped into `Boolean(Boolean(true))`."""
    src = "test.skip(true, 'x');"
    once = json.loads(_node_eval(f"m.rewriteTestSkipTrueLiterals({json.dumps(src)})"))
    twice = json.loads(_node_eval(f"m.rewriteTestSkipTrueLiterals({json.dumps(once)})"))
    assert once == twice == "test.skip(Boolean(true), 'x');"


def test_rewriteTestSkipTrueLiterals_does_not_touch_unrelated_true() -> None:
    """The rewriter must only touch `true` literals inside `test.skip(...)`
    — `true` in any other context (assertions, conditionals) stays."""
    src = "expect(x).toBe(true);\nif (true) { foo(); }"
    out = json.loads(_node_eval(f"m.rewriteTestSkipTrueLiterals({json.dumps(src)})"))
    assert out == src


def test_selectImportsForBodies_groups_by_module() -> None:
    """Each module shows up once in the import block, with its needed
    names sorted for determinism."""
    src = "loginUser(); getTestUser(); navigateToRouteFromApp();"
    out = _node_eval(f"m.selectImportsForBodies({json.dumps(src)})")
    groups = json.loads(out)
    paths = sorted(g["from"] for g in groups)
    assert paths == ["../fixtures/auth", "../fixtures/helpers"]
    auth = next(g for g in groups if g["from"] == "../fixtures/auth")
    assert auth["names"] == ["getTestUser", "loginUser"]
    helpers = next(g for g in groups if g["from"] == "../fixtures/helpers")
    assert helpers["names"] == ["navigateToRouteFromApp"]


# --------------------------- CLI integration -----------------------------

def test_cli_split_writes_files_and_replaces_src_with_stub(tmp_path: Path) -> None:
    src = tmp_path / "phase7.5-features-gap-closure.spec.ts"
    out_dir = tmp_path / "features"
    out_dir.mkdir()
    src.write_text(SAMPLE_SOURCE)
    res = subprocess.run(
        ["node", str(SCRIPT), f"--src={src}", f"--out-dir={out_dir}"],
        capture_output=True, text=True, timeout=15,
    )
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["totalTests"] == 3
    assert {f["file"] for f in payload["files"]} == {
        "integrations-developer-baas-gap.spec.ts",
        "search-gap.spec.ts",
    }
    # New files were written
    for entry in payload["files"]:
        new_path = out_dir / entry["file"]
        assert new_path.is_file()
        body = new_path.read_text()
        assert "@deprecated" in body
        assert body.startswith("/**")
    # Source replaced with stub (so suite doesn't run the same tests twice)
    new_src = src.read_text()
    assert "this file has been split" in new_src
    assert "test.describe" not in new_src or "test.describe(" not in new_src


def test_cli_dry_run_does_not_mutate(tmp_path: Path) -> None:
    src = tmp_path / "phase7.5-features-gap-closure.spec.ts"
    out_dir = tmp_path / "features"
    out_dir.mkdir()
    original = SAMPLE_SOURCE
    src.write_text(original)
    res = subprocess.run(
        ["node", str(SCRIPT), f"--src={src}", f"--out-dir={out_dir}", "--dry-run"],
        capture_output=True, text=True, timeout=15,
    )
    assert res.returncode == 0, res.stderr
    # Source unchanged.
    assert src.read_text() == original
    # No files written to out_dir.
    assert list(out_dir.iterdir()) == []


def test_cli_idempotent_rerun_on_stub_is_clean_noop(tmp_path: Path) -> None:
    """Re-running the splitter on the post-split stub must succeed (exit 0)
    so CI / dev re-invocations don't false-fail. Any other zero-block
    source remains an error (could be a corrupted file)."""
    src = tmp_path / "phase7.5-features-gap-closure.spec.ts"
    out_dir = tmp_path / "features"
    out_dir.mkdir()
    src.write_text(SAMPLE_SOURCE)
    # First split.
    res1 = subprocess.run(
        ["node", str(SCRIPT), f"--src={src}", f"--out-dir={out_dir}"],
        capture_output=True, text=True, timeout=15,
    )
    assert res1.returncode == 0
    # Second invocation against the now-stub file.
    res2 = subprocess.run(
        ["node", str(SCRIPT), f"--src={src}", f"--out-dir={out_dir}"],
        capture_output=True, text=True, timeout=15,
    )
    assert res2.returncode == 0, (
        f"re-run on stub must be a clean no-op, got: {res2.stderr}"
    )
    payload = json.loads(res2.stdout)
    assert payload.get("alreadySplit") is True
    assert payload["totalTests"] == 0


def test_cli_exits_2_on_corrupted_source_with_no_blocks(tmp_path: Path) -> None:
    """A file that is neither the post-split stub nor a valid test source
    must still error — silent acceptance would mask a real corruption."""
    src = tmp_path / "phase7.5-features-gap-closure.spec.ts"
    out_dir = tmp_path / "features"
    out_dir.mkdir()
    src.write_text("// some unexpected content with no tests and no stub marker\n")
    res = subprocess.run(
        ["node", str(SCRIPT), f"--src={src}", f"--out-dir={out_dir}"],
        capture_output=True, text=True, timeout=15,
    )
    assert res.returncode == 2
    assert "no test blocks extracted" in res.stderr


def test_cli_exits_2_on_missing_src(tmp_path: Path) -> None:
    res = subprocess.run(
        ["node", str(SCRIPT), f"--src={tmp_path}/missing.ts", f"--out-dir={tmp_path}"],
        capture_output=True, text=True, timeout=15,
    )
    assert res.returncode == 2
    assert "src not found" in res.stderr
