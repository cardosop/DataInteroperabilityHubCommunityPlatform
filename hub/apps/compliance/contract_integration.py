"""
Compliance Service Integration with Contract Compliance Policy (GAP-8.2.2).

Reads compliance policy from HubContract and integrates it with compliance service execution.
Validates contract terms schema before use (5.4.2); invalid payloads are rejected with 400 at API boundary.
"""

from typing import Any

from hub.apps.contracts.models import Contract


class ContractComplianceSchemaError(Exception):
    """Raised when contract compliance payload does not match expected schema (5.4.2)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


def validate_contract_compliance_payload(hub_contract: dict[str, Any]) -> None:
    """
    Validate hub_contract (or its privacy_compliance section) for compliance use (5.4.2).
    Raises ContractComplianceSchemaError if invalid; use at API boundary and return 400.
    """
    if not isinstance(hub_contract, dict):
        raise ContractComplianceSchemaError(
            "Contract compliance payload must be a JSON object",
            details={"type": type(hub_contract).__name__},
        )
    section = hub_contract.get("privacy_compliance")
    if section is None:
        return
    if not isinstance(section, dict):
        raise ContractComplianceSchemaError(
            "privacy_compliance must be a JSON object",
            details={"privacy_compliance_type": type(section).__name__},
        )
    if "contains_personal_data" in section and not isinstance(
        section["contains_personal_data"], bool
    ):
        raise ContractComplianceSchemaError(
            "privacy_compliance.contains_personal_data must be a boolean",
            details={"value": section["contains_personal_data"]},
        )
    for list_key in ("personal_data_categories", "jurisdictions", "legal_bases"):
        if list_key in section and section[list_key] is not None:
            if not isinstance(section[list_key], list):
                raise ContractComplianceSchemaError(
                    f"privacy_compliance.{list_key} must be a list",
                    details={list_key: type(section[list_key]).__name__},
                )
            for i, item in enumerate(section[list_key]):
                if not isinstance(item, str):
                    raise ContractComplianceSchemaError(
                        f"privacy_compliance.{list_key}[{i}] must be a string",
                        details={list_key: item},
                    )
    if "retention_policy" in section and section["retention_policy"] is not None:
        if not isinstance(section["retention_policy"], dict):
            raise ContractComplianceSchemaError(
                "privacy_compliance.retention_policy must be an object or null",
                details={"retention_policy_type": type(section["retention_policy"]).__name__},
            )


# ---------------------------------------------------------------------------
# Regulation key aliases (19.10.7) — mirrored from
# services/compliance-service/regulations/__init__.py
# ---------------------------------------------------------------------------

#: Maps legacy/variant regulation keys to canonical keys.
#: Keep in sync with REGULATION_KEY_ALIASES in the compliance-service package.
REGULATION_KEY_ALIASES: dict = {
    # APAC
    "PIPL": "PIPL_CN",
    "PIPL_CHINA": "PIPL_CN",
    # Americas
    "CCPA_CPRA": "CCPA",
    "CCPA/CPRA": "CCPA",
    # APAC — Australia
    "PRIVACY_ACT": "PRIVACY_ACT_AU",
}

# ---------------------------------------------------------------------------
# Import vocabulary mappings - handle import path with hyphen
import os
import sys

semantic_service_path = os.path.join(
    os.path.dirname(__file__), "../../../services/semantic-service"
)
if semantic_service_path not in sys.path:
    sys.path.insert(0, semantic_service_path)
try:
    from vocabulary_mappings import get_dpv_category, get_dpv_jurisdiction, get_dpv_legal_basis
except ImportError:

    def get_dpv_category(category):
        return None

    def get_dpv_jurisdiction(jurisdiction):
        return None

    def get_dpv_legal_basis(basis):
        return None


class ContractCompliancePolicyExtractor:
    """
    Extracts compliance policy from HubContract and converts it to compliance service parameters.
    """

    @staticmethod
    def extract_compliance_policy(contract: Contract) -> dict[str, Any]:
        """
        Extract compliance policy from contract's HubContract JSON.
        Validates schema before use (5.4.2); raises ContractComplianceSchemaError if invalid.

        Args:
            contract: Contract instance

        Returns:
            Dictionary with:
            - contains_personal_data: Boolean
            - personal_data_categories: List of category strings
            - jurisdictions: List of jurisdiction strings
            - legal_bases: List of legal basis strings
            - retention_policy: Retention policy dictionary
        """
        hub_contract = contract.hub_contract_json or {}
        validate_contract_compliance_payload(hub_contract)
        compliance_section = hub_contract.get("privacy_compliance", {})

        return {
            "contains_personal_data": compliance_section.get("contains_personal_data", False),
            "personal_data_categories": compliance_section.get("personal_data_categories", []),
            "jurisdictions": compliance_section.get("jurisdictions", []),
            "legal_bases": compliance_section.get("legal_bases", []),
            "retention_policy": compliance_section.get("retention_policy"),
        }

    @staticmethod
    def get_targeted_pii_categories(contract: Contract) -> list[str]:
        """
        Get targeted PII categories from contract for focused detection (GAP-8.2.2).

        Args:
            contract: Contract instance

        Returns:
            List of PII category strings for targeted detection
        """
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(contract)
        return policy.get("personal_data_categories", [])

    @staticmethod
    def get_regulatory_mapping(contract: Contract) -> list[str]:
        """
        Get jurisdictions from contract for regulatory mapping (GAP-8.2.2).

        Normalises legacy key strings via REGULATION_KEY_ALIASES before
        returning so downstream callers always receive canonical keys
        (e.g. "PIPL" -> "PIPL_CN", "CCPA_CPRA" -> "CCPA").

        Args:
            contract: Contract instance

        Returns:
            List of canonical jurisdiction strings (GDPR, LGPD, CCPA…)
        """
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(contract)
        raw: list[str] = policy.get("jurisdictions", [])
        return [REGULATION_KEY_ALIASES.get(j, j) for j in raw]

    @staticmethod
    def get_legal_bases(contract: Contract) -> list[str]:
        """
        Get legal bases from contract for compliance reporting (GAP-8.2.2).

        Args:
            contract: Contract instance

        Returns:
            List of legal basis strings (CONSENT, CONTRACT, etc.)
        """
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(contract)
        return policy.get("legal_bases", [])

    @staticmethod
    def get_retention_policy(contract: Contract) -> dict[str, Any] | None:
        """
        Get retention policy from contract for data retention enforcement (GAP-8.2.2).

        Args:
            contract: Contract instance

        Returns:
            Retention policy dictionary with period and notes, or None
        """
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(contract)
        return policy.get("retention_policy")

    @staticmethod
    def map_categories_to_dpv(categories: list[str]) -> list[str]:
        """
        Map personal data categories to DPV vocabulary terms (GAP-8.2.2).

        Args:
            categories: List of category strings

        Returns:
            List of DPV category identifiers
        """
        dpv_categories = []
        for category in categories:
            dpv_term = get_dpv_category(category)
            if dpv_term:
                # Extract the local name from the URIRef
                dpv_categories.append(
                    str(dpv_term).split("#")[-1] if "#" in str(dpv_term) else category
                )
            else:
                # Keep original if no mapping found
                dpv_categories.append(category)
        return dpv_categories

    @staticmethod
    def map_jurisdictions_to_dpv(jurisdictions: list[str]) -> list[str]:
        """
        Map jurisdictions to DPV vocabulary terms (GAP-8.2.2).

        Args:
            jurisdictions: List of jurisdiction strings

        Returns:
            List of DPV jurisdiction identifiers
        """
        dpv_jurisdictions = []
        for jurisdiction in jurisdictions:
            dpv_term = get_dpv_jurisdiction(jurisdiction)
            if dpv_term:
                # Extract the local name from the URIRef
                dpv_jurisdictions.append(
                    str(dpv_term).split("#")[-1] if "#" in str(dpv_term) else jurisdiction
                )
            else:
                # Keep original if no mapping found
                dpv_jurisdictions.append(jurisdiction)
        return dpv_jurisdictions
