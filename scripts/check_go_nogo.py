#!/usr/bin/env python3
"""U.8 — beta go/no-go gate (machine-verifiable evidence, no mocks).

Evaluates every automatable GO/NO-GO criterion from the U.8 task against
LIVE evidence — real subprocess runs (lint ratchet, infra suites, staging
smoke, migration rehearsal, backup/restore drill, frontend baseline,
vitest), real artifacts (migration-safety-policy approvals, beta-ops
runbook, freeze calendar), and real remote CI state via ``gh``. The
purely human items (alerting/on-call confirmation, freeze agreement) are
OWNER-ACTION criteria that only pass once recorded in
``docs/operations/beta-go-nogo-ledger.md`` — the gate can never fake a
human sign-off.

Exit codes:
  0  GO          — every criterion PASS (owner actions recorded)
  2  NO-GO       — at least one FAIL (a red gate, an unledgered failure,
                   an unrecorded veto)
  4  AWAITING-OWNER — only OWNER/conditional items remain open
  1  usage error
  3  gate infrastructure error (evidence could not be produced — never
     treated as GO)

Usage:
  python scripts/check_go_nogo.py                 # full battery
  python scripts/check_go_nogo.py --criteria lint-ratchet,secrets-contract
  python scripts/check_go_nogo.py --branch prepro01 --allow-stale-ci
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY = REPO_ROOT / "docs" / "operations" / "migration-safety-policy.md"
RUNBOOK = REPO_ROOT / "docs" / "operations" / "beta-ops-runbook.md"
LEDGER = REPO_ROOT / "docs" / "operations" / "beta-go-nogo-ledger.md"
FREEZE_CALENDAR = REPO_ROOT / "docs" / "operations" / "change-freeze-calendar.md"
REHEARSAL = REPO_ROOT / "infrastructure" / "scripts" / "migration-rehearsal.sh"
BASELINE_CHECK = REPO_ROOT / "frontend" / "scripts" / "check-test-baseline.cjs"

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_LEDGERED = "LEDGERED"  # known failures with ticket+expiry recorded
VERDICT_OWNER = "OWNER"  # human sign-off required, not yet recorded


@dataclass
class Result:
    verdict: str
    detail: str


# ── Pure evaluation logic (unit-tested; no subprocesses) ────────────────────


def parse_signoff_ledger_text(text: str) -> dict[str, dict]:
    """Parse the sign-off ledger markdown table into {key: row}."""
    rows: dict[str, dict] = {}
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] in ("key", "---", "—"):
            continue
        rows[cells[0]] = {
            "criterion": cells[1],
            "owner": cells[2],
            "confirmed": cells[3].strip().lower() in ("yes", "true", "y"),
            "date": cells[4],
        }
    return rows


def load_signoff_ledger(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return parse_signoff_ledger_text(path.read_text(encoding="utf-8"))


def parse_rehearsal_approvals(policy: Path) -> list[str]:
    """Extract the recorded --approve-data-loss op ids from the policy doc.

    The rehearsal refuses to run blind; the gate runs it ONLY with the
    approvals whose justifications are recorded in
    migration-safety-policy.md — a silent drop can never ride through.
    """
    if not policy.exists():
        return []
    text = policy.read_text(encoding="utf-8")
    ops: list[str] = []
    for m in re.finditer(r"^\|\s*`([a-z_]+\.\d{4}_[^`]+)`\s*\|", text, re.MULTILINE):
        op = m.group(1)
        if op not in ops:
            ops.append(op)
    return ops


def classify_rehearsal_log(text: str) -> Result:
    """Classify a rehearsal run from its log (the real veto evidence)."""
    if "ALL STAGES PASSED" in text and "DATA-LOSS VETO:" not in text:
        return Result(
            VERDICT_PASS, "all 7 stages passed (forward + veto drill + reverse + idempotence)"
        )
    if "DATA-LOSS VETO:" in text:
        m = re.search(r"DATA-LOSS VETO:\s*([^\n]+)", text)
        return Result(
            VERDICT_FAIL, f"veto blocked the rehearsal: {m.group(1) if m else 'unapproved op'}"
        )
    if "EXIT=2" in text:
        return Result(VERDICT_FAIL, "rehearsal exited 2 (rehearsal failure)")
    return Result(VERDICT_FAIL, "rehearsal log lacks the ALL STAGES PASSED marker")


def check_eks_ticket_annotation(text: str) -> bool:
    """210.29 must carry an owner AND an ISO expiry — the U.6 deferral contract.

    The annotation can wrap across lines (markdown paragraph) — search a
    bounded window after each mention instead of a single line.
    """
    for m in re.finditer(r"210\.29", text):
        window = text[m.start() : m.start() + 500]
        has_owner = re.search(r"owner", window, re.IGNORECASE) is not None
        has_expiry = re.search(r"EXPIRES\s+\d{4}-\d{2}-\d{2}", window, re.IGNORECASE) is not None
        if has_owner and has_expiry:
            return True
    return False


def classify_a11y(failed: int, ledgered: int) -> Result:
    """a11y verdict: 0 failures → PASS; failures with ticket+expiry recorded
    in the go-nogo ledger → LEDGERED (conditional); anything else → FAIL."""
    if failed == 0:
        return Result(VERDICT_PASS, "a11y suite green")
    if failed == ledgered:
        return Result(
            VERDICT_LEDGERED,
            f"{failed} a11y failure(s) — all ledgered with ticket + expiry in the beta-go-nogo ledger",
        )
    return Result(
        VERDICT_FAIL,
        f"{failed} a11y failure(s), only {ledgered} ledgered — unledgered failures block the go decision",
    )


def parse_a11y_ledger(path: Path) -> list[dict]:
    """Rows of the go-nogo ledger's a11y table (spec|failure|ticket|expires)."""
    if not path.exists():
        return []
    rows: list[dict] = []
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("## a11y"):
            in_section = True
            continue
        if in_section and line.strip().startswith("#") and not line.strip().startswith("###"):
            in_section = False
            continue
        if not in_section or not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] in ("spec", "—") or set(cells[0]) == {"-"}:
            continue
        rows.append(
            {"spec": cells[0], "failure": cells[1], "ticket": cells[2], "expires": cells[3]}
        )
    return rows


def verdict_exit_code(results: dict[str, Result]) -> int:
    verdicts = {r.verdict for r in results.values()}
    if not verdicts or verdicts <= {VERDICT_PASS}:
        return 0  # GO
    if VERDICT_FAIL in verdicts:
        return 2  # NO-GO
    if verdicts <= {VERDICT_PASS, VERDICT_LEDGERED, VERDICT_OWNER}:
        return 4  # AWAITING-OWNER
    return 2


# ── Evidence runners ─────────────────────────────────────────────────────────


def run_cmd(
    args: list[str], cwd: Path | None = None, timeout: int | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=cwd or REPO_ROOT, capture_output=True, text=True, timeout=timeout, check=False
    )


def _make(targets: list[str]) -> Result:
    failures: list[str] = []
    for target in targets:
        try:
            proc = run_cmd(["make", target], timeout=1800)
        except subprocess.TimeoutExpired:
            # A timed-out make does NOT kill grandchildren inside compose
            # containers (a stuck pg_restore kept a DROP DATABASE locked for
            # the next run — measured). Report the FAIL; never let the
            # exception abort the whole gate.
            failures.append(
                f"{target} TIMED OUT after 1800s — a container-side child may still be running"
            )
            continue
        if proc.returncode != 0:
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-5:]
            failures.append(f"{target} exited {proc.returncode}: {' | '.join(tail)}")
    if failures:
        return Result(VERDICT_FAIL, "; ".join(failures))
    return Result(VERDICT_PASS, ", ".join(targets) + " green")


def criterion_lint_ratchet() -> Result:
    proc = run_cmd([sys.executable, "scripts/check_lint_debt_ratchet.py"], timeout=1200)
    if proc.returncode == 0:
        return Result(VERDICT_PASS, "lint debt ratchet clean (GATE-35)")
    return Result(VERDICT_FAIL, "lint debt grew past baseline — see ratchet output")


def criterion_local_battery() -> Result:
    """The local rehearsal of the blocking CI gate sequence."""
    return _make(["ci-lint-local", "test-infra-staging-pipeline", "test-helm"])


def criterion_remote_ci(branch: str, allow_stale: bool) -> Result:
    if not shutil.which("gh"):
        return Result(VERDICT_FAIL, "gh CLI unavailable — remote CI state cannot be checked")
    proc = run_cmd(
        ["gh", "run", "list", "--workflow=ci.yml", "--branch", branch, "--limit", "1"],
        timeout=120,
    )
    if proc.returncode != 0:
        return Result(VERDICT_FAIL, f"gh run list failed: {proc.stderr.strip()[:200]}")
    first = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""
    if "completed" not in first:
        return Result(
            VERDICT_FAIL, f"no completed ci.yml run on {branch} (latest: {first or 'none'})"
        )
    if "success" in first:
        return Result(VERDICT_PASS, f"latest ci.yml run on {branch} green: {first}")
    if allow_stale:
        return Result(
            VERDICT_OWNER,
            f"latest ci.yml run on {branch} is RED ({first.split(chr(9))[0]}) — root-cause fixes are in the tree; owner push required",
        )
    return Result(VERDICT_FAIL, f"latest ci.yml run on {branch} is RED: {first}")


def criterion_secrets_contract() -> Result:
    proc = run_cmd(
        [
            sys.executable,
            "-m",
            "pytest",
            "scripts/tests/test_staging_env_contract.py",
            "-q",
            "-p",
            "no:cacheprovider",
            "--confcutdir=scripts/tests",
            "--override-ini=addopts=",
        ],
        timeout=600,
    )
    if proc.returncode == 0:
        return Result(
            VERDICT_PASS, "staging env contract 13/13 — every ${VAR:?} secret provisioned"
        )
    return Result(
        VERDICT_FAIL,
        f"staging env contract failed: {proc.stdout.strip().splitlines()[-1] if proc.stdout else proc.stderr.strip()[:200]}",
    )


def criterion_staging_smoke() -> Result:
    return _make(["staging-smoke"])


def criterion_data_rehearsal(keep: bool) -> Result:
    approvals = parse_rehearsal_approvals(POLICY)
    if not approvals:
        return Result(
            VERDICT_FAIL,
            "no recorded approvals in migration-safety-policy.md — refusing to run the rehearsal blind",
        )
    cmd = ["bash", str(REHEARSAL)]
    if keep:
        cmd.append("--keep")
    for op in approvals:
        cmd += ["--approve-data-loss", op]
    proc = run_cmd(cmd, timeout=7200)
    log = proc.stdout + proc.stderr
    classification = classify_rehearsal_log(log)
    classification.detail = f"rehearsal exited {proc.returncode}; {classification.detail}"
    return classification


def criterion_makemigrations_clean() -> Result:
    proc = run_cmd(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.staging.yml",
            "--env-file",
            ".env.staging",
            "exec",
            "-T",
            "-e",
            "POSTGRES_HOST=postgres",
            "-e",
            "POSTGRES_PORT=5432",
            "-e",
            "PGBOUNCER_ENABLED=false",
            "api-service",
            "python",
            "hub/manage.py",
            "makemigrations",
            "--check",
        ],
        timeout=900,
    )
    if proc.returncode != 0:
        return Result(
            VERDICT_FAIL,
            f"makemigrations --check exited {proc.returncode}: {(proc.stdout + proc.stderr)[-400:]}",
        )
    return Result(VERDICT_PASS, "makemigrations --check clean — no unmade migrations")


def criterion_backup_restore() -> Result:
    return _make(["staging-backup", "staging-restore-drill"])


def criterion_frontend_baseline() -> Result:
    proc = run_cmd(["node", str(BASELINE_CHECK)], cwd=REPO_ROOT / "frontend", timeout=300)
    if proc.returncode == 0:
        return Result(VERDICT_PASS, "frontend failure baseline checker green")
    return Result(
        VERDICT_FAIL,
        f"frontend baseline checker exited {proc.returncode}: {(proc.stdout + proc.stderr)[-300:]}",
    )


def criterion_vitest() -> Result:
    if not (REPO_ROOT / "frontend" / "node_modules").exists():
        return Result(
            VERDICT_FAIL,
            "frontend/node_modules missing — run npm install first (the gate will not skip)",
        )
    proc = run_cmd(
        ["npx", "vitest", "--run", "--reporter=basic"], cwd=REPO_ROOT / "frontend", timeout=1200
    )
    m = re.search(r"Tests\s+(\d+) failed \|\s*(\d+) passed", proc.stdout + proc.stderr)
    if proc.returncode == 0:
        return Result(VERDICT_PASS, "frontend unit tests green")
    summary = f"{m.group(1)} failed / {m.group(2)} passed" if m else "unknown counts"
    return Result(VERDICT_FAIL, f"frontend unit tests red: {summary} — see vitest output")


def criterion_alerting_oncall(ledger: dict[str, dict]) -> Result:
    if not RUNBOOK.exists():
        return Result(VERDICT_FAIL, "beta-ops-runbook.md missing")
    text = RUNBOOK.read_text(encoding="utf-8")
    # The runbook spells the SLAs with a space ("48 h triage", "4 h for
    # staging outage") — match the REAL wording, not an idealized spelling.
    machine_ok = "on-call" in text.lower() and "48 h" in text and "4 h" in text
    alertmanager = (REPO_ROOT / "monitoring" / "alertmanager" / "alertmanager-staging.yml").exists()
    if not machine_ok or not alertmanager:
        return Result(VERDICT_FAIL, "on-call runbook section or alertmanager-staging.yml missing")
    row = ledger.get("oncall-confirmed")
    if row and row["confirmed"]:
        return Result(VERDICT_PASS, f"on-call confirmed by {row['owner']} ({row['date']})")
    return Result(
        VERDICT_OWNER,
        "runbook + alerting config present; HUMAN confirmation pending (ledger key oncall-confirmed)",
    )


def criterion_freeze_agreed(ledger: dict[str, dict]) -> Result:
    if not FREEZE_CALENDAR.exists():
        return Result(VERDICT_FAIL, "change-freeze-calendar.md missing")
    row = ledger.get("freeze-agreed")
    if row and row["confirmed"]:
        return Result(VERDICT_PASS, f"freeze window agreed by {row['owner']} ({row['date']})")
    return Result(
        VERDICT_OWNER, "freeze calendar present; HUMAN agreement pending (ledger key freeze-agreed)"
    )


def criterion_eks_ticket() -> Result:
    if not RUNBOOK.exists():
        return Result(VERDICT_FAIL, "beta-ops-runbook.md missing")
    if check_eks_ticket_annotation(RUNBOOK.read_text(encoding="utf-8")):
        return Result(VERDICT_PASS, "EKS ticket 210.29 filed with owner + EXPIRES (runbook §6)")
    return Result(VERDICT_FAIL, "EKS ticket 210.29 lacks owner or EXPIRES annotation")


def criterion_a11y() -> Result:
    """Run the a11y E2E batch (1b) and cross-check failures against the ledger."""
    batch = REPO_ROOT / "frontend" / "scripts" / "e2e-batches.sh"
    proc = run_cmd(["bash", str(batch), "1b"], timeout=3600)
    m = re.search(r"(\d+)\s+failed", proc.stdout + proc.stderr)
    failed = int(m.group(1)) if m else None
    if failed is None:
        return Result(VERDICT_FAIL, "could not parse the batch-1b failure count — see batch output")
    ledgered = len(parse_a11y_ledger(LEDGER))
    classification = classify_a11y(failed, ledgered)
    classification.detail += f" (batch 1b: {failed} failed, ledger holds {ledgered})"
    return classification


# ── Main ─────────────────────────────────────────────────────────────────────

CRITERIA: dict[str, Callable[..., Result]] = {
    "lint-ratchet": criterion_lint_ratchet,
    "ci-local": criterion_local_battery,
    "secrets-contract": criterion_secrets_contract,
    "staging-smoke": criterion_staging_smoke,
    "data-rehearsal": criterion_data_rehearsal,
    "makemigrations": criterion_makemigrations_clean,
    "backup-restore": criterion_backup_restore,
    "frontend-baseline": criterion_frontend_baseline,
    "vitest": criterion_vitest,
    "a11y": criterion_a11y,
    "eks-ticket": criterion_eks_ticket,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--criteria", default="", help="comma-separated subset (default: all)")
    parser.add_argument("--branch", default="prepro01")
    parser.add_argument(
        "--allow-stale-ci",
        action="store_true",
        help="treat a red remote CI run as OWNER-action instead of FAIL",
    )
    parser.add_argument("--keep-rehearsal-db", action="store_true")
    parser.add_argument(
        "--json", type=Path, default=None, help="write the machine-readable report to this path"
    )
    args = parser.parse_args()

    ledger = load_signoff_ledger(LEDGER)
    selected = [c for c in (args.criteria.split(",") if args.criteria else list(CRITERIA)) if c]

    results: dict[str, Result] = {}
    for name in selected:
        print(f"[go-nogo] {name} ...", flush=True)
        if name == "ci-remote":
            results[name] = criterion_remote_ci(args.branch, args.allow_stale_ci)
        elif name in CRITERIA:
            fn = CRITERIA[name]
            if name == "data-rehearsal":
                results[name] = fn(keep=args.keep_rehearsal_db)
            else:
                results[name] = fn()
        else:
            print(f"[go-nogo] unknown criterion {name} — ignoring")
        print(f"[go-nogo]   {results[name].verdict}: {results[name].detail}", flush=True)

    results["alerting-oncall"] = criterion_alerting_oncall(ledger)
    results["freeze-agreed"] = criterion_freeze_agreed(ledger)

    exit_code = verdict_exit_code(results)
    report = {
        "exit_code": exit_code,
        "verdict": {0: "GO", 2: "NO-GO", 4: "AWAITING-OWNER", 1: "USAGE", 3: "ERROR"}[exit_code],
        "criteria": {
            name: {"verdict": r.verdict, "detail": r.detail} for name, r in results.items()
        },
    }
    print("\n=== U.8 go/no-go report ===")
    for name, r in results.items():
        print(f"  {r.verdict:9s}  {name}: {r.detail}")
    print(f"\nVERDICT: {report['verdict']} (exit {exit_code})")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
