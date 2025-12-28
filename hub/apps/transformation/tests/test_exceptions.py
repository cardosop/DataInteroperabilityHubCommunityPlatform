"""
Unit tests for Transformation Error Hierarchy

Tests verify:
1. Error hierarchy structure and inheritance
2. Error code constants
3. Error context and details
4. Error serialization (to_dict)
5. HTTP status codes
6. Error message formatting
"""
import time
from django.test import TestCase

from hub.apps.transformation.exceptions import (
    TransformationError,
    TransformationValidationError,
    TransformationExecutionError,
    PipelineNotFoundError,
    AssetCompatibilityError,
    ResourceQuotaExceededError,
)
from hub.apps.core.services.base import ServiceError


class TransformationErrorTest(TestCase):
    """Test base TransformationError class"""

    def test_transformation_error_basic(self):
        """Test basic TransformationError creation"""
        error = TransformationError("Test error message")
        self.assertEqual(str(error), "TransformationError(TRANSFORMATION_UNKNOWN_ERROR): Test error message")
        self.assertEqual(error.message, "Test error message")
        self.assertEqual(error.error_code, TransformationError.ERROR_CODE_UNKNOWN)
        self.assertEqual(error.http_status, 500)
        self.assertEqual(error.details, {})

    def test_transformation_error_with_error_code(self):
        """Test TransformationError with custom error code"""
        error = TransformationError(
            "Test error",
            error_code=TransformationError.ERROR_CODE_VALIDATION_FAILED
        )
        self.assertEqual(error.error_code, TransformationError.ERROR_CODE_VALIDATION_FAILED)

    def test_transformation_error_with_details(self):
        """Test TransformationError with details"""
        details = {"field": "test_field", "value": 123}
        error = TransformationError("Test error", details=details)
        self.assertEqual(error.details, details)

    def test_transformation_error_with_http_status(self):
        """Test TransformationError with custom HTTP status"""
        error = TransformationError("Test error", http_status=400)
        self.assertEqual(error.http_status, 400)

    def test_transformation_error_with_tenant_user(self):
        """Test TransformationError with tenant and user IDs"""
        error = TransformationError(
            "Test error",
            tenant_id="tenant-123",
            user_id="user-456"
        )
        self.assertEqual(error.tenant_id, "tenant-123")
        self.assertEqual(error.user_id, "user-456")

    def test_transformation_error_with_cause(self):
        """Test TransformationError with cause exception"""
        cause = ValueError("Original error")
        error = TransformationError("Test error", cause=cause)
        self.assertEqual(error.cause, cause)
        self.assertEqual(error.details["cause_type"], "ValueError")
        self.assertEqual(error.details["cause_message"], "Original error")

    def test_transformation_error_to_dict(self):
        """Test TransformationError serialization to dict"""
        error = TransformationError(
            "Test error",
            error_code="TEST_ERROR",
            details={"key": "value"},
            http_status=400,
            tenant_id="tenant-123",
            user_id="user-456"
        )
        result = error.to_dict()

        self.assertEqual(result["error"], "TEST_ERROR")
        self.assertEqual(result["message"], "Test error")
        self.assertEqual(result["http_status"], 400)
        self.assertEqual(result["details"]["key"], "value")
        self.assertEqual(result["tenant_id"], "tenant-123")
        self.assertEqual(result["user_id"], "user-456")
        self.assertIn("timestamp", result)

    def test_transformation_error_to_dict_minimal(self):
        """Test TransformationError to_dict with minimal fields"""
        error = TransformationError("Test error")
        result = error.to_dict()

        self.assertEqual(result["error"], TransformationError.ERROR_CODE_UNKNOWN)
        self.assertEqual(result["message"], "Test error")
        self.assertEqual(result["http_status"], 500)
        self.assertNotIn("tenant_id", result)
        self.assertNotIn("user_id", result)
        self.assertIn("timestamp", result)

    def test_transformation_error_repr(self):
        """Test TransformationError representation"""
        error = TransformationError("Test error", error_code="TEST_ERROR")
        repr_str = repr(error)
        self.assertIn("TransformationError", repr_str)
        self.assertIn("TEST_ERROR", repr_str)
        self.assertIn("Test error", repr_str)

    def test_transformation_error_inherits_from_service_error(self):
        """Test that TransformationError inherits from ServiceError"""
        error = TransformationError("Test error")
        self.assertIsInstance(error, ServiceError)
        self.assertIsInstance(error, TransformationError)


class TransformationValidationErrorTest(TestCase):
    """Test TransformationValidationError class"""

    def test_validation_error_basic(self):
        """Test basic TransformationValidationError creation"""
        error = TransformationValidationError("Validation failed")
        self.assertEqual(error.error_code, TransformationValidationError.ERROR_CODE_VALIDATION_FAILED)
        self.assertEqual(error.http_status, 400)

    def test_validation_error_with_field_path(self):
        """Test TransformationValidationError with field path"""
        error = TransformationValidationError(
            "Validation failed",
            field_path="/pipeline/nodes/0"
        )
        self.assertEqual(error.details["field_path"], "/pipeline/nodes/0")

    def test_validation_error_with_expected_actual(self):
        """Test TransformationValidationError with expected and actual values"""
        error = TransformationValidationError(
            "Type mismatch",
            expected="string",
            actual=123
        )
        self.assertEqual(error.details["expected"], "string")
        self.assertEqual(error.details["actual"], 123)

    def test_validation_error_error_codes(self):
        """Test TransformationValidationError error code constants"""
        error = TransformationValidationError(
            "Invalid pipeline definition",
            error_code=TransformationValidationError.ERROR_CODE_INVALID_PIPELINE_DEFINITION
        )
        self.assertEqual(error.error_code, TransformationValidationError.ERROR_CODE_INVALID_PIPELINE_DEFINITION)

        error = TransformationValidationError(
            "Invalid node config",
            error_code=TransformationValidationError.ERROR_CODE_INVALID_NODE_CONFIG
        )
        self.assertEqual(error.error_code, TransformationValidationError.ERROR_CODE_INVALID_NODE_CONFIG)

    def test_validation_error_inherits_from_transformation_error(self):
        """Test that TransformationValidationError inherits from TransformationError"""
        error = TransformationValidationError("Validation failed")
        self.assertIsInstance(error, TransformationError)
        self.assertIsInstance(error, TransformationValidationError)
        self.assertIsInstance(error, ServiceError)


class TransformationExecutionErrorTest(TestCase):
    """Test TransformationExecutionError class"""

    def test_execution_error_basic(self):
        """Test basic TransformationExecutionError creation"""
        error = TransformationExecutionError("Execution failed")
        self.assertEqual(error.error_code, TransformationExecutionError.ERROR_CODE_EXECUTION_FAILED)
        self.assertEqual(error.http_status, 500)

    def test_execution_error_with_pipeline_execution_ids(self):
        """Test TransformationExecutionError with pipeline and execution IDs"""
        error = TransformationExecutionError(
            "Execution failed",
            pipeline_id="pipeline-123",
            execution_id="execution-456"
        )
        self.assertEqual(error.details["pipeline_id"], "pipeline-123")
        self.assertEqual(error.details["execution_id"], "execution-456")

    def test_execution_error_with_node_info(self):
        """Test TransformationExecutionError with node information"""
        error = TransformationExecutionError(
            "Node execution failed",
            node_id="node-789",
            step_name="filter_step"
        )
        self.assertEqual(error.details["node_id"], "node-789")
        self.assertEqual(error.details["step_name"], "filter_step")

    def test_execution_error_error_codes(self):
        """Test TransformationExecutionError error code constants"""
        error = TransformationExecutionError(
            "Execution timeout",
            error_code=TransformationExecutionError.ERROR_CODE_EXECUTION_TIMEOUT
        )
        self.assertEqual(error.error_code, TransformationExecutionError.ERROR_CODE_EXECUTION_TIMEOUT)

        error = TransformationExecutionError(
            "Node execution failed",
            error_code=TransformationExecutionError.ERROR_CODE_NODE_EXECUTION_FAILED
        )
        self.assertEqual(error.error_code, TransformationExecutionError.ERROR_CODE_NODE_EXECUTION_FAILED)

    def test_execution_error_inherits_from_transformation_error(self):
        """Test that TransformationExecutionError inherits from TransformationError"""
        error = TransformationExecutionError("Execution failed")
        self.assertIsInstance(error, TransformationError)
        self.assertIsInstance(error, TransformationExecutionError)


class PipelineNotFoundErrorTest(TestCase):
    """Test PipelineNotFoundError class"""

    def test_pipeline_not_found_error_basic(self):
        """Test basic PipelineNotFoundError creation"""
        error = PipelineNotFoundError("Pipeline not found")
        self.assertEqual(error.error_code, PipelineNotFoundError.ERROR_CODE_PIPELINE_NOT_FOUND)
        self.assertEqual(error.http_status, 404)

    def test_pipeline_not_found_error_with_pipeline_id(self):
        """Test PipelineNotFoundError with pipeline ID"""
        error = PipelineNotFoundError(
            "Pipeline not found",
            pipeline_id="pipeline-123"
        )
        self.assertEqual(error.details["pipeline_id"], "pipeline-123")

    def test_pipeline_not_found_error_error_codes(self):
        """Test PipelineNotFoundError error code constants"""
        error = PipelineNotFoundError(
            "Pipeline deleted",
            error_code=PipelineNotFoundError.ERROR_CODE_PIPELINE_DELETED
        )
        self.assertEqual(error.error_code, PipelineNotFoundError.ERROR_CODE_PIPELINE_DELETED)

        error = PipelineNotFoundError(
            "Pipeline archived",
            error_code=PipelineNotFoundError.ERROR_CODE_PIPELINE_ARCHIVED
        )
        self.assertEqual(error.error_code, PipelineNotFoundError.ERROR_CODE_PIPELINE_ARCHIVED)

    def test_pipeline_not_found_error_inherits_from_transformation_error(self):
        """Test that PipelineNotFoundError inherits from TransformationError"""
        error = PipelineNotFoundError("Pipeline not found")
        self.assertIsInstance(error, TransformationError)
        self.assertIsInstance(error, PipelineNotFoundError)


class AssetCompatibilityErrorTest(TestCase):
    """Test AssetCompatibilityError class"""

    def test_asset_compatibility_error_basic(self):
        """Test basic AssetCompatibilityError creation"""
        error = AssetCompatibilityError("Asset incompatible")
        self.assertEqual(error.error_code, AssetCompatibilityError.ERROR_CODE_ASSET_INCOMPATIBLE)
        self.assertEqual(error.http_status, 400)

    def test_asset_compatibility_error_with_asset_ids(self):
        """Test AssetCompatibilityError with asset IDs"""
        error = AssetCompatibilityError(
            "Asset incompatible",
            asset_id="asset-123",
            source_asset_id="source-456",
            target_asset_id="target-789"
        )
        self.assertEqual(error.details["asset_id"], "asset-123")
        self.assertEqual(error.details["source_asset_id"], "source-456")
        self.assertEqual(error.details["target_asset_id"], "target-789")

    def test_asset_compatibility_error_with_schemas(self):
        """Test AssetCompatibilityError with schema information"""
        expected_schema = {"type": "string", "format": "email"}
        actual_schema = {"type": "integer"}

        error = AssetCompatibilityError(
            "Schema mismatch",
            field_path="/email",
            expected_schema=expected_schema,
            actual_schema=actual_schema
        )
        self.assertEqual(error.details["field_path"], "/email")
        self.assertEqual(error.details["expected_schema"], expected_schema)
        self.assertEqual(error.details["actual_schema"], actual_schema)

    def test_asset_compatibility_error_error_codes(self):
        """Test AssetCompatibilityError error code constants"""
        error = AssetCompatibilityError(
            "Schema incompatible",
            error_code=AssetCompatibilityError.ERROR_CODE_SCHEMA_INCOMPATIBLE
        )
        self.assertEqual(error.error_code, AssetCompatibilityError.ERROR_CODE_SCHEMA_INCOMPATIBLE)

        error = AssetCompatibilityError(
            "Data type mismatch",
            error_code=AssetCompatibilityError.ERROR_CODE_DATA_TYPE_MISMATCH
        )
        self.assertEqual(error.error_code, AssetCompatibilityError.ERROR_CODE_DATA_TYPE_MISMATCH)

    def test_asset_compatibility_error_inherits_from_transformation_error(self):
        """Test that AssetCompatibilityError inherits from TransformationError"""
        error = AssetCompatibilityError("Asset incompatible")
        self.assertIsInstance(error, TransformationError)
        self.assertIsInstance(error, AssetCompatibilityError)


class ResourceQuotaExceededErrorTest(TestCase):
    """Test ResourceQuotaExceededError class"""

    def test_quota_exceeded_error_basic(self):
        """Test basic ResourceQuotaExceededError creation"""
        error = ResourceQuotaExceededError("Quota exceeded")
        self.assertEqual(error.error_code, ResourceQuotaExceededError.ERROR_CODE_QUOTA_EXCEEDED)
        self.assertEqual(error.http_status, 429)  # Too Many Requests

    def test_quota_exceeded_error_with_quota_info(self):
        """Test ResourceQuotaExceededError with quota information"""
        error = ResourceQuotaExceededError(
            "Execution time limit exceeded",
            quota_type="execution_time",
            limit=3600.0,
            current=3700.0
        )
        self.assertEqual(error.details["quota_type"], "execution_time")
        self.assertEqual(error.details["limit"], 3600.0)
        self.assertEqual(error.details["current"], 3700.0)

    def test_quota_exceeded_error_error_codes(self):
        """Test ResourceQuotaExceededError error code constants"""
        error = ResourceQuotaExceededError(
            "Execution time limit exceeded",
            error_code=ResourceQuotaExceededError.ERROR_CODE_EXECUTION_TIME_LIMIT
        )
        self.assertEqual(error.error_code, ResourceQuotaExceededError.ERROR_CODE_EXECUTION_TIME_LIMIT)

        error = ResourceQuotaExceededError(
            "Memory limit exceeded",
            error_code=ResourceQuotaExceededError.ERROR_CODE_MEMORY_LIMIT
        )
        self.assertEqual(error.error_code, ResourceQuotaExceededError.ERROR_CODE_MEMORY_LIMIT)

    def test_quota_exceeded_error_inherits_from_transformation_error(self):
        """Test that ResourceQuotaExceededError inherits from TransformationError"""
        error = ResourceQuotaExceededError("Quota exceeded")
        self.assertIsInstance(error, TransformationError)
        self.assertIsInstance(error, ResourceQuotaExceededError)


class ErrorHierarchyInheritanceTest(TestCase):
    """Test error hierarchy inheritance"""

    def test_error_inheritance(self):
        """Test that all error classes inherit from TransformationError"""
        self.assertTrue(issubclass(TransformationValidationError, TransformationError))
        self.assertTrue(issubclass(TransformationExecutionError, TransformationError))
        self.assertTrue(issubclass(PipelineNotFoundError, TransformationError))
        self.assertTrue(issubclass(AssetCompatibilityError, TransformationError))
        self.assertTrue(issubclass(ResourceQuotaExceededError, TransformationError))

        # All should also inherit from ServiceError
        self.assertTrue(issubclass(TransformationError, ServiceError))
        self.assertTrue(issubclass(TransformationValidationError, ServiceError))
        self.assertTrue(issubclass(TransformationExecutionError, ServiceError))
        self.assertTrue(issubclass(PipelineNotFoundError, ServiceError))
        self.assertTrue(issubclass(AssetCompatibilityError, ServiceError))
        self.assertTrue(issubclass(ResourceQuotaExceededError, ServiceError))

    def test_error_isinstance(self):
        """Test isinstance checks for error hierarchy"""
        validation_error = TransformationValidationError("Validation failed")
        self.assertIsInstance(validation_error, ServiceError)
        self.assertIsInstance(validation_error, TransformationError)
        self.assertIsInstance(validation_error, TransformationValidationError)

        execution_error = TransformationExecutionError("Execution failed")
        self.assertIsInstance(execution_error, ServiceError)
        self.assertIsInstance(execution_error, TransformationError)
        self.assertIsInstance(execution_error, TransformationExecutionError)

    def test_error_polymorphism(self):
        """Test error polymorphism in error handling"""
        errors = [
            TransformationValidationError("Validation failed"),
            TransformationExecutionError("Execution failed"),
            PipelineNotFoundError("Pipeline not found"),
            AssetCompatibilityError("Asset incompatible"),
            ResourceQuotaExceededError("Quota exceeded"),
        ]

        for error in errors:
            self.assertIsInstance(error, TransformationError)
            self.assertIsInstance(error, ServiceError)
            self.assertIn("error", error.to_dict())
            self.assertIn("message", error.to_dict())
            self.assertIn("http_status", error.to_dict())
            self.assertIn("timestamp", error.to_dict())


class ErrorSerializationTest(TestCase):
    """Test error serialization"""

    def test_error_serialization_basic(self):
        """Test basic error serialization"""
        error = TransformationError("Test error")
        result = error.to_dict()

        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("message", result)
        self.assertIn("http_status", result)
        self.assertIn("timestamp", result)

    def test_error_serialization_with_all_fields(self):
        """Test error serialization with all fields"""
        error = TransformationError(
            "Test error",
            error_code="CUSTOM_ERROR",
            details={"key1": "value1", "key2": 123},
            http_status=400,
            tenant_id="tenant-123",
            user_id="user-456"
        )
        result = error.to_dict()

        self.assertEqual(result["error"], "CUSTOM_ERROR")
        self.assertEqual(result["message"], "Test error")
        self.assertEqual(result["http_status"], 400)
        self.assertEqual(result["details"]["key1"], "value1")
        self.assertEqual(result["details"]["key2"], 123)
        self.assertEqual(result["tenant_id"], "tenant-123")
        self.assertEqual(result["user_id"], "user-456")
        self.assertIsInstance(result["timestamp"], int)

    def test_error_serialization_without_optional_fields(self):
        """Test error serialization without optional fields"""
        error = TransformationError("Test error")
        result = error.to_dict()

        self.assertNotIn("tenant_id", result)
        self.assertNotIn("user_id", result)
        # details is always included (initialized to empty dict)
        self.assertIn("details", result)
        self.assertEqual(result["details"], {})

    def test_error_serialization_empty_details(self):
        """Test error serialization with empty details dict"""
        error = TransformationError("Test error", details={})
        result = error.to_dict()

        # Empty details dict should still be included
        self.assertIn("details", result)
        self.assertEqual(result["details"], {})

    def test_error_serialization_nested_details(self):
        """Test error serialization with nested details"""
        nested_details = {
            "pipeline": {
                "id": "pipeline-123",
                "name": "Test Pipeline"
            },
            "nodes": [
                {"id": "node-1", "type": "filter"},
                {"id": "node-2", "type": "transform"}
            ]
        }
        error = TransformationError("Test error", details=nested_details)
        result = error.to_dict()

        self.assertEqual(result["details"]["pipeline"]["id"], "pipeline-123")
        self.assertEqual(result["details"]["nodes"][0]["type"], "filter")
        self.assertEqual(len(result["details"]["nodes"]), 2)

    def test_error_serialization_timestamp(self):
        """Test that error serialization includes timestamp"""
        before_time = int(time.time())
        error = TransformationError("Test error")
        after_time = int(time.time())

        result = error.to_dict()
        timestamp = result["timestamp"]

        self.assertIsInstance(timestamp, int)
        self.assertGreaterEqual(timestamp, before_time)
        self.assertLessEqual(timestamp, after_time)

    def test_error_serialization_json_serializable(self):
        """Test that error serialization is JSON-serializable"""
        import json

        error = TransformationError(
            "Test error",
            details={
                "pipeline_id": "pipeline-123",
                "node_count": 5,
                "is_active": True
            },
            tenant_id="tenant-123",
            user_id="user-456"
        )
        result = error.to_dict()

        # Should be JSON-serializable without errors
        json_str = json.dumps(result)
        self.assertIsInstance(json_str, str)

        # Should be able to deserialize
        deserialized = json.loads(json_str)
        self.assertEqual(deserialized["error"], result["error"])
        self.assertEqual(deserialized["message"], result["message"])

    def test_validation_error_serialization(self):
        """Test TransformationValidationError serialization"""
        error = TransformationValidationError(
            "Validation failed",
            field_path="/nodes/0",
            expected="string",
            actual=123
        )
        result = error.to_dict()

        self.assertEqual(result["error"], TransformationValidationError.ERROR_CODE_VALIDATION_FAILED)
        self.assertEqual(result["details"]["field_path"], "/nodes/0")
        self.assertEqual(result["details"]["expected"], "string")
        self.assertEqual(result["details"]["actual"], 123)

    def test_execution_error_serialization(self):
        """Test TransformationExecutionError serialization"""
        error = TransformationExecutionError(
            "Execution failed",
            pipeline_id="pipeline-123",
            execution_id="execution-456",
            node_id="node-789"
        )
        result = error.to_dict()

        self.assertEqual(result["details"]["pipeline_id"], "pipeline-123")
        self.assertEqual(result["details"]["execution_id"], "execution-456")
        self.assertEqual(result["details"]["node_id"], "node-789")

    def test_pipeline_not_found_error_serialization(self):
        """Test PipelineNotFoundError serialization"""
        error = PipelineNotFoundError(
            "Pipeline not found",
            pipeline_id="pipeline-123"
        )
        result = error.to_dict()

        self.assertEqual(result["error"], PipelineNotFoundError.ERROR_CODE_PIPELINE_NOT_FOUND)
        self.assertEqual(result["http_status"], 404)
        self.assertEqual(result["details"]["pipeline_id"], "pipeline-123")

    def test_asset_compatibility_error_serialization(self):
        """Test AssetCompatibilityError serialization"""
        error = AssetCompatibilityError(
            "Asset incompatible",
            pipeline_id="pipeline-123",
            asset_id="asset-456",
            field_path="/email"
        )
        result = error.to_dict()

        self.assertEqual(result["details"]["pipeline_id"], "pipeline-123")
        self.assertEqual(result["details"]["asset_id"], "asset-456")
        self.assertEqual(result["details"]["field_path"], "/email")

    def test_quota_exceeded_error_serialization(self):
        """Test ResourceQuotaExceededError serialization"""
        error = ResourceQuotaExceededError(
            "Quota exceeded",
            quota_type="execution_time",
            limit=3600.0,
            current=3700.0
        )
        result = error.to_dict()

        self.assertEqual(result["http_status"], 429)
        self.assertEqual(result["details"]["quota_type"], "execution_time")
        self.assertEqual(result["details"]["limit"], 3600.0)
        self.assertEqual(result["details"]["current"], 3700.0)

