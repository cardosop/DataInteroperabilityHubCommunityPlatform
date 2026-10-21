"""TDD parity pin for the ci-lint-local rehearsal target (Phase U / U.2).

The rehearsal must run the EXACT gate sequence the ci.yml ``lint`` job
runs — a rehearsal that omits a gate is worse than no rehearsal (it
manufactures false confidence). This suite parses the REAL ci.yml lint
job and the REAL Makefile target and asserts that every gate-shaped
command in the job appears in the target. Django-dependent steps are
allowed to run in-container (the repo's convention); the parity pin is
on the command's GATE, not its container prefix.

No mocks: both sides are parsed from the real committed files with the
same duplicate-key-safe loader the arming checker uses.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_ci_arming import load_workflow

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
MAKEFILE = REPO_ROOT / "Makefile"

# Command signatures that MUST appear in the rehearsal target when they
# appear in the lint job's run: blocks.
_GATE_SIGNATURES = (
    "check_lint_debt_ratchet.py",  # GATE-35
    "check_mypy_debt_ratchet.py",  # GATE-36
    "check_paid_ready_registrations.py",  # GATE-38
    "check_ci_arming.py",  # P.8 D2
    "check_zero_assertion_tests.py",  # GATE-39
    "check_skip_expiry.py",  # GATE-40
    "check_codeowners_paths.py",  # GATE-41
    "check_core_test_scope.py",  # W14
    "makemigrations --check",  # GATE-12 blocking twin
    "check_throttle_coverage",  # Phase 273.7.3
    "spec_from_file_location",  # import-shape ban
    "_SSRF_BLOCKED_NETWORKS",  # SSRF-list ban
    "validate_openspec_change.py",  # GATE-30 repo validator
    "ruff format --check",  # format gate
    "lint-test-sleeps.sh",  # Phase 84 sleeps threshold
    "lint_cli_sdk_openapi_parity.py",  # 277.B.083 parity ratchet
    "lint_no_client_tenant_id.py",  # tenant-scope guard
)


def lint_job_run_blocks() -> list[str]:
    """Every `run:` block (scalar + literal) across the ci.yml LINT FAMILY
    (jobs named lint* — the standalone gates like lint-test-sleeps and
    lint-cli-sdk-openapi-parity are their own jobs, not lint-job steps)."""
    doc = load_workflow(CI_YML)
    blocks: list[str] = []
    for name, job in doc.get("jobs", {}).items():
        if not str(name).lower().startswith("lint"):
            continue
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []):
            if not isinstance(step, dict):
                continue
            run = step.get("run")
            if isinstance(run, str):
                blocks.append(run)
            elif isinstance(run, list):
                blocks.extend(str(line) for line in run)
    return blocks


def makefile_target_body() -> str:
    """The ci-lint-local target recipe from the real Makefile."""
    lines = MAKEFILE.read_text(encoding="utf-8").splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("ci-lint-local:"):
            start = i
            break
    assert start is not None, "Makefile has no ci-lint-local target"
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("\t"):
            body.append(line.strip())
        elif line.strip() == "":
            continue
        else:
            break
    return "\n".join(body)


class TestRealParity:
    def test_every_lint_job_gate_is_rehearsed(self):
        """Any gate present in the lint job's run blocks must appear in
        the rehearsal target — the drift this pin exists to catch."""
        blocks = lint_job_run_blocks()
        joined = "\n".join(blocks)
        body = makefile_target_body()
        missing = [sig for sig in _GATE_SIGNATURES if sig in joined and sig not in body]
        assert missing == [], (
            "ci-lint-local omits gate command(s) present in the ci.yml lint "
            f"job — the rehearsal would manufacture false confidence: {missing}"
        )

    def test_target_contains_no_unknown_gate_commands(self):
        """Reverse direction: the rehearsal must not run gate scripts the
        lint job does not (a stricter local rehearsal surprises authors)."""
        blocks = lint_job_run_blocks()
        joined = "\n".join(blocks)
        body = makefile_target_body()
        unknown = [sig for sig in _GATE_SIGNATURES if sig in body and sig not in joined]
        assert unknown == [], (
            f"ci-lint-local runs gate command(s) absent from the lint job: {unknown}"
        )
