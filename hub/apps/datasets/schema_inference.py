"""
Schema Inference Module

Infers schema from CSV, JSON, and Parquet files.
"""
import csv
import json
import io
from typing import Dict, List, Any, Optional
from datetime import datetime
import re

try:
    import pandas as pd
    import pyarrow.parquet as pq
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


# Default sample size for schema inference
DEFAULT_SAMPLE_SIZE = 10000
DEFAULT_SAMPLE_DATA_SIZE = 100


def detect_delimiter(content: bytes, sample_size: int = 1024) -> str:
    """
    Detect CSV delimiter from file content.
    
    Args:
        content: File content bytes
        sample_size: Number of bytes to sample
    
    Returns:
        Detected delimiter (comma, semicolon, tab, pipe)
    """
    sample = content[:sample_size].decode('utf-8', errors='ignore')
    
    delimiters = [',', ';', '\t', '|']
    delimiter_counts = {}
    
    for delim in delimiters:
        delimiter_counts[delim] = sample.count(delim)
    
    # Return delimiter with highest count
    if max(delimiter_counts.values()) > 0:
        return max(delimiter_counts, key=delimiter_counts.get)
    
    return ','  # Default to comma


def detect_encoding(content: bytes) -> str:
    """
    Detect file encoding.
    
    Args:
        content: File content bytes
    
    Returns:
        Detected encoding (default: utf-8)
    """
    # Try common encodings
    encodings = ['utf-8', 'utf-16', 'latin-1', 'windows-1252']
    
    for encoding in encodings:
        try:
            content.decode(encoding)
            return encoding
        except (UnicodeDecodeError, LookupError):
            continue
    
    return 'utf-8'  # Default


def infer_type_from_values(values: List[Any]) -> Dict[str, Any]:
    """
    Infer data type from a list of values.
    
    Args:
        values: List of sample values
    
    Returns:
        Dictionary with 'data_type', 'nullable', and other metadata
    """
    # Remove None/null values for type inference
    non_null_values = [v for v in values if v is not None and v != '']
    
    if not non_null_values:
        return {
            'data_type': 'string',
            'nullable': True
        }
    
    # Check for boolean
    bool_patterns = {
        'true', 'false', 'True', 'False', 'TRUE', 'FALSE',
        '1', '0', 'yes', 'no', 'Yes', 'No', 'YES', 'NO'
    }
    if all(str(v).strip() in bool_patterns for v in non_null_values):
        return {
            'data_type': 'boolean',
            'nullable': len(non_null_values) < len(values)
        }
    
    # Check for integer
    try:
        int_values = [int(float(v)) for v in non_null_values]
        # Check if all are actually integers (no decimals)
        if all(float(v) == int(float(v)) for v in non_null_values):
            return {
                'data_type': 'integer',
                'nullable': len(non_null_values) < len(values)
            }
    except (ValueError, TypeError):
        pass
    
    # Check for float
    try:
        float_values = [float(v) for v in non_null_values]
        return {
            'data_type': 'float',
            'nullable': len(non_null_values) < len(values)
        }
    except (ValueError, TypeError):
        pass
    
    # Check for date/datetime
    date_patterns = [
        r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
        r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',  # ISO 8601
        r'^\d{2}/\d{2}/\d{4}$',  # MM/DD/YYYY
    ]
    
    date_matches = 0
    for pattern in date_patterns:
        if all(re.match(pattern, str(v)) for v in non_null_values[:10]):  # Check first 10
            date_matches += 1
    
    if date_matches > 0:
        return {
            'data_type': 'datetime',
            'nullable': len(non_null_values) < len(values)
        }
    
    # Default to string
    return {
        'data_type': 'string',
        'nullable': len(non_null_values) < len(values)
    }


def infer_schema_from_csv(file_content: bytes, sample_size: int = DEFAULT_SAMPLE_SIZE) -> Dict[str, Any]:
    """
    Infer schema from CSV file.
    
    Args:
        file_content: CSV file content as bytes
        sample_size: Number of rows to sample (default: 10,000)
    
    Returns:
        Dictionary with inferred schema
    """
    # Detect encoding and delimiter
    encoding = detect_encoding(file_content)
    delimiter = detect_delimiter(file_content)
    
    # Decode content
    try:
        text_content = file_content.decode(encoding)
    except UnicodeDecodeError:
        text_content = file_content.decode('utf-8', errors='ignore')
    
    # Parse CSV
    csv_reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
    
    # Collect sample rows
    rows = []
    field_names = None
    
    for i, row in enumerate(csv_reader):
        if i == 0:
            field_names = list(row.keys())
        
        if i >= sample_size:
            break
        
        rows.append(row)
    
    if not field_names or not rows:
        raise ValueError("CSV file is empty or has no headers")
    
    # Infer schema for each field
    fields = []
    primary_key_candidates = []
    
    for field_name in field_names:
        values = [row.get(field_name) for row in rows]
        type_info = infer_type_from_values(values)
        
        field_schema = {
            'name': field_name,
            'data_type': type_info['data_type'],
            'nullable': type_info['nullable'],
            'sample_values': values[:10]  # First 10 sample values
        }
        
        fields.append(field_schema)
        
        # Check for potential primary key (all unique, non-null values)
        non_null_values = [v for v in values if v is not None and v != '']
        if len(non_null_values) == len(set(non_null_values)) and len(non_null_values) == len(values):
            primary_key_candidates.append(field_name)
    
    return {
        'fields': fields,
        'primary_key_candidates': primary_key_candidates,
        'row_count_estimated': len(rows),
        'inference_metadata': {
            'sample_size': len(rows),
            'strategy': 'first_n_rows',
            'format': 'CSV',
            'encoding': encoding,
            'delimiter': delimiter
        }
    }


def infer_schema_from_json(file_content: bytes, sample_size: int = DEFAULT_SAMPLE_SIZE) -> Dict[str, Any]:
    """
    Infer schema from JSON file (JSON Lines / NDJSON or single object/array).
    
    Args:
        file_content: JSON file content as bytes
        sample_size: Number of objects to sample (default: 10,000)
    
    Returns:
        Dictionary with inferred schema
    """
    text_content = file_content.decode('utf-8', errors='ignore')
    
    # Try JSON Lines format (one JSON object per line)
    objects = []
    lines = text_content.strip().split('\n')
    
    for line in lines[:sample_size]:
        line = line.strip()
        if not line:
            continue
        
        try:
            obj = json.loads(line)
            objects.append(obj)
        except json.JSONDecodeError:
            continue
    
    # If no objects found, try single JSON object/array
    if not objects:
        try:
            data = json.loads(text_content)
            if isinstance(data, list):
                objects = data[:sample_size]
            elif isinstance(data, dict):
                objects = [data]
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format")
    
    if not objects:
        raise ValueError("JSON file is empty or invalid")
    
    # Flatten nested objects (using dot notation)
    def flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict:
        """Flatten nested dictionary"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                # Handle arrays of objects (take first element)
                items.extend(flatten_dict(v[0], new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    # Flatten all objects
    flattened_objects = [flatten_dict(obj) for obj in objects]
    
    # Get all field names
    all_fields = set()
    for obj in flattened_objects:
        all_fields.update(obj.keys())
    
    # Infer schema for each field
    fields = []
    for field_name in sorted(all_fields):
        values = [obj.get(field_name) for obj in flattened_objects]
        type_info = infer_type_from_values(values)
        
        field_schema = {
            'name': field_name,
            'data_type': type_info['data_type'],
            'nullable': type_info['nullable'],
            'sample_values': values[:10]
        }
        
        fields.append(field_schema)
    
    return {
        'fields': fields,
        'primary_key_candidates': [],
        'row_count_estimated': len(objects),
        'inference_metadata': {
            'sample_size': len(objects),
            'strategy': 'first_n_objects',
            'format': 'JSON'
        }
    }


def infer_schema_from_parquet(file_content: bytes) -> Dict[str, Any]:
    """
    Infer schema from Parquet file.
    
    Args:
        file_content: Parquet file content as bytes
    
    Returns:
        Dictionary with inferred schema
    """
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas and pyarrow are required for Parquet schema inference")
    
    # Read Parquet file
    parquet_file = io.BytesIO(file_content)
    
    try:
        # Read with pandas
        df = pd.read_parquet(parquet_file)
        
        # Sample first 10,000 rows for type inference
        sample_df = df.head(10000)
        
        fields = []
        primary_key_candidates = []
        
        for column in df.columns:
            dtype = str(df[column].dtype)
            
            # Map pandas dtypes to our types
            if dtype.startswith('int'):
                data_type = 'integer'
            elif dtype.startswith('float'):
                data_type = 'float'
            elif dtype == 'bool':
                data_type = 'boolean'
            elif dtype.startswith('datetime'):
                data_type = 'datetime'
            else:
                data_type = 'string'
            
            # Check nullable
            nullable = df[column].isna().any()
            
            # Get sample values
            sample_values = sample_df[column].head(10).tolist()
            # Convert NaN to None
            sample_values = [None if pd.isna(v) else v for v in sample_values]
            
            field_schema = {
                'name': column,
                'data_type': data_type,
                'nullable': nullable,
                'sample_values': sample_values
            }
            
            fields.append(field_schema)
            
            # Check for potential primary key
            if not nullable and df[column].nunique() == len(df):
                primary_key_candidates.append(column)
        
        return {
            'fields': fields,
            'primary_key_candidates': primary_key_candidates,
            'row_count_estimated': len(df),
            'inference_metadata': {
                'sample_size': len(sample_df),
                'strategy': 'parquet_metadata',
                'format': 'PARQUET'
            }
        }
    
    except Exception as e:
        raise ValueError(f"Failed to read Parquet file: {str(e)}")


def extract_sample_data(file_content: bytes, format: str, sample_size: int = DEFAULT_SAMPLE_DATA_SIZE) -> List[Dict[str, Any]]:
    """
    Extract sample data from file (first N rows).
    
    Args:
        file_content: File content as bytes
        format: File format (CSV, JSON, PARQUET)
        sample_size: Number of rows to extract (default: 100)
    
    Returns:
        List of dictionaries representing sample rows
    """
    if format.upper() == 'CSV':
        encoding = detect_encoding(file_content)
        delimiter = detect_delimiter(file_content)
        text_content = file_content.decode(encoding, errors='ignore')
        
        csv_reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
        rows = []
        
        for i, row in enumerate(csv_reader):
            if i >= sample_size:
                break
            rows.append(row)
        
        return rows
    
    elif format.upper() == 'JSON':
        text_content = file_content.decode('utf-8', errors='ignore')
        lines = text_content.strip().split('\n')
        
        objects = []
        for line in lines[:sample_size]:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                objects.append(obj)
            except json.JSONDecodeError:
                continue
        
        # If no objects from lines, try single JSON
        if not objects:
            try:
                data = json.loads(text_content)
                if isinstance(data, list):
                    return data[:sample_size]
                elif isinstance(data, dict):
                    return [data]
            except json.JSONDecodeError:
                pass
        
        return objects
    
    elif format.upper() == 'PARQUET':
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas is required for Parquet sample extraction")
        
        parquet_file = io.BytesIO(file_content)
        df = pd.read_parquet(parquet_file)
        sample_df = df.head(sample_size)
        
        # Convert to list of dicts, handling NaN values
        return sample_df.replace({pd.NA: None}).to_dict('records')
    
    else:
        raise ValueError(f"Unsupported format: {format}")

