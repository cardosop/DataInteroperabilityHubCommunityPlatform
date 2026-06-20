#!/usr/bin/env python3
"""
Performance Baseline Establishment Script

This script runs performance tests and establishes a baseline for comparison.
Since we're already on Django 6, this establishes the Django 6 baseline.
For Django 4.2 baseline, you would need to run this in a separate Django 4.2 environment.

Usage:
    python scripts/run_performance_baseline.py [--output OUTPUT_FILE] [--django-version VERSION]

Example:
    python scripts/run_performance_baseline.py --output baseline_django6.json
    python scripts/run_performance_baseline.py --django-version 4.2 --output baseline_django42.json
"""

import argparse
import json

# Setup Django before imports
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

django.setup()

import contextlib

from django.contrib.auth import get_user_model
from django.db import reset_queries
from django.test import Client

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant

User = get_user_model()


class PerformanceBaselineCollector:
    """Collects performance baseline metrics"""

    def __init__(self, django_version: str = None):
        self.django_version = django_version or django.get_version()
        self.results: dict[str, Any] = {
            "django_version": self.django_version,
            "python_version": sys.version.split()[0],
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
        }
        self.client = Client()
        self.tenant = None
        self.user = None

    def setup_test_data(self):
        """Set up test data for performance testing"""
        import uuid

        unique_id = str(uuid.uuid4())[:8]

        # Use get_or_create to avoid duplicate key errors
        self.tenant, _ = Tenant.objects.get_or_create(
            slug=f"perf-test-tenant-{unique_id}",
            defaults={"name": f"Performance Test Tenant {unique_id}"},
        )
        self.user, _ = User.objects.get_or_create(
            email=f"perftest-{unique_id}@example.com",
            defaults={
                "password": "pbkdf2_sha256$test",  # Dummy hash, will be set properly
                "tenant": self.tenant,
            },
        )
        # Set password properly
        self.user.set_password("testpass123")
        self.user.save()
        self.client.force_login(self.user)

    def measure_api_response_times(self) -> dict[str, float]:
        """Measure API response times"""
        print("Measuring API response times...")
        metrics = {}

        endpoints = [
            ("/health/", "health"),
            ("/api/v1/assets/", "assets_list"),
            ("/api/v1/tenants/", "tenants_list"),
        ]

        for endpoint, name in endpoints:
            times = []
            for _ in range(10):
                start = time.perf_counter()
                try:
                    response = self.client.get(endpoint)
                    if response.status_code in [200, 404]:  # 404 is OK for missing endpoints
                        elapsed = time.perf_counter() - start
                        times.append(elapsed * 1000)  # Convert to ms
                except Exception:
                    pass  # Skip if endpoint doesn't exist

            if times:
                metrics[f"{name}_p50"] = statistics.median(times)
                metrics[f"{name}_p95"] = (
                    sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0]
                )
                metrics[f"{name}_p99"] = (
                    sorted(times)[int(len(times) * 0.99)] if len(times) > 1 else times[0]
                )
                metrics[f"{name}_avg"] = statistics.mean(times)
                metrics[f"{name}_min"] = min(times)
                metrics[f"{name}_max"] = max(times)

        return metrics

    def measure_database_query_times(self) -> dict[str, float]:
        """Measure database query times"""
        print("Measuring database query times...")
        metrics = {}

        # Simple query
        times = []
        for _ in range(100):
            reset_queries()
            start = time.perf_counter()
            Tenant.objects.all().count()
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)

        metrics["simple_query_p50"] = statistics.median(times)
        metrics["simple_query_p95"] = sorted(times)[int(len(times) * 0.95)]
        metrics["simple_query_avg"] = statistics.mean(times)

        # Join query
        times = []
        for _ in range(100):
            reset_queries()
            start = time.perf_counter()
            User.objects.select_related("tenant").all().count()
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)

        metrics["join_query_p50"] = statistics.median(times)
        metrics["join_query_p95"] = sorted(times)[int(len(times) * 0.95)]
        metrics["join_query_avg"] = statistics.mean(times)

        return metrics

    def measure_jsonfield_query_times(self) -> dict[str, float]:
        """Measure JSONField query times"""
        print("Measuring JSONField query times...")
        metrics = {}

        # Create test contracts with JSONField data
        contracts = []
        for i in range(10):
            asset = Asset.objects.create(tenant=self.tenant, name=f"Test Asset {i}", status="DRAFT")
            contract = Contract.objects.create(
                tenant=self.tenant,
                asset=asset,
                version=1,  # IntegerField, not string
                original_spec_type="ODCS",
                original_spec_version="3.0.0",
                original_format="JSON",
                original_raw="{}",
                hub_contract_version="1.0.0",
                hub_contract_json={
                    "field1": f"value{i}",
                    "field2": {"nested": f"data{i}"},
                    "field3": [1, 2, 3, i],
                },
            )
            contracts.append(contract)

        # JSONField lookup
        times = []
        for _ in range(50):
            reset_queries()
            start = time.perf_counter()
            Contract.objects.filter(hub_contract_json__field1="value5").count()
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)

        metrics["jsonfield_lookup_p50"] = statistics.median(times)
        metrics["jsonfield_lookup_p95"] = sorted(times)[int(len(times) * 0.95)]
        metrics["jsonfield_lookup_avg"] = statistics.mean(times)

        # Cleanup
        for contract in contracts:
            contract.asset.delete()
            contract.delete()

        return metrics

    def measure_middleware_execution_times(self) -> dict[str, float]:
        """Measure middleware execution times"""
        print("Measuring middleware execution times...")
        metrics = {}

        times = []
        for _ in range(50):
            start = time.perf_counter()
            self.client.get("/health/")
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)

        metrics["middleware_p50"] = statistics.median(times)
        metrics["middleware_p95"] = sorted(times)[int(len(times) * 0.95)]
        metrics["middleware_avg"] = statistics.mean(times)

        return metrics

    def measure_job_queue_processing_times(self) -> dict[str, float]:
        """Measure job queue processing times"""
        print("Measuring job queue processing times...")
        metrics = {}

        # Create jobs
        jobs = []
        for i in range(10):
            job = Job.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                type=JobType.DQ_RUN,
                status=JobStatus.PENDING,
                resource_type="asset",
                resource_id=str(
                    Asset.objects.create(
                        tenant=self.tenant, name=f"Test Asset {i}", status="DRAFT"
                    ).id
                ),
            )
            jobs.append(job)

        # Measure job creation time
        times = []
        for i in range(20):
            start = time.perf_counter()
            Job.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                type=JobType.DQ_RUN,
                status=JobStatus.PENDING,
                resource_type="asset",
                resource_id=str(
                    Asset.objects.create(
                        tenant=self.tenant, name=f"Temp Asset {i}", status="DRAFT"
                    ).id
                ),
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)

        metrics["job_creation_p50"] = statistics.median(times)
        metrics["job_creation_p95"] = sorted(times)[int(len(times) * 0.95)]
        metrics["job_creation_avg"] = statistics.mean(times)

        # Cleanup
        for job in jobs:
            if hasattr(job, "resource_id") and job.resource_id:
                with contextlib.suppress(Asset.DoesNotExist):
                    Asset.objects.get(id=job.resource_id).delete()
            job.delete()

        return metrics

    def measure_file_storage_operations_times(self) -> dict[str, float]:
        """Measure file storage operations times"""
        print("Measuring file storage operations times...")
        metrics = {}

        # Create test files
        files = []
        for i in range(10):
            file_obj = File.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                name=f"test_file_{i}.txt",
                status=FileStatus.PENDING,
                storage_path=f"test/path/file_{i}.txt",
                size=1024 * (i + 1),
            )
            files.append(file_obj)

        # Measure file creation time
        times = []
        for i in range(20):
            start = time.perf_counter()
            File.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                name=f"temp_file_{i}.txt",
                status=FileStatus.PENDING,
                storage_path=f"test/path/temp_{i}.txt",
                size=1024,
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)

        metrics["file_creation_p50"] = statistics.median(times)
        metrics["file_creation_p95"] = sorted(times)[int(len(times) * 0.95)]
        metrics["file_creation_avg"] = statistics.mean(times)

        # Cleanup
        for file_obj in files:
            file_obj.delete()

        return metrics

    def collect_all_metrics(self):
        """Collect all performance metrics"""
        self.setup_test_data()

        self.results["metrics"]["api_response_times"] = self.measure_api_response_times()
        self.results["metrics"]["database_query_times"] = self.measure_database_query_times()
        self.results["metrics"]["jsonfield_query_times"] = self.measure_jsonfield_query_times()
        self.results["metrics"]["middleware_execution_times"] = (
            self.measure_middleware_execution_times()
        )
        self.results["metrics"]["job_queue_processing_times"] = (
            self.measure_job_queue_processing_times()
        )
        self.results["metrics"]["file_storage_operations_times"] = (
            self.measure_file_storage_operations_times()
        )

    def save_results(self, output_file: str):
        """Save results to file"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"\n✅ Performance baseline saved to: {output_path}")
        print(f"   Django version: {self.django_version}")
        print(f"   Timestamp: {self.results['timestamp']}")


def main():
    parser = argparse.ArgumentParser(description="Establish performance baseline")
    parser.add_argument(
        "--output",
        default="performance_baseline.json",
        help="Output file path (default: performance_baseline.json)",
    )
    parser.add_argument(
        "--django-version", default=None, help="Django version (default: current version)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Performance Baseline Establishment")
    print("=" * 60)
    print(f"Django version: {django.get_version()}")
    print(f"Python version: {sys.version.split()[0]}")
    print()

    collector = PerformanceBaselineCollector(django_version=args.django_version)
    collector.collect_all_metrics()
    collector.save_results(args.output)

    print("\n✅ Performance baseline establishment complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
