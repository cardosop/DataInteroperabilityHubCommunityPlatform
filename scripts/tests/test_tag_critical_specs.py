"""
TDD unit tests for scripts/tag_critical_specs.cjs — Phase 226 E1.

Background
----------
Track 226.E1 mandates that every spec referencing a critical UC or
JOURNEY ID (per `docs/CRITICAL_UC_JOURNEY_IDS.yaml`) carries the
`@critical` tag in its `test.describe(...)` title, and that the 6
deprecated `phase*.spec.ts` files carry `@deprecated`. Playwright
`--grep '@critical'` is the only filter the PR-time CI job applies; if a
critical spec lacks the tag it silently drops out of the smoke run, which
defeats the gate's purpose.

CLI surface
-----------
    node scripts/tag_critical_specs.cjs \
        [--root=DIR]               (default: frontend/e2e)
        [--critical-list=PATH]     (default: docs/CRITICAL_UC_JOURNEY_IDS.yaml)
        [--deprecated=PATH,...]    (basenames to mark @deprecated)
        [--write]                  (mutate files; without --write, report only)
        [--json]                   (machine-readable output)

Exit codes
----------
    0 — every critical-ID spec has @critical, every deprecated has @deprecated
    1 — missing tags found
    2 — config error

Pure logic
----------
The .cjs module exports `parseCriticalIds`, `findCriticalRefs`,
`hasTag`, and `injectTag`. The pytest harness exercises both layers —
pure functions via a `node -e` shim, and the CLI via subprocess.

Run locally:
    pytest scripts/tests/test_tag_critical_specs.py -v
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "tag_critical_specs.cjs"


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
    """Evaluate a JS expression in a child node process and return stdout."""
    cmd = [
        "node",
        "-e",
        f"const m = require('{SCRIPT}'); process.stdout.write(JSON.stringify({expr}));",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert res.returncode == 0, f"node failed: {res.stderr}"
    return res.stdout


def _run_cli(
    root: Path,
    critical_list: Path,
    *,
    deprecated: list[str] | None = None,
    write: bool = False,
) -> subprocess.CompletedProcess:
    cmd = [
        "node",
        str(SCRIPT),
        f"--root={root}",
        f"--critical-list={critical_list}",
        "--json",
    ]
    if deprecated:
        cmd.append(f"--deprecated={','.join(deprecated)}")
    if write:
        cmd.append("--write")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


# ----------------------------- parseCriticalIds --------------------------

def test_parseCriticalIds_extracts_uc_and_journey_separately() -> None:
    yaml_source = """\
version: "1.0"
critical_use_cases:
  - UC-AUTH-001  # registers
  - UC-AM-001    # asset create
critical_journeys:
  - JOURNEY-AUTH-001
  - JOURNEY-DPO-001  # asset onboarding
thresholds:
  uc_coverage_percent: 70
"""
    out = _node_eval(f"m.parseCriticalIds({json.dumps(yaml_source)})")
    parsed = json.loads(out)
    assert parsed["critical_use_cases"] == ["UC-AM-001", "UC-AUTH-001"]
    assert parsed["critical_journeys"] == ["JOURNEY-AUTH-001", "JOURNEY-DPO-001"]


def test_parseCriticalIds_terminates_on_top_level_key() -> None:
    """Once we hit `thresholds:` the UC list must close — entries below are not UC IDs."""
    yaml_source = """\
critical_use_cases:
  - UC-A-001
thresholds:
  - SOMETHING_ELSE
"""
    out = _node_eval(f"m.parseCriticalIds({json.dumps(yaml_source)})")
    parsed = json.loads(out)
    assert parsed["critical_use_cases"] == ["UC-A-001"]


def test_parseCriticalIds_empty_input_returns_empty_lists() -> None:
    out = _node_eval(f"m.parseCriticalIds({json.dumps('')})")
    parsed = json.loads(out)
    assert parsed == {"critical_use_cases": [], "critical_journeys": []}


# ------------------------------- findCriticalRefs ------------------------

def test_findCriticalRefs_matches_word_boundary_only() -> None:
    """`UC-AUTH-001` MUST NOT match `UC-AUTH-0011`. Critical for stable counts."""
    src = "test.describe('UC-AUTH-001', () => {}); // also UC-AUTH-0011 unrelated"
    out = _node_eval(f"m.findCriticalRefs({json.dumps(src)}, ['UC-AUTH-001', 'UC-AUTH-002'])")
    refs = json.loads(out)
    assert refs == ["UC-AUTH-001"]


def test_findCriticalRefs_finds_id_in_comment_or_docstring() -> None:
    src = "/** Use cases: UC-AM-001 */\nimport { test } from '...';"
    out = _node_eval(f"m.findCriticalRefs({json.dumps(src)}, ['UC-AM-001'])")
    refs = json.loads(out)
    assert refs == ["UC-AM-001"]


def test_findCriticalRefs_returns_empty_on_no_match() -> None:
    out = _node_eval(f"m.findCriticalRefs({json.dumps('no ids here')}, ['UC-X-001'])")
    refs = json.loads(out)
    assert refs == []


# ------------------------------- hasTag / injectTag ----------------------

def test_hasTag_detects_existing_tag_in_describe_title() -> None:
    src = "test.describe('JOURNEY-AUTH-001 @critical', () => {});"
    out = _node_eval(f"m.hasTag({json.dumps(src)}, '@critical')")
    assert json.loads(out) is True


def test_hasTag_negative_when_tag_only_in_comment() -> None:
    """Tag must be in the describe title, not a free-floating comment."""
    src = "// @critical because UC-AUTH-001\ntest.describe('something', () => {});"
    out = _node_eval(f"m.hasTag({json.dumps(src)}, '@critical')")
    assert json.loads(out) is False


def test_injectTag_appends_tag_to_first_describe_title() -> None:
    src = "test.describe('JOURNEY-DPO-001: Onboard New Asset', () => {});"
    out = _node_eval(f"m.injectTag({json.dumps(src)}, '@critical')")
    result = json.loads(out)
    assert result["changed"] is True
    assert "JOURNEY-DPO-001: Onboard New Asset @critical" in result["source"]


def test_injectTag_idempotent_when_tag_already_present() -> None:
    src = "test.describe('JOURNEY-DPO-001 @critical', () => {});"
    out = _node_eval(f"m.injectTag({json.dumps(src)}, '@critical')")
    result = json.loads(out)
    assert result["changed"] is False
    assert result["source"] == src


def test_injectTag_noop_when_no_describe_block() -> None:
    src = "import { test } from '@playwright/test';\ntest('foo', () => {});"
    out = _node_eval(f"m.injectTag({json.dumps(src)}, '@critical')")
    result = json.loads(out)
    assert result["changed"] is False
    assert result["source"] == src


# --------------------------------- CLI integration ------------------------

def _seed_yaml(tmpdir: Path) -> Path:
    f = tmpdir / "critical.yaml"
    f.write_text(
        "critical_use_cases:\n"
        "  - UC-AUTH-001\n"
        "critical_journeys:\n"
        "  - JOURNEY-AUTH-001\n"
    )
    return f


def test_cli_check_mode_passes_when_all_specs_tagged(tmp_path: Path) -> None:
    yaml_path = _seed_yaml(tmp_path)
    root = tmp_path / "e2e"
    root.mkdir()
    (root / "ok.spec.ts").write_text(
        "import { test } from '@playwright/test';\n"
        "test.describe('JOURNEY-AUTH-001 @critical', () => {});\n"
    )
    (root / "phase2-catalog-journey.spec.ts").write_text(
        "import { test } from '@playwright/test';\n"
        "test.describe('phase2 @deprecated', () => {});\n"
    )
    res = _run_cli(
        root, yaml_path,
        deprecated=["phase2-catalog-journey.spec.ts"],
    )
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["critical_specs_tagged"] == 1
    assert payload["deprecated_specs_tagged"] == 1
    assert payload["missing_critical"] == []
    assert payload["missing_deprecated"] == []


def test_cli_check_mode_fails_when_critical_spec_missing_tag(tmp_path: Path) -> None:
    yaml_path = _seed_yaml(tmp_path)
    root = tmp_path / "e2e"
    root.mkdir()
    (root / "missing.spec.ts").write_text(
        "import { test } from '@playwright/test';\n"
        "test.describe('JOURNEY-AUTH-001 first-time visitor', () => {});\n"
    )
    res = _run_cli(root, yaml_path)
    assert res.returncode == 1, res.stdout + res.stderr
    payload = json.loads(res.stdout)
    assert len(payload["missing_critical"]) == 1
    assert payload["missing_critical"][0]["file"].endswith("missing.spec.ts")
    assert "JOURNEY-AUTH-001" in payload["missing_critical"][0]["ids"]


def test_cli_write_mode_injects_missing_tag(tmp_path: Path) -> None:
    yaml_path = _seed_yaml(tmp_path)
    root = tmp_path / "e2e"
    root.mkdir()
    spec = root / "needs_tag.spec.ts"
    spec.write_text(
        "import { test } from '@playwright/test';\n"
        "test.describe('UC-AUTH-001 register', () => {});\n"
    )
    res = _run_cli(root, yaml_path, write=True)
    assert res.returncode == 0, res.stderr
    after = spec.read_text()
    assert "@critical" in after
    # Re-running should be a no-op and still pass.
    res2 = _run_cli(root, yaml_path)
    assert res2.returncode == 0
    assert spec.read_text() == after


def test_cli_write_mode_marks_deprecated_phase_files(tmp_path: Path) -> None:
    yaml_path = _seed_yaml(tmp_path)
    root = tmp_path / "e2e"
    root.mkdir()
    spec = root / "phase3-quality-gates.spec.ts"
    spec.write_text(
        "import { test } from '@playwright/test';\n"
        "test.describe('phase3 quality', () => {});\n"
    )
    res = _run_cli(
        root, yaml_path,
        deprecated=["phase3-quality-gates.spec.ts"],
        write=True,
    )
    assert res.returncode == 0, res.stderr
    after = spec.read_text()
    assert "@deprecated" in after


def test_cli_deprecated_spec_is_not_also_tagged_critical(tmp_path: Path) -> None:
    """A phase* spec that mentions a critical ID must NOT receive `@critical` —
    otherwise Playwright `--grep '@critical'` would still match it and the
    PR-time smoke run would re-pull the legacy code we're trying to retire."""
    yaml_path = _seed_yaml(tmp_path)
    root = tmp_path / "e2e"
    root.mkdir()
    spec = root / "phase7.5-features-gap-closure.spec.ts"
    spec.write_text(
        "import { test } from '@playwright/test';\n"
        "// Mentions UC-AUTH-001 in passing\n"
        "test.describe('phase7.5 gap closure', () => {});\n"
    )
    res = _run_cli(
        root, yaml_path,
        deprecated=["phase7.5-features-gap-closure.spec.ts"],
        write=True,
    )
    assert res.returncode == 0, res.stderr
    after = spec.read_text()
    assert "@deprecated" in after
    assert "@critical" not in after
    payload = json.loads(res.stdout)
    assert payload["critical_specs_count"] == 0
    assert payload["deprecated_specs_count"] == 1


def test_cli_skips_fixtures_and_setup_dirs(tmp_path: Path) -> None:
    """Fixtures aren't specs — they should not be scanned even if they
    happen to mention a critical ID in a docstring."""
    yaml_path = _seed_yaml(tmp_path)
    root = tmp_path / "e2e"
    fixtures = root / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "helpers.spec.ts").write_text(
        "// JOURNEY-AUTH-001 helper used by all auth specs\n"
        "test.describe('helpers', () => {});\n"
    )
    res = _run_cli(root, yaml_path)
    payload = json.loads(res.stdout)
    # Fixtures dir is skipped, so the helper does NOT count as a critical spec.
    assert payload["critical_specs_count"] == 0


def test_cli_skips_stub_files_without_describe_blocks(tmp_path: Path) -> None:
    """A spec file with no `test.describe(...)` call (e.g. the post-split
    phase7.5 stub that just `export {}`s) cannot be tagged and holds no
    tests. The tag gate must treat it as fine, not as a missing tag."""
    yaml_path = _seed_yaml(tmp_path)
    root = tmp_path / "e2e"
    root.mkdir()
    stub = root / "phase7.5-features-gap-closure.spec.ts"
    stub.write_text("/** stub — split per E3 */\nexport {};\n")
    res = _run_cli(
        root, yaml_path,
        deprecated=["phase7.5-features-gap-closure.spec.ts"],
    )
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["deprecated_specs_count"] == 0
    assert payload["missing_deprecated"] == []


def test_cli_exit_2_on_missing_root(tmp_path: Path) -> None:
    yaml_path = _seed_yaml(tmp_path)
    res = _run_cli(tmp_path / "nonexistent", yaml_path)
    assert res.returncode == 2
    assert "root not found" in res.stderr


def test_cli_exit_2_on_missing_yaml(tmp_path: Path) -> None:
    root = tmp_path / "e2e"
    root.mkdir()
    res = _run_cli(root, tmp_path / "nonexistent.yaml")
    assert res.returncode == 2
    assert "critical-list not found" in res.stderr
