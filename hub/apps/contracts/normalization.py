"""
Contract Normalization

Normalizes contracts from ODCS and DataContract.com to HubContract format.
"""
import json
from typing import Dict, Any, Tuple, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from .models import NormalizationStatus, OriginalSpecType


def detect_spec_type(contract_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Detect contract specification type and version from contract data.
    
    Args:
        contract_data: Parsed contract data (dict)
    
    Returns:
        Tuple of (spec_type, spec_version)
    """
    # Check for ODCS indicators
    if 'odcs' in contract_data or 'odcs_version' in contract_data:
        version = contract_data.get('odcs_version', '1.0')
        return (OriginalSpecType.ODCS, str(version))
    
    # Check for DataContract.com indicators
    if 'dataContractSpecification' in contract_data:
        version = contract_data.get('dataContractSpecification', '0.4.0')
        return (OriginalSpecType.DATACONTRACT_COM, str(version))
    
    # Check for schema field (common in both)
    if 'schema' in contract_data:
        # Try to infer from structure
        if 'fields' in contract_data.get('schema', {}):
            # Likely ODCS
            return (OriginalSpecType.ODCS, '3.0.0')
        elif 'type' in contract_data.get('schema', {}):
            # Likely DataContract.com
            return (OriginalSpecType.DATACONTRACT_COM, '0.4.0')
    
    # Default to unknown
    return ("UNKNOWN", "1.0")


def parse_contract(raw_contract: str, format: str) -> Dict[str, Any]:
    """
    Parse contract from raw string.
    
    Args:
        raw_contract: Raw contract content
        format: Format (JSON or YAML)
    
    Returns:
        Parsed contract as dictionary
    """
    if format.upper() == 'JSON':
        return json.loads(raw_contract)
    elif format.upper() == 'YAML':
        if not YAML_AVAILABLE:
            raise ValueError("PyYAML is required for YAML parsing. Install with: pip install pyyaml")
        return yaml.safe_load(raw_contract)
    else:
        raise ValueError(f"Unsupported format: {format}")


def normalize_odcs_to_hubcontract(odcs_contract: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], NormalizationStatus, list, list]:
    """
    Normalize ODCS contract to HubContract format.
    
    Args:
        odcs_contract: ODCS contract data
    
    Returns:
        Tuple of (hub_contract_json, normalization_status, errors, warnings)
    """
    errors = []
    warnings = []
    
    try:
        # Basic HubContract structure
        hub_contract = {
            'hub_contract_version': 1,
            'id': odcs_contract.get('id', ''),
            'info': {
                'name': odcs_contract.get('name', ''),
                'description': odcs_contract.get('description'),
                'version': odcs_contract.get('version'),
            },
            'schema': {}
        }
        
        # Map schema
        if 'schema' in odcs_contract:
            odcs_schema = odcs_contract['schema']
            hub_schema = {}
            
            # Map fields
            if 'fields' in odcs_schema:
                hub_schema['fields'] = []
                for field in odcs_schema['fields']:
                    hub_field = {
                        'name': field.get('name', ''),
                        'type': field.get('type', 'string'),
                        'nullable': field.get('nullable', True),
                    }
                    if 'description' in field:
                        hub_field['description'] = field['description']
                    hub_schema['fields'].append(hub_field)
            
            # Map primary key
            if 'primary_key' in odcs_schema:
                hub_schema['primary_key'] = odcs_schema['primary_key']
            
            # Map unique constraints
            if 'unique_constraints' in odcs_schema:
                hub_schema['unique_constraints'] = odcs_schema['unique_constraints']
            
            hub_contract['schema'] = hub_schema
        
        # Preserve unmappable fields in extensions
        extensions = {}
        odcs_extensions = {}
        
        # Copy fields that don't map directly
        for key, value in odcs_contract.items():
            if key not in ['id', 'name', 'description', 'version', 'schema']:
                odcs_extensions[key] = value
        
        if odcs_extensions:
            extensions['odcs'] = odcs_extensions
            warnings.append("Some ODCS fields preserved in extensions.odcs")
        
        if extensions:
            hub_contract['extensions'] = extensions
        
        # Determine status
        status = NormalizationStatus.NORMALIZED_OK
        if warnings:
            status = NormalizationStatus.NORMALIZED_WITH_WARNINGS
        
        return hub_contract, status, errors, warnings
    
    except Exception as e:
        errors.append(f"Normalization failed: {str(e)}")
        return None, NormalizationStatus.NORMALIZATION_FAILED, errors, warnings


def normalize_datacontract_com_to_hubcontract(datacontract_contract: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], NormalizationStatus, list, list]:
    """
    Normalize DataContract.com contract to HubContract format.
    
    Args:
        datacontract_contract: DataContract.com contract data
    
    Returns:
        Tuple of (hub_contract_json, normalization_status, errors, warnings)
    """
    errors = []
    warnings = []
    
    try:
        # Basic HubContract structure
        hub_contract = {
            'hub_contract_version': 1,
            'id': datacontract_contract.get('id', ''),
            'info': {
                'name': datacontract_contract.get('info', {}).get('title', ''),
                'description': datacontract_contract.get('info', {}).get('description'),
                'version': datacontract_contract.get('info', {}).get('version'),
            },
            'schema': {}
        }
        
        # Map schema
        if 'schema' in datacontract_contract:
            dc_schema = datacontract_contract['schema']
            hub_schema = {}
            
            # Map fields from DataContract.com schema
            if 'type' in dc_schema and dc_schema['type'] == 'object' and 'properties' in dc_schema:
                hub_schema['fields'] = []
                for field_name, field_def in dc_schema['properties'].items():
                    hub_field = {
                        'name': field_name,
                        'type': field_def.get('type', 'string'),
                        'nullable': field_name not in dc_schema.get('required', []),
                    }
                    if 'description' in field_def:
                        hub_field['description'] = field_def['description']
                    hub_schema['fields'].append(hub_field)
            
            hub_contract['schema'] = hub_schema
        
        # Preserve unmappable fields in extensions
        extensions = {}
        dc_extensions = {}
        
        # Copy fields that don't map directly
        # Exclude metadata fields that are not part of the contract data
        excluded_fields = ['id', 'info', 'schema', 'dataContractSpecification']
        for key, value in datacontract_contract.items():
            if key not in excluded_fields:
                dc_extensions[key] = value
        
        if dc_extensions:
            extensions['datacontract_com'] = dc_extensions
            warnings.append("Some DataContract.com fields preserved in extensions.datacontract_com")
        
        if extensions:
            hub_contract['extensions'] = extensions
        
        # Determine status
        status = NormalizationStatus.NORMALIZED_OK
        if warnings:
            status = NormalizationStatus.NORMALIZED_WITH_WARNINGS
        
        return hub_contract, status, errors, warnings
    
    except Exception as e:
        errors.append(f"Normalization failed: {str(e)}")
        return None, NormalizationStatus.NORMALIZATION_FAILED, errors, warnings


def normalize_contract(
    raw_contract: str,
    format: str,
    spec_type: Optional[str] = None
) -> Tuple[Optional[Dict[str, Any]], str, str, NormalizationStatus, list, list]:
    """
    Normalize contract to HubContract format.
    
    Args:
        raw_contract: Raw contract content
        format: Format (JSON or YAML)
        spec_type: Optional spec type (ODCS or DATACONTRACT_COM). If None, will be detected.
    
    Returns:
        Tuple of (hub_contract_json, detected_spec_type, detected_spec_version, normalization_status, errors, warnings)
    """
    try:
        # Parse contract
        contract_data = parse_contract(raw_contract, format)
        
        # Detect spec type if not provided
        if not spec_type:
            spec_type, spec_version = detect_spec_type(contract_data)
        else:
            spec_version = contract_data.get('version', '1.0')
        
        # Normalize based on spec type
        if spec_type == OriginalSpecType.ODCS:
            hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(contract_data)
        elif spec_type == OriginalSpecType.DATACONTRACT_COM:
            hub_contract, status, errors, warnings = normalize_datacontract_com_to_hubcontract(contract_data)
        else:
            errors = [f"Unsupported spec type: {spec_type}"]
            return None, spec_type, spec_version, NormalizationStatus.NORMALIZATION_FAILED, errors, []
        
        return hub_contract, spec_type, spec_version, status, errors, warnings
    
    except Exception as e:
        errors = [f"Failed to normalize contract: {str(e)}"]
        return None, "UNKNOWN", "1.0", NormalizationStatus.NORMALIZATION_FAILED, errors, []


def validate_hubcontract_schema(hub_contract: Dict[str, Any]) -> Tuple[bool, list]:
    """
    Validate HubContract JSON against schema.
    
    Args:
        hub_contract: HubContract JSON
    
    Returns:
        Tuple of (is_valid: bool, errors: list)
    """
    errors = []
    
    # Check required fields
    if 'hub_contract_version' not in hub_contract:
        errors.append("Missing required field: hub_contract_version")
    elif hub_contract['hub_contract_version'] != 1:
        errors.append(f"Invalid hub_contract_version: {hub_contract['hub_contract_version']} (expected: 1)")
    
    if 'id' not in hub_contract or not hub_contract['id']:
        errors.append("Missing or empty required field: id")
    
    if 'info' not in hub_contract:
        errors.append("Missing required field: info")
    elif 'name' not in hub_contract['info'] or not hub_contract['info']['name']:
        errors.append("Missing or empty required field: info.name")
    
    if 'schema' not in hub_contract:
        errors.append("Missing required field: schema")
    elif 'fields' not in hub_contract['schema'] or not hub_contract['schema']['fields']:
        errors.append("Missing or empty required field: schema.fields")
    
    return len(errors) == 0, errors

