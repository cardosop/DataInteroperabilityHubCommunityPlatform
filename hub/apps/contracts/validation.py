"""
Validation and enrichment functions for HubContract objects.

Validates and enriches contacts, SLA properties, roles/team, pricing, lineage,
and advanced schema attributes during normalization.
"""
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from django.core.validators import EmailValidator, URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email or not isinstance(email, str):
        return False, "Email must be a non-empty string"
    
    validator = EmailValidator()
    try:
        validator(email)
        return True, None
    except DjangoValidationError as e:
        return False, str(e)


def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate URL format.
    
    Args:
        url: URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"
    
    validator = URLValidator()
    try:
        validator(url)
        return True, None
    except DjangoValidationError as e:
        return False, str(e)


def validate_and_enrich_contacts(contacts: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Validate and enrich contact entries.
    
    Args:
        contacts: List of contact dictionaries
        
    Returns:
        Tuple of (enriched_contacts, validation_errors)
    """
    if not isinstance(contacts, list):
        return [], ["contacts must be a list"]
    
    enriched = []
    errors = []
    
    for idx, contact in enumerate(contacts):
        if not isinstance(contact, dict):
            errors.append(f"contact[{idx}] must be a dictionary")
            continue
        
        enriched_contact = contact.copy()
        
        # Validate email if present
        if 'email' in enriched_contact and enriched_contact['email']:
            is_valid, error = validate_email(enriched_contact['email'])
            if not is_valid:
                errors.append(f"contact[{idx}].email: {error}")
                # Preserve invalid email but mark it
                enriched_contact['_email_validation_error'] = error
        
        # Validate URL if present
        if 'url' in enriched_contact and enriched_contact['url']:
            is_valid, error = validate_url(enriched_contact['url'])
            if not is_valid:
                errors.append(f"contact[{idx}].url: {error}")
                # Preserve invalid URL but mark it
                enriched_contact['_url_validation_error'] = error
        
        # Enrich: normalize tool values
        if 'tool' in enriched_contact and enriched_contact['tool']:
            tool = str(enriched_contact['tool']).lower()
            # Normalize common tool names
            tool_map = {
                'e-mail': 'email',
                'mail': 'email',
                'slack': 'slack',
                'teams': 'teams',
                'discord': 'discord',
                'ticket': 'ticket',
                'jira': 'ticket',
                'github': 'ticket',
            }
            enriched_contact['tool'] = tool_map.get(tool, tool)
        
        enriched.append(enriched_contact)
    
    return enriched, errors


def validate_and_enrich_servicelevels(servicelevels: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Validate and enrich service level entries.
    
    Args:
        servicelevels: List of service level dictionaries
        
    Returns:
        Tuple of (enriched_servicelevels, validation_errors)
    """
    if not isinstance(servicelevels, list):
        return [], ["servicelevels must be a list"]
    
    enriched = []
    errors = []
    
    for idx, sl in enumerate(servicelevels):
        if not isinstance(sl, dict):
            errors.append(f"servicelevel[{idx}] must be a dictionary")
            continue
        
        enriched_sl = sl.copy()
        
        # Validate target (should be numeric for metrics)
        if 'target' in enriched_sl and enriched_sl['target']:
            target = enriched_sl['target']
            if isinstance(target, str):
                # Try to parse as number
                try:
                    # Remove % if present
                    target_clean = target.replace('%', '').strip()
                    float(target_clean)
                    enriched_sl['target'] = target_clean
                except ValueError:
                    errors.append(f"servicelevel[{idx}].target must be numeric")
        
        # Validate unit
        if 'unit' in enriched_sl and enriched_sl['unit']:
            unit = str(enriched_sl['unit']).lower()
            # Normalize common units
            unit_map = {
                'percent': '%',
                'percentage': '%',
                'ms': 'ms',
                'milliseconds': 'ms',
                'seconds': 's',
                'req/s': 'req/s',
                'requests_per_second': 'req/s',
            }
            enriched_sl['unit'] = unit_map.get(unit, unit)
        
        # Validate operator
        if 'operator' in enriched_sl and enriched_sl['operator']:
            operator = str(enriched_sl['operator']).upper()
            valid_operators = ['>=', '<=', '>', '<', '==', '!=', '=']
            if operator not in valid_operators:
                # Normalize common operators
                operator_map = {
                    'GREATER_THAN': '>',
                    'LESS_THAN': '<',
                    'GREATER_EQUAL': '>=',
                    'LESS_EQUAL': '<=',
                    'EQUAL': '==',
                    'NOT_EQUAL': '!=',
                }
                enriched_sl['operator'] = operator_map.get(operator, operator)
        
        # Enrich: add default priority if missing
        if 'priority' not in enriched_sl:
            enriched_sl['priority'] = 'P3'  # Default priority
        
        enriched.append(enriched_sl)
    
    return enriched, errors


def validate_and_enrich_roles(roles: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Validate and enrich role entries.
    
    Args:
        roles: List of role dictionaries
        
    Returns:
        Tuple of (enriched_roles, validation_errors)
    """
    if not isinstance(roles, list):
        return [], ["roles must be a list"]
    
    enriched = []
    errors = []
    
    for idx, role in enumerate(roles):
        if not isinstance(role, dict):
            errors.append(f"role[{idx}] must be a dictionary")
            continue
        
        enriched_role = role.copy()
        
        # Validate roleName (required if role present)
        if 'roleName' not in enriched_role and 'role_name' not in enriched_role:
            errors.append(f"role[{idx}] must have roleName")
        
        # Normalize field names
        if 'role_name' in enriched_role and 'roleName' not in enriched_role:
            enriched_role['roleName'] = enriched_role.pop('role_name')
        
        if 'access_type' in enriched_role and 'accessType' not in enriched_role:
            enriched_role['accessType'] = enriched_role.pop('access_type')
        
        # Validate accessType
        if 'accessType' in enriched_role and enriched_role['accessType']:
            access_type = str(enriched_role['accessType']).upper()
            valid_types = ['READ', 'WRITE', 'ADMIN', 'OWNER']
            if access_type not in valid_types:
                # Normalize common types
                type_map = {
                    'R': 'READ',
                    'W': 'WRITE',
                    'A': 'ADMIN',
                    'O': 'OWNER',
                }
                enriched_role['accessType'] = type_map.get(access_type, access_type)
        
        # Validate approvers (should be list)
        if 'approvers' in enriched_role:
            if not isinstance(enriched_role['approvers'], list):
                if isinstance(enriched_role['approvers'], str):
                    # Convert comma-separated string to list
                    enriched_role['approvers'] = [a.strip() for a in enriched_role['approvers'].split(',')]
                else:
                    errors.append(f"role[{idx}].approvers must be a list")
        
        enriched.append(enriched_role)
    
    return enriched, errors


def validate_and_enrich_team(team: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Validate and enrich team membership entries.
    
    Args:
        team: List of team membership dictionaries
        
    Returns:
        Tuple of (enriched_team, validation_errors)
    """
    if not isinstance(team, list):
        return [], ["team must be a list"]
    
    enriched = []
    errors = []
    
    for idx, member in enumerate(team):
        if not isinstance(member, dict):
            errors.append(f"team[{idx}] must be a dictionary")
            continue
        
        enriched_member = member.copy()
        
        # Normalize field names
        if 'member' in enriched_member and 'memberName' not in enriched_member:
            enriched_member['memberName'] = enriched_member.get('member')
        
        if 'member_name' in enriched_member and 'memberName' not in enriched_member:
            enriched_member['memberName'] = enriched_member.pop('member_name')
        
        if 'date_in' in enriched_member and 'dateIn' not in enriched_member:
            enriched_member['dateIn'] = enriched_member.pop('date_in')
        
        if 'date_out' in enriched_member and 'dateOut' not in enriched_member:
            enriched_member['dateOut'] = enriched_member.pop('date_out')
        
        # Validate date formats (ISO 8601)
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$')
        
        if 'dateIn' in enriched_member and enriched_member['dateIn']:
            if not date_pattern.match(str(enriched_member['dateIn'])):
                errors.append(f"team[{idx}].dateIn must be ISO 8601 format")
        
        if 'dateOut' in enriched_member and enriched_member['dateOut']:
            if not date_pattern.match(str(enriched_member['dateOut'])):
                errors.append(f"team[{idx}].dateOut must be ISO 8601 format")
        
        enriched.append(enriched_member)
    
    return enriched, errors


def validate_and_enrich_pricing(pricing: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validate and enrich pricing information.
    
    Args:
        pricing: Pricing dictionary
        
    Returns:
        Tuple of (enriched_pricing, validation_errors)
    """
    if not isinstance(pricing, dict):
        return {}, ["pricing must be a dictionary"]
    
    enriched = pricing.copy()
    errors = []
    
    # Normalize field names
    if 'price_amount' in enriched and 'priceAmount' not in enriched:
        enriched['priceAmount'] = enriched.pop('price_amount')
    
    if 'price_currency' in enriched and 'priceCurrency' not in enriched:
        enriched['priceCurrency'] = enriched.pop('price_currency')
    
    if 'price_unit' in enriched and 'priceUnit' not in enriched:
        enriched['priceUnit'] = enriched.pop('price_unit')
    
    # Validate priceAmount (should be numeric)
    if 'priceAmount' in enriched and enriched['priceAmount']:
        try:
            float(enriched['priceAmount'])
        except (ValueError, TypeError):
            errors.append("pricing.priceAmount must be numeric")
    
    # Validate priceCurrency (ISO 4217)
    if 'priceCurrency' in enriched and enriched['priceCurrency']:
        currency = str(enriched['priceCurrency']).upper()
        # Common currencies
        valid_currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'INR', 'BRL']
        if currency not in valid_currencies and len(currency) != 3:
            errors.append("pricing.priceCurrency should be ISO 4217 format (3 letters)")
        enriched['priceCurrency'] = currency
    
    # Validate priceUnit
    if 'priceUnit' in enriched and enriched['priceUnit']:
        unit = str(enriched['priceUnit']).lower()
        valid_units = ['per_request', 'per_gb', 'per_hour', 'per_month', 'per_year', 'one_time']
        if unit not in valid_units:
            # Normalize common units
            unit_map = {
                'request': 'per_request',
                'gb': 'per_gb',
                'hour': 'per_hour',
                'month': 'per_month',
                'year': 'per_year',
                'onetime': 'one_time',
                'one-time': 'one_time',
            }
            enriched['priceUnit'] = unit_map.get(unit, unit)
    
    return enriched, errors


def validate_and_enrich_lineage(lineage: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Validate and enrich lineage entries.
    
    Args:
        lineage: List of lineage dictionaries
        
    Returns:
        Tuple of (enriched_lineage, validation_errors)
    """
    if not isinstance(lineage, list):
        return [], ["lineage must be a list"]
    
    enriched = []
    errors = []
    
    for idx, entry in enumerate(lineage):
        if not isinstance(entry, dict):
            errors.append(f"lineage[{idx}] must be a dictionary")
            continue
        
        enriched_entry = entry.copy()
        
        # Normalize field names
        if 'input_fields' in enriched_entry and 'inputFields' not in enriched_entry:
            enriched_entry['inputFields'] = enriched_entry.pop('input_fields')
        
        if 'transform_source_objects' in enriched_entry and 'inputFields' not in enriched_entry:
            enriched_entry['inputFields'] = enriched_entry.pop('transform_source_objects')
        
        if 'transformations' in enriched_entry:
            if isinstance(enriched_entry['transformations'], list):
                for t_idx, transform in enumerate(enriched_entry['transformations']):
                    if isinstance(transform, dict):
                        if 'logic' not in transform and 'transformLogic' in transform:
                            transform['logic'] = transform.pop('transformLogic')
                        if 'description' not in transform and 'transformDescription' in transform:
                            transform['description'] = transform.pop('transformDescription')
        
        # Validate inputFields structure
        if 'inputFields' in enriched_entry:
            input_fields = enriched_entry['inputFields']
            if isinstance(input_fields, list):
                parsed_fields = []
                for f_idx, field in enumerate(input_fields):
                    if isinstance(field, dict):
                        # Validate reference format: namespace/name/model/field
                        if 'contract' in field or 'namespace' in field or 'name' in field:
                            # Valid reference dict
                            parsed_fields.append(field)
                        else:
                            # Invalid dict structure, keep as-is
                            parsed_fields.append(field)
                    elif isinstance(field, str):
                        # Try to parse as string reference: namespace/name/model/field
                        parts = field.split('/')
                        if len(parts) >= 2:
                            parsed_fields.append({
                                'namespace': parts[0] if len(parts) > 0 else '',
                                'name': parts[1] if len(parts) > 1 else '',
                                'model_name': parts[2] if len(parts) > 2 else None,
                                'field': parts[3] if len(parts) > 3 else None,
                            })
                        else:
                            # Invalid string format, keep as-is
                            parsed_fields.append(field)
                    else:
                        # Unknown type, keep as-is
                        parsed_fields.append(field)
                enriched_entry['inputFields'] = parsed_fields
        
        enriched.append(enriched_entry)
    
    return enriched, errors


def validate_and_enrich_advanced_schema_attributes(model: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validate and enrich advanced schema attributes.
    
    Args:
        model: Model dictionary with schema attributes
        
    Returns:
        Tuple of (enriched_model, validation_errors)
    """
    if not isinstance(model, dict):
        return {}, ["model must be a dictionary"]
    
    enriched = model.copy()
    errors = []
    
    # Normalize logical/physical type fields
    if 'logicalType' in enriched and 'logical_type' not in enriched:
        enriched['logical_type'] = enriched.get('logicalType')
    
    if 'physicalType' in enriched and 'physical_type' not in enriched:
        enriched['physical_type'] = enriched.get('physicalType')
    
    if 'physicalName' in enriched and 'physical_name' not in enriched:
        enriched['physical_name'] = enriched.get('physicalName')
    
    if 'dataGranularityDescription' in enriched and 'data_granularity_description' not in enriched:
        enriched['data_granularity_description'] = enriched.get('dataGranularityDescription')
    
    # Validate logical type (common values)
    if 'logical_type' in enriched and enriched['logical_type']:
        logical_type = str(enriched['logical_type']).lower()
        common_types = ['table', 'view', 'stream', 'topic', 'queue', 'file', 'api']
        # Allow any value but normalize common ones
        if logical_type in common_types:
            enriched['logical_type'] = logical_type
    
    # Validate physical type (common values)
    if 'physical_type' in enriched and enriched['physical_type']:
        physical_type = str(enriched['physical_type']).lower()
        common_types = ['postgresql', 'mysql', 'snowflake', 'bigquery', 's3', 'kafka', 'api']
        # Allow any value but normalize common ones
        if physical_type in common_types:
            enriched['physical_type'] = physical_type
    
    return enriched, errors

