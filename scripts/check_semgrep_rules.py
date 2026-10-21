#!/usr/bin/env python3
"""W11.10 (oss-release-remediation, GATE-25) — the LOCAL semgrep rules,
BLOCKING.

The pre-W11.10 state: GATE-25's CI step never installed semgrep (the
`command -v semgrep` branch always fell through to the silent skip) and
ran ``--config=auto`` alone — the repo's own rules
(``semgrep/rules/*.yaml`` + ``.semgrep/*.yml``) were NEVER executed
anywhere.  This runner executes exactly the local ERROR-severity rule
set and fails on findings AND on a semgrep failure (a parse error in a
rule is a gate failure, never a silent skip — the bandit-ratchet
lesson).

Exit codes: 0 clean, 1 findings, 2 semgrep missing / rule parse error.
The advisory ``prefer-chain.yaml`` stays advisory (the P.9 verdict) —
it is not part of this set.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

LOCAL_RULES = [
    "semgrep/rules/transformation.yaml",
    "semgrep/rules/warehouses.yaml",
    "semgrep/rules/warehouse-dq-compliance.yaml",
    ".semgrep/business-rules-direct-instantiation.yml",
]


def _resolve_semgrep() -> str | None:
    explicit = shutil.which("semgrep")
    if explicit:
        return explicit
    venv_semgrep = REPO_ROOT / "venv" / "bin" / "semgrep"
    if venv_semgrep.exists():
        return str(venv_semgrep)
    return None


def main(_argv: list[str]) -> int:
    semgrep = _resolve_semgrep()
    if semgrep is None:
        print("SEMGREP-GATE: semgrep not installed — the local-rules gate is BLOCKING "
              "(install: pip install semgrep)")
        return 2

    missing = [rule for rule in LOCAL_RULES if not (REPO_ROOT / rule).is_file()]
    if missing:
        print(f"SEMGREP-GATE: local rule file(s) missing: {missing}")
        return 2

    cmd = [semgrep] + [f"--config={rule}" for rule in LOCAL_RULES] + [
        "--error",
        "--quiet",
        "--no-rewrite-rule-ids",
    ]
    result = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=900,
        check=False,  # semgrep's exit code IS the gate signal
    )
    if result.returncode == 0:
        print("SEMGREP-GATE: clean — all local rules pass, zero findings")
        return 0
    if result.returncode == 1:
        print("SEMGREP-GATE: findings — local-rule violations (see semgrep output):")
        print(result.stdout)
        return 1
    print("SEMGREP-GATE: semgrep failure (rule parse error or tool crash) — "
          "the gate FAILS, never skips:")
    print(result.stderr[-4000:])
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
