"""
ODPS $ref Resolver Configuration

Provides configuration management for ODPS $ref resolver security settings,
including directory whitelist, URL allowlist/denylist, and other security controls.

Configuration is loaded from:
1. YAML configuration file: `hub/apps/contracts/config/odps_refs.yaml`
2. Environment variables (override YAML values)
3. Default values (fallback if neither YAML nor env vars are set)
4. Per-tenant overrides (from TenantConfig.odps_refs_config JSONField)
"""

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import structlog

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

logger = structlog.get_logger(__name__)

# Default configuration values
DEFAULT_ALLOWED_BASE_DIRS = ["./contracts/refs", "./odps-refs"]
DEFAULT_URL_ALLOWLIST: list[str] = []
DEFAULT_URL_DENYLIST: list[str] = []

# Environment variable names
ENV_ODPS_REFS_DIR = "ODPS_REFS_DIR"
ENV_ODPS_URL_ALLOWLIST = "ODPS_URL_ALLOWLIST"
ENV_ODPS_URL_DENYLIST = "ODPS_URL_DENYLIST"


class ODPSRefsConfig:
    """
    Configuration manager for ODPS $ref resolver security settings.

    Loads configuration from YAML file and environment variables, providing
    a unified interface for accessing security configuration.

    Attributes:
        allowed_base_dirs: List of allowed base directories for local $ref resolution
        url_allowlist: List of allowed URL patterns for external $ref resolution
        url_denylist: List of denied URL patterns for external $ref resolution
    """

    def __init__(
        self, config_file: Path | None = None, tenant_config: dict[str, Any] | None = None
    ):
        """
        Initialize configuration from file and environment variables.

        Args:
            config_file: Optional path to configuration file. If None, uses default location.
            tenant_config: Optional per-tenant configuration dict (from TenantConfig.odps_refs_config).
                          Overrides global config if provided.
        """
        self._config_file = config_file or self._get_default_config_file()
        self._config_data = {}
        self._tenant_config = tenant_config or {}
        self._load_config()

    def _get_default_config_file(self) -> Path:
        """Get default configuration file path"""
        # This file is in hub/apps/contracts/config/
        # So parent.parent is hub/apps/contracts/
        base_dir = Path(__file__).parent
        return base_dir / "odps_refs.yaml"

    def _load_config(self) -> None:
        """Load configuration from YAML file and environment variables"""
        # Load from YAML file if available
        if YAML_AVAILABLE and self._config_file.exists():
            try:
                with open(self._config_file, encoding="utf-8") as f:
                    self._config_data = yaml.safe_load(f) or {}
                logger.debug(
                    "Loaded ODPS refs configuration from file", config_file=str(self._config_file)
                )
            except Exception as e:
                logger.warning(
                    "Failed to load ODPS refs configuration from file, using defaults",
                    config_file=str(self._config_file),
                    error=str(e),
                )
                self._config_data = {}
        else:
            if not YAML_AVAILABLE:
                logger.debug("YAML library not available, using defaults and environment variables")
            else:
                logger.debug(
                    "ODPS refs configuration file not found, using defaults",
                    config_file=str(self._config_file),
                )
            self._config_data = {}

        # Apply environment variable overrides
        self._apply_env_overrides()

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration"""
        # ODPS_REFS_DIR: Additional directory to add to allowed_base_dirs
        odps_refs_dir = os.getenv(ENV_ODPS_REFS_DIR)
        if odps_refs_dir:
            # Ensure allowed_base_dirs exists in config
            if "allowed_base_dirs" not in self._config_data:
                self._config_data["allowed_base_dirs"] = []

            # Add environment variable directory if not already present
            if odps_refs_dir not in self._config_data["allowed_base_dirs"]:
                self._config_data["allowed_base_dirs"].append(odps_refs_dir)
                logger.debug(
                    "Added directory from environment variable to allowed_base_dirs",
                    directory=odps_refs_dir,
                    env_var=ENV_ODPS_REFS_DIR,
                )

        # ODPS_URL_ALLOWLIST: Comma-separated list of allowed URL patterns
        url_allowlist_env = os.getenv(ENV_ODPS_URL_ALLOWLIST)
        if url_allowlist_env:
            allowlist_items = [
                item.strip() for item in url_allowlist_env.split(",") if item.strip()
            ]
            if allowlist_items:
                # Merge with existing allowlist (env vars take precedence)
                existing_allowlist = self._config_data.get("url_allowlist", [])
                # Combine and deduplicate
                combined_allowlist = list(set(existing_allowlist + allowlist_items))
                self._config_data["url_allowlist"] = combined_allowlist
                logger.debug(
                    "Set URL allowlist from environment variable",
                    count=len(combined_allowlist),
                    env_var=ENV_ODPS_URL_ALLOWLIST,
                )

        # ODPS_URL_DENYLIST: Comma-separated list of denied URL patterns
        url_denylist_env = os.getenv(ENV_ODPS_URL_DENYLIST)
        if url_denylist_env:
            denylist_items = [item.strip() for item in url_denylist_env.split(",") if item.strip()]
            if denylist_items:
                # Merge with existing denylist (env vars take precedence)
                existing_denylist = self._config_data.get("url_denylist", [])
                # Combine and deduplicate
                combined_denylist = list(set(existing_denylist + denylist_items))
                self._config_data["url_denylist"] = combined_denylist
                logger.debug(
                    "Set URL denylist from environment variable",
                    count=len(combined_denylist),
                    env_var=ENV_ODPS_URL_DENYLIST,
                )

        # Apply per-tenant overrides (highest precedence)
        if self._tenant_config:
            if "url_allowlist" in self._tenant_config:
                self._config_data["url_allowlist"] = self._tenant_config["url_allowlist"]
                logger.debug("Applied per-tenant URL allowlist override")
            if "url_denylist" in self._tenant_config:
                self._config_data["url_denylist"] = self._tenant_config["url_denylist"]
                logger.debug("Applied per-tenant URL denylist override")

    @property
    def allowed_base_dirs(self) -> list[str]:
        """
        Get list of allowed base directories for local $ref resolution.

        Returns:
            List of directory paths (can be relative or absolute)

        Example:
            >>> config = ODPSRefsConfig()
            >>> dirs = config.allowed_base_dirs
            >>> print(dirs)
            ['./contracts/refs', './odps-refs']
        """
        # Get from config data, or use defaults
        dirs = self._config_data.get("allowed_base_dirs", DEFAULT_ALLOWED_BASE_DIRS.copy())

        # Ensure it's a list
        if not isinstance(dirs, list):
            logger.warning("allowed_base_dirs is not a list, using defaults", value=dirs)
            return DEFAULT_ALLOWED_BASE_DIRS.copy()

        # Return a copy to prevent external modification
        return dirs.copy()

    def get_allowed_base_dirs_absolute(self, base_path: Path | None = None) -> list[Path]:
        """
        Get list of allowed base directories as absolute Path objects.

        Args:
            base_path: Base path for resolving relative directories. If None, uses current working directory.

        Returns:
            List of absolute Path objects for allowed directories

        Example:
            >>> config = ODPSRefsConfig()
            >>> abs_dirs = config.get_allowed_base_dirs_absolute(Path('/project/root'))
            >>> print(abs_dirs)
            [PosixPath('/project/root/contracts/refs'), PosixPath('/project/root/odps-refs')]
        """
        if base_path is None:
            base_path = Path.cwd()

        absolute_dirs = []
        for dir_path in self.allowed_base_dirs:
            dir_path_obj = Path(dir_path)
            if dir_path_obj.is_absolute():
                absolute_dirs.append(dir_path_obj)
            else:
                absolute_dirs.append((base_path / dir_path_obj).resolve())

        return absolute_dirs

    def is_path_allowed(self, file_path: Path, base_path: Path | None = None) -> bool:
        """
        Check if a file path is within an allowed base directory.

        This method prevents path traversal attacks by ensuring that the file
        path is within one of the whitelisted base directories.

        Args:
            file_path: Path to the file to check (can be relative or absolute)
            base_path: Base path for resolving relative paths. If None, uses current working directory.

        Returns:
            True if the path is within an allowed directory, False otherwise

        Example:
            >>> config = ODPSRefsConfig()
            >>> config.is_path_allowed(Path('./contracts/refs/schema.yaml'))
            True
            >>> config.is_path_allowed(Path('/etc/passwd'))
            False
        """
        if base_path is None:
            base_path = Path.cwd()

        # Resolve the file path to absolute
        if file_path.is_absolute():
            resolved_file_path = file_path.resolve()
        else:
            resolved_file_path = (base_path / file_path).resolve()

        # Get allowed directories as absolute paths
        allowed_dirs = self.get_allowed_base_dirs_absolute(base_path)

        # Check if the file path is within any allowed directory
        for allowed_dir in allowed_dirs:
            try:
                # Resolve the allowed directory
                resolved_allowed_dir = allowed_dir.resolve()

                # Check if file path is within allowed directory
                # Use resolve() to handle symlinks and normalize paths
                # is_relative_to() is available in Python 3.9+, use alternative for compatibility
                try:
                    # Python 3.9+ method
                    if hasattr(resolved_file_path, "is_relative_to"):
                        if resolved_file_path.is_relative_to(resolved_allowed_dir):
                            return True
                except (AttributeError, ValueError):
                    pass

                # Fallback for Python < 3.9: check if commonpath matches
                try:
                    common_path = Path(
                        os.path.commonpath([str(resolved_file_path), str(resolved_allowed_dir)])
                    )
                    if common_path == resolved_allowed_dir:
                        return True
                except (ValueError, OSError):
                    # Paths don't have a common path (different drives on Windows, or invalid paths)
                    pass
            except (ValueError, OSError) as e:
                # Handle cases where path resolution fails
                logger.debug(
                    "Failed to check path against allowed directory",
                    allowed_dir=str(allowed_dir),
                    file_path=str(file_path),
                    error=str(e),
                )
                continue

        return False

    @property
    def url_allowlist(self) -> list[str]:
        """
        Get list of allowed URL patterns for external $ref resolution.

        Patterns can be:
        - Full URLs: "https://example.com/schemas/"
        - Domain patterns: "https://*.example.com"
        - Host patterns: "example.com"
        - Wildcard patterns: "https://*"

        Returns:
            List of URL patterns (strings)

        Example:
            >>> config = ODPSRefsConfig()
            >>> patterns = config.url_allowlist
            >>> print(patterns)
            ['https://schemas.example.com', 'https://*.trusted-domain.com']
        """
        # Get from tenant config first, then config data, then defaults
        patterns = self._tenant_config.get("url_allowlist") or self._config_data.get(
            "url_allowlist", DEFAULT_URL_ALLOWLIST.copy()
        )

        # Ensure it's a list
        if not isinstance(patterns, list):
            logger.warning("url_allowlist is not a list, using defaults", value=patterns)
            return DEFAULT_URL_ALLOWLIST.copy()

        # Return a copy to prevent external modification
        return patterns.copy()

    @property
    def url_denylist(self) -> list[str]:
        """
        Get list of denied URL patterns for external $ref resolution.

        Patterns can be:
        - Full URLs: "https://malicious.com/"
        - Domain patterns: "https://*.malicious.com"
        - Host patterns: "malicious.com"
        - Wildcard patterns: "http://*" (deny all HTTP)

        Returns:
            List of URL patterns (strings)

        Example:
            >>> config = ODPSRefsConfig()
            >>> patterns = config.url_denylist
            >>> print(patterns)
            ['http://*', 'https://*.malicious.com']
        """
        # Get from tenant config first, then config data, then defaults
        patterns = self._tenant_config.get("url_denylist") or self._config_data.get(
            "url_denylist", DEFAULT_URL_DENYLIST.copy()
        )

        # Ensure it's a list
        if not isinstance(patterns, list):
            logger.warning("url_denylist is not a list, using defaults", value=patterns)
            return DEFAULT_URL_DENYLIST.copy()

        # Return a copy to prevent external modification
        return patterns.copy()

    def is_url_allowed(self, url: str) -> bool:
        """
        Check if a URL is allowed for external $ref resolution.

        This method checks the URL against both allowlist and denylist patterns.
        Denylist takes precedence - if a URL matches the denylist, it's denied.
        If allowlist is empty, all URLs are allowed (unless in denylist).
        If allowlist is not empty, URL must match at least one pattern.

        Args:
            url: URL to check (must be a valid URL)

        Returns:
            True if URL is allowed, False otherwise

        Example:
            >>> config = ODPSRefsConfig()
            >>> config.is_url_allowed("https://schemas.example.com/schema.json")
            True
            >>> config.is_url_allowed("http://malicious.com/schema.json")
            False
        """
        # Validate URL is not empty
        if not url or not isinstance(url, str):
            return False

        try:
            parsed_url = urlparse(url)
        except Exception as e:
            logger.warning("Failed to parse URL for allowlist check", url=url, error=str(e))
            return False

        # Validate URL has required components (scheme and netloc)
        if not parsed_url.scheme or not parsed_url.netloc:
            logger.debug(
                "URL missing required components (scheme or netloc)",
                url=url,
                scheme=parsed_url.scheme,
                netloc=parsed_url.netloc,
            )
            return False

        # Check denylist first (denylist takes precedence)
        denylist = self.url_denylist
        if denylist:
            for pattern in denylist:
                if self._url_matches_pattern(url, parsed_url, pattern):
                    logger.debug("URL denied by denylist pattern", url=url, pattern=pattern)
                    return False

        # Check allowlist
        allowlist = self.url_allowlist
        if not allowlist:
            # Empty allowlist means all URLs are allowed (unless in denylist)
            return True

        # URL must match at least one allowlist pattern
        for pattern in allowlist:
            if self._url_matches_pattern(url, parsed_url, pattern):
                logger.debug("URL allowed by allowlist pattern", url=url, pattern=pattern)
                return True

        # URL doesn't match any allowlist pattern
        logger.debug("URL not in allowlist", url=url, allowlist=allowlist)
        return False

    def _url_matches_pattern(self, url: str, parsed_url: Any, pattern: str) -> bool:
        """
        Check if a URL matches a pattern.

        Patterns support:
        - Exact match: "https://example.com/schema.json" (matches exact URL including path)
        - Domain wildcard: "https://*.example.com" (matches any subdomain, any path)
        - Host wildcard: "*.example.com" (matches any subdomain, any scheme/path)
        - Full wildcard: "https://*" (matches any host with https)
        - Scheme + host: "https://example.com" (matches any path on that host)
        - Host only: "example.com" (matches any scheme/path on that host)

        Args:
            url: Full URL string
            parsed_url: Parsed URL object from urlparse
            pattern: Pattern to match against

        Returns:
            True if URL matches pattern, False otherwise
        """
        # Normalize pattern (remove trailing slashes for comparison)
        pattern = pattern.rstrip("/")
        url_normalized = url.rstrip("/")

        # Exact match (including path)
        if url_normalized == pattern:
            return True

        # Parse pattern to extract components
        try:
            pattern_parsed = urlparse(pattern)
        except Exception:
            # If pattern can't be parsed as URL, try as hostname
            if "*" in pattern:
                # Wildcard hostname pattern
                pattern_regex = pattern.replace(".", r"\.").replace("*", ".*")
                if re.match(f"^{pattern_regex}$", parsed_url.netloc):
                    return True
            elif pattern == parsed_url.netloc:
                return True
            return False

        # Pattern has scheme - match scheme and host
        if pattern_parsed.scheme:
            # Scheme must match
            if pattern_parsed.scheme != parsed_url.scheme:
                return False

            # Extract pattern host
            pattern_host = pattern_parsed.netloc or pattern_parsed.path.split("/")[0]

            # Check if pattern has a path component
            pattern_has_path = bool(pattern_parsed.path and pattern_parsed.path != "/")

            if pattern_has_path:
                # Pattern includes path - must match exactly (including path)
                # Normalize paths for comparison
                pattern_path = pattern_parsed.path.rstrip("/")
                url_path = parsed_url.path.rstrip("/")

                # Host must match
                if pattern_host == parsed_url.netloc:
                    # Exact path match
                    if pattern_path == url_path:
                        return True
                elif "*" in pattern_host:
                    # Wildcard hostname with path
                    pattern_regex = pattern_host.replace(".", r"\.").replace("*", ".*")
                    if re.match(f"^{pattern_regex}$", parsed_url.netloc):
                        if pattern_path == url_path:
                            return True
            # Pattern has no path - match host only (any path allowed)
            elif "*" in pattern_host:
                # Wildcard hostname pattern
                pattern_regex = pattern_host.replace(".", r"\.").replace("*", ".*")
                if re.match(f"^{pattern_regex}$", parsed_url.netloc):
                    return True
            elif pattern_host == parsed_url.netloc:
                return True
        else:
            # No scheme in pattern - match host only (any scheme/path allowed)
            pattern_host = pattern.split("/")[0]
            if "*" in pattern_host:
                # Wildcard hostname pattern
                pattern_regex = pattern_host.replace(".", r"\.").replace("*", ".*")
                if re.match(f"^{pattern_regex}$", parsed_url.netloc):
                    return True
            elif pattern_host == parsed_url.netloc:
                return True

        return False


# Global configuration instance (lazy-loaded)
_config_instance: ODPSRefsConfig | None = None


def get_odps_refs_config(
    config_file: Path | None = None, tenant_config: dict[str, Any] | None = None
) -> ODPSRefsConfig:
    """
    Get the global ODPS refs configuration instance.

    This function provides a singleton-like access to the configuration,
    loading it once and reusing the same instance.

    Args:
        config_file: Optional path to configuration file. If None, uses default location.
        tenant_config: Optional per-tenant configuration dict (from TenantConfig.odps_refs_config).
                      Overrides global config if provided.

    Returns:
        ODPSRefsConfig instance

    Example:
        >>> config = get_odps_refs_config()
        >>> dirs = config.allowed_base_dirs
        >>> is_allowed = config.is_url_allowed("https://example.com/schema.json")
    """
    global _config_instance

    # If tenant_config is provided, create a new instance (don't cache per-tenant configs)
    if tenant_config is not None:
        return ODPSRefsConfig(config_file=config_file, tenant_config=tenant_config)

    if _config_instance is None or config_file is not None:
        _config_instance = ODPSRefsConfig(config_file=config_file)

    return _config_instance


# Convenience function for getting allowed base directories
def get_allowed_base_dirs() -> list[str]:
    """
    Get list of allowed base directories for local $ref resolution.

    This is a convenience function that uses the global configuration instance.

    Returns:
        List of directory paths

    Example:
        >>> dirs = get_allowed_base_dirs()
        >>> print(dirs)
        ['./contracts/refs', './odps-refs']
    """
    return get_odps_refs_config().allowed_base_dirs


# Convenience function for checking if URL is allowed
def is_url_allowed(url: str, tenant_config: dict[str, Any] | None = None) -> bool:
    """
    Check if a URL is allowed for external $ref resolution.

    This is a convenience function that uses the global configuration instance
    with optional per-tenant overrides.

    Args:
        url: URL to check
        tenant_config: Optional per-tenant configuration dict (from TenantConfig.odps_refs_config).

    Returns:
        True if URL is allowed, False otherwise

    Example:
        >>> is_allowed = is_url_allowed("https://example.com/schema.json")
        >>> print(is_allowed)
        True
    """
    config = get_odps_refs_config(tenant_config=tenant_config)
    return config.is_url_allowed(url)
