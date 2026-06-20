"""
Comprehensive tests for Saga pattern implementation.

Tests saga step definition, execution, compensation, and error handling.
"""

import uuid

from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.saga import (
    SagaCompensationError,
    SagaExecutionError,
    SagaOrchestrator,
    SagaStatus,
    SagaStep,
    SagaStepResult,
)


class SagaPatternTest(TestCase):
    """Test Saga pattern implementation"""

    def setUp(self):
        """Set up test fixtures"""
        self.saga_id = str(uuid.uuid4())

        # Track execution for verification
        self.execution_log = []
        self.compensation_log = []

    def _create_success_action(self, step_name: str, output_data: dict = None):
        """Create a successful forward action"""
        # Capture reference to execution_log to ensure closure uses current instance
        execution_log = self.execution_log

        def action(input_data: dict) -> SagaStepResult:
            execution_log.append(
                {
                    "step": step_name,
                    "action": "forward",
                    "input": input_data.copy(),
                    "timestamp": timezone.now(),
                }
            )
            return SagaStepResult.success_result(
                output=output_data or {"result": f"{step_name}_completed"}
            )

        return action

    def _create_failure_action(self, step_name: str, error_message: str = None):
        """Create a failing forward action"""
        # Capture reference to execution_log to ensure closure uses current instance
        execution_log = self.execution_log

        def action(input_data: dict) -> SagaStepResult:
            execution_log.append(
                {
                    "step": step_name,
                    "action": "forward",
                    "input": input_data.copy(),
                    "timestamp": timezone.now(),
                }
            )
            return SagaStepResult.failure_result(
                error=error_message or f"{step_name}_failed", error_details={"step": step_name}
            )

        return action

    def _create_compensation_action(self, step_name: str):
        """Create a compensation action"""
        # Capture reference to compensation_log to ensure closure uses current instance
        compensation_log = self.compensation_log

        def action(input_data: dict) -> SagaStepResult:
            compensation_log.append(
                {
                    "step": step_name,
                    "action": "compensation",
                    "input": input_data.copy(),
                    "timestamp": timezone.now(),
                }
            )
            return SagaStepResult.success_result(output={"compensated": step_name})

        return action

    def test_saga_step_definition(self):
        """Test saga step definition"""
        # Valid step with compensation
        step = SagaStep(
            name="test_step",
            forward_action=self._create_success_action("test_step"),
            compensation_action=self._create_compensation_action("test_step"),
            description="Test step",
        )

        self.assertEqual(step.name, "test_step")
        self.assertIsNotNone(step.forward_action)
        self.assertIsNotNone(step.compensation_action)
        self.assertEqual(step.description, "Test step")

        # Valid step without compensation
        step_no_comp = SagaStep(
            name="test_step_no_comp",
            forward_action=self._create_success_action("test_step_no_comp"),
        )

        self.assertIsNone(step_no_comp.compensation_action)

    def test_saga_step_validation(self):
        """Test saga step validation"""
        # Empty name should raise ValueError
        with self.assertRaises(ValueError) as cm:
            SagaStep(name="", forward_action=self._create_success_action("test"))
        self.assertIn("name is required", str(cm.exception))

        # Non-callable forward_action should raise ValueError
        with self.assertRaises(ValueError) as cm:
            SagaStep(name="test", forward_action="not_callable")
        self.assertIn("forward_action must be callable", str(cm.exception))

        # Non-callable compensation_action should raise ValueError
        with self.assertRaises(ValueError) as cm:
            SagaStep(
                name="test",
                forward_action=self._create_success_action("test"),
                compensation_action="not_callable",
            )
        self.assertIn("compensation_action must be callable", str(cm.exception))

    def test_saga_step_result_creation(self):
        """Test saga step result creation"""
        # Success result
        success_result = SagaStepResult.success_result(output={"key": "value"})
        self.assertTrue(success_result.success)
        self.assertEqual(success_result.output, {"key": "value"})
        self.assertIsNone(success_result.error)

        # Failure result
        failure_result = SagaStepResult.failure_result(
            error="Test error", error_details={"code": "TEST_ERROR"}
        )
        self.assertFalse(failure_result.success)
        self.assertEqual(failure_result.error, "Test error")
        self.assertEqual(failure_result.error_details, {"code": "TEST_ERROR"})

    def test_saga_execution_success(self):
        """Test successful saga execution"""
        orchestrator = SagaOrchestrator(saga_id=self.saga_id)

        steps = [
            SagaStep(
                name="step1",
                forward_action=self._create_success_action("step1", {"value1": 1}),
                compensation_action=self._create_compensation_action("step1"),
            ),
            SagaStep(
                name="step2",
                forward_action=self._create_success_action("step2", {"value2": 2}),
                compensation_action=self._create_compensation_action("step2"),
            ),
            SagaStep(
                name="step3",
                forward_action=self._create_success_action("step3", {"value3": 3}),
                compensation_action=self._create_compensation_action("step3"),
            ),
        ]

        context = orchestrator.execute(steps, initial_state={"initial": "data"})

        # Verify execution
        self.assertEqual(orchestrator.get_status(), SagaStatus.COMPLETED)
        self.assertEqual(len(context.step_results), 3)
        self.assertEqual(len(self.execution_log), 3)
        self.assertEqual(len(self.compensation_log), 0)  # No compensation needed

        # Verify all steps succeeded
        for step, result in context.step_results:
            self.assertTrue(result.success, f"Step {step.name} should have succeeded")

        # Verify state propagation
        self.assertIn("value1", context.state)
        self.assertIn("value2", context.state)
        self.assertIn("value3", context.state)
        self.assertEqual(context.state["value1"], 1)
        self.assertEqual(context.state["value2"], 2)
        self.assertEqual(context.state["value3"], 3)

    def test_saga_execution_with_step_failure(self):
        """Test saga execution with step failure and compensation"""
        # Reset logs for this test
        self.execution_log = []
        self.compensation_log = []

        orchestrator = SagaOrchestrator(saga_id=self.saga_id)

        steps = [
            SagaStep(
                name="step1",
                forward_action=self._create_success_action("step1", {"value1": 1}),
                compensation_action=self._create_compensation_action("step1"),
            ),
            SagaStep(
                name="step2",
                forward_action=self._create_success_action("step2", {"value2": 2}),
                compensation_action=self._create_compensation_action("step2"),
            ),
            SagaStep(
                name="step3_fail",
                forward_action=self._create_failure_action("step3_fail", "Step 3 failed"),
                compensation_action=self._create_compensation_action("step3_fail"),
            ),
        ]

        with self.assertRaises(SagaExecutionError) as cm:
            orchestrator.execute(steps)

        # Verify execution stopped at step3
        self.assertEqual(orchestrator.get_status(), SagaStatus.COMPENSATED)
        self.assertIn("step3_fail", str(cm.exception))

        # Verify steps 1, 2, and 3 executed
        self.assertEqual(len(self.execution_log), 3)
        self.assertEqual(self.execution_log[0]["step"], "step1")
        self.assertEqual(self.execution_log[1]["step"], "step2")
        self.assertEqual(self.execution_log[2]["step"], "step3_fail")

        # Verify compensation executed for steps 1 and 2 (in reverse order)
        self.assertEqual(len(self.compensation_log), 2)
        self.assertEqual(self.compensation_log[0]["step"], "step2")  # Compensated in reverse
        self.assertEqual(self.compensation_log[1]["step"], "step1")

        # Verify context
        context = orchestrator.get_context()
        self.assertEqual(len(context.step_results), 3)
        self.assertTrue(context.step_results[0][1].success)  # step1 succeeded
        self.assertTrue(context.step_results[1][1].success)  # step2 succeeded
        self.assertFalse(context.step_results[2][1].success)  # step3 failed

    def test_saga_execution_first_step_failure(self):
        """Test saga execution when first step fails"""
        orchestrator = SagaOrchestrator(saga_id=self.saga_id)

        steps = [
            SagaStep(
                name="step1_fail",
                forward_action=self._create_failure_action("step1_fail", "First step failed"),
                compensation_action=self._create_compensation_action("step1_fail"),
            ),
            SagaStep(
                name="step2",
                forward_action=self._create_success_action("step2"),
                compensation_action=self._create_compensation_action("step2"),
            ),
        ]

        with self.assertRaises(SagaExecutionError):
            orchestrator.execute(steps)

        # Verify only step1 executed
        self.assertEqual(len(self.execution_log), 1)
        self.assertEqual(self.execution_log[0]["step"], "step1_fail")

        # Verify no compensation (no previous steps to compensate)
        self.assertEqual(len(self.compensation_log), 0)

    def test_saga_execution_without_compensation(self):
        """Test saga execution with steps that have no compensation"""
        # Reset logs for this test
        self.execution_log = []
        self.compensation_log = []

        orchestrator = SagaOrchestrator(saga_id=self.saga_id)

        steps = [
            SagaStep(
                name="step1",
                forward_action=self._create_success_action("step1"),
                compensation_action=None,  # No compensation
            ),
            SagaStep(
                name="step2",
                forward_action=self._create_success_action("step2"),
                compensation_action=self._create_compensation_action("step2"),
            ),
            SagaStep(
                name="step3_fail",
                forward_action=self._create_failure_action("step3_fail"),
                compensation_action=None,
            ),
        ]

        with self.assertRaises(SagaExecutionError):
            orchestrator.execute(steps)

        # Verify compensation skipped for step1 (no compensation action)
        # But step2 should be compensated
        self.assertEqual(len(self.compensation_log), 1)
        self.assertEqual(self.compensation_log[0]["step"], "step2")

    def test_saga_execution_with_compensation_failure(self):
        """Test saga execution when compensation fails"""
        orchestrator = SagaOrchestrator(saga_id=self.saga_id)

        def failing_compensation(input_data: dict) -> SagaStepResult:
            return SagaStepResult.failure_result(error="Compensation failed")

        steps = [
            SagaStep(
                name="step1",
                forward_action=self._create_success_action("step1"),
                compensation_action=failing_compensation,
            ),
            SagaStep(
                name="step2_fail",
                forward_action=self._create_failure_action("step2_fail"),
                compensation_action=None,
            ),
        ]

        with self.assertRaises(SagaCompensationError) as cm:
            with self.assertRaises(SagaExecutionError):
                orchestrator.execute(steps)

        # Verify compensation was attempted but failed
        self.assertEqual(orchestrator.get_status(), SagaStatus.COMPENSATION_FAILED)
        self.assertIn("Compensation failed", str(cm.exception))

    def test_saga_execution_with_exception(self):
        """Test saga execution when step raises exception"""
        orchestrator = SagaOrchestrator(saga_id=self.saga_id)

        def exception_action(input_data: dict) -> SagaStepResult:
            raise ValueError("Unexpected exception")

        steps = [
            SagaStep(
                name="step1",
                forward_action=self._create_success_action("step1"),
                compensation_action=self._create_compensation_action("step1"),
            ),
            SagaStep(
                name="step2_exception",
                forward_action=exception_action,
                compensation_action=self._create_compensation_action("step2_exception"),
            ),
        ]

        with self.assertRaises(SagaExecutionError) as cm:
            orchestrator.execute(steps)

        # Verify exception was caught and compensation executed
        self.assertEqual(orchestrator.get_status(), SagaStatus.COMPENSATED)
        self.assertIn("Unexpected exception", str(cm.exception))
        self.assertEqual(len(self.compensation_log), 1)

    def test_saga_state_propagation(self):
        """Test that state propagates correctly between steps"""
        orchestrator = SagaOrchestrator(saga_id=self.saga_id)

        def step1_action(input_data: dict) -> SagaStepResult:
            return SagaStepResult.success_result(output={"step1_output": "value1"})

        def step2_action(input_data: dict) -> SagaStepResult:
            # Verify step1 output is in input
            self.assertIn("step1_output", input_data)
            self.assertEqual(input_data["step1_output"], "value1")
            return SagaStepResult.success_result(output={"step2_output": "value2"})

        def step3_action(input_data: dict) -> SagaStepResult:
            # Verify both previous outputs are in input
            self.assertIn("step1_output", input_data)
            self.assertIn("step2_output", input_data)
            return SagaStepResult.success_result(output={"step3_output": "value3"})

        steps = [
            SagaStep(name="step1", forward_action=step1_action),
            SagaStep(name="step2", forward_action=step2_action),
            SagaStep(name="step3", forward_action=step3_action),
        ]

        context = orchestrator.execute(steps, initial_state={"initial": "data"})

        # Verify final state contains all outputs
        self.assertIn("initial", context.state)
        self.assertIn("step1_output", context.state)
        self.assertIn("step2_output", context.state)
        self.assertIn("step3_output", context.state)

    def test_saga_step_input_data(self):
        """Test saga step with custom input data"""
        # Reset logs for this test
        self.execution_log = []
        self.compensation_log = []

        orchestrator = SagaOrchestrator(saga_id=self.saga_id)

        def step_action(input_data: dict) -> SagaStepResult:
            # Verify step-specific input is present
            self.assertIn("step_specific", input_data)
            self.assertEqual(input_data["step_specific"], "custom_value")
            # Log the input for verification
            self.execution_log.append(
                {
                    "step": "step1",
                    "action": "forward",
                    "input": input_data.copy(),
                    "timestamp": timezone.now(),
                }
            )
            return SagaStepResult.success_result()

        steps = [
            SagaStep(
                name="step1",
                forward_action=step_action,
                input_data={"step_specific": "custom_value"},
            )
        ]

        orchestrator.execute(steps, initial_state={"shared": "data"})

        # Verify step received both shared state and step-specific input
        self.assertEqual(len(self.execution_log), 1)
        self.assertIn("shared", self.execution_log[0]["input"])
        self.assertIn("step_specific", self.execution_log[0]["input"])

    def test_saga_empty_steps_list(self):
        """Test saga execution with empty steps list"""
        orchestrator = SagaOrchestrator(saga_id=self.saga_id)

        with self.assertRaises(ValueError) as cm:
            orchestrator.execute([])

        self.assertIn("cannot be empty", str(cm.exception))

    def test_saga_context_tracking(self):
        """Test saga context tracking"""
        orchestrator = SagaOrchestrator(saga_id=self.saga_id)

        steps = [
            SagaStep(
                name="step1",
                forward_action=self._create_success_action("step1"),
                compensation_action=self._create_compensation_action("step1"),
            ),
            SagaStep(
                name="step2",
                forward_action=self._create_success_action("step2"),
                compensation_action=self._create_compensation_action("step2"),
            ),
        ]

        context = orchestrator.execute(steps)

        # Verify context tracking
        self.assertEqual(context.saga_id, self.saga_id)
        self.assertIsNotNone(context.started_at)
        self.assertIsNotNone(context.completed_at)
        self.assertEqual(len(context.get_completed_steps()), 2)
        self.assertIsNone(context.get_failed_step())

        # Verify step results
        self.assertEqual(len(context.step_results), 2)
        self.assertEqual(context.step_results[0][0].name, "step1")
        self.assertEqual(context.step_results[1][0].name, "step2")

    def test_saga_context_failed_step_tracking(self):
        """Test saga context tracks failed step"""
        orchestrator = SagaOrchestrator(saga_id=self.saga_id)

        steps = [
            SagaStep(
                name="step1",
                forward_action=self._create_success_action("step1"),
                compensation_action=self._create_compensation_action("step1"),
            ),
            SagaStep(
                name="step2_fail",
                forward_action=self._create_failure_action("step2_fail"),
                compensation_action=None,
            ),
        ]

        with self.assertRaises(SagaExecutionError):
            orchestrator.execute(steps)

        context = orchestrator.get_context()
        failed_step = context.get_failed_step()

        self.assertIsNotNone(failed_step)
        self.assertEqual(failed_step[0].name, "step2_fail")
        self.assertFalse(failed_step[1].success)

    def test_saga_orchestrator_id(self):
        """Test saga orchestrator ID generation"""
        # Without ID
        orchestrator1 = SagaOrchestrator()
        self.assertIsNotNone(orchestrator1.saga_id)
        self.assertIsInstance(orchestrator1.saga_id, str)

        # With ID
        custom_id = str(uuid.uuid4())
        orchestrator2 = SagaOrchestrator(saga_id=custom_id)
        self.assertEqual(orchestrator2.saga_id, custom_id)

    def test_saga_status_transitions(self):
        """Test saga status transitions"""
        orchestrator = SagaOrchestrator(saga_id=self.saga_id)

        # Initial status
        self.assertEqual(orchestrator.get_status(), SagaStatus.PENDING)

        # Successful execution
        steps = [SagaStep(name="step1", forward_action=self._create_success_action("step1"))]

        orchestrator.execute(steps)
        self.assertEqual(orchestrator.get_status(), SagaStatus.COMPLETED)

        # Failed execution with compensation
        orchestrator2 = SagaOrchestrator(saga_id=str(uuid.uuid4()))
        steps2 = [
            SagaStep(
                name="step1",
                forward_action=self._create_success_action("step1"),
                compensation_action=self._create_compensation_action("step1"),
            ),
            SagaStep(name="step2_fail", forward_action=self._create_failure_action("step2_fail")),
        ]

        with self.assertRaises(SagaExecutionError):
            orchestrator2.execute(steps2)

        self.assertEqual(orchestrator2.get_status(), SagaStatus.COMPENSATED)
