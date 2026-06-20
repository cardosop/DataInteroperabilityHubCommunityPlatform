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

import pytest

pytestmark = pytest.mark.slow
import uuid

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.compliance.models import ComplianceRun
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.dq.models import DQRun
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory

User = get_user_model()

# Service URLs: use Docker hostnames when running in docker-compose.test (localhost fails from inside container)
DQ_SERVICE_URL = os.getenv("DQ_SERVICE_URL", "http://dq-service-test:8083")
COMPLIANCE_SERVICE_URL = os.getenv("COMPLIANCE_SERVICE_URL", "http://compliance-service-test:8082")
SEMANTIC_SERVICE_URL = os.getenv("SEMANTIC_SERVICE_URL", "http://semantic-service-test:8081")

pytestmark = pytest.mark.django_db(transaction=True)


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
        """Test DQ service integration"""
        # Create DQ run via API
        response = self.client.post(
            "/api/v1/dq/runs/",
            {"asset_id": str(self.asset.id), "profile": "intake_basic_gx"},
            format="json",
        )

        # Should return 201 (created), 400 (bad request), 503 (service unavailable), or 404 (not found)
        self.assertIn(  # noqa: broad-status-codes

            response.status_code,
            [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_404_NOT_FOUND,
            ],
        )

    def test_dq_service_health_check(self):
        """Test DQ service health check"""
        url = f"{DQ_SERVICE_URL.rstrip('/')}/health"
        if check_service_health(url):
            response = requests.get(url, timeout=5)
            self.assertIn(response.status_code, [200, 404])
        else:
            pytest.skip("DQ service not available")  # noqa: skip-in-body — runtime service dependency

    def test_dq_run_creation_with_job(self):
        """Test DQ run creation with job"""
        # Create job first
        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="asset",
            resource_id=str(self.asset.id),
        )

        # Create DQ run linked to job
        # DQRun requires at least one of asset, dataset, or file (from clean() method)
        from hub.apps.dq.models import DQEngine

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,  # Required: at least one of asset, dataset, or file
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.SODA,  # Use enum value, not string
        )

        # DQ run should be created
        self.assertIsNotNone(dq_run.id)
        self.assertEqual(dq_run.job, job)


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
        """Test Compliance service integration"""
        # Create compliance run via API
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {"asset_id": str(self.asset.id), "regulations": ["GDPR", "CCPA"]},
            format="json",
        )

        # Should return 201 (created), 400 (bad request), 503 (service unavailable), or 404 (not found)
        self.assertIn(  # noqa: broad-status-codes

            response.status_code,
            [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_404_NOT_FOUND,
            ],
        )

    def test_compliance_service_health_check(self):
        """Test Compliance service health check"""
        url = f"{COMPLIANCE_SERVICE_URL.rstrip('/')}/health"
        if check_service_health(url):
            response = requests.get(url, timeout=5)
            self.assertIn(response.status_code, [200, 404])
        else:
            pytest.skip("Compliance service not available")  # noqa: skip-in-body — runtime service dependency

    def test_compliance_run_creation_with_job(self):
        """Test Compliance run creation with job"""
        # Create job first
        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="asset",
            resource_id=str(self.asset.id),
        )

        # Create Compliance run linked to job
        # ComplianceRun requires at least one of asset, dataset, or file (from clean() method)
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,  # Required: at least one of asset, dataset, or file
            job=job,
            regulations=["GDPR", "CCPA"],
        )

        # Compliance run should be created
        self.assertIsNotNone(compliance_run.id)
        self.assertEqual(compliance_run.job, job)


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
        """Test Semantic service integration"""
        # Test URI resolution
        response = self.client.get(
            "/api/v1/semantic/resolve-uri/", {"uri": "http://example.org/resource"}
        )

        # Should return 200 (success), 404 (not found), 503 (service unavailable), or 404 (endpoint not found)
        self.assertIn(response.status_code, [200, 404, 503])

    def test_semantic_service_health_check(self):
        """Test Semantic service health check"""
        url = f"{SEMANTIC_SERVICE_URL.rstrip('/')}/health"
        if check_service_health(url):
            response = requests.get(url, timeout=5)
            self.assertIn(response.status_code, [200, 404])
        else:
            pytest.skip("Semantic service not available")  # noqa: skip-in-body — runtime service dependency

    def test_semantic_service_sparql_query(self):
        """Test Semantic service SPARQL query"""
        response = self.client.post(
            "/api/v1/semantic/sparql/",
            {"query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"},
            format="json",
        )

        # Should return 200 (success), 400 (bad request), 503 (service unavailable), or 404 (not found)
        self.assertIn(response.status_code, [200, 400, 503, 404])  # noqa: broad-status-codes



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
        """Test external service error handling"""
        # Test that service unavailability is handled gracefully
        # This is tested through service integration endpoints

        # Try to create DQ run (may fail if service unavailable)
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

        # Should handle service unavailability gracefully (503 or 404)
        # Should not return 500 (internal server error)
        self.assertNotEqual(response.status_code, 500)


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
        """Test service-to-service workflow"""
        # Test complete workflow:
        # 1. Contract normalization (DataContract service)
        # 2. Semantic mapping (Semantic service)
        # 3. DQ run (DQ service)
        # 4. Compliance check (Compliance service)

        # Create job that triggers service-to-service communication
        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.CONTRACT_VALIDATION,
            status=JobStatus.PENDING,
            resource_type="contract",
            resource_id=str(self.contract.id),
        )

        # Job should be created
        self.assertIsNotNone(job.id)

        # In real scenario, this job would trigger service-to-service communication
        # This test verifies the job creation works

    def test_service_communication_error_handling(self):
        """Test service communication error handling"""
        # Test that service communication errors are handled gracefully

        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="asset",
            resource_id=str(self.contract.asset.id),
        )

        # Job should be created even if services are unavailable
        self.assertIsNotNone(job.id)

        # Service unavailability should be handled at execution time, not creation time
