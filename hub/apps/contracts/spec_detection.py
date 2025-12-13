"""
Spec Detection and Metadata Tracking

Detects contract specification type (ODCS) and tracks original spec metadata.
"""
from typing import Dict, Any, Tuple, Optional
from .models import OriginalSpecType


def detect_spec_type(contract_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Detect contract specification type (ODCS only).
    
    Detection logic:
    - ODCS: Has 'apiVersion' and 'kind' fields
    
    Args:
        contract_data: Contract data dictionary
    
    Returns:
        Tuple of (spec_type, spec_version)
    """
    if not isinstance(contract_data, dict):
        return OriginalSpecType.ODCS, "3.0.2"
    
    # Check for deprecated DCS format (dataContractSpecification field)
    # This is detected but will cause an error during normalization
    if 'dataContractSpecification' in contract_data:
        # Return ODCS type but normalization will detect and reject DCS contracts
        # This allows us to provide a clear error message during normalization
        return OriginalSpecType.ODCS, "3.0.2"
    
    # Check for ODCS - has 'apiVersion' and 'kind' fields
    if 'apiVersion' in contract_data and 'kind' in contract_data:
        # Extract version from apiVersion (e.g., "odcs.io/v3.0.2" -> "3.0.2")
        api_version = contract_data.get('apiVersion', '')
        if isinstance(api_version, str):
            # Extract version from apiVersion string
            if '/' in api_version:
                version_part = api_version.split('/')[-1]
                # Remove 'v' prefix if present
                if version_part.startswith('v'):
                    version_part = version_part[1:]
                spec_version = version_part
            else:
                spec_version = api_version
        else:
            spec_version = str(api_version)
        
        # Default to 3.0.2 if version not found
        if not spec_version or spec_version == api_version:
            spec_version = "3.0.2"
        
        return OriginalSpecType.ODCS, spec_version
    
    # Default to ODCS if detection fails
    return OriginalSpecType.ODCS, "3.0.2"


def extract_original_spec_metadata(contract_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract original specification metadata from contract.
    
    Args:
        contract_data: Contract data dictionary
    
    Returns:
        Dictionary with original_spec metadata:
        - type: spec type (ODCS)
        - version: spec version
        - conforms_to: conformance information (dct:conformsTo)
    """
    spec_type, spec_version = detect_spec_type(contract_data)
    
    metadata = {
        'type': spec_type,
        'version': spec_version,
    }
    
    # Extract conformance information (dct:conformsTo)
    conforms_to = extract_conformance_info(contract_data, spec_type)
    if conforms_to:
        metadata['conforms_to'] = conforms_to
    
    return metadata


def extract_conformance_info(contract_data: Dict[str, Any], spec_type: str) -> Optional[Dict[str, Any]]:
    """
    Extract spec conformance tracking information (dct:conformsTo).
    
    Args:
        contract_data: Contract data dictionary
        spec_type: Detected spec type
    
    Returns:
        Conformance information dictionary or None
    """
    if not isinstance(contract_data, dict):
        return None
    
    # Check for dct:conformsTo field (Dublin Core Terms)
    conforms_to = contract_data.get('dct:conformsTo') or contract_data.get('conformsTo')
    
    if conforms_to:
        return {
            'uri': conforms_to if isinstance(conforms_to, str) else conforms_to.get('uri'),
            'spec_type': spec_type,
            'spec_version': detect_spec_type(contract_data)[1]
        }
    
    # For ODCS, check apiVersion as conformance indicator
    if spec_type == OriginalSpecType.ODCS and 'apiVersion' in contract_data:
        api_version = contract_data.get('apiVersion')
        return {
            'uri': f"https://bitol-io.github.io/open-data-contract-standard/{api_version.split('/')[-1]}",
            'spec_type': spec_type,
            'spec_version': detect_spec_type(contract_data)[1]
        }
    
    return None


def store_original_spec_metadata(hub_contract: Dict[str, Any], contract_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Store original specification metadata in HubContract.
    
    Adds 'original_spec' section to HubContract with:
    - type: Original spec type (ODCS)
    - version: Original spec version
    - conforms_to: Conformance information
    
    Args:
        hub_contract: HubContract dictionary
        contract_data: Original contract data
    
    Returns:
        HubContract with original_spec metadata added
    """
    if not isinstance(hub_contract, dict):
        hub_contract = {}
    
    # Extract original spec metadata
    original_metadata = extract_original_spec_metadata(contract_data)
    
    # Add original_spec section to HubContract
    hub_contract['original_spec'] = original_metadata
    
    return hub_contract

