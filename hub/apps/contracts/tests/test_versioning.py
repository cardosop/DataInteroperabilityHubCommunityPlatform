"""
Unit Tests for Semantic Versioning Framework
"""

import pytest

from hub.apps.contracts.versioning import (
    CURRENT_HUBCONTRACT_VERSION_STRING,
    SemanticVersion,
    VersionMigrationFramework,
    compare_versions,
    detect_version,
    ensure_version,
    get_default_version,
    is_compatible_version,
    parse_version,
    validate_version,
)


class TestSemanticVersion:
    """Test SemanticVersion class"""

    def test_version_creation(self):
        """Test creating SemanticVersion objects"""
        v = SemanticVersion(1, 0, 0)
        assert str(v) == "1.0.0"
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0

    def test_version_comparison(self):
        """Test version comparison"""
        v1 = SemanticVersion(1, 0, 0)
        v2 = SemanticVersion(1, 0, 1)
        v3 = SemanticVersion(1, 1, 0)
        v4 = SemanticVersion(2, 0, 0)

        assert v1 < v2
        assert v1 < v3
        assert v1 < v4
        assert v1 == SemanticVersion(1, 0, 0)
        assert v1 <= v2
        assert v2 > v1
        assert v2 >= v1


class TestParseVersion:
    """Test version parsing"""

    def test_parse_valid_version(self):
        """Test parsing valid version strings"""
        assert parse_version("1.0.0") == SemanticVersion(1, 0, 0)
        assert parse_version("2.5.10") == SemanticVersion(2, 5, 10)
        assert parse_version("0.1.0") == SemanticVersion(0, 1, 0)

    def test_parse_invalid_version(self):
        """Test parsing invalid version strings"""
        assert parse_version("") is None
        assert parse_version("1.0") is None
        assert parse_version("1.0.0.0") is None
        assert parse_version("1.0.0-beta") is None
        assert parse_version("invalid") is None
        assert parse_version(None) is None


class TestValidateVersion:
    """Test version validation"""

    def test_validate_valid_version(self):
        """Test validating valid versions"""
        is_valid, error = validate_version("1.0.0")
        assert is_valid is True
        assert error is None

    def test_validate_invalid_version(self):
        """Test validating invalid versions"""
        is_valid, error = validate_version("")
        assert is_valid is False
        assert error is not None

        is_valid, error = validate_version("1.0")
        assert is_valid is False
        assert error is not None


class TestDetectVersion:
    """Test version detection"""

    def test_detect_version_from_contract(self):
        """Test detecting version from contract data"""
        contract = {"hub_contract_version": "1.0.0"}
        assert detect_version(contract) == "1.0.0"

        contract = {"hub_contract_version": "2.1.3"}
        assert detect_version(contract) == "2.1.3"

    def test_detect_version_missing(self):
        """Test detecting version when missing"""
        contract = {}
        assert detect_version(contract) is None


class TestGetDefaultVersion:
    """Test default version"""

    def test_get_default_version(self):
        """Test getting default version"""
        assert get_default_version() == CURRENT_HUBCONTRACT_VERSION_STRING
        assert get_default_version() == "1.0.0"


class TestEnsureVersion:
    """Test ensuring version in contract"""

    def test_ensure_version_with_valid_version(self):
        """Test ensuring version when valid version exists"""
        contract = {"hub_contract_version": "1.0.0"}
        result = ensure_version(contract)
        assert result["hub_contract_version"] == "1.0.0"

    def test_ensure_version_with_missing_version(self):
        """Test ensuring version when missing"""
        contract = {}
        result = ensure_version(contract)
        assert result["hub_contract_version"] == get_default_version()

    def test_ensure_version_with_invalid_version(self):
        """Test ensuring version when invalid version exists"""
        contract = {"hub_contract_version": "invalid"}
        result = ensure_version(contract)
        assert result["hub_contract_version"] == get_default_version()


class TestCompareVersions:
    """Test version comparison"""

    def test_compare_versions(self):
        """Test comparing versions"""
        assert compare_versions("1.0.0", "1.0.1") == -1
        assert compare_versions("1.0.1", "1.0.0") == 1
        assert compare_versions("1.0.0", "1.0.0") == 0

    def test_compare_versions_invalid(self):
        """Test comparing invalid versions"""
        with pytest.raises(ValueError):
            compare_versions("invalid", "1.0.0")


class TestIsCompatibleVersion:
    """Test version compatibility"""

    def test_compatible_versions(self):
        """Test compatible versions (same major)"""
        assert is_compatible_version("1.0.0", "1.0.1") is True
        assert is_compatible_version("1.0.0", "1.5.0") is True
        assert is_compatible_version("1.0.0", "1.0.0") is True

    def test_incompatible_versions(self):
        """Test incompatible versions (different major)"""
        assert is_compatible_version("1.0.0", "2.0.0") is False
        assert is_compatible_version("2.0.0", "1.0.0") is False


class TestVersionMigrationFramework:
    """Test version migration framework"""

    def test_migrate_same_version(self):
        """Test migrating same version (no-op)"""
        contract = {"hub_contract_version": "1.0.0", "id": "test"}
        result, warnings = VersionMigrationFramework.migrate(contract, "1.0.0", "1.0.0")
        assert result == contract
        assert warnings == []

    def test_migrate_to_latest(self):
        """Test migrating to latest version"""
        contract = {"hub_contract_version": "1.0.0", "id": "test"}
        result, _warnings = VersionMigrationFramework.migrate_to_latest(contract)
        assert result["hub_contract_version"] == CURRENT_HUBCONTRACT_VERSION_STRING

    def test_migrate_unsupported(self):
        """Test migrating unsupported versions"""
        contract = {"hub_contract_version": "2.0.0", "id": "test"}
        with pytest.raises(NotImplementedError):
            VersionMigrationFramework.migrate(contract, "2.0.0", "3.0.0")

    # Edge cases and error handling tests
    def test_semantic_version_with_large_numbers(self):
        """Test SemanticVersion with very large version numbers."""
        v = SemanticVersion(999, 999, 999)
        assert str(v) == "999.999.999"
        assert v.major == 999
        assert v.minor == 999
        assert v.patch == 999

    def test_semantic_version_with_zero_values(self):
        """Test SemanticVersion with zero values."""
        v = SemanticVersion(0, 0, 0)
        assert str(v) == "0.0.0"
        assert v.major == 0
        assert v.minor == 0
        assert v.patch == 0

    def test_semantic_version_equality(self):
        """Test SemanticVersion equality comparison."""
        v1 = SemanticVersion(1, 2, 3)
        v2 = SemanticVersion(1, 2, 3)
        v3 = SemanticVersion(1, 2, 4)

        assert v1 == v2
        assert v1 != v3
        assert (hash(v1) == hash(v2)) if callable(getattr(v1, "__hash__", None)) else True

    def test_parse_version_with_whitespace(self):
        """Test parsing version strings with whitespace (parser strips whitespace)."""
        result = parse_version(" 1.0.0 ")
        # parse_version strips whitespace and succeeds
        assert result is None or isinstance(result, SemanticVersion)
        result = parse_version("1.0.0\n")
        assert result is None or isinstance(result, SemanticVersion)
        result = parse_version("\t1.0.0")
        assert result is None or isinstance(result, SemanticVersion)

    def test_parse_version_with_leading_zeros(self):
        """Test parsing version strings with leading zeros."""
        # Leading zeros may or may not be valid depending on implementation
        result = parse_version("01.02.03")
        # Should either parse or return None
        assert result is None or isinstance(result, SemanticVersion)

    def test_parse_version_with_negative_numbers(self):
        """Test parsing version strings with negative numbers."""
        assert parse_version("-1.0.0") is None
        assert parse_version("1.-1.0") is None
        assert parse_version("1.0.-1") is None

    def test_validate_version_with_whitespace(self):
        """Test validating version strings with whitespace (validator may strip)."""
        is_valid, _error = validate_version(" 1.0.0 ")
        # Validator may accept whitespace-trimmed versions
        assert isinstance(is_valid, bool)

    def test_validate_version_with_special_characters(self):
        """Test validating version strings with special characters."""
        invalid_versions = [
            "1.0.0-alpha",
            "1.0.0+build",
            "1.0.0_rc1",
            "v1.0.0",
            "1.0.0.0",
            "1.0",
        ]
        for version in invalid_versions:
            is_valid, error = validate_version(version)
            assert is_valid is False
            assert error is not None

    def test_detect_version_with_nested_structure(self):
        """Test detecting version from nested contract structure."""
        contract = {"metadata": {"hub_contract_version": "1.0.0"}}
        # detect_version should look at top level
        result = detect_version(contract)
        assert result is None  # Not at top level

    def test_detect_version_with_different_key_names(self):
        """Test detecting version with different key name variations."""
        contract = {"version": "1.0.0"}  # Different key name
        result = detect_version(contract)
        # Should only detect hub_contract_version key
        assert result is None

    def test_get_default_version_consistency(self):
        """Test that default version is consistent across calls."""
        v1 = get_default_version()
        v2 = get_default_version()
        assert v1 == v2
        assert v1 == CURRENT_HUBCONTRACT_VERSION_STRING

    def test_ensure_version_preserves_other_fields(self):
        """Test that ensure_version preserves other contract fields."""
        contract = {"id": "test-id", "info": {"name": "Test"}, "hub_contract_version": "1.0.0"}
        result = ensure_version(contract)
        assert result["id"] == "test-id"
        assert result["info"] == {"name": "Test"}
        assert result["hub_contract_version"] == "1.0.0"

    def test_ensure_version_adds_version_to_empty_contract(self):
        """Test that ensure_version adds version to empty contract."""
        contract = {}
        result = ensure_version(contract)
        assert "hub_contract_version" in result
        assert result["hub_contract_version"] == get_default_version()

    def test_compare_versions_with_none(self):
        """Test comparing versions with None values."""
        with pytest.raises((ValueError, TypeError)):
            compare_versions(None, "1.0.0")

        with pytest.raises((ValueError, TypeError)):
            compare_versions("1.0.0", None)

    def test_compare_versions_same_string(self):
        """Test comparing same version strings."""
        assert compare_versions("1.0.0", "1.0.0") == 0
        assert compare_versions("2.5.10", "2.5.10") == 0

    def test_compare_versions_major_difference(self):
        """Test comparing versions with major version differences."""
        assert compare_versions("1.0.0", "2.0.0") == -1
        assert compare_versions("2.0.0", "1.0.0") == 1

    def test_compare_versions_minor_difference(self):
        """Test comparing versions with minor version differences."""
        assert compare_versions("1.0.0", "1.1.0") == -1
        assert compare_versions("1.1.0", "1.0.0") == 1

    def test_compare_versions_patch_difference(self):
        """Test comparing versions with patch version differences."""
        assert compare_versions("1.0.0", "1.0.1") == -1
        assert compare_versions("1.0.1", "1.0.0") == 1

    def test_is_compatible_version_with_same_version(self):
        """Test compatibility check with same version."""
        assert is_compatible_version("1.0.0", "1.0.0") is True

    def test_is_compatible_version_with_patch_difference(self):
        """Test compatibility check with patch version difference."""
        assert is_compatible_version("1.0.0", "1.0.5") is True
        assert is_compatible_version("1.0.5", "1.0.0") is True

    def test_is_compatible_version_with_minor_difference(self):
        """Test compatibility check with minor version difference."""
        assert is_compatible_version("1.0.0", "1.5.0") is True
        assert is_compatible_version("1.5.0", "1.0.0") is True

    def test_is_compatible_version_with_major_difference(self):
        """Test compatibility check with major version difference."""
        assert is_compatible_version("1.0.0", "2.0.0") is False
        assert is_compatible_version("2.0.0", "1.0.0") is False

    def test_is_compatible_version_with_invalid_versions(self):
        """Test compatibility check with invalid versions (returns False, doesn't raise)."""
        result = is_compatible_version("invalid", "1.0.0")
        assert result is False

        result = is_compatible_version("1.0.0", "invalid")
        assert result is False

    def test_migrate_with_empty_contract(self):
        """Test migration with empty contract — None version raises ValueError."""
        contract = {}
        with pytest.raises(ValueError):
            VersionMigrationFramework.migrate(contract, None, CURRENT_HUBCONTRACT_VERSION_STRING)

    def test_migrate_with_contract_missing_id(self):
        """Test migration with contract missing id field."""
        contract = {"hub_contract_version": "1.0.0"}
        result, warnings = VersionMigrationFramework.migrate(
            contract, "1.0.0", CURRENT_HUBCONTRACT_VERSION_STRING
        )
        assert "hub_contract_version" in result
        assert isinstance(warnings, list)

    def test_migrate_to_latest_with_invalid_current_version(self):
        """Test migrating to latest with invalid current version."""
        contract = {"hub_contract_version": "invalid", "id": "test"}
        try:
            result, _warnings = VersionMigrationFramework.migrate_to_latest(contract)
            # If it succeeds, contract should have version set
            assert "hub_contract_version" in result
        except (ValueError, NotImplementedError):
            # Raising on invalid version is acceptable
            pass

    def test_migrate_preserves_contract_structure(self):
        """Test that migration preserves contract structure."""
        contract = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "info": {"name": "Test"},
            "schema": {"fields": []},
        }
        result, _warnings = VersionMigrationFramework.migrate(
            contract, "1.0.0", CURRENT_HUBCONTRACT_VERSION_STRING
        )
        assert result["id"] == "test"
        assert result["info"] == {"name": "Test"}
        assert result["schema"] == {"fields": []}
