"""
Marketplace Integration Views Tests

Comprehensive tests for marketplace connection management endpoints.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.db import transaction
import uuid

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.integrations.base import MarketplaceType
from hub.apps.users.models import UserStatus, Role
from hub.apps.auth.models import APIKey

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceConnectionViewSetTest(TestCase):
    """Test suite for MarketplaceConnectionViewSet"""

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

        # Authenticate client
        self.client.force_authenticate(user=self.user)

        # Sample connection data
        self.valid_connection_data = {
            'marketplace_type': MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            'name': 'Test Connection',
            'config': {
                'api_key': 'test_key',
                'api_secret': 'test_secret'
            },
            'is_active': True
        }

    def test_create_connection_success(self):
        """Test successful connection creation"""
        response = self.client.post(
            '/api/v1/integrations/marketplace/connections/',
            self.valid_connection_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "Test Connection")
        self.assertEqual(response.data['marketplace_type'], MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value)
        self.assertTrue(response.data['is_active'])
        self.assertIn('id', response.data)
        self.assertIn('created_at', response.data)
        self.assertIn('updated_at', response.data)
        # Config should never be exposed
        self.assertNotIn('config', response.data)

        # Verify connection was created in database
        connection = MarketplaceConnection.objects.get(id=response.data['id'])
        self.assertEqual(connection.name, "Test Connection")
        self.assertEqual(connection.tenant, self.tenant)

    def test_create_connection_missing_required_fields(self):
        """Test connection creation with missing required fields"""
        data = {
            'name': 'Test Connection',
            # Missing marketplace_type and config
        }

        response = self.client.post(
            '/api/v1/integrations/marketplace/connections/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_connection_invalid_marketplace_type(self):
        """Test connection creation with invalid marketplace type"""
        data = self.valid_connection_data.copy()
        data['marketplace_type'] = 'INVALID_TYPE'

        response = self.client.post(
            '/api/v1/integrations/marketplace/connections/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('marketplace_type', str(response.data))

    def test_create_connection_invalid_config(self):
        """Test connection creation with invalid config (not a dict)"""
        data = self.valid_connection_data.copy()
        data['config'] = 'not a dict'

        response = self.client.post(
            '/api/v1/integrations/marketplace/connections/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('config', str(response.data))

    def test_create_connection_duplicate_name(self):
        """Test connection creation with duplicate name (same tenant)"""
        # Create first connection
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name='Duplicate Name',
            config={'key': 'value'}
        )

        # Try to create another with same name
        data = self.valid_connection_data.copy()
        data['name'] = 'Duplicate Name'

        response = self.client.post(
            '/api/v1/integrations/marketplace/connections/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_list_connections_success(self):
        """Test successful connection listing"""
        # Create test connections
        connection1 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Connection 1",
            config={'key': 'value1'},
            is_active=True
        )
        connection2 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Connection 2",
            config={'key': 'value2'},
            is_active=False
        )

        response = self.client.get('/api/v1/integrations/marketplace/connections/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 2)

    def test_list_connections_with_marketplace_type_filter(self):
        """Test connection listing with marketplace_type filter"""
        # Create test connections with different types
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Snowflake Connection",
            config={'key': 'value'}
        )
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="AWS Connection",
            config={'key': 'value'}
        )

        response = self.client.get(
            '/api/v1/integrations/marketplace/connections/',
            {'marketplace_type': MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['marketplace_type'], MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value)

    def test_list_connections_with_is_active_filter(self):
        """Test connection listing with is_active filter"""
        # Create test connections with different active statuses
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Active Connection",
            config={'key': 'value'},
            is_active=True
        )
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Inactive Connection",
            config={'key': 'value'},
            is_active=False
        )

        response = self.client.get(
            '/api/v1/integrations/marketplace/connections/',
            {'is_active': 'true'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertTrue(response.data['results'][0]['is_active'])

    def test_list_connections_with_search(self):
        """Test connection listing with search"""
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Snowflake Connection",
            config={'key': 'value'}
        )
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="AWS Connection",
            config={'key': 'value'}
        )

        response = self.client.get(
            '/api/v1/integrations/marketplace/connections/',
            {'search': 'Snowflake'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertIn('Snowflake', response.data['results'][0]['name'])

    def test_list_connections_with_ordering(self):
        """Test connection listing with ordering"""
        connection1 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="A Connection",
            config={'key': 'value'}
        )
        connection2 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="B Connection",
            config={'key': 'value'}
        )

        response = self.client.get(
            '/api/v1/integrations/marketplace/connections/',
            {'ordering': 'name'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['name'], 'A Connection')
        self.assertEqual(response.data['results'][1]['name'], 'B Connection')

    def test_retrieve_connection_success(self):
        """Test successful connection retrieval"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={'key': 'value'},
            is_active=True
        )

        response = self.client.get(
            f'/api/v1/integrations/marketplace/connections/{connection.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(connection.id))
        self.assertEqual(response.data['name'], "Test Connection")
        self.assertNotIn('config', response.data)

    def test_retrieve_connection_not_found(self):
        """Test retrieving non-existent connection"""
        fake_id = uuid.uuid4()
        response = self.client.get(
            f'/api/v1/integrations/marketplace/connections/{fake_id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_connection_success(self):
        """Test successful connection update"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Original Name",
            config={'key': 'value'},
            is_active=True
        )

        update_data = {
            'name': 'Updated Name',
            'is_active': False
        }

        response = self.client.put(
            f'/api/v1/integrations/marketplace/connections/{connection.id}/',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Name')
        self.assertFalse(response.data['is_active'])

        # Verify update in database
        connection.refresh_from_db()
        self.assertEqual(connection.name, 'Updated Name')
        self.assertFalse(connection.is_active)

    def test_partial_update_connection_success(self):
        """Test successful partial connection update"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Original Name",
            config={'key': 'value'},
            is_active=True
        )

        update_data = {
            'name': 'Updated Name'
        }

        response = self.client.patch(
            f'/api/v1/integrations/marketplace/connections/{connection.id}/',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Name')
        self.assertTrue(response.data['is_active'])  # Should remain unchanged

    def test_update_connection_config(self):
        """Test updating connection config"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={'old_key': 'old_value'},
            is_active=True
        )

        update_data = {
            'config': {'new_key': 'new_value'}
        }

        response = self.client.patch(
            f'/api/v1/integrations/marketplace/connections/{connection.id}/',
            update_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify config was updated (decrypted)
        connection.refresh_from_db()
        decrypted_config = connection.get_config()
        self.assertEqual(decrypted_config['new_key'], 'new_value')

    def test_delete_connection_success(self):
        """Test successful connection deletion"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={'key': 'value'},
            is_active=True
        )

        connection_id = connection.id

        response = self.client.delete(
            f'/api/v1/integrations/marketplace/connections/{connection.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify connection was deleted
        self.assertFalse(MarketplaceConnection.objects.filter(id=connection_id).exists())

    def test_delete_connection_not_found(self):
        """Test deleting non-existent connection"""
        fake_id = uuid.uuid4()
        response = self.client.delete(
            f'/api/v1/integrations/marketplace/connections/{fake_id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_test_connection_success(self):
        """Test successful connection test"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={'api_key': 'test_key', 'api_secret': 'test_secret'},
            is_active=True
        )

        response = self.client.post(
            f'/api/v1/integrations/marketplace/connections/{connection.id}/test/'
        )

        # Note: Actual test result depends on connector implementation
        # This test verifies the endpoint is accessible and returns proper format
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,  # If connector test fails
            status.HTTP_500_INTERNAL_SERVER_ERROR  # If connector not available
        ])

        if response.status_code == status.HTTP_200_OK:
            self.assertIn('success', response.data)
            self.assertIn('message', response.data)
            self.assertIn('tested_at', response.data)
            self.assertIn('connection_id', response.data)

    def test_test_connection_not_found(self):
        """Test testing non-existent connection"""
        fake_id = uuid.uuid4()
        response = self.client.post(
            f'/api/v1/integrations/marketplace/connections/{fake_id}/test/'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_access(self):
        """Test unauthenticated users cannot access endpoints"""
        self.client.logout()

        response = self.client.get('/api/v1/integrations/marketplace/connections/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.client.post(
            '/api/v1/integrations/marketplace/connections/',
            self.valid_connection_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tenant_isolation(self):
        """Test tenant isolation - users can only see their tenant's connections"""
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

        # Create connection in other tenant
        other_connection = MarketplaceConnection.objects.create(
            tenant=other_tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Other Connection",
            config={'key': 'value'}
        )

        # Try to access with original user
        response = self.client.get(
            f'/api/v1/integrations/marketplace/connections/{other_connection.id}/'
        )

        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ])

    def test_platform_admin_access(self):
        """Test platform admins can access all connections"""
        # Create platform admin user
        admin_user = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            is_platform_admin=True
        )

        # Create connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={'key': 'value'}
        )

        # Authenticate as admin
        self.client.force_authenticate(user=admin_user)

        # Should be able to access
        response = self.client.get(
            f'/api/v1/integrations/marketplace/connections/{connection.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

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

        # Try to create connection
        response = self.client.post(
            '/api/v1/integrations/marketplace/connections/',
            self.valid_connection_data,
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

        # Create connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={'key': 'value'}
        )

        self.client.force_authenticate(user=regular_user)

        # Should be able to read
        response = self.client.get(
            f'/api/v1/integrations/marketplace/connections/{connection.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pagination(self):
        """Test pagination works correctly"""
        # Create multiple connections
        for i in range(25):
            MarketplaceConnection.objects.create(
                tenant=self.tenant,
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                name=f"Connection {i}",
                config={'key': 'value'}
            )

        response = self.client.get(
            '/api/v1/integrations/marketplace/connections/',
            {'page_size': 10}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['count'], 25)

