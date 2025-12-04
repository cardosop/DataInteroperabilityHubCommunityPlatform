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


def _determine_normalization_status(hub_contract: Optional[Dict[str, Any]], errors: list, warnings: list) -> NormalizationStatus:
    """
    Determine normalization status based on completeness and errors.
    
    Args:
        hub_contract: Normalized HubContract JSON (None if normalization failed)
        errors: List of errors encountered during normalization
        warnings: List of warnings encountered during normalization
    
    Returns:
        NormalizationStatus enum value
    """
    # If normalization failed (errors or no contract), return FAILED
    if errors or hub_contract is None:
        return NormalizationStatus.NORMALIZATION_FAILED
    
    # Check if critical sections are present
    info = hub_contract.get('info', {})
    if 'info' not in hub_contract or 'name' not in info or not info.get('name'):
        return NormalizationStatus.NORMALIZATION_FAILED
    
    schema = hub_contract.get('schema', {})
    if 'schema' not in hub_contract or 'fields' not in schema:
        return NormalizationStatus.NORMALIZATION_FAILED
    
    if not schema.get('fields'):
        return NormalizationStatus.NORMALIZATION_FAILED
    
    # If warnings or extensions present, status is WITH_WARNINGS
    if warnings or hub_contract.get('extensions'):
        return NormalizationStatus.NORMALIZED_WITH_WARNINGS
    
    # All critical sections present, no warnings
    return NormalizationStatus.NORMALIZED_OK


def _calculate_normalization_coverage(hub_contract: Dict[str, Any]) -> float:
    """
    Calculate normalization coverage as percentage of sections mapped.
    
    Args:
        hub_contract: Normalized HubContract JSON
    
    Returns:
        Coverage percentage (0.0 to 1.0)
    """
    # Define all possible sections
    all_sections = {
        'info': ['name', 'description', 'version', 'owners', 'tags'],
        'schema': ['fields', 'primary_key', 'unique_constraints', 'indexes'],
        'quality': ['default_profile_key', 'rules'],
        'privacy_compliance': ['contains_personal_data', 'personal_data_categories', 'jurisdictions', 'legal_bases', 'retention_policy'],
        'lifecycle': ['data_source', 'refresh_cadence', 'slas'],
        'marketplace': ['license_summary', 'intended_use', 'restricted_use']
    }
    
    total_sub_sections = sum(len(subsections) for subsections in all_sections.values())
    mapped_sub_sections = 0
    
    # Count mapped sections
    for section_name, subsections in all_sections.items():
        section_data = hub_contract.get(section_name, {})
        if section_name == 'info':
            # Info section is required, count name as mapped
            if 'name' in section_data:
                mapped_sub_sections += 1
            for sub in subsections:
                if sub != 'name' and sub in section_data:
                    mapped_sub_sections += 1
        elif section_name == 'schema':
            # Schema.fields is required
            if 'fields' in section_data and section_data['fields']:
                mapped_sub_sections += 1
            for sub in subsections:
                if sub != 'fields' and sub in section_data:
                    mapped_sub_sections += 1
        else:
            # Optional sections
            if section_name in hub_contract:
                for sub in subsections:
                    if sub in section_data:
                        mapped_sub_sections += 1
    
    return mapped_sub_sections / total_sub_sections if total_sub_sections > 0 else 0.0


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
    
    # Default to ODCS if we can't detect (better than UNKNOWN which is invalid)
    # This allows the contract to be created and normalized, even if spec type is uncertain
    return (OriginalSpecType.ODCS, '1.0.0')


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
        
        # Extract info section with owners and tags
        info = odcs_contract.get('info', {})
        if isinstance(info, dict):
            if 'owners' in info:
                hub_contract['info']['owners'] = info['owners']
            if 'tags' in info:
                hub_contract['info']['tags'] = info['tags']
        # Also check top-level for owners/tags (ODCS may have them at root)
        if 'owners' in odcs_contract:
            hub_contract['info']['owners'] = odcs_contract['owners']
        if 'tags' in odcs_contract:
            hub_contract['info']['tags'] = odcs_contract['tags']
        
        # Map schema
        if 'schema' in odcs_contract:
            odcs_schema = odcs_contract['schema']
            hub_schema = {}
            
            # Map primary key, unique constraints, and indexes first (needed for field-level flags)
            primary_key_fields = []
            if 'primary_key' in odcs_schema:
                primary_key_fields = odcs_schema['primary_key'] if isinstance(odcs_schema['primary_key'], list) else [odcs_schema['primary_key']]
                hub_schema['primary_key'] = primary_key_fields
            
            unique_constraint_fields = []
            if 'unique_constraints' in odcs_schema:
                unique_constraints = odcs_schema['unique_constraints']
                hub_schema['unique_constraints'] = unique_constraints
                # Flatten unique constraints to get all unique fields
                for constraint in unique_constraints:
                    if isinstance(constraint, list):
                        unique_constraint_fields.extend(constraint)
                    else:
                        unique_constraint_fields.append(constraint)
            
            indexed_fields = []
            if 'indexes' in odcs_schema:
                indexes = odcs_schema['indexes']
                hub_schema['indexes'] = indexes
                # Extract field names from indexes
                for index in indexes:
                    if isinstance(index, dict) and 'fields' in index:
                        indexed_fields.extend(index['fields'] if isinstance(index['fields'], list) else [index['fields']])
                    elif isinstance(index, list):
                        indexed_fields.extend(index)
                    elif isinstance(index, str):
                        indexed_fields.append(index)
            
            # Map fields with all properties
            if 'fields' in odcs_schema:
                hub_schema['fields'] = []
                for field in odcs_schema['fields']:
                    field_name = field.get('name', '')
                    hub_field = {
                        'name': field_name,
                        'data_type': field.get('type', 'string'),
                        'nullable': field.get('nullable', True),
                    }
                    # Extract all optional field properties
                    if 'description' in field:
                        hub_field['description'] = field['description']
                    if 'semantic_type' in field:
                        hub_field['semantic_type'] = field['semantic_type']
                    if 'format' in field:
                        hub_field['format'] = field['format']
                    if 'pattern' in field:
                        hub_field['pattern'] = field['pattern']
                    if 'enum' in field:
                        hub_field['enum'] = field['enum']
                    if 'default' in field:
                        hub_field['default'] = field['default']
                    if 'min_length' in field or 'minLength' in field:
                        hub_field['min_length'] = field.get('min_length') or field.get('minLength')
                    if 'max_length' in field or 'maxLength' in field:
                        hub_field['max_length'] = field.get('max_length') or field.get('maxLength')
                    if 'minimum' in field:
                        hub_field['minimum'] = field['minimum']
                    if 'maximum' in field:
                        hub_field['maximum'] = field['maximum']
                    if 'metadata' in field:
                        hub_field['metadata'] = field['metadata']
                    
                    # Set schema constraint flags on fields
                    if field_name in primary_key_fields:
                        hub_field['is_primary_key'] = True
                    if 'is_primary_key' in field:
                        hub_field['is_primary_key'] = field['is_primary_key']
                    
                    if field_name in unique_constraint_fields:
                        hub_field['is_unique'] = True
                    if 'is_unique' in field:
                        hub_field['is_unique'] = field['is_unique']
                    
                    if field_name in indexed_fields:
                        hub_field['is_indexed'] = True
                    if 'is_indexed' in field:
                        hub_field['is_indexed'] = field['is_indexed']
                    
                    hub_schema['fields'].append(hub_field)
            
            hub_contract['schema'] = hub_schema
        
        # Extract quality section
        if 'quality' in odcs_contract:
            quality_data = odcs_contract['quality']
            hub_contract['quality'] = {}
            if 'default_profile_key' in quality_data:
                hub_contract['quality']['default_profile_key'] = quality_data['default_profile_key']
            if 'rules' in quality_data:
                hub_contract['quality']['rules'] = quality_data['rules']
        
        # Extract privacy_compliance section
        if 'privacy_compliance' in odcs_contract or 'compliance' in odcs_contract:
            compliance_data = odcs_contract.get('privacy_compliance') or odcs_contract.get('compliance', {})
            hub_contract['privacy_compliance'] = {}
            if 'contains_personal_data' in compliance_data:
                hub_contract['privacy_compliance']['contains_personal_data'] = compliance_data['contains_personal_data']
            if 'personal_data_categories' in compliance_data:
                hub_contract['privacy_compliance']['personal_data_categories'] = compliance_data['personal_data_categories']
            if 'jurisdictions' in compliance_data:
                hub_contract['privacy_compliance']['jurisdictions'] = compliance_data['jurisdictions']
            if 'legal_bases' in compliance_data:
                hub_contract['privacy_compliance']['legal_bases'] = compliance_data['legal_bases']
            if 'retention_policy' in compliance_data:
                hub_contract['privacy_compliance']['retention_policy'] = compliance_data['retention_policy']
        
        # Extract lifecycle section
        if 'lifecycle' in odcs_contract:
            lifecycle_data = odcs_contract['lifecycle']
            hub_contract['lifecycle'] = {}
            if 'data_source' in lifecycle_data:
                hub_contract['lifecycle']['data_source'] = lifecycle_data['data_source']
            if 'refresh_cadence' in lifecycle_data:
                hub_contract['lifecycle']['refresh_cadence'] = lifecycle_data['refresh_cadence']
            if 'slas' in lifecycle_data:
                hub_contract['lifecycle']['slas'] = lifecycle_data['slas']
        
        # Extract marketplace section
        if 'marketplace' in odcs_contract:
            marketplace_data = odcs_contract['marketplace']
            hub_contract['marketplace'] = {}
            if 'license_summary' in marketplace_data:
                hub_contract['marketplace']['license_summary'] = marketplace_data['license_summary']
            if 'intended_use' in marketplace_data:
                hub_contract['marketplace']['intended_use'] = marketplace_data['intended_use']
            if 'restricted_use' in marketplace_data:
                hub_contract['marketplace']['restricted_use'] = marketplace_data['restricted_use']
        
        # Preserve unmappable fields in extensions
        extensions = {}
        odcs_extensions = {}
        
        # Known mappable fields (already mapped above)
        known_fields = {
            'id', 'name', 'description', 'version', 'schema', 'info',
            'quality', 'privacy_compliance', 'compliance', 'lifecycle', 'marketplace',
            'owners', 'tags'  # May be at root level
        }
        
        # Copy fields that don't map directly
        for key, value in odcs_contract.items():
            if key not in known_fields:
                odcs_extensions[key] = value
        
        if odcs_extensions:
            extensions['odcs'] = odcs_extensions
            warnings.append("Some ODCS fields preserved in extensions.odcs")
        
        if extensions:
            hub_contract['extensions'] = extensions
        
        # Determine status based on completeness
        status = _determine_normalization_status(hub_contract, errors, warnings)
        
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
        # Extract info section
        info = datacontract_contract.get('info', {})
        
        # Basic HubContract structure
        hub_contract = {
            'hub_contract_version': 1,
            'id': datacontract_contract.get('id', ''),
            'info': {
                'name': info.get('title', ''),
                'description': info.get('description'),
                'version': info.get('version'),
            },
            'schema': {}
        }
        
        # Extract owners and tags from info section
        if 'owners' in info:
            hub_contract['info']['owners'] = info['owners']
        if 'tags' in info:
            hub_contract['info']['tags'] = info['tags']
        
        # Map schema
        if 'schema' in datacontract_contract:
            dc_schema = datacontract_contract['schema']
            hub_schema = {}
            
            # Map primary key, unique constraints, indexes from DataContract.com first (needed for field-level flags)
            primary_key_fields = []
            if 'primaryKey' in dc_schema:
                primary_key_fields = dc_schema['primaryKey'] if isinstance(dc_schema['primaryKey'], list) else [dc_schema['primaryKey']]
                hub_schema['primary_key'] = primary_key_fields
            elif 'primary_key' in dc_schema:
                primary_key_fields = dc_schema['primary_key'] if isinstance(dc_schema['primary_key'], list) else [dc_schema['primary_key']]
                hub_schema['primary_key'] = primary_key_fields
            
            unique_constraint_fields = []
            if 'uniqueConstraints' in dc_schema:
                unique_constraints = dc_schema['uniqueConstraints']
                hub_schema['unique_constraints'] = unique_constraints
                for constraint in unique_constraints:
                    if isinstance(constraint, list):
                        unique_constraint_fields.extend(constraint)
                    else:
                        unique_constraint_fields.append(constraint)
            elif 'unique_constraints' in dc_schema:
                unique_constraints = dc_schema['unique_constraints']
                hub_schema['unique_constraints'] = unique_constraints
                for constraint in unique_constraints:
                    if isinstance(constraint, list):
                        unique_constraint_fields.extend(constraint)
                    else:
                        unique_constraint_fields.append(constraint)
            
            indexed_fields = []
            if 'indexes' in dc_schema:
                indexes = dc_schema['indexes']
                hub_schema['indexes'] = indexes
                for index in indexes:
                    if isinstance(index, dict) and 'fields' in index:
                        indexed_fields.extend(index['fields'] if isinstance(index['fields'], list) else [index['fields']])
                    elif isinstance(index, list):
                        indexed_fields.extend(index)
                    elif isinstance(index, str):
                        indexed_fields.append(index)
            
            # Map fields from DataContract.com schema with all properties
            if 'type' in dc_schema and dc_schema['type'] == 'object' and 'properties' in dc_schema:
                hub_schema['fields'] = []
                required_fields = dc_schema.get('required', [])
                for field_name, field_def in dc_schema['properties'].items():
                    hub_field = {
                        'name': field_name,
                        'data_type': field_def.get('type', 'string'),
                        'nullable': field_name not in required_fields,
                    }
                    # Extract all optional field properties from JSON Schema
                    if 'description' in field_def:
                        hub_field['description'] = field_def['description']
                    if 'format' in field_def:
                        hub_field['format'] = field_def['format']
                    if 'pattern' in field_def:
                        hub_field['pattern'] = field_def['pattern']
                    if 'enum' in field_def:
                        hub_field['enum'] = field_def['enum']
                    if 'default' in field_def:
                        hub_field['default'] = field_def['default']
                    if 'minLength' in field_def:
                        hub_field['min_length'] = field_def['minLength']
                    if 'maxLength' in field_def:
                        hub_field['max_length'] = field_def['maxLength']
                    if 'minimum' in field_def:
                        hub_field['minimum'] = field_def['minimum']
                    if 'maximum' in field_def:
                        hub_field['maximum'] = field_def['maximum']
                    # Extract semantic_type from x-datahub extension or metadata
                    if 'x-datahub' in field_def and 'semantic_type' in field_def['x-datahub']:
                        hub_field['semantic_type'] = field_def['x-datahub']['semantic_type']
                    elif 'semantic_type' in field_def:
                        hub_field['semantic_type'] = field_def['semantic_type']
                    # Extract metadata from x-datahub extension or metadata field
                    if 'x-datahub' in field_def and 'metadata' in field_def['x-datahub']:
                        hub_field['metadata'] = field_def['x-datahub']['metadata']
                    elif 'metadata' in field_def:
                        hub_field['metadata'] = field_def['metadata']
                    
                    # Set schema constraint flags on fields
                    if field_name in primary_key_fields:
                        hub_field['is_primary_key'] = True
                    if 'is_primary_key' in field_def or 'isPrimaryKey' in field_def:
                        hub_field['is_primary_key'] = field_def.get('is_primary_key') or field_def.get('isPrimaryKey')
                    
                    if field_name in unique_constraint_fields:
                        hub_field['is_unique'] = True
                    if 'is_unique' in field_def or 'isUnique' in field_def:
                        hub_field['is_unique'] = field_def.get('is_unique') or field_def.get('isUnique')
                    
                    if field_name in indexed_fields:
                        hub_field['is_indexed'] = True
                    if 'is_indexed' in field_def or 'isIndexed' in field_def:
                        hub_field['is_indexed'] = field_def.get('is_indexed') or field_def.get('isIndexed')
                    
                    hub_schema['fields'].append(hub_field)
            
            hub_contract['schema'] = hub_schema
        
        # Extract quality section
        if 'quality' in datacontract_contract:
            quality_data = datacontract_contract['quality']
            hub_contract['quality'] = {}
            if 'default_profile_key' in quality_data or 'defaultProfileKey' in quality_data:
                hub_contract['quality']['default_profile_key'] = quality_data.get('default_profile_key') or quality_data.get('defaultProfileKey')
            if 'rules' in quality_data:
                hub_contract['quality']['rules'] = quality_data['rules']
        
        # Extract privacy_compliance section
        if 'privacy' in datacontract_contract or 'privacy_compliance' in datacontract_contract:
            compliance_data = datacontract_contract.get('privacy_compliance') or datacontract_contract.get('privacy', {})
            hub_contract['privacy_compliance'] = {}
            if 'containsPersonalData' in compliance_data or 'contains_personal_data' in compliance_data:
                hub_contract['privacy_compliance']['contains_personal_data'] = compliance_data.get('contains_personal_data') or compliance_data.get('containsPersonalData')
            if 'personalDataCategories' in compliance_data or 'personal_data_categories' in compliance_data:
                hub_contract['privacy_compliance']['personal_data_categories'] = compliance_data.get('personal_data_categories') or compliance_data.get('personalDataCategories')
            if 'jurisdictions' in compliance_data:
                hub_contract['privacy_compliance']['jurisdictions'] = compliance_data['jurisdictions']
            if 'legalBases' in compliance_data or 'legal_bases' in compliance_data:
                hub_contract['privacy_compliance']['legal_bases'] = compliance_data.get('legal_bases') or compliance_data.get('legalBases')
            if 'retentionPolicy' in compliance_data or 'retention_policy' in compliance_data:
                hub_contract['privacy_compliance']['retention_policy'] = compliance_data.get('retention_policy') or compliance_data.get('retentionPolicy')
        
        # Extract lifecycle section
        if 'lifecycle' in datacontract_contract:
            lifecycle_data = datacontract_contract['lifecycle']
            hub_contract['lifecycle'] = {}
            if 'dataSource' in lifecycle_data or 'data_source' in lifecycle_data:
                hub_contract['lifecycle']['data_source'] = lifecycle_data.get('data_source') or lifecycle_data.get('dataSource')
            if 'refreshCadence' in lifecycle_data or 'refresh_cadence' in lifecycle_data:
                hub_contract['lifecycle']['refresh_cadence'] = lifecycle_data.get('refresh_cadence') or lifecycle_data.get('refreshCadence')
            if 'slas' in lifecycle_data:
                hub_contract['lifecycle']['slas'] = lifecycle_data['slas']
        
        # Extract marketplace section
        if 'marketplace' in datacontract_contract:
            marketplace_data = datacontract_contract['marketplace']
            hub_contract['marketplace'] = {}
            if 'licenseSummary' in marketplace_data or 'license_summary' in marketplace_data:
                hub_contract['marketplace']['license_summary'] = marketplace_data.get('license_summary') or marketplace_data.get('licenseSummary')
            if 'intendedUse' in marketplace_data or 'intended_use' in marketplace_data:
                hub_contract['marketplace']['intended_use'] = marketplace_data.get('intended_use') or marketplace_data.get('intendedUse')
            if 'restrictedUse' in marketplace_data or 'restricted_use' in marketplace_data:
                hub_contract['marketplace']['restricted_use'] = marketplace_data.get('restricted_use') or marketplace_data.get('restrictedUse')
        
        # Preserve unmappable fields in extensions
        extensions = {}
        dc_extensions = {}
        
        # Known mappable fields (already mapped above)
        known_fields = {
            'id', 'info', 'schema', 'dataContractSpecification',
            'quality', 'privacy', 'privacy_compliance', 'lifecycle', 'marketplace'
        }
        
        # Copy fields that don't map directly
        for key, value in datacontract_contract.items():
            if key not in known_fields:
                dc_extensions[key] = value
        
        if dc_extensions:
            extensions['datacontract_com'] = dc_extensions
            warnings.append("Some DataContract.com fields preserved in extensions.datacontract_com")
        
        if extensions:
            hub_contract['extensions'] = extensions
        
        # Determine status based on completeness
        status = _determine_normalization_status(hub_contract, errors, warnings)
        
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
        # Return ODCS as default spec type (UNKNOWN is not a valid choice)
        return None, OriginalSpecType.ODCS, "1.0.0", NormalizationStatus.NORMALIZATION_FAILED, errors, []


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

