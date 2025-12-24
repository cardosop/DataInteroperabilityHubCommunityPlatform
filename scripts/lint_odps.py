#!/usr/bin/env python3
"""
ODPS Linting Tool

Lints ODPS (Open Data Product Standard) files in both JSON and YAML formats.
Validates structure, required fields, schema URLs, and ODPS-specific rules.

Usage:
    python scripts/lint_odps.py [--format json|yaml] [--strict] [file...]

Exit codes:
    0: All files are valid
    1: One or more files have linting errors
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hub.apps.contracts.odps_parser import ODPSParser
from hub.apps.contracts.odps_version_detection import detect_odps_version
from hub.apps.contracts.odps_errors import ODPSValidationError


class ODPSLinter:
    """ODPS file linter"""

    def __init__(self, strict: bool = False):
        self.strict = strict
        self.errors: List[Tuple[str, str]] = []  # List of (file_path, error_message)
        self.warnings: List[Tuple[str, str]] = []  # List of (file_path, warning_message)

    def lint_file(self, file_path: Path) -> bool:
        """
        Lint a single ODPS file.

        Args:
            file_path: Path to the ODPS file

        Returns:
            True if file is valid, False otherwise
        """
        if not file_path.exists():
            self.errors.append((str(file_path), "File does not exist"))
            return False

        # Determine file format
        if file_path.suffix in ['.yaml', '.yml']:
            return self._lint_yaml_file(file_path)
        elif file_path.suffix == '.json':
            return self._lint_json_file(file_path)
        else:
            self.errors.append((str(file_path), f"Unknown file format: {file_path.suffix}"))
            return False

    def _lint_yaml_file(self, file_path: Path) -> bool:
        """Lint a YAML ODPS file"""
        if not YAML_AVAILABLE or yaml is None:
            self.errors.append((str(file_path), "PyYAML is not available"))
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                data = yaml.safe_load(content)

            if data is None:
                self.errors.append((str(file_path), "YAML file is empty or invalid"))
                return False

            return self._lint_odps_content(data, file_path, 'yaml')
        except Exception as e:
            # Check if it's a YAML error
            if YAML_AVAILABLE and yaml is not None and isinstance(e, yaml.YAMLError):
                self.errors.append((str(file_path), f"Invalid YAML: {e}"))
            else:
                self.errors.append((str(file_path), f"Error reading file: {e}"))
            return False

    def _lint_json_file(self, file_path: Path) -> bool:
        """Lint a JSON ODPS file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return self._lint_odps_content(data, file_path, 'json')
        except json.JSONDecodeError as e:
            self.errors.append((str(file_path), f"Invalid JSON: {e}"))
            return False
        except Exception as e:
            self.errors.append((str(file_path), f"Error reading file: {e}"))
            return False

    def _lint_odps_content(self, data: Dict[str, Any], file_path: Path, format: str) -> bool:
        """Lint ODPS content structure"""
        is_valid = True

        # Check if it's an ODPS document
        if not isinstance(data, dict):
            self.errors.append((str(file_path), "ODPS document must be a dictionary"))
            return False

        # Skip files that don't look like ODPS documents (e.g., reference files)
        # ODPS documents must have 'schema' field with opendataproducts.org URL
        has_odps_schema = (
            'schema' in data and
            isinstance(data['schema'], str) and
            'opendataproducts.org/schema' in data['schema']
        )

        if not has_odps_schema:
            # This might be a reference file, not a full ODPS document
            # Check if it's in a location where we expect ODPS documents
            file_path_str = str(file_path)
            is_expected_odps = (
                'valid' in file_path_str or
                'invalid' in file_path_str or
                'marketplace' in file_path_str or
                'multilingual' in file_path_str
            )

            if is_expected_odps:
                # In locations where we expect ODPS documents, this is an error
                self.errors.append((str(file_path), "File does not appear to be an ODPS document (missing schema URL with opendataproducts.org)"))
                is_valid = False
            else:
                # Reference files (like quality-rules.yaml) are OK
                self.warnings.append((str(file_path), "File does not appear to be an ODPS document (missing schema URL)"))

            # If we're in strict mode or it's an expected ODPS location, return the validation result
            if is_expected_odps:
                return is_valid
            # Otherwise, it's a reference file, so skip further validation
            return True

        # Check required top-level fields
        required_fields = ['schema', 'version', 'product']
        for field in required_fields:
            if field not in data:
                self.errors.append((str(file_path), f"Missing required field: {field}"))
                is_valid = False

        # Check schema URL format
        if 'schema' in data:
            schema = data['schema']
            if not isinstance(schema, str):
                self.errors.append((str(file_path), "Field 'schema' must be a string"))
                is_valid = False
            elif not schema.startswith('https://opendataproducts.org/schema/'):
                self.warnings.append((str(file_path), f"Schema URL should start with 'https://opendataproducts.org/schema/': {schema}"))

        # Check version format
        if 'version' in data:
            version = data['version']
            if not isinstance(version, str):
                self.errors.append((str(file_path), "Field 'version' must be a string"))
                is_valid = False

        # Check product structure
        if 'product' in data:
            product = data['product']
            if not isinstance(product, dict):
                self.errors.append((str(file_path), "Field 'product' must be a dictionary"))
                is_valid = False
            else:
                # Check product.details
                if 'details' not in product:
                    self.errors.append((str(file_path), "Field 'product.details' is required"))
                    is_valid = False
                elif isinstance(product.get('details'), dict):
                    details = product['details']
                    # Check for at least one language
                    if not details:
                        self.errors.append((str(file_path), "Field 'product.details' must contain at least one language"))
                        is_valid = False
                    else:
                        # Check each language has required fields
                        for lang, lang_data in details.items():
                            if not isinstance(lang_data, dict):
                                self.errors.append((str(file_path), f"Field 'product.details.{lang}' must be a dictionary"))
                                is_valid = False
                            else:
                                required_product_fields = ['productID', 'name']
                                for field in required_product_fields:
                                    if field not in lang_data:
                                        self.errors.append((str(file_path), f"Missing required field: product.details.{lang}.{field}"))
                                        is_valid = False

        # Validate using ODPSParser if available
        try:
            # Detect version
            detected_version = detect_odps_version(data)
            if detected_version == "unknown":
                self.warnings.append((str(file_path), "Could not detect ODPS version from document"))

            # Validate with ODPSParser
            is_valid_parser, validation_errors = ODPSParser.validate(
                odps_document=data,
                version=detected_version if detected_version != "unknown" else None
            )

            if not is_valid_parser:
                for error in validation_errors:
                    error_msg = str(error) if hasattr(error, '__str__') else repr(error)
                    self.errors.append((str(file_path), f"ODPS validation error: {error_msg}"))
                    is_valid = False
        except Exception as e:
            # If validation fails due to missing dependencies, warn but don't fail
            if self.strict:
                self.errors.append((str(file_path), f"ODPS validation failed: {e}"))
                is_valid = False
            else:
                self.warnings.append((str(file_path), f"ODPS validation skipped: {e}"))

        return is_valid

    def lint_directory(self, directory: Path, pattern: str = "**/*.{json,yaml,yml}") -> bool:
        """
        Lint all ODPS files in a directory.

        Args:
            directory: Directory to lint
            pattern: Glob pattern for files to lint

        Returns:
            True if all files are valid, False otherwise
        """
        if not directory.exists():
            self.errors.append((str(directory), "Directory does not exist"))
            return False

        all_valid = True
        for file_path in directory.glob(pattern):
            if file_path.is_file():
                if not self.lint_file(file_path):
                    all_valid = False

        return all_valid

    def print_results(self) -> None:
        """Print linting results"""
        if self.errors:
            print("\n❌ Linting Errors:")
            for file_path, error in self.errors:
                print(f"  {file_path}: {error}")

        if self.warnings:
            print("\n⚠️  Linting Warnings:")
            for file_path, warning in self.warnings:
                print(f"  {file_path}: {warning}")

        if not self.errors and not self.warnings:
            print("✅ No linting issues found")
        elif not self.errors:
            print(f"\n✅ No errors found ({len(self.warnings)} warning(s))")
        else:
            print(f"\n❌ Found {len(self.errors)} error(s) and {len(self.warnings)} warning(s)")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Lint ODPS (Open Data Product Standard) files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Lint a single file
  python scripts/lint_odps.py tests/fixtures/odps/v4.1/valid/sample-valid-v4.1.json

  # Lint all ODPS files in a directory
  python scripts/lint_odps.py tests/fixtures/odps/

  # Lint with strict mode (fail on warnings)
  python scripts/lint_odps.py --strict tests/fixtures/odps/
        """
    )
    parser.add_argument(
        'files',
        nargs='*',
        type=Path,
        help='ODPS files or directories to lint'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Treat warnings as errors'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'yaml'],
        help='Expected file format (auto-detected if not specified)'
    )

    args = parser.parse_args()

    linter = ODPSLinter(strict=args.strict)

    if not args.files:
        # Default: lint all ODPS fixtures
        default_dir = project_root / "tests" / "fixtures" / "odps"
        if default_dir.exists():
            print(f"Linting ODPS files in {default_dir}...")
            all_valid = linter.lint_directory(default_dir)
        else:
            print("No files specified and default directory not found")
            parser.print_help()
            sys.exit(1)
    else:
        all_valid = True
        for file_path in args.files:
            if file_path.is_file():
                if not linter.lint_file(file_path):
                    all_valid = False
            elif file_path.is_dir():
                if not linter.lint_directory(file_path):
                    all_valid = False
            else:
                print(f"Error: {file_path} is not a file or directory")
                all_valid = False

    linter.print_results()

    # Exit with error code if there are errors or (in strict mode) warnings
    if linter.errors or (args.strict and linter.warnings):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

