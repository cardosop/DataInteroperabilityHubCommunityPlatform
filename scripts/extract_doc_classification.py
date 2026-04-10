#!/usr/bin/env python3
"""Extract doc classification from audit report + current disk state.

Reads docs/documentation_audit_report.json (2026-01-26 audit) as a
heuristic input and walks the current docs/ tree on disk.  Emits
docs/mvpdocs/_audit/classification.yaml with one entry per file
mapping to one of eight audience/lifecycle categories.

Idempotent -- safe to re-run; overwrites the YAML each time.

Phase 217.0.1
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
AUDIT_JSON = DOCS_DIR / "documentation_audit_report.json"
OUTPUT_YAML = (
    DOCS_DIR / "mvpdocs" / "_audit" / "classification.yaml"
)

# Post-MVP gated namespaces (from hub/apps/api/mvp_mode.py)
POST_MVP_KEYWORDS = frozenset(
    {
        "baas",
        "virtualization",
        "mesh",
        "ml",
        "transformation",
        "scheduled-ingestion",
        "scheduled_ingestion",
        "scheduled-export",
        "scheduled_export",
        "social",
        "ai",
        "integrations",
        "model_serving",
        "model-serving",
    }
)

# Specific known internal-report filenames (stems)
_INTERNAL_REPORT_NAMES = frozenset(
    {
        "COMPREHENSIVE_FIXES_SUMMARY",
        "DOCKER_OPTIMIZATION_RESULTS",
        "MIGRATION_TESTS_COMPLETE_STATUS",
        "MOCK_MIGRATION_PROGRESS",
        "OPTIMIZATION_COMPLETE",
        "REVERSE_LOOKUP_ANALYSIS",
        "ROOT_CAUSE_FIXES_SUMMARY",
        "test_review_report",
        "test_review_summary_for_tasks",
    }
)

# Categories (output values)
CAT_MVP_USER = "mvp-user"
CAT_MVP_INTEGRATOR = "mvp-integrator"
CAT_MVP_OPERATOR = "mvp-operator"
CAT_MVP_STAKEHOLDER = "mvp-stakeholder"
CAT_INTERNAL_REPORT = "internal-report"
CAT_POST_MVP = "post-mvp"
CAT_ARCHIVE = "archive"
CAT_DUPLICATE = "duplicate"

VALID_CATEGORIES = frozenset(
    {
        CAT_MVP_USER,
        CAT_MVP_INTEGRATOR,
        CAT_MVP_OPERATOR,
        CAT_MVP_STAKEHOLDER,
        CAT_INTERNAL_REPORT,
        CAT_POST_MVP,
        CAT_ARCHIVE,
        CAT_DUPLICATE,
    }
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _load_audit_categories() -> dict[str, str]:
    """Return {relative_path: audit_category} from the audit JSON."""
    if not AUDIT_JSON.exists():
        return {}
    with open(AUDIT_JSON) as f:
        data = json.load(f)
    result: dict[str, str] = {}
    for category, files in data.get("files_by_category", {}).items():
        for fname in files:
            result[fname] = category
    return result


def _is_post_mvp(rel_path: str) -> bool:
    """Check if a doc path signals post-MVP content."""
    lower = rel_path.lower()
    return any(kw in lower for kw in POST_MVP_KEYWORDS)


def _classify_file(  # noqa: C901
    rel_path: str,
    audit_cat: str | None,
) -> tuple[str, str]:
    """Classify a single doc file into one of eight categories.

    Returns (category, note) where note explains the decision.
    """
    stem = Path(rel_path).stem
    lower = rel_path.lower()

    # 1. Deprecated / archive directories
    if "deprecated-doc/" in rel_path:
        return CAT_ARCHIVE, "under deprecated-doc/"

    # 2. Internal reports (specific known files)
    if stem in _INTERNAL_REPORT_NAMES:
        return CAT_INTERNAL_REPORT, "known internal report (D158)"
    if "UI_ANALYSIS_" in stem:
        return CAT_INTERNAL_REPORT, "UI analysis snapshot"

    # 3. Documentation templates
    if "documentation_templates/" in rel_path:
        return CAT_ARCHIVE, "template, not user-facing content"

    # 4. Audit artifacts → archive
    if "api-audit/" in rel_path:
        return CAT_ARCHIVE, "api-audit artifact, consolidated"

    # 5. The audit report itself is internal
    if rel_path == "documentation_audit_report.json":
        return CAT_INTERNAL_REPORT, "audit metadata"

    # 6. Known stakeholder files whose names contain post-MVP
    #    keywords but are actually MVP-scope
    if stem == "CRITICAL_UC_JOURNEY_IDS":
        return (
            CAT_MVP_STAKEHOLDER,
            "canonical UC/journey registry (both MVP+post-MVP)",
        )

    # 6a. Specific runbook overrides (manual audit 217.3.2)
    if rel_path == "runbooks/KYC_PROVIDER_INTEGRATION.md":
        return CAT_POST_MVP, "KYC provider is external integration"
    if stem in ("fuseki-pv-migration", "MIGRATION_PHASE_1"):
        return CAT_INTERNAL_REPORT, "one-off migration runbook"

    # 7. Post-MVP content
    if _is_post_mvp(rel_path):
        return CAT_POST_MVP, "post-MVP gated namespace in path"

    # 8. Runbooks → operator
    if "runbooks/" in lower or "runbook" in lower:
        return CAT_MVP_OPERATOR, "runbook content"
    operator_kws = (
        "deploy",
        "operation",
        "infrastructure",
        "docker",
        "security_finding",
        "evidence_collection",
        "operator",
    )
    if any(kw in lower for kw in operator_kws):
        return CAT_MVP_OPERATOR, "operator keyword match"

    # 9. API/SDK/CLI references → integrator
    integrator_kws = (
        "api_reference",
        "api_standard",
        "api_endpoint",
        "api_error",
        "api_naming",
        "api_best",
        "api_version",
        "api_testing",
        "api_usability",
        "webhook_api",
        "websocket_api",
        "graphql_api",
        "sdk",
        "cli",
    )
    if any(kw in lower for kw in integrator_kws):
        return CAT_MVP_INTEGRATOR, "API/SDK/CLI reference"

    # 10. Test/coverage/gap analysis → internal report
    internal_kws = (
        "test_execution",
        "test_suite",
        "gap_analysis",
        "test_review",
        "skip_registry",
        "mypy_ratchet",
        "full_test_suite",
        "post_deploy_test",
    )
    if any(kw in lower for kw in internal_kws):
        return CAT_INTERNAL_REPORT, "test/analysis artifact"

    # 11. Product guide / features / personas → stakeholder
    stakeholder_kws = (
        "product_guide",
        "mvp_feature",
        "mvp_persona",
        "capability-degradation",
    )
    if any(kw in lower for kw in stakeholder_kws):
        return CAT_MVP_STAKEHOLDER, "product/feature docs"

    # 12. Developer guide → integrator
    dev_kws = ("developer_guide", "testing_guide", "style_guide")
    if any(kw in lower for kw in dev_kws):
        return CAT_MVP_INTEGRATOR, "developer reference"

    # 13. User-facing guides
    user_kws = (
        "frontend_guide",
        "user_guide",
        "marketplace_and_connector",
        "data_contract",
    )
    if any(kw in lower for kw in user_kws):
        return CAT_MVP_USER, "user-facing guide"

    # 14. Architecture → stakeholder
    if "architecture" in lower or "design" in lower:
        return CAT_MVP_STAKEHOLDER, "architecture/design doc"

    # 15. Security / compliance → operator
    if "security" in lower or "compliance" in lower:
        return CAT_MVP_OPERATOR, "security/compliance content"

    # 16. Connectors subdir → integrator
    if "connectors/" in rel_path:
        return CAT_MVP_INTEGRATOR, "connector development docs"

    # 17. MVP overlay → user
    if "mvpdocs/" in rel_path:
        return CAT_MVP_USER, "MVP overlay content"

    # 18. Secrets docs → operator
    if "secret" in lower:
        return CAT_MVP_OPERATOR, "secrets management"

    # 19. Critical UC / journey IDs → stakeholder
    if "critical_uc" in lower or "journey" in lower:
        return CAT_MVP_STAKEHOLDER, "use-case/journey registry"

    # 20. README → user
    if stem.upper() == "README":
        return CAT_MVP_USER, "readme"

    # 21. Fallback: use audit category if available
    if audit_cat:
        mapping = {
            "api": CAT_MVP_INTEGRATOR,
            "architecture": CAT_MVP_STAKEHOLDER,
            "developer": CAT_MVP_INTEGRATOR,
            "operational": CAT_MVP_OPERATOR,
            "user": CAT_MVP_USER,
            "other": CAT_INTERNAL_REPORT,
        }
        cat = mapping.get(audit_cat, CAT_INTERNAL_REPORT)
        return cat, f"audit-category fallback ({audit_cat})"

    return CAT_INTERNAL_REPORT, "unclassified fallback"


def _yaml_escape(s: str) -> str:
    """Escape a YAML string value if needed."""
    if any(c in s for c in ":#{}[]&*!|>'\",@`"):
        return f'"{s}"'
    return s


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------


def main() -> int:
    audit_cats = _load_audit_categories()

    entries: list[tuple[str, str, str]] = []
    for root, _dirs, files in os.walk(DOCS_DIR):
        for fname in sorted(files):
            full = Path(root) / fname
            rel = str(full.relative_to(DOCS_DIR))
            if rel.startswith("mvpdocs/_audit/classification"):
                continue
            cat, note = _classify_file(rel, audit_cats.get(rel))
            entries.append((rel, cat, note))

    entries.sort(key=lambda e: e[0])

    # Write YAML (hand-formatted to avoid PyYAML dependency)
    OUTPUT_YAML.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "# Documentation classification — auto-generated by"
        " scripts/extract_doc_classification.py",
        "# Source audit: docs/documentation_audit_report.json"
        " (2026-01-26, 252 files cataloged)",
        f"# Current disk scan: {len(entries)} files classified",
        "# Categories: mvp-user | mvp-integrator |"
        " mvp-operator | mvp-stakeholder |",
        "#   internal-report | post-mvp | archive | duplicate",
        "#",
        "# Phase 217.0.1 — idempotent; re-run to refresh.",
        "",
        "files:",
    ]
    body: list[str] = []
    for rel_path, category, note in entries:
        body.append(
            f"  - path: {_yaml_escape(rel_path)}"
        )
        body.append(f"    category: {category}")
        body.append(f"    note: {_yaml_escape(note)}")

    content = "\n".join(header + body) + "\n"
    OUTPUT_YAML.write_text(content, encoding="utf-8")

    # Summary
    counts = Counter(cat for _, cat, _ in entries)
    out = OUTPUT_YAML.relative_to(REPO_ROOT)
    print(f"Classified {len(entries)} files -> {out}")
    for cat in sorted(VALID_CATEGORIES):
        print(f"  {cat}: {counts.get(cat, 0)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
