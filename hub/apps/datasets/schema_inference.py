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
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    np = None


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


def infer_format_from_values(values: List[Any], field_name: str = '') -> Optional[str]:
    """
    Infer format from data patterns (GAP-8.2.4).
    
    Args:
        values: List of sample values
        field_name: Field name for context
    
    Returns:
        Format string (email, uri, date-time, etc.) or None
    """
    non_null_values = [str(v) for v in values if v is not None and v != '']
    if not non_null_values:
        return None
    
    # Email format
    email_pattern = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
    if all(email_pattern.match(v) for v in non_null_values[:10]):
        return 'email'
    
    # URI format
    uri_pattern = re.compile(r'^https?://|^ftp://|^file://|^[a-z][a-z0-9+.-]*://')
    if all(uri_pattern.match(v) for v in non_null_values[:10]):
        return 'uri'
    
    # Date-time format (ISO 8601)
    datetime_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
    if all(datetime_pattern.match(v) for v in non_null_values[:10]):
        return 'date-time'
    
    # Date format
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    if all(date_pattern.match(v) for v in non_null_values[:10]):
        return 'date'
    
    return None


def infer_pattern_from_values(values: List[Any]) -> Optional[str]:
    """
    Infer regex pattern from data patterns (GAP-8.2.4).
    
    Args:
        values: List of sample values
    
    Returns:
        Regex pattern string or None
    """
    non_null_values = [str(v) for v in values if v is not None and v != '']
    if len(non_null_values) < 3:
        return None
    
    # Try to find common patterns
    # Phone number pattern
    phone_pattern = re.compile(r'^\+?\d[\d\- ]{7,}$')
    if all(phone_pattern.match(v) for v in non_null_values[:10]):
        return r'^\+?\d[\d\- ]{7,}$'
    
    # UUID pattern
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    if all(uuid_pattern.match(v) for v in non_null_values[:10]):
        return r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    
    # Credit card pattern
    card_pattern = re.compile(r'^\d{13,19}$')
    if all(card_pattern.match(re.sub(r'\D', '', v)) for v in non_null_values[:10]):
        return r'^\d{13,19}$'
    
    # Alphanumeric code pattern (e.g., ORDER-12345)
    code_pattern = re.compile(r'^[A-Z]+-\d+$')
    if all(code_pattern.match(v) for v in non_null_values[:10]):
        return r'^[A-Z]+-\d+$'
    
    return None


def infer_enum_from_values(values: List[Any], max_enum_size: int = 20) -> Optional[List[Any]]:
    """
    Infer enum from limited unique values (GAP-8.2.4).
    
    Args:
        values: List of sample values
        max_enum_size: Maximum number of unique values to consider as enum
    
    Returns:
        List of enum values or None
    """
    non_null_values = [v for v in values if v is not None and v != '']
    if not non_null_values:
        return None
    
    unique_values = list(set(non_null_values))
    
    # If unique values are limited and represent a reasonable enum
    if len(unique_values) <= max_enum_size and len(unique_values) >= 2:
        # Check if enum makes sense:
        # - If we have few unique values relative to total (high repetition), it's likely an enum
        # - For small datasets (<= 10 samples), if we have 2-5 unique values, it's likely an enum
        # - For larger datasets, we want at least 2 samples per unique value on average, or unique values should be <= 50% of total
        unique_ratio = len(unique_values) / len(non_null_values) if non_null_values else 1.0
        avg_samples_per_value = len(non_null_values) / len(unique_values) if unique_values else 0
        
        # Consider it an enum if:
        # 1. Small dataset (<= 10 samples) with 2-5 unique values (likely categorical)
        # 2. Unique values are a small fraction of total (high repetition), OR
        # 3. We have at least 2 samples per unique value on average
        if len(non_null_values) <= 10 and 2 <= len(unique_values) <= 5:
            return sorted(unique_values)
        elif unique_ratio <= 0.5 or avg_samples_per_value >= 2.0:
            return sorted(unique_values)
    
    return None


def infer_semantic_type_from_field(field_name: str, values: List[Any]) -> Optional[str]:
    """
    Infer semantic type from column names and data patterns (GAP-8.2.4).
    
    Args:
        field_name: Field name
        values: List of sample values
    
    Returns:
        Semantic type identifier (ORDER_ID, EMAIL, PHONE_NUMBER, etc.) or None
    """
    field_name_lower = field_name.lower()
    
    # Map common field name patterns to semantic types
    semantic_type_map = {
        'order_id': 'ORDER_ID',
        'orderid': 'ORDER_ID',
        'order_number': 'ORDER_ID',
        'ordernumber': 'ORDER_ID',
        'email': 'EMAIL',
        'email_address': 'EMAIL',
        'emailaddress': 'EMAIL',
        'phone': 'PHONE_NUMBER',
        'phone_number': 'PHONE_NUMBER',
        'phonenumber': 'PHONE_NUMBER',
        'mobile': 'PHONE_NUMBER',
        'customer_id': 'CUSTOMER_ID',
        'customerid': 'CUSTOMER_ID',
        'user_id': 'USER_ID',
        'userid': 'USER_ID',
        'product_id': 'PRODUCT_ID',
        'productid': 'PRODUCT_ID',
        'transaction_id': 'TRANSACTION_ID',
        'transactionid': 'TRANSACTION_ID',
        'address': 'ADDRESS',
        'street_address': 'ADDRESS',
        'streetaddress': 'ADDRESS',
        'postal_code': 'POSTAL_CODE',
        'postalcode': 'POSTAL_CODE',
        'zip_code': 'POSTAL_CODE',
        'zipcode': 'POSTAL_CODE',
        'country': 'COUNTRY_CODE',
        'country_code': 'COUNTRY_CODE',
        'countrycode': 'COUNTRY_CODE',
        'currency': 'CURRENCY_CODE',
        'currency_code': 'CURRENCY_CODE',
        'currencycode': 'CURRENCY_CODE',
        'price': 'MONETARY_AMOUNT',
        'amount': 'MONETARY_AMOUNT',
        'total': 'MONETARY_AMOUNT',
        'url': 'URI',
        'uri': 'URI',
        'website': 'URI',
        'timestamp': 'TIMESTAMP',
        'created_at': 'TIMESTAMP',
        'createdat': 'TIMESTAMP',
        'updated_at': 'TIMESTAMP',
        'updatedat': 'TIMESTAMP',
    }
    
    # Check field name mapping
    for pattern, semantic_type in semantic_type_map.items():
        if pattern in field_name_lower:
            return semantic_type
    
    # Check data patterns if field name doesn't match
    non_null_values = [str(v) for v in values if v is not None and v != '']
    if non_null_values:
        # Email pattern
        email_pattern = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
        if all(email_pattern.match(v) for v in non_null_values[:10]):
            return 'EMAIL'
        
        # Phone pattern
        phone_pattern = re.compile(r'^\+?\d[\d\- ]{7,}$')
        if all(phone_pattern.match(v) for v in non_null_values[:10]):
            return 'PHONE_NUMBER'
        
        # URI pattern
        uri_pattern = re.compile(r'^https?://|^ftp://|^file://')
        if all(uri_pattern.match(v) for v in non_null_values[:10]):
            return 'URI'
    
    return None


def infer_field_properties(values: List[Any], field_name: str = '') -> Dict[str, Any]:
    """
    Infer enhanced field properties from values (GAP-8.2.4).
    
    Args:
        values: List of sample values
        field_name: Field name for context
    
    Returns:
        Dictionary with enhanced field properties
    """
    non_null_values = [v for v in values if v is not None and v != '']
    
    properties = {}
    
    # Infer format
    format_value = infer_format_from_values(values, field_name)
    if format_value:
        properties['format'] = format_value
    
    # Infer pattern
    pattern_value = infer_pattern_from_values(values)
    if pattern_value:
        properties['pattern'] = pattern_value
    
    # Infer enum
    enum_value = infer_enum_from_values(values)
    if enum_value:
        properties['enum'] = enum_value
    
    # Infer semantic type
    semantic_type = infer_semantic_type_from_field(field_name, values)
    if semantic_type:
        properties['semantic_type'] = semantic_type
    
    # Infer min/max length for strings
    if non_null_values:
        string_values = [str(v) for v in non_null_values]
        lengths = [len(v) for v in string_values]
        if lengths:
            properties['min_length'] = min(lengths)
            properties['max_length'] = max(lengths)
            # Only include if there's variation
            if min(lengths) == max(lengths):
                properties['min_length'] = min(lengths)
                properties['max_length'] = max(lengths)
    
    # Infer min/max value for numbers
    try:
        numeric_values = [float(v) for v in non_null_values]
        if numeric_values:
            properties['minimum'] = min(numeric_values)
            properties['maximum'] = max(numeric_values)
    except (ValueError, TypeError):
        pass
    
    # Infer default (most common value)
    if non_null_values:
        from collections import Counter
        value_counts = Counter(non_null_values)
        most_common = value_counts.most_common(1)[0]
        # Only set as default if it appears in at least 50% of values
        if most_common[1] >= len(non_null_values) * 0.5:
            properties['default'] = most_common[0]
    
    return properties


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
    
    # Infer schema for each field with enhanced properties (GAP-8.2.4)
    fields = []
    primary_key_candidates = []
    unique_constraint_candidates = []
    index_recommendations = []
    
    for field_name in field_names:
        values = [row.get(field_name) for row in rows]
        type_info = infer_type_from_values(values)
        
        # Infer enhanced field properties (GAP-8.2.4)
        enhanced_properties = infer_field_properties(values, field_name)
        
        field_schema = {
            'name': field_name,
            'data_type': type_info['data_type'],
            'nullable': type_info['nullable'],
            'sample_values': values[:10]  # First 10 sample values
        }
        
        # Add enhanced properties
        field_schema.update(enhanced_properties)
        
        fields.append(field_schema)
        
        # Check for potential primary key (all unique, non-null values)
        non_null_values = [v for v in values if v is not None and v != '']
        if len(non_null_values) == len(set(non_null_values)) and len(non_null_values) == len(values):
            primary_key_candidates.append(field_name)
        
        # Check for unique constraint (all unique values, but may have nulls)
        if len(non_null_values) == len(set(non_null_values)) and len(non_null_values) > 0:
            unique_constraint_candidates.append(field_name)
        
        # Recommend index for frequently queried patterns (GAP-8.2.4)
        # - ID fields (ends with _id)
        # - Foreign key patterns
        # - Timestamp fields
        if field_name.lower().endswith('_id') or field_name.lower().endswith('id'):
            index_recommendations.append({
                'field': field_name,
                'reason': 'ID field pattern',
                'priority': 'high'
            })
        elif 'timestamp' in field_name.lower() or 'created_at' in field_name.lower() or 'updated_at' in field_name.lower():
            index_recommendations.append({
                'field': field_name,
                'reason': 'Timestamp field',
                'priority': 'medium'
            })
    
    return {
        'fields': fields,
        'primary_key_candidates': primary_key_candidates,
        'unique_constraint_candidates': unique_constraint_candidates,
        'index_recommendations': index_recommendations,
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
            # Only accept dict objects in JSON Lines format
            # If it's a list, expand it
            if isinstance(obj, list):
                objects.extend([item for item in obj if isinstance(item, dict)][:sample_size])
            elif isinstance(obj, dict):
                objects.append(obj)
        except json.JSONDecodeError:
            continue
    
    # If no objects found, try single JSON object/array
    if not objects:
        try:
            data = json.loads(text_content)
            if isinstance(data, list):
                # Extract dict objects from list
                objects = [item for item in data if isinstance(item, dict)][:sample_size]
            elif isinstance(data, dict):
                objects = [data]
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format")
    
    if not objects:
        raise ValueError("JSON file is empty or invalid")
    
    # Flatten nested objects (using dot notation)
    def flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict:
        """Flatten nested dictionary"""
        if not isinstance(d, dict):
            return {}
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
    
    # Flatten all objects (ensure all are dicts)
    flattened_objects = [flatten_dict(obj) for obj in objects if isinstance(obj, dict)]
    
    # Get all field names
    all_fields = set()
    for obj in flattened_objects:
        all_fields.update(obj.keys())
    
    # Infer schema for each field with enhanced properties (GAP-8.2.4)
    fields = []
    primary_key_candidates = []
    unique_constraint_candidates = []
    index_recommendations = []
    
    for field_name in sorted(all_fields):
        values = [obj.get(field_name) for obj in flattened_objects]
        type_info = infer_type_from_values(values)
        
        # Infer enhanced field properties (GAP-8.2.4)
        enhanced_properties = infer_field_properties(values, field_name)
        
        field_schema = {
            'name': field_name,
            'data_type': type_info['data_type'],
            'nullable': type_info['nullable'],
            'sample_values': values[:10]
        }
        
        # Add enhanced properties
        field_schema.update(enhanced_properties)
        
        fields.append(field_schema)
        
        # Check for potential primary key and unique constraints
        non_null_values = [v for v in values if v is not None and v != '']
        if len(non_null_values) == len(set(non_null_values)) and len(non_null_values) == len(values):
            primary_key_candidates.append(field_name)
        elif len(non_null_values) == len(set(non_null_values)) and len(non_null_values) > 0:
            unique_constraint_candidates.append(field_name)
        
        # Recommend index for ID and timestamp fields
        if field_name.lower().endswith('_id') or field_name.lower().endswith('id'):
            index_recommendations.append({
                'field': field_name,
                'reason': 'ID field pattern',
                'priority': 'high'
            })
        elif 'timestamp' in field_name.lower() or 'created_at' in field_name.lower() or 'updated_at' in field_name.lower():
            index_recommendations.append({
                'field': field_name,
                'reason': 'Timestamp field',
                'priority': 'medium'
            })
    
    return {
        'fields': fields,
        'primary_key_candidates': primary_key_candidates,
        'unique_constraint_candidates': unique_constraint_candidates,
        'index_recommendations': index_recommendations,
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
        unique_constraint_candidates = []
        index_recommendations = []
        
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
            
            # Check nullable - convert numpy bool to Python bool
            nullable = bool(df[column].isna().any())
            
            # Get sample values
            sample_values = sample_df[column].head(10).tolist()
            # Convert NaN to None and numpy types to Python native types for JSON serialization
            def convert_to_json_serializable(v):
                if pd.isna(v):
                    return None
                # Convert numpy types to Python native types
                if np is not None:
                    # Convert numpy bool to Python bool
                    if isinstance(v, np.bool_):
                        return bool(v)
                    # Convert numpy int/float to Python int/float
                    if isinstance(v, (np.integer, np.int64, np.int32, np.int16, np.int8)):
                        return int(v)
                    if isinstance(v, (np.floating, np.float64, np.float32, np.float16)):
                        return float(v)
                    # For other numpy scalars, use item() method
                    if hasattr(v, 'item'):
                        return v.item()
                # Python native bool is already JSON serializable
                return v
            
            sample_values = [convert_to_json_serializable(v) for v in sample_values]
            
            # Infer enhanced field properties (GAP-8.2.4)
            enhanced_properties = infer_field_properties(sample_values, column)
            
            field_schema = {
                'name': column,
                'data_type': data_type,
                'nullable': nullable,
                'sample_values': sample_values
            }
            
            # Add enhanced properties
            field_schema.update(enhanced_properties)
            
            fields.append(field_schema)
            
            # Check for potential primary key
            if not nullable and df[column].nunique() == len(df):
                primary_key_candidates.append(column)
            
            # Check for unique constraint
            if df[column].nunique() == len(df[column].dropna()):
                unique_constraint_candidates.append(column)
            
            # Recommend index for ID and timestamp fields (GAP-8.2.4)
            if column.lower().endswith('_id') or column.lower().endswith('id'):
                index_recommendations.append({
                    'field': column,
                    'reason': 'ID field pattern',
                    'priority': 'high'
                })
            elif 'timestamp' in column.lower() or 'created_at' in column.lower() or 'updated_at' in column.lower():
                index_recommendations.append({
                    'field': column,
                    'reason': 'Timestamp field',
                    'priority': 'medium'
                })
        
        return {
            'fields': fields,
            'primary_key_candidates': primary_key_candidates,
            'unique_constraint_candidates': unique_constraint_candidates,
            'index_recommendations': index_recommendations,
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
                # Handle both dicts and lists in JSON Lines
                if isinstance(obj, list):
                    # Expand list items (only dicts)
                    objects.extend([item for item in obj if isinstance(item, dict)][:sample_size])
                elif isinstance(obj, dict):
                    objects.append(obj)
            except json.JSONDecodeError:
                continue
        
        # If no objects from lines, try single JSON
        if not objects:
            try:
                data = json.loads(text_content)
                if isinstance(data, list):
                    # Extract dict objects from list, limit to sample_size
                    return [item for item in data if isinstance(item, dict)][:sample_size]
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

