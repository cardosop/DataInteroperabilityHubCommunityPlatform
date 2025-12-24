#!/usr/bin/env python3
"""
ODPS Security Scanner

Comprehensive security scanning for ODPS (Open Data Product Standard) files.
Detects security vulnerabilities including:
- Malicious $ref references (path traversal, external URL injection)
- Path traversal vulnerabilities
- URL injection vulnerabilities
- Script injection attempts
- Command injection attempts
- XXE (XML External Entity) attempts

Usage:
    python scripts/scan_odps_security.py [--strict] [file...]

Exit codes:
    0: No security issues found
    1: Security issues detected
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set, Optional
from urllib.parse import urlparse

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
from hub.apps.contracts.ref_resolver import RefResolver, RefMode
from hub.apps.contracts.odps_errors import ODPSRefResolutionError


class ODPSSecurityScanner:
    """ODPS security vulnerability scanner"""

    # Security patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",           # ../ (Unix)
        r"\.\.\\",          # ..\ (Windows)
        r"\.\./\.\./",      # Multiple levels
        r"\.\./\.\./\.\./", # Deep traversal
        r"file:///",        # file:// protocol
        r"/etc/passwd",     # Common target
        r"/etc/shadow",     # Common target
        r"/windows/system32",  # Windows target
        r"C:\\",            # Windows absolute path
        r"\.\.%2F",         # URL-encoded ../
        r"\.\.%5C",         # URL-encoded ..\
    ]

    MALICIOUS_URL_PATTERNS = [
        r"javascript:",     # JavaScript protocol
        r"data:text/html",  # Data URI with HTML
        r"vbscript:",       # VBScript protocol
        r"file://",         # File protocol
        r"jar:",            # JAR protocol
        r"phar:",           # PHAR protocol
    ]

    SCRIPT_INJECTION_PATTERNS = [
        r"<script",         # Script tags
        r"</script>",       # Closing script tags
        r"onerror=",       # Event handlers
        r"onload=",
        r"onclick=",
        r"eval\(",          # JavaScript eval
        r"alert\(",         # JavaScript alert
        r"document\.cookie", # Cookie access
        r"document\.write", # Document write
    ]

    COMMAND_INJECTION_PATTERNS = [
        r";\s*(rm|wget|curl|cat|ls|pwd|whoami)",  # Command separators
        r"\|\s*(sh|bash|python|perl|ruby)",       # Pipes to shells
        r"\$\(",                                  # Command substitution
        r"`[^`]+`",                               # Backtick execution
        r"\$\{[^}]+\}",                           # Variable expansion
    ]

    XXE_PATTERNS = [
        r"<!DOCTYPE",
        r"<!ENTITY",
        r"SYSTEM",
        r"&[a-zA-Z]+;",     # Entity references
    ]

    def __init__(self, strict: bool = False):
        self.strict = strict
        self.vulnerabilities: List[Tuple[str, str, str]] = []  # (file_path, severity, issue)
        self.warnings: List[Tuple[str, str]] = []  # (file_path, warning)

    def scan_file(self, file_path: Path) -> bool:
        """
        Scan a single ODPS file for security vulnerabilities.

        Args:
            file_path: Path to the ODPS file

        Returns:
            True if no vulnerabilities found, False otherwise
        """
        if not file_path.exists():
            self.vulnerabilities.append((str(file_path), "ERROR", "File does not exist"))
            return False

        # Load file
        try:
            if file_path.suffix in ['.yaml', '.yml']:
                if not YAML_AVAILABLE or yaml is None:
                    self.vulnerabilities.append((str(file_path), "ERROR", "PyYAML not available"))
                    return False
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
        except json.JSONDecodeError as e:
            self.vulnerabilities.append((str(file_path), "ERROR", f"Invalid JSON: {e}"))
            return False
        except Exception as e:
            if YAML_AVAILABLE and yaml is not None and isinstance(e, yaml.YAMLError):
                self.vulnerabilities.append((str(file_path), "ERROR", f"Invalid YAML: {e}"))
            else:
                self.vulnerabilities.append((str(file_path), "ERROR", f"Error reading file: {e}"))
            return False

        if not isinstance(data, dict):
            self.vulnerabilities.append((str(file_path), "ERROR", "ODPS document must be a dictionary"))
            return False

        # Skip non-ODPS files (reference files)
        if 'schema' not in data or not isinstance(data.get('schema'), str) or 'opendataproducts.org/schema' not in data.get('schema', ''):
            # This might be a reference file, skip security scanning
            return True

        is_secure = True

        # Scan for vulnerabilities
        is_secure &= self._scan_path_traversal(data, file_path)
        is_secure &= self._scan_url_injection(data, file_path)
        is_secure &= self._scan_malicious_refs(data, file_path)
        is_secure &= self._scan_script_injection(data, file_path)
        is_secure &= self._scan_command_injection(data, file_path)
        is_secure &= self._scan_xxe_attempts(data, file_path)

        return is_secure

    def _scan_path_traversal(self, data: Dict[str, Any], file_path: Path) -> bool:
        """Scan for path traversal vulnerabilities"""
        is_secure = True
        json_str = json.dumps(data)

        # Check for path traversal patterns in all string values
        for pattern in self.PATH_TRAVERSAL_PATTERNS:
            matches = re.finditer(pattern, json_str, re.IGNORECASE)
            for match in matches:
                # Get context around the match
                start = max(0, match.start() - 50)
                end = min(len(json_str), match.end() + 50)
                context = json_str[start:end]

                # Check if it's in a $ref or URL field
                field_context = self._get_field_context(data, match.start())

                severity = "HIGH"
                if "$ref" in field_context.lower() or "url" in field_context.lower():
                    severity = "CRITICAL"

                self.vulnerabilities.append((
                    str(file_path),
                    severity,
                    f"Path traversal pattern detected: '{match.group()}' in {field_context}"
                ))
                is_secure = False

        return is_secure

    def _scan_url_injection(self, data: Dict[str, Any], file_path: Path) -> bool:
        """Scan for URL injection vulnerabilities"""
        is_secure = True
        json_str = json.dumps(data)

        # Check for malicious URL patterns
        for pattern in self.MALICIOUS_URL_PATTERNS:
            matches = re.finditer(pattern, json_str, re.IGNORECASE)
            for match in matches:
                field_context = self._get_field_context(data, match.start())

                self.vulnerabilities.append((
                    str(file_path),
                    "CRITICAL",
                    f"Malicious URL pattern detected: '{match.group()}' in {field_context}"
                ))
                is_secure = False

        # Check for suspicious URLs in $ref fields
        refs = self._find_all_refs(data)
        for ref_path, ref_value in refs:
            if isinstance(ref_value, str):
                parsed = urlparse(ref_value)
                # Check for dangerous schemes
                if parsed.scheme in ['javascript', 'data', 'vbscript', 'file', 'jar', 'phar']:
                    self.vulnerabilities.append((
                        str(file_path),
                        "CRITICAL",
                        f"Malicious URL scheme in $ref: '{ref_value}' at {ref_path}"
                    ))
                    is_secure = False

                # Check for path traversal in URLs
                if '../' in parsed.path or '..\\' in parsed.path:
                    self.vulnerabilities.append((
                        str(file_path),
                        "HIGH",
                        f"Path traversal in URL: '{ref_value}' at {ref_path}"
                    ))
                    is_secure = False

        return is_secure

    def _scan_malicious_refs(self, data: Dict[str, Any], file_path: Path) -> bool:
        """Scan for malicious $ref references"""
        is_secure = True

        # Find all $ref fields
        refs = self._find_all_refs(data)

        for ref_path, ref_value in refs:
            if not isinstance(ref_value, str):
                continue

            # Check for path traversal in local refs
            if ref_value.startswith('./') or ref_value.startswith('../') or not ref_value.startswith('#'):
                # This is a local or external ref
                # Check for path traversal
                for pattern in self.PATH_TRAVERSAL_PATTERNS:
                    if re.search(pattern, ref_value, re.IGNORECASE):
                        self.vulnerabilities.append((
                            str(file_path),
                            "CRITICAL",
                            f"Malicious $ref detected: '{ref_value}' at {ref_path} (path traversal)"
                        ))
                        is_secure = False
                        break

                # Check for malicious URLs
                if '://' in ref_value:
                    parsed = urlparse(ref_value)
                    if parsed.scheme in ['javascript', 'data', 'vbscript', 'file']:
                        self.vulnerabilities.append((
                            str(file_path),
                            "CRITICAL",
                            f"Malicious URL in $ref: '{ref_value}' at {ref_path}"
                        ))
                        is_secure = False

        return is_secure

    def _scan_script_injection(self, data: Dict[str, Any], file_path: Path) -> bool:
        """Scan for script injection attempts"""
        is_secure = True
        json_str = json.dumps(data)

        for pattern in self.SCRIPT_INJECTION_PATTERNS:
            matches = re.finditer(pattern, json_str, re.IGNORECASE)
            for match in matches:
                field_context = self._get_field_context(data, match.start())

                self.vulnerabilities.append((
                    str(file_path),
                    "HIGH",
                    f"Script injection pattern detected: '{match.group()}' in {field_context}"
                ))
                is_secure = False

        return is_secure

    def _scan_command_injection(self, data: Dict[str, Any], file_path: Path) -> bool:
        """Scan for command injection attempts"""
        is_secure = True
        json_str = json.dumps(data)

        for pattern in self.COMMAND_INJECTION_PATTERNS:
            matches = re.finditer(pattern, json_str, re.IGNORECASE)
            for match in matches:
                field_context = self._get_field_context(data, match.start())

                self.vulnerabilities.append((
                    str(file_path),
                    "HIGH",
                    f"Command injection pattern detected: '{match.group()}' in {field_context}"
                ))
                is_secure = False

        return is_secure

    def _scan_xxe_attempts(self, data: Dict[str, Any], file_path: Path) -> bool:
        """Scan for XXE (XML External Entity) attempts"""
        is_secure = True
        json_str = json.dumps(data)

        for pattern in self.XXE_PATTERNS:
            matches = re.finditer(pattern, json_str, re.IGNORECASE)
            for match in matches:
                field_context = self._get_field_context(data, match.start())

                self.vulnerabilities.append((
                    str(file_path),
                    "MEDIUM",
                    f"XXE pattern detected: '{match.group()}' in {field_context}"
                ))
                is_secure = False

        return is_secure

    def _find_all_refs(self, data: Any, path: str = "") -> List[Tuple[str, Any]]:
        """Recursively find all $ref fields in the document"""
        refs = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                if key == "$ref" and isinstance(value, str):
                    refs.append((current_path, value))
                elif isinstance(value, (dict, list)):
                    refs.extend(self._find_all_refs(value, current_path))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]"
                if isinstance(item, (dict, list)):
                    refs.extend(self._find_all_refs(item, current_path))

        return refs

    def _get_field_context(self, data: Dict[str, Any], position: int) -> str:
        """Get field context for a position in JSON string"""
        # For now, return a generic context
        # A more sophisticated implementation would track the JSON path
        return "document"

    def scan_directory(self, directory: Path, pattern: str = "**/*.{json,yaml,yml}") -> bool:
        """
        Scan all ODPS files in a directory.

        Args:
            directory: Directory to scan
            pattern: Glob pattern for files to scan

        Returns:
            True if all files are secure, False otherwise
        """
        if not directory.exists():
            self.vulnerabilities.append((str(directory), "ERROR", "Directory does not exist"))
            return False

        all_secure = True
        for file_path in directory.glob(pattern):
            if file_path.is_file():
                if not self.scan_file(file_path):
                    all_secure = False

        return all_secure

    def print_results(self) -> None:
        """Print security scan results"""
        if self.vulnerabilities:
            print("\n🔒 Security Scan Results:")
            print("=" * 60)

            # Group by severity
            critical = [v for v in self.vulnerabilities if v[1] == "CRITICAL"]
            high = [v for v in self.vulnerabilities if v[1] == "HIGH"]
            medium = [v for v in self.vulnerabilities if v[1] == "MEDIUM"]
            errors = [v for v in self.vulnerabilities if v[1] == "ERROR"]

            if critical:
                print("\n❌ CRITICAL Vulnerabilities:")
                for file_path, severity, issue in critical:
                    print(f"  {file_path}: {issue}")

            if high:
                print("\n⚠️  HIGH Severity Issues:")
                for file_path, severity, issue in high:
                    print(f"  {file_path}: {issue}")

            if medium:
                print("\n⚠️  MEDIUM Severity Issues:")
                for file_path, severity, issue in medium:
                    print(f"  {file_path}: {issue}")

            if errors:
                print("\n❌ Errors:")
                for file_path, severity, issue in errors:
                    print(f"  {file_path}: {issue}")

            print(f"\n❌ Found {len(self.vulnerabilities)} security issue(s)")
        else:
            print("✅ No security vulnerabilities found")

        if self.warnings:
            print("\n⚠️  Warnings:")
            for file_path, warning in self.warnings:
                print(f"  {file_path}: {warning}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Scan ODPS files for security vulnerabilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan a single file
  python scripts/scan_odps_security.py tests/fixtures/odps/v4.1/valid/sample-valid-v4.1.json

  # Scan all ODPS files in a directory
  python scripts/scan_odps_security.py tests/fixtures/odps/

  # Scan with strict mode (treat warnings as errors)
  python scripts/scan_odps_security.py --strict tests/fixtures/odps/
        """
    )
    parser.add_argument(
        'files',
        nargs='*',
        type=Path,
        help='ODPS files or directories to scan'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Treat warnings as errors'
    )

    args = parser.parse_args()

    scanner = ODPSSecurityScanner(strict=args.strict)

    if not args.files:
        # Default: scan all ODPS fixtures
        default_dir = project_root / "tests" / "fixtures" / "odps"
        if default_dir.exists():
            print(f"Scanning ODPS files in {default_dir}...")
            all_secure = scanner.scan_directory(default_dir)
        else:
            print("No files specified and default directory not found")
            parser.print_help()
            sys.exit(1)
    else:
        all_secure = True
        for file_path in args.files:
            if file_path.is_file():
                if not scanner.scan_file(file_path):
                    all_secure = False
            elif file_path.is_dir():
                if not scanner.scan_directory(file_path):
                    all_secure = False
            else:
                print(f"Error: {file_path} is not a file or directory")
                all_secure = False

    scanner.print_results()

    # Exit with error code if vulnerabilities found
    if scanner.vulnerabilities:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

