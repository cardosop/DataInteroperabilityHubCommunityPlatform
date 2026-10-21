"""CI arming TDD suite (Phase P.8 D2).

The gate exists because "the paid suite and gates are wired" is a claim
about a YAML file that no test parses: the working branch had zero CI runs
repo-wide since the Actions minutes ran out, and nothing pinned the arming
mechanism. This suite makes the mechanism TESTED: the real
``check_ci_arming.py`` parses ``.github/workflows/ci.yml`` with
duplicate-key detection (a dead workflow must never count as armed) and
pins three invariants:

1. the branch trigger set is SINGLE-SOURCED via a YAML anchor — arming a
   working branch is a one-line change, not a rewrite of two lists that
   can drift;
2. GATE-38 (paid ready() registration ratchet) runs as a BLOCKING step of
   the ``lint`` job — warn-only placement in ``_reusable.lint.yml`` does
   not satisfy "gates wired where they block";
3. the full-mode paid suite (``test-backend``) runs on every push to an
   armed branch.

No mocks: synthetic workflow documents are evaluated by the REAL checker
functions; the final test runs the checker against the real ci.yml.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_ci_arming import (
    DuplicateKeySafeLoader,
    collect_violations,
    load_workflow,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"

GATE38_STEP = {
    "name": "Run paid ready() registration ratchet (GATE-38)",
    "run": "python scripts/check_paid_ready_registrations.py",
}
LINT_JOB = {
    "name": "Lint and Format Check",
    "runs-on": "ubuntu-latest",
    "steps": [GATE38_STEP],
}
PAID_SUITE_JOB = {
    "name": "Backend Tests (pytest)",
    "runs-on": "ubuntu-latest",
    "needs": ["lint"],
    "if": (
        "github.event_name == 'push' ||\n"
        "(github.event_name == 'pull_request' && (\n"
        "  contains(github.event.pull_request.changed_files_names || '', 'hub/')\n"
        "))"
    ),
    "steps": [{"uses": "actions/checkout@v4"}],
}
TENANT_ID_LINT_JOB = {
    "name": "Lint No-Client-Tenant-Id",
    "runs-on": "ubuntu-latest",
    "steps": [
        {"uses": "actions/checkout@v4"},
        {
            "name": "Lint forbidden client-tenant-id reads",
            "run": (
                "python scripts/lint_no_client_tenant_id.py "
                "--root hub/apps "
                "--allowlist lint/no-client-tenant-id-allowlist.yml"
            ),
        },
    ],
}
SECRET_SCAN_JOB = {
    "name": "Secret Scanning (Gitleaks)",
    "runs-on": "ubuntu-latest",
    "steps": [
        {"uses": "actions/checkout@v4", "with": {"fetch-depth": 0}},
        {
            "name": "Run Gitleaks",
            "uses": "gitleaks/gitleaks-action@v2",
            "env": {"GITLEAKS_CONFIG": ".gitleaks.toml"},
        },
    ],
}


def _workflow(
    jobs: dict,
    branches_anchor: bool = True,
    concurrency: bool = True,
    secret_scan: bool = True,
    secret_scan_job: dict | None = None,
    tenant_id_lint: bool = True,
    tenant_id_lint_job: dict | None = None,
) -> str:
    """Render a synthetic ci.yml with the two branch lists single-sourced
    through a YAML anchor (the real arming mechanism) unless asked not to,
    the burn-control concurrency group present unless asked not to, and a
    valid BLOCKING secret-scan job injected unless asked not to (W0.6
    invariant 6). ``secret_scan_job`` substitutes a variant of that job."""
    if branches_anchor:
        on = (
            "on:\n"
            "  push:\n"
            "    branches: &ci-branches [main, develop, release/mvp-v1]\n"
            "  pull_request:\n"
            "    branches: *ci-branches\n"
        )
    else:
        on = (
            "on:\n"
            "  push:\n"
            "    branches: [main, develop, release/mvp-v1]\n"
            "  pull_request:\n"
            "    branches: [main, develop, release/mvp-v1]\n"
        )
    conc = (
        "concurrency:\n  group: ci-${{ github.ref }}\n  cancel-in-progress: true\n"
        if concurrency
        else ""
    )
    if secret_scan:
        jobs = {**jobs, "secret-scan": secret_scan_job or dict(SECRET_SCAN_JOB)}
    if tenant_id_lint:
        jobs = {
            **jobs,
            "lint-no-client-tenant-id": tenant_id_lint_job or dict(TENANT_ID_LINT_JOB),
        }
    dumped = "\n".join("  " + line for line in yaml.safe_dump(jobs).splitlines())
    return on + conc + "jobs:\n" + dumped + "\n"


def _loads(text: str) -> dict:
    """Parse with the REAL checker loader (bool-safe, duplicate-key-safe) —
    the tests must not parse more leniently than the gate does."""
    return yaml.load(text, Loader=DuplicateKeySafeLoader)


class TestBranchTriggerSingleSourcing:
    def test_anchored_branch_list_is_clean(self):
        doc = _loads(
            _workflow({"lint": dict(LINT_JOB), "test-backend": dict(PAID_SUITE_JOB)})
        )
        assert collect_violations(doc) == []

    def test_duplicated_branch_lists_are_a_violation(self):
        """Two literal lists are a rewrite target: arming a branch needs two
        edits and the lists can drift apart — the class this gate exists for."""
        doc = _loads(_workflow({"lint": dict(LINT_JOB)}, branches_anchor=False))
        violations = collect_violations(doc)
        assert any("single-sourced" in v for v in violations), violations

    def test_missing_pull_request_branch_list_is_a_violation(self):
        dumped = "\n".join(
            "  " + line
            for line in yaml.safe_dump({"lint": dict(LINT_JOB)}).splitlines()
        )
        text = (
            "on:\n  push:\n    branches: [main]\n  pull_request:\njobs:\n"
            + dumped
            + "\n"
        )
        violations = collect_violations(_loads(text))
        assert any("pull_request" in v for v in violations), violations


class TestGate38BlockingPlacement:
    def _doc_with_lint_steps(self, steps):
        job = dict(LINT_JOB, steps=steps)
        return _loads(_workflow({"lint": job, "test-backend": dict(PAID_SUITE_JOB)}))

    def test_blocking_gate38_step_is_clean(self):
        assert collect_violations(self._doc_with_lint_steps([GATE38_STEP])) == []

    def test_warn_only_gate38_step_is_a_violation(self):
        """continue-on-error: true = warn-only — the _reusable.lint.yml
        placement does not satisfy 'gates wired where they block'."""
        warn_step = dict(GATE38_STEP, **{"continue-on-error": True})
        violations = collect_violations(self._doc_with_lint_steps([warn_step]))
        assert any("GATE-38" in v and "block" in v for v in violations), violations

    def test_missing_gate38_step_is_a_violation(self):
        violations = collect_violations(
            self._doc_with_lint_steps([{"run": "python scripts/other.py"}])
        )
        assert any("GATE-38" in v for v in violations), violations

    def test_missing_lint_job_is_a_violation(self):
        violations = collect_violations(
            _loads(_workflow({"test-backend": dict(PAID_SUITE_JOB)}))
        )
        assert any("lint" in v for v in violations), violations


class TestPaidSuitePushWiring:
    def test_paid_suite_running_on_push_is_clean(self):
        doc = _loads(
            _workflow({"lint": dict(LINT_JOB), "test-backend": dict(PAID_SUITE_JOB)})
        )
        assert collect_violations(doc) == []

    def test_paid_suite_limited_to_pr_file_filter_is_a_violation(self):
        """A PR-only file filter means an armed push never runs the paid
        suite — arming must cost one line, not a filter rewrite."""
        pr_only = {
            **PAID_SUITE_JOB,
            "if": (
                "github.event_name == 'pull_request' &&\n"
                "contains(github.event.pull_request.changed_files_names || '', 'hub/')"
            ),
        }
        doc = _loads(_workflow({"lint": dict(LINT_JOB), "test-backend": pr_only}))
        violations = collect_violations(doc)
        assert any("test-backend" in v for v in violations), violations

    def test_missing_paid_suite_job_is_a_violation(self):
        violations = collect_violations(_loads(_workflow({"lint": dict(LINT_JOB)})))
        assert any("test-backend" in v for v in violations), violations

    def test_unconditional_paid_suite_job_is_clean(self):
        """No `if` = runs on every trigger of an armed branch — acceptable."""
        job = dict(PAID_SUITE_JOB)
        job.pop("if")
        doc = _loads(_workflow({"lint": dict(LINT_JOB), "test-backend": job}))
        assert collect_violations(doc) == []


class TestSecretScanBlocking:
    """W0.6 invariant 6: gitleaks must BLOCK on every armed push."""

    def test_blocking_secret_scan_job_is_clean(self):
        doc = _loads(
            _workflow({"lint": dict(LINT_JOB), "test-backend": dict(PAID_SUITE_JOB)})
        )
        assert collect_violations(doc) == []

    def test_missing_secret_scan_job_is_a_violation(self):
        doc = _loads(_workflow({"lint": dict(LINT_JOB)}, secret_scan=False))
        violations = collect_violations(doc)
        assert any("secret-scan" in v for v in violations), violations

    def test_warn_only_gitleaks_step_is_a_violation(self):
        job = dict(SECRET_SCAN_JOB)
        job["steps"] = [
            {
                "uses": "gitleaks/gitleaks-action@v2",
                "continue-on-error": True,
                "env": {"GITLEAKS_CONFIG": ".gitleaks.toml"},
            }
        ]
        doc = _loads(_workflow({}, secret_scan_job=job))
        violations = collect_violations(doc)
        assert any("continue-on-error" in v for v in violations), violations

    def test_missing_gitleaks_config_is_a_violation(self):
        job = dict(SECRET_SCAN_JOB)
        job["steps"] = [
            {"uses": "actions/checkout@v4", "with": {"fetch-depth": 0}},
            {"uses": "gitleaks/gitleaks-action@v2"},
        ]
        doc = _loads(_workflow({}, secret_scan_job=job))
        violations = collect_violations(doc)
        assert any("GITLEAKS_CONFIG" in v for v in violations), violations

    def test_shallow_checkout_is_a_violation(self):
        job = dict(SECRET_SCAN_JOB)
        job["steps"] = [
            {"uses": "actions/checkout@v4"},
            {
                "uses": "gitleaks/gitleaks-action@v2",
                "env": {"GITLEAKS_CONFIG": ".gitleaks.toml"},
            },
        ]
        doc = _loads(_workflow({}, secret_scan_job=job))
        violations = collect_violations(doc)
        assert any("fetch-depth" in v for v in violations), violations


class TestLoaderFalsifiability:
    def test_duplicate_key_workflow_is_rejected_by_the_loader(self):
        """A dead workflow must never count as armed: the loader rejects
        duplicate keys the way GitHub's strict parser does."""
        text = "jobs:\n  lint:\n    runs-on: x\n  lint:\n    runs-on: y\n"
        with pytest.raises(yaml.YAMLError, match="'lint'"):
            _loads(text)

    def test_bare_on_key_parses_as_the_literal_trigger_key(self):
        """PyYAML 1.1 turns `on:` into boolean True; GitHub treats it as the
        literal key — the checker's loader must match GitHub."""
        doc = _loads("on:\n  push:\n    branches: [main]\n")
        assert doc.get("on") == {"push": {"branches": ["main"]}}


ORCHESTRATOR_YML = REPO_ROOT / ".github" / "workflows" / "test-orchestrator.yml"


def _orchestrator(branches: list[str]) -> str:
    """Render a synthetic test-orchestrator.yml with the given branch lists."""
    return (
        "on:\n"
        f"  push:\n    branches: {branches}\n"
        f"  pull_request:\n    branches: {branches}\n"
        "workflow_dispatch:\n"
        "jobs:\n  path-filter:\n    runs-on: ubuntu-latest\n"
        "    steps: [{uses: actions/checkout@v4}]\n"
    )


class TestOrchestratorAlignment:
    def test_aligned_orchestrator_is_clean(self):
        doc = _loads(
            _workflow({"lint": dict(LINT_JOB), "test-backend": dict(PAID_SUITE_JOB)})
        )
        orch = _loads(_orchestrator(["main", "develop", "release/mvp-v1"]))
        assert collect_violations(doc, orch) == []

    def test_orchestrator_missing_an_armed_branch_is_a_violation(self):
        """Arming in ci.yml without the orchestrator leaves the reusable
        warn-only workflow silent on the new branch."""
        doc = _loads(
            _workflow({"lint": dict(LINT_JOB), "test-backend": dict(PAID_SUITE_JOB)})
        )
        orch = _loads(_orchestrator(["main", "develop"]))
        violations = collect_violations(doc, orch)
        assert any(
            "release/mvp-v1" in v and "test-orchestrator" in v for v in violations
        ), violations

    def test_orchestrator_extra_branches_are_not_a_violation(self):
        """The orchestrator's own armed set may be wider (it carries the
        staging suite) — only ci-armed branches MUST be covered."""
        doc = _loads(
            _workflow({"lint": dict(LINT_JOB), "test-backend": dict(PAID_SUITE_JOB)})
        )
        orch = _loads(_orchestrator(["main", "develop", "release/mvp-v1", "staging"]))
        assert collect_violations(doc, orch) == []


class TestConcurrencyGroup:
    def test_concurrency_with_cancel_is_clean(self):
        doc = _loads(
            _workflow({"lint": dict(LINT_JOB), "test-backend": dict(PAID_SUITE_JOB)})
        )
        assert collect_violations(doc) == []

    def test_missing_concurrency_group_is_a_violation(self):
        doc = _loads(
            _workflow(
                {"lint": dict(LINT_JOB), "test-backend": dict(PAID_SUITE_JOB)},
                concurrency=False,
            )
        )
        violations = collect_violations(doc)
        assert any("concurrency" in v for v in violations), violations


class TestRealCiYml:
    def test_real_ci_yml_is_armed(self):
        """The RED→GREEN driver: the real workflow must satisfy all
        invariants (anchor, blocking GATE-38, paid suite on push,
        orchestrator alignment, burn-control concurrency)."""
        doc = load_workflow(CI_YML)
        orch = load_workflow(ORCHESTRATOR_YML)
        violations = collect_violations(doc, orch)
        assert violations == [], "\n".join(violations)


class TestTenantIdLintBlocking:
    """W1.2b invariant 7: the no-client-tenant-id lint (G2) must BLOCK on
    every armed push — the anchor-rot class went undetected while the
    placement was warn-only."""

    def test_blocking_tenant_id_lint_job_is_clean(self):
        doc = _loads(
            _workflow({"lint": dict(LINT_JOB), "test-backend": dict(PAID_SUITE_JOB)})
        )
        assert collect_violations(doc) == []

    def test_missing_tenant_id_lint_job_is_a_violation(self):
        doc = _loads(_workflow({"lint": dict(LINT_JOB)}, tenant_id_lint=False))
        violations = collect_violations(doc)
        assert any("lint-no-client-tenant-id" in v for v in violations), violations

    def test_warn_only_tenant_id_lint_is_a_violation(self):
        job = dict(TENANT_ID_LINT_JOB)
        job["steps"] = [
            {"uses": "actions/checkout@v4"},
            {
                "run": "python scripts/lint_no_client_tenant_id.py --root hub/apps",
                "continue-on-error": True,
            },
        ]
        doc = _loads(_workflow({}, tenant_id_lint_job=job))
        violations = collect_violations(doc)
        assert any("continue-on-error" in v for v in violations), violations

    def test_job_without_the_lint_step_is_a_violation(self):
        job = dict(TENANT_ID_LINT_JOB)
        job["steps"] = [{"uses": "actions/checkout@v4"}]
        doc = _loads(_workflow({}, tenant_id_lint_job=job))
        violations = collect_violations(doc)
        assert any("lint_no_client_tenant_id.py" in v for v in violations), violations
