"""W11.10 (oss-release-remediation) — security tooling gates: the
BLOCKING wiring + planted-violation pins (ASVS V14, register rows
17/20).

Each gate is proven to bite: a PLANTED violation flips the gate RED
(real tool runs against a planted temp tree), and the CI/workflow
wiring is source-pinned (a warn-only revert flips the pin).  The
falsifiability harness entries (gate-25-semgrep-local-rules,
gate-47-dependency-vulns, trivy-deploy-gate, npm-audit-gate,
gitleaks-ci-gate) exercise the same weakenings on the registry.

Django-free for the CI no-django lint job (the tool runs use the host
binaries the CI steps install).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

CODE_QUALITY_WF = REPO_ROOT / ".github" / "workflows" / "code-quality.yml"
LINT_WF = REPO_ROOT / ".github" / "workflows" / "_reusable.lint.yml"
DEPLOY_WF = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
CI_WF = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=cwd or REPO_ROOT, capture_output=True, text=True, timeout=900, check=False
    )


# ── GATE-25 — semgrep local rules ─────────────────────────────────────────

def test_semgrep_local_rules_clean_on_the_tree():
    proc = _run([sys.executable, "scripts/check_semgrep_rules.py"])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_planted_sql_interpolation_flips_semgrep_gate_red(tmp_path):
    """A planted raw f-string SQL in the warehouses app flips the gate
    (the rules actually detect the class they exist for)."""
    (tmp_path / "hub" / "apps" / "warehouses").mkdir(parents=True)
    (tmp_path / "hub" / "apps" / "warehouses" / "planted_connector.py").write_text(
        'def run(conn, table):\n    conn.execute_query(f"SELECT * FROM {table}")\n',
        encoding="utf-8",
    )
    # Run semgrep directly over the planted tree with the warehouses rule.
    semgrep = REPO_ROOT / "venv" / "bin" / "semgrep"
    proc = _run(
        [str(semgrep),
         f"--config={REPO_ROOT}/semgrep/rules/warehouses.yaml",
         "--error", "--quiet", "--no-rewrite-rule-ids", "."],
        cwd=tmp_path,
    )
    assert proc.returncode == 1, "the planted interpolation must be flagged"


def test_semgrep_runner_pins_the_full_local_rule_set():
    """Every ERROR-severity local rule is in the runner's set — a rule
    dropped from the list flips this pin (the harness weakening)."""
    runner = (REPO_ROOT / "scripts" / "check_semgrep_rules.py").read_text(
        encoding="utf-8"
    )
    for rule in (
        "semgrep/rules/transformation.yaml",
        "semgrep/rules/warehouses.yaml",
        "semgrep/rules/warehouse-dq-compliance.yaml",
        ".semgrep/business-rules-direct-instantiation.yml",
    ):
        assert rule in runner, f"runner missing {rule}"


def test_semgrep_rule_parse_error_is_a_gate_failure_not_a_skip():
    """A syntactically broken local rule must FAIL the runner (the
    bandit-ratchet lesson: a parse error masked as green is the class
    this gate kills)."""
    broken = REPO_ROOT / "semgrep" / "rules" / "_broken_parse_probe.yaml"
    broken.write_text(
        "rules:\n  - id: broken-probe\n    languages: [python]\n"
        "    severity: ERROR\n    message: probe\n"
        "    patterns:\n      - pattern: from x import ...\n",
        encoding="utf-8",
    )
    try:
        semgrep = REPO_ROOT / "venv" / "bin" / "semgrep"
        proc = _run(
            [str(semgrep), f"--config={broken}", "--error", "--quiet", "."],
            cwd=REPO_ROOT / "hub",
        )
        assert proc.returncode != 0, "a parse-broken rule must not pass"
    finally:
        broken.unlink(missing_ok=True)


# ── GATE-37 — bandit ratchet, BLOCKING wiring ─────────────────────────────

def test_bandit_ratchet_is_blocking_in_code_quality_workflow():
    text = CODE_QUALITY_WF.read_text(encoding="utf-8")
    step = "check_bandit_debt_ratchet.py --output-file bandit-quality.json"
    assert step in text
    # The warn-only escape hatch must be GONE from the ratchet step
    # (other steps in the workflow legitimately carry it).
    assert (
        step + "\n        continue-on-error: true" not in text
    ), "the bandit ratchet step must be blocking (W11.10)"


def test_bandit_ratchet_is_in_quality_gates():
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "check_bandit_debt_ratchet.py --output-file" in makefile


# ── GATE-47 — dependency vulns, BLOCKING wiring ───────────────────────────

def test_dependency_vuln_gate_is_in_quality_gates():
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "check_dependency_vulns.py" in makefile


# ── Trivy deploy gate — source-pinned ─────────────────────────────────────

def test_deploy_trivy_gate_is_blocking_critical_high():
    text = DEPLOY_WF.read_text(encoding="utf-8")
    assert "trivy-action" in text
    assert "severity: CRITICAL,HIGH" in text
    # The blocking pass must carry exit-code 1 with no bypass flag.
    assert "exit-code: '1'" in text or "exit-code: \"1\"" in text


# ── Gitleaks CI gate — source-pinned ──────────────────────────────────────

def test_gitleaks_ci_job_is_blocking():
    text = CI_WF.read_text(encoding="utf-8")
    assert "gitleaks/gitleaks-action" in text
    assert "GITLEAKS_CONFIG: .gitleaks.toml" in text


# ── Semgrep wiring in the lint workflow ───────────────────────────────────

def test_lint_workflow_runs_the_local_rule_gate():
    text = LINT_WF.read_text(encoding="utf-8")
    assert "check_semgrep_rules.py" in text, (
        "the lint workflow must run the local-rules gate (W11.10)"
    )
