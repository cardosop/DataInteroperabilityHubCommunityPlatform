"""
Comprehensive E2E tests for dataset operations.

Covers:
- Dataset CRUD operations
- Dataset versioning
- Schema updates
- Sample data extraction
- Multiple datasets per asset
- Dataset format support (CSV, JSON, Parquet)

Uses REAL services (no mocks).
"""
import pytest
import hashlib
from django.test import TestCase
from rest_framework import status

from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus

from .conftest import E2ETestBase


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e1]


class DatasetOperationsE2ETest(E2ETestBase):
    """Test dataset operations"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
    
    def test_create_dataset_success(self):
        """Test creating a dataset"""
        # Upload file first
        test_content = b'col1,col2\nval1,val2\nval3,val4'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='dataset_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        
        # Create asset
        asset_id = self.create_asset(key='dataset-test', name='Dataset Test')
        
        # Create dataset
        dataset_id = self.create_dataset(file_id, asset_id)
        
        # Verify dataset created
        dataset = Dataset.objects.get(id=dataset_id)
        self.assertEqual(str(dataset.asset_id), str(asset_id))
        self.assertEqual(str(dataset.file_id), str(file_id))
        self.assertEqual(dataset.format, 'CSV')
        self.assertEqual(dataset.version, 1)
        self.assertIsNotNone(dataset.schema_json)
        self.assertIsNotNone(dataset.sample_data_json)
    
    def test_create_dataset_with_json_format(self):
        """Test creating dataset with JSON format"""
        json_content = b'{"id": 1, "name": "Alice"}\n{"id": 2, "name": "Bob"}'
        content_hash = hashlib.sha256(json_content).hexdigest()
        file_id = self.init_file_upload(name='dataset_test.json', content_type='application/json', size=len(json_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=json_content)
        
        asset_id = self.create_asset(key='json-dataset-test', name='JSON Dataset Test')
        dataset_id = self.create_dataset(file_id, asset_id)
        
        # Verify dataset created with JSON format
        dataset = Dataset.objects.get(id=dataset_id)
        self.assertEqual(dataset.format, 'JSON')
        self.assertIsNotNone(dataset.schema_json)
    
    def test_list_datasets_with_filters(self):
        """Test listing datasets with filters"""
        # Create multiple datasets
        asset_id = self.create_asset(key='list-datasets-test', name='List Datasets Test')
        
        test_content1 = b'col1,col2\nval1,val2'
        content_hash1 = hashlib.sha256(test_content1).hexdigest()
        file_id1 = self.init_file_upload(name='dataset1.csv', content_type='text/csv', size=len(test_content1))
        self.complete_file_upload(file_id1, content_sha256=content_hash1, test_content=test_content1)
        dataset_id1 = self.create_dataset(file_id1, asset_id)
        
        test_content2 = b'col1,col2\nval3,val4'
        content_hash2 = hashlib.sha256(test_content2).hexdigest()
        file_id2 = self.init_file_upload(name='dataset2.csv', content_type='text/csv', size=len(test_content2))
        self.complete_file_upload(file_id2, content_sha256=content_hash2, test_content=test_content2)
        dataset_id2 = self.create_dataset(file_id2, asset_id)
        
        # List datasets
        response = self.client.get('/api/v1/datasets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 2)
        
        # Filter by asset
        response = self.client.get(f'/api/v1/datasets/?asset_id={asset_id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dataset_ids = {d['id'] for d in response.data['results']}
        self.assertIn(str(dataset_id1), dataset_ids)
        self.assertIn(str(dataset_id2), dataset_ids)
    
    def test_get_dataset_details(self):
        """Test retrieving dataset details"""
        asset_id = self.create_asset(key='get-dataset-test', name='Get Dataset Test')
        test_content = b'col1,col2\nval1,val2'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='get_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)
        
        response = self.client.get(f'/api/v1/datasets/{dataset_id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(dataset_id))
        self.assertEqual(response.data['format'], 'CSV')
        self.assertIn('schema_json', response.data)
        self.assertIn('sample_data_json', response.data)
    
    def test_dataset_versioning(self):
        """Test dataset versioning per asset"""
        asset_id = self.create_asset(key='version-test', name='Version Test')
        
        # Create first dataset (version 1)
        test_content1 = b'col1,col2\nval1,val2'
        content_hash1 = hashlib.sha256(test_content1).hexdigest()
        file_id1 = self.init_file_upload(name='v1.csv', content_type='text/csv', size=len(test_content1))
        self.complete_file_upload(file_id1, content_sha256=content_hash1, test_content=test_content1)
        dataset_id1 = self.create_dataset(file_id1, asset_id)
        
        dataset1 = Dataset.objects.get(id=dataset_id1)
        self.assertEqual(dataset1.version, 1)
        
        # Create second dataset (version 2)
        test_content2 = b'col1,col2,col3\nval1,val2,val3'
        content_hash2 = hashlib.sha256(test_content2).hexdigest()
        file_id2 = self.init_file_upload(name='v2.csv', content_type='text/csv', size=len(test_content2))
        self.complete_file_upload(file_id2, content_sha256=content_hash2, test_content=test_content2)
        dataset_id2 = self.create_dataset(file_id2, asset_id)
        
        dataset2 = Dataset.objects.get(id=dataset_id2)
        self.assertEqual(dataset2.version, 2)
    
    def test_dataset_schema_inference(self):
        """Test that dataset schema is inferred correctly"""
        asset_id = self.create_asset(key='schema-inference-test', name='Schema Inference Test')
        test_content = b'id,name,age\n1,Alice,30\n2,Bob,25'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='schema_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)
        
        # Verify schema inferred
        dataset = Dataset.objects.get(id=dataset_id)
        self.assertIsNotNone(dataset.schema_json)
        self.assertIn('fields', dataset.schema_json)
        
        fields = dataset.schema_json['fields']
        field_names = {f['name'] for f in fields}
        self.assertIn('id', field_names)
        self.assertIn('name', field_names)
        self.assertIn('age', field_names)
    
    def test_dataset_sample_data_extraction(self):
        """Test that sample data is extracted correctly"""
        asset_id = self.create_asset(key='sample-data-test', name='Sample Data Test')
        # Create CSV with many rows
        csv_rows = ['col1,col2'] + [f'val{i},val{i+1}' for i in range(1, 201)]
        test_content = '\n'.join(csv_rows).encode()
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='sample_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)
        
        # Verify sample data extracted (should be first 100 rows)
        dataset = Dataset.objects.get(id=dataset_id)
        self.assertIsNotNone(dataset.sample_data_json)
        self.assertIsInstance(dataset.sample_data_json, list)
        self.assertGreater(len(dataset.sample_data_json), 0)
        self.assertLessEqual(len(dataset.sample_data_json), 100)
    
    def test_dataset_row_count_estimation(self):
        """Test that row count is estimated correctly"""
        asset_id = self.create_asset(key='rowcount-test', name='Row Count Test')
        # Create CSV with known number of rows
        csv_rows = ['col1,col2'] + [f'val{i},val{i+1}' for i in range(1, 51)]
        test_content = '\n'.join(csv_rows).encode()
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='rowcount_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)
        
        # Verify row count estimated
        dataset = Dataset.objects.get(id=dataset_id)
        self.assertIsNotNone(dataset.row_count)
        self.assertGreaterEqual(dataset.row_count, 49)  # Allow for header
        self.assertLessEqual(dataset.row_count, 51)
    
    def test_delete_dataset(self):
        """Test deleting a dataset"""
        asset_id = self.create_asset(key='delete-dataset-test', name='Delete Dataset Test')
        test_content = b'col1,col2\nval1,val2'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='delete_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)
        
        response = self.client.delete(f'/api/v1/datasets/{dataset_id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify dataset deleted
        self.assertFalse(Dataset.objects.filter(id=dataset_id).exists())
    
    def test_multiple_datasets_per_asset(self):
        """Test multiple datasets per asset (versioning)"""
        asset_id = self.create_asset(key='multi-dataset-test', name='Multi Dataset Test')
        
        # Create multiple datasets
        datasets = []
        for i in range(3):
            test_content = f'col1,col2\nval{i}1,val{i}2'.encode()
            content_hash = hashlib.sha256(test_content).hexdigest()
            file_id = self.init_file_upload(name=f'dataset_{i}.csv', content_type='text/csv', size=len(test_content))
            self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
            dataset_id = self.create_dataset(file_id, asset_id)
            datasets.append(dataset_id)
        
        # Verify all datasets exist and are linked to asset
        for dataset_id in datasets:
            dataset = Dataset.objects.get(id=dataset_id)
            self.assertEqual(str(dataset.asset_id), str(asset_id))
        
        # Verify versions are sequential
        dataset_versions = [Dataset.objects.get(id=d).version for d in datasets]
        self.assertEqual(sorted(dataset_versions), [1, 2, 3])

