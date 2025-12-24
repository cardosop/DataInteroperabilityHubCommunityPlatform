#!/usr/bin/env python3
"""
ODPS Formatting Tool

Formats ODPS (Open Data Product Standard) files in both JSON and YAML formats.
Ensures consistent formatting, indentation, and structure.

Usage:
    python scripts/format_odps.py [--format json|yaml] [--in-place] [file...]

Exit codes:
    0: All files are formatted correctly
    1: One or more files need formatting or have errors
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hub.apps.contracts.odps_generator import format_odps_as_json, format_odps_as_yaml
from hub.apps.contracts.odps_errors import ODPSExportError


class ODPSFormatter:
    """ODPS file formatter"""

    def __init__(self, in_place: bool = False, json_indent: int = 2, yaml_indent: int = 2):
        self.in_place = in_place
        self.json_indent = json_indent
        self.yaml_indent = yaml_indent
        self.formatted_count = 0
        self.error_count = 0

    def format_file(self, file_path: Path, target_format: Optional[str] = None) -> bool:
        """
        Format a single ODPS file.

        Args:
            file_path: Path to the ODPS file
            target_format: Target format ('json' or 'yaml'), None for auto-detect

        Returns:
            True if file is formatted correctly, False otherwise
        """
        if not file_path.exists():
            print(f"❌ {file_path}: File does not exist")
            self.error_count += 1
            return False

        # Determine file format
        if target_format:
            file_format = target_format
        elif file_path.suffix in ['.yaml', '.yml']:
            file_format = 'yaml'
        elif file_path.suffix == '.json':
            file_format = 'json'
        else:
            print(f"❌ {file_path}: Unknown file format")
            self.error_count += 1
            return False

        try:
            # Load file
            if file_format == 'yaml':
                if not YAML_AVAILABLE or yaml is None:
                    print(f"❌ {file_path}: PyYAML is not available")
                    self.error_count += 1
                    return False
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
            else:  # json
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            if not isinstance(data, dict):
                print(f"❌ {file_path}: ODPS document must be a dictionary")
                self.error_count += 1
                return False

            # Format using ODPS formatters
            if file_format == 'yaml':
                formatted = format_odps_as_yaml(
                    data,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False
                )
            else:  # json
                formatted = format_odps_as_json(
                    data,
                    indent=self.json_indent,
                    ensure_ascii=False
                )

            # Check if formatting changed
            original_content = file_path.read_text(encoding='utf-8')
            needs_formatting = original_content.strip() != formatted.strip()

            if needs_formatting:
                if self.in_place:
                    file_path.write_text(formatted, encoding='utf-8')
                    print(f"✅ {file_path}: Formatted")
                    self.formatted_count += 1
                    return True
                else:
                    print(f"⚠️  {file_path}: Needs formatting (use --in-place to fix)")
                    self.error_count += 1
                    return False
            else:
                print(f"✅ {file_path}: Already formatted correctly")
                return True

        except json.JSONDecodeError as e:
            print(f"❌ {file_path}: Invalid JSON: {e}")
            self.error_count += 1
            return False
        except Exception as e:
            # Check if it's a YAML error
            if YAML_AVAILABLE and yaml is not None and isinstance(e, yaml.YAMLError):
                print(f"❌ {file_path}: Invalid YAML: {e}")
            elif isinstance(e, ODPSExportError):
                print(f"❌ {file_path}: ODPS formatting error: {e}")
            else:
                print(f"❌ {file_path}: Error: {e}")
            self.error_count += 1
            return False

    def format_directory(self, directory: Path, pattern: str = "**/*.{json,yaml,yml}") -> bool:
        """
        Format all ODPS files in a directory.

        Args:
            directory: Directory to format
            pattern: Glob pattern for files to format

        Returns:
            True if all files are formatted correctly, False otherwise
        """
        if not directory.exists():
            print(f"❌ {directory}: Directory does not exist")
            self.error_count += 1
            return False

        all_valid = True
        for file_path in directory.glob(pattern):
            if file_path.is_file():
                if not self.format_file(file_path):
                    all_valid = False

        return all_valid

    def print_summary(self) -> None:
        """Print formatting summary"""
        if self.formatted_count > 0:
            print(f"\n✅ Formatted {self.formatted_count} file(s)")
        if self.error_count > 0:
            print(f"❌ {self.error_count} file(s) need formatting or have errors")
        elif self.formatted_count == 0:
            print("\n✅ All files are already formatted correctly")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Format ODPS (Open Data Product Standard) files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check formatting (dry run)
  python scripts/format_odps.py tests/fixtures/odps/v4.1/valid/sample-valid-v4.1.json

  # Format files in place
  python scripts/format_odps.py --in-place tests/fixtures/odps/v4.1/valid/

  # Format with custom JSON indentation
  python scripts/format_odps.py --json-indent 4 --in-place file.json
        """
    )
    parser.add_argument(
        'files',
        nargs='*',
        type=Path,
        help='ODPS files or directories to format'
    )
    parser.add_argument(
        '--in-place',
        action='store_true',
        help='Format files in place (modify files)'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'yaml'],
        help='Target file format (auto-detected if not specified)'
    )
    parser.add_argument(
        '--json-indent',
        type=int,
        default=2,
        help='JSON indentation level (default: 2)'
    )
    parser.add_argument(
        '--yaml-indent',
        type=int,
        default=2,
        help='YAML indentation level (default: 2)'
    )

    args = parser.parse_args()

    formatter = ODPSFormatter(
        in_place=args.in_place,
        json_indent=args.json_indent,
        yaml_indent=args.yaml_indent
    )

    if not args.files:
        # Default: format all ODPS fixtures
        default_dir = project_root / "tests" / "fixtures" / "odps"
        if default_dir.exists():
            print(f"Formatting ODPS files in {default_dir}...")
            all_valid = formatter.format_directory(default_dir)
        else:
            print("No files specified and default directory not found")
            parser.print_help()
            sys.exit(1)
    else:
        all_valid = True
        for file_path in args.files:
            if file_path.is_file():
                if not formatter.format_file(file_path, target_format=args.format):
                    all_valid = False
            elif file_path.is_dir():
                if not formatter.format_directory(file_path):
                    all_valid = False
            else:
                print(f"Error: {file_path} is not a file or directory")
                all_valid = False

    formatter.print_summary()

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()

