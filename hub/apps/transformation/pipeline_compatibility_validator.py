"""
Pipeline Compatibility Validator

Comprehensive validation for pipeline compatibility with input schemas, data types,
node compatibility, and pipeline definition structure.

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.cache import cache

from hub.apps.assets.models import Asset
from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.transformation.models import NodeType, TransformationPipeline

logger = logging.getLogger(__name__)

# Cache TTL for validation results (in seconds)
CACHE_TTL_VALIDATION = getattr(settings, "CACHE_TTL_PIPELINE_VALIDATION", 300)  # 5 minutes default

# Cache key prefix
CACHE_PREFIX_VALIDATION = "pipeline:compatibility:validation"


@dataclass
class SchemaField:
    """Represents a schema field with type information."""

    name: str
    data_type: str
    nullable: bool = True
    description: str | None = None
    format: str | None = None
    pattern: str | None = None
    enum: list[Any] | None = None
    default: Any | None = None
    min_length: int | None = None
    max_length: int | None = None
    minimum: float | None = None
    maximum: float | None = None

    @classmethod
    def from_dict(cls, field_dict: dict[str, Any]) -> "SchemaField":
        """Create SchemaField from dictionary."""
        return cls(
            name=field_dict.get("name", ""),
            data_type=field_dict.get("data_type") or field_dict.get("type", "string"),
            nullable=field_dict.get("nullable", True),
            description=field_dict.get("description"),
            format=field_dict.get("format"),
            pattern=field_dict.get("pattern"),
            enum=field_dict.get("enum"),
            default=field_dict.get("default"),
            min_length=field_dict.get("min_length") or field_dict.get("minLength"),
            max_length=field_dict.get("max_length") or field_dict.get("maxLength"),
            minimum=field_dict.get("minimum"),
            maximum=field_dict.get("maximum"),
        )


class PipelineCompatibilityValidator:
    """
    Validates pipeline compatibility with input schemas and pipeline definitions.

    Provides comprehensive validation for:
    - Schema compatibility (input schema vs pipeline input schema)
    - Data type compatibility (field types match)
    - Node compatibility (node types supported, node order valid)
    - Pipeline definition validation (required fields, valid structure)
    """

    # Valid node types
    VALID_NODE_TYPES = {choice[0] for choice in NodeType.choices}

    # Node execution order constraints
    NODE_DEPENDENCIES = {
        NodeType.FILTER: set(),  # Filter can be first
        NodeType.JOIN: {NodeType.FILTER},  # Join should come after filter
        NodeType.AGGREGATE: {
            NodeType.FILTER,
            NodeType.JOIN,
        },  # Aggregate needs filtered/joined data
        NodeType.TRANSFORM: {
            NodeType.FILTER,
            NodeType.JOIN,
            NodeType.AGGREGATE,
        },  # Transform can come after any
        NodeType.OUTPUT: {
            NodeType.FILTER,
            NodeType.JOIN,
            NodeType.AGGREGATE,
            NodeType.TRANSFORM,
        },  # Output should be last
    }

    # Required fields per node type
    NODE_REQUIRED_FIELDS = {
        NodeType.FILTER: {"filter_expression"},
        NodeType.JOIN: {"join_keys", "join_type"},
        NodeType.AGGREGATE: {"group_by", "aggregation_functions"},
        NodeType.TRANSFORM: {"transform_expression"},
        NodeType.OUTPUT: set(),  # Output nodes don't require specific fields
    }

    # Data type compatibility matrix
    # Maps source types to compatible target types
    TYPE_COMPATIBILITY = {
        "string": {"string", "text"},
        "integer": {"integer", "number", "float", "long"},
        "float": {"float", "number", "double"},
        "number": {"integer", "float", "number", "double", "long"},
        "boolean": {"boolean", "bool"},
        "date": {"date", "datetime", "timestamp"},
        "datetime": {"datetime", "timestamp", "date"},
        "timestamp": {"timestamp", "datetime", "date"},
        "array": {"array", "list"},
        "object": {"object", "dict", "json"},
    }

    def __init__(self, tenant_id: str | None = None, user_id: str | None = None):
        """
        Initialize validator.

        Args:
            tenant_id: Optional tenant ID for caching
            user_id: Optional user ID for caching
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

    def validate_pipeline_compatibility(
        self,
        pipeline: TransformationPipeline,
        input_schema: dict[str, Any] | None = None,
        input_asset: Asset | None = None,
        use_cache: bool = True,
    ) -> ValidationResult:
        """
        Comprehensive pipeline compatibility validation.

        Validates:
        - Schema compatibility (input schema vs pipeline input schema)
        - Data type compatibility (field types match)
        - Node compatibility (node types supported, node order valid)
        - Pipeline definition validation (required fields, valid structure)

        Args:
            pipeline: TransformationPipeline instance to validate
            input_schema: Optional input schema dictionary (if not provided, extracted from input_asset)
            input_asset: Optional input asset (used to extract schema if input_schema not provided)
            use_cache: Whether to use cached validation results

        Returns:
            ValidationResult with validation status, errors, warnings, and details
        """
        # Generate cache key if caching enabled
        cache_key = None
        if use_cache:
            cache_key = self._generate_cache_key(pipeline, input_schema, input_asset)
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Returning cached validation result for pipeline {pipeline.id}")
                return cached_result

        # Collect all validation results
        all_errors = []
        all_warnings = []
        all_details = {
            "pipeline_id": str(pipeline.id),
            "pipeline_name": pipeline.name,
            "validation_checks": {},
        }

        # 1. Validate pipeline definition structure
        definition_result = self.validate_pipeline_definition(pipeline)
        all_errors.extend(definition_result.errors)
        all_warnings.extend(definition_result.warnings)
        all_details["validation_checks"]["pipeline_definition"] = definition_result.details

        # 2. Validate node compatibility
        node_result = self.validate_node_compatibility(pipeline)
        all_errors.extend(node_result.errors)
        all_warnings.extend(node_result.warnings)
        all_details["validation_checks"]["node_compatibility"] = node_result.details

        # 3. Extract or get input schema
        effective_input_schema = input_schema
        if not effective_input_schema and input_asset:
            effective_input_schema = self._extract_schema_from_asset(input_asset)
            if effective_input_schema:
                all_details["input_schema_source"] = "asset"
                all_details["input_asset_id"] = str(input_asset.id)
            else:
                all_warnings.append(
                    f"Could not extract schema from input asset {input_asset.id}. "
                    f"Schema compatibility checks will be skipped."
                )
        elif effective_input_schema:
            all_details["input_schema_source"] = "provided"

        # 4. Validate schema compatibility if input schema available
        if effective_input_schema:
            schema_result = self.validate_schema_compatibility(pipeline, effective_input_schema)
            all_errors.extend(schema_result.errors)
            all_warnings.extend(schema_result.warnings)
            all_details["validation_checks"]["schema_compatibility"] = schema_result.details

            # 5. Validate data type compatibility
            data_type_result = self.validate_data_type_compatibility(
                pipeline, effective_input_schema
            )
            all_errors.extend(data_type_result.errors)
            all_warnings.extend(data_type_result.warnings)
            all_details["validation_checks"]["data_type_compatibility"] = data_type_result.details
        else:
            all_warnings.append(
                "No input schema provided. Schema and data type compatibility checks skipped."
            )
            all_details["validation_checks"]["schema_compatibility"] = {
                "skipped": True,
                "reason": "No input schema provided",
            }
            all_details["validation_checks"]["data_type_compatibility"] = {
                "skipped": True,
                "reason": "No input schema provided",
            }

        # Create final result
        result = ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            details=all_details,
        )

        # Cache result if caching enabled
        if use_cache and cache_key:
            cache.set(cache_key, result, CACHE_TTL_VALIDATION)
            logger.debug(f"Cached validation result for pipeline {pipeline.id}")

        return result

    def validate_pipeline_definition(self, pipeline: TransformationPipeline) -> ValidationResult:
        """
        Validate pipeline definition structure.

        Validates:
        - Pipeline definition is a valid JSON object
        - Required fields are present (version, steps)
        - Steps are valid (name, type, node_config)
        - Step structure is correct

        Args:
            pipeline: TransformationPipeline instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {"pipeline_id": str(pipeline.id), "pipeline_name": pipeline.name, "checks": {}}

        # Validate pipeline_definition is a dictionary
        if not isinstance(pipeline.get_pipeline_definition(), dict):
            errors.append("Pipeline definition must be a JSON object (dictionary)")
            details["checks"]["pipeline_definition_type"] = False
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        details["checks"]["pipeline_definition_type"] = True

        # Validate required fields
        required_fields = ["version", "steps"]
        for field in required_fields:
            if field not in pipeline.get_pipeline_definition():
                errors.append(f"Pipeline definition must contain '{field}' field")
                details["checks"][f"has_{field}"] = False
            else:
                details["checks"][f"has_{field}"] = True

        # Validate version format
        version = pipeline.get_pipeline_definition().get("version")
        if version:
            if not isinstance(version, str) or not version.strip():
                errors.append("Pipeline definition 'version' must be a non-empty string")
                details["checks"]["version_format"] = False
            else:
                details["checks"]["version_format"] = True
                details["version"] = version

        # Validate steps
        steps = pipeline.get_pipeline_definition().get("steps", [])
        if not isinstance(steps, list):
            errors.append("Pipeline definition 'steps' must be a list")
            details["checks"]["steps_type"] = False
        elif len(steps) == 0:
            errors.append("Pipeline definition must have at least one step")
            details["checks"]["steps_count"] = False
        else:
            details["checks"]["steps_type"] = True
            details["checks"]["steps_count"] = True
            details["step_count"] = len(steps)

            # Validate each step
            step_names = set()
            for i, step in enumerate(steps):
                step_errors = self._validate_step_structure(step, i)
                errors.extend(step_errors)

                # Check for duplicate step names
                step_name = step.get("name")
                if step_name:
                    if step_name in step_names:
                        errors.append(f"Duplicate step name '{step_name}' at index {i}")
                    else:
                        step_names.add(step_name)

            details["unique_step_names"] = len(step_names) == len(steps)
            if not details["unique_step_names"]:
                warnings.append("Some steps have duplicate names, which may cause confusion")

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def validate_node_compatibility(self, pipeline: TransformationPipeline) -> ValidationResult:
        """
        Validate node compatibility within a pipeline.

        Validates:
        - Node types are valid
        - Node execution order is valid
        - Required fields are present for each node type
        - Node dependencies are satisfied

        Args:
            pipeline: TransformationPipeline instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            "pipeline_id": str(pipeline.id),
            "pipeline_name": pipeline.name,
            "node_compatibility_checks": {},
        }

        steps = pipeline.get_pipeline_definition().get("steps", [])
        if not steps:
            errors.append("Pipeline has no steps to validate")
            details["node_compatibility_checks"]["has_steps"] = False
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        details["node_compatibility_checks"]["has_steps"] = True

        # Extract node types and their positions
        node_types_by_position = []
        for i, step in enumerate(steps):
            node_config = step.get("node_config", {})
            node_type = node_config.get("node_type")
            step_name = step.get("name", f"step_{i}")

            if node_type:
                node_types_by_position.append((i, step_name, node_type))

                # Validate node type
                if node_type not in self.VALID_NODE_TYPES:
                    errors.append(
                        f"Step '{step_name}' (index {i}) has invalid node_type '{node_type}'. "
                        f"Valid types: {', '.join(self.VALID_NODE_TYPES)}"
                    )
                    continue

                # Validate required fields for node type
                try:
                    node_type_enum = NodeType(node_type)
                    required_fields = self.NODE_REQUIRED_FIELDS.get(node_type_enum, set())

                    missing_fields = required_fields - set(node_config.keys())
                    if missing_fields:
                        errors.append(
                            f"Step '{step_name}' (node_type: {node_type}) is missing required fields: "
                            f"{', '.join(missing_fields)}"
                        )
                except ValueError:
                    # Already handled above
                    pass

        details["node_types_found"] = [nt for _, _, nt in node_types_by_position]
        details["node_count"] = len(node_types_by_position)

        # Validate node execution order
        if len(node_types_by_position) > 1:
            for i in range(len(node_types_by_position)):
                _pos, step_name, node_type = node_types_by_position[i]

                try:
                    node_type_enum = NodeType(node_type)
                    dependencies = self.NODE_DEPENDENCIES.get(node_type_enum, set())

                    # Check if dependencies are satisfied
                    preceding_types = {nt for _, _, nt in node_types_by_position[:i]}

                    missing_deps = dependencies - preceding_types
                    if missing_deps and dependencies:  # Only warn if there are required deps
                        warnings.append(
                            f"Step '{step_name}' (node_type: {node_type}) typically requires "
                            f"preceding nodes of type: {', '.join(missing_deps)}. "
                            f"Found: {', '.join(preceding_types) if preceding_types else 'none'}"
                        )
                except ValueError:
                    # Invalid node type already handled above
                    pass

        # Validate that there's at least one OUTPUT node
        output_nodes = [nt for _, _, nt in node_types_by_position if nt == "output"]
        if not output_nodes:
            warnings.append("Pipeline has no OUTPUT node. Pipeline may not produce output.")
        else:
            details["output_node_count"] = len(output_nodes)

        # Validate node-specific configurations
        for i, step in enumerate(steps):
            node_config = step.get("node_config", {})
            node_type = node_config.get("node_type")
            step_name = step.get("name", f"step_{i}")

            if node_type:
                node_errors = self._validate_node_config(node_type, node_config, step_name, i)
                errors.extend(node_errors)

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def validate_schema_compatibility(
        self, pipeline: TransformationPipeline, input_schema: dict[str, Any]
    ) -> ValidationResult:
        """
        Validate schema compatibility between input schema and pipeline input schema.

        Validates:
        - Pipeline input schema fields exist in input schema
        - All required pipeline fields are present in input schema
        - Field names match (case-sensitive)

        Args:
            pipeline: TransformationPipeline instance
            input_schema: Input schema dictionary with 'fields' key

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {"pipeline_id": str(pipeline.id), "schema_compatibility_checks": {}}

        # Extract pipeline input schema from pipeline definition
        pipeline_input_schema = pipeline.get_pipeline_definition().get("input_schema")
        if not pipeline_input_schema:
            # If no explicit input schema, extract from referenced fields in steps
            pipeline_input_schema = self._extract_pipeline_input_schema(pipeline)
            details["pipeline_input_schema_source"] = "extracted_from_steps"
        else:
            details["pipeline_input_schema_source"] = "explicit"

        if not pipeline_input_schema:
            warnings.append(
                "Pipeline does not define an input schema. Cannot validate schema compatibility."
            )
            details["schema_compatibility_checks"]["pipeline_input_schema_exists"] = False
            return ValidationResult(
                is_valid=True,  # Not an error, just a warning
                errors=errors,
                warnings=warnings,
                details=details,
            )

        details["schema_compatibility_checks"]["pipeline_input_schema_exists"] = True

        # Parse input schema fields
        input_fields = {}
        input_schema_fields = input_schema.get("fields", [])
        if not isinstance(input_schema_fields, list):
            errors.append("Input schema 'fields' must be a list")
            details["schema_compatibility_checks"]["input_schema_valid"] = False
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        for field_dict in input_schema_fields:
            if isinstance(field_dict, dict) and "name" in field_dict:
                field_name = field_dict["name"]
                input_fields[field_name] = SchemaField.from_dict(field_dict)

        details["input_field_count"] = len(input_fields)
        details["input_field_names"] = list(input_fields.keys())

        # Parse pipeline input schema fields
        pipeline_fields = {}
        pipeline_schema_fields = pipeline_input_schema.get("fields", [])
        if isinstance(pipeline_schema_fields, list):
            for field_dict in pipeline_schema_fields:
                if isinstance(field_dict, dict) and "name" in field_dict:
                    field_name = field_dict["name"]
                    pipeline_fields[field_name] = SchemaField.from_dict(field_dict)
        elif isinstance(pipeline_input_schema, dict):
            # Handle case where pipeline_input_schema is a dict with field names as keys
            for field_name, field_info in pipeline_input_schema.items():
                if isinstance(field_info, dict):
                    pipeline_fields[field_name] = SchemaField.from_dict(
                        {**field_info, "name": field_name}
                    )

        details["pipeline_field_count"] = len(pipeline_fields)
        details["pipeline_field_names"] = list(pipeline_fields.keys())

        # Validate all pipeline fields exist in input schema
        missing_fields = set(pipeline_fields.keys()) - set(input_fields.keys())
        if missing_fields:
            errors.append(
                f"Pipeline requires fields that are not present in input schema: "
                f"{', '.join(sorted(missing_fields))}"
            )
            details["schema_compatibility_checks"]["all_fields_present"] = False
            details["missing_fields"] = list(missing_fields)
        else:
            details["schema_compatibility_checks"]["all_fields_present"] = True

        # Check for extra fields in input schema (warning, not error)
        extra_fields = set(input_fields.keys()) - set(pipeline_fields.keys())
        if extra_fields:
            warnings.append(
                f"Input schema contains fields not referenced by pipeline: "
                f"{', '.join(sorted(extra_fields))}"
            )
            details["extra_fields"] = list(extra_fields)

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def validate_data_type_compatibility(
        self, pipeline: TransformationPipeline, input_schema: dict[str, Any]
    ) -> ValidationResult:
        """
        Validate data type compatibility between input schema and pipeline requirements.

        Validates:
        - Field types are compatible (using type compatibility matrix)
        - Type conversions are safe

        Args:
            pipeline: TransformationPipeline instance
            input_schema: Input schema dictionary with 'fields' key

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {"pipeline_id": str(pipeline.id), "data_type_compatibility_checks": {}}

        # Extract pipeline input schema
        pipeline_input_schema = pipeline.get_pipeline_definition().get("input_schema")
        if not pipeline_input_schema:
            pipeline_input_schema = self._extract_pipeline_input_schema(pipeline)

        if not pipeline_input_schema:
            warnings.append(
                "Pipeline does not define an input schema. Cannot validate data type compatibility."
            )
            details["data_type_compatibility_checks"]["pipeline_input_schema_exists"] = False
            return ValidationResult(
                is_valid=True, errors=errors, warnings=warnings, details=details
            )

        details["data_type_compatibility_checks"]["pipeline_input_schema_exists"] = True

        # Parse input schema fields
        input_fields = {}
        input_schema_fields = input_schema.get("fields", [])
        for field_dict in input_schema_fields:
            if isinstance(field_dict, dict) and "name" in field_dict:
                field_name = field_dict["name"]
                input_fields[field_name] = SchemaField.from_dict(field_dict)

        # Parse pipeline input schema fields
        pipeline_fields = {}
        pipeline_schema_fields = pipeline_input_schema.get("fields", [])
        if isinstance(pipeline_schema_fields, list):
            for field_dict in pipeline_schema_fields:
                if isinstance(field_dict, dict) and "name" in field_dict:
                    field_name = field_dict["name"]
                    pipeline_fields[field_name] = SchemaField.from_dict(field_dict)
        elif isinstance(pipeline_input_schema, dict):
            for field_name, field_info in pipeline_input_schema.items():
                if isinstance(field_info, dict):
                    pipeline_fields[field_name] = SchemaField.from_dict(
                        {**field_info, "name": field_name}
                    )

        # Validate type compatibility for common fields
        type_mismatches = []
        for field_name, pipeline_field in pipeline_fields.items():
            if field_name in input_fields:
                input_field = input_fields[field_name]
                input_type = input_field.data_type.lower()
                pipeline_type = pipeline_field.data_type.lower()

                # Check type compatibility
                compatible_types = self.TYPE_COMPATIBILITY.get(input_type, {input_type})
                if pipeline_type not in compatible_types and input_type != pipeline_type:
                    type_mismatches.append(
                        {
                            "field": field_name,
                            "input_type": input_type,
                            "pipeline_type": pipeline_type,
                            "compatible": False,
                        }
                    )
                    errors.append(
                        f"Field '{field_name}' has incompatible types: "
                        f"input schema has '{input_type}', pipeline expects '{pipeline_type}'"
                    )
                elif input_type != pipeline_type:
                    warnings.append(
                        f"Field '{field_name}' has different types but they are compatible: "
                        f"input schema has '{input_type}', pipeline expects '{pipeline_type}'"
                    )

        details["data_type_compatibility_checks"]["type_mismatches"] = type_mismatches
        details["data_type_compatibility_checks"]["all_types_compatible"] = (
            len(type_mismatches) == 0
        )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_step_structure(self, step: dict[str, Any], index: int) -> list[str]:
        """Validate a single step structure."""
        errors = []

        if not isinstance(step, dict):
            errors.append(f"Step {index} must be a JSON object")
            return errors

        # Validate required fields
        if "name" not in step:
            errors.append(f"Step {index} must have a 'name' field")
        elif not isinstance(step["name"], str) or not step["name"].strip():
            errors.append(f"Step {index} 'name' must be a non-empty string")

        if "type" not in step:
            errors.append(f"Step {index} must have a 'type' field")
        elif not isinstance(step["type"], str):
            errors.append(f"Step {index} 'type' must be a string")

        # Validate node_config if present
        node_config = step.get("node_config")
        if node_config is not None and not isinstance(node_config, dict):
            errors.append(f"Step {index} 'node_config' must be a JSON object")

        return errors

    def _validate_node_config(
        self, node_type: str, node_config: dict[str, Any], step_name: str, step_index: int
    ) -> list[str]:
        """Validate node-specific configuration."""
        errors = []

        try:
            node_type_enum = NodeType(node_type)
        except ValueError:
            # Invalid node type - already handled elsewhere
            return errors

        # Validate FILTER node
        if node_type_enum == NodeType.FILTER:
            filter_expr = node_config.get("filter_expression")
            if not filter_expr:
                errors.append(
                    f"Step '{step_name}' (FILTER node) must have 'filter_expression' in node_config"
                )
            elif not isinstance(filter_expr, str):
                errors.append(
                    f"Step '{step_name}' (FILTER node) 'filter_expression' must be a string"
                )

        # Validate JOIN node
        elif node_type_enum == NodeType.JOIN:
            join_keys = node_config.get("join_keys")
            join_type = node_config.get("join_type")

            if not join_keys and not join_type:
                errors.append(
                    f"Step '{step_name}' (JOIN node) must have either 'join_keys' or 'join_type' in node_config"
                )

            if join_keys and not isinstance(join_keys, (list, dict)):
                errors.append(
                    f"Step '{step_name}' (JOIN node) 'join_keys' must be a list or dictionary"
                )

            if join_type:
                valid_join_types = {"inner", "left", "right", "outer", "full"}
                if join_type not in valid_join_types:
                    errors.append(
                        f"Step '{step_name}' (JOIN node) 'join_type' must be one of: "
                        f"{', '.join(valid_join_types)}"
                    )

        # Validate AGGREGATE node
        elif node_type_enum == NodeType.AGGREGATE:
            group_by = node_config.get("group_by")
            agg_funcs = node_config.get("aggregation_functions")

            if not group_by:
                errors.append(
                    f"Step '{step_name}' (AGGREGATE node) must have 'group_by' in node_config"
                )
            elif not isinstance(group_by, (list, str)):
                errors.append(
                    f"Step '{step_name}' (AGGREGATE node) 'group_by' must be a list or string"
                )

            if not agg_funcs:
                errors.append(
                    f"Step '{step_name}' (AGGREGATE node) must have 'aggregation_functions' in node_config"
                )
            elif not isinstance(agg_funcs, (list, dict)):
                errors.append(
                    f"Step '{step_name}' (AGGREGATE node) 'aggregation_functions' must be a list or dictionary"
                )

        # Validate TRANSFORM node
        elif node_type_enum == NodeType.TRANSFORM:
            transform_expr = node_config.get("transform_expression")
            if not transform_expr:
                errors.append(
                    f"Step '{step_name}' (TRANSFORM node) must have 'transform_expression' in node_config"
                )
            elif not isinstance(transform_expr, (str, dict)):
                errors.append(
                    f"Step '{step_name}' (TRANSFORM node) 'transform_expression' must be a string or dictionary"
                )

        # OUTPUT node doesn't require specific validation

        return errors

    def _extract_pipeline_input_schema(
        self, pipeline: TransformationPipeline
    ) -> dict[str, Any] | None:
        """
        Extract pipeline input schema from pipeline steps.

        Analyzes pipeline steps to determine what fields are referenced,
        creating an implicit input schema.

        Args:
            pipeline: TransformationPipeline instance

        Returns:
            Dictionary representing pipeline input schema, or None if cannot be determined
        """
        referenced_fields = self._extract_referenced_fields(pipeline)
        if not referenced_fields:
            return None

        # Create a simple schema structure
        fields = []
        for field_name in sorted(referenced_fields):
            fields.append(
                {
                    "name": field_name,
                    "data_type": "string",  # Default type, actual type would need more analysis
                    "nullable": True,
                }
            )

        return {"fields": fields}

    def _extract_referenced_fields(self, pipeline: TransformationPipeline) -> set[str]:
        """
        Extract field names referenced in pipeline steps.

        Args:
            pipeline: TransformationPipeline instance

        Returns:
            Set of field names referenced in the pipeline
        """
        referenced_fields = set()
        steps = pipeline.get_pipeline_definition().get("steps", [])

        for step in steps:
            node_config = step.get("node_config", {})
            node_type = node_config.get("node_type")

            if node_type == "filter":
                # Extract fields from filter expression
                filter_expr = node_config.get("filter_expression", "")
                import re

                field_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b"
                matches = re.findall(field_pattern, filter_expr)
                keywords = {"and", "or", "not", "in", "is", "null", "true", "false", "if", "else"}
                referenced_fields.update(m for m in matches if m.lower() not in keywords)

            elif node_type == "join":
                join_keys = node_config.get("join_keys")
                if isinstance(join_keys, list):
                    referenced_fields.update(join_keys)
                elif isinstance(join_keys, dict):
                    referenced_fields.update(join_keys.keys())
                    referenced_fields.update(join_keys.values())
                elif isinstance(join_keys, str):
                    referenced_fields.add(join_keys)

            elif node_type == "aggregate":
                group_by = node_config.get("group_by")
                if isinstance(group_by, list):
                    referenced_fields.update(group_by)
                elif isinstance(group_by, str):
                    referenced_fields.add(group_by)

                agg_funcs = node_config.get("aggregation_functions", {})
                if isinstance(agg_funcs, dict):
                    referenced_fields.update(agg_funcs.keys())

            elif node_type == "transform":
                transform_expr = node_config.get("transform_expression", "")
                if isinstance(transform_expr, str):
                    import re

                    field_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b"
                    matches = re.findall(field_pattern, transform_expr)
                    keywords = {
                        "and",
                        "or",
                        "not",
                        "in",
                        "is",
                        "null",
                        "true",
                        "false",
                        "if",
                        "else",
                        "sum",
                        "avg",
                        "count",
                        "min",
                        "max",
                    }
                    referenced_fields.update(m for m in matches if m.lower() not in keywords)
                elif isinstance(transform_expr, dict):
                    for value in transform_expr.values():
                        if isinstance(value, str):
                            referenced_fields.add(value)

        return referenced_fields

    def _extract_schema_from_asset(self, asset: Asset) -> dict[str, Any] | None:
        """
        Extract schema from asset's latest dataset.

        Args:
            asset: Asset instance

        Returns:
            Schema dictionary or None if asset has no dataset
        """
        latest_dataset = asset.datasets.order_by("-version").first()
        if not latest_dataset:
            return None

        schema_json = latest_dataset.schema_json
        if not schema_json:
            return None

        # Ensure schema_json has 'fields' key
        if isinstance(schema_json, dict) and "fields" not in schema_json:
            # Try to convert if schema_json is a different format
            if "schema" in schema_json:
                schema_json = schema_json["schema"]
            else:
                # Assume schema_json itself is the schema
                pass

        return schema_json if isinstance(schema_json, dict) else None

    def _generate_cache_key(
        self,
        pipeline: TransformationPipeline,
        input_schema: dict[str, Any] | None,
        input_asset: Asset | None,
    ) -> str:
        """
        Generate cache key for validation result.

        Args:
            pipeline: TransformationPipeline instance
            input_schema: Optional input schema dictionary
            input_asset: Optional input asset

        Returns:
            Cache key string
        """
        key_parts = [
            CACHE_PREFIX_VALIDATION,
            str(pipeline.id),
            pipeline.version or "unknown",
        ]

        if input_asset:
            key_parts.append(f"asset:{input_asset.id}")
            # Include asset dataset version for cache invalidation
            latest_dataset = input_asset.datasets.order_by("-version").first()
            if latest_dataset:
                key_parts.append(f"dataset:{latest_dataset.version}")
        elif input_schema:
            # Hash input schema for cache key
            schema_str = json.dumps(input_schema, sort_keys=True, default=str)
            schema_hash = hashlib.md5(schema_str.encode()).hexdigest()[:16]
            key_parts.append(f"schema:{schema_hash}")

        if self.tenant_id:
            key_parts.append(f"tenant:{self.tenant_id}")

        return ":".join(key_parts)
