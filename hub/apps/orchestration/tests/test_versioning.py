"""
Unit tests for workflow versioning.
"""

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from hub.apps.orchestration.models import WorkflowDefinition
from hub.apps.orchestration.versioning import WorkflowVersionManager

pytestmark = pytest.mark.django_db(transaction=True)


class WorkflowVersionManagerTest(TestCase):
    """Test WorkflowVersionManager"""

    def setUp(self):
        self.valid_dsl = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "test_task"}],
        }
        self.workflow_name = f"test_workflow_{uuid.uuid4().hex[:8]}"

    def test_get_workflow_definition_with_version(self):
        """Test getting workflow definition with specific version"""
        WorkflowDefinition.objects.create(
            name=self.workflow_name, version="1.0.0", dsl_json=self.valid_dsl
        )

        workflow_def = WorkflowVersionManager.get_workflow_definition(
            self.workflow_name, version="1.0.0"
        )

        self.assertIsNotNone(workflow_def)
        self.assertEqual(workflow_def.version, "1.0.0")

    def test_get_workflow_definition_active(self):
        """Test getting active workflow definition"""
        WorkflowDefinition.objects.create(
            name=self.workflow_name, version="1.0.0", dsl_json=self.valid_dsl, is_active=True
        )
        WorkflowDefinition.objects.create(
            name=self.workflow_name, version="1.0.1", dsl_json=self.valid_dsl, is_active=False
        )

        workflow_def = WorkflowVersionManager.get_workflow_definition(self.workflow_name)

        self.assertIsNotNone(workflow_def)
        self.assertEqual(workflow_def.version, "1.0.0")
        self.assertTrue(workflow_def.is_active)

    def test_get_all_versions(self):
        """Test getting all versions of a workflow"""
        WorkflowDefinition.objects.create(
            name=self.workflow_name, version="1.0.0", dsl_json=self.valid_dsl
        )
        WorkflowDefinition.objects.create(
            name=self.workflow_name, version="1.0.1", dsl_json=self.valid_dsl
        )

        versions = WorkflowVersionManager.get_all_versions(self.workflow_name)

        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].version, "1.0.1")  # Ordered by -version

    def test_create_version_with_version(self):
        """Test creating workflow version with specified version"""
        workflow_def = WorkflowVersionManager.create_version(
            workflow_name=self.workflow_name, dsl_json=self.valid_dsl, version="1.0.0"
        )

        self.assertEqual(workflow_def.version, "1.0.0")
        self.assertTrue(workflow_def.is_active)

    def test_create_version_auto_increment(self):
        """Test creating workflow version with auto-increment"""
        WorkflowDefinition.objects.create(
            name=self.workflow_name, version="1.0.0", dsl_json=self.valid_dsl
        )

        workflow_def = WorkflowVersionManager.create_version(
            workflow_name=self.workflow_name, dsl_json=self.valid_dsl
        )

        self.assertEqual(workflow_def.version, "1.0.1")

    def test_create_version_first_version(self):
        """Test creating first version of workflow"""
        workflow_def = WorkflowVersionManager.create_version(
            workflow_name=self.workflow_name, dsl_json=self.valid_dsl
        )

        self.assertEqual(workflow_def.version, "1.0.0")

    def test_activate_version(self):
        """Test activating a workflow version"""
        WorkflowDefinition.objects.create(
            name=self.workflow_name, version="1.0.0", dsl_json=self.valid_dsl, is_active=True
        )
        WorkflowDefinition.objects.create(
            name=self.workflow_name, version="1.0.1", dsl_json=self.valid_dsl, is_active=False
        )

        activated = WorkflowVersionManager.activate_version(self.workflow_name, "1.0.1")

        self.assertTrue(activated.is_active)

        # Check that other version is deactivated
        workflow_def_1 = WorkflowDefinition.objects.get(name=self.workflow_name, version="1.0.0")
        self.assertFalse(workflow_def_1.is_active)

    def test_validate_version_valid(self):
        """Test validating valid version format"""
        try:
            WorkflowVersionManager._validate_version("1.0.0")
        except ValidationError:
            self.fail("_validate_version raised ValidationError for valid version")

    def test_validate_version_invalid(self):
        """Test validating invalid version format"""
        with self.assertRaises(ValidationError):
            WorkflowVersionManager._validate_version("invalid")

        with self.assertRaises(ValidationError):
            WorkflowVersionManager._validate_version("1.0")

        with self.assertRaises(ValidationError):
            WorkflowVersionManager._validate_version("1.0.0.0")

    def test_increment_patch_version(self):
        """Test incrementing patch version"""
        result = WorkflowVersionManager._increment_patch_version("1.0.0")
        self.assertEqual(result, "1.0.1")

        result = WorkflowVersionManager._increment_patch_version("1.2.5")
        self.assertEqual(result, "1.2.6")

    def test_compare_versions(self):
        """Test comparing versions"""
        result = WorkflowVersionManager.compare_versions("1.0.0", "1.0.1")
        self.assertEqual(result, -1)

        result = WorkflowVersionManager.compare_versions("1.0.1", "1.0.0")
        self.assertEqual(result, 1)

        result = WorkflowVersionManager.compare_versions("1.0.0", "1.0.0")
        self.assertEqual(result, 0)
