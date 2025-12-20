#!/usr/bin/env python3
"""
Update Original Inventory with Categorization

This script updates the original inventory file with categorization information.
"""

from pathlib import Path
import re
from datetime import datetime

def update_inventory():
    """Update inventory file with categorization"""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    inventory_file = repo_root / 'docs' / 'api-audit' / 'current-api-inventory.md'
    categorized_file = repo_root / 'docs' / 'api-audit' / 'current-api-inventory-categorized.md'
    
    if not categorized_file.exists():
        print(f"Error: Categorized file not found")
        return 1
    
    # Read categorized content
    categorized_content = categorized_file.read_text(encoding='utf-8')
    
    # Extract summary statistics
    stats_match = re.search(r'## Summary Statistics\n\n(.*?)\n\n###', categorized_content, re.DOTALL)
    if not stats_match:
        print("Could not extract statistics from categorized file")
        return 1
    
    stats_section = stats_match.group(1)
    
    # Read original inventory
    if inventory_file.exists():
        content = inventory_file.read_text(encoding='utf-8')
        
        # Check if categorization already exists
        if '## Categorization' in content:
            # Update existing section
            pattern = re.compile(r'## Categorization\n\n.*?(?=\n## |$)', re.DOTALL)
            new_section = f"## Categorization\n\n{stats_section}\n\n"
            content = pattern.sub(new_section, content)
        else:
            # Insert after overview
            insertion_point = content.find('## Summary Statistics')
            if insertion_point > 0:
                new_content = content[:insertion_point]
                new_content += f"\n## Categorization\n\n{stats_section}\n\n"
                new_content += content[insertion_point:]
                content = new_content
            else:
                # Insert at beginning of document
                insertion_point = content.find('\n## ')
                if insertion_point > 0:
                    new_content = content[:insertion_point]
                    new_content += f"\n## Categorization\n\n{stats_section}\n\n"
                    new_content += content[insertion_point:]
                    content = new_content
        
        inventory_file.write_text(content, encoding='utf-8')
        print(f"✅ Updated {inventory_file.name} with categorization")
    else:
        print(f"Warning: Original inventory file not found at {inventory_file}")
    
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(update_inventory())

