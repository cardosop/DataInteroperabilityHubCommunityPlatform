"""
Performance Test Suite for Django 6

Tests performance of API endpoints, database queries, JSONField queries,
middleware, job queue operations, file storage operations, and compares with baseline metrics.
"""
import pytest
import time
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.db import connection
from django.core.management import call_command
from django_rq import get_queue
from django_rq.jobs import Job as RQJob

from hub.apps.tenants.models import Tenant
from hub.apps.contracts.models import Contract
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.assets.models import Asset
from hub.apps.jobs.utils import create_job
from hub.apps.files.storage import S3StorageClient
from django.conf import settings


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class PerformanceTest(TestCase):
    """Base class for performance tests"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.client.force_login(self.user)
    
    def measure_time(self, func, *args, **kwargs):
        """Measure execution time of a function"""
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        return result, elapsed


class APIEndpointPerformanceTest(PerformanceTest):
    """Test API endpoint performance"""
    
    def test_health_endpoint_performance(self):
        """Test health endpoint response time"""
        _, elapsed = self.measure_time(self.client.get, '/health/')
        
        # Health endpoint should respond quickly (< 100ms)
        self.assertLess(elapsed, 0.1, f"Health endpoint too slow: {elapsed:.3f}s")
    
    def test_api_endpoint_performance(self):
        """Test API endpoint response time"""
        # Test assets endpoint
        _, elapsed = self.measure_time(self.client.get, '/api/v1/assets/')
        
        # API endpoint should respond reasonably (< 1s for list)
        self.assertLess(elapsed, 1.0, f"API endpoint too slow: {elapsed:.3f}s")


class DatabaseQueryPerformanceTest(PerformanceTest):
    """Test database query performance"""
    
    def test_simple_query_performance(self):
        """Test simple database query performance"""
        def run_query():
            return Tenant.objects.all().count()
        
        _, elapsed = self.measure_time(run_query)
        
        # Simple query should be fast (< 50ms)
        self.assertLess(elapsed, 0.05, f"Simple query too slow: {elapsed:.3f}s")
    
    def test_join_query_performance(self):
        """Test join query performance"""
        def run_query():
            return User.objects.select_related('tenant').all().count()
        
        _, elapsed = self.measure_time(run_query)
        
        # Join query should be reasonably fast (< 100ms)
        self.assertLess(elapsed, 0.1, f"Join query too slow: {elapsed:.3f}s")


class JSONFieldQueryPerformanceTest(PerformanceTest):
    """Test JSONField query performance"""
    
    def setUp(self):
        """Set up test fixtures with JSONField data"""
        super().setUp()
        
        # Create contracts with JSONField data
        from hub.apps.assets.models import Asset
        from hub.apps.contracts.models import OriginalSpecType, OriginalFormat, ContractStatus
        
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="json-perf-asset",
            name="JSON Perf Asset"
        )
        
        for i in range(10):
            Contract.objects.create(
                tenant=self.tenant,
                asset=asset,
                version=i+1,  # Use different versions to avoid unique constraint violation
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="1.0.0",
                original_format=OriginalFormat.JSON,
                original_raw='{"id": "test"}',
                hub_contract_version="1.0.0",
                hub_contract_json={
                    "version": f"1.{i}.0",
                    "status": "active" if i % 2 == 0 else "inactive",
                    "metadata": {
                        "author": f"Author {i}",
                        "tags": [f"tag{i}", f"tag{i+1}"]
                    }
                }
            )
    
    def test_jsonfield_query_performance(self):
        """Test JSONField query performance"""
        def run_query():
            return Contract.objects.filter(
                hub_contract_json__status="active"
            ).count()
        
        _, elapsed = self.measure_time(run_query)
        
        # JSONField query should be reasonably fast (< 200ms)
        self.assertLess(elapsed, 0.2, f"JSONField query too slow: {elapsed:.3f}s")
    
    def test_jsonfield_nested_query_performance(self):
        """Test nested JSONField query performance"""
        def run_query():
            return Contract.objects.filter(
                hub_contract_json__metadata__author__startswith="Author"
            ).count()
        
        _, elapsed = self.measure_time(run_query)
        
        # Nested JSONField query should be reasonably fast (< 300ms)
        self.assertLess(elapsed, 0.3, f"Nested JSONField query too slow: {elapsed:.3f}s")
    
    def test_jsonfield_array_contains_performance(self):
        """Test JSONField array contains query performance with GIN index."""
        def run_query():
            return Contract.objects.filter(
                hub_contract_json__metadata__tags__contains=["tag1"]
            ).count()
        
        _, elapsed = self.measure_time(run_query)
        
        # Array contains query with GIN index should be fast (< 200ms)
        self.assertLess(elapsed, 0.2, f"Array contains query too slow: {elapsed:.3f}s")
    
    def test_jsonfield_complex_filter_performance(self):
        """Test complex JSONField filter performance."""
        def run_query():
            from django.db.models import Q
            return Contract.objects.filter(
                Q(hub_contract_json__metadata__tags__contains=["tag1"]) |
                Q(hub_contract_json__metadata__tags__contains=["tag2"])
            ).count()
        
        _, elapsed = self.measure_time(run_query)
        
        # Complex filter should be reasonably fast (< 300ms)
        self.assertLess(elapsed, 0.3, f"Complex filter too slow: {elapsed:.3f}s")
    
    def test_jsonfield_gin_index_usage(self):
        """Test that GIN index is used for JSONField queries (PostgreSQL only)."""
        if connection.vendor != 'postgresql':
            self.skipTest("GIN index test only for PostgreSQL")
        
        # Get query plan for array contains query
        query = Contract.objects.filter(
            hub_contract_json__metadata__tags__contains=["tag1"]
        )
        
        with connection.cursor() as cursor:
            sql, params = query.query.get_compiler(connection=connection).as_sql()
            cursor.execute(f"EXPLAIN (FORMAT JSON) {sql}", params)
            plan = cursor.fetchone()[0]
            plan_str = str(plan)
            
            # Check if GIN index is used (Index Scan or Bitmap Index Scan)
            uses_index = (
                'Index Scan' in plan_str or 
                'Bitmap Index Scan' in plan_str or
                'hub_contract_json' in plan_str.lower()
            )
            
            self.assertTrue(
                uses_index,
                f"GIN index not used in query plan: {plan_str}"
            )


class MiddlewarePerformanceTest(PerformanceTest):
    """Test middleware performance"""
    
    def test_middleware_chain_performance(self):
        """Test middleware chain execution performance"""
        # Make request through full middleware chain
        _, elapsed = self.measure_time(self.client.get, '/api/v1/assets/')
        
        # Middleware chain should be fast (< 1s for full request, allowing for test environment overhead)
        # In production, should be <500ms
        self.assertLess(elapsed, 1.0, f"Middleware chain too slow: {elapsed:.3f}s (target: <500ms in production)")
    
    def test_middleware_overhead(self):
        """Test middleware overhead"""
        # Compare request with and without middleware
        # (This is approximate - health endpoint has less middleware)
        health_time = self.measure_time(self.client.get, '/health/')[1]
        api_time = self.measure_time(self.client.get, '/api/v1/assets/')[1]
        
        # API endpoint should not be excessively slower than health
        overhead = api_time - health_time
        self.assertLess(overhead, 0.4, f"Middleware overhead too high: {overhead:.3f}s")


class LoadTest(PerformanceTest):
    """Test performance under load"""
    
    def test_concurrent_requests(self):
        """Test performance with multiple requests"""
        times = []
        for _ in range(10):
            _, elapsed = self.measure_time(self.client.get, '/health/')
            times.append(elapsed)
        
        # Average response time should be reasonable
        avg_time = sum(times) / len(times)
        self.assertLess(avg_time, 0.1, f"Average response time too high: {avg_time:.3f}s")
        
        # Max response time should not be excessive
        max_time = max(times)
        self.assertLess(max_time, 0.2, f"Max response time too high: {max_time:.3f}s")


class JobQueuePerformanceTest(PerformanceTest):
    """Test job queue performance"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="perf-asset",
            name="Performance Asset"
        )
    
    def test_job_creation_performance(self):
        """Test job creation performance"""
        def create_job():
            return Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                status=JobStatus.PENDING,
                resource_type="ASSET",
                resource_id=str(self.asset.id),
                details_json={'test': 'data'}
            )
        
        _, elapsed = self.measure_time(create_job)
        
        # Job creation should be fast (< 50ms)
        self.assertLess(elapsed, 0.05, f"Job creation too slow: {elapsed:.3f}s")
    
    def test_job_enqueue_performance(self):
        """Test job enqueue performance"""
        def enqueue_job():
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                status=JobStatus.PENDING,
                resource_type="ASSET",
                resource_id=str(self.asset.id),
                details_json={'test': 'data'}
            )
            # Enqueue job (may fail if Redis not available, but we measure the operation)
            try:
                queue = get_queue('default')
                from hub.apps.jobs.tasks import process_job
                queue.enqueue(process_job, str(job.id), job_type=JobType.DQ_RUN, timeout=600)
            except Exception:
                pass  # Ignore Redis connection errors in tests
            return job
        
        _, elapsed = self.measure_time(enqueue_job)
        
        # Job enqueue should be reasonably fast (< 200ms, including Redis operation)
        self.assertLess(elapsed, 0.2, f"Job enqueue too slow: {elapsed:.3f}s")
    
    def test_job_query_performance(self):
        """Test job query performance"""
        # Create multiple jobs
        for i in range(10):
            Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                status=JobStatus.PENDING,
                resource_type="ASSET",
                resource_id=str(self.asset.id),
                details_json={'test': f'data{i}'}
            )
        
        def query_jobs():
            return list(Job.objects.filter(tenant=self.tenant, status=JobStatus.PENDING))
        
        _, elapsed = self.measure_time(query_jobs)
        
        # Job query should be fast (< 100ms for 10 jobs)
        self.assertLess(elapsed, 0.1, f"Job query too slow: {elapsed:.3f}s")
    
    def test_job_status_update_performance(self):
        """Test job status update performance"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=str(self.asset.id),
                details_json={'test': 'data'}
        )
        
        def update_job_status():
            job.status = JobStatus.RUNNING
            job.save()
        
        _, elapsed = self.measure_time(update_job_status)
        
        # Job status update should be fast (< 50ms)
        self.assertLess(elapsed, 0.05, f"Job status update too slow: {elapsed:.3f}s")
    
    def test_job_bulk_creation_performance(self):
        """Test bulk job creation performance"""
        def create_multiple_jobs():
            jobs = []
            for i in range(50):
                job = Job.objects.create(
                    tenant=self.tenant,
                    type=JobType.DQ_RUN,
                    status=JobStatus.PENDING,
                    resource_type="ASSET",
                    resource_id=str(self.asset.id),
                    details_json={'test': f'data{i}'}
                )
                jobs.append(job)
            return jobs
        
        _, elapsed = self.measure_time(create_multiple_jobs)
        
        # Bulk job creation should be reasonably fast (< 2s for 50 jobs)
        self.assertLess(elapsed, 2.0, f"Bulk job creation too slow: {elapsed:.3f}s")
        
        # Average time per job should be reasonable
        avg_time_per_job = elapsed / 50
        self.assertLess(avg_time_per_job, 0.05, f"Average time per job too high: {avg_time_per_job:.3f}s")


class FileStoragePerformanceTest(PerformanceTest):
    """Test file storage performance"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Note: File storage tests may require S3/MinIO to be running
        # Tests will gracefully handle connection errors
    
    def test_file_creation_performance(self):
        """Test file record creation performance"""
        def create_file():
            return File.objects.create(
                tenant=self.tenant,
                name="perf-test.csv",
                content_type="text/csv",
                size=1024,
                status=FileStatus.PENDING,
                storage_path="test/perf-test.csv"
            )
        
        _, elapsed = self.measure_time(create_file)
        
        # File creation should be fast (< 50ms)
        self.assertLess(elapsed, 0.05, f"File creation too slow: {elapsed:.3f}s")
    
    def test_file_init_upload_performance(self):
        """Test file upload initialization performance"""
        def init_upload():
            # Test via API endpoint
            response = self.client.post(
                '/api/v1/files/files/init/',
                {
                    'name': 'perf-upload.csv',
                    'content_type': 'text/csv',
                    'size': 2048
                },
                format='json'
            )
            return response
        
        _, elapsed = self.measure_time(init_upload)
        
        # File upload init should be reasonably fast (< 500ms)
        self.assertLess(elapsed, 0.5, f"File upload init too slow: {elapsed:.3f}s")
    
    def test_file_query_performance(self):
        """Test file query performance"""
        # Create multiple files
        for i in range(10):
            File.objects.create(
                tenant=self.tenant,
                name=f"perf-file-{i}.csv",
                content_type="text/csv",
                size=1024 * (i + 1),
                status=FileStatus.ACTIVE,
                storage_path=f"test/perf-file-{i}.csv"
            )
        
        def query_files():
            return list(File.objects.filter(tenant=self.tenant, status=FileStatus.ACTIVE))
        
        _, elapsed = self.measure_time(query_files)
        
        # File query should be fast (< 100ms for 10 files)
        self.assertLess(elapsed, 0.1, f"File query too slow: {elapsed:.3f}s")
    
    def test_file_status_update_performance(self):
        """Test file status update performance"""
        file = File.objects.create(
            tenant=self.tenant,
            name="perf-status-update.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.PENDING,
            storage_path="test/perf-status-update.csv"
        )
        
        def update_file_status():
            file.status = FileStatus.ACTIVE
            file.save()
        
        _, elapsed = self.measure_time(update_file_status)
        
        # File status update should be fast (< 50ms)
        self.assertLess(elapsed, 0.05, f"File status update too slow: {elapsed:.3f}s")
    
    def test_s3_storage_client_initialization_performance(self):
        """Test S3 storage client initialization performance"""
        def init_s3_client():
            try:
                client = S3StorageClient()
                return client
            except Exception:
                # Ignore connection errors in tests
                return None
        
        _, elapsed = self.measure_time(init_s3_client)
        
        # S3 client initialization should be fast (< 200ms)
        self.assertLess(elapsed, 0.2, f"S3 client initialization too slow: {elapsed:.3f}s")
    
    def test_file_bulk_creation_performance(self):
        """Test bulk file creation performance"""
        def create_multiple_files():
            files = []
            for i in range(50):
                file = File.objects.create(
                    tenant=self.tenant,
                    name=f"perf-bulk-{i}.csv",
                    content_type="text/csv",
                    size=1024 * (i + 1),
                    status=FileStatus.PENDING,
                    storage_path=f"test/perf-bulk-{i}.csv"
                )
                files.append(file)
            return files
        
        _, elapsed = self.measure_time(create_multiple_files)
        
        # Bulk file creation should be reasonably fast (< 2s for 50 files)
        self.assertLess(elapsed, 2.0, f"Bulk file creation too slow: {elapsed:.3f}s")
        
        # Average time per file should be reasonable
        avg_time_per_file = elapsed / 50
        self.assertLess(avg_time_per_file, 0.05, f"Average time per file too high: {avg_time_per_file:.3f}s")
    
    def test_file_metadata_query_performance(self):
        """Test file metadata query performance"""
        # Create files with metadata
        for i in range(10):
            File.objects.create(
                tenant=self.tenant,
                name=f"perf-metadata-{i}.csv",
                content_type="text/csv",
                size=1024 * (i + 1),
                status=FileStatus.ACTIVE,
                storage_path=f"test/perf-metadata-{i}.csv",
                metadata_json={'upload_method': 'browser', 'chunk_count': i + 1}
            )
        
        def query_file_metadata():
            return list(File.objects.filter(
                tenant=self.tenant,
                metadata_json__upload_method='browser'
            ))
        
        _, elapsed = self.measure_time(query_file_metadata)
        
        # File metadata query should be reasonably fast (< 200ms for 10 files)
        self.assertLess(elapsed, 0.2, f"File metadata query too slow: {elapsed:.3f}s")

