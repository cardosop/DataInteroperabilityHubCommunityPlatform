"""
ODPS Normalization Module

Provides normalization of ODPS (Open Data Product Standard) documents to HubContract format.
"""

# Re-export classes from normalization.py module to make them available
# Import using importlib to avoid circular imports
import sys
import importlib.util
from pathlib import Path

# Get the path to normalization.py (parent directory)
_normalization_py_path = Path(__file__).parent.parent / 'normalization.py'

if _normalization_py_path.exists():
    # Load the .py file as a module
    # Note: Using importlib to load normalization.py as a separate module to avoid circular imports
    # The deprecation warning about __package__ != __spec__.parent is expected and harmless
    # as we're loading a .py file that's not part of the package structure
    _spec = importlib.util.spec_from_file_location('normalization_py_module', _normalization_py_path)
    _normalization_py_module = importlib.util.module_from_spec(_spec)
    _normalization_py_module.__package__ = 'hub.apps.contracts'
    _spec.loader.exec_module(_normalization_py_module)

    # Re-export the classes
    NormalizationResult = _normalization_py_module.NormalizationResult
    SpecNormalizer = _normalization_py_module.SpecNormalizer

    # Also export ODPSNormalizer from this package
    from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer

    # Re-export get_normalizer and register_normalizer from normalization.py
    get_normalizer = _normalization_py_module.get_normalizer
    register_normalizer = _normalization_py_module.register_normalizer

    # Re-export normalize_contract, parse_contract, and validate_hubcontract_schema
    normalize_contract = _normalization_py_module.normalize_contract
    parse_contract = _normalization_py_module.parse_contract
    validate_hubcontract_schema = _normalization_py_module.validate_hubcontract_schema

    # Re-export internal functions for testing
    if hasattr(_normalization_py_module, '_determine_normalization_status'):
        _determine_normalization_status = _normalization_py_module._determine_normalization_status
    if hasattr(_normalization_py_module, '_calculate_normalization_coverage'):
        _calculate_normalization_coverage = _normalization_py_module._calculate_normalization_coverage
    if hasattr(_normalization_py_module, 'detect_spec_type'):
        detect_spec_type = _normalization_py_module.detect_spec_type

    # Re-export ODCSNormalizer and registry utilities
    ODCSNormalizer = _normalization_py_module.ODCSNormalizer
    _NORMALIZER_REGISTRY = _normalization_py_module._NORMALIZER_REGISTRY
    _reset_normalizer_registry = _normalization_py_module._reset_normalizer_registry

    # Re-export NormalizationStatus from models (used by normalization.py)
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
        import json
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
else:
    __all__ = []

