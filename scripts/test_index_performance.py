#!/usr/bin/env python
"""
Test database index performance using EXPLAIN ANALYZE.

This script tests all indexes created in Phase 15 to ensure they are being used
by PostgreSQL query planner for optimal performance.

Usage:
    python scripts/test_index_performance.py [--verbose]
"""

import argparse
import os
import sys

import django
from django.db import connection


def setup_django():
    """Setup Django environment."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
    django.setup()


def explain_query(query: str, params: tuple = None) -> dict:
    """
    Execute EXPLAIN ANALYZE on a query and return results.

    Args:
        query: SQL query to explain
        params: Query parameters (optional)

    Returns:
        Dictionary with query plan and execution stats
    """
    with connection.cursor() as cursor:
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
        cursor.execute(explain_query, params or ())
        result = cursor.fetchone()
        if result and result[0]:
            return result[0][0]
        return {}


def check_index_usage(plan: dict, index_name: str) -> bool:
    """
    Check if a specific index is used in the query plan.

    Args:
        plan: Query plan dictionary
        index_name: Name of index to check for

    Returns:
        True if index is used, False otherwise
    """
    plan_str = str(plan).lower()
    return index_name.lower() in plan_str


def test_contract_indexes(verbose: bool = False) -> list[tuple[str, bool, str]]:
    """Test contract JSONB indexes."""
    results = []

    # Test contact_email filter
    query = """
        SELECT id FROM contracts_contract
        WHERE hub_contract_json->'contact'->>'email' = %s
        LIMIT 10
    """
    plan = explain_query(query, ("test@example.com",))
    index_used = check_index_usage(plan, "contact_email")
    results.append(("Contact Email Filter", index_used, str(plan.get("Plan", {}))))

    # Test server_type filter
    query = """
        SELECT id FROM contracts_contract
        WHERE hub_contract_json->'servers'->>'type' = %s
        LIMIT 10
    """
    plan = explain_query(query, ("s3",))
    index_used = check_index_usage(plan, "servers_type")
    results.append(("Server Type Filter", index_used, str(plan.get("Plan", {}))))

    # Test servicelevels filter
    query = """
        SELECT id FROM contracts_contract
        WHERE hub_contract_json->'servicelevels' @> %s::jsonb
        LIMIT 10
    """
    plan = explain_query(query, ('[{"property": "availability"}]',))
    index_used = check_index_usage(plan, "servicelevels")
    results.append(("Service Levels Filter", index_used, str(plan.get("Plan", {}))))

    # Test models filter
    query = """
        SELECT id FROM contracts_contract
        WHERE hub_contract_json->'models' @> %s::jsonb
        LIMIT 10
    """
    plan = explain_query(query, ('[{"name": "test"}]',))
    index_used = check_index_usage(plan, "models")
    results.append(("Models Filter", index_used, str(plan.get("Plan", {}))))

    # Test lineage filter
    query = """
        SELECT id FROM contracts_contract
        WHERE hub_contract_json->'lineage' IS NOT NULL
        LIMIT 10
    """
    plan = explain_query(query)
    index_used = check_index_usage(plan, "lineage")
    results.append(("Lineage Filter", index_used, str(plan.get("Plan", {}))))

    return results


def test_version_history_indexes(verbose: bool = False) -> list[tuple[str, bool, str]]:
    """Test version history indexes."""
    results = []

    # Test parent_version lookup
    query = """
        SELECT id FROM datasets_dataset
        WHERE tenant_id = %s AND asset_id = %s AND parent_version_id IS NOT NULL
        LIMIT 10
    """
    plan = explain_query(
        query, ("00000000-0000-0000-0000-000000000000", "00000000-0000-0000-0000-000000000000")
    )
    index_used = check_index_usage(plan, "parent_version")
    results.append(("Version Tree Traversal", index_used, str(plan.get("Plan", {}))))

    # Test semantic version lookup
    query = """
        SELECT id FROM datasets_dataset
        WHERE tenant_id = %s AND asset_id = %s AND semantic_version = %s
        LIMIT 10
    """
    plan = explain_query(
        query,
        ("00000000-0000-0000-0000-000000000000", "00000000-0000-0000-0000-000000000000", "1.0.0"),
    )
    index_used = check_index_usage(plan, "semantic_version")
    results.append(("Semantic Version Lookup", index_used, str(plan.get("Plan", {}))))

    # Test version hash lookup
    query = """
        SELECT id FROM datasets_dataset
        WHERE version_hash = %s
        LIMIT 10
    """
    plan = explain_query(query, ("test_hash",))
    index_used = check_index_usage(plan, "version_hash")
    results.append(("Version Hash Lookup", index_used, str(plan.get("Plan", {}))))

    return results


def test_search_indexes(verbose: bool = False) -> list[tuple[str, bool, str]]:
    """Test search indexes."""
    results = []

    # Test full-text search
    query = """
        SELECT id FROM search_index
        WHERE tenant_id = %s AND search_vector @@ to_tsquery('english', %s)
        LIMIT 10
    """
    plan = explain_query(query, ("00000000-0000-0000-0000-000000000000", "test"))
    index_used = check_index_usage(plan, "search_vector")
    results.append(("Full-Text Search", index_used, str(plan.get("Plan", {}))))

    # Test classification filter
    query = """
        SELECT id FROM search_index
        WHERE tenant_id = %s AND resource_type = %s AND classification = %s
        LIMIT 10
    """
    plan = explain_query(query, ("00000000-0000-0000-0000-000000000000", "CONTRACT", "PUBLIC"))
    index_used = check_index_usage(plan, "classification")
    results.append(("Classification Filter", index_used, str(plan.get("Plan", {}))))

    return results


def test_observability_indexes(verbose: bool = False) -> list[tuple[str, bool, str]]:
    """Test observability indexes."""
    results = []

    # Test stale data query
    query = """
        SELECT id FROM data_observability_metrics
        WHERE tenant_id = %s AND is_stale = true
        ORDER BY recorded_at DESC
        LIMIT 10
    """
    plan = explain_query(query, ("00000000-0000-0000-0000-000000000000",))
    index_used = check_index_usage(plan, "is_stale")
    results.append(("Stale Data Query", index_used, str(plan.get("Plan", {}))))

    # Test pipeline execution query
    query = """
        SELECT id FROM pipeline_executions
        WHERE tenant_id = %s AND pipeline_type = %s AND status = %s
        ORDER BY created_at DESC
        LIMIT 10
    """
    plan = explain_query(
        query, ("00000000-0000-0000-0000-000000000000", "SCHEDULED_INGESTION", "COMPLETED")
    )
    index_used = check_index_usage(plan, "pipeline_type")
    results.append(("Pipeline Execution Query", index_used, str(plan.get("Plan", {}))))

    return results


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test database index performance")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    setup_django()

    print("=" * 80)
    print("Database Index Performance Test")
    print("=" * 80)
    print()

    all_results = []

    # Test contract indexes
    print("Testing Contract Indexes...")
    print("-" * 80)
    contract_results = test_contract_indexes(args.verbose)
    all_results.extend(contract_results)
    for name, used, plan in contract_results:
        status = "✓" if used else "✗"
        print(f"{status} {name}: {'Index used' if used else 'Index NOT used'}")
        if args.verbose:
            print(f"  Plan: {plan[:200]}...")
    print()

    # Test version history indexes
    print("Testing Version History Indexes...")
    print("-" * 80)
    version_results = test_version_history_indexes(args.verbose)
    all_results.extend(version_results)
    for name, used, plan in version_results:
        status = "✓" if used else "✗"
        print(f"{status} {name}: {'Index used' if used else 'Index NOT used'}")
        if args.verbose:
            print(f"  Plan: {plan[:200]}...")
    print()

    # Test search indexes
    print("Testing Search Indexes...")
    print("-" * 80)
    search_results = test_search_indexes(args.verbose)
    all_results.extend(search_results)
    for name, used, plan in search_results:
        status = "✓" if used else "✗"
        print(f"{status} {name}: {'Index used' if used else 'Index NOT used'}")
        if args.verbose:
            print(f"  Plan: {plan[:200]}...")
    print()

    # Test observability indexes
    print("Testing Observability Indexes...")
    print("-" * 80)
    observability_results = test_observability_indexes(args.verbose)
    all_results.extend(observability_results)
    for name, used, plan in observability_results:
        status = "✓" if used else "✗"
        print(f"{status} {name}: {'Index used' if used else 'Index NOT used'}")
        if args.verbose:
            print(f"  Plan: {plan[:200]}...")
    print()

    # Summary
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    total = len(all_results)
    passed = sum(1 for _, used, _ in all_results if used)
    failed = total - passed
    print(f"Total tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()

    if failed > 0:
        print("Failed tests:")
        for name, used, _ in all_results:
            if not used:
                print(f"  - {name}")
        sys.exit(1)
    else:
        print("All index tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
