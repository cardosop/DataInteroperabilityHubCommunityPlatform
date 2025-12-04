"""
T.18: Load test API endpoints (target: 99.5% availability)

Tests API endpoint availability and error rates under load.
Targets:
- 99.5% availability (error rate ≤ 0.5%)
- P95 API response time ≤ 300ms for typical CRUD endpoints
- 30-50 RPS sustained throughput

Note: This file requires locust to be installed. It will be skipped if locust is not available.
"""
import pytest

# Skip if locust is not installed
try:
    from locust import HttpUser, task, between, events
    from locust.contrib.fasthttp import FastHttpUser
    LOCUST_AVAILABLE = True
except ImportError:
    LOCUST_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="locust not installed - install with: pip install locust")

if LOCUST_AVAILABLE:
    import time
    import random
    
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    from tests.performance.helpers import PerformanceTestHelper
    
    
    class APIEndpointsAvailabilityUser(FastHttpUser):
        """Locust user for API endpoint availability testing"""
        
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
            self.created_resources = {
                'assets': [],
                'contracts': [],
                'files': [],
                'datasets': []
            }
        
        # Read operations (70% of traffic)
        @task(7)
        def test_get_assets(self):
            """GET /assets - List assets"""
            self._test_endpoint('GET', '/api/v1/assets', name='GET /assets')
        
        @task(5)
        def test_get_asset_detail(self):
            """GET /assets/{id} - Get asset detail"""
            if self.created_resources['assets']:
                asset_id = random.choice(self.created_resources['assets'])
                self._test_endpoint('GET', f'/api/v1/assets/{asset_id}', name='GET /assets/{id}')
            else:
                self.test_get_assets()
        
        @task(5)
        def test_get_contracts(self):
            """GET /contracts - List contracts"""
            self._test_endpoint('GET', '/api/v1/contracts', name='GET /contracts')
        
        @task(4)
        def test_get_contract_detail(self):
            """GET /contracts/{id} - Get contract detail"""
            if self.created_resources['contracts']:
                contract_id = random.choice(self.created_resources['contracts'])
                self._test_endpoint('GET', f'/api/v1/contracts/{contract_id}', name='GET /contracts/{id}')
            else:
                self.test_get_contracts()
        
        @task(4)
        def test_get_jobs(self):
            """GET /jobs - List jobs"""
            self._test_endpoint('GET', '/api/v1/jobs', name='GET /jobs')
        
        @task(3)
        def test_get_job_detail(self):
            """GET /jobs/{id} - Get job detail"""
            # Jobs are created by other operations, so we'll just try to list
            self.test_get_jobs()
        
        @task(3)
        def test_get_files(self):
            """GET /files - List files"""
            self._test_endpoint('GET', '/api/v1/files', name='GET /files')
        
        @task(2)
        def test_get_datasets(self):
            """GET /datasets - List datasets"""
            self._test_endpoint('GET', '/api/v1/datasets', name='GET /datasets')
        
        # Write operations (20% of traffic)
        @task(2)
        def test_create_asset(self):
            """POST /assets - Create asset"""
            asset_data = {
                'name': f'perf-asset-{int(time.time())}-{random.randint(1000, 9999)}',
                'description': 'Performance test asset',
                'status': 'DRAFT'
            }
            response = self._test_endpoint('POST', '/api/v1/assets', json=asset_data, name='POST /assets')
            if response and response.status_code == 201:
                data = response.json()
                if 'id' in data:
                    self.created_resources['assets'].append(data['id'])
        
        @task(1)
        def test_update_asset(self):
            """PATCH /assets/{id} - Update asset"""
            if self.created_resources['assets']:
                asset_id = random.choice(self.created_resources['assets'])
                update_data = {
                    'description': f'Updated at {time.time()}'
                }
                self._test_endpoint('PATCH', f'/api/v1/assets/{asset_id}', json=update_data, name='PATCH /assets/{id}')
        
        @task(1)
        def test_create_contract(self):
            """POST /contracts - Create contract"""
            contract_data = {
                'name': f'perf-contract-{int(time.time())}-{random.randint(1000, 9999)}',
                'version': '1.0.0',
                'spec': {
                    'type': 'datacontract',
                    'version': '0.8.0',
                    'id': f'perf-contract-{int(time.time())}',
                    'info': {
                        'title': 'Performance Test Contract',
                        'version': '1.0.0'
                    }
                }
            }
            response = self._test_endpoint('POST', '/api/v1/contracts', json=contract_data, name='POST /contracts')
            if response and response.status_code == 201:
                data = response.json()
                if 'id' in data:
                    self.created_resources['contracts'].append(data['id'])
        
        @task(1)
        def test_create_dq_run(self):
            """POST /dq-runs - Create DQ run"""
            # This requires a file, so we'll skip if no files available
            # In a real scenario, we'd create a file first
            dq_data = {
                'profile_key': 'intake_basic',
                'engine': 'great_expectations'
            }
            self._test_endpoint('POST', '/api/v1/dq-runs', json=dq_data, name='POST /dq-runs', allow_errors=True)
        
        # File operations (10% of traffic)
        @task(1)
        def test_init_file_upload(self):
            """POST /files/init - Initialize file upload"""
            file_data = {
                'name': f'perf-file-{int(time.time())}-{random.randint(1000, 9999)}.csv',
                'content_type': 'text/csv',
                'size_bytes': random.randint(1024, 10 * 1024 * 1024)  # 1KB to 10MB
            }
            response = self._test_endpoint('POST', '/api/v1/files/init', json=file_data, name='POST /files/init')
            if response and response.status_code == 201:
                data = response.json()
                if 'id' in data:
                    self.created_resources['files'].append(data['id'])
        
        def _test_endpoint(self, method: str, path: str, json: dict = None, name: str = None, allow_errors: bool = False):
            """Test an API endpoint and track availability metrics"""
            endpoint_name = name or path
            start_time = time.time()
            
            try:
                if method == 'GET':
                    response = self.client.get(path, headers=self.headers, name=endpoint_name, catch_response=True)
                elif method == 'POST':
                    response = self.client.post(path, json=json or {}, headers=self.headers, name=endpoint_name, catch_response=True)
                elif method == 'PATCH':
                    response = self.client.patch(path, json=json or {}, headers=self.headers, name=endpoint_name, catch_response=True)
                elif method == 'DELETE':
                    response = self.client.delete(path, headers=self.headers, name=endpoint_name, catch_response=True)
                else:
                    return None
                
                response_time = (time.time() - start_time) * 1000  # ms
                
                # Track response time
                if response_time > 300:  # P95 target
                    events.request.fire(
                        request_type="api_slow",
                        name=f"{endpoint_name}_slow",
                        response_time=response_time,
                        response_length=0,
                        exception=None
                    )
                
                # Track error rates
                if response.status_code >= 500:
                    # Server error - counts against availability
                    if not allow_errors:
                        response.failure(f"Server error: {response.status_code}")
                    events.request.fire(
                        request_type="api_error",
                        name=f"{endpoint_name}_5xx",
                        response_time=response_time,
                        response_length=0,
                        exception=None
                    )
                elif response.status_code >= 400 and not allow_errors:
                    # Client error - might be expected in some cases
                    response.failure(f"Client error: {response.status_code}")
                else:
                    response.success()
                
                return response
                
            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                events.request.fire(
                    request_type="api_error",
                    name=f"{endpoint_name}_exception",
                    response_time=response_time,
                    response_length=0,
                    exception=e
                )
                raise
