#!/usr/bin/env python3
"""
Update Documentation Endpoints

This script updates all code examples in developer guides and integration guides
to use standardized endpoint patterns:
- `/api/v1/compliance/runs/` (not `/api/v1/compliance/compliance-runs/`)
- `/api/v1/dq/runs/` (not `/api/v1/dq/dq-runs/`)

Usage:
    python3 scripts/update-documentation-endpoints.py
"""

import re
from pathlib import Path
from typing import List, Tuple
import sys


# Patterns to replace
REPLACEMENTS = [
    # Compliance endpoints
    (r'/api/v1/compliance/compliance-runs/', '/api/v1/compliance/runs/'),
    (r'/api/v1/compliance/compliance-runs\b', '/api/v1/compliance/runs'),
    (r'compliance-runs/', 'runs/'),
    (r'compliance-runs\b', 'runs'),

    # DQ endpoints
    (r'/api/v1/dq/dq-runs/', '/api/v1/dq/runs/'),
    (r'/api/v1/dq/dq-runs\b', '/api/v1/dq/runs'),
    (r'dq-runs/', 'runs/'),
    (r'dq-runs\b', 'runs'),
]

# Files to check (exclude audit files and deprecated docs)
DOC_PATTERNS = [
    'docs/*.md',
    'docs/**/*.md',
]

# Files to exclude
EXCLUDE_PATTERNS = [
    '**/api-audit/**',
    '**/deprecated-doc/**',
    '**/node_modules/**',
    '**/.git/**',
]


def should_process_file(file_path: Path) -> bool:
    """Check if file should be processed"""
    file_str = str(file_path)

    # Exclude patterns
    for exclude_pattern in EXCLUDE_PATTERNS:
        if exclude_pattern.replace('**/', '') in file_str:
            return False

    # Only process markdown files
    if not file_path.suffix == '.md':
        return False

    return True


def find_old_patterns(content: str) -> List[Tuple[int, str, str]]:
    """Find all old patterns in content"""
    issues = []
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        # Check for old compliance patterns
        if '/compliance-runs/' in line or '/compliance/compliance-runs' in line:
            if '/api/v1/compliance/runs/' not in line:  # Not already correct
                issues.append((line_num, line, 'compliance-runs'))

        # Check for old DQ patterns
        if '/dq-runs/' in line or '/dq/dq-runs' in line:
            if '/api/v1/dq/runs/' not in line:  # Not already correct
                issues.append((line_num, line, 'dq-runs'))

    return issues


def update_content(content: str) -> Tuple[str, int]:
    """Update content with standardized patterns"""
    updated_content = content
    replacements_count = 0

    for pattern, replacement in REPLACEMENTS:
        matches = len(re.findall(pattern, updated_content))
        if matches > 0:
            updated_content = re.sub(pattern, replacement, updated_content)
            replacements_count += matches

    return updated_content, replacements_count


def process_file(file_path: Path, dry_run: bool = False) -> Tuple[bool, int, List[Tuple[int, str, str]]]:
    """Process a single file"""
    try:
        content = file_path.read_text(encoding='utf-8')

        # Find old patterns
        issues = find_old_patterns(content)

        if not issues:
            return False, 0, []

        if dry_run:
            return True, len(issues), issues

        # Update content
        updated_content, replacements_count = update_content(content)

        # Write back
        file_path.write_text(updated_content, encoding='utf-8')

        return True, replacements_count, issues

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False, 0, []


def main():
    """Main execution"""
    project_root = Path(__file__).resolve().parent.parent
    docs_dir = project_root / 'docs'

    # Parse command line arguments
    dry_run = '--dry-run' in sys.argv

    print("🔍 Searching for old endpoint patterns in documentation...")
    print(f"📁 Scanning: {docs_dir}")
    if dry_run:
        print("🔍 DRY RUN MODE - No files will be modified")
    print()

    # Find all markdown files
    all_files = []
    for pattern in DOC_PATTERNS:
        all_files.extend(docs_dir.glob(pattern.replace('docs/', '')))

    # Filter files
    files_to_process = [f for f in all_files if should_process_file(f)]

    print(f"📊 Found {len(files_to_process)} documentation files to check")
    print()

    # Process files
    updated_files = []
    total_replacements = 0
    all_issues = []

    for file_path in sorted(files_to_process):
        relative_path = file_path.relative_to(project_root)
        was_updated, replacements, issues = process_file(file_path, dry_run=dry_run)

        if was_updated:
            updated_files.append(relative_path)
            total_replacements += replacements
            all_issues.extend([(relative_path, line_num, line, pattern)
                              for line_num, line, pattern in issues])

            if dry_run:
                print(f"⚠️  {relative_path}: {len(issues)} issues found")
                for line_num, line, pattern in issues[:3]:  # Show first 3
                    print(f"   Line {line_num}: {line.strip()[:80]}")
                if len(issues) > 3:
                    print(f"   ... and {len(issues) - 3} more")
            else:
                print(f"✅ {relative_path}: {replacements} replacements made")

    # Summary
    print()
    print("=" * 60)
    if dry_run:
        print(f"🔍 DRY RUN SUMMARY")
        print(f"📊 Files with issues: {len(updated_files)}")
        print(f"📊 Total issues found: {len(all_issues)}")
        if all_issues:
            print("\n⚠️  Issues found:")
            for file_path, line_num, line, pattern in all_issues[:10]:
                print(f"  - {file_path}:{line_num} ({pattern})")
            if len(all_issues) > 10:
                print(f"  ... and {len(all_issues) - 10} more")
    else:
        print(f"✅ UPDATE SUMMARY")
        print(f"📊 Files updated: {len(updated_files)}")
        print(f"📊 Total replacements: {total_replacements}")
        if updated_files:
            print("\n✅ Updated files:")
            for file_path in updated_files:
                print(f"  - {file_path}")

    print()

    return 0 if len(updated_files) == 0 or not dry_run else 1


if __name__ == '__main__':
    sys.exit(main())

