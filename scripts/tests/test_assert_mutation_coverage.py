"""
TDD unit tests for scripts/assert_mutation_coverage.cjs — Phase 226 B6.

Written in pytest because the existing scripts/tests/ harness is pytest-based
(see test_e2e_metrics.py). Exercises the script through its CLI by invoking
plain `node` — the gate is a `.cjs` module, not TypeScript, because this repo
does not carry a ts-node dependency (see scripts/e2e_metrics_typescript.cjs
for the established pattern). Inputs are TypeScript source strings fed into
the analyzer, outputs are verified as exit codes and stdout shapes.

Run locally:
    pytest scripts/tests/test_assert_mutation_coverage.py -v
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "assert_mutation_coverage.cjs"


def _has_node() -> bool:
    try:
        res = subprocess.run(["node", "--version"], check=False, capture_output=True, timeout=10)
        return res.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(
    not _has_node(),
    reason="node not available in PATH",
)


def _run(
    tmpdir: Path,
    *,
    mode: str = "warning",
    allowlist: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run the gate against a temp spec tree and return the CompletedProcess."""
    cmd = [
        "node",
        str(SCRIPT),
        f"--mode={mode}",
        f"--root={tmpdir}",
        "--json",
    ]
    if allowlist is not None:
        cmd.append(f"--allowlist={allowlist}")
    else:
        cmd.append(f"--allowlist={tmpdir}/nonexistent_allowlist.txt")
    return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=120)


def _write_spec(tmpdir: Path, name: str, source: str) -> Path:
    """Write a spec file into tmpdir."""
    p = tmpdir / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(source, encoding="utf-8")
    return p


def test_empty_spec_tree_passes(tmp_path: Path) -> None:
    """Zero specs → no findings, exit 0 in both modes."""
    res = _run(tmp_path, mode="warning")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["total"] == 0


def test_spec_with_no_mutations_passes(tmp_path: Path) -> None:
    """A read-only spec has nothing to verify."""
    _write_spec(
        tmp_path,
        "read_only.spec.ts",
        """
import { test } from '@playwright/test';
test('reads data only', async ({ page }) => {
  await page.goto('/');
  await page.locator('.nav').waitFor();
});
""",
    )
    res = _run(tmp_path)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["total"] == 0


def test_mutation_with_full_verification_pair_passes(tmp_path: Path) -> None:
    """page.request.post followed by verifyViaApi + verifyAuditEvent passes."""
    _write_spec(
        tmp_path,
        "good.spec.ts",
        """
import { test } from '@playwright/test';
test('good coverage', async ({ page }) => {
  const res = await page.request.post('/api/v1/assets/', { data: { name: 'x' } });
  await verifyViaApi(page, `/api/v1/assets/${id}/`, { status: 'DRAFT' });
  await verifyAuditEvent(page, { action: 'ASSET_CREATED', resourceType: 'ASSET', resourceId: id });
});
""",
    )
    res = _run(tmp_path)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["total"] == 0


def test_mutation_without_verifyviaapi_fails_in_blocking_mode(tmp_path: Path) -> None:
    """page.request.post without verifyViaApi → finding; blocking mode fails."""
    _write_spec(
        tmp_path,
        "bad.spec.ts",
        """
import { test } from '@playwright/test';
test('no coverage', async ({ page }) => {
  const res = await page.request.post('/api/v1/assets/', { data: { name: 'x' } });
});
""",
    )
    res = _run(tmp_path, mode="blocking")
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["total"] >= 1
    assert any(
        "verifyViaApi" in "+".join(f["missing"]) and "verifyAuditEvent" in "+".join(f["missing"])
        for f in data["findings"]
    )


def test_mutation_without_verification_warns_but_does_not_fail(tmp_path: Path) -> None:
    """Warning mode never fails — prints + exit 0."""
    _write_spec(
        tmp_path,
        "bad.spec.ts",
        """
import { test } from '@playwright/test';
test('no coverage', async ({ page }) => {
  const res = await page.request.post('/api/v1/assets/', { data: { name: 'x' } });
});
""",
    )
    res = _run(tmp_path, mode="warning")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["total"] >= 1
    assert data["nonAllowed"] >= 1


def test_ui_click_on_create_button_counts_as_mutation(tmp_path: Path) -> None:
    """A click() on a button labelled 'Create …' is a mutation site."""
    _write_spec(
        tmp_path,
        "ui.spec.ts",
        """
import { test } from '@playwright/test';
test('ui create', async ({ page }) => {
  await page.locator('button:has-text("Create Asset")').click();
});
""",
    )
    res = _run(tmp_path, mode="blocking")
    assert res.returncode == 1


def test_noverify_escape_hatch_suppresses_finding(tmp_path: Path) -> None:
    """// noverify: <reason> within window silences the gap."""
    _write_spec(
        tmp_path,
        "noverify.spec.ts",
        """
import { test } from '@playwright/test';
test('skip verify for non-audit mutation', async ({ page }) => {
  // noverify: health-check endpoint does not write audit rows by design
  await page.request.post('/api/v1/_internal/health/');
});
""",
    )
    res = _run(tmp_path, mode="blocking")
    assert res.returncode == 0, f"stdout={res.stdout} stderr={res.stderr}"


def test_allowlist_grandfathers_a_pre_existing_spec(tmp_path: Path) -> None:
    """Allow-list with future expiry lets the gap pass."""
    _write_spec(
        tmp_path,
        "pending.spec.ts",
        """
import { test } from '@playwright/test';
test('pending adoption', async ({ page }) => {
  await page.request.post('/api/v1/assets/', { data: { name: 'x' } });
});
""",
    )
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text("pending.spec.ts:2099-12-31:pending B1a adoption\n")

    res = _run(tmp_path, mode="blocking", allowlist=allowlist)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["total"] >= 1
    assert data["nonAllowed"] == 0


def test_allowlist_past_expiry_fails_even_in_warning_mode(tmp_path: Path) -> None:
    """Past-expiry allow-list entry must fail regardless of mode."""
    _write_spec(
        tmp_path,
        "expired.spec.ts",
        """
import { test } from '@playwright/test';
test('expired allow', async ({ page }) => {
  await page.request.post('/api/v1/assets/', { data: { name: 'x' } });
});
""",
    )
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text("expired.spec.ts:2020-01-01:past expiry\n")

    res = _run(tmp_path, mode="warning", allowlist=allowlist)
    assert res.returncode == 1, res.stderr


def test_malformed_allowlist_exits_2(tmp_path: Path) -> None:
    """Malformed allow-list entry → exit 2, not 1."""
    _write_spec(tmp_path, "ok.spec.ts", "// empty\n")
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text("this-line-has-no-colons\n")

    res = _run(tmp_path, mode="warning", allowlist=allowlist)
    assert res.returncode == 2


def test_invalid_date_in_allowlist_exits_2(tmp_path: Path) -> None:
    """Invalid date in allow-list → exit 2."""
    _write_spec(tmp_path, "ok.spec.ts", "// empty\n")
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text("ok.spec.ts:not-a-date:reason\n")

    res = _run(tmp_path, mode="warning", allowlist=allowlist)
    assert res.returncode == 2


def test_multiple_mutations_in_one_spec_each_checked_independently(tmp_path: Path) -> None:
    """One spec with 2 mutation sites reports 2 findings if both lack pair."""
    _write_spec(
        tmp_path,
        "multi.spec.ts",
        """
import { test } from '@playwright/test';
test('multiple', async ({ page }) => {
  const a = await page.request.post('/api/v1/assets/', { data: { name: 'a' } });
  const b = await page.request.post('/api/v1/contracts/', { data: { name: 'b' } });
});
""",
    )
    res = _run(tmp_path, mode="blocking")
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["total"] >= 2


def test_verification_helpers_outside_window_do_not_count(tmp_path: Path) -> None:
    """verifyViaApi called 50 lines later does NOT cover a mutation 30-line window."""
    extra_lines = "\n".join([f"  // padding {i}" for i in range(45)])
    _write_spec(
        tmp_path,
        "far.spec.ts",
        f"""
import {{ test }} from '@playwright/test';
test('far apart', async ({{ page }}) => {{
  const a = await page.request.post('/api/v1/assets/', {{ data: {{ name: 'a' }} }});
{extra_lines}
  await verifyViaApi(page, `/api/v1/assets/${{id}}/`, {{ status: 'DRAFT' }});
  await verifyAuditEvent(page, {{ action: 'X', resourceType: 'Y', resourceId: id }});
}});
""",
    )
    res = _run(tmp_path, mode="blocking")
    assert res.returncode == 1


# ---- OQ7 (2026-04-25): --update mode + helper exports ------------------------


def test_update_mode_seeds_allowlist_with_grandfathered_specs(tmp_path: Path) -> None:
    """`--update` writes one allow-list entry per spec with findings."""
    _write_spec(
        tmp_path,
        "ungated.spec.ts",
        """
import { test } from '@playwright/test';
test('a', async ({ page }) => {
  const r = await page.request.post('/api/v1/assets/', { data: {} });
  // no verifyViaApi or verifyAuditEvent — should be flagged
});
""",
    )
    _write_spec(
        tmp_path,
        "covered.spec.ts",
        """
import { test } from '@playwright/test';
test('b', async ({ page }) => {
  const r = await page.request.post('/api/v1/assets/', { data: {} });
  await verifyViaApi(page, `/api/v1/assets/x/`, { status: 'DRAFT' });
  await verifyAuditEvent(page, { action: 'X', resourceType: 'Y', resourceId: 'z' });
});
""",
    )
    allowlist = tmp_path / "allowlist.txt"
    res = subprocess.run(
        [
            "node",
            str(SCRIPT),
            f"--root={tmp_path}",
            f"--allowlist={allowlist}",
            "--update",
            "--expiry-days=30",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert res.returncode == 0, res.stderr
    contents = allowlist.read_text(encoding="utf-8")
    # Only the ungated spec is grandfathered.
    assert "ungated.spec.ts" in contents
    assert "covered.spec.ts" not in contents
    # Expiry format pinned: each non-comment entry must be
    # `path:YYYY-MM-DD:reason`. Regex catches both shape regressions
    # (missing/wrong-format date) and accidental concatenation.
    entry_lines = [
        line.strip()
        for line in contents.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert entry_lines, "allow-list seeded with zero entries"
    entry_pattern = re.compile(r"^[^:]+:\d{4}-\d{2}-\d{2}:.+$")
    for line in entry_lines:
        assert entry_pattern.match(line), f"malformed allow-list entry: {line!r}"


def test_update_mode_then_blocking_mode_passes(tmp_path: Path) -> None:
    """End-to-end: --update grandfathers, then --mode=blocking exits 0."""
    _write_spec(
        tmp_path,
        "ungated.spec.ts",
        """
import { test } from '@playwright/test';
test('a', async ({ page }) => {
  const r = await page.request.post('/api/v1/assets/', { data: {} });
});
""",
    )
    allowlist = tmp_path / "allowlist.txt"
    seed = subprocess.run(
        [
            "node",
            str(SCRIPT),
            f"--root={tmp_path}",
            f"--allowlist={allowlist}",
            "--update",
            "--expiry-days=30",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert seed.returncode == 0, seed.stderr

    gate = subprocess.run(
        [
            "node",
            str(SCRIPT),
            "--mode=blocking",
            f"--root={tmp_path}",
            f"--allowlist={allowlist}",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert gate.returncode == 0, gate.stdout + gate.stderr


def test_update_expiry_days_must_be_positive(tmp_path: Path) -> None:
    res = subprocess.run(
        ["node", str(SCRIPT), "--update", "--expiry-days=-1", f"--root={tmp_path}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res.returncode == 2


def test_default_mode_is_blocking(tmp_path: Path) -> None:
    """OQ7 (2026-04-25): default mode flipped from `warning` to `blocking`."""
    _write_spec(
        tmp_path,
        "ungated.spec.ts",
        """
import { test } from '@playwright/test';
test('a', async ({ page }) => {
  const r = await page.request.post('/api/v1/assets/', { data: {} });
});
""",
    )
    res = subprocess.run(
        [
            "node",
            str(SCRIPT),
            f"--root={tmp_path}",
            f"--allowlist={tmp_path}/nonexistent.txt",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    # No --mode flag → default → must fail because findings exist & no allow-list.
    assert res.returncode == 1, res.stdout
