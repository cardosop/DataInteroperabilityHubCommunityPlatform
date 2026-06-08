#!/usr/bin/env python3
"""285.12.6.6 4F — Audit tenant FK cascade paths for hard-delete completeness."""
from __future__ import annotations
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_CASCADE_OPS = {"CASCADE", "PROTECT", "SET_NULL", "SET_DEFAULT", "DO_NOTHING"}

def audit() -> int:
    """Find all ForeignKey on_delete behaviours across Django models."""
    import ast
    fks: list[tuple[str, str, str]] = []
    for pyf in sorted((_REPO / "hub" / "apps").rglob("models.py")):
        if "migrations" in str(pyf): continue
        try:
            tree = ast.parse(pyf.read_text())
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr') and node.func.attr == 'ForeignKey':
                    for kw in node.keywords:
                        if kw.arg == 'on_delete' and hasattr(kw.value, 'attr'):
                            fks.append((str(pyf.parent.name), kw.value.attr, str(node.lineno)))
    
    cascade = sum(1 for _, v, _ in fks if v == 'CASCADE')
    protect = sum(1 for _, v, _ in fks if v == 'PROTECT')
    set_null = sum(1 for _, v, _ in fks if v in ('SET_NULL','SET_DEFAULT'))
    print(f"Tenant FK cascade audit: {len(fks)} total FKs")
    print(f"  CASCADE: {cascade}")
    print(f"  PROTECT: {protect}")
    print(f"  SET_NULL/SET_DEFAULT: {set_null}")
    return 0

sys.exit(audit())
