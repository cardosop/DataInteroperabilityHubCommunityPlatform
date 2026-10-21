#!/usr/bin/env python3
"""
P2-2 (close-oss-release-conditions) — the G4 Actions review.

GitHub retains Actions run logs and artifacts independently of the git
rewrite; any run that printed or stored secret values keeps them until
its retention expires. This tool produces the review:

  plan (default) — enumerate the repository's workflow runs and their
      artifacts via the REAL GitHub API and classify artifacts into
      the value-carrier class (trace/network/junit/E2E recordings —
      the same class the P2-0 scan found carrying test-stack tokens)
      vs inert artifacts; print the review table (counts + classes,
      no values).  Exit 0 when the remote is readable.

  --inspect-run ID — download the run's log archive into --out-dir
      (0600), unzip it, and scan it with the REAL gitleaks binary and
      the REAL house config. Findings are named by rule/file — values
      are never printed.  Exit 0 clean / 1 findings / 2 tooling or
      API failure (fail-closed: an unresolvable run is a FAILURE,
      never a silent "clean").

The purge decisions are recorded from the review output (the window
runner prints them after the sweep); the deletion commands are the
runbook's post-review steps.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

CARRIER_PATTERNS = (
    "trace", "network", "junit", "e2e", "playwright", "recording",
    "test-results", "load-test", "k6",
)


def carrier_artifact(name: str) -> bool:
    """The value-carrier class: artifacts whose names match the
    trace/network/junit/E2E recording classes (the P2-0 scan's
    carrier files)."""
    lowered = name.lower()
    return any(pattern in lowered for pattern in CARRIER_PATTERNS)


def _gh(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=False
    )


def _api_json(*args: str) -> list:
    """gh api + --jq + --paginate emits newline-delimited JSON objects
    (one per row, per page); a plain call emits one JSON array. Parse
    both shapes."""
    result = _gh("api", *args)
    if result.returncode != 0:
        raise RuntimeError(f"gh api failed: {result.stderr.strip()[:200]}")
    try:
        loaded = json.loads(result.stdout or "[]")
        return loaded if isinstance(loaded, list) else [loaded]
    except json.JSONDecodeError:
        rows = []
        for raw in result.stdout.splitlines():
            row = raw.strip()
            if row:
                rows.append(json.loads(row))
        return rows


def enumerate_runs(slug: str, limit: int = 30) -> list[dict]:
    return _api_json(
        f"repos/{slug}/actions/runs?per_page={limit}",
        "--jq",
        ".workflow_runs[] | {id, name, headBranch, createdAt, status}",
    )


def enumerate_artifacts(slug: str) -> list[dict]:
    return _api_json(
        f"repos/{slug}/actions/artifacts?per_page=100",
        "--jq",
        ".artifacts[] | {name, size: .size_in_bytes, expired, "
        "workflow: .workflow_run.head_branch}",
    )


def review(slug: str, run_limit: int) -> dict:
    runs = enumerate_runs(slug, run_limit)
    artifacts = enumerate_artifacts(slug)
    carrier = [a for a in artifacts if carrier_artifact(a["name"])]
    expired = [a for a in artifacts if a.get("expired")]
    return {
        "runs": len(runs),
        "artifacts": len(artifacts),
        "carrier": carrier,
        "expired": expired,
    }


def inspect_run(slug: str, run_id: str, out_dir: Path) -> tuple[int, list[str]]:
    """Download the run's logs and gitleaks-scan them. (code, problems)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o700)
    archive = out_dir / "logs.zip"
    result = _gh(
        "api", f"repos/{slug}/actions/runs/{run_id}/logs",
    )
    if result.returncode != 0:
        return 2, [f"log download failed for run {run_id}: {result.stderr.strip()[:200]}"]
    archive.write_bytes(result.stdout.encode("latin-1"))
    os.chmod(archive, 0o600)
    extracted = out_dir / "logs"
    extracted.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(extracted)
    except zipfile.BadZipFile:
        return 2, [f"log archive for run {run_id} is not a zip — fail-closed"]
    gitleaks = shutil.which("gitleaks")
    if not gitleaks:
        return 2, ["gitleaks binary not found — the inspection cannot be skipped"]
    report = out_dir / "report.json"
    scan = subprocess.run(
        [
            gitleaks, "detect", "--source", str(extracted),
            "--no-git", "--config", ".gitleaks.toml",
            "--report-format", "json", "--report-path", str(report),
            "--no-banner", "--log-level=warn",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if scan.returncode not in (0, 1):
        return 2, [f"gitleaks failed (exit {scan.returncode}): {scan.stderr.strip()[-200:]}"]
    try:
        findings = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 2, ["gitleaks produced no readable report"]
    problems = [
        "gitleaks found {rule} in {file}".format(
            rule=f.get("RuleID", "?"), file=f.get("File", "?")
        )
        for f in findings
    ]
    return (1 if problems else 0), problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-limit", type=int, default=30)
    parser.add_argument("--inspect-run", default=None, help="run id")
    parser.add_argument("--out-dir", type=Path, default=Path("/tmp/p22-actions-review"))
    args = parser.parse_args(argv)

    if not shutil.which("gh"):
        print("ERROR: gh CLI not found — the review cannot run (fail-closed)",
              file=sys.stderr)
        return 2
    if args.inspect_run:
        code, problems = inspect_run(args.repo, args.inspect_run, args.out_dir)
        if code == 2:
            for problem in problems:
                print(f"FAIL: {problem}")
            print("INSPECT FAILED: the run logs could not be proven")
            return 2
        if problems:
            for problem in problems:
                print(f"FAIL: {problem}")
            print(f"INSPECT FAILED: run {args.inspect_run} logs carry findings")
            return 1
        print(f"INSPECT: run {args.inspect_run} logs clean")
        return 0
    try:
        table = review(args.repo, args.run_limit)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"ACTIONS REVIEW for {args.repo}:")
    print(f"  workflow runs (latest {args.run_limit}): {table['runs']}")
    print(f"  artifacts: {table['artifacts']}")
    print(f"  value-carrier class: {len(table['carrier'])}")
    for artifact in table["carrier"]:
        print(f"    {artifact['name']} "
              f"({artifact['size']} bytes, workflow branch "
              f"{artifact['workflow'] or '?'})")
    print(f"  expired artifacts: {len(table['expired'])}")
    print("REVIEW ONLY — purge decisions are recorded from this output "
          "(see docs/runbooks/history-rewrite-maintenance-window.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
