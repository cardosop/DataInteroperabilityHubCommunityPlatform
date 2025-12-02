#!/usr/bin/env python3
"""
Script to remove remaining mocks from test files.

This script removes all @patch decorators and with patch() blocks
for service mocks, replacing them with real service calls.
"""
import re
import sys
from pathlib import Path

def remove_patch_decorators(content):
    """Remove @patch decorators for service mocks"""
    # Remove @patch decorators for ComplianceServiceClient, DQServiceClient, DataContractCLIClient
    patterns = [
        r"@patch\('hub\.apps\.compliance\.service_client\.ComplianceServiceClient\.scan_file'\)\s*\n",
        r"@patch\('hub\.apps\.dq\.service_client\.DQServiceClient\.run_dq'\)\s*\n",
        r"@patch\('hub\.apps\.contracts\.cli_client\.DataContractCLIClient\.validate'\)\s*\n",
        r"@patch\('hub\.apps\.files\.views\.S3StorageClient'\)\s*\n",
        r"@patch\('hub\.apps\.datasets\.views\.boto3'\)\s*\n",
    ]
    
    for pattern in patterns:
        content = re.sub(pattern, '', content)
    
    return content

def remove_with_patch_blocks(content):
    """Remove with patch() blocks for service mocks"""
    # This is more complex - need to handle nested blocks
    # For now, we'll do a simple replacement
    lines = content.split('\n')
    result = []
    skip_until_indent = None
    in_patch_block = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this is a with patch() line
        if 'with patch(' in line and any(service in line for service in [
            'ComplianceServiceClient', 'DQServiceClient', 'DataContractCLIClient',
            'S3StorageClient', 'boto3'
        ]):
            # Skip this line and find the matching block
            in_patch_block = True
            indent_level = len(line) - len(line.lstrip())
            i += 1
            continue
        
        # If we're in a patch block, check if we've exited
        if in_patch_block:
            current_indent = len(line) - len(line.lstrip()) if line.strip() else 999
            if line.strip() and current_indent <= indent_level:
                in_patch_block = False
                # Don't skip this line, it's the line after the block
            else:
                # Skip this line (it's inside the patch block)
                i += 1
                continue
        
        result.append(line)
        i += 1
    
    return '\n'.join(result)

def fix_file(file_path):
    """Fix a single test file"""
    print(f"Processing {file_path}...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Remove patch decorators
    content = remove_patch_decorators(content)
    
    # Remove unused imports
    if 'from unittest.mock import' in content:
        # Check if Mock, MagicMock, patch are still used
        if 'Mock(' not in content and 'MagicMock(' not in content and '@patch' not in content and 'with patch(' not in content:
            # Remove the import
            content = re.sub(r"from unittest\.mock import[^\n]*\n", '', content)
            content = re.sub(r"import unittest\.mock[^\n]*\n", '', content)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"  ✅ Updated {file_path}")
        return True
    else:
        print(f"  ⏭️  No changes needed for {file_path}")
        return False

if __name__ == '__main__':
    # Files to process
    test_files = [
        'hub/apps/contracts/tests/test_integration_onboarding.py',
        'tests/e2e/test_data_first_comprehensive.py',
        'tests/e2e/test_contract_first_comprehensive.py',
        'tests/e2e/test_contract_only_comprehensive.py',
    ]
    
    changed = 0
    for test_file in test_files:
        file_path = Path(test_file)
        if file_path.exists():
            if fix_file(file_path):
                changed += 1
        else:
            print(f"  ⚠️  File not found: {test_file}")
    
    print(f"\n✅ Processed {len(test_files)} files, {changed} changed")

