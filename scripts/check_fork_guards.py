#!/usr/bin/env python3
"""GATE-56 (oss-release-remediation W7.3) — fork-safety gate for CI workflows.

GitHub never passes repository secrets to a fork-PR run (dependabot PRs
count as forks), so any workflow that (a) triggers on ``pull_request``
and (b) uses a secret other than ``GITHUB_TOKEN`` FAILS on fork PRs
unless the secret-using path is guarded. W7.3 pins the contract:

  * every non-GITHUB_TOKEN secret use inside a pull_request-triggered
    workflow must sit behind one of:
      - a job-level ``if`` fork guard (``head.repo.fork``),
      - a step-level ``if`` fork guard on every secret-using step,
      - a job-level ``if`` that excludes pull_request events
        (push/schedule/dispatch/…-only jobs never run on fork PRs),
      - a token-presence self-skip (``[ -n "${{ secrets.X }}" ]`` or
        ``[ -n "${{ env.X }}" ]`` — the chromatic.yml pattern);
  * guards must use the canonical expression
    ``github.event.pull_request.head.repo.fork`` (a typo'd guard is dead);
  * visual-regression.yml carries the named W7.3 fix: the Chromatic job
    is fork-guarded AND token-self-skipping, and a fork-only
    storybook build-smoke job exists so fork PRs stay green;
  * the shipped overlay's DCO job ranges over the PR commits
    (``base.sha..head.sha`` — the GitHub-synthesized merge commit at
    HEAD is unsigned by design and would fail every DCO check), never
    ``origin/<base>`` (the fork's own — possibly stale — branch copy).

``pull_request_target`` workflows are EXEMPT: they run in the base-repo
context where secrets ARE available (their risks are the checkout-of-
untrusted-code class, out of this gate's scope).

Exit 0 clean; 1 violations; 2 usage error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover - CI installs pyyaml explicitly
    _yaml = None

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIRS = (
    _REPO_ROOT / ".github" / "workflows",
    _REPO_ROOT / "scripts" / "publish_public_overlay" / ".github" / "workflows",
)
ALLOWLIST_DEFAULT = _REPO_ROOT / "scripts" / "fork_guards_allowlist.txt"

_SECRET_RE = re.compile(r"secrets\.([A-Za-z0-9_]+)")
_FORK_GUARD = "github.event.pull_request.head.repo.fork"
# Word boundary: `head.repo.forked` must NOT count as the canonical guard.
_FORK_GUARD_RE = re.compile(r"github\.event\.pull_request\.head\.repo\.fork\b")
# Events that never occur on a pull_request run: a job whose `if`
# mentions event_name and enables ONLY these can't run on fork PRs.
_EVENT_ONLY_NAMES = (
    "push",
    "schedule",
    "workflow_dispatch",
    "workflow_call",
    "release",
    "workflow_run",
    "deployment",
)
_SELF_SKIP_RE = re.compile(r'-[nz]\s+"\$\{\{\s*(?:secrets|env)\.([A-Za-z0-9_]+)\s*\}\}"')


def _load_workflow(path: Path) -> dict:
    if _yaml is None:  # pragma: no cover
        raise SystemExit("pyyaml is required")
    return _yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _trigger(workflow: dict):
    # pyyaml implements YAML 1.1, where the bare key `on:` parses as the
    # boolean True — look under True, "on", and "true" alike.
    for key in ("on", True, "true"):
        if key in workflow:
            return workflow[key]
    return {}


def _is_pr_triggered(workflow: dict) -> bool:
    on = _trigger(workflow)
    if on is True or on is None:
        return True
    if isinstance(on, str):
        return on in ("pull_request", "pull_request_target")
    if isinstance(on, list):
        return "pull_request" in on or "pull_request_target" in on
    if isinstance(on, dict):
        return "pull_request" in on or "pull_request_target" in on
    return False


def _is_pr_target(workflow: dict) -> bool:
    on = _trigger(workflow)
    if isinstance(on, dict):
        return "pull_request_target" in on
    return False


def _event_restricted(if_expr: str) -> bool:
    """True when the `if` cannot be true on a pull_request run.

    Compound `||` expressions count as restricted only when EVERY branch
    is event-safe: a typo'd fork guard (``head.repo.forked == false``)
    beside ``event_name != 'pull_request'`` re-enables the job on fork
    PRs (GitHub treats the unknown property as empty → ``== false`` is
    true), so a mixed branch must not inherit the exclusion.
    """
    if not if_expr or "github.event_name" not in if_expr:
        return False

    def _branch_safe(branch: str) -> bool:
        if "github.event_name" not in branch:
            return False
        if re.search(
            r"github\.event_name\s*!=\s*['\"]pull_request['\"]", branch
        ):
            return True
        targets = re.findall(
            r"github\.event_name\s*==\s*['\"]([a-z_]+)['\"]", branch
        )
        return bool(targets) and "pull_request" not in targets and all(
            t in _EVENT_ONLY_NAMES for t in targets
        )

    branches = if_expr.split("||")
    return all(_branch_safe(branch) for branch in branches)


def _fork_guarded(if_expr: str) -> bool:
    return bool(_FORK_GUARD_RE.search(if_expr))


def _self_skipped(job: dict, secret: str) -> bool:
    """The chromatic.yml pattern: the secret's presence is probed before
    any real use, so an unset secret (forks/unprovisioned) skips."""
    for step in job.get("steps", []):
        for line in step.get("run", "").splitlines():
            match = _SELF_SKIP_RE.search(line)
            if match and match.group(1) == secret:
                return True
    return False


def _secret_step_guards(job: dict) -> dict[str, bool]:
    """Per-secret: is every USING step covered by a step-level guard?"""
    per_secret: dict[str, bool] = {}
    for step in job.get("steps", []):
        text = str(step)
        if_expr = str(step.get("if", ""))
        guarded = _fork_guarded(if_expr) or _event_restricted(if_expr)
        for name in sorted(set(_SECRET_RE.findall(text))):
            if name == "GITHUB_TOKEN":
                continue
            # Every step that references the secret must be guarded.
            per_secret[name] = per_secret.get(name, True) and guarded
    return per_secret


def collect_violations(
    workflow_dir: Path, allowlist: set[tuple[str, str, str]] | None = None
) -> list[str]:
    allowlist = allowlist or set()
    violations: list[str] = []
    for path in sorted(workflow_dir.glob("*.yml")):
        workflow = _load_workflow(path)
        if not _is_pr_triggered(workflow):
            continue
        if _is_pr_target(workflow):
            continue
        rel = path.name
        jobs = workflow.get("jobs") or {}
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            job_if = str(job.get("if", ""))
            if _fork_guarded(job_if) or _event_restricted(job_if):
                continue
            step_guards = _secret_step_guards(job)
            for secret, covered in step_guards.items():
                if covered or _self_skipped(job, secret):
                    continue
                if (rel, job_name, secret) in allowlist:
                    continue
                violations.append(
                    f"{rel}: job {job_name!r} uses secrets.{secret} with no "
                    "fork guard (job/step) and no token-presence self-skip"
                )
        # The named W7.3 fix — visual-regression.yml must be fork-green
        # by construction, not just by the generic rules.
        if rel == "visual-regression.yml":
            violations.extend(_visual_regression_checks(workflow))
    return violations


def _load_allowlist(path: Path) -> set[tuple[str, str, str]]:
    """`workflow:job:secret:reason` triples; malformed lines fail loudly."""
    triples: set[tuple[str, str, str]] = set()
    if not path.exists():
        return triples
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(":", 3)
        if len(parts) != 4 or not all(parts[:3]):
            print(
                f"{path}:{lineno}: malformed allowlist line (expected "
                "workflow:job:secret:reason)",
                file=sys.stderr,
            )
            raise SystemExit(2)
        triples.add((parts[0], parts[1], parts[2]))
    return triples


def _dead_allowlist_anchors(
    dirs: list[Path], allowlist: set[tuple[str, str, str]]
) -> list[str]:
    """A listed triple must still match its file/job/secret — the repo's
    dead-anchors-fail convention."""
    workflows: dict[str, dict] = {}
    for directory in dirs:
        for path in directory.glob("*.yml"):
            workflows[path.name] = _load_workflow(path)
    dead: list[str] = []
    for wf, job_name, secret in sorted(allowlist):
        workflow = workflows.get(wf)
        if workflow is None:
            dead.append(f"allowlist anchor {wf}:{job_name}:{secret}: file missing")
            continue
        job = (workflow.get("jobs") or {}).get(job_name)
        if not isinstance(job, dict):
            dead.append(f"allowlist anchor {wf}:{job_name}:{secret}: job missing")
            continue
        if secret not in _SECRET_RE.findall(str(job)):
            dead.append(
                f"allowlist anchor {wf}:{job_name}:{secret}: secret unused in job"
            )
    return dead


def _visual_regression_checks(workflow: dict) -> list[str]:
    problems: list[str] = []
    chromatic_job = None
    for name, job in (workflow.get("jobs") or {}).items():
        if isinstance(job, dict) and "CHROMATIC_PROJECT_TOKEN" in str(job):
            chromatic_job = (name, job)
    if chromatic_job is None:
        return ["visual-regression.yml: no job references CHROMATIC_PROJECT_TOKEN"]
    name, job = chromatic_job
    job_if = str(job.get("if", ""))
    if not _fork_guarded(job_if):
        problems.append(
            f"visual-regression.yml: Chromatic job {name!r} has no fork guard"
        )
    if not _self_skipped(job, "CHROMATIC_PROJECT_TOKEN"):
        problems.append(
            f"visual-regression.yml: Chromatic job {name!r} has no "
            "token-presence self-skip"
        )
    fork_smoke = any(
        isinstance(j, dict)
        and _fork_guarded(str(j.get("if", "")))
        and "== true" in str(j.get("if", ""))
        for j in (workflow.get("jobs") or {}).values()
    )
    if not fork_smoke:
        problems.append(
            "visual-regression.yml: no fork-only storybook build-smoke job"
        )
    return problems


def _overlay_dco_violations(workflow_dir: Path) -> list[str]:
    problems: list[str] = []
    for path in sorted(workflow_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"check_dco\.sh\s+[\"']([^\"']+)", text):
            arg = match.group(1)
            if "origin/" in arg or "head.sha" not in arg:
                problems.append(
                    f"{path.name}: DCO range {arg!r} must be "
                    "base.sha..head.sha (PR commits only — HEAD is the "
                    "synthetic merge commit, which GitHub never signs)"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GATE-56 — fork-safety gate for CI workflows (W7.3)"
    )
    parser.add_argument(
        "--workflow-dir",
        action="append",
        default=[],
        help="workflow dir to check (repeatable; default: both trees)",
    )
    parser.add_argument(
        "--allowlist",
        default=str(ALLOWLIST_DEFAULT),
        help="allowlist file (workflow:job:secret:reason triples)",
    )
    parser.add_argument(
        "--check-dead-anchors",
        action="store_true",
        help="run dead-anchor accounting even on scoped --workflow-dir runs",
    )
    args = parser.parse_args(argv)

    dirs = [Path(d) for d in (args.workflow_dir or DEFAULT_DIRS)]
    allowlist = _load_allowlist(Path(args.allowlist))
    problems: list[str] = []
    for directory in dirs:
        if not directory.is_dir():
            print(f"error: not a directory: {directory}", file=sys.stderr)
            return 2
        problems.extend(collect_violations(directory, allowlist))
        problems.extend(_overlay_dco_violations(directory))
    # Dead-anchor accounting needs the FULL tree (a scoped --workflow-dir
    # run legitimately lacks files the allowlist names); the flag forces
    # it for planted-violation pins.
    if not args.workflow_dir or args.check_dead_anchors:
        problems.extend(_dead_allowlist_anchors(dirs, allowlist))

    if problems:
        print("fork-guard check FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("fork-guard check clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
