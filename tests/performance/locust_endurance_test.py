"""
Endurance Testing with Locust

Endurance testing (soak testing) runs the system under normal load
for extended periods to identify:
- Memory leaks
- Resource exhaustion over time
- Degradation of performance
- Database connection pool issues
- Background job queue issues

Test Duration: Typically 1-24 hours
Load: Normal to moderate (50-70% of capacity)
"""

import pytest

# Skip if locust is not installed
try:
    from locust import HttpUser, between, task
    from locust.contrib.fasthttp import FastHttpUser

    LOCUST_AVAILABLE = True
except ImportError:
    LOCUST_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="locust not installed - install with: pip install locust")

if LOCUST_AVAILABLE:
    import random

    # Import shared helpers
    import sys
    import time
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))

    from tests.performance.helpers import PerformanceTestHelper

    class EnduranceTestUser(FastHttpUser):
        """
        Endurance test user that simulates normal usage over extended periods.

        This user class generates realistic, sustained load to identify
        long-term issues like memory leaks and resource exhaustion.
        """

        wait_time = between(1, 5)  # Realistic wait time between requests

        def on_start(self):
            """Authenticate user on start."""
            self.helper = PerformanceTestHelper(base_url=self.host)
            self.test_data = self.helper.create_test_tenant_and_user()
            self.headers = self.test_data["headers"]
            self.access_token = self.test_data["access_token"]
            self.contract_ids = []
            self.asset_ids = []
            self.request_count = 0

        @task(10)
        def endurance_list_contracts(self):
            """Sustained contract listing operations."""
            params = {
                "page": random.randint(1, 5),
                "page_size": random.choice([10, 20]),
                "ordering": "-created_at",
            }

            response = self.client.get(
                "/api/v1/contracts/",
                headers=self.headers,
                params=params,
                name="endurance_list_contracts",
            )
            self.request_count += 1

            # Periodically check for performance degradation
            if self.request_count % 100 == 0 and response.elapsed.total_seconds() > 2.0:
                # Log slow response but don't fail (endurance test)
                print(f"Warning: Slow response detected: {response.elapsed.total_seconds()}s")

        @task(5)
        def endurance_get_contract(self):
            """Sustained contract retrieval operations."""
            if not self.contract_ids:
                # Create a contract if we don't have any
                self.endurance_create_contract()
                return

            contract_id = random.choice(self.contract_ids)

            self.client.get(
                f"/api/v1/contracts/{contract_id}/",
                headers=self.headers,
                name="endurance_get_contract",
            )
            self.request_count += 1

        @task(3)
        def endurance_create_contract(self):
            """Sustained contract creation operations."""
            contract_data = {
                "name": f"endurance-contract-{int(time.time())}-{random.randint(1000, 9999)}",
                "version": "1.0.0",
                "spec": {
                    "type": "datacontract",
                    "version": "0.8.0",
                    "id": f"endurance-contract-{int(time.time())}",
                    "info": {"title": "Endurance Test Contract", "version": "1.0.0"},
                },
            }

            response = self.client.post(
                "/api/v1/contracts/",
                headers=self.headers,
                json=contract_data,
                name="endurance_create_contract",
            )
            self.request_count += 1

            if response.status_code in [200, 201]:
                data = response.json()
                if "id" in data:
                    self.contract_ids.append(data["id"])
                    # Keep only last 100 contract IDs to avoid memory growth
                    if len(self.contract_ids) > 100:
                        self.contract_ids.pop(0)

        @task(5)
        def endurance_list_assets(self):
            """Sustained asset listing operations."""
            params = {
                "page": random.randint(1, 5),
                "page_size": random.choice([10, 20]),
            }

            self.client.get(
                "/api/v1/assets/",
                headers=self.headers,
                params=params,
                name="endurance_list_assets",
            )
            self.request_count += 1

        @task(2)
        def endurance_create_asset(self):
            """Sustained asset creation operations."""
            asset_data = {
                "name": f"endurance-asset-{int(time.time())}-{random.randint(1000, 9999)}",
                "description": "Endurance test asset",
                "status": "DRAFT",
            }

            response = self.client.post(
                "/api/v1/assets/",
                headers=self.headers,
                json=asset_data,
                name="endurance_create_asset",
            )
            self.request_count += 1

            if response.status_code in [200, 201]:
                data = response.json()
                if "id" in data:
                    self.asset_ids.append(data["id"])
                    # Keep only last 50 asset IDs
                    if len(self.asset_ids) > 50:
                        self.asset_ids.pop(0)

        @task(2)
        def endurance_get_job_status(self):
            """Sustained job status checking."""
            self.client.get(
                "/api/v1/jobs/",
                headers=self.headers,
                params={"page_size": 10},
                name="endurance_get_job_status",
            )
            self.request_count += 1

        @task(1)
        def endurance_health_check(self):
            """Periodic health checks to monitor system state."""
            self.client.get("/health", name="endurance_health_check")
            self.request_count += 1

    class EnduranceTestMemoryMonitor(FastHttpUser):
        """
        Memory monitoring user for endurance testing.

        This user periodically checks system health and resource usage
        to detect memory leaks and resource exhaustion.
        """

        wait_time = between(30, 60)  # Check every 30-60 seconds

        def on_start(self):
            """Set up monitoring."""
            self.helper = PerformanceTestHelper(base_url=self.host)
            self.test_data = self.helper.create_test_tenant_and_user()
            self.headers = self.test_data["headers"]
            self.access_token = self.test_data["access_token"]
            self.start_time = time.time()

        @task
        def monitor_system_health(self):
            """Monitor system health metrics."""
            # Check health endpoint
            self.client.get("/health", name="endurance_health_check")

            # Check API metrics if available
            try:
                self.client.get(
                    "/api/v1/observability/metrics/",
                    headers=self.headers,
                    name="endurance_metrics_check",
                )
            except Exception:
                # Metrics endpoint might not be available, that's OK
                pass

            # Log elapsed time periodically
            elapsed = time.time() - self.start_time
            if int(elapsed) % 3600 == 0:  # Every hour
                print(f"Endurance test running for {elapsed / 3600:.1f} hours")
