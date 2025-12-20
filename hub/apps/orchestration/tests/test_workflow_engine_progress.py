"""
Unit tests for WorkflowEngine progress calculation.

Tests verify that progress calculation works correctly for all scenarios:
- 0% progress (not started)
- 50% progress (middle)
- 100% progress (completed)
- Edge cases (total_steps=0, current_step_index=-1, etc.)
"""
try:
    import pytest
    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import uuid
from django.test import TestCase

from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from hub.apps.orchestration.workflow_engine import WorkflowEngine


class WorkflowEngineProgressCalculationTest(TestCase):
    """Test WorkflowEngine progress calculation"""

    def setUp(self):
        """Set up test fixtures"""
        self.engine = WorkflowEngine()
        self.test_counter = 0

    def _create_workflow_instance(self, total_steps: int, current_step_index: int = 0) -> WorkflowInstance:
        """Helper to create a workflow instance with specified steps and current index"""
        # Use unique workflow name/version for each test to avoid unique constraint violations
        self.test_counter += 1
        unique_id = str(uuid.uuid4())[:8]
        workflow_name = f"test_workflow_{self.test_counter}_{unique_id}"
        workflow_version = f"1.0.{self.test_counter}"

        # Create workflow definition with specified number of steps
        # Note: WorkflowDefinition requires at least one step, so we can't test total_steps=0
        # using the model. We'll handle that case separately.
        if total_steps == 0:
            # For 0 steps case, we'll create a minimal workflow and mock the DSL
            dsl_json = {
                "version": "1.0",
                "steps": [
                    {
                        "name": "dummy_step",
                        "type": "task",
                        "task": "test_task"
                    }
                ]
            }
        else:
            dsl_json = {
                "version": "1.0",
                "steps": [
                    {
                        "name": f"step_{i}",
                        "type": "task",
                        "task": "test_task"
                    }
                    for i in range(total_steps)
                ]
            }

        workflow_def = WorkflowDefinition.objects.create(
            name=workflow_name,
            version=workflow_version,
            dsl_json=dsl_json
        )

        # Create workflow instance
        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=workflow_name,
            workflow_version=workflow_version,
            status=WorkflowStatus.RUNNING,
            current_step_index=current_step_index
        )

        # For 0 steps case, we need to mock the DSL to return empty steps
        if total_steps == 0:
            # Patch the workflow_definition.dsl_json to have empty steps
            original_dsl = workflow_def.dsl_json
            workflow_def.dsl_json = {"version": "1.0", "steps": []}
            workflow_def.save()
            # Refresh instance to get updated definition
            instance.refresh_from_db()

        return instance

    def test_progress_25_percent_at_step_0(self):
        """Test that progress is 25% when at step 0 of 4 (first step)"""
        instance = self._create_workflow_instance(total_steps=4, current_step_index=0)

        progress = self.engine._calculate_progress(instance)

        expected_progress = ((0 + 1) / 4) * 100.0  # 25%
        self.assertEqual(progress, expected_progress,
                        f"Progress should be {expected_progress}% when at step 0 of 4")

    def test_progress_0_percent_negative_index(self):
        """Test that progress is 0% when current_step_index = -1"""
        instance = self._create_workflow_instance(total_steps=4, current_step_index=-1)

        progress = self.engine._calculate_progress(instance)

        self.assertEqual(progress, 0.0, "Progress should be 0% when current_step_index = -1")

    def test_progress_25_percent_first_step(self):
        """Test that progress is 25% when at step 0 of 4 (first step)"""
        instance = self._create_workflow_instance(total_steps=4, current_step_index=0)

        # After completing step 0, current_step_index becomes 1
        # Progress = (1 + 1) / 4 * 100 = 50%
        # Actually, if we're at step 0 (just started), progress should be 25%
        # Let me recalculate: if current_step_index=0 means we're about to execute step 0
        # After step 0 completes, current_step_index=1, progress = (1+1)/4*100 = 50%
        # So at current_step_index=0, we're at step 0, progress = (0+1)/4*100 = 25%
        progress = self.engine._calculate_progress(instance)

        expected_progress = ((0 + 1) / 4) * 100.0  # 25%
        self.assertEqual(progress, expected_progress,
                        f"Progress should be {expected_progress}% when at step 0 of 4")

    def test_progress_50_percent_middle(self):
        """Test that progress is 50% when at middle step"""
        instance = self._create_workflow_instance(total_steps=4, current_step_index=1)

        progress = self.engine._calculate_progress(instance)

        expected_progress = ((1 + 1) / 4) * 100.0  # 50%
        self.assertEqual(progress, expected_progress,
                        f"Progress should be {expected_progress}% when at step 1 of 4")

    def test_progress_100_percent_completed(self):
        """Test that progress is 100% when all steps completed"""
        instance = self._create_workflow_instance(total_steps=4, current_step_index=4)

        progress = self.engine._calculate_progress(instance)

        self.assertEqual(progress, 100.0, "Progress should be 100% when current_step_index equals total_steps")

    def test_progress_100_percent_beyond_completed(self):
        """Test that progress is 100% when current_step_index > total_steps"""
        instance = self._create_workflow_instance(total_steps=4, current_step_index=5)

        progress = self.engine._calculate_progress(instance)

        self.assertEqual(progress, 100.0, "Progress should be 100% when current_step_index > total_steps")

    def test_progress_edge_case_total_steps_zero(self):
        """Test that progress is 0% when total_steps = 0 (Task 0.3.1)"""
        # Create a workflow instance with at least one step (model requirement for validation)
        self.test_counter += 1
        unique_id = str(uuid.uuid4())[:8]
        workflow_name = f"test_workflow_zero_{self.test_counter}_{unique_id}"
        workflow_version = f"1.0.{self.test_counter}"

        dsl_json = {
            "version": "1.0",
            "steps": [
                {
                    "name": "dummy_step",
                    "type": "task",
                    "task": "test_task"
                }
            ]
        }

        workflow_def = WorkflowDefinition.objects.create(
            name=workflow_name,
            version=workflow_version,
            dsl_json=dsl_json
        )

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=workflow_name,
            workflow_version=workflow_version,
            status=WorkflowStatus.RUNNING,
            current_step_index=0
        )

        # Update dsl_json directly in database to have 0 steps (bypassing model validation)
        # This tests the edge case where total_steps = 0 without using mocks
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE workflow_definitions
                SET dsl_json = %s::jsonb
                WHERE id = %s
                """,
                ['{"version": "1.0", "steps": []}', str(workflow_def.id)]
            )

        # Refresh instance to get updated definition
        instance.refresh_from_db()
        workflow_def.refresh_from_db()

        # Verify the edge case is handled correctly
        progress = self.engine._calculate_progress(instance)
        self.assertEqual(progress, 0.0, "Progress should be 0% when total_steps = 0")

    def test_progress_edge_case_single_step(self):
        """Test progress calculation for single step workflow"""
        instance = self._create_workflow_instance(total_steps=1, current_step_index=0)

        progress = self.engine._calculate_progress(instance)

        expected_progress = ((0 + 1) / 1) * 100.0  # 100%
        self.assertEqual(progress, expected_progress,
                        f"Progress should be {expected_progress}% when at step 0 of 1")

    def test_progress_edge_case_single_step_completed(self):
        """Test progress calculation for single step workflow when completed"""
        instance = self._create_workflow_instance(total_steps=1, current_step_index=1)

        progress = self.engine._calculate_progress(instance)

        self.assertEqual(progress, 100.0, "Progress should be 100% when single step completed")

    def test_progress_calculation_formula(self):
        """Test that progress calculation follows the correct formula"""
        test_cases = [
            (4, 0, 25.0),   # Step 0 of 4 = 25%
            (4, 1, 50.0),   # Step 1 of 4 = 50%
            (4, 2, 75.0),   # Step 2 of 4 = 75%
            (4, 3, 100.0),  # Step 3 of 4 = 100%
            (10, 4, 50.0),  # Step 4 of 10 = 50%
            (10, 9, 100.0), # Step 9 of 10 = 100%
            (2, 0, 50.0),   # Step 0 of 2 = 50%
            (2, 1, 100.0),  # Step 1 of 2 = 100%
        ]

        for total_steps, current_step_index, expected_progress in test_cases:
            with self.subTest(total_steps=total_steps, current_step_index=current_step_index):
                instance = self._create_workflow_instance(
                    total_steps=total_steps,
                    current_step_index=current_step_index
                )

                progress = self.engine._calculate_progress(instance)

                self.assertEqual(
                    progress, expected_progress,
                    f"Progress should be {expected_progress}% for step {current_step_index} of {total_steps}"
                )

    def test_progress_returns_float(self):
        """Test that progress calculation returns a float"""
        instance = self._create_workflow_instance(total_steps=4, current_step_index=1)

        progress = self.engine._calculate_progress(instance)

        self.assertIsInstance(progress, float, "Progress should be a float")

    def test_progress_is_bounded_0_to_100(self):
        """Test that progress is always between 0.0 and 100.0"""
        test_cases = [
            (4, -5),   # Negative index
            (4, -1),   # -1 index
            (4, 0),    # Start
            (4, 2),    # Middle
            (4, 4),    # Completed
            (4, 10),   # Beyond completed
        ]

        for total_steps, current_step_index in test_cases:
            with self.subTest(total_steps=total_steps, current_step_index=current_step_index):
                instance = self._create_workflow_instance(
                    total_steps=total_steps,
                    current_step_index=current_step_index
                )

                progress = self.engine._calculate_progress(instance)

                self.assertGreaterEqual(
                    progress, 0.0,
                    f"Progress should be >= 0.0 for step {current_step_index} of {total_steps}"
                )
                self.assertLessEqual(
                    progress, 100.0,
                    f"Progress should be <= 100.0 for step {current_step_index} of {total_steps}"
                )

        # Test 0 steps case separately (bypassing model validation using direct DB update)
        self.test_counter += 1
        unique_id = str(uuid.uuid4())[:8]
        workflow_name = f"test_workflow_bounded_{self.test_counter}_{unique_id}"
        workflow_version = f"1.0.{self.test_counter}"

        dsl_json = {
            "version": "1.0",
            "steps": [{"name": "dummy", "type": "task", "task": "test_task"}]
        }

        workflow_def = WorkflowDefinition.objects.create(
            name=workflow_name,
            version=workflow_version,
            dsl_json=dsl_json
        )

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=workflow_name,
            workflow_version=workflow_version,
            status=WorkflowStatus.RUNNING,
            current_step_index=0
        )

        # Update dsl_json directly in database to have 0 steps (bypassing model validation)
        # This tests the edge case without using mocks
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE workflow_definitions
                SET dsl_json = %s::jsonb
                WHERE id = %s
                """,
                ['{"version": "1.0", "steps": []}', str(workflow_def.id)]
            )

        # Refresh to get updated definition
        instance.refresh_from_db()
        workflow_def.refresh_from_db()

        progress = self.engine._calculate_progress(instance)
        self.assertGreaterEqual(progress, 0.0, "Progress should be >= 0.0 for 0 steps")
        self.assertLessEqual(progress, 100.0, "Progress should be <= 100.0 for 0 steps")

    def test_progress_with_real_workflow_instance(self):
        """Test progress calculation with a real workflow instance from create_instance"""
        # Register a test task
        def test_task(input_data, instance, step):
            return {"result": "success"}

        self.engine.register_task("test_task", test_task)

        # Create a workflow definition first
        unique_id = str(uuid.uuid4())[:8]
        workflow_name = f"test_workflow_real_{unique_id}"

        dsl_json = {
            "version": "1.0",
            "steps": [
                {"name": "step_1", "type": "task", "task": "test_task"},
                {"name": "step_2", "type": "task", "task": "test_task"},
            ]
        }

        WorkflowDefinition.objects.create(
            name=workflow_name,
            version="1.0",
            dsl_json=dsl_json
        )

        # Create workflow instance using the engine
        instance = self.engine.create_instance(
            workflow_name=workflow_name,
            input_data={},
            workflow_version="1.0"
        )

        # Initially, current_step_index should be 0
        progress = self.engine._calculate_progress(instance)

        # Should have some steps (at least 1)
        # With 2 steps and current_step_index=0, progress = (0+1)/2*100 = 50%
        expected_progress = ((0 + 1) / 2) * 100.0  # 50%
        self.assertEqual(progress, expected_progress,
                        f"Progress should be {expected_progress}% for a newly created workflow with 2 steps")
        self.assertLessEqual(progress, 100.0, "Progress should be <= 100%")

    def test_progress_edge_case_very_large_step_index(self):
        """Test progress calculation with very large current_step_index (Task 0.3.1)"""
        instance = self._create_workflow_instance(total_steps=5, current_step_index=1000)

        progress = self.engine._calculate_progress(instance)

        # Should be capped at 100.0
        self.assertEqual(progress, 100.0, "Progress should be 100% when current_step_index >> total_steps")

    def test_progress_edge_case_negative_step_index_beyond_negative_one(self):
        """Test progress calculation with current_step_index < -1 (Task 0.3.1)"""
        instance = self._create_workflow_instance(total_steps=5, current_step_index=-10)

        progress = self.engine._calculate_progress(instance)

        # Should be 0.0 for any negative index
        self.assertEqual(progress, 0.0, "Progress should be 0% when current_step_index < 0")

    def test_progress_edge_case_exactly_at_completion(self):
        """Test progress calculation when current_step_index exactly equals total_steps (Task 0.3.1)"""
        instance = self._create_workflow_instance(total_steps=5, current_step_index=5)

        progress = self.engine._calculate_progress(instance)

        # Should be 100.0 when current_step_index == total_steps
        self.assertEqual(progress, 100.0, "Progress should be 100% when current_step_index == total_steps")

    def test_progress_edge_case_one_before_completion(self):
        """Test progress calculation when current_step_index is one before completion (Task 0.3.1)"""
        instance = self._create_workflow_instance(total_steps=5, current_step_index=4)

        progress = self.engine._calculate_progress(instance)

        # Should be 100% (4+1)/5*100 = 100%
        expected_progress = ((4 + 1) / 5) * 100.0  # 100%
        self.assertEqual(progress, expected_progress,
                        f"Progress should be {expected_progress}% when at last step")

    def test_progress_formula_consistency(self):
        """Test that progress calculation formula is consistent across different step counts (Task 0.3.1)"""
        # Test various combinations to ensure formula consistency
        test_cases = [
            (1, 0, 100.0),    # Single step at start = 100%
            (2, 0, 50.0),     # Two steps at start = 50%
            (2, 1, 100.0),    # Two steps at end = 100%
            (3, 0, 33.333333333333336),  # Three steps at start ≈ 33.33%
            (3, 1, 66.66666666666667),   # Three steps at middle ≈ 66.67%
            (3, 2, 100.0),    # Three steps at end = 100%
            (5, 2, 60.0),     # Five steps at index 2 = 60%
            (10, 4, 50.0),    # Ten steps at index 4 = 50%
            (100, 49, 50.0),  # 100 steps at index 49 = 50%
        ]

        for total_steps, current_step_index, expected_progress in test_cases:
            with self.subTest(total_steps=total_steps, current_step_index=current_step_index):
                instance = self._create_workflow_instance(
                    total_steps=total_steps,
                    current_step_index=current_step_index
                )

                progress = self.engine._calculate_progress(instance)

                # Use almostEqual for floating point comparisons
                self.assertAlmostEqual(
                    progress, expected_progress, places=5,
                    msg=f"Progress should be {expected_progress}% for step {current_step_index} of {total_steps}, got {progress}%"
                )

