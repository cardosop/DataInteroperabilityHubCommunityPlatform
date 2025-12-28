"""
Transformation Business Rules

Comprehensive business rules validation for transformation pipelines, including:
- Pipeline structure validation
- Node compatibility validation
- Schema alignment validation
- Asset compatibility validation

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError

from hub.apps.transformation.models import (
    TransformationPipeline,
    TransformationNode,
    NodeType,
    PipelineStatus,
    ExecutionMode
)
from hub.apps.transformation.exceptions import (
    TransformationValidationError,
    AssetCompatibilityError,
    ResourceQuotaExceededError
)
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.schema_evolution import (
    SchemaEvolutionTracker,
    CompatibilityLevel
)
from hub.apps.core.services.base import PermissionError

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation operation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]

    def __bool__(self):
        return self.is_valid


class TransformationBusinessRules:
    """
    Business rules validator for transformation pipelines.

    Validates:
    - Pipeline structure and definition
    - Node compatibility and ordering
    - Schema alignment between assets and pipeline
    - Asset compatibility with pipeline requirements
    """

    # Valid node types
    VALID_NODE_TYPES = {choice[0] for choice in NodeType.choices}

    # Node execution order constraints
    # Nodes that must come before other nodes
    NODE_DEPENDENCIES = {
        NodeType.FILTER: set(),  # Filter can be first
        NodeType.JOIN: {NodeType.FILTER},  # Join should come after filter
        NodeType.AGGREGATE: {NodeType.FILTER, NodeType.JOIN},  # Aggregate needs filtered/joined data
        NodeType.TRANSFORM: {NodeType.FILTER, NodeType.JOIN, NodeType.AGGREGATE},  # Transform can come after any
        NodeType.OUTPUT: {NodeType.FILTER, NodeType.JOIN, NodeType.AGGREGATE, NodeType.TRANSFORM}  # Output should be last
    }

    # Required fields per node type
    NODE_REQUIRED_FIELDS = {
        NodeType.FILTER: {"filter_expression"},
        NodeType.JOIN: {"join_keys", "join_type"},
        NodeType.AGGREGATE: {"group_by", "aggregation_functions"},
        NodeType.TRANSFORM: {"transform_expression"},
        NodeType.OUTPUT: set()  # Output nodes don't require specific fields
    }

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize TransformationBusinessRules.

        Args:
            tenant_id: Optional tenant ID for tenant-specific validation
            user_id: Optional user ID for permission and cross-tenant validation
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

    def validate_pipeline_structure(
        self,
        pipeline: TransformationPipeline,
        raise_on_error: bool = True
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
            "validation_checks": {}
        }

        # Validate pipeline_definition is a dictionary
        if not isinstance(pipeline.pipeline_definition, dict):
            errors.append(
                "Pipeline definition must be a JSON object (dictionary)"
            )
            details["validation_checks"]["pipeline_definition_type"] = False
        else:
            details["validation_checks"]["pipeline_definition_type"] = True

            # Validate required fields
            required_fields = ["version", "steps"]
            for field in required_fields:
                if field not in pipeline.pipeline_definition:
                    errors.append(
                        f"Pipeline definition must contain '{field}' field"
                    )
                    details["validation_checks"][f"has_{field}"] = False
                else:
                    details["validation_checks"][f"has_{field}"] = True

            # Validate version format
            version = pipeline.pipeline_definition.get("version")
            if version:
                if not isinstance(version, str) or not version.strip():
                    errors.append(
                        "Pipeline definition 'version' must be a non-empty string"
                    )
                    details["validation_checks"]["version_format"] = False
                else:
                    details["validation_checks"]["version_format"] = True

            # Validate steps
            steps = pipeline.pipeline_definition.get("steps", [])
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
                            errors.append(
                                f"Duplicate step name '{step_name}' at index {i}"
                            )
                        else:
                            step_names.add(step_name)

                details["unique_step_names"] = len(step_names) == len(steps)
                if not details["unique_step_names"]:
                    warnings.append(
                        "Some steps have duplicate names, which may cause confusion"
                    )

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
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise TransformationValidationError(
                message="Pipeline structure validation failed",
                error_code=TransformationValidationError.ERROR_CODE_INVALID_PIPELINE_DEFINITION,
                details=details,
                tenant_id=self.tenant_id
            )

        return result

    def _validate_step_structure(
        self,
        step: Dict[str, Any],
        index: int
    ) -> List[str]:
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
                errors.append(
                    f"Step {index} 'node_config' must be a JSON object"
                )
            else:
                # Validate node_type if present
                node_type = node_config.get("node_type")
                if node_type:
                    if node_type not in self.VALID_NODE_TYPES:
                        errors.append(
                            f"Step {index} has invalid node_type '{node_type}'. "
                            f"Valid types: {', '.join(self.VALID_NODE_TYPES)}"
                        )

        return errors

    def validate_node_compatibility(
        self,
        pipeline: TransformationPipeline,
        raise_on_error: bool = True
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
            "node_compatibility_checks": {}
        }

        steps = pipeline.pipeline_definition.get("steps", [])
        if not steps:
            errors.append("Pipeline has no steps to validate")
            details["node_compatibility_checks"]["has_steps"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise TransformationValidationError(
                    message="Pipeline has no steps",
                    error_code=TransformationValidationError.ERROR_CODE_INVALID_PIPELINE_DEFINITION,
                    details=details,
                    tenant_id=self.tenant_id
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
                pos, step_name, node_type = node_types_by_position[i]

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
            warnings.append(
                "Pipeline has no OUTPUT node. Pipeline may not produce output."
            )
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
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise TransformationValidationError(
                message="Node compatibility validation failed",
                error_code=TransformationValidationError.ERROR_CODE_INVALID_NODE_CONFIG,
                details=details,
                tenant_id=self.tenant_id
            )

        return result

    def _validate_node_config(
        self,
        node_type: str,
        node_config: Dict[str, Any],
        step_name: str,
        step_index: int
    ) -> List[str]:
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

        # Validate JOIN node
        elif node_type_enum == NodeType.JOIN:
            join_keys = node_config.get("join_keys")
            join_type = node_config.get("join_type")

            if not join_keys and not join_type:
                errors.append(
                    f"Step '{step_name}' (JOIN node) must have either 'join_keys' or 'join_type' in node_config"
                )

            if join_keys:
                if not isinstance(join_keys, (list, dict)):
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

    def validate_schema_alignment(
        self,
        pipeline: TransformationPipeline,
        source_asset: Asset,
        target_asset: Optional[Asset] = None,
        raise_on_error: bool = True
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
            "schema_alignment_checks": {}
        }

        # Get source asset schema
        source_dataset = source_asset.datasets.order_by('-version').first()
        if not source_dataset:
            errors.append(
                f"Source asset '{source_asset.name}' has no dataset"
            )
            details["schema_alignment_checks"]["source_dataset_exists"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise AssetCompatibilityError(
                    message="Source asset has no dataset",
                    error_code=AssetCompatibilityError.ERROR_CODE_SCHEMA_INCOMPATIBLE,
                    pipeline_id=str(pipeline.id),
                    asset_id=str(source_asset.id),
                    details=details,
                    tenant_id=self.tenant_id
                )
            return result

        details["schema_alignment_checks"]["source_dataset_exists"] = True
        source_schema = source_dataset.schema_json or {}
        source_fields = {f.get("name"): f for f in source_schema.get("fields", [])}
        details["source_schema_fields"] = list(source_fields.keys())

        # Validate target asset schema if provided
        if target_asset:
            target_dataset = target_asset.datasets.order_by('-version').first()
            if target_dataset:
                target_schema = target_dataset.schema_json or {}
                target_fields = {f.get("name"): f for f in target_schema.get("fields", [])}
                details["target_schema_fields"] = list(target_fields.keys())
                details["schema_alignment_checks"]["target_dataset_exists"] = True
            else:
                warnings.append(
                    f"Target asset '{target_asset.name}' has no dataset"
                )
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
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise AssetCompatibilityError(
                message="Schema alignment validation failed",
                error_code=AssetCompatibilityError.ERROR_CODE_SCHEMA_INCOMPATIBLE,
                pipeline_id=str(pipeline.id),
                asset_id=str(source_asset.id),
                expected_schema=source_schema,
                details=details,
                tenant_id=self.tenant_id
            )

        return result

    def _extract_referenced_fields(
        self,
        pipeline: TransformationPipeline
    ) -> Set[str]:
        """
        Extract field names referenced in pipeline steps.

        Args:
            pipeline: TransformationPipeline instance

        Returns:
            Set of field names referenced in the pipeline
        """
        referenced_fields = set()
        steps = pipeline.pipeline_definition.get("steps", [])

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
                field_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
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
                    field_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
                    matches = re.findall(field_pattern, transform_expr)
                    keywords = {"and", "or", "not", "in", "is", "null", "true", "false", "if", "else", "sum", "avg", "count", "min", "max"}
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
        target_asset: Optional[Asset] = None,
        raise_on_error: bool = True
    ) -> ValidationResult:
        """
        Validate asset compatibility with pipeline requirements.

        Validates:
        - Source asset is in a valid state (ACTIVE, has dataset)
        - Source asset format is compatible with pipeline
        - Target asset (if provided) is compatible
        - Asset schemas are compatible with pipeline operations

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
            "asset_compatibility_checks": {}
        }

        # Validate source asset status
        from hub.apps.assets.models import AssetStatus
        valid_source_statuses = [AssetStatus.ACTIVE.value, AssetStatus.PUBLIC.value]
        if source_asset.status not in valid_source_statuses:
            errors.append(
                f"Source asset '{source_asset.name}' must be ACTIVE or PUBLIC. "
                f"Current status: {source_asset.status}"
            )
            details["asset_compatibility_checks"]["source_asset_status"] = False
        else:
            details["asset_compatibility_checks"]["source_asset_status"] = True

        # Validate source asset has dataset
        source_dataset = source_asset.datasets.order_by('-version').first()
        if not source_dataset:
            errors.append(
                f"Source asset '{source_asset.name}' has no dataset"
            )
            details["asset_compatibility_checks"]["source_dataset_exists"] = False
        else:
            details["asset_compatibility_checks"]["source_dataset_exists"] = True
            details["source_dataset_format"] = source_dataset.format
            details["source_dataset_version"] = source_dataset.version

            # Validate dataset format is supported
            supported_formats = {"CSV", "JSON", "PARQUET"}
            if source_dataset.format not in supported_formats:
                warnings.append(
                    f"Source dataset format '{source_dataset.format}' may not be fully supported. "
                    f"Supported formats: {', '.join(supported_formats)}"
                )

        # Validate target asset if provided
        if target_asset:
            details["target_asset_id"] = str(target_asset.id)

            valid_target_statuses = [AssetStatus.ACTIVE.value, AssetStatus.DRAFT.value]
            if target_asset.status not in valid_target_statuses:
                errors.append(
                    f"Target asset '{target_asset.name}' must be ACTIVE or DRAFT. "
                    f"Current status: {target_asset.status}"
                )
                details["asset_compatibility_checks"]["target_asset_status"] = False
            else:
                details["asset_compatibility_checks"]["target_asset_status"] = True

            # Validate target asset has dataset (optional for new assets)
            target_dataset = target_asset.datasets.order_by('-version').first()
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
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
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
                tenant_id=self.tenant_id
            )

        return result

    def validate_all(
        self,
        pipeline: TransformationPipeline,
        source_asset: Optional[Asset] = None,
        target_asset: Optional[Asset] = None,
        raise_on_error: bool = True
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
        all_details = {
            "pipeline_id": str(pipeline.id),
            "validation_results": {}
        }

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
            details=all_details
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
                    tenant_id=self.tenant_id
                )
            else:
                raise TransformationValidationError(
                    message="Pipeline validation failed",
                    error_code=TransformationValidationError.ERROR_CODE_VALIDATION_FAILED,
                    details=all_details,
                    tenant_id=self.tenant_id
                )

        return result

    def validate_cross_tenant_operations(
        self,
        pipeline: TransformationPipeline,
        source_asset: Asset,
        target_asset: Optional[Asset] = None,
        raise_on_error: bool = True
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
        errors = []
        warnings = []
        details = {
            "pipeline_id": str(pipeline.id),
            "source_asset_id": str(source_asset.id),
            "cross_tenant_checks": {}
        }

        if not self.tenant_id:
            errors.append("tenant_id is required for cross-tenant validation")
            details["cross_tenant_checks"]["tenant_id_provided"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise TransformationValidationError(
                    message="tenant_id is required for cross-tenant validation",
                    error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                    details=details,
                    tenant_id=self.tenant_id
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
            source_access_result = self._validate_cross_tenant_asset_access(
                source_asset, "READ"
            )
            if not source_access_result["allowed"]:
                errors.append(
                    f"Cross-tenant access denied for source asset '{source_asset.name}'. "
                    f"Reason: {source_access_result.get('reason', 'Access denied')}"
                )
                details["cross_tenant_checks"]["source_access_allowed"] = False
                details["cross_tenant_checks"]["source_access_reason"] = source_access_result.get("reason")
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
                    details["cross_tenant_checks"]["target_access_reason"] = target_access_result.get("reason")
                else:
                    details["cross_tenant_checks"]["target_access_allowed"] = True
                    if target_access_result.get("entitlement_required"):
                        details["cross_tenant_checks"]["target_entitlement_used"] = True
            else:
                details["cross_tenant_checks"]["target_access_allowed"] = True
                details["cross_tenant_checks"]["target_is_same_tenant"] = True

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
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
                    tenant_id=self.tenant_id
                )

        return result

    def _validate_cross_tenant_asset_access(
        self,
        asset: Asset,
        access_type: str = "READ"
    ) -> Dict[str, Any]:
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

        result = {
            "allowed": False,
            "reason": None,
            "entitlement_required": False
        }

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
                access_type=access_type
            )

            if not abac_result.allowed:
                result["reason"] = (
                    f"ABAC policy denied {access_type} access to asset '{asset.name}'. "
                    f"Policy: {abac_result.policy.name if abac_result.policy else 'Unknown'}"
                )
                return result
        except Exception as e:
            logger.warning(
                f"ABAC evaluation failed for asset {asset.id}: {e}",
                exc_info=True
            )
            # Continue with entitlement check as fallback

        # Check marketplace entitlements for cross-tenant access
        if self.tenant_id and str(asset.tenant_id) != self.tenant_id:
            has_access, error_code, entitlement = check_entitlement(
                consumer_tenant_id=self.tenant_id,
                asset_id=str(asset.id),
                provider_tenant_id=str(asset.tenant_id)
            )

            if not has_access:
                result["reason"] = (
                    f"Entitlement required for cross-tenant access. "
                    f"Error code: {error_code}"
                )
                result["entitlement_required"] = True
                return result

            result["entitlement_required"] = entitlement is not None

        result["allowed"] = True
        return result

    def validate_resource_quota(
        self,
        pipeline: TransformationPipeline,
        raise_on_error: bool = True
    ) -> ValidationResult:
        """
        Validate resource quota for pipeline execution.

        Validates:
        - Tenant job concurrency limits (via TenantService.get_tenant_job_limits)
        - Tenant queued job limits
        - Pipeline node count limits (if applicable)

        Args:
            pipeline: TransformationPipeline instance
            raise_on_error: If True, raise ResourceQuotaExceededError on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            ResourceQuotaExceededError: If quota is exceeded and raise_on_error is True
        """
        errors = []
        warnings = []
        details = {
            "pipeline_id": str(pipeline.id),
            "quota_checks": {}
        }

        if not self.tenant_id:
            errors.append("tenant_id is required for quota validation")
            details["quota_checks"]["tenant_id_provided"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise TransformationValidationError(
                    message="tenant_id is required for quota validation",
                    error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                    details=details,
                    tenant_id=self.tenant_id
                )
            return result

        details["quota_checks"]["tenant_id_provided"] = True

        # Get tenant job limits
        try:
            from hub.apps.tenants.services import get_tenant_job_limits
            from hub.apps.jobs.utils import check_tenant_job_limits
            from django.core.cache import cache

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
                f"Failed to check tenant job limits for tenant {self.tenant_id}: {e}",
                exc_info=True
            )
            warnings.append(
                f"Could not validate resource quota: {str(e)}. "
                f"Proceeding with pipeline validation."
            )
            details["quota_checks"]["validation_error"] = str(e)

        # Check pipeline node count limits (optional, for future use)
        steps = pipeline.pipeline_definition.get("steps", [])
        node_count = len(steps)
        details["quota_checks"]["pipeline_node_count"] = node_count

        # Future: Add node count limits if needed
        # max_nodes = limits.get("max_pipeline_nodes", 100)
        # if node_count > max_nodes:
        #     errors.append(...)

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            # Determine which quota was exceeded
            quota_type = "concurrency"
            limit = details["quota_checks"].get("max_job_concurrency")
            current = details["quota_checks"].get("running_jobs", 0)

            if details["quota_checks"].get("queue_limit_exceeded"):
                quota_type = "queue"
                limit = details["quota_checks"].get("max_queued_jobs")
                current = details["quota_checks"].get("queued_jobs", 0)

            raise ResourceQuotaExceededError(
                message="Resource quota exceeded for pipeline execution",
                error_code=ResourceQuotaExceededError.ERROR_CODE_CONCURRENT_EXECUTIONS_LIMIT
                if quota_type == "concurrency"
                else ResourceQuotaExceededError.ERROR_CODE_QUOTA_EXCEEDED,
                quota_type=quota_type,
                limit=limit,
                current=current,
                pipeline_id=str(pipeline.id),
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                details=details
            )

        return result

    def validate_pipeline_execution_permission(
        self,
        pipeline: TransformationPipeline,
        source_asset: Optional[Asset] = None,
        target_asset: Optional[Asset] = None,
        raise_on_error: bool = True
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
        errors = []
        warnings = []
        details = {
            "pipeline_id": str(pipeline.id),
            "permission_checks": {}
        }

        if not self.user_id:
            errors.append("user_id is required for permission validation")
            details["permission_checks"]["user_id_provided"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise TransformationValidationError(
                    message="user_id is required for permission validation",
                    error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                    details=details,
                    tenant_id=self.tenant_id
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
                access_type="EXECUTE"
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
            logger.warning(
                f"ABAC evaluation failed for pipeline {pipeline.id}: {e}",
                exc_info=True
            )
            warnings.append(
                f"Could not validate pipeline execution permission: {str(e)}. "
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
                    access_type="READ"
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
                        details["permission_checks"]["source_asset_policy"] = source_result.policy.name

            except Exception as e:
                logger.warning(
                    f"ABAC evaluation failed for source asset {source_asset.id}: {e}",
                    exc_info=True
                )
                warnings.append(
                    f"Could not validate source asset access permission: {str(e)}. "
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
                    access_type="WRITE"
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
                        details["permission_checks"]["target_asset_policy"] = target_result.policy.name

            except Exception as e:
                logger.warning(
                    f"ABAC evaluation failed for target asset {target_asset.id}: {e}",
                    exc_info=True
                )
                warnings.append(
                    f"Could not validate target asset write permission: {str(e)}. "
                    f"Proceeding with validation."
                )
                details["permission_checks"]["target_asset_validation_error"] = str(e)

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            error_msg = f"Pipeline execution permission denied: {', '.join(errors)}"
            raise PermissionError(error_msg)

        return result


class ExecutionBusinessRules:
    """
    Business rules validator for pipeline execution decisions.

    Validates and determines:
    - Resource limits (job concurrency, queue depth)
    - Execution mode selection (SYNC vs ASYNC)
    - Timeout validation and configuration

    All validation methods follow engineering best practices:
    - No mocks/stubs - use real services and models
    - Fix root causes, not symptoms
    - Comprehensive error messages with context
    - Follow DRY, SOLID, and clean code principles
    """

    # Execution mode selection thresholds
    SYNC_ROW_THRESHOLD = 10000  # < 10,000 rows = SYNC
    SYNC_SIZE_THRESHOLD = 10 * 1024 * 1024  # < 10MB = SYNC

    # Timeout limits (in seconds)
    MIN_TIMEOUT_SECONDS = 60  # Minimum 1 minute
    MAX_TIMEOUT_SECONDS = 7200  # Maximum 2 hours
    DEFAULT_SYNC_TIMEOUT = 300  # 5 minutes for SYNC
    DEFAULT_ASYNC_TIMEOUT = 3600  # 1 hour for ASYNC

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize ExecutionBusinessRules.

        Args:
            tenant_id: Optional tenant ID for tenant-specific validation
            user_id: Optional user ID for user-specific validation
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

    def validate_resource_limits(
        self,
        pipeline: Optional[TransformationPipeline] = None,
        raise_on_error: bool = True
    ) -> ValidationResult:
        """
        Validate resource limits for pipeline execution.

        Validates:
        - Tenant job concurrency limits (via TenantService.get_tenant_job_limits)
        - Tenant queued job limits
        - Worker capacity availability

        Args:
            pipeline: Optional TransformationPipeline instance (for context)
            raise_on_error: If True, raise ResourceQuotaExceededError on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            ResourceQuotaExceededError: If resource limits are exceeded and raise_on_error is True
        """
        errors = []
        warnings = []
        details = {
            "resource_checks": {}
        }

        if pipeline:
            details["pipeline_id"] = str(pipeline.id)

        if not self.tenant_id:
            errors.append("tenant_id is required for resource limit validation")
            details["resource_checks"]["tenant_id_provided"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise TransformationValidationError(
                    "tenant_id is required for resource limit validation",
                    error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                    details=details,
                    tenant_id=self.tenant_id
                )
            return result

        details["resource_checks"]["tenant_id_provided"] = True

        # Get tenant job limits
        try:
            from hub.apps.tenants.services import get_tenant_job_limits
            from hub.apps.jobs.utils import check_tenant_job_limits
            from django.core.cache import cache

            limits = get_tenant_job_limits(self.tenant_id)
            max_concurrency = limits["max_job_concurrency"]
            max_queued = limits["max_queued_jobs"]

            details["resource_checks"]["max_job_concurrency"] = max_concurrency
            details["resource_checks"]["max_queued_jobs"] = max_queued

            # Check tenant job limits
            can_create_job, error_message = check_tenant_job_limits(self.tenant_id)

            if not can_create_job:
                # Get current counts for detailed error message
                running_key = f"job:tenant:{self.tenant_id}:running"
                queued_key = f"job:tenant:{self.tenant_id}:queued"
                running_count = cache.get(running_key, 0)
                queued_count = cache.get(queued_key, 0)

                details["resource_checks"]["running_jobs"] = running_count
                details["resource_checks"]["queued_jobs"] = queued_count

                if running_count >= max_concurrency:
                    errors.append(
                        f"Tenant has reached maximum concurrent job limit ({max_concurrency}). "
                        f"Current running jobs: {running_count}. Please wait for jobs to complete."
                    )
                    details["resource_checks"]["concurrency_limit_exceeded"] = True
                else:
                    details["resource_checks"]["concurrency_limit_exceeded"] = False

                if queued_count >= max_queued:
                    errors.append(
                        f"Tenant has reached maximum queued job limit ({max_queued}). "
                        f"Current queued jobs: {queued_count}. Please wait for queue to process."
                    )
                    details["resource_checks"]["queue_limit_exceeded"] = True
                else:
                    details["resource_checks"]["queue_limit_exceeded"] = False

                details["resource_checks"]["resource_limit_exceeded"] = True
            else:
                # Get current counts for informational purposes
                running_key = f"job:tenant:{self.tenant_id}:running"
                queued_key = f"job:tenant:{self.tenant_id}:queued"
                running_count = cache.get(running_key, 0)
                queued_count = cache.get(queued_key, 0)

                details["resource_checks"]["running_jobs"] = running_count
                details["resource_checks"]["queued_jobs"] = queued_count
                details["resource_checks"]["concurrency_limit_exceeded"] = False
                details["resource_checks"]["queue_limit_exceeded"] = False
                details["resource_checks"]["resource_limit_exceeded"] = False

                # Add warnings if approaching limits
                if running_count >= max_concurrency * 0.8:
                    warnings.append(
                        f"Tenant is approaching concurrent job limit ({running_count}/{max_concurrency}). "
                        f"Consider waiting before starting new executions."
                    )
                if queued_count >= max_queued * 0.8:
                    warnings.append(
                        f"Tenant is approaching queued job limit ({queued_count}/{max_queued}). "
                        f"Consider waiting before starting new executions."
                    )

        except Exception as e:
            logger.warning(
                f"Failed to validate resource limits: {e}",
                extra={
                    "tenant_id": self.tenant_id,
                    "pipeline_id": str(pipeline.id) if pipeline else None,
                    "error": str(e)
                },
                exc_info=True
            )
            errors.append(f"Failed to validate resource limits: {str(e)}")
            details["resource_checks"]["validation_error"] = str(e)

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            error_msg = f"Resource limits exceeded: {', '.join(errors)}"
            raise ResourceQuotaExceededError(
                error_msg,
                error_code=ResourceQuotaExceededError.ERROR_CODE_QUOTA_EXCEEDED,
                details=details,
                tenant_id=self.tenant_id
            )

        return result

    def select_execution_mode(
        self,
        asset_id: str,
        force_mode: Optional[str] = None,
        pipeline: Optional[TransformationPipeline] = None
    ) -> str:
        """
        Select execution mode (SYNC or ASYNC) based on dataset size and other factors.

        Selection criteria:
        - Force mode (if provided) takes precedence
        - Dataset row count: < 10,000 rows = SYNC, otherwise ASYNC
        - Dataset file size: < 10MB = SYNC, otherwise ASYNC
        - Default to ASYNC if dataset info unavailable
        - Consider tenant resource limits (prefer SYNC if resources available)

        Args:
            asset_id: Asset ID to check dataset size
            force_mode: Optional forced execution mode (SYNC, ASYNC) - takes precedence
            pipeline: Optional TransformationPipeline instance (for context)

        Returns:
            Execution mode string (SYNC or ASYNC)

        Raises:
            TransformationValidationError: If asset not found or invalid
        """
        from hub.apps.transformation.models import ExecutionMode

        # Force mode takes precedence
        if force_mode:
            forced_mode = force_mode.upper()
            # Check if forced_mode matches ExecutionMode values (handle both string and tuple formats)
            sync_value = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC
            async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC

            if forced_mode in [sync_value, async_value]:
                logger.info(
                    f"Execution mode forced to {forced_mode}",
                    extra={
                        "asset_id": asset_id,
                        "tenant_id": self.tenant_id,
                        "forced_mode": forced_mode
                    }
                )
                return forced_mode
            else:
                logger.warning(
                    f"Invalid force_mode {force_mode}, ignoring and using auto-selection",
                    extra={
                        "asset_id": asset_id,
                        "tenant_id": self.tenant_id,
                        "invalid_mode": force_mode
                    }
                )

        if not self.tenant_id:
            logger.warning(
                "tenant_id not provided, defaulting to ASYNC mode",
                extra={"asset_id": asset_id}
            )
            # Return ASYNC string value
            async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC
            return async_value

        try:
            from hub.apps.assets.models import Asset

            asset = Asset.objects.get(id=asset_id, tenant_id=self.tenant_id)
            latest_dataset = asset.datasets.order_by('-version').first()

            if not latest_dataset:
                # Default to ASYNC if no dataset info available
                logger.info(
                    "No dataset found for asset, defaulting to ASYNC mode",
                    extra={
                        "asset_id": asset_id,
                        "tenant_id": self.tenant_id
                    }
                )
                # Return ASYNC string value
                async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC
                return async_value

            # Use row_count if available, otherwise use file size
            row_count = latest_dataset.row_count
            file_size = latest_dataset.file.size if latest_dataset.file else 0

            # Check resource availability - prefer SYNC if resources are available
            # Only switch to ASYNC if we can confirm resources are explicitly exhausted
            resources_available = True  # Default to available
            try:
                resource_result = self.validate_resource_limits(pipeline=pipeline, raise_on_error=False)
                # Only consider resources unavailable if validation explicitly failed
                # (not if there was an error checking)
                if not resource_result.is_valid and len(resource_result.errors) > 0:
                    # Check if the error is specifically about resource limits being exceeded
                    error_messages = ' '.join(resource_result.errors).lower()
                    if 'limit' in error_messages or 'quota' in error_messages:
                        resources_available = False
            except Exception as e:
                # If we can't check resources, assume they're available (lenient approach)
                logger.debug(
                    f"Could not check resource limits for execution mode selection: {e}. "
                    f"Assuming resources available.",
                    extra={
                        "asset_id": asset_id,
                        "tenant_id": self.tenant_id,
                        "error": str(e)
                    }
                )
                resources_available = True  # Assume available if check fails

            # Selection logic
            selected_mode = None

            # Get ExecutionMode string values (handle tuple format)
            sync_value = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC
            async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC

            # Check row count threshold
            if row_count is not None:
                if row_count < self.SYNC_ROW_THRESHOLD:
                    selected_mode = sync_value
                else:
                    selected_mode = async_value
            # Check file size threshold
            elif file_size > 0:
                if file_size < self.SYNC_SIZE_THRESHOLD:
                    selected_mode = sync_value
                else:
                    selected_mode = async_value
            else:
                # No size information available, default to ASYNC
                selected_mode = async_value

            # If resources are limited, prefer ASYNC even for small datasets
            if selected_mode == sync_value and not resources_available:
                logger.info(
                    "Resources limited, switching from SYNC to ASYNC mode",
                    extra={
                        "asset_id": asset_id,
                        "tenant_id": self.tenant_id,
                        "row_count": row_count,
                        "file_size": file_size
                    }
                )
                selected_mode = async_value

            logger.info(
                f"Selected execution mode: {selected_mode}",
                extra={
                    "asset_id": asset_id,
                    "tenant_id": self.tenant_id,
                    "selected_mode": selected_mode,
                    "row_count": row_count,
                    "file_size": file_size,
                    "resources_available": resources_available
                }
            )

            return selected_mode

        except Asset.DoesNotExist:
            error_msg = f"Asset {asset_id} not found"
            logger.error(
                error_msg,
                extra={
                    "asset_id": asset_id,
                    "tenant_id": self.tenant_id
                }
            )
            raise TransformationValidationError(
                error_msg,
                error_code=TransformationValidationError.ERROR_CODE_INVALID_FIELD_VALUE,
                details={"asset_id": asset_id},
                tenant_id=self.tenant_id
            )
        except Exception as e:
            logger.warning(
                f"Error selecting execution mode, defaulting to ASYNC: {e}",
                extra={
                    "asset_id": asset_id,
                    "tenant_id": self.tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )
            # Return ASYNC string value
            async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC
            return async_value

    def validate_timeout(
        self,
        timeout_seconds: Optional[int],
        execution_mode: Optional[str] = None,
        raise_on_error: bool = True
    ) -> ValidationResult:
        """
        Validate timeout configuration for pipeline execution.

        Validates:
        - Timeout is within acceptable range (MIN_TIMEOUT_SECONDS to MAX_TIMEOUT_SECONDS)
        - Timeout is appropriate for execution mode (SYNC vs ASYNC)
        - Timeout is not unreasonably short for the operation type

        Args:
            timeout_seconds: Timeout in seconds (None uses default)
            execution_mode: Optional execution mode (SYNC, ASYNC) for mode-specific validation
            raise_on_error: If True, raise TransformationValidationError on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            TransformationValidationError: If timeout is invalid and raise_on_error is True
        """
        errors = []
        warnings = []
        details = {
            "timeout_validation": {}
        }

        # Get ExecutionMode string values (handle tuple format) - needed throughout method
        sync_value = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC
        async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC

        # If no timeout provided, use defaults based on execution mode
        if timeout_seconds is None:
            if execution_mode == sync_value:
                timeout_seconds = self.DEFAULT_SYNC_TIMEOUT
            elif execution_mode == async_value:
                timeout_seconds = self.DEFAULT_ASYNC_TIMEOUT
            else:
                timeout_seconds = self.DEFAULT_ASYNC_TIMEOUT  # Default to ASYNC timeout

            details["timeout_validation"]["timeout_provided"] = False
            details["timeout_validation"]["default_timeout_used"] = timeout_seconds
            warnings.append(
                f"No timeout specified, using default: {timeout_seconds} seconds "
                f"({timeout_seconds // 60} minutes)"
            )
        else:
            details["timeout_validation"]["timeout_provided"] = True
            details["timeout_validation"]["specified_timeout"] = timeout_seconds

        details["timeout_validation"]["timeout_seconds"] = timeout_seconds
        details["timeout_validation"]["execution_mode"] = execution_mode

        # Validate timeout range
        if timeout_seconds < self.MIN_TIMEOUT_SECONDS:
            errors.append(
                f"Timeout ({timeout_seconds} seconds) is below minimum allowed "
                f"({self.MIN_TIMEOUT_SECONDS} seconds / {self.MIN_TIMEOUT_SECONDS // 60} minutes). "
                f"Pipeline execution may fail prematurely."
            )
            details["timeout_validation"]["below_minimum"] = True
        else:
            details["timeout_validation"]["below_minimum"] = False

        if timeout_seconds > self.MAX_TIMEOUT_SECONDS:
            errors.append(
                f"Timeout ({timeout_seconds} seconds) exceeds maximum allowed "
                f"({self.MAX_TIMEOUT_SECONDS} seconds / {self.MAX_TIMEOUT_SECONDS // 60} minutes). "
                f"This may cause resource exhaustion."
            )
            details["timeout_validation"]["exceeds_maximum"] = True
        else:
            details["timeout_validation"]["exceeds_maximum"] = False

        # Validate timeout appropriateness for execution mode
        if execution_mode:
            if execution_mode == sync_value:
                # SYNC executions should typically be shorter
                if timeout_seconds > self.DEFAULT_ASYNC_TIMEOUT:
                    warnings.append(
                        f"SYNC execution timeout ({timeout_seconds} seconds) is longer than "
                        f"typical ASYNC timeout ({self.DEFAULT_ASYNC_TIMEOUT} seconds). "
                        f"Consider using ASYNC mode for long-running operations."
                    )
                    details["timeout_validation"]["sync_timeout_too_long"] = True
                else:
                    details["timeout_validation"]["sync_timeout_too_long"] = False

                # SYNC executions should have reasonable minimum
                if timeout_seconds < 120:  # Less than 2 minutes
                    warnings.append(
                        f"SYNC execution timeout ({timeout_seconds} seconds) may be too short. "
                        f"Consider at least 2 minutes for reliable completion."
                    )
                    details["timeout_validation"]["sync_timeout_too_short"] = True
                else:
                    details["timeout_validation"]["sync_timeout_too_short"] = False

            elif execution_mode == async_value:
                # ASYNC executions can be longer, but warn if very long
                if timeout_seconds > self.MAX_TIMEOUT_SECONDS * 0.9:  # > 90% of max
                    warnings.append(
                        f"ASYNC execution timeout ({timeout_seconds} seconds) is very close to "
                        f"maximum ({self.MAX_TIMEOUT_SECONDS} seconds). Consider breaking into "
                        f"smaller operations."
                    )
                    details["timeout_validation"]["async_timeout_very_long"] = True
                else:
                    details["timeout_validation"]["async_timeout_very_long"] = False

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            error_msg = f"Timeout validation failed: {', '.join(errors)}"
            raise TransformationValidationError(
                error_msg,
                error_code=TransformationValidationError.ERROR_CODE_INVALID_FIELD_VALUE,
                details=details,
                tenant_id=self.tenant_id
            )

        return result

    def validate_compute_quota(
        self,
        raise_on_error: bool = True
    ) -> ValidationResult:
        """
        Validate compute quota (concurrent job executions).

        Checks if tenant has capacity for additional concurrent job executions
        based on max_job_concurrency limit from TenantService.get_tenant_job_limits().

        Args:
            raise_on_error: If True, raise ResourceQuotaExceededError on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            ResourceQuotaExceededError: If compute quota is exceeded and raise_on_error is True
        """
        errors = []
        warnings = []
        details = {
            "quota_type": "compute",
            "quota_checks": {}
        }

        if not self.tenant_id:
            errors.append("tenant_id is required for compute quota validation")
            details["quota_checks"]["tenant_id_provided"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise ResourceQuotaExceededError(
                    message="tenant_id is required for compute quota validation",
                    error_code=ResourceQuotaExceededError.ERROR_CODE_CONCURRENT_EXECUTIONS_LIMIT,
                    quota_type="compute",
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    details=details
                )
            return result

        details["quota_checks"]["tenant_id_provided"] = True

        try:
            from hub.apps.tenants.services import get_tenant_job_limits
            from hub.apps.jobs.utils import check_tenant_job_limits
            from django.core.cache import cache

            # Get tenant job limits
            limits = get_tenant_job_limits(self.tenant_id)
            max_concurrency = limits["max_job_concurrency"]
            max_queued = limits["max_queued_jobs"]

            details["quota_checks"]["max_job_concurrency"] = max_concurrency
            details["quota_checks"]["max_queued_jobs"] = max_queued

            # Check tenant job limits (concurrency and queue depth)
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
                    details["quota_checks"]["limit"] = max_concurrency
                    details["quota_checks"]["current"] = running_count
                else:
                    details["quota_checks"]["concurrency_limit_exceeded"] = False

                if queued_count >= max_queued:
                    errors.append(
                        f"Tenant has reached maximum queued job limit ({max_queued}). "
                        f"Current queued jobs: {queued_count}. Please wait for queue to process."
                    )
                    details["quota_checks"]["queue_limit_exceeded"] = True
                    details["quota_checks"]["limit"] = max_queued
                    details["quota_checks"]["current"] = queued_count
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
                f"Failed to check compute quota for tenant {self.tenant_id}: {e}",
                exc_info=True
            )
            warnings.append(
                f"Could not validate compute quota: {str(e)}. "
                f"Proceeding with execution."
            )
            details["quota_checks"]["validation_error"] = str(e)

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            # Determine which quota was exceeded
            quota_type = "concurrency"
            limit = details["quota_checks"].get("max_job_concurrency")
            current = details["quota_checks"].get("running_jobs", 0)

            if details["quota_checks"].get("queue_limit_exceeded"):
                quota_type = "queue"
                limit = details["quota_checks"].get("max_queued_jobs")
                current = details["quota_checks"].get("queued_jobs", 0)

            raise ResourceQuotaExceededError(
                message="Compute quota exceeded for pipeline execution",
                error_code=ResourceQuotaExceededError.ERROR_CODE_CONCURRENT_EXECUTIONS_LIMIT,
                quota_type=quota_type,
                limit=limit,
                current=current,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                details=details
            )

        return result

    def validate_storage_quota(
        self,
        required_storage_bytes: Optional[int] = None,
        raise_on_error: bool = True
    ) -> ValidationResult:
        """
        Validate storage quota.

        Checks:
        - File size limits (max_file_size_bytes from tenant config)
        - Total storage usage (if tracked)

        Args:
            required_storage_bytes: Optional required storage in bytes for the operation
            raise_on_error: If True, raise ResourceQuotaExceededError on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            ResourceQuotaExceededError: If storage quota is exceeded and raise_on_error is True
        """
        errors = []
        warnings = []
        details = {
            "quota_type": "storage",
            "quota_checks": {}
        }

        if not self.tenant_id:
            errors.append("tenant_id is required for storage quota validation")
            details["quota_checks"]["tenant_id_provided"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise ResourceQuotaExceededError(
                    message="tenant_id is required for storage quota validation",
                    error_code=ResourceQuotaExceededError.ERROR_CODE_STORAGE_LIMIT,
                    quota_type="storage",
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    details=details
                )
            return result

        details["quota_checks"]["tenant_id_provided"] = True

        try:
            from hub.apps.tenants.services import get_tenant_file_size_limit

            # Get tenant file size limit
            max_file_size = get_tenant_file_size_limit(self.tenant_id)
            details["quota_checks"]["max_file_size_bytes"] = max_file_size

            # Check file size limit if required storage is specified
            if required_storage_bytes is not None:
                details["quota_checks"]["required_storage_bytes"] = required_storage_bytes
                if required_storage_bytes > max_file_size:
                    errors.append(
                        f"Required storage ({required_storage_bytes} bytes) exceeds "
                        f"maximum file size limit ({max_file_size} bytes)."
                    )
                    details["quota_checks"]["file_size_limit_exceeded"] = True
                    details["quota_checks"]["limit"] = max_file_size
                    details["quota_checks"]["current"] = required_storage_bytes
                else:
                    details["quota_checks"]["file_size_limit_exceeded"] = False

            # TODO: Add total storage usage check when storage tracking is implemented
            # This would check if tenant's total storage usage + required_storage_bytes
            # exceeds a total storage quota limit
            details["quota_checks"]["total_storage_check"] = "not_implemented"

        except Exception as e:
            logger.warning(
                f"Failed to check storage quota for tenant {self.tenant_id}: {e}",
                exc_info=True
            )
            warnings.append(
                f"Could not validate storage quota: {str(e)}. "
                f"Proceeding with execution."
            )
            details["quota_checks"]["validation_error"] = str(e)

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ResourceQuotaExceededError(
                message="Storage quota exceeded for pipeline execution",
                error_code=ResourceQuotaExceededError.ERROR_CODE_STORAGE_LIMIT,
                quota_type="storage",
                limit=details["quota_checks"].get("max_file_size_bytes"),
                current=details["quota_checks"].get("required_storage_bytes"),
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                details=details
            )

        return result

    def validate_query_quota(
        self,
        raise_on_error: bool = True
    ) -> ValidationResult:
        """
        Validate query quota (for preview operations).

        Checks if tenant has quota remaining for query/preview operations
        using rate limiting for SPARQL_QUERY or CATALOG_READ categories.

        Args:
            raise_on_error: If True, raise ResourceQuotaExceededError on validation failure

        Returns:
            ValidationResult with validation status and details

        Raises:
            ResourceQuotaExceededError: If query quota is exceeded and raise_on_error is True
        """
        errors = []
        warnings = []
        details = {
            "quota_type": "query",
            "quota_checks": {}
        }

        if not self.tenant_id:
            errors.append("tenant_id is required for query quota validation")
            details["quota_checks"]["tenant_id_provided"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise ResourceQuotaExceededError(
                    message="tenant_id is required for query quota validation",
                    error_code=ResourceQuotaExceededError.ERROR_CODE_QUOTA_EXCEEDED,
                    quota_type="query",
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    details=details
                )
            return result

        details["quota_checks"]["tenant_id_provided"] = True

        try:
            from hub.apps.rate_limiting.quota import QuotaManager
            from hub.apps.rate_limiting.utils import EndpointCategory, TimeWindow

            # Check SPARQL query quota (for semantic/preview queries)
            has_sparql_quota, sparql_quota_info = QuotaManager.check_quota(
                tenant_id=self.tenant_id,
                category=EndpointCategory.SPARQL_QUERY,
                window=TimeWindow.DAILY
            )

            details["quota_checks"]["sparql_query"] = {
                "has_quota": has_sparql_quota,
                "limit": sparql_quota_info.get("limit"),
                "used": sparql_quota_info.get("used"),
                "remaining": sparql_quota_info.get("remaining")
            }

            if not has_sparql_quota:
                errors.append(
                    f"Tenant has exceeded SPARQL query quota. "
                    f"Limit: {sparql_quota_info.get('limit')}, "
                    f"Used: {sparql_quota_info.get('used')}, "
                    f"Remaining: {sparql_quota_info.get('remaining')}."
                )
                details["quota_checks"]["sparql_query_limit_exceeded"] = True
                details["quota_checks"]["limit"] = sparql_quota_info.get("limit")
                details["quota_checks"]["current"] = sparql_quota_info.get("used")
            else:
                details["quota_checks"]["sparql_query_limit_exceeded"] = False

            # Check catalog read quota (for preview operations)
            has_catalog_quota, catalog_quota_info = QuotaManager.check_quota(
                tenant_id=self.tenant_id,
                category=EndpointCategory.CATALOG_READ,
                window=TimeWindow.DAILY
            )

            details["quota_checks"]["catalog_read"] = {
                "has_quota": has_catalog_quota,
                "limit": catalog_quota_info.get("limit"),
                "used": catalog_quota_info.get("used"),
                "remaining": catalog_quota_info.get("remaining")
            }

            if not has_catalog_quota:
                errors.append(
                    f"Tenant has exceeded catalog read quota. "
                    f"Limit: {catalog_quota_info.get('limit')}, "
                    f"Used: {catalog_quota_info.get('used')}, "
                    f"Remaining: {catalog_quota_info.get('remaining')}."
                )
                details["quota_checks"]["catalog_read_limit_exceeded"] = True
                # Update limit/current if not already set or if catalog is more restrictive
                if "limit" not in details["quota_checks"] or (
                    catalog_quota_info.get("used", 0) > details["quota_checks"].get("current", 0)
                ):
                    details["quota_checks"]["limit"] = catalog_quota_info.get("limit")
                    details["quota_checks"]["current"] = catalog_quota_info.get("used")
            else:
                details["quota_checks"]["catalog_read_limit_exceeded"] = False

            details["quota_checks"]["quota_exceeded"] = (
                details["quota_checks"].get("sparql_query_limit_exceeded", False) or
                details["quota_checks"].get("catalog_read_limit_exceeded", False)
            )

        except Exception as e:
            logger.warning(
                f"Failed to check query quota for tenant {self.tenant_id}: {e}",
                exc_info=True
            )
            warnings.append(
                f"Could not validate query quota: {str(e)}. "
                f"Proceeding with execution."
            )
            details["quota_checks"]["validation_error"] = str(e)

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ResourceQuotaExceededError(
                message="Query quota exceeded for preview operations",
                error_code=ResourceQuotaExceededError.ERROR_CODE_QUOTA_EXCEEDED,
                quota_type="query",
                limit=details["quota_checks"].get("limit"),
                current=details["quota_checks"].get("current"),
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                details=details
            )

        return result

