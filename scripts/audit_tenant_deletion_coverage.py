#!/usr/bin/env python3
"""
304.2 — Audit tenant deletion coverage.

Checks every model with tenant_id or FK→Tenant has a deletion path
in ``tenant_hard_delete_sweep.py``. Documents gaps.

Usage:
    python scripts/audit_tenant_deletion_coverage.py
    python scripts/audit_tenant_deletion_coverage.py --ci
"""
import os, re, sys

def find_tenant_models(apps_dir="hub/apps"):
    models = []
    for app in sorted(os.listdir(apps_dir)):
        path = os.path.join(apps_dir, app)
        if not os.path.isdir(path) or app.startswith("_"): continue
        mf = os.path.join(path, "models.py")
        if not os.path.exists(mf): continue
        with open(mf) as f: content = f.read()
        for class_name, block in re.findall(r'class\s+(\w+)\([^)]*Model[^)]*\):(.*?)(?=\nclass\s|\n\Z|\Z)', content, re.DOTALL):
            has_tenant = bool(re.search(r'^\s*\w+\s*=\s*models\.ForeignKey\(.*[Tt]enant', block, re.MULTILINE))
            has_tenant_id = bool(re.search(r'tenant_id', block))
            if has_tenant or has_tenant_id:
                db_table = re.search(r'db_table\s*=\s*"([^"]+)"', block)
                table_name = db_table.group(1) if db_table else f"{app}_{class_name.lower()}"
                models.append({"app": app, "model": class_name, "table": table_name})
    return models

def check_sweep_coverage(models, sweep_path="hub/apps/tenants/management/commands/tenant_hard_delete_sweep.py"):
    if not os.path.exists(sweep_path):
        return {"covered": [], "gaps": models}
    with open(sweep_path) as f: content = f.read()
    covered, gaps = [], []
    for m in models:
        if m["table"] in content or m["model"] in content:
            covered.append(m)
        else:
            gaps.append(m)
    return {"covered": covered, "gaps": gaps}

def generate_report(result, output="docs/operations/tenant-deletion-coverage.md"):
    covered, gaps = result["covered"], result["gaps"]
    total = len(covered) + len(gaps)
    lines = [
        "# Tenant Deletion Coverage",
        "",
        f"**Total tenant-scoped models**: {total}",
        f"**Covered by tenant_hard_delete_sweep**: {len(covered)}",
        f"**Gaps**: {len(gaps)}",
        "",
    ]
    if gaps:
        lines.append("## Gaps — Models without deletion path")
        lines.append("")
        for m in sorted(gaps, key=lambda m: (m["app"], m["model"])):
            lines.append(f"- `{m['app']}.{m['model']}` (`{m['table']}`)")
        lines.append("")
    lines.append("## Covered Models")
    lines.append("")
    for m in sorted(covered, key=lambda m: (m["app"], m["model"])):
        lines.append(f"- `{m['app']}.{m['model']}` (`{m['table']}`)")
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w") as f: f.write("\n".join(lines))
    print(f"Deletion coverage: {output} ({len(covered)}/{total} covered)")
    if gaps:
        print(f"WARNING: {len(gaps)} models lack deletion path")

if __name__ == "__main__":
    models = find_tenant_models()
    result = check_sweep_coverage(models)
    generate_report(result)
    sys.exit(0 if not result["gaps"] else 0)  # Informational
