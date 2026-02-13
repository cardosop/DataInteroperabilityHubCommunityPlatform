"""
Comprehensive integration tests for $ref resolution (Task 1.7.4)

Tests ensure that $ref resolution works correctly for all modes with comprehensive coverage:
- Internal $ref resolution (#/definitions/...)
- Local file $ref resolution (./path/to/file.json)
- External URL $ref resolution (https://example.com/schema.json)
- Recursive $ref resolution (nested and chained refs)
- Integration scenarios combining multiple ref types
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

from django.test import TestCase

from hub.apps.contracts.config.odps_refs_config import ODPSRefsConfig
from hub.apps.contracts.odps_errors import ODPSRefResolutionError
from hub.apps.contracts.ref_resolver import (
    ExternalRefHandling,
    RefMode,
    RefResolver,
)


class RefResolverIntegrationTestBase(TestCase):
    """Base class for $ref resolution integration tests with shared fixtures."""

    def setUp(self):
        """Set up test fixtures for all $ref resolution modes."""
        # Create temporary directory for local file refs
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(self._cleanup_temp_dir)

        # Create test files for local ref resolution
        self._create_test_files()

        # Initialize resolver with test base path
        config = ODPSRefsConfig()
        # Add temp directory to allowed base dirs via _config_data
        config._config_data = {
            "allowed_base_dirs": [str(self.temp_dir)],
            "url_allowlist": [],
            "url_denylist": [],
        }
        self.resolver = RefResolver(
            config=config,
            base_path=self.temp_dir,
            enable_caching=False,  # Disable caching for deterministic tests
        )

    def _cleanup_temp_dir(self):
        """Clean up temporary directory."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _create_test_files(self):
        """Create test files for local ref resolution."""
        # Create schemas directory
        schemas_dir = self.temp_dir / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)

        # Create definitions directory
        definitions_dir = self.temp_dir / "definitions"
        definitions_dir.mkdir(parents=True, exist_ok=True)

        # Test file 1: Simple schema
        (schemas_dir / "email.json").write_text(
            json.dumps({"type": "string", "format": "email", "description": "Email address schema"})
        )

        # Test file 2: User schema with nested refs
        # Note: Nested $refs must be relative to base_path, not the file's directory
        (schemas_dir / "user.json").write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "email": {"$ref": "./schemas/email.json"},
                        "name": {"type": "string"},
                    },
                    "required": ["id", "email"],
                }
            )
        )

        # Test file 3: Product schema
        (schemas_dir / "product.json").write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "price": {"type": "number"},
                    },
                }
            )
        )

        # Test file 4: Quality definition
        (definitions_dir / "quality.json").write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number", "minimum": 0, "maximum": 100},
                        "metrics": {"type": "array", "items": {"type": "string"}},
                    },
                }
            )
        )

        # Test file 5: Schema with internal ref (for recursive testing)
        # Note: Nested $refs must be relative to base_path, not the file's directory
        (schemas_dir / "order.json").write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "user": {"$ref": "./schemas/user.json"},
                        "products": {"type": "array", "items": {"$ref": "./schemas/product.json"}},
                    },
                }
            )
        )

    def _assert_resolved_value(
        self, resolved: Dict[str, Any], expected_keys: list, description: str = ""
    ):
        """Assert that resolved value has expected structure."""
        desc_suffix = f": {description}" if description else ""
        self.assertIsInstance(resolved, dict, f"Resolved value should be a dict{desc_suffix}")
        for key in expected_keys:
            self.assertIn(key, resolved, f"Resolved value should have key '{key}'{desc_suffix}")


class RefResolverInternalRefIntegrationTest(RefResolverIntegrationTestBase):
    """Test internal $ref resolution integration."""

    def test_resolve_internal_simple_definition(self):
        """Test resolving simple internal $ref to definitions."""
        document = {
            "definitions": {
                "Email": {"type": "string", "format": "email", "description": "Email address"}
            },
            "product": {"dataQuality": {"$ref": "#/definitions/Email"}},
        }

        resolved = self.resolver.resolve_internal("#/definitions/Email", document)
        self._assert_resolved_value(resolved, ["type", "format", "description"])
        self.assertEqual(resolved["type"], "string")
        self.assertEqual(resolved["format"], "email")

    def test_resolve_internal_nested_path(self):
        """Test resolving internal $ref with nested path."""
        document = {
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
                    }
                }
            },
            "product": {"owner": {"$ref": "#/components/schemas/User"}},
        }

        resolved = self.resolver.resolve_internal("#/components/schemas/User", document)
        self._assert_resolved_value(resolved, ["type", "properties"])
        self.assertEqual(resolved["type"], "object")
        self.assertIn("id", resolved["properties"])

    def test_resolve_internal_root_reference(self):
        """Test resolving internal $ref to root level."""
        document = {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "product": {"schema": {"$ref": "#"}},
        }

        resolved = self.resolver.resolve_internal("#", document)
        self._assert_resolved_value(resolved, ["type", "properties"])
        self.assertEqual(resolved["type"], "object")

    def test_resolve_internal_array_reference(self):
        """Test resolving internal $ref to array element."""
        document = {
            "definitions": {"items": [{"type": "string"}, {"type": "number"}]},
            "product": {"types": {"$ref": "#/definitions/items/0"}},
        }

        resolved = self.resolver.resolve_internal("#/definitions/items/0", document)
        self.assertIsInstance(resolved, dict)
        self.assertEqual(resolved["type"], "string")

    def test_resolve_internal_missing_reference(self):
        """Test that missing internal $ref raises error."""
        document = {"definitions": {"Email": {"type": "string"}}}

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_internal("#/definitions/NonExistent", document)
        self.assertIn("not found", str(cm.exception).lower())


class RefResolverLocalRefIntegrationTest(RefResolverIntegrationTestBase):
    """Test local file $ref resolution integration."""

    def test_resolve_local_simple_file(self):
        """Test resolving simple local file $ref."""
        resolved = self.resolver.resolve_local("./schemas/email.json")
        self._assert_resolved_value(resolved, ["type", "format", "description"])
        self.assertEqual(resolved["type"], "string")
        self.assertEqual(resolved["format"], "email")

    def test_resolve_local_relative_path(self):
        """Test resolving local $ref with relative path."""
        resolved = self.resolver.resolve_local("schemas/user.json")
        self._assert_resolved_value(resolved, ["type", "properties"])
        self.assertEqual(resolved["type"], "object")
        self.assertIn("email", resolved["properties"])

    def test_resolve_local_nested_ref(self):
        """Test resolving local file that contains another $ref."""
        # user.json contains a ref to email.json (relative to base_path)
        resolved = self.resolver.resolve_local("./schemas/user.json")
        self._assert_resolved_value(resolved, ["type", "properties"])
        # The nested $ref should be resolved when using resolve_all_refs
        # For now, just verify the file is loaded
        self.assertIn("email", resolved["properties"])
        # The email property should have a $ref (will be resolved by resolve_all_refs)
        self.assertIn("$ref", resolved["properties"]["email"])

    def test_resolve_local_missing_file(self):
        """Test that missing local file raises error."""
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local("./schemas/nonexistent.json")
        self.assertIn("not found", str(cm.exception).lower())

    def test_resolve_local_path_traversal_prevention(self):
        """Test that path traversal attempts are prevented."""
        # Try to access file outside allowed directory
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local("../../etc/passwd")
        error_msg = str(cm.exception).lower()
        # Should fail due to security validation
        self.assertTrue(
            "not allowed" in error_msg
            or "outside" in error_msg
            or "security" in error_msg
            or "not in allowed" in error_msg,
            f"Expected security/validation error, got: {cm.exception}",
        )


class RefResolverExternalRefIntegrationTest(RefResolverIntegrationTestBase):
    """Test external URL $ref resolution integration."""

    def setUp(self):
        """Set up test fixtures with HTTP test server."""
        super().setUp()
        # Use httpbin.org for real HTTP testing (no mocks)
        # httpbin.org is a real HTTP testing service
        self.test_base_url = "https://httpbin.org"

    def test_resolve_external_url_validation_allowlist(self):
        """Test that external URL allowlist validation works."""
        # Configure resolver with URL restrictions
        config = ODPSRefsConfig()
        config._config_data = {
            "allowed_base_dirs": [],
            "url_allowlist": [self.test_base_url],
            "url_denylist": [],
        }
        resolver = RefResolver(config=config, enable_caching=False)

        # Test that URL not in allowlist is rejected
        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve_external("https://example.com/schema.json")
        # Should fail due to URL validation
        error_msg = str(cm.exception).lower()
        self.assertTrue(
            "not allowed" in error_msg or "denied" in error_msg or "security" in error_msg,
            f"Expected security/validation error, got: {cm.exception}",
        )

    def test_resolve_external_url_validation_denylist(self):
        """Test that external URL denylist validation works."""
        # Configure resolver with URL restrictions
        config = ODPSRefsConfig()
        config._config_data = {
            "allowed_base_dirs": [],
            "url_allowlist": [],  # Empty allowlist means all allowed (unless in denylist)
            "url_denylist": ["https://blocked.com"],
        }
        resolver = RefResolver(config=config, enable_caching=False)

        # Test that URL in denylist is rejected
        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve_external("https://blocked.com/schema.json")
        # Should fail due to URL validation
        error_msg = str(cm.exception).lower()
        self.assertTrue(
            "not allowed" in error_msg or "denied" in error_msg or "security" in error_msg,
            f"Expected security/validation error, got: {cm.exception}",
        )

    def test_resolve_external_invalid_url(self):
        """Test that invalid external URL raises error."""
        config = ODPSRefsConfig()
        config._config_data = {
            "allowed_base_dirs": [],
            "url_allowlist": [],  # Allow all for this test
            "url_denylist": [],
        }
        resolver = RefResolver(config=config, enable_caching=False)

        # Test invalid URL format
        with self.assertRaises(ODPSRefResolutionError):
            resolver.resolve_external("not-a-valid-url")

    def test_resolve_external_nonexistent_url(self):
        """Test that nonexistent external URL raises error."""
        config = ODPSRefsConfig()
        config._config_data = {
            "allowed_base_dirs": [],
            "url_allowlist": [],  # Allow all for this test
            "url_denylist": [],
        }
        resolver = RefResolver(config=config, enable_caching=False, timeout_per_ref=2)

        # Test URL that doesn't exist (should timeout or fail)
        with self.assertRaises(ODPSRefResolutionError):
            resolver.resolve_external("https://nonexistent-domain-12345.com/schema.json")


class RefResolverRecursiveRefIntegrationTest(RefResolverIntegrationTestBase):
    """Test recursive $ref resolution integration."""

    def test_resolve_all_refs_simple_internal(self):
        """Test resolving all refs with simple internal refs."""
        document = {
            "product": {"dataQuality": {"$ref": "#/definitions/quality"}},
            "definitions": {"quality": {"score": 95, "metrics": ["completeness", "validity"]}},
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # Original should be unchanged
        self.assertIn("$ref", original["product"]["dataQuality"])

        # Resolved should have ref replaced
        self.assertNotIn("$ref", resolved["product"]["dataQuality"])
        self.assertEqual(resolved["product"]["dataQuality"]["score"], 95)
        self.assertIn("metrics", resolved["product"]["dataQuality"])

    def test_resolve_all_refs_nested_internal(self):
        """Test resolving all refs with nested internal refs."""
        document = {
            "product": {
                "owner": {"$ref": "#/components/schemas/user"},
                "schema": {"$ref": "#/components/schemas/product"},
            },
            "components": {
                "schemas": {
                    "user": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "email": {"$ref": "#/components/schemas/email"},
                        },
                    },
                    "email": {"type": "string", "format": "email"},
                    "product": {"type": "object", "properties": {"id": {"type": "string"}}},
                }
            },
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # All refs should be resolved
        self.assertNotIn("$ref", resolved["product"]["owner"])
        self.assertNotIn("$ref", resolved["product"]["schema"])
        self.assertNotIn("$ref", resolved["components"]["schemas"]["user"]["properties"]["email"])

        # Verify resolved values
        self.assertEqual(resolved["product"]["owner"]["type"], "object")
        self.assertEqual(resolved["product"]["schema"]["type"], "object")
        self.assertEqual(
            resolved["components"]["schemas"]["user"]["properties"]["email"]["type"], "string"
        )

    def test_resolve_all_refs_with_local_refs(self):
        """Test resolving all refs with local file refs."""
        # Create a document that references local files
        document = {"product": {"schema": {"$ref": "./schemas/user.json"}}}

        original, resolved = self.resolver.resolve_all_refs(document)

        # Local ref should be resolved
        self.assertNotIn("$ref", resolved["product"]["schema"])
        self.assertIn("type", resolved["product"]["schema"])
        self.assertEqual(resolved["product"]["schema"]["type"], "object")

    def test_resolve_all_refs_mixed_refs(self):
        """Test resolving all refs with mixed internal and local refs."""
        document = {
            "product": {
                "owner": {"$ref": "#/definitions/user"},
                "schema": {"$ref": "./schemas/product.json"},
            },
            "definitions": {
                "user": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "email": {"$ref": "./schemas/email.json"},
                    },
                }
            },
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # All refs should be resolved
        self.assertNotIn("$ref", resolved["product"]["owner"])
        self.assertNotIn("$ref", resolved["product"]["schema"])
        self.assertNotIn("$ref", resolved["definitions"]["user"]["properties"]["email"])

        # Verify resolved values
        self.assertEqual(resolved["product"]["owner"]["type"], "object")
        self.assertEqual(resolved["product"]["schema"]["type"], "object")
        self.assertEqual(resolved["definitions"]["user"]["properties"]["email"]["type"], "string")

    def test_resolve_all_refs_recursive_chain(self):
        """Test resolving refs in a recursive chain."""
        # Create a chain: A -> B -> C
        # Note: Nested $refs must be relative to base_path, not the file's directory
        (self.temp_dir / "schemas" / "c.json").write_text(
            json.dumps({"type": "string", "description": "C schema"})
        )

        (self.temp_dir / "schemas" / "b.json").write_text(
            json.dumps({"type": "object", "properties": {"c": {"$ref": "./schemas/c.json"}}})
        )

        (self.temp_dir / "schemas" / "a.json").write_text(
            json.dumps({"type": "object", "properties": {"b": {"$ref": "./schemas/b.json"}}})
        )

        document = {"product": {"schema": {"$ref": "./schemas/a.json"}}}

        original, resolved = self.resolver.resolve_all_refs(document)

        # All refs in chain should be resolved
        self.assertNotIn("$ref", resolved["product"]["schema"])
        self.assertNotIn("$ref", resolved["product"]["schema"]["properties"]["b"])
        self.assertNotIn(
            "$ref", resolved["product"]["schema"]["properties"]["b"]["properties"]["c"]
        )

        # Verify chain resolution
        self.assertEqual(resolved["product"]["schema"]["type"], "object")
        self.assertEqual(resolved["product"]["schema"]["properties"]["b"]["type"], "object")
        self.assertEqual(
            resolved["product"]["schema"]["properties"]["b"]["properties"]["c"]["type"], "string"
        )

    def test_resolve_all_refs_circular_detection(self):
        """Test that circular references are detected."""
        # Create circular reference: A -> B -> A
        # Note: Nested $refs must be relative to base_path, not the file's directory
        (self.temp_dir / "schemas" / "a.json").write_text(
            json.dumps({"type": "object", "properties": {"b": {"$ref": "./schemas/b.json"}}})
        )

        (self.temp_dir / "schemas" / "b.json").write_text(
            json.dumps({"type": "object", "properties": {"a": {"$ref": "./schemas/a.json"}}})
        )

        document = {"product": {"schema": {"$ref": "./schemas/a.json"}}}

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_all_refs(document)
        self.assertIn("circular", str(cm.exception).lower())

    def test_resolve_all_refs_in_array(self):
        """Test resolving refs in arrays."""
        document = {
            "product": {
                "schemas": [{"$ref": "#/definitions/email"}, {"$ref": "#/definitions/user"}]
            },
            "definitions": {
                "email": {"type": "string", "format": "email"},
                "user": {"type": "object", "properties": {"id": {"type": "string"}}},
            },
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # Refs in array should be resolved
        self.assertNotIn("$ref", resolved["product"]["schemas"][0])
        self.assertNotIn("$ref", resolved["product"]["schemas"][1])
        self.assertEqual(resolved["product"]["schemas"][0]["type"], "string")
        self.assertEqual(resolved["product"]["schemas"][1]["type"], "object")

    def test_resolve_all_refs_preserves_original(self):
        """Test that original document is preserved."""
        document = {
            "product": {"dataQuality": {"$ref": "#/definitions/quality"}},
            "definitions": {"quality": {"score": 95}},
        }

        original, resolved = self.resolver.resolve_all_refs(document, preserve_original=True)

        # Original should have $ref
        self.assertIn("$ref", original["product"]["dataQuality"])
        self.assertEqual(original["product"]["dataQuality"]["$ref"], "#/definitions/quality")

        # Resolved should not have $ref
        self.assertNotIn("$ref", resolved["product"]["dataQuality"])
        self.assertEqual(resolved["product"]["dataQuality"]["score"], 95)

        # Original and resolved should be different objects
        self.assertIsNot(original, resolved)


class RefResolverIntegrationScenariosTest(RefResolverIntegrationTestBase):
    """Test complex integration scenarios combining multiple ref types."""

    def test_integration_complex_document(self):
        """Test resolving refs in a complex document with all ref types."""
        # Create additional test files
        (self.temp_dir / "schemas" / "address.json").write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {"street": {"type": "string"}, "city": {"type": "string"}},
                }
            )
        )

        document = {
            "product": {
                "owner": {"$ref": "#/definitions/user"},
                "schema": {"$ref": "./schemas/user.json"},
                "address": {"$ref": "./schemas/address.json"},
            },
            "definitions": {
                "user": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "email": {"$ref": "#/definitions/email"},
                        "profile": {
                            "$ref": "./schemas/user.json"
                        },  # This will work since it's relative to base_path
                    },
                },
                "email": {"type": "string", "format": "email"},
            },
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # All refs should be resolved
        self.assertNotIn("$ref", resolved["product"]["owner"])
        self.assertNotIn("$ref", resolved["product"]["schema"])
        self.assertNotIn("$ref", resolved["product"]["address"])
        self.assertNotIn("$ref", resolved["definitions"]["user"]["properties"]["email"])
        self.assertNotIn("$ref", resolved["definitions"]["user"]["properties"]["profile"])

        # Verify structure
        self.assertEqual(resolved["product"]["owner"]["type"], "object")
        self.assertEqual(resolved["product"]["schema"]["type"], "object")
        self.assertEqual(resolved["product"]["address"]["type"], "object")
        self.assertEqual(resolved["definitions"]["user"]["properties"]["email"]["type"], "string")

    def test_integration_external_ref_handling_modes(self):
        """Test different external ref handling modes."""
        # Create a local file that can be used as a test external ref
        # Since we can't make real external HTTP calls reliably, we test the handling modes
        # with a local file that simulates external ref behavior

        # Test REMOVE mode - should remove external refs
        document = {
            "product": {
                "schema": {"$ref": "https://example.com/schema.json"},
                "owner": {"$ref": "#/definitions/user"},
            },
            "definitions": {"user": {"type": "object", "properties": {"id": {"type": "string"}}}},
        }

        config = ODPSRefsConfig()
        config._config_data = {
            "allowed_base_dirs": [],
            "url_allowlist": [],  # Empty allowlist means external refs will be rejected
            "url_denylist": [],
        }
        resolver = RefResolver(config=config, enable_caching=False)

        # Test REMOVE mode - external refs should be removed, internal refs should work
        original, resolved = resolver.resolve_all_refs(
            document, external_ref_handling=ExternalRefHandling.REMOVE
        )
        # The external $ref key should be removed
        self.assertNotIn("schema", resolved["product"])
        # Internal ref should still be resolved
        self.assertNotIn("$ref", resolved["product"]["owner"])

        # Test DISABLE mode - should raise error for external refs
        with self.assertRaises(ODPSRefResolutionError):
            resolver.resolve_all_refs(document, external_ref_handling=ExternalRefHandling.DISABLE)

    def test_integration_nested_resolved_values(self):
        """Test that resolved values can contain nested structures."""
        document = {
            "product": {"dataQuality": {"$ref": "#/definitions/quality"}},
            "definitions": {
                "quality": {
                    "score": 95,
                    "metrics": {
                        "completeness": {"$ref": "#/definitions/metric"},
                        "validity": {"$ref": "#/definitions/metric"},
                    },
                },
                "metric": {"type": "number", "minimum": 0, "maximum": 100},
            },
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # Nested refs should be resolved
        self.assertNotIn("$ref", resolved["product"]["dataQuality"])
        self.assertNotIn("$ref", resolved["product"]["dataQuality"]["metrics"]["completeness"])
        self.assertNotIn("$ref", resolved["product"]["dataQuality"]["metrics"]["validity"])

        # Verify nested structure
        self.assertEqual(resolved["product"]["dataQuality"]["score"], 95)
        self.assertEqual(
            resolved["product"]["dataQuality"]["metrics"]["completeness"]["type"], "number"
        )
