#!/usr/bin/env python3
"""285.12.7.1 7A — Audit i18n coverage: flag hardcoded English strings in .tsx/.ts."""
from __future__ import annotations
import re, sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_FE_DIR = _REPO / "frontend" / "src"
_HARDCODED_RE = re.compile(r"(?<!i18n\.)(?<!t\()[>'\"]([A-Z][a-z]+(?:\s+[a-z]+){2,})['\"<]")

def audit() -> int:
    count = 0
    for f in _FE_DIR.rglob("*.tsx"):
        try:
            text = f.read_text()
        except Exception:
            continue
        matches = _HARDCODED_RE.findall(text)
        if matches:
            count += len(matches)
    print(f"i18n audit: ~{count} potential hardcoded English strings in FE files")
    return 0

sys.exit(audit())
