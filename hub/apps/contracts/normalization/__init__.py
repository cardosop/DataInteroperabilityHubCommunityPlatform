"""
ODPS Normalization Module

Provides normalization of ODPS (Open Data Product Standard) documents to HubContract format.
"""

import json

from hub.apps.contracts.models import NormalizationStatus
from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
from hub.apps.contracts.normalization_engine import (
    _NORMALIZER_REGISTRY,
    NormalizationResult,
    ODCSNormalizer,
    SpecNormalizer,
    _calculate_normalization_coverage,
    _determine_normalization_status,
    _reset_normalizer_registry,
    detect_spec_type,
    get_normalizer,
    normalize_contract,
    parse_contract,
    register_normalizer,
    validate_hubcontract_schema,
)


# Backward compatibility wrapper for deprecated normalize_odcs_to_hubcontract function
def normalize_odcs_to_hubcontract(odcs_contract_dict):
    """
    Backward compatibility wrapper for deprecated normalize_odcs_to_hubcontract function.

    This function maintains the old API signature for tests that haven't been updated yet.
    It wraps normalize_contract() to provide the same return signature.

    Args:
        odcs_contract_dict: ODCS contract as a dictionary

    Returns:
        Tuple of (hub_contract_dict, status, errors, warnings)
    """
    hub_contract, _spec_type, _spec_version, status, errors, warnings = normalize_contract(
        raw_contract=json.dumps(odcs_contract_dict), format="JSON", spec_type="ODCS"
    )
    return hub_contract, status, errors, warnings


__all__ = [
    "_NORMALIZER_REGISTRY",
    "NormalizationResult",
    "NormalizationStatus",  # Re-exported from models
    "ODCSNormalizer",
    "ODPSNormalizer",
    "SpecNormalizer",
    "_calculate_normalization_coverage",  # For testing
    "_determine_normalization_status",  # For testing
    "_reset_normalizer_registry",
    "detect_spec_type",  # For testing
    "get_normalizer",
    "normalize_contract",
    "normalize_odcs_to_hubcontract",  # Backward compatibility
    "parse_contract",
    "register_normalizer",
    "validate_hubcontract_schema",
]
