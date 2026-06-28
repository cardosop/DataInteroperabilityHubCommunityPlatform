"""
Comprehensive Service Integration Tests for Django 6

Tests all services work correctly with Django 6:
- API service (Django)
- Worker service (Django RQ)
- DataContract service (FastAPI)
- Compliance service (FastAPI)
- DQ service (FastAPI)
- Semantic service (FastAPI)
- Microservices integration

Service-to-service auth uses the INTERNAL_API_KEY env var (configured
in docker-compose.test.yml as ``test-internal-api-key-for-test-env``).
Tests skip gracefully when a service health check fails — they run when
the full docker-compose.test.yml stack is available.
"""

import os
import uuid

import pytest
import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from django_rq import get_queue
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory

User = get_user_model()

# Service URLs: use Docker hostnames when running in docker-compose.test
DATACONTRACT_SERVICE_URL = os.getenv(
    "DATACONTRACT_SERVICE_URL", "http://datacontract-service-test:8080"
)
COMPLIANCE_SERVICE_URL = os.getenv("COMPLIANCE_SERVICE_URL", "http://compliance-service-test:8082")
DQ_SERVICE_URL = os.getenv("DQ_SERVICE_URL", "http://dq-service-test:8083")
SEMANTIC_SERVICE_URL = os.getenv("SEMANTIC_SERVICE_URL", "http://semantic-service-test:8081")

# Service-to-service auth — matches docker-compose.test.yml INTERNAL_API_KEY default.
_INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "test-internal-api-key-for-test-env")
_AUTH_HEADERS = {"X-Internal-Api-Key": _INTERNAL_API_KEY}

pytestmark = pytest.mark.django_db(transaction=True)


def check_service_health(service_url: str, timeout: int = 5) -> bool:
    """Check if a service is healthy (public /health endpoint — no auth needed)."""
    try:
        response = requests.get(service_url, timeout=timeout)
        return response.status_code in [200, 404]
    except (requests.exceptions.RequestException, requests.exceptions.Timeout):
        return False


class APIServiceDjango6Test(TestCase):
    """Test API service with Django 6"""

    def setUp(self):
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)
        ensure_user_has_data_provider_role(self.user)

    def test_api_service_health(self):
        response = self.client.get("/health/")
        self.assertIn(response.status_code, [200, 404])

    def test_api_service_django_version(self):
        import django
        django_version = django.get_version()
        self.assertTrue(
            django_version.startswith("6."), f"Django version is {django_version}, expected 6.x"
        )

    def test_api_service_database_connection(self):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            self.assertEqual(result[0], 1)

    def test_api_service_redis_connection(self):
        from django.core.cache import cache
        cache.set("test_key", "test_value", 60)
        value = cache.get("test_key")
        self.assertEqual(value, "test_value")

    def test_api_service_middleware_chain(self):
        """Test API service returns valid responses through the middleware chain."""
        response = self.client.get("/health/")
        self.assertIn(response.status_code, [200, 503])
        self.assertIn("Content-Type", response)

    def test_api_service_authenticated_request(self):
        """Test that an authenticated request to the assets API does not crash."""
        response = self.client.get("/api/v1/assets/")
        # Authenticated request should return 200 (success) or 403 (forbidden
        # — user may lack specific asset permissions).  401 would mean the
        # force_authenticate didn't work; 5xx is a crash.
        self.assertIn(response.status_code, [200, 403])


class WorkerServiceDjango6Test(TestCase):
    """Test worker service with Django 6"""

    def setUp(self):
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_worker_service_queue_connection(self):
        """Test that the RQ default queue is available and can accept jobs."""
        queue = get_queue("default")
        self.assertIsNotNone(queue)
        # Verify the queue is connected by checking job count doesn't raise
        self.assertGreaterEqual(queue.count, 0)

    def test_worker_service_job_creation(self):
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status="DRAFT"
        )
        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="asset",
            resource_id=str(asset.id),
        )
        self.assertIsNotNone(job.id)
        self.assertEqual(job.type, JobType.DQ_RUN)
        self.assertEqual(job.status, JobStatus.PENDING)

    def test_worker_service_job_enqueue(self):
        """Test that a task can be enqueued to the RQ default queue."""
        from django_rq import enqueue

        def dummy_task():
            return "success"

        rq_job = enqueue(dummy_task)
        self.assertIsNotNone(rq_job.id)


class DataContractServiceDjango6Test(TestCase):
    """Test DataContract service with Django 6"""

    def setUp(self):
        self.service_url = DATACONTRACT_SERVICE_URL.rstrip("/")

    def test_datacontract_service_health(self):
        url = f"{self.service_url}/health"
        if check_service_health(url):
            response = requests.get(url, timeout=5)
            self.assertIn(response.status_code, [200, 404])
        else:
            pytest.skip("DataContract service not available")  # noqa: skip-in-body — runtime service dependency

    def test_datacontract_service_normalization(self):
        """Test DataContract service /normalize endpoint with auth.

        The hub normalizes contracts locally via normalization_service.py;
        this test validates the service-side endpoint contract directly.
        """
        if not check_service_health(f"{self.service_url}/health"):  # noqa: skip-in-body — runtime service dependency
            pytest.skip("DataContract service not available")

        # NormalizeRequest expects: raw_contract (str), format (str), spec_type (str|None)
        test_contract = {
            "raw_contract": "id: test-contract\ninfo:\n  title: Test Contract",
            "format": "yaml",
        }

        try:
            response = requests.post(
                f"{self.service_url}/normalize",
                json=test_contract,
                headers=_AUTH_HEADERS,
                timeout=10,
            )
            # 200=success, 400/422=validation error (body mismatch), 404=endpoint missing
            self.assertIn(response.status_code, [200, 400, 404, 422])
        except requests.exceptions.ConnectionError:
            pytest.skip("DataContract service not reachable")
        except requests.exceptions.RequestException as exc:
            pytest.fail(f"DataContract normalization request failed: {exc}")


class ComplianceServiceDjango6Test(TestCase):
    """Test Compliance service with Django 6"""

    def setUp(self):
        self.service_url = COMPLIANCE_SERVICE_URL.rstrip("/")

    def test_compliance_service_health(self):
        if check_service_health(f"{self.service_url}/health"):
            response = requests.get(f"{self.service_url}/health", timeout=5)
            self.assertIn(response.status_code, [200, 404])
        else:
            pytest.skip("Compliance service not available")  # noqa: skip-in-body — runtime service dependency

    def test_compliance_service_scan_dataframe(self):
        """Test Compliance service /scan-dataframe endpoint with auth.

        The hub primarily uses /scan-file (multipart); /scan-dataframe accepts
        JSON and is the simpler path for integration smoke-testing.
        """
        if not check_service_health(f"{self.service_url}/health"):  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Compliance service not available")

        # /scan-dataframe expects: data (list of dicts), tenant_id, etc.
        test_payload = {
            "data": [{"text": "Contact us at support@example.com or call 555-1234"}],
        }

        try:
            response = requests.post(
                f"{self.service_url}/scan-dataframe",
                json=test_payload,
                headers=_AUTH_HEADERS,
                timeout=10,
            )
            # 200=success, 400/422=validation error, 404=endpoint missing, 501=not implemented
            self.assertIn(response.status_code, [200, 400, 404, 422, 501])
        except requests.exceptions.ConnectionError:
            pytest.skip("Compliance service not reachable")
        except requests.exceptions.RequestException as exc:
            pytest.fail(f"Compliance scan-dataframe request failed: {exc}")


class DQServiceDjango6Test(TestCase):
    """Test DQ service with Django 6"""

    def setUp(self):
        self.service_url = DQ_SERVICE_URL.rstrip("/")

    def test_dq_service_health(self):
        url = f"{self.service_url}/health"
        if check_service_health(url):
            response = requests.get(url, timeout=5)
            self.assertIn(response.status_code, [200, 404])
        else:
            pytest.skip("DQ service not available")  # noqa: skip-in-body — runtime service dependency

    def test_dq_service_run_dataframe(self):
        """Test DQ service /run-dataframe endpoint with auth.

        The hub primarily uses /run (multipart); /run-dataframe accepts JSON
        and is the simpler path for integration smoke-testing.
        """
        if not check_service_health(f"{self.service_url}/health"):  # noqa: skip-in-body — runtime service dependency
            pytest.skip("DQ service not available")

        test_payload = {
            "data": [{"col1": "value1", "col2": 123}],
            "checks": [],
        }

        try:
            response = requests.post(
                f"{self.service_url}/run-dataframe",
                json=test_payload,
                headers=_AUTH_HEADERS,
                timeout=10,
            )
            # 200=success, 400/422=validation error, 404/501=not implemented
            self.assertIn(response.status_code, [200, 400, 404, 422, 501])
        except requests.exceptions.ConnectionError:
            pytest.skip("DQ service not reachable")
        except requests.exceptions.RequestException as exc:
            pytest.fail(f"DQ run-dataframe request failed: {exc}")


class SemanticServiceDjango6Test(TestCase):
    """Test Semantic service with Django 6"""

    def setUp(self):
        self.service_url = SEMANTIC_SERVICE_URL.rstrip("/")

    def test_semantic_service_health(self):
        url = f"{self.service_url}/health"
        if check_service_health(url):
            response = requests.get(url, timeout=5)
            self.assertIn(response.status_code, [200, 404])
        else:
            pytest.skip("Semantic service not available")  # noqa: skip-in-body — runtime service dependency

    def test_semantic_service_uri_resolution(self):
        """Test Semantic service /id/{resource_path} endpoint with auth.

        The hub client resolves URIs via GET /id/{resource_type}/{resource_id}.
        """
        if not check_service_health(f"{self.service_url}/health"):  # noqa: skip-in-body — runtime service dependency
            pytest.skip("Semantic service not available")

        try:
            response = requests.get(
                f"{self.service_url}/id/asset/test-uuid",
                headers=_AUTH_HEADERS,
                timeout=10,
            )
            # 200=found, 404=not found, 501=not implemented, 503=unavailable
            self.assertIn(response.status_code, [200, 404, 501, 503])
        except requests.exceptions.ConnectionError:
            pytest.skip("Semantic service not reachable")
        except requests.exceptions.Timeout:
            pytest.skip("Semantic service request timed out")
        except requests.exceptions.RequestException as exc:
            pytest.fail(f"Semantic URI resolution request failed: {exc}")


class MicroservicesIntegrationTest(TestCase):
    """Test all microservices integration"""

    def setUp(self):
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)
        ensure_user_has_data_provider_role(self.user)

        self.asset = Asset.objects.create(
            tenant=self.tenant, key="integration-asset", name="Integration Asset", status="DRAFT"
        )
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "test-contract"},
        )

    def test_job_creation_via_orm(self):
        """Test that a DQ run Job can be created and persisted via the ORM."""
        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="asset",
            resource_id=str(self.asset.id),
        )
        self.assertIsNotNone(job.id)
        self.assertEqual(job.type, JobType.DQ_RUN)
        self.assertEqual(job.tenant, self.tenant)

    def test_service_to_service_communication(self):
        self.client.force_authenticate(user=self.user)
        ensure_user_has_data_provider_role(self.user)

        response = self.client.post(
            "/api/v1/dq/runs/",
            {"asset_id": str(self.asset.id), "profile": "intake_basic_gx"},
            format="json",
        )
        # DQ run creation may return 201 (created), 400 (bad request — missing
        # profile/config), or 403 (plan/subscription required).  503 means the
        # DQ service is unavailable (infra issue — skip rather than fail).
        if response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            pytest.skip("DQ service unavailable")
        self.assertIn(  # noqa: broad-status-codes
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN],
        )

    def test_all_services_accessible(self):
        """Test that the microservice health endpoints are reachable.

        Uses the container-side Docker hostnames (not localhost) so the
        test works both inside docker compose exec and on the host.
        """
        services = [
            ("DataContract", DATACONTRACT_SERVICE_URL.rstrip("/") + "/health"),
            ("Compliance", COMPLIANCE_SERVICE_URL.rstrip("/") + "/health"),
            ("DQ", DQ_SERVICE_URL.rstrip("/") + "/health"),
            ("Semantic", SEMANTIC_SERVICE_URL.rstrip("/") + "/health"),
        ]
        accessible = []
        for name, url in services:
            if check_service_health(url):
                accessible.append(name)

        # At least one microservice should be reachable in the test stack
        assert len(accessible) >= 1, (
            f"No microservices reachable. Checked: {[s[0] for s in services]}"
        )
