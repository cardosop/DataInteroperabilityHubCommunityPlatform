"""
Stress Testing with Locust

Stress testing pushes the system beyond normal operational capacity to identify:
- Breaking points
- Resource limits
- Failure modes
- Recovery behavior

Test Scenarios:
1. Gradual ramp-up to maximum capacity
2. Sustained load at maximum capacity
3. Beyond capacity load (overload)
4. Resource exhaustion scenarios
"""

import pytest

# Skip if locust is not installed
try:
    from locust import HttpUser, between, events, task
    from locust.contrib.fasthttp import FastHttpUser

    LOCUST_AVAILABLE = True
except ImportError:
    LOCUST_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="locust not installed - install with: pip install locust")

if LOCUST_AVAILABLE:
    import os
    import random

    # Import shared helpers
    import sys
    import time
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))

    from tests.performance.helpers import PerformanceTestHelper

    class StressTestUser(FastHttpUser):
        """
        Stress test user that gradually increases load until system breaks.

        This user class simulates realistic API usage patterns while gradually
        increasing the load to identify system breaking points.
        """

        wait_time = between(0.1, 0.5)  # Very short wait time for stress testing

        def on_start(self):
            """Authenticate user on start."""
            self.helper = PerformanceTestHelper(base_url=self.host)
            self.test_data = self.helper.create_test_tenant_and_user()
            self.headers = self.test_data["headers"]
            self.access_token = self.test_data["access_token"]
            self.contract_ids = []
            self.asset_ids = []
            self.dataset_ids = []

        @task(5)
        def stress_list_contracts(self):
            """Heavy contract listing with filters and pagination."""
            params = {
                "page": random.randint(1, 10),
                "page_size": random.choice([10, 20, 50, 100]),
                "ordering": random.choice(
                    ["-created_at", "created_at", "-updated_at", "updated_at"]
                ),
            }
            # Add random filters to increase query complexity
            if random.random() < 0.3:
                params["status"] = random.choice(["DRAFT", "ACTIVE", "ARCHIVED"])

            with self.client.get(
                "/api/v1/contracts/contracts/",
                headers=self.headers,
                params=params,
                catch_response=True,
                name="stress_list_contracts",
            ) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 429:
                    # Rate limiting is expected under stress
                    response.failure("Rate limited")
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

        @task(3)
        def stress_create_contract(self):
            """Rapid contract creation to stress write operations."""
            contract_data = {
                "name": f"stress-contract-{int(time.time())}-{random.randint(1000, 9999)}",
                "version": "1.0.0",
                "spec": {
                    "type": "datacontract",
                    "version": "0.8.0",
                    "id": f"stress-contract-{int(time.time())}",
                    "info": {"title": "Stress Test Contract", "version": "1.0.0"},
                },
            }

            with self.client.post(
                "/api/v1/contracts/contracts/",
                headers=self.headers,
                json=contract_data,
                catch_response=True,
                name="stress_create_contract",
            ) as response:
                if response.status_code in [200, 201]:
                    data = response.json()
                    if "id" in data:
                        self.contract_ids.append(data["id"])
                    response.success()
                elif response.status_code == 429:
                    response.failure("Rate limited")
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

        @task(4)
        def stress_get_contract(self):
            """Rapid contract retrieval to stress read operations."""
            if not self.contract_ids:
                return

            contract_id = random.choice(self.contract_ids)

            with self.client.get(
                f"/api/v1/contracts/contracts/{contract_id}/",
                headers=self.headers,
                catch_response=True,
                name="stress_get_contract",
            ) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 404:
                    # Contract might have been deleted, not a failure
                    response.success()
                elif response.status_code == 429:
                    response.failure("Rate limited")
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

        @task(2)
        def stress_list_assets(self):
            """Heavy asset listing with complex queries."""
            params = {
                "page": random.randint(1, 10),
                "page_size": random.choice([10, 20, 50]),
            }

            with self.client.get(
                "/api/v1/assets/assets/",
                headers=self.headers,
                params=params,
                catch_response=True,
                name="stress_list_assets",
            ) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 429:
                    response.failure("Rate limited")
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

        @task(2)
        def stress_create_asset(self):
            """Rapid asset creation."""
            asset_data = {
                "name": f"stress-asset-{int(time.time())}-{random.randint(1000, 9999)}",
                "description": "Stress test asset",
                "status": "DRAFT",
            }

            with self.client.post(
                "/api/v1/assets/assets/",
                headers=self.headers,
                json=asset_data,
                catch_response=True,
                name="stress_create_asset",
            ) as response:
                if response.status_code in [200, 201]:
                    data = response.json()
                    if "id" in data:
                        self.asset_ids.append(data["id"])
                    response.success()
                elif response.status_code == 429:
                    response.failure("Rate limited")
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

        @task(1)
        def stress_complex_query(self):
            """Complex queries that stress the database."""
            # Search with multiple filters
            params = {
                "search": random.choice(["test", "contract", "asset", "data"]),
                "page": random.randint(1, 5),
            }

            with self.client.get(
                "/api/v1/contracts/contracts/",
                headers=self.headers,
                params=params,
                catch_response=True,
                name="stress_complex_query",
            ) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 429:
                    response.failure("Rate limited")
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

    class StressTestOverloadUser(FastHttpUser):
        """
        Overload test user that pushes system beyond capacity.

        This user class generates extreme load to test system behavior
        when pushed beyond normal operational limits.
        """

        wait_time = between(0.05, 0.2)  # Minimal wait time for overload testing

        def on_start(self):
            """Authenticate user on start."""
            self.helper = PerformanceTestHelper(base_url=self.host)
            self.test_data = self.helper.create_test_tenant_and_user()
            self.headers = self.test_data["headers"]
            self.access_token = self.test_data["access_token"]

        @task(10)
        def overload_rapid_requests(self):
            """Generate rapid-fire requests to overload the system."""
            with self.client.get(
                "/api/v1/contracts/contracts/",
                headers=self.headers,
                catch_response=True,
                name="overload_rapid_requests",
            ) as response:
                # Accept any response (including errors) as valid for overload testing
                if response.status_code < 500:
                    response.success()
                else:
                    response.failure(f"Server error: {response.status_code}")

        @task(5)
        def overload_heavy_payloads(self):
            """Send large payloads to stress request processing."""
            large_contract = {
                "name": f"overload-contract-{int(time.time())}-{random.randint(1000, 9999)}",
                "version": "1.0.0",
                "spec": {
                    "type": "datacontract",
                    "version": "0.8.0",
                    "id": f"overload-contract-{int(time.time())}",
                    "info": {"title": "Overload Test Contract", "version": "1.0.0"},
                },
            }
            # Add large nested data
            large_contract["info"] = {
                "description": "x" * 10000,  # 10KB description
                "tags": [f"tag-{i}" for i in range(100)],
                "metadata": {f"key-{i}": f"value-{i}" * 100 for i in range(50)},
            }

            with self.client.post(
                "/api/v1/contracts/contracts/",
                headers=self.headers,
                json=large_contract,
                catch_response=True,
                name="overload_heavy_payloads",
            ) as response:
                if response.status_code < 500:
                    response.success()
                else:
                    response.failure(f"Server error: {response.status_code}")
