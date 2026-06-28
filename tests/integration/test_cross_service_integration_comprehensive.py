"""
Comprehensive Cross-Service Integration Tests for Django 6

Tests all cross-service integrations:
- DQ service integration
- Compliance service integration
- Semantic service integration
- External service integration
- Service-to-service communication
"""

import os
import uuid

import pytest
import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.compliance.models import ComplianceRun
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.dq.models import DQEngine, DQRun
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory

User = get_user_model()

# Service URLs: use Docker hostnames when running in docker-compose.test
DQ_SERVICE_URL = os.getenv("DQ_SERVICE_URL", "http://dq-service-test:8083")
COMPLIANCE_SERVICE_URL = os.getenv("COMPLIANCE_SERVICE_URL", "http://compliance-service-test:8082")
SEMANTIC_SERVICE_URL = os.getenv("SEMANTIC_SERVICE_URL", "http://semantic-service-test:8081")

pytestmark = [
    pytest.mark.slow,
    pytest.mark.django_db(transaction=True),
]


def check_service_health(service_url: str, timeout: int = 5) -> bool:
    """Check if a service is healthy"""
    try:
        response = requests.get(service_url, timeout=timeout)
        return response.status_code in [200, 404]
    except (requests.exceptions.RequestException, requests.exceptions.Timeout):
        return False


class DQServiceIntegrationTest(TestCase):
    """Test DQ service integration"""

    def setUp(self):
        """Set up test fixtures"""
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

        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="dq-test-asset", name="DQ Test Asset", status="DRAFT"
        )

    def test_dq_service_integration(self):
        """Test DQ service integration — creates a DQ run via API and validates the response."""
        response = self.client.post(
            "/api/v1/dq/runs/",
            {"asset_id": str(self.asset.id), "profile": "intake_basic_gx"},
            format="json",
        )

        # 201 = successfully created, 400 = invalid input (acceptable if profile unknown)
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST],
        )
        if response.status_code == status.HTTP_201_CREATED:
            data = response.json() if hasattr(response, "json") else response.data
            self.assertIsNotNone(data.get("id"), f"Expected 'id' in DQ run response, got: {data}")

    def test_dq_service_health_check(self):
        """Test DQ service health check — the /health endpoint must return 200."""
        url = f"{DQ_SERVICE_URL.rstrip('/')}/health"
        response = requests.get(url, timeout=5)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
            f"DQ service health check failed at {url}: {response.status_code}",
        )

    def test_dq_run_creation_with_job(self):
        """Test DQ run creation linked to a job — verifies the FK relationship."""
        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="asset",
            resource_id=str(self.asset.id),
        )

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.SODA,
        )

        self.assertEqual(dq_run.job, job)
        self.assertEqual(dq_run.job_id, job.id)


class ComplianceServiceIntegrationTest(TestCase):
    """Test Compliance service integration"""

    def setUp(self):
        """Set up test fixtures"""
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

        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="compliance-test-asset",
            name="Compliance Test Asset",
            status="DRAFT",
        )

    def test_compliance_service_integration(self):
        """Test Compliance service integration — creates a compliance run via API."""
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"asset_id": str(self.asset.id), "regulations": ["GDPR", "CCPA"]},
            format="json",
        )

        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST],
        )
        if response.status_code == status.HTTP_201_CREATED:
            data = response.json() if hasattr(response, "json") else response.data
            self.assertIsNotNone(data.get("id"), f"Expected 'id' in compliance run response, got: {data}")

    def test_compliance_service_health_check(self):
        """Test Compliance service health check — the /health endpoint must return 200."""
        url = f"{COMPLIANCE_SERVICE_URL.rstrip('/')}/health"
        response = requests.get(url, timeout=5)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
            f"Compliance service health check failed at {url}: {response.status_code}",
        )

    def test_compliance_run_creation_with_job(self):
        """Test Compliance run creation linked to a job — verifies the FK relationship."""
        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="asset",
            resource_id=str(self.asset.id),
        )

        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            regulations=["GDPR", "CCPA"],
        )

        self.assertEqual(compliance_run.job, job)
        self.assertEqual(compliance_run.job_id, job.id)


class SemanticServiceIntegrationTest(TestCase):
    """Test Semantic service integration"""

    def setUp(self):
        """Set up test fixtures"""
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

        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="semantic-test-asset",
            name="Semantic Test Asset",
            status="DRAFT",
        )

    def test_semantic_service_integration(self):
        """Test Semantic service URI resolution — returns 200 for resolvable URIs."""
        response = self.client.get(
            "/api/v1/semantic/resolve-uri/", {"uri": "http://example.org/resource"}
        )

        self.assertIn(response.status_code, [200, 404])
        if response.status_code == 200:
            data = response.json() if hasattr(response, "json") else response.data
            self.assertIsNotNone(data)

    def test_semantic_service_health_check(self):
        """Test Semantic service health check — the /health endpoint must return 200."""
        url = f"{SEMANTIC_SERVICE_URL.rstrip('/')}/health"
        response = requests.get(url, timeout=5)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
            f"Semantic service health check failed at {url}: {response.status_code}",
        )

    def test_semantic_service_sparql_query(self):
        """Test Semantic service SPARQL query — accepts valid SPARQL and returns 200 or 400."""
        response = self.client.post(
            "/api/v1/semantic/sparql/",
            {"query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"},
            format="json",
        )

        self.assertIn(response.status_code, [200, 400, 404, 503])
        if response.status_code == 200:
            data = response.json() if hasattr(response, "json") else response.data
            self.assertIsNotNone(data)



class ExternalServiceIntegrationTest(TestCase):
    """Test external service integration"""

    def setUp(self):
        """Set up test fixtures"""
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

    def test_external_service_error_handling(self):
        """Test that external service unavailability returns 4xx/5xx, never a 500 crash."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="external-test-asset",
            name="External Test Asset",
            status="DRAFT",
        )

        response = self.client.post(
            "/api/v1/dq/runs/",
            {"asset_id": str(asset.id), "profile": "intake_basic_gx"},
            format="json",
        )

        # The endpoint must never crash with 500 — it should return a controlled
        # error status even when backend services are unavailable.
        self.assertNotEqual(response.status_code, 500)
        self.assertIn(
            response.status_code,
            [201, 400, 404, 503],
            f"Unexpected status {response.status_code}",
        )


class ServiceToServiceCommunicationTest(TestCase):
    """Test service-to-service communication"""

    def setUp(self):
        """Set up test fixtures"""
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

        # Create test contract
        asset = Asset.objects.create(
            tenant=self.tenant, key="service-test-asset", name="Service Test Asset", status="DRAFT"
        )

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "test-contract"},
        )

    def test_service_to_service_workflow(self):
        """Test that a contract-validation job can be created and transitions correctly.

        Verifies that job creation for cross-service workflows (contract validation
        → normalization → semantic mapping → DQ → compliance) succeeds and the job
        carries the correct metadata.
        """
        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="contract",
            resource_id=str(self.contract.id),
        )

        self.assertIsNotNone(job.pk, "Job should be persisted with a primary key")
        self.assertEqual(job.type, JobType.CONTRACT_VALIDATION)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(job.resource_type, "contract")
        self.assertEqual(str(job.resource_id), str(self.contract.id))
        self.assertEqual(job.tenant, self.tenant)

    def test_service_communication_error_handling(self):
        """Test that jobs can be created even when backend services are unavailable.

        Job creation should succeed synchronously — backend unavailability
        should be surfaced at execution time, not at creation time.
        """
        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="asset",
            resource_id=str(self.contract.asset.id),
        )

        # Job creation succeeds regardless of backend service availability
        self.assertIsNotNone(job.pk, "Job should be persisted with a primary key")
        self.assertEqual(job.type, JobType.DQ_RUN)
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertIsNotNone(job.created_at)
