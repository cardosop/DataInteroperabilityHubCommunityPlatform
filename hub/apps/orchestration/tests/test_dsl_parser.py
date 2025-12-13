"""
Unit tests for workflow DSL parser.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError

from hub.apps.orchestration.dsl_parser import WorkflowDSLParser


class WorkflowDSLParserTest(TestCase):
    """Test workflow DSL parser"""
    
    def test_parse_valid_json(self):
        """Test parsing valid JSON workflow"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "test_task"
                }
            ]
        }
        
        result = WorkflowDSLParser.parse_json(dsl_json)
        self.assertEqual(result["version"], "1.0.0")
        self.assertEqual(len(result["steps"]), 1)
    
    def test_parse_missing_version(self):
        """Test parsing workflow with missing version"""
        dsl_json = {
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "test_task"
                }
            ]
        }
        
        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)
        
        self.assertIn("version", str(cm.exception))
    
    def test_parse_missing_steps(self):
        """Test parsing workflow with missing steps"""
        dsl_json = {
            "version": "1.0.0"
        }
        
        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)
        
        self.assertIn("steps", str(cm.exception))
    
    def test_parse_empty_steps(self):
        """Test parsing workflow with empty steps"""
        dsl_json = {
            "version": "1.0.0",
            "steps": []
        }
        
        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)
        
        self.assertIn("at least one step", str(cm.exception))
    
    def test_parse_step_missing_name(self):
        """Test parsing step with missing name"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {
                    "type": "task",
                    "task": "test_task"
                }
            ]
        }
        
        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)
        
        self.assertIn("name", str(cm.exception))
    
    def test_parse_step_missing_type(self):
        """Test parsing step with missing type"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "task": "test_task"
                }
            ]
        }
        
        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)
        
        self.assertIn("type", str(cm.exception))
    
    def test_parse_step_invalid_type(self):
        """Test parsing step with invalid type"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "invalid_type",
                    "task": "test_task"
                }
            ]
        }
        
        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)
        
        self.assertIn("invalid type", str(cm.exception))
    
    def test_parse_task_step_missing_task(self):
        """Test parsing task step with missing task field"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "task"
                }
            ]
        }
        
        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)
        
        self.assertIn("task", str(cm.exception))
    
    def test_parse_parallel_step_missing_steps(self):
        """Test parsing parallel step with missing steps field"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "parallel"
                }
            ]
        }
        
        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)
        
        self.assertIn("steps", str(cm.exception))
    
    def test_parse_conditional_step_missing_condition(self):
        """Test parsing conditional step with missing condition"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "conditional",
                    "then": []
                }
            ]
        }
        
        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)
        
        self.assertIn("condition", str(cm.exception))
    
    def test_parse_retry_step_missing_max_retries(self):
        """Test parsing retry step with missing max_retries"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "retry",
                    "steps": []
                }
            ]
        }
        
        with self.assertRaises(ValidationError) as cm:
            WorkflowDSLParser.parse_json(dsl_json)
        
        self.assertIn("max_retries", str(cm.exception))
    
    def test_to_json(self):
        """Test converting workflow to JSON"""
        dsl_json = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "test_task"
                }
            ]
        }
        
        json_str = WorkflowDSLParser.to_json(dsl_json)
        self.assertIn("version", json_str)
        self.assertIn("steps", json_str)

