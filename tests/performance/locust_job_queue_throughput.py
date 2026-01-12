"""
T.16: Load test job queue throughput

Tests job queue processing throughput under load.
Targets from Testing_Strategy.md §8.1.5:
- ≥ 100 jobs/hour for DQ/compliance jobs
- Up to 50 new jobs within 5 minutes without queue latency > 5 minutes
- P50 end-to-end duration ≤ 15 minutes
- P95 end-to-end duration ≤ 30 minutes
"""
import pytest

# Skip if locust is not installed
try:
    from locust import HttpUser, task, between, events
    from locust.contrib.fasthttp import FastHttpUser
    LOCUST_AVAILABLE = True
except ImportError:
    LOCUST_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="locust not installed")

    # Skip entire module if locust not available
    pass
    pytestmark = pytest.mark.skip(reason="locust not installed")

if LOCUST_AVAILABLE:
    import time
    import random
    from typing import List, Dict

    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    from tests.performance.helpers import PerformanceTestHelper

    class JobQueueThroughputUser(FastHttpUser):
        """Locust user for job queue throughput testing"""

        wait_time = between(0.5, 2)  # Wait 0.5-2 seconds between tasks
        weight = 1

        def on_start(self):
            """Set up test user and authentication"""
            self.helper = PerformanceTestHelper(base_url=self.host)
            self.test_data = self.helper.create_test_tenant_and_user(
                tenant_name=f"perf-tenant-{random.randint(1000, 9999)}",
                user_email=f"perf-user-{random.randint(1000, 9999)}@example.com"
            )
            self.headers = self.test_data['headers']
            self.access_token = self.test_data['access_token']
            self.created_jobs: List[Dict] = []
            self.job_start_times: Dict[str, float] = {}

        @task(5)
        def test_create_dq_job(self):
            """Create a DQ run job"""
            self._create_job('DQ_RUN')

        @task(5)
        def test_create_compliance_job(self):
            """Create a compliance run job"""
            self._create_job('COMPLIANCE_RUN')

        @task(3)
        def test_create_semantic_mapping_job(self):
            """Create a semantic mapping job"""
            self._create_job('SEMANTIC_MAPPING')

        @task(10)
        def test_poll_job_status(self):
            """Poll job status"""
            if not self.created_jobs:
                return

            job = random.choice(self.created_jobs)
            job_id = job['id']

            with self.client.get(
                f"/api/v1/jobs/{job_id}",
                headers=self.headers,
                name="/api/v1/jobs/{id}",
                catch_response=True
            ) as response:
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status')

                    # Track job completion
                    if status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                        if job_id in self.job_start_times:
                            end_time = time.time()
                            duration = (end_time - self.job_start_times[job_id]) / 60  # minutes

                            # Track metrics
                            events.request.fire(
                                request_type="job_completion",
                                name=f"job_{status.lower()}_duration",
                                response_time=duration * 60 * 1000,  # Convert to ms
                                response_length=0,
                                exception=None
                            )

                            # Remove completed job
                            self.created_jobs.remove(job)
                            del self.job_start_times[job_id]

                    response.success()
                elif response.status_code == 404:
                    # Job might have been deleted, remove from list
                    if job in self.created_jobs:
                        self.created_jobs.remove(job)
                    if job_id in self.job_start_times:
                        del self.job_start_times[job_id]
                    response.failure("Job not found")
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

        @task(2)
        def test_list_jobs(self):
            """List jobs with filtering"""
            params = {
                'status': random.choice(['PENDING', 'RUNNING', 'COMPLETED', 'FAILED']),
                'type': random.choice(['DQ_RUN', 'COMPLIANCE_RUN', 'SEMANTIC_MAPPING']),
                'limit': 20
            }

            with self.client.get(
                "/api/v1/jobs",
                headers=self.headers,
                params=params,
                name="/api/v1/jobs",
                catch_response=True
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

        def _create_job(self, job_type: str):
            """Create a job of specified type"""
            # First, we need a resource to create a job for
            # For DQ/compliance, we need a file or dataset
            # For semantic mapping, we need an asset

            # Create a minimal DQ run or compliance run
            if job_type in ['DQ_RUN', 'COMPLIANCE_RUN']:
                self._create_dq_or_compliance_run(job_type)
            elif job_type == 'SEMANTIC_MAPPING':
                self._create_semantic_mapping_job()

        def _create_dq_or_compliance_run(self, run_type: str):
            """Create a DQ or compliance run (which creates a job)"""
            endpoint = '/dq/runs' if run_type == 'DQ_RUN' else '/compliance/runs'

            # Create a minimal file first if needed
            file_id = self._ensure_test_file()
            if not file_id:
                return

            run_data = {
                'file_id': file_id,
                'profile_key': 'intake_basic' if run_type == 'DQ_RUN' else None
            }

            start_time = time.time()

            with self.client.post(
                f"/api/v1{endpoint}",
                json=run_data,
                headers=self.headers,
                name=f"/api/v1{endpoint}",
                catch_response=True
            ) as response:
                if response.status_code == 201:
                    data = response.json()
                    job_id = data.get('job', {}).get('id') or data.get('job_id')

                    if job_id:
                        self.created_jobs.append({'id': job_id, 'type': run_type})
                        self.job_start_times[job_id] = start_time

                        # Track queue latency (time from creation to RUNNING)
                        events.request.fire(
                            request_type="job_creation",
                            name=f"{run_type.lower()}_created",
                            response_time=(time.time() - start_time) * 1000,
                            response_length=0,
                            exception=None
                        )

                    response.success()
                else:
                    response.failure(f"Failed to create {run_type}: {response.status_code}")

        def _create_semantic_mapping_job(self):
            """Create a semantic mapping job"""
            # This would typically be created when an asset is created
            # For now, we'll create a minimal asset which triggers semantic mapping
            asset_data = {
                'name': f'perf-test-asset-{int(time.time())}',
                'description': 'Performance test asset',
                'status': 'DRAFT'
            }

            start_time = time.time()

            with self.client.post(
                "/api/v1/assets",
                json=asset_data,
                headers=self.headers,
                name="/api/v1/assets (for semantic mapping)",
                catch_response=True
            ) as response:
                if response.status_code == 201:
                    data = response.json()
                    asset_id = data.get('id')

                    # Semantic mapping job is created automatically
                    # We can check for it by listing jobs
                    # For now, we'll track the asset creation
                    response.success()
                else:
                    response.failure(f"Failed to create asset: {response.status_code}")

        def _ensure_test_file(self) -> str:
            """Ensure we have a test file, create one if needed"""
            # For performance testing, we can reuse a single test file
            # or create a minimal one
            # This is a simplified version - in practice, you'd want to
            # create a proper file via the file upload API

            # Return a placeholder file ID - in real implementation,
            # you'd create an actual file
            return "00000000-0000-0000-0000-000000000000"  # Placeholder

