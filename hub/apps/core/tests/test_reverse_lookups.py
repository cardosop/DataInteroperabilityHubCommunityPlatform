"""
Comprehensive tests for Django URL reverse lookups.

This test suite verifies:
1. All reverse() calls can be resolved
2. All reverse lookups map to valid URL patterns
3. Reverse lookup dependencies are correct
"""

import json
from pathlib import Path

import pytest
from django.test import TestCase
from django.urls import NoReverseMatch, reverse


@pytest.mark.django_db(transaction=True)
class ReverseLookupTest(TestCase):
    """Test that all reverse lookups can be resolved"""

    def test_all_reverse_calls_resolvable(self):
        """Test that all reverse() calls found in codebase can be resolved"""
        # Load reverse lookup analysis
        # Try multiple possible locations
        possible_paths = [
            Path(__file__).parent.parent.parent.parent
            / "reverse_lookup_analysis.json",  # From hub/apps/core/tests/
            Path(__file__).parent.parent.parent.parent.parent
            / "reverse_lookup_analysis.json",  # From project root
            Path("/app/reverse_lookup_analysis.json"),  # Absolute path in Docker
            Path("/app/hub/reverse_lookup_analysis.json"),  # Alternative Docker path
        ]

        analysis_file = None
        for path in possible_paths:
            if path.exists():
                analysis_file = path
                break

        if not analysis_file or not analysis_file.exists():
            self.fail(
                "Required artifact reverse_lookup_analysis.json not found. "
                "Run scripts/analyze_reverse_lookups.py to generate it."
            )

        assert analysis_file is not None  # Type guard for linter
        with open(analysis_file) as f:
            analysis = json.load(f)

        reverse_calls = analysis.get("reverse_calls", [])
        unmapped = analysis.get("unmapped", [])

        # Track failures
        failures = []

        for reverse_call in reverse_calls:
            url_name = reverse_call.get("url_name")
            kwargs = reverse_call.get("kwargs", {})

            # Skip unmapped lookups (they're known issues)
            if any(u["url_name"] == url_name for u in unmapped):
                continue

            # Skip dynamic reverse calls (f-strings)
            if url_name.endswith("-") or "{" in url_name:
                continue

            # Handle reverse calls with kwargs that contain Python expressions (not actual values)
            # These are extracted from source code and can't be evaluated safely
            # We'll try to resolve them with dummy values to verify the URL pattern exists
            if kwargs:
                # Check if any kwargs contain Python expressions or variable names
                has_expression_kwargs = any(
                    isinstance(v, str)
                    and (
                        any(
                            expr in v
                            for expr in ["self.", "uuid.", "str(", "int(", ".id", ".uuid4()"]
                        )
                        or
                        # Also check if value is just a variable name (like 'report_id' without quotes)
                        (v in ["report_id", "domain_id", "id", "pk"] and len(kwargs) == 1)
                    )
                    for v in kwargs.values()
                )

                if has_expression_kwargs:
                    # Try to resolve with dummy values to verify the URL pattern exists
                    try:
                        # Generate appropriate dummy values based on parameter names
                        dummy_kwargs = {}
                        for key in kwargs.keys():
                            if "report_id" in key.lower():
                                # Special handling for report_id (needs different UUID)
                                dummy_kwargs[key] = "00000000-0000-0000-0000-000000000001"
                            elif "id" in key.lower() or "pk" in key.lower():
                                # Use a UUID-like string for ID parameters
                                dummy_kwargs[key] = "00000000-0000-0000-0000-000000000000"
                            else:
                                dummy_kwargs[key] = "test-value"

                        # For URLs that might need multiple kwargs, ensure we have all required ones
                        # Check if URL name suggests it needs multiple parameters
                        # Only add report_id for "get-compliance-report", not "list-compliance-reports"
                        if "get-compliance-report" in url_name:
                            # These need both id and report_id
                            if "id" not in dummy_kwargs and "pk" not in dummy_kwargs:
                                dummy_kwargs["id"] = "00000000-0000-0000-0000-000000000000"
                            if "report_id" not in dummy_kwargs:
                                dummy_kwargs["report_id"] = "00000000-0000-0000-0000-000000000001"

                        # Don't add extra kwargs that weren't in the original - only use what we extracted

                        # Remove report_id if URL doesn't need it (like list-compliance-reports)
                        if "list-compliance-reports" in url_name and "report_id" in dummy_kwargs:
                            del dummy_kwargs["report_id"]

                        url = reverse(url_name, kwargs=dummy_kwargs)
                        # If it resolves, the pattern is valid (even if we can't test with real values)
                        continue
                    except NoReverseMatch as e:  # noqa: no-reverse-match — URL validation
                        # Check if the error indicates missing required kwargs
                        error_msg = str(e)
                        if (
                            "with no arguments" in error_msg
                            or "with keyword arguments" in error_msg
                        ):
                            # Try to infer required kwargs from the error message or URL pattern
                            # For detail views, usually need 'id' or 'pk'
                            if "-detail" in url_name or "-analytics" in url_name or "-" in url_name:
                                # Try common parameter names
                                for param_name in ["id", "pk"]:
                                    try:
                                        test_kwargs = {
                                            param_name: "00000000-0000-0000-0000-000000000000"
                                        }
                                        reverse(url_name, kwargs=test_kwargs)
                                        # If it works, the pattern exists but requires kwargs
                                        continue
                                    except NoReverseMatch:  # noqa: no-reverse-match — URL validation
                                        continue

                        # Pattern doesn't exist or requires specific kwargs - this is a real issue
                        failures.append(
                            {
                                "url_name": url_name,
                                "file": reverse_call.get("file"),
                                "line": reverse_call.get("line"),
                                "error": f"URL pattern not found: {e!s}",
                            }
                        )
                    except Exception as e:
                        # Other errors might be due to invalid dummy values, skip for now
                        failures.append(
                            {
                                "url_name": url_name,
                                "file": reverse_call.get("file"),
                                "line": reverse_call.get("line"),
                                "error": f"Error resolving with dummy kwargs: {e!s}",
                            }
                        )
                    continue

            # Handle reverse calls that require kwargs but don't have them extracted
            # Check if URL name suggests it needs kwargs (detail views, custom actions)
            if not kwargs and (
                "-detail" in url_name or "-analytics" in url_name or url_name.count("-") >= 2
            ):
                # Try common parameter names to see if pattern exists
                pattern_found = False
                for param_name in ["id", "pk"]:
                    try:
                        test_kwargs = {param_name: "00000000-0000-0000-0000-000000000000"}
                        reverse(url_name, kwargs=test_kwargs)
                        pattern_found = True
                        # Pattern exists but requires kwargs - this is expected for detail views
                        break
                    except NoReverseMatch:  # noqa: no-reverse-match — URL validation
                        continue

                if pattern_found:
                    # Pattern exists, just requires kwargs - skip this test case
                    continue

            try:
                if kwargs:
                    url = reverse(url_name, kwargs=kwargs)
                else:
                    url = reverse(url_name)
                self.assertIsNotNone(url, f"Reverse lookup '{url_name}' returned None")
            except NoReverseMatch as e:  # noqa: no-reverse-match — URL validation
                failures.append(
                    {
                        "url_name": url_name,
                        "file": reverse_call.get("file"),
                        "line": reverse_call.get("line"),
                        "error": str(e),
                    }
                )
            except Exception as e:
                failures.append(
                    {
                        "url_name": url_name,
                        "file": reverse_call.get("file"),
                        "line": reverse_call.get("line"),
                        "error": f"Unexpected error: {e!s}",
                    }
                )

        if failures:
            failure_msg = "\n".join(
                [f"  - {f['url_name']} in {f['file']}:{f['line']}: {f['error']}" for f in failures]
            )
            self.fail(f"Failed to resolve {len(failures)} reverse lookups:\n{failure_msg}")

    def test_reverse_lookup_mapping(self):
        """Test that reverse lookups map to valid URL patterns"""
        # Load reverse lookup analysis
        # Try multiple possible locations
        possible_paths = [
            Path(__file__).parent.parent.parent.parent / "reverse_lookup_analysis.json",
            Path(__file__).parent.parent.parent.parent.parent / "reverse_lookup_analysis.json",
            Path("/app/reverse_lookup_analysis.json"),
            Path("/app/hub/reverse_lookup_analysis.json"),
        ]

        analysis_file = None
        for path in possible_paths:
            if path.exists():
                analysis_file = path
                break

        if not analysis_file or not analysis_file.exists():
            self.fail(
                "Required artifact reverse_lookup_analysis.json not found. "
                "Run scripts/analyze_reverse_lookups.py to generate it."
            )

        assert analysis_file is not None  # Type guard for linter
        with open(analysis_file) as f:
            analysis = json.load(f)

        mapping = analysis.get("mapping", {})
        url_patterns = analysis.get("url_patterns", {})

        # Check that mapped lookups have valid patterns
        failures = []
        for url_name, mappings in mapping.items():
            for m in mappings:
                pattern = m.get("pattern")
                if pattern is None:
                    # This is an unmapped lookup, skip it
                    continue

                pattern_name = pattern.get("name")
                if pattern_name and pattern_name not in url_patterns:
                    failures.append(
                        {
                            "url_name": url_name,
                            "pattern_name": pattern_name,
                            "source": m.get("source", {}).get("file"),
                        }
                    )

        if failures:
            failure_msg = "\n".join(
                [f"  - {f['url_name']} -> {f['pattern_name']} (in {f['source']})" for f in failures]
            )
            self.fail(f"Found {len(failures)} invalid pattern mappings:\n{failure_msg}")

    def test_unmapped_lookups_are_documented(self):
        """Test that unmapped lookups are documented and have reasonable explanations"""
        # Load reverse lookup analysis
        # Try multiple possible locations
        possible_paths = [
            Path(__file__).parent.parent.parent.parent / "reverse_lookup_analysis.json",
            Path(__file__).parent.parent.parent.parent.parent / "reverse_lookup_analysis.json",
            Path("/app/reverse_lookup_analysis.json"),
            Path("/app/hub/reverse_lookup_analysis.json"),
        ]

        analysis_file = None
        for path in possible_paths:
            if path.exists():
                analysis_file = path
                break

        if not analysis_file or not analysis_file.exists():
            self.fail(
                "Required artifact reverse_lookup_analysis.json not found. "
                "Run scripts/analyze_reverse_lookups.py to generate it."
            )

        assert analysis_file is not None  # Type guard for linter
        with open(analysis_file) as f:
            analysis = json.load(f)

        unmapped = analysis.get("unmapped", [])

        # Check that unmapped lookups are reasonable
        # (e.g., dynamic reverse calls, test-only, etc.)
        problematic = []
        for u in unmapped:
            url_name = u.get("url_name", "")
            # Dynamic reverse calls (f-strings) are OK
            if url_name.endswith("-") or "{" in url_name:
                continue
            # Check if it's actually resolvable
            try:
                # Try to resolve with dummy kwargs
                reverse(url_name, kwargs={"id": "test", "pk": "test"})
                problematic.append(
                    {
                        "url_name": url_name,
                        "sources": u.get("sources", []),
                    }
                )
            except NoReverseMatch:  # noqa: no-reverse-match — URL validation
                # This is expected for unmapped lookups
                pass
            except Exception as e:
                # Unexpected errors should be surfaced, not swallowed
                problematic.append(
                    {
                        "url_name": url_name,
                        "sources": u.get("sources", []),
                        "error": str(e),
                    }
                )

        if problematic:
            failure_msg = "\n".join(
                [f"  - {p['url_name']} (used in {len(p['sources'])} places)" for p in problematic]
            )
            self.fail(
                f"Found {len(problematic)} unmapped lookups that are actually resolvable:\n{failure_msg}\n"
                "These should be added to the URL pattern mapping."
            )
