"""
Unit tests for schema inference functionality.
"""
from django.test import TestCase
from hub.apps.datasets.schema_inference import (
    infer_schema_from_csv,
    infer_schema_from_json,
    infer_schema_from_parquet,
    detect_delimiter,
    detect_encoding,
    infer_type_from_values
)


class SchemaInferenceTest(TestCase):
    """Test schema inference for different file formats"""
    
    def test_detect_delimiter_comma(self):
        """Test delimiter detection for comma-separated CSV"""
        content = b"name,age,city\nJohn,30,NYC\nJane,25,LA"
        delimiter = detect_delimiter(content)
        self.assertEqual(delimiter, ',')
    
    def test_detect_delimiter_semicolon(self):
        """Test delimiter detection for semicolon-separated CSV"""
        content = b"name;age;city\nJohn;30;NYC\nJane;25;LA"
        delimiter = detect_delimiter(content)
        self.assertEqual(delimiter, ';')
    
    def test_detect_delimiter_tab(self):
        """Test delimiter detection for tab-separated CSV"""
        content = b"name\tage\tcity\nJohn\t30\tNYC\nJane\t25\tLA"
        delimiter = detect_delimiter(content)
        self.assertEqual(delimiter, '\t')
    
    def test_infer_type_integer(self):
        """Test type inference for integer values"""
        values = [1, 2, 3, 4, 5]
        type_info = infer_type_from_values(values)
        self.assertEqual(type_info['data_type'], 'integer')
        self.assertFalse(type_info['nullable'])
    
    def test_infer_type_float(self):
        """Test type inference for float values"""
        values = [1.5, 2.7, 3.2, 4.9, 5.1]
        type_info = infer_type_from_values(values)
        self.assertEqual(type_info['data_type'], 'float')
        self.assertFalse(type_info['nullable'])
    
    def test_infer_type_string(self):
        """Test type inference for string values"""
        values = ['apple', 'banana', 'cherry']
        type_info = infer_type_from_values(values)
        self.assertEqual(type_info['data_type'], 'string')
        self.assertFalse(type_info['nullable'])
    
    def test_infer_type_boolean(self):
        """Test type inference for boolean values"""
        values = ['true', 'false', 'true', 'false']
        type_info = infer_type_from_values(values)
        self.assertEqual(type_info['data_type'], 'boolean')
        self.assertFalse(type_info['nullable'])
    
    def test_infer_type_nullable(self):
        """Test type inference with null values"""
        values = [1, 2, None, 4, 5]
        type_info = infer_type_from_values(values)
        self.assertEqual(type_info['data_type'], 'integer')
        self.assertTrue(type_info['nullable'])
    
    def test_infer_schema_from_csv_simple(self):
        """Test schema inference from simple CSV"""
        csv_content = b"""name,age,city
John,30,NYC
Jane,25,LA
Bob,35,Chicago"""
        
        schema = infer_schema_from_csv(csv_content, sample_size=10)
        
        self.assertIn('fields', schema)
        self.assertEqual(len(schema['fields']), 3)
        
        # Check field names
        field_names = [f['name'] for f in schema['fields']]
        self.assertIn('name', field_names)
        self.assertIn('age', field_names)
        self.assertIn('city', field_names)
        
        # Check age field type (should be integer)
        age_field = next(f for f in schema['fields'] if f['name'] == 'age')
        self.assertEqual(age_field['data_type'], 'integer')
        
        # Check inference metadata
        self.assertIn('inference_metadata', schema)
        self.assertEqual(schema['inference_metadata']['format'], 'CSV')
    
    def test_infer_schema_from_csv_with_nulls(self):
        """Test schema inference from CSV with null values"""
        csv_content = b"""name,age,city
John,30,NYC
Jane,,LA
Bob,35,"""
        
        schema = infer_schema_from_csv(csv_content, sample_size=10)
        
        # Age field should be nullable
        age_field = next(f for f in schema['fields'] if f['name'] == 'age')
        self.assertTrue(age_field['nullable'])
        
        # City field should be nullable
        city_field = next(f for f in schema['fields'] if f['name'] == 'city')
        self.assertTrue(city_field['nullable'])
    
    def test_infer_schema_from_json_simple(self):
        """Test schema inference from simple JSON objects"""
        json_content = b"""{"name": "John", "age": 30, "city": "NYC"}
{"name": "Jane", "age": 25, "city": "LA"}
{"name": "Bob", "age": 35, "city": "Chicago"}"""
        
        schema = infer_schema_from_json(json_content, sample_size=10)
        
        self.assertIn('fields', schema)
        self.assertEqual(len(schema['fields']), 3)
        
        # Check field names
        field_names = [f['name'] for f in schema['fields']]
        self.assertIn('name', field_names)
        self.assertIn('age', field_names)
        self.assertIn('city', field_names)
        
        # Check inference metadata
        self.assertIn('inference_metadata', schema)
        self.assertEqual(schema['inference_metadata']['format'], 'JSON')
    
    def test_infer_schema_from_json_array(self):
        """Test schema inference from JSON array"""
        json_content = b"""[{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]"""
        
        schema = infer_schema_from_json(json_content, sample_size=10)
        
        self.assertIn('fields', schema)
        self.assertEqual(len(schema['fields']), 2)
    
    def test_infer_schema_from_json_nested(self):
        """Test schema inference from nested JSON objects"""
        json_content = b"""{"user": {"name": "John", "age": 30}, "city": "NYC"}
{"user": {"name": "Jane", "age": 25}, "city": "LA"}"""
        
        schema = infer_schema_from_json(json_content, sample_size=10)
        
        # Should flatten nested objects with dot notation
        field_names = [f['name'] for f in schema['fields']]
        self.assertIn('user.name', field_names)
        self.assertIn('user.age', field_names)
        self.assertIn('city', field_names)
    
    def test_infer_schema_from_csv_delimiter_detection(self):
        """Test CSV schema inference with different delimiters"""
        # Semicolon-delimited CSV
        csv_content = b"""name;age;city
John;30;NYC
Jane;25;LA"""
        
        schema = infer_schema_from_csv(csv_content, sample_size=10)
        
        self.assertIn('inference_metadata', schema)
        # Should detect semicolon delimiter
        self.assertEqual(schema['inference_metadata']['delimiter'], ';')
    
    def test_infer_schema_from_csv_primary_key_candidate(self):
        """Test primary key candidate detection"""
        csv_content = b"""id,name,age
1,John,30
2,Jane,25
3,Bob,35"""
        
        schema = infer_schema_from_csv(csv_content, sample_size=10)
        
        # ID field should be a primary key candidate (all unique, non-null)
        self.assertIn('primary_key_candidates', schema)
        self.assertIn('id', schema['primary_key_candidates'])

