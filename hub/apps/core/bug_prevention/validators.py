"""
Input and Output Validation

Comprehensive validation using Pydantic for request/response validation.
"""

from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator
from rest_framework.exceptions import ValidationError as DRFValidationError

T = TypeVar("T", bound=BaseModel)


class ValidationResult:
    """Result of validation operation."""

    def __init__(
        self,
        is_valid: bool,
        data: dict[str, Any] | None = None,
        errors: list[dict[str, Any]] | None = None,
    ):
        self.is_valid = is_valid
        self.data = data
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {"is_valid": self.is_valid, "data": self.data, "errors": self.errors}


class InputValidator:
    """Input validation using Pydantic models."""

    @staticmethod
    def validate(
        model_class: type[T], data: dict[str, Any], strict: bool = False
    ) -> ValidationResult:
        """
        Validate input data against Pydantic model.

        Args:
            model_class: Pydantic model class
            data: Input data dictionary
            strict: Whether to use strict mode

        Returns:
            ValidationResult with validation status and errors
        """
        try:
            if strict:
                instance = model_class.model_validate(data, strict=True)
            else:
                instance = model_class.model_validate(data)

            return ValidationResult(is_valid=True, data=instance.model_dump())
        except ValidationError as e:
            errors = []
            for error in e.errors():
                errors.append(
                    {
                        "field": ".".join(str(loc) for loc in error.get("loc", [])),
                        "message": error.get("msg", "Validation error"),
                        "type": error.get("type", "validation_error"),
                        "input": error.get("input"),
                    }
                )

            return ValidationResult(is_valid=False, errors=errors)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[
                    {
                        "field": "__all__",
                        "message": f"Unexpected validation error: {e!s}",
                        "type": "unexpected_error",
                    }
                ],
            )

    @staticmethod
    def validate_and_raise(model_class: type[T], data: dict[str, Any], strict: bool = False) -> T:
        """
        Validate input data and raise exception if invalid.

        Args:
            model_class: Pydantic model class
            data: Input data dictionary
            strict: Whether to use strict mode

        Returns:
            Validated model instance

        Raises:
            DRFValidationError: If validation fails
        """
        result = InputValidator.validate(model_class, data, strict=strict)

        if not result.is_valid:
            error_messages = {}
            for error in result.errors:
                field = error["field"]
                if field not in error_messages:
                    error_messages[field] = []
                error_messages[field].append(error["message"])

            raise DRFValidationError(error_messages)

        return (
            model_class.model_validate(data, strict=strict)
            if strict
            else model_class.model_validate(data)
        )


class OutputValidator:
    """Output validation using Pydantic models."""

    @staticmethod
    def validate(
        model_class: type[T], data: dict[str, Any] | T, strict: bool = False
    ) -> ValidationResult:
        """
        Validate output data against Pydantic model.

        Args:
            model_class: Pydantic model class
            data: Output data (dict or model instance)
            strict: Whether to use strict mode

        Returns:
            ValidationResult with validation status and errors
        """
        try:
            if isinstance(data, model_class):
                # Already a model instance, just validate
                instance = data
            # Convert dict to model
            elif strict:
                instance = model_class.model_validate(data, strict=True)
            else:
                instance = model_class.model_validate(data)

            return ValidationResult(is_valid=True, data=instance.model_dump())
        except ValidationError as e:
            errors = []
            for error in e.errors():
                errors.append(
                    {
                        "field": ".".join(str(loc) for loc in error.get("loc", [])),
                        "message": error.get("msg", "Validation error"),
                        "type": error.get("type", "validation_error"),
                        "input": error.get("input"),
                    }
                )

            return ValidationResult(is_valid=False, errors=errors)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[
                    {
                        "field": "__all__",
                        "message": f"Unexpected validation error: {e!s}",
                        "type": "unexpected_error",
                    }
                ],
            )

    @staticmethod
    def validate_and_serialize(
        model_class: type[T], data: dict[str, Any] | T, strict: bool = False
    ) -> dict[str, Any]:
        """
        Validate output data and return serialized dictionary.

        Args:
            model_class: Pydantic model class
            data: Output data (dict or model instance)
            strict: Whether to use strict mode

        Returns:
            Serialized data dictionary

        Raises:
            DRFValidationError: If validation fails
        """
        result = OutputValidator.validate(model_class, data, strict=strict)

        if not result.is_valid:
            error_messages = {}
            for error in result.errors:
                field = error["field"]
                if field not in error_messages:
                    error_messages[field] = []
                error_messages[field].append(error["message"])

            raise DRFValidationError(error_messages)

        if isinstance(data, model_class):
            return data.model_dump()
        else:
            instance = (
                model_class.model_validate(data, strict=strict)
                if strict
                else model_class.model_validate(data)
            )
            return instance.model_dump()


# Common validation models


class UUIDValidator(BaseModel):
    """UUID validation model."""

    value: UUID = Field(..., description="UUID value")

    @field_validator("value", mode="before")
    @classmethod
    def validate_uuid(cls, value: Any) -> UUID:
        """Validate UUID format."""
        if isinstance(value, str):
            try:
                return UUID(value)
            except ValueError:
                raise ValueError("Invalid UUID format")
        elif isinstance(value, UUID):
            return value
        else:
            raise ValueError("UUID must be string or UUID instance")


class IdempotencyKeyValidator(BaseModel):
    """Idempotency key validation model."""

    key: str = Field(..., min_length=8, max_length=256, description="Idempotency key")

    @field_validator("key")
    @classmethod
    def validate_key_format(cls, value: str) -> str:
        """Validate idempotency key format."""
        import re

        pattern = r"^[a-zA-Z0-9\-_/]{8,256}$"
        if not re.match(pattern, value):
            raise ValueError(
                "Idempotency key must be 8-256 characters and contain only "
                "alphanumeric characters, hyphens, underscores, and forward slashes"
            )
        return value
