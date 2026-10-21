#!/usr/bin/env python3
"""
Generate comprehensive audit reports from endpoint audit results
"""

import json

# Setup Django
import os
import sys
from datetime import datetime
from pathlib import Path

os.chdir("/app")
if "/app" not in sys.path:
    sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

import django

django.setup()

# Import audit script
import importlib.util

script_path = Path("/app/scripts/audit-api-endpoints.py")
spec = importlib.util.spec_from_file_location("audit_api_endpoints", script_path)
audit_api_endpoints = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_api_endpoints)

EndpointAuditor = audit_api_endpoints.EndpointAuditor


def generate_markdown_inventory(data):
    """Generate Markdown inventory"""
    lines = ["# API Endpoint Inventory (Current State)\n"]
    lines.append(f"Generated: {datetime.now().isoformat()}\n")
    lines.append("## Summary\n")
    lines.append(f"- Total Endpoints: {data['inventory']['summary']['total_endpoints']}")
    lines.append(f"- Total Services: {data['inventory']['summary']['total_services']}")
    lines.append(f"- Duplicates Found: {len(data['issues'].get('duplicates', []))}")
    lines.append(
        f"- Naming Inconsistencies: {len(data['issues'].get('naming_inconsistencies', []))}\n"
    )

    lines.append("## Endpoints by Service\n")
    by_service = data["inventory"].get("by_service", {})
    for service, endpoints in sorted(by_service.items()):
        service_name = service if service else "(root)"
        lines.append(f"### {service_name.title()} ({len(endpoints)} endpoints)\n")
        for endpoint in endpoints[:50]:  # Limit to first 50 per service
            path = endpoint.get("full_path", endpoint.get("pattern", ""))
            name = endpoint.get("name", "")
            methods = ", ".join(endpoint.get("methods", ["GET"]))
            lines.append(f"- `{methods}` {path}")
            if name:
                lines.append(f"  - Name: `{name}`")
        if len(endpoints) > 50:
            lines.append(f"  - ... and {len(endpoints) - 50} more endpoints")
        lines.append("")

    return "\n".join(lines)


def generate_proposed_fixes_markdown(data):
    """Generate proposed fixes markdown"""
    lines = ["# API Endpoint Inventory (Proposed Fixes)\n"]
    lines.append(f"Generated: {datetime.now().isoformat()}\n")
    lines.append("## Summary\n")
    lines.append(f"- Total Endpoints: {data['inventory']['summary']['total_endpoints']}")
    lines.append(f"- Duplicates to Fix: {len(data['issues'].get('duplicates', []))}")
    lines.append(
        f"- Naming Issues to Fix: {len(data['issues'].get('naming_inconsistencies', []))}\n"
    )

    dups = data["issues"].get("duplicates", [])
    if dups:
        lines.append("## Duplicate Endpoints\n")
        for dup in dups[:30]:
            path = dup.get("path", dup.get("name", "unknown"))
            count = dup.get("count", 0)
            lines.append(f"- **{path}**: {count} occurrences")
            lines.append("  - Recommendation: Remove duplicate definitions or consolidate")
        lines.append("")

    naming = data["issues"].get("naming_inconsistencies", [])
    if naming:
        lines.append("## Naming Inconsistencies\n")
        for inc in naming[:20]:
            service = inc.get("service", "unknown")
            inc_type = inc.get("type", "unknown")
            lines.append(f"- **{service}**: {inc_type}")
            lines.append("  - Recommendation: Standardize naming pattern within service")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # Run audit
    auditor = EndpointAuditor()
    results = auditor.audit(
        "hub/apps/api/urls.py",
        check_duplicates=True,
        check_naming=True,
    )

    # Generate reports
    output_dir = Path("/app/docs/api-audit")
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON inventory
    json_output = auditor.output_json(results)
    (output_dir / "endpoint-inventory-current.json").write_text(json_output)

    # Markdown audit report
    markdown_report = auditor.output_markdown(results)
    (output_dir / "endpoint-naming-audit-report.md").write_text(markdown_report)

    # Markdown inventory
    markdown_inventory = generate_markdown_inventory(results)
    (output_dir / "endpoint-inventory-current.md").write_text(markdown_inventory)

    # Proposed fixes JSON
    proposed = {
        "summary": {
            "total_endpoints": results["inventory"]["summary"]["total_endpoints"],
            "total_services": results["inventory"]["summary"]["total_services"],
            "duplicates_to_fix": len(results["issues"].get("duplicates", [])),
            "naming_issues_to_fix": len(results["issues"].get("naming_inconsistencies", [])),
        },
        "proposed_fixes": {
            "duplicates": [
                {
                    "path": dup.get("path", dup.get("name", "unknown")),
                    "count": dup.get("count", 0),
                    "recommendation": "Remove duplicate endpoint definitions or consolidate into single endpoint",
                }
                for dup in results["issues"].get("duplicates", [])[:50]
            ],
            "naming_inconsistencies": [
                {
                    "service": inc.get("service", "unknown"),
                    "type": inc.get("type", "unknown"),
                    "recommendation": "Standardize naming pattern within service",
                }
                for inc in results["issues"].get("naming_inconsistencies", [])[:50]
            ],
        },
        "endpoints_by_service": results["inventory"].get("by_service", {}),
    }
    (output_dir / "endpoint-inventory-proposed.json").write_text(json.dumps(proposed, indent=2))

    # Proposed fixes markdown
    proposed_markdown = generate_proposed_fixes_markdown(results)
    (output_dir / "endpoint-inventory-proposed.md").write_text(proposed_markdown)

    # Print summary
    print("✅ Audit Reports Generated:")
    print(f"  - Total Endpoints: {results['inventory']['summary']['total_endpoints']}")
    print(f"  - Total Services: {results['inventory']['summary']['total_services']}")
    print(f"  - Duplicates Found: {len(results['issues'].get('duplicates', []))}")
    print(f"  - Naming Issues: {len(results['issues'].get('naming_inconsistencies', []))}")
    print(f"\n📄 Reports saved to: {output_dir}")
