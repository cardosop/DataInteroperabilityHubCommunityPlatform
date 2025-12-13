"""
Test Factories for Datasets

Real factories (not mocks) for creating test data for Dataset models.
"""
import uuid
from typing import Optional, Dict, Any, List
from django.contrib.auth import get_user_model

from hub.apps.datasets.models import Dataset, DatasetKind
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset
from hub.apps.files.models import File

User = get_user_model()


class DatasetFactory:
    """Factory for creating Dataset instances"""
    
    @staticmethod
    def create_dataset(
        tenant: Tenant,
        file: File,
        asset: Optional[Asset] = None,
        schema_json: Optional[Dict[str, Any]] = None,
        sample_data_json: Optional[List[Dict[str, Any]]] = None,
        row_count: Optional[int] = None,
        format: Optional[str] = None,
        version: int = 1,
        created_by: Optional[User] = None,
        **kwargs
    ) -> Dataset:
        """
        Create a Dataset instance.
        
        Args:
            tenant: Tenant instance (required)
            file: File instance (required)
            asset: Asset instance (optional)
            schema_json: Inferred schema as JSON
            sample_data_json: Sample data (first 100 rows) as JSON array
            row_count: Total number of rows
            format: File format (CSV, JSON, PARQUET)
            version: Dataset version (default: 1)
            created_by: User who created the dataset
            **kwargs: Additional fields
            
        Returns:
            Dataset instance
        """
        if schema_json is None:
            schema_json = {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False,
                        "description": "Unique identifier"
                    },
                    {
                        "name": "value",
                        "type": "string",
                        "nullable": True,
                        "description": "Value field"
                    }
                ]
            }
        
        if sample_data_json is None:
            sample_data_json = [
                {"id": "1", "value": "test1"},
                {"id": "2", "value": "test2"}
            ]
        
        if row_count is None:
            row_count = 100
        
        if format is None:
            format = "CSV"
        
        return Dataset.objects.create(
            tenant=tenant,
            asset=asset,
            file=file,
            schema_json=schema_json,
            sample_data_json=sample_data_json,
            row_count=row_count,
            format=format,
            version=version,
            created_by=created_by,
            **kwargs
        )
    
    @staticmethod
    def create_dataset_with_complex_schema(
        tenant: Tenant,
        file: File,
        asset: Optional[Asset] = None,
        created_by: Optional[User] = None,
        **kwargs
    ) -> Dataset:
        """
        Create a Dataset with a complex schema (multiple fields, types, constraints).
        
        Args:
            tenant: Tenant instance
            file: File instance
            asset: Asset instance (optional)
            created_by: User who created the dataset
            **kwargs: Additional fields
            
        Returns:
            Dataset instance with complex schema
        """
        schema_json = {
            "fields": [
                {
                    "name": "id",
                    "type": "string",
                    "nullable": False,
                    "description": "Primary key",
                    "format": None,
                    "pattern": "^[A-Z0-9]{8}$",
                    "min_length": 8,
                    "max_length": 8
                },
                {
                    "name": "email",
                    "type": "string",
                    "nullable": False,
                    "description": "Email address",
                    "format": "email",
                    "max_length": 255
                },
                {
                    "name": "age",
                    "type": "integer",
                    "nullable": True,
                    "description": "Age in years",
                    "minimum": 0,
                    "maximum": 150
                },
                {
                    "name": "score",
                    "type": "number",
                    "nullable": True,
                    "description": "Score value",
                    "minimum": 0.0,
                    "maximum": 100.0
                },
                {
                    "name": "is_active",
                    "type": "boolean",
                    "nullable": False,
                    "description": "Active status",
                    "default": True
                },
                {
                    "name": "tags",
                    "type": "array",
                    "nullable": True,
                    "description": "Array of tags",
                    "items": {"type": "string"}
                }
            ],
            "primary_key": ["id"],
            "unique_constraints": [["email"]],
            "indexes": [["age"], ["score"]]
        }
        
        sample_data_json = [
            {
                "id": "ABC12345",
                "email": "user1@example.com",
                "age": 25,
                "score": 85.5,
                "is_active": True,
                "tags": ["premium", "active"]
            },
            {
                "id": "DEF67890",
                "email": "user2@example.com",
                "age": 30,
                "score": 92.0,
                "is_active": True,
                "tags": ["standard"]
            }
        ]
        
        return DatasetFactory.create_dataset(
            tenant=tenant,
            file=file,
            asset=asset,
            schema_json=schema_json,
            sample_data_json=sample_data_json,
            row_count=1000,
            created_by=created_by,
            **kwargs
        )

