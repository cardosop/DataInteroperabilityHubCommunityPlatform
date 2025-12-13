"""
Context Fields Promotion

Moves context fields from extensions to info section in HubContract.
"""
from typing import Dict, Any, Optional


def promote_context_fields(hub_contract: Dict[str, Any], original_contract: Dict[str, Any]) -> Dict[str, Any]:
    """
    Promote context fields from extensions to info section.
    
    Moves the following fields from extensions to info:
    - status -> info.status
    - domain -> info.domain
    - tenant -> info.tenant
    - dataProduct -> info.dataProduct
    - links -> info.links
    - authoritativeDefinitions -> info.authoritativeDefinitions
    
    Args:
        hub_contract: HubContract dictionary
        original_contract: Original contract data (for extracting from extensions)
    
    Returns:
        HubContract with context fields promoted to info section
    """
    if not isinstance(hub_contract, dict):
        hub_contract = {}
    
    # Ensure info section exists
    if 'info' not in hub_contract:
        hub_contract['info'] = {}
    
    # Get extensions (from hub_contract or original_contract)
    extensions = hub_contract.get('extensions', {})
    if not extensions and isinstance(original_contract, dict):
        # Try to get from original contract extensions
        if 'extensions' in original_contract:
            extensions = original_contract['extensions']
        elif 'x-' in str(original_contract):
            # Check for x-prefixed fields (common extension pattern)
            extensions = {k: v for k, v in original_contract.items() if k.startswith('x-')}
    
    # Context fields to promote
    context_fields = {
        'status': 'status',
        'domain': 'domain',
        'tenant': 'tenant',
        'dataProduct': 'dataProduct',
        'links': 'links',
        'authoritativeDefinitions': 'authoritativeDefinitions',
    }
    
    # Check both extensions and top-level of original contract
    source_data = {}
    if isinstance(extensions, dict):
        source_data.update(extensions)
    if isinstance(original_contract, dict):
        # Check top-level for context fields
        for field in context_fields.keys():
            if field in original_contract and field not in source_data:
                source_data[field] = original_contract[field]
    
    # Promote fields to info section
    for source_field, target_field in context_fields.items():
        if source_field in source_data:
            value = source_data[source_field]
            # Only promote if not already in info
            if target_field not in hub_contract['info']:
                hub_contract['info'][target_field] = value
    
    return hub_contract


def extract_context_fields_from_extensions(extensions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract context fields from extensions dictionary.
    
    Args:
        extensions: Extensions dictionary
    
    Returns:
        Dictionary of context fields found in extensions
    """
    if not isinstance(extensions, dict):
        return {}
    
    context_fields = {}
    context_field_names = ['status', 'domain', 'tenant', 'dataProduct', 'links', 'authoritativeDefinitions']
    
    for field_name in context_field_names:
        if field_name in extensions:
            context_fields[field_name] = extensions[field_name]
    
    return context_fields

