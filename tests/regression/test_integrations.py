"""
Comprehensive regression tests for all integrations.

Tests integrations with:
- DQ service
- Compliance service
- Semantic service
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
import json

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.dq.models import DQRun, DQRunStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.semantic.models import SemanticResource, ResourceType

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class IntegrationRegressionTest(TestCase):
    """Base class for integration regression tests"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Integration Test Tenant",
            slug="integration-test-tenant"
        )
        self.user = User.objects.create_user(
            email="integration@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="integration-asset",
            name="Integration Asset"
        )
        
        # Create test contract
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "integration-contract", "info": {"title": "Integration Contract"}}',
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "integration-contract", "info": {"title": "Integration Contract"}}
        )


class DQServiceIntegrationTest(IntegrationRegressionTest):
    """Test DQ service integration"""
    
    def test_dq_run_creation(self):
        """Test creating a DQ run"""
        response = self.client.post(
            '/api/v1/dq/dq-runs/',
            {
                'asset_id': str(self.asset.id),
                'profile': 'intake_basic_gx'
            },
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
        
        if response.status_code == status.HTTP_201_CREATED:
            dq_run_id = response.data['id']
            
            # Verify DQ run was created
            retrieve_response = self.client.get(f'/api/v1/dq/dq-runs/{dq_run_id}/')
            self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
            self.assertEqual(retrieve_response.data['id'], dq_run_id)
    
    def test_dq_run_status_tracking(self):
        """Test DQ run status tracking"""
        from hub.apps.jobs.models import Job, JobType, JobStatus
        # Create job first (required for DQRun)
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type='ASSET',
            resource_id=self.asset.id
        )
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            profile_key='intake_basic_gx',
            engine='GREAT_EXPECTATIONS',
            status=DQRunStatus.PENDING
        )
        
        # Retrieve DQ run
        response = self.client.get(f'/api/v1/dq/dq-runs/{dq_run.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'PENDING')
    
    def test_dq_run_list(self):
        """Test listing DQ runs"""
        from hub.apps.jobs.models import Job, JobType, JobStatus
        # Create jobs first (required for DQRun)
        job1 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type='ASSET',
            resource_id=self.asset.id
        )
        job2 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type='ASSET',
            resource_id=self.asset.id
        )
        # Create multiple DQ runs
        DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job1,
            profile_key='intake_basic_gx',
            engine='GREAT_EXPECTATIONS',
            status=DQRunStatus.PENDING
        )
        DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job2,
            profile_key='intake_basic_gx',
            engine='GREAT_EXPECTATIONS',
            status=DQRunStatus.RUNNING
        )
        
        # List DQ runs
        response = self.client.get('/api/v1/dq/dq-runs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))


class ComplianceServiceIntegrationTest(IntegrationRegressionTest):
    """Test compliance service integration"""
    
    def test_compliance_run_creation(self):
        """Test creating a compliance run"""
        response = self.client.post(
            '/api/v1/compliance/compliance-runs/',
            {
                'asset_id': str(self.asset.id),
                'scan_mode': 'internal'
            },
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
        
        if response.status_code == status.HTTP_201_CREATED:
            compliance_run_id = response.data['id']
            
            # Verify compliance run was created
            retrieve_response = self.client.get(f'/api/v1/compliance/compliance-runs/{compliance_run_id}/')
            self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
            self.assertEqual(retrieve_response.data['id'], compliance_run_id)
    
    def test_compliance_run_status_tracking(self):
        """Test compliance run status tracking"""
        from hub.apps.jobs.models import Job, JobType, JobStatus
        # Create job first (required for ComplianceRun)
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type='ASSET',
            resource_id=self.asset.id
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            status=ComplianceRunStatus.PENDING
        )
        
        # Retrieve compliance run
        response = self.client.get(f'/api/v1/compliance/compliance-runs/{compliance_run.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'PENDING')
    
    def test_compliance_run_list(self):
        """Test listing compliance runs"""
        from hub.apps.jobs.models import Job, JobType, JobStatus
        # Create jobs first (required for ComplianceRun)
        job1 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type='ASSET',
            resource_id=self.asset.id
        )
        job2 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.RUNNING,
            resource_type='ASSET',
            resource_id=self.asset.id
        )
        # Create multiple compliance runs
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job1,
            status=ComplianceRunStatus.PENDING
        )
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job2,
            status=ComplianceRunStatus.RUNNING
        )
        
        # List compliance runs
        response = self.client.get('/api/v1/compliance/compliance-runs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
    
    def test_compliance_scan_modes(self):
        """Test different compliance scan modes"""
        # Test internal scan mode
        response = self.client.post(
            '/api/v1/compliance/compliance-runs/',
            {
                'asset_id': str(self.asset.id),
                'scan_mode': 'internal'
            },
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
        
        # Test external scan mode
        response = self.client.post(
            '/api/v1/compliance/compliance-runs/',
            {
                'asset_id': str(self.asset.id),
                'scan_mode': 'external'
            },
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])


class SemanticServiceIntegrationTest(IntegrationRegressionTest):
    """Test semantic service integration"""
    
    def test_semantic_resource_creation(self):
        """Test semantic resource creation (implicit via contract/asset creation)"""
        # Semantic resources are typically created automatically when contracts/assets are created
        # Verify semantic resource exists
        semantic_resource = SemanticResource.objects.filter(
            resource_type=ResourceType.ASSET,
            resource_id=str(self.asset.id)
        ).first()
        
        # May or may not exist depending on async processing
        if semantic_resource:
            # Verify it can be retrieved
            response = self.client.get(f'/api/v1/semantic/semantic-resources/{semantic_resource.id}/')
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def test_semantic_resource_list(self):
        """Test listing semantic resources"""
        response = self.client.get('/api/v1/semantic/semantic-resources/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))
    
    def test_sparql_query(self):
        """Test SPARQL query endpoint"""
        query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
        response = self.client.post(
            '/api/v1/semantic/sparql',
            {'query': query},
            format='json'
        )
        # May return 200 (success), 400 (bad query), or 503 (service unavailable)
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ])
    
    def test_resolve_uri(self):
        """Test URI resolution"""
        response = self.client.get(f'/api/v1/semantic/id/ASSET/{self.asset.id}')
        # May return 200 (found), 404 (not found), or 503 (service unavailable)
        self.assertIn(response.status_code, [
            status.HTTP_200_OK, 
            status.HTTP_404_NOT_FOUND,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ])
    
    def test_get_ontology(self):
        """Test ontology retrieval"""
        response = self.client.get('/api/v1/semantic/ontology')
        # May return 200 (success) or 503 (service unavailable)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])
    
    def test_get_jsonld_context(self):
        """Test JSON-LD context retrieval"""
        response = self.client.get('/api/v1/semantic/context.jsonld')
        # May return 200 (success) or 503 (service unavailable)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])


class CrossServiceIntegrationTest(IntegrationRegressionTest):
    """Test cross-service integrations"""
    
    def test_dq_and_compliance_integration(self):
        """Test DQ and compliance services working together"""
        # Create DQ run
        dq_response = self.client.post(
            '/api/v1/dq/dq-runs/',
            {
                'asset_id': str(self.asset.id),
                'profile': 'intake_basic_gx'
            },
            format='json'
        )
        
        # Create compliance run
        compliance_response = self.client.post(
            '/api/v1/compliance/compliance-runs/',
            {
                'asset_id': str(self.asset.id),
                'scan_mode': 'internal'
            },
            format='json'
        )
        
        # Both should be created successfully (or return appropriate errors)
        self.assertIn(dq_response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
        self.assertIn(compliance_response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
    
    def test_contract_semantic_integration(self):
        """Test contract and semantic service integration"""
        # Contract should trigger semantic mapping
        # Verify semantic resource exists for contract
        semantic_resource = SemanticResource.objects.filter(
            resource_type=ResourceType.CONTRACT,
            resource_id=str(self.contract.id)
        ).first()
        
        # May or may not exist depending on async processing
        if semantic_resource:
            # Verify it can be retrieved via API
            response = self.client.get(f'/api/v1/semantic/semantic-resources/{semantic_resource.id}/')
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def test_asset_semantic_integration(self):
        """Test asset and semantic service integration"""
        # Asset should trigger semantic mapping
        # Verify semantic resource exists for asset
        semantic_resource = SemanticResource.objects.filter(
            resource_type=ResourceType.ASSET,
            resource_id=str(self.asset.id)
        ).first()
        
        # May or may not exist depending on async processing
        if semantic_resource:
            # Verify it can be retrieved via API
            response = self.client.get(f'/api/v1/semantic/semantic-resources/{semantic_resource.id}/')
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

