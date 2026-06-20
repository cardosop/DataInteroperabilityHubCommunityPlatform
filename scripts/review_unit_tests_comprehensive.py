#!/usr/bin/env python3
"""
Comprehensive Unit Test Review Script for All 29 Features

This script reviews unit tests across all features/apps and generates a comprehensive report
covering:
- Test file existence and structure
- Mock/stub usage audit
- Coverage analysis
- TDD principles verification
- Development best practices verification
- Gap identification
- Update plan generation
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class TestFileReview:
    """Review results for a single test file"""

    file_path: str
    exists: bool
    line_count: int
    test_count: int
    mock_usage: list[dict]
    stub_usage: list[dict]
    scenarios_covered: dict[str, bool]  # success, failure, edge_cases, error_handling
    tdd_compliance: bool
    best_practices_issues: list[str]
    coverage_estimate: float | None


@dataclass
class AppReview:
    """Review results for an entire app"""

    app_name: str
    app_path: str
    test_files: dict[str, TestFileReview]
    total_tests: int
    total_mocks: int
    total_stubs: int
    coverage_status: str  # "complete", "partial", "missing"
    gaps: list[str]
    update_plan: list[str]


class TestReviewer:
    """Comprehensive test reviewer"""

    # Mock/stub patterns to detect
    MOCK_PATTERNS = [
        r"@patch\s*\(",
        r"Mock\s*\(",
        r"mock\s*\.",
        r"@mock\.",
        r"unittest\.mock",
        r"from unittest\.mock import",
        r"from unittest import mock",
        r"@pytest\.fixture.*mock",
        r"@pytest\.mock",
    ]

    STUB_PATTERNS = [
        r"stub\s*\(",
        r"Stub\s*\(",
        r"\.stub\s*\(",
    ]

    # TDD indicators
    TDD_PATTERNS = [
        r"def test_.*\(self\):",
        r"def test_.*\(\):",
        r"@pytest\.mark\..*",
        r"class Test.*:",
    ]

    # Best practices violations
    VIOLATION_PATTERNS = [
        r"# TODO.*mock",
        r"# FIXME.*mock",
        r"skip.*flaky",
        r"@pytest\.mark\.skipif.*flaky",
        r"retry.*without.*fix",
        r"except.*pass",
        r"except.*:.*\n\s*pass",
    ]

    def __init__(self, base_path: str = "hub/apps"):
        self.base_path = Path(base_path)
        self.reviews: dict[str, AppReview] = {}

    def review_all_apps(self) -> dict[str, AppReview]:
        """Review all apps"""
        apps = self._get_all_apps()

        for app_name in apps:
            print(f"Reviewing {app_name}...")
            review = self.review_app(app_name)
            self.reviews[app_name] = review

        return self.reviews

    def _get_all_apps(self) -> list[str]:
        """Get list of all apps"""
        apps = []
        if self.base_path.exists():
            for item in self.base_path.iterdir():
                if item.is_dir() and not item.name.startswith("_"):
                    # Check if it has a tests directory
                    tests_dir = item / "tests"
                    if tests_dir.exists():
                        apps.append(item.name)
        return sorted(apps)

    def review_app(self, app_name: str) -> AppReview:
        """Review a single app"""
        app_path = self.base_path / app_name
        tests_dir = app_path / "tests"

        test_files = {}
        total_tests = 0
        total_mocks = 0
        total_stubs = 0

        # Expected test files based on tasks.md
        expected_files = self._get_expected_test_files(app_name)

        for test_file_name in expected_files:
            test_file_path = tests_dir / test_file_name
            review = self.review_test_file(str(test_file_path), app_name)
            test_files[test_file_name] = review
            total_tests += review.test_count
            total_mocks += len(review.mock_usage)
            total_stubs += len(review.stub_usage)

        # Also check for any additional test files
        if tests_dir.exists():
            for test_file in tests_dir.glob("test_*.py"):
                test_file_name = test_file.name
                if test_file_name not in test_files:
                    review = self.review_test_file(str(test_file), app_name)
                    test_files[test_file_name] = review
                    total_tests += review.test_count
                    total_mocks += len(review.mock_usage)
                    total_stubs += len(review.stub_usage)

        # Determine coverage status
        coverage_status = self._determine_coverage_status(test_files, app_name)

        # Identify gaps
        gaps = self._identify_gaps(test_files, app_name)

        # Create update plan
        update_plan = self._create_update_plan(test_files, gaps, app_name)

        return AppReview(
            app_name=app_name,
            app_path=str(app_path),
            test_files=test_files,
            total_tests=total_tests,
            total_mocks=total_mocks,
            total_stubs=total_stubs,
            coverage_status=coverage_status,
            gaps=gaps,
            update_plan=update_plan,
        )

    def _get_expected_test_files(self, app_name: str) -> list[str]:
        """Get expected test files for an app based on tasks.md"""
        expected_files_map = {
            "auth": [
                "test_authentication.py",
                "test_authentication_flows.py",
                "test_authorization.py",
                "test_sessions.py",
                "test_register_me.py",
                "test_middleware.py",
            ],
            "contracts": [
                "test_views.py",
                "test_services.py",
                "test_validation.py",
                "test_normalization_metrics.py",
                "test_odps_normalizer.py",
                "test_odps_generator_coverage_gaps.py",
                "test_ref_resolver.py",
                "test_ref_resolver_caching.py",
                "test_ref_resolver_security.py",
                "test_lineage_service.py",
                "test_lineage_traversal.py",
                "test_lineage_visualization.py",
                "test_lineage_reference_resolution.py",
                "test_odps_rate_limiting.py",
                "test_odps_metrics.py",
                "test_rollback_odps_migration.py",
                "test_caching_enhanced.py",
                "test_ref_warming.py",
                "test_cli_client.py",
                "test_views_validation.py",
                "test_migration_rollback_comprehensive.py",
            ],
            "assets": [
                "test_asset_crud.py",
                "test_services.py",
                "test_asset_relationships.py",
                "test_health_score.py",
                "test_caching.py",
                "test_business_rules.py",
            ],
            "datasets": [
                "test_views.py",
                "test_services.py",
                "test_versioning.py",
                "test_business_rules.py",
                "test_caching.py",
            ],
            "dq": [
                "test_views.py",
                "test_service_client.py",
                "test_business_rules.py",
            ],
            "compliance": [
                "test_views.py",
                "test_services.py",
                "test_business_rules.py",
                "test_serializers.py",
            ],
            "marketplace": [
                "test_views.py",
                "test_services.py",
                "test_kyc_enforcement.py",
                "test_business_rules.py",
            ],
            "governance": [
                "test_access_request_views.py",
                "test_retention_service.py",
                "test_retention_api_integration.py",
                "test_services.py",
                "test_business_rules.py",
            ],
            "search": [
                "test_views.py",
                "test_search_engine.py",
                "test_indexing.py",
                "test_business_rules.py",
                "test_performance.py",
                "test_search_service_event_integration.py",
                "test_search_views_event_publishing_e2e.py",
            ],
            "observability": [
                "test_otel_metrics.py",
                "test_metrics.py",
                "test_business_rules.py",
            ],
            "orchestration": [
                "test_product_creation_workflow.py",
                "test_odps_workflow_events.py",
                "test_workflow_business_rules_integration.py",
                "test_workflow_task_business_rules_integration.py",
                "test_workflow_business_rules_performance.py",
                "test_workflow_business_rules_unit.py",
                "test_workflow_gateway_independence.py",
                "test_alerting.py",
                "test_monitoring_validation.py",
                "test_feature_flags.py",
                "test_rollback_procedures.py",
                "test_gradual_rollout.py",
                "test_post_deployment.py",
            ],
            "semantic": [
                "test_models.py",
                "test_business_rules.py",
                "test_caching.py",
                "test_caching_integration.py",
                "test_external_resource_mapping.py",
                "test_external_resource_sparql.py",
                "test_odps_semantic_mapping.py",
                "test_odps_semantic_mapping_alert.py",
                "test_odps_semantic_mapping_metrics.py",
                "test_rdf_mapping.py",
                "test_service_client_odps.py",
                "test_sparql_endpoint.py",
                "test_sparql_limits.py",
                "test_uri_generation.py",
                "test_uri_ontology_endpoints.py",
                "test_uri_validators.py",
                "test_uri_validators_integration.py",
                "test_utils.py",
            ],
            "ai": [
                "test_views.py",
                "test_serializers.py",
                "test_llm_client.py",
            ],
            "ml": [
                "test_views.py",
                "test_models.py",
                "test_training.py",
                "test_inference.py",
            ],
            "social": [
                "test_views.py",
                "test_models.py",
                "test_serializers.py",
                "test_social_service.py",
                "test_social_api_integration.py",
            ],
            "mesh": [
                "test_views.py",
                "test_services.py",
                "test_serializers.py",
                "test_business_rules.py",
            ],
            "virtualization": [
                "test_models.py",
                "test_views.py",
                "test_services.py",
                "test_serializers.py",
                "test_business_rules.py",
                "test_execute_query.py",
                "test_execute_query_integration.py",
                "test_federated_asset_sources.py",
                "test_governance_integration.py",
                "test_compliance_integration.py",
                "test_quality_integration.py",
                "test_security.py",
                "test_performance.py",
                "test_metrics.py",
                "test_job_queue_integration.py",
                "test_service_workflow_integration.py",
                "test_query_execution_views.py",
                "test_topology_views.py",
                "test_views_integration.py",
                "test_urls.py",
                "test_migration.py",
                "test_virtualization_business_rules_refactoring.py",
            ],
            "scheduled_ingestion": [
                "test_views.py",
                "test_services.py",
                "test_ingestion.py",
                "test_internal_worker_api.py",
                "test_prefect_full_flow_integration.py",
                "test_phase7_comprehensive.py",
                "test_phase6_infrastructure.py",
                "test_phase5_integrations.py",
                "test_phase9_documentation.py",
                "test_management_commands.py",
                "test_business_rules.py",
                "test_serializers.py",
            ],
            "scheduled_export": [
                "test_views.py",
                "test_models.py",
                "test_services.py",
                "test_service_and_business_rules.py",
                "test_internal_worker_api.py",
                "test_run_completion_side_effects.py",
            ],
            "webhooks": [
                "test_webhook_service.py",
                "test_webhook_api_integration.py",
            ],
            "audit": [
                "test_audit_event_querying.py",
                "test_odps_audit_comprehensive_validation.py",
                "test_audit_policy_critical_paths.py",
                "test_utils.py",
                "test_views.py",
            ],
            "jobs": [
                "test_job_creation_processing.py",
                "test_job_processors.py",
                "test_scheduled_ingestion_job.py",
                "test_utils.py",
                "test_views.py",
            ],
            "files": [
                "test_views.py",
                "test_services.py",
                "test_storage.py",
                "test_business_rules.py",
                "test_serializers.py",
            ],
            "integrations": [
                "test_views.py",
                "test_services.py",
                "test_services_integration.py",
                "test_mapping_models.py",
                "test_mapping_serializers.py",
                "test_mapping_views.py",
                "test_event_publishers.py",
                "test_event_publishers_e2e.py",
                "test_event_publishers_integration.py",
                "test_federated_asset_creation.py",
                "test_federated_asset_workflow.py",
                "test_gcp_marketplace_connector.py",
                "test_gcp_marketplace_connector_error_handling.py",
                "test_gcp_marketplace_connector_security.py",
                "test_marketplace_framework.py",
                "test_scheduled_sync.py",
                "test_service_workflow_integration.py",
                "test_services_marketplace_events_e2e.py",
                "test_tasks.py",
                "test_urls.py",
                "test_business_rules.py",
                "test_serializers.py",
            ],
            "rate_limiting": [
                "test_config.py",
                "test_middleware.py",
                "test_integration.py",
                "test_error_response.py",
            ],
            "tenants": [
                "test_models.py",
                "test_plan_limit_service.py",
                "test_plan_limit_enforcement_integration.py",
                "test_plan_limit_enforcement_comprehensive.py",
                "test_tenant_config_compliance_integration.py",
                "test_tenant_config_dq_integration.py",
                "test_tenant_config_file_upload_integration.py",
                "test_tenant_config_job_integration.py",
                "test_services.py",
                "test_serializers.py",
                "test_middleware.py",
                "test_views.py",
                "test_urls.py",
            ],
            "billing": [
                "test_subscription_integration.py",
                "test_views.py",
                "test_services.py",
                "test_models.py",
            ],
            "gdpr": [
                "test_erasure_integration.py",
                "test_views.py",
                "test_services.py",
                "test_models.py",
            ],
            "health": [
                "test_views.py",
                "test_services.py",
            ],
        }

        return expected_files_map.get(app_name, [])

    def review_test_file(self, file_path: str, app_name: str) -> TestFileReview:
        """Review a single test file"""
        path = Path(file_path)
        exists = path.exists()

        if not exists:
            return TestFileReview(
                file_path=file_path,
                exists=False,
                line_count=0,
                test_count=0,
                mock_usage=[],
                stub_usage=[],
                scenarios_covered={
                    "success": False,
                    "failure": False,
                    "edge_cases": False,
                    "error_handling": False,
                },
                tdd_compliance=False,
                best_practices_issues=["File does not exist"],
                coverage_estimate=None,
            )

        content = path.read_text()
        lines = content.split("\n")

        # Count tests
        test_count = len(re.findall(r"def test_", content))

        # Find mocks
        mock_usage = self._find_mocks(content, file_path)

        # Find stubs
        stub_usage = self._find_stubs(content, file_path)

        # Check scenarios
        scenarios_covered = self._check_scenarios(content)

        # Check TDD compliance
        tdd_compliance = self._check_tdd_compliance(content)

        # Check best practices
        best_practices_issues = self._check_best_practices(content, file_path)

        # Estimate coverage (rough)
        coverage_estimate = self._estimate_coverage(content, test_count)

        return TestFileReview(
            file_path=file_path,
            exists=True,
            line_count=len(lines),
            test_count=test_count,
            mock_usage=mock_usage,
            stub_usage=stub_usage,
            scenarios_covered=scenarios_covered,
            tdd_compliance=tdd_compliance,
            best_practices_issues=best_practices_issues,
            coverage_estimate=coverage_estimate,
        )

    def _find_mocks(self, content: str, file_path: str) -> list[dict]:
        """Find mock usage in content"""
        mocks = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            for pattern in self.MOCK_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    # Check if it's justified (external boundary)
                    is_justified = self._is_justified_mock(line, content, file_path)
                    mocks.append(
                        {
                            "line": i,
                            "content": line.strip(),
                            "pattern": pattern,
                            "justified": is_justified,
                        }
                    )
                    break

        return mocks

    def _find_stubs(self, content: str, file_path: str) -> list[dict]:
        """Find stub usage in content"""
        stubs = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            for pattern in self.STUB_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    is_justified = self._is_justified_stub(line, content, file_path)
                    stubs.append(
                        {
                            "line": i,
                            "content": line.strip(),
                            "pattern": pattern,
                            "justified": is_justified,
                        }
                    )
                    break

        return stubs

    def _is_justified_mock(self, line: str, content: str, file_path: str) -> bool:
        """Check if mock is justified (external process boundary)"""
        # Middleware get_response mock is acceptable
        if "get_response" in line.lower() and "middleware" in content.lower():
            return True

        # External API mocks (third-party services)
        external_patterns = [
            r"third.?party",
            r"external.?api",
            r"external.?service",
            r"@external",
            r"# external",
        ]

        context_lines = content[max(0, content.find(line) - 500) : content.find(line) + 500]
        for pattern in external_patterns:
            if re.search(pattern, context_lines, re.IGNORECASE):
                return True

        return False

    def _is_justified_stub(self, line: str, content: str, file_path: str) -> bool:
        """Check if stub is justified"""
        return self._is_justified_mock(line, content, file_path)

    def _check_scenarios(self, content: str) -> dict[str, bool]:
        """Check if scenarios are covered"""
        scenarios = {
            "success": False,
            "failure": False,
            "edge_cases": False,
            "error_handling": False,
        }

        # Success scenarios
        success_patterns = [
            r"test.*success",
            r"test.*valid",
            r"assert.*200",
            r"assert.*created",
            r"assert.*True",
        ]

        # Failure scenarios
        failure_patterns = [
            r"test.*fail",
            r"test.*invalid",
            r"assert.*400",
            r"assert.*404",
            r"assert.*False",
            r"assert.*None",
        ]

        # Edge cases
        edge_patterns = [
            r"test.*edge",
            r"test.*boundary",
            r"test.*empty",
            r"test.*null",
            r"test.*max",
            r"test.*min",
        ]

        # Error handling
        error_patterns = [
            r"test.*error",
            r"test.*exception",
            r"assert.*raises",
            r"with.*pytest\.raises",
            r"assert.*500",
        ]

        content_lower = content.lower()

        for pattern in success_patterns:
            if re.search(pattern, content_lower):
                scenarios["success"] = True
                break

        for pattern in failure_patterns:
            if re.search(pattern, content_lower):
                scenarios["failure"] = True
                break

        for pattern in edge_patterns:
            if re.search(pattern, content_lower):
                scenarios["edge_cases"] = True
                break

        for pattern in error_patterns:
            if re.search(pattern, content_lower):
                scenarios["error_handling"] = True
                break

        return scenarios

    def _check_tdd_compliance(self, content: str) -> bool:
        """Check TDD compliance"""
        # TDD: Tests should be written before implementation
        # Indicators: test functions exist, assertions present
        has_tests = bool(re.search(r"def test_", content))
        has_assertions = bool(re.search(r"assert ", content))

        return has_tests and has_assertions

    def _check_best_practices(self, content: str, file_path: str) -> list[str]:
        """Check for best practices violations"""
        issues = []

        for pattern in self.VIOLATION_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                line_num = content[: match.start()].count("\n") + 1
                issues.append(f"Line {line_num}: {match.group()}")

        return issues

    def _estimate_coverage(self, content: str, test_count: int) -> float | None:
        """Rough coverage estimate based on test count and file structure"""
        # This is a rough estimate - actual coverage requires running pytest-cov
        if test_count == 0:
            return 0.0

        # Very rough heuristic
        lines = len(content.split("\n"))
        if lines > 0:
            # Assume each test covers some code
            estimated = min(100.0, (test_count * 10) / max(1, lines / 100))
            return round(estimated, 1)

        return None

    def _determine_coverage_status(
        self, test_files: dict[str, TestFileReview], app_name: str
    ) -> str:
        """Determine overall coverage status"""
        existing_files = [f for f, r in test_files.items() if r.exists]
        expected_files = self._get_expected_test_files(app_name)

        if len(existing_files) == 0:
            return "missing"
        elif len(existing_files) < len(expected_files) * 0.5:
            return "partial"
        else:
            return "complete"

    def _identify_gaps(self, test_files: dict[str, TestFileReview], app_name: str) -> list[str]:
        """Identify gaps in test coverage"""
        gaps = []
        expected_files = self._get_expected_test_files(app_name)

        # Missing files
        for expected_file in expected_files:
            if expected_file not in test_files or not test_files[expected_file].exists:
                gaps.append(f"Missing test file: {expected_file}")

        # Files with issues
        for file_name, review in test_files.items():
            if not review.exists:
                continue

            if review.test_count == 0:
                gaps.append(f"{file_name}: No tests found")

            if len(review.mock_usage) > 0:
                unjustified = [m for m in review.mock_usage if not m.get("justified", False)]
                if unjustified:
                    gaps.append(f"{file_name}: {len(unjustified)} unjustified mocks found")

            if len(review.stub_usage) > 0:
                unjustified = [s for s in review.stub_usage if not s.get("justified", False)]
                if unjustified:
                    gaps.append(f"{file_name}: {len(unjustified)} unjustified stubs found")

            if not all(review.scenarios_covered.values()):
                missing = [k for k, v in review.scenarios_covered.items() if not v]
                gaps.append(f"{file_name}: Missing scenarios: {', '.join(missing)}")

            if not review.tdd_compliance:
                gaps.append(f"{file_name}: TDD compliance issues")

            if review.best_practices_issues:
                gaps.append(
                    f"{file_name}: Best practices violations: {len(review.best_practices_issues)} issues"
                )

        return gaps

    def _create_update_plan(
        self, test_files: dict[str, TestFileReview], gaps: list[str], app_name: str
    ) -> list[str]:
        """Create update plan for an app"""
        plan = []

        if not gaps:
            plan.append("✅ All tests meet requirements")
            return plan

        # Group gaps by type
        missing_files = [g for g in gaps if "Missing test file" in g]
        mock_issues = [g for g in gaps if "unjustified mocks" in g]
        stub_issues = [g for g in gaps if "unjustified stubs" in g]
        scenario_issues = [g for g in gaps if "Missing scenarios" in g]
        tdd_issues = [g for g in gaps if "TDD compliance" in g]
        best_practices_issues = [g for g in gaps if "Best practices violations" in g]

        if missing_files:
            plan.append(f"Create {len(missing_files)} missing test files")

        if mock_issues:
            plan.append(f"Remove/replace {len(mock_issues)} files with unjustified mocks")

        if stub_issues:
            plan.append(f"Remove/replace {len(stub_issues)} files with unjustified stubs")

        if scenario_issues:
            plan.append(f"Add missing scenarios to {len(scenario_issues)} test files")

        if tdd_issues:
            plan.append(f"Fix TDD compliance in {len(tdd_issues)} test files")

        if best_practices_issues:
            plan.append(f"Fix best practices violations in {len(best_practices_issues)} test files")

        return plan

    def generate_report(self, output_file: str = "test_review_report.json"):
        """Generate comprehensive review report"""
        report = {
            "review_date": datetime.now().isoformat(),
            "apps_reviewed": len(self.reviews),
            "apps": {},
        }

        for app_name, review in self.reviews.items():
            app_data = {
                "app_name": review.app_name,
                "app_path": review.app_path,
                "total_tests": review.total_tests,
                "total_mocks": review.total_mocks,
                "total_stubs": review.total_stubs,
                "coverage_status": review.coverage_status,
                "gaps": review.gaps,
                "update_plan": review.update_plan,
                "test_files": {},
            }

            for file_name, file_review in review.test_files.items():
                app_data["test_files"][file_name] = {
                    "exists": file_review.exists,
                    "line_count": file_review.line_count,
                    "test_count": file_review.test_count,
                    "mock_count": len(file_review.mock_usage),
                    "stub_count": len(file_review.stub_usage),
                    "scenarios_covered": file_review.scenarios_covered,
                    "tdd_compliance": file_review.tdd_compliance,
                    "best_practices_issues_count": len(file_review.best_practices_issues),
                    "coverage_estimate": file_review.coverage_estimate,
                }

            report["apps"][app_name] = app_data

        # Write JSON report
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

        # Generate markdown summary
        md_file = output_file.replace(".json", ".md")
        self._generate_markdown_report(report, md_file)

        return report

    def _generate_markdown_report(self, report: dict, output_file: str):
        """Generate markdown report"""
        md_lines = [
            "# Comprehensive Unit Test Review Report",
            "",
            f"**Review Date**: {report['review_date']}",
            f"**Apps Reviewed**: {report['apps_reviewed']}",
            "",
            "## Summary",
            "",
        ]

        # Summary statistics
        total_tests = sum(r.total_tests for r in self.reviews.values())
        total_mocks = sum(r.total_mocks for r in self.reviews.values())
        total_stubs = sum(r.total_stubs for r in self.reviews.values())
        apps_with_gaps = sum(1 for r in self.reviews.values() if r.gaps)

        md_lines.extend(
            [
                f"- **Total Tests**: {total_tests}",
                f"- **Total Mocks Found**: {total_mocks}",
                f"- **Total Stubs Found**: {total_stubs}",
                f"- **Apps with Gaps**: {apps_with_gaps}/{len(self.reviews)}",
                "",
                "## App-by-App Review",
                "",
            ]
        )

        # App details
        for app_name, app_data in sorted(report["apps"].items()):
            md_lines.extend(
                [
                    f"### {app_name.upper()}",
                    "",
                    f"- **Status**: {app_data['coverage_status'].upper()}",
                    f"- **Total Tests**: {app_data['total_tests']}",
                    f"- **Mocks**: {app_data['total_mocks']}",
                    f"- **Stubs**: {app_data['total_stubs']}",
                    "",
                ]
            )

            if app_data["gaps"]:
                md_lines.append("#### Gaps:")
                for gap in app_data["gaps"]:
                    md_lines.append(f"- {gap}")
                md_lines.append("")

            if app_data["update_plan"]:
                md_lines.append("#### Update Plan:")
                for item in app_data["update_plan"]:
                    md_lines.append(f"- {item}")
                md_lines.append("")

            md_lines.append("---\n")

        Path(output_file).write_text("\n".join(md_lines))


def main():
    """Main entry point"""
    reviewer = TestReviewer()

    print("Starting comprehensive unit test review...")
    print(f"Reviewing apps in: {reviewer.base_path}")

    reviews = reviewer.review_all_apps()

    print(f"\nReview complete! Reviewed {len(reviews)} apps.")

    # Generate report
    reviewer.generate_report("test_review_report.json")

    print("\nReport generated:")
    print("  - JSON: test_review_report.json")
    print("  - Markdown: test_review_report.md")

    # Print summary
    total_tests = sum(r.total_tests for r in reviews.values())
    total_mocks = sum(r.total_mocks for r in reviews.values())
    apps_with_gaps = sum(1 for r in reviews.values() if r.gaps)

    print("\nSummary:")
    print(f"  - Total tests: {total_tests}")
    print(f"  - Total mocks: {total_mocks}")
    print(f"  - Apps with gaps: {apps_with_gaps}/{len(reviews)}")


if __name__ == "__main__":
    main()
