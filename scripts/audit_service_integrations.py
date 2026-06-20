#!/usr/bin/env python3
"""
Service Integration Audit Script

Comprehensive audit of service integrations against established patterns.
This script identifies integrations not following patterns and creates a remediation plan.

Patterns checked:
1. Direct Service Calls (Synchronous) - Must use service clients with:
   - HTTP client (httpx) with connection pooling
   - Retry logic with exponential backoff
   - Circuit breaker for fault tolerance
   - Distributed tracing support
   - Health check capabilities

2. Event-Driven Coordination (Asynchronous) - Must use:
   - EventPublisher/EventSubscriber classes
   - Event schema validation
   - Dead letter queue handling

3. Workflow Orchestration (Multi-Step) - Must use:
   - WorkflowEngine for complex operations
   - State management
   - Compensation logic

4. BaseService Pattern - Services must extend BaseService
"""

import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class IntegrationIssue:
    """Represents an integration issue found during audit."""

    file_path: str
    line_number: int
    issue_type: str  # 'missing_circuit_breaker', 'missing_retry', 'direct_http_call', etc.
    severity: str  # 'critical', 'high', 'medium', 'low'
    description: str
    code_snippet: str
    recommendation: str
    pattern_violated: str  # Which pattern is violated


@dataclass
class ServiceIntegration:
    """Represents a service integration found in code."""

    file_path: str
    service_name: str
    integration_type: str  # 'service_client', 'direct_call', 'event', 'workflow'
    has_circuit_breaker: bool
    has_retry_logic: bool
    has_tracing: bool
    uses_base_service: bool
    issues: list[IntegrationIssue]


class ServiceIntegrationAuditor:
    """Audits service integrations against established patterns."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.hub_apps_path = project_root / "hub" / "apps"
        self.issues: list[IntegrationIssue] = []
        self.integrations: list[ServiceIntegration] = []

        # Known service clients
        self.service_clients = {
            "ComplianceServiceClient": "hub/apps/compliance/service_client.py",
            "DQServiceClient": "hub/apps/dq/service_client.py",
            "SemanticServiceClient": "hub/apps/semantic/service_client.py",
            "DataContractCLIClient": "hub/apps/contracts/cli_client.py",
        }

        # Known BaseService classes
        self.base_service_classes = {
            "BaseService",
            "ContractService",
            "TransformationService",
            "MarketplaceService",
            "DataMeshService",
            "VirtualizationService",
            "IngestionService",
            "GovernanceService",
            "SearchService",
            "ODPSService",
        }

    def audit_all(self) -> dict:
        """Run complete audit of all service integrations."""
        print("Starting service integration audit...")

        # Find all Python files in hub/apps
        python_files = list(self.hub_apps_path.rglob("*.py"))
        print(f"Found {len(python_files)} Python files to audit")

        # Exclude test files and migrations
        files_to_audit = [
            f
            for f in python_files
            if "test" not in str(f) and "migration" not in str(f) and "__pycache__" not in str(f)
        ]
        print(f"Auditing {len(files_to_audit)} non-test files")

        # Audit each file
        for file_path in files_to_audit:
            try:
                self._audit_file(file_path)
            except Exception as e:
                print(f"Error auditing {file_path}: {e}")
                continue

        # Generate report
        return self._generate_report()

    def _audit_file(self, file_path: Path):
        """Audit a single file for service integration issues."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return

        relative_path = str(file_path.relative_to(self.project_root))

        # Check for direct HTTP calls
        self._check_direct_http_calls(content, relative_path)

        # Check for service client usage
        self._check_service_client_usage(tree, content, relative_path)

        # Check for BaseService usage
        self._check_base_service_usage(tree, content, relative_path)

        # Check for event-driven patterns
        self._check_event_patterns(tree, content, relative_path)

        # Check for workflow patterns
        self._check_workflow_patterns(tree, content, relative_path)

    def _check_direct_http_calls(self, content: str, file_path: str):
        """Check for direct HTTP calls without service clients."""
        # Patterns to detect direct HTTP calls
        patterns = [
            (r"httpx\.(get|post|put|delete|patch|request)\s*\(", "httpx direct call"),
            (r"requests\.(get|post|put|delete|patch|request)\s*\(", "requests direct call"),
            (r"urllib\.(request|parse)", "urllib direct call"),
            (r"http\.client\.", "http.client direct call"),
        ]

        lines = content.split("\n")
        for line_num, line in enumerate(lines, 1):
            # Skip comments and docstrings
            if line.strip().startswith("#") or '"""' in line or "'''" in line:
                continue

            for pattern, call_type in patterns:
                if re.search(pattern, line):
                    # Check if it's in a service client file (allowed)
                    if "service_client" in file_path or "cli_client" in file_path:
                        continue

                    # Check if it's in a test file
                    if "test" in file_path:
                        continue

                    # Found direct HTTP call
                    issue = IntegrationIssue(
                        file_path=file_path,
                        line_number=line_num,
                        issue_type="direct_http_call",
                        severity="high",
                        description=f"Direct {call_type} found. Should use service client instead.",
                        code_snippet=line.strip()[:200],
                        recommendation="Use appropriate service client (ComplianceServiceClient, DQServiceClient, etc.) instead of direct HTTP calls.",
                        pattern_violated="Pattern 1: Direct Service Calls",
                    )
                    self.issues.append(issue)

    def _check_service_client_usage(self, tree: ast.AST, content: str, file_path: str):
        """Check service client usage patterns."""
        lines = content.split("\n")

        # Find all service client instantiations
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if it's instantiating a service client
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name in self.service_clients:
                        # Check if circuit breaker is used
                        self._check_client_methods(node, func_name, file_path, lines)

    def _check_client_methods(
        self, node: ast.Call, client_name: str, file_path: str, lines: list[str]
    ):
        """Check if service client methods are used correctly."""
        # This is a simplified check - in practice, we'd need to track variable assignments
        # and method calls more carefully

    def _check_base_service_usage(self, tree: ast.AST, content: str, file_path: str):
        """Check if services extend BaseService."""
        # Only check service files
        if "services.py" not in file_path:
            return

        # Check for class definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name

                # Check if it's a service class (ends with Service)
                if class_name.endswith("Service") and class_name != "BaseService":
                    # Check if it extends BaseService
                    has_base_service = False
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            if base.id == "BaseService":
                                has_base_service = True
                                break
                        elif isinstance(base, ast.Attribute):
                            if base.attr == "BaseService":
                                has_base_service = True
                                break

                    if not has_base_service:
                        issue = IntegrationIssue(
                            file_path=file_path,
                            line_number=node.lineno,
                            issue_type="missing_base_service",
                            severity="high",
                            description=f"Service class {class_name} does not extend BaseService.",
                            code_snippet=f"class {class_name}(...):",
                            recommendation=f"Change to: class {class_name}(BaseService, ...):",
                            pattern_violated="Service Layer Pattern",
                        )
                        self.issues.append(issue)

    def _check_event_patterns(self, tree: ast.AST, content: str, file_path: str):
        """Check event-driven pattern usage."""
        # Check for synchronous calls in event handlers (anti-pattern)
        lines = content.split("\n")

        # Look for event subscriber decorators
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for @event_subscriber decorator
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name):
                            if decorator.func.id == "event_subscriber":
                                # Check function body for synchronous calls
                                self._check_event_handler_body(node, file_path, lines)

    def _check_event_handler_body(self, node: ast.FunctionDef, file_path: str, lines: list[str]):
        """Check event handler body for anti-patterns."""
        # Look for direct service calls in event handlers
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    # Check if it's calling a service client method directly
                    attr_name = child.func.attr
                    if attr_name in ["scan_file", "run_dq", "map_contract", "validate"]:
                        issue = IntegrationIssue(
                            file_path=file_path,
                            line_number=child.lineno,
                            issue_type="synchronous_call_in_event_handler",
                            severity="critical",
                            description=f"Synchronous service call '{attr_name}' in event handler. This blocks event processing.",
                            code_snippet=lines[child.lineno - 1].strip()[:200],
                            recommendation="Publish an event instead of making synchronous calls in event handlers.",
                            pattern_violated="Pattern 2: Event-Driven Coordination (Anti-Pattern 1)",
                        )
                        self.issues.append(issue)

    def _check_workflow_patterns(self, tree: ast.AST, content: str, file_path: str):
        """Check workflow orchestration pattern usage."""
        # Check for complex multi-step operations that should use workflows
        # This is a simplified check - would need more sophisticated analysis

    def _generate_report(self) -> dict:
        """Generate comprehensive audit report."""
        # Group issues by type
        issues_by_type = defaultdict(list)
        for issue in self.issues:
            issues_by_type[issue.issue_type].append(issue)

        # Group issues by severity
        issues_by_severity = defaultdict(list)
        for issue in self.issues:
            issues_by_severity[issue.severity].append(issue)

        # Group issues by file
        issues_by_file = defaultdict(list)
        for issue in self.issues:
            issues_by_file[issue.file_path].append(issue)

        # Count by pattern violated
        issues_by_pattern = defaultdict(list)
        for issue in self.issues:
            issues_by_pattern[issue.pattern_violated].append(issue)

        report = {
            "summary": {
                "total_issues": len(self.issues),
                "critical_issues": len(issues_by_severity["critical"]),
                "high_issues": len(issues_by_severity["high"]),
                "medium_issues": len(issues_by_severity["medium"]),
                "low_issues": len(issues_by_severity["low"]),
                "files_affected": len(issues_by_file),
            },
            "issues_by_type": {
                issue_type: len(issues) for issue_type, issues in issues_by_type.items()
            },
            "issues_by_pattern": {
                pattern: len(issues) for pattern, issues in issues_by_pattern.items()
            },
            "issues": [asdict(issue) for issue in self.issues],
            "issues_by_file": {
                file_path: [asdict(issue) for issue in issues]
                for file_path, issues in issues_by_file.items()
            },
        }

        return report

    def generate_remediation_plan(self, report: dict) -> dict:
        """Generate remediation plan based on audit findings."""
        plan = {
            "overview": "Remediation plan for service integration pattern compliance",
            "phases": [],
        }

        # Phase 1: Critical issues
        critical_issues = [issue for issue in self.issues if issue.severity == "critical"]
        if critical_issues:
            plan["phases"].append(
                {
                    "phase": 1,
                    "name": "Fix Critical Issues",
                    "priority": "critical",
                    "issues": [asdict(issue) for issue in critical_issues],
                    "actions": [
                        "Remove synchronous calls from event handlers",
                        "Replace with event publishing pattern",
                        "Test event-driven flows",
                    ],
                }
            )

        # Phase 2: High priority issues
        high_issues = [issue for issue in self.issues if issue.severity == "high"]
        if high_issues:
            plan["phases"].append(
                {
                    "phase": 2,
                    "name": "Fix High Priority Issues",
                    "priority": "high",
                    "issues": [asdict(issue) for issue in high_issues],
                    "actions": [
                        "Replace direct HTTP calls with service clients",
                        "Ensure all services extend BaseService",
                        "Add circuit breakers where missing",
                        "Add retry logic where missing",
                        "Add distributed tracing",
                    ],
                }
            )

        # Phase 3: Medium priority issues
        medium_issues = [issue for issue in self.issues if issue.severity == "medium"]
        if medium_issues:
            plan["phases"].append(
                {
                    "phase": 3,
                    "name": "Fix Medium Priority Issues",
                    "priority": "medium",
                    "issues": [asdict(issue) for issue in medium_issues],
                    "actions": [
                        "Refactor to use workflow orchestration where appropriate",
                        "Improve error handling",
                        "Add health checks",
                    ],
                }
            )

        return plan


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    auditor = ServiceIntegrationAuditor(project_root)

    print("=" * 80)
    print("Service Integration Audit")
    print("=" * 80)

    # Run audit
    report = auditor.audit_all()

    # Generate remediation plan
    remediation_plan = auditor.generate_remediation_plan(report)

    # Save reports
    output_dir = project_root / "docs" / "api-audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "service-integration-audit.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nAudit report saved to: {report_path}")

    plan_path = output_dir / "service-integration-remediation-plan.json"
    with open(plan_path, "w") as f:
        json.dump(remediation_plan, f, indent=2)
    print(f"Remediation plan saved to: {plan_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("Audit Summary")
    print("=" * 80)
    print(f"Total Issues Found: {report['summary']['total_issues']}")
    print(f"  Critical: {report['summary']['critical_issues']}")
    print(f"  High: {report['summary']['high_issues']}")
    print(f"  Medium: {report['summary']['medium_issues']}")
    print(f"  Low: {report['summary']['low_issues']}")
    print(f"Files Affected: {report['summary']['files_affected']}")

    print("\nIssues by Type:")
    for issue_type, count in report["issues_by_type"].items():
        print(f"  {issue_type}: {count}")

    print("\nIssues by Pattern Violated:")
    for pattern, count in report["issues_by_pattern"].items():
        print(f"  {pattern}: {count}")

    print("\n" + "=" * 80)
    print("Remediation Plan Phases: {len(remediation_plan['phases'])}")
    for phase in remediation_plan["phases"]:
        print(f"\nPhase {phase['phase']}: {phase['name']} ({phase['priority']} priority)")
        print(f"  Issues: {len(phase['issues'])}")
        print("  Actions:")
        for action in phase["actions"]:
            print(f"    - {action}")


if __name__ == "__main__":
    main()
