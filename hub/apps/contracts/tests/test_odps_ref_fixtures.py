"""
Unit tests for ODPS test fixtures with $ref references.

Tests verify that all ODPS $ref fixture files are:
1. Valid JSON
2. Valid ODPS (pass schema validation)
3. Contain $ref references as expected
"""

import json
from pathlib import Path

from django.test import TestCase

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

try:
    import jsonschema
    from jsonschema import Draft202012Validator, SchemaError, ValidationError, validate

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

    # Create mock classes for when jsonschema is not available
    # Use _Mock prefix to avoid shadowing real jsonschema class names
    class _MockDraft202012Validator:
        def check_schema(self, schema):
            pass

        def validate(self, instance):
            pass

    class _MockSchemaError(Exception):
        pass

    class _MockValidationError(Exception):
        pass

    Draft202012Validator = _MockDraft202012Validator
    SchemaError = _MockSchemaError
    ValidationError = _MockValidationError


from hub.apps.contracts.odps_schema import load_odps_schema


class ODPSRefFixturesTest(TestCase):
    """Test ODPS test fixtures with $ref references"""

    def setUp(self):
        """Set up test fixtures"""
        # Get the base directory for tests
        # Path(__file__) is in hub/apps/contracts/tests/
        # We need to go up to the project root
        self.base_dir = Path(__file__).parent.parent.parent.parent.parent
        self.fixtures_dir = self.base_dir / "tests" / "fixtures" / "odps"
        self.required_versions = ["v4.1", "v4.0", "v3.x", "v2.x", "v1.x"]

    def _load_json_file(self, file_path: Path) -> dict:
        """Load and parse a JSON file"""
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)

    def _load_yaml_file(self, file_path: Path) -> dict:
        """Load and parse a YAML file"""
        if not YAML_AVAILABLE:
            raise ImportError("yaml library not available")
        with open(file_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _find_refs_in_object(self, obj: any, path: str = "") -> list:
        """Recursively find all $ref references in an object"""
        refs = []
        if isinstance(obj, dict):
            if "$ref" in obj:
                refs.append((path, obj["$ref"]))
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                refs.extend(self._find_refs_in_object(value, new_path))
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                new_path = f"{path}[{idx}]"
                refs.extend(self._find_refs_in_object(item, new_path))
        return refs

    def test_internal_ref_files_exist(self):
        """Test that internal $ref sample files exist for all versions"""
        for version in self.required_versions:
            with self.subTest(version=version):
                refs_dir = self.fixtures_dir / version / "with_refs"
                internal_ref_file = (
                    refs_dir
                    / f"sample-internal-ref-{version.replace('v', 'v') if version.startswith('v') else version}.json"
                )

                # Handle version-specific naming
                if version == "v4.1":
                    internal_ref_file = refs_dir / "sample-internal-ref-v4.1.json"
                elif version == "v4.0":
                    internal_ref_file = refs_dir / "sample-internal-ref-v4.0.json"
                elif version == "v3.x":
                    internal_ref_file = refs_dir / "sample-internal-ref-v3.9.json"
                elif version == "v2.x":
                    internal_ref_file = refs_dir / "sample-internal-ref-v2.9.json"
                elif version == "v1.x":
                    internal_ref_file = refs_dir / "sample-internal-ref-v1.9.json"

                self.assertTrue(
                    internal_ref_file.exists(),
                    f"Internal $ref sample file should exist for version {version} at: {internal_ref_file}",
                )

    def test_local_ref_json_sample_files_exist(self):
        """Test that local $ref sample files exist for all versions"""
        for version in self.required_versions:
            with self.subTest(version=version):
                refs_dir = self.fixtures_dir / version / "with_refs"

                # Handle version-specific naming
                if version == "v4.1":
                    local_ref_file = refs_dir / "sample-local-ref-v4.1.json"
                elif version == "v4.0":
                    local_ref_file = refs_dir / "sample-local-ref-v4.0.json"
                elif version == "v3.x":
                    local_ref_file = refs_dir / "sample-local-ref-v3.9.json"
                elif version == "v2.x":
                    local_ref_file = refs_dir / "sample-local-ref-v2.9.json"
                elif version == "v1.x":
                    local_ref_file = refs_dir / "sample-local-ref-v1.9.json"

                self.assertTrue(
                    local_ref_file.exists(),
                    f"Local $ref sample file should exist for version {version} at: {local_ref_file}",
                )

    def test_external_ref_files_exist(self):
        """Test that external $ref sample files exist for all versions"""
        for version in self.required_versions:
            with self.subTest(version=version):
                refs_dir = self.fixtures_dir / version / "with_refs"

                # Handle version-specific naming
                if version == "v4.1":
                    external_ref_file = refs_dir / "sample-external-ref-v4.1.json"
                elif version == "v4.0":
                    external_ref_file = refs_dir / "sample-external-ref-v4.0.json"
                elif version == "v3.x":
                    external_ref_file = refs_dir / "sample-external-ref-v3.9.json"
                elif version == "v2.x":
                    external_ref_file = refs_dir / "sample-external-ref-v2.9.json"
                elif version == "v1.x":
                    external_ref_file = refs_dir / "sample-external-ref-v1.9.json"

                self.assertTrue(
                    external_ref_file.exists(),
                    f"External $ref sample file should exist for version {version} at: {external_ref_file}",
                )

    def test_internal_ref_files_are_valid_json(self):
        """Test that internal $ref sample files are valid JSON"""
        test_cases = [
            ("v4.1", "sample-internal-ref-v4.1.json"),
            ("v4.0", "sample-internal-ref-v4.0.json"),
            ("v3.x", "sample-internal-ref-v3.9.json"),
            ("v2.x", "sample-internal-ref-v2.9.json"),
            ("v1.x", "sample-internal-ref-v1.9.json"),
        ]

        for version, filename in test_cases:
            with self.subTest(version=version, filename=filename):
                refs_dir = self.fixtures_dir / version / "with_refs"
                file_path = refs_dir / filename

                try:
                    data = self._load_json_file(file_path)
                    self.assertIsInstance(
                        data, dict, f"File {filename} should contain a JSON object"
                    )
                except json.JSONDecodeError as e:
                    self.fail(f"File {filename} is not valid JSON: {e}")

    def test_internal_ref_files_contain_internal_refs(self):
        """Test that internal $ref files contain internal $ref references"""
        test_cases = [
            ("v4.1", "sample-internal-ref-v4.1.json"),
            ("v4.0", "sample-internal-ref-v4.0.json"),
            ("v3.x", "sample-internal-ref-v3.9.json"),
            ("v2.x", "sample-internal-ref-v2.9.json"),
            ("v1.x", "sample-internal-ref-v1.9.json"),
        ]

        for version, filename in test_cases:
            with self.subTest(version=version, filename=filename):
                refs_dir = self.fixtures_dir / version / "with_refs"
                file_path = refs_dir / filename
                data = self._load_json_file(file_path)

                # Find all $ref references
                refs = self._find_refs_in_object(data)

                # Check that at least one internal $ref exists (starts with #)
                internal_refs = [ref_value for _, ref_value in refs if ref_value.startswith("#")]
                self.assertGreater(
                    len(internal_refs),
                    0,
                    f"File {filename} should contain at least one internal $ref (starting with #)",
                )

    def test_local_ref_files_contain_local_refs(self):
        """Test that local $ref files contain local $ref references"""
        test_cases = [
            ("v4.1", "sample-local-ref-v4.1.json"),
            ("v4.0", "sample-local-ref-v4.0.json"),
            ("v3.x", "sample-local-ref-v3.9.json"),
            ("v2.x", "sample-local-ref-v2.9.json"),
            ("v1.x", "sample-local-ref-v1.9.json"),
        ]

        for version, filename in test_cases:
            with self.subTest(version=version, filename=filename):
                refs_dir = self.fixtures_dir / version / "with_refs"
                file_path = refs_dir / filename
                data = self._load_json_file(file_path)

                # Find all $ref references
                refs = self._find_refs_in_object(data)

                # Check that at least one local $ref exists (starts with ./)
                local_refs = [ref_value for _, ref_value in refs if ref_value.startswith("./")]
                self.assertGreater(
                    len(local_refs),
                    0,
                    f"File {filename} should contain at least one local $ref (starting with ./)",
                )

    def test_external_ref_files_contain_external_refs(self):
        """Test that external $ref files contain external $ref references"""
        test_cases = [
            ("v4.1", "sample-external-ref-v4.1.json"),
            ("v4.0", "sample-external-ref-v4.0.json"),
            ("v3.x", "sample-external-ref-v3.9.json"),
            ("v2.x", "sample-external-ref-v2.9.json"),
            ("v1.x", "sample-external-ref-v1.9.json"),
        ]

        for version, filename in test_cases:
            with self.subTest(version=version, filename=filename):
                refs_dir = self.fixtures_dir / version / "with_refs"
                file_path = refs_dir / filename
                data = self._load_json_file(file_path)

                # Find all $ref references
                refs = self._find_refs_in_object(data)

                # Check that at least one external $ref exists (starts with http:// or https://)
                external_refs = [
                    ref_value
                    for _, ref_value in refs
                    if ref_value.startswith("http://") or ref_value.startswith("https://")
                ]
                self.assertGreater(
                    len(external_refs),
                    0,
                    f"File {filename} should contain at least one external $ref (starting with http:// or https://)",
                )

    def test_ref_files_are_valid_odps(self):
        """Test that all $ref sample files are valid ODPS (pass schema validation)"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        test_cases = [
            ("4.1", "v4.1", "sample-internal-ref-v4.1.json"),
            ("4.1", "v4.1", "sample-local-ref-v4.1.json"),
            ("4.1", "v4.1", "sample-external-ref-v4.1.json"),
            ("4.0", "v4.0", "sample-internal-ref-v4.0.json"),
            ("4.0", "v4.0", "sample-local-ref-v4.0.json"),
            ("4.0", "v4.0", "sample-external-ref-v4.0.json"),
            ("3.x", "v3.x", "sample-internal-ref-v3.9.json"),
            ("3.x", "v3.x", "sample-local-ref-v3.9.json"),
            ("3.x", "v3.x", "sample-external-ref-v3.9.json"),
            ("2.x", "v2.x", "sample-internal-ref-v2.9.json"),
            ("2.x", "v2.x", "sample-local-ref-v2.9.json"),
            ("2.x", "v2.x", "sample-external-ref-v2.9.json"),
            ("1.x", "v1.x", "sample-internal-ref-v1.9.json"),
            ("1.x", "v1.x", "sample-local-ref-v1.9.json"),
            ("1.x", "v1.x", "sample-external-ref-v1.9.json"),
        ]

        for schema_version, version_dir, filename in test_cases:
            with self.subTest(version=schema_version, filename=filename):
                # Load ODPS schema
                try:
                    schema = load_odps_schema(schema_version)
                except FileNotFoundError:
                    self.skipTest(f"ODPS schema not found for version {schema_version}")

                # Load fixture file
                refs_dir = self.fixtures_dir / version_dir / "with_refs"
                file_path = refs_dir / filename
                data = self._load_json_file(file_path)

                # Validate against schema
                try:
                    # Note: $ref resolution is not performed by jsonschema by default
                    # We're validating the structure, not resolving $refs
                    validate(instance=data, schema=schema)
                except ValidationError as e:
                    self.fail(
                        f"File {filename} for version {schema_version} failed schema validation: {e.message}"
                    )
                except SchemaError as e:
                    self.fail(f"Schema error for version {schema_version}: {e.message}")

    def test_local_ref_yaml_referenced_files_exist(self):
        """Test that local $ref referenced YAML files (quality-rules, contract-definition) exist"""
        test_cases = [
            ("v4.1", "quality-rules.yaml"),
            ("v4.0", "quality-rules.yaml"),
            ("v3.x", "quality-rules.yaml"),
            ("v2.x", "quality-rules.yaml"),
            ("v1.x", "quality-rules.yaml"),
            ("v2.x", "contract-definition.yaml"),
            ("v1.x", "contract-definition.yaml"),
        ]

        for version, ref_filename in test_cases:
            with self.subTest(version=version, filename=ref_filename):
                refs_dir = self.fixtures_dir / version / "with_refs"
                ref_file = refs_dir / ref_filename

                self.assertTrue(
                    ref_file.exists(),
                    f"Referenced local file {ref_filename} should exist for version {version} at: {ref_file}",
                )

                # Verify it's valid YAML
                if not YAML_AVAILABLE:
                    self.skipTest("yaml library not available")
                try:
                    data = self._load_yaml_file(ref_file)
                    self.assertIsInstance(
                        data, dict, f"File {ref_filename} should contain a YAML object"
                    )
                except Exception as e:
                    self.fail(f"File {ref_filename} is not valid YAML: {e}")

    def test_mixed_refs_file_exists(self):
        """Test that mixed $ref sample file exists for v4.1"""
        refs_dir = self.fixtures_dir / "v4.1" / "with_refs"
        mixed_ref_file = refs_dir / "sample-mixed-refs-v4.1.json"

        self.assertTrue(
            mixed_ref_file.exists(), f"Mixed $ref sample file should exist at: {mixed_ref_file}"
        )

        # Verify it contains all three types of refs
        data = self._load_json_file(mixed_ref_file)
        refs = self._find_refs_in_object(data)

        internal_refs = [ref_value for _, ref_value in refs if ref_value.startswith("#")]
        local_refs = [ref_value for _, ref_value in refs if ref_value.startswith("./")]
        external_refs = [
            ref_value
            for _, ref_value in refs
            if ref_value.startswith("http://") or ref_value.startswith("https://")
        ]

        self.assertGreater(len(internal_refs), 0, "Mixed refs file should contain internal $ref")
        self.assertGreater(len(local_refs), 0, "Mixed refs file should contain local $ref")
        self.assertGreater(len(external_refs), 0, "Mixed refs file should contain external $ref")
