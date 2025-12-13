"""
T.17: Load test database query performance

Tests database query performance under load.
Targets:
- P50 query time ≤ 50ms
- P95 query time ≤ 200ms
- P99 query time ≤ 500ms
"""

import pytest

# Skip if locust is not installed
try:
    from locust import HttpUser, between, events, task
    from locust.contrib.fasthttp import FastHttpUser

    LOCUST_AVAILABLE = True
except ImportError:
    LOCUST_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="locust not installed")

    # Skip entire module if locust not available
    pass
    pytestmark = pytest.mark.skip(reason="locust not installed")

if LOCUST_AVAILABLE:
    import random
    import sys
    import time
    from pathlib import Path

    from django.db import connection
    from django.test.utils import override_settings

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    from tests.performance.helpers import PerformanceTestHelper

    class DatabaseQueryPerformanceUser(FastHttpUser):
        """Locust user for database query performance testing"""

        wait_time = between(0.1, 0.5)  # Wait 0.1-0.5 seconds between tasks
        weight = 1

        def on_start(self):
            """Set up test user and authentication"""
            self.helper = PerformanceTestHelper(base_url=self.host)
            self.test_data = self.helper.create_test_tenant_and_user(
                tenant_name=f"perf-tenant-{random.randint(1000, 9999)}",
                user_email=f"perf-user-{random.randint(1000, 9999)}@example.com",
            )
            self.headers = self.test_data["headers"]
            self.access_token = self.test_data["access_token"]

        @task(10)
        def test_simple_lookup(self):
            """Test simple single-row lookup (GET /assets/{id})"""
            # First get an asset ID
            with self.client.get(
                "/api/v1/assets",
                headers=self.headers,
                params={"limit": 1},
                name="/api/v1/assets (simple lookup)",
                catch_response=True,
            ) as response:
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    if results:
                        asset_id = results[0].get("id")
                        self._measure_query_time(
                            lambda: self.client.get(
                                f"/api/v1/assets/{asset_id}",
                                headers=self.headers,
                                name="/api/v1/assets/{id} (single lookup)",
                            ),
                            "single_row_lookup",
                        )
                    response.success()
                else:
                    response.failure(f"Failed to list assets: {response.status_code}")

        @task(8)
        def test_filtered_list(self):
            """Test filtered list query (GET /assets with filters)"""
            params = {
                "status": random.choice(["DRAFT", "ACTIVE", "ARCHIVED"]),
                "limit": random.randint(10, 50),
                "offset": random.randint(0, 100),
            }

            self._measure_query_time(
                lambda: self.client.get(
                    "/api/v1/assets",
                    headers=self.headers,
                    params=params,
                    name="/api/v1/assets (filtered list)",
                ),
                "filtered_list_query",
            )

        @task(5)
        def test_join_query(self):
            """Test query with joins (GET /jobs with related data)"""
            params = {"status": random.choice(["PENDING", "RUNNING", "COMPLETED"]), "limit": 20}

            self._measure_query_time(
                lambda: self.client.get(
                    "/api/v1/jobs",
                    headers=self.headers,
                    params=params,
                    name="/api/v1/jobs (join query)",
                ),
                "join_query",
            )

        @task(3)
        def test_search_query(self):
            """Test search query (GET /assets with search)"""
            search_terms = ["test", "data", "asset", "dataset", "contract"]
            params = {"search": random.choice(search_terms), "limit": 20}

            self._measure_query_time(
                lambda: self.client.get(
                    "/api/v1/assets",
                    headers=self.headers,
                    params=params,
                    name="/api/v1/assets (search query)",
                ),
                "search_query",
            )

        @task(2)
        def test_aggregation_query(self):
            """Test aggregation query (GET /jobs with counts)"""
            # Some endpoints might return counts or aggregations
            # This is a placeholder for aggregation queries
            self._measure_query_time(
                lambda: self.client.get(
                    "/api/v1/jobs",
                    headers=self.headers,
                    params={"limit": 1},
                    name="/api/v1/jobs (aggregation)",
                ),
                "aggregation_query",
            )

        def _measure_query_time(self, query_func, query_name: str):
            """Measure query execution time and track metrics"""
            start_time = time.time()

            try:
                response = query_func()
                query_time = (time.time() - start_time) * 1000  # Convert to ms

                # Track query performance
                events.request.fire(
                    request_type="db_query",
                    name=query_name,
                    response_time=query_time,
                    response_length=0,
                    exception=None,
                )

                # Check if query exceeds targets
                if query_time > 500:  # P99 target
                    events.request.fire(
                        request_type="db_query_slow",
                        name=f"{query_name}_p99_exceeded",
                        response_time=query_time,
                        response_length=0,
                        exception=None,
                    )
                elif query_time > 200:  # P95 target
                    events.request.fire(
                        request_type="db_query_slow",
                        name=f"{query_name}_p95_exceeded",
                        response_time=query_time,
                        response_length=0,
                        exception=None,
                    )
                elif query_time > 50:  # P50 target
                    events.request.fire(
                        request_type="db_query_slow",
                        name=f"{query_name}_p50_exceeded",
                        response_time=query_time,
                        response_length=0,
                        exception=None,
                    )

                return response
            except Exception as e:
                query_time = (time.time() - start_time) * 1000
                events.request.fire(
                    request_type="db_query",
                    name=query_name,
                    response_time=query_time,
                    response_length=0,
                    exception=e,
                )
                raise
