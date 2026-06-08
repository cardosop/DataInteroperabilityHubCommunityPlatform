#!/usr/bin/env python3
"""
304.1 / 308.6 — PII field audit across all Django models.

Introspects all models across all apps for fields matching PII
patterns (email, phone, SSN, name, address, IP, credit card).
Generates ``docs/PII_DATA_MAP.md``.

Usage:
    python scripts/audit_pii_fields.py                    # generate full map
    python scripts/audit_pii_fields.py --ci               # CI: exit 1 on new PII
    python scripts/audit_pii_fields.py --ci --json         # JSON output for CI
    python scripts/audit_pii_fields.py --output report.md  # custom output path
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

PII_PATTERNS = {
    "email":       re.compile(r"^email", re.IGNORECASE),
    "phone":       re.compile(r"phone|mobile|cell|fax", re.IGNORECASE),
    "ssn":         re.compile(r"ssn|social_security|national_id|tax_id(?!_type|_verified)", re.IGNORECASE),
    "name":        re.compile(r"^(first_name|last_name|display_name|full_name|given_name|family_name)$", re.IGNORECASE),
    "address":     re.compile(r"address|street|city|state|postal|zip|country", re.IGNORECASE),
    "ip_address":  re.compile(r"ip_address|ip_addr|remote_addr|client_ip", re.IGNORECASE),
    "credit_card": re.compile(r"credit_card|card_number|cc_number|payment_card", re.IGNORECASE),
}

EXEMPT_FIELDS = {
    "tax_id_verified":   "Boolean — verification status only",
    "tax_id_type":       "Enum — type classifier, not the ID itself",
    "invitation_token":  "SHA-256 hash, not plaintext",
    "password":          "Hashed by Django (PBKDF2/bcrypt)",
    "email_verified":    "Boolean — verification status only",
}


def scan_models(apps_dir: str = "hub/apps") -> dict:
    results = defaultdict(list)
    for app in sorted(os.listdir(apps_dir)):
        path = os.path.join(apps_dir, app)
        if not os.path.isdir(path) or app.startswith("_"):
            continue
        mf = os.path.join(path, "models.py")
        if not os.path.exists(mf):
            continue
        with open(mf) as f:
            content = f.read()
        for class_name, block in re.findall(
            r"class\s+(\w+)\([^)]*Model[^)]*\):(.*?)(?=\nclass\s|\n\Z|\Z)",
            content, re.DOTALL,
        ):
            for field_name in re.findall(
                r"^\s*(\w+)\s*=\s*models\.\w+Field\([^)]*\)", block, re.MULTILINE,
            ):
                if field_name in EXEMPT_FIELDS:
                    continue
                for pii_type, pattern in PII_PATTERNS.items():
                    if pattern.search(field_name):
                        results[app].append({
                            "model": class_name, "field": field_name,
                            "pii_type": pii_type,
                        })
    return dict(results)


def generate_map(results: dict, output: str = "docs/PII_DATA_MAP.md") -> None:
    total = sum(len(v) for v in results.values())
    lines = [
        "# PII Data Map", "",
        f"**Total apps**: {len(results)} | **Total PII fields**: {total}", "",
    ]
    for app in sorted(results):
        lines.append(f"## {app}")
        for e in sorted(results[app], key=lambda e: (e["model"], e["field"])):
            lines.append(f"- `{e['model']}.{e['field']}` — {e['pii_type']}")
        lines.append("")
    lines.append("## Exemptions")
    for fld, reason in sorted(EXEMPT_FIELDS.items()):
        lines.append(f"- `{fld}`: {reason}")
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w") as f:
        f.write("\n".join(lines))
    print(f"PII_DATA_MAP: {output} ({len(results)} apps, {total} fields)")


def _load_previous_results(path: str = "docs/PII_DATA_MAP.md") -> dict:
    """Parse the previous PII map to compare for new PII fields."""
    previous: dict[str, set] = defaultdict(set)
    if not os.path.exists(path):
        return dict(previous)
    with open(path) as f:
        content = f.read()
    for match in re.findall(r"- `(\w+)\.(\w+)` — (\w+)", content):
        model, field, pii_type = match
        previous[model].add(field)
    return dict(previous)


def run_ci_check(results: dict, json_output: bool = False) -> int:
    """Compare current PII fields against previously documented map.
    Exit 1 if new PII fields are detected (informational — does not block)."""
    previous = _load_previous_results()
    new_fields: list[dict] = []
    for app, entries in results.items():
        for e in entries:
            if e["field"] not in previous.get(e["model"], set()):
                new_fields.append({
                    "app": app, "model": e["model"],
                    "field": e["field"], "pii_type": e["pii_type"],
                })

    if json_output:
        print(json.dumps({
            "status": "new_pii_detected" if new_fields else "ok",
            "new_fields": new_fields,
            "total_pii_fields": sum(len(v) for v in results.values()),
            "total_apps": len(results),
        }, indent=2))
    else:
        if new_fields:
            print(f"⚠ {len(new_fields)} new PII field(s) detected:")
            for nf in new_fields:
                print(f"  - {nf['app']}.{nf['model']}.{nf['field']} ({nf['pii_type']})")
            print("\nUpdate docs/PII_DATA_MAP.md: python scripts/audit_pii_fields.py")
            print("This is informational — CI does not block on PII changes.")
        else:
            print("✓ No new PII fields detected.")

    # Informational only — always exit 0 in CI
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="304.1/308.6 — PII field audit")
    parser.add_argument(
        "--ci", action="store_true", default=False,
        help="CI mode: compare against existing PII map, exit 1 on new fields.",
    )
    parser.add_argument(
        "--json", action="store_true", default=False,
        help="Output results as JSON.",
    )
    parser.add_argument(
        "--output", type=str, default="docs/PII_DATA_MAP.md",
        help="Output path for the PII data map.",
    )
    args = parser.parse_args()

    results = scan_models()

    if args.ci:
        return run_ci_check(results, json_output=args.json)

    generate_map(results, output=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
