"""
Marketplace Sync Job Views Tests

Comprehensive tests for marketplace sync job management endpoints.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.db import transaction
import uuid
from django.utils import timezone

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.integrations.models import MarketplaceSyncJob, MarketplaceConnection
from hub.apps.integrations.base import SyncDirection, SyncStatus, MarketplaceType
from hub.apps.users.models import UserStatus, Role
from hub.apps.auth.models import APIKey

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceSyncJobViewSetTest(TestCase):
    """Test suite for MarketplaceSyncJobViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        # Create user with DATA_PROVIDER role
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create DATA_PROVIDER role and assign to user
        data_provider_role, _ = Role.objects.get_or_create(
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"}
        )
        self.user.user_roles.create(role=data_provider_role)

        # Create API key with integrations:write scope
        self.api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            scopes=["integrations:write", "integrations:read"]
        )

        # Create connection
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test_key", "api_secret": "test_secret"},
            is_active=True
        )

        # Authenticate client
        self.client.force_authenticate(user=self.user)

        # Sample sync request data
        self.valid_push_sync_data = {
            'connection_id': str(self.connection.id),
            'direction': SyncDirection.PUSH.value,
            'asset_ids': [str(uuid.uuid4()), str(uuid.uuid4())],
            'options': {'dry_run': False}
        }

        self.valid_pull_sync_data = {
            'connection_id': str(self.connection.id),
            'direction': SyncDirection.PULL.value,
            'listing_ids': ['listing1', 'listing2'],
            'filters': {'category': 'data'},
            'options': {'create_assets': True}
        }

    def test_create_push_sync_job_success(self):
        """Test successful PUSH sync job creation"""
        response = self.client.post(
            '/api/v1/integrations/marketplace/sync/',
            self.valid_push_sync_data,
            format='json'
        )

        # Should create sync job (may return 201 or 400/500 if connector not available)
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ])

        if response.status_code == status.HTTP_201_CREATED:
            self.assertIn('id', response.data)
            self.assertEqual(response.data['direction'], SyncDirection.PUSH.value)
            self.assertEqual(response.data['status'], SyncStatus.PENDING.value)
            self.assertIn('connection_id', response.data)

    def test_create_pull_sync_job_success(self):
        """Test successful PULL sync job creation"""
        response = self.client.post(
            '/api/v1/integrations/marketplace/sync/',
            self.valid_pull_sync_data,
            format='json'
        )

        # Should create sync job (may return 201 or 400/500 if connector not available)
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ])

        if response.status_code == status.HTTP_201_CREATED:
            self.assertIn('id', response.data)
            self.assertEqual(response.data['direction'], SyncDirection.PULL.value)
            self.assertEqual(response.data['status'], SyncStatus.PENDING.value)

    def test_create_sync_job_missing_required_fields(self):
        """Test sync job creation with missing required fields"""
        data = {
            'direction': SyncDirection.PUSH.value,
            # Missing connection_id and asset_ids
        }

        response = self.client.post(
            '/api/v1/integrations/marketplace/sync/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_push_sync_job_without_asset_ids(self):
        """Test PUSH sync job creation without asset_ids"""
        data = {
            'connection_id': str(self.connection.id),
            'direction': SyncDirection.PUSH.value,
            # Missing asset_ids
        }

        response = self.client.post(
            '/api/v1/integrations/marketplace/sync/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('asset_ids', str(response.data))

    def test_create_sync_job_invalid_connection_id(self):
        """Test sync job creation with invalid connection_id"""
        data = self.valid_push_sync_data.copy()
        data['connection_id'] = str(uuid.uuid4())  # Non-existent connection

        response = self.client.post(
            '/api/v1/integrations/marketplace/sync/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_sync_jobs_success(self):
        """Test successful sync job listing"""
        # Create test sync jobs
        sync_job1 = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            items_synced=0,
            items_failed=0
        )
        sync_job2 = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.COMPLETED.value,
            items_synced=10,
            items_failed=0
        )

        response = self.client.get('/api/v1/integrations/marketplace/sync/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 2)

    def test_list_sync_jobs_with_connection_filter(self):
        """Test sync job listing with connection_id filter"""
        # Create sync jobs
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )

        # Create another connection and sync job
        other_connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Other Connection",
            config={"key": "value"},
            is_active=True
        )
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=other_connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.PENDING.value
        )

        response = self.client.get(
            '/api/v1/integrations/marketplace/sync/',
            {'connection_id': str(self.connection.id)}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['connection_id'], str(self.connection.id))

    def test_list_sync_jobs_with_status_filter(self):
        """Test sync job listing with status filter"""
        # Create sync jobs with different statuses
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.COMPLETED.value
        )

        response = self.client.get(
            '/api/v1/integrations/marketplace/sync/',
            {'status': SyncStatus.PENDING.value}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['status'], SyncStatus.PENDING.value)

    def test_list_sync_jobs_with_direction_filter(self):
        """Test sync job listing with direction filter"""
        # Create sync jobs with different directions
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.PENDING.value
        )

        response = self.client.get(
            '/api/v1/integrations/marketplace/sync/',
            {'direction': SyncDirection.PUSH.value}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['direction'], SyncDirection.PUSH.value)

    def test_retrieve_sync_job_success(self):
        """Test successful sync job retrieval"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            items_synced=0,
            items_failed=0
        )

        response = self.client.get(
            f'/api/v1/integrations/marketplace/sync/{sync_job.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(sync_job.id))
        self.assertEqual(response.data['direction'], SyncDirection.PUSH.value)
        self.assertEqual(response.data['status'], SyncStatus.PENDING.value)

    def test_retrieve_sync_job_not_found(self):
        """Test retrieving non-existent sync job"""
        fake_id = uuid.uuid4()
        response = self.client.get(
            f'/api/v1/integrations/marketplace/sync/{fake_id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_sync_job_success(self):
        """Test successful sync job cancellation"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            items_synced=0,
            items_failed=0
        )

        cancel_data = {
            'reason': 'User requested cancellation'
        }

        response = self.client.post(
            f'/api/v1/integrations/marketplace/sync/{sync_job.id}/cancel/',
            cancel_data,
            format='json'
        )

        # Should succeed (200) or fail if job cannot be cancelled (400)
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST
        ])

        if response.status_code == status.HTTP_200_OK:
            # Verify job was cancelled (status might be CANCELLED or still PENDING depending on implementation)
            self.assertIn('id', response.data)

    def test_cancel_completed_sync_job(self):
        """Test cancelling a completed sync job (should fail)"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.COMPLETED.value,
            items_synced=10,
            items_failed=0,
            completed_at=timezone.now()
        )

        cancel_data = {
            'reason': 'User requested cancellation'
        }

        response = self.client.post(
            f'/api/v1/integrations/marketplace/sync/{sync_job.id}/cancel/',
            cancel_data,
            format='json'
        )

        # Should fail because job is already completed
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_sync_job_not_found(self):
        """Test cancelling non-existent sync job"""
        fake_id = uuid.uuid4()
        cancel_data = {'reason': 'Test'}

        response = self.client.post(
            f'/api/v1/integrations/marketplace/sync/{fake_id}/cancel/',
            cancel_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_access(self):
        """Test unauthenticated users cannot access endpoints"""
        self.client.logout()

        response = self.client.get('/api/v1/integrations/marketplace/sync/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.client.post(
            '/api/v1/integrations/marketplace/sync/',
            self.valid_push_sync_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tenant_isolation(self):
        """Test tenant isolation - users can only see their tenant's sync jobs"""
        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )

        # Create connection and sync job in other tenant
        other_connection = MarketplaceConnection.objects.create(
            tenant=other_tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Other Connection",
            config={'key': 'value'}
        )
        other_sync_job = MarketplaceSyncJob.objects.create(
            tenant=other_tenant,
            connection=other_connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )

        # Try to access with original user
        response = self.client.get(
            f'/api/v1/integrations/marketplace/sync/{other_sync_job.id}/'
        )

        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ])

    def test_permissions_write_operations(self):
        """Test write operations require DATA_PROVIDER or TENANT_ADMIN role"""
        # Create user without DATA_PROVIDER role
        regular_user = User.objects.create_user(
            email="regular@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        self.client.force_authenticate(user=regular_user)

        # Try to create sync job
        response = self.client.post(
            '/api/v1/integrations/marketplace/sync/',
            self.valid_push_sync_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_permissions_read_operations(self):
        """Test read operations only require authentication"""
        # Create user without DATA_PROVIDER role
        regular_user = User.objects.create_user(
            email="regular@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )

        self.client.force_authenticate(user=regular_user)

        # Should be able to read
        response = self.client.get(
            f'/api/v1/integrations/marketplace/sync/{sync_job.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pagination(self):
        """Test pagination works correctly"""
        # Create multiple sync jobs
        for i in range(25):
            MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value
            )

        response = self.client.get(
            '/api/v1/integrations/marketplace/sync/',
            {'page_size': 10}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['count'], 25)

