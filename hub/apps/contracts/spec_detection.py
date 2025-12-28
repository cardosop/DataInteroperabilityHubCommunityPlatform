"""
Spec Detection and Metadata Tracking

Detects contract specification type (ODPS and ODCS) and tracks original spec metadata.
"""
from typing import Dict, Any, Tuple, Optional
from .models import OriginalSpecType
from .odps_version_detection import detect_odps_version as detect_odps_version_from_data


def detect_odps_version(contract_data: Dict[str, Any]) -> Optional[str]:
    """
    Detect ODPS version from contract data.

    Uses the ODPS version detection module to extract version from:
    1. Schema URL (primary)
    2. Version field (fallback)

    Args:
        contract_data: Contract data dictionary

    Returns:
        ODPS version string (e.g., "4.1", "4.0", "3.x", "2.x", "1.x") or None if not ODPS
    """
    if not isinstance(contract_data, dict):
        return None

    # Use the ODPS version detection function
    version = detect_odps_version_from_data(contract_data)

    # Return None if version is "unknown" (not an ODPS contract)
    if version == "unknown":
        return None

    return version


def is_odps_contract(contract_data: Dict[str, Any]) -> bool:
    """
    Check if contract data represents an ODPS contract.

    Detection logic:
    - Checks for 'schema' field with ODPS indicators:
      * opendataproducts.org/schema
      * schemas.opendataproducts.io/spec
    - Checks for 'open-data-product' in schema URL
    - Checks for 'product' field (ODPS structure indicator)

    Args:
        contract_data: Contract data dictionary

    Returns:
        True if contract appears to be ODPS, False otherwise
    """
    if not isinstance(contract_data, dict):
        return False

    # Check for schema field with ODPS indicators
    schema_url = contract_data.get("schema")
    if schema_url and isinstance(schema_url, str):
        schema_lower = schema_url.lower()
        # Check for ODPS schema URL patterns
        if "opendataproducts.org/schema" in schema_lower:
            return True
        if "schemas.opendataproducts.io/spec" in schema_lower:
            return True
        if "open-data-product" in schema_lower:
            return True

    # Check for product field (ODPS structure indicator)
    # ODPS contracts have a 'product' field with details
    if "product" in contract_data:
        product = contract_data.get("product")
        if isinstance(product, dict):
            # Check if it has ODPS-like structure
            if "details" in product:
                return True

    # If contract has ODCS indicators (apiVersion and kind), it's definitely ODCS, not ODPS
    # This prevents misclassification when ODCS contracts have version fields that
    # could be interpreted as ODPS versions
    if "apiVersion" in contract_data and "kind" in contract_data:
        # Strong ODCS indicator - don't check version field for ODPS
        return False

    # Try version detection - if it returns a valid version, it's ODPS
    # Only do this if we don't have strong ODCS indicators
    odps_version = detect_odps_version(contract_data)
    if odps_version and odps_version != "unknown":
        return True

    return False


def detect_spec_type(contract_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Detect contract specification type (ODPS or ODCS).

    Detection logic (in order):
    1. ODPS: Check for ODPS indicators (schema URL, product field)
    2. ODCS: Has 'apiVersion' and 'kind' fields

    ODPS detection is checked first because:
    - ODPS contracts are more specific (marketplace-focused)
    - ODPS has clear schema URL indicators
    - Prevents misclassification of ODPS contracts as ODCS

    Args:
        contract_data: Contract data dictionary

    Returns:
        Tuple of (spec_type, spec_version)
    """
    if not isinstance(contract_data, dict):
        return OriginalSpecType.ODCS, "3.0.2"

    # Route ODPS detection before ODCS detection
    # Check for ODPS first (more specific indicators)
    if is_odps_contract(contract_data):
        odps_version = detect_odps_version(contract_data)
        if odps_version and odps_version != "unknown":
            # Normalize version for storage (use detected version)
            # For .x versions, use the latest known version in that series
            if odps_version == "3.x":
                spec_version = "3.9"  # Latest 3.x version
            elif odps_version == "2.x":
                spec_version = "2.9"  # Latest 2.x version
            elif odps_version == "1.x":
                spec_version = "1.9"  # Latest 1.x version
            else:
                spec_version = odps_version  # Use exact version (4.1, 4.0)

            return OriginalSpecType.ODPS, spec_version
        else:
            # ODPS detected but version unknown - default to latest
            return OriginalSpecType.ODPS, "4.1"

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

