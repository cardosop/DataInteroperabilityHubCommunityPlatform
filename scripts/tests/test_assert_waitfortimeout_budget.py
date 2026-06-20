"""
TDD unit tests for scripts/assert_waitfortimeout_budget.cjs — Phase 226 C1.

Background
----------
Track 226.C1 mandates that the count of `page.waitForTimeout(...)` (or
`.waitForTimeout(...)` on Page-typed objects) across `frontend/e2e` shall
not exceed a checked-in budget. The gate ratchets the budget down only;
PRs that introduce more `waitForTimeout` than the current budget allows
fail CI. Engineers reduce the budget when they remove waits.

Why a separate gate (not just a one-time refactor)
--------------------------------------------------
Without a CI gate, a single PR can re-introduce all the waits the team
fought to remove — flake regression goes silent. The gate is the
enforcement edge of the principle: "every waitForTimeout is debt".

CLI surface
-----------
    node scripts/assert_waitfortimeout_budget.cjs \
        [--budget=N]              (default: read scripts/waitfortimeout_budget.json)
        [--root=DIR]              (default: frontend/e2e)
        [--exclude=GLOB,...]      (default: empty)
        [--json]                  (machine-readable output)
        [--update-budget]         (writes the current count as the new budget)

Exit codes
----------
    0  — count <= budget
    1  — count > budget (PR introduces new waits beyond budget)
    2  — config error (budget file malformed, root missing, etc.)

Pure logic
----------
The .cjs module exports `countWaitForTimeout(source)` which returns
the number of matches in a single source string. The CLI walks the
filesystem; the pytest harness exercises both layers.

Run locally:
    pytest scripts/tests/test_assert_waitfortimeout_budget.py -v
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "assert_waitfortimeout_budget.cjs"


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
    budget: int | None = None,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    cmd: list[str] = [
        "node",
        str(SCRIPT),
        f"--root={tmpdir}",
        "--json",
    ]
    if budget is not None:
        cmd.append(f"--budget={budget}")
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=120)


def _write_spec(tmpdir: Path, name: str, body: str) -> Path:
    p = tmpdir / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_empty_tree_zero_count(tmp_path: Path):
    """No spec files → count 0 → exit 0 even with budget 0."""
    res = _run(tmp_path, budget=0)
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["count"] == 0
    assert payload["budget"] == 0
    assert payload["overBudget"] is False


def test_single_spec_no_waits_passes(tmp_path: Path):
    _write_spec(
        tmp_path,
        "clean.spec.ts",
        "import { test } from '@playwright/test';\n"
        "test('clean', async ({ page }) => { await page.goto('/'); });\n",
    )
    res = _run(tmp_path, budget=0)
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["count"] == 0


def test_counts_page_waitfortimeout_calls(tmp_path: Path):
    _write_spec(
        tmp_path,
        "noisy.spec.ts",
        "import { test } from '@playwright/test';\n"
        "test('noisy', async ({ page }) => {\n"
        "  await page.waitForTimeout(1000);\n"
        "  await page.waitForTimeout(2000);\n"
        "  await page.waitForTimeout(500);\n"
        "});\n",
    )
    res = _run(tmp_path, budget=10)
    payload = json.loads(res.stdout)
    assert payload["count"] == 3
    assert payload["overBudget"] is False
    assert res.returncode == 0


def test_budget_breach_returns_exit_1(tmp_path: Path):
    _write_spec(
        tmp_path,
        "noisy.spec.ts",
        "import { test } from '@playwright/test';\n"
        "test('noisy', async ({ page }) => {\n"
        "  await page.waitForTimeout(1000);\n"
        "  await page.waitForTimeout(2000);\n"
        "  await page.waitForTimeout(500);\n"
        "});\n",
    )
    res = _run(tmp_path, budget=2)
    payload = json.loads(res.stdout)
    assert payload["count"] == 3
    assert payload["budget"] == 2
    assert payload["overBudget"] is True
    assert res.returncode == 1


def test_chained_locator_waitfortimeout_caught(tmp_path: Path):
    """`somePage.waitForTimeout(...)` (variable Page object) must also count."""
    _write_spec(
        tmp_path,
        "indirect.spec.ts",
        "import { test } from '@playwright/test';\n"
        "test('indirect', async ({ page }) => {\n"
        "  const otherPage = page;\n"
        "  await otherPage.waitForTimeout(1000);\n"
        "});\n",
    )
    res = _run(tmp_path, budget=10)
    payload = json.loads(res.stdout)
    assert payload["count"] == 1


def test_walks_subdirectories(tmp_path: Path):
    _write_spec(
        tmp_path / "journeys" / "auth",
        "JOURNEY-AUTH-001.spec.ts",
        "import { test } from '@playwright/test';\n"
        "test('a', async ({ page }) => { await page.waitForTimeout(1); });\n",
    )
    _write_spec(
        tmp_path / "features",
        "extras.spec.ts",
        "import { test } from '@playwright/test';\n"
        "test('b', async ({ page }) => { await page.waitForTimeout(1); });\n",
    )
    res = _run(tmp_path, budget=10)
    payload = json.loads(res.stdout)
    assert payload["count"] == 2


def test_counts_helpers_ts_outside_spec_glob(tmp_path: Path):
    """fixtures/helpers.ts is the biggest offender; gate must scan .ts not just .spec.ts."""
    _write_spec(
        tmp_path / "fixtures",
        "helpers.ts",
        "export async function flake(page) {\n  await page.waitForTimeout(2000);\n}\n",
    )
    res = _run(tmp_path, budget=10)
    payload = json.loads(res.stdout)
    assert payload["count"] == 1


def test_excludes_node_modules_and_test_results(tmp_path: Path):
    """Walks must skip node_modules / test-results / playwright-report etc."""
    _write_spec(
        tmp_path / "node_modules" / "some-pkg",
        "evil.ts",
        "export const x = () => page.waitForTimeout(1);\n",
    )
    _write_spec(
        tmp_path / "test-results" / "trace",
        "evil.ts",
        "export const x = () => page.waitForTimeout(1);\n",
    )
    _write_spec(
        tmp_path,
        "real.spec.ts",
        "import { test } from '@playwright/test';\n"
        "test('a', async ({ page }) => { await page.waitForTimeout(1); });\n",
    )
    res = _run(tmp_path, budget=10)
    payload = json.loads(res.stdout)
    # Only the real spec should be counted.
    assert payload["count"] == 1


def test_exclude_glob_argument(tmp_path: Path):
    _write_spec(
        tmp_path / ["phase8-hardening.spec.ts"][0] or tmp_path,
        "phase8-hardening.spec.ts",
        "import { test } from '@playwright/test';\n"
        "test('a', async ({ page }) => { await page.waitForTimeout(1); });\n",
    )
    _write_spec(
        tmp_path,
        "fresh.spec.ts",
        "import { test } from '@playwright/test';\n"
        "test('b', async ({ page }) => { await page.waitForTimeout(1); });\n",
    )
    res = _run(
        tmp_path,
        budget=10,
        extra_args=["--exclude=phase8-hardening.spec.ts"],
    )
    payload = json.loads(res.stdout)
    assert payload["count"] == 1, "phase8-hardening should be excluded"


def test_missing_root_returns_exit_2(tmp_path: Path):
    res = _run(tmp_path / "does-not-exist", budget=0)
    assert res.returncode == 2


def test_invalid_budget_returns_exit_2(tmp_path: Path):
    res = _run(tmp_path, extra_args=["--budget=not-a-number"])
    assert res.returncode == 2


def test_budget_file_used_when_no_cli_budget(tmp_path: Path):
    """When --budget not passed, read the canonical budget file."""
    budget_file = tmp_path / "budget.json"
    budget_file.write_text(json.dumps({"budget": 5}))
    _write_spec(
        tmp_path / "specs",
        "x.spec.ts",
        "import { test } from '@playwright/test';\n"
        "test('a', async ({ page }) => { await page.waitForTimeout(1); });\n",
    )
    res = subprocess.run(
        [
            "node",
            str(SCRIPT),
            f"--root={tmp_path / 'specs'}",
            f"--budget-file={budget_file}",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    payload = json.loads(res.stdout)
    assert payload["budget"] == 5
    assert payload["count"] == 1
    assert payload["overBudget"] is False
    assert res.returncode == 0


def test_pure_logic_count_export():
    """countWaitForTimeout is exported for direct use in node REPL / tests."""
    # Use a Node one-liner to exercise the exported function so we don't need a
    # JS test runner. Validates the pure logic path the CLI reuses.
    code = (
        "const { countWaitForTimeout } = require(process.argv[1]);"
        "const src = `await page.waitForTimeout(1); await x.waitForTimeout(2);`;"
        "process.stdout.write(String(countWaitForTimeout(src)));"
    )
    res = subprocess.run(
        ["node", "-e", code, str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "2"
