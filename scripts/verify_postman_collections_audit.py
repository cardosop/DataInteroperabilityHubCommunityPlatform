#!/usr/bin/env python3
"""
Verification script for Postman collections audit

Verifies that the Postman collections audit was completed successfully.
"""

import json
import sys
from pathlib import Path


def verify_audit_report(report_file: str) -> bool:
    """Verify the audit report exists and has correct structure"""
    report_path = Path(report_file)

    if not report_path.exists():
        print(f"❌ Report file not found: {report_file}")
        return False

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in report file: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading report file: {e}")
        return False

    # Verify structure
    required_keys = ['summary', 'collections', 'endpoints']
    for key in required_keys:
        if key not in report:
            print(f"❌ Missing required key in report: {key}")
            return False

    summary = report['summary']
    required_summary_keys = [
        'generated_at',
        'total_collections',
        'valid_collections',
        'invalid_collections',
        'total_requests',
        'valid_requests',
        'invalid_requests'
    ]

    for key in required_summary_keys:
        if key not in summary:
            print(f"❌ Missing required key in summary: {key}")
            return False

    # Verify data types
    if not isinstance(summary['total_collections'], int):
        print("❌ total_collections should be an integer")
        return False

    if not isinstance(report['collections'], list):
        print("❌ collections should be a list")
        return False

    if not isinstance(report['endpoints'], list):
        print("❌ endpoints should be a list")
        return False

    # Verify counts match
    if len(report['collections']) != summary['total_collections']:
        print(f"❌ Collection count mismatch: summary says {summary['total_collections']}, but found {len(report['collections'])}")
        return False

    # Verify valid/invalid counts
    valid_count = sum(1 for c in report['collections'] if c.get('is_valid', False))
    invalid_count = sum(1 for c in report['collections'] if not c.get('is_valid', True))

    if valid_count != summary['valid_collections']:
        print(f"⚠️  Valid collection count mismatch: summary says {summary['valid_collections']}, but counted {valid_count}")

    if invalid_count != summary['invalid_collections']:
        print(f"⚠️  Invalid collection count mismatch: summary says {summary['invalid_collections']}, but counted {invalid_count}")

    print("✅ Report structure is valid")
    print(f"   Total collections: {summary['total_collections']}")
    print(f"   Valid collections: {summary['valid_collections']}")
    print(f"   Invalid collections: {summary['invalid_collections']}")
    print(f"   Total requests: {summary['total_requests']}")
    print(f"   Valid requests: {summary['valid_requests']}")
    print(f"   Invalid requests: {summary['invalid_requests']}")

    return True


def main():
    """Main verification function"""
    report_file = "docs/api-audit/postman-collections-audit.json"

    if len(sys.argv) > 1:
        report_file = sys.argv[1]

    success = verify_audit_report(report_file)

    if success:
        print("\n✅ Postman collections audit verification passed")
        sys.exit(0)
    else:
        print("\n❌ Postman collections audit verification failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

