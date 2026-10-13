#!/usr/bin/env python3
"""Phase Q.1.4 — bandit debt ratchet (W1.4).

Runs the REAL bandit invocation over the tree — the same targets/config/
severity/confidence as the CI step — and compares the issue count against a
committed baseline (``scripts/bandit_debt_baseline.json``). Growth past the
baseline fails; ``--update`` ratchets the floor.

Two failure classes this gate exists to surface, both previously masked by
``|| true`` in code-quality.yml:
* bandit exit 2 — e.g. an unparseable ``.bandit`` config (the INI-style file
  failed with "expected '<document start>'" while CI reported green) —
  reads as a GATE failure, never a clean pass;
* the issue count itself, which was never recorded anywhere.

Bandit 1.9 writes a rich progress line into the ``-o`` file BEFORE the JSON —
the gate skips to the first ``{`` (documented; the CI artifact file has the
same shape).

Exit codes: 0 clean, 1 bandit debt growth, 2 usage error (missing bandit,
unparseable config/output).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = Path(__file__).resolve().parent / "bandit_debt_baseline.json"

# Keep in step with the code-quality.yml bandit step.
DEFAULT_TARGETS = ["hub/", "services/"]
DEFAULT_CONFIG = ".bandit"
SEVERITY = "medium"
CONFIDENCE = "medium"


def _resolve_bandit(explicit: str | None) -> str:
    if explicit:
        return explicit
    repo_venv_bandit = REPO_ROOT / "venv" / "bin" / "bandit"
    if repo_venv_bandit.exists():
        return str(repo_venv_bandit)
    return shutil.which("bandit") or (str(sys.executable) + " -m bandit")


def run_bandit(
    targets: list[str],
    config: str,
    bandit_binary: str | None = None,
    output_file: Path | None = None,
) -> tuple[int | None, str | None]:
    """Run bandit; return (issue-count, failure-message).

    rc 1 (issues found) is a RUN — the count is the signal. rc 2 is a
    failure (crash / config parse error) and must never read as clean.
    """
    binary = _resolve_bandit(bandit_binary)
    out = output_file or (REPO_ROOT / ".bandit-ratchet-output.json")
    command = [
        binary,
        "-r",
        *targets,
        "-f",
        "json",
        "-c",
        config,
        "--severity-level",
        SEVERITY,
        "--confidence-level",
        CONFIDENCE,
        "-o",
        str(out),
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None, f"bandit executable not found: {binary}"
    if proc.returncode == 2:
        detail = (proc.stderr or "").strip()[-300:]
        return None, f"bandit failed (rc 2) — {detail}"
    try:
        raw = out.read_text()
        payload = json.loads(raw[raw.find("{") :])
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"bandit emitted unparseable output: {exc}"
    # Rewrite the artifact as PURE JSON: the progress-line prefix also broke
    # the code-quality metrics step's direct json.load() (masked by its
    # except-pass) — consumers get a clean file.
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return len(payload.get("results", [])), None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bandit debt ratchet")
    parser.add_argument(
        "--targets", nargs="*", default=None, help="scan roots (default: hub/ services/)"
    )
    parser.add_argument("--config", default=None, help="bandit config file (default: .bandit)")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--bandit-binary", default=None)
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="artifact path for the bandit JSON (default: .bandit-ratchet-output.json)",
    )
    parser.add_argument("--update", action="store_true", help="regenerate the baseline")
    args = parser.parse_args(argv)

    targets = args.targets or DEFAULT_TARGETS
    config = args.config or DEFAULT_CONFIG
    count, error = run_bandit(targets, config, args.bandit_binary, args.output_file)
    if error:
        print(f"BANDIT-RATCHET: bandit run failed: {error}")
        return 2

    if args.update:
        baseline = {
            "generated_at": subprocess.run(
                ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip(),
            "total": count,
        }
        args.baseline.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
        print(f"BANDIT-RATCHET: baseline written — total={count}")
        return 0

    if not args.baseline.exists():
        print(f"BANDIT-RATCHET: baseline file missing: {args.baseline} (run --update to create)")
        return 2

    try:
        baseline_total = json.loads(args.baseline.read_text()).get("total", 0)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"BANDIT-RATCHET: baseline unreadable: {exc}")
        return 2

    if count > baseline_total:
        print(
            f"BANDIT-RATCHET: {count} issues > baseline {baseline_total} "
            f"(net growth of {count - baseline_total})"
        )
        return 1
    print(f"BANDIT-RATCHET: clean — {count} issues (baseline {baseline_total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
