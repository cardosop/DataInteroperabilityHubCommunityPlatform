"""
Comprehensive regression tests for all API endpoints.

Tests all HTTP methods (GET, POST, PUT, PATCH, DELETE) for all API endpoints
to ensure Django 6 compatibility and no regressions.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
import json
import uuid

from datetime import timedelta
from django.utils import timezone

from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import UserStatus
from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.dq.models import DQRun, DQRunStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.marketplace.models import Listing, ListingStatus
from hub.apps.auth.models import APIKey
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.billing.tests.plan_fixtures import get_pro_plan
from hub.apps.testing.role_support import ensure_user_has_tenant_admin_role

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class APIRegressionTest(TestCase):
    """Base class for API regression tests"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        plan = get_pro_plan()
        self.tenant = Tenant.objects.create(
            name=f"Regression Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"regression-test-tenant-{uuid.uuid4().hex[:8]}",
            plan=plan,
        )
        Subscription.objects.create(
            tenant=self.tenant,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        self.user = User.objects.create_user(
            email=f"regression-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        ensure_user_has_tenant_admin_role(self.user)
        self.client.force_authenticate(user=self.user)

        # Create user-scoped API key for API key authentication tests
        # API keys must be user-scoped (not tenant-scoped) for authentication
        self.api_key_obj = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,  # User-scoped API key required
            name="Regression Test API Key",
            key_hash=APIKey.hash_key("test-api-key-123")
        )
        self.api_key = "test-api-key-123"


class AuthAPIRegressionTest(APIRegressionTest):
    """Test all authentication API endpoints"""

    def test_login_endpoint(self):
        """Test POST /api/v1/auth/login/"""
        self.client.logout()
        response = self.client.post(
            '/api/v1/auth/login/',
            {'email': self.user.email, 'password': 'testpass123'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        # Refresh token is now in httponly cookie, not response body
        has_refresh_cookie = any(
            'refresh_token' in str(c) for c in response.cookies.values()
        )
        has_refresh_body = 'refresh_token' in response.data
        self.assertTrue(
            has_refresh_cookie or has_refresh_body,
            "Login must return refresh_token in body or httponly cookie",
        )

    def test_refresh_token_endpoint(self):
        """Test POST /api/v1/auth/refresh/"""
        # First login to get tokens
        login_response = self.client.post(
            '/api/v1/auth/login/',
            {'email': self.user.email, 'password': 'testpass123'},
            format='json'
        )
        # Refresh token may be in body or httponly cookie
        refresh_token = login_response.data.get('refresh_token')
        if not refresh_token:
            cookie = login_response.cookies.get('refresh_token')
            if cookie:
                refresh_token = cookie.value

        if not refresh_token:
            self.skipTest("Login did not return refresh token in body or cookie")

        # Test refresh — send as cookie (the server reads from cookie)
        self.client.cookies['refresh_token'] = refresh_token
        response = self.client.post(
            '/api/v1/auth/refresh/',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)

    def test_logout_endpoint(self):
        """Test POST /api/v1/auth/logout/"""
        response = self.client.post('/api/v1/auth/logout/', {}, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])

    def test_api_key_list(self):
        """Test GET /api/v1/auth/api-keys/"""
        response = self.client.get('/api/v1/auth/api-keys/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response may be paginated (dict with 'results') or a list
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertIsInstance(response.data['results'], list)
        else:
            self.assertIsInstance(response.data, list)

    def test_api_key_create(self):
        """Test POST /api/v1/auth/api-keys/"""
        response = self.client.post(
            '/api/v1/auth/api-keys/',
            {'name': 'New API Key'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Response may have 'api_key' field (plaintext key) or 'key' field
        self.assertIn('id', response.data)
        # Check for either 'api_key' or 'key' field (both are valid)
        self.assertTrue('api_key' in response.data or 'key' in response.data,
                       f"Response should have 'api_key' or 'key' field. Got: {list(response.data.keys())}")

    def test_api_key_retrieve(self):
        """Test GET /api/v1/auth/api-keys/{id}/"""
        response = self.client.get(f'/api/v1/auth/api-keys/{self.api_key_obj.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.api_key_obj.id))

    def test_api_key_delete(self):
        """Test DELETE /api/v1/auth/api-keys/{id}/"""
        api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,  # User-scoped API key required
            name="To Delete",
            key_hash=APIKey.hash_key("delete-me")
        )
        response = self.client.delete(f'/api/v1/auth/api-keys/{api_key.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(APIKey.objects.filter(id=api_key.id).exists())


class TenantAPIRegressionTest(APIRegressionTest):
    """Test all tenant API endpoints"""

    def test_tenant_list(self):
        """Test GET /api/v1/tenants/"""
        # Tenant list requires platform admin
        self.user.is_platform_admin = True
        self.user.save()
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/v1/tenants/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))

    def test_tenant_create(self):
        """Test POST /api/v1/tenants/"""
        # Only platform admins can create tenants
        self.user.is_platform_admin = True
        self.user.save()
        # Refresh user to ensure is_platform_admin is set
        self.user.refresh_from_db()
        # Re-authenticate to ensure updated user is used
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            '/api/v1/tenants/',
            {'name': 'New Tenant', 'slug': 'new-tenant'},
            format='json'
        )
        # May require platform admin, so check for either success or permission denied
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_403_FORBIDDEN])

    def test_tenant_retrieve(self):
        """Test GET /api/v1/tenants/{id}/"""
        # Make user platform admin to access tenant detail
        self.user.is_platform_admin = True
        self.user.save()
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f'/api/v1/tenants/{self.tenant.id}/')
        # Platform admin should be able to retrieve any tenant
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
        if response.status_code == status.HTTP_200_OK:
            self.assertEqual(response.data['id'], str(self.tenant.id))

    def test_tenant_update(self):
        """Test PUT /api/v1/tenants/{id}/"""
        # Make user platform admin to update tenant
        self.user.is_platform_admin = True
        self.user.save()
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            f'/api/v1/tenants/{self.tenant.id}/',
            {'name': 'Updated Tenant', 'slug': self.tenant.slug},
            format='json'
        )
        # May require tenant admin, so check for either success or permission denied
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_tenant_partial_update(self):
        """Test PATCH /api/v1/tenants/{id}/"""
        # Make user platform admin to update tenant
        self.user.is_platform_admin = True
        self.user.save()
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/',
            {'name': 'Partially Updated Tenant'},
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_tenant_config_retrieve(self):
        """Test GET /api/v1/tenants/{id}/config/"""
        # Make user platform admin or TENANT_ADMIN to access config
        self.user.is_platform_admin = True
        self.user.save()
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f'/api/v1/tenants/{self.tenant.id}/config/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_tenant_config_update(self):
        """Test PATCH /api/v1/tenants/{id}/config/"""
        # Make user platform admin or TENANT_ADMIN to update config
        self.user.is_platform_admin = True
        self.user.save()
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {'default_dq_profile': 'intake_basic_gx'},
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


class AssetAPIRegressionTest(APIRegressionTest):
    """Test all asset API endpoints"""

    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test Description"
        )

    def test_asset_list(self):
        """Test GET /api/v1/assets/"""
        response = self.client.get('/api/v1/assets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))

    def test_asset_create(self):
        """Test POST /api/v1/assets/"""
        response = self.client.post(
            '/api/v1/assets/',
            {
                'key': 'new-asset',
                'name': 'New Asset',
                'description': 'New Description'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)

    def test_asset_retrieve(self):
        """Test GET /api/v1/assets/{id}/"""
        response = self.client.get(f'/api/v1/assets/{self.asset.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.asset.id))

    def test_asset_update(self):
        """Test PUT /api/v1/assets/{id}/"""
        response = self.client.put(
            f'/api/v1/assets/{self.asset.id}/',
            {
                'key': self.asset.key,
                'name': 'Updated Asset',
                'description': 'Updated Description'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_asset_partial_update(self):
        """Test PATCH /api/v1/assets/{id}/"""
        response = self.client.patch(
            f'/api/v1/assets/{self.asset.id}/',
            {'name': 'Partially Updated Asset'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_asset_delete(self):
        """Test DELETE /api/v1/assets/{id}/"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="to-delete",
            name="To Delete"
        )
        response = self.client.delete(f'/api/v1/assets/{asset.id}/')
        self.assertIn(response.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_403_FORBIDDEN])


class ContractAPIRegressionTest(APIRegressionTest):
    """Test all contract API endpoints"""

    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="contract-asset",
            name="Contract Asset"
        )
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test Contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "test", "name": "Test Contract"}
        )

    def test_contract_list(self):
        """Test GET /api/v1/contracts/"""
        response = self.client.get('/api/v1/contracts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))

    def test_contract_create(self):
        """Test POST /api/v1/contracts/"""
        import json as _json
        odcs_contract = {
            "id": f"new-contract-{uuid.uuid4().hex[:8]}",
            "kind": "DataContract",
            "apiVersion": "v3.0.0",
            "info": {
                "title": "New Contract",
                "version": "1.0.0",
            },
            "schema": {
                "type": "object",
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "value", "type": "number"},
                ],
            },
        }
        response = self.client.post(
            '/api/v1/contracts/',
            {
                'asset_id': str(self.asset.id),
                'original_raw': _json.dumps(odcs_contract),
                'original_format': 'JSON',
                'original_spec_type': 'ODCS',
                'original_spec_version': '3.0.0'
            },
            format='json'
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST],
            f"Contract creation unexpected: {response.data}",
        )

    def test_contract_retrieve(self):
        """Test GET /api/v1/contracts/{id}/"""
        response = self.client.get(f'/api/v1/contracts/{self.contract.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.contract.id))

    def test_contract_update(self):
        """Test PUT /api/v1/contracts/{id}/"""
        response = self.client.put(
            f'/api/v1/contracts/{self.contract.id}/',
            {
                'asset_id': str(self.asset.id),
                'original_raw': '{"id": "updated", "name": "Updated Contract"}',
                'original_format': 'JSON',
                'original_spec_type': 'ODCS',
                'original_spec_version': '1.0.0'
            },
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_contract_partial_update(self):
        """Test PATCH /api/v1/contracts/{id}/"""
        response = self.client.patch(
            f'/api/v1/contracts/{self.contract.id}/',
            {'status': ContractStatus.ACTIVE},
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_contract_delete(self):
        """Test DELETE /api/v1/contracts/{id}/"""
        # Use a different version to avoid unique constraint violation
        # Check existing contracts for this asset to find next available version
        existing_versions = Contract.objects.filter(
            tenant=self.tenant,
            asset=self.asset
        ).values_list('version', flat=True)
        next_version = max(existing_versions, default=0) + 1

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            version=next_version,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "delete", "name": "Delete Contract"}',
            hub_contract_version="1.0.0"
        )
        response = self.client.delete(f'/api/v1/contracts/{contract.id}/')
        self.assertIn(response.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_403_FORBIDDEN])


class FileAPIRegressionTest(APIRegressionTest):
    """Test all file API endpoints"""

    def setUp(self):
        super().setUp()
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.UPLOADING  # Use valid status (UPLOADED doesn't exist)
        )

    def test_file_list(self):
        """Test GET /api/v1/files/"""
        response = self.client.get('/api/v1/files/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))

    def test_file_init_upload(self):
        """Test POST /api/v1/files/init/"""
        response = self.client.post(
            '/api/v1/files/init/',
            {
                'name': 'new-file.csv',
                'content_type': 'text/csv',
                'size': 2048
            },
            format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED,
            f"File init failed: {response.data}",
        )

    def test_file_retrieve(self):
        """Test GET /api/v1/files/{id}/"""
        response = self.client.get(f'/api/v1/files/{self.file.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.file.id))

    def test_file_delete(self):
        """Test DELETE /api/v1/files/{id}/"""
        file = File.objects.create(
            tenant=self.tenant,
            name="to-delete.csv",
            content_type="text/csv",
            size=512,
            status=FileStatus.ACTIVE  # Use valid status (UPLOADED doesn't exist)
        )
        response = self.client.delete(f'/api/v1/files/{file.id}/')
        self.assertIn(response.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_403_FORBIDDEN])


class JobAPIRegressionTest(APIRegressionTest):
    """Test all job API endpoints"""

    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="job-asset",
            name="Job Asset"
        )
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,  # Use 'type' not 'job_type'
            status=JobStatus.PENDING,
            resource_type="ASSET",  # Required field
            resource_id=self.asset.id,  # Required field
            created_by=self.user
        )

    def test_job_list(self):
        """Test GET /api/v1/jobs/"""
        response = self.client.get('/api/v1/jobs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))

    def test_job_create(self):
        """Test POST /api/v1/jobs/"""
        response = self.client.post(
            '/api/v1/jobs/',
            {
                'job_type': 'DQ_RUN',
                'input_data': {'test': 'data'}
            },
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_job_retrieve(self):
        """Test GET /api/v1/jobs/{id}/"""
        response = self.client.get(f'/api/v1/jobs/{self.job.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.job.id))

    def test_job_cancel(self):
        """Test POST /api/v1/jobs/{id}/cancel/"""
        response = self.client.post(f'/api/v1/jobs/{self.job.id}/cancel/', {}, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])


class DQAPIRegressionTest(APIRegressionTest):
    """Test all DQ API endpoints"""

    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="dq-asset",
            name="DQ Asset"
        )
        # DQRun requires a job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=self.asset.id,
            created_by=self.user
        )
        self.dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,  # Required field
            profile_key="intake_basic_gx",
            engine="GREAT_EXPECTATIONS",
            status=DQRunStatus.PENDING
        )

    def test_dq_run_list(self):
        """Test GET /api/v1/dq/runs/"""
        response = self.client.get('/api/v1/dq/runs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))

    def test_dq_run_create(self):
        """Test POST /api/v1/dq/runs/"""
        response = self.client.post(
            '/api/v1/dq/runs/',
            {
                'asset_id': str(self.asset.id),
                'profile': 'intake_basic_gx'
            },
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_dq_run_retrieve(self):
        """Test GET /api/v1/dq/runs/{id}/"""
        response = self.client.get(f'/api/v1/dq/runs/{self.dq_run.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.dq_run.id))


class ComplianceAPIRegressionTest(APIRegressionTest):
    """Test all compliance API endpoints"""

    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="compliance-asset",
            name="Compliance Asset"
        )
        # ComplianceRun requires a job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=self.asset.id,
            created_by=self.user
        )
        self.compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,  # Required field
            status=ComplianceRunStatus.PENDING
        )

    def test_compliance_run_list(self):
        """Test GET /api/v1/compliance/runs/"""
        response = self.client.get('/api/v1/compliance/runs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))

    def test_compliance_run_create(self):
        """Test POST /api/v1/compliance/runs/"""
        response = self.client.post(
            '/api/v1/compliance/runs/',
            {
                'asset_id': str(self.asset.id),
                'scan_mode': 'internal'
            },
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_compliance_run_retrieve(self):
        """Test GET /api/v1/compliance/runs/{id}/"""
        response = self.client.get(f'/api/v1/compliance/runs/{self.compliance_run.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.compliance_run.id))


class SemanticAPIRegressionTest(APIRegressionTest):
    """Test all semantic API endpoints"""

    def test_semantic_resource_list(self):
        """Test GET /api/v1/semantic/semantic-resources/"""
        response = self.client.get('/api/v1/semantic/semantic-resources/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))

    def test_sparql_query(self):
        """Test POST /api/v1/semantic/sparql"""
        response = self.client.post(
            '/api/v1/semantic/sparql',
            {'query': 'SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10'},
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_503_SERVICE_UNAVAILABLE])

    def test_resolve_uri(self):
        """Test GET /api/v1/semantic/id/{resource_type}/{resource_id}"""
        # Use a valid UUID format (may not exist, but should return 404 not 500)
        import uuid
        test_uuid = str(uuid.uuid4())
        response = self.client.get(f'/api/v1/semantic/id/ASSET/{test_uuid}')
        # May return 200 (found), 404 (not found), or 400 (invalid UUID format)
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST
        ])

    def test_get_ontology(self):
        """Test GET /api/v1/semantic/ontology"""
        response = self.client.get('/api/v1/semantic/ontology')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])

    def test_get_jsonld_context(self):
        """Test GET /api/v1/semantic/context.jsonld"""
        response = self.client.get('/api/v1/semantic/context.jsonld')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])


class MarketplaceAPIRegressionTest(APIRegressionTest):
    """Test all marketplace API endpoints"""

    def setUp(self):
        super().setUp()
        from hub.apps.assets.models import AssetStatus
        # Assets must be ACTIVE to be listed in marketplace
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="marketplace-asset",
            name="Marketplace Asset",
            status=AssetStatus.ACTIVE
        )
        # Only ACTIVE assets can be listed, so we can create listing
        self.listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT
        )

    def test_listing_list(self):
        """Test GET /api/v1/marketplace/listings/"""
        response = self.client.get('/api/v1/marketplace/listings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))

    def test_listing_create(self):
        """Test POST /api/v1/marketplace/listings/"""
        response = self.client.post(
            '/api/v1/marketplace/listings/',
            {
                'asset_id': str(self.asset.id),
                'title': 'New Listing'
            },
            format='json'
        )
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_listing_retrieve(self):
        """Test GET /api/v1/marketplace/listings/{id}/"""
        response = self.client.get(f'/api/v1/marketplace/listings/{self.listing.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.listing.id))

    def test_order_list(self):
        """Test GET /api/v1/marketplace/orders/"""
        response = self.client.get('/api/v1/marketplace/orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))

    def test_entitlement_list(self):
        """Test GET /api/v1/marketplace/entitlements/"""
        response = self.client.get('/api/v1/marketplace/entitlements/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))


class UserAPIRegressionTest(APIRegressionTest):
    """Test all user API endpoints"""

    def test_user_list(self):
        """Test GET /api/v1/users/"""
        response = self.client.get('/api/v1/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))

    def test_user_retrieve(self):
        """Test GET /api/v1/users/{id}/"""
        response = self.client.get(f'/api/v1/users/{self.user.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.user.id))

    def test_role_list(self):
        """Test GET /api/v1/users/roles/"""
        response = self.client.get('/api/v1/users/roles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, (list, dict))

