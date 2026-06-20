"""
API Versioning

Version management, backward compatibility, and deprecation handling.
"""

from __future__ import annotations

import datetime

import structlog
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from rest_framework.response import Response

logger = structlog.get_logger(__name__)


class APIVersion:
    """Represents an API version"""

    def __init__(self, major: int, minor: int = 0, patch: int = 0):
        self.major = major
        self.minor = minor
        self.patch = patch

    def __str__(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}"

    def __eq__(self, other) -> bool:
        if not isinstance(other, APIVersion):
            return False
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other) -> bool:
        if not isinstance(other, APIVersion):
            return False
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other) -> bool:
        return self == other or self < other

    def __gt__(self, other) -> bool:
        return not self <= other

    def __ge__(self, other) -> bool:
        return not self < other

    @classmethod
    def parse(cls, version_str: str) -> APIVersion | None:
        """Parse version string (e.g., 'v1', 'v1.0', 'v1.0.0')"""
        try:
            # Remove 'v' prefix if present
            version_str = version_str.lstrip("v")

            parts = version_str.split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0

            return cls(major, minor, patch)
        except (ValueError, IndexError):
            return None

    def is_compatible_with(self, other: APIVersion) -> bool:
        """Check if this version is backward compatible with another"""
        # Same major version is compatible
        return self.major == other.major


class DeprecatedEndpoint:
    """Represents a deprecated endpoint"""

    def __init__(
        self,
        path: str,
        method: str,
        deprecated_since: str,
        sunset_date: str | None = None,
        replacement: str | None = None,
        migration_guide: str | None = None,
    ):
        self.path = path
        self.method = method
        self.deprecated_since = deprecated_since
        self.sunset_date = sunset_date
        self.replacement = replacement
        self.migration_guide = migration_guide

    def is_sunset(self) -> bool:
        """Check if endpoint is sunset (past sunset date)"""
        if not self.sunset_date:
            return False

        try:
            sunset = timezone.datetime.fromisoformat(self.sunset_date.replace("Z", "+00:00"))
            now = timezone.now()
            # Ensure both datetimes are timezone-aware for comparison
            if timezone.is_naive(now):
                now = timezone.make_aware(now, datetime.UTC)
            if timezone.is_naive(sunset):
                sunset = timezone.make_aware(sunset, datetime.UTC)
            return now > sunset
        except (ValueError, AttributeError):
            return False

    def get_warning_header(self) -> str:
        """Generate deprecation warning header value"""
        parts = ['299 - "Deprecated API"']

        if self.sunset_date:
            parts.append(f'sunset="{self.sunset_date}"')

        if self.replacement:
            parts.append(f'link="{self.replacement}"')

        return ", ".join(parts)


class APIVersionManager:
    """
    Manager for API versioning and deprecation.
    """

    # Current API version
    CURRENT_VERSION = APIVersion(1, 0, 0)

    # Supported versions
    SUPPORTED_VERSIONS = [APIVersion(1, 0, 0)]

    # Deprecated endpoints registry
    DEPRECATED_ENDPOINTS: dict[str, DeprecatedEndpoint] = {}

    @classmethod
    def get_version_from_path(cls, path: str) -> APIVersion | None:
        """Extract API version from URL path"""
        # Path format: /api/v1/...
        parts = path.strip("/").split("/")

        if len(parts) >= 2 and parts[0] == "api":
            version_str = parts[1]  # 'v1', 'v2', etc.
            return APIVersion.parse(version_str)

        return None

    @classmethod
    def get_version_from_header(cls, request: HttpRequest) -> APIVersion | None:
        """
        Extract API version from Accept header.

        Supports vendor media type: application/vnd.idh.v1+json
        """
        accept = request.META.get("HTTP_ACCEPT", "")

        if not accept:
            return None

        # Check for vendor media type: application/vnd.idh.v1+json
        # Pattern: application/vnd.idh.v{N}+json or application/vnd.idh.v{N}.{M}+json
        if "application/vnd.idh.v" in accept:
            # Extract version from Accept header
            for part in accept.split(","):
                part = part.strip()
                if "application/vnd.idh.v" in part:
                    # Find the 'v' after 'idh.'
                    idh_pos = part.find("idh.v")
                    if idh_pos != -1:
                        # Extract version number starting after 'v'
                        start = idh_pos + len("idh.v")
                        # Find end of version (before '+' or ';' or end of string)
                        end = part.find("+", start)
                        if end == -1:
                            end = part.find(";", start)
                        if end == -1:
                            end = len(part)

                        version_str = part[start:end].strip()
                        if version_str:
                            return APIVersion.parse(version_str)

        return None

    @classmethod
    def get_request_version(cls, request: HttpRequest) -> APIVersion:
        """Get API version from request (path or header)"""
        # Try path first
        version = cls.get_version_from_path(request.path)
        if version:
            return version

        # Try header
        version = cls.get_version_from_header(request)
        if version:
            return version

        # Default to current version
        return cls.CURRENT_VERSION

    @classmethod
    def is_version_supported(cls, version: APIVersion) -> bool:
        """Check if version is supported"""
        return version in cls.SUPPORTED_VERSIONS

    @classmethod
    def register_deprecated_endpoint(cls, endpoint: DeprecatedEndpoint):
        """Register a deprecated endpoint"""
        key = f"{endpoint.method}:{endpoint.path}"
        cls.DEPRECATED_ENDPOINTS[key] = endpoint

    @classmethod
    def get_deprecated_endpoint(cls, path: str, method: str) -> DeprecatedEndpoint | None:
        """Get deprecated endpoint info"""
        key = f"{method}:{path}"
        return cls.DEPRECATED_ENDPOINTS.get(key)

    @classmethod
    def add_deprecation_warning(cls, response: HttpResponse, path: str, method: str):
        """
        Add deprecation warning to response.

        Adds Warning header (RFC 7234) with deprecation information:
        - 299 status code (deprecated API)
        - Sunset date (if specified)
        - Replacement link (if available)
        """
        endpoint = cls.get_deprecated_endpoint(path, method)
        if endpoint and not endpoint.is_sunset():
            warning = endpoint.get_warning_header()
            response["Warning"] = warning

            # Also add deprecation info in response body for JSON responses
            if hasattr(response, "data") and isinstance(response.data, dict):
                if "meta" not in response.data:
                    response.data["meta"] = {}
                response.data["meta"]["deprecated"] = True
                response.data["meta"]["deprecated_since"] = endpoint.deprecated_since
                if endpoint.sunset_date:
                    response.data["meta"]["sunset_date"] = endpoint.sunset_date
                if endpoint.replacement:
                    response.data["meta"]["replacement"] = endpoint.replacement
                if endpoint.migration_guide:
                    response.data["meta"]["migration_guide"] = endpoint.migration_guide

    @classmethod
    def check_backward_compatibility(
        cls, request_version: APIVersion, endpoint_version: APIVersion
    ) -> tuple[bool, str | None]:
        """
        Check backward compatibility between request and endpoint versions.

        Returns:
            Tuple of (is_compatible, error_message)
        """
        # Same major version is compatible
        if request_version.major == endpoint_version.major:
            return True, None

        # Different major versions are incompatible
        return (
            False,
            f"API version {request_version} is not compatible with endpoint version {endpoint_version}",
        )


class APIVersionMiddleware:
    """
    Middleware for API versioning and deprecation warnings.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request
        response = self.process_request(request)
        if response:
            return response

        # Get response
        response = self.get_response(request)

        # Process response
        response = self.process_response(request, response)

        return response

    def process_request(self, request):
        """Process request for version checking"""
        # Only process API requests
        if not request.path.startswith("/api/"):
            return None

        # Get request version
        version = APIVersionManager.get_request_version(request)

        # Check if version is supported
        if not APIVersionManager.is_version_supported(version):
            return Response(
                {
                    "error": {
                        "code": "UNSUPPORTED_API_VERSION",
                        "message": f"API version {version} is not supported",
                        "http_status": 400,
                        "supported_versions": [
                            str(v) for v in APIVersionManager.SUPPORTED_VERSIONS
                        ],
                        "current_version": str(APIVersionManager.CURRENT_VERSION),
                    }
                },
                status=400,
            )

        # Store version in request
        request.api_version = version

        return None

    def process_response(self, request, response):
        """Process response for deprecation warnings and version headers (Phase 25.6.2)"""
        # Only process API responses
        if not request.path.startswith("/api/"):
            return response

        # Handle None response (root cause fix: test passes None)
        if response is None:
            from django.http import HttpResponse

            response = HttpResponse()

        # Get request version
        version = getattr(request, "api_version", APIVersionManager.CURRENT_VERSION)

        # Add API version headers (Phase 25.6.2)
        response["X-API-Version"] = str(version)
        response["X-API-Supported-Versions"] = ",".join(
            [str(v) for v in APIVersionManager.SUPPORTED_VERSIONS]
        )

        # Add deprecation warning if endpoint is deprecated
        # Root cause fix: Use add_deprecation_warning method which adds Warning header (RFC 7234)
        # This ensures consistency with API_VERSIONING_POLICY.md and test expectations
        deprecated_endpoint = APIVersionManager.get_deprecated_endpoint(
            request.path, request.method
        )
        if deprecated_endpoint and not deprecated_endpoint.is_sunset():
            # Add Warning header (RFC 7234) via add_deprecation_warning method
            APIVersionManager.add_deprecation_warning(response, request.path, request.method)
            # Also add X-API-Deprecated header for explicit deprecation flag
            response["X-API-Deprecated"] = "true"
            if deprecated_endpoint.sunset_date:
                # sunset_date is stored as ISO string, convert to HTTP date format
                try:
                    sunset_dt = timezone.datetime.fromisoformat(
                        deprecated_endpoint.sunset_date.replace("Z", "+00:00")
                    )
                    response["Sunset"] = sunset_dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
                except (ValueError, AttributeError):
                    # If parsing fails, use the string as-is
                    response["Sunset"] = deprecated_endpoint.sunset_date
            if deprecated_endpoint.replacement:
                response["Link"] = f'<{deprecated_endpoint.replacement}>; rel="successor-version"'

        return response
