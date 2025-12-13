"""
Unit Tests for Semantic Versioning Framework
"""
import pytest
from hub.apps.contracts.versioning import (
    SemanticVersion,
    parse_version,
    validate_version,
    detect_version,
    get_default_version,
    ensure_version,
    compare_versions,
    is_compatible_version,
    VersionMigrationFramework,
    CURRENT_HUBCONTRACT_VERSION_STRING
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
        contract = {'hub_contract_version': '1.0.0'}
        assert detect_version(contract) == '1.0.0'
        
        contract = {'hub_contract_version': '2.1.3'}
        assert detect_version(contract) == '2.1.3'
    
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
        contract = {'hub_contract_version': '1.0.0'}
        result = ensure_version(contract)
        assert result['hub_contract_version'] == '1.0.0'
    
    def test_ensure_version_with_missing_version(self):
        """Test ensuring version when missing"""
        contract = {}
        result = ensure_version(contract)
        assert result['hub_contract_version'] == get_default_version()
    
    def test_ensure_version_with_invalid_version(self):
        """Test ensuring version when invalid version exists"""
        contract = {'hub_contract_version': 'invalid'}
        result = ensure_version(contract)
        assert result['hub_contract_version'] == get_default_version()


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
        contract = {'hub_contract_version': '1.0.0', 'id': 'test'}
        result, warnings = VersionMigrationFramework.migrate(contract, '1.0.0', '1.0.0')
        assert result == contract
        assert warnings == []
    
    def test_migrate_to_latest(self):
        """Test migrating to latest version"""
        contract = {'hub_contract_version': '1.0.0', 'id': 'test'}
        result, warnings = VersionMigrationFramework.migrate_to_latest(contract)
        assert result['hub_contract_version'] == CURRENT_HUBCONTRACT_VERSION_STRING
    
    def test_migrate_unsupported(self):
        """Test migrating unsupported versions"""
        contract = {'hub_contract_version': '2.0.0', 'id': 'test'}
        with pytest.raises(NotImplementedError):
            VersionMigrationFramework.migrate(contract, '2.0.0', '3.0.0')

