"""
Performance Baseline Tests for Django 6

These tests establish performance baselines for critical operations and
compare them against expected thresholds. These baselines can be used
to detect performance regressions.

All tests use real services (no mocks/stubs) and follow TDD principles.
"""
import pytest

pytestmark = pytest.mark.slow
import time
import statistics
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.db import connection
from django.core.management import call_command

from hub.apps.tenants.models import Tenant
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.assets.models import Asset
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.datasets.models import Dataset
import uuid


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class PerformanceBaselineTest(TestCase):
    """Base class for performance baseline tests."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}")
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.client.force_login(self.user)
    
    def measure_time(self, func, *args, **kwargs):
        """Measure execution time of a function."""
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        return result, elapsed
    
    def measure_multiple(self, func, iterations=10, *args, **kwargs):
        """Measure execution time multiple times and return statistics."""
        times = []
        for _ in range(iterations):
            _, elapsed = self.measure_time(func, *args, **kwargs)
            times.append(elapsed)
        
        return {
            'min': min(times),
            'max': max(times),
            'mean': statistics.mean(times),
            'median': statistics.median(times),
            'stdev': statistics.stdev(times) if len(times) > 1 else 0,
            'times': times
        }


class DatabaseQueryBaselineTest(PerformanceBaselineTest):
    """Baseline tests for database queries."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        
        # Create test data
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="baseline-asset",
            name="Baseline Asset"
        )
        
        # Create multiple contracts for testing
        for i in range(50):
            Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                version=i+1,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="1.0.0",
                original_format=OriginalFormat.JSON,
                original_raw='{}',
                hub_contract_version="1.0.0",
                hub_contract_json={
                    "info": {
                        "title": f"Contract {i}",
                        "tags": [f"tag{i % 10}", f"tag{(i+1) % 10}"]
                    },
                    "quality": {
                        "default_profile_key": "great_expectations" if i % 2 == 0 else "soda"
                    },
                    "privacy_compliance": {
                        "jurisdictions": ["GDPR"] if i % 3 == 0 else ["CCPA"],
                        "contains_personal_data": i % 2 == 0
                    }
                },
                created_by=self.user
            )
    
    def test_simple_query_baseline(self):
        """Establish baseline for simple queries."""
        stats = self.measure_multiple(
            lambda: Contract.objects.filter(tenant=self.tenant).count(),
            iterations=20
        )
        
        # Simple query should be very fast
        self.assertLess(stats['mean'], 0.05, f"Simple query too slow: {stats['mean']:.3f}s")
        self.assertLess(stats['max'], 0.1, f"Simple query max time too high: {stats['max']:.3f}s")
    
    def test_jsonfield_query_baseline(self):
        """Establish baseline for JSONField queries."""
        stats = self.measure_multiple(
            lambda: Contract.objects.filter(
                hub_contract_json__info__tags__contains=["tag1"]
            ).count(),
            iterations=20
        )
        
        # JSONField query with GIN index should be fast
        self.assertLess(stats['mean'], 0.1, f"JSONField query too slow: {stats['mean']:.3f}s")
        self.assertLess(stats['max'], 0.2, f"JSONField query max time too high: {stats['max']:.3f}s")
    
    def test_jsonfield_nested_query_baseline(self):
        """Establish baseline for nested JSONField queries."""
        stats = self.measure_multiple(
            lambda: Contract.objects.filter(
                hub_contract_json__quality__default_profile_key="great_expectations"
            ).count(),
            iterations=20
        )
        
        # Nested JSONField query should be reasonably fast
        self.assertLess(stats['mean'], 0.15, f"Nested JSONField query too slow: {stats['mean']:.3f}s")
        self.assertLess(stats['max'], 0.3, f"Nested JSONField query max time too high: {stats['max']:.3f}s")
    
    def test_complex_query_baseline(self):
        """Establish baseline for complex queries with multiple filters."""
        from django.db.models import Q
        
        stats = self.measure_multiple(
            lambda: Contract.objects.filter(
                Q(hub_contract_json__info__tags__contains=["tag1"]) |
                Q(hub_contract_json__quality__default_profile_key="great_expectations")
            ).count(),
            iterations=20
        )
        
        # Complex query should be reasonably fast
        self.assertLess(stats['mean'], 0.2, f"Complex query too slow: {stats['mean']:.3f}s")
        self.assertLess(stats['max'], 0.4, f"Complex query max time too high: {stats['max']:.3f}s")
    
    def test_join_query_baseline(self):
        """Establish baseline for join queries."""
        stats = self.measure_multiple(
            lambda: list(Contract.objects.select_related('asset', 'tenant').filter(tenant=self.tenant)[:10]),
            iterations=20
        )
        
        # Join query should be reasonably fast
        self.assertLess(stats['mean'], 0.1, f"Join query too slow: {stats['mean']:.3f}s")
        self.assertLess(stats['max'], 0.2, f"Join query max time too high: {stats['max']:.3f}s")


class APIEndpointBaselineTest(PerformanceBaselineTest):
    """Baseline tests for API endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        
        # Create test data
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="baseline-asset",
            name="Baseline Asset"
        )
        
        for i in range(20):
            Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                version=i+1,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="1.0.0",
                original_format=OriginalFormat.JSON,
                original_raw='{}',
                hub_contract_version="1.0.0",
                hub_contract_json={
                    "info": {"tags": [f"tag{i % 5}"]}
                },
                created_by=self.user
            )
    
    def test_health_endpoint_baseline(self):
        """Establish baseline for health endpoint."""
        stats = self.measure_multiple(
            lambda: self.client.get('/health/'),
            iterations=20
        )
        
        # Health endpoint should be very fast
        self.assertLess(stats['mean'], 0.05, f"Health endpoint too slow: {stats['mean']:.3f}s")
        self.assertLess(stats['max'], 0.1, f"Health endpoint max time too high: {stats['max']:.3f}s")
    
    def test_contract_list_endpoint_baseline(self):
        """Establish baseline for contract list endpoint."""
        stats = self.measure_multiple(
            lambda: self.client.get('/api/v1/contracts/'),
            iterations=20
        )
        
        # Contract list endpoint should be reasonably fast
        self.assertLess(stats['mean'], 0.5, f"Contract list endpoint too slow: {stats['mean']:.3f}s")
        self.assertLess(stats['max'], 1.0, f"Contract list endpoint max time too high: {stats['max']:.3f}s")
    
    def test_contract_filter_endpoint_baseline(self):
        """Establish baseline for contract filter endpoint."""
        stats = self.measure_multiple(
            lambda: self.client.get('/api/v1/contracts/', {'tag': 'tag1'}),
            iterations=20
        )
        
        # Contract filter endpoint should be reasonably fast
        self.assertLess(stats['mean'], 0.6, f"Contract filter endpoint too slow: {stats['mean']:.3f}s")
        self.assertLess(stats['max'], 1.2, f"Contract filter endpoint max time too high: {stats['max']:.3f}s")


class MiddlewareBaselineTest(PerformanceBaselineTest):
    """Baseline tests for middleware."""
    
    def test_middleware_chain_baseline(self):
        """Establish baseline for middleware chain execution."""
        stats = self.measure_multiple(
            lambda: self.client.get('/api/v1/assets/'),
            iterations=20
        )
        
        # Middleware chain should be reasonably fast
        self.assertLess(stats['mean'], 0.5, f"Middleware chain too slow: {stats['mean']:.3f}s")
        self.assertLess(stats['max'], 1.0, f"Middleware chain max time too high: {stats['max']:.3f}s")


class JSONFieldGINIndexBaselineTest(PerformanceBaselineTest):
    """Baseline tests for JSONField GIN index performance."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        
        if connection.vendor != 'postgresql':
            self.skipTest("GIN index tests only for PostgreSQL")
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="gin-baseline-asset",
            name="GIN Baseline Asset"
        )
        
        # Create contracts with various JSONField data
        for i in range(100):
            Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                version=i+1,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="1.0.0",
                original_format=OriginalFormat.JSON,
                original_raw='{}',
                hub_contract_version="1.0.0",
                hub_contract_json={
                    "info": {
                        "tags": [f"tag{i % 20}", f"tag{(i+1) % 20}"]
                    },
                    "quality": {
                        "default_profile_key": "great_expectations" if i % 2 == 0 else "soda"
                    },
                    "privacy_compliance": {
                        "jurisdictions": ["GDPR", "CCPA"] if i % 3 == 0 else ["GDPR"],
                        "contains_personal_data": i % 2 == 0
                    }
                },
                created_by=self.user
            )
    
    def test_gin_index_array_contains_baseline(self):
        """Establish baseline for GIN index array contains queries."""
        stats = self.measure_multiple(
            lambda: Contract.objects.filter(
                hub_contract_json__info__tags__contains=["tag1"]
            ).count(),
            iterations=30
        )
        
        # With GIN index, array contains should be very fast
        self.assertLess(stats['mean'], 0.05, f"GIN index array contains too slow: {stats['mean']:.3f}s")
        self.assertLess(stats['max'], 0.1, f"GIN index array contains max time too high: {stats['max']:.3f}s")
    
    def test_gin_index_nested_key_baseline(self):
        """Establish baseline for GIN index nested key queries."""
        stats = self.measure_multiple(
            lambda: Contract.objects.filter(
                hub_contract_json__quality__default_profile_key="great_expectations"
            ).count(),
            iterations=30
        )
        
        # With GIN index, nested key should be fast
        self.assertLess(stats['mean'], 0.08, f"GIN index nested key too slow: {stats['mean']:.3f}s")
        self.assertLess(stats['max'], 0.15, f"GIN index nested key max time too high: {stats['max']:.3f}s")
    
    def test_gin_index_complex_filter_baseline(self):
        """Establish baseline for GIN index complex filter queries."""
        from django.db.models import Q
        
        stats = self.measure_multiple(
            lambda: Contract.objects.filter(
                Q(hub_contract_json__info__tags__contains=["tag1"]) &
                Q(hub_contract_json__privacy_compliance__jurisdictions__contains=["GDPR"])
            ).count(),
            iterations=30
        )
        
        # With GIN index, complex filter should be reasonably fast
        self.assertLess(stats['mean'], 0.1, f"GIN index complex filter too slow: {stats['mean']:.3f}s")
        self.assertLess(stats['max'], 0.2, f"GIN index complex filter max time too high: {stats['max']:.3f}s")

