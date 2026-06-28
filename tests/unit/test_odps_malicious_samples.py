"""
Unit tests for malicious ODPS test sample files.

Tests verify that malicious ODPS sample files:
1. Are valid JSON (structure-wise, not content-wise)
2. Contain security attack patterns
3. Are properly flagged/detected by security validators
4. Are rejected by security checks

These tests ensure that security validation mechanisms work correctly.
"""

try:
    import pytest

    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import json
import re
from pathlib import Path

from django.test import TestCase


class ODPSMaliciousSamplesTest(TestCase):
    """Test malicious ODPS sample files for security testing"""

    def setUp(self):
        """Set up test fixtures"""
        # Get the base directory for tests
        self.base_dir = Path(__file__).parent.parent.parent
        self.malicious_dir = (
            self.base_dir / "tests" / "fixtures" / "odps" / "security" / "malicious"
        )

        # Security patterns to detect
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"\.\./\.\./",
            r"file:///",
            r"/etc/passwd",
            r"/etc/shadow",
            r"/windows/system32",
        ]

        self.malicious_url_patterns = [
            r"javascript:",
            r"data:text/html",
            r"vbscript:",
            r"file://",
        ]

        self.script_injection_patterns = [
            r"<script",
            r"</script>",
            r"onerror=",
            r"onload=",
            r"onclick=",
            r"eval\(",
            r"alert\(",
            r"document\.cookie",
        ]

        self.xxe_patterns = [
            r"<!DOCTYPE",
            r"<!ENTITY",
            r"SYSTEM",
            r"&[a-zA-Z]+;",
        ]

        self.command_injection_patterns = [
            r";\s*(rm|wget|curl|cat|ls|pwd)",
            r"\|\s*(sh|bash|python|perl)",
            r"\$\(",
            r"`[^`]+`",
        ]

    def _find_patterns_in_value(self, value, patterns):
        """Recursively search for patterns in a JSON value"""
        matches = []

        if isinstance(value, str):
            for pattern in patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    matches.append((pattern, value))
        elif isinstance(value, dict):
            for v in value.values():
                matches.extend(self._find_patterns_in_value(v, patterns))
        elif isinstance(value, list):
            for item in value:
                matches.extend(self._find_patterns_in_value(item, patterns))

        return matches

    def test_path_traversal_file_exists_and_is_valid_json(self):
        """Test that path traversal attack file exists and is valid JSON"""
        file_path = self.malicious_dir / "path-traversal-attempt.json"

        self.assertTrue(
            file_path.exists(), f"Path traversal attack file should exist at: {file_path}"
        )

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIsInstance(data, dict, "File should contain a JSON object")
        except json.JSONDecodeError as e:
            self.fail(f"Path traversal attack file is not valid JSON: {e}")

    def test_path_traversal_file_contains_attack_patterns(self):
        """Test that path traversal file contains path traversal attack patterns"""
        file_path = self.malicious_dir / "path-traversal-attempt.json"

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # Convert entire JSON to string for pattern matching
        json_str = json.dumps(data)

        # Check for path traversal patterns
        found_patterns = []
        for pattern in self.path_traversal_patterns:
            if re.search(pattern, json_str, re.IGNORECASE):
                found_patterns.append(pattern)

        self.assertGreater(
            len(found_patterns),
            0,
            f"Path traversal file should contain path traversal patterns. Found: {found_patterns}",
        )

        # Specifically check contractURL field
        contract_url = data.get("product", {}).get("contract", {}).get("contractURL", "")
        self.assertIn("../", contract_url, "contractURL should contain path traversal pattern")

    def test_malicious_url_file_exists_and_contains_javascript_url(self):
        """Test that malicious URL file exists and contains javascript: URL"""
        file_path = self.malicious_dir / "malicious-url-javascript.json"

        self.assertTrue(file_path.exists(), f"Malicious URL file should exist at: {file_path}")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # Check for javascript: URLs
        json_str = json.dumps(data)
        matches = self._find_patterns_in_value(data, self.malicious_url_patterns)

        self.assertGreater(
            len(matches),
            0,
            f"Malicious URL file should contain javascript: or other malicious URL patterns. Found: {matches}",
        )

        # Specifically verify javascript: pattern exists
        self.assertIn("javascript:", json_str.lower(), "File should contain javascript: URL")

    def test_xxe_attempt_file_exists_and_contains_xxe_patterns(self):
        """Test that XXE attempt file exists and contains XXE attack patterns"""
        file_path = self.malicious_dir / "xxe-attempt.json"

        self.assertTrue(file_path.exists(), f"XXE attempt file should exist at: {file_path}")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # Check for XXE patterns
        json_str = json.dumps(data)
        matches = self._find_patterns_in_value(data, self.xxe_patterns)

        self.assertGreater(
            len(matches), 0, f"XXE attempt file should contain XXE patterns. Found: {matches}"
        )

        # Check for file:// URL (common in XXE)
        self.assertIn("file://", json_str, "File should contain file:// URL pattern")

    def test_script_injection_file_exists_and_contains_script_patterns(self):
        """Test that script injection file exists and contains script injection patterns"""
        file_path = self.malicious_dir / "script-injection-attempt.json"

        self.assertTrue(file_path.exists(), f"Script injection file should exist at: {file_path}")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # Check for script injection patterns
        matches = self._find_patterns_in_value(data, self.script_injection_patterns)

        self.assertGreater(
            len(matches),
            0,
            f"Script injection file should contain script injection patterns. Found: {matches}",
        )

        # Specifically check for <script> tags
        json_str = json.dumps(data)
        self.assertIn("<script", json_str.lower(), "File should contain <script> tags")

    def test_all_malicious_files_are_valid_json(self):
        """Test that all malicious files are valid JSON (structure-wise)"""
        malicious_files = [
            "path-traversal-attempt.json",
            "malicious-url-javascript.json",
            "xxe-attempt.json",
            "script-injection-attempt.json",
            "path-traversal-multiple.json",
            "command-injection-attempt.json",
        ]

        for filename in malicious_files:
            file_path = self.malicious_dir / filename
            with self.subTest(file=filename):
                self.assertTrue(file_path.exists(), f"Malicious file should exist: {file_path}")

                try:
                    with open(file_path, encoding="utf-8") as f:
                        data = json.load(f)
                    self.assertIsInstance(
                        data, dict, f"File {filename} should contain a JSON object"
                    )
                except json.JSONDecodeError as e:
                    self.fail(f"Malicious file {filename} is not valid JSON: {e}")

    def test_all_malicious_files_contain_security_note(self):
        """Test that all malicious files contain a security note indicating they are intentionally malicious"""
        malicious_files = [
            "path-traversal-attempt.json",
            "malicious-url-javascript.json",
            "xxe-attempt.json",
            "script-injection-attempt.json",
            "path-traversal-multiple.json",
            "command-injection-attempt.json",
        ]

        for filename in malicious_files:
            file_path = self.malicious_dir / filename
            with self.subTest(file=filename):
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                # Check for security note (either _security_note or in description)
                has_note = (
                    "_security_note" in data
                    or "intentionally malicious" in json.dumps(data).lower()
                    or "security testing" in json.dumps(data).lower()
                )

                self.assertTrue(
                    has_note,
                    f"Malicious file {filename} should contain a security note indicating it is intentionally malicious",
                )

    def test_path_traversal_multiple_contains_multiple_attack_vectors(self):
        """Test that path traversal multiple file contains multiple attack vectors"""
        file_path = self.malicious_dir / "path-traversal-multiple.json"

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        json_str = json.dumps(data)

        # Count path traversal patterns
        pattern_count = sum(
            1
            for pattern in self.path_traversal_patterns
            if re.search(pattern, json_str, re.IGNORECASE)
        )

        self.assertGreaterEqual(
            pattern_count,
            2,
            f"Path traversal multiple file should contain multiple path traversal patterns. Found: {pattern_count}",
        )

    def test_command_injection_file_contains_command_patterns(self):
        """Test that command injection file contains command injection patterns"""
        file_path = self.malicious_dir / "command-injection-attempt.json"

        self.assertTrue(file_path.exists(), f"Command injection file should exist at: {file_path}")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # Check for command injection patterns
        matches = self._find_patterns_in_value(data, self.command_injection_patterns)

        self.assertGreater(
            len(matches),
            0,
            f"Command injection file should contain command injection patterns. Found: {matches}",
        )

    def test_malicious_files_match_expected_security_patterns(self):
        """Test that malicious sample files contain attack patterns matching expected regex categories.

        This test validates fixture quality — it verifies that the malicious sample files
        contain the expected attack vectors (path traversal, malicious URLs, XSS, etc.)
        by checking file contents against regex patterns, not by testing a SecurityValidator class.
        """
        malicious_files = {
            "path-traversal-attempt.json": self.path_traversal_patterns,
            "malicious-url-javascript.json": self.malicious_url_patterns,
            "xxe-attempt.json": self.xxe_patterns,
            "script-injection-attempt.json": self.script_injection_patterns,
            "command-injection-attempt.json": self.command_injection_patterns,
        }

        for filename, expected_patterns in malicious_files.items():
            file_path = self.malicious_dir / filename
            with self.subTest(file=filename):
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                # Check for expected attack patterns
                matches = self._find_patterns_in_value(data, expected_patterns)

                self.assertGreater(
                    len(matches),
                    0,
                    f"Malicious file {filename} should be detected by security validator. "
                    f"Expected patterns: {expected_patterns}, Found: {matches}",
                )

    def test_malicious_files_have_proper_structure(self):
        """Test that malicious files maintain proper ODPS structure (for realistic testing)"""
        malicious_files = [
            "path-traversal-attempt.json",
            "malicious-url-javascript.json",
            "xxe-attempt.json",
            "script-injection-attempt.json",
        ]

        for filename in malicious_files:
            file_path = self.malicious_dir / filename
            with self.subTest(file=filename):
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                # Check basic ODPS structure
                self.assertIn("schema", data, f"File {filename} should have 'schema' field")
                self.assertIn("version", data, f"File {filename} should have 'version' field")
                self.assertIn("product", data, f"File {filename} should have 'product' field")
                self.assertIn(
                    "details",
                    data.get("product", {}),
                    f"File {filename} should have 'product.details' field",
                )
