#!/usr/bin/env python3
"""
Performance Profiling Script for Asset Endpoints

This script profiles the performance of asset endpoints to identify bottlenecks
and measure baseline performance before and after optimizations.

Usage:
    python scripts/performance/profile_asset_endpoints.py --endpoint create
    python scripts/performance/profile_asset_endpoints.py --endpoint activate
    python scripts/performance/profile_asset_endpoints.py --all
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
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, ValidationStatus, NormalizationStatus
from hub.apps.datasets.models import Dataset
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


def profile_asset_create(num_iterations: int = 100) -> Dict[str, Any]:
    """Profile asset creation endpoint"""
    print(f"\n{'='*60}")
    print("Profiling POST /api/v1/assets/")
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
        key = f"test-asset-{i}-{int(time.time())}"
        
        with query_tracking() as queries:
            with transaction.atomic():
                # Simulate the create endpoint logic
                if Asset.objects.filter(tenant=tenant, key=key).exists():
                    continue
                
                asset = Asset.objects.create(
                    tenant=tenant,
                    key=key,
                    name=f"Test Asset {i}",
                    description="Test description",
                    domain="test",
                    status=AssetStatus.DRAFT,
                    visibility="INTERNAL",
                    created_by=user
                )
                
                # Simulate audit event (simplified)
                # create_audit_event(...)
        
        query_counts.append(queries)
        
        # Measure total time
        _, exec_time = measure_time(
            lambda: Asset.objects.create(
                tenant=tenant,
                key=f"{key}-timed",
                name=f"Test Asset {i} Timed",
                status=AssetStatus.DRAFT,
                created_by=user
            )
        )
        execution_times.append(exec_time)
        
        # Cleanup
        Asset.objects.filter(tenant=tenant, key__startswith=f"test-asset-{i}").delete()
    
    return {
        "endpoint": "POST /api/v1/assets/",
        "iterations": num_iterations,
        "execution_times": execution_times,
        "query_counts": query_counts,
        "p50": statistics.median(execution_times) if execution_times else 0,
        "p95": statistics.quantiles(execution_times, n=20)[18] if len(execution_times) >= 20 else max(execution_times) if execution_times else 0,
        "p99": statistics.quantiles(execution_times, n=100)[98] if len(execution_times) >= 100 else max(execution_times) if execution_times else 0,
        "avg_queries": statistics.mean(query_counts) if query_counts else 0,
        "max_queries": max(query_counts) if query_counts else 0,
    }


def profile_asset_activate(num_iterations: int = 50) -> Dict[str, Any]:
    """Profile asset activation endpoint"""
    print(f"\n{'='*60}")
    print("Profiling POST /api/v1/assets/{id}/activate/")
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
        # Create asset with contract
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"activate-test-{i}-{int(time.time())}",
            name=f"Activate Test Asset {i}",
            status=AssetStatus.DRAFT,
            created_by=user
        )
        
        # Create contract
        contract = Contract.objects.create(
            tenant=tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
            original_format="JSON",
            original_raw='{"id": "test"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1},
            created_by=user
        )
        
        # Refresh asset to get latest version
        asset.refresh_from_db()
        
        with query_tracking() as queries:
            with transaction.atomic():
                # Simulate the activate endpoint logic
                # Check optimistic locking
                version = asset.version
                
                # Check if already active
                if asset.status == AssetStatus.ACTIVE:
                    continue
                
                # Check activation requirements (can_activate)
                # This performs queries: contracts.filter(), datasets.first()
                can_activate, blockers = asset.can_activate()
                
                if can_activate:
                    # Activate asset
                    asset.status = AssetStatus.ACTIVE
                    asset.full_clean()
                    asset.increment_version()
                    asset.save(update_fields=['status', 'updated_at'])
        
        query_counts.append(queries)
        
        # Measure total time
        asset.refresh_from_db()
        _, exec_time = measure_time(
            lambda: asset.can_activate()
        )
        execution_times.append(exec_time)
        
        # Cleanup
        Asset.objects.filter(id=asset.id).delete()
        Contract.objects.filter(id=contract.id).delete()
    
    return {
        "endpoint": "POST /api/v1/assets/{id}/activate/",
        "iterations": num_iterations,
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
    if "create" in results['endpoint'].lower():
        print(f"  Target P95: < 1000ms")
        print(f"  Current P95: {results['p95']:.2f}ms")
        print(f"  Status: {'✅ PASS' if results['p95'] < 1000 else '❌ FAIL'}")
    else:
        print(f"  Target P95: < 2000ms")
        print(f"  Current P95: {results['p95']:.2f}ms")
        print(f"  Status: {'✅ PASS' if results['p95'] < 2000 else '❌ FAIL'}")


def main():
    parser = argparse.ArgumentParser(description="Profile asset endpoints performance")
    parser.add_argument(
        "--endpoint",
        choices=["create", "activate"],
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
        results_create = profile_asset_create(args.iterations)
        print_results(results_create)
        
        results_activate = profile_asset_activate(args.iterations // 2)  # Fewer iterations for activate
        print_results(results_activate)
    elif args.endpoint == "create":
        results = profile_asset_create(args.iterations)
        print_results(results)
    elif args.endpoint == "activate":
        results = profile_asset_activate(args.iterations)
        print_results(results)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

