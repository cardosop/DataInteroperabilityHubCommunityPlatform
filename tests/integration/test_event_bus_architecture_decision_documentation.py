"""
Event Bus Architecture Decision Documentation Validation Tests

Comprehensive tests to validate that openspec/changes/odps1/design.md Decision 13
accurately documents the Event Bus Architecture decision with all required sections.

All tests validate against real documentation - no mocks or stubs.
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Set
from django.test import TestCase
import structlog

logger = structlog.get_logger(__name__)


class EventBusArchitectureDecisionDocumentationTest(TestCase):
    """Test that Decision 13: Event Bus Architecture in design.md is complete and accurate"""

    def setUp(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).parent.parent.parent
        self.openspec_path = self.project_root / "openspec" / "changes" / "odps1"
        self.design_doc = self.openspec_path / "design.md"
        self.docs_path = self.project_root / "docs"

    def test_design_documentation_exists(self):
        """Test that design.md exists"""
        self.assertTrue(
            self.design_doc.exists(),
            f"design.md not found at {self.design_doc}"
        )

    def test_design_documentation_is_readable(self):
        """Test that design.md is readable"""
        content = self.design_doc.read_text()
        self.assertGreater(len(content), 0, "design.md is empty")

    def test_decision_13_exists(self):
        """Test that Decision 13: Event Bus Architecture exists"""
        content = self.design_doc.read_text()

        # Check for Decision 13 header
        self.assertIn("Decision 13: Event Bus Architecture", content,
                      "Decision 13: Event Bus Architecture not found")

    def test_current_architecture_section_exists(self):
        """Test that Current Architecture: Redis Pub/Sub + PostgreSQL Pattern section exists"""
        content = self.design_doc.read_text()

        # Check for Current Architecture section
        self.assertIn("Current Architecture: Redis Pub/Sub + PostgreSQL Pattern", content,
                      "Current Architecture section not found")

        # Check for key subsections
        self.assertIn("Architecture Overview", content,
                      "Architecture Overview subsection not found")
        self.assertIn("Key Components", content,
                      "Key Components subsection not found")
        self.assertIn("Performance Characteristics", content,
                      "Performance Characteristics subsection not found")
        self.assertIn("Architecture Limitations", content,
                      "Architecture Limitations subsection not found")
        self.assertIn("Bottlenecks Identified", content,
                      "Bottlenecks Identified subsection not found")

    def test_current_architecture_components_documented(self):
        """Test that all key components are documented"""
        content = self.design_doc.read_text()

        # Check for EventBus component
        self.assertIn("EventBus", content,
                      "EventBus component not documented")
        self.assertIn("hub/apps/core/events/bus.py", content,
                      "EventBus file path not documented")

        # Check for Connection Pooling
        self.assertIn("Connection Pooling", content,
                      "Connection Pooling not documented")
        self.assertIn("REDIS_EVENTS_URL", content,
                      "REDIS_EVENTS_URL configuration not documented")

        # Check for Persistence Flow
        self.assertIn("Persistence Flow", content,
                      "Persistence Flow not documented")

    def test_performance_characteristics_documented(self):
        """Test that performance characteristics are documented"""
        content = self.design_doc.read_text()

        # Check for throughput
        self.assertIn("Throughput", content,
                      "Throughput not documented")
        self.assertIn("1,500-2,000 events/sec", content,
                      "Throughput value not documented")

        # Check for latency
        self.assertIn("Average Latency", content,
                      "Average Latency not documented")
        self.assertIn("<10ms", content,
                      "Pub/Sub latency not documented")
        self.assertIn("<100ms", content,
                      "Persistence latency not documented")

        # Check for error rate
        self.assertIn("Error Rate", content,
                      "Error Rate not documented")

    def test_architecture_limitations_documented(self):
        """Test that architecture limitations are documented"""
        content = self.design_doc.read_text()

        # Check for key limitations
        self.assertIn("Synchronous Persistence", content,
                      "Synchronous Persistence limitation not documented")
        self.assertIn("Single Redis Instance", content,
                      "Single Redis Instance limitation not documented")
        self.assertIn("No Message Ordering Guarantees", content,
                      "Message ordering limitation not documented")
        self.assertIn("No Backpressure Mechanism", content,
                      "Backpressure limitation not documented")
        self.assertIn("Limited Replay Capabilities", content,
                      "Replay limitation not documented")
        self.assertIn("No Consumer Groups", content,
                      "Consumer groups limitation not documented")

    def test_bottlenecks_documented(self):
        """Test that bottlenecks are documented"""
        content = self.design_doc.read_text()

        # Check for primary bottleneck
        self.assertIn("PostgreSQL Persistence", content,
                      "PostgreSQL Persistence bottleneck not documented")
        self.assertIn("Primary Bottleneck", content,
                      "Primary bottleneck not identified")

        # Check for secondary bottleneck
        self.assertIn("Event Validation", content,
                      "Event Validation bottleneck not documented")
        self.assertIn("Secondary Bottleneck", content,
                      "Secondary bottleneck not identified")

    def test_evaluation_process_section_exists(self):
        """Test that Evaluation Process (Phase 9.7.1.1) section exists"""
        content = self.design_doc.read_text()

        # Check for Evaluation Process section
        self.assertIn("Evaluation Process (Phase 9.7.1.1)", content,
                      "Evaluation Process section not found")

        # Check for all four phases
        self.assertIn("Phase 9.7.1.1.1: Evaluate Current Event Bus Implementation", content,
                      "Phase 9.7.1.1.1 not documented")
        self.assertIn("Phase 9.7.1.1.2: Evaluate Redis Streams as Alternative", content,
                      "Phase 9.7.1.1.2 not documented")
        self.assertIn("Phase 9.7.1.1.3: Evaluate Kafka/RabbitMQ as Alternative", content,
                      "Phase 9.7.1.1.3 not documented")
        self.assertIn("Phase 9.7.1.1.4: Make Architecture Decision", content,
                      "Phase 9.7.1.1.4 not documented")

    def test_evaluation_phase_details_documented(self):
        """Test that each evaluation phase has required details"""
        content = self.design_doc.read_text()

        # Check for Objective, Activities, Test Results, Key Findings in phases 1-3
        phases_with_test_results = [
            "Phase 9.7.1.1.1",
            "Phase 9.7.1.1.2",
            "Phase 9.7.1.1.3"
        ]

        for phase in phases_with_test_results:
            # Find the phase section
            phase_start = content.find(phase)
            if phase_start != -1:
                # Get next 2000 characters (should contain the phase details)
                phase_section = content[phase_start:phase_start + 2000]

                # Check for required subsections
                self.assertIn("Objective", phase_section,
                             f"Objective not found in {phase}")
                self.assertIn("Activities", phase_section,
                             f"Activities not found in {phase}")
                self.assertIn("Test Results", phase_section,
                             f"Test Results not found in {phase}")
                self.assertIn("Key Findings", phase_section,
                             f"Key Findings not found in {phase}")

        # Phase 9.7.1.1.4 has Decision instead of Test Results
        phase_4_start = content.find("Phase 9.7.1.1.4")
        if phase_4_start != -1:
            phase_4_section = content[phase_4_start:phase_4_start + 2000]
            self.assertIn("Objective", phase_4_section,
                         "Objective not found in Phase 9.7.1.1.4")
            self.assertIn("Activities", phase_4_section,
                         "Activities not found in Phase 9.7.1.1.4")
            self.assertIn("Decision", phase_4_section,
                         "Decision not found in Phase 9.7.1.1.4")
            self.assertIn("Comprehensive Comparison", phase_4_section,
                         "Comprehensive Comparison not found in Phase 9.7.1.1.4")

    def test_decision_criteria_section_exists(self):
        """Test that Decision Criteria section exists"""
        content = self.design_doc.read_text()

        # Check for Decision Criteria section
        self.assertIn("Decision Criteria", content,
                      "Decision Criteria section not found")

        # Check for scoring methodology
        self.assertIn("Scoring Criteria", content,
                      "Scoring Criteria not documented")
        self.assertIn("1-5 scale", content,
                      "Scoring scale not documented")

        # Check for decision factors
        self.assertIn("Performance", content,
                      "Performance factor not documented")
        self.assertIn("Scalability", content,
                      "Scalability factor not documented")
        self.assertIn("Complexity", content,
                      "Complexity factor not documented")
        self.assertIn("Infrastructure", content,
                      "Infrastructure factor not documented")
        self.assertIn("Operations", content,
                      "Operations factor not documented")

    def test_decision_matrix_exists(self):
        """Test that decision matrix with scores exists"""
        content = self.design_doc.read_text()

        # Check for decision matrix table
        self.assertIn("Decision Matrix Scoring", content,
                      "Decision Matrix Scoring not found")

        # Check for all options
        self.assertIn("Redis Pub/Sub", content,
                      "Redis Pub/Sub not in decision matrix")
        self.assertIn("Redis Streams", content,
                      "Redis Streams not in decision matrix")
        self.assertIn("Kafka", content,
                      "Kafka not in decision matrix")
        self.assertIn("RabbitMQ", content,
                      "RabbitMQ not in decision matrix")

        # Check for overall score
        self.assertIn("Overall Score", content,
                      "Overall Score not documented")
        self.assertIn("4.15", content,
                      "Redis Pub/Sub score not documented")

    def test_chosen_solution_section_exists(self):
        """Test that Chosen Solution section exists"""
        content = self.design_doc.read_text()

        # Check for Chosen Solution section
        self.assertIn("Chosen Solution (from Phase 9.7.1.1.4)", content,
                      "Chosen Solution section not found")

        # Check for primary decision
        self.assertIn("Primary Decision", content,
                      "Primary Decision not documented")

        # Check for rationale
        self.assertIn("Rationale", content,
                      "Rationale not documented")

        # Check for current state assessment
        self.assertIn("Current State Assessment", content,
                      "Current State Assessment not documented")

        # Check for decision factors
        self.assertIn("Decision Factors", content,
                      "Decision Factors not documented")

    def test_migration_approach_section_exists(self):
        """Test that Migration Approach section exists"""
        content = self.design_doc.read_text()

        # Check for Migration Approach section
        self.assertIn("Migration Approach", content,
                      "Migration Approach section not found")

        # Check for migration phases
        self.assertIn("Phase 1:", content,
                      "Migration Phase 1 not documented")
        self.assertIn("Phase 2:", content,
                      "Migration Phase 2 not documented")
        self.assertIn("Phase 3:", content,
                      "Migration Phase 3 not documented")
        self.assertIn("Phase 4:", content,
                      "Migration Phase 4 not documented")

    def test_migration_steps_documented(self):
        """Test that migration steps are documented"""
        content = self.design_doc.read_text()

        # Find Migration Approach section first
        migration_approach_start = content.find("#### Migration Approach")
        self.assertNotEqual(migration_approach_start, -1,
                           "Migration Approach section not found")

        # Find Phase 3: Migration (Redis Streams) within Migration Approach section
        # Look for Phase 3 after Migration Approach section
        phase_3_search_start = migration_approach_start
        phase_3_start = content.find("**Phase 3: Migration (Redis Streams)**", phase_3_search_start)
        self.assertNotEqual(phase_3_start, -1,
                           "Phase 3: Migration (Redis Streams) not found in Migration Approach section")

        if phase_3_start != -1:
            # Get section from Phase 3 to end of Migration Approach (or next major section)
            phase_3_section = content[phase_3_start:phase_3_start + 3000]

            # Check for migration steps
            self.assertIn("Migration Steps", phase_3_section,
                         "Migration Steps not documented in Phase 3")
            self.assertIn("Deploy Streams Implementation", phase_3_section,
                         "Deploy Streams step not documented")
            self.assertIn("Migrate Publishers", phase_3_section,
                         "Migrate Publishers step not documented")
            self.assertIn("Migrate Subscribers", phase_3_section,
                         "Migrate Subscribers step not documented")
            self.assertIn("Validation", phase_3_section,
                         "Validation step not documented")
            self.assertIn("Completion", phase_3_section,
                         "Completion step not documented")

    def test_migration_effort_estimates_documented(self):
        """Test that migration effort estimates are documented"""
        content = self.design_doc.read_text()

        # Check for effort estimates
        self.assertIn("Estimated Effort", content,
                      "Estimated Effort not documented")
        self.assertIn("10-20 hours", content,
                      "Migration effort estimate not documented")

    def test_success_criteria_documented(self):
        """Test that success criteria are documented"""
        content = self.design_doc.read_text()

        # Check for success criteria
        self.assertIn("Success Criteria", content,
                      "Success Criteria not documented")

        # Check for specific criteria
        self.assertIn("Throughput", content,
                      "Throughput success criteria not documented")
        self.assertIn("Latency", content,
                      "Latency success criteria not documented")
        self.assertIn("No functionality regression", content,
                      "Functionality regression criteria not documented")

    def test_risk_mitigation_documented(self):
        """Test that risk mitigation strategies are documented"""
        content = self.design_doc.read_text()

        # Check for risks and mitigations
        self.assertIn("Risks & Mitigations", content,
                      "Risks & Mitigations section not found")

        # Check for specific risks
        self.assertIn("Scalability limitations", content,
                      "Scalability risk not documented")
        self.assertIn("Missing features", content,
                      "Missing features risk not documented")
        self.assertIn("Performance bottlenecks", content,
                      "Performance bottlenecks risk not documented")

    def test_cross_references_to_detailed_docs(self):
        """Test that cross-references to detailed documentation exist"""
        content = self.design_doc.read_text()

        # Check for references to detailed documentation
        self.assertIn("docs/EVENT_BUS_ARCHITECTURE_DECISION.md", content,
                      "Reference to EVENT_BUS_ARCHITECTURE_DECISION.md not found")
        self.assertIn("docs/EVENT_BUS_PERFORMANCE_ANALYSIS.md", content,
                      "Reference to EVENT_BUS_PERFORMANCE_ANALYSIS.md not found")
        self.assertIn("docs/REDIS_STREAMS_EVALUATION.md", content,
                      "Reference to REDIS_STREAMS_EVALUATION.md not found")
        self.assertIn("docs/KAFKA_RABBITMQ_EVALUATION.md", content,
                      "Reference to KAFKA_RABBITMQ_EVALUATION.md not found")

    def test_referenced_docs_exist(self):
        """Test that referenced documentation files exist"""
        content = self.design_doc.read_text()

        # Extract referenced doc paths
        doc_pattern = r'docs/([A-Z_]+\.md)'
        referenced_docs = re.findall(doc_pattern, content)

        for doc_name in referenced_docs:
            doc_path = self.docs_path / doc_name
            self.assertTrue(
                doc_path.exists(),
                f"Referenced documentation file not found: {doc_path}"
            )

    def test_decision_date_documented(self):
        """Test that decision date is documented"""
        content = self.design_doc.read_text()

        # Check for decision date
        self.assertIn("Decision Date", content,
                      "Decision Date not documented")
        self.assertIn("2025-12-30", content,
                      "Decision date not documented")

    def test_review_date_documented(self):
        """Test that review date is documented"""
        content = self.design_doc.read_text()

        # Check for review date
        self.assertIn("Review Date", content,
                      "Review Date not documented")
        self.assertIn("2025-06-30", content,
                      "Review date not documented")

    def test_markdown_formatting_valid(self):
        """Test that markdown formatting is valid"""
        content = self.design_doc.read_text()

        # Check for proper heading hierarchy
        # Decision 13 should use ### (level 3)
        decision_13_match = re.search(r'### Decision 13:', content)
        self.assertIsNotNone(decision_13_match,
                             "Decision 13 should use ### heading level")

        # Subsections should use #### (level 4)
        subsection_matches = re.findall(r'#### (Current Architecture|Evaluation Process|Decision Criteria|Chosen Solution|Migration Approach)', content)
        self.assertGreater(len(subsection_matches), 0,
                          "Subsections should use #### heading level")

    def test_no_broken_references(self):
        """Test that there are no obviously broken references"""
        content = self.design_doc.read_text()

        # Check for markdown link syntax
        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        links = re.findall(link_pattern, content)

        broken_links = []
        for link_text, link_path in links:
            # Skip external links
            if link_path.startswith('http'):
                continue

            # Check for file references
            if link_path.startswith('docs/'):
                doc_file = self.docs_path / link_path.replace('docs/', '')
                if not doc_file.exists():
                    broken_links.append(f"{link_text} -> {link_path}")

        self.assertEqual(len(broken_links), 0,
                         f"Broken references found: {broken_links}")

