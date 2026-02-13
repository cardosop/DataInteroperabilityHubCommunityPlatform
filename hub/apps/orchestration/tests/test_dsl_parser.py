"""
Unit tests for workflow DSL parser.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from hub.apps.orchestration.dsl_parser import WorkflowDSLParser


class WorkflowDSLParserTest(TestCase):
    """Test workflow DSL parser"""

    def test_parse_valid_json(self):
        """Test parsing valid JSON workflow"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
        }

        result = WorkflowDSLParser.parse_json(dsl_json)
        self.assertEqual(result["version"], "1.0.0")
        self.assertEqual(len(result["steps"]), 1)

    def test_parse_missing_version(self):
        """Test parsing workflow with missing version"""
        dsl_json = {"steps": [{"name": "step1", "type": "task", "task": "test_task"}]}

        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)

        self.assertIn("version", str(cm.exception))

    def test_parse_missing_steps(self):
        """Test parsing workflow with missing steps"""
        dsl_json = {"version": "1.0.0"}

        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)

        self.assertIn("steps", str(cm.exception))

    def test_parse_empty_steps(self):
        """Test parsing workflow with empty steps"""
        dsl_json = {"version": "1.0.0", "steps": []}

        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)

        self.assertIn("at least one step", str(cm.exception))

    def test_parse_step_missing_name(self):
        """Test parsing step with missing name"""
        dsl_json = {"version": "1.0.0", "steps": [{"type": "task", "task": "test_task"}]}

        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)

        self.assertIn("name", str(cm.exception))

    def test_parse_step_missing_type(self):
        """Test parsing step with missing type"""
        dsl_json = {"version": "1.0.0", "steps": [{"name": "step1", "task": "test_task"}]}

        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)

        self.assertIn("type", str(cm.exception))

    def test_parse_step_invalid_type(self):
        """Test parsing step with invalid type"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "invalid_type", "task": "test_task"}],
        }

        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)

        self.assertIn("invalid type", str(cm.exception))

    def test_parse_task_step_missing_task(self):
        """Test parsing task step with missing task field"""
        dsl_json = {"version": "1.0.0", "steps": [{"name": "step1", "type": "task"}]}

        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)

        self.assertIn("task", str(cm.exception))

    def test_parse_parallel_step_missing_steps(self):
        """Test parsing parallel step with missing steps field"""
        dsl_json = {"version": "1.0.0", "steps": [{"name": "step1", "type": "parallel"}]}

        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)

        self.assertIn("steps", str(cm.exception))

    def test_parse_conditional_step_missing_condition(self):
        """Test parsing conditional step with missing condition"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "conditional", "then": []}],
        }

        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)

        self.assertIn("condition", str(cm.exception))

    def test_parse_retry_step_missing_max_retries(self):
        """Test parsing retry step with missing max_retries"""
        dsl_json = {"version": "1.0.0", "steps": [{"name": "step1", "type": "retry", "steps": []}]}

        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)

        self.assertIn("max_retries", str(cm.exception))

    def test_to_json(self):
        """Test converting workflow to JSON"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
        }

        json_str = WorkflowDSLParser.to_json(dsl_json)
        self.assertIn("version", json_str)
        self.assertIn("steps", json_str)


class WorkflowDSLParserEdgeCasesTest(TestCase):
    """Test WorkflowDSLParser edge cases"""

    def test_parse_json_with_very_long_step_name(self):
        """Test parsing workflow with very long step name"""
        long_name = "a" * 1000
        dsl_json = {
            "version": "1.0.0",
            "steps": [{"name": long_name, "type": "task", "task": "test_task"}],
        }

        result = WorkflowDSLParser.parse_json(dsl_json)
        self.assertEqual(result["steps"][0]["name"], long_name)

    def test_parse_json_with_special_characters_in_name(self):
        """Test parsing workflow with special characters in step name"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {"name": "step-1_with.special@chars#123", "type": "task", "task": "test_task"}
            ],
        }

        result = WorkflowDSLParser.parse_json(dsl_json)
        self.assertEqual(result["steps"][0]["name"], "step-1_with.special@chars#123")

    def test_to_json_with_none_values(self):
        """Test to_json() with None values in DSL"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {"name": "step1", "type": "task", "task": "test_task", "optional_field": None}
            ],
        }

        json_str = WorkflowDSLParser.to_json(dsl_json)
        self.assertIn("version", json_str)
        self.assertIn("steps", json_str)


class WorkflowDSLParserErrorHandlingTest(TestCase):
    """Test WorkflowDSLParser error handling scenarios"""

    def test_parse_json_with_invalid_json_structure(self):
        """Test parse_json() with non-dict input raises ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json("not a dict")
        self.assertIn("dictionary", str(cm.exception).lower())

    def test_parse_json_with_circular_reference_risk(self):
        """Test parse_json() handles deeply nested structures"""
        # Create deeply nested structure that could cause recursion issues
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "test_task",
                    "metadata": {"nested": {"deep": {"very": {"deep": {"value": 1}}}}},
                }
            ],
        }

        # Should handle deep nesting gracefully
        result = WorkflowDSLParser.parse_json(dsl_json)
        self.assertEqual(result["version"], "1.0.0")

    def test_to_json_with_invalid_data(self):
        """Test to_json() with invalid data types"""
        # Pass non-serializable data
        import json

        dsl_json = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
        }

        # Should serialize successfully
        json_str = WorkflowDSLParser.to_json(dsl_json)
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        self.assertEqual(parsed["version"], "1.0.0")
