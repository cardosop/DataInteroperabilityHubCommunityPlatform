"""
Tests for Input/Output Validators
"""
from typing import Optional
from uuid import UUID, uuid4

from django.test import TestCase
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

import uuid

from hub.apps.core.bug_prevention.validators import (
    InputValidator,
    OutputValidator,
    ValidationResult,
    IdempotencyKeyValidator,
    UUIDValidator,
)


class SampleModel(BaseModel):
    """Test Pydantic model."""
    model_config = ConfigDict(extra="forbid")  # Reject extra fields
    
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=150)
    email: Optional[str] = Field(None, pattern=r"^[^@]+@[^@]+\.[^@]+$")


class InputValidatorTest(TestCase):
    """Test InputValidator."""
    
    def test_validate_success(self):
        """Test successful validation."""
        data = {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com"
        }
        
        result = InputValidator.validate(SampleModel, data)
        
        self.assertTrue(result.is_valid)
        self.assertIsNotNone(result.data)
        self.assertEqual(result.data["name"], "John Doe")
        self.assertEqual(result.data["age"], 30)
        self.assertEqual(len(result.errors), 0)
    
    def test_validate_failure_missing_field(self):
        """Test validation failure with missing field."""
        data = {
            "age": 30
        }
        
        result = InputValidator.validate(SampleModel, data)
        
        self.assertFalse(result.is_valid)
        self.assertIsNone(result.data)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("name" in error["field"] for error in result.errors))
    
    def test_validate_failure_invalid_value(self):
        """Test validation failure with invalid value."""
        data = {
            "name": "John Doe",
            "age": -1,  # Invalid: negative age
            "email": "john@example.com"
        }
        
        result = InputValidator.validate(SampleModel, data)
        
        self.assertFalse(result.is_valid)
        self.assertIsNone(result.data)
        self.assertGreater(len(result.errors), 0)
    
    def test_validate_failure_invalid_email(self):
        """Test validation failure with invalid email."""
        data = {
            "name": "John Doe",
            "age": 30,
            "email": "invalid-email"  # Invalid email format
        }
        
        result = InputValidator.validate(SampleModel, data)
        
        self.assertFalse(result.is_valid)
        self.assertIsNone(result.data)
        self.assertGreater(len(result.errors), 0)
    
    def test_validate_and_raise_success(self):
        """Test validate_and_raise with valid data."""
        data = {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com"
        }
        
        instance = InputValidator.validate_and_raise(SampleModel, data)
        
        self.assertIsInstance(instance, SampleModel)
        self.assertEqual(instance.name, "John Doe")
        self.assertEqual(instance.age, 30)
    
    def test_validate_and_raise_failure(self):
        """Test validate_and_raise with invalid data."""
        data = {
            "name": "",  # Invalid: empty name
            "age": 30
        }
        
        with self.assertRaises(DRFValidationError):
            InputValidator.validate_and_raise(SampleModel, data)
    
    def test_validate_rejects_extra_fields(self):
        """Test that extra fields are rejected due to model's extra='forbid' config."""
        data = {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com",
            "extra_field": "should be rejected"
        }

        # SampleModel has extra="forbid", so extra fields should be rejected
        result = InputValidator.validate(SampleModel, data, strict=False)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("extra_field" in error["field"] for error in result.errors))

        # Extra fields should also be rejected with strict=True
        result = InputValidator.validate(SampleModel, data, strict=True)
        self.assertFalse(result.is_valid)

    def test_validate_strict_mode_type_coercion(self):
        """Test that strict mode controls type coercion (e.g. string to int)."""
        data = {
            "name": "John Doe",
            "age": "30",  # String instead of int
            "email": "john@example.com",
        }

        # With strict=False, Pydantic coerces "30" to int 30
        result = InputValidator.validate(SampleModel, data, strict=False)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.data["age"], 30)

        # With strict=True, Pydantic rejects the type mismatch
        result = InputValidator.validate(SampleModel, data, strict=True)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("age" in error["field"] for error in result.errors))


class OutputValidatorTest(TestCase):
    """Test OutputValidator."""
    
    def test_validate_success_dict(self):
        """Test successful validation with dictionary."""
        data = {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com"
        }
        
        result = OutputValidator.validate(SampleModel, data)
        
        self.assertTrue(result.is_valid)
        self.assertIsNotNone(result.data)
        self.assertEqual(result.data["name"], "John Doe")
    
    def test_validate_success_model(self):
        """Test successful validation with model instance."""
        instance = SampleModel(
            name="John Doe",
            age=30,
            email=f"john-{uuid.uuid4().hex[:8]}@example.com"
        )
        
        result = OutputValidator.validate(SampleModel, instance)
        
        self.assertTrue(result.is_valid)
        self.assertIsNotNone(result.data)
        self.assertEqual(result.data["name"], "John Doe")
    
    def test_validate_failure(self):
        """Test validation failure."""
        data = {
            "name": "",  # Invalid: empty name
            "age": 30
        }
        
        result = OutputValidator.validate(SampleModel, data)
        
        self.assertFalse(result.is_valid)
        self.assertIsNone(result.data)
        self.assertGreater(len(result.errors), 0)
    
    def test_validate_and_serialize_success(self):
        """Test validate_and_serialize with valid data."""
        data = {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com"
        }
        
        serialized = OutputValidator.validate_and_serialize(SampleModel, data)
        
        self.assertIsInstance(serialized, dict)
        self.assertEqual(serialized["name"], "John Doe")
        self.assertEqual(serialized["age"], 30)
    
    def test_validate_and_serialize_failure(self):
        """Test validate_and_serialize with invalid data."""
        data = {
            "name": "",  # Invalid: empty name
            "age": 30
        }
        
        with self.assertRaises(DRFValidationError):
            OutputValidator.validate_and_serialize(SampleModel, data)


class IdempotencyKeyValidatorTest(TestCase):
    """Test IdempotencyKeyValidator."""
    
    def test_validate_success(self):
        """Test successful validation."""
        key = "test-key-123"
        
        validator = IdempotencyKeyValidator(key=key)
        
        self.assertEqual(validator.key, key)
    
    def test_validate_too_short(self):
        """Test validation failure with too short key."""
        key = "short"  # Less than 8 characters
        
        with self.assertRaises(ValidationError):
            IdempotencyKeyValidator(key=key)
    
    def test_validate_too_long(self):
        """Test validation failure with too long key."""
        key = "a" * 257  # More than 256 characters
        
        with self.assertRaises(ValidationError):
            IdempotencyKeyValidator(key=key)
    
    def test_validate_invalid_characters(self):
        """Test validation failure with invalid characters."""
        key = "test key with spaces!"  # Contains spaces and exclamation
        
        with self.assertRaises(ValidationError):
            IdempotencyKeyValidator(key=key)
    
    def test_validate_valid_characters(self):
        """Test validation with valid characters."""
        valid_keys = [
            "test-key-123",
            "test_key_123",
            "test/key/123",
            "test1234",  # 8 characters (minimum length)
            "a" * 8,  # Minimum length
            "a" * 256,  # Maximum length
        ]
        
        for key in valid_keys:
            validator = IdempotencyKeyValidator(key=key)
            self.assertEqual(validator.key, key)


class UUIDValidatorTest(TestCase):
    """Test UUIDValidator."""
    
    def test_validate_success_string(self):
        """Test successful validation with string UUID."""
        uuid_str = str(uuid4())
        
        validator = UUIDValidator(value=uuid_str)
        
        self.assertIsInstance(validator.value, UUID)
        self.assertEqual(str(validator.value), uuid_str)
    
    def test_validate_success_uuid(self):
        """Test successful validation with UUID instance."""
        uuid_value = uuid4()
        
        validator = UUIDValidator(value=uuid_value)
        
        self.assertIsInstance(validator.value, UUID)
        self.assertEqual(validator.value, uuid_value)
    
    def test_validate_failure_invalid_format(self):
        """Test validation failure with invalid UUID format."""
        invalid_uuid = "not-a-uuid"
        
        with self.assertRaises(ValidationError):
            UUIDValidator(value=invalid_uuid)
    
    def test_validate_failure_wrong_type(self):
        """Test validation failure with wrong type."""
        invalid_value = 12345
        
        with self.assertRaises(ValidationError):
            UUIDValidator(value=invalid_value)

