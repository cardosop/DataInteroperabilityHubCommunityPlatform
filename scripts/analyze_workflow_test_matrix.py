#!/usr/bin/env python3
"""
Comprehensive workflow test matrix analyzer.

Analyzes workflows, their API trigger points, and associated tests to create
a complete test matrix for Phase 11.1.
"""
import ast
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class WorkflowAnalyzer:
    """Analyzes workflows, API triggers, and tests."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.workflows_dir = project_root / "hub" / "apps" / "orchestration" / "workflows"
        self.views_dir = project_root / "hub" / "apps"
        self.tests_integration_dir = project_root / "tests" / "integration"
        self.tests_e2e_dir = project_root / "tests" / "e2e"
        self.orchestration_tests_dir = project_root / "hub" / "apps" / "orchestration" / "tests"

        self.workflows: Dict[str, Dict] = {}
        self.api_triggers: Dict[str, List[Dict]] = defaultdict(list)
        self.integration_tests: Dict[str, List[str]] = defaultdict(list)
        self.e2e_tests: Dict[str, List[str]] = defaultdict(list)

    def discover_workflows(self) -> Dict[str, Dict]:
        """Discover all workflows in the workflows directory."""
        workflows = {}

        for workflow_file in self.workflows_dir.glob("*.py"):
            if workflow_file.name.startswith("__") or workflow_file.name.startswith("test_"):
                continue

            workflow_name = workflow_file.stem
            class_name = self._extract_workflow_class_name(workflow_file)

            if class_name:
                workflows[class_name] = {
                    "file": str(workflow_file.relative_to(self.project_root)),
                    "class_name": class_name,
                    "workflow_name": self._extract_workflow_name(workflow_file, class_name),
                }

        return workflows

    def _extract_workflow_class_name(self, file_path: Path) -> Optional[str]:
        """Extract workflow class name from file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if "Workflow" in node.name:
                            return node.name
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
        return None

    def _extract_workflow_name(self, file_path: Path, class_name: str) -> Optional[str]:
        """Extract WORKFLOW_NAME constant from workflow class."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == class_name:
                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if (
                                        isinstance(target, ast.Name)
                                        and target.id == "WORKFLOW_NAME"
                                    ):
                                        if isinstance(item.value, ast.Constant):
                                            return item.value.value
                                        elif isinstance(item.value, ast.Str):  # Python < 3.8
                                            return item.value.s
        except Exception as e:
            print(f"Error extracting workflow name from {file_path}: {e}")
        return None

    def find_api_triggers(self) -> Dict[str, List[Dict]]:
        """Find where workflows are triggered from API endpoints."""
        triggers = defaultdict(list)

        # Known workflow patterns
        workflow_patterns = [
            r"(\w+Workflow)\.execute\(",
            r"(\w+Workflow)\.execute_start\(",
            r"(\w+Workflow)\.create_instance\(",
        ]

        # Search in views and services
        search_dirs = [
            self.views_dir,
            self.project_root / "hub" / "apps" / "contracts",
            self.project_root / "hub" / "apps" / "assets",
            self.project_root / "hub" / "apps" / "datasets",
            self.project_root / "hub" / "apps" / "marketplace",
            self.project_root / "hub" / "apps" / "scheduled_ingestion",
            self.project_root / "hub" / "apps" / "integrations",
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for py_file in search_dir.rglob("*.py"):
                if py_file.name.startswith("test_"):
                    continue

                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        lines = content.split("\n")

                        for pattern in workflow_patterns:
                            matches = re.finditer(pattern, content)
                            for match in matches:
                                workflow_class = match.group(1)

                                # Find the function/method containing this call
                                func_name, api_path = self._extract_api_context(
                                    py_file, match.start(), lines
                                )

                                triggers[workflow_class].append(
                                    {
                                        "file": str(py_file.relative_to(self.project_root)),
                                        "function": func_name,
                                        "api_path": api_path,
                                        "line": content[: match.start()].count("\n") + 1,
                                    }
                                )
                except Exception as e:
                    print(f"Error analyzing {py_file}: {e}")

        return triggers

    def _extract_api_context(
        self, file_path: Path, position: int, lines: List[str]
    ) -> Tuple[str, str]:
        """Extract function name and API path context."""
        func_name = "unknown"
        api_path = "unknown"

        try:
            # Find the function containing this position
            line_num = len([c for c in file_path.read_text()[:position] if c == "\n"])
            current_line = line_num

            # Look backwards for function definition
            for i in range(current_line, max(0, current_line - 50), -1):
                line = lines[i] if i < len(lines) else ""
                if re.match(r"\s*def\s+(\w+)", line):
                    func_name = re.match(r"\s*def\s+(\w+)", line).group(1)
                    break
                elif re.match(r"\s*@action", line):
                    # Django REST Framework action
                    func_name = "action"
                    break

            # Try to find URL pattern or API path hints
            if "views.py" in str(file_path):
                # Try to infer from file path
                parts = str(file_path).split(os.sep)
                if "contracts" in parts:
                    api_path = "/api/v1/contracts/"
                elif "assets" in parts:
                    api_path = "/api/v1/assets/"
                elif "datasets" in parts:
                    api_path = "/api/v1/datasets/"
                elif "marketplace" in parts:
                    api_path = "/api/v1/marketplace/"
                elif "scheduled_ingestion" in parts:
                    api_path = "/api/v1/scheduled-ingestions/"
        except Exception:
            pass

        return func_name, api_path

    def find_integration_tests(self) -> Dict[str, List[str]]:
        """Find integration tests for each workflow."""
        tests = defaultdict(list)

        # Search in orchestration tests
        if self.orchestration_tests_dir.exists():
            for test_file in self.orchestration_tests_dir.glob("test_*.py"):
                workflow_refs = self._find_workflow_references_in_file(test_file)
                for workflow_class in workflow_refs:
                    tests[workflow_class].append(str(test_file.relative_to(self.project_root)))

        # Search in integration tests
        if self.tests_integration_dir.exists():
            for test_file in self.tests_integration_dir.rglob("test_*.py"):
                workflow_refs = self._find_workflow_references_in_file(test_file)
                for workflow_class in workflow_refs:
                    tests[workflow_class].append(str(test_file.relative_to(self.project_root)))

        return tests

    def find_e2e_tests(self) -> Dict[str, List[str]]:
        """Find E2E tests for each workflow."""
        tests = defaultdict(list)

        if self.tests_e2e_dir.exists():
            for test_file in self.tests_e2e_dir.glob("test_*.py"):
                workflow_refs = self._find_workflow_references_in_file(test_file)
                for workflow_class in workflow_refs:
                    tests[workflow_class].append(str(test_file.relative_to(self.project_root)))

        return tests

    def _find_workflow_references_in_file(self, file_path: Path) -> Set[str]:
        """Find workflow class references in a test file."""
        workflow_refs = set()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

                # Look for workflow imports and usage
                patterns = [
                    r"from\s+.*\.(\w+Workflow)\s+import",
                    r"import\s+.*\.(\w+Workflow)",
                    r"(\w+Workflow)\.execute\(",
                    r"(\w+Workflow)\.register_workflow\(",
                    r"(\w+Workflow)\.register_tasks\(",
                ]

                for pattern in patterns:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        workflow_refs.add(match.group(1))
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

        return workflow_refs

    def analyze(self) -> Dict:
        """Run complete analysis."""
        print("Discovering workflows...")
        self.workflows = self.discover_workflows()
        print(f"Found {len(self.workflows)} workflows")

        print("Finding API triggers...")
        self.api_triggers = self.find_api_triggers()
        print(f"Found API triggers for {len(self.api_triggers)} workflows")

        print("Finding integration tests...")
        self.integration_tests = self.find_integration_tests()
        print(f"Found integration tests for {len(self.integration_tests)} workflows")

        print("Finding E2E tests...")
        self.e2e_tests = self.find_e2e_tests()
        print(f"Found E2E tests for {len(self.e2e_tests)} workflows")

        return {
            "workflows": self.workflows,
            "api_triggers": dict(self.api_triggers),
            "integration_tests": dict(self.integration_tests),
            "e2e_tests": dict(self.e2e_tests),
        }

    def generate_matrix(self) -> str:
        """Generate markdown test matrix."""
        lines = []
        lines.append("# Workflow Test Matrix")
        lines.append("")
        lines.append("Generated for Phase 11.1 - Workflow and Test Inventory")
        lines.append("")
        lines.append("## Overview")
        lines.append("")
        lines.append("This matrix maps workflows to their API trigger points and test coverage.")
        lines.append("")
        lines.append("## Matrix")
        lines.append("")
        lines.append("| Workflow | API Trigger Path | Integration Tests | E2E Tests |")
        lines.append("|----------|-----------------|-------------------|-----------|")

        # Get all unique workflows
        all_workflows = set(self.workflows.keys())
        all_workflows.update(self.api_triggers.keys())
        all_workflows.update(self.integration_tests.keys())
        all_workflows.update(self.e2e_tests.keys())

        for workflow_class in sorted(all_workflows):
            workflow_info = self.workflows.get(workflow_class, {})
            workflow_name = workflow_info.get("workflow_name", workflow_class)

            # API triggers
            triggers = self.api_triggers.get(workflow_class, [])
            api_paths = []
            if triggers:
                for trigger in triggers:
                    api_path = trigger.get("api_path", "unknown")
                    func = trigger.get("function", "")
                    if api_path != "unknown":
                        api_paths.append(f"{api_path} ({func})")
                    else:
                        api_paths.append(f"{trigger['file']}:{trigger['function']}")
            api_paths_str = "<br>".join(api_paths) if api_paths else "N/A"

            # Integration tests
            int_tests = self.integration_tests.get(workflow_class, [])
            int_tests_str = "<br>".join(int_tests) if int_tests else "N/A"

            # E2E tests
            e2e_tests = self.e2e_tests.get(workflow_class, [])
            e2e_tests_str = "<br>".join(e2e_tests) if e2e_tests else "N/A"

            lines.append(
                f"| {workflow_class}<br>({workflow_name}) | {api_paths_str} | {int_tests_str} | {e2e_tests_str} |"
            )

        return "\n".join(lines)


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    analyzer = WorkflowAnalyzer(project_root)

    results = analyzer.analyze()

    # Generate matrix
    matrix_md = analyzer.generate_matrix()

    # Save results
    artifacts_dir = project_root / "openspec" / "changes" / "workflows1" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON data
    with open(artifacts_dir / "workflow_analysis.json", "w") as f:
        json.dump(results, f, indent=2)

    # Save matrix
    with open(artifacts_dir / "WORKFLOW_TEST_MATRIX.md", "w") as f:
        f.write(matrix_md)

    print(f"\nResults saved to:")
    print(f"  - {artifacts_dir / 'workflow_analysis.json'}")
    print(f"  - {artifacts_dir / 'WORKFLOW_TEST_MATRIX.md'}")

    print("\n" + "=" * 80)
    print(matrix_md)
    print("=" * 80)


if __name__ == "__main__":
    main()
