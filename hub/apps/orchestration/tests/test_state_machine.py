"""
Unit tests for workflow state machine.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError

from hub.apps.orchestration.state_machine import WorkflowStateMachine
from hub.apps.orchestration.models import WorkflowStatus


class WorkflowStateMachineTest(TestCase):
    """Test workflow state machine"""
    
    def test_can_transition_draft_to_running(self):
        """Test DRAFT → RUNNING transition"""
        self.assertTrue(
            WorkflowStateMachine.can_transition(
                WorkflowStatus.DRAFT,
                WorkflowStatus.RUNNING
            )
        )
    
    def test_can_transition_running_to_completed(self):
        """Test RUNNING → COMPLETED transition"""
        self.assertTrue(
            WorkflowStateMachine.can_transition(
                WorkflowStatus.RUNNING,
                WorkflowStatus.COMPLETED
            )
        )
    
    def test_can_transition_running_to_failed(self):
        """Test RUNNING → FAILED transition"""
        self.assertTrue(
            WorkflowStateMachine.can_transition(
                WorkflowStatus.RUNNING,
                WorkflowStatus.FAILED
            )
        )
    
    def test_can_transition_running_to_rolling_back(self):
        """Test RUNNING → ROLLING_BACK transition"""
        self.assertTrue(
            WorkflowStateMachine.can_transition(
                WorkflowStatus.RUNNING,
                WorkflowStatus.ROLLING_BACK
            )
        )
    
    def test_cannot_transition_completed_to_running(self):
        """Test COMPLETED → RUNNING transition (invalid)"""
        self.assertFalse(
            WorkflowStateMachine.can_transition(
                WorkflowStatus.COMPLETED,
                WorkflowStatus.RUNNING
            )
        )
    
    def test_cannot_transition_draft_to_completed(self):
        """Test DRAFT → COMPLETED transition (invalid)"""
        self.assertFalse(
            WorkflowStateMachine.can_transition(
                WorkflowStatus.DRAFT,
                WorkflowStatus.COMPLETED
            )
        )
    
    def test_validate_transition_valid(self):
        """Test validate_transition with valid transition"""
        try:
            WorkflowStateMachine.validate_transition(
                WorkflowStatus.DRAFT,
                WorkflowStatus.RUNNING
            )
        except ValidationError:
            self.fail("validate_transition raised ValidationError for valid transition")
    
    def test_validate_transition_invalid(self):
        """Test validate_transition with invalid transition"""
        with self.assertRaises(ValidationError):
            WorkflowStateMachine.validate_transition(
                WorkflowStatus.COMPLETED,
                WorkflowStatus.RUNNING
            )
    
    def test_is_terminal_completed(self):
        """Test is_terminal for COMPLETED"""
        self.assertTrue(WorkflowStateMachine.is_terminal(WorkflowStatus.COMPLETED))
    
    def test_is_terminal_failed(self):
        """Test is_terminal for FAILED"""
        self.assertTrue(WorkflowStateMachine.is_terminal(WorkflowStatus.FAILED))
    
    def test_is_terminal_running(self):
        """Test is_terminal for RUNNING"""
        self.assertFalse(WorkflowStateMachine.is_terminal(WorkflowStatus.RUNNING))
    
    def test_get_valid_transitions_draft(self):
        """Test get_valid_transitions for DRAFT"""
        transitions = WorkflowStateMachine.get_valid_transitions(WorkflowStatus.DRAFT)
        self.assertIn(WorkflowStatus.RUNNING, transitions)
        self.assertIn(WorkflowStatus.CANCELLED, transitions)
    
    def test_get_valid_transitions_running(self):
        """Test get_valid_transitions for RUNNING"""
        transitions = WorkflowStateMachine.get_valid_transitions(WorkflowStatus.RUNNING)
        self.assertIn(WorkflowStatus.COMPLETED, transitions)
        self.assertIn(WorkflowStatus.FAILED, transitions)
        self.assertIn(WorkflowStatus.CANCELLED, transitions)
        self.assertIn(WorkflowStatus.PAUSED, transitions)
        self.assertIn(WorkflowStatus.ROLLING_BACK, transitions)

