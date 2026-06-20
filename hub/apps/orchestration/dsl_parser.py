"""
Workflow DSL Parser

Parses workflow definitions in YAML/JSON format and validates structure.
"""

import json
from typing import Any

import yaml
from django.core.exceptions import ValidationError


class WorkflowDSLParser:
    """
    Workflow DSL parser.

    Supports both YAML and JSON formats.
    Validates workflow structure and semantics.
    """

    # Supported step types
    STEP_TYPES = {
        "task",  # Single task execution
        "parallel",  # Parallel task execution
        "conditional",  # Conditional branching
        "loop",  # Loop execution
        "wait",  # Wait for condition
        "retry",  # Retry logic wrapper
        "compensate",  # Compensation step
    }

    # Required workflow fields
    REQUIRED_WORKFLOW_FIELDS = {"version", "steps"}

    # Required step fields
    REQUIRED_STEP_FIELDS = {"name", "type"}

    @classmethod
    def parse(cls, dsl_content: str, format: str = "json") -> dict[str, Any]:
        """
        Parse workflow DSL content.

        Args:
            dsl_content: Workflow DSL content (JSON or YAML string)
            format: Format type ("json" or "yaml")

        Returns:
            Parsed workflow definition dictionary

        Raises:
            ValidationError: If DSL is invalid
        """
        try:
            if format.lower() == "json":
                workflow_def = json.loads(dsl_content)
            elif format.lower() == "yaml":
                workflow_def = yaml.safe_load(dsl_content)
            else:
                raise ValidationError(f"Unsupported format: {format}. Supported: json, yaml")
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise ValidationError(f"Invalid {format.upper()} format: {e!s}")

        # Validate workflow structure
        cls._validate_workflow(workflow_def)

        return workflow_def

    @classmethod
    def parse_json(cls, dsl_json: dict[str, Any]) -> dict[str, Any]:
        """
        Parse workflow DSL from JSON dictionary.

        Args:
            dsl_json: Workflow DSL dictionary

        Returns:
            Validated workflow definition dictionary

        Raises:
            ValidationError: If DSL is invalid
        """
        cls._validate_workflow(dsl_json)
        return dsl_json

    @classmethod
    def _validate_workflow(cls, workflow_def: dict[str, Any]) -> None:
        """
        Validate workflow definition structure.

        Args:
            workflow_def: Workflow definition dictionary

        Raises:
            ValidationError: If workflow definition is invalid
        """
        if not isinstance(workflow_def, dict):
            raise ValidationError("Workflow definition must be a dictionary")

        # Check required fields
        missing_fields = cls.REQUIRED_WORKFLOW_FIELDS - set(workflow_def.keys())
        if missing_fields:
            raise ValidationError(f"Missing required workflow fields: {', '.join(missing_fields)}")

        # Validate version
        version = workflow_def.get("version")
        if not isinstance(version, str):
            raise ValidationError("Workflow version must be a string")

        # Validate steps
        steps = workflow_def.get("steps")
        if not isinstance(steps, list):
            raise ValidationError("Workflow steps must be a list")

        if len(steps) == 0:
            raise ValidationError("Workflow must contain at least one step")

        # Validate each step
        for i, step in enumerate(steps):
            cls._validate_step(step, i)

        # Validate dependencies if present
        dependencies = workflow_def.get("dependencies", [])
        if dependencies:
            if not isinstance(dependencies, list):
                raise ValidationError("Workflow dependencies must be a list")
            for dep in dependencies:
                if not isinstance(dep, str):
                    raise ValidationError("Each dependency must be a string (workflow name)")

    @classmethod
    def _validate_step(cls, step: dict[str, Any], step_index: int) -> None:
        """
        Validate a workflow step.

        Args:
            step: Step definition dictionary
            step_index: Step index (for error messages)

        Raises:
            ValidationError: If step is invalid
        """
        if not isinstance(step, dict):
            raise ValidationError(f"Step {step_index} must be a dictionary")

        # Check required fields
        missing_fields = cls.REQUIRED_STEP_FIELDS - set(step.keys())
        if missing_fields:
            raise ValidationError(
                f"Step {step_index} missing required fields: {', '.join(missing_fields)}"
            )

        # Validate step name
        step_name = step.get("name")
        if not isinstance(step_name, str) or not step_name.strip():
            raise ValidationError(f"Step {step_index} name must be a non-empty string")

        # Validate step type
        step_type = step.get("type")
        if step_type not in cls.STEP_TYPES:
            raise ValidationError(
                f"Step {step_index} has invalid type '{step_type}'. "
                f"Valid types: {', '.join(cls.STEP_TYPES)}"
            )

        # Validate step-specific fields based on type
        if step_type == "task":
            cls._validate_task_step(step, step_index)
        elif step_type == "parallel":
            cls._validate_parallel_step(step, step_index)
        elif step_type == "conditional":
            cls._validate_conditional_step(step, step_index)
        elif step_type == "loop":
            cls._validate_loop_step(step, step_index)
        elif step_type == "retry":
            cls._validate_retry_step(step, step_index)

    @classmethod
    def _validate_task_step(cls, step: dict[str, Any], step_index: int) -> None:
        """Validate a task step"""
        # Task steps should have 'task' field (task identifier or function name)
        if "task" not in step:
            raise ValidationError(f"Step {step_index} (type: task) must have 'task' field")

    @classmethod
    def _validate_parallel_step(cls, step: dict[str, Any], step_index: int) -> None:
        """Validate a parallel step"""
        if "steps" not in step:
            raise ValidationError(f"Step {step_index} (type: parallel) must have 'steps' field")
        if not isinstance(step["steps"], list):
            raise ValidationError(f"Step {step_index} (type: parallel) 'steps' must be a list")
        if len(step["steps"]) == 0:
            raise ValidationError(f"Step {step_index} (type: parallel) must have at least one step")

    @classmethod
    def _validate_conditional_step(cls, step: dict[str, Any], step_index: int) -> None:
        """Validate a conditional step"""
        if "condition" not in step:
            raise ValidationError(
                f"Step {step_index} (type: conditional) must have 'condition' field"
            )
        if "then" not in step:
            raise ValidationError(f"Step {step_index} (type: conditional) must have 'then' field")

    @classmethod
    def _validate_loop_step(cls, step: dict[str, Any], step_index: int) -> None:
        """Validate a loop step"""
        if "items" not in step and "condition" not in step:
            raise ValidationError(
                f"Step {step_index} (type: loop) must have either 'items' or 'condition' field"
            )
        if "steps" not in step:
            raise ValidationError(f"Step {step_index} (type: loop) must have 'steps' field")

    @classmethod
    def _validate_retry_step(cls, step: dict[str, Any], step_index: int) -> None:
        """Validate a retry step"""
        if "max_retries" not in step:
            raise ValidationError(f"Step {step_index} (type: retry) must have 'max_retries' field")
        if "steps" not in step:
            raise ValidationError(f"Step {step_index} (type: retry) must have 'steps' field")

    @classmethod
    def to_json(cls, workflow_def: dict[str, Any]) -> str:
        """
        Convert workflow definition to JSON string.

        Args:
            workflow_def: Workflow definition dictionary

        Returns:
            JSON string representation
        """
        return json.dumps(workflow_def, indent=2)

    @classmethod
    def to_yaml(cls, workflow_def: dict[str, Any]) -> str:
        """
        Convert workflow definition to YAML string.

        Args:
            workflow_def: Workflow definition dictionary

        Returns:
            YAML string representation
        """
        return yaml.dump(workflow_def, default_flow_style=False, sort_keys=False)
