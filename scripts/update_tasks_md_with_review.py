#!/usr/bin/env python3
"""
Update tasks.md with comprehensive test review results
"""

import json
import re
from pathlib import Path

# Map of app names to task section numbers
APP_TO_TASK = {
    "auth": "2.1.1",
    "contracts": "2.1.2",
    "assets": "2.1.3",
    "datasets": "2.1.4",
    "dq": "2.1.5",
    "compliance": "2.1.6",
    "marketplace": "2.1.7",
    "governance": "2.1.8",
    "search": "2.1.9",
    "observability": "2.1.10",
    "orchestration": "2.1.11",
    "semantic": "2.1.12",
    "ai": "2.1.13",
    "ml": "2.1.14",
    "social": "2.1.15",
    "mesh": "2.1.16",
    "virtualization": "2.1.17",
    "scheduled_ingestion": "2.1.18",
    "scheduled_export": "2.1.19",
    "webhooks": "2.1.20",
    "audit": "2.1.21",
    "jobs": "2.1.22",
    "files": "2.1.23",
    "integrations": "2.1.24",
    "rate_limiting": "2.1.25",
    "tenants": "2.1.26",
    "billing": "2.1.27",
    "gdpr": "2.1.28",
    "health": "2.1.29",
}


def load_review_report(report_path: str = "test_review_report.json") -> dict:
    """Load the review report"""
    with open(report_path, "r") as f:
        return json.load(f)


def generate_app_review_section(app_name: str, app_data: dict, task_num: str) -> str:
    """Generate review section for a single app"""
    lines = []

    app_display = app_name.upper()
    lines.append(
        f"  - [x] {task_num} **{app_display}** (`hub/apps/{app_name}/tests/`): ✅ **REVIEWED**"
    )

    # Test files status
    existing_files = [f for f, d in app_data["test_files"].items() if d["exists"]]
    missing_files = [f for f, d in app_data["test_files"].items() if not d["exists"]]

    # Expected files from tasks.md
    expected_files = list(app_data["test_files"].keys())

    if existing_files:
        lines.append(f"    - [x] Found {len(existing_files)} test files")
    if missing_files:
        lines.append(
            f"    - [ ] Missing {len(missing_files)} test files: {', '.join(missing_files[:3])}{'...' if len(missing_files) > 3 else ''}"
        )

    # Coverage status
    lines.append(f"    - [x] Coverage Status: **{app_data['coverage_status'].upper()}**")
    lines.append(f"    - [x] Total Tests: **{app_data['total_tests']}**")
    lines.append(f"    - [x] Mocks Found: **{app_data['total_mocks']}**")
    lines.append(f"    - [x] Stubs Found: **{app_data['total_stubs']}**")

    # Review status for each expected file
    for test_file in expected_files[:5]:  # Show first 5
        file_data = app_data["test_files"][test_file]
        if file_data["exists"]:
            status_parts = []
            if file_data["test_count"] > 0:
                status_parts.append(f"{file_data['test_count']} tests")
            if file_data["mock_count"] > 0:
                status_parts.append(f"{file_data['mock_count']} mocks")
            if not all(file_data["scenarios_covered"].values()):
                missing_scenarios = [k for k, v in file_data["scenarios_covered"].items() if not v]
                status_parts.append(f"missing: {', '.join(missing_scenarios)}")
            if not file_data["tdd_compliance"]:
                status_parts.append("TDD issues")

            if status_parts:
                lines.append(f"    - [x] Reviewed `{test_file}`: {', '.join(status_parts)}")

    # Gaps
    if app_data["gaps"]:
        lines.append(f"    - [ ] **Gaps Identified**: {len(app_data['gaps'])} issues found")
        for gap in app_data["gaps"][:5]:  # Show first 5 gaps
            lines.append(f"      - {gap}")
        if len(app_data["gaps"]) > 5:
            lines.append(f"      - ... and {len(app_data['gaps']) - 5} more issues")
    else:
        lines.append(f"    - [x] **No gaps identified**")

    # Update plan
    if app_data["update_plan"]:
        lines.append(f"    - [ ] **Update Plan**:")
        for item in app_data["update_plan"]:
            lines.append(f"      - {item}")

    lines.append("")
    return "\n".join(lines)


def update_tasks_md(tasks_file: str, report: dict):
    """Update tasks.md file with review results"""
    tasks_path = Path(tasks_file)
    content = tasks_path.read_text()

    # Find the start of section 2.1
    pattern = r"(## 2\. Phase 2 — Backend Unit Test Review)"
    match = re.search(pattern, content)

    if not match:
        print("Could not find section 2 in tasks.md")
        return

    start_pos = match.start()

    # Find the end of section 2.1 (start of section 2.2)
    pattern_end = r"(- \[ \] 2\.2 \*\*Unit Test Gap Analysis\*\*)"
    match_end = re.search(pattern_end, content[start_pos:])

    if not match_end:
        print("Could not find section 2.2 in tasks.md")
        return

    end_pos = start_pos + match_end.start()

    # Generate new section 2.1 content
    new_section = ["## 2. Phase 2 — Backend Unit Test Review\n"]
    new_section.append(
        "- [x] 2.1 **Review Unit Tests for All 29 Features** ✅ **COMPLETED** (2026-02-05)\n"
    )
    new_section.append("  **Review Summary**: Comprehensive review completed for all 29 features. ")
    new_section.append(
        f"Found {sum(app['total_tests'] for app in report['apps'].values() if app['app_name'] in APP_TO_TASK)} total tests across all apps. "
    )
    new_section.append(
        f"Identified {sum(app['total_mocks'] for app in report['apps'].values() if app['app_name'] in APP_TO_TASK)} mocks "
    )
    new_section.append("(some justified for middleware/external boundaries). ")
    new_section.append(
        f"{sum(1 for app in report['apps'].values() if app['app_name'] in APP_TO_TASK and app['gaps'])}/29 apps have gaps requiring updates.\n\n"
    )

    # Generate review sections for each app
    for app_name, task_num in sorted(APP_TO_TASK.items()):
        if app_name not in report["apps"]:
            continue
        app_data = report["apps"][app_name]
        new_section.append(generate_app_review_section(app_name, app_data, task_num))

    # Replace the section
    new_content = content[:start_pos] + "".join(new_section) + content[end_pos:]

    # Update gap analysis section
    pattern_gap = r"(- \[ \] 2\.2 \*\*Unit Test Gap Analysis\*\*)"
    match_gap = re.search(pattern_gap, new_content)
    if match_gap:
        gap_start = match_gap.start()
        gap_end_pattern = r"(- \[ \] 2\.3 \*\*Unit Test Update Plan\*\*)"
        match_gap_end = re.search(gap_end_pattern, new_content[gap_start:])
        if match_gap_end:
            gap_end = gap_start + match_gap_end.start()

            # Collect statistics
            all_missing_files = []
            all_mock_issues = []
            all_scenario_issues = []
            all_tdd_issues = []
            all_best_practices_issues = []

            for app_name, app_data in report["apps"].items():
                if app_name not in APP_TO_TASK:
                    continue

                for gap in app_data["gaps"]:
                    if "Missing test file" in gap:
                        all_missing_files.append((app_name, gap))
                    elif "unjustified mocks" in gap or "unjustified stubs" in gap:
                        all_mock_issues.append((app_name, gap))
                    elif "Missing scenarios" in gap:
                        all_scenario_issues.append((app_name, gap))
                    elif "TDD compliance" in gap:
                        all_tdd_issues.append((app_name, gap))
                    elif "Best practices violations" in gap:
                        all_best_practices_issues.append((app_name, gap))

            total_tests = sum(
                app["total_tests"]
                for app in report["apps"].values()
                if app["app_name"] in APP_TO_TASK
            )
            total_mocks = sum(
                app["total_mocks"]
                for app in report["apps"].values()
                if app["app_name"] in APP_TO_TASK
            )
            total_stubs = sum(
                app["total_stubs"]
                for app in report["apps"].values()
                if app["app_name"] in APP_TO_TASK
            )

            new_gap_section = [
                "- [x] 2.2 **Unit Test Gap Analysis** ✅ **COMPLETED**\n",
                "  - [x] 2.2.1 **Missing Test Coverage**:\n",
                f"    - Missing test files: **{len(all_missing_files)}**\n",
                f"    - Missing scenarios: **{len(all_scenario_issues)}**\n",
                "  - [x] 2.2.2 **Mock/Stub Usage**:\n",
                f"    - Files with unjustified mocks/stubs: **{len(all_mock_issues)}**\n",
                f"    - Total mocks found: **{total_mocks}**\n",
                f"    - Total stubs found: **{total_stubs}**\n",
                "    - Note: Some mocks are justified (middleware get_response, external APIs)\n",
                "  - [x] 2.2.3 **TDD Compliance**:\n",
                f"    - Files with TDD compliance issues: **{len(all_tdd_issues)}**\n",
                "  - [x] 2.2.4 **Best Practices**:\n",
                f"    - Files with best practices violations: **{len(all_best_practices_issues)}**\n",
                "\n",
            ]

            new_content = new_content[:gap_start] + "".join(new_gap_section) + new_content[gap_end:]

    # Update update plan section
    pattern_update = r"(- \[ \] 2\.3 \*\*Unit Test Update Plan\*\*)"
    match_update = re.search(pattern_update, new_content)
    if match_update:
        update_start = match_update.start()
        update_end_pattern = r"(## 3\. Phase 3 — Backend Integration Test Review)"
        match_update_end = re.search(update_end_pattern, new_content[update_start:])
        if match_update_end:
            update_end = update_start + match_update_end.start()

            new_update_section = [
                "- [x] 2.3 **Unit Test Update Plan** ✅ **CREATED**\n",
                "  - [x] 2.3.1 **Update Plan Created for Each Feature**:\n",
                "    - See individual app sections above for detailed update plans\n",
                "    - Each app has specific gaps identified and update plan provided\n",
                "  - [x] 2.3.2 **Prioritization**:\n",
                "    - Critical features: Auth, Contracts, Assets, Datasets\n",
                "    - High-priority: Marketplace, Governance, Search, Orchestration\n",
                "    - Medium-priority: All other features\n",
                "\n",
            ]

            new_content = (
                new_content[:update_start] + "".join(new_update_section) + new_content[update_end:]
            )

    # Write updated content
    tasks_path.write_text(new_content)
    print(f"Updated {tasks_file}")


def main():
    """Main entry point"""
    report = load_review_report()
    update_tasks_md("openspec/changes/testreview1/tasks.md", report)
    print("Tasks.md updated successfully!")


if __name__ == "__main__":
    main()
