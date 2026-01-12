#!/usr/bin/env python3
"""
Validate API Naming Standards

This script validates that all API endpoints comply with the API naming standards
defined in docs/API_NAMING_STANDARDS.md.

Usage:
    python scripts/validate_api_naming_standards.py [--strict] [--output OUTPUT_FILE]
"""

import re
import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
from datetime import datetime
import importlib.util

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class ValidationError:
    """Represents a validation error"""
    rule: str
    endpoint_path: str
    method: Optional[str]
    file_path: str
    line_number: Optional[int]
    message: str
    severity: str  # 'error' or 'warning'
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Validation result summary"""
    total_endpoints: int
    errors: List[ValidationError]
    warnings: List[ValidationError]
    passed: bool


class APINamingStandardsValidator:
    """Validates API endpoints against naming standards"""

    # Validation patterns from API_NAMING_STANDARDS.md
    COLLECTION_PATTERN = re.compile(r'^/api/v1/[a-z0-9-]+/$')
    DETAIL_PATTERN = re.compile(r'^/api/v1/[a-z0-9-]+/\{[a-z]+\}/$')
    ACTION_PATTERN = re.compile(r'^/api/v1/[a-z0-9-]+/\{[a-z]+\}/[a-z0-9-]+/$')
    SUB_RESOURCE_PATTERN = re.compile(r'^/api/v1/[a-z0-9-]+/\{[a-z]+\}/[a-z0-9-]+/$')

    # Kebab-case pattern
    KEBAB_CASE_PATTERN = re.compile(r'^[a-z0-9-]+$')

    def __init__(self, hub_dir: Optional[Path] = None):
        self.hub_dir = hub_dir or project_root / "hub"
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.endpoints: List[Dict[str, Any]] = []

    def extract_endpoints(self) -> List[Dict[str, Any]]:
        """Extract endpoints from Django codebase"""
        try:
            import importlib.util
            script_dir = Path(__file__).parent
            spec = importlib.util.spec_from_file_location(
                "extract_django_api_inventory",
                script_dir / "extract-django-api-inventory.py"
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                extractor = module.DjangoAPIExtractor(self.hub_dir)
                endpoints = extractor.extract_all()

                return [
                    {
                        "path": ep.path,
                        "method": ep.method,
                        "view_class": ep.view_class,
                        "file_path": ep.file_path
                    }
                    for ep in endpoints
                ]
        except Exception as e:
            print(f"   ⚠ Warning: Could not extract endpoints from codebase: {e}", file=sys.stderr)

        return []

    def validate_no_duplication(self, endpoint: Dict[str, Any]) -> List[ValidationError]:
        """Validate no duplication rule"""
        errors = []
        path = endpoint['path']

        # Remove /api/v1/ prefix and split path segments
        if path.startswith('/api/v1/'):
            segments = path.replace('/api/v1/', '').strip('/').split('/')
        else:
            segments = path.strip('/').split('/')

        # Remove {id} and other path parameters
        segments = [s for s in segments if not s.startswith('{')]

        # Check for duplicate consecutive segments
        for i in range(len(segments) - 1):
            if segments[i] == segments[i + 1]:
                errors.append(ValidationError(
                    rule="no_duplication",
                    endpoint_path=path,
                    method=endpoint.get('method'),
                    file_path=endpoint.get('file_path', ''),
                    line_number=None,
                    message=f"Duplicate segment '{segments[i]}' appears twice in path",
                    severity="error",
                    suggestion=f"Remove duplicate segment. Expected: {path.replace(f'/{segments[i]}/{segments[i]}', f'/{segments[i]}')}"
                ))

        return errors

    def validate_plural_resources(self, endpoint: Dict[str, Any]) -> List[ValidationError]:
        """Validate plural resources rule"""
        errors = []
        path = endpoint['path']
        method = endpoint.get('method', 'GET')

        # Only check collection endpoints (GET /api/v1/{resource}/ or POST /api/v1/{resource}/)
        if not (path.endswith('/') and not re.search(r'/\{[^}]+\}/', path)):
            return errors

        # Extract resource name (first segment after /api/v1/)
        match = re.match(r'^/api/v1/([^/]+)/', path)
        if not match:
            return errors

        resource_name = match.group(1)

        # Check if resource name is singular
        # Common singular forms that should be plural
        singular_patterns = [
            r'^asset$', r'^contract$', r'^dataset$', r'^file$',
            r'^job$', r'^user$', r'^tenant$', r'^role$',
            r'^webhook$', r'^plugin$', r'^order$', r'^listing$'
        ]

        for pattern in singular_patterns:
            if re.match(pattern, resource_name):
                errors.append(ValidationError(
                    rule="plural_resources",
                    endpoint_path=path,
                    method=method,
                    file_path=endpoint.get('file_path', ''),
                    line_number=None,
                    message=f"Resource name '{resource_name}' should be plural",
                    severity="error",
                    suggestion=f"Use plural form: {path.replace(f'/{resource_name}/', f'/{resource_name}s/')}"
                ))
                break

        return errors

    def validate_kebab_case(self, endpoint: Dict[str, Any]) -> List[ValidationError]:
        """Validate kebab-case rule"""
        errors = []
        path = endpoint['path']

        # Extract all path segments
        if path.startswith('/api/v1/'):
            segments = path.replace('/api/v1/', '').strip('/').split('/')
        else:
            segments = path.strip('/').split('/')

        # Remove path parameters
        segments = [s for s in segments if not s.startswith('{')]

        # Check each segment for kebab-case
        for segment in segments:
            if not self.KEBAB_CASE_PATTERN.match(segment):
                # Check what's wrong
                if '_' in segment:
                    issue = "snake_case"
                    suggestion = segment.replace('_', '-')
                elif any(c.isupper() for c in segment):
                    issue = "camelCase or PascalCase"
                    suggestion = re.sub(r'([a-z])([A-Z])', r'\1-\2', segment).lower()
                else:
                    issue = "invalid characters"
                    suggestion = re.sub(r'[^a-z0-9-]', '-', segment.lower())

                errors.append(ValidationError(
                    rule="kebab_case",
                    endpoint_path=path,
                    method=endpoint.get('method'),
                    file_path=endpoint.get('file_path', ''),
                    line_number=None,
                    message=f"Segment '{segment}' uses {issue}, should use kebab-case",
                    severity="error",
                    suggestion=f"Use kebab-case: {suggestion}"
                ))

        return errors

    def validate_pattern_consistency(self, endpoint: Dict[str, Any]) -> List[ValidationError]:
        """Validate pattern consistency"""
        errors = []
        path = endpoint['path']

        # Check if path matches one of the defined patterns
        matches_pattern = (
            self.COLLECTION_PATTERN.match(path) or
            self.DETAIL_PATTERN.match(path) or
            self.ACTION_PATTERN.match(path) or
            self.SUB_RESOURCE_PATTERN.match(path)
        )

        if not matches_pattern and path.startswith('/api/v1/'):
            # Check if it's a valid nested pattern
            nested_pattern = re.compile(r'^/api/v1/[a-z0-9-]+/\{[a-z]+\}/[a-z0-9-]+/\{[a-z]+\}/$')
            if not nested_pattern.match(path):
                errors.append(ValidationError(
                    rule="pattern_consistency",
                    endpoint_path=path,
                    method=endpoint.get('method'),
                    file_path=endpoint.get('file_path', ''),
                    line_number=None,
                    message=f"Path does not match any defined pattern",
                    severity="warning",
                    suggestion="Ensure path matches one of: /api/v1/{resource}/, /api/v1/{resource}/{id}/, /api/v1/{resource}/{id}/{action}/, or /api/v1/{resource}/{id}/{sub-resource}/"
                ))

        return errors

    def validate_explicit_naming(self, endpoint: Dict[str, Any]) -> List[ValidationError]:
        """Validate explicit naming rule"""
        errors = []
        path = endpoint['path']

        # Extract resource names
        if path.startswith('/api/v1/'):
            segments = path.replace('/api/v1/', '').strip('/').split('/')
        else:
            segments = path.strip('/').split('/')

        # Remove path parameters
        segments = [s for s in segments if not s.startswith('{')]

        # Check for unclear abbreviations
        unclear_abbreviations = {
            'dc': 'data-contracts',
            'si': 'scheduled-ingestions',
            'dq': 'data-quality',  # Acceptable if documented, but warn
        }

        for segment in segments:
            if segment in unclear_abbreviations:
                errors.append(ValidationError(
                    rule="explicit_naming",
                    endpoint_path=path,
                    method=endpoint.get('method'),
                    file_path=endpoint.get('file_path', ''),
                    line_number=None,
                    message=f"Abbreviation '{segment}' is unclear, use explicit name",
                    severity="warning",
                    suggestion=f"Use explicit name: {unclear_abbreviations[segment]}"
                ))

        return errors

    def validate_all(self, strict: bool = False) -> ValidationResult:
        """Validate all endpoints"""
        print("🔍 Extracting endpoints from codebase...")
        self.endpoints = self.extract_endpoints()
        print(f"   ✓ Found {len(self.endpoints)} endpoints")

        print("\n🔍 Validating endpoints against naming standards...")

        for endpoint in self.endpoints:
            path = endpoint['path']

            # Skip non-API endpoints
            if not path.startswith('/api/v1/'):
                continue

            # Validate no duplication
            self.errors.extend(self.validate_no_duplication(endpoint))

            # Validate plural resources
            self.errors.extend(self.validate_plural_resources(endpoint))

            # Validate kebab-case
            self.errors.extend(self.validate_kebab_case(endpoint))

            # Validate pattern consistency
            if strict:
                self.errors.extend(self.validate_pattern_consistency(endpoint))
            else:
                self.warnings.extend(self.validate_pattern_consistency(endpoint))

            # Validate explicit naming
            self.warnings.extend(self.validate_explicit_naming(endpoint))

        # Separate errors and warnings
        actual_errors = [e for e in self.errors if e.severity == 'error']
        actual_warnings = [e for e in self.errors if e.severity == 'warning'] + self.warnings

        passed = len(actual_errors) == 0

        return ValidationResult(
            total_endpoints=len(self.endpoints),
            errors=actual_errors,
            warnings=actual_warnings,
            passed=passed
        )

    def generate_report(self, result: ValidationResult, output_file: Optional[Path] = None) -> Dict:
        """Generate validation report"""
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_endpoints": result.total_endpoints,
                "errors": len(result.errors),
                "warnings": len(result.warnings),
                "passed": result.passed
            },
            "errors": [
                {
                    "rule": e.rule,
                    "endpoint_path": e.endpoint_path,
                    "method": e.method,
                    "file_path": e.file_path,
                    "message": e.message,
                    "severity": e.severity,
                    "suggestion": e.suggestion
                }
                for e in result.errors
            ],
            "warnings": [
                {
                    "rule": w.rule,
                    "endpoint_path": w.endpoint_path,
                    "method": w.method,
                    "file_path": w.file_path,
                    "message": w.message,
                    "severity": w.severity,
                    "suggestion": w.suggestion
                }
                for w in result.warnings
            ],
            "errors_by_rule": defaultdict(int),
            "warnings_by_rule": defaultdict(int)
        }

        # Count errors and warnings by rule
        for error in result.errors:
            report["errors_by_rule"][error.rule] += 1

        for warning in result.warnings:
            report["warnings_by_rule"][warning.rule] += 1

        report["errors_by_rule"] = dict(report["errors_by_rule"])
        report["warnings_by_rule"] = dict(report["warnings_by_rule"])

        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n📊 Report generated: {output_file}")

        return report


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(
        description="Validate API endpoints against naming standards"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat pattern consistency violations as errors"
    )
    parser.add_argument(
        "--output",
        default="docs/api-audit/api-naming-validation.json",
        help="Output file path for validation report"
    )
    parser.add_argument(
        "--hub-dir",
        default="hub",
        help="Hub directory path"
    )

    args = parser.parse_args()

    hub_dir = project_root / args.hub_dir
    output_file = project_root / args.output

    validator = APINamingStandardsValidator(hub_dir)

    result = validator.validate_all(strict=args.strict)

    # Print summary
    print("\n" + "=" * 60)
    print("Validation Results")
    print("=" * 60)
    print(f"\n📋 Endpoints Validated: {result.total_endpoints}")
    print(f"❌ Errors: {len(result.errors)}")
    print(f"⚠️  Warnings: {len(result.warnings)}")

    if result.errors:
        print("\n❌ Errors Found:")
        for error in result.errors[:10]:  # Show first 10
            print(f"   [{error.rule}] {error.endpoint_path}")
            print(f"      {error.message}")
            if error.suggestion:
                print(f"      Suggestion: {error.suggestion}")
        if len(result.errors) > 10:
            print(f"   ... and {len(result.errors) - 10} more errors")

    if result.warnings:
        print("\n⚠️  Warnings Found:")
        for warning in result.warnings[:5]:  # Show first 5
            print(f"   [{warning.rule}] {warning.endpoint_path}")
            print(f"      {warning.message}")
        if len(result.warnings) > 5:
            print(f"   ... and {len(result.warnings) - 5} more warnings")

    # Generate report
    validator.generate_report(result, output_file)

    # Exit with error code if validation failed
    if not result.passed:
        print("\n❌ Validation failed! Please fix errors before proceeding.")
        sys.exit(1)
    else:
        print("\n✅ All validations passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()

