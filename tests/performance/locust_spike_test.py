"""
Spike Testing with Locust

Spike testing suddenly increases load to extreme levels to test:
- System's ability to handle sudden traffic spikes
- Recovery behavior after spike
- Resource allocation under sudden load
- Rate limiting effectiveness
- Graceful degradation

Test Pattern:
1. Normal load (baseline)
2. Sudden spike to 2-10x normal load
3. Sustained spike
4. Sudden drop back to normal
5. Recovery period
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

    class SpikeTestUser(FastHttpUser):
        """
        Spike test user that generates sudden load spikes.

        This user class simulates sudden traffic increases (e.g., viral content,
        flash sales, breaking news) to test system resilience.
        """

        wait_time = between(0.1, 1.0)  # Variable wait time for spike simulation

        def on_start(self):
            """Authenticate user on start."""
            self.helper = PerformanceTestHelper(base_url=self.host)
            self.test_data = self.helper.create_test_tenant_and_user()
            self.headers = self.test_data["headers"]
            self.access_token = self.test_data["access_token"]
            self.contract_ids = []
            self.spike_active = False

        @task(8)
        def spike_list_contracts(self):
            """High-frequency contract listing during spike."""
            params = {
                "page": random.randint(1, 10),
                "page_size": random.choice([10, 20, 50]),
            }

            with self.client.get(
                "/api/v1/contracts/contracts/",
                headers=self.headers,
                params=params,
                catch_response=True,
                name="spike_list_contracts",
            ) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 429:
                    # Rate limiting expected during spike
                    response.failure("Rate limited during spike")
                elif response.status_code >= 500:
                    response.failure(f"Server error during spike: {response.status_code}")
                else:
                    response.success()  # Accept other status codes during spike

        @task(5)
        def spike_get_contract(self):
            """High-frequency contract retrieval during spike."""
            if not self.contract_ids:
                return

            contract_id = random.choice(self.contract_ids)

            with self.client.get(
                f"/api/v1/contracts/contracts/{contract_id}/",
                headers=self.headers,
                catch_response=True,
                name="spike_get_contract",
            ) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 429:
                    response.failure("Rate limited during spike")
                elif response.status_code >= 500:
                    response.failure(f"Server error during spike: {response.status_code}")
                else:
                    response.success()

        @task(3)
        def spike_create_contract(self):
            """High-frequency contract creation during spike."""
            contract_data = {
                "name": f"spike-contract-{int(time.time())}-{random.randint(1000, 9999)}",
                "version": "1.0.0",
                "spec": {
                    "type": "datacontract",
                    "version": "0.8.0",
                    "id": f"spike-contract-{int(time.time())}",
                    "info": {"title": "Spike Test Contract", "version": "1.0.0"},
                },
            }

            with self.client.post(
                "/api/v1/contracts/contracts/",
                headers=self.headers,
                json=contract_data,
                catch_response=True,
                name="spike_create_contract",
            ) as response:
                if response.status_code in [200, 201]:
                    data = response.json()
                    if "id" in data:
                        self.contract_ids.append(data["id"])
                        # Keep only recent IDs
                        if len(self.contract_ids) > 50:
                            self.contract_ids.pop(0)
                    response.success()
                elif response.status_code == 429:
                    response.failure("Rate limited during spike")
                elif response.status_code >= 500:
                    response.failure(f"Server error during spike: {response.status_code}")
                else:
                    response.success()

        @task(2)
        def spike_search(self):
            """High-frequency search operations during spike."""
            search_terms = ["test", "contract", "data", "asset", "quality"]

            with self.client.get(
                "/api/v1/contracts/contracts/",
                headers=self.headers,
                params={"search": random.choice(search_terms)},
                catch_response=True,
                name="spike_search",
            ) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 429:
                    response.failure("Rate limited during spike")
                elif response.status_code >= 500:
                    response.failure(f"Server error during spike: {response.status_code}")
                else:
                    response.success()

        @task(1)
        def spike_health_check(self):
            """Health checks during spike to monitor system state."""
            with self.client.get("/health", catch_response=True, name="spike_health_check") as response:
                if response.status_code == 200:
                    response.success()
                else:
                    # Health check failures are critical
                    response.failure(f"Health check failed: {response.status_code}")

    class SpikeTestRapidUser(FastHttpUser):
        """
        Rapid spike user for extreme spike testing.

        This user generates extremely high request rates to simulate
        the most extreme spike scenarios (e.g., DDoS-like traffic).
        """

        wait_time = between(0.01, 0.1)  # Very short wait time for rapid spikes

        def on_start(self):
            """Authenticate user on start."""
            self.helper = PerformanceTestHelper(base_url=self.host)
            self.test_data = self.helper.create_test_tenant_and_user()
            self.headers = self.test_data["headers"]
            self.access_token = self.test_data["access_token"]

        @task(10)
        def rapid_spike_requests(self):
            """Generate rapid-fire requests for extreme spike."""
            with self.client.get(
                "/api/v1/contracts/contracts/",
                headers=self.headers,
                catch_response=True,
                name="rapid_spike_requests",
            ) as response:
                # Accept any response during extreme spike
                if response.status_code < 500:
                    response.success()
                else:
                    response.failure(f"Server error: {response.status_code}")
