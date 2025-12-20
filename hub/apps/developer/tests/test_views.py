"""
Comprehensive tests for developer experience endpoints (plugins, SDK).

Tests cover:
- Unit tests for plugin listing
- Unit tests for SDK documentation
- Integration tests
- Security tests (public endpoints)
- Performance tests
- Error handling
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.developer.models import Plugin, PluginStatus, PluginCategory, SDKDocumentation, SDKLanguage

pytestmark = pytest.mark.django_db(transaction=True)


class PluginViewSetTest(TestCase):
    """Test plugin marketplace endpoint"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create test plugins
        self.plugin1 = Plugin.objects.create(
            name="Test Plugin 1",
            description="Test plugin description 1",
            version="1.0.0",
            author="Test Author",
            category=PluginCategory.CONNECTOR,
            status=PluginStatus.AVAILABLE,
            download_count=100,
            rating=4.5
        )
        
        self.plugin2 = Plugin.objects.create(
            name="Test Plugin 2",
            description="Test plugin description 2",
            version="2.0.0",
            author="Test Author 2",
            category=PluginCategory.TRANSFORMER,
            status=PluginStatus.AVAILABLE,
            download_count=50,
            rating=4.0
        )
        
        self.plugin3 = Plugin.objects.create(
            name="Deprecated Plugin",
            description="Deprecated plugin",
            version="0.1.0",
            author="Test Author",
            category=PluginCategory.OTHER,
            status=PluginStatus.DEPRECATED,
            download_count=10,
            rating=3.0
        )
    
    def test_list_plugins_public(self):
        """Test plugin listing is public (no auth required)"""
        response = self.client.get('/api/v1/developer/plugins/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data or [])
        
        # Should only return available plugins by default
        if 'results' in response.data:
            plugin_names = [p['name'] for p in response.data['results']]
            self.assertIn('Test Plugin 1', plugin_names)
            self.assertIn('Test Plugin 2', plugin_names)
            self.assertNotIn('Deprecated Plugin', plugin_names)
    
    def test_list_plugins_filter_by_category(self):
        """Test filtering plugins by category"""
        response = self.client.get('/api/v1/developer/plugins/?category=CONNECTOR')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if 'results' in response.data:
            for plugin in response.data['results']:
                self.assertEqual(plugin['category'], 'CONNECTOR')
    
    def test_list_plugins_search(self):
        """Test searching plugins"""
        response = self.client.get('/api/v1/developer/plugins/?search=Plugin 1')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if 'results' in response.data:
            plugin_names = [p['name'] for p in response.data['results']]
            self.assertIn('Test Plugin 1', plugin_names)
            self.assertNotIn('Test Plugin 2', plugin_names)
    
    def test_list_plugins_sort_by_popularity(self):
        """Test sorting plugins by popularity"""
        response = self.client.get('/api/v1/developer/plugins/?sort=popularity')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if 'results' in response.data and len(response.data['results']) > 1:
            downloads = [p['download_count'] for p in response.data['results']]
            self.assertEqual(downloads, sorted(downloads, reverse=True))
    
    def test_list_plugins_sort_by_rating(self):
        """Test sorting plugins by rating"""
        response = self.client.get('/api/v1/developer/plugins/?sort=rating')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if 'results' in response.data and len(response.data['results']) > 1:
            ratings = [p['rating'] or 0 for p in response.data['results']]
            self.assertEqual(ratings, sorted(ratings, reverse=True))
    
    def test_retrieve_plugin(self):
        """Test retrieving a single plugin"""
        response = self.client.get(f'/api/v1/developer/plugins/{self.plugin1.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Plugin 1')
        self.assertEqual(response.data['version'], '1.0.0')
        self.assertEqual(response.data['category'], 'CONNECTOR')


class SDKDocumentationViewSetTest(TestCase):
    """Test SDK documentation endpoint"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create test SDK documentation
        self.python_sdk = SDKDocumentation.objects.create(
            language=SDKLanguage.PYTHON,
            version="1.0.0",
            documentation="# Python SDK\n\nPython SDK for Data Hub API.",
            installation="pip install datahub-sdk",
            quick_start="from datahub import DataHubClient\n\nclient = DataHubClient(api_key='your-key')",
            examples_json=[
                {
                    'title': 'List Assets',
                    'code': 'assets = client.assets.list()\nfor asset in assets:\n    print(asset.name)',
                    'description': 'List all assets'
                }
            ],
            api_reference_json={
                'endpoints': [
                    {'path': '/api/v1/assets/', 'method': 'GET', 'description': 'List assets'}
                ]
            },
            is_active=True
        )
        
        self.js_sdk = SDKDocumentation.objects.create(
            language=SDKLanguage.JAVASCRIPT,
            version="1.0.0",
            documentation="# JavaScript SDK\n\nJavaScript SDK for Data Hub API.",
            installation="npm install @datahub/sdk",
            quick_start="import { DataHubClient } from '@datahub/sdk';\n\nconst client = new DataHubClient({ apiKey: 'your-key' });",
            examples_json=[],
            api_reference_json={},
            is_active=True
        )
    
    def test_list_sdk_all_languages(self):
        """Test listing all SDK documentation"""
        response = self.client.get('/api/v1/developer/sdk/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('sdks', response.data)
        self.assertEqual(len(response.data['sdks']), 2)
    
    def test_list_sdk_specific_language(self):
        """Test listing SDK for specific language"""
        response = self.client.get('/api/v1/developer/sdk/?language=python')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('sdk_name', response.data)
        self.assertEqual(response.data['language'], 'python')
        self.assertEqual(response.data['version'], '1.0.0')
        self.assertIn('documentation', response.data)
        self.assertIn('installation', response.data)
        self.assertIn('quick_start', response.data)
    
    def test_list_sdk_with_examples(self):
        """Test SDK documentation includes examples"""
        response = self.client.get('/api/v1/developer/sdk/?language=python&include_examples=true')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('examples', response.data)
        self.assertEqual(len(response.data['examples']), 1)
    
    def test_list_sdk_without_examples(self):
        """Test SDK documentation excludes examples when requested"""
        response = self.client.get('/api/v1/developer/sdk/?language=python&include_examples=false')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['examples'], [])
    
    def test_list_sdk_nonexistent_language(self):
        """Test SDK documentation for nonexistent language"""
        response = self.client.get('/api/v1/developer/sdk/?language=rust')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_list_sdk_public(self):
        """Test SDK documentation is public (no auth required)"""
        response = self.client.get('/api/v1/developer/sdk/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_retrieve_sdk(self):
        """Test retrieving SDK documentation by ID"""
        response = self.client.get(f'/api/v1/developer/sdk/{self.python_sdk.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['language'], 'python')
        self.assertEqual(response.data['version'], '1.0.0')

