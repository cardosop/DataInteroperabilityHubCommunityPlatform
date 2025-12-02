#!/usr/bin/env python
"""
Fix broken imports where pytestmark was inserted in the middle of import statements.
"""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

BROKEN_FILES = [
    'hub/apps/datasets/tests/test_schema_inference.py',
    'hub/apps/marketplace/tests/test_access_utils.py',
    'hub/apps/marketplace/tests/test_serializers.py',
    'hub/apps/marketplace/tests/test_models.py',
    'hub/apps/contracts/tests/test_serializers.py',
    'hub/apps/contracts/tests/test_models.py',
    'hub/apps/contracts/tests/test_cli_client.py',
    'hub/apps/observability/tests/test_metrics.py',
    'hub/apps/jobs/tests/test_utils.py',
    'tests/e2e/test_marketplace_purchase_flow.py',
]


def fix_broken_imports(file_path: Path):
    """Fix broken import statements"""
    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Find pytestmark line
        pytestmark_idx = None
        for i, line in enumerate(lines):
            if 'pytestmark = pytest.mark.django_db(transaction=True)' in line:
                pytestmark_idx = i
                break
        
        if pytestmark_idx is None:
            return False
        
        # Check if it's in the middle of an import
        # Look backwards for opening paren
        in_import = False
        paren_count = 0
        import_start = None
        
        for i in range(pytestmark_idx - 1, -1, -1):
            line = lines[i]
            if ')' in line:
                break
            if '(' in line and ('import' in line or 'from' in lines[max(0, i-1)]):
                # Found opening of import
                in_import = True
                import_start = i
                break
        
        if in_import:
            # Remove pytestmark from wrong location
            lines.pop(pytestmark_idx)
            # Also remove blank line if present
            if pytestmark_idx < len(lines) and lines[pytestmark_idx].strip() == '':
                lines.pop(pytestmark_idx)
            
            # Find where to place pytestmark (after all imports)
            insert_idx = None
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].startswith('import ') or lines[i].startswith('from '):
                    # Find the end of this import block
                    j = i + 1
                    while j < len(lines) and (lines[j].startswith(' ') or lines[j].strip() == '' or lines[j].startswith(')')):
                        j += 1
                    insert_idx = j
                    break
            
            if insert_idx is not None:
                # Insert blank line and pytestmark
                if insert_idx < len(lines) and lines[insert_idx].strip() != '':
                    lines.insert(insert_idx, '')
                    insert_idx += 1
                lines.insert(insert_idx, 'pytestmark = pytest.mark.django_db(transaction=True)')
                
                new_content = '\n'.join(lines)
                file_path.write_text(new_content, encoding='utf-8')
                return True
        
        return False
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


def main():
    """Fix all broken files"""
    fixed = 0
    for rel_path in BROKEN_FILES:
        file_path = PROJECT_ROOT / rel_path
        if file_path.exists():
            if fix_broken_imports(file_path):
                print(f"✅ Fixed: {rel_path}")
                fixed += 1
            else:
                print(f"⏭️  Skipped: {rel_path}")
    
    print(f"\n✅ Fixed {fixed} files")


if __name__ == '__main__':
    main()

