#!/usr/bin/env python3
"""
Comprehensive OpenAPI Schema Validation and Enhancement

Validates and enhances all OpenAPI 3.0 specifications with:
- Complete validation rules (required fields, types, formats, enums, min/max, patterns)
- Default values where appropriate
- Comprehensive examples
- Better documentation
"""

import os
import sys
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def validate_and_enhance_specs():
    """Validate and enhance all OpenAPI specs."""
    specs_dir = PROJECT_ROOT / 'docs' / 'api-contracts' / 'missing'
    errors = []
    enhanced_count = 0
    
    for spec_file in sorted(specs_dir.rglob('*.yaml')):
        if spec_file.name == 'README.md':
            continue
        
        print(f"\n{'='*80}")
        print(f"Processing: {spec_file.relative_to(PROJECT_ROOT)}")
        print('='*80)
        
        try:
            # Read spec
            with open(spec_file, 'r', encoding='utf-8') as f:
                spec = yaml.safe_load(f)
            
            # Validate
            if 'openapi' not in spec:
                errors.append(f'{spec_file}: Missing openapi version')
                continue
            if 'info' not in spec:
                errors.append(f'{spec_file}: Missing info section')
                continue
            if 'paths' not in spec:
                errors.append(f'{spec_file}: Missing paths section')
                continue
            
            # Enhance schemas
            if 'components' in spec and 'schemas' in spec['components']:
                schemas = spec['components']['schemas']
                for schema_name, schema in schemas.items():
                    if isinstance(schema, dict):
                        enhanced = enhance_schema_comprehensively(schema, schema_name)
                        if enhanced != schema:
                            schemas[schema_name] = enhanced
                            enhanced_count += 1
                            print(f"  ✅ Enhanced schema: {schema_name}")
            
            # Write enhanced spec
            with open(spec_file, 'w', encoding='utf-8') as f:
                yaml.dump(spec, f, default_flow_style=False, sort_keys=False,
                         allow_unicode=True, width=120, indent=2)
            
            print(f"  ✅ File validated and enhanced")
            
        except Exception as e:
            errors.append(f'{spec_file}: {e}')
            print(f"  ❌ Error: {e}")
    
    print(f"\n{'='*80}")
    if errors:
        print(f"❌ Found {len(errors)} errors:")
        for error in errors:
            print(f"  {error}")
        return False
    else:
        print(f"✅ All {enhanced_count} schemas validated and enhanced successfully!")
        return True


def enhance_schema_comprehensively(schema, schema_name):
    """Comprehensively enhance a schema with validation rules, defaults, and examples."""
    if not isinstance(schema, dict) or schema.get('type') != 'object':
        return schema
    
    enhanced = schema.copy()
    properties = enhanced.get('properties', {})
    
    # Enhance all properties
    for prop_name, prop_schema in properties.items():
        if isinstance(prop_schema, dict):
            properties[prop_name] = enhance_property_comprehensively(
                prop_schema, prop_name, schema_name
            )
    
    enhanced['properties'] = properties
    return enhanced


def enhance_property_comprehensively(prop_schema, prop_name, parent_schema_name):
    """Comprehensively enhance a property with validation rules, defaults, and examples."""
    enhanced = prop_schema.copy()
    prop_type = enhanced.get('type')
    
    # Add validation rules based on type and property name
    if prop_type == 'string':
        # Add string validations
        if 'minLength' not in enhanced:
            if 'id' in prop_name.lower() and prop_name.endswith('_id'):
                enhanced['minLength'] = 36  # UUID length
                enhanced['maxLength'] = 36
            elif 'email' in prop_name.lower():
                enhanced['minLength'] = 5
                enhanced['maxLength'] = 255
            elif 'name' in prop_name.lower() or 'title' in prop_name.lower():
                enhanced['minLength'] = 1
                enhanced['maxLength'] = 255
            elif 'description' in prop_name.lower():
                enhanced['minLength'] = 0
                enhanced['maxLength'] = 1000
            elif 'content' in prop_name.lower():
                enhanced['minLength'] = 1
                enhanced['maxLength'] = 5000
            elif 'query' in prop_name.lower():
                enhanced['minLength'] = 3
                enhanced['maxLength'] = 500
            else:
                enhanced['minLength'] = 1
                enhanced['maxLength'] = 255
        
        # Add format if not present
        if 'format' not in enhanced:
            if 'email' in prop_name.lower():
                enhanced['format'] = 'email'
                enhanced['pattern'] = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            elif 'url' in prop_name.lower() or 'uri' in prop_name.lower():
                enhanced['format'] = 'uri'
            elif ('date' in prop_name.lower() or 'time' in prop_name.lower()) and 'at' in prop_name.lower():
                enhanced['format'] = 'date-time'
            elif 'id' in prop_name.lower() and prop_name.endswith('_id'):
                enhanced['format'] = 'uuid'
    
    elif prop_type == 'integer':
        # Add integer validations
        if 'minimum' not in enhanced:
            if 'rating' in prop_name.lower():
                enhanced['minimum'] = 1
                enhanced['maximum'] = 5
            elif 'limit' in prop_name.lower() or 'page_size' in prop_name.lower():
                enhanced['minimum'] = 1
                enhanced['maximum'] = 100
                enhanced['default'] = 10
            elif 'page' in prop_name.lower() or 'offset' in prop_name.lower():
                enhanced['minimum'] = 0
                enhanced['maximum'] = 10000
                enhanced['default'] = 0
            elif 'count' in prop_name.lower():
                enhanced['minimum'] = 0
            else:
                enhanced['minimum'] = 0
    
    elif prop_type == 'number':
        # Add number validations
        if 'minimum' not in enhanced:
            enhanced['minimum'] = 0
        if 'maximum' not in enhanced and 'confidence' in prop_name.lower():
            enhanced['maximum'] = 1
    
    elif prop_type == 'array':
        # Add array validations
        if 'minItems' not in enhanced:
            enhanced['minItems'] = 0
        if 'maxItems' not in enhanced:
            enhanced['maxItems'] = 1000
    
    # Add example if not present
    if 'example' not in enhanced:
        enhanced['example'] = generate_example(enhanced, prop_name)
    
    # Add description if not present
    if 'description' not in enhanced:
        enhanced['description'] = generate_description(enhanced, prop_name)
    
    return enhanced


def generate_example(prop_schema, prop_name):
    """Generate example value for property."""
    prop_type = prop_schema.get('type')
    format_type = prop_schema.get('format')
    enum_values = prop_schema.get('enum')
    
    if enum_values:
        return enum_values[0]
    
    if format_type == 'uuid':
        return '550e8400-e29b-41d4-a716-446655440000'
    elif format_type == 'email':
        return 'user@example.com'
    elif format_type == 'date-time':
        return '2025-01-15T10:30:00Z'
    elif format_type == 'date':
        return '2025-01-15'
    elif format_type == 'uri':
        return 'https://example.com'
    
    if prop_type == 'string':
        if 'id' in prop_name.lower():
            return f'{prop_name}_example'
        return f'example_{prop_name}'
    elif prop_type == 'integer':
        return prop_schema.get('minimum', 0) or 1
    elif prop_type == 'number':
        return 0.0
    elif prop_type == 'boolean':
        return False
    elif prop_type == 'array':
        return []
    elif prop_type == 'object':
        return {}
    
    return None


def generate_description(prop_schema, prop_name):
    """Generate description for property."""
    prop_type = prop_schema.get('type')
    format_type = prop_schema.get('format')
    
    # Convert snake_case to Title Case
    words = prop_name.replace('_', ' ').title()
    
    if format_type:
        return f'{words} ({format_type})'
    elif prop_type:
        return f'{words} ({prop_type})'
    else:
        return words


if __name__ == '__main__':
    success = validate_and_enhance_specs()
    sys.exit(0 if success else 1)

