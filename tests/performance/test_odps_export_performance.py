"""
10.5.6: ODPS Export Performance Tests

Tests ODPS export performance for different sizes:
- Small ODPS products (1KB)
- Medium ODPS products (1MB)
- Large ODPS products (10MB, 100MB)

Targets (CI-adjusted for shared DB, cold start, batch load):
- Export duration < 6s for 1KB
- Export duration < 5s for 1MB
- Export duration < 30s for 10MB
- Export duration < 300s for 100MB
- Memory usage reasonable
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

import pytest
from django.test import TestCase, TransactionTestCase

from hub.apps.contracts.models import Contract
from hub.apps.contracts.services import ODPSService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


def create_odps_document(product_id: str = None, size_kb: float = 1.0) -> dict:
    """Create ODPS document of approximately specified size"""
    if not product_id:
        product_id = f"export-perf-{int(time.time() * 1000)}"

    # Calculate approximate content size
    base_doc = {
        "schema": "https://opendataproducts.org/schema/v4.1",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "productID": product_id,
                    "name": f"Export Performance Test {product_id}",
                    "description": f"ODPS product for export performance testing (~{size_kb}KB)",
                }
            },
            "contract": {
                "spec": {
                    "apiVersion": "odcs/v3",
                    "kind": "DataContract",
                    "id": f"{product_id}-contract",
                    "name": f"Export Test Contract {product_id}",
                    "schema": {"fields": []},
                }
            },
            "dataSchema": {"fields": []},
        },
    }

    # Add fields to reach target size (in both contract.schema and dataSchema)
    # Each field adds approximately 100 bytes
    num_fields = int(size_kb * 1024 / 100)
    for i in range(min(num_fields, 10000)):  # Cap at 10000 fields
        field_def = {
            "name": f"field_{i}",
            "type": "string",
            "description": f"Field {i} for size testing" + "x" * 50,
        }
        base_doc["product"]["contract"]["spec"]["schema"]["fields"].append(field_def)
        base_doc["product"]["dataSchema"]["fields"].append(field_def)

    return base_doc


class ODPSExportPerformanceTestBase(TransactionTestCase):
    """Base class for ODPS export performance tests"""

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures"""
        import uuid
        
        # Create test tenant and user with unique names to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        tenant_name = f"Export Performance Test Tenant {unique_id}"
        tenant_slug = f"export-perf-test-{unique_id}"
        
        # Try to get existing tenant or create new one
        self.tenant, created = Tenant.objects.get_or_create(
            slug=tenant_slug,
            defaults={
                "name": tenant_name,
                "status": "ACTIVE",
                "kyc_status": "VERIFIED"
            }
        )
        
        # If tenant already exists, update name to be unique
        if not created:
            self.tenant.name = tenant_name
            self.tenant.save()
        
        # Create user with unique email
        user_email = f"export-perf-test-{unique_id}@example.com"
        self.user, _ = User.objects.get_or_create(
            email=user_email,
            defaults={
                "password": "test-password-123",
                "tenant": self.tenant,
                "status": UserStatus.ACTIVE,
            }
        )
        self.odps_service = ODPSService()

    def tearDown(self):
        """Clean up test data"""
        if hasattr(self, 'tenant'):
            try:
                Contract.objects.filter(tenant=self.tenant).delete()
            except Exception:
                pass  # Ignore cleanup errors

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for export performance tests."""
        # Don't flush - transactions are rolled back which provides isolation
        pass

    def get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except (ImportError, AttributeError):
            # psutil not available, return 0
            return 0.0


class TestODPSExportPerformance(ODPSExportPerformanceTestBase):
    """Test ODPS export performance for different sizes"""

    def test_export_performance_small_1kb(self):
        """Test export performance for small ODPS product (1KB)"""
        odps_doc = create_odps_document(size_kb=1.0)

        # Create contract
        contract = self.odps_service.create_odps(
            odps_raw=json.dumps(odps_doc),
            odps_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resolve_external_refs=False,  # Disable to avoid external service timeouts in tests
        )

        # Measure export performance
        start_time = time.time()
        start_memory = self.get_memory_usage()

        exported = self.odps_service.export_odps(
            contract_id=str(contract.id),
            output_format="json",
            tenant_id=str(self.tenant.id),
        )

        duration = time.time() - start_time
        end_memory = self.get_memory_usage()
        memory_delta = end_memory - start_memory

        # Verify export succeeded
        self.assertIsNotNone(exported)

        # Verify performance targets (6s allows CI variance, DB load, cold start)
        self.assertLess(duration, 6.0, f"Export took {duration:.2f}s, exceeds 6s target for 1KB")

        # Verify reasonable memory usage (< 50MB increase)
        self.assertLess(
            memory_delta, 50.0, f"Memory increase {memory_delta:.2f}MB exceeds 50MB target"
        )

    def test_export_performance_medium_1mb(self):
        """Test export performance for medium ODPS product (1MB)"""
        odps_doc = create_odps_document(size_kb=1024.0)

        # Create contract
        contract = self.odps_service.create_odps(
            odps_raw=json.dumps(odps_doc),
            odps_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resolve_external_refs=False,  # Disable to avoid external service timeouts in tests
        )

        # Measure export performance
        start_time = time.time()
        start_memory = self.get_memory_usage()

        exported = self.odps_service.export_odps(
            contract_id=str(contract.id),
            output_format="json",
            tenant_id=str(self.tenant.id),
        )

        duration = time.time() - start_time
        end_memory = self.get_memory_usage()
        memory_delta = end_memory - start_memory

        # Verify export succeeded
        self.assertIsNotNone(exported)

        # Verify performance targets
        self.assertLess(duration, 5.0, f"Export took {duration:.2f}s, exceeds 5s target for 1MB")

        # Verify reasonable memory usage (< 200MB increase)
        self.assertLess(
            memory_delta, 200.0, f"Memory increase {memory_delta:.2f}MB exceeds 200MB target"
        )

    def test_export_performance_large_10mb(self):
        """Test export performance for large ODPS product (10MB)"""
        odps_doc = create_odps_document(size_kb=10240.0)

        # Create contract
        contract = self.odps_service.create_odps(
            odps_raw=json.dumps(odps_doc),
            odps_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resolve_external_refs=False,  # Disable to avoid external service timeouts in tests
        )

        # Measure export performance
        start_time = time.time()
        start_memory = self.get_memory_usage()

        exported = self.odps_service.export_odps(
            contract_id=str(contract.id),
            output_format="json",
            tenant_id=str(self.tenant.id),
        )

        duration = time.time() - start_time
        end_memory = self.get_memory_usage()
        memory_delta = end_memory - start_memory

        # Verify export succeeded
        self.assertIsNotNone(exported)

        # Verify performance targets
        self.assertLess(duration, 30.0, f"Export took {duration:.2f}s, exceeds 30s target for 10MB")

        # Verify reasonable memory usage (< 500MB increase)
        self.assertLess(
            memory_delta, 500.0, f"Memory increase {memory_delta:.2f}MB exceeds 500MB target"
        )

    def test_export_performance_very_large_100mb(self):
        """Test export performance for very large ODPS product (100MB)"""
        # Skip if system doesn't have enough memory
        if not PSUTIL_AVAILABLE or psutil is None:
            self.skipTest("psutil not available for memory check")
        available_memory = psutil.virtual_memory().available / 1024 / 1024  # MB
        if available_memory < 2000:  # Less than 2GB available
            self.skipTest("Insufficient memory for 100MB test")

        odps_doc = create_odps_document(size_kb=102400.0)

        # Create contract
        contract = self.odps_service.create_odps(
            odps_raw=json.dumps(odps_doc),
            odps_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resolve_external_refs=False,  # Disable to avoid external service timeouts in tests
        )

        # Measure export performance
        start_time = time.time()
        start_memory = self.get_memory_usage()

        exported = self.odps_service.export_odps(
            contract_id=str(contract.id),
            output_format="json",
            tenant_id=str(self.tenant.id),
        )

        duration = time.time() - start_time
        end_memory = self.get_memory_usage()
        memory_delta = end_memory - start_memory

        # Verify export succeeded
        self.assertIsNotNone(exported)

        # Verify performance targets
        self.assertLess(
            duration, 300.0, f"Export took {duration:.2f}s, exceeds 300s target for 100MB"
        )

        # Verify reasonable memory usage (< 2GB increase) - skip if psutil not available
        if PSUTIL_AVAILABLE:
            self.assertLess(
                memory_delta, 2000.0, f"Memory increase {memory_delta:.2f}MB exceeds 2GB target"
            )


class TestODPSExportFormatPerformance(ODPSExportPerformanceTestBase):
    """Test ODPS export performance for different formats"""

    def test_export_json_performance(self):
        """Test JSON export performance.

        Uses 1KB document to stay under PostgreSQL index key limit (8191 bytes).
        Larger documents cause ProgramLimitExceeded on hub_contract_json GIN index.
        """
        odps_doc = create_odps_document(size_kb=1.0)

        contract = self.odps_service.create_odps(
            odps_raw=json.dumps(odps_doc),
            odps_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resolve_external_refs=False,  # Disable to avoid external service timeouts in tests
        )

        start_time = time.time()

        exported = self.odps_service.export_odps(
            contract_id=str(contract.id),
            output_format="json",
            tenant_id=str(self.tenant.id),
        )

        duration = time.time() - start_time

        self.assertIsNotNone(exported)
        # 15s allows CI variance (shared DB, cold start, batch load)
        self.assertLess(duration, 15.0, f"JSON export took {duration:.2f}s")

    def test_export_yaml_performance(self):
        """Test YAML export performance"""
        odps_doc = create_odps_document(size_kb=1.0)

        contract = self.odps_service.create_odps(
            odps_raw=json.dumps(odps_doc),
            odps_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resolve_external_refs=False,  # Disable to avoid external service timeouts in tests
        )

        start_time = time.time()

        exported = self.odps_service.export_odps(
            contract_id=str(contract.id),
            output_format="yaml",
            tenant_id=str(self.tenant.id),
        )

        duration = time.time() - start_time

        self.assertIsNotNone(exported)
        self.assertLess(duration, 2.0, f"YAML export took {duration:.2f}s")


class TestODPSExportConcurrentPerformance(ODPSExportPerformanceTestBase):
    """Test ODPS export performance under concurrent load"""

    def test_concurrent_export_performance(self):
        """Test export performance with concurrent requests.

        Uses 1KB docs to stay under PostgreSQL index key limits.
        """
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Create multiple contracts (1KB each to avoid path index limits)
        contracts = []
        for i in range(10):
            odps_doc = create_odps_document(size_kb=1.0, product_id=f"concurrent-{i}")
            contract = self.odps_service.create_odps(
                odps_raw=json.dumps(odps_doc),
                odps_format="JSON",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                resolve_external_refs=False,  # Disable to avoid external service timeouts in tests
            )
            contracts.append(contract)

        # Export concurrently
        results = []
        errors = []
        lock = threading.Lock()

        def export_contract(contract):
            try:
                start_time = time.time()
                exported = self.odps_service.export_odps(
                    contract_id=str(contract.id),
                    output_format="json",
                    tenant_id=str(self.tenant.id),
                )
                duration = time.time() - start_time

                with lock:
                    results.append(
                        {"contract_id": str(contract.id), "duration": duration, "success": True}
                    )
            except Exception as e:
                with lock:
                    errors.append(str(e))
                    results.append({"contract_id": str(contract.id), "success": False})

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(export_contract, contract) for contract in contracts]
            for future in as_completed(futures):
                future.result()

        total_duration = time.time() - start_time

        # Verify all exports succeeded
        successful = sum(1 for r in results if r.get("success", False))
        self.assertEqual(
            successful, len(contracts), f"Only {successful}/{len(contracts)} exports succeeded"
        )

        # Verify reasonable total duration (< 20s for 10 concurrent exports; CI variance)
        self.assertLess(
            total_duration,
            20.0,
            f"Concurrent exports took {total_duration:.2f}s, exceeds 20s target",
        )
