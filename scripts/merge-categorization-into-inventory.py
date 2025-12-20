#!/usr/bin/env python3
"""
Merge Categorization into Original Inventory

This script merges categorization information into the original inventory file,
adding categorization columns to the endpoint tables.
"""

from pathlib import Path
import re
from datetime import datetime

def merge_categorization():
    """Merge categorization into inventory"""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    inventory_file = repo_root / 'docs' / 'api-audit' / 'codebase-endpoints-inventory.md'
    categorized_file = repo_root / 'docs' / 'api-audit' / 'current-api-inventory-categorized.md'
    
    if not categorized_file.exists():
        print(f"Error: Categorized file not found")
        return 1
    
    # Read categorized content to build lookup
    categorized_content = categorized_file.read_text(encoding='utf-8')
    
    # Extract categorization for each endpoint
    endpoint_categories = {}
    
    # Parse the complete endpoint table
    table_pattern = re.compile(
        r'\| (\w+)\s+\|\s+`([^`]+)`\s+\|\s+([^|]+)\s+\|\s+([^|]+)\s+\|\s+([^|]+)\s+\|\s+([^|]+)\s+\|\s+([^|]+)\s+\|',
        re.MULTILINE
    )
    
    for match in table_pattern.finditer(categorized_content):
        method = match.group(1)
        path = match.group(2)
        feature_type = match.group(3).strip()
        status = match.group(4).strip()
        completeness = match.group(5).strip()
        schema = match.group(6).strip()
        tests = match.group(7).strip()
        deprecated = match.group(8).strip()
        
        key = f"{method}:{path}"
        endpoint_categories[key] = {
            'feature_type': feature_type,
            'status': status,
            'completeness': completeness,
            'schema': schema,
            'tests': tests,
            'deprecated': deprecated
        }
    
    # Read original inventory
    if not inventory_file.exists():
        print(f"Warning: Inventory file not found at {inventory_file}")
        return 1
    
    content = inventory_file.read_text(encoding='utf-8')
    
    # Update tables with categorization
    # Pattern: | Method | Path | View | Action | Description |
    table_header_pattern = re.compile(
        r'(\|\s*Method\s*\|\s*Path\s*\|\s*View\s*\|\s*Action\s*\|\s*Description\s*\|)',
        re.MULTILINE
    )
    
    def update_table(match):
        header = match.group(1)
        # Add categorization columns
        new_header = header.rstrip('|') + ' | Feature Type | Status | Completeness | Schema | Tests | Deprecated |'
        return new_header
    
    content = table_header_pattern.sub(update_table, content)
    
    # Update table rows
    table_row_pattern = re.compile(
        r'\| (GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+\|\s+`([^`]+)`\s+\|\s+`?([^|`]+)`?\s+\|\s+([^|]+)\s+\|\s+([^|]+)\s+\|',
        re.MULTILINE
    )
    
    def update_row(match):
        method = match.group(1)
        path = match.group(2)
        view = match.group(3).strip()
        action = match.group(4).strip()
        description = match.group(5).strip()
        
        key = f"{method}:{path}"
        cat = endpoint_categories.get(key, {})
        
        feature_type = cat.get('feature_type', '-')
        status = cat.get('status', '-')
        completeness = cat.get('completeness', '-').split('(')[0].strip()  # Shorten
        schema = cat.get('schema', '❌')
        tests = cat.get('tests', '❌')
        deprecated = cat.get('deprecated', '-')
        
        return f"| {method} | `{path}` | `{view}` | {action} | {description} | {feature_type} | {status} | {completeness} | {schema} | {tests} | {deprecated} |"
    
    content = table_row_pattern.sub(update_row, content)
    
    # Add categorization summary at the top
    stats_match = re.search(r'## Summary Statistics\n\n(.*?)\n\n###', categorized_content, re.DOTALL)
    if stats_match:
        stats_section = stats_match.group(1)
        
        # Insert after overview
        if '## Categorization' not in content:
            insertion_point = content.find('## Extraction Methodology')
            if insertion_point > 0:
                new_content = content[:insertion_point]
                new_content += f"\n## Categorization\n\n{stats_section}\n\n"
                new_content += content[insertion_point:]
                content = new_content
    
    # Update last updated date
    content = re.sub(
        r'\*\*Last Updated\*\*:.*',
        f'**Last Updated**: {datetime.now().strftime("%Y-%m-%d")}',
        content
    )
    
    inventory_file.write_text(content, encoding='utf-8')
    print(f"✅ Updated {inventory_file.name} with categorization")
    
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(merge_categorization())

