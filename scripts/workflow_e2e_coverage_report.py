#!/usr/bin/env python3
"""
Phase 6.10.2 — Workflow E2E Coverage Report

Generates workflow E2E test coverage reporting:
- Workflow coverage (which workflows are tested)
- Business rules coverage (which business rules are tested)
- Journey coverage (which journeys include workflow tests)
- Use case coverage (which use cases include workflow tests)

Output: workflow_coverage_report.md and workflow_coverage_report.json
Run from repo root: python scripts/workflow_e2e_coverage_report.py
"""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# All workflow types (WORKFLOW_NAME) from hub/apps/orchestration/workflows
ALL_WORKFLOW_TYPES = [
    "asset_creation",
    "contract_creation",
    "marketplace_publication",
    "product_creation",
    "dataset_creation",
    "scheduled_ingestion",
    "access_request",
    "compliance_reporting",
    "data_quality_check",
    "data_mesh",
    "version_creation",
    "virtualization_query_execution",
    "api_key_management",
    "model_training",
    "model_inference",
    "marketplace_sync",
]

# Manifest: workflow type -> list of (test_file, test_class_or_description)
WORKFLOW_COVERAGE = {
    "asset_creation": [
        ("test_workflow_business_rules_e2e.py", "TestAssetCreationWorkflowBusinessRulesE2E"),
        ("test_workflow_use_case_integration_e2e.py", "TestUC_AM_001_WorkflowIntegrationE2E"),
        ("test_workflow_user_journey_integration_e2e.py", "DPO-015 product_creation flow"),
    ],
    "contract_creation": [
        ("test_workflow_business_rules_e2e.py", "TestContractCreationWorkflowBusinessRulesE2E"),
        ("test_workflow_error_recovery_compensation_e2e.py", "retry/compensation/state recovery"),
        ("test_workflow_observability_business_rules_e2e.py", "metrics/events/logging/tracing"),
        (
            "test_workflow_security_business_rules_e2e.py",
            "tenant isolation, auth, input validation",
        ),
        ("test_workflow_use_case_integration_e2e.py", "TestUC_CM_001_WorkflowIntegrationE2E"),
        ("test_workflow_user_journey_integration_e2e.py", "DPO-001, DE-001"),
    ],
    "marketplace_publication": [
        (
            "test_workflow_business_rules_e2e.py",
            "TestMarketplacePublicationWorkflowBusinessRulesE2E",
        ),
        ("test_workflow_use_case_integration_e2e.py", "TestUC_MKT_001_WorkflowIntegrationE2E"),
        ("test_workflow_user_journey_integration_e2e.py", "DPO-002"),
    ],
    "product_creation": [
        ("test_workflow_business_rules_e2e.py", "TestProductCreationWorkflowBusinessRulesE2E"),
        (
            "test_workflow_performance_business_rules_e2e.py",
            "TestWorkflowPerformanceBusinessRulesE2E",
        ),
        ("test_workflow_user_journey_integration_e2e.py", "DPO-015, DE-014"),
    ],
    "dataset_creation": [
        ("test_workflow_business_rules_e2e.py", "TestDatasetCreationWorkflowBusinessRulesE2E"),
    ],
    "scheduled_ingestion": [
        ("test_workflow_business_rules_e2e.py", "TestScheduledIngestionWorkflowBusinessRulesE2E"),
    ],
    "access_request": [
        ("test_workflow_user_journey_integration_e2e.py", "TestDataConsumerWorkflowJourneysE2E"),
    ],
    "compliance_reporting": [
        (
            "test_workflow_user_journey_integration_e2e.py",
            "TestComplianceOfficerWorkflowJourneysE2E",
        ),
        ("test_workflow_use_case_integration_e2e.py", "TestComplianceUseCaseWorkflowE2E"),
    ],
    "data_quality_check": [
        ("test_workflow_user_journey_integration_e2e.py", "TestDataQualityWorkflowInJourneysE2E"),
        ("test_workflow_use_case_integration_e2e.py", "TestDataQualityUseCaseWorkflowE2E"),
    ],
    "data_mesh": [
        (
            "test_workflow_user_journey_integration_e2e.py",
            "TestDataMeshDomainOwnerWorkflowJourneysE2E",
        ),
    ],
    "version_creation": [
        ("test_workflow_use_case_integration_e2e.py", "via asset/version flows"),
    ],
    "virtualization_query_execution": [],
    "api_key_management": [],
    "model_training": [],
    "model_inference": [],
    "marketplace_sync": [],
}

# Journeys that include workflow E2E tests (from USER_JOURNEYS / Phase 6.8)
JOURNEY_COVERAGE = [
    (
        "DPO-001",
        "Contract creation (Data Product Owner)",
        "TestJOURNEY_DPO_001_WorkflowIntegrationE2E",
    ),
    ("DPO-002", "Marketplace publication", "TestJOURNEY_DPO_002_WorkflowIntegrationE2E"),
    (
        "DPO-015",
        "Product creation (ODPS product-first)",
        "TestJOURNEY_DPO_015_WorkflowIntegrationE2E",
    ),
    ("DE-001", "Contract creation programmatic", "TestJOURNEY_DE_001_WorkflowIntegrationE2E"),
    ("DE-014", "Product creation via API", "TestJOURNEY_DE_014_WorkflowIntegrationE2E"),
    (
        "Compliance Officer",
        "Compliance reporting workflow",
        "TestComplianceOfficerWorkflowJourneysE2E",
    ),
    ("Data Consumer", "Access request workflow", "TestDataConsumerWorkflowJourneysE2E"),
    ("Data Mesh Domain Owner", "Data mesh workflow", "TestDataMeshDomainOwnerWorkflowJourneysE2E"),
    ("Data Quality", "Data quality check workflow", "TestDataQualityWorkflowInJourneysE2E"),
]

# Use cases that include workflow E2E tests (from USE_CASES / Phase 6.9)
USE_CASE_COVERAGE = [
    ("UC-AM-001", "Create Asset via Data-First Flow", "TestUC_AM_001_WorkflowIntegrationE2E"),
    ("UC-CM-001", "Create Contract", "TestUC_CM_001_WorkflowIntegrationE2E"),
    ("UC-MKT-001", "Publish Asset to Marketplace", "TestUC_MKT_001_WorkflowIntegrationE2E"),
    ("UC-DQ-001", "Data Quality check workflow", "TestDataQualityUseCaseWorkflowE2E"),
    ("UC-COMP-001", "Compliance reporting workflow", "TestComplianceUseCaseWorkflowE2E"),
]

# Business rules coverage: test files that validate business rules in workflow context
BUSINESS_RULES_COVERAGE = [
    (
        "test_workflow_business_rules_e2e.py",
        "Product, Contract, Asset, Marketplace, Dataset, Scheduled Ingestion BR",
    ),
    (
        "test_workflow_observability_business_rules_e2e.py",
        "Metrics, events, logging, tracing with BR",
    ),
    (
        "test_workflow_security_business_rules_e2e.py",
        "Tenant isolation, authorization, input validation, BR validation",
    ),
    (
        "test_workflow_error_recovery_compensation_e2e.py",
        "Retry, compensation, state recovery, validation behavior",
    ),
    ("test_workflow_performance_business_rules_e2e.py", "Validation overhead, throughput with BR"),
    ("test_workflow_user_journey_integration_e2e.py", "All journey workflows with BR validation"),
    ("test_workflow_use_case_integration_e2e.py", "All use case workflows with BR validation"),
]


def _repo_root() -> Path:
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent


def _count_workflows_with_e2e() -> int:
    return sum(1 for w in ALL_WORKFLOW_TYPES if WORKFLOW_COVERAGE.get(w))


def _workflow_coverage_pct() -> float:
    n = len(ALL_WORKFLOW_TYPES)
    covered = _count_workflows_with_e2e()
    return (100.0 * covered / n) if n else 0.0


def build_report_data() -> dict:
    workflows_tested = [w for w in ALL_WORKFLOW_TYPES if WORKFLOW_COVERAGE.get(w)]
    workflows_untested = [w for w in ALL_WORKFLOW_TYPES if not WORKFLOW_COVERAGE.get(w)]
    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "workflow_coverage": {
            "all_workflow_types": ALL_WORKFLOW_TYPES,
            "tested": workflows_tested,
            "untested": workflows_untested,
            "total": len(ALL_WORKFLOW_TYPES),
            "tested_count": len(workflows_tested),
            "coverage_pct": round(_workflow_coverage_pct(), 1),
            "details": {
                w: [{"file": f, "class_or_desc": c} for f, c in WORKFLOW_COVERAGE.get(w, [])]
                for w in ALL_WORKFLOW_TYPES
            },
        },
        "business_rules_coverage": [
            {"file": f, "description": d} for f, d in BUSINESS_RULES_COVERAGE
        ],
        "journey_coverage": [
            {"id": j[0], "description": j[1], "test_class": j[2]} for j in JOURNEY_COVERAGE
        ],
        "use_case_coverage": [
            {"id": u[0], "description": u[1], "test_class": u[2]} for u in USE_CASE_COVERAGE
        ],
    }


def write_md(report_dir: Path, data: dict) -> None:
    out = report_dir / "workflow_coverage_report.md"
    w = data["workflow_coverage"]
    lines = [
        "# Workflow E2E Test Coverage Report",
        "",
        f"Generated: {data['generated_at']}",
        "",
        "## 1. Workflow coverage",
        "",
        f"- **Total workflow types**: {w['total']}",
        f"- **Tested in E2E**: {w['tested_count']}",
        f"- **Coverage**: {w['coverage_pct']}%",
        "",
        "### Tested workflows",
        "",
    ]
    for name in w["tested"]:
        details = w["details"].get(name, [])
        lines.append(f"- **{name}**: {', '.join(d['file'] for d in details)}")
    lines.extend(["", "### Not covered by workflow E2E (unit/integration elsewhere)", ""])
    for name in w["untested"]:
        lines.append(f"- {name}")
    lines.extend(
        [
            "",
            "## 2. Business rules coverage",
            "",
            "Tests that validate business rules in workflow context:",
            "",
        ]
    )
    for br in data["business_rules_coverage"]:
        lines.append(f"- `{br['file']}`: {br['description']}")
    lines.extend(
        [
            "",
            "## 3. Journey coverage",
            "",
            "User journeys that include workflow E2E tests:",
            "",
        ]
    )
    for j in data["journey_coverage"]:
        lines.append(f"- **{j['id']}** ({j['description']}): `{j['test_class']}`")
    lines.extend(
        [
            "",
            "## 4. Use case coverage",
            "",
            "Use cases that include workflow E2E tests:",
            "",
        ]
    )
    for u in data["use_case_coverage"]:
        lines.append(f"- **{u['id']}** ({u['description']}): `{u['test_class']}`")
    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}")


def write_json(report_dir: Path, data: dict) -> None:
    out = report_dir / "workflow_coverage_report.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {out}")


def main() -> int:
    root = _repo_root()
    report_dir = root / "tests" / "e2e"
    if not report_dir.is_dir():
        report_dir = root
    os.chdir(root)
    data = build_report_data()
    write_md(report_dir, data)
    write_json(report_dir, data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
