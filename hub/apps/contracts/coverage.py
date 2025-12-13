"""
Coverage metrics for ODCS normalization.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from .models import OriginalSpecType


@dataclass
class SectionCoverage:
    """Coverage details for a HubContract section."""

    name: str
    required_fields: Set[str]
    optional_fields: Set[str]
    present_required: Set[str] = field(default_factory=set)
    present_optional: Set[str] = field(default_factory=set)

    @property
    def missing_required(self) -> Set[str]:
        return self.required_fields - self.present_required

    @property
    def missing_optional(self) -> Set[str]:
        return self.optional_fields - self.present_optional

    @property
    def required_score(self) -> float:
        if not self.required_fields:
            return 1.0
        return len(self.present_required) / len(self.required_fields)

    @property
    def optional_score(self) -> float:
        if not self.optional_fields:
            return 1.0
        return len(self.present_optional) / len(self.optional_fields)

    def score(self, required_weight: float = 0.7) -> float:
        """
        Weighted score to emphasize required fields while still accounting for optional coverage.
        """
        required_weight = min(max(required_weight, 0.0), 1.0)
        optional_weight = 1.0 - required_weight
        return (self.required_score * required_weight) + (self.optional_score * optional_weight)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "required_fields": sorted(self.required_fields),
            "optional_fields": sorted(self.optional_fields),
            "present_required": sorted(self.present_required),
            "present_optional": sorted(self.present_optional),
            "missing_required": sorted(self.missing_required),
            "missing_optional": sorted(self.missing_optional),
            "required_score": self.required_score,
            "optional_score": self.optional_score,
            "score": self.score(),
        }


@dataclass
class CoverageResult:
    """Overall coverage report."""

    spec_type: str
    spec_version: str
    overall: float
    sections: Dict[str, SectionCoverage]
    unmapped_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_type": self.spec_type,
            "spec_version": self.spec_version,
            "overall": self.overall,
            "sections": {name: section.to_dict() for name, section in self.sections.items()},
            "unmapped_fields": self.unmapped_fields,
        }


# Definition of ODCS sections and expected fields
ODCS_SECTION_SPEC: Dict[str, Dict[str, Iterable[str]]] = {
    "info": {
        "required": {"name"},
        "optional": {"description", "version", "status", "domain", "tenant", "dataProduct", "links", "authoritativeDefinitions", "owners", "tags"},
    },
    "schema": {
        "required": {"fields"},
        "optional": {"primary_key", "unique_constraints", "indexes"},
    },
    "models": {"required": set(), "optional": set()},
    "quality": {"required": set(), "optional": {"default_profile_key", "rules"}},
    "contact": {"required": set(), "optional": set()},
    "servers": {"required": set(), "optional": set()},
    "terms": {"required": set(), "optional": {"usage", "limitations", "billing", "support", "sla"}},
    "privacy_compliance": {
        "required": set(),
        "optional": {"contains_personal_data", "personal_data_categories", "jurisdictions", "legal_bases", "retention_policy"},
    },
    "lifecycle": {"required": set(), "optional": {"data_source", "refresh_cadence", "slas"}},
    "marketplace": {"required": set(), "optional": {"license_summary", "intended_use", "restricted_use"}},
    "original_spec": {"required": {"type", "version"}, "optional": {"conforms_to"}},
    "servicelevels": {"required": set(), "optional": set()},
}


def _field_is_present(section_data: Any, field_name: str) -> bool:
    value = None
    if isinstance(section_data, dict):
        value = section_data.get(field_name)
    if value is None:
        return False
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value.keys()) > 0
    if isinstance(value, str):
        return bool(value.strip())
    return True


def calculate_coverage(
    hub_contract: Dict[str, Any],
    spec_type: str = OriginalSpecType.ODCS,
    spec_version: Optional[str] = None,
    section_spec: Dict[str, Dict[str, Iterable[str]]] = ODCS_SECTION_SPEC,
) -> CoverageResult:
    """
    Calculate coverage metrics for a HubContract.
    """
    sections: Dict[str, SectionCoverage] = {}
    is_mapping = isinstance(hub_contract, dict)
    spec_version = spec_version or (hub_contract.get("original_spec", {}).get("version") if is_mapping else None) or "unknown"

    for section_name, spec in section_spec.items():
        section_data = hub_contract.get(section_name, {}) if isinstance(hub_contract, dict) else {}
        required = set(spec.get("required", []))
        optional = set(spec.get("optional", []))
        present_required = {field for field in required if _field_is_present(section_data, field)}
        present_optional = {field for field in optional if _field_is_present(section_data, field)}

        sections[section_name] = SectionCoverage(
            name=section_name,
            required_fields=required,
            optional_fields=optional,
            present_required=present_required,
            present_optional=present_optional,
        )

    # Overall score: average of section scores
    overall = sum(section.score() for section in sections.values()) / len(sections) if sections else 0.0

    known_sections = set(section_spec.keys())
    unmapped_fields = [field for field in hub_contract.keys() if field not in known_sections] if is_mapping else []

    return CoverageResult(
        spec_type=spec_type,
        spec_version=spec_version,
        overall=overall,
        sections=sections,
        unmapped_fields=sorted(unmapped_fields),
    )


def coverage_report(result: CoverageResult) -> str:
    """
    Human-readable coverage summary for logging or debugging.
    """
    lines = [f"Coverage for {result.spec_type} v{result.spec_version}: {result.overall:.2%}"]
    for name, section in result.sections.items():
        lines.append(
            f"- {name}: {section.score():.2%} "
            f"(required {section.required_score:.2%}, optional {section.optional_score:.2%}; "
            f"missing required: {', '.join(sorted(section.missing_required)) or 'none'})"
        )
    if result.unmapped_fields:
        lines.append(f"- Unmapped top-level fields: {', '.join(result.unmapped_fields)}")
    return "\n".join(lines)
