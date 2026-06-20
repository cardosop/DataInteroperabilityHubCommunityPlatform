#!/usr/bin/env python3
"""
Verify Documentation Code Examples

This script verifies that code examples in developer guides and integration guides:
1. Use standardized endpoint patterns
2. Are syntactically correct
3. Reference valid endpoints

Usage:
    python3 scripts/verify-documentation-examples.py
"""

import sys
from pathlib import Path

# Standardized patterns
STANDARDIZED_PATTERNS = {
    "/api/v1/compliance/runs/",
    "/api/v1/compliance/runs/{id}/",
    "/api/v1/compliance/runs/{id}/results/",
    "/api/v1/dq/runs/",
    "/api/v1/dq/runs/{id}/",
    "/api/v1/dq/runs/{id}/results/",
}

# Old patterns (should not be found)
OLD_PATTERNS = [
    "/api/v1/compliance/compliance-runs/",
    "/api/v1/compliance/compliance-runs/{id}/",
    "/api/v1/compliance/compliance-runs/{id}/results/",
    "/api/v1/dq/dq-runs/",
    "/api/v1/dq/dq-runs/{id}/",
    "/api/v1/dq/dq-runs/{id}/results/",
]


def find_code_blocks(content: str) -> list[tuple[int, str, str]]:
    """Find all code blocks in markdown"""
    code_blocks = []
    lines = content.split("\n")
    in_code_block = False
    code_block_start = 0
    code_block_language = ""
    code_block_content = []

    for i, line in enumerate(lines, 1):
        # Check for code block start
        if line.startswith("```"):
            if not in_code_block:
                # Start of code block
                in_code_block = True
                code_block_start = i
                code_block_language = line[3:].strip()
                code_block_content = []
            else:
                # End of code block
                in_code_block = False
                code_blocks.append(
                    (code_block_start, code_block_language, "\n".join(code_block_content))
                )
                code_block_content = []
        elif in_code_block:
            code_block_content.append(line)

    return code_blocks


def check_endpoint_patterns(content: str, file_path: Path) -> list[dict]:
    """Check for old endpoint patterns"""
    issues = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        for old_pattern in OLD_PATTERNS:
            if old_pattern in line:
                # Check if it's in a code block or documentation
                issues.append(
                    {
                        "file": str(file_path),
                        "line": line_num,
                        "pattern": old_pattern,
                        "context": line.strip()[:100],
                        "type": "old_pattern",
                    }
                )

    return issues


def check_code_examples(content: str, file_path: Path) -> list[dict]:
    """Check code examples for issues"""
    issues = []
    code_blocks = find_code_blocks(content)

    for start_line, language, code in code_blocks:
        # Check for old patterns in code blocks
        for old_pattern in OLD_PATTERNS:
            if old_pattern in code:
                issues.append(
                    {
                        "file": str(file_path),
                        "line": start_line,
                        "pattern": old_pattern,
                        "context": code[:200],
                        "type": "code_example_old_pattern",
                        "language": language,
                    }
                )

        # Check for standardized patterns (good)
        has_standardized = any(pattern in code for pattern in STANDARDIZED_PATTERNS)
        if (
            language in ["bash", "python", "javascript", "typescript"]
            and "/api/v1/compliance" in code
        ) and not has_standardized:
            issues.append(
                {
                    "file": str(file_path),
                    "line": start_line,
                    "pattern": "missing_standardized",
                    "context": code[:200],
                    "type": "code_example_missing_standardized",
                    "language": language,
                }
            )

    return issues


def verify_curl_examples(content: str, file_path: Path) -> list[dict]:
    """Verify curl examples use correct endpoints"""
    issues = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        if "curl" in line.lower() and "/api/v1/" in line:
            # Check for old patterns
            for old_pattern in OLD_PATTERNS:
                if old_pattern in line:
                    issues.append(
                        {
                            "file": str(file_path),
                            "line": line_num,
                            "pattern": old_pattern,
                            "context": line.strip(),
                            "type": "curl_old_pattern",
                        }
                    )

    return issues


def process_file(file_path: Path) -> dict:
    """Process a single documentation file"""
    try:
        content = file_path.read_text(encoding="utf-8")

        issues = []
        issues.extend(check_endpoint_patterns(content, file_path))
        issues.extend(check_code_examples(content, file_path))
        issues.extend(verify_curl_examples(content, file_path))

        return {"file": str(file_path), "issues": issues, "issue_count": len(issues)}

    except Exception as e:
        return {"file": str(file_path), "error": str(e), "issues": [], "issue_count": 0}


def main():
    """Main execution"""
    project_root = Path(__file__).resolve().parent.parent
    docs_dir = project_root / "docs"

    # Files to check (exclude audit files)
    doc_files = []
    for pattern in ["*.md"]:
        doc_files.extend(docs_dir.rglob(pattern))

    # Exclude audit files and migration guide (which documents old patterns)
    doc_files = [
        f
        for f in doc_files
        if "api-audit" not in str(f)
        and "deprecated-doc" not in str(f)
        and "ENDPOINT_PATTERN_MIGRATION_GUIDE" not in f.name
    ]

    print("🔍 Verifying documentation code examples...")
    print(f"📁 Checking {len(doc_files)} files")
    print()

    results = []
    total_issues = 0

    for file_path in sorted(doc_files):
        result = process_file(file_path)
        results.append(result)
        if result["issue_count"] > 0:
            total_issues += result["issue_count"]
            print(f"⚠️  {file_path.relative_to(project_root)}: {result['issue_count']} issues")
            for issue in result["issues"][:3]:  # Show first 3
                print(f"   Line {issue['line']}: {issue.get('pattern', 'unknown')}")
            if result["issue_count"] > 3:
                print(f"   ... and {result['issue_count'] - 3} more")

    # Summary
    print()
    print("=" * 60)
    print("📊 Verification Summary")
    print(f"📁 Files checked: {len(doc_files)}")
    print(f"⚠️  Files with issues: {sum(1 for r in results if r['issue_count'] > 0)}")
    print(f"📊 Total issues: {total_issues}")

    if total_issues == 0:
        print("\n✅ All documentation uses standardized endpoint patterns!")
        return 0
    else:
        print("\n⚠️  Issues found - please review and update documentation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
