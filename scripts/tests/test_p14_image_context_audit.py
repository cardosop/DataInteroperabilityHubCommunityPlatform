"""
P0-14 (close-oss-release-conditions, G5) — image-context audit pins.

The audit answers: which published images bake credential material,
regardless of the git rewrite? Pins, each at the weakest point:

1. **The live-token exposure root cause is closed**: the tracked
   `.claude/settings.json` (a real `sk-` bearer token, baked by every
   backend image's `COPY . .`) is untracked, the root .dockerignore
   excludes `.claude/`, and the house gitleaks config carries an
   anthropic rule (the scanner gap that let the token ride through the
   P0-9 tracked-tree scan).
2. **The audit tool is real**: planted fixtures prove it flags a baked
   `.env` and passes a dockerignored one; the inventory covers every
   image the deploy workflow pushes; the real-repo run is clean.
3. **The P2-6 input exists**: the committed audit doc carries the
   affected-image list (every tag published before the rotations).

No mocks: real git, real gitleaks, real Dockerfile parsing, real
workflow YAML.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS.parent))

from envpolicy import skip_or_fail

_spec = importlib.util.spec_from_file_location(
    "audit_image_build_contexts", SCRIPTS.parent / "audit_image_build_contexts.py"
)
assert _spec is not None, "audit_image_build_contexts.py must load (P0-14)"
assert _spec.loader is not None, "audit_image_build_contexts.py must carry a loader"
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

GITLEAKS = subprocess.run(
    ["sh", "-c", "command -v gitleaks"], capture_output=True, text=True, check=False
).stdout.strip()
CONFIG = REPO_ROOT / ".gitleaks.toml"
DEPLOY_WF = REPO_ROOT / ".github/workflows/deploy.yml"
DOC = REPO_ROOT / "docs/operations/image-context-audit-2026-10-19.md"

PLANTED_TOKEN = "sk-ant-test1234567890abcdefghijklmnop"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


# ── 1. The live-token exposure root cause ─────────────────────────────────


def test_root_dockerignore_excludes_claude_and_env():
    text = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert ".env*" in text
    assert ".claude/" in text, (
        ".claude/ was baked by every `COPY . .` backend image — the "
        "settings file carried a live sk- token"
    )


def test_claude_settings_not_tracked():
    tracked = _git("ls-files", ".claude/settings.json")
    assert tracked == "", (
        "the dev Claude config (live token) must not ship in the repo — "
        "it is already gitignored; tracking it was the anomaly"
    )


def test_gitleaks_config_catches_anthropic_tokens(tmp_path):
    """RED-first: a planted sk-ant token must trip the REAL scan with
    the house config — the rule gap that let the live token pass the
    P0-9 tracked-tree scan."""
    if not GITLEAKS:
        skip_or_fail("gitleaks binary (the pin runs the real scanner)")
    planted = tmp_path / "planted.txt"
    planted.write_text(f'ANTHROPIC_AUTH_TOKEN = "{PLANTED_TOKEN}"\n')
    result = subprocess.run(
        [
            GITLEAKS,
            "detect",
            "--no-git",
            "--source",
            str(planted),
            "--config",
            str(CONFIG),
            "--report-format",
            "json",
            "--report-path",
            str(tmp_path / "report.json"),
            "--no-banner",
            "--log-level=error",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, "the planted token must trip the scan"


# ── 2. The audit tool ─────────────────────────────────────────────────────


def _fixture_context(tmp_path: Path, files: dict[str, str], dockerfile: str):
    root = tmp_path / "ctx"
    root.mkdir()
    for name, content in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    (root / "Dockerfile").write_text(dockerfile)
    return root


def test_audit_flags_planted_baked_env(tmp_path):
    """A Dockerfile COPYing a real .env into the image is a finding —
    the shape the pre-rewrite CI checkouts baked at every build."""
    root = _fixture_context(
        tmp_path,
        {"svc/.env": "STAGING_SECRET=abc\n", "svc/app.py": "print(1)\n"},
        "FROM scratch\nCOPY svc/ /app/\n",
    )
    findings = audit.audit_context(
        root, audit.parse_dockerfile_copies(root / "Dockerfile")
    )
    assert any("svc/.env" in f for f in findings), findings


def test_audit_clean_when_dockerignored(tmp_path):
    """A .env excluded by .dockerignore is NOT a finding — the
    dockerignore is the boundary the audit respects."""
    root = _fixture_context(
        tmp_path,
        {
            "svc/.env": "LOCAL_ONLY=1\n",
            "svc/app.py": "print(1)\n",
            ".dockerignore": ".env*\n",
        },
        "FROM scratch\nCOPY svc/ /app/\n",
    )
    findings = audit.audit_context(
        root,
        audit.parse_dockerfile_copies(root / "Dockerfile"),
        dockerignore=root / ".dockerignore",
    )
    assert findings == [], findings


def test_audit_treats_env_templates_as_safe(tmp_path):
    root = _fixture_context(
        tmp_path,
        {
            "svc/.env.example": "TEMPLATE=1\n",
            "svc/.env.production.template": "TEMPLATE=2\n",
        },
        "FROM scratch\nCOPY svc/ /app/\n",
    )
    findings = audit.audit_context(
        root, audit.parse_dockerfile_copies(root / "Dockerfile")
    )
    assert findings == [], findings


def test_dockerfile_copy_resolution_handles_continuations_and_from():
    """Real Dockerfile syntax: multi-line continuations, --from stage
    refs (not context content), and quoted paths."""
    dockerfile = (
        "FROM alpine AS base\n"
        "COPY requirements.txt \\\n"
        "    extra.txt ./\n"
        "COPY --from=builder /out /app\n"
        "COPY 'svc/x.txt' /app/\n"
    )
    copies = audit.parse_dockerfile_copies_via_text(dockerfile)
    assert "requirements.txt" in copies
    assert "extra.txt" in copies
    assert "svc/x.txt" in copies
    assert not any(c.startswith("/out") for c in copies), copies


def test_inventory_covers_every_pushed_image():
    """The inventory is derived from the deploy workflow — every image
    the CI pushes must be audited (a new image without a context audit
    fails here). The dormant inference-service lane was DELETED in P2-6
    (delete-or-wire disposition) — it is no longer part of the push
    inventory."""
    images = audit.load_inventory(DEPLOY_WF)
    expected = {
        "api-service",
        "worker-service",
        "compliance-service",
        "prefect-integration-service",
        "semantic-service",
        "dq-service",
        "datacontract-service",
        "frontend",
        "product-site",
    }
    names = {entry["service"] for entry in images}
    assert expected == names, f"inventory drift: {expected ^ names}"


def test_audit_repo_run_clean():
    """The real repo audits clean after the P0-14 root fixes: no baked
    .env, no credential findings in the COPY'd content."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS.parent / "audit_image_build_contexts.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-1500:] + result.stderr[-500:]


# ── 3. The P2-6 input ─────────────────────────────────────────────────────


def test_audit_ci_wired_into_build_job():
    """The audit gates the deploy build job itself — findings stop the
    job BEFORE any image is pushed, on the runner that builds."""
    wf = DEPLOY_WF.read_text(encoding="utf-8")
    assert "scripts/audit_image_build_contexts.py" in wf, (
        "the audit must run in the deploy workflow's build job"
    )


def test_audit_report_doc_lists_affected_images():
    text = DOC.read_text(encoding="utf-8")
    assert "affected" in text.lower(), "the P2-6 input must name the affected images"
    assert "rebuild" in text.lower()
    assert ".claude/settings.json" in text, (
        "the live-token exposure must be recorded in the report"
    )


def test_house_config_still_scans_clean_tracked_tree(tmp_path):
    """After untracking .claude/settings.json, the tracked-tree scan
    stays clean with the NEW anthropic rule (the rule must not
    false-positive on the repo)."""
    if not GITLEAKS:
        skip_or_fail("gitleaks binary (the regression scan runs the real scanner)")
    staging = tmp_path / "tracked"
    staging.mkdir()
    for line in _git("ls-files").splitlines():
        if not line:
            continue
        src = REPO_ROOT / line
        if not src.is_file():
            continue
        dst = staging / line
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    result = subprocess.run(
        [
            GITLEAKS,
            "detect",
            "--no-git",
            "--source",
            ".",
            "--config",
            str(CONFIG),
            "--no-banner",
            "--log-level=error",
        ],
        cwd=staging,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-800:]
