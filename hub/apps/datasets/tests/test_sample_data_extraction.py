"""
Unit tests for sample data extraction.
"""
import pytest
from django.test import TestCase
from hub.apps.datasets.schema_inference import extract_sample_data



pytestmark = pytest.mark.django_db(transaction=True)
class SampleDataExtractionTest(TestCase):
    """Test sample data extraction for different file formats"""
    
    def test_extract_sample_data_csv(self):
        """Test sample data extraction from CSV"""
        csv_content = b"""name,age,city
John,30,NYC
Jane,25,LA
Bob,35,Chicago
Alice,28,Seattle
Charlie,32,Boston"""
        
        sample = extract_sample_data(csv_content, 'CSV', sample_size=3)
        
        self.assertEqual(len(sample), 3)
        self.assertEqual(sample[0]['name'], 'John')
        self.assertEqual(sample[0]['age'], '30')
        self.assertEqual(sample[1]['name'], 'Jane')
    
    def test_extract_sample_data_json_lines(self):
        """Test sample data extraction from JSON Lines"""
        json_content = b"""{"name": "John", "age": 30, "city": "NYC"}
{"name": "Jane", "age": 25, "city": "LA"}
{"name": "Bob", "age": 35, "city": "Chicago"}
{"name": "Alice", "age": 28, "city": "Seattle"}"""
        
        sample = extract_sample_data(json_content, 'JSON', sample_size=2)
        
        self.assertEqual(len(sample), 2)
        self.assertEqual(sample[0]['name'], 'John')
        self.assertEqual(sample[0]['age'], 30)
        self.assertEqual(sample[1]['name'], 'Jane')
    
    def test_extract_sample_data_json_array(self):
        """Test sample data extraction from JSON array"""
        json_content = b"""[{"name": "John", "age": 30}, {"name": "Jane", "age": 25}, {"name": "Bob", "age": 35}]"""
        
        sample = extract_sample_data(json_content, 'JSON', sample_size=2)
        
        self.assertEqual(len(sample), 2)
        self.assertEqual(sample[0]['name'], 'John')
        self.assertEqual(sample[1]['name'], 'Jane')
    
    def test_extract_sample_data_csv_empty(self):
        """Test sample data extraction from empty CSV"""
        csv_content = b"""name,age,city"""
        
        sample = extract_sample_data(csv_content, 'CSV', sample_size=10)
        
        self.assertEqual(len(sample), 0)
    
    def test_extract_sample_data_csv_more_rows_than_sample(self):
        """Test sample data extraction limits to sample size"""
        csv_content = b"""name,age,city
John,30,NYC
Jane,25,LA
Bob,35,Chicago
Alice,28,Seattle
Charlie,32,Boston
David,40,Miami
Eve,22,Portland"""
        
        sample = extract_sample_data(csv_content, 'CSV', sample_size=3)
        
        self.assertEqual(len(sample), 3)
        self.assertEqual(sample[0]['name'], 'John')
        self.assertEqual(sample[1]['name'], 'Jane')
        self.assertEqual(sample[2]['name'], 'Bob')
    
    def test_extract_sample_data_json_single_object(self):
        """Test sample data extraction from single JSON object"""
        json_content = b"""{"name": "John", "age": 30, "city": "NYC"}"""
        
        sample = extract_sample_data(json_content, 'JSON', sample_size=10)
        
        self.assertEqual(len(sample), 1)
        self.assertEqual(sample[0]['name'], 'John')
    
    def test_extract_sample_data_csv_different_delimiter(self):
        """Test sample data extraction from CSV with semicolon delimiter"""
        csv_content = b"""name;age;city
John;30;NYC
Jane;25;LA"""
        
        sample = extract_sample_data(csv_content, 'CSV', sample_size=10)
        
        self.assertEqual(len(sample), 2)
        self.assertEqual(sample[0]['name'], 'John')
        self.assertEqual(sample[0]['age'], '30')

