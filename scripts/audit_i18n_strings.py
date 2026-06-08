#!/usr/bin/env python3
"""
307.11 / 310.6 — Audit hardcoded English strings in Python and TSX files.

Scans backend (Python) and frontend (TSX/TS) for hardcoded user-facing
English strings. Reports coverage percentage (strings in i18n files vs
hardcoded strings). Target: >50% coverage.

Usage:
    python scripts/audit_i18n_strings.py
    python scripts/audit_i18n_strings.py --ci
    python scripts/audit_i18n_strings.py --json
"""
import argparse
import json
import os
import re
import sys

# Patterns for hardcoded English strings in UI-facing code
ENGLISH_PATTERNS = [
    re.compile(
        r'(?:title|label|placeholder|description|message|error|text|heading|button|aria-label|summary|hint|tooltip|empty|loading|success|warning|confirm|cancel|save|delete|edit|create|search|filter|sort|export|import|refresh|retry|dismiss|close|back|next|submit|send|upload|download|copy|paste|help|about|settings|profile|logout|login|register|welcome|overview|details|actions|status|name|type|size)\s*[:=]\s*["\']([A-Z][a-z].*?)["\']',
        re.IGNORECASE,
    ),
]

SCAN_DIRS = ["hub/apps", "frontend/src/features", "frontend/src/shared"]
I18N_DIRS = ["frontend/src/i18n"]
SKIP_DIRS = {"__pycache__", "node_modules", "migrations", "tests", ".venv", "venv"}


def count_hardcoded_strings() -> tuple[list[dict], int, int]:
    """Scan for hardcoded strings. Returns (findings, hardcoded_count, total_lines_scanned)."""
    findings: list[dict] = []
    hardcoded_count = 0
    total_lines = 0

    for scan_dir in SCAN_DIRS:
        if not os.path.exists(scan_dir):
            continue
        for root, dirs, files in os.walk(scan_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if not (f.endswith(".py") or f.endswith(".tsx") or f.endswith(".ts")):
                    continue
                path = os.path.join(root, f)
                try:
                    with open(path) as fh:
                        for lineno, line in enumerate(fh, 1):
                            total_lines += 1
                            for pat in ENGLISH_PATTERNS:
                                for m in pat.finditer(line):
                                    findings.append({
                                        "path": path, "line": lineno,
                                        "text": m.group(1)[:80],
                                    })
                                    hardcoded_count += 1
                except Exception:
                    pass

    return findings, hardcoded_count, total_lines


def count_i18n_strings() -> int:
    """Count translated strings in i18n directories."""
    count = 0
    for i18n_dir in I18N_DIRS:
        if not os.path.exists(i18n_dir):
            continue
        for root, dirs, files in os.walk(i18n_dir):
            for f in files:
                if not (f.endswith(".json") or f.endswith(".ts") or f.endswith(".tsx")):
                    continue
                path = os.path.join(root, f)
                try:
                    with open(path) as fh:
                        content = fh.read()
                    # Count translation key-value pairs in JSON/YAML-style i18n
                    count += len(re.findall(r'"([^"]+)":\s*"', content))
                    # Count TypeScript i18n exports
                    count += len(re.findall(r":\s*['\"](.+?)['\"]", content))
                except Exception:
                    pass
    return count


def run_audit(json_output: bool = False, ci: bool = False) -> int:
    findings, hardcoded, total_lines = count_hardcoded_strings()
    i18n_count = count_i18n_strings()

    # Coverage: i18n strings as percentage of total (i18n + hardcoded)
    total_ui_strings = hardcoded + i18n_count
    coverage_pct = (i18n_count / total_ui_strings * 100) if total_ui_strings > 0 else 100.0

    if json_output:
        print(json.dumps({
            "hardcoded_strings": hardcoded,
            "i18n_strings": i18n_count,
            "coverage_pct": round(coverage_pct, 1),
            "total_lines_scanned": total_lines,
            "passes_50": coverage_pct > 50,
            "findings": findings[:50],
        }, indent=2))
    else:
        print(f"Hardcoded English strings: {hardcoded}")
        print(f"i18n translated strings:  {i18n_count}")
        print(f"i18n coverage:            {coverage_pct:.1f}%")
        print(f"Target:                   >50%")
        if findings:
            print(f"\nTop hardcoded strings (first 10):")
            for f in findings[:10]:
                print(f"  {f['path']}:{f['line']} — \"{f['text']}\"")
            if len(findings) > 10:
                print(f"  ... and {len(findings) - 10} more")

    if ci:
        if coverage_pct > 50:
            print(f"\n✅ i18n coverage {coverage_pct:.1f}% exceeds 50% target.")
            return 0
        else:
            print(f"\n❌ i18n coverage {coverage_pct:.1f}% below 50% target.")
            return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="307.11/310.6 — i18n hardcoded string audit")
    parser.add_argument("--ci", action="store_true", default=False)
    parser.add_argument("--json", action="store_true", default=False)
    args = parser.parse_args()
    return run_audit(json_output=args.json, ci=args.ci)


if __name__ == "__main__":
    raise SystemExit(main())
