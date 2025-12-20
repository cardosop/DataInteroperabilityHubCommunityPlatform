#!/usr/bin/env python3
"""
Performance Profiling Script for P1 Endpoints

This script profiles the performance of P1 endpoints to identify bottlenecks
and measure baseline performance before and after optimizations.

Usage:
    python scripts/performance/profile_p1_endpoints.py --endpoint marketplace
    python scripts/performance/profile_p1_endpoints.py --endpoint search
    python scripts/performance/profile_p1_endpoints.py --endpoint dq
    python scripts/performance/profile_p1_endpoints.py --all
"""
import os
import sys
import django
import time
import statistics
import argparse
from contextlib import contextmanager
from typing import Dict, List, Any
from django.db import connection, reset_queries
from django.test.utils import override_settings

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
django.setup()

from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.marketplace.models import Listing, ListingStatus
from hub.apps.search.models import SearchIndex
from hub.apps.dq.models import DQRun, DQRunStatus
from django.db import transaction


User = get_user_model()


@contextmanager
def query_tracking():
    """Context manager to track database queries"""
    reset_queries()
    start_queries = len(connection.queries)
    yield
    end_queries = len(connection.queries)
    queries_executed = end_queries - start_queries
    return queries_executed


def measure_time(func, *args, **kwargs):
    """Measure execution time of a function"""
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
    return result, execution_time


def profile_marketplace_listings(num_iterations: int = 100) -> Dict[str, Any]:
    """Profile marketplace listings endpoint"""
    print(f"\n{'='*60}")
    print("Profiling GET /api/v1/marketplace/listings/")
    print(f"{'='*60}\n")
    
    # Setup test data
    tenant = Tenant.objects.first()
    if not tenant:
        tenant = Tenant.objects.create(name="Test Tenant", key="test-tenant")
    
    user = User.objects.filter(tenant=tenant).first()
    if not user:
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=tenant
        )
    
    execution_times = []
    query_counts = []
    
    for i in range(num_iterations):
        with query_tracking() as queries:
            # Simulate the list endpoint logic
            queryset = Listing.objects.filter(tenant=tenant)
            # Apply select_related for tenant
            queryset = queryset.select_related('tenant', 'asset')
            listings = list(queryset[:20])  # Pagination
        
        query_counts.append(queries)
        
        # Measure total time
        _, exec_time = measure_time(
            lambda: list(Listing.objects.filter(tenant=tenant).select_related('tenant', 'asset')[:20])
        )
        execution_times.append(exec_time)
    
    return {
        "endpoint": "GET /api/v1/marketplace/listings/",
        "iterations": num_iterations,
        "execution_times": execution_times,
        "query_counts": query_counts,
        "p50": statistics.median(execution_times) if execution_times else 0,
        "p95": statistics.quantiles(execution_times, n=20)[18] if len(execution_times) >= 20 else max(execution_times) if execution_times else 0,
        "p99": statistics.quantiles(execution_times, n=100)[98] if len(execution_times) >= 100 else max(execution_times) if execution_times else 0,
        "avg_queries": statistics.mean(query_counts) if query_counts else 0,
        "max_queries": max(query_counts) if query_counts else 0,
    }


def profile_search_endpoint(num_iterations: int = 100) -> Dict[str, Any]:
    """Profile search endpoint"""
    print(f"\n{'='*60}")
    print("Profiling GET /api/v1/search/search/")
    print(f"{'='*60}\n")
    
    # Setup test data
    tenant = Tenant.objects.first()
    if not tenant:
        tenant = Tenant.objects.create(name="Test Tenant", key="test-tenant")
    
    execution_times = []
    query_counts = []
    
    for i in range(num_iterations):
        query = f"test query {i}"
        
        with query_tracking() as queries:
            # Simulate the search endpoint logic
            from hub.apps.search.search_engine import SearchEngine
            results, total = SearchEngine.search(
                tenant_id=str(tenant.id),
                query=query,
                limit=20,
                offset=0
            )
        
        query_counts.append(queries)
        
        # Measure total time
        _, exec_time = measure_time(
            lambda: SearchEngine.search(
                tenant_id=str(tenant.id),
                query=query,
                limit=20,
                offset=0
            )
        )
        execution_times.append(exec_time)
    
    return {
        "endpoint": "GET /api/v1/search/search/",
        "iterations": num_iterations,
        "execution_times": execution_times,
        "query_counts": query_counts,
        "p50": statistics.median(execution_times) if execution_times else 0,
        "p95": statistics.quantiles(execution_times, n=20)[18] if len(execution_times) >= 20 else max(execution_times) if execution_times else 0,
        "p99": statistics.quantiles(execution_times, n=100)[98] if len(execution_times) >= 100 else max(execution_times) if execution_times else 0,
        "avg_queries": statistics.mean(query_counts) if query_counts else 0,
        "max_queries": max(query_counts) if query_counts else 0,
    }


def profile_dq_results(num_iterations: int = 50) -> Dict[str, Any]:
    """Profile DQ run results endpoint"""
    print(f"\n{'='*60}")
    print("Profiling GET /api/v1/dq/dq-runs/{id}/results/")
    print(f"{'='*60}\n")
    
    # Setup test data
    tenant = Tenant.objects.first()
    if not tenant:
        tenant = Tenant.objects.create(name="Test Tenant", key="test-tenant")
    
    execution_times = []
    query_counts = []
    
    # Create test DQ runs
    dq_runs = []
    for i in range(min(num_iterations, 10)):  # Create fewer test runs
        dq_run = DQRun.objects.create(
            tenant=tenant,
            profile_key="intake_basic_gx",
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.0,
            checks_json=[
                {"name": "check1", "status": "PASS", "details": {}},
                {"name": "check2", "status": "PASS", "details": {}}
            ],
            details_json={"metadata": {"total_rows": 1000}}
        )
        dq_runs.append(dq_run)
    
    for dq_run in dq_runs:
        with query_tracking() as queries:
            # Simulate the results endpoint logic
            # Get DQ run with related objects
            dq_run = DQRun.objects.select_related('tenant', 'asset', 'dataset', 'job').get(id=dq_run.id)
            # Access results
            checks = dq_run.checks_json or []
            details = dq_run.details_json or {}
        
        query_counts.append(queries)
        
        # Measure total time
        _, exec_time = measure_time(
            lambda: DQRun.objects.select_related('tenant', 'asset', 'dataset', 'job').get(id=dq_run.id)
        )
        execution_times.append(exec_time)
    
    # Cleanup
    for dq_run in dq_runs:
        DQRun.objects.filter(id=dq_run.id).delete()
    
    return {
        "endpoint": "GET /api/v1/dq/dq-runs/{id}/results/",
        "iterations": len(dq_runs),
        "execution_times": execution_times,
        "query_counts": query_counts,
        "p50": statistics.median(execution_times) if execution_times else 0,
        "p95": statistics.quantiles(execution_times, n=20)[18] if len(execution_times) >= 20 else max(execution_times) if execution_times else 0,
        "p99": statistics.quantiles(execution_times, n=100)[98] if len(execution_times) >= 100 else max(execution_times) if execution_times else 0,
        "avg_queries": statistics.mean(query_counts) if query_counts else 0,
        "max_queries": max(query_counts) if query_counts else 0,
    }


def print_results(results: Dict[str, Any]):
    """Print profiling results"""
    print(f"\nResults for {results['endpoint']}")
    print(f"Iterations: {results['iterations']}")
    print(f"\nExecution Time (ms):")
    print(f"  P50: {results['p50']:.2f}ms")
    print(f"  P95: {results['p95']:.2f}ms")
    print(f"  P99: {results['p99']:.2f}ms")
    print(f"  Min: {min(results['execution_times']):.2f}ms")
    print(f"  Max: {max(results['execution_times']):.2f}ms")
    print(f"\nDatabase Queries:")
    print(f"  Average: {results['avg_queries']:.2f}")
    print(f"  Max: {results['max_queries']}")
    print(f"\nTarget Performance:")
    if "marketplace" in results['endpoint'].lower():
        print(f"  Target P95: < 500ms")
        print(f"  Current P95: {results['p95']:.2f}ms")
        print(f"  Status: {'✅ PASS' if results['p95'] < 500 else '❌ FAIL'}")
    elif "search" in results['endpoint'].lower():
        print(f"  Target P95: < 200ms")
        print(f"  Current P95: {results['p95']:.2f}ms")
        print(f"  Status: {'✅ PASS' if results['p95'] < 200 else '❌ FAIL'}")
    else:
        print(f"  Target P95: < 500ms")
        print(f"  Current P95: {results['p95']:.2f}ms")
        print(f"  Status: {'✅ PASS' if results['p95'] < 500 else '❌ FAIL'}")


def main():
    parser = argparse.ArgumentParser(description="Profile P1 endpoints performance")
    parser.add_argument(
        "--endpoint",
        choices=["marketplace", "search", "dq"],
        help="Endpoint to profile"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Profile all endpoints"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of iterations (default: 100)"
    )
    
    args = parser.parse_args()
    
    if args.all:
        results_marketplace = profile_marketplace_listings(args.iterations)
        print_results(results_marketplace)
        
        results_search = profile_search_endpoint(args.iterations)
        print_results(results_search)
        
        results_dq = profile_dq_results(args.iterations // 2)
        print_results(results_dq)
    elif args.endpoint == "marketplace":
        results = profile_marketplace_listings(args.iterations)
        print_results(results)
    elif args.endpoint == "search":
        results = profile_search_endpoint(args.iterations)
        print_results(results)
    elif args.endpoint == "dq":
        results = profile_dq_results(args.iterations)
        print_results(results)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

