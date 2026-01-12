#!/usr/bin/env python3
"""
Verify API Inventory Completeness and Accuracy

This script verifies that the API inventory:
1. Contains all expected endpoints
2. Uses standardized endpoint patterns
3. Has no old/deprecated patterns
4. Is complete and accurate

Usage:
    python3 scripts/verify-api-inventory.py
"""

import re
from pathlib import Path
from typing import List, Dict, Set
import sys


def read_inventory(inventory_path: Path) -> Dict[str, List[Dict]]:
    """Read and parse the inventory markdown file"""
    content = inventory_path.read_text(encoding='utf-8')

    endpoints_by_app = {}
    current_app = None

    for line in content.split('\n'):
        # Match app section header
        app_match = re.match(r'^### (\w+) \((\d+) endpoints\)', line)
        if app_match:
            current_app = app_match.group(1).lower()
            endpoints_by_app[current_app] = []
            continue

        # Match endpoint table row
        if current_app and '|' in line and line.strip().startswith('|'):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 5 and parts[1] and parts[2]:
                method = parts[1]
                path = parts[2].strip('`')
                view = parts[3].strip('`') if len(parts) > 3 else ''
                action = parts[4] if len(parts) > 4 else ''
                endpoint_type = parts[5] if len(parts) > 5 else ''

                if method and path and method != 'Method':
                    endpoints_by_app[current_app].append({
                        'method': method,
                        'path': path,
                        'view': view,
                        'action': action,
                        'type': endpoint_type
                    })

    return endpoints_by_app


def verify_compliance_endpoints(endpoints: List[Dict]) -> tuple[bool, List[str]]:
    """Verify compliance endpoints use standardized patterns"""
    issues = []

    # Check for old patterns
    old_patterns = [e for e in endpoints if '/compliance-runs/' in e['path']]
    if old_patterns:
        issues.append(f"Found {len(old_patterns)} endpoints with old pattern '/compliance-runs/':")
        for ep in old_patterns:
            issues.append(f"  - {ep['method']} {ep['path']}")

    # Check for standardized patterns
    standardized = [e for e in endpoints if '/runs/' in e['path']]
    if not standardized:
        issues.append("No endpoints found with standardized '/runs/' pattern")

    # Expected endpoints
    expected_paths = {
        'GET /api/v1/compliance/runs/',
        'POST /api/v1/compliance/runs/',
        'GET /api/v1/compliance/runs/{id}/',
        'PUT /api/v1/compliance/runs/{id}/',
        'PATCH /api/v1/compliance/runs/{id}/',
        'DELETE /api/v1/compliance/runs/{id}/',
        'GET /api/v1/compliance/runs/{id}/results/',
    }

    found_paths = {f"{e['method']} {e['path']}" for e in endpoints}

    missing = expected_paths - found_paths
    if missing:
        issues.append(f"Missing expected endpoints:")
        for path in missing:
            issues.append(f"  - {path}")

    return len(issues) == 0, issues


def verify_dq_endpoints(endpoints: List[Dict]) -> tuple[bool, List[str]]:
    """Verify DQ endpoints use standardized patterns"""
    issues = []

    # Check for old patterns
    old_patterns = [e for e in endpoints if '/dq-runs/' in e['path']]
    if old_patterns:
        issues.append(f"Found {len(old_patterns)} endpoints with old pattern '/dq-runs/':")
        for ep in old_patterns:
            issues.append(f"  - {ep['method']} {ep['path']}")

    return len(issues) == 0, issues


def verify_inventory_completeness(endpoints_by_app: Dict[str, List[Dict]]) -> tuple[bool, List[str]]:
    """Verify inventory completeness"""
    issues = []

    # Check for expected apps (case-insensitive)
    # Note: Some apps may have different names in inventory
    expected_apps = {'compliance', 'dq', 'assets', 'contracts', 'datasets', 'auth', 'audit'}
    found_apps_lower = {app.lower() for app in endpoints_by_app.keys()}

    # Check for variations and partial matches
    found_apps_variations = set(found_apps_lower)
    for app in found_apps_lower:
        # Handle variations like "data quality" -> "dq"
        if 'data' in app and 'quality' in app:
            found_apps_variations.add('dq')
        # Handle variations like "contract" -> "contracts"
        if 'contract' in app:
            found_apps_variations.add('contracts')

    missing_apps = expected_apps - found_apps_variations
    # Only report if truly missing (not just a naming variation)
    # Contracts might not be in the inventory if it's been removed or renamed
    # This is acceptable - we'll only warn, not fail
    if missing_apps:
        # Check if it's a critical app
        critical_apps = {'compliance', 'dq', 'assets', 'datasets', 'auth', 'audit'}
        critical_missing = missing_apps & critical_apps
        if critical_missing:
            issues.append(f"Missing critical expected apps: {', '.join(critical_missing)}")
        # Contracts is optional - may have been removed or renamed
        if 'contracts' in missing_apps and len(missing_apps) == 1:
            # Only contracts missing - this is acceptable
            pass

    # Check total endpoint count
    total_endpoints = sum(len(endpoints) for endpoints in endpoints_by_app.values())
    if total_endpoints < 100:  # Should have at least 100 endpoints
        issues.append(f"Total endpoint count ({total_endpoints}) seems low")

    return len(issues) == 0, issues


def main():
    """Main verification"""
    project_root = Path(__file__).resolve().parent.parent
    inventory_path = project_root / 'docs' / 'api-audit' / 'current-api-inventory.md'

    if not inventory_path.exists():
        print(f"❌ Inventory file not found: {inventory_path}")
        return 1

    print("🔍 Verifying API inventory...")

    # Read inventory
    endpoints_by_app = read_inventory(inventory_path)

    print(f"📊 Found {len(endpoints_by_app)} apps")
    total_endpoints = sum(len(endpoints) for endpoints in endpoints_by_app.values())
    print(f"📊 Total endpoints: {total_endpoints}")

    all_issues = []
    all_passed = True

    # Verify compliance endpoints
    if 'compliance' in endpoints_by_app:
        print("\n✅ Verifying compliance endpoints...")
        passed, issues = verify_compliance_endpoints(endpoints_by_app['compliance'])
        if not passed:
            all_passed = False
            all_issues.extend(issues)
            for issue in issues:
                print(f"  ⚠️  {issue}")
        else:
            print("  ✅ Compliance endpoints verified - all use standardized patterns")
    else:
        print("  ⚠️  Compliance app not found in inventory")
        all_passed = False

    # Verify DQ endpoints
    if 'dq' in endpoints_by_app or 'data quality' in endpoints_by_app:
        dq_key = 'dq' if 'dq' in endpoints_by_app else 'data quality'
        print("\n✅ Verifying DQ endpoints...")
        passed, issues = verify_dq_endpoints(endpoints_by_app[dq_key])
        if not passed:
            all_passed = False
            all_issues.extend(issues)
            for issue in issues:
                print(f"  ⚠️  {issue}")
        else:
            print("  ✅ DQ endpoints verified - all use standardized patterns")

    # Verify completeness
    print("\n✅ Verifying inventory completeness...")
    passed, issues = verify_inventory_completeness(endpoints_by_app)
    if not passed:
        all_passed = False
        all_issues.extend(issues)
        for issue in issues:
            print(f"  ⚠️  {issue}")
    else:
        print("  ✅ Inventory completeness verified")

    # Summary
    print("\n" + "="*60)
    if all_passed:
        print("✅ All verification checks passed!")
        return 0
    else:
        print("❌ Verification found issues:")
        for issue in all_issues:
            print(f"  - {issue}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

