"""
Unit tests for ODPS $ref Resolver.

Tests verify:
1. RefResolver initialization
2. Security controls (URL validation, timeout, size limits, path traversal prevention)
3. Internal $ref resolution
4. Local $ref resolution
5. External $ref resolution
6. Redis caching for external refs
7. Error handling
"""
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, SimpleTestCase

import httpx

from hub.apps.contracts.ref_resolver import (
    RefResolver,
    RefMode,
    ExternalRefHandling,
    DEFAULT_TIMEOUT_PER_REF,
    DEFAULT_TIMEOUT_TOTAL,
    DEFAULT_MAX_REF_SIZE,
    DEFAULT_MAX_TOTAL_SIZE,
    DEFAULT_CACHE_TTL,
)
from hub.apps.contracts.config.odps_refs_config import ODPSRefsConfig
from hub.apps.contracts.odps_errors import ODPSRefResolutionError


class RefResolverInitializationTest(TestCase):
    """Test RefResolver initialization"""

    def test_ref_resolver_initialization_defaults(self):
        """Test that RefResolver initializes with default values"""
        resolver = RefResolver()

        self.assertIsNotNone(resolver.config)
        self.assertIsNotNone(resolver.base_path)
        self.assertEqual(resolver.timeout_per_ref, DEFAULT_TIMEOUT_PER_REF)
        self.assertEqual(resolver.timeout_total, DEFAULT_TIMEOUT_TOTAL)
        self.assertEqual(resolver.max_ref_size, DEFAULT_MAX_REF_SIZE)
        self.assertEqual(resolver.max_total_size, DEFAULT_MAX_TOTAL_SIZE)
        self.assertEqual(resolver.cache_ttl, DEFAULT_CACHE_TTL)
        self.assertEqual(resolver._total_size, 0)

    def test_ref_resolver_initialization_custom_config(self):
        """Test that RefResolver initializes with custom configuration"""
        config = ODPSRefsConfig()
        base_path = Path("/custom/path")
        tenant_id = "test-tenant-id"
        user_id = "test-user-id"

        resolver = RefResolver(
            config=config,
            base_path=base_path,
            tenant_id=tenant_id,
            user_id=user_id,
            timeout_per_ref=10,
            timeout_total=60,
            max_ref_size=2048000,
            max_total_size=20480000,
            cache_ttl=7200,
            enable_caching=False,
        )

        self.assertEqual(resolver.config, config)
        self.assertEqual(resolver.base_path, base_path)
        self.assertEqual(resolver.tenant_id, tenant_id)
        self.assertEqual(resolver.user_id, user_id)
        self.assertEqual(resolver.timeout_per_ref, 10)
        self.assertEqual(resolver.timeout_total, 60)
        self.assertEqual(resolver.max_ref_size, 2048000)
        self.assertEqual(resolver.max_total_size, 20480000)
        self.assertEqual(resolver.cache_ttl, 7200)
        self.assertFalse(resolver.enable_caching)

    def test_ref_resolver_detect_mode_internal(self):
        """Test that internal $ref mode is detected correctly"""
        resolver = RefResolver()

        mode = resolver._detect_mode("#/definitions/Email")
        self.assertEqual(mode, RefMode.INTERNAL)

        mode = resolver._detect_mode("#/components/schemas/User")
        self.assertEqual(mode, RefMode.INTERNAL)

    def test_ref_resolver_detect_mode_local(self):
        """Test that local $ref mode is detected correctly"""
        resolver = RefResolver()

        mode = resolver._detect_mode("./schemas/email.json")
        self.assertEqual(mode, RefMode.LOCAL)

        mode = resolver._detect_mode("../schemas/user.json")
        self.assertEqual(mode, RefMode.LOCAL)

        mode = resolver._detect_mode("schemas/product.json")
        self.assertEqual(mode, RefMode.LOCAL)

    def test_ref_resolver_detect_mode_external(self):
        """Test that external $ref mode is detected correctly"""
        resolver = RefResolver()

        mode = resolver._detect_mode("https://example.com/schema.json")
        self.assertEqual(mode, RefMode.EXTERNAL)

        mode = resolver._detect_mode("http://example.com/schema.json")
        self.assertEqual(mode, RefMode.EXTERNAL)

    def test_ref_resolver_detect_mode_empty_path(self):
        """Test that empty $ref path raises ValueError"""
        resolver = RefResolver()

        with self.assertRaises(ValueError) as cm:
            resolver._detect_mode("")
        self.assertIn("cannot be empty", str(cm.exception))


class RefResolverInternalRefTest(TestCase):
    """Test internal $ref resolution"""

    def setUp(self):
        """Set up test fixtures"""
        self.resolver = RefResolver()

    def test_resolve_internal_simple(self):
        """Test resolving simple internal $ref"""
        document = {
            "definitions": {
                "Email": {
                    "type": "string",
                    "format": "email"
                }
            }
        }

        result = self.resolver.resolve_internal("#/definitions/Email", document)
        self.assertEqual(result, {"type": "string", "format": "email"})

    def test_resolve_internal_nested(self):
        """Test resolving nested internal $ref"""
        document = {
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string"}
                        }
                    }
                }
            }
        }

        result = self.resolver.resolve_internal("#/components/schemas/User", document)
        self.assertEqual(result["type"], "object")
        self.assertIn("properties", result)

    def test_resolve_internal_not_found(self):
        """Test that missing internal $ref raises error"""
        document = {
            "definitions": {
                "Email": {"type": "string"}
            }
        }

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_internal("#/definitions/NotFound", document)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)

    def test_resolve_internal_invalid_path(self):
        """Test that invalid internal $ref path raises error"""
        document = {"definitions": {"Email": {"type": "string"}}}

        with self.assertRaises(ValueError):
            self.resolver.resolve_internal("definitions/Email", document)  # Missing #

        with self.assertRaises(ValueError):
            self.resolver.resolve_internal("#definitions/Email", document)  # Missing leading /

    def test_resolve_internal_with_escaped_characters(self):
        """Test resolving internal $ref with escaped characters (~0 for ~, ~1 for /)"""
        document = {
            "paths": {
                "a~b": {
                    "type": "object",
                    "description": "Path with tilde"
                },
                "a/b": {
                    "type": "object",
                    "description": "Path with slash"
                }
            }
        }

        # Test ~0 (escaped tilde)
        result = self.resolver.resolve_internal("#/paths/a~0b", document)
        self.assertEqual(result["description"], "Path with tilde")

        # Test ~1 (escaped slash)
        result = self.resolver.resolve_internal("#/paths/a~1b", document)
        self.assertEqual(result["description"], "Path with slash")

    def test_resolve_internal_with_array_indices(self):
        """Test resolving internal $ref with array indices"""
        document = {
            "items": [
                {"name": "first", "value": 1},
                {"name": "second", "value": 2},
                {"name": "third", "value": 3}
            ]
        }

        # Test array index
        result = self.resolver.resolve_internal("#/items/1", document)
        self.assertEqual(result["name"], "second")
        self.assertEqual(result["value"], 2)

        # Test nested array access
        document = {
            "matrix": [
                [
                    {"x": 0, "y": 0},
                    {"x": 1, "y": 0}
                ],
                [
                    {"x": 0, "y": 1},
                    {"x": 1, "y": 1}
                ]
            ]
        }

        result = self.resolver.resolve_internal("#/matrix/1/0", document)
        self.assertEqual(result["x"], 0)
        self.assertEqual(result["y"], 1)

    def test_resolve_internal_root_reference(self):
        """Test resolving root reference (# or #/)"""
        document = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "name": "Test Product"
            }
        }

        # Test root reference with #
        result = self.resolver.resolve_internal("#", document)
        self.assertEqual(result, document)

        # Test root reference with #/
        result = self.resolver.resolve_internal("#/", document)
        self.assertEqual(result, document)

    def test_resolve_internal_nested_with_arrays(self):
        """Test resolving nested internal $ref that includes arrays"""
        document = {
            "product": {
                "dataQuality": {
                    "rules": [
                        {
                            "ruleID": "rule1",
                            "threshold": 0.95
                        },
                        {
                            "ruleID": "rule2",
                            "threshold": 0.90
                        }
                    ]
                }
            }
        }

        result = self.resolver.resolve_internal("#/product/dataQuality", document)
        self.assertIn("rules", result)
        self.assertEqual(len(result["rules"]), 2)
        self.assertEqual(result["rules"][0]["ruleID"], "rule1")

    def test_resolve_internal_array_index_out_of_bounds(self):
        """Test that array index out of bounds raises error"""
        document = {
            "items": [{"name": "first"}]
        }

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_internal("#/items/5", document)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        self.assertIn("out of bounds", str(cm.exception.message))

    def test_resolve_internal_invalid_array_index(self):
        """Test that invalid array index (non-numeric) raises error"""
        document = {
            "items": [{"name": "first"}]
        }

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_internal("#/items/invalid", document)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        self.assertIn("invalid array index", str(cm.exception.message).lower())

    def test_resolve_internal_type_mismatch_not_dict(self):
        """Test that resolving to non-dict value raises error (ODPS requires dict)"""
        document = {
            "value": "string_value",
            "number": 42,
            "array": [1, 2, 3]
        }

        # String value
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_internal("#/value", document)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        self.assertIn("must be an object", str(cm.exception.message))

        # Number value
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_internal("#/number", document)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)

        # Array value
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_internal("#/array", document)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)

    def test_resolve_internal_path_through_non_object(self):
        """Test that accessing path through non-object/array raises error"""
        document = {
            "value": "string_value"
        }

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_internal("#/value/nested", document)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        self.assertIn("not an object or array", str(cm.exception.message))

    def test_resolve_internal_complex_nested_structure(self):
        """Test resolving complex nested structure like ODPS documents"""
        document = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "dataQuality": {
                    "qualityScore": 95,
                    "rules": [
                        {"ruleID": "rule1", "threshold": 0.95}
                    ]
                }
            },
            "$defs": {
                "dataQualityReference": {
                    "$ref": "#/product/dataQuality"
                }
            }
        }

        # Test resolving the nested dataQuality reference
        result = self.resolver.resolve_internal("#/product/dataQuality", document)
        self.assertEqual(result["qualityScore"], 95)
        self.assertEqual(len(result["rules"]), 1)

        # Test resolving deeply nested path
        result = self.resolver.resolve_internal("#/product/details/en", document)
        self.assertEqual(result["productID"], "test-product")
        self.assertEqual(result["name"], "Test Product")


class RefResolverLocalRefTest(TestCase):
    """Test local $ref resolution"""

    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory structure
        self.temp_dir = Path(tempfile.mkdtemp())
        self.allowed_dir = self.temp_dir / "contracts" / "refs"
        self.allowed_dir.mkdir(parents=True)

        # Create test config with allowed directory
        config = ODPSRefsConfig()
        # Override allowed_base_dirs for test
        config._config_data = {
            'allowed_base_dirs': [str(self.allowed_dir)]
        }

        self.resolver = RefResolver(
            config=config,
            base_path=self.temp_dir,
        )

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolve_local_simple(self):
        """Test resolving simple local $ref"""
        # Create test file
        test_file = self.allowed_dir / "email.json"
        test_data = {"type": "string", "format": "email"}
        with open(test_file, 'w') as f:
            json.dump(test_data, f)

        result = self.resolver.resolve_local(f"./contracts/refs/email.json")
        self.assertEqual(result, test_data)

    def test_resolve_local_path_traversal_prevention(self):
        """Test that path traversal attempts are prevented"""
        # Try to access file outside allowed directory
        malicious_path = "../../../etc/passwd"

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(malicious_path)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)

    def test_resolve_local_file_not_found(self):
        """Test that missing local file raises error"""
        # Use relative path that doesn't exist
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local("./contracts/refs/nonexistent.json")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)

    def test_resolve_local_invalid_json(self):
        """Test that invalid JSON in local file raises error"""
        # Create file with invalid JSON
        test_file = self.allowed_dir / "invalid.json"
        with open(test_file, 'w') as f:
            f.write("not valid json {")

        # Use relative path from base_path to allowed_dir
        relative_path = test_file.relative_to(self.temp_dir)
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(f"./{relative_path}")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)

    def test_resolve_local_size_limit(self):
        """Test that local file size limit is enforced"""
        # Create large file
        test_file = self.allowed_dir / "large.json"
        large_data = {"data": "x" * (DEFAULT_MAX_REF_SIZE + 1)}
        with open(test_file, 'w') as f:
            json.dump(large_data, f)

        resolver = RefResolver(
            max_ref_size=1000,  # Small limit
            config=self.resolver.config,
            base_path=self.temp_dir,
        )

        # Use relative path from base_path to allowed_dir
        relative_path = test_file.relative_to(self.temp_dir)
        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve_local(f"./{relative_path}")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED)

    def test_resolve_local_relative_path_ref(self):
        """Test resolving local $ref with relative path (without ./ prefix)"""
        # Create test file
        test_file = self.allowed_dir / "schema.json"
        test_data = {"type": "object", "properties": {"name": {"type": "string"}}}
        with open(test_file, 'w') as f:
            json.dump(test_data, f)

        # Test with relative path without ./ prefix
        relative_path = test_file.relative_to(self.temp_dir)
        result = self.resolver.resolve_local(str(relative_path))
        self.assertEqual(result, test_data)

    def test_resolve_local_path_traversal_multiple_levels(self):
        """Test that path traversal with multiple levels (../../../etc/passwd) is prevented"""
        malicious_path = "../../../etc/passwd"

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(malicious_path)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)
        self.assertIn("not in allowed directories", cm.exception.message)

    def test_resolve_local_directory_traversal(self):
        """Test that directory traversal (../../) is prevented"""
        # Create a file outside allowed directory
        outside_dir = self.temp_dir / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "secret.json"
        with open(outside_file, 'w') as f:
            json.dump({"secret": "data"}, f)

        # Try to access it via directory traversal
        malicious_path = "../../outside/secret.json"

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(malicious_path)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)

    def test_resolve_local_absolute_path_rejection(self):
        """Test that absolute paths (/etc/passwd) are rejected"""
        # Try with absolute path
        absolute_path = "/etc/passwd"

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(absolute_path)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)
        self.assertIn("absolute path", cm.exception.message.lower())

    def test_resolve_local_symlink_attack_prevention(self):
        """Test that symlink attacks are prevented"""
        import os

        # Create a file outside allowed directory
        outside_dir = self.temp_dir / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "secret.json"
        with open(outside_file, 'w') as f:
            json.dump({"secret": "data"}, f)

        # Create a symlink inside allowed directory pointing outside
        symlink_file = self.allowed_dir / "link.json"
        try:
            os.symlink(str(outside_file), str(symlink_file))
        except OSError:
            # Symlinks not supported on this platform, skip test
            self.skipTest("Symlinks not supported on this platform")

        # Try to resolve the symlink - should fail because target is outside allowed dir
        relative_path = symlink_file.relative_to(self.temp_dir)
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(f"./{relative_path}")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)
        # The error should mention symlink or the target being outside allowed directories
        error_msg_lower = cm.exception.message.lower()
        self.assertTrue(
            "symlink" in error_msg_lower or "outside allowed directories" in error_msg_lower,
            f"Error message should mention symlink or outside allowed directories, got: {cm.exception.message}"
        )

    def test_resolve_local_symlink_within_allowed_dir(self):
        """Test that symlinks within allowed directory are allowed"""
        import os

        # Create a file within allowed directory
        target_file = self.allowed_dir / "target.json"
        test_data = {"type": "object"}
        with open(target_file, 'w') as f:
            json.dump(test_data, f)

        # Create a symlink pointing to the target file
        symlink_file = self.allowed_dir / "link.json"
        try:
            os.symlink(str(target_file), str(symlink_file))
        except OSError:
            # Symlinks not supported on this platform, skip test
            self.skipTest("Symlinks not supported on this platform")

        # Should succeed because both symlink and target are in allowed directory
        relative_path = symlink_file.relative_to(self.temp_dir)
        result = self.resolver.resolve_local(f"./{relative_path}")
        self.assertEqual(result, test_data)

    def test_resolve_local_file_type_validation_json(self):
        """Test that .json files are accepted"""
        test_file = self.allowed_dir / "test.json"
        test_data = {"type": "string"}
        with open(test_file, 'w') as f:
            json.dump(test_data, f)

        relative_path = test_file.relative_to(self.temp_dir)
        result = self.resolver.resolve_local(f"./{relative_path}")
        self.assertEqual(result, test_data)

    def test_resolve_local_file_type_validation_yaml(self):
        """Test that .yaml files are accepted"""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        test_file = self.allowed_dir / "test.yaml"
        test_data = {"type": "string", "format": "email"}
        with open(test_file, 'w') as f:
            yaml.dump(test_data, f)

        relative_path = test_file.relative_to(self.temp_dir)
        result = self.resolver.resolve_local(f"./{relative_path}")
        self.assertEqual(result, test_data)

    def test_resolve_local_file_type_validation_yml(self):
        """Test that .yml files are accepted"""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        test_file = self.allowed_dir / "test.yml"
        test_data = {"type": "object", "properties": {}}
        with open(test_file, 'w') as f:
            yaml.dump(test_data, f)

        relative_path = test_file.relative_to(self.temp_dir)
        result = self.resolver.resolve_local(f"./{relative_path}")
        self.assertEqual(result, test_data)

    def test_resolve_local_file_type_validation_rejects_invalid_extensions(self):
        """Test that files with invalid extensions are rejected"""
        # Create file with invalid extension
        test_file = self.allowed_dir / "test.txt"
        with open(test_file, 'w') as f:
            f.write('{"type": "string"}')

        relative_path = test_file.relative_to(self.temp_dir)
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(f"./{relative_path}")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)
        self.assertIn("invalid file extension", cm.exception.message.lower())

    def test_resolve_local_file_type_validation_rejects_no_extension(self):
        """Test that files without extensions are rejected"""
        # Create file without extension
        test_file = self.allowed_dir / "test"
        with open(test_file, 'w') as f:
            f.write('{"type": "string"}')

        relative_path = test_file.relative_to(self.temp_dir)
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(f"./{relative_path}")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)

    def test_resolve_local_invalid_yaml(self):
        """Test that invalid YAML in local file raises error"""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        # Create file with invalid YAML
        test_file = self.allowed_dir / "invalid.yaml"
        with open(test_file, 'w') as f:
            f.write("not valid yaml: [unclosed")

        relative_path = test_file.relative_to(self.temp_dir)
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(f"./{relative_path}")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        self.assertIn("not valid yaml", cm.exception.message.lower())

    def test_resolve_local_yaml_not_dict(self):
        """Test that YAML files that don't contain a dict are rejected"""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        # Create YAML file with list (not dict)
        test_file = self.allowed_dir / "list.yaml"
        with open(test_file, 'w') as f:
            yaml.dump(["item1", "item2"], f)

        relative_path = test_file.relative_to(self.temp_dir)
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(f"./{relative_path}")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        self.assertIn("must contain a json/yaml object", cm.exception.message.lower())

    def test_resolve_local_path_normalization(self):
        """Test that path normalization eliminates .. and . components"""
        # Create nested directory structure
        nested_dir = self.allowed_dir / "nested" / "deep"
        nested_dir.mkdir(parents=True)
        test_file = nested_dir / "data.json"
        test_data = {"nested": "data"}
        with open(test_file, 'w') as f:
            json.dump(test_data, f)

        # Use path with .. and . components that should normalize correctly
        # From base_path (temp_dir), use relative path that normalizes to the nested file
        relative_path = test_file.relative_to(self.temp_dir)
        # Create a path with .. that should normalize to the same file
        # e.g., if file is at contracts/refs/nested/deep/data.json
        # and we're at temp_dir, we can use contracts/refs/./nested/./deep/data.json
        normalized_path = str(relative_path).replace("nested", "./nested").replace("deep", "./deep")
        result = self.resolver.resolve_local(normalized_path)
        self.assertEqual(result, test_data)

    def test_resolve_local_directory_not_file(self):
        """Test that directories are rejected (must be a file)"""
        # Try to reference a directory instead of a file
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local("./contracts/refs")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        self.assertIn("not a file", cm.exception.message.lower())

    def test_resolve_local_security_path_traversal_attacks(self):
        """Security test: Test that various path traversal attack patterns are prevented"""
        # Test multiple path traversal attack vectors
        attack_vectors = [
            "../../../etc/passwd",
            "../../etc/passwd",
            "../etc/passwd",
            "....//....//etc/passwd",  # Double dot encoding
            "..%2F..%2Fetc%2Fpasswd",  # URL encoding (should be handled as literal)
            "/etc/passwd",  # Absolute path
            "C:\\Windows\\System32\\config\\sam",  # Windows absolute path
        ]

        for attack_path in attack_vectors:
            with self.subTest(attack_path=attack_path):
                with self.assertRaises(ODPSRefResolutionError) as cm:
                    self.resolver.resolve_local(attack_path)
                # Should be either security violation or invalid ref
                self.assertIn(
                    cm.exception.error_code,
                    [
                        ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                        ODPSRefResolutionError.ERROR_CODE_INVALID_REF
                    ],
                    f"Attack path '{attack_path}' should be rejected"
                )


class RefResolverExternalRefTest(TestCase):
    """Test external $ref resolution"""

    def setUp(self):
        """Set up test fixtures"""
        # Create config with URL allowlist
        config = ODPSRefsConfig()
        config._config_data = {
            'url_allowlist': ['https://example.com'],
            'url_denylist': []
        }

        self.resolver = RefResolver(
            config=config,
            tenant_id="test-tenant",
            user_id="test-user",
        )

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    @patch('hub.apps.contracts.ref_resolver.httpx.Client')
    def test_resolve_external_success(self, mock_client_class, mock_rate_limit):
        """Test successful external $ref resolution"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)  # (is_allowed, error)

        # Create resolver with caching disabled to avoid cache interference
        resolver = RefResolver(
            config=self.resolver.config,
            tenant_id=self.resolver.tenant_id,
            user_id=self.resolver.user_id,
            enable_caching=False,  # Disable caching for test
        )

        # Mock HTTP response
        mock_response = Mock()
        mock_response.content = b'{"type": "string", "format": "email"}'
        mock_response.json.return_value = {"type": "string", "format": "email"}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = resolver.resolve_external("https://example.com/schema.json")
        self.assertEqual(result, {"type": "string", "format": "email"})

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_resolve_external_rate_limit_exceeded(self, mock_rate_limit):
        """Test that rate limit exceeded raises error"""
        # Mock rate limit check to return error
        mock_rate_limit.return_value = (
            False,  # is_allowed
            ODPSRefResolutionError(
                message="Rate limit exceeded",
                error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
            )
        )

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external("https://example.com/schema.json")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_resolve_external_url_not_allowed(self, mock_rate_limit):
        """Test that URL not in allowlist raises error"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)  # (is_allowed, error)

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external("https://malicious.com/schema.json")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    @patch('hub.apps.contracts.ref_resolver.httpx.Client')
    def test_resolve_external_timeout(self, mock_client_class, mock_rate_limit):
        """Test that external $ref timeout raises error"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)  # (is_allowed, error)

        # Create resolver with caching disabled
        resolver = RefResolver(
            config=self.resolver.config,
            tenant_id=self.resolver.tenant_id,
            user_id=self.resolver.user_id,
            enable_caching=False,  # Disable caching for test
        )

        # Mock HTTP timeout
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get.side_effect = httpx.TimeoutException("Request timed out")
        mock_client_class.return_value = mock_client

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve_external("https://example.com/schema.json")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED)

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    @patch('hub.apps.contracts.ref_resolver.httpx.Client')
    def test_resolve_external_size_limit(self, mock_client_class, mock_rate_limit):
        """Test that external $ref size limit is enforced"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)  # (is_allowed, error)

        # Create resolver with small size limit and caching disabled
        resolver = RefResolver(
            max_ref_size=1000,  # Small limit
            config=self.resolver.config,
            tenant_id=self.resolver.tenant_id,
            user_id=self.resolver.user_id,
            enable_caching=False,  # Disable caching for test
        )

        # Mock HTTP response with large content
        mock_response = Mock()
        large_content = b'x' * (1000 + 1)  # Exceeds limit
        mock_response.content = large_content
        mock_response.json.return_value = {"data": "x" * (1000 + 1)}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve_external("https://example.com/schema.json")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED)


class RefResolverCachingTest(TestCase):
    """Test Redis caching for external refs"""

    def setUp(self):
        """Set up test fixtures"""
        config = ODPSRefsConfig()
        config._config_data = {
            'url_allowlist': ['https://example.com'],
            'url_denylist': []
        }

        self.resolver = RefResolver(
            config=config,
            tenant_id="test-tenant",
            user_id="test-user",
            enable_caching=True,
        )

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_external_ref_caching(self, mock_rate_limit):
        """Test that external refs are cached in Redis"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)  # (is_allowed, error)

        # Create resolver with caching enabled
        resolver = RefResolver(
            config=self.resolver.config,
            tenant_id=self.resolver.tenant_id,
            user_id=self.resolver.user_id,
            enable_caching=True,
        )

        # Mock Redis client
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = None  # Cache miss initially
        mock_redis_client.setex = Mock()

        # Replace the resolver's Redis client with our mock
        resolver._redis_client = mock_redis_client

        # Mock HTTP response
        with patch('hub.apps.contracts.ref_resolver.httpx.Client') as mock_client_class:
            mock_response = Mock()
            test_data = {"type": "string", "format": "email"}
            mock_response.content = json.dumps(test_data).encode('utf-8')
            mock_response.json.return_value = test_data
            mock_response.raise_for_status = Mock()

            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            # First call - should fetch and cache
            result = resolver.resolve_external("https://example.com/schema.json")
            self.assertEqual(result, test_data)

            # Verify cache set was called (called twice: once with content hash, once with simple key)
            self.assertGreaterEqual(mock_redis_client.setex.call_count, 1)

        # Second call - should use cache
        # Reset mock to simulate cache hit
        cached_data = json.dumps(test_data).encode('utf-8')
        mock_redis_client.get.return_value = cached_data

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_external_ref_url_validation_scheme(self, mock_rate_limit):
        """Test that external $ref URL validation rejects invalid schemes"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)

        # Test invalid scheme (ftp)
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external("ftp://example.com/schema.json")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)
        self.assertIn("invalid scheme", str(cm.exception.message).lower())

        # Test invalid scheme (file)
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external("file:///etc/passwd")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_external_ref_url_validation_host(self, mock_rate_limit):
        """Test that external $ref URL validation requires valid host"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)

        # Test missing host
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external("https:///schema.json")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        self.assertIn("missing host", str(cm.exception.message).lower())

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_external_ref_url_validation_length(self, mock_rate_limit):
        """Test that external $ref URL validation enforces length limit (2048 chars)"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)

        # Test URL exceeding 2048 characters
        long_url = "https://example.com/" + "x" * 2050
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(long_url)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        self.assertIn("exceeds maximum", str(cm.exception.message).lower())

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_external_ref_url_validation_invalid_format(self, mock_rate_limit):
        """Test that external $ref URL validation rejects invalid URL format"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)

        # Test invalid URL format (missing scheme results in SECURITY_VIOLATION)
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external("not-a-valid-url")
        # Invalid scheme is treated as a security violation
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_external_ref_rate_limit_error_handling(self, mock_rate_limit):
        """Test that rate limit errors provide clear messages"""
        # Mock rate limit check to return error with retry_after
        mock_rate_limit.return_value = (
            False,  # is_allowed
            ODPSRefResolutionError(
                message="Rate limit exceeded: 10 requests per minute",
                error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                retry_after=60,
            )
        )

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external("https://example.com/schema.json")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertIn("Rate limit exceeded", str(cm.exception.message))
        self.assertEqual(cm.exception.retry_after, 60)

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    @patch('hub.apps.contracts.ref_resolver.httpx.Client')
    def test_external_ref_cache_key_format(self, mock_client_class, mock_rate_limit):
        """Test that cache key format uses url_hash and content_hash"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)

        # Create resolver with caching enabled
        resolver = RefResolver(
            config=self.resolver.config,
            tenant_id=self.resolver.tenant_id,
            user_id=self.resolver.user_id,
            enable_caching=True,
        )

        # Mock Redis client
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = None  # Cache miss
        mock_redis_client.setex = Mock()
        resolver._redis_client = mock_redis_client

        # Mock HTTP response
        test_data = {"type": "string", "format": "email"}
        test_url = "https://example.com/schema.json"
        mock_response = Mock()
        mock_response.content = json.dumps(test_data).encode('utf-8')
        mock_response.json.return_value = test_data
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Resolve external ref
        result = resolver.resolve_external(test_url)
        self.assertEqual(result, test_data)

        # Verify cache set was called with correct key format
        # Cache key should be in format: odps_ref:{url_hash}:{content_hash}
        setex_calls = mock_redis_client.setex.call_args_list
        self.assertGreater(len(setex_calls), 0)

        # Check that cache keys follow the required format
        cache_keys = [call[0][0] for call in setex_calls]

        # Calculate expected URL hash
        import hashlib
        url_hash = hashlib.sha256(test_url.encode('utf-8')).hexdigest()[:16]

        # Calculate expected content hash
        content_hash = hashlib.sha256(mock_response.content).hexdigest()[:16]

        # Expected cache key format: odps_ref:{url_hash}:{content_hash}
        expected_data_key = f"odps_ref:{url_hash}:{content_hash}"
        expected_url_key = f"odps_ref:{url_hash}"

        # Verify both keys are present
        self.assertIn(expected_data_key, cache_keys,
                     f"Expected cache key {expected_data_key} not found in {cache_keys}")
        self.assertIn(expected_url_key, cache_keys,
                     f"Expected URL mapping key {expected_url_key} not found in {cache_keys}")

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_external_ref_cache_ttl(self, mock_rate_limit):
        """Test that cache TTL is set correctly (1 hour = 3600 seconds)"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)

        # Create resolver with caching enabled and custom TTL
        resolver = RefResolver(
            config=self.resolver.config,
            tenant_id=self.resolver.tenant_id,
            user_id=self.resolver.user_id,
            enable_caching=True,
            cache_ttl=3600,  # 1 hour
        )

        # Mock Redis client
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = None  # Cache miss
        mock_redis_client.setex = Mock()
        resolver._redis_client = mock_redis_client

        # Mock HTTP response
        with patch('hub.apps.contracts.ref_resolver.httpx.Client') as mock_client_class:
            mock_response = Mock()
            test_data = {"type": "string", "format": "email"}
            mock_response.content = json.dumps(test_data).encode('utf-8')
            mock_response.json.return_value = test_data
            mock_response.raise_for_status = Mock()

            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Resolve external ref
            resolver.resolve_external("https://example.com/schema.json")

            # Verify cache TTL is set correctly
            setex_calls = mock_redis_client.setex.call_args_list
            self.assertGreater(len(setex_calls), 0)

            # Check that TTL is 3600 seconds (1 hour)
            ttls = [call[0][1] for call in setex_calls]
            self.assertTrue(any(ttl == 3600 for ttl in ttls))

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    @patch('hub.apps.contracts.ref_resolver.httpx.Client')
    def test_external_ref_non_dict_response(self, mock_client_class, mock_rate_limit):
        """Test that external $ref rejects non-dict responses (ODPS requirement)"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)

        # Create resolver with caching disabled
        resolver = RefResolver(
            config=self.resolver.config,
            tenant_id=self.resolver.tenant_id,
            user_id=self.resolver.user_id,
            enable_caching=False,
        )

        # Mock HTTP response with non-dict JSON (array)
        mock_response = Mock()
        mock_response.content = b'[1, 2, 3]'
        mock_response.json.return_value = [1, 2, 3]
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve_external("https://example.com/schema.json")
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        # Check that error message mentions it's not a JSON object
        error_msg_lower = str(cm.exception.message).lower()
        self.assertTrue(
            "not a json object" in error_msg_lower or "not a json" in error_msg_lower,
            f"Expected error message about 'not a json object', got: {cm.exception.message}"
        )

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    @patch('hub.apps.contracts.ref_resolver.httpx.Client')
    def test_external_ref_cache_invalidation(self, mock_client_class, mock_rate_limit):
        """Test that cache invalidation works when content changes"""
        # Mock rate limit check (allowed)
        mock_rate_limit.return_value = (True, None)

        # Create resolver with caching enabled
        resolver = RefResolver(
            config=self.resolver.config,
            tenant_id=self.resolver.tenant_id,
            user_id=self.resolver.user_id,
            enable_caching=True,
        )

        # Mock Redis client
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = None  # Cache miss
        mock_redis_client.setex = Mock()
        resolver._redis_client = mock_redis_client

        # Mock HTTP response with first content
        test_data_1 = {"type": "string", "format": "email"}
        test_url = "https://example.com/schema.json"

        mock_response_1 = Mock()
        mock_response_1.content = json.dumps(test_data_1).encode('utf-8')
        mock_response_1.json.return_value = test_data_1
        mock_response_1.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get.return_value = mock_response_1
        mock_client_class.return_value = mock_client

        # First resolution
        result_1 = resolver.resolve_external(test_url)
        self.assertEqual(result_1, test_data_1)

        # Verify cache was set
        setex_calls_1 = mock_redis_client.setex.call_args_list
        self.assertGreater(len(setex_calls_1), 0)

        # Now simulate content change (different content hash)
        test_data_2 = {"type": "string", "format": "uri"}
        mock_response_2 = Mock()
        mock_response_2.content = json.dumps(test_data_2).encode('utf-8')
        mock_response_2.json.return_value = test_data_2
        mock_response_2.raise_for_status = Mock()
        mock_client.get.return_value = mock_response_2

        # Reset mock to track second call
        mock_redis_client.setex.reset_mock()

        # Second resolution (should fetch again due to content change)
        result_2 = resolver.resolve_external(test_url)
        self.assertEqual(result_2, test_data_2)

        # Verify cache was set again with new content hash
        setex_calls_2 = mock_redis_client.setex.call_args_list
        self.assertGreater(len(setex_calls_2), 0)

        # Verify different cache keys were used (different content hashes)
        cache_keys_1 = [call[0][0] for call in setex_calls_1]
        cache_keys_2 = [call[0][0] for call in setex_calls_2]

        # Extract content hash from cache keys (format: odps_ref:{url_hash}:{content_hash})
        import hashlib
        content_hash_1 = hashlib.sha256(mock_response_1.content).hexdigest()[:16]
        content_hash_2 = hashlib.sha256(mock_response_2.content).hexdigest()[:16]

        # Content hashes should be different
        self.assertNotEqual(content_hash_1, content_hash_2, "Content hashes should differ for different content")

        # Cache keys should contain different content hashes
        self.assertTrue(any(content_hash_1 in key for key in cache_keys_1))
        self.assertTrue(any(content_hash_2 in key for key in cache_keys_2))

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_external_ref_rate_limit_per_tenant(self, mock_rate_limit):
        """Test that rate limiting works at per-tenant level"""
        # Mock rate limit check to return tenant-level error
        mock_rate_limit.return_value = (
            False,
            ODPSRefResolutionError(
                message="Rate limit exceeded for tenant: 10 requests per minute",
                error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                retry_after=60,
            )
        )

        resolver = RefResolver(
            config=self.resolver.config,
            tenant_id="test-tenant",
            user_id="test-user",
        )

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve_external("https://example.com/schema.json")

        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertIn("tenant", str(cm.exception.message).lower())

        # Verify check_rate_limit was called with tenant_id
        mock_rate_limit.assert_called_once()
        call_args = mock_rate_limit.call_args
        self.assertEqual(call_args[1]['tenant_id'], "test-tenant")

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_external_ref_rate_limit_per_user(self, mock_rate_limit):
        """Test that rate limiting works at per-user level"""
        # Mock rate limit check to return user-level error
        mock_rate_limit.return_value = (
            False,
            ODPSRefResolutionError(
                message="Rate limit exceeded for user: 5 requests per minute",
                error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                retry_after=60,
            )
        )

        resolver = RefResolver(
            config=self.resolver.config,
            tenant_id="test-tenant",
            user_id="test-user",
        )

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve_external("https://example.com/schema.json")

        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertIn("user", str(cm.exception.message).lower())

        # Verify check_rate_limit was called with user_id
        mock_rate_limit.assert_called_once()
        call_args = mock_rate_limit.call_args
        self.assertEqual(call_args[1]['user_id'], "test-user")

    @patch('hub.apps.contracts.ref_resolver.check_rate_limit')
    def test_external_ref_rate_limit_global(self, mock_rate_limit):
        """Test that rate limiting works at global level"""
        # Mock rate limit check to return global-level error
        mock_rate_limit.return_value = (
            False,
            ODPSRefResolutionError(
                message="Global rate limit exceeded: 100 requests per minute",
                error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                retry_after=60,
            )
        )

        resolver = RefResolver(
            config=self.resolver.config,
            tenant_id="test-tenant",
            user_id="test-user",
        )

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve_external("https://example.com/schema.json")

        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertIn("global", str(cm.exception.message).lower())


class RefResolverSecurityControlsTest(TestCase):
    """Test security controls"""

    def setUp(self):
        """Set up test fixtures"""
        self.resolver = RefResolver(
            tenant_id="test-tenant",
            user_id="test-user",
        )

    def test_timeout_check(self):
        """Test that total timeout is checked"""
        resolver = RefResolver(timeout_total=1)  # 1 second timeout
        resolver._start_time = time.time() - 2  # 2 seconds ago

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver._check_timeout()
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED)

    def test_size_limit_per_ref(self):
        """Test that per-ref size limit is enforced"""
        resolver = RefResolver(max_ref_size=1000)

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver._check_size_limit(2000)  # Exceeds limit
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED)

    def test_size_limit_total(self):
        """Test that total size limit is enforced"""
        resolver = RefResolver(max_total_size=1000)
        resolver._total_size = 800  # Already used 800 bytes

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver._check_size_limit(300)  # Would exceed total limit
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED)

    def test_resolve_auto_detect_mode(self):
        """Test that resolve() auto-detects mode correctly"""
        # Test internal ref
        document = {"definitions": {"Email": {"type": "string"}}}
        result = self.resolver.resolve("#/definitions/Email", document)
        self.assertEqual(result, {"type": "string"})

        # Test that document is required for internal refs
        with self.assertRaises(ValueError):
            self.resolver.resolve("#/definitions/Email", None)


class RefResolverOrchestrationTest(SimpleTestCase):
    """Test $ref resolution orchestration (resolve_all_refs)"""

    def setUp(self):
        """Set up test fixtures"""
        self.resolver = RefResolver(
            tenant_id="test-tenant",
            user_id="test-user",
        )

    def test_resolve_all_refs_simple_internal(self):
        """Test resolving a simple internal $ref"""
        document = {
            "product": {
                "dataQuality": {"$ref": "#/definitions/quality"}
            },
            "definitions": {
                "quality": {"score": 95, "completeness": 0.98}
            }
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # Original should be preserved
        self.assertIn("$ref", original["product"]["dataQuality"])
        self.assertEqual(original["product"]["dataQuality"]["$ref"], "#/definitions/quality")

        # Resolved should have $ref replaced
        self.assertNotIn("$ref", resolved["product"]["dataQuality"])
        self.assertEqual(resolved["product"]["dataQuality"]["score"], 95)
        self.assertEqual(resolved["product"]["dataQuality"]["completeness"], 0.98)

    def test_resolve_all_refs_nested_internal(self):
        """Test resolving nested internal $refs"""
        document = {
            "product": {
                "dataQuality": {"$ref": "#/definitions/quality"}
            },
            "definitions": {
                "quality": {
                    "rules": {"$ref": "#/definitions/rules"}
                },
                "rules": {
                    "items": [
                        {"ruleID": "rule1", "threshold": 0.95}
                    ]
                }
            }
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # Both refs should be resolved
        self.assertNotIn("$ref", resolved["product"]["dataQuality"])
        self.assertNotIn("$ref", resolved["definitions"]["quality"])
        self.assertEqual(resolved["product"]["dataQuality"]["rules"]["items"][0]["ruleID"], "rule1")

    def test_resolve_all_refs_in_array(self):
        """Test resolving $refs in arrays"""
        document = {
            "product": {
                "rules": [
                    {"$ref": "#/definitions/rule1"},
                    {"$ref": "#/definitions/rule2"}
                ]
            },
            "definitions": {
                "rule1": {"ruleID": "rule1", "threshold": 0.95},
                "rule2": {"ruleID": "rule2", "threshold": 0.90}
            }
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # All refs in array should be resolved
        self.assertEqual(len(resolved["product"]["rules"]), 2)
        self.assertEqual(resolved["product"]["rules"][0]["ruleID"], "rule1")
        self.assertEqual(resolved["product"]["rules"][1]["ruleID"], "rule2")
        self.assertNotIn("$ref", resolved["product"]["rules"][0])
        self.assertNotIn("$ref", resolved["product"]["rules"][1])

    def test_resolve_all_refs_circular_detection(self):
        """Test that circular references are detected and raise error"""
        document = {
            "product": {
                "dataQuality": {"$ref": "#/definitions/quality"}
            },
            "definitions": {
                "quality": {"$ref": "#/product/dataQuality"}  # Circular reference
            }
        }

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_all_refs(document)

        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_CIRCULAR_REF)
        self.assertIn("Circular reference detected", str(cm.exception.message))

    def test_resolve_all_refs_circular_self_reference(self):
        """Test that self-referencing circular refs are detected"""
        document = {
            "product": {
                "dataQuality": {"$ref": "#/product/dataQuality"}  # Self-reference
            }
        }

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_all_refs(document)

        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_CIRCULAR_REF)
        self.assertIn("Circular reference detected", str(cm.exception.message))

    def test_resolve_all_refs_circular_chain(self):
        """Test that circular reference chains are detected"""
        document = {
            "a": {"$ref": "#/b"},
            "b": {"$ref": "#/c"},
            "c": {"$ref": "#/a"}  # Forms a cycle: a -> b -> c -> a
        }

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_all_refs(document)

        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_CIRCULAR_REF)
        self.assertIn("Circular reference detected", str(cm.exception.message))

    def test_resolve_all_refs_preserves_original(self):
        """Test that original document is preserved (deep copy)"""
        document = {
            "product": {
                "dataQuality": {"$ref": "#/definitions/quality"}
            },
            "definitions": {
                "quality": {"score": 95}
            }
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # Original should be unchanged
        self.assertIn("$ref", original["product"]["dataQuality"])
        self.assertEqual(original["product"]["dataQuality"]["$ref"], "#/definitions/quality")

        # Resolved should be different
        self.assertNotIn("$ref", resolved["product"]["dataQuality"])
        self.assertEqual(resolved["product"]["dataQuality"]["score"], 95)

        # Modifying resolved should not affect original
        resolved["product"]["dataQuality"]["score"] = 100
        self.assertEqual(original["product"]["dataQuality"]["$ref"], "#/definitions/quality")
        self.assertEqual(resolved["product"]["dataQuality"]["score"], 100)

    def test_resolve_all_refs_no_refs(self):
        """Test resolving a document with no $refs"""
        document = {
            "product": {
                "dataQuality": {"score": 95, "completeness": 0.98}
            }
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # Both should be identical (no refs to resolve)
        self.assertEqual(original, resolved)
        self.assertEqual(resolved["product"]["dataQuality"]["score"], 95)

    def test_resolve_all_refs_invalid_ref_type(self):
        """Test that non-string $ref values raise error"""
        document = {
            "product": {
                "dataQuality": {"$ref": 123}  # Invalid: $ref must be string
            }
        }

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_all_refs(document)

        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        self.assertIn("$ref value must be a string", str(cm.exception.message))

    def test_resolve_all_refs_mixed_refs(self):
        """Test resolving document with multiple types of refs (internal only in this test)"""
        document = {
            "product": {
                "dataQuality": {"$ref": "#/definitions/quality"},
                "marketplace": {
                    "pricing": {"$ref": "#/definitions/pricing"}
                }
            },
            "definitions": {
                "quality": {"score": 95},
                "pricing": {"planID": "basic", "price": 9.99}
            }
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # All refs should be resolved
        self.assertNotIn("$ref", resolved["product"]["dataQuality"])
        self.assertNotIn("$ref", resolved["product"]["marketplace"]["pricing"])
        self.assertEqual(resolved["product"]["dataQuality"]["score"], 95)
        self.assertEqual(resolved["product"]["marketplace"]["pricing"]["planID"], "basic")

    def test_resolve_all_refs_nested_resolved_value(self):
        """Test that resolved values with their own $refs are also resolved"""
        document = {
            "product": {
                "dataQuality": {"$ref": "#/definitions/quality"}
            },
            "definitions": {
                "quality": {
                    "rules": {"$ref": "#/definitions/rules"}
                },
                "rules": {
                    "items": [
                        {"ruleID": "rule1", "threshold": 0.95}
                    ]
                }
            }
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # The resolved value should also have its $ref resolved
        self.assertNotIn("$ref", resolved["product"]["dataQuality"])
        self.assertNotIn("$ref", resolved["product"]["dataQuality"]["rules"])
        self.assertEqual(resolved["product"]["dataQuality"]["rules"]["items"][0]["ruleID"], "rule1")

    def test_resolve_all_refs_invalid_document_type(self):
        """Test that non-dict documents raise ValueError"""
        with self.assertRaises(ValueError) as cm:
            self.resolver.resolve_all_refs([])  # List, not dict

        self.assertIn("Document must be a dict", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            self.resolver.resolve_all_refs("not a dict")  # String, not dict

        self.assertIn("Document must be a dict", str(cm.exception))

    def test_resolve_all_refs_preserve_original_false(self):
        """Test that preserve_original=False still works (but not recommended)"""
        document = {
            "product": {
                "dataQuality": {"$ref": "#/definitions/quality"}
            },
            "definitions": {
                "quality": {"score": 95}
            }
        }

        original, resolved = self.resolver.resolve_all_refs(document, preserve_original=False)

        # When preserve_original=False, original and document are the same object
        # But resolved should still be a copy
        self.assertNotIn("$ref", resolved["product"]["dataQuality"])
        self.assertEqual(resolved["product"]["dataQuality"]["score"], 95)


class RefResolverOrchestrationLocalRefTest(SimpleTestCase):
    """Test $ref resolution orchestration with local refs (using real files)"""

    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory structure
        self.temp_dir = Path(tempfile.mkdtemp())
        self.allowed_dir = self.temp_dir / "contracts" / "refs"
        self.allowed_dir.mkdir(parents=True)

        # Create test config with allowed directory
        config = ODPSRefsConfig()
        # Override allowed_base_dirs for test
        config._config_data = {
            'allowed_base_dirs': [str(self.allowed_dir)]
        }

        self.resolver = RefResolver(
            config=config,
            base_path=self.temp_dir,
            tenant_id="test-tenant",
            user_id="test-user",
        )

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolve_all_refs_with_local_ref(self):
        """Test resolving document with local $ref"""
        # Create test file
        quality_file = self.allowed_dir / "quality-rules.json"
        quality_data = {"score": 95, "completeness": 0.98, "accuracy": 0.97}
        with open(quality_file, 'w') as f:
            json.dump(quality_data, f)

        document = {
            "product": {
                "dataQuality": {"$ref": "./contracts/refs/quality-rules.json"}
            }
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # Original should be preserved
        self.assertIn("$ref", original["product"]["dataQuality"])

        # Resolved should have $ref replaced with file content
        self.assertNotIn("$ref", resolved["product"]["dataQuality"])
        self.assertEqual(resolved["product"]["dataQuality"]["score"], 95)
        self.assertEqual(resolved["product"]["dataQuality"]["completeness"], 0.98)

    def test_resolve_all_refs_with_mixed_internal_and_local(self):
        """Test resolving document with both internal and local refs"""
        # Create test file
        quality_file = self.allowed_dir / "quality-rules.json"
        quality_data = {"score": 95, "rules": {"$ref": "#/definitions/rules"}}
        with open(quality_file, 'w') as f:
            json.dump(quality_data, f)

        document = {
            "product": {
                "dataQuality": {"$ref": "./contracts/refs/quality-rules.json"}
            },
            "definitions": {
                "rules": {"items": [{"ruleID": "rule1", "threshold": 0.95}]}
            }
        }

        original, resolved = self.resolver.resolve_all_refs(document)

        # Local ref should be resolved
        self.assertNotIn("$ref", resolved["product"]["dataQuality"])
        self.assertEqual(resolved["product"]["dataQuality"]["score"], 95)

        # Internal ref within the resolved local file should also be resolved
        self.assertNotIn("$ref", resolved["product"]["dataQuality"]["rules"])
        self.assertEqual(resolved["product"]["dataQuality"]["rules"]["items"][0]["ruleID"], "rule1")


class RefResolverExternalRefHandlingTest(SimpleTestCase):
    """Test external $ref handling modes (disable, remove, replace)"""

    def setUp(self):
        """Set up test fixtures"""
        self.resolver = RefResolver(
            tenant_id="test-tenant",
            user_id="test-user",
        )

    def test_resolve_all_refs_disable_external_refs(self):
        """Test that disabling external refs raises error when external ref is found"""
        document = {
            "product": {
                "schema": {"$ref": "https://example.com/schema.json"}
            }
        }

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_all_refs(
                document,
                external_ref_handling=ExternalRefHandling.DISABLE
            )

        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION)
        self.assertIn("External $ref is disabled", str(cm.exception.message))

    def test_resolve_all_refs_remove_external_refs(self):
        """Test that removing external refs deletes the $ref key"""
        document = {
            "product": {
                "schema": {"$ref": "https://example.com/schema.json"},
                "name": "Test Product"
            }
        }

        original, resolved = self.resolver.resolve_all_refs(
            document,
            external_ref_handling=ExternalRefHandling.REMOVE
        )

        # Original should be preserved
        self.assertIn("$ref", original["product"]["schema"])

        # Resolved should have external ref removed (entire dict deleted)
        self.assertNotIn("schema", resolved["product"])
        self.assertEqual(resolved["product"]["name"], "Test Product")

    def test_resolve_all_refs_remove_external_refs_preserves_internal(self):
        """Test that removing external refs preserves internal refs"""
        document = {
            "product": {
                "schema": {"$ref": "https://example.com/schema.json"},
                "quality": {"$ref": "#/definitions/quality"}
            },
            "definitions": {
                "quality": {"score": 95}
            }
        }

        original, resolved = self.resolver.resolve_all_refs(
            document,
            external_ref_handling=ExternalRefHandling.REMOVE
        )

        # External ref should be removed
        self.assertNotIn("schema", resolved["product"])

        # Internal ref should be resolved (not removed)
        self.assertNotIn("$ref", resolved["product"]["quality"])
        self.assertEqual(resolved["product"]["quality"]["score"], 95)

    def test_resolve_all_refs_remove_external_refs_in_array(self):
        """Test that removing external refs works in arrays"""
        document = {
            "product": {
                "schemas": [
                    {"$ref": "https://example.com/schema1.json"},
                    {"$ref": "https://example.com/schema2.json"},
                    {"name": "local"}
                ]
            }
        }

        original, resolved = self.resolver.resolve_all_refs(
            document,
            external_ref_handling=ExternalRefHandling.REMOVE
        )

        # External refs should be completely removed from the array
        # Only the local item should remain
        self.assertEqual(len(resolved["product"]["schemas"]), 1)
        self.assertEqual(resolved["product"]["schemas"][0], {"name": "local"})

    def test_resolve_all_refs_replace_external_refs(self):
        """Test that replacing external refs resolves them (default behavior)"""
        # Note: This test would require mocking external HTTP calls
        # For now, we test that the mode doesn't raise errors for external refs
        # In a real scenario with mocked HTTP, external refs would be resolved
        document = {
            "product": {
                "schema": {"$ref": "https://example.com/schema.json"},
                "name": "Test Product"
            }
        }

        # With REPLACE mode, it will try to resolve (will fail without mock, but that's expected)
        # We test that DISABLE and REMOVE work, and REPLACE is the default
        with self.assertRaises(ODPSRefResolutionError):
            # This will fail because we can't actually fetch the URL, but it shows REPLACE mode tries to resolve
            self.resolver.resolve_all_refs(
                document,
                external_ref_handling=ExternalRefHandling.REPLACE
            )

    def test_resolve_all_refs_resolve_mode_default(self):
        """Test that RESOLVE mode is the default behavior"""
        document = {
            "product": {
                "quality": {"$ref": "#/definitions/quality"}
            },
            "definitions": {
                "quality": {"score": 95}
            }
        }

        # Default behavior should resolve internal refs
        original, resolved = self.resolver.resolve_all_refs(document)

        self.assertNotIn("$ref", resolved["product"]["quality"])
        self.assertEqual(resolved["product"]["quality"]["score"], 95)

    def test_remove_external_refs_method(self):
        """Test the remove_external_refs convenience method"""
        document = {
            "product": {
                "schema": {"$ref": "https://example.com/schema.json"},
                "quality": {"$ref": "#/definitions/quality"}
            },
            "definitions": {
                "quality": {"score": 95}
            }
        }

        result = self.resolver.remove_external_refs(document)

        # External ref should be removed
        self.assertNotIn("schema", result["product"])

        # Internal ref should still be present (not resolved by remove_external_refs)
        # Actually, remove_external_refs uses REMOVE mode which only removes external refs
        # Internal refs are still resolved normally
        self.assertNotIn("$ref", result["product"]["quality"])
        self.assertEqual(result["product"]["quality"]["score"], 95)

