#!/usr/bin/env python3
"""
Generate tasks.md update based on comprehensive test review results
"""

import json

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
    with open(report_path) as f:
        return json.load(f)


def generate_review_summary(report: dict) -> str:
    """Generate markdown summary for tasks.md update"""
    lines = []

    lines.append("## 2. Phase 2 — Backend Unit Test Review - COMPLETED")
    lines.append("")
    lines.append("**Review Date**: " + report["review_date"])
    lines.append("**Total Apps Reviewed**: " + str(report["apps_reviewed"]))
    lines.append("")

    # Summary statistics
    total_tests = sum(app["total_tests"] for app in report["apps"].values())
    total_mocks = sum(app["total_mocks"] for app in report["apps"].values())
    total_stubs = sum(app["total_stubs"] for app in report["apps"].values())
    apps_with_gaps = sum(1 for app in report["apps"].values() if app["gaps"])

    lines.append("### Summary Statistics")
    lines.append("")
    lines.append(f"- **Total Tests Found**: {total_tests}")
    lines.append(f"- **Total Mocks Found**: {total_mocks}")
    lines.append(f"- **Total Stubs Found**: {total_stubs}")
    lines.append(f"- **Apps with Gaps**: {apps_with_gaps}/{len(report['apps'])}")
    lines.append("")

    # Review each app
    lines.append("- [x] 2.1 **Review Unit Tests for All 29 Features** ✅ **COMPLETED**")
    lines.append("")

    for app_name, task_num in sorted(APP_TO_TASK.items()):
        if app_name not in report["apps"]:
            continue

        app_data = report["apps"][app_name]
        lines.append(
            f"  - [x] {task_num} **{app_name.upper()}** (`hub/apps/{app_name}/tests/`): ✅ **REVIEWED**"
        )

        # Test files status
        existing_files = [f for f, d in app_data["test_files"].items() if d["exists"]]
        missing_files = [f for f, d in app_data["test_files"].items() if not d["exists"]]

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

        # Gaps
        if app_data["gaps"]:
            lines.append(f"    - [ ] **Gaps Identified**: {len(app_data['gaps'])} issues found")
            for gap in app_data["gaps"][:5]:  # Show first 5 gaps
                lines.append(f"      - {gap}")
            if len(app_data["gaps"]) > 5:
                lines.append(f"      - ... and {len(app_data['gaps']) - 5} more")
        else:
            lines.append("    - [x] **No gaps identified**")

        # Update plan
        if app_data["update_plan"]:
            lines.append("    - [ ] **Update Plan**:")
            for item in app_data["update_plan"]:
                lines.append(f"      - {item}")

        lines.append("")

    # Gap analysis section
    lines.append("- [x] 2.2 **Unit Test Gap Analysis** ✅ **COMPLETED**")
    lines.append("")

    # Collect all gaps by type
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

    lines.append("  - [x] 2.2.1 **Missing Test Coverage**:")
    lines.append(f"    - Missing test files: **{len(all_missing_files)}**")
    lines.append(f"    - Missing scenarios: **{len(all_scenario_issues)}**")
    lines.append("")

    lines.append("  - [x] 2.2.2 **Mock/Stub Usage**:")
    lines.append(f"    - Files with unjustified mocks/stubs: **{len(all_mock_issues)}**")
    lines.append(f"    - Total mocks found: **{total_mocks}**")
    lines.append(f"    - Total stubs found: **{total_stubs}**")
    lines.append("")

    lines.append("  - [x] 2.2.3 **TDD Compliance**:")
    lines.append(f"    - Files with TDD compliance issues: **{len(all_tdd_issues)}**")
    lines.append("")

    lines.append("  - [x] 2.2.4 **Best Practices**:")
    lines.append(
        f"    - Files with best practices violations: **{len(all_best_practices_issues)}**"
    )
    lines.append("")

    # Update plan section
    lines.append("- [x] 2.3 **Unit Test Update Plan** ✅ **CREATED**")
    lines.append("")
    lines.append("  - [x] 2.3.1 **Update Plan Created for Each Feature**:")
    lines.append("    - See individual app sections above for detailed update plans")
    lines.append("")
    lines.append("  - [x] 2.3.2 **Prioritization**:")
    lines.append("    - Critical features: Auth, Contracts, Assets, Datasets")
    lines.append("    - High-priority: Marketplace, Governance, Search, Orchestration")
    lines.append("    - Medium-priority: All other features")
    lines.append("")

    return "\n".join(lines)


def main():
    """Main entry point"""
    report = load_review_report()
    summary = generate_review_summary(report)

    # Write summary to file
    output_file = "test_review_summary_for_tasks.md"
    with open(output_file, "w") as f:
        f.write(summary)

    print(f"Summary generated: {output_file}")
    print("\n" + "=" * 80)
    print(summary)
    print("=" * 80)


if __name__ == "__main__":
    main()
