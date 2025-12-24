#!/usr/bin/env python3
"""
ODPS Marketplace Integration Dashboard Validation Test

Comprehensive validation of the ODPS Marketplace Integration dashboard
without requiring Django or database access.

This script validates:
- Dashboard JSON structure
- Required panels exist
- SQL queries are safe
- Panel configurations are correct
- All required fields are present

Usage:
    python scripts/test_odps_marketplace_dashboard.py
"""
import json
import sys
from pathlib import Path


def validate_dashboard():
    """Validate the ODPS Marketplace Integration dashboard."""
    project_root = Path(__file__).parent.parent
    dashboard_path = project_root / "monitoring" / "grafana" / "dashboards" / "odps-marketplace-integration.json"

    errors = []
    warnings = []

    print("=== ODPS Marketplace Integration Dashboard Validation ===\n")

    # Test 1: File exists
    if not dashboard_path.exists():
        print(f"❌ Dashboard file not found: {dashboard_path}")
        return False

    print(f"✅ Dashboard file exists: {dashboard_path}")

    # Test 2: Valid JSON
    try:
        with open(dashboard_path, 'r') as f:
            config = json.load(f)
        print("✅ Dashboard JSON is valid")
    except json.JSONDecodeError as e:
        print(f"❌ Dashboard JSON is invalid: {e}")
        return False

    # Test 3: Required structure
    if 'dashboard' not in config:
        print("❌ Dashboard missing 'dashboard' key")
        return False

    dashboard = config['dashboard']

    required_keys = ['title', 'tags', 'schemaVersion', 'version', 'panels']
    for key in required_keys:
        if key not in dashboard:
            errors.append(f"Dashboard missing required key: {key}")

    if errors:
        for error in errors:
            print(f"❌ {error}")
        return False

    print(f"✅ Dashboard structure valid")
    print(f"   Title: {dashboard['title']}")
    print(f"   Tags: {dashboard['tags']}")
    print(f"   Schema Version: {dashboard['schemaVersion']}")
    print(f"   Version: {dashboard['version']}")
    print(f"   Panels: {len(dashboard['panels'])}")

    # Test 4: Required panels
    print("\n=== Required Panels Check ===")
    required_panels = [
        'Marketplace Listing Creation Rate',
        'Marketplace Purchase Rate',
        'Pricing Plan Usage',
        'Access Method Usage'
    ]

    panel_titles = [p.get('title', '') for p in dashboard['panels']]
    for required in required_panels:
        found = any(required in title for title in panel_titles)
        if found:
            print(f"✅ Panel found: {required}")
        else:
            errors.append(f"Required panel missing: {required}")
            print(f"❌ Panel missing: {required}")

    # Test 5: Panel structure
    print("\n=== Panel Structure Validation ===")
    for panel in dashboard['panels']:
        title = panel.get('title', 'Unknown')
        panel_id = panel.get('id', 'Unknown')

        # Check required fields
        required_fields = ['id', 'title', 'type', 'gridPos', 'targets']
        missing = [f for f in required_fields if f not in panel]

        if missing:
            errors.append(f"Panel '{title}' missing fields: {missing}")
            print(f"❌ {title}: Missing {missing}")
            continue

        # Check targets
        targets = panel.get('targets', [])
        if not targets:
            errors.append(f"Panel '{title}' has no targets")
            print(f"❌ {title}: No targets")
            continue

        # Check each target
        for i, target in enumerate(targets):
            has_sql = 'rawSql' in target or 'rawQuery' in target
            has_expr = 'expr' in target

            if not has_sql and not has_expr:
                errors.append(f"Panel '{title}' target {i+1} has no query")
                print(f"❌ {title} target {i+1}: No query")
            elif has_sql:
                sql = target.get('rawSql', target.get('rawQuery', ''))
                if not sql or len(sql.strip()) == 0:
                    errors.append(f"Panel '{title}' target {i+1} has empty SQL")
                    print(f"❌ {title} target {i+1}: Empty SQL")
                else:
                    # Verify it's a SELECT query
                    if not sql.strip().upper().startswith('SELECT'):
                        errors.append(f"Panel '{title}' target {i+1} is not a SELECT query")
                        print(f"❌ {title} target {i+1}: Not a SELECT query")
                    else:
                        print(f"✅ {title} target {i+1}: Valid SELECT query")

        # Check gridPos
        grid_pos = panel.get('gridPos', {})
        required_grid = ['h', 'w', 'x', 'y']
        missing_grid = [f for f in required_grid if f not in grid_pos]
        if missing_grid:
            errors.append(f"Panel '{title}' gridPos missing: {missing_grid}")
            print(f"❌ {title}: gridPos incomplete")
        else:
            print(f"✅ {title}: gridPos valid")

        # Check description
        if 'description' not in panel or not panel.get('description'):
            warnings.append(f"Panel '{title}' missing description")
            print(f"⚠️  {title}: Missing description")
        else:
            print(f"✅ {title}: Has description")

    # Test 6: SQL query content validation
    print("\n=== SQL Query Content Validation ===")
    all_sqls = []
    for panel in dashboard['panels']:
        for target in panel.get('targets', []):
            sql = target.get('rawSql', target.get('rawQuery', ''))
            if sql:
                all_sqls.append((panel.get('title', 'Unknown'), sql))

    # Check for required table references
    listings_sqls = [title for title, sql in all_sqls if 'listings' in sql.lower()]
    orders_sqls = [title for title, sql in all_sqls if 'orders' in sql.lower()]
    pricing_sqls = [title for title, sql in all_sqls if 'pricing' in sql.lower() or 'pricing_plans' in sql.lower()]
    access_sqls = [title for title, sql in all_sqls if 'access_method' in sql.lower() or 'accessMethod' in sql]

    if listings_sqls:
        print(f"✅ Listings queries found in: {', '.join(set(listings_sqls))}")
    else:
        errors.append("No queries reference listings table")
        print("❌ No listings queries")

    if orders_sqls:
        print(f"✅ Orders queries found in: {', '.join(set(orders_sqls))}")
    else:
        errors.append("No queries reference orders table")
        print("❌ No orders queries")

    if pricing_sqls:
        print(f"✅ Pricing plan queries found in: {', '.join(set(pricing_sqls))}")
    else:
        errors.append("No queries reference pricing plans")
        print("❌ No pricing plan queries")

    if access_sqls:
        print(f"✅ Access method queries found in: {', '.join(set(access_sqls))}")
    else:
        errors.append("No queries reference access methods")
        print("❌ No access method queries")

    # Test 7: Task tag
    print("\n=== Metadata Validation ===")
    if 'task-6.6.8' in dashboard['tags']:
        print("✅ Task tag present: task-6.6.8")
    else:
        errors.append("Dashboard missing task-6.6.8 tag")
        print("❌ Missing task-6.6.8 tag")

    if 'marketplace' in dashboard['tags']:
        print("✅ Marketplace tag present")
    else:
        warnings.append("Dashboard missing marketplace tag")
        print("⚠️  Missing marketplace tag")

    # Summary
    print("\n=== Validation Summary ===")
    if errors:
        print(f"❌ Found {len(errors)} error(s):")
        for error in errors:
            print(f"   - {error}")
        return False

    if warnings:
        print(f"⚠️  Found {len(warnings)} warning(s):")
        for warning in warnings:
            print(f"   - {warning}")

    print("✅ All validation tests passed!")
    print(f"✅ Dashboard has {len(dashboard['panels'])} panels")
    print("✅ All required panels are present")
    print("✅ All SQL queries are safe (SELECT-only)")
    print("✅ Dashboard is ready for use")

    return True


if __name__ == "__main__":
    success = validate_dashboard()
    sys.exit(0 if success else 1)

