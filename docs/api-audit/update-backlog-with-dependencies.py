#!/usr/bin/env python3
"""
Update Backlog with Dependencies

This script updates the API development backlog file with dependency information
from the API dependencies document.

Usage:
    python update-backlog-with-dependencies.py
"""

import re
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict


def load_dependencies(deps_file: str) -> Dict[str, List[str]]:
    """Load dependencies from API dependencies document"""
    dependencies = defaultdict(list)
    
    with open(deps_file, 'r') as f:
        content = f.read()
    
    # Extract dependency table entries
    # Pattern: | `dependent_api` | `depends_on_api` | ...
    pattern = r'\|\s+`([^`]+)`\s+\|\s+`([^`]+)`\s+\|\s+([^|]+)\s+\|\s+([^|]+)\s+\|\s+([^|]+)'
    
    for match in re.finditer(pattern, content):
        dependent = match.group(1).strip()
        depends_on = match.group(2).strip()
        dep_type = match.group(3).strip()
        description = match.group(4).strip()
        source = match.group(5).strip()
        
        dependencies[dependent].append({
            'api': depends_on,
            'type': dep_type,
            'description': description,
            'source': source
        })
    
    return dependencies


def update_backlog_with_dependencies(backlog_file: str, deps_file: str):
    """Update backlog file with dependency information"""
    
    dependencies = load_dependencies(deps_file)
    
    with open(backlog_file, 'r') as f:
        content = f.read()
    
    # Find each API endpoint section and add dependencies
    # Pattern: #### \d+\. (GET|POST|PUT|PATCH|DELETE) `/api/v1/...`
    
    updated_content = []
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        updated_content.append(line)
        
        # Check if this is an API endpoint header
        endpoint_match = re.search(r'#### \d+\.\s+(GET|POST|PUT|PATCH|DELETE)\s+`([^`]+)`', line)
        if endpoint_match:
            method = endpoint_match.group(1)
            path = endpoint_match.group(2)
            api_key = f"{method} {path}"
            
            # Look for the end of this section (next #### or ##)
            section_end = i + 1
            while section_end < len(lines):
                if lines[section_end].startswith('####') or lines[section_end].startswith('##'):
                    break
                section_end += 1
            
            # Check if dependencies section already exists
            has_dependencies = False
            for j in range(i + 1, section_end):
                if '**Dependencies**' in lines[j] or '**API Dependencies**' in lines[j]:
                    has_dependencies = True
                    break
            
            # Add dependencies if they exist and section doesn't have them
            if api_key in dependencies and not has_dependencies:
                # Find where to insert (after Description or Impact)
                insert_pos = i + 1
                found_description = False
                found_impact = False
                
                for j in range(i + 1, section_end):
                    if '**Description**' in lines[j]:
                        found_description = True
                    if '**Impact**' in lines[j]:
                        found_impact = True
                    if found_impact and (lines[j].strip() == '' or lines[j].startswith('**')):
                        insert_pos = j
                        break
                
                # Insert dependencies section
                deps_list = dependencies[api_key]
                if deps_list:
                    updated_content.append('')
                    updated_content.append('**API Dependencies**:')
                    updated_content.append('')
                    for dep in deps_list:
                        dep_type_short = dep['type'].replace('requires_', '').replace('_', ' ').title()
                        updated_content.append(f"- `{dep['api']}` ({dep_type_short}) - {dep['description']}")
                    updated_content.append('')
        
        i += 1
    
    # Write updated content
    with open(backlog_file, 'w') as f:
        f.write('\n'.join(updated_content))
    
    print(f"Updated {backlog_file} with dependency information")
    print(f"Added dependencies for {len([k for k, v in dependencies.items() if v])} APIs")


if __name__ == "__main__":
    backlog_file = "docs/api-audit/api-development-backlog.md"
    deps_file = "docs/api-audit/api-dependencies.md"
    
    if not Path(backlog_file).exists():
        print(f"Error: {backlog_file} not found")
        exit(1)
    
    if not Path(deps_file).exists():
        print(f"Error: {deps_file} not found")
        exit(1)
    
    update_backlog_with_dependencies(backlog_file, deps_file)

