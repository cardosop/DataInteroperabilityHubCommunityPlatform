#!/usr/bin/env python3
"""
283.6.6 / 284.E.5 — GA gate score regression check.

Reads the feature-flag registry and the GA readiness audit document to verify
every GA flag scores ≥70 (minimum bar) and the mean score ≥90.

The audit scores are embedded directly in this script as the authoritative
source until a machine-readable audit format is adopted (tracked: Phase 286).

Exit 0 when all GA flags pass; exit 1 when any flag scores below threshold.

Usage
-----
    python scripts/check_ga_gate_scores.py            # human-readable report
    python scripts/check_ga_gate_scores.py --json     # JSON output for CI
    python scripts/check_ga_gate_scores.py --strict   # require ≥95 per flag (future target)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))


def _load_registry():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "feature_flag_registry",
        _REPO_ROOT / "hub" / "apps" / "tenants" / "feature_flag_registry.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load feature_flag_registry module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["feature_flag_registry"] = module
    spec.loader.exec_module(module)
    return module.REGISTRY


# ── GA flag scores from docs/ga-readiness-audit-2026-05.md ──────────────
# Updated: 2026-05-16 (Phase 283.6.1)
# These MUST be kept in sync with the audit document.
# TODO(Phase 286): extract scores from a machine-readable YAML/JSON audit manifest.

GA_SCORES: dict[str, int] = {
    # ── 285.4 — scores updated for gap closure (runbooks + PRODUCT_GUIDE + CLI + E2E) ──
    "data_quality_enabled": 95,  # 285.4.9 — PRODUCT_GUIDE §DQ done
    "data_quality_advanced_enabled": 95,  # 285.4.10 — PRODUCT_GUIDE §DQ done
    "compliance_fail_closed_enabled": 96,
    "asset_creation_enabled": 96,  # 285.4.12 — PRODUCT_GUIDE §Assets done
    "datasets_enabled": 95,  # 285.4.4 — runbook RB-FLAG-004 + PRODUCT_GUIDE §Datasets done
    "files_enabled": 95,  # 285.4.5 — runbook RB-FLAG-004 + PRODUCT_GUIDE §Datasets done
    "compliance_consent_enabled": 95,
    "compliance_ropa_enabled": 95,  # 285.4.13 — PRODUCT_GUIDE §Compliance done
    "compliance_dpia_enabled": 95,  # 285.4.14 — PRODUCT_GUIDE §Compliance + E2E dpia-wizard-flow.spec.ts done
    "compliance_dsar_enabled": 95,
    "compliance_breach_enabled": 95,  # 285.4.15 — PRODUCT_GUIDE §Compliance + E2E breach-report-flow.spec.ts done
    "compliance_processor_agreements_enabled": 94,  # 285.4.6 — runbook RB-FLAG-007 + PRODUCT_GUIDE done
    "compliance_retention_enforcer_enabled": 94,  # 285.4.7 — runbook RB-FLAG-008 + PRODUCT_GUIDE done
    "compliance_audit_full_sampling": 95,  # 285.4.11 — runbook RB-FLAG-003 + PRODUCT_GUIDE done
    "compliance_intake_gate_enabled": 96,
    "semantic_memento_enabled": 93,  # 285.4.8 — PRODUCT_GUIDE + existing runbook done
    "semantic_inference_enabled": 93,  # 285.4.8 — PRODUCT_GUIDE + existing runbook done
    "semantic_custom_ontology_enabled": 93,  # 285.4.8 — PRODUCT_GUIDE + existing runbook done
    "semantic_ldn_enabled": 93,  # 285.4.8 — PRODUCT_GUIDE + existing runbook done
    "trust_signals_enabled": 92,  # 285.4.1 — runbook RB-FLAG-001 + PRODUCT_GUIDE §Trust Signals done
    "versioning_enabled": 94,  # 285.4.2 — CLI 247L + runbook RB-FLAG-006 + PRODUCT_GUIDE §Versioning done
    "workflows_enabled": 93,  # 285.4.3 — runbook RB-FLAG-002 + PRODUCT_GUIDE §Workflows done
    "federated_import_enabled": 90,
    "asset_auto_activate_on_gate_pass": 91,
    "semantic_search_enabled": 88,
    "semantic_graphql_ld_enabled": 92,
    "data_movement_enabled": 90,  # 285.6.4.5 — GA, dlt unified engine
    # ── 285.10 — warehouse-native DQ + Compliance ──
    "warehouse_dq_enabled": 95,  # 285.10.4.4.5 — CLI, SDK, RLS, Audit, E2E, A11y, Dark Mode, Error UX, i18n, Runbooks (3), Metrics, Docs
    "warehouse_compliance_enabled": 95,  # 285.10.4.4.5 — same 13-gate coverage as warehouse_dq_enabled
    # ── 285.11 — pipeline dependency graph ──
    "pipeline_dependency_enabled": 90,  # 285.11.6.4 — CLI, SDK, RLS, Throttle, Audit, Metrics, Runbooks (2), Error codes (6), Docs
    # ── Pre-existing GA flags (missing from earlier pass) ──
    "ml_enabled": 88,  # 285.9b.M.13 — CLI, SDK, RLS, Throttle, Audit, Metrics, Docs
    "transformation_enabled": 90,  # 285.9.1.0.4 — CLI, SDK, RLS, Throttle, Audit, Runbooks (4), Docs
    # ── 285.12.4 — Feature Completion flag promotions (CANARY→GA) ──
    "data_mesh_enabled": 85,  # 285.12.4.3 — CLI, SDK, RLS, Throttle, Audit, Metrics, Docs
    "baas_enabled": 85,  # 285.12.4.4 — CLI, SDK, RLS, Throttle, Audit, Metrics, Docs
    "virtualization_enabled": 85,  # 285.12.4.5 — CLI, SDK, RLS, Throttle, Audit, Metrics, Docs
}


def _classify(score: int, threshold: int = 70) -> Literal["PASS", "WARN", "FAIL"]:
    if score < 70:
        return "FAIL"
    if score >= threshold:
        return "PASS"
    return "WARN"


def _check(registry, min_score: int = 70) -> tuple[list[dict], float, bool]:
    """Returns (rows, mean_score, all_pass)."""
    rows: list[dict] = []
    ga_names = {f.name for f in registry if f.stage == "GA"}

    for name in sorted(ga_names):
        score = GA_SCORES.get(name)
        if score is None:
            rows.append(
                {
                    "name": name,
                    "score": None,
                    "classification": "UNSCORED",
                    "error": "missing from GA_SCORES — update check_ga_gate_scores.py",
                }
            )
            continue
        rows.append(
            {
                "name": name,
                "score": score,
                "classification": _classify(score, min_score),
            }
        )

    scored = [r for r in rows if r["score"] is not None]
    mean = sum(r["score"] for r in scored) / len(scored) if scored else 0.0
    # In strict mode (threshold ≥95), WARN also counts as failure.
    fail_classes = {"FAIL", "UNSCORED"}
    if min_score >= 95:
        fail_classes.add("WARN")
    all_pass = all(r["classification"] not in fail_classes for r in rows)
    return rows, mean, all_pass


def _format_human(rows: list[dict], mean: float) -> str:
    lines: list[str] = []
    lines.append(f"GA Gate Score Check — {datetime.now(tz=UTC).isoformat()}")
    lines.append(f"Mean score: {mean:.1f}")
    lines.append("")
    lines.append(f"{'FLAG':<50} {'SCORE':>6} {'STATUS':<10}")
    lines.append("-" * 68)
    for r in rows:
        score_str = str(r["score"]) if r["score"] is not None else "?"
        status = r["classification"]
        lines.append(f"{r['name']:<50} {score_str:>6} {status:<10}")
    lines.append("-" * 68)

    fails = [r for r in rows if r["classification"] == "FAIL"]
    warns = [r for r in rows if r["classification"] == "WARN"]
    unscored = [r for r in rows if r["classification"] == "UNSCORED"]
    passes = [r for r in rows if r["classification"] == "PASS"]

    lines.append(f"  PASS (≥95):  {len(passes)}")
    lines.append(f"  WARN (70–94): {len(warns)}")
    lines.append(f"  FAIL (<70):  {len(fails)}")
    lines.append(f"  UNSCORED:    {len(unscored)}")

    if unscored:
        lines.append("\nUNSCORED flags (add to GA_SCORES dict):")
        for r in unscored:
            lines.append(f"  - {r['name']}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="283.6.6 — GA gate score regression check.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require ≥95 per flag (future target; default is ≥70).",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=70,
        help="Minimum acceptable score (default: 70).",
    )
    args = parser.parse_args()

    registry = _load_registry()
    min_score = 95 if args.strict else args.min_score
    rows, mean, all_pass = _check(registry, min_score=min_score)

    if args.json:
        output = {
            "checked_at": datetime.now(tz=UTC).isoformat(),
            "mean_score": round(mean, 1),
            "min_threshold": min_score,
            "all_pass": all_pass,
            "flags": rows,
        }
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_format_human(rows, mean))

    if not all_pass:
        fails = [r for r in rows if r["classification"] in ("FAIL", "UNSCORED")]
        sys.stderr.write(
            f"\nFAIL: {len(fails)} GA flag(s) below minimum score ({min_score}). "
            "Update docs/ga-readiness-audit-2026-05.md with gap closure plan.\n"
        )
        return 1

    # Also enforce mean ≥90 as a soft target (warn only).
    if mean < 90:
        sys.stderr.write(
            f"\nWARNING: mean GA score ({mean:.1f}) is below the 90-point target. "
            "Continue closing gaps documented in the audit.\n"
        )

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
