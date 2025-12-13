"""
Semantic Versioning Framework for HubContract

Provides version detection, validation, and migration framework for HubContract versions.
"""
import re
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class VersionComponent(Enum):
    """Version component types"""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


@dataclass
class SemanticVersion:
    """
    Semantic version representation (MAJOR.MINOR.PATCH)
    
    Follows Semantic Versioning 2.0.0 specification.
    """
    major: int
    minor: int
    patch: int
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def __repr__(self) -> str:
        return f"SemanticVersion({self.major}, {self.minor}, {self.patch})"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, SemanticVersion):
            return False
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)
    
    def __lt__(self, other) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
    
    def __le__(self, other) -> bool:
        return self == other or self < other
    
    def __gt__(self, other) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)
    
    def __ge__(self, other) -> bool:
        return self == other or self > other


# Current HubContract version (development version)
CURRENT_HUBCONTRACT_VERSION = SemanticVersion(1, 0, 0)
CURRENT_HUBCONTRACT_VERSION_STRING = "1.0.0"


def parse_version(version_string: str) -> Optional[SemanticVersion]:
    """
    Parse semantic version string to SemanticVersion object.
    
    Args:
        version_string: Version string in format "MAJOR.MINOR.PATCH" (e.g., "1.0.0")
    
    Returns:
        SemanticVersion object or None if invalid
    """
    if not version_string or not isinstance(version_string, str):
        return None
    
    # Match semantic version pattern: MAJOR.MINOR.PATCH
    pattern = r'^(\d+)\.(\d+)\.(\d+)$'
    match = re.match(pattern, version_string.strip())
    
    if not match:
        return None
    
    try:
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3))
        
        # Validate version components are non-negative
        if major < 0 or minor < 0 or patch < 0:
            return None
        
        return SemanticVersion(major, minor, patch)
    except (ValueError, IndexError):
        return None


def validate_version(version_string: str) -> Tuple[bool, Optional[str]]:
    """
    Validate semantic version string.
    
    Args:
        version_string: Version string to validate
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if not version_string:
        return False, "Version string cannot be empty"
    
    if not isinstance(version_string, str):
        return False, "Version must be a string"
    
    parsed = parse_version(version_string)
    
    if parsed is None:
        return False, f"Invalid version format: '{version_string}'. Expected format: MAJOR.MINOR.PATCH (e.g., '1.0.0')"
    
    return True, None


def detect_version(contract_data: Dict[str, Any]) -> Optional[str]:
    """
    Detect HubContract version from contract data.
    
    Looks for 'hub_contract_version' field in the contract.
    
    Args:
        contract_data: Contract data dictionary
    
    Returns:
        Version string if found, None otherwise
    """
    if not isinstance(contract_data, dict):
        return None
    
    # Check for hub_contract_version field
    version = contract_data.get('hub_contract_version')
    
    if version is None:
        return None
    
    # Convert to string if needed
    if isinstance(version, (int, float)):
        # Handle integer versions (e.g., 1 for v1)
        if isinstance(version, int):
            return f"{version}.0.0"
        else:
            return str(version)
    
    if isinstance(version, str):
        return version
    
    return None


def get_default_version() -> str:
    """
    Get default HubContract version for new contracts.
    
    During development, all contracts use version "1.0.0".
    
    Returns:
        Default version string ("1.0.0")
    """
    return CURRENT_HUBCONTRACT_VERSION_STRING


def ensure_version(contract_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure contract has a valid hub_contract_version field.
    
    If version is missing or invalid, sets it to default version "1.0.0".
    
    Args:
        contract_data: Contract data dictionary
    
    Returns:
        Contract data with ensured version field
    """
    if not isinstance(contract_data, dict):
        contract_data = {}
    
    # Check if version exists and is valid
    version = detect_version(contract_data)
    
    if version:
        is_valid, error = validate_version(version)
        if is_valid:
            return contract_data
    
    # Set default version
    contract_data['hub_contract_version'] = get_default_version()
    return contract_data


def compare_versions(version1: str, version2: str) -> int:
    """
    Compare two semantic versions.
    
    Args:
        version1: First version string
        version2: Second version string
    
    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
    
    Raises:
        ValueError: If either version is invalid
    """
    v1 = parse_version(version1)
    v2 = parse_version(version2)
    
    if v1 is None:
        raise ValueError(f"Invalid version: {version1}")
    if v2 is None:
        raise ValueError(f"Invalid version: {version2}")
    
    if v1 < v2:
        return -1
    elif v1 > v2:
        return 1
    else:
        return 0


def is_compatible_version(version: str, target_version: str) -> bool:
    """
    Check if a version is compatible with target version.
    
    Compatibility rules:
    - Same major version: compatible
    - Different major version: incompatible
    
    Args:
        version: Version to check
        target_version: Target version for compatibility check
    
    Returns:
        True if compatible, False otherwise
    """
    try:
        v1 = parse_version(version)
        v2 = parse_version(target_version)
        
        if v1 is None or v2 is None:
            return False
        
        # Same major version means compatible
        return v1.major == v2.major
    except (ValueError, AttributeError):
        return False


class VersionMigrationFramework:
    """
    Framework for migrating HubContract between versions.
    
    This framework is ready for future use when HubContract versions are incremented.
    During development, all contracts use version "1.0.0", so no migrations are needed.
    """
    
    @staticmethod
    def migrate(contract_data: Dict[str, Any], from_version: str, to_version: str) -> Tuple[Dict[str, Any], list]:
        """
        Migrate contract from one version to another.
        
        Args:
            contract_data: Contract data to migrate
            from_version: Source version
            to_version: Target version
        
        Returns:
            Tuple of (migrated_contract_data, migration_warnings)
        """
        warnings = []
        
        # Validate versions
        is_valid_from, error_from = validate_version(from_version)
        is_valid_to, error_to = validate_version(to_version)
        
        if not is_valid_from:
            raise ValueError(f"Invalid source version: {from_version} - {error_from}")
        if not is_valid_to:
            raise ValueError(f"Invalid target version: {to_version} - {error_to}")
        
        # If versions are the same, no migration needed
        if from_version == to_version:
            return contract_data, warnings
        
        # Parse versions
        from_v = parse_version(from_version)
        to_v = parse_version(to_version)
        
        if from_v is None or to_v is None:
            raise ValueError(f"Failed to parse versions: {from_version} -> {to_version}")
        
        # If downgrading, that's not supported
        if from_v > to_v:
            raise ValueError(f"Downgrading from {from_version} to {to_version} is not supported")
        
        # During development, all contracts are version 1.0.0
        # No migrations needed yet
        if from_v.major == 1 and to_v.major == 1:
            # Same major version, minor/patch updates may require migrations in future
            # For now, just ensure version field is updated
            contract_data = contract_data.copy()
            contract_data['hub_contract_version'] = to_version
            return contract_data, warnings
        
        # Future: Add migration logic for version increments
        # For now, raise error for unsupported migrations
        raise NotImplementedError(
            f"Migration from {from_version} to {to_version} is not yet implemented. "
            f"Current supported version: {CURRENT_HUBCONTRACT_VERSION_STRING}"
        )
    
    @staticmethod
    def migrate_to_latest(contract_data: Dict[str, Any]) -> Tuple[Dict[str, Any], list]:
        """
        Migrate contract to latest HubContract version.
        
        Args:
            contract_data: Contract data to migrate
        
        Returns:
            Tuple of (migrated_contract_data, migration_warnings)
        """
        current_version = detect_version(contract_data) or get_default_version()
        return VersionMigrationFramework.migrate(
            contract_data,
            current_version,
            CURRENT_HUBCONTRACT_VERSION_STRING
        )

