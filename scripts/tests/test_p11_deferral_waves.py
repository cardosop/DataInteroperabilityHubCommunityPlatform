"""
P0-11 (close-oss-release-conditions, F-1…F-3) — deferral-wave pins.

Four lanes, each pinned at its weakest point:

1. **storybook-static out of the tree** — no tracked or on-disk build
   litter under frontend/; GATE-55's blind spot for the `frontend/`
   prefix is fixed (planted-fixture pin: a committed
   frontend/storybook-static tree flips the gate); the visual-regression
   build ships as a CI artifact (upload-artifact step).
2. **PWA surface DELETED** (decision 2026-10-19, usage evidence recorded
   in the `decide-pwa-story` change) — sw.js / manifest.json / the
   serviceWorker registration are gone; the GATE-61 stub row flips to
   deleted with an absent marker (reintroduction flips the gate).
3. **i18n es/fr COMPLETED to 100%** (decision 2026-10-19) — the real
   vitest coverage suite runs at threshold 100 (frontend CI); the
   committed coverage.json is byte-reproducible from the zero-dependency
   generator; the orphaned ar.ts is gone.
4. **SDK `: any` ratchet** — the real gate over sdk/js/src fails on
   growth, passes at the committed baseline, and `--update` shrinks the
   floor after a fix wave; CI-wired into the SDK lint job.

No mocks: real gates, real git, real node/vitest, real files.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS.parent))

from envpolicy import skip_or_fail


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS.parent / filename)
    assert spec is not None, f"{filename} must load (P0-11)"
    assert spec.loader is not None, f"{filename} must carry a loader"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

litter = _load("check_shipped_tree_litter", "check_shipped_tree_litter.py")
sdk_ratchet = _load("check_sdk_any_typing", "check_sdk_any_typing.py")

from check_shipped_tree_litter import _violations as litter_violations

BACKLOG = REPO_ROOT / "openspec/changes/track-oss-deferred-debt/tasks.md"
CHANGES = REPO_ROOT / "openspec/changes"
REGISTRY = SCRIPTS.parent / "stub_inventory_registry.json"
STUB_DOC = REPO_ROOT / "docs/audits/stub-inventory-2026.md"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


# ── 1. storybook-static out of the tree ───────────────────────────────────


def test_storybook_static_not_tracked_nor_on_disk():
    tracked = _git("ls-files", "frontend/storybook-static")
    assert tracked == "", f"still tracked: {tracked.splitlines()[:3]}"
    assert not (REPO_ROOT / "frontend/storybook-static").exists(), (
        "the build litter must not exist on disk either"
    )


def test_litter_gate_flags_planted_frontend_storybook(tmp_path):
    """GATE-55's frontend/ blind spot is fixed: a committed
    frontend/storybook-static tree flips the gate (it could not before
    P0-11 — the prefix only matched repo-root paths)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "frontend" / "storybook-static").mkdir(parents=True)
    (repo / "frontend" / "storybook-static" / "index.html").write_text("x")
    (repo / "keep.txt").write_text("kept\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c"],
        cwd=repo,
        check=True,
    )
    problems = litter_violations(repo)
    assert any("storybook-static" in p for p in problems), problems


def test_visual_regression_build_is_a_ci_artifact():
    """The visual-regression workflow uploads the built Storybook as a
    retrievable CI artifact — the build output is generated in CI,
    never shipped."""
    wf = (REPO_ROOT / ".github/workflows/visual-regression.yml").read_text(
        encoding="utf-8"
    )
    assert "upload-artifact" in wf
    assert "storybook-static" in wf


# ── 2. PWA surface deleted ────────────────────────────────────────────────


def test_pwa_surface_absent():
    tracked = _git("ls-files", "frontend/public/sw.js", "frontend/public/manifest.json")
    assert tracked == "", f"still tracked: {tracked!r}"
    main_tsx = (REPO_ROOT / "frontend/src/main.tsx").read_text(encoding="utf-8")
    assert "serviceWorker" not in main_tsx, (
        "the registration must be gone with the surface"
    )
    index_html = (REPO_ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "manifest" not in index_html.lower(), "the manifest link must be gone"


def test_pwa_stub_row_deleted_with_absent_marker():
    rows = json.loads(REGISTRY.read_text(encoding="utf-8"))["rows"]
    row = next(r for r in rows if r["id"] == "STUB-006")
    assert row["status"] == "deleted", row
    assert "absent_marker" in row, "a deleted row must carry its reintroduction marker"
    assert row["evidence"] == "frontend/src/main.tsx"
    assert "STUB-006" in STUB_DOC.read_text(encoding="utf-8"), (
        "the human evidence doc must carry the resolved note"
    )


def test_pwa_decision_recorded_in_routed_change():
    change = CHANGES / "decide-pwa-story"
    proposal = (change / "proposal.md").read_text(encoding="utf-8")
    assert "## Why" in proposal
    assert "## What Changes" in proposal
    assert "usage" in proposal.lower()
    assert "DELETE" in proposal, (
        "the usage-based recommendation and the decision must be recorded"
    )
    backlog = BACKLOG.read_text(encoding="utf-8")
    assert "[x] `TICKET=W105-PWA-STORY`" in backlog, (
        "the backlog row must close with the citation"
    )


# ── 3. i18n es/fr completed ───────────────────────────────────────────────


def test_es_fr_completion_threshold_is_100():
    """The real vitest coverage suite (frontend CI) enforces 100% —
    zero keys identical to the English fallback for es and fr."""
    test = (
        REPO_ROOT / "frontend/src/shared/i18n/locales/coverage.test.ts"
    ).read_text(encoding="utf-8")
    assert "toBe(100)" in test or "toEqual(100)" in test, (
        "the completion contract is 100%, not >=90%"
    )


def test_coverage_json_is_reproducible():
    """The committed coverage.json is byte-reproducible from the live
    locale files by the zero-dependency generator — a stale snapshot
    cannot pass."""
    node = subprocess.run(
        ["sh", "-c", "command -v node"], capture_output=True, text=True, check=False
    ).stdout.strip()
    if not node:
        skip_or_fail("node binary (the coverage generator is zero-dep .cjs)")
    result = subprocess.run(
        [node, "scripts/generate-i18n-coverage.cjs", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_i18n_key_check_green():
    """The 228.X.1 key-consistency checker runs for real (zero-dep
    node): every key used in a t() call exists in the en catalog —
    the 224-key drift found at P0-11 must never regrow silently."""
    node = subprocess.run(
        ["sh", "-c", "command -v node"], capture_output=True, text=True, check=False
    ).stdout.strip()
    if not node:
        skip_or_fail("node binary (the 228.X.1 checker is zero-dep .cjs)")
    result = subprocess.run(
        [node, "frontend/scripts/check-i18n-keys.cjs"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-600:]


def test_coverage_json_reports_100pct():
    cov = json.loads(
        (REPO_ROOT / "frontend/src/shared/i18n/locales/coverage.json").read_text(
            encoding="utf-8"
        )
    )
    assert cov["locales"]["es"]["coverage_pct"] == 100, cov
    assert cov["locales"]["fr"]["coverage_pct"] == 100, cov
    assert cov["threshold_90pct"] is True


def test_orphaned_ar_locale_removed():
    assert not (REPO_ROOT / "frontend/src/shared/i18n/locales/ar.ts").exists()
    grep = subprocess.run(
        ["grep", "-rn", "locales/ar", "frontend/src"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert grep.stdout == "", f"still referenced: {grep.stdout[:200]}"


def test_i18n_decision_recorded_in_routed_change():
    change = CHANGES / "complete-i18n-or-drop-facade"
    proposal = (change / "proposal.md").read_text(encoding="utf-8")
    assert "## Why" in proposal
    assert "## What Changes" in proposal
    assert "COMPLETE" in proposal, "the complete-or-retire decision must be recorded"
    backlog = BACKLOG.read_text(encoding="utf-8")
    assert "[x] `TICKET=W105-I18N-COMPLETION`" in backlog


# ── 4. SDK `: any` ratchet ────────────────────────────────────────────────


def _fixture_sdk(tmp_path: Path, sources: dict[str, str], count: int) -> Path:
    root = tmp_path / "sdkroot"
    (root / "sdk/js/src").mkdir(parents=True)
    for name, text in sources.items():
        (root / "sdk/js/src" / name).write_text(text)
    baseline = root / "baseline.json"
    baseline.write_text(json.dumps({"sdk/js/src": count}))
    return root


def test_sdk_any_ratchet_planted_site_fails(tmp_path):
    """Growth past the baseline flips the gate — a planted site on a
    fixture tree with a matching baseline."""
    root = _fixture_sdk(tmp_path, {"clean.ts": "export const x = 1;\n"}, 0)
    (root / "sdk/js/src" / "leaky.ts").write_text(
        "export async function f(params?: any): Promise<any> { return params; }\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS.parent / "check_sdk_any_typing.py"),
            "--root",
            str(root),
            "--baseline",
            str(root / "baseline.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr


def test_sdk_any_ratchet_update_shrinks(tmp_path):
    """After a fix wave, --update ratchets the floor down to the new
    count — the gate's real accounting, not a fake."""
    root = _fixture_sdk(tmp_path, {"a.ts": "export const f = (p: any) => p;\n"}, 1)
    baseline = root / "baseline.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS.parent / "check_sdk_any_typing.py"),
            "--root",
            str(root),
            "--baseline",
            str(baseline),
            "--update",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(baseline.read_text()) == {"sdk/js/src": 1}
    # The gate then passes at the new floor.
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS.parent / "check_sdk_any_typing.py"),
            "--root",
            str(root),
            "--baseline",
            str(baseline),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_sdk_any_ratchet_repo_green():
    """The real repo passes at the committed baseline."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS.parent / "check_sdk_any_typing.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_sdk_ratchet_ci_wired():
    wf = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "check_sdk_any_typing.py" in wf, (
        "the ratchet must run in the SDK lint job"
    )


def test_sdk_change_recorded_in_routed_change():
    change = CHANGES / "sdk-any-typing-sweep"
    proposal = (change / "proposal.md").read_text(encoding="utf-8")
    assert "## Why" in proposal
    assert "## What Changes" in proposal
    backlog = BACKLOG.read_text(encoding="utf-8")
    assert "W105-SDK-ANY-TYPING" in backlog
