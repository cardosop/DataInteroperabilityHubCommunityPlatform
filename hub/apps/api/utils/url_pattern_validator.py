"""
URL Pattern Validation Utility

Validates Django URL patterns against API naming standards to catch issues
like duplicate service names, naming violations, and pattern inconsistencies.

This utility is designed to run at Django startup to catch configuration errors early.
"""

import re
import sys
from typing import List, Dict, Optional, Tuple, Set, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class URLPatternValidationError:
    """Represents a URL pattern validation error"""
    rule: str
    pattern: str
    url_name: Optional[str]
    file_path: str
    line_number: Optional[int]
    message: str
    severity: str  # 'error' or 'warning'
    suggestion: Optional[str] = None


@dataclass
class URLPatternValidationResult:
    """URL pattern validation result summary"""
    total_patterns: int
    errors: List[URLPatternValidationError]
    warnings: List[URLPatternValidationError]
    passed: bool


class URLPatternValidator:
    """
    Validates Django URL patterns against API naming standards.

    This validator checks for:
    - Duplicate service name segments (e.g., /contracts/contracts/)
    - Naming standards violations (kebab-case, plural resources, etc.)
    - Pattern inconsistencies
    """

    # Validation patterns from API_NAMING_STANDARDS.md
    KEBAB_CASE_PATTERN = re.compile(r'^[a-z0-9-]+$')

    # Common singular forms that should be plural
    SINGULAR_PATTERNS = [
        r'^asset$', r'^contract$', r'^dataset$', r'^file$',
        r'^job$', r'^user$', r'^tenant$', r'^role$',
        r'^webhook$', r'^plugin$', r'^order$', r'^listing$'
    ]

    # Unclear abbreviations (warnings only)
    UNCLEAR_ABBREVIATIONS = {
        'dc': 'data-contracts',
        'si': 'scheduled-ingestions',
        'dq': 'data-quality',  # Acceptable if documented
    }

    def __init__(self):
        self.errors: List[URLPatternValidationError] = []
        self.warnings: List[URLPatternValidationError] = []
        self.patterns: List[Dict[str, Any]] = []

    def extract_url_patterns(self) -> List[Dict[str, Any]]:
        """
        Extract URL patterns from Django URL configuration.

        Returns:
            List of dictionaries containing pattern information
        """
        patterns = []

        try:
            from django.urls import get_resolver
            from django.conf import settings

            # Get the root URL resolver
            resolver = get_resolver()

            # Find the /api/v1/ resolver by traversing
            # Start from root and find the API v1 patterns
            api_v1_patterns = None
            for pattern in resolver.url_patterns:
                pattern_str = str(getattr(pattern, 'pattern', ''))
                # Look for the /api/v1/ pattern
                if 'api/v1' in pattern_str or (hasattr(pattern, 'url_patterns') and self._has_api_v1_patterns(pattern)):
                    if hasattr(pattern, 'url_patterns'):
                        # Check if this is the /api/v1/ resolver
                        for sub_pattern in pattern.url_patterns:
                            sub_str = str(getattr(sub_pattern, 'pattern', ''))
                            if 'api/v1' in sub_str or (hasattr(sub_pattern, 'url_patterns')):
                                api_v1_patterns = sub_pattern.url_patterns if hasattr(sub_pattern, 'url_patterns') else None
                                if api_v1_patterns:
                                    break
                        if api_v1_patterns:
                            break

            # If we found API v1 patterns, use them; otherwise use root patterns
            if api_v1_patterns:
                self._extract_patterns_recursive(api_v1_patterns, patterns, '/api/v1/')
            else:
                # Fallback: extract from root with /api/v1/ prefix
                self._extract_patterns_recursive(resolver.url_patterns, patterns, '/api/v1/')

        except Exception as e:
            logger.warning(
                "url_pattern_extraction_failed",
                error=str(e),
                message="Could not extract URL patterns"
            )

        return patterns

    def _has_api_v1_patterns(self, pattern) -> bool:
        """Check if a pattern contains API v1 patterns"""
        if not hasattr(pattern, 'url_patterns'):
            return False
        for sub_pattern in pattern.url_patterns:
            pattern_str = str(getattr(sub_pattern, 'pattern', ''))
            if 'api/v1' in pattern_str or 'contracts' in pattern_str or 'assets' in pattern_str:
                return True
        return False

    def _extract_patterns_recursive(
        self,
        url_patterns: List,
        patterns: List[Dict[str, Any]],
        prefix: str = '',
        file_path: str = 'unknown'
    ) -> None:
        """Recursively extract URL patterns from Django URL configuration"""
        for pattern in url_patterns:
            try:
                # Get pattern string
                if hasattr(pattern, 'pattern'):
                    pattern_str = str(pattern.pattern)
                elif hasattr(pattern, 'regex'):
                    pattern_str = str(pattern.regex.pattern)
                else:
                    continue

                # Get URL name
                url_name = getattr(pattern, 'name', None)

                # Get callback/view info
                callback = getattr(pattern, 'callback', None)
                if callback:
                    if hasattr(callback, '__module__'):
                        file_path = callback.__module__.replace('.', '/') + '.py'
                    elif hasattr(callback, 'view_class'):
                        view_class = callback.view_class
                        if hasattr(view_class, '__module__'):
                            file_path = view_class.__module__.replace('.', '/') + '.py'

                # Build full path
                if prefix:
                    # Remove leading ^ and trailing $ from pattern
                    clean_pattern = pattern_str.lstrip('^').rstrip('$')
                    # Avoid double slashes
                    if clean_pattern.startswith('/'):
                        full_pattern = prefix.rstrip('/') + clean_pattern
                    else:
                        full_pattern = prefix.rstrip('/') + '/' + clean_pattern
                else:
                    full_pattern = pattern_str

                # Normalize pattern for analysis (remove regex groups)
                normalized_pattern = self._normalize_pattern(full_pattern)

                patterns.append({
                    'pattern': full_pattern,
                    'normalized_pattern': normalized_pattern,
                    'url_name': url_name,
                    'file_path': file_path,
                    'line_number': None,  # Django doesn't provide line numbers
                    'original_pattern': pattern_str
                })

                # Handle include() patterns
                if hasattr(pattern, 'url_patterns'):
                    # Get the prefix from the pattern
                    if hasattr(pattern, 'pattern'):
                        include_prefix = str(pattern.pattern).lstrip('^').rstrip('$')
                        # Don't normalize here - we'll normalize when building full patterns
                        # Just clean up the prefix string
                        include_prefix = include_prefix.strip('/')

                        # Build new prefix by combining current prefix with include prefix
                        if prefix:
                            # Remove any trailing /api/v1/ duplication
                            prefix_clean = prefix.rstrip('/')
                            if include_prefix:
                                # Combine prefixes, avoiding duplication
                                new_prefix = prefix_clean + '/' + include_prefix
                            else:
                                new_prefix = prefix_clean
                        else:
                            new_prefix = include_prefix if include_prefix else ''

                        # Ensure we have /api/v1/ at the start if we're in API v1 context
                        if not new_prefix.startswith('/api/v1/') and prefix.startswith('/api/v1/'):
                            # We're in API v1 context, ensure prefix starts correctly
                            if new_prefix.startswith('/'):
                                # Already absolute, check if it needs /api/v1/
                                if not new_prefix.startswith('/api/v1/'):
                                    new_prefix = '/api/v1' + new_prefix
                            else:
                                # Relative, prepend current prefix base
                                base = '/api/v1' if prefix.startswith('/api/v1/') else ''
                                new_prefix = base + '/' + new_prefix if base else new_prefix

                        # Normalize slashes
                        new_prefix = re.sub(r'/+', '/', new_prefix)
                        if not new_prefix.endswith('/') and new_prefix:
                            new_prefix += '/'
                    else:
                        new_prefix = prefix

                    self._extract_patterns_recursive(
                        pattern.url_patterns,
                        patterns,
                        new_prefix,
                        file_path
                    )

            except Exception as e:
                logger.debug(
                    "pattern_extraction_error",
                    error=str(e),
                    pattern=str(pattern),
                    message="Could not extract pattern"
                )
                continue

    def _normalize_pattern(self, pattern: str) -> str:
        """
        Normalize URL pattern for analysis by removing regex groups.

        Example:
            /api/v1/contracts/(?P<id>[^/.]+)/lineage/visualization/
            -> /api/v1/contracts/{id}/lineage/visualization/
        """
        # Remove leading ^ and trailing $ if present
        normalized = pattern.lstrip('^').rstrip('$')

        # Replace named groups like (?P<id>[^/.]+) with {id}
        normalized = re.sub(r'\(\?P<(\w+)>[^)]+\)', r'{\1}', normalized)
        # Replace unnamed groups with {}
        normalized = re.sub(r'\([^)]+\)', '{}', normalized)

        # Remove regex escape sequences that are part of the pattern but not segments
        # e.g., \. becomes . (but we'll handle format suffixes separately)
        normalized = normalized.replace('\\.', '.')

        # Remove optional trailing slashes and question marks (regex quantifiers)
        normalized = re.sub(r'\?$', '', normalized)  # Remove trailing ?
        normalized = re.sub(r'/$', '', normalized)  # Remove trailing /
        normalized = normalized + '/'  # Add back trailing / for consistency

        return normalized

    def validate_no_duplication(self, pattern_info: Dict[str, Any]) -> List[URLPatternValidationError]:
        """
        Validate no duplication rule.

        Checks for duplicate consecutive segments in URL paths.
        Example: /api/v1/contracts/contracts/{id}/ is invalid
        """
        errors = []
        normalized_pattern = pattern_info['normalized_pattern']

        # Only check API v1 patterns
        if not normalized_pattern.startswith('/api/v1/'):
            return errors

        # Remove /api/v1/ prefix and split path segments
        segments = normalized_pattern.replace('/api/v1/', '').strip('/').split('/')

        # Remove path parameters like {id}
        segments = [s for s in segments if not s.startswith('{')]

        # Check for duplicate consecutive segments
        for i in range(len(segments) - 1):
            if segments[i] == segments[i + 1]:
                errors.append(URLPatternValidationError(
                    rule="no_duplication",
                    pattern=pattern_info['pattern'],
                    url_name=pattern_info.get('url_name'),
                    file_path=pattern_info.get('file_path', 'unknown'),
                    line_number=pattern_info.get('line_number'),
                    message=f"Duplicate segment '{segments[i]}' appears twice in path",
                    severity="error",
                    suggestion=f"Remove duplicate segment. Expected: {normalized_pattern.replace(f'/{segments[i]}/{segments[i]}', f'/{segments[i]}')}"
                ))

        return errors

    def validate_plural_resources(self, pattern_info: Dict[str, Any]) -> List[URLPatternValidationError]:
        """
        Validate plural resources rule.

        Collection endpoints should use plural resource names.
        """
        errors = []
        normalized_pattern = pattern_info['normalized_pattern']

        # Only check API v1 patterns
        if not normalized_pattern.startswith('/api/v1/'):
            return errors

        # Extract first resource segment after /api/v1/
        match = re.match(r'^/api/v1/([^/{}]+)/', normalized_pattern)
        if not match:
            return errors

        resource_name = match.group(1)

        # Check if resource name is singular
        for pattern in self.SINGULAR_PATTERNS:
            if re.match(pattern, resource_name):
                errors.append(URLPatternValidationError(
                    rule="plural_resources",
                    pattern=pattern_info['pattern'],
                    url_name=pattern_info.get('url_name'),
                    file_path=pattern_info.get('file_path', 'unknown'),
                    line_number=pattern_info.get('line_number'),
                    message=f"Resource name '{resource_name}' should be plural",
                    severity="error",
                    suggestion=f"Use plural form: {normalized_pattern.replace(f'/{resource_name}/', f'/{resource_name}s/')}"
                ))
                break

        return errors

    def validate_kebab_case(self, pattern_info: Dict[str, Any]) -> List[URLPatternValidationError]:
        """
        Validate kebab-case rule.

        All URL path segments should use kebab-case (lowercase with hyphens).
        """
        errors = []
        normalized_pattern = pattern_info['normalized_pattern']

        # Only check API v1 patterns
        if not normalized_pattern.startswith('/api/v1/'):
            return errors

        # Extract all path segments
        segments = normalized_pattern.replace('/api/v1/', '').strip('/').split('/')

        # Remove path parameters and regex patterns
        valid_segments = []
        for segment in segments:
            # Skip path parameters like {id}
            if segment.startswith('{') and segment.endswith('}'):
                continue
            # Skip regex patterns (contain backslashes, dots with escapes, etc.)
            if '\\' in segment or segment.startswith('<') or segment.endswith('>'):
                continue
            # Skip format suffixes that are part of regex (e.g., "format}")
            if segment.endswith('}'):
                continue
            # Skip empty segments
            if not segment:
                continue
            valid_segments.append(segment)

        # Check each valid segment for kebab-case
        for segment in valid_segments:
            # Skip if it's a file extension (e.g., .json, .yaml)
            if '.' in segment and not segment.startswith('.'):
                # Split on dot and check the base name
                base_name = segment.split('.')[0]
                if base_name:
                    segment = base_name

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

                errors.append(URLPatternValidationError(
                    rule="kebab_case",
                    pattern=pattern_info['pattern'],
                    url_name=pattern_info.get('url_name'),
                    file_path=pattern_info.get('file_path', 'unknown'),
                    line_number=pattern_info.get('line_number'),
                    message=f"Segment '{segment}' uses {issue}, should use kebab-case",
                    severity="error",
                    suggestion=f"Use kebab-case: {suggestion}"
                ))

        return errors

    def validate_explicit_naming(self, pattern_info: Dict[str, Any]) -> List[URLPatternValidationError]:
        """
        Validate explicit naming rule.

        Warns about unclear abbreviations.
        """
        warnings = []
        normalized_pattern = pattern_info['normalized_pattern']

        # Only check API v1 patterns
        if not normalized_pattern.startswith('/api/v1/'):
            return warnings

        # Extract all path segments
        segments = normalized_pattern.replace('/api/v1/', '').strip('/').split('/')

        # Remove path parameters
        segments = [s for s in segments if not s.startswith('{')]

        # Check for unclear abbreviations
        for segment in segments:
            if segment in self.UNCLEAR_ABBREVIATIONS:
                warnings.append(URLPatternValidationError(
                    rule="explicit_naming",
                    pattern=pattern_info['pattern'],
                    url_name=pattern_info.get('url_name'),
                    file_path=pattern_info.get('file_path', 'unknown'),
                    line_number=pattern_info.get('line_number'),
                    message=f"Abbreviation '{segment}' is unclear, consider using explicit name",
                    severity="warning",
                    suggestion=f"Consider using explicit name: {self.UNCLEAR_ABBREVIATIONS[segment]}"
                ))

        return warnings

    def validate_all(self, strict: bool = False) -> URLPatternValidationResult:
        """
        Validate all URL patterns.

        Args:
            strict: If True, treat warnings as errors

        Returns:
            URLPatternValidationResult with validation results
        """
        logger.info("url_pattern_validation_started", message="Starting URL pattern validation")

        # Extract patterns
        self.patterns = self.extract_url_patterns()
        logger.info(
            "url_patterns_extracted",
            count=len(self.patterns),
            message=f"Extracted {len(self.patterns)} URL patterns"
        )

        # Validate each pattern
        for pattern_info in self.patterns:
            normalized_pattern = pattern_info.get('normalized_pattern', '')

            # Only validate API v1 patterns
            if not normalized_pattern.startswith('/api/v1/'):
                continue

            # Validate no duplication
            self.errors.extend(self.validate_no_duplication(pattern_info))

            # Validate plural resources
            self.errors.extend(self.validate_plural_resources(pattern_info))

            # Validate kebab-case
            self.errors.extend(self.validate_kebab_case(pattern_info))

            # Validate explicit naming (warnings)
            self.warnings.extend(self.validate_explicit_naming(pattern_info))

        # Separate errors and warnings
        actual_errors = [e for e in self.errors if e.severity == 'error']
        actual_warnings = [e for e in self.errors if e.severity == 'warning'] + self.warnings

        # In strict mode, treat warnings as errors
        if strict:
            actual_errors.extend(actual_warnings)
            actual_warnings = []

        passed = len(actual_errors) == 0

        result = URLPatternValidationResult(
            total_patterns=len(self.patterns),
            errors=actual_errors,
            warnings=actual_warnings,
            passed=passed
        )

        if passed:
            logger.info(
                "url_pattern_validation_passed",
                total_patterns=result.total_patterns,
                warnings=len(result.warnings),
                message="URL pattern validation passed"
            )
        else:
            logger.error(
                "url_pattern_validation_failed",
                total_patterns=result.total_patterns,
                errors=len(result.errors),
                warnings=len(result.warnings),
                message="URL pattern validation failed"
            )
            # Log each error
            for error in result.errors:
                logger.error(
                    "url_pattern_validation_error",
                    rule=error.rule,
                    pattern=error.pattern,
                    url_name=error.url_name,
                    file_path=error.file_path,
                    message=error.message,
                    suggestion=error.suggestion
                )

        return result

    def format_errors(self, result: URLPatternValidationResult) -> str:
        """
        Format validation errors as a human-readable string.

        Args:
            result: Validation result to format

        Returns:
            Formatted error message string
        """
        lines = []
        lines.append("=" * 80)
        lines.append("URL Pattern Validation Results")
        lines.append("=" * 80)
        lines.append(f"Total patterns checked: {result.total_patterns}")
        lines.append(f"Errors: {len(result.errors)}")
        lines.append(f"Warnings: {len(result.warnings)}")
        lines.append("")

        if result.errors:
            lines.append("ERRORS:")
            lines.append("-" * 80)
            for i, error in enumerate(result.errors, 1):
                lines.append(f"{i}. [{error.rule}] {error.pattern}")
                lines.append(f"   URL Name: {error.url_name or 'N/A'}")
                lines.append(f"   File: {error.file_path}")
                lines.append(f"   Message: {error.message}")
                if error.suggestion:
                    lines.append(f"   Suggestion: {error.suggestion}")
                lines.append("")

        if result.warnings:
            lines.append("WARNINGS:")
            lines.append("-" * 80)
            for i, warning in enumerate(result.warnings, 1):
                lines.append(f"{i}. [{warning.rule}] {warning.pattern}")
                lines.append(f"   URL Name: {warning.url_name or 'N/A'}")
                lines.append(f"   File: {warning.file_path}")
                lines.append(f"   Message: {warning.message}")
                if warning.suggestion:
                    lines.append(f"   Suggestion: {warning.suggestion}")
                lines.append("")

        if result.passed:
            lines.append("✓ All URL patterns passed validation!")
        else:
            lines.append("✗ URL pattern validation failed. Please fix the errors above.")

        lines.append("=" * 80)

        return "\n".join(lines)


def validate_url_patterns(strict: bool = False, raise_on_error: bool = False) -> URLPatternValidationResult:
    """
    Convenience function to validate URL patterns.

    Args:
        strict: If True, treat warnings as errors
        raise_on_error: If True, raise exception on validation failure

    Returns:
        URLPatternValidationResult

    Raises:
        ValueError: If validation fails and raise_on_error is True
    """
    validator = URLPatternValidator()
    result = validator.validate_all(strict=strict)

    if not result.passed and raise_on_error:
        error_message = validator.format_errors(result)
        raise ValueError(f"URL pattern validation failed:\n{error_message}")

    return result

