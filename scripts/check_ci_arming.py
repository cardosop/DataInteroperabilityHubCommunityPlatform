"""CI arming checker (Phase P.8 D2 + Phase U/U.2).

The working branch had zero workflow runs repo-wide since the Actions
minutes ran out, and nothing pinned the arming mechanism — "the paid suite
and gates are wired" was a claim about a YAML file no test parsed. This
checker parses ``.github/workflows/ci.yml`` with duplicate-key detection
(a syntactically dead workflow must never count as armed) and enforces
five invariants so that arming CI for a working branch is a ONE-LINE
trigger change with a burn-controlled, orchestrator-aligned run:

1. The push/pull_request branch lists are SINGLE-SOURCED through a YAML
   anchor — arming a branch is one edit, and the two lists cannot drift.
2. GATE-38 (paid ready() registration ratchet) runs as a BLOCKING step of
   the ``lint`` job. ``_reusable.lint.yml`` is warn-only on PRs
   (``continue-on-error: ${{ inputs.warn-only }}``, default true), so a
   gate that must stop a merge belongs in ``ci.yml``'s lint job.
3. The full-mode paid suite (``test-backend``) runs on every PUSH to an
   armed branch — not only on a PR file filter.
4. Every branch in the armed set ALSO appears in
   ``test-orchestrator.yml``'s trigger lists — arming ci.yml alone leaves
   the reusable warn-only workflow silent on the new branch. The
   orchestrator's own set may be WIDER (it carries the staging suite);
   only ci-armed branches must be covered.
5. ci.yml declares a ``concurrency`` group with
   ``cancel-in-progress: true`` — superseded pushes must not double-spend
   Actions minutes on the included tier (Phase U decision 1).

Executing the arming (adding a branch to the anchored list) remains
operator-gated on Actions billing; this checker only proves that arming
costs one line and nothing is left unaligned.

Wired blocking in ``ci.yml``'s lint job (next to GATE-36/GATE-38) and in
the ``_reusable.lint.yml`` boundary suite list.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

GATE38_RUN_MARKER = "scripts/check_paid_ready_registrations.py"
PAID_SUITE_JOB = "test-backend"
LINT_JOB = "lint"
SECRET_SCAN_JOB = "secret-scan"
TENANT_ID_LINT_JOB = "lint-no-client-tenant-id"


class DuplicateKeySafeLoader(yaml.SafeLoader):
    """SafeLoader that REJECTS duplicate mapping keys.

    PyYAML silently keeps the LAST value for a duplicated key — a workflow
    with a dead duplicate job would parse clean and read as "armed" while
    GitHub rejects the whole file. Same loader contract as
    scripts/tests/test_public_ci_parity.py (the published-workflow guard).
    """

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"duplicate key {key!r} (first defined at line {node.start_mark.line + 1})",
                    node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


# PyYAML's YAML 1.1 resolver turns the bare key ``on:`` into the boolean
# True — GitHub's workflow parser treats it as the literal key 'on'.
# Disable 1.1 bool resolution so trigger lookups and duplicate-key
# detection operate on the same keys GitHub sees (true/false VALUES become
# the strings "true"/"false"; this checker only tests their truthiness,
# which is unaffected).
DuplicateKeySafeLoader.add_constructor(
    "tag:yaml.org,2002:bool", DuplicateKeySafeLoader.construct_yaml_str
)


def load_workflow(path: Path) -> dict:
    """Parse a workflow file; raise on any YAML GitHub would reject."""
    with path.open(encoding="utf-8") as fh:
        return yaml.load(fh, Loader=DuplicateKeySafeLoader)


def collect_violations(doc: dict, orchestrator_doc: dict | None = None) -> list[str]:
    """Return the arming invariants the workflow document violates.

    ``orchestrator_doc`` (test-orchestrator.yml) enables invariant 4
    (armed-branch alignment) — callers that only hold ci.yml pass None and
    get invariants 1-3 + 5.
    """
    violations: list[str] = []

    # 1. Single-sourced branch trigger set (one-line arming).
    on = doc.get("on")
    if not isinstance(on, dict):
        return [
            "ci.yml has no 'on:' trigger block — the armed branch set is not explicit"
        ]
    push_block = on.get("push")
    pr_block = on.get("pull_request")
    push_branches = push_block.get("branches") if isinstance(push_block, dict) else None
    pr_branches = pr_block.get("branches") if isinstance(pr_block, dict) else None
    if not push_branches:
        violations.append(
            "on.push.branches is missing — the armed branch set is not explicit"
        )
    elif not isinstance(push_branches, list) or not push_branches:
        violations.append("on.push.branches must be a non-empty list")
    if pr_branches is None:
        violations.append(
            "on.pull_request.branches is missing — PR coverage of the armed set must be explicit"
        )
    elif push_branches is not pr_branches:
        # PyYAML resolves a YAML anchor to ONE list object; two literal
        # lists are equal but not identical.
        violations.append(
            "on.push.branches and on.pull_request.branches are not "
            "single-sourced through a YAML anchor (&ci-branches) — arming a "
            "branch would need two edits and the lists can drift"
        )

    # 2. GATE-38 blocks in the lint job.
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        return [*violations, "ci.yml has no 'jobs:' block"]
    lint = jobs.get(LINT_JOB)
    if not isinstance(lint, dict) or not lint:
        violations.append(f"ci.yml declares no '{LINT_JOB}' job")
        gate38_steps = []
    else:
        gate38_steps = [
            step
            for step in lint.get("steps", [])
            if isinstance(step, dict) and GATE38_RUN_MARKER in str(step.get("run", ""))
        ]
    if not gate38_steps:
        violations.append(
            f"GATE-38 ({GATE38_RUN_MARKER}) is not wired in the blocking "
            f"'{LINT_JOB}' job — the warn-only _reusable.lint.yml placement "
            "does not satisfy 'gates wired where they block'"
        )
    elif any(step.get("continue-on-error") for step in gate38_steps):
        violations.append(
            "GATE-38 runs with continue-on-error in the lint job — a warn-only "
            "gate cannot block a merge"
        )

    # 3. The full-mode paid suite runs on every push to an armed branch.
    paid_suite = jobs.get(PAID_SUITE_JOB)
    if not isinstance(paid_suite, dict) or not paid_suite:
        violations.append(
            f"ci.yml declares no '{PAID_SUITE_JOB}' job (full-mode paid suite)"
        )
    else:
        condition = str(paid_suite.get("if", ""))
        if condition and "github.event_name == 'push'" not in condition:
            violations.append(
                f"'{PAID_SUITE_JOB}' (paid suite) is gated to PR-only filters — "
                "an armed push must run the paid suite without a filter rewrite"
            )

    # 4. Armed branches are also covered by test-orchestrator.yml (the
    #    reusable warn-only workflow) — arming ci.yml alone leaves it silent.
    if orchestrator_doc is not None and isinstance(push_branches, list):
        orch_on = orchestrator_doc.get("on")
        orch_push = orch_on.get("push") if isinstance(orch_on, dict) else None
        orch_branches = (
            orch_push.get("branches") if isinstance(orch_push, dict) else None
        )
        if not isinstance(orch_branches, list):
            violations.append(
                "test-orchestrator.yml has no on.push.branches list — the "
                "reusable workflow cannot cover the armed set"
            )
        else:
            missing = [b for b in push_branches if b not in orch_branches]
            if missing:
                violations.append(
                    "test-orchestrator.yml does not cover every armed branch: "
                    f"{missing} — arming ci.yml alone leaves the reusable "
                    "warn-only workflow silent on those branches"
                )

    # 5. Burn control: superseded pushes must be cancelled, not double-spent.
    #    The loader disables YAML 1.1 bool resolution (so `on:` stays the
    #    literal trigger key), leaving true/false VALUES as strings — the
    #    check must accept both forms.
    concurrency = doc.get("concurrency")
    if not isinstance(concurrency, dict):
        violations.append(
            "ci.yml declares no 'concurrency' group — superseded pushes "
            "double-spend Actions minutes (Phase U decision 1: included tier)"
        )
    elif concurrency.get("cancel-in-progress") not in (True, "true"):
        violations.append(
            "ci.yml's concurrency group does not set cancel-in-progress: true "
            "— superseded runs keep burning minutes"
        )

    # 6. W0.6 (oss-release-remediation): the secret-scan job must carry
    #    the gitleaks step BLOCKING on every armed push — GITLEAKS_CONFIG
    #    pinned to the repo config, full history fetched (fetch-depth 0),
    #    and no continue-on-error anywhere in the job. A warn-only secret
    #    scan is the vacuity class the W0.2 scan found and fixed.
    secret_scan = jobs.get(SECRET_SCAN_JOB)
    if not isinstance(secret_scan, dict) or not secret_scan:
        violations.append(
            f"ci.yml declares no '{SECRET_SCAN_JOB}' job — gitleaks must "
            "block on every armed push (W0.6)"
        )
    else:
        gitleaks_steps = [
            step
            for step in secret_scan.get("steps", [])
            if isinstance(step, dict) and "gitleaks" in str(step.get("uses", ""))
        ]
        if not gitleaks_steps:
            violations.append(
                f"the '{SECRET_SCAN_JOB}' job carries no gitleaks-action step"
            )
        else:
            for step in gitleaks_steps:
                if "GITLEAKS_CONFIG" not in (step.get("env") or {}):
                    violations.append(
                        "the gitleaks step does not set GITLEAKS_CONFIG "
                        "(.gitleaks.toml) — a config-less scan is vacuous "
                        "(the W0.2 finding)"
                    )
        warn_steps = [
            step
            for step in secret_scan.get("steps", [])
            if isinstance(step, dict) and step.get("continue-on-error")
        ]
        if warn_steps:
            violations.append(
                f"the '{SECRET_SCAN_JOB}' job carries continue-on-error — "
                "a warn-only gitleaks step cannot block a merge (W0.6)"
            )
        checkout_steps = [
            step
            for step in secret_scan.get("steps", [])
            if isinstance(step, dict) and step.get("uses") == "actions/checkout@v4"
        ]
        if checkout_steps and not any(
            (step.get("with") or {}).get("fetch-depth") == 0 for step in checkout_steps
        ):
            violations.append(
                f"the '{SECRET_SCAN_JOB}' checkout does not fetch full "
                "history (fetch-depth 0) — the scan would miss historical "
                "secrets"
            )

    # 7. W1.2b (oss-release-remediation): the no-client-tenant-id lint
    #    (G2) must run BLOCKING in its own job — the anchor rot (drifted
    #    allowlist lines) went undetected while the placement was
    #    warn-only, so a warn-only or missing job is a violation.
    tenant_id_lint = jobs.get(TENANT_ID_LINT_JOB)
    if not isinstance(tenant_id_lint, dict) or not tenant_id_lint:
        violations.append(
            f"ci.yml declares no '{TENANT_ID_LINT_JOB}' job — the client-"
            "tenant-id lint must block on every armed push (W1.2b)"
        )
    else:
        lint_steps = [
            step
            for step in tenant_id_lint.get("steps", [])
            if isinstance(step, dict)
            and "lint_no_client_tenant_id.py" in str(step.get("run", ""))
        ]
        if not lint_steps:
            violations.append(
                f"the '{TENANT_ID_LINT_JOB}' job carries no "
                "lint_no_client_tenant_id.py step (W1.2b)"
            )
        warn_steps = [
            step
            for step in tenant_id_lint.get("steps", [])
            if isinstance(step, dict) and step.get("continue-on-error")
        ]
        if warn_steps:
            violations.append(
                f"the '{TENANT_ID_LINT_JOB}' job carries continue-on-error "
                "— a warn-only tenant-id lint cannot block a merge (W1.2b)"
            )

    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P.8 D2 — CI arming invariants (one-line trigger change)"
    )
    parser.add_argument(
        "--workflow",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / ".github"
        / "workflows"
        / "ci.yml",
    )
    parser.add_argument(
        "--orchestrator",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / ".github"
        / "workflows"
        / "test-orchestrator.yml",
    )
    args = parser.parse_args(argv)

    doc = load_workflow(args.workflow)
    orchestrator_doc = (
        load_workflow(args.orchestrator) if args.orchestrator.exists() else None
    )
    violations = collect_violations(doc, orchestrator_doc)
    for violation in violations:
        print(f"CI-ARMING: {violation}")
    if violations:
        return 1
    print(
        "CI-ARMING: branch set single-sourced, GATE-38 blocking in lint, "
        "paid suite runs on push, orchestrator aligned, burn-controlled"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
