"""
Build the canonical compliance **results** JSON for a ``ComplianceRun``.

Shared by ``GET …/runs/{id}/results/`` and export endpoints so wire format stays
single-sourced (Phase 231.8).
"""

from __future__ import annotations

from typing import Any

from hub.apps.compliance.models import ComplianceRun

from .results_wire import alert_dict_wire, legal_basis_violations_wire, regulation_summaries_wire


def build_compliance_run_results_payload(compliance_run: ComplianceRun) -> dict[str, Any]:
    column_findings = compliance_run.column_findings_json or []
    regulation_mapping = compliance_run.regulation_mapping_json or {}
    detected_categories = compliance_run.detected_categories_json or {}

    regulations_by_pii_type: dict[str, list[str]] = {}
    for reg_name, reg_info in regulation_mapping.items():
        if reg_name == "metadata":
            continue
        if not isinstance(reg_info, dict):
            continue
        if reg_info.get("applies") is False:
            continue
        for pii in reg_info.get("applicable_categories", []) or []:
            regulations_by_pii_type.setdefault(pii, []).append(reg_name)

    violations = []
    violation_details = []
    remediation_suggestions = []

    for finding in column_findings:
        column_name = finding.get("column") or finding.get("column_name", "Unknown")
        pii_types = finding.get("categories") or finding.get("pii_types", [])
        risk_score = finding.get("match_ratio") or finding.get("risk_score", 0.0)

        for pii_type in pii_types:
            violation = {
                "column": column_name,
                "pii_type": pii_type,
                "risk_score": risk_score,
                "severity": (
                    "HIGH" if risk_score > 0.7 else "MEDIUM" if risk_score > 0.4 else "LOW"
                ),
            }
            violations.append(violation)

            violation_detail = {
                "column": column_name,
                "pii_type": pii_type,
                "risk_score": risk_score,
                "severity": violation["severity"],
                "regulations_affected": sorted(regulations_by_pii_type.get(pii_type, [])),
                "detection_confidence": finding.get("confidence"),
                "sample_values": finding.get("sample_values", [])[:3],
            }
            violation_details.append(violation_detail)

            if pii_type in [
                "PII_DIRECT_EMAIL",
                "PII_DIRECT_PHONE",
                "PII_DIRECT_SSN",
                "PAYMENT_CARD",
            ]:
                remediation_suggestions.append(
                    {
                        "column": column_name,
                        "pii_type": pii_type,
                        "suggestion": (
                            f"Consider masking or redacting {pii_type} data in column {column_name}"
                        ),
                        "priority": "HIGH" if risk_score > 0.7 else "MEDIUM",
                    }
                )

    total_columns = len(column_findings) if column_findings else 1
    columns_with_pii = len(
        [f for f in column_findings if f.get("categories") or f.get("pii_types")]
    )
    columns_without_pii = total_columns - columns_with_pii

    compliance_score = 100.0
    pii_penalty = 0.0
    if total_columns > 0:
        pii_penalty = (columns_with_pii / total_columns) * 50
        compliance_score = max(0, 100 - pii_penalty)

    score_breakdown = {
        "total_columns": total_columns,
        "columns_with_pii": columns_with_pii,
        "columns_without_pii": columns_without_pii,
        "pii_detection_rate": columns_with_pii / total_columns if total_columns > 0 else 0,
        "base_score": 100,
        "pii_penalty": pii_penalty if total_columns > 0 else 0,
        "final_score": compliance_score,
    }

    risk_assessment = {
        "overall_risk_level": compliance_run.risk_level or "UNKNOWN",
        "risk_score": regulation_mapping.get("metering", {}).get("risk_score", 0.0),
        "allowed_to_store": compliance_run.allowed_to_store,
        "total_violations": len(violations),
        "high_severity_violations": len([v for v in violations if v["severity"] == "HIGH"]),
        "medium_severity_violations": len([v for v in violations if v["severity"] == "MEDIUM"]),
        "low_severity_violations": len([v for v in violations if v["severity"] == "LOW"]),
        "regulations_checked": compliance_run.regulations or [],
        "recommendations": [],
    }

    has_violations = len(violations) > 0
    if has_violations:
        if compliance_run.risk_level == "CRITICAL":
            risk_assessment["recommendations"].append(
                "Immediate action required: Data contains high-risk PII"
            )
        elif compliance_run.risk_level == "HIGH":
            risk_assessment["recommendations"].append(
                "Review and remediate high-risk PII detections"
            )
        elif compliance_run.risk_level == "MEDIUM":
            risk_assessment["recommendations"].append(
                "Consider implementing data masking for detected PII"
            )
    elif compliance_run.overall_status == "FAIL":
        risk_assessment["recommendations"].append(
            "Compliance check failed due to policy violations "
            "(e.g. missing legal basis). Review the issues section for details."
        )

    violation_timeline = []
    if compliance_run.completed_at:
        violation_timeline.append(
            {
                "timestamp": compliance_run.completed_at.isoformat(),
                "event": "Compliance scan completed",
                "violations_detected": len(violations),
                "risk_level": compliance_run.risk_level,
            }
        )

    return {
        "compliance_run_id": str(compliance_run.id),
        "overall_status": compliance_run.overall_status,
        "risk_level": compliance_run.risk_level,
        "allowed_to_store": compliance_run.allowed_to_store,
        "compliance_score": compliance_score,
        "score_breakdown": score_breakdown,
        "violations": violations,
        "violation_details": violation_details,
        "remediation_suggestions": remediation_suggestions,
        "risk_assessment": risk_assessment,
        "violation_timeline": violation_timeline,
        "regulations": compliance_run.regulations or [],
        "detected_categories": detected_categories,
        "column_findings": column_findings,
        "started_at": (
            compliance_run.started_at.isoformat() if compliance_run.started_at else None
        ),
        "completed_at": (
            compliance_run.completed_at.isoformat() if compliance_run.completed_at else None
        ),
        "cross_border_alert": alert_dict_wire(compliance_run.cross_border_alert),
        "localisation_alert": alert_dict_wire(compliance_run.localisation_alert),
        "legal_basis_violations": legal_basis_violations_wire(
            compliance_run.legal_basis_violations
        ),
        "regulation_summaries": regulation_summaries_wire(regulation_mapping),
    }
