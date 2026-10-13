#!/usr/bin/env python3
"""Phase Q.4.2 — environment provisioning check.

Verifies the RUNNING interpreter satisfies ``requirements.txt`` (name +
specifier) and prints exactly what is missing plus the `pip install` line.
A half-provisioned venv produces phantom test failures (the ``csp``
incident: 7 boundary tests died with ModuleNotFoundError twelve frames
into client.get()). This checker makes the environment state visible
BEFORE the suite runs.

Exit 0 when complete, 1 when distributions are missing.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_REQ_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*(==|>=|<=|~=|!=|>|<|===)?\s*([^\s;#]*)?")


def _required_distributions(requirements_path: Path) -> dict[str, str]:
    """name -> specifier ('' when unpinned)."""
    required: dict[str, str] = {}
    for raw in requirements_path.read_text().splitlines():
        line = raw.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        match = _REQ_RE.match(line)
        if not match:
            continue
        name = match.group(1).lower().replace("_", "-")
        specifier = (match.group(2) or "") + (match.group(3) or "")
        required[name] = specifier.strip()
    return required


def _installed_distributions(python: str) -> dict[str, str]:
    result = subprocess.run(
        [python, "-m", "pip", "list", "--format=freeze"],
        capture_output=True,
        text=True,
        check=True,
    )
    installed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "==" not in line:
            continue
        name, version = line.split("==", 1)
        installed[name.lower().replace("_", "-")] = version.strip()
    return installed


def missing_distributions(python: str, requirements_path: Path) -> dict[str, str]:
    required = _required_distributions(requirements_path)
    installed = _installed_distributions(python)
    missing: dict[str, str] = {}
    for name, specifier in required.items():
        if name not in installed:
            missing[name] = specifier
    return missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Environment provisioning check")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="interpreter to verify (default: the one running this script)",
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "requirements.txt",
    )
    args = parser.parse_args(argv)

    missing = missing_distributions(args.python, args.requirements)
    if missing:
        print(f"ENV-PROVISIONING: {len(missing)} distribution(s) missing for {args.python}:")
        for name in sorted(missing):
            spec = f"{missing[name]}" if missing[name] else "(unpinned)"
            print(f"  - {name} {spec}")
        print(f"\nFix: {args.python} -m pip install -r {args.requirements}")
        return 1
    print(f"ENV-PROVISIONING: {args.python} satisfies {args.requirements}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
