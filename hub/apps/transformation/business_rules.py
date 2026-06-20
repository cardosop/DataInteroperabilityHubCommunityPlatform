"""
Transformation Business Rules

Comprehensive business rules validation for transformation pipelines, extending
the BusinessRules base class with transformation-specific validation logic.

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""

import logging
from dataclasses import dataclass
from typing import Any

from hub.apps.assets.models import Asset
from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.datasets.models import Dataset
from hub.apps.transformation.exceptions import (
    AssetCompatibilityError,
    ResourceQuotaExceededError,
    TransformationValidationError,
)
from hub.apps.transformation.models import (
    NodeType,
    PipelineStatus,
    TransformationPipeline,
)

logger = logging.getLogger(__name__)


@dataclass
class TransformationRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for transformation business rules.

    Adds transformation-specific context:
    - pipeline: The transformation pipeline being validated
    - source_asset: Optional source asset
    - target_asset: Optional target asset
    """

    pipeline: TransformationPipeline | None = None
    source_asset: Asset | None = None
    target_asset: Asset | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "pipeline_id": str(self.pipeline.id) if self.pipeline else None,
                "source_asset_id": str(self.source_asset.id) if self.source_asset else None,
                "target_asset_id": str(self.target_asset.id) if self.target_asset else None,
            }
        )
        return base_dict


@register_rule(
    rule_name="transformation_pipeline_validation",
    description="Validates transformation pipeline structure, node compatibility, and asset compatibility",
    tags=["transformation", "pipeline", "validation"],
    priority=10,
    openspec_ref="specs/transformation-business-rules/spec.md",
)
class TransformationBusinessRules(BusinessRules):
    """
    Business rules validator for transformation pipelines.

    Extends BusinessRules base class with transformation-specific validation:
    - Pipeline structure validation
    - Node compatibility validation
    - Schema alignment validation
    - Asset compatibility validation
    """

    # Valid node types
    VALID_NODE_TYPES = {choice[0] for choice in NodeType.choices}

    # Node execution order constraints
    # Nodes that must come before other nodes
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

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "TransformationBusinessRules"

    def validate(
        self, context: RuleExecutionContext | None = None, *args, **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all transformation validation checks.
        It can be called with a TransformationRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        pipeline and assets from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - pipeline: TransformationPipeline instance (required)
                - source_asset: Optional source Asset instance
                - target_asset: Optional target Asset instance
                - validation_type: Optional validation type filter
                    ('structure', 'node_compatibility', 'schema_alignment',
                     'asset_compatibility', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract pipeline and assets from context or kwargs
        if isinstance(context, TransformationRuleExecutionContext):
            pipeline = context.pipeline
            source_asset = context.source_asset
            target_asset = context.target_asset
        else:
            # Try to get from kwargs first
            pipeline = kwargs.get("pipeline")
            source_asset = kwargs.get("source_asset")
            target_asset = kwargs.get("target_asset")

            # If not in kwargs, try to get from context.metadata or context.resource
            if not pipeline:
                if (
                    context
                    and hasattr(context, "resource")
                    and isinstance(context.resource, TransformationPipeline)
                ):
                    pipeline = context.resource
                elif context and hasattr(context, "metadata"):
                    pipeline = context.metadata.get("pipeline")

            if not source_asset and context and hasattr(context, "metadata"):
                source_asset = context.metadata.get("source_asset")

            if not target_asset and context and hasattr(context, "metadata"):
                target_asset = context.metadata.get("target_asset")

        if not pipeline:
            return ValidationResult(
                is_valid=False,
                errors=["Pipeline is required for transformation validation"],
                details={"validation_type": "missing_pipeline"},
            )

        # Determine which validations to run
        validation_type = kwargs.get("validation_type", "all")

        # Run appropriate validations
        if validation_type == "structure":
            return self.validate_pipeline_structure(pipeline, raise_on_error=False)
        elif validation_type == "node_compatibility":
            return self.validate_node_compatibility(pipeline, raise_on_error=False)
        elif validation_type == "schema_alignment":
            if not source_asset:
                return ValidationResult(
                    is_valid=False,
                    errors=["Source asset is required for schema alignment validation"],
                    details={"validation_type": "schema_alignment"},
                )
            return self.validate_schema_alignment(
                pipeline, source_asset, target_asset, raise_on_error=False
            )
        elif validation_type == "asset_compatibility":
            if not source_asset:
                return ValidationResult(
                    is_valid=False,
                    errors=["Source asset is required for asset compatibility validation"],
                    details={"validation_type": "asset_compatibility"},
                )
            return self.validate_asset_compatibility(
                pipeline, source_asset, target_asset, raise_on_error=False
            )
        else:  # 'all' or default
            return self.validate_all(pipeline, source_asset, target_asset, raise_on_error=False)

    def validate_pipeline_structure(
        self, pipeline: TransformationPipeline, raise_on_error: bool = True
    ) -> ValidationResult:
        """
        Validate pipeline structure and definition.

        Validates:
        - Pipeline definition is a valid JSON object
        - Required fields are present (version, steps)
        - Steps are valid (name, type, node_config)
        - Node types are valid
        - Step ordering is valid

        Args:
            pipeline: TransformationPipeline instance to validate
            raise_on_error: If True, raise TransformationValidationError on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            TransformationValidationError: If validation fails and raise_on_error is True
        """
        errors = []
        warnings = []
        details = {
            "pipeline_id": str(pipeline.id),
            "pipeline_name": pipeline.name,
            "validation_checks": {},
        }

        # Validate pipeline_definition is a dictionary
        if not isinstance(pipeline.get_pipeline_definition(), dict):
            errors.append("Pipeline definition must be a JSON object (dictionary)")
            details["validation_checks"]["pipeline_definition_type"] = False
        else:
            details["validation_checks"]["pipeline_definition_type"] = True

            # Validate required fields
            required_fields = ["version", "steps"]
            for field in required_fields:
                if field not in pipeline.get_pipeline_definition():
                    errors.append(f"Pipeline definition must contain '{field}' field")
                    details["validation_checks"][f"has_{field}"] = False
                else:
                    details["validation_checks"][f"has_{field}"] = True

            # Validate version format
            version = pipeline.get_pipeline_definition().get("version")
            if version:
                if not isinstance(version, str) or not version.strip():
                    errors.append("Pipeline definition 'version' must be a non-empty string")
                    details["validation_checks"]["version_format"] = False
                else:
                    details["validation_checks"]["version_format"] = True

            # Validate steps
            steps = pipeline.get_pipeline_definition().get("steps", [])
            if not isinstance(steps, list):
                errors.append("Pipeline definition 'steps' must be a list")
                details["validation_checks"]["steps_type"] = False
            elif len(steps) == 0:
                errors.append("Pipeline definition must have at least one step")
                details["validation_checks"]["steps_count"] = False
            else:
                details["validation_checks"]["steps_type"] = True
                details["validation_checks"]["steps_count"] = True
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

        # Validate pipeline status
        valid_statuses = [choice[0] for choice in PipelineStatus.choices]
        if pipeline.status not in valid_statuses:
            errors.append(
                f"Invalid pipeline status '{pipeline.status}'. "
                f"Valid statuses: {', '.join(valid_statuses)}"
            )
            details["validation_checks"]["status_valid"] = False
        else:
            details["validation_checks"]["status_valid"] = True

        result = ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

        if not result.is_valid and raise_on_error:
            raise TransformationValidationError(
                message="Pipeline structure validation failed",
                error_code=TransformationValidationError.ERROR_CODE_INVALID_PIPELINE_DEFINITION,
                details=details,
                tenant_id=self.tenant_id,
            )

        return result

    def _validate_step_structure(self, step: dict[str, Any], index: int) -> list[str]:
        """
        Validate a single step structure.

        Args:
            step: Step dictionary
            index: Step index in the pipeline

        Returns:
            List of error messages
        """
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
        if node_config is not None:
            if not isinstance(node_config, dict):
                errors.append(f"Step {index} 'node_config' must be a JSON object")
            else:
                # Validate node_type if present
                node_type = node_config.get("node_type")
                if node_type and node_type not in self.VALID_NODE_TYPES:
                    errors.append(
                        f"Step {index} has invalid node_type '{node_type}'. "
                        f"Valid types: {', '.join(self.VALID_NODE_TYPES)}"
                    )

        return errors

    def validate_node_compatibility(
        self, pipeline: TransformationPipeline, raise_on_error: bool = True
    ) -> ValidationResult:
        """
        Validate node compatibility within a pipeline.

        Validates:
        - Node types are compatible with each other
        - Node execution order is valid
        - Required fields are present for each node type
        - Node dependencies are satisfied

        Args:
            pipeline: TransformationPipeline instance to validate
            raise_on_error: If True, raise TransformationValidationError on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            TransformationValidationError: If validation fails and raise_on_error is True
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
            result = ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )
            if raise_on_error:
                raise TransformationValidationError(
                    message="Pipeline has no steps",
                    error_code=TransformationValidationError.ERROR_CODE_INVALID_PIPELINE_DEFINITION,
                    details=details,
                    tenant_id=self.tenant_id,
                )
            return result

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
                        f"Step '{step_name}' (index {i}) has invalid node_type '{node_type}'"
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
                    if missing_deps and dependencies:  # Only error if there are required deps
                        # This is a warning, not an error, as some pipelines may have valid reasons
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

        result = ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

        if not result.is_valid and raise_on_error:
            raise TransformationValidationError(
                message="Node compatibility validation failed",
                error_code=TransformationValidationError.ERROR_CODE_INVALID_NODE_CONFIG,
                details=details,
                tenant_id=self.tenant_id,
            )

        return result

    # SQL/expression safety: deny dangerous patterns
    _DANGEROUS_PATTERNS = [
        "DROP ",
        "DELETE ",
        "TRUNCATE ",
        "ALTER ",
        "INSERT ",
        "UPDATE ",
        "CREATE ",
        "GRANT ",
        "REVOKE ",
        "EXEC ",
        "EXECUTE ",
        "xp_",
        "sp_",
        "INFORMATION_SCHEMA",
        "sys.",
        "pg_catalog",
        "pg_sleep",
        "--",
        "/*",
        "UNION SELECT",
        "INTO OUTFILE",
        "LOAD_FILE",
    ]

    @classmethod
    def _check_expression_safety(
        cls,
        expression: str,
        field_name: str,
        step_name: str,
    ) -> list[str]:
        """Check expression for dangerous SQL patterns."""
        errors = []
        upper = expression.upper()
        for pattern in cls._DANGEROUS_PATTERNS:
            if pattern.upper() in upper:
                errors.append(
                    f"Step '{step_name}': {field_name} "
                    f"contains forbidden pattern '{pattern.strip()}'"
                )
                break
        return errors

    def _validate_node_config(
        self, node_type: str, node_config: dict[str, Any], step_name: str, step_index: int
    ) -> list[str]:
        """
        Validate node-specific configuration.

        Args:
            node_type: Node type string
            node_config: Node configuration dictionary
            step_name: Step name
            step_index: Step index

        Returns:
            List of error messages
        """
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
            else:
                errors.extend(
                    self._check_expression_safety(
                        filter_expr,
                        "filter_expression",
                        step_name,
                    )
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
            elif isinstance(transform_expr, str):
                errors.extend(
                    self._check_expression_safety(
                        transform_expr,
                        "transform_expression",
                        step_name,
                    )
                )

        # OUTPUT node doesn't require specific validation

        return errors

    def validate_schema_alignment(
        self,
        pipeline: TransformationPipeline,
        source_asset: Asset,
        target_asset: Asset | None = None,
        raise_on_error: bool = True,
    ) -> ValidationResult:
        """
        Validate schema alignment between pipeline and assets.

        Validates:
        - Source asset schema is compatible with pipeline input requirements
        - Target asset schema (if provided) is compatible with pipeline output
        - Schema fields referenced in pipeline steps exist in source schema
        - Schema types are compatible with node operations

        Args:
            pipeline: TransformationPipeline instance
            source_asset: Source asset to validate
            target_asset: Optional target asset to validate
            raise_on_error: If True, raise AssetCompatibilityError on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            AssetCompatibilityError: If validation fails and raise_on_error is True
        """
        errors = []
        warnings = []
        details = {
            "pipeline_id": str(pipeline.id),
            "source_asset_id": str(source_asset.id),
            "schema_alignment_checks": {},
        }

        # Get source asset schema
        source_dataset = source_asset.datasets.order_by("-version").first()
        if not source_dataset:
            errors.append(f"Source asset '{source_asset.name}' has no dataset")
            details["schema_alignment_checks"]["source_dataset_exists"] = False
            result = ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )
            if raise_on_error:
                raise AssetCompatibilityError(
                    message="Source asset has no dataset",
                    error_code=AssetCompatibilityError.ERROR_CODE_SCHEMA_INCOMPATIBLE,
                    pipeline_id=str(pipeline.id),
                    asset_id=str(source_asset.id),
                    details=details,
                    tenant_id=self.tenant_id,
                )
            return result

        details["schema_alignment_checks"]["source_dataset_exists"] = True
        source_schema = source_dataset.schema_json or {}
        source_fields = {f.get("name"): f for f in source_schema.get("fields", [])}
        details["source_schema_fields"] = list(source_fields.keys())

        # Validate target asset schema if provided
        if target_asset:
            target_dataset = target_asset.datasets.order_by("-version").first()
            if target_dataset:
                target_schema = target_dataset.schema_json or {}
                target_fields = {f.get("name"): f for f in target_schema.get("fields", [])}
                details["target_schema_fields"] = list(target_fields.keys())
                details["schema_alignment_checks"]["target_dataset_exists"] = True
            else:
                warnings.append(f"Target asset '{target_asset.name}' has no dataset")
                details["schema_alignment_checks"]["target_dataset_exists"] = False

        # Extract field references from pipeline steps
        referenced_fields = self._extract_referenced_fields(pipeline)
        details["referenced_fields"] = list(referenced_fields)

        # Validate referenced fields exist in source schema
        missing_fields = referenced_fields - set(source_fields.keys())
        if missing_fields:
            errors.append(
                f"Pipeline references fields that don't exist in source asset schema: "
                f"{', '.join(missing_fields)}"
            )
            details["schema_alignment_checks"]["all_fields_present"] = False
            details["missing_fields"] = list(missing_fields)
        else:
            details["schema_alignment_checks"]["all_fields_present"] = True

        # Validate field types are compatible with node operations
        for field_name in referenced_fields:
            if field_name in source_fields:
                field_info = source_fields[field_name]
                field_type = field_info.get("data_type", "string")

                # Check if field type is compatible with operations
                # This is a basic check - more sophisticated validation can be added
                if field_type not in {"string", "integer", "float", "boolean", "date", "datetime"}:
                    warnings.append(
                        f"Field '{field_name}' has unusual data type '{field_type}'. "
                        f"Pipeline operations may not work as expected."
                    )

        result = ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

        if not result.is_valid and raise_on_error:
            raise AssetCompatibilityError(
                message="Schema alignment validation failed",
                error_code=AssetCompatibilityError.ERROR_CODE_SCHEMA_INCOMPATIBLE,
                pipeline_id=str(pipeline.id),
                asset_id=str(source_asset.id),
                expected_schema=source_schema,
                details=details,
                tenant_id=self.tenant_id,
            )

        return result

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
                # Extract fields from filter expression (basic parsing)
                filter_expr = node_config.get("filter_expression", "")
                # Simple extraction - look for common patterns
                # This is a simplified version - full expression parsing would be more robust
                import re

                # Match field names (alphanumeric with underscores, not starting with numbers)
                field_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b"
                matches = re.findall(field_pattern, filter_expr)
                # Filter out common keywords
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
                    # Extract field references from transform expression
                    import re

                    # Pattern to match field names, handling method calls (e.g., "name.upper()" -> "name")
                    # Match identifiers that are not followed by a dot (method calls) or are at the start
                    # This pattern matches: field names, but excludes method names after dots
                    # First, remove method calls (e.g., "name.upper()" -> "name")
                    # Replace method calls with just the field name
                    transform_expr_cleaned = re.sub(
                        r"\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", ".", transform_expr
                    )
                    # Now extract field names
                    field_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b"
                    matches = re.findall(field_pattern, transform_expr_cleaned)
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
                        "len",
                        "str",
                        "int",
                        "float",
                        "bool",
                    }
                    referenced_fields.update(m for m in matches if m.lower() not in keywords)
                elif isinstance(transform_expr, dict):
                    # If transform_expression is a dict, extract field names from values
                    for value in transform_expr.values():
                        if isinstance(value, str):
                            referenced_fields.add(value)

        return referenced_fields

    def validate_asset_compatibility(
        self,
        pipeline: TransformationPipeline,
        source_asset: Asset,
        target_asset: Asset | None = None,
        raise_on_error: bool = True,
    ) -> ValidationResult:
        """
        Validate asset compatibility with pipeline requirements.

        Validates:
        - Source asset is in a valid state (ACTIVE, has dataset)
        - Asset schema matches pipeline input schema
        - Asset data format is compatible (CSV, JSON, Parquet, etc.)
        - Asset size is validated (for execution mode selection: sync vs async)
        - User has access to asset (cross-tenant access validation)
        - Target asset (if provided) is compatible

        Args:
            pipeline: TransformationPipeline instance
            source_asset: Source asset to validate
            target_asset: Optional target asset to validate
            raise_on_error: If True, raise AssetCompatibilityError on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            AssetCompatibilityError: If validation fails and raise_on_error is True
        """
        errors = []
        warnings = []
        details = {
            "pipeline_id": str(pipeline.id),
            "source_asset_id": str(source_asset.id),
            "asset_compatibility_checks": {},
        }

        # Validate source asset status
        from hub.apps.assets.models import AssetStatus

        valid_source_statuses = [AssetStatus.ACTIVE, AssetStatus.PUBLIC]
        if source_asset.status not in valid_source_statuses:
            errors.append(
                f"Source asset '{source_asset.name}' must be ACTIVE or PUBLIC. "
                f"Current status: {source_asset.status}"
            )
            details["asset_compatibility_checks"]["source_asset_status"] = False
        else:
            details["asset_compatibility_checks"]["source_asset_status"] = True

        # Validate source asset has dataset
        source_dataset = source_asset.datasets.order_by("-version").first()
        if not source_dataset:
            errors.append(f"Source asset '{source_asset.name}' has no dataset")
            details["asset_compatibility_checks"]["source_dataset_exists"] = False
            result = ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )
            if raise_on_error:
                raise AssetCompatibilityError(
                    message="Source asset has no dataset",
                    error_code=AssetCompatibilityError.ERROR_CODE_ASSET_INCOMPATIBLE,
                    pipeline_id=str(pipeline.id),
                    asset_id=str(source_asset.id),
                    source_asset_id=str(source_asset.id),
                    target_asset_id=str(target_asset.id) if target_asset else None,
                    details=details,
                    tenant_id=self.tenant_id,
                )
            return result

        details["asset_compatibility_checks"]["source_dataset_exists"] = True
        details["source_dataset_format"] = source_dataset.format
        details["source_dataset_version"] = source_dataset.version

        # 1. Validate asset schema matches pipeline input schema
        schema_validation_result = self._validate_asset_schema_compatibility(
            pipeline, source_asset, source_dataset
        )
        errors.extend(schema_validation_result["errors"])
        warnings.extend(schema_validation_result["warnings"])
        details["asset_compatibility_checks"]["schema_validation"] = schema_validation_result[
            "details"
        ]

        # 2. Validate asset data format (CSV, JSON, Parquet, etc.)
        format_validation_result = self._validate_asset_format_compatibility(source_dataset)
        errors.extend(format_validation_result["errors"])
        warnings.extend(format_validation_result["warnings"])
        details["asset_compatibility_checks"]["format_validation"] = format_validation_result[
            "details"
        ]

        # 3. Validate asset size (for execution mode selection: sync vs async)
        size_validation_result = self._validate_asset_size_for_execution_mode(source_dataset)
        errors.extend(size_validation_result["errors"])
        warnings.extend(size_validation_result["warnings"])
        details["asset_compatibility_checks"]["size_validation"] = size_validation_result["details"]

        # 4. Validate asset access (user has access to asset)
        access_validation_result = self._validate_asset_access(source_asset)
        errors.extend(access_validation_result["errors"])
        warnings.extend(access_validation_result["warnings"])
        details["asset_compatibility_checks"]["access_validation"] = access_validation_result[
            "details"
        ]

        # Validate target asset if provided
        if target_asset:
            details["target_asset_id"] = str(target_asset.id)

            valid_target_statuses = [AssetStatus.ACTIVE, AssetStatus.DRAFT]
            if target_asset.status not in valid_target_statuses:
                errors.append(
                    f"Target asset '{target_asset.name}' must be ACTIVE or DRAFT. "
                    f"Current status: {target_asset.status}"
                )
                details["asset_compatibility_checks"]["target_asset_status"] = False
            else:
                details["asset_compatibility_checks"]["target_asset_status"] = True

            # Validate target asset has dataset (optional for new assets)
            target_dataset = target_asset.datasets.order_by("-version").first()
            if target_dataset:
                details["target_dataset_format"] = target_dataset.format
                details["target_dataset_version"] = target_dataset.version
                details["asset_compatibility_checks"]["target_dataset_exists"] = True
            else:
                details["asset_compatibility_checks"]["target_dataset_exists"] = False

        # Validate tenant compatibility
        if self.tenant_id:
            if str(source_asset.tenant_id) != self.tenant_id:
                errors.append(
                    f"Source asset belongs to different tenant. "
                    f"Expected: {self.tenant_id}, Got: {source_asset.tenant_id}"
                )
                details["asset_compatibility_checks"]["tenant_match"] = False
            else:
                details["asset_compatibility_checks"]["tenant_match"] = True

            if target_asset and str(target_asset.tenant_id) != self.tenant_id:
                errors.append(
                    f"Target asset belongs to different tenant. "
                    f"Expected: {self.tenant_id}, Got: {target_asset.tenant_id}"
                )
                details["asset_compatibility_checks"]["target_tenant_match"] = False
            elif target_asset:
                details["asset_compatibility_checks"]["target_tenant_match"] = True

        result = ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

        if not result.is_valid and raise_on_error:
            raise AssetCompatibilityError(
                message="Asset compatibility validation failed",
                error_code=AssetCompatibilityError.ERROR_CODE_ASSET_INCOMPATIBLE,
                pipeline_id=str(pipeline.id),
                asset_id=str(source_asset.id),
                source_asset_id=str(source_asset.id),
                target_asset_id=str(target_asset.id) if target_asset else None,
                details=details,
                tenant_id=self.tenant_id,
            )

        return result

    def validate_all(
        self,
        pipeline: TransformationPipeline,
        source_asset: Asset | None = None,
        target_asset: Asset | None = None,
        raise_on_error: bool = True,
    ) -> ValidationResult:
        """
        Run all validation checks.

        Args:
            pipeline: TransformationPipeline instance
            source_asset: Optional source asset
            target_asset: Optional target asset
            raise_on_error: If True, raise exception on validation failure

        Returns:
            Combined ValidationResult with all validation results
        """
        all_errors = []
        all_warnings = []
        all_details = {"pipeline_id": str(pipeline.id), "validation_results": {}}

        # Validate pipeline structure
        structure_result = self.validate_pipeline_structure(pipeline, raise_on_error=False)
        all_errors.extend(structure_result.errors)
        all_warnings.extend(structure_result.warnings)
        all_details["validation_results"]["structure"] = structure_result.details

        # Validate node compatibility
        node_result = self.validate_node_compatibility(pipeline, raise_on_error=False)
        all_errors.extend(node_result.errors)
        all_warnings.extend(node_result.warnings)
        all_details["validation_results"]["node_compatibility"] = node_result.details

        # Validate asset compatibility if assets provided
        if source_asset:
            asset_result = self.validate_asset_compatibility(
                pipeline, source_asset, target_asset, raise_on_error=False
            )
            all_errors.extend(asset_result.errors)
            all_warnings.extend(asset_result.warnings)
            all_details["validation_results"]["asset_compatibility"] = asset_result.details

            # Validate schema alignment
            schema_result = self.validate_schema_alignment(
                pipeline, source_asset, target_asset, raise_on_error=False
            )
            all_errors.extend(schema_result.errors)
            all_warnings.extend(schema_result.warnings)
            all_details["validation_results"]["schema_alignment"] = schema_result.details

        result = ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            details=all_details,
        )

        if not result.is_valid and raise_on_error:
            # Determine appropriate exception type
            if any("schema" in err.lower() or "field" in err.lower() for err in all_errors):
                raise AssetCompatibilityError(
                    message="Pipeline validation failed",
                    error_code=AssetCompatibilityError.ERROR_CODE_SCHEMA_INCOMPATIBLE,
                    pipeline_id=str(pipeline.id),
                    asset_id=str(source_asset.id) if source_asset else None,
                    details=all_details,
                    tenant_id=self.tenant_id,
                )
            else:
                raise TransformationValidationError(
                    message="Pipeline validation failed",
                    error_code=TransformationValidationError.ERROR_CODE_VALIDATION_FAILED,
                    details=all_details,
                    tenant_id=self.tenant_id,
                )

        return result

    def _validate_asset_schema_compatibility(
        self, pipeline: TransformationPipeline, source_asset: Asset, source_dataset: "Dataset"
    ) -> dict[str, Any]:
        """
        Validate asset schema matches pipeline input schema.

        Args:
            pipeline: TransformationPipeline instance
            source_asset: Source asset
            source_dataset: Source dataset

        Returns:
            Dictionary with errors, warnings, and details
        """
        errors = []
        warnings = []
        details = {
            "asset_schema_valid": False,
            "pipeline_input_schema_exists": False,
            "schema_fields_match": False,
            "missing_fields": [],
            "type_mismatches": [],
        }

        # Get asset schema from dataset
        asset_schema = source_dataset.schema_json
        if not asset_schema:
            errors.append(f"Source asset '{source_asset.name}' dataset has no schema")
            return {"errors": errors, "warnings": warnings, "details": details}

        asset_fields = asset_schema.get("fields", [])
        if not isinstance(asset_fields, list):
            errors.append("Asset schema 'fields' must be a list")
            return {"errors": errors, "warnings": warnings, "details": details}

        # Create field map from asset schema
        asset_field_map = {}
        for field_dict in asset_fields:
            field_name = field_dict.get("name")
            if field_name:
                asset_field_map[field_name] = {
                    "data_type": field_dict.get("data_type") or field_dict.get("type", "string"),
                    "nullable": field_dict.get("nullable", True),
                }

        details["asset_field_count"] = len(asset_field_map)
        details["asset_fields"] = list(asset_field_map.keys())

        # Extract pipeline input schema
        pipeline_input_schema = pipeline.get_pipeline_definition().get("input_schema")
        if not pipeline_input_schema:
            # If no explicit input schema, extract from referenced fields in steps
            referenced_fields = self._extract_referenced_fields(pipeline)
            if referenced_fields:
                pipeline_input_schema = {"fields": [{"name": f} for f in referenced_fields]}
                details["pipeline_input_schema_source"] = "extracted_from_steps"
            else:
                warnings.append(
                    "Pipeline does not define an input schema and no fields could be extracted from steps. "
                    "Schema validation skipped."
                )
                details["pipeline_input_schema_exists"] = False
                return {"errors": errors, "warnings": warnings, "details": details}
        else:
            details["pipeline_input_schema_source"] = "explicit"

        details["pipeline_input_schema_exists"] = True

        # Parse pipeline input schema fields
        pipeline_fields = pipeline_input_schema.get("fields", [])
        if not isinstance(pipeline_fields, list):
            # Handle case where pipeline_input_schema is a dict with field names as keys
            if isinstance(pipeline_input_schema, dict):
                pipeline_fields = [
                    {"name": name, **info} if isinstance(info, dict) else {"name": name}
                    for name, info in pipeline_input_schema.items()
                ]
            else:
                errors.append("Pipeline input schema 'fields' must be a list or dictionary")
                return {"errors": errors, "warnings": warnings, "details": details}

        pipeline_field_map = {}
        for field_info in pipeline_fields:
            if isinstance(field_info, dict):
                field_name = field_info.get("name")
                if field_name:
                    pipeline_field_map[field_name] = {
                        "data_type": field_info.get("data_type")
                        or field_info.get("type", "string"),
                        "nullable": field_info.get("nullable", True),
                    }
            elif isinstance(field_info, str):
                pipeline_field_map[field_info] = {"data_type": "string", "nullable": True}

        details["pipeline_field_count"] = len(pipeline_field_map)
        details["pipeline_fields"] = list(pipeline_field_map.keys())

        # Validate all pipeline fields exist in asset schema
        missing_fields = set(pipeline_field_map.keys()) - set(asset_field_map.keys())
        if missing_fields:
            errors.append(
                f"Pipeline requires fields that are not present in asset schema: "
                f"{', '.join(sorted(missing_fields))}"
            )
            details["missing_fields"] = list(missing_fields)
        else:
            details["schema_fields_match"] = True

        # Check for type compatibility (warnings only, as types can be coerced)
        type_mismatches = []
        for field_name in pipeline_field_map:
            if field_name in asset_field_map:
                pipeline_type = pipeline_field_map[field_name]["data_type"].lower()
                asset_type = asset_field_map[field_name]["data_type"].lower()

                # Type compatibility mapping
                compatible_types = {
                    "integer": {"integer", "number", "long", "int"},
                    "float": {"float", "number", "double", "decimal"},
                    "string": {"string", "text", "varchar"},
                    "boolean": {"boolean", "bool"},
                    "date": {"date", "datetime", "timestamp"},
                    "datetime": {"datetime", "timestamp", "date"},
                }

                # Check if types are compatible
                is_compatible = (
                    pipeline_type == asset_type
                    or pipeline_type in compatible_types.get(asset_type, set())
                    or asset_type in compatible_types.get(pipeline_type, set())
                )

                if not is_compatible:
                    type_mismatches.append(
                        {
                            "field": field_name,
                            "asset_type": asset_type,
                            "pipeline_type": pipeline_type,
                        }
                    )

        if type_mismatches:
            warnings.append(
                f"Type mismatches detected between asset schema and pipeline input schema: "
                f"{len(type_mismatches)} field(s) may require type coercion"
            )
            details["type_mismatches"] = type_mismatches

        details["asset_schema_valid"] = len(missing_fields) == 0

        return {"errors": errors, "warnings": warnings, "details": details}

    def _validate_asset_format_compatibility(self, source_dataset: "Dataset") -> dict[str, Any]:
        """
        Validate asset data format (CSV, JSON, Parquet, etc.).

        Args:
            source_dataset: Source dataset

        Returns:
            Dictionary with errors, warnings, and details
        """
        errors = []
        warnings = []
        details = {
            "format_valid": False,
            "format": source_dataset.format,
            "supported_format": False,
        }

        # Supported formats
        supported_formats = {"CSV", "JSON", "PARQUET"}
        format_upper = source_dataset.format.upper() if source_dataset.format else None

        if not format_upper:
            errors.append("Dataset format is not specified")
            return {"errors": errors, "warnings": warnings, "details": details}

        if format_upper not in supported_formats:
            errors.append(
                f"Dataset format '{source_dataset.format}' is not supported. "
                f"Supported formats: {', '.join(sorted(supported_formats))}"
            )
            details["supported_format"] = False
        else:
            details["supported_format"] = True
            details["format_valid"] = True

        # Additional format-specific validations
        if format_upper == "CSV":
            # CSV-specific validations could be added here
            pass
        elif format_upper == "JSON":
            # JSON-specific validations could be added here
            pass
        elif format_upper == "PARQUET":
            # Parquet-specific validations could be added here
            pass

        return {"errors": errors, "warnings": warnings, "details": details}

    def _validate_asset_size_for_execution_mode(self, source_dataset: "Dataset") -> dict[str, Any]:
        """
        Validate asset size for execution mode selection (sync vs async).

        Args:
            source_dataset: Source dataset

        Returns:
            Dictionary with errors, warnings, and details
        """
        errors = []
        warnings = []
        details = {
            "size_valid": False,
            "execution_mode": None,
            "row_count": None,
            "file_size": None,
            "size_threshold_exceeded": False,
        }

        # Execution mode selection thresholds (matching TransformationService)
        SYNC_ROW_THRESHOLD = 10000
        SYNC_SIZE_THRESHOLD = 10 * 1024 * 1024  # 10MB

        # Get row count
        row_count = source_dataset.row_count
        details["row_count"] = row_count

        # Get file size
        file_size = 0
        if source_dataset.file:
            file_size = source_dataset.file.size or 0
        details["file_size"] = file_size
        details["file_size_mb"] = round(file_size / (1024 * 1024), 2) if file_size else 0

        # Validate size information is available
        if row_count is None and file_size == 0:
            warnings.append(
                "Asset size information (row_count and file_size) is not available. "
                "Execution mode will default to ASYNC."
            )
            details["execution_mode"] = "ASYNC"
            details["size_valid"] = True  # Not an error, just a warning
            return {"errors": errors, "warnings": warnings, "details": details}

        # Determine execution mode based on thresholds
        if (row_count is not None and row_count < SYNC_ROW_THRESHOLD) or (
            file_size > 0 and file_size < SYNC_SIZE_THRESHOLD
        ):
            details["execution_mode"] = "SYNC"
            details["size_threshold_exceeded"] = False
            details["size_valid"] = True
        else:
            details["execution_mode"] = "ASYNC"
            details["size_threshold_exceeded"] = True
            details["size_valid"] = True

        details["sync_row_threshold"] = SYNC_ROW_THRESHOLD
        details["sync_size_threshold_mb"] = round(SYNC_SIZE_THRESHOLD / (1024 * 1024), 2)

        return {"errors": errors, "warnings": warnings, "details": details}

    def _validate_asset_access(self, source_asset: Asset) -> dict[str, Any]:
        """
        Validate user has access to asset.

        Args:
            source_asset: Source asset

        Returns:
            Dictionary with errors, warnings, and details
        """
        errors = []
        warnings = []
        details = {
            "access_valid": False,
            "access_allowed": False,
            "cross_tenant": False,
            "entitlement_required": False,
        }

        # If no tenant_id or user_id, skip access validation (will be handled elsewhere)
        if not self.tenant_id:
            warnings.append("tenant_id not provided, skipping asset access validation")
            details["access_valid"] = True  # Not an error, just skipped
            return {"errors": errors, "warnings": warnings, "details": details}

        # Check if cross-tenant access
        is_cross_tenant = str(source_asset.tenant_id) != self.tenant_id
        details["cross_tenant"] = is_cross_tenant

        if not is_cross_tenant:
            # Same tenant - access allowed
            details["access_allowed"] = True
            details["access_valid"] = True
            return {"errors": errors, "warnings": warnings, "details": details}

        # Cross-tenant access - validate using existing method
        if not self.user_id:
            warnings.append(
                "user_id not provided for cross-tenant asset access validation. "
                "Access validation skipped."
            )
            details["access_valid"] = True  # Not an error, just skipped
            return {"errors": errors, "warnings": warnings, "details": details}

        # Use existing cross-tenant access validation
        access_result = self._validate_cross_tenant_asset_access(source_asset, "READ")
        access_allowed = access_result.get("allowed", False)
        details["access_allowed"] = bool(access_allowed)
        details["entitlement_required"] = bool(access_result.get("entitlement_required", False))

        if not access_allowed:
            access_reason = access_result.get("reason") or "Access denied"
            errors.append(
                f"Access denied to source asset '{source_asset.name}'. Reason: {access_reason}"
            )
            details["access_reason"] = str(access_reason)
            details["access_valid"] = False
        else:
            details["access_valid"] = True

        return {"errors": errors, "warnings": warnings, "details": details}

    def validate_cross_tenant_operations(
        self,
        pipeline: TransformationPipeline,
        source_asset: Asset,
        target_asset: Asset | None = None,
        raise_on_error: bool = True,
    ) -> ValidationResult:
        """
        Validate cross-tenant operations for pipeline execution.

        Validates:
        - Pipeline can execute on asset from different tenant (if allowed)
        - Cross-tenant access permissions via GovernanceService (ABACEngine)
        - Entitlements for cross-tenant asset access (via marketplace)

        Args:
            pipeline: TransformationPipeline instance
            source_asset: Source asset to validate
            target_asset: Optional target asset to validate
            raise_on_error: If True, raise exception on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            TransformationValidationError: If validation fails and raise_on_error is True
            PermissionError: If cross-tenant access is denied
        """
        from hub.apps.core.services.base import PermissionError

        errors = []
        warnings = []
        details = {
            "pipeline_id": str(pipeline.id),
            "source_asset_id": str(source_asset.id),
            "cross_tenant_checks": {},
        }

        if not self.tenant_id:
            errors.append("tenant_id is required for cross-tenant validation")
            details["cross_tenant_checks"]["tenant_id_provided"] = False
            result = ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )
            if raise_on_error:
                raise TransformationValidationError(
                    message="tenant_id is required for cross-tenant validation",
                    error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                    details=details,
                    tenant_id=self.tenant_id,
                )
            return result

        details["cross_tenant_checks"]["tenant_id_provided"] = True
        details["pipeline_tenant_id"] = str(pipeline.tenant_id)
        details["source_asset_tenant_id"] = str(source_asset.tenant_id)

        # Check if source asset is from different tenant
        source_is_cross_tenant = str(source_asset.tenant_id) != self.tenant_id
        details["cross_tenant_checks"]["source_is_cross_tenant"] = source_is_cross_tenant

        if source_is_cross_tenant:
            # Validate cross-tenant access for source asset
            source_access_result = self._validate_cross_tenant_asset_access(source_asset, "READ")
            if not source_access_result["allowed"]:
                errors.append(
                    f"Cross-tenant access denied for source asset '{source_asset.name}'. "
                    f"Reason: {source_access_result.get('reason', 'Access denied')}"
                )
                details["cross_tenant_checks"]["source_access_allowed"] = False
                details["cross_tenant_checks"]["source_access_reason"] = source_access_result.get(
                    "reason"
                )
            else:
                details["cross_tenant_checks"]["source_access_allowed"] = True
                if source_access_result.get("entitlement_required"):
                    details["cross_tenant_checks"]["source_entitlement_used"] = True
        else:
            details["cross_tenant_checks"]["source_access_allowed"] = True
            details["cross_tenant_checks"]["source_is_same_tenant"] = True

        # Check target asset if provided
        if target_asset:
            details["target_asset_id"] = str(target_asset.id)
            details["target_asset_tenant_id"] = str(target_asset.tenant_id)

            target_is_cross_tenant = str(target_asset.tenant_id) != self.tenant_id
            details["cross_tenant_checks"]["target_is_cross_tenant"] = target_is_cross_tenant

            if target_is_cross_tenant:
                # Validate cross-tenant access for target asset (WRITE permission)
                target_access_result = self._validate_cross_tenant_asset_access(
                    target_asset, "WRITE"
                )
                if not target_access_result["allowed"]:
                    errors.append(
                        f"Cross-tenant access denied for target asset '{target_asset.name}'. "
                        f"Reason: {target_access_result.get('reason', 'Access denied')}"
                    )
                    details["cross_tenant_checks"]["target_access_allowed"] = False
                    details["cross_tenant_checks"]["target_access_reason"] = (
                        target_access_result.get("reason")
                    )
                else:
                    details["cross_tenant_checks"]["target_access_allowed"] = True
                    if target_access_result.get("entitlement_required"):
                        details["cross_tenant_checks"]["target_entitlement_used"] = True
            else:
                details["cross_tenant_checks"]["target_access_allowed"] = True
                details["cross_tenant_checks"]["target_is_same_tenant"] = True

        result = ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

        if not result.is_valid and raise_on_error:
            # Check if it's a permission error
            if any("access denied" in err.lower() for err in errors):
                error_msg = f"Cross-tenant access denied: {', '.join(errors)}"
                raise PermissionError(error_msg)
            else:
                raise TransformationValidationError(
                    message="Cross-tenant operation validation failed",
                    error_code=TransformationValidationError.ERROR_CODE_VALIDATION_FAILED,
                    details=details,
                    tenant_id=self.tenant_id,
                )

        return result

    def _validate_cross_tenant_asset_access(
        self, asset: Asset, access_type: str = "READ"
    ) -> dict[str, Any]:
        """
        Validate cross-tenant access to an asset.

        Uses:
        - ABACEngine for permission evaluation
        - Marketplace entitlements for cross-tenant asset access

        Args:
            asset: Asset to validate access for
            access_type: Access type (READ, WRITE)

        Returns:
            Dictionary with:
            - allowed: bool
            - reason: Optional[str]
            - entitlement_required: bool
        """
        from hub.apps.governance.abac import ABACEngine
        from hub.apps.marketplace.access_utils import check_entitlement

        result = {"allowed": False, "reason": None, "entitlement_required": False}

        if not self.user_id:
            result["reason"] = "user_id is required for access validation"
            return result

        # Check ABAC policies first
        try:
            abac_result = ABACEngine.evaluate_access(
                user_id=self.user_id,
                tenant_id=str(asset.tenant_id),
                resource_type="ASSET",
                resource_id=str(asset.id),
                access_type=access_type,
            )

            if not abac_result.allowed:
                result["reason"] = (
                    f"ABAC policy denied {access_type} access to asset '{asset.name}'. "
                    f"Policy: {abac_result.policy.name if abac_result.policy else 'Unknown'}"
                )
                return result
        except Exception as e:
            logger.warning(f"ABAC evaluation failed for asset {asset.id}: {e}", exc_info=True)
            # Continue with entitlement check as fallback

        # Check marketplace entitlements for cross-tenant access
        if self.tenant_id and str(asset.tenant_id) != self.tenant_id:
            has_access, error_code, entitlement = check_entitlement(
                consumer_tenant_id=self.tenant_id,
                asset_id=str(asset.id),
                provider_tenant_id=str(asset.tenant_id),
            )

            if not has_access:
                result["reason"] = (
                    f"Entitlement required for cross-tenant access. Error code: {error_code}"
                )
                result["entitlement_required"] = True
                return result

            result["entitlement_required"] = entitlement is not None

        result["allowed"] = True
        return result

    def _estimate_compute_quota(self, pipeline: TransformationPipeline) -> dict[str, float]:
        """
        Estimate compute quota requirements (CPU, memory) from pipeline definition.

        Estimates based on:
        - Number of pipeline steps/nodes
        - Node types (complex operations require more resources)
        - Execution mode (sync vs async)

        Args:
            pipeline: TransformationPipeline instance

        Returns:
            Dictionary with estimated compute quota:
            - cpu_cores: Estimated CPU cores required
            - memory_gb: Estimated memory in GB required
            - compute_hours: Estimated compute hours per execution
        """
        steps = pipeline.get_pipeline_definition().get("steps", [])
        node_count = len(steps)

        # Base compute requirements per node
        # CPU: 0.5 cores per node (minimum), 1.0 for complex operations
        # Memory: 1 GB per node (minimum), 2 GB for complex operations
        base_cpu_per_node = 0.5
        base_memory_per_node_gb = 1.0

        # Complex node types require more resources
        complex_node_types = {
            NodeType.JOIN.upper(),
            NodeType.AGGREGATE.upper(),
            NodeType.TRANSFORM.upper(),
        }

        def get_node_type(step):
            """Extract node_type from step, checking node_config first"""
            node_config = step.get("node_config", {})
            node_type = node_config.get("node_type") or step.get("node_type")
            return node_type.upper() if node_type else None

        complex_node_count = sum(1 for step in steps if get_node_type(step) in complex_node_types)

        # Calculate CPU requirements
        # Base: 0.5 cores per node
        # Complex nodes: additional 0.5 cores each
        cpu_cores = (node_count * base_cpu_per_node) + (complex_node_count * 0.5)

        # Calculate memory requirements
        # Base: 1 GB per node
        # Complex nodes: additional 1 GB each
        memory_gb = (node_count * base_memory_per_node_gb) + (complex_node_count * 1.0)

        # Estimate compute hours per execution
        # Base: 0.1 hours per node
        # Complex nodes: additional 0.1 hours each
        compute_hours_per_execution = (node_count * 0.1) + (complex_node_count * 0.1)

        return {
            "cpu_cores": cpu_cores,
            "memory_gb": memory_gb,
            "compute_hours": compute_hours_per_execution,
        }

    def _estimate_storage_quota(
        self, pipeline: TransformationPipeline, source_asset: Asset | None = None
    ) -> dict[str, float]:
        """
        Estimate storage quota requirements for pipeline results.

        Estimates based on:
        - Source asset size (if available)
        - Pipeline transformation type (filtering reduces size, joins increase)
        - Number of output nodes

        Args:
            pipeline: TransformationPipeline instance
            source_asset: Optional source asset to estimate from

        Returns:
            Dictionary with estimated storage quota:
            - storage_gb: Estimated storage in GB required for results
        """
        steps = pipeline.get_pipeline_definition().get("steps", [])
        node_count = len(steps)

        # Base storage estimation
        # If source asset size is available, use it as baseline
        base_storage_gb = 0.0
        if source_asset:
            # Try to get dataset size if available
            try:
                if hasattr(source_asset, "dataset") and source_asset.dataset:
                    dataset = source_asset.dataset
                    if hasattr(dataset, "size_bytes") and dataset.size_bytes:
                        base_storage_gb = dataset.size_bytes / (1024.0**3)  # Convert bytes to GB
            except Exception:
                pass

        # If no source size available, estimate based on node count
        # Base: 0.1 GB per node (for metadata and intermediate results)
        if base_storage_gb == 0.0:
            base_storage_gb = node_count * 0.1

        # Estimate result storage based on transformation types
        # Filter operations: reduce size by ~50%
        # Join operations: increase size by ~100% (worst case)
        # Aggregate operations: reduce size significantly (~80% reduction)
        # Transform operations: similar size (~10% increase)

        def get_node_type(step):
            """Extract node_type from step, checking node_config first"""
            node_config = step.get("node_config", {})
            node_type = node_config.get("node_type") or step.get("node_type")
            return node_type.upper() if node_type else None

        filter_count = sum(1 for step in steps if get_node_type(step) == NodeType.FILTER.upper())
        join_count = sum(1 for step in steps if get_node_type(step) == NodeType.JOIN.upper())
        aggregate_count = sum(
            1 for step in steps if get_node_type(step) == NodeType.AGGREGATE.upper()
        )

        # Apply transformation multipliers
        storage_multiplier = 1.0
        storage_multiplier -= filter_count * 0.1  # Filters reduce size
        storage_multiplier += join_count * 0.5  # Joins increase size
        storage_multiplier -= aggregate_count * 0.3  # Aggregates reduce size significantly

        # Ensure multiplier is reasonable (at least 0.1)
        storage_multiplier = max(0.1, storage_multiplier)

        estimated_storage_gb = base_storage_gb * storage_multiplier

        # Add overhead for metadata and intermediate results
        # 10% overhead for metadata
        estimated_storage_gb *= 1.1

        return {"storage_gb": estimated_storage_gb}

    def _estimate_query_quota(
        self, pipeline: TransformationPipeline, is_preview: bool = False
    ) -> dict[str, float]:
        """
        Estimate query quota requirements for preview operations.

        Estimates based on:
        - Pipeline complexity (number of nodes)
        - Preview mode (preview operations consume query quota)

        Args:
            pipeline: TransformationPipeline instance
            is_preview: Whether this is a preview operation

        Returns:
            Dictionary with estimated query quota:
            - query_quota: Estimated query quota units required
        """
        if not is_preview:
            # Non-preview operations don't consume query quota
            return {"query_quota": 0.0}

        steps = pipeline.get_pipeline_definition().get("steps", [])
        node_count = len(steps)

        # Base query quota: 1 unit per preview operation
        # Additional quota based on complexity: 0.5 units per node
        query_quota = 1.0 + (node_count * 0.5)

        return {"query_quota": query_quota}

    def validate_resource_quota(
        self,
        pipeline: TransformationPipeline,
        source_asset: Asset | None = None,
        is_preview: bool = False,
        raise_on_error: bool = True,
    ) -> ValidationResult:
        """
        Validate resource quota for pipeline execution.

        Validates:
        - Tenant job concurrency limits (via TenantService.get_tenant_job_limits)
        - Tenant queued job limits
        - Compute quota (CPU, memory limits) via GovernanceService
        - Storage quota (result storage limits) via GovernanceService
        - Query quota (for preview operations) via GovernanceService
        - Tenant-level quota validation via GovernanceService

        Args:
            pipeline: TransformationPipeline instance
            source_asset: Optional source asset for storage estimation
            is_preview: Whether this is a preview operation (affects query quota)
            raise_on_error: If True, raise ResourceQuotaExceededError on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            ResourceQuotaExceededError: If quota is exceeded and raise_on_error is True
        """
        errors = []
        warnings = []
        details = {"pipeline_id": str(pipeline.id), "quota_checks": {}}

        if not self.tenant_id:
            errors.append("tenant_id is required for quota validation")
            details["quota_checks"]["tenant_id_provided"] = False
            result = ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )
            if raise_on_error:
                raise TransformationValidationError(
                    message="tenant_id is required for quota validation",
                    error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                    details=details,
                    tenant_id=self.tenant_id,
                )
            return result

        details["quota_checks"]["tenant_id_provided"] = True

        # Get tenant job limits
        try:
            from django.core.cache import cache

            from hub.apps.jobs.utils import check_tenant_job_limits
            from hub.apps.tenants.services import get_tenant_job_limits

            limits = get_tenant_job_limits(self.tenant_id)
            max_concurrency = limits["max_job_concurrency"]
            max_queued = limits["max_queued_jobs"]

            details["quota_checks"]["max_job_concurrency"] = max_concurrency
            details["quota_checks"]["max_queued_jobs"] = max_queued

            # Check tenant job limits
            can_create_job, error_message = check_tenant_job_limits(self.tenant_id)

            if not can_create_job:
                # Get current counts for detailed error message
                running_key = f"job:tenant:{self.tenant_id}:running"
                queued_key = f"job:tenant:{self.tenant_id}:queued"
                running_count = cache.get(running_key, 0)
                queued_count = cache.get(queued_key, 0)

                details["quota_checks"]["running_jobs"] = running_count
                details["quota_checks"]["queued_jobs"] = queued_count

                if running_count >= max_concurrency:
                    errors.append(
                        f"Tenant has reached maximum concurrent job limit ({max_concurrency}). "
                        f"Current running jobs: {running_count}. Please wait for jobs to complete."
                    )
                    details["quota_checks"]["concurrency_limit_exceeded"] = True
                else:
                    details["quota_checks"]["concurrency_limit_exceeded"] = False

                if queued_count >= max_queued:
                    errors.append(
                        f"Tenant has reached maximum queued job limit ({max_queued}). "
                        f"Current queued jobs: {queued_count}. Please wait for queue to process."
                    )
                    details["quota_checks"]["queue_limit_exceeded"] = True
                else:
                    details["quota_checks"]["queue_limit_exceeded"] = False

                details["quota_checks"]["quota_exceeded"] = True
            else:
                # Get current counts for informational purposes
                running_key = f"job:tenant:{self.tenant_id}:running"
                queued_key = f"job:tenant:{self.tenant_id}:queued"
                running_count = cache.get(running_key, 0)
                queued_count = cache.get(queued_key, 0)

                details["quota_checks"]["running_jobs"] = running_count
                details["quota_checks"]["queued_jobs"] = queued_count
                details["quota_checks"]["quota_exceeded"] = False
                details["quota_checks"]["concurrency_limit_exceeded"] = False
                details["quota_checks"]["queue_limit_exceeded"] = False

        except Exception as e:
            logger.warning(
                f"Failed to check tenant job limits for tenant {self.tenant_id}: {e}", exc_info=True
            )
            warnings.append(
                f"Could not validate job concurrency quota: {e!s}. "
                f"Proceeding with other quota validations."
            )
            details["quota_checks"]["job_limits_validation_error"] = str(e)

        # Estimate resource requirements
        compute_quota = self._estimate_compute_quota(pipeline)
        storage_quota = self._estimate_storage_quota(pipeline, source_asset)
        query_quota = self._estimate_query_quota(pipeline, is_preview)

        details["quota_checks"]["estimated_compute"] = compute_quota
        details["quota_checks"]["estimated_storage"] = storage_quota
        details["quota_checks"]["estimated_query"] = query_quota

        # Integrate with GovernanceService for quota validation
        try:
            from hub.apps.core.services.base import ValidationError
            from hub.apps.governance.services import GovernanceService

            governance_service = GovernanceService(tenant_id=self.tenant_id, user_id=self.user_id)

            # Build requested quota dictionary for GovernanceService
            requested_quota = {
                "storage_gb": storage_quota["storage_gb"],
                "compute_hours": compute_quota["compute_hours"],
            }

            # Add query quota if this is a preview operation
            if is_preview and query_quota["query_quota"] > 0:
                requested_quota["query_quota"] = query_quota["query_quota"]

            details["quota_checks"]["requested_quota"] = requested_quota

            # Validate quota allocation via GovernanceService
            try:
                validated_quota = governance_service.validate_resource_quota_allocation(
                    tenant_id=self.tenant_id, requested_quota=requested_quota
                )
                details["quota_checks"]["validated_quota"] = validated_quota
                details["quota_checks"]["governance_validation_passed"] = True

                # Enforce tenant-level resource limits
                governance_service.check_tenant_resource_limits(
                    tenant_id=self.tenant_id, requested_quota=validated_quota
                )
                details["quota_checks"]["tenant_limits_check_passed"] = True

            except ValidationError as e:
                # GovernanceService validation failed
                error_message = str(e)
                errors.append(f"Resource quota validation failed: {error_message}")
                details["quota_checks"]["governance_validation_passed"] = False
                details["quota_checks"]["governance_validation_error"] = error_message

                # Determine which quota type was exceeded
                if "storage" in error_message.lower() or "storage_gb" in error_message.lower():
                    details["quota_checks"]["storage_quota_exceeded"] = True
                    quota_type = "storage"
                    limit = requested_quota.get("storage_gb")
                    current = None  # GovernanceService doesn't return current usage
                elif "compute" in error_message.lower() or "compute_hours" in error_message.lower():
                    details["quota_checks"]["compute_quota_exceeded"] = True
                    quota_type = "compute"
                    limit = requested_quota.get("compute_hours")
                    current = None
                elif "query" in error_message.lower() or "query_quota" in error_message.lower():
                    details["quota_checks"]["query_quota_exceeded"] = True
                    quota_type = "query"
                    limit = requested_quota.get("query_quota")
                    current = None
                else:
                    quota_type = "unknown"
                    limit = None
                    current = None

                details["quota_checks"]["quota_type"] = quota_type
                details["quota_checks"]["quota_exceeded"] = True

        except Exception as e:
            logger.warning(
                f"Failed to validate resource quota via GovernanceService for tenant {self.tenant_id}: {e}",
                exc_info=True,
            )
            warnings.append(
                f"Could not validate resource quota via GovernanceService: {e!s}. "
                f"Proceeding with pipeline validation."
            )
            details["quota_checks"]["governance_service_error"] = str(e)
            details["quota_checks"]["governance_validation_passed"] = None

        # Check pipeline node count limits (optional, for future use)
        steps = pipeline.get_pipeline_definition().get("steps", [])
        node_count = len(steps)
        details["quota_checks"]["pipeline_node_count"] = node_count

        result = ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

        if not result.is_valid and raise_on_error:
            # Determine which quota was exceeded
            quota_type = details["quota_checks"].get("quota_type", "concurrency")
            limit = details["quota_checks"].get("max_job_concurrency")
            current = details["quota_checks"].get("running_jobs", 0)

            # Check for specific quota types
            if details["quota_checks"].get("storage_quota_exceeded"):
                quota_type = "storage"
                limit = details["quota_checks"]["estimated_storage"].get("storage_gb")
                error_code = ResourceQuotaExceededError.ERROR_CODE_STORAGE_LIMIT
            elif details["quota_checks"].get("compute_quota_exceeded"):
                quota_type = "compute"
                limit = details["quota_checks"]["estimated_compute"].get("compute_hours")
                error_code = ResourceQuotaExceededError.ERROR_CODE_MEMORY_LIMIT
            elif details["quota_checks"].get("query_quota_exceeded"):
                quota_type = "query"
                limit = details["quota_checks"]["estimated_query"].get("query_quota")
                error_code = ResourceQuotaExceededError.ERROR_CODE_QUOTA_EXCEEDED
            elif details["quota_checks"].get("queue_limit_exceeded"):
                quota_type = "queue"
                limit = details["quota_checks"].get("max_queued_jobs")
                current = details["quota_checks"].get("queued_jobs", 0)
                error_code = ResourceQuotaExceededError.ERROR_CODE_QUOTA_EXCEEDED
            else:
                error_code = ResourceQuotaExceededError.ERROR_CODE_CONCURRENT_EXECUTIONS_LIMIT

            raise ResourceQuotaExceededError(
                message="Resource quota exceeded for pipeline execution",
                error_code=error_code,
                quota_type=quota_type,
                limit=limit,
                current=current,
                pipeline_id=str(pipeline.id),
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                details=details,
            )

        return result

    def validate_pipeline_execution_permission(
        self,
        pipeline: TransformationPipeline,
        source_asset: Asset | None = None,
        target_asset: Asset | None = None,
        raise_on_error: bool = True,
    ) -> ValidationResult:
        """
        Validate pipeline execution permissions.

        Validates:
        - User has permission to execute pipeline (via ABACEngine)
        - User has permission to access source asset (if provided)
        - User has permission to write to target asset (if provided)

        Args:
            pipeline: TransformationPipeline instance
            source_asset: Optional source asset
            target_asset: Optional target asset
            raise_on_error: If True, raise PermissionError on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            PermissionError: If permission validation fails and raise_on_error is True
        """
        from hub.apps.core.services.base import PermissionError

        errors = []
        warnings = []
        details = {"pipeline_id": str(pipeline.id), "permission_checks": {}}

        if not self.user_id:
            errors.append("user_id is required for permission validation")
            details["permission_checks"]["user_id_provided"] = False
            result = ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )
            if raise_on_error:
                raise TransformationValidationError(
                    message="user_id is required for permission validation",
                    error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                    details=details,
                    tenant_id=self.tenant_id,
                )
            return result

        details["permission_checks"]["user_id_provided"] = True
        details["user_id"] = self.user_id

        # Validate pipeline execution permission
        try:
            from hub.apps.governance.abac import ABACEngine

            pipeline_result = ABACEngine.evaluate_access(
                user_id=self.user_id,
                tenant_id=str(pipeline.tenant_id),
                resource_type="TRANSFORMATION_PIPELINE",
                resource_id=str(pipeline.id),
                access_type="EXECUTE",
            )

            if not pipeline_result.allowed:
                errors.append(
                    f"User does not have permission to execute pipeline '{pipeline.name}'. "
                    f"Policy: {pipeline_result.policy.name if pipeline_result.policy else 'Unknown'}"
                )
                details["permission_checks"]["pipeline_execute_allowed"] = False
                details["permission_checks"]["pipeline_policy"] = (
                    pipeline_result.policy.name if pipeline_result.policy else None
                )
            else:
                details["permission_checks"]["pipeline_execute_allowed"] = True
                if pipeline_result.policy:
                    details["permission_checks"]["pipeline_policy"] = pipeline_result.policy.name

        except Exception as e:
            logger.warning(f"ABAC evaluation failed for pipeline {pipeline.id}: {e}", exc_info=True)
            warnings.append(
                f"Could not validate pipeline execution permission: {e!s}. "
                f"Proceeding with validation."
            )
            details["permission_checks"]["pipeline_validation_error"] = str(e)

        # Validate source asset access permission
        if source_asset:
            try:
                from hub.apps.governance.abac import ABACEngine

                source_result = ABACEngine.evaluate_access(
                    user_id=self.user_id,
                    tenant_id=str(source_asset.tenant_id),
                    resource_type="ASSET",
                    resource_id=str(source_asset.id),
                    access_type="READ",
                )

                if not source_result.allowed:
                    errors.append(
                        f"User does not have READ permission for source asset '{source_asset.name}'. "
                        f"Policy: {source_result.policy.name if source_result.policy else 'Unknown'}"
                    )
                    details["permission_checks"]["source_asset_read_allowed"] = False
                    details["permission_checks"]["source_asset_policy"] = (
                        source_result.policy.name if source_result.policy else None
                    )
                else:
                    details["permission_checks"]["source_asset_read_allowed"] = True
                    if source_result.policy:
                        details["permission_checks"]["source_asset_policy"] = (
                            source_result.policy.name
                        )

            except Exception as e:
                logger.warning(
                    f"ABAC evaluation failed for source asset {source_asset.id}: {e}", exc_info=True
                )
                warnings.append(
                    f"Could not validate source asset access permission: {e!s}. "
                    f"Proceeding with validation."
                )
                details["permission_checks"]["source_asset_validation_error"] = str(e)

        # Validate target asset write permission
        if target_asset:
            try:
                from hub.apps.governance.abac import ABACEngine

                target_result = ABACEngine.evaluate_access(
                    user_id=self.user_id,
                    tenant_id=str(target_asset.tenant_id),
                    resource_type="ASSET",
                    resource_id=str(target_asset.id),
                    access_type="WRITE",
                )

                if not target_result.allowed:
                    errors.append(
                        f"User does not have WRITE permission for target asset '{target_asset.name}'. "
                        f"Policy: {target_result.policy.name if target_result.policy else 'Unknown'}"
                    )
                    details["permission_checks"]["target_asset_write_allowed"] = False
                    details["permission_checks"]["target_asset_policy"] = (
                        target_result.policy.name if target_result.policy else None
                    )
                else:
                    details["permission_checks"]["target_asset_write_allowed"] = True
                    if target_result.policy:
                        details["permission_checks"]["target_asset_policy"] = (
                            target_result.policy.name
                        )

            except Exception as e:
                logger.warning(
                    f"ABAC evaluation failed for target asset {target_asset.id}: {e}", exc_info=True
                )
                warnings.append(
                    f"Could not validate target asset write permission: {e!s}. "
                    f"Proceeding with validation."
                )
                details["permission_checks"]["target_asset_validation_error"] = str(e)

        result = ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

        if not result.is_valid and raise_on_error:
            error_msg = f"Pipeline execution permission denied: {', '.join(errors)}"
            raise PermissionError(error_msg)

        return result
