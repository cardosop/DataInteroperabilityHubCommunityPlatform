"""
ODPS Normalization Module

Provides normalization of ODPS (Open Data Product Standard) documents to HubContract format.
"""

import json

from hub.apps.contracts.normalization_engine import (
    NormalizationResult,
    SpecNormalizer,
    get_normalizer,
    register_normalizer,
    normalize_contract,
    parse_contract,
    validate_hubcontract_schema,
    ODCSNormalizer,
    _NORMALIZER_REGISTRY,
    _reset_normalizer_registry,
    _determine_normalization_status,
    _calculate_normalization_coverage,
    detect_spec_type,
)
from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
from hub.apps.contracts.models import NormalizationStatus


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
    hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
        raw_contract=json.dumps(odcs_contract_dict),
        format="JSON",
        spec_type="ODCS"
    )
    return hub_contract, status, errors, warnings


__all__ = [
    'NormalizationResult',
    'SpecNormalizer',
    'ODPSNormalizer',
    'ODCSNormalizer',
    'get_normalizer',
    'register_normalizer',
    'normalize_contract',
    'normalize_odcs_to_hubcontract',  # Backward compatibility
    'parse_contract',
    'validate_hubcontract_schema',
    'NormalizationStatus',  # Re-exported from models
    '_determine_normalization_status',  # For testing
    '_calculate_normalization_coverage',  # For testing
    'detect_spec_type',  # For testing
    '_NORMALIZER_REGISTRY',
    '_reset_normalizer_registry'
]
