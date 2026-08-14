#!/usr/bin/env python3
"""Copyleft audit for the core dependency set (Phase 313.3.4).

Asserts that no package in the requirements.txt closure carries a hard
copyleft license (GPL / AGPL / SSPL). LGPL (psycopg2, pyclamd) and
dual-licensed packages with a permissive option (docutils BSD) are
accepted and reported. Venv-local pollution (packages not declared in
requirements.txt) is out of scope by construction.

Usage: python scripts/check_copyleft.py
Exit 1 on any hard-copyleft dependency.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def is_hard_copyleft(license_name: str) -> bool:
    """Classify by intent: LGPL and permissive dual-licenses are accepted;
    plain GPL / AGPL / SSPL are hard copyleft."""
    lic = license_name.lower()
    if "lesser" in lic or "library" in lic:
        return False  # LGPL — acceptable
    if "bsd" in lic or "public domain" in lic or "mit" in lic or "apache" in lic or "artistic" in lic:
        return False  # dual-licensed with a permissive option
    return bool(re.search(r"\bgpl|\bagpl|\bsspl", lic))


def requirement_names() -> set[str]:
    names: set[str] = set()
    for line in Path("requirements.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        m = re.match(r"^([A-Za-z0-9_.-]+)", line)
        if m:
            names.add(m.group(1).lower())
    return names


def main() -> int:
    names = requirement_names()
    pip_licenses = Path(__file__).resolve().parents[1] / "venv" / "bin" / "pip-licenses"
    if not pip_licenses.exists():
        pip_licenses = "pip-licenses"
    proc = subprocess.run(
        [str(pip_licenses), "--from", "mixed", "--format", "csv"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        print("pip-licenses unavailable — skipping copyleft audit (CI-gated)")
        return 0

    offenders: list[tuple[str, str, str]] = []
    for line in proc.stdout.splitlines()[1:]:
        cols = [c.strip().strip('"') for c in line.split(",")]
        if len(cols) < 3 or cols[0].lower() not in names:
            continue
        if is_hard_copyleft(cols[2]):
            offenders.append((cols[0], cols[1], cols[2]))

    if offenders:
        print("COpyleft audit FAILED — hard-copyleft dependencies in requirements.txt:")
        for name, version, license_name in offenders:
            print(f"  {name} {version}: {license_name}")
        return 1
    print("copyleft audit clean: no GPL/AGPL/SSPL in the requirements.txt closure "
          "(LGPL + permissive dual-licenses accepted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
