#!/usr/bin/env python3
"""285.12.4.11 — Audit Fernet encryption usage (encrypt/decrypt_json_field)."""
from __future__ import annotations
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_ENC_FNS = {"encrypt_json_field", "decrypt_json_field", "Fernet", "MultiFernet"}

def audit() -> int:
    files = set()
    for pyf in _REPO.rglob("hub/apps/**/*.py"):
        if any(p in pyf.parts for p in ("__pycache__","migrations","tests",".venv")):
            continue
        try:
            text = pyf.read_text()
        except Exception:
            continue
        for fn in _ENC_FNS:
            if fn in text:
                files.add(str(pyf.relative_to(_REPO)))
                break
    print(f"Encryption coverage: {len(files)} files use Fernet encryption")
    for f in sorted(files):
        print(f"  {f}")
    return 0

sys.exit(audit())
