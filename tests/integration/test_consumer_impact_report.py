"""
Tests for Consumer Impact Analysis Report

Tests verify:
1. Report completeness (all required sections present)
2. Report accuracy (data matches source analysis files)
3. Impact score calculations are correct
4. Priority classifications are accurate
"""
import json
import pytest
from pathlib import Path


class TestConsumerImpactReport:
    """Test consumer impact analysis report"""

    @pytest.fixture
    def report_path(self):
        """Path to the generated report"""
        return Path(__file__).parent.parent.parent / "docs" / "api-audit" / "consumer-impact-analysis.md"

    @pytest.fixture
    def report_data_path(self):
        """Path to the generated report data"""
        return Path(__file__).parent.parent.parent / "docs" / "api-audit" / "consumer-impact-analysis.json"

    @pytest.fixture
    def report_data(self, report_data_path):
        """Load report data"""
        if not report_data_path.exists():
            pytest.skip("Consumer impact report not found. Run scripts/generate_consumer_impact_report.py first.")

        with open(report_data_path, "r") as f:
            return json.load(f)

    def test_report_file_exists(self, report_path):
        """Test that report file exists"""
        assert report_path.exists(), f"Report file not found: {report_path}"

    def test_report_data_file_exists(self, report_data_path):
        """Test that report data file exists"""
        assert report_data_path.exists(), f"Report data file not found: {report_data_path}"

    def test_report_structure(self, report_data):
        """Test that report has required structure"""
        assert "summary" in report_data, "Report missing summary section"
        assert "impact_matrix" in report_data, "Report missing impact_matrix section"
        assert "consumers" in report_data, "Report missing consumers section"
        assert "endpoint_consumers" in report_data, "Report missing endpoint_consumers section"
        assert "report" in report_data, "Report missing markdown report"

    def test_summary_statistics(self, report_data):
        """Test that summary statistics are present and valid"""
        summary = report_data["summary"]

        assert "total_endpoints" in summary, "Summary missing total_endpoints"
        assert "total_consumers" in summary, "Summary missing total_consumers"
        assert "priority_counts" in summary, "Summary missing priority_counts"

        assert isinstance(summary["total_endpoints"], int), "total_endpoints must be integer"
        assert isinstance(summary["total_consumers"], int), "total_consumers must be integer"
        assert summary["total_endpoints"] > 0, "total_endpoints must be > 0"
        assert summary["total_consumers"] > 0, "total_consumers must be > 0"

        priority_counts = summary["priority_counts"]
        assert "CRITICAL" in priority_counts, "Missing CRITICAL priority count"
        assert "HIGH" in priority_counts, "Missing HIGH priority count"
        assert "MEDIUM" in priority_counts, "Missing MEDIUM priority count"
        assert "LOW" in priority_counts, "Missing LOW priority count"

        total_priority_endpoints = sum(priority_counts.values())
        assert total_priority_endpoints == summary["total_endpoints"], \
            f"Priority counts don't match total endpoints: {total_priority_endpoints} != {summary['total_endpoints']}"

    def test_impact_matrix_structure(self, report_data):
        """Test that impact matrix has correct structure"""
        impact_matrix = report_data["impact_matrix"]

        assert len(impact_matrix) > 0, "Impact matrix is empty"

        for endpoint, info in impact_matrix.items():
            assert "endpoint" in info, f"Missing endpoint in {endpoint}"
            assert "impact_score" in info, f"Missing impact_score in {endpoint}"
            assert "priority" in info, f"Missing priority in {endpoint}"
            assert "total_consumers" in info, f"Missing total_consumers in {endpoint}"
            assert "consumer_types" in info, f"Missing consumer_types in {endpoint}"
            assert "consumers" in info, f"Missing consumers in {endpoint}"

            assert isinstance(info["impact_score"], (int, float)), f"impact_score must be numeric for {endpoint}"
            assert info["impact_score"] >= 0, f"impact_score must be >= 0 for {endpoint}"
            assert info["priority"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"], \
                f"Invalid priority for {endpoint}: {info['priority']}"
            assert isinstance(info["total_consumers"], int), f"total_consumers must be integer for {endpoint}"
            assert info["total_consumers"] >= 0, f"total_consumers must be >= 0 for {endpoint}"
            assert isinstance(info["consumer_types"], dict), f"consumer_types must be dict for {endpoint}"
            assert isinstance(info["consumers"], list), f"consumers must be list for {endpoint}"

    def test_priority_classification_accuracy(self, report_data):
        """Test that priority classifications match impact scores"""
        impact_matrix = report_data["impact_matrix"]

        for endpoint, info in impact_matrix.items():
            score = info["impact_score"]
            priority = info["priority"]

            if priority == "CRITICAL":
                assert score >= 50, f"CRITICAL priority endpoint {endpoint} has score {score} < 50"
            elif priority == "HIGH":
                assert 20 <= score < 50, f"HIGH priority endpoint {endpoint} has score {score} not in [20, 50)"
            elif priority == "MEDIUM":
                assert 10 <= score < 20, f"MEDIUM priority endpoint {endpoint} has score {score} not in [10, 20)"
            elif priority == "LOW":
                assert score < 10, f"LOW priority endpoint {endpoint} has score {score} >= 10"

    def test_consumer_references_consistency(self, report_data):
        """Test that consumer references are consistent across data structures"""
        impact_matrix = report_data["impact_matrix"]
        consumers = report_data["consumers"]
        endpoint_consumers = report_data["endpoint_consumers"]

        for endpoint, info in impact_matrix.items():
            expected_consumers = set(endpoint_consumers.get(endpoint, []))
            actual_consumers = set(info["consumers"])

            assert expected_consumers == actual_consumers, \
                f"Consumer mismatch for {endpoint}: expected {len(expected_consumers)}, got {len(actual_consumers)}"

            # Verify all consumers exist in consumers dict
            for consumer_id in info["consumers"]:
                assert consumer_id in consumers, f"Consumer {consumer_id} not found in consumers dict"

    def test_consumer_type_counts(self, report_data):
        """Test that consumer type counts match actual consumers"""
        impact_matrix = report_data["impact_matrix"]
        consumers = report_data["consumers"]

        for endpoint, info in impact_matrix.items():
            type_counts = info["consumer_types"]

            # Count actual consumers by type
            actual_type_counts = {}
            for consumer_id in info["consumers"]:
                if consumer_id in consumers:
                    consumer_refs = consumers[consumer_id]
                    if consumer_refs:
                        consumer_type = consumer_refs[0].get("type", "unknown")
                        actual_type_counts[consumer_type] = actual_type_counts.get(consumer_type, 0) + len(consumer_refs)

            # Compare counts - should match exactly since we're counting references
            for consumer_type, expected_count in type_counts.items():
                actual_count = actual_type_counts.get(consumer_type, 0)
                assert actual_count == expected_count, \
                    f"Type count mismatch for {endpoint}, {consumer_type}: expected {expected_count}, got {actual_count}"

    def test_markdown_report_completeness(self, report_data):
        """Test that markdown report contains required sections"""
        report = report_data["report"]

        required_sections = [
            "# Consumer Impact Analysis Report",
            "## Overview",
            "## Summary Statistics",
            "## Consumer Type Breakdown",
            "## CRITICAL Priority Endpoints",
            "## HIGH Priority Endpoints",
            "## MEDIUM Priority Endpoints",
            "## LOW Priority Endpoints",
            "## Methodology",
            "## Data Sources",
        ]

        for section in required_sections:
            assert section in report, f"Missing required section: {section}"

    def test_markdown_report_statistics(self, report_data):
        """Test that markdown report statistics match JSON data"""
        report = report_data["report"]
        summary = report_data["summary"]

        # Check that summary statistics appear in markdown
        assert str(summary["total_endpoints"]) in report, "total_endpoints not in markdown"
        assert str(summary["total_consumers"]) in report, "total_consumers not in markdown"

        priority_counts = summary["priority_counts"]
        for priority in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            assert str(priority_counts[priority]) in report, f"{priority} count not in markdown"

    def test_endpoint_coverage(self, report_data):
        """Test that report covers a reasonable number of endpoints"""
        summary = report_data["summary"]

        # Should have at least 100 endpoints (based on previous analysis)
        assert summary["total_endpoints"] >= 100, \
            f"Report covers too few endpoints: {summary['total_endpoints']} < 100"

    def test_consumer_coverage(self, report_data):
        """Test that report covers a reasonable number of consumers"""
        summary = report_data["summary"]

        # Should have at least 1000 consumers (based on previous analysis)
        assert summary["total_consumers"] >= 1000, \
            f"Report covers too few consumers: {summary['total_consumers']} < 1000"

    def test_priority_distribution(self, report_data):
        """Test that priority distribution is reasonable"""
        summary = report_data["summary"]
        priority_counts = summary["priority_counts"]

        total = summary["total_endpoints"]

        # Most endpoints should be LOW priority (safe default)
        low_percentage = priority_counts["LOW"] / total if total > 0 else 0
        assert low_percentage >= 0.5, \
            f"Too many high-priority endpoints: {low_percentage * 100:.1f}% are LOW (expected >= 50%)"

        # CRITICAL endpoints should be rare
        critical_percentage = priority_counts["CRITICAL"] / total if total > 0 else 0
        assert critical_percentage <= 0.1, \
            f"Too many CRITICAL endpoints: {critical_percentage * 100:.1f}% are CRITICAL (expected <= 10%)"

    def test_impact_score_calculation(self, report_data):
        """Test that impact scores are calculated correctly"""
        impact_matrix = report_data["impact_matrix"]
        consumers = report_data["consumers"]

        type_weights = {
            "sdk": 2.0,
            "webhook": 1.5,
            "api_client": 1.0,
            "reverse_lookup": 0.5,
            "hardcoded": 1.0,
        }

        for endpoint, info in list(impact_matrix.items())[:10]:  # Test first 10 endpoints
            # Calculate expected score
            expected_score = 0.0
            type_counts = {}

            for consumer_id in info["consumers"]:
                if consumer_id in consumers:
                    consumer_refs = consumers[consumer_id]
                    if consumer_refs:
                        consumer_type = consumer_refs[0].get("type", "unknown")
                        type_counts[consumer_type] = type_counts.get(consumer_type, 0) + len(consumer_refs)

            for consumer_type, count in type_counts.items():
                weight = type_weights.get(consumer_type, 1.0)
                expected_score += count * weight

            # Allow small variance for floating point precision
            actual_score = info["impact_score"]
            variance = abs(actual_score - expected_score) / max(expected_score, 1) if expected_score > 0 else 0
            assert variance <= 0.01 or abs(actual_score - expected_score) < 0.1, \
                f"Impact score mismatch for {endpoint}: expected {expected_score:.1f}, got {actual_score:.1f} (variance: {variance * 100:.1f}%)"

    def test_consumer_type_diversity(self, report_data):
        """Test that report includes diverse consumer types"""
        impact_matrix = report_data["impact_matrix"]

        all_types = set()
        for endpoint, info in impact_matrix.items():
            all_types.update(info["consumer_types"].keys())

        # Should have at least 3 different consumer types
        assert len(all_types) >= 3, \
            f"Report has too few consumer types: {len(all_types)} < 3 (found: {all_types})"

    def test_top_endpoints_have_high_scores(self, report_data):
        """Test that top endpoints by impact score have reasonable scores"""
        impact_matrix = report_data["impact_matrix"]

        # Sort by impact score
        sorted_endpoints = sorted(
            impact_matrix.items(),
            key=lambda x: x[1]["impact_score"],
            reverse=True
        )

        # Top 10 endpoints should have impact scores > 0
        for endpoint, info in sorted_endpoints[:10]:
            assert info["impact_score"] > 0, \
                f"Top endpoint {endpoint} has impact score 0"

