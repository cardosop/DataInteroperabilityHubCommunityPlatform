#!/usr/bin/env python3
"""
Verification script for code examples audit

Verifies that the code examples audit was completed successfully.
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
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in report file: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading report file: {e}")
        return False

    # Verify structure
    required_keys = ["summary", "examples", "endpoints"]
    for key in required_keys:
        if key not in report:
            print(f"❌ Missing required key in report: {key}")
            return False

    summary = report["summary"]
    required_summary_keys = [
        "generated_at",
        "total_examples",
        "valid_examples",
        "invalid_examples",
        "total_endpoints_found",
        "valid_endpoints",
        "invalid_endpoints",
    ]

    for key in required_summary_keys:
        if key not in summary:
            print(f"❌ Missing required key in summary: {key}")
            return False

    # Verify data types
    if not isinstance(summary["total_examples"], int):
        print("❌ total_examples should be an integer")
        return False

    if not isinstance(report["examples"], list):
        print("❌ examples should be a list")
        return False

    if not isinstance(report["endpoints"], list):
        print("❌ endpoints should be a list")
        return False

    # Verify counts match
    if len(report["examples"]) != summary["total_examples"]:
        print(
            f"❌ Example count mismatch: summary says {summary['total_examples']}, but found {len(report['examples'])}"
        )
        return False

    # Verify valid/invalid counts
    valid_count = sum(1 for e in report["examples"] if e.get("is_valid", False))
    invalid_count = sum(1 for e in report["examples"] if not e.get("is_valid", True))

    if valid_count != summary["valid_examples"]:
        print(
            f"⚠️  Valid example count mismatch: summary says {summary['valid_examples']}, but counted {valid_count}"
        )

    if invalid_count != summary["invalid_examples"]:
        print(
            f"⚠️  Invalid example count mismatch: summary says {summary['invalid_examples']}, but counted {invalid_count}"
        )

    print("✅ Report structure is valid")
    print(f"   Total examples: {summary['total_examples']}")
    print(f"   Valid examples: {summary['valid_examples']}")
    print(f"   Invalid examples: {summary['invalid_examples']}")
    print(f"   Total endpoints found: {summary['total_endpoints_found']}")
    print(f"   Valid endpoints: {summary['valid_endpoints']}")
    print(f"   Invalid endpoints: {summary['invalid_endpoints']}")

    return True


def main():
    """Main verification function"""
    report_file = "docs/api-audit/code-examples-audit.json"

    if len(sys.argv) > 1:
        report_file = sys.argv[1]

    success = verify_audit_report(report_file)

    if success:
        print("\n✅ Code examples audit verification passed")
        sys.exit(0)
    else:
        print("\n❌ Code examples audit verification failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
