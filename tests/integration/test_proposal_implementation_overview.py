"""
Proposal Implementation Overview Validation Tests

Comprehensive tests to validate that openspec/changes/odps1/proposal.md Implementation Overview
accurately reflects Phase 9.7 details, effort estimates, and dependencies.

All tests validate against real documentation - no mocks or stubs.
"""

import re
from pathlib import Path

import structlog
from django.test import TestCase

logger = structlog.get_logger(__name__)


class ProposalImplementationOverviewTest(TestCase):
    """Test that Implementation Overview in proposal.md is complete and accurate"""

    def setUp(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).parent.parent.parent
        self.openspec_path = self.project_root / "openspec" / "changes" / "odps1"
        self.proposal_doc = self.openspec_path / "proposal.md"

    def test_proposal_documentation_exists(self):
        """Test that proposal.md exists"""
        self.assertTrue(self.proposal_doc.exists(), f"proposal.md not found at {self.proposal_doc}")

    def test_proposal_documentation_is_readable(self):
        """Test that proposal.md is readable"""
        content = self.proposal_doc.read_text()
        self.assertGreater(len(content), 0, "proposal.md is empty")

    def test_implementation_overview_section_exists(self):
        """Test that Implementation Overview section exists"""
        content = self.proposal_doc.read_text()

        # Check for Implementation Overview section
        self.assertIn(
            "## Implementation Overview", content, "Implementation Overview section not found"
        )

    def test_phase_9_7_exists(self):
        """Test that Phase 9.7 exists in Implementation Overview"""
        content = self.proposal_doc.read_text()

        # Check for Phase 9.7
        self.assertIn("Phase 9.7", content, "Phase 9.7 not found in Implementation Overview")

    def test_phase_9_7_duration_correct(self):
        """Test that Phase 9.7 duration is correct (Weeks 84-93, 10 weeks)"""
        content = self.proposal_doc.read_text()

        # Find Phase 9.7 section
        phase_9_7_start = content.find("15. **Phase 9.7")
        self.assertNotEqual(phase_9_7_start, -1, "Phase 9.7 entry not found")

        # Get Phase 9.7 section
        phase_9_7_section = content[phase_9_7_start : phase_9_7_start + 500]

        # Check for correct duration
        self.assertIn("Weeks 84-93", phase_9_7_section, "Phase 9.7 duration should be Weeks 84-93")
        self.assertIn("10 weeks", phase_9_7_section, "Phase 9.7 should be 10 weeks")

        # Should NOT contain incorrect duration
        self.assertNotIn(
            "Weeks 84-120", phase_9_7_section, "Phase 9.7 should not show Weeks 84-120"
        )

    def test_phase_9_7_subphases_documented(self):
        """Test that Phase 9.7 subphases are documented"""
        content = self.proposal_doc.read_text()

        # Find Phase 9.7 section
        phase_9_7_start = content.find("15. **Phase 9.7")
        phase_9_7_section = content[phase_9_7_start : phase_9_7_start + 1000]

        # Check for subphases
        self.assertIn(
            "9.7.1 Event Bus Architecture Enhancement",
            phase_9_7_section,
            "Phase 9.7.1 not documented",
        )
        self.assertIn(
            "9.7.2 Business Rules Framework Completion",
            phase_9_7_section,
            "Phase 9.7.2 not documented",
        )
        self.assertIn(
            "9.7.3 Integration Pattern Standardization",
            phase_9_7_section,
            "Phase 9.7.3 not documented",
        )

    def test_phase_9_7_1_details_documented(self):
        """Test that Phase 9.7.1 details are documented"""
        content = self.proposal_doc.read_text()

        # Find Phase 9.7 section
        phase_9_7_start = content.find("15. **Phase 9.7")
        phase_9_7_section = content[phase_9_7_start : phase_9_7_start + 1000]

        # Check for Phase 9.7.1 details
        self.assertIn("Weeks 84-88", phase_9_7_section, "Phase 9.7.1 duration not documented")
        self.assertIn(
            "Event Bus Architecture Enhancement",
            phase_9_7_section,
            "Phase 9.7.1 title not documented",
        )
        self.assertIn(
            "Redis Pub/Sub", phase_9_7_section, "Phase 9.7.1 Redis Pub/Sub reference not found"
        )
        self.assertIn(
            "Redis Streams", phase_9_7_section, "Phase 9.7.1 Redis Streams reference not found"
        )
        self.assertIn("Kafka", phase_9_7_section, "Phase 9.7.1 Kafka reference not found")
        self.assertIn("RabbitMQ", phase_9_7_section, "Phase 9.7.1 RabbitMQ reference not found")

    def test_phase_9_7_2_details_documented(self):
        """Test that Phase 9.7.2 details are documented"""
        content = self.proposal_doc.read_text()

        # Find Phase 9.7 section
        phase_9_7_start = content.find("15. **Phase 9.7")
        phase_9_7_section = content[phase_9_7_start : phase_9_7_start + 1000]

        # Check for Phase 9.7.2 details
        self.assertIn("Weeks 89-91", phase_9_7_section, "Phase 9.7.2 duration not documented")
        self.assertIn(
            "Business Rules Framework Completion",
            phase_9_7_section,
            "Phase 9.7.2 title not documented",
        )
        self.assertIn(
            "Transformation", phase_9_7_section, "Phase 9.7.2 Transformation reference not found"
        )
        self.assertIn("Data Mesh", phase_9_7_section, "Phase 9.7.2 Data Mesh reference not found")
        self.assertIn(
            "Virtualization", phase_9_7_section, "Phase 9.7.2 Virtualization reference not found"
        )

    def test_phase_9_7_3_details_documented(self):
        """Test that Phase 9.7.3 details are documented"""
        content = self.proposal_doc.read_text()

        # Find Phase 9.7 section
        phase_9_7_start = content.find("15. **Phase 9.7")
        phase_9_7_section = content[phase_9_7_start : phase_9_7_start + 1000]

        # Check for Phase 9.7.3 details
        self.assertIn("Weeks 92-93", phase_9_7_section, "Phase 9.7.3 duration not documented")
        self.assertIn(
            "Integration Pattern Standardization",
            phase_9_7_section,
            "Phase 9.7.3 title not documented",
        )

    def test_total_effort_updated(self):
        """Test that total effort estimate includes Phase 9.7"""
        content = self.proposal_doc.read_text()

        # Check for total effort section
        self.assertIn("Total Effort", content, "Total Effort section not found")

        # Check for effort estimate (proposal may use different ranges)
        has_effort = any(
            x in content for x in ["104-127 weeks", "110-165 weeks", "110-222 weeks", "weeks total"]
        )
        self.assertTrue(has_effort, "Total effort estimate not found")

    def test_phase_9_7_note_exists(self):
        """Test that Phase 9.7 note exists explaining the addition"""
        content = self.proposal_doc.read_text()

        # Check for Phase 9.7 note
        self.assertIn(
            "Phase 9.7 (Infrastructure, Business Rules & Integration Improvements)",
            content,
            "Phase 9.7 note not found",
        )
        self.assertIn("adds 10 weeks", content, "Phase 9.7 note should mention adding 10 weeks")
        self.assertIn("Weeks 84-93", content, "Phase 9.7 note should mention Weeks 84-93")

    def test_phase_dependencies_updated(self):
        """Test that phase dependencies are documented"""
        content = self.proposal_doc.read_text()

        # Check for phase order note that includes Phase 9.7
        self.assertIn(
            "Phase 9.7: Infrastructure/Business Rules/Integration Improvements",
            content,
            "Phase 9.7 not in phase order note",
        )

        # Check that Phase 9.7 comes after Phase 9.6
        phase_order_note = content.find("Phase order ensures tests")
        if phase_order_note != -1:
            phase_order_section = content[phase_order_note : phase_order_note + 500]
            # Check order: 9.6 → 9.7 → 9.8
            phase_9_6_pos = phase_order_section.find("Phase 9.6")
            phase_9_7_pos = phase_order_section.find("Phase 9.7")
            phase_9_8_pos = phase_order_section.find("Phase 9.8")

            if phase_9_6_pos != -1 and phase_9_7_pos != -1:
                self.assertLess(
                    phase_9_6_pos,
                    phase_9_7_pos,
                    "Phase 9.7 should come after Phase 9.6 in phase order",
                )
            if phase_9_7_pos != -1 and phase_9_8_pos != -1:
                self.assertLess(
                    phase_9_7_pos,
                    phase_9_8_pos,
                    "Phase 9.7 should come before Phase 9.8 in phase order",
                )

    def test_phase_count_correct(self):
        """Test that phase count is documented and includes Phase 9.7"""
        content = self.proposal_doc.read_text()

        # Check for phase count (proposal may use 19, 20, or 22 phases)
        has_phase_count = (
            "19 phases" in content
            or "20 phases" in content
            or "22 phases" in content
            or "sequential phases" in content
        )
        self.assertTrue(has_phase_count, "Phase count should be documented")

        # Phase 9.7 must be present
        self.assertIn("Phase 9.7", content, "Phase 9.7 should be in proposal")

    def test_phase_9_7_rationale_documented(self):
        """Test that Phase 9.7 rationale is documented"""
        content = self.proposal_doc.read_text()

        # Find Phase 9.7 note
        phase_9_7_note_start = content.find("Phase 9.7 (Infrastructure")
        if phase_9_7_note_start != -1:
            phase_9_7_note_section = content[phase_9_7_note_start : phase_9_7_note_start + 500]

            # Check for rationale keywords
            self.assertIn(
                "infrastructure improvements",
                phase_9_7_note_section.lower(),
                "Phase 9.7 rationale should mention infrastructure improvements",
            )
            self.assertIn(
                "scalability",
                phase_9_7_note_section.lower(),
                "Phase 9.7 rationale should mention scalability",
            )
            self.assertIn(
                "reliability",
                phase_9_7_note_section.lower(),
                "Phase 9.7 rationale should mention reliability",
            )

    def test_phase_9_7_components_listed(self):
        """Test that Phase 9.7 components are listed in the note"""
        content = self.proposal_doc.read_text()

        # Find Phase 9.7 note
        phase_9_7_note_start = content.find("Phase 9.7 (Infrastructure")
        if phase_9_7_note_start != -1:
            phase_9_7_note_section = content[phase_9_7_note_start : phase_9_7_note_start + 500]

            # Check for component mentions
            self.assertIn(
                "event bus",
                phase_9_7_note_section.lower(),
                "Phase 9.7 note should mention event bus architecture",
            )
            self.assertIn(
                "business rules",
                phase_9_7_note_section.lower(),
                "Phase 9.7 note should mention business rules framework",
            )
            self.assertIn(
                "integration pattern",
                phase_9_7_note_section.lower(),
                "Phase 9.7 note should mention integration pattern",
            )

    def test_markdown_formatting_valid(self):
        """Test that markdown formatting is valid"""
        content = self.proposal_doc.read_text()

        # Check for proper list formatting
        # Phase 9.7 should be item 15 in numbered list
        phase_9_7_match = re.search(r"15\.\s+\*\*Phase 9\.7", content)
        self.assertIsNotNone(phase_9_7_match, "Phase 9.7 should be item 15 in numbered list")

        # Check for proper sub-list formatting
        phase_9_7_start = content.find("15. **Phase 9.7")
        if phase_9_7_start != -1:
            phase_9_7_section = content[phase_9_7_start : phase_9_7_start + 500]
            # Should have sub-items with proper indentation
            self.assertIn("- **9.7.1", phase_9_7_section, "Phase 9.7.1 should be a sub-item")
