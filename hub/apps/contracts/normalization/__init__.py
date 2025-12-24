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

    # Re-export ODCSNormalizer and registry utilities
    ODCSNormalizer = _normalization_py_module.ODCSNormalizer
    normalize_odcs_to_hubcontract = _normalization_py_module.normalize_odcs_to_hubcontract
    _NORMALIZER_REGISTRY = _normalization_py_module._NORMALIZER_REGISTRY
    _reset_normalizer_registry = _normalization_py_module._reset_normalizer_registry

    __all__ = [
        'NormalizationResult',
        'SpecNormalizer',
        'ODPSNormalizer',
        'ODCSNormalizer',
        'normalize_odcs_to_hubcontract',
        'get_normalizer',
        'register_normalizer',
        'normalize_contract',
        'parse_contract',
        'validate_hubcontract_schema',
        '_NORMALIZER_REGISTRY',
        '_reset_normalizer_registry'
    ]
else:
    __all__ = []

