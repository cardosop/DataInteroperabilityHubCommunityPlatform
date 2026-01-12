#!/usr/bin/env python3
"""
Verification script for documentation endpoint audit

This script verifies that:
1. All documentation files were found
2. All endpoints were mapped correctly
3. Documentation mapping is complete
"""

import json
import sys
from pathlib import Path


def verify_audit_report(report_path: str) -> bool:
    """Verify the audit report"""
    report_file = Path(report_path)

    if not report_file.exists():
        print(f"❌ Report file not found: {report_path}")
        return False

    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
    except Exception as e:
        print(f"❌ Error reading report: {e}")
        return False

    # Verify structure
    required_keys = ['summary', 'endpoints', 'documentation_mappings']
    for key in required_keys:
        if key not in report:
            print(f"❌ Missing required key: {key}")
            return False

    summary = report['summary']

    # Verify summary
    print("="*60)
    print("Documentation Audit Verification")
    print("="*60)
    print(f"\n📊 Summary:")
    print(f"   Total Endpoints: {summary['total_endpoints']}")
    print(f"   Total References: {summary['total_references']}")
    print(f"   Documentation Files: {summary['total_documentation_files']}")

    # Verify documentation types
    print(f"\n📄 Documentation Types:")
    for doc_type, count in summary['documentation_types'].items():
        print(f"   {doc_type}: {count}")

    # Verify endpoints
    endpoints = report['endpoints']
    print(f"\n🔗 Endpoints:")
    print(f"   Total: {len(endpoints)}")

    endpoints_with_methods = len([e for e in endpoints if e.get('methods')])
    print(f"   With Methods: {endpoints_with_methods}")

    endpoints_with_multiple_docs = len([e for e in endpoints if len(e.get('documentation_files', [])) > 1])
    print(f"   With Multiple Docs: {endpoints_with_multiple_docs}")

    # Verify verification results
    verification = summary.get('verification', {})
    doc_found = verification.get('documentation_found', {})
    mapping_comp = verification.get('mapping_completeness', {})

    print(f"\n✅ Verification Results:")
    print(f"   Documentation Found Status: {doc_found.get('status')}")
    print(f"   Files Checked: {doc_found.get('files_checked')}")
    print(f"   Files With Endpoints: {doc_found.get('files_with_endpoints')}")
    print(f"   Mapping Completeness Status: {mapping_comp.get('status')}")
    print(f"   Endpoints With Docs: {mapping_comp.get('endpoints_with_docs')}")

    # Check for issues
    issues = []

    if doc_found.get('status') != 'success':
        issues.append("Documentation found status is not 'success'")

    if mapping_comp.get('status') != 'success':
        issues.append("Mapping completeness status is not 'success'")

    if len(endpoints) == 0:
        issues.append("No endpoints found in report")

    if len(endpoints) != summary['total_endpoints']:
        issues.append(f"Endpoint count mismatch: {len(endpoints)} != {summary['total_endpoints']}")

    if issues:
        print(f"\n⚠️  Issues Found:")
        for issue in issues:
            print(f"   - {issue}")
        return False

    print(f"\n✅ All verifications passed!")
    return True


def main():
    """Main execution"""
    report_path = "docs/api-audit/documentation-endpoint-audit.json"

    if len(sys.argv) > 1:
        report_path = sys.argv[1]

    success = verify_audit_report(report_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

