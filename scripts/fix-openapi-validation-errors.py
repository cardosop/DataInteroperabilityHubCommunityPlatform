#!/usr/bin/env python3
"""
Fix OpenAPI Validation Errors

Automatically fixes common OpenAPI validation errors:
1. Removes trailing slashes from paths (or keeps them if they're intentional)
2. Fixes $ref siblings issues (removes example/description from $ref objects)
3. Fixes date-time format issues in examples
4. Fixes content type encoding issues
"""

import os
import sys
import yaml
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def fix_path_trailing_slash(spec: Dict[str, Any]) -> bool:
    """Remove trailing slashes from paths (OpenAPI best practice)."""
    fixed = False
    
    if 'paths' in spec:
        paths = spec['paths']
        new_paths = {}
        
        for path, path_item in paths.items():
            # Keep trailing slash for root paths or if it's intentional
            # But remove for most cases as per OpenAPI best practice
            if path.endswith('/') and path != '/':
                new_path = path.rstrip('/')
                new_paths[new_path] = path_item
                fixed = True
            else:
                new_paths[path] = path_item
        
        spec['paths'] = new_paths
    
    return fixed


def fix_ref_siblings(obj: Any, path: str = '') -> bool:
    """Fix $ref siblings by removing example/description from $ref objects."""
    fixed = False
    
    if isinstance(obj, dict):
        if '$ref' in obj:
            # Remove example and description if $ref is present
            if 'example' in obj:
                del obj['example']
                fixed = True
            if 'description' in obj:
                # Keep description but move it to the referenced schema if possible
                # For now, just remove it to fix validation
                del obj['description']
                fixed = True
        
        # Recursively fix nested objects
        for key, value in list(obj.items()):
            if fix_ref_siblings(value, f"{path}.{key}"):
                fixed = True
    
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if fix_ref_siblings(item, f"{path}[{i}]"):
                fixed = True
    
    return fixed


def fix_date_time_examples(obj: Any, parent_format: Optional[str] = None) -> bool:
    """Fix date-time format issues in examples."""
    fixed = False
    
    if isinstance(obj, dict):
        # Check for date-time fields
        current_format = obj.get('format', parent_format)
        
        if current_format == 'date-time':
            # Fix example if it's not a valid date-time
            if 'example' in obj:
                example = obj['example']
                if isinstance(example, str):
                    # Check if it's already valid ISO 8601
                    if not re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', example):
                        # If it's not a date-time, remove the format or change example
                        # For time_range, it might be a string like "last_month", so remove format
                        if example in ['last_month', 'last_week', 'last_year', 'today', 'yesterday']:
                            # This is not a date-time, remove format
                            if 'format' in obj:
                                del obj['format']
                                fixed = True
                        else:
                            # Try to fix common issues
                            if 'Z' not in example and '+' not in example and re.match(r'^\d{4}-\d{2}-\d{2}', example):
                                obj['example'] = example + 'T00:00:00Z'
                                fixed = True
        
        # Recursively fix nested objects
        for key, value in list(obj.items()):
            if fix_date_time_examples(value, current_format):
                fixed = True
    
    elif isinstance(obj, list):
        for item in obj:
            if fix_date_time_examples(item, parent_format):
                fixed = True
    
    return fixed


def fix_content_type_encoding(spec: Dict[str, Any]) -> bool:
    """Fix content type encoding issues (application~1json -> application/json)."""
    fixed = False
    
    def fix_in_object(obj: Any) -> bool:
        local_fixed = False
        
        if isinstance(obj, dict):
            # Check for content objects
            if 'content' in obj:
                content = obj['content']
                if isinstance(content, dict):
                    new_content = {}
                    for key, value in content.items():
                        # Fix encoded content type
                        if '~1' in key:
                            new_key = key.replace('~1', '/')
                            new_content[new_key] = value
                            local_fixed = True
                        else:
                            new_content[key] = value
                    obj['content'] = new_content
            
            # Recursively fix nested objects
            for key, value in list(obj.items()):
                if fix_in_object(value):
                    local_fixed = True
        
        elif isinstance(obj, list):
            for item in obj:
                if fix_in_object(item):
                    local_fixed = True
        
        return local_fixed
    
    return fix_in_object(spec)


def fix_spec_file(file_path: Path) -> bool:
    """Fix validation errors in a single OpenAPI spec file."""
    print(f"\nFixing: {file_path.relative_to(PROJECT_ROOT)}")
    
    try:
        # Read spec
        with open(file_path, 'r', encoding='utf-8') as f:
            spec = yaml.safe_load(f)
        
        if not spec:
            print(f"  ⚠️  Empty or invalid spec file")
            return False
        
        fixed = False
        
        # Fix path trailing slashes
        if fix_path_trailing_slash(spec):
            print(f"  ✅ Fixed path trailing slashes")
            fixed = True
        
        # Fix $ref siblings
        if fix_ref_siblings(spec):
            print(f"  ✅ Fixed $ref siblings")
            fixed = True
        
        # Fix date-time examples
        if fix_date_time_examples(spec):
            print(f"  ✅ Fixed date-time examples")
            fixed = True
        
        # Fix content type encoding
        if fix_content_type_encoding(spec):
            print(f"  ✅ Fixed content type encoding")
            fixed = True
        
        # Write fixed spec
        if fixed:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(spec, f, default_flow_style=False, sort_keys=False,
                         allow_unicode=True, width=120, indent=2)
            print(f"  ✅ Saved fixes")
            return True
        else:
            print(f"  ℹ️  No fixes needed")
            return False
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        raise


def main():
    """Main entry point."""
    contracts_dir = PROJECT_ROOT / 'docs' / 'api-contracts' / 'missing'
    
    if not contracts_dir.exists():
        print(f"❌ Directory not found: {contracts_dir}")
        sys.exit(1)
    
    print("=" * 80)
    print("Fixing OpenAPI Validation Errors")
    print("=" * 80)
    print(f"Fixing specs in: {contracts_dir.relative_to(PROJECT_ROOT)}")
    
    spec_files = list(contracts_dir.rglob("*.yaml")) + list(contracts_dir.rglob("*.yml"))
    fixed_count = 0
    
    for spec_file in sorted(spec_files):
        if spec_file.name == "README.md":
            continue
        
        if fix_spec_file(spec_file):
            fixed_count += 1
    
    print("\n" + "=" * 80)
    print(f"✅ Fixed {fixed_count} OpenAPI spec files!")


if __name__ == '__main__':
    main()

