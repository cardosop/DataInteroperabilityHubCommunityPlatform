"""
Performance Tests for Asset Endpoints

Tests performance requirements for asset endpoints:
- POST /api/v1/assets/ - Target: < 1000ms p95
- POST /api/v1/assets/{id}/activate/ - Target: < 2000ms p95

These tests use real services and infrastructure (no mocks).
"""
import time
import statistics
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, ValidationStatus, NormalizationStatus

User = get_user_model()


class AssetPerformanceTest(TestCase):
    """Performance tests for asset endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Test Tenant", key="test-tenant")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.client.force_authenticate(user=self.user)
    
    def measure_endpoint_performance(self, method, url, data=None, iterations=50):
        """Measure endpoint performance"""
        execution_times = []
        query_counts = []
        
        for i in range(iterations):
            reset_queries()
            start_queries = len(connection.queries)
            
            start_time = time.perf_counter()
            
            if method == 'POST':
                response = self.client.post(url, data, format='json')
            elif method == 'GET':
                response = self.client.get(url, format='json')
            elif method == 'PATCH':
                response = self.client.patch(url, data, format='json')
            elif method == 'DELETE':
                response = self.client.delete(url, format='json')
            
            end_time = time.perf_counter()
            
            execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
            execution_times.append(execution_time)
            
            end_queries = len(connection.queries)
            query_count = end_queries - start_queries
            query_counts.append(query_count)
        
        return {
            'execution_times': execution_times,
            'query_counts': query_counts,
            'p50': statistics.median(execution_times) if execution_times else 0,
            'p95': statistics.quantiles(execution_times, n=20)[18] if len(execution_times) >= 20 else max(execution_times) if execution_times else 0,
            'p99': statistics.quantiles(execution_times, n=100)[98] if len(execution_times) >= 100 else max(execution_times) if execution_times else 0,
            'avg_queries': statistics.mean(query_counts) if query_counts else 0,
            'max_queries': max(query_counts) if query_counts else 0,
        }
    
    def test_create_asset_performance(self):
        """Test POST /api/v1/assets/ performance - Target: < 1000ms p95"""
        results = self.measure_endpoint_performance(
            method='POST',
            url='/api/v1/assets/assets/',
            data={
                'key': f'test-asset-{int(time.time())}',
                'name': 'Test Asset',
                'description': 'Test description',
                'domain': 'test',
                'visibility': 'INTERNAL'
            },
            iterations=50
        )
        
        # Cleanup
        Asset.objects.filter(tenant=self.tenant, key__startswith='test-asset-').delete()
        
        # Assert performance targets
        self.assertLess(
            results['p95'],
            1000,
            f"P95 response time ({results['p95']:.2f}ms) exceeds target (1000ms)"
        )
        
        # Log results
        print(f"\n{'='*60}")
        print("POST /api/v1/assets/ Performance Results")
        print(f"{'='*60}")
        print(f"P50: {results['p50']:.2f}ms")
        print(f"P95: {results['p95']:.2f}ms (Target: < 1000ms)")
        print(f"P99: {results['p99']:.2f}ms")
        print(f"Average Queries: {results['avg_queries']:.2f}")
        print(f"Max Queries: {results['max_queries']}")
        print(f"{'='*60}\n")
    
    def test_activate_asset_performance(self):
        """Test POST /api/v1/assets/{id}/activate/ performance - Target: < 2000ms p95"""
        # Create asset with contract for activation
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f'activate-test-{int(time.time())}',
            name='Activate Test Asset',
            status=AssetStatus.DRAFT,
            created_by=self.user
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type='ODCS',
            original_spec_version='3.0.0',
            original_format='JSON',
            original_raw='{"id": "test"}',
            hub_contract_version='1.0.0',
            hub_contract_json={'hub_contract_version': 1},
            created_by=self.user
        )
        
        results = self.measure_endpoint_performance(
            method='POST',
            url=f'/api/v1/assets/assets/{asset.id}/activate/',
            data={'version': asset.version},
            iterations=30  # Fewer iterations for activate (more complex)
        )
        
        # Cleanup
        Contract.objects.filter(id=contract.id).delete()
        Asset.objects.filter(id=asset.id).delete()
        
        # Assert performance targets
        self.assertLess(
            results['p95'],
            2000,
            f"P95 response time ({results['p95']:.2f}ms) exceeds target (2000ms)"
        )
        
        # Log results
        print(f"\n{'='*60}")
        print("POST /api/v1/assets/{id}/activate/ Performance Results")
        print(f"{'='*60}")
        print(f"P50: {results['p50']:.2f}ms")
        print(f"P95: {results['p95']:.2f}ms (Target: < 2000ms)")
        print(f"P99: {results['p99']:.2f}ms")
        print(f"Average Queries: {results['avg_queries']:.2f}")
        print(f"Max Queries: {results['max_queries']}")
        print(f"{'='*60}\n")
    
    def test_create_asset_query_count(self):
        """Test that asset creation uses minimal database queries"""
        reset_queries()
        start_queries = len(connection.queries)
        
        response = self.client.post(
            '/api/v1/assets/assets/',
            {
                'key': f'test-asset-query-{int(time.time())}',
                'name': 'Test Asset',
                'description': 'Test description',
                'domain': 'test',
                'visibility': 'INTERNAL'
            },
            format='json'
        )
        
        end_queries = len(connection.queries)
        query_count = end_queries - start_queries
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Asset creation should use minimal queries:
        # 1. Check duplicate key (exists query)
        # 2. Get/create tenant (if cached, 0 queries)
        # 3. Create asset (1 query)
        # 4. Create audit event (1 query, but may be async)
        # Target: < 5 queries
        self.assertLess(
            query_count,
            5,
            f"Asset creation uses too many queries: {query_count} (target: < 5)"
        )
        
        # Cleanup
        if 'id' in response.data:
            Asset.objects.filter(id=response.data['id']).delete()
    
    def test_activate_asset_query_count(self):
        """Test that asset activation uses optimized queries with prefetch_related"""
        # Create asset with contract
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f'activate-query-test-{int(time.time())}',
            name='Activate Query Test Asset',
            status=AssetStatus.DRAFT,
            created_by=self.user
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type='ODCS',
            original_spec_version='3.0.0',
            original_format='JSON',
            original_raw='{"id": "test"}',
            hub_contract_version='1.0.0',
            hub_contract_json={'hub_contract_version': 1},
            created_by=self.user
        )
        
        reset_queries()
        start_queries = len(connection.queries)
        
        asset.refresh_from_db()
        response = self.client.post(
            f'/api/v1/assets/assets/{asset.id}/activate/',
            {'version': asset.version},
            format='json'
        )
        
        end_queries = len(connection.queries)
        query_count = end_queries - start_queries
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Asset activation should use optimized queries with prefetch_related:
        # 1. Get asset with prefetch_related (1-2 queries)
        # 2. Check can_activate (uses prefetched data, 0 queries)
        # 3. Save asset (1 query)
        # 4. Semantic mapping (may be async, 0-1 queries)
        # 5. Audit event (may be async, 0-1 queries)
        # Target: < 5 queries
        self.assertLess(
            query_count,
            5,
            f"Asset activation uses too many queries: {query_count} (target: < 5)"
        )
        
        # Cleanup
        Contract.objects.filter(id=contract.id).delete()
        Asset.objects.filter(id=asset.id).delete()
    
    def test_create_asset_concurrent_performance(self):
        """Test asset creation performance under concurrent load"""
        import threading
        
        results = []
        errors = []
        
        def create_asset(thread_id):
            try:
                start_time = time.perf_counter()
                response = self.client.post(
                    '/api/v1/assets/assets/',
                    {
                        'key': f'concurrent-test-{thread_id}-{int(time.time())}',
                        'name': f'Concurrent Test Asset {thread_id}',
                        'description': 'Test description',
                        'domain': 'test',
                        'visibility': 'INTERNAL'
                    },
                    format='json'
                )
                end_time = time.perf_counter()
                
                if response.status_code == status.HTTP_201_CREATED:
                    results.append((end_time - start_time) * 1000)
                    # Cleanup
                    if 'id' in response.data:
                        Asset.objects.filter(id=response.data['id']).delete()
                else:
                    errors.append(response.status_code)
            except Exception as e:
                errors.append(str(e))
        
        # Create 10 concurrent requests
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_asset, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        if results:
            p95 = statistics.quantiles(results, n=20)[18] if len(results) >= 20 else max(results)
            
            self.assertLess(
                p95,
                1000,
                f"P95 response time under concurrent load ({p95:.2f}ms) exceeds target (1000ms)"
            )
            
            print(f"\nConcurrent Load Test Results:")
            print(f"Successful requests: {len(results)}")
            print(f"Errors: {len(errors)}")
            print(f"P95: {p95:.2f}ms")
            if errors:
                print(f"Errors: {errors}")

